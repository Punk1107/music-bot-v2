from __future__ import annotations

from app.core.circuit_breaker import CircuitBreaker, CircuitBreakerOpen
from app.core.exceptions import ExternalServiceUnavailableError
from app.core.types import EnqueueResult


class MusicService:
    def __init__(self, queue_repo, config_repo, youtube_client, spotify_client, breaker: CircuitBreaker) -> None:
        self.queue_repo = queue_repo
        self.config_repo = config_repo
        self.youtube_client = youtube_client
        self.spotify_client = spotify_client
        self.breaker = breaker

    async def enqueue_track_by_query(self, guild_id: int, channel_id: int, query: str, requester_id: int) -> EnqueueResult:
        if not self.breaker.allow_request():
            raise ExternalServiceUnavailableError("External service temporarily unavailable")
        try:
            if "open.spotify.com/track/" in query or query.startswith("spotify:track:"):
                track = await self.spotify_client.get_track_metadata(query, requester_id=requester_id)
            else:
                track = await self.youtube_client.search_and_resolve(query=query, requester_id=requester_id)
        except CircuitBreakerOpen as exc:
            raise ExternalServiceUnavailableError("External service temporarily unavailable") from exc
        except Exception:
            self.breaker.record_failure()
            raise
        self.breaker.record_success()
        position = await self.queue_repo.append_track(guild_id, channel_id, track, requester_id)
        return EnqueueResult(track=track, position=position)

    async def get_queue(self, guild_id: int):
        return await self.queue_repo.get_queue(guild_id=guild_id)

    async def skip_track(self, guild_id: int):
        return await self.queue_repo.dequeue(guild_id=guild_id)

    async def get_server_config(self, guild_id: int):
        return await self.config_repo.get_config(guild_id=guild_id)

    async def pause_player(self, voice_client) -> bool:
        if not voice_client or not voice_client.is_playing():
            return False
        voice_client.pause()
        return True

    async def resume_player(self, voice_client) -> bool:
        if not voice_client or not voice_client.is_paused():
            return False
        voice_client.resume()
        return True

    async def stop_player(self, guild_id: int, voice_client) -> None:
        if voice_client:
            voice_client.stop()
        await self.queue_repo.clear_queue(guild_id)

    async def leave_voice(self, guild_id: int, voice_client) -> bool:
        if not voice_client:
            return False
        await self.queue_repo.clear_queue(guild_id)
        await voice_client.disconnect()
        return True
