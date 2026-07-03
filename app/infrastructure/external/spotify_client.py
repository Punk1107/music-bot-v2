from __future__ import annotations

import re
from typing import Any, Callable

import aiohttp

from app.core.exceptions import EntityNotFoundError, ExternalServiceUnavailableError
from app.core.types import TrackMetadata


class SpotifyClient:
    API_URL = "https://api.spotify.com/v1/tracks/{track_id}"

    def __init__(self, access_token: str, session_factory: Callable[..., Any] | None = None) -> None:
        self.access_token = access_token
        self.session_factory = session_factory or aiohttp.ClientSession

    async def get_track_metadata(self, url: str, requester_id: int) -> TrackMetadata:
        track_id = self._extract_track_id(url)
        if not track_id:
            raise EntityNotFoundError("Invalid Spotify track URL")
        try:
            async with self.session_factory() as session:
                async with session.get(
                    self.API_URL.format(track_id=track_id),
                    headers={"Authorization": f"Bearer {self.access_token}"},
                    timeout=10,
                ) as response:
                    if response.status == 404:
                        raise EntityNotFoundError("Spotify track not found")
                    if response.status >= 400:
                        raise ExternalServiceUnavailableError("Spotify service unavailable")
                    payload = await response.json()
        except (EntityNotFoundError, ExternalServiceUnavailableError):
            raise
        except TimeoutError as exc:
            raise ExternalServiceUnavailableError("Spotify request timed out") from exc
        except aiohttp.ClientError as exc:
            raise ExternalServiceUnavailableError("Spotify request failed") from exc

        artists = payload.get("artists") or []
        artist_names = ", ".join(a.get("name", "") for a in artists if a.get("name"))
        name = payload.get("name") or "Unknown title"
        title = f"{artist_names} - {name}" if artist_names else name
        images = (payload.get("album") or {}).get("images") or []
        thumbnail_url = images[0].get("url") if images else None
        return TrackMetadata(
            id=track_id,
            title=title,
            duration=int((payload.get("duration_ms") or 0) / 1000),
            source="spotify",
            url=f"https://open.spotify.com/track/{track_id}",
            requester_id=requester_id,
            thumbnail_url=thumbnail_url,
            metadata={"uri": payload.get("uri")},
        )

    @staticmethod
    def _extract_track_id(url: str) -> str | None:
        match = re.search(r"open\.spotify\.com/track/([^?&/]+)", url)
        if match:
            return match.group(1)
        match = re.fullmatch(r"spotify:track:([^:]+)", url)
        if match:
            return match.group(1)
        return None
