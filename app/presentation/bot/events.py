from __future__ import annotations


def register_bot_events(bot) -> None:
    @bot.event
    async def on_ready() -> None:
        return None


async def handle_guild_join(guild, service) -> None:
    await service.get_server_config(guild.id)


async def handle_voice_state_update(member, before, after, service) -> None:
    if getattr(before, "channel", None) is not None and getattr(after, "channel", None) is None:
        await service.get_queue(member.guild.id)
