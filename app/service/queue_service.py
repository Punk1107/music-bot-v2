from __future__ import annotations

from app.service.effects_service import ServiceMessage


class QueueService:
    def __init__(self, bot) -> None:
        self.bot = bot

    def get_queue_state(self, guild_id: int):
        return self.bot.get_player(guild_id)

    async def shuffle(self, guild_id: int) -> ServiceMessage:
        player = self.bot.get_player(guild_id)
        if player.is_empty():
            return ServiceMessage("error", "Queue Empty", "Nothing to shuffle.", True)
        await player.shuffle()
        return ServiceMessage("success", "Shuffled", f"Shuffled {len(player)} tracks.")

    async def clear(self, guild_id: int) -> ServiceMessage:
        player = self.bot.get_player(guild_id)
        count = len(player)
        await player.clear()
        await self.bot.db.clear_queue(guild_id)
        return ServiceMessage("success", "Queue Cleared", f"Removed {count} track(s).")

    def cycle_loop(self, guild_id: int) -> ServiceMessage:
        player = self.bot.get_player(guild_id)
        player.loop_mode = player.loop_mode.next()
        return ServiceMessage("success", "Loop Mode", f"Set to {player.loop_mode.label()}.")

    async def remove(self, guild_id: int, position: int) -> ServiceMessage:
        player = self.bot.get_player(guild_id)
        track = await player.remove(position - 1)
        if track is None:
            return ServiceMessage("error", "Invalid Position", "Position is out of range.", True)
        return ServiceMessage("success", "Removed", f"Removed {track.short_title}.")

    async def move(self, guild_id: int, from_pos: int, to_pos: int) -> ServiceMessage:
        player = self.bot.get_player(guild_id)
        if from_pos < 1 or to_pos < 1:
            return ServiceMessage("error", "Invalid Position", "Positions must be positive.", True)
        track = await player.move(from_pos - 1, to_pos - 1)
        if track is None:
            return ServiceMessage("error", "Move Failed", "Could not move that track.", True)
        return ServiceMessage("success", "Moved", f"Moved {track.short_title}.")
