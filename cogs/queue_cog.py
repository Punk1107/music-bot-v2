# -*- coding: utf-8 -*-
"""
cogs/queue_cog.py — Queue management commands.

Commands:
  /queue [page]       — Show the current queue (paginated)
  /shuffle            — Shuffle the queue
  /clear              — Clear the entire queue
  /loop               — Cycle loop mode (Off → Track → Queue)
  /remove <position>  — Remove a specific track by 1-based position
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import discord
from discord import app_commands
from discord.ext import commands

from utils.embeds import (
    error_embed, success_embed, info_embed,
    now_playing_embed,
)
from utils.views import QueueView
from utils.formatters import fmt_duration

if TYPE_CHECKING:
    from main import MusicBot

logger = logging.getLogger(__name__)


class QueueCog(commands.Cog, name="Queue"):
    """Queue management commands."""

    def __init__(self, bot: "MusicBot") -> None:
        self.bot = bot

    # ── Commands ──────────────────────────────────────────────────────────────

    @app_commands.command(name="queue", description="Show the current song queue.")
    @app_commands.describe(page="Page number (default 1)")
    async def queue(
        self, interaction: discord.Interaction, page: int = 1
    ) -> None:
        player = self.bot.get_player(interaction.guild_id)

        if player.is_empty() and player.now_playing is None:
            await interaction.response.send_message(
                embed=info_embed("Queue Empty", "The queue is currently empty. Use `/play` to add songs."),
                ephemeral=True,
            )
            return

        view = QueueView(
            self.bot,
            interaction.guild_id,
            guild_name = interaction.guild.name,
        )
        view.page = max(1, page)
        embed = view.build_embed()
        await interaction.response.send_message(embed=embed, view=view)

    @app_commands.command(name="shuffle", description="Shuffle the queue randomly.")
    async def shuffle(self, interaction: discord.Interaction) -> None:
        player = self.bot.get_player(interaction.guild_id)
        if player.is_empty():
            await interaction.response.send_message(
                embed=error_embed("Queue Empty", "Nothing to shuffle."),
                ephemeral=True,
            )
            return
        await player.shuffle()
        await interaction.response.send_message(
            embed=success_embed("Shuffled", f"🔀 Shuffled **{len(player)}** tracks.")
        )

    @app_commands.command(name="clear", description="Clear the entire queue.")
    async def clear(self, interaction: discord.Interaction) -> None:
        player = self.bot.get_player(interaction.guild_id)
        count  = len(player)
        await player.clear()
        await self.bot.db.clear_queue(interaction.guild_id)
        await interaction.response.send_message(
            embed=success_embed(
                "Queue Cleared",
                f"Removed **{count}** track{'s' if count != 1 else ''} from the queue.",
            )
        )

    @app_commands.command(name="loop", description="Cycle loop mode: Off → Track → Queue.")
    async def loop(self, interaction: discord.Interaction) -> None:
        player = self.bot.get_player(interaction.guild_id)
        player.loop_mode = player.loop_mode.next()
        await interaction.response.send_message(
            embed=success_embed("Loop Mode", f"Set to **{player.loop_mode.label()}**.")
        )

    @app_commands.command(name="remove", description="Remove a track from the queue by position.")
    @app_commands.describe(position="Position in the queue (1-based)")
    async def remove(self, interaction: discord.Interaction, position: int) -> None:
        player = self.bot.get_player(interaction.guild_id)
        track  = await player.remove(position - 1)  # Convert to 0-based index
        if track is None:
            await interaction.response.send_message(
                embed=error_embed(
                    "Invalid Position",
                    f"Position **{position}** is out of range. Queue has **{len(player)}** tracks.",
                ),
                ephemeral=True,
            )
            return
        await interaction.response.send_message(
            embed=success_embed(
                "Removed",
                f"Removed **{track.short_title}** (`{fmt_duration(track.duration)}`) from position **{position}**.",
            )
        )

    @app_commands.command(name="move", description="Move a track to a different queue position.")
    @app_commands.describe(
        from_pos="Current position (1-based)",
        to_pos="Target position (1-based)",
    )
    async def move(
        self,
        interaction: discord.Interaction,
        from_pos: int,
        to_pos: int,
    ) -> None:
        player = self.bot.get_player(interaction.guild_id)
        n = len(player)

        if not (1 <= from_pos <= n) or not (1 <= to_pos <= n):
            await interaction.response.send_message(
                embed=error_embed(
                    "Invalid Position",
                    f"Positions must be between 1 and {n}.",
                ),
                ephemeral=True,
            )
            return

        # Atomic move — holds queue_lock for the entire operation
        track = await player.move(from_pos - 1, to_pos - 1)
        if track is None:
            await interaction.response.send_message(
                embed=error_embed("Move Failed", "Could not move that track."),
                ephemeral=True,
            )
            return

        await interaction.response.send_message(
            embed=success_embed(
                "Moved",
                f"Moved **{track.short_title}** from position **{from_pos}** to **{to_pos}**.",
            )
        )


async def setup(bot: "MusicBot") -> None:
    await bot.add_cog(QueueCog(bot))
