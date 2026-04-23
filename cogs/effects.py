# -*- coding: utf-8 -*-
"""
cogs/effects.py — Audio effects and volume control.

Commands:
  /volume <0-200>    — Set playback volume
  /effects <effect>  — Toggle an audio effect (with autocomplete)
  /effects_clear     — Disable all active effects
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import discord
from discord import app_commands
from discord.ext import commands

from models.enums import AudioEffect
from utils.embeds import error_embed, success_embed, info_embed

if TYPE_CHECKING:
    from main import MusicBot

logger = logging.getLogger(__name__)


class EffectsCog(commands.Cog, name="Effects"):
    """Audio effect and volume controls."""

    def __init__(self, bot: "MusicBot") -> None:
        self.bot = bot

    # ── Autocomplete ──────────────────────────────────────────────────────────

    async def _effect_autocomplete(
        self,
        interaction: discord.Interaction,
        current: str,
    ) -> list[app_commands.Choice[str]]:
        return [
            app_commands.Choice(name=e.display_name, value=e.value)
            for e in AudioEffect
            if current.lower() in e.display_name.lower() or current.lower() in e.value
        ][:25]

    # ── Commands ──────────────────────────────────────────────────────────────

    @app_commands.command(name="volume", description="Set the playback volume (0-200%).")
    @app_commands.describe(level="Volume level (0–200)")
    async def volume(self, interaction: discord.Interaction, level: int) -> None:
        if not (0 <= level <= 200):
            await interaction.response.send_message(
                embed=error_embed("Invalid Volume", "Volume must be between 0 and 200."),
                ephemeral=True,
            )
            return

        player  = self.bot.get_player(interaction.guild_id)
        player.volume = level / 100.0

        vc = interaction.guild.voice_client
        if vc and vc.source:
            # discord.py PCMVolumeTransformer — only works if source is transformed
            try:
                vc.source.volume = player.volume
            except AttributeError:
                pass  # Not a PCMVolumeTransformer — volume applied on next track

        bar = "🔇" if level == 0 else ("🔈" if level < 50 else ("🔉" if level < 100 else "🔊"))
        await interaction.response.send_message(
            embed=success_embed("Volume", f"{bar} Set to **{level}%**.")
        )

    @app_commands.command(name="effects", description="Toggle an audio effect.")
    @app_commands.describe(effect="Effect to toggle")
    @app_commands.autocomplete(effect=_effect_autocomplete)
    async def effects(self, interaction: discord.Interaction, effect: str) -> None:
        audio_effect = AudioEffect.from_value(effect)
        if not audio_effect:
            await interaction.response.send_message(
                embed=error_embed("Unknown Effect", f"Effect `{effect}` not found."),
                ephemeral=True,
            )
            return

        cfg = await self.bot.get_server_config(interaction.guild_id)
        if not cfg.effects_enabled:
            await interaction.response.send_message(
                embed=error_embed("Effects Disabled",
                                  "Audio effects are disabled for this server."),
                ephemeral=True,
            )
            return

        player  = self.bot.get_player(interaction.guild_id)
        enabled = player.toggle_effect(audio_effect)
        status  = "enabled ✅" if enabled else "disabled ❌"

        active_list = ", ".join(e.display_name for e in player.effects) or "None"
        await interaction.response.send_message(
            embed=success_embed(
                f"Effect {status}",
                f"**{audio_effect.display_name}** is now {status}.\n"
                f"**Active effects:** {active_list}\n\n"
                "_Note: Changes apply to the next track._",
            )
        )

    @app_commands.command(name="effects_clear", description="Disable all active audio effects.")
    async def effects_clear(self, interaction: discord.Interaction) -> None:
        player = self.bot.get_player(interaction.guild_id)
        if not player.effects:
            await interaction.response.send_message(
                embed=info_embed("No Effects", "No effects are currently active."),
                ephemeral=True,
            )
            return
        count = len(player.effects)
        player.clear_effects()
        await interaction.response.send_message(
            embed=success_embed(
                "Effects Cleared",
                f"Cleared **{count}** effect{'s' if count != 1 else ''}. "
                "Changes apply from the next track.",
            )
        )

    @app_commands.command(name="effects_list", description="Show all available audio effects.")
    async def effects_list(self, interaction: discord.Interaction) -> None:
        player = self.bot.get_player(interaction.guild_id)
        active = {e for e in player.effects}
        lines  = []
        for e in AudioEffect:
            mark = "✅" if e in active else "⬜"
            lines.append(f"{mark} {e.display_name}")

        embed = discord.Embed(
            title       = "🎛 Audio Effects",
            description = "\n".join(lines),
            colour      = 0x5865F2,
        )
        embed.set_footer(text="Use /effects <name> to toggle. Changes apply from the next track.")
        await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot: "MusicBot") -> None:
    await bot.add_cog(EffectsCog(bot))
