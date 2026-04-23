# -*- coding: utf-8 -*-
"""
core/youtube.py — YouTube data extraction via yt-dlp.

Provides:
- Single track extraction from URL
- Text-based search
- YouTube playlist extraction
- In-memory LRU-style result cache

V2 Optimizations:
- Separated metadata opts (fast, extract_flat) from stream opts (full resolve)
- noplaylist=True for single tracks to avoid accidental playlist expansion
- Audio-only format selection with no DASH manifest parsing
"""

from __future__ import annotations

import asyncio
import logging
import re
import time
from typing import Optional
from urllib.parse import urlparse

import yt_dlp

import config
from models.track import Track

logger = logging.getLogger(__name__)

_YOUTUBE_DOMAINS = frozenset(
    [
        "youtube.com",
        "www.youtube.com",
        "m.youtube.com",
        "music.youtube.com",
        "youtu.be",
    ]
)

# ── yt-dlp base options ───────────────────────────────────────────────────────

# Used for metadata-only extraction (get_track, search) — fast, no format resolve
_META_OPTS: dict = {
    "format":                        config.YTDL_AUDIO_FORMAT,
    "quiet":                         True,
    "no_warnings":                   True,
    "ignoreerrors":                  True,
    "default_search":                "ytsearch",
    "nocheckcertificate":            True,
    "source_address":                "0.0.0.0",
    "noplaylist":                    True,      # ✅ prevent accidental playlist load
    "extract_flat":                  True,      # ✅ metadata only, skip format resolution
    "geo_bypass":                    True,
    "cachedir":                      False,
    "retries":                       config.YTDL_RETRIES,
    "socket_timeout":                10,
    "skip_download":                 True,
}

# Used for stream URL resolution — full resolve, no cache
_STREAM_OPTS: dict = {
    "format":                        config.YTDL_AUDIO_FORMAT,
    "quiet":                         True,
    "no_warnings":                   True,
    "ignoreerrors":                  False,     # raise on stream errors
    "nocheckcertificate":            True,
    "source_address":                "0.0.0.0",
    "noplaylist":                    True,
    "extract_flat":                  False,     # ✅ full resolve for CDN URL
    "geo_bypass":                    True,
    "cachedir":                      False,
    "retries":                       2,         # fewer retries for speed
    "socket_timeout":                10,
    "skip_download":                 True,
    "youtube_include_dash_manifest": False,     # ✅ skip DASH — faster
}

# Used for playlist extraction — flat list, fast
_PLAYLIST_OPTS: dict = {
    "format":             config.YTDL_AUDIO_FORMAT,
    "quiet":              True,
    "no_warnings":        True,
    "ignoreerrors":       True,
    "nocheckcertificate": True,
    "source_address":     "0.0.0.0",
    "noplaylist":         False,               # must be False for playlists
    "extract_flat":       "in_playlist",       # ✅ flat extraction only
    "geo_bypass":         True,
    "cachedir":           False,
    "retries":            config.YTDL_RETRIES,
    "socket_timeout":     20,
    "skip_download":      True,
}

# Use cookies file if present (helps with age-restricted / sign-in videos)
import pathlib
if pathlib.Path("cookies.txt").exists():
    for _opts in (_META_OPTS, _STREAM_OPTS, _PLAYLIST_OPTS):
        _opts["cookiefile"] = "cookies.txt"


class YouTubeExtractor:
    """Thread-safe, cached YouTube extractor wrapping yt-dlp."""

    def __init__(self) -> None:
        self._cache:      dict[str, tuple[dict, float]] = {}
        self._cache_lock: asyncio.Lock = asyncio.Lock()

    # ── Private helpers ───────────────────────────────────────────────────────

    @staticmethod
    def _clean_url(url: str) -> str:
        """Strip playlist/index params from a YouTube URL."""
        if "youtube.com" in url or "youtu.be" in url:
            url = re.sub(r"[&?]list=[^&]*", "", url)
            url = re.sub(r"[&?]index=[^&]*", "", url)
            url = re.sub(r"[&?]start_radio=[^&]*", "", url)
        return url

    @staticmethod
    def _run_ytdl(opts: dict, query: str) -> dict | None:
        """Blocking yt-dlp call — must be run in executor."""
        with yt_dlp.YoutubeDL(opts) as ydl:
            return ydl.extract_info(query, download=False)

    async def _extract(
        self,
        query: str,
        *,
        opts: dict | None = None,
        use_cache: bool = True,
        timeout: float | None = None,
    ) -> dict | None:
        """
        Extract info for *query* with optional caching and retry logic.
        Runs the blocking yt-dlp call in a thread-pool executor.

        Args:
            query:     URL or search string
            opts:      yt-dlp options dict; defaults to _META_OPTS
            use_cache: whether to read/write the in-memory cache
            timeout:   asyncio timeout (seconds); defaults to config.YTDL_TIMEOUT
        """
        if opts is None:
            opts = _META_OPTS
        if timeout is None:
            timeout = config.YTDL_TIMEOUT

        cache_key = f"{query}::{sorted(opts.items())}"

        if use_cache:
            async with self._cache_lock:
                if cache_key in self._cache:
                    data, ts = self._cache[cache_key]
                    if time.monotonic() - ts < config.YTDL_CACHE_TIMEOUT:
                        return data
                    del self._cache[cache_key]

        loop = asyncio.get_running_loop()
        last_exc: Exception | None = None

        for attempt in range(1, config.YTDL_RETRIES + 1):
            try:
                result = await asyncio.wait_for(
                    loop.run_in_executor(None, self._run_ytdl, opts, query),
                    timeout=timeout,
                )
                if result and use_cache:
                    async with self._cache_lock:
                        self._cache[cache_key] = (result, time.monotonic())
                        # Evict oldest entries when cache is full
                        if len(self._cache) > config.YTDL_CACHE_MAX_SIZE:
                            oldest = min(self._cache, key=lambda k: self._cache[k][1])
                            del self._cache[oldest]
                return result
            except asyncio.TimeoutError:
                logger.warning(
                    "yt-dlp timeout attempt %d/%d: %s", attempt, config.YTDL_RETRIES, query
                )
                last_exc = asyncio.TimeoutError()
            except Exception as exc:
                logger.warning(
                    "yt-dlp error attempt %d/%d: %s", attempt, config.YTDL_RETRIES, exc
                )
                last_exc = exc
            if attempt < config.YTDL_RETRIES:
                await asyncio.sleep(attempt)  # exponential-ish back-off

        logger.error(
            "yt-dlp failed after %d attempts for '%s': %s",
            config.YTDL_RETRIES, query, last_exc,
        )
        return None

    @staticmethod
    def _entry_to_track(entry: dict) -> Track | None:
        """Convert a raw yt-dlp entry dict to a Track, or None if unusable."""
        title = entry.get("title")
        url   = entry.get("webpage_url") or entry.get("url")
        if not title or not url:
            return None
        duration = entry.get("duration") or 0
        if duration > config.MAX_TRACK_LENGTH:
            return None
        return Track(
            title       = title,
            url         = url,
            duration    = int(duration),
            thumbnail   = entry.get("thumbnail"),
            uploader    = entry.get("uploader", "Unknown"),
            view_count  = entry.get("view_count"),
            upload_date = entry.get("upload_date"),
        )

    @staticmethod
    def _extract_stream_url(entry: dict) -> str | None:
        """
        Pull the best direct audio-stream URL out of a raw yt-dlp entry.

        yt-dlp populates `entry["url"]` with the CDN audio URL only when
        formats have been fully resolved (i.e. `extract_flat=False`).
        """
        formats = entry.get("formats") or []
        if formats:
            # Prefer audio-only formats; fall back to combined av if needed.
            audio_only = [
                f for f in formats
                if f.get("vcodec") in ("none", None, "") and f.get("url")
            ]
            candidates = audio_only or [f for f in formats if f.get("url")]
            if candidates:
                best = max(
                    candidates,
                    key=lambda f: (f.get("abr") or f.get("tbr") or 0),
                )
                stream = best.get("url")
                if stream:
                    return stream

        # Fall back to the top-level url
        stream = entry.get("url")
        if (
            stream
            and not stream.startswith("http://www.youtube")
            and not stream.startswith("https://www.youtube")
            and "youtu" not in stream
        ):
            return stream

        return None

    # ── Public API ────────────────────────────────────────────────────────────

    def is_youtube_url(self, url: str) -> bool:
        try:
            return urlparse(url).netloc.lower().lstrip("www.") in _YOUTUBE_DOMAINS
        except Exception:
            return False

    def is_playlist_url(self, url: str) -> bool:
        return "list=" in url and "youtube.com" in url

    async def get_track(self, url: str) -> Optional[Track]:
        """
        Fetch metadata for a single YouTube URL.
        Uses extract_flat=True for speed — no format resolution.
        """
        url  = self._clean_url(url)
        # Use full resolve opts for single tracks so we get complete metadata
        info = await self._extract(url, opts={**_META_OPTS, "extract_flat": False})
        if not info:
            return None
        entry = (info.get("entries") or [info])[0]
        if not entry:
            return None
        return self._entry_to_track(entry)

    async def get_stream_url(self, url: str) -> str | None:
        """
        Resolve *url* (a YouTube webpage URL) to a direct CDN audio-stream URL
        that FFmpeg can open.  Returns None on failure.

        Always bypasses cache — CDN URLs expire after a few hours.
        Uses optimized _STREAM_OPTS to minimize latency.
        """
        url = self._clean_url(url)
        loop = asyncio.get_running_loop()
        try:
            result = await asyncio.wait_for(
                loop.run_in_executor(None, self._run_ytdl, _STREAM_OPTS, url),
                timeout=config.YTDL_STREAM_TIMEOUT,  # ✅ faster timeout
            )
        except Exception as exc:
            logger.error("get_stream_url failed for '%s': %s", url, exc)
            raise  # re-raise so caller can handle + classify

        if not result:
            return None
        entry = (result.get("entries") or [result])[0]
        if not entry:
            return None
        return self._extract_stream_url(entry)

    async def search(self, query: str, max_results: int = 10) -> list[Track]:
        """Search YouTube and return up to *max_results* Track objects."""
        if not query or not query.strip():
            return []
        # Search uses metadata-only opts (extract_flat=True for speed)
        info = await self._extract(
            f"ytsearch{max_results}:{query.strip()}",
            opts={**_META_OPTS, "extract_flat": False},  # need metadata for duration
        )
        if not info or "entries" not in info:
            return []
        tracks: list[Track] = []
        for entry in info["entries"]:
            if not entry:
                continue
            track = self._entry_to_track(entry)
            if track:
                tracks.append(track)
        return tracks

    async def get_playlist(self, url: str, max_tracks: int = 50) -> list[Track]:
        """
        Extract up to *max_tracks* tracks from a YouTube playlist.

        V2.1 optimisation: uses a single flat extraction pass instead of
        individual metadata fetches per track.  Full metadata (stream URL)
        is resolved lazily at playback time via get_stream_url().
        """
        logger.info("Extracting playlist (max %d): %s", max_tracks, url)
        loop = asyncio.get_running_loop()
        try:
            result = await asyncio.wait_for(
                loop.run_in_executor(None, self._run_ytdl, _PLAYLIST_OPTS, url),
                timeout=30.0,
            )
        except asyncio.TimeoutError:
            logger.error("Playlist extraction timed out: %s", url)
            return []
        except Exception as exc:
            logger.error("Playlist extraction failed: %s", exc)
            return []

        if not result or "entries" not in result:
            return []

        tracks: list[Track] = []
        for entry in result["entries"][:max_tracks]:
            if not entry:
                continue
            title = entry.get("title") or entry.get("ie_key", "Unknown")
            # Prefer webpage_url; fall back to constructing from video id
            video_id  = entry.get("id", "")
            video_url = (
                entry.get("url")
                or entry.get("webpage_url")
                or (f"https://www.youtube.com/watch?v={video_id}" if video_id else None)
            )
            if not video_url or not title:
                continue
            # Duration from flat entry (may be 0 for live/unavailable entries)
            duration = int(entry.get("duration") or 0)
            if duration > config.MAX_TRACK_LENGTH:
                continue  # Skip tracks that exceed length limit
            track = Track(
                title       = title,
                url         = video_url,
                duration    = duration,
                thumbnail   = entry.get("thumbnail"),
                uploader    = entry.get("uploader") or entry.get("channel", "Unknown"),
                view_count  = entry.get("view_count"),
                upload_date = entry.get("upload_date"),
            )
            tracks.append(track)

        logger.info("Extracted %d/%d tracks from playlist (flat)", len(tracks), max_tracks)
        return tracks
