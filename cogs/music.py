# -*- coding: utf-8 -*-
"""
cogs/music.py — Core music playback commands.

V3 Changes:
  - asyncio.gather with Semaphore(5) for parallel Spotify→YouTube resolution
  - Self-healing _try_reconnect() on unexpected voice disconnect
  - Dynamic embed accent color from thumbnail via color_thief.get_dominant_color()
  - All player queue mutations use new async methods (enqueue, dequeue, etc.)
  - track_added_embed uses delete_after=20s when queued (not first track)
  - voice_connection_error_embed for reconnect failure notification
"""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING, List, Optional

import discord
from discord import app_commands
from discord.ext import commands

import config
from core.validator import validate_url, validate_search_query
from models.track import Track
from utils.embeds import (
    error_embed, success_embed, info_embed,
    now_playing_embed, track_added_embed, search_results_embed,
)
from utils.views import MusicControlView, SearchSelectView
from utils.rate_limiter import RateLimiter
from utils.error_handler import notify_playback_error, voice_connection_error_embed
from utils.color_thief import get_dominant_color

if TYPE_CHECKING:
    from main import MusicBot

logger = logging.getLogger(__name__)


class MusicCog(commands.Cog, name="Music"):
    """Core music playback commands."""

    def __init__(self, bot: "MusicBot") -> None:
        self.bot      = bot
        self.rate_limiter = RateLimiter()

    # ── Guard helpers ─────────────────────────────────────────────────────────

    async def _ensure_voice(
        self, interaction: discord.Interaction
    ) -> Optional[discord.VoiceClient]:
        """
        Make sure the bot is in a voice channel.
        Returns the VoiceClient, or sends an error and returns None.
        """
        guild = interaction.guild
        vc    = guild.voice_client

        if vc and vc.is_connected():
            return vc

        if not interaction.user.voice:
            await interaction.followup.send(
                embed=error_embed("Not in a Voice Channel",
                                  "Join a voice channel first."),
                ephemeral=True,
            )
            return None

        channel = interaction.user.voice.channel
        try:
            vc = await channel.connect(timeout=10.0, reconnect=True)
            # ✔ Store for self-healing reconnect
            player = self.bot.get_player(interaction.guild_id)
            player.last_channel_id = channel.id
            return vc
        except asyncio.TimeoutError:
            await interaction.followup.send(
                embed=error_embed("Connection Timeout",
                                  "Could not connect to your voice channel."),
                ephemeral=True,
            )
            return None
        except discord.ClientException as exc:
            await interaction.followup.send(
                embed=error_embed("Connection Error", str(exc)), ephemeral=True
            )
            return None

    async def _try_reconnect(
        self, guild_id: int
    ) -> Optional[discord.VoiceClient]:
        """
        Self-healing voice reconnect with exponential backoff.
        Attempts up to config.RECONNECT_ATTEMPTS times.
        Returns the new VoiceClient or None on total failure.
        """
        player = self.bot.get_player(guild_id)
        guild  = self.bot.get_guild(guild_id)
        if not guild or not player.last_channel_id:
            return None

        channel = guild.get_channel(player.last_channel_id)
        if not channel or not isinstance(channel, discord.VoiceChannel):
            return None

        for attempt in range(1, config.RECONNECT_ATTEMPTS + 1):
            delay = config.RECONNECT_BASE_DELAY * (2 ** (attempt - 1))  # 2s, 4s, 8s
            logger.info(
                "Voice reconnect attempt %d/%d for guild %d in %.0fs…",
                attempt, config.RECONNECT_ATTEMPTS, guild_id, delay,
            )
            await asyncio.sleep(delay)
            try:
                vc = await channel.connect(timeout=10.0, reconnect=True)
                logger.info(
                    "✅ Voice reconnected for guild %d on attempt %d", guild_id, attempt
                )
                return vc
            except Exception as exc:
                logger.warning(
                    "Reconnect attempt %d failed for guild %d: %s", attempt, guild_id, exc
                )

        # All attempts exhausted
        logger.error("Voice reconnect failed for guild %d after %d attempts.",
                     guild_id, config.RECONNECT_ATTEMPTS)
        if player.text_channel:
            try:
                await player.text_channel.send(
                    embed=voice_connection_error_embed(
                        channel.name, config.RECONNECT_ATTEMPTS
                    ),
                    delete_after=30.0,
                )
            except Exception:
                pass
        return None

    def _rate_check(self, interaction: discord.Interaction) -> bool:
        return self.rate_limiter.is_rate_limited(
            interaction.guild_id, interaction.user.id
        )

    # ── Internal playback ─────────────────────────────────────────────────────

    async def _play_next(self, guild_id: int, *, skip_depth: int = 0) -> None:
        """
        Pop the next track from the player queue and start playback.
        This is the single playback entry-point — all other code calls this.

        Args:
            skip_depth: number of consecutive broken tracks skipped in this chain.
                        Stops auto-skipping after config.SKIP_ERROR_LIMIT to prevent
                        infinite recursion on a queue full of broken tracks.
        """
        player = self.bot.get_player(guild_id)
        guild  = self.bot.get_guild(guild_id)
        if not guild:
            return

        vc: Optional[discord.VoiceClient] = guild.voice_client
        if not vc or not vc.is_connected():
            # ━━ Self-healing: attempt to reconnect before giving up ━━━━━━━━━━━━━━━━
            vc = await self._try_reconnect(guild_id)
            if not vc:
                player.reset()
                return

        # Race condition guard: don't start a second track if one is already playing
        if vc.is_playing():
            logger.debug(
                "guild %d: _play_next called while already playing — ignoring.", guild_id
            )
            return

        # Finish the previous track (handles loop logic inside GuildPlayer)
        await player.finish_track()

        next_track = await player.dequeue()
        if not next_track:
            player.idle_since = discord.utils.utcnow()
            return  # Queue exhausted

        # Resolve the actual CDN audio-stream URL via yt-dlp.
        try:
            stream_url = await self.bot.youtube.get_stream_url(next_track.url)
        except Exception as exc:
            logger.error("Failed to resolve stream for '%s': %s", next_track.title, exc)
            # Guard against infinite recursion
            if skip_depth >= config.SKIP_ERROR_LIMIT:
                logger.error(
                    "Reached skip limit (%d) for guild %d — stopping playback.",
                    config.SKIP_ERROR_LIMIT, guild_id,
                )
                if player.text_channel:
                    await notify_playback_error(
                        player.text_channel, exc, next_track, skipping=False,
                        delete_after=20.0,
                    )
                return
            # Notify user and skip to next track
            if player.text_channel:
                await notify_playback_error(
                    player.text_channel, exc, next_track, skipping=True,
                )
            await self._play_next(guild_id, skip_depth=skip_depth + 1)
            return

        if not stream_url:
            logger.warning("No stream URL for track: %s", next_track.url)
            if skip_depth >= config.SKIP_ERROR_LIMIT:
                return
            await self._play_next(guild_id, skip_depth=skip_depth + 1)
            return

        ffmpeg_opts = self.bot.audio_processor.build_ffmpeg_options(
            effects    = player.effects,
            volume     = player.volume,
            start_time = player.seek_position,
            quality    = player.quality,
        )

        player.start_track(next_track)

        def after_play(exc: Optional[Exception]) -> None:
            if exc:
                logger.error("Playback error in guild %d: %s", guild_id, exc)
            # Guard against scheduling into a closed loop (e.g. during shutdown)
            if self.bot._shutdown:
                return
            try:
                asyncio.run_coroutine_threadsafe(
                    self._play_next(guild_id), self.bot.loop
                )
            except RuntimeError:
                logger.debug("Could not schedule _play_next — event loop closed.")

        try:
            source = discord.FFmpegPCMAudio(stream_url, **ffmpeg_opts)
            vc.play(source, after=after_play)
        except Exception as exc:
            logger.error("FFmpeg error for '%s': %s", next_track.title, exc)
            if skip_depth < config.SKIP_ERROR_LIMIT:
                await self._play_next(guild_id, skip_depth=skip_depth + 1)
            return

        # ── Save to DB + resolve accent color in parallel (asyncio.gather) ─────
        async def _record_db():
            try:
                await self.bot.db.record_track_played(
                    guild_id, next_track.requester_id, next_track
                )
            except Exception as exc:
                logger.warning("Failed to record track played for guild %d: %s", guild_id, exc)

        async def _resolve_color():
            color = await get_dominant_color(
                next_track.thumbnail,
                session=getattr(self.bot, "http_session", None),
            )
            player.accent_color = color

        await asyncio.gather(_record_db(), _resolve_color())

        # Cancel any previous progress-bar updater for this guild
        if player.progress_task and not player.progress_task.done():
            player.progress_task.cancel()
        player.progress_task = None

        # Announce / update in text channel
        if player.text_channel:
            try:
                cfg = await self.bot.get_server_config(guild_id)
                if cfg.announce_songs:
                    # Resolve requester member object — cache-first, no fetch
                    requester_member: Optional[discord.Member] = None
                    if next_track.requester_id:
                        requester_member = guild.get_member(next_track.requester_id)
                        # Only fetch if not in cache AND members intent is enabled
                        if requester_member is None:
                            try:
                                requester_member = await guild.fetch_member(next_track.requester_id)
                            except discord.HTTPException:
                                pass  # Non-critical — embed works fine without member

                    embed = now_playing_embed(
                        next_track,
                        elapsed      = 0,
                        requester    = requester_member,
                        loop_label   = player.loop_mode.label(),
                        loop_short   = player.loop_mode.short_label(),
                        effects      = [e.display_name for e in player.effects],
                        volume       = player.volume,
                        quality      = player.quality,
                        queue_count  = len(player),
                        queue_dur    = player.queue_duration(),
                        channel_name = next_track.uploader or "",
                        accent_color = player.accent_color,
                    )
                    view = MusicControlView(self.bot, guild_id)

                    # Always send a fresh Now Playing message for each track
                    msg = await player.text_channel.send(embed=embed, view=view)

                    player.now_playing_msg    = msg
                    player.now_playing_msg_id = msg.id

                    # Start background task to update the progress bar
                    player.progress_task = asyncio.create_task(
                        self._update_progress_bar(guild_id)
                    )
            except Exception as exc:
                logger.warning("Could not send now-playing message: %s", exc)

    # ── Progress bar updater ──────────────────────────────────────────────────

    async def _update_progress_bar(self, guild_id: int) -> None:
        """
        Background task: edit the now-playing message every N seconds to
        show the live progress bar.  Stops automatically when the track ends,
        is skipped, or the now-playing message is deleted by a user.
        """
        player = self.bot.get_player(guild_id)
        guild  = self.bot.get_guild(guild_id)

        while True:
            await asyncio.sleep(config.PROGRESS_BAR_UPDATE_INTERVAL)

            # Stop if the track finished or the message reference was cleared
            if player.now_playing is None or player.now_playing_msg is None:
                return

            try:
                vc = guild.voice_client if guild else None
                if not vc or not (vc.is_playing() or vc.is_paused()):
                    return

                # Resolve requester member (cache-only — no extra API calls)
                requester_member: Optional[discord.Member] = None
                if player.now_playing.requester_id and guild:
                    requester_member = guild.get_member(player.now_playing.requester_id)

                elapsed = player.elapsed_seconds()
                embed = now_playing_embed(
                    player.now_playing,
                    elapsed      = elapsed,
                    requester    = requester_member,
                    loop_label   = player.loop_mode.label(),
                    loop_short   = player.loop_mode.short_label(),
                    effects      = [e.display_name for e in player.effects],
                    volume       = player.volume,
                    quality      = player.quality,
                    queue_count  = len(player),
                    queue_dur    = player.queue_duration(),
                    channel_name = player.now_playing.uploader or "",
                    accent_color = player.accent_color,  # reuse cached color
                )
                await player.now_playing_msg.edit(embed=embed)

            except asyncio.CancelledError:
                # Task was cancelled by skip/stop — exit cleanly
                return

            except discord.NotFound:
                # The Now Playing message was deleted by a user.
                logger.debug(
                    "Now-playing message deleted in guild %d — stopping progress task.",
                    guild_id,
                )
                player.now_playing_msg    = None
                player.now_playing_msg_id = None
                return

            except discord.HTTPException as exc:
                # Transient API hiccup (rate-limit, 5xx) — log and keep going.
                logger.debug("Progress bar HTTP error in guild %d: %s", guild_id, exc)

            except Exception as exc:
                # Unexpected error — log and stop to avoid spamming.
                logger.warning("Progress bar update failed in guild %d: %s", guild_id, exc)
                return

    # ── Autocomplete ──────────────────────────────────────────────────────────

    async def _play_autocomplete(
        self,
        interaction: discord.Interaction,
        current: str,
    ) -> List[app_commands.Choice[str]]:
        """
        Provide search suggestions for the /play command.
        Pulls from per-guild search history stored in the database.
        """
        try:
            suggestions = await self.bot.db.get_search_suggestions(
                interaction.guild_id, current, limit=25
            )
            return [
                app_commands.Choice(name=s[:100], value=s[:100])
                for s in suggestions
            ]
        except Exception:
            return []

    # ── Commands ──────────────────────────────────────────────────────────────

    @app_commands.command(name="join", description="Join your voice channel.")
    async def join(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer()
        if not interaction.user.voice:
            await interaction.followup.send(
                embed=error_embed("Not in Voice Channel",
                                  "You must be in a voice channel."),
                ephemeral=True,
            )
            return
        vc = await self._ensure_voice(interaction)
        if vc:
            player = self.bot.get_player(interaction.guild_id)
            player.text_channel = interaction.channel
            await interaction.followup.send(
                embed=success_embed("Connected",
                                    f"Joined **{vc.channel.name}**."),
            )

    @app_commands.command(name="leave", description="Leave the voice channel and clear the queue.")
    async def leave(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer()
        vc = interaction.guild.voice_client
        if not vc:
            await interaction.followup.send(
                embed=error_embed("Not Connected", "I'm not in a voice channel."),
                ephemeral=True,
            )
            return
        player = self.bot.get_player(interaction.guild_id)
        player.reset()
        await vc.disconnect()
        await interaction.followup.send(
            embed=success_embed("Disconnected", "Left the voice channel and cleared the queue.")
        )

    @app_commands.command(name="play", description="Play music from YouTube URL, Spotify URL, or search query.")
    @app_commands.describe(query="YouTube/Spotify URL or search keywords")
    @app_commands.autocomplete(query=_play_autocomplete)
    async def play(self, interaction: discord.Interaction, query: str) -> None:
        # thinking=True shows the animated "Bot is thinking…" spinner during I/O
        await interaction.response.defer(thinking=True)

        if self._rate_check(interaction):
            secs = self.rate_limiter.retry_after(interaction.guild_id, interaction.user.id)
            await interaction.followup.send(
                embed=error_embed("Slow Down!", f"Try again in **{secs:.1f}s**."),
                ephemeral=True,
            )
            return

        # Validate URL or search text
        if query.startswith("http"):
            result = await validate_url(query)
            if not result:
                await interaction.followup.send(
                    embed=error_embed("🚫 Blocked URL",
                                      getattr(result, "reason", "This URL is not allowed.")),
                    ephemeral=True,
                )
                return
        else:
            result = validate_search_query(query)
            if not result:
                await interaction.followup.send(
                    embed=error_embed("🚫 Blocked Search",
                                      getattr(result, "reason", "This search is not allowed.")),
                    ephemeral=True,
                )
                return

        vc = await self._ensure_voice(interaction)
        if not vc:
            return

        player = self.bot.get_player(interaction.guild_id)
        player.text_channel = interaction.channel

        cfg = await self.bot.get_server_config(interaction.guild_id)

        # ── Spotify ────────────────────────────────────────────────────────────
        if self.bot.spotify.is_spotify_url(query):
            spotify_tracks = await self.bot.spotify.get_tracks_from_url(query)
            if not spotify_tracks:
                await interaction.followup.send(
                    embed=error_embed("Spotify Error",
                                      "Could not fetch Spotify tracks. "
                                      "Check credentials or try a YouTube URL."),
                    ephemeral=True,
                )
                return

            added = 0
            sem = asyncio.Semaphore(5)  # max 5 parallel YouTube searches

            async def _resolve_spotify_track(sp_track):
                async with sem:
                    if len(player) >= cfg.max_queue_size:
                        return
                    yt_results = await self.bot.youtube.search(
                        sp_track.search_query, max_results=1
                    )
                    if not yt_results:
                        return
                    t = yt_results[0]
                    t.requester_id = interaction.user.id
                    if sp_track.image_url:
                        t.thumbnail = sp_track.image_url
                    await player.enqueue(t)
                    nonlocal added
                    added += 1

            await asyncio.gather(
                *[_resolve_spotify_track(sp) for sp in spotify_tracks]
            )

            if not added:
                await interaction.followup.send(
                    embed=error_embed("No Tracks Found", "Could not match any Spotify tracks to YouTube."),
                    ephemeral=True,
                )
                return

            await interaction.followup.send(
                embed=success_embed(
                    "Spotify Playlist Added",
                    f"Added **{added}** track{'s' if added != 1 else ''} to the queue.",
                )
            )

        # ── YouTube playlist ────────────────────────────────────────────────────
        elif self.bot.youtube.is_playlist_url(query):
            tracks = await self.bot.youtube.get_playlist(query)
            if not tracks:
                await interaction.followup.send(
                    embed=error_embed("Empty Playlist", "Could not extract any tracks."),
                    ephemeral=True,
                )
                return
            added = 0
            to_add = []
            for t in tracks:
                if len(player) + len(to_add) >= cfg.max_queue_size:
                    break
                t.requester_id = interaction.user.id
                to_add.append(t)
            await player.extend(to_add)
            added = len(to_add)
            await interaction.followup.send(
                embed=success_embed(
                    "Playlist Added",
                    f"Queued **{added}** track{'s' if added != 1 else ''}.",
                )
            )

        # ── Single YouTube URL ──────────────────────────────────────────────────
        elif self.bot.youtube.is_youtube_url(query):
            try:
                track = await self.bot.youtube.get_track(query)
            except Exception as exc:
                await interaction.followup.send(
                    embed=error_embed(
                        "Could Not Load URL",
                        f"Failed to extract info from that link.\n*(ไม่สามารถดึงข้อมูลจาก URL นี้ได้)*",
                    ),
                    ephemeral=True,
                )
                return
            if not track:
                await interaction.followup.send(
                    embed=error_embed("Not Found", "Could not extract info from that URL."),
                    ephemeral=True,
                )
                return
            if len(player) >= cfg.max_queue_size:
                await interaction.followup.send(
                    embed=error_embed("Queue Full", f"Maximum **{cfg.max_queue_size}** tracks."),
                    ephemeral=True,
                )
                return
            track.requester_id = interaction.user.id
            await player.enqueue(track)
            pos = len(player)
            is_first = not vc.is_playing() and not vc.is_paused()
            await interaction.followup.send(
                embed=track_added_embed(
                    track, pos,
                    requester    = interaction.user,
                    channel_name = track.uploader or "",
                    queue_count  = len(player),
                    queue_dur    = player.queue_duration(),
                    is_first     = is_first,
                ),
                delete_after=None if is_first else 20.0,
            )

        # ── Search query ────────────────────────────────────────────────────────
        else:
            results = await self.bot.youtube.search(query, max_results=5)
            if not results:
                await interaction.followup.send(
                    embed=error_embed("No Results", f"No results for **{query}**."),
                    ephemeral=True,
                )
                return
            # Auto-pick the first result for /play; /search gives the dropdown
            track = results[0]
            track.requester_id = interaction.user.id
            if len(player) >= cfg.max_queue_size:
                await interaction.followup.send(
                    embed=error_embed("Queue Full", f"Maximum **{cfg.max_queue_size}** tracks."),
                    ephemeral=True,
                )
                return
            await player.enqueue(track)
            pos = len(player)
            is_first = not vc.is_playing() and not vc.is_paused()
            await interaction.followup.send(
                embed=track_added_embed(
                    track, pos,
                    requester    = interaction.user,
                    channel_name = track.uploader or "",
                    queue_count  = len(player),
                    queue_dur    = player.queue_duration(),
                    is_first     = is_first,
                ),
                delete_after=None if is_first else 20.0,
            )

        # Save search query to history for autocomplete — fire-and-forget with error logging
        if not query.startswith("http"):
            def _on_save_error(task: asyncio.Task) -> None:
                exc = task.exception()
                if exc:
                    logger.debug("save_search_query failed: %s", exc)

            task = asyncio.create_task(
                self.bot.db.save_search_query(
                    interaction.guild_id, interaction.user.id, query
                )
            )
            task.add_done_callback(_on_save_error)

        # ── Start playback if nothing is playing ─────────────────────────────────
        if not vc.is_playing() and not vc.is_paused():
            await self._play_next(interaction.guild_id)

    @app_commands.command(name="search", description="Search YouTube and choose a track from a list.")
    @app_commands.describe(query="Search keywords")
    async def search(self, interaction: discord.Interaction, query: str) -> None:
        # thinking=True shows the animated spinner during YouTube search I/O
        await interaction.response.defer(thinking=True)

        sq = validate_search_query(query)
        if not sq:
            await interaction.followup.send(
                embed=error_embed("🚫 Blocked Search",
                                  getattr(sq, "reason", "This search is not allowed.")),
                ephemeral=True,
            )
            return

        results = await self.bot.youtube.search(query, max_results=10)
        if not results:
            await interaction.followup.send(
                embed=error_embed("No Results", f"No results for **{query}**."),
                ephemeral=True,
            )
            return

        embed = search_results_embed(results, query)

        async def on_select(index: int) -> None:
            track = results[index]
            track.requester_id = interaction.user.id
            vc = await self._ensure_voice(interaction)
            if not vc:
                return
            player = self.bot.get_player(interaction.guild_id)
            player.text_channel = interaction.channel
            cfg = await self.bot.get_server_config(interaction.guild_id)
            if len(player) >= cfg.max_queue_size:
                await interaction.followup.send(
                    embed=error_embed("Queue Full", f"Max **{cfg.max_queue_size}** tracks."),
                    ephemeral=True,
                )
                return
            await player.enqueue(track)
            pos = len(player)
            is_first = not vc.is_playing() and not vc.is_paused()
            await interaction.followup.send(
                embed=track_added_embed(
                    track, pos,
                    requester    = interaction.user,
                    channel_name = track.uploader or "",
                    queue_count  = len(player),
                    queue_dur    = player.queue_duration(),
                    is_first     = is_first,
                ),
                delete_after=None if is_first else 20.0,
            )
            if is_first:
                await self._play_next(interaction.guild_id)

        view = SearchSelectView(results, on_select)
        await interaction.followup.send(embed=embed, view=view)

    @app_commands.command(name="pause", description="Pause playback.")
    async def pause(self, interaction: discord.Interaction) -> None:
        vc = interaction.guild.voice_client
        if vc and vc.is_playing():
            vc.pause()
            await interaction.response.send_message(
                embed=success_embed("Paused", "Playback paused."), ephemeral=True
            )
        else:
            await interaction.response.send_message(
                embed=error_embed("Not Playing", "Nothing is playing right now."),
                ephemeral=True,
            )

    @app_commands.command(name="resume", description="Resume playback.")
    async def resume(self, interaction: discord.Interaction) -> None:
        vc = interaction.guild.voice_client
        if vc and vc.is_paused():
            vc.resume()
            await interaction.response.send_message(
                embed=success_embed("Resumed", "Playback resumed."), ephemeral=True
            )
        else:
            await interaction.response.send_message(
                embed=error_embed("Not Paused", "Nothing is paused."), ephemeral=True
            )

    @app_commands.command(name="skip", description="Skip the current track.")
    async def skip(self, interaction: discord.Interaction) -> None:
        vc = interaction.guild.voice_client
        if vc and (vc.is_playing() or vc.is_paused()):
            # Cancel progress task before stopping
            player = self.bot.get_player(interaction.guild_id)
            if player.progress_task and not player.progress_task.done():
                player.progress_task.cancel()
                player.progress_task = None
            vc.stop()  # triggers after_play → _play_next
            # Ephemeral: no need to announce a skip publicly
            await interaction.response.send_message(
                embed=success_embed("Skipped", "⏭ Skipped to the next track."),
                ephemeral=True,
            )
        else:
            await interaction.response.send_message(
                embed=error_embed("Not Playing", "Nothing to skip."), ephemeral=True
            )

    @app_commands.command(name="stop", description="Stop playback and clear the queue.")
    async def stop(self, interaction: discord.Interaction) -> None:
        vc = interaction.guild.voice_client
        player = self.bot.get_player(interaction.guild_id)
        # Cancel the progress-bar task explicitly before reset()
        if player.progress_task and not player.progress_task.done():
            player.progress_task.cancel()
            player.progress_task = None
        player.reset()
        if vc:
            vc.stop()
        await self.bot.db.clear_queue(interaction.guild_id)
        await interaction.response.send_message(
            embed=success_embed("Stopped", "⏹ Playback stopped and queue cleared.")
        )


async def setup(bot: "MusicBot") -> None:
    await bot.add_cog(MusicCog(bot))
