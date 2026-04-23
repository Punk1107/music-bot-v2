# -*- coding: utf-8 -*-
"""
utils/views.py — Discord UI Views (Buttons, Selects) for the music bot.
"""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING, Optional

import discord

from utils.embeds import error_embed, queue_embed

if TYPE_CHECKING:
    from main import MusicBot

logger = logging.getLogger(__name__)


# ── Music control buttons ─────────────────────────────────────────────────────

class MusicControlView(discord.ui.View):
    """
    Persistent playback-control bar shown under the now-playing embed.
    Buttons: ⏸/▶ Pause/Resume | ⏭ Skip | 🔁 Loop | 🔀 Shuffle | ⏹ Stop
    """

    def __init__(self, bot: "MusicBot", guild_id: int) -> None:
        super().__init__(timeout=None)
        self.bot      = bot
        self.guild_id = guild_id

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _voice_client(self, interaction: discord.Interaction) -> Optional[discord.VoiceClient]:
        guild = self.bot.get_guild(self.guild_id)
        return guild.voice_client if guild else None

    async def _check(self, interaction: discord.Interaction) -> bool:
        """Ensure the user is in the same voice channel."""
        vc = self._voice_client(interaction)
        if not vc:
            await interaction.response.send_message(
                embed=error_embed("Not Connected", "I'm not in a voice channel."),
                ephemeral=True,
            )
            return False
        if not interaction.user.voice or interaction.user.voice.channel != vc.channel:
            await interaction.response.send_message(
                embed=error_embed("Wrong Channel", "Join my voice channel first."),
                ephemeral=True,
            )
            return False
        return True

    # ── Buttons ───────────────────────────────────────────────────────────────

    @discord.ui.button(label="⏸", style=discord.ButtonStyle.secondary, custom_id="mb_pause")
    async def pause_resume(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        if not await self._check(interaction):
            return
        vc = self._voice_client(interaction)
        if vc.is_paused():
            vc.resume()
            button.label = "⏸"
            await interaction.response.edit_message(view=self)
        elif vc.is_playing():
            vc.pause()
            button.label = "▶"
            await interaction.response.edit_message(view=self)
        else:
            await interaction.response.defer()

    @discord.ui.button(label="⏭", style=discord.ButtonStyle.primary, custom_id="mb_skip")
    async def skip(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        if not await self._check(interaction):
            return
        vc = self._voice_client(interaction)
        # Cancel progress task immediately so it doesn't edit stale message (Bug #4)
        player = self.bot.get_player(self.guild_id)
        if player.progress_task and not player.progress_task.done():
            player.progress_task.cancel()
            player.progress_task = None
        if vc and vc.is_playing():
            vc.stop()
        await interaction.response.send_message("⏭ Skipped.", ephemeral=True, delete_after=3)

    @discord.ui.button(label="🔁", style=discord.ButtonStyle.secondary, custom_id="mb_loop")
    async def loop(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        if not await self._check(interaction):
            return
        player = self.bot.get_player(self.guild_id)
        player.loop_mode = player.loop_mode.next()
        button.label = {
            "off":   "🔁",
            "track": "🔂",
            "queue": "🔁Q",
        }.get(player.loop_mode.value, "🔁")
        await interaction.response.edit_message(view=self)

    @discord.ui.button(label="🔀", style=discord.ButtonStyle.secondary, custom_id="mb_shuffle")
    async def shuffle(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        if not await self._check(interaction):
            return
        player = self.bot.get_player(self.guild_id)
        player.shuffle()
        await interaction.response.send_message("🔀 Queue shuffled.", ephemeral=True, delete_after=3)

    @discord.ui.button(label="⏹", style=discord.ButtonStyle.danger, custom_id="mb_stop")
    async def stop(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        if not await self._check(interaction):
            return
        player = self.bot.get_player(self.guild_id)
        player.reset()
        vc = self._voice_client(interaction)
        if vc:
            vc.stop()
            await vc.disconnect()
        await interaction.response.send_message("⏹ Stopped and disconnected.", ephemeral=True)
        self.stop()


# ── Search result select ──────────────────────────────────────────────────────

class SearchSelectView(discord.ui.View):
    """
    Dropdown shown after /search — user picks one track to enqueue.
    Calls *callback(index)* with the 0-based track index.
    """

    def __init__(
        self,
        tracks: list,
        callback,
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
        await self._callback(index)

    async def on_timeout(self) -> None:
        self.stop()


# ── Queue pagination ──────────────────────────────────────────────────────────

class QueueView(discord.ui.View):
    """
    Paginated queue display with ◀ / ▶ navigation buttons.

    Improvements (V2):
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

    def _build_embed(self) -> discord.Embed:
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
                    child.label    = "◀"
                elif child.custom_id == "queue_next":
                    child.disabled = self.page >= max_pages
                    child.label    = "▶"
                elif child.custom_id == "queue_page_indicator":
                    child.label    = f"📄 {self.page}/{max_pages}"

    @discord.ui.button(label="◀", style=discord.ButtonStyle.secondary, custom_id="queue_prev")
    async def prev_page(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        if self.page > 1:
            self.page -= 1
        self._update_buttons()
        await interaction.response.edit_message(embed=self._build_embed(), view=self)

    @discord.ui.button(label="📄 1/1", style=discord.ButtonStyle.secondary, custom_id="queue_page_indicator", disabled=True)
    async def page_indicator(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        await interaction.response.defer()

    @discord.ui.button(label="▶", style=discord.ButtonStyle.secondary, custom_id="queue_next")
    async def next_page(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        if self.page < self._max_pages():
            self.page += 1
        self._update_buttons()
        await interaction.response.edit_message(embed=self._build_embed(), view=self)

    @discord.ui.button(label="🔄 Refresh", style=discord.ButtonStyle.primary, custom_id="queue_refresh")
    async def refresh(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        """Re-read the live queue and update the embed."""
        self._update_buttons()
        await interaction.response.edit_message(embed=self._build_embed(), view=self)

