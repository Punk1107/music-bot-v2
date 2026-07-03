from __future__ import annotations

import time
from dataclasses import dataclass

import psutil


@dataclass
class Stats:
    uptime_label: str
    memory_mb: float
    cpu_percent: float
    guild_count: int
    user_count: int
    voice_client_count: int
    playing_count: int


class InfoService:
    def __init__(self, bot, start_time: float | None = None) -> None:
        self.bot = bot
        self.start_time = time.monotonic() if start_time is None else start_time

    def now_playing_state(self, guild_id: int):
        return self.bot.get_player(guild_id)

    async def history(self, guild_id: int, limit: int = 20):
        limit = max(1, min(20, limit))
        return await self.bot.db.get_history(guild_id, limit=limit)

    def stats(self) -> Stats:
        proc = psutil.Process()
        uptime = int(time.monotonic() - self.start_time)
        hours, rem = divmod(uptime, 3600)
        minutes, seconds = divmod(rem, 60)
        voice_clients = getattr(self.bot, "voice_clients", [])
        return Stats(
            uptime_label=f"{hours}h {minutes}m {seconds}s",
            memory_mb=proc.memory_info().rss / 1024 / 1024,
            cpu_percent=proc.cpu_percent(),
            guild_count=len(getattr(self.bot, "guilds", [])),
            user_count=sum(g.member_count or 0 for g in getattr(self.bot, "guilds", [])),
            voice_client_count=len(voice_clients),
            playing_count=sum(1 for vc in voice_clients if vc.is_playing()),
        )
