from __future__ import annotations

import re
from typing import Any, Callable

import aiohttp

from app.core.exceptions import EntityNotFoundError, ExternalServiceUnavailableError
from app.core.types import TrackMetadata


class YouTubeClient:
    SEARCH_URL = "https://www.googleapis.com/youtube/v3/search"
    VIDEOS_URL = "https://www.googleapis.com/youtube/v3/videos"

    def __init__(self, api_key: str, session_factory: Callable[..., Any] | None = None) -> None:
        self.api_key = api_key
        self.session_factory = session_factory or aiohttp.ClientSession

    async def search_and_resolve(self, query: str, requester_id: int) -> TrackMetadata:
        params = {
            "part": "snippet",
            "q": query,
            "type": "video",
            "maxResults": 1,
            "key": self.api_key,
        }
        payload = await self._get_json(self.SEARCH_URL, params)
        items = payload.get("items") or []
        if not items:
            raise EntityNotFoundError("No results found")
        item = items[0]
        video_id = (item.get("id") or {}).get("videoId")
        if not video_id:
            raise EntityNotFoundError("No playable video found")
        snippet = item.get("snippet") or {}
        return TrackMetadata(
            id=video_id,
            title=snippet.get("title") or "Unknown title",
            duration=0,
            source="youtube",
            url=f"https://www.youtube.com/watch?v={video_id}",
            requester_id=requester_id,
            thumbnail_url=self._thumbnail_url(snippet),
            metadata={"channel": snippet.get("channelTitle")},
        )

    async def get_track_metadata(self, url: str, requester_id: int) -> TrackMetadata:
        video_id = self._extract_video_id(url)
        if not video_id:
            raise EntityNotFoundError("Invalid YouTube URL")
        params = {"part": "snippet,contentDetails", "id": video_id, "key": self.api_key}
        payload = await self._get_json(self.VIDEOS_URL, params)
        items = payload.get("items") or []
        if not items:
            raise EntityNotFoundError("Unable to resolve YouTube video")
        item = items[0]
        snippet = item.get("snippet") or {}
        details = item.get("contentDetails") or {}
        return TrackMetadata(
            id=item.get("id") or video_id,
            title=snippet.get("title") or "Unknown title",
            duration=0,
            source="youtube",
            url=f"https://www.youtube.com/watch?v={video_id}",
            requester_id=requester_id,
            thumbnail_url=self._thumbnail_url(snippet),
            metadata={"duration": details.get("duration")},
        )

    async def _get_json(self, url: str, params: dict[str, Any]) -> dict[str, Any]:
        try:
            async with self.session_factory() as session:
                async with session.get(url, params=params, timeout=10) as response:
                    if response.status == 404:
                        raise EntityNotFoundError("YouTube item not found")
                    if response.status >= 400:
                        raise ExternalServiceUnavailableError("YouTube service unavailable")
                    return await response.json()
        except (EntityNotFoundError, ExternalServiceUnavailableError):
            raise
        except TimeoutError as exc:
            raise ExternalServiceUnavailableError("YouTube request timed out") from exc
        except aiohttp.ClientError as exc:
            raise ExternalServiceUnavailableError("YouTube request failed") from exc

    @staticmethod
    def _extract_video_id(url: str) -> str | None:
        patterns = [
            r"youtu\.be/([^?&/]+)",
            r"youtube\.com/watch\?v=([^?&/]+)",
        ]
        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                return match.group(1)
        return None

    @staticmethod
    def _thumbnail_url(snippet: dict[str, Any]) -> str | None:
        thumbs = snippet.get("thumbnails") or {}
        for key in ("maxres", "high", "medium", "default"):
            if key in thumbs and thumbs[key].get("url"):
                return thumbs[key]["url"]
        return None
