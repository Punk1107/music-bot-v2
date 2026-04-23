# -*- coding: utf-8 -*-
"""
utils/views.py — Discord UI Views (Buttons, Selects) for the music bot.

V3 Changes:
  - MusicControlView: dynamic button state management via _sync_buttons()
    * ⏭ Skip button shows live queue count badge: "⏭ Skip (3)"
    * ⏭ Skip disabled when nothing is playing
    * 🔀 Shuffle disabled when queue has < 2 tracks
    * 🔁 Loop button emoji & style reflects current LoopMode
  - Two new volume buttons 🔉 / 🔊 (row 1) for ±10% quick nudge
  - update_view() helper refreshes the Now Playing message with new button state
  - QueueView: unchanged (already has good pagination logic)
  - SearchSelectView: unchanged
"""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING, Optional, Callable, Awaitable

import discord

from utils.embeds import error_embed, success_embed, info_embed, queue_embed, now_playing_embed

if TYPE_CHECKING:
    from main import MusicBot

logger = logging.getLogger(__name__)


# ── Music control buttons ─────────────────────────────────────────────────────

class MusicControlView(discord.ui.View):
    """
    Persistent playback-control bar shown under the now-playing embed.

    Row 0: ⏸/▶ Pause/Resume | ⏭ Skip | 🔁 Loop | 🔀 Shuffle | ⏹ Stop
    Row 1: 🔉 Vol -10%       | 🔊 Vol +10%

    Buttons are dynamically enabled/disabled based on real-time player state.
    """

    def __init__(self, bot: "MusicBot", guild_id: int) -> None:
        super().__init__(timeout=None)
        self.bot      = bot
        self.guild_id = guild_id
        # Sync button states on creation
        self._sync_buttons()

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _voice_client(self, interaction: discord.Interaction) -> Optional[discord.VoiceClient]:
        guild = self.bot.get_guild(self.guild_id)
        return guild.voice_client if guild else None

    def _sync_buttons(self) -> None:
        """
        Update button labels and disabled states to match current player state.
        Call this before any edit_message() to keep the UI in sync.
        """
        player = self.bot.get_player(self.guild_id)
        queue_size   = len(player)
        is_playing   = player.now_playing is not None

        for child in self.children:
            if not hasattr(child, "custom_id"):
                continue
            cid = child.custom_id

            if cid == "mb_skip":
                # Show queue count badge; disable when nothing to skip to
                label = f"⏭ Skip"
                if queue_size > 0:
                    label = f"⏭ Skip ({queue_size})"
                child.label    = label
                child.disabled = not is_playing

            elif cid == "mb_shuffle":
                # Shuffle is meaningless with 0 or 1 tracks
                child.disabled = queue_size < 2

            elif cid == "mb_loop":
                # Reflect current loop mode
                child.label = player.loop_mode.label()
                child.style = (
                    discord.ButtonStyle.success
                    if player.loop_mode.value != "off"
                    else discord.ButtonStyle.secondary
                )

            elif cid == "mb_vol_down":
                child.disabled = player.volume <= 0.0

            elif cid == "mb_vol_up":
                child.disabled = player.volume >= 2.0

    async def _check(self, interaction: discord.Interaction) -> bool:
        """Ensure the user is in the same voice channel as the bot."""
        vc = self._voice_client(interaction)
        if not vc:
            await interaction.response.send_message(
                embed=error_embed("Not Connected", "I'm not in a voice channel."),
                ephemeral=True,
            )
            return False
        if not interaction.user.voice:
            await interaction.response.send_message(
                embed=error_embed("Not in Voice", "You need to join a voice channel first."),
                ephemeral=True,
            )
            return False
        if interaction.user.voice.channel != vc.channel:
            await interaction.response.send_message(
                embed=error_embed(
                    "Wrong Channel",
                    f"Join **{vc.channel.name}** to use these controls.",
                ),
                ephemeral=True,
            )
            return False
        return True

    async def _refresh_view(self, interaction: discord.Interaction) -> None:
        """Re-sync button states and edit the Now Playing message in-place."""
        self._sync_buttons()
        try:
            await interaction.response.edit_message(view=self)
        except discord.InteractionResponded:
            # Already responded — try followup edit
            try:
                await interaction.message.edit(view=self)
            except Exception:
                pass

    # ── Row 0: Core controls ──────────────────────────────────────────────────

    @discord.ui.button(
        label="⏸ Pause",
        style=discord.ButtonStyle.secondary,
        custom_id="mb_pause",
        row=0,
    )
    async def pause_resume(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        if not await self._check(interaction):
            return
        vc = self._voice_client(interaction)
        if vc.is_paused():
            vc.resume()
            button.label = "⏸ Pause"
            button.style = discord.ButtonStyle.secondary
        elif vc.is_playing():
            vc.pause()
            button.label = "▶ Resume"
            button.style = discord.ButtonStyle.success  # green = "press to resume"
        self._sync_buttons()
        await interaction.response.edit_message(view=self)

    @discord.ui.button(
        label="⏭ Skip",
        style=discord.ButtonStyle.primary,
        custom_id="mb_skip",
        row=0,
    )
    async def skip(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        if not await self._check(interaction):
            return
        vc = self._voice_client(interaction)
        player = self.bot.get_player(self.guild_id)
        # Cancel progress task immediately so it doesn't edit a stale message
        if player.progress_task and not player.progress_task.done():
            player.progress_task.cancel()
            player.progress_task = None
        if vc and (vc.is_playing() or vc.is_paused()):
            vc.stop()
        await interaction.response.send_message(
            embed=success_embed("Skipped", "⏭ Skipped to the next track."),
            ephemeral=True,
        )

    @discord.ui.button(
        label="🔁 Loop Off",
        style=discord.ButtonStyle.secondary,
        custom_id="mb_loop",
        row=0,
    )
    async def loop(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        if not await self._check(interaction):
            return
        player = self.bot.get_player(self.guild_id)
        player.loop_mode = player.loop_mode.next()
        await self._refresh_view(interaction)

    @discord.ui.button(
        label="🔀 Shuffle",
        style=discord.ButtonStyle.secondary,
        custom_id="mb_shuffle",
        row=0,
    )
    async def shuffle(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        if not await self._check(interaction):
            return
        player = self.bot.get_player(self.guild_id)
        await player.shuffle()
        await interaction.response.send_message(
            embed=success_embed("Shuffled", "🔀 Queue has been shuffled."),
            ephemeral=True,
        )

    @discord.ui.button(
        label="⏹ Stop",
        style=discord.ButtonStyle.danger,
        custom_id="mb_stop",
        row=0,
    )
    async def stop(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        if not await self._check(interaction):
            return
        player = self.bot.get_player(self.guild_id)
        # Cancel progress task before reset
        if player.progress_task and not player.progress_task.done():
            player.progress_task.cancel()
            player.progress_task = None
        player.reset()
        vc = self._voice_client(interaction)
        if vc:
            vc.stop()
            await vc.disconnect()
        await interaction.response.send_message(
            embed=success_embed("Stopped", "⏹ Playback stopped and disconnected."),
            ephemeral=True,
        )
        self.stop()

    # ── Row 1: Volume controls ────────────────────────────────────────────────

    @discord.ui.button(
        label="🔉 Vol -10%",
        style=discord.ButtonStyle.secondary,
        custom_id="mb_vol_down",
        row=1,
    )
    async def vol_down(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        if not await self._check(interaction):
            return
        player      = self.bot.get_player(self.guild_id)
        new_vol     = max(0.0, player.volume - 0.10)
        player.volume = new_vol
        vc = self._voice_client(interaction)
        if vc and vc.source:
            try:
                vc.source.volume = player.volume
            except AttributeError:
                pass
        self._sync_buttons()
        # Rebuild the Now Playing embed with the updated volume, then edit in-place
        guild = self.bot.get_guild(self.guild_id)
        requester_member: Optional[discord.Member] = None
        if player.now_playing and player.now_playing.requester_id and guild:
            requester_member = guild.get_member(player.now_playing.requester_id)
        if player.now_playing:
            embed = now_playing_embed(
                player.now_playing,
                elapsed      = player.elapsed_seconds(),
                requester    = requester_member,
                loop_label   = player.loop_mode.label(),
                loop_short   = player.loop_mode.short_label(),
                effects      = [e.display_name for e in player.effects],
                volume       = player.volume,
                quality      = player.quality,
                queue_count  = len(player),
                queue_dur    = player.queue_duration(),
                channel_name = player.now_playing.uploader or "",
                accent_color = player.accent_color,
            )
            await interaction.response.edit_message(embed=embed, view=self)
        else:
            await interaction.response.edit_message(view=self)

    @discord.ui.button(
        label="🔊 Vol +10%",
        style=discord.ButtonStyle.secondary,
        custom_id="mb_vol_up",
        row=1,
    )
    async def vol_up(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        if not await self._check(interaction):
            return
        player      = self.bot.get_player(self.guild_id)
        new_vol     = min(2.0, player.volume + 0.10)
        player.volume = new_vol
        vc = self._voice_client(interaction)
        if vc and vc.source:
            try:
                vc.source.volume = player.volume
            except AttributeError:
                pass
        self._sync_buttons()
        # Rebuild the Now Playing embed with the updated volume, then edit in-place
        guild = self.bot.get_guild(self.guild_id)
        requester_member: Optional[discord.Member] = None
        if player.now_playing and player.now_playing.requester_id and guild:
            requester_member = guild.get_member(player.now_playing.requester_id)
        if player.now_playing:
            embed = now_playing_embed(
                player.now_playing,
                elapsed      = player.elapsed_seconds(),
                requester    = requester_member,
                loop_label   = player.loop_mode.label(),
                loop_short   = player.loop_mode.short_label(),
                effects      = [e.display_name for e in player.effects],
                volume       = player.volume,
                quality      = player.quality,
                queue_count  = len(player),
                queue_dur    = player.queue_duration(),
                channel_name = player.now_playing.uploader or "",
                accent_color = player.accent_color,
            )
            await interaction.response.edit_message(embed=embed, view=self)
        else:
            await interaction.response.edit_message(view=self)


# ── Search result select ──────────────────────────────────────────────────────

class SearchSelectView(discord.ui.View):
    """
    Dropdown shown after /search — user picks one track to enqueue.
    Calls *callback(index)* with the 0-based track index.
    """

    def __init__(
        self,
        tracks: list,
        callback: Callable[[int], Awaitable[None]],
        *,
        timeout: float = 30.0,
    ) -> None:
        super().__init__(timeout=timeout)
        self._callback = callback

        options = [
            discord.SelectOption(
                label       = (t.title[:98] + "…") if len(t.title) > 99 else t.title,
                description = f"{t.uploader}  ·  {t.duration_str}",
                value       = str(i),
                emoji       = "🎵",
            )
            for i, t in enumerate(tracks[:10])
        ]
        select = discord.ui.Select(
            placeholder = "Choose a track…",
            options     = options,
            custom_id   = "search_select",
        )
        select.callback = self._on_select
        self.add_item(select)

    async def _on_select(self, interaction: discord.Interaction) -> None:
        index = int(interaction.data["values"][0])
        await interaction.response.defer()
        self.stop()
        try:
            await self._callback(index)
        except Exception as exc:
            logger.warning("SearchSelectView callback error: %s", exc)
            try:
                await interaction.followup.send(
                    embed=error_embed("Selection Error", "Something went wrong. Please try again."),
                    ephemeral=True,
                )
            except Exception:
                pass

    async def on_timeout(self) -> None:
        self.stop()


# ── Queue pagination ──────────────────────────────────────────────────────────

class QueueView(discord.ui.View):
    """
    Paginated queue display with ◀ / ▶ navigation buttons.

    Changes (V2.1):
    - _build_embed() renamed to build_embed() — public API
    - Buttons are disabled when on first / last page
    - Refresh button to re-read the live queue
    - Page indicator in button labels
    """

    PER_PAGE = 10

    def __init__(
        self,
        bot:         "MusicBot",
        guild_id:    int,
        guild_name:  str = "",
        *,
        timeout: float = 120.0,
    ) -> None:
        super().__init__(timeout=timeout)
        self.bot        = bot
        self.guild_id   = guild_id
        self.guild_name = guild_name
        self.page       = 1
        self._update_buttons()

    def build_embed(self) -> discord.Embed:
        """Build and return the queue embed for the current page (public)."""
        player = self.bot.get_player(self.guild_id)
        tracks = player.as_list()
        return queue_embed(
            tracks,
            guild_name     = self.guild_name,
            now_playing    = player.now_playing,
            page           = self.page,
            per_page       = self.PER_PAGE,
            total_duration = player.queue_duration(),
        )

    # Keep the private alias for any internal legacy calls
    _build_embed = build_embed

    def _max_pages(self) -> int:
        player = self.bot.get_player(self.guild_id)
        count  = len(player)
        return max(1, -(-count // self.PER_PAGE))

    def _update_buttons(self) -> None:
        """Disable/enable navigation buttons based on current page."""
        max_pages = self._max_pages()
        for child in self.children:
            if hasattr(child, "custom_id"):
                if child.custom_id == "queue_prev":
                    child.disabled = self.page <= 1
                    child.label    = "◀ Prev"
                elif child.custom_id == "queue_next":
                    child.disabled = self.page >= max_pages
                    child.label    = "Next ▶"
                elif child.custom_id == "queue_page_indicator":
                    child.label    = f"📄 {self.page}/{max_pages}"

    @discord.ui.button(label="◀ Prev", style=discord.ButtonStyle.secondary, custom_id="queue_prev")
    async def prev_page(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        if self.page > 1:
            self.page -= 1
        self._update_buttons()
        await interaction.response.edit_message(embed=self.build_embed(), view=self)

    @discord.ui.button(label="📄 1/1", style=discord.ButtonStyle.secondary, custom_id="queue_page_indicator", disabled=True)
    async def page_indicator(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        await interaction.response.defer()

    @discord.ui.button(label="Next ▶", style=discord.ButtonStyle.secondary, custom_id="queue_next")
    async def next_page(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        if self.page < self._max_pages():
            self.page += 1
        self._update_buttons()
        await interaction.response.edit_message(embed=self.build_embed(), view=self)

    @discord.ui.button(label="🔄 Refresh", style=discord.ButtonStyle.primary, custom_id="queue_refresh")
    async def refresh(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        """Re-read the live queue and update the embed."""
        self._update_buttons()
        await interaction.response.edit_message(embed=self.build_embed(), view=self)
