# -*- coding: utf-8 -*-
"""
cogs/info.py — Informational commands.

Commands:
  /nowplaying  — Show the current track with progress bar
  /history     — Show recent play history
  /help        — Show all bot commands
  /stats       — Bot performance & server stats
"""

from __future__ import annotations

import logging
import time
from datetime import datetime, timezone
from typing import TYPE_CHECKING

import discord
import psutil
from discord import app_commands
from discord.ext import commands

import config
from utils.embeds import (
    error_embed, info_embed, now_playing_embed,
    history_embed, help_embed,
)
from utils.formatters import fmt_duration

if TYPE_CHECKING:
    from main import MusicBot

logger = logging.getLogger(__name__)

_START_TIME = time.monotonic()


class InfoCog(commands.Cog, name="Info"):
    """Informational and diagnostic commands."""

    def __init__(self, bot: "MusicBot") -> None:
        self.bot = bot

    # ── Commands ──────────────────────────────────────────────────────────────

    @app_commands.command(name="nowplaying", description="Show the current track with progress bar.")
    async def nowplaying(self, interaction: discord.Interaction) -> None:
        player = self.bot.get_player(interaction.guild_id)

        if not player.now_playing:
            await interaction.response.send_message(
                embed=info_embed("Nothing Playing", "No track is currently playing."),
                ephemeral=True,
            )
            return

        embed = now_playing_embed(
            player.now_playing,
            elapsed    = player.elapsed_seconds(),
            loop_label = player.loop_mode.label(),
            effects    = [e.display_name for e in player.effects],
            volume     = player.volume,
        )
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="history", description="Show recently played tracks.")
    @app_commands.describe(limit="Number of tracks to show (1-20, default 10)")
    async def history(
        self, interaction: discord.Interaction, limit: int = 10
    ) -> None:
        limit   = max(1, min(20, limit))
        entries = await self.bot.db.get_history(interaction.guild_id, limit=limit)
        embed   = history_embed(entries, guild_name=interaction.guild.name)
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="help", description="Show all available commands.")
    async def help(self, interaction: discord.Interaction) -> None:
        await interaction.response.send_message(embed=help_embed(), ephemeral=True)

    @app_commands.command(name="stats", description="Show bot performance statistics.")
    async def stats(self, interaction: discord.Interaction) -> None:
        proc    = psutil.Process()
        uptime  = time.monotonic() - _START_TIME
        mem_mb  = proc.memory_info().rss / 1024 / 1024
        cpu     = proc.cpu_percent(interval=0.1)
        guilds  = len(self.bot.guilds)
        users   = sum(g.member_count or 0 for g in self.bot.guilds)
        vc_cnt  = len(self.bot.voice_clients)
        playing = sum(1 for vc in self.bot.voice_clients if vc.is_playing())

        h, rem  = divmod(int(uptime), 3600)
        m, s    = divmod(rem, 60)
        uptime_str = f"{h}h {m}m {s}s"

        embed = discord.Embed(
            title     = "📊 Bot Statistics",
            colour    = config.COLOR_PRIMARY,
            timestamp = datetime.now(timezone.utc),
        )
        embed.add_field(name="⏱ Uptime",          value=uptime_str,              inline=True)
        embed.add_field(name="💾 Memory",          value=f"{mem_mb:.1f} MB",      inline=True)
        embed.add_field(name="🖥 CPU",             value=f"{cpu:.1f}%",           inline=True)
        embed.add_field(name="🏠 Guilds",          value=str(guilds),             inline=True)
        embed.add_field(name="👥 Users",           value=str(users),              inline=True)
        embed.add_field(name="🔊 Voice Channels",  value=str(vc_cnt),             inline=True)
        embed.add_field(name="▶ Now Playing",      value=str(playing),            inline=True)

        await interaction.response.send_message(embed=embed)


async def setup(bot: "MusicBot") -> None:
    await bot.add_cog(InfoCog(bot))
