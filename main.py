# -*- coding: utf-8 -*-
"""
main.py — Music Bot V2 entry point.

Initialises the bot, loads all cogs, wires up event handlers,
and runs the asyncio event loop.
"""

from __future__ import annotations

import asyncio
import logging
import signal
from collections import defaultdict
from typing import Optional

import discord
from discord.ext import commands, tasks

import config
from config import setup_logging

# ── Boot logging before anything else ────────────────────────────────────────
setup_logging()
logger = logging.getLogger(__name__)

# ── Core modules ────────────────────────────────────────────────────────────────────
from core.database import DatabaseManager
from core.youtube  import YouTubeExtractor
from core.spotify  import SpotifyExtractor
from core.audio    import AudioEffectsProcessor
from core.player   import GuildPlayer
from models.server_config import ServerConfig
from utils.error_handler  import command_error_embed

# ── Optional keep-alive webserver ─────────────────────────────────────────────
try:
    import webserver
    _WEBSERVER_AVAILABLE = True
except ImportError:
    _WEBSERVER_AVAILABLE = False

# ── Cog paths ─────────────────────────────────────────────────────────────────
_COGS = [
    "cogs.music",
    "cogs.queue_cog",
    "cogs.effects",
    "cogs.info",
]


# ── Bot class ─────────────────────────────────────────────────────────────────

class MusicBot(commands.Bot):
    """
    Top-level bot class.

    Owns all shared singletons (DB, extractors, audio processor)
    and the per-guild GuildPlayer registry.
    """

    def __init__(self) -> None:
        intents = discord.Intents.default()
        intents.guilds       = True
        intents.voice_states = True
        intents.members      = True
        intents.message_content = True

        super().__init__(
            command_prefix  = "!",
            intents         = intents,
            application_id  = config.APP_ID,
            help_command    = None,
            case_insensitive= True,
        )

        # ── Shared singletons ─────────────────────────────────────────────────
        self.db              = DatabaseManager()
        self.youtube         = YouTubeExtractor()
        self.spotify         = SpotifyExtractor()
        self.audio_processor = AudioEffectsProcessor()

        # ── Per-guild player registry ─────────────────────────────────────────
        self._players: dict[int, GuildPlayer] = {}

        # ── Server config cache ───────────────────────────────────────────────
        self._config_cache: dict[int, ServerConfig] = {}

        self._shutdown = False

    # ── Player registry ───────────────────────────────────────────────────────

    def get_player(self, guild_id: int) -> GuildPlayer:
        """Return the GuildPlayer for *guild_id*, creating one if needed."""
        if guild_id not in self._players:
            self._players[guild_id] = GuildPlayer(guild_id)
        return self._players[guild_id]

    # ── Server config ─────────────────────────────────────────────────────────

    async def get_server_config(self, guild_id: int) -> ServerConfig:
        if guild_id not in self._config_cache:
            self._config_cache[guild_id] = await self.db.get_server_config(guild_id)
        return self._config_cache[guild_id]

    async def save_server_config(self, cfg: ServerConfig) -> None:
        self._config_cache[cfg.guild_id] = cfg
        await self.db.save_server_config(cfg)

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    async def setup_hook(self) -> None:
        """Called once by discord.py before connecting to the gateway."""
        await self.db.initialise()

        for ext in _COGS:
            try:
                await self.load_extension(ext)
                logger.info("Loaded cog: %s", ext)
            except Exception as exc:
                logger.error("Failed to load cog %s: %s", ext, exc, exc_info=True)

        # Sync slash commands (global)
        try:
            synced = await self.tree.sync()
            logger.info("Synced %d application commands.", len(synced))
        except discord.HTTPException as exc:
            logger.error("Failed to sync application commands: %s", exc)

        # Start background tasks
        self._idle_checker.start()
        self._queue_saver.start()

    async def on_ready(self) -> None:
        logger.info(
            "✅ Logged in as %s (ID: %s) — connected to %d guild(s).",
            self.user,
            self.user.id,
            len(self.guilds),
        )
        await self.change_presence(
            activity=discord.Activity(
                type=discord.ActivityType.listening,
                name="🎵 Music | /help",
            )
        )

    async def close(self) -> None:
        """Graceful shutdown: persist all queues before disconnecting."""
        if self._shutdown:
            return
        self._shutdown = True
        logger.info("Shutting down…")

        for guild_id, player in self._players.items():
            try:
                guild = self.get_guild(guild_id)
                if guild and player.now_playing:
                    ch_id = (
                        guild.voice_client.channel.id
                        if guild.voice_client
                        else 0
                    )
                    await self.db.save_queue(
                        guild_id, ch_id, player.as_list()
                    )
            except Exception as exc:
                logger.warning("Failed to persist queue for guild %d: %s", guild_id, exc)

        await super().close()
        logger.info("Bot disconnected cleanly.")

    # ── Event handlers ────────────────────────────────────────────────────────

    async def on_voice_state_update(
        self,
        member:  discord.Member,
        before:  discord.VoiceState,
        after:   discord.VoiceState,
    ) -> None:
        """Auto-disconnect if the bot is left alone in a voice channel."""
        guild_id = member.guild.id
        vc       = member.guild.voice_client

        if not vc or not vc.channel:
            return

        # Non-bot members remaining in bot's channel
        human_listeners = [
            m for m in vc.channel.members if not m.bot
        ]
        if not human_listeners:
            player = self.get_player(guild_id)
            player.idle_since = discord.utils.utcnow()

    async def on_guild_remove(self, guild: discord.Guild) -> None:
        """Clean up state when the bot is removed from a guild."""
        self._players.pop(guild.id, None)
        self._config_cache.pop(guild.id, None)

    async def on_application_command_error(
        self, interaction: discord.Interaction, error: Exception
    ) -> None:
        """Global slash-command error handler — sends a user-friendly error embed."""
        logger.error("Command error in guild %s: %s", interaction.guild_id, error, exc_info=True)
        embed = command_error_embed(error)
        try:
            if interaction.response.is_done():
                await interaction.followup.send(embed=embed, ephemeral=True)
            else:
                await interaction.response.send_message(embed=embed, ephemeral=True)
        except Exception:
            pass

    # ── Background tasks ──────────────────────────────────────────────────────

    @tasks.loop(seconds=30)
    async def _idle_checker(self) -> None:
        """Disconnect the bot from guilds where it has been idle too long."""
        import datetime
        now = discord.utils.utcnow()

        for guild in self.guilds:
            vc = guild.voice_client
            if not vc or not vc.is_connected():
                continue
            if vc.is_playing() or vc.is_paused():
                # Reset idle timer when playing
                player = self.get_player(guild.id)
                player.idle_since = None
                continue

            player = self.get_player(guild.id)
            if player.idle_since is None:
                player.idle_since = now
                continue

            idle_secs = (now - player.idle_since).total_seconds()
            cfg = await self.get_server_config(guild.id)
            if idle_secs >= cfg.auto_disconnect_timeout:
                logger.info(
                    "Auto-disconnecting from guild %d after %ds idle.",
                    guild.id, idle_secs,
                )
                # ── Cleanup before disconnect ────────────────────────────────────
                # 1) Cancel progress bar task
                if player.progress_task and not player.progress_task.done():
                    player.progress_task.cancel()
                    player.progress_task = None

                # 2) Delete the now-playing message
                if player.now_playing_msg:
                    try:
                        await player.now_playing_msg.delete()
                    except Exception:
                        pass
                    player.clear_now_playing_msg()

                # 3) Reset player state
                player.reset()
                await vc.disconnect()

                # 4) Send farewell message (auto-deletes after 15s)
                if player.text_channel:
                    try:
                        farewell_embed = discord.Embed(
                            title       = "💤 ออกจากห้องเสียงแล้ว",
                            description = (
                                f"บอทไม่มีคนฟังนานกว่า **{int(idle_secs // 60)} นาที**\n"
                                "ออกจากห้องเสียงเพื่อประหยัดทรัพยากรแล้วนะครับ \u2764"
                            ),
                            colour      = 0xFEE75C,
                        )
                        farewell_embed.set_footer(text="พิมพ์ /play เมื่อพร้อมฟังอีกครั้งนะครับ")
                        await player.text_channel.send(
                            embed=farewell_embed, delete_after=15.0
                        )
                    except Exception:
                        pass

    @_idle_checker.before_loop
    async def _before_idle_checker(self) -> None:
        await self.wait_until_ready()

    @tasks.loop(minutes=5)
    async def _queue_saver(self) -> None:
        """Periodically persist all active queues to the database."""
        for guild_id, player in self._players.items():
            if not player.is_empty():
                try:
                    guild = self.get_guild(guild_id)
                    ch_id = (
                        guild.voice_client.channel.id
                        if guild and guild.voice_client
                        else 0
                    )
                    await self.db.save_queue(guild_id, ch_id, player.as_list())
                except Exception as exc:
                    logger.warning("Queue auto-save failed for guild %d: %s", guild_id, exc)

    @_queue_saver.before_loop
    async def _before_queue_saver(self) -> None:
        await self.wait_until_ready()


# ── Entry point ───────────────────────────────────────────────────────────────

async def main() -> None:
    # Optional: start keep-alive webserver (for Render / UptimeRobot)
    if _WEBSERVER_AVAILABLE:
        webserver.start()

    bot = MusicBot()

    # Graceful SIGINT / SIGTERM handling
    loop = asyncio.get_running_loop()

    def _shutdown_handler():
        loop.create_task(bot.close())

    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, _shutdown_handler)
        except NotImplementedError:
            pass  # Windows does not support add_signal_handler for all signals

    async with bot:
        await bot.start(config.TOKEN)


if __name__ == "__main__":
    asyncio.run(main())
