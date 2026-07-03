from __future__ import annotations

import discord
from discord.ext import commands

from app.presentation.bot.commands import register_music_commands


class MusicBot(commands.Bot):
    def __init__(self, service) -> None:
        intents = discord.Intents.default()
        super().__init__(command_prefix="!", intents=intents)
        self.service = service

    async def setup_hook(self) -> None:
        register_music_commands(self, self.service)
        try:
            await self.tree.sync()
        except Exception:
            pass

    async def on_ready(self) -> None:
        await self.change_presence(activity=discord.Game(name="/play"))

    async def on_command_error(self, ctx, error) -> None:
        if getattr(ctx, "responded", False):
            return
        await ctx.reply("An error occurred while processing your command.")

    async def close(self) -> None:
        await super().close()
