from __future__ import annotations

from dataclasses import dataclass

from models.enums import AudioEffect


@dataclass
class ServiceMessage:
    kind: str
    title: str
    description: str
    ephemeral: bool = False


class EffectsService:
    def __init__(self, bot) -> None:
        self.bot = bot

    def autocomplete(self, current: str) -> list[AudioEffect]:
        needle = current.lower()
        return [effect for effect in AudioEffect if needle in effect.value or needle in effect.display_name.lower()][:25]

    def set_volume(self, guild_id: int, level: int, voice_client=None) -> ServiceMessage:
        if not 0 <= level <= 200:
            return ServiceMessage("error", "Invalid Volume", "Volume must be between 0 and 200.", True)
        player = self.bot.get_player(guild_id)
        player.volume = level / 100.0
        if voice_client and getattr(voice_client, "source", None):
            try:
                voice_client.source.volume = player.volume
            except AttributeError:
                pass
        return ServiceMessage("success", "Volume", f"Set to {level}%.")

    async def toggle_effect(self, guild_id: int, effect: str) -> ServiceMessage:
        audio_effect = AudioEffect.from_value(effect)
        if not audio_effect:
            return ServiceMessage("error", "Unknown Effect", f"Effect `{effect}` not found.", True)
        config = await self.bot.get_server_config(guild_id)
        if not getattr(config, "effects_enabled", True):
            return ServiceMessage("error", "Effects Disabled", "Audio effects are disabled for this server.", True)
        player = self.bot.get_player(guild_id)
        enabled = player.toggle_effect(audio_effect)
        state = "enabled" if enabled else "disabled"
        return ServiceMessage("success", "Effect", f"{audio_effect.display_name} {state}.")

    def clear_effects(self, guild_id: int) -> ServiceMessage:
        player = self.bot.get_player(guild_id)
        if not player.effects:
            return ServiceMessage("info", "No Effects", "No effects are currently active.", True)
        count = len(player.effects)
        player.clear_effects()
        return ServiceMessage("success", "Effects Cleared", f"Cleared {count} effect(s).")

    def list_effects(self, guild_id: int) -> list[tuple[AudioEffect, bool]]:
        active = set(self.bot.get_player(guild_id).effects)
        return [(effect, effect in active) for effect in AudioEffect]
