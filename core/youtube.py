# -*- coding: utf-8 -*-
"""
core/youtube.py — YouTube data extraction via yt-dlp.

Provides:
- Single track extraction from URL
- Text-based search (with dedicated Track-level LRU cache)
- YouTube playlist extraction
- In-memory LRU-style result cache for raw yt-dlp responses
- Predictive stream pre-fetching (P3-2)
- Extraction concurrency throttle (P3-5)

V4 Changes:
  - _EXTRACT_SEM: module-level asyncio.Semaphore caps concurrent heavy yt-dlp
    extractions at config.EXTRACT_CONCURRENCY (default 3) to prevent CPU spikes.
  - prefetch_stream_url(): resolves CDN URL for next track in background and
    caches on track.stream_url_cache / stream_url_expires (14400s TTL).
  - get_stream_url(): checks track.stream_url_cache before calling yt-dlp —
    cache hit returns instantly with zero API overhead.
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

# Module-level semaphore — limits concurrent heavy yt-dlp extractions (P3-5)
_EXTRACT_SEM: asyncio.Semaphore | None = None  # initialised lazily on first use

def _get_extract_sem() -> asyncio.Semaphore:
    """Return (and lazily create) the module-level extraction semaphore."""
    global _EXTRACT_SEM
    if _EXTRACT_SEM is None:
        _EXTRACT_SEM = asyncio.Semaphore(config.EXTRACT_CONCURRENCY)
    return _EXTRACT_SEM


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
    "noplaylist":                    True,      # prevent accidental playlist load
    "extract_flat":                  True,      # metadata only, skip format resolution
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
    "extract_flat":                  False,     # full resolve for CDN URL
    "geo_bypass":                    True,
    "cachedir":                      False,
    "retries":                       2,         # fewer retries for speed
    "socket_timeout":                10,
    "skip_download":                 True,
    "youtube_include_dash_manifest": False,     # skip DASH — faster
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
    "extract_flat":       "in_playlist",       # flat extraction only
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
        # ── Raw-dict cache (for URL metadata lookups) ──────────────────────
        self._cache:      dict[str, tuple[dict, float]] = {}
        self._cache_lock: asyncio.Lock = asyncio.Lock()

        # ── Track-list search cache (query → resolved Track objects) ───────
        self._search_cache:      dict[str, tuple[list[Track], float]] = {}
        self._search_cache_lock: asyncio.Lock = asyncio.Lock()

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

        Throttled by _EXTRACT_SEM to prevent concurrent CPU saturation (P3-5).
        Uses true exponential backoff: 1s → 2s → 4s (capped at 8s).
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

        async with _get_extract_sem():   # ← P3-5: throttle concurrent extractions
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
                    backoff = min(2 ** (attempt - 1), 8)
                    logger.warning(
                        "yt-dlp timeout attempt %d/%d for '%s' — backoff %ds",
                        attempt, config.YTDL_RETRIES, query, backoff,
                    )
                    last_exc = asyncio.TimeoutError()

                except Exception as exc:
                    backoff = min(2 ** (attempt - 1), 8)
                    logger.warning(
                        "yt-dlp error attempt %d/%d: %s", attempt, config.YTDL_RETRIES, exc
                    )
                    last_exc = exc

                if attempt < config.YTDL_RETRIES:
                    await asyncio.sleep(min(2 ** (attempt - 1), 8))

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
        Uses full resolve opts for single tracks to get complete metadata.
        """
        url  = self._clean_url(url)
        info = await self._extract(url, opts={**_META_OPTS, "extract_flat": False})
        if not info:
            return None
        entry = (info.get("entries") or [info])[0]
        if not entry:
            return None
        return self._entry_to_track(entry)

    async def get_stream_url(self, url: str, track: Optional[Track] = None) -> str | None:
        """
        Resolve *url* (a YouTube webpage URL) to a direct CDN audio-stream URL
        that FFmpeg can open.  Returns None on failure.

        P3-2: If *track* is provided and has a valid pre-fetched stream URL
        (stream_url_cache, not yet expired), returns it instantly without any
        yt-dlp call. This gives gapless/instant playback for pre-fetched tracks.

        Falls through to yt-dlp on cache miss or expiry.
        Always bypasses the metadata cache — CDN URLs expire after a few hours.
        Uses optimized _STREAM_OPTS to minimize latency.
        """
        # ── P3-2: Pre-fetch cache hit ─────────────────────────────────────────
        if track and track.stream_url_cache and track.stream_url_expires:
            if time.monotonic() < track.stream_url_expires:
                logger.debug("Pre-fetch cache hit for '%s'", url[:60])
                return track.stream_url_cache

        url = self._clean_url(url)
        loop = asyncio.get_running_loop()
        try:
            result = await asyncio.wait_for(
                loop.run_in_executor(None, self._run_ytdl, _STREAM_OPTS, url),
                timeout=config.YTDL_STREAM_TIMEOUT,
            )
        except asyncio.TimeoutError:
            logger.error("get_stream_url timed out for '%s'", url)
            raise
        except Exception as exc:
            logger.error("get_stream_url failed for '%s': %s", url, exc)
            raise  # re-raise so caller can handle + classify

        if not result:
            return None
        entry = (result.get("entries") or [result])[0]
        if not entry:
            return None
        return self._extract_stream_url(entry)

    async def prefetch_stream_url(self, track: Track) -> None:
        """
        P3-2: Pre-fetch and cache the CDN stream URL for *track*.

        Stores the resolved URL on track.stream_url_cache with a TTL of
        config.STREAM_URL_TTL seconds (default 4 hours). When get_stream_url()
        is later called for this track, it returns the cached URL instantly.

        Designed to be called via asyncio.create_task() with a leading sleep:
            asyncio.create_task(_prefetch_after_delay(track, delay=T - 15))

        Silently swallows all exceptions — pre-fetch failures are non-fatal.
        The fallback path in get_stream_url() will handle it at playback time.
        """
        try:
            url = self._clean_url(track.url)
            loop = asyncio.get_running_loop()
            result = await asyncio.wait_for(
                loop.run_in_executor(None, self._run_ytdl, _STREAM_OPTS, url),
                timeout=config.YTDL_STREAM_TIMEOUT + 5,
            )
            if not result:
                return
            entry = (result.get("entries") or [result])[0]
            if not entry:
                return
            stream_url = self._extract_stream_url(entry)
            if stream_url:
                track.stream_url_cache   = stream_url
                track.stream_url_expires = time.monotonic() + config.STREAM_URL_TTL
                logger.debug(
                    "Pre-fetched stream URL for '%s' (expires in %.0fs)",
                    track.title[:50], config.STREAM_URL_TTL,
                )
        except Exception as exc:
            # Non-fatal — playback will fall back to on-demand resolution
            logger.debug("Pre-fetch failed for '%s': %s", track.url[:60], exc)

    async def search(self, query: str, max_results: int = 10) -> list[Track]:
        """
        Search YouTube and return up to *max_results* Track objects.

        Uses a dedicated Track-level LRU cache (keyed by query+max_results) so
        cache hits are instant — no yt-dlp call, no dict re-parsing.
        """
        if not query or not query.strip():
            return []

        cache_key = f"{query.strip()}::{max_results}"
        now = time.monotonic()

        # ── Cache hit check ──────────────────────────────────────────────
        async with self._search_cache_lock:
            entry = self._search_cache.get(cache_key)
            if entry:
                tracks, ts = entry
                if now - ts < config.SEARCH_CACHE_TTL:
                    logger.debug("Search cache hit for '%s'", query)
                    return tracks
                del self._search_cache[cache_key]

        # ── Cache miss — fetch from yt-dlp ───────────────────────────────
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

        # ── Store in search cache ─────────────────────────────────────────
        if tracks:
            async with self._search_cache_lock:
                self._search_cache[cache_key] = (tracks, time.monotonic())
                if len(self._search_cache) > config.SEARCH_CACHE_MAX_SIZE:
                    oldest = min(self._search_cache, key=lambda k: self._search_cache[k][1])
                    del self._search_cache[oldest]

        return tracks

    async def get_playlist(self, url: str, max_tracks: int = 50) -> list[Track]:
        """
        Extract up to *max_tracks* tracks from a YouTube playlist.

        Uses a single flat extraction pass — full metadata (stream URL)
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
            video_id  = entry.get("id", "")
            video_url = (
                entry.get("url")
                or entry.get("webpage_url")
                or (f"https://www.youtube.com/watch?v={video_id}" if video_id else None)
            )
            if not video_url or not title:
                continue
            duration = int(entry.get("duration") or 0)
            if duration > config.MAX_TRACK_LENGTH:
                continue
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
