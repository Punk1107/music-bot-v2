# -*- coding: utf-8 -*-
"""
core/spotify.py — Spotify track/playlist/album extractor.

Converts Spotify links to search queries that YouTubeExtractor can use.
The entire module degrades gracefully if spotipy is not installed or
if credentials are missing — no crash, just a logged notice.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Optional

import config

logger = logging.getLogger(__name__)

# ── Optional spotipy import ───────────────────────────────────────────────────
try:
    import spotipy
    from spotipy.oauth2 import SpotifyClientCredentials
    _SPOTIPY_AVAILABLE = True
except ImportError:
    _SPOTIPY_AVAILABLE = False


# ── Dataclass-like result ─────────────────────────────────────────────────────

class SpotifyTrackInfo:
    """Lightweight container for a single Spotify track's metadata."""

    __slots__ = ("name", "artist", "album", "duration_ms", "image_url", "search_query")

    def __init__(
        self,
        *,
        name:         str,
        artist:       str,
        album:        str,
        duration_ms:  int,
        image_url:    Optional[str],
        search_query: str,
    ) -> None:
        self.name         = name
        self.artist       = artist
        self.album        = album
        self.duration_ms  = duration_ms
        self.image_url    = image_url
        self.search_query = search_query

    @property
    def duration_secs(self) -> int:
        return self.duration_ms // 1000


# ── Main extractor ────────────────────────────────────────────────────────────

class SpotifyExtractor:
    """
    Extract track metadata from Spotify URLs and convert to YouTube search queries.

    Usage:
        extractor = SpotifyExtractor()
        if extractor.available:
            tracks = await extractor.get_tracks_from_url("https://open.spotify.com/...")
    """

    def __init__(self) -> None:
        self._client: "spotipy.Spotify | None" = None

        if not _SPOTIPY_AVAILABLE:
            logger.info(
                "spotipy not installed — Spotify features disabled. "
                "Install with: pip install spotipy"
            )
            return

        if not (config.SPOTIFY_CLIENT_ID and config.SPOTIFY_CLIENT_SECRET):
            logger.info(
                "SPOTIFY_CLIENT_ID / SPOTIFY_CLIENT_SECRET not set — "
                "Spotify features disabled."
            )
            return

        try:
            creds = SpotifyClientCredentials(
                client_id     = config.SPOTIFY_CLIENT_ID,
                client_secret = config.SPOTIFY_CLIENT_SECRET,
            )
            self._client = spotipy.Spotify(client_credentials_manager=creds)
            logger.info("✅ Spotify integration enabled")
        except Exception as exc:
            logger.error("Failed to initialise Spotify client: %s", exc)

    # ── Properties ────────────────────────────────────────────────────────────

    @property
    def available(self) -> bool:
        return self._client is not None

    # ── URL helpers ───────────────────────────────────────────────────────────

    @staticmethod
    def is_spotify_url(url: str) -> bool:
        return "spotify.com" in url.lower()

    @staticmethod
    def _extract_id(url: str, segment: str) -> Optional[str]:
        """Pull the Spotify entity ID out of a URL segment like '/track/'."""
        try:
            return url.split(f"/{segment}/")[1].split("?")[0].split("/")[0]
        except IndexError:
            return None

    # ── Internals ─────────────────────────────────────────────────────────────

    def _make_track_info(
        self, track: dict, album_image: Optional[str] = None
    ) -> SpotifyTrackInfo:
        artists = ", ".join(a["name"] for a in track.get("artists", []))
        name    = track.get("name", "Unknown")
        album   = (
            track.get("album", {}).get("name", "Unknown")
            if "album" in track
            else "Unknown"
        )
        images = track.get("album", {}).get("images") if "album" in track else None
        image  = (images[0]["url"] if images else album_image)
        return SpotifyTrackInfo(
            name         = name,
            artist       = artists,
            album        = album,
            duration_ms  = track.get("duration_ms", 0),
            image_url    = image,
            search_query = f"{artists} - {name}",
        )

    def _run_sync(self, fn, *args):
        """Tiny helper: call a synchronous Spotify API function."""
        return fn(*args)

    # ── Public API ────────────────────────────────────────────────────────────

    async def get_tracks_from_url(self, url: str) -> list[SpotifyTrackInfo]:
        """
        Dispatch to the correct handler based on the URL type.
        Returns an empty list if unavailable or on error.
        """
        if not self.available:
            return []

        url = url.strip()
        if "/track/" in url:
            track = await self._get_single_track(url)
            return [track] if track else []
        if "/album/" in url:
            return await self._get_album_tracks(url)
        if "/playlist/" in url:
            return await self._get_playlist_tracks(url)

        logger.warning("Unrecognised Spotify URL: %s", url)
        return []

    async def _get_single_track(self, url: str) -> Optional[SpotifyTrackInfo]:
        track_id = self._extract_id(url, "track")
        if not track_id:
            return None
        loop = asyncio.get_running_loop()
        for attempt in range(1, 4):
            try:
                raw = await loop.run_in_executor(
                    None, self._run_sync, self._client.track, track_id
                )
                if raw:
                    return self._make_track_info(raw)
            except Exception as exc:
                logger.warning(
                    "Spotify track fetch attempt %d/3 failed: %s", attempt, exc
                )
                await asyncio.sleep(attempt)
        return None

    async def _get_album_tracks(self, url: str) -> list[SpotifyTrackInfo]:
        album_id = self._extract_id(url, "album")
        if not album_id:
            return []
        loop = asyncio.get_running_loop()
        try:
            raw_album = await loop.run_in_executor(
                None, self._run_sync, self._client.album, album_id
            )
            if not raw_album:
                return []
            image = (raw_album.get("images") or [{}])[0].get("url")
            tracks: list[SpotifyTrackInfo] = []
            for item in raw_album["tracks"]["items"]:
                # Album tracks don't nest album data — inject image manually
                info = SpotifyTrackInfo(
                    name         = item.get("name", "Unknown"),
                    artist       = ", ".join(a["name"] for a in item.get("artists", [])),
                    album        = raw_album.get("name", "Unknown"),
                    duration_ms  = item.get("duration_ms", 0),
                    image_url    = image,
                    search_query = (
                        f"{', '.join(a['name'] for a in item.get('artists', []))}"
                        f" - {item.get('name', '')}"
                    ),
                )
                tracks.append(info)
            logger.info("✅ Extracted %d tracks from Spotify album '%s'", len(tracks), raw_album.get("name"))
            return tracks
        except Exception as exc:
            logger.error("Spotify album extraction failed: %s", exc)
            return []

    async def _get_playlist_tracks(self, url: str) -> list[SpotifyTrackInfo]:
        playlist_id = self._extract_id(url, "playlist")
        if not playlist_id:
            return []
        loop = asyncio.get_running_loop()
        try:
            results = await loop.run_in_executor(
                None, self._run_sync, self._client.playlist_tracks, playlist_id
            )
            tracks: list[SpotifyTrackInfo] = []
            while results:
                for item in results.get("items", []):
                    raw = item.get("track")
                    if raw:
                        tracks.append(self._make_track_info(raw))
                next_url = results.get("next")
                if next_url:
                    results = await loop.run_in_executor(
                        None, self._run_sync, self._client.next, results
                    )
                else:
                    break
            logger.info("✅ Extracted %d tracks from Spotify playlist", len(tracks))
            return tracks
        except Exception as exc:
            logger.error("Spotify playlist extraction failed: %s", exc)
            return []
