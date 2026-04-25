# -*- coding: utf-8 -*-
"""
main.py — Music Bot V2 entry point.

V3 Changes:
  - AudioBackend abstraction: bot.audio_backend = create_backend(config.AUDIO_BACKEND)
  - CircuitBreaker instances for YouTube and Spotify (bot.yt_breaker, bot.sp_breaker)
  - NLUPipeline wired as bot.nlu (feature-flagged via NLU_ENABLED)
  - on_ready: queue auto-restore from DB (+ auto-resume if AUTO_RESUME=true)
  - on_application_command_error: forwards full traceback to DEV_LOG_CHANNEL_ID
  - /chat command registered for NLU (only when NLU_ENABLED=true)
"""

from __future__ import annotations

import asyncio
import logging
import signal
from typing import Optional

import aiohttp
import discord
from discord.ext import commands, tasks

import config
from config import setup_logging

# ── Boot logging before anything else ────────────────────────────────────────
setup_logging()
logger = logging.getLogger(__name__)

# ── Core modules ────────────────────────────────────────────────────────────────────
from core.database       import DatabaseManager
from core.youtube        import YouTubeExtractor
from core.spotify        import SpotifyExtractor
from core.audio          import AudioEffectsProcessor
from core.audio_backend  import AudioBackend, create_backend
from core.circuit_breaker import CircuitBreaker
from core.nlu            import NLUPipeline
from core.player         import GuildPlayer
from models.server_config import ServerConfig
from utils.error_handler  import command_error_embed, forward_to_dev_channel

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

    Owns all shared singletons (DB, extractors, audio processor, backends)
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

        # ── P3-1: Audio backend (FFmpeg by default, Lavalink-ready) ──────────
        self.audio_backend: AudioBackend = create_backend(config.AUDIO_BACKEND)

        # ── P2-2: Circuit breakers for external APIs ──────────────────────────
        self.yt_breaker: CircuitBreaker = CircuitBreaker(
            name              = "youtube",
            failure_threshold = config.CIRCUIT_BREAKER_THRESHOLD,
            recovery_window   = config.CIRCUIT_BREAKER_WINDOW,
        )
        self.sp_breaker: CircuitBreaker = CircuitBreaker(
            name              = "spotify",
            failure_threshold = config.CIRCUIT_BREAKER_THRESHOLD,
            recovery_window   = config.CIRCUIT_BREAKER_WINDOW,
        )

        # ── P4-1: NLU pipeline (feature-flagged) ──────────────────────────────
        self.nlu = NLUPipeline()

        # ── Shared HTTP session (for thumbnail color extraction, etc.) ─────────
        # Initialised in setup_hook() once the event loop is running.
        self.http_session: Optional[aiohttp.ClientSession] = None

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
            self._evict_config_cache_if_needed()
        return self._config_cache[guild_id]

    async def save_server_config(self, cfg: ServerConfig) -> None:
        self._config_cache[cfg.guild_id] = cfg
        await self.db.save_server_config(cfg)

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    async def setup_hook(self) -> None:
        """Called once by discord.py before connecting to the gateway."""
        # Create the shared HTTP session here — event loop is running
        self.http_session = aiohttp.ClientSession(
            connector=aiohttp.TCPConnector(limit=20, ttl_dns_cache=300),
            timeout=aiohttp.ClientTimeout(total=10.0),
            headers={"User-Agent": "MusicBot/2.0 (Discord)"},
        )
        logger.info("Shared aiohttp.ClientSession created.")

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

        # ── P2-3: Auto-restore queues from DB on startup ──────────────────────
        await self._restore_queues_on_startup()

    async def _restore_queues_on_startup(self) -> None:
        """
        P2-3: Restore persisted queues for all connected guilds.

        For each guild where the bot is in a voice channel (or was previously),
        loads the saved queue from SQLite into the in-memory GuildPlayer.

        If AUTO_RESUME=true, also rejoins the voice channel and starts playback.
        Otherwise, the queue is silently restored and will play on the next /play.
        """
        restored = 0
        for guild in self.guilds:
            try:
                tracks = await self.db.load_queue(guild.id)
                if not tracks:
                    continue
                player = self.get_player(guild.id)
                await player.extend(tracks)
                restored += 1
                logger.info(
                    "Restored %d tracks for guild %d from DB.",
                    len(tracks), guild.id,
                )

                if config.AUTO_RESUME:
                    await self._try_auto_resume(guild, player)

            except Exception as exc:
                logger.warning(
                    "Failed to restore queue for guild %d: %s", guild.id, exc
                )

        if restored:
            logger.info("Queue restore complete: %d guild(s) restored.", restored)

    async def _try_auto_resume(self, guild: discord.Guild, player: GuildPlayer) -> None:
        """
        Attempt to rejoin the saved voice channel and resume playback.
        Called only when AUTO_RESUME=true.
        """
        if not player.last_channel_id:
            return
        channel = guild.get_channel(player.last_channel_id)
        if not channel or not isinstance(channel, discord.VoiceChannel):
            return
        try:
            vc = await channel.connect(timeout=10.0, reconnect=True)
            logger.info(
                "AUTO_RESUME: Rejoined VC '%s' in guild %d.",
                channel.name, guild.id,
            )
            # Trigger playback via the music cog's _play_next
            music_cog = self.cogs.get("Music")
            if music_cog and hasattr(music_cog, "_play_next"):
                await music_cog._play_next(guild.id)
        except Exception as exc:
            logger.warning(
                "AUTO_RESUME: Failed to rejoin VC for guild %d: %s", guild.id, exc
            )

    async def close(self) -> None:
        """Graceful shutdown: persist all queues and close DB before disconnecting."""
        if self._shutdown:
            return
        self._shutdown = True
        logger.info("Shutting down…")

        for guild_id, player in list(self._players.items()):
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

        # Close shared HTTP session
        if self.http_session and not self.http_session.closed:
            await self.http_session.close()
            logger.info("Shared aiohttp.ClientSession closed.")

        # Close the persistent DB connection cleanly
        try:
            await self.db.close()
        except Exception as exc:
            logger.warning("DB close error during shutdown: %s", exc)

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

    def _evict_config_cache_if_needed(self) -> None:
        """Evict the oldest entry when the config cache exceeds 100 guilds."""
        max_size = 100
        if len(self._config_cache) > max_size:
            oldest_key = next(iter(self._config_cache))
            del self._config_cache[oldest_key]

    async def on_application_command_error(
        self, interaction: discord.Interaction, error: Exception
    ) -> None:
        """
        P2-5: Global slash-command error handler.

        Sends a polite 'Command Failed' embed to the user, AND forwards the
        full traceback to the configured DEV_LOG_CHANNEL_ID (if set).
        """
        logger.error(
            "Command error in guild %s: %s", interaction.guild_id, error, exc_info=True
        )

        # ── Forward to dev channel (non-blocking, swallows errors) ──────────
        asyncio.create_task(
            forward_to_dev_channel(
                self,
                error,
                context = "on_application_command_error",
                guild_id = interaction.guild_id,
                user_id  = interaction.user.id if interaction.user else None,
                command  = (
                    interaction.command.name
                    if interaction.command else None
                ),
            )
        )

        # ── User-facing polite message ────────────────────────────────────────
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

                # 4) Send bilingual farewell message (auto-deletes after 15s)
                if player.text_channel:
                    try:
                        idle_mins = int(idle_secs // 60)
                        farewell_embed = discord.Embed(
                            title       = "💤 Left Voice Channel — Idle Timeout",
                            description = (
                                f"No listeners for **{idle_mins} minute{'s' if idle_mins != 1 else ''}** — "
                                "disconnected to save resources.\n"
                                f"*(บอทไม่มีคนฟังนานกว่า **{idle_mins} นาที** "
                                "ออกจากห้องเสียงเพื่อประหยัดทรัพยากรแล้วนะครับ ❤)*"
                            ),
                            colour      = 0xFEE75C,
                        )
                        farewell_embed.set_footer(
                            text="Use /play when you're ready to listen again.  "
                                 "*(พิมพ์ /play เมื่อพร้อมฟังอีกครั้งนะครับ)*"
                        )
                        await player.text_channel.send(
                            embed=farewell_embed
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
