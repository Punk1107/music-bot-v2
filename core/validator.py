# -*- coding: utf-8 -*-
"""
core/validator.py — URL safety validation pipeline.

Checks for:
  1. Banned content patterns (NSFW, gambling, piracy)
  2. Known banned domains
  3. Banned TLDs
  4. Extra banned domains from environment variable
  5. Whitelist of allowed providers
  6. Direct audio file extension
  7. Content-Type header sniffing (async, cached)
  8. Search-text sanitisation (validate_search_query)
"""

from __future__ import annotations

import logging
import re
import time
from dataclasses import dataclass
from urllib.parse import urlparse

import aiohttp

import config

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# Pattern lists
# ─────────────────────────────────────────────────────────────────────────────

# Patterns applied with \b word-boundary (safe — long enough to avoid FP)
_WORD_BOUNDARY_PATTERNS: list[str] = [
    # NSFW
    r"pornhub", r"xvideos", r"xhamster", r"redtube", r"youporn", r"spankbang",
    r"nhentai", r"hentai", r"fakku", r"rule34", r"camgirl", r"onlyfans",
    r"chaturbate", r"myfreecams", r"bongacams", r"livejasmin", r"stripchat",
    r"camsoda", r"jasmin", r"cam4", r"avgle", r"tnaflix", r"drtuber",
    # Gambling
    r"sbobet", r"ufabet", r"betflix", r"betmove", r"betway",
    r"1xbet", r"22bet", r"dafabet", r"fun88",
    r"lsm99", r"gclub", r"goldenslot", r"sagame", r"sexy\s*baccarat",
    r"ambbet", r"pgslot", r"joker123", r"slotxo", r"918kiss",
    # Piracy / illegal streaming
    r"123movies", r"fmovies", r"gomovies", r"putlocker", r"solarmovie",
    r"kissasian", r"kissanime", r"9anime", r"aniwave", r"soap2day",
    # Thai keywords
    r"หนังโป๊", r"ผู้ใหญ่", r"เว็บพนัน", r"บาคาร่า", r"สล็อต",
    r"แทงบอล", r"คาสิโน", r"หวย", r"พนันออนไลน์",
]

# Patterns WITHOUT \b (substring match — short terms prone to FP if word-bounded)
_SUBSTRING_PATTERNS: list[str] = [
    r"porn(?!ographic\s+film)", r"xxx", r"nsfw", r"xnxx",
    r"18\+", r"jav(?:hd|sub|bus|lib)",   # jav only when followed by common suffixes
    r"casino(?:online)?",
    r"gambl(?:ing|er)?",
    r"sportsbook",
    r"w88", r"m88",
]

_COMPILED_WORD = [
    re.compile(rf"\b{p}\b", re.IGNORECASE | re.UNICODE)
    for p in _WORD_BOUNDARY_PATTERNS
]
_COMPILED_SUB = [
    re.compile(p, re.IGNORECASE | re.UNICODE)
    for p in _SUBSTRING_PATTERNS
]

# ─────────────────────────────────────────────────────────────────────────────
# Domain / TLD blacklists
# ─────────────────────────────────────────────────────────────────────────────

_BANNED_DOMAINS: frozenset[str] = frozenset([
    # NSFW
    "pornhub.com", "xvideos.com", "xnxx.com", "redtube.com", "youporn.com",
    "xhamster.com", "spankbang.com", "nhentai.net", "e-hentai.org",
    "avgle.com", "fakku.net", "rule34.xxx", "onlyfans.com",
    "chaturbate.com", "myfreecams.com", "bongacams.com", "cam4.com",
    "livejasmin.com", "stripchat.com", "camsoda.com", "tnaflix.com",
    "drtuber.com", "hclips.com", "hdzog.com", "fuq.com",
    # Gambling — international
    "1xbet.com", "sbobet.com", "ufabet.com", "dafabet.com", "fun88.com",
    "m88.com", "w88.com", "bet365.com", "betway.com", "22bet.com",
    "betonline.ag", "bwin.com", "888casino.com", "pokerstars.com",
    # Gambling — Thai
    "lsm99.com", "gclub.com", "goldenslot.com", "sagame.com",
    "ambbet.net", "pgslot.com", "joker123.net", "slotxo.com",
    "betflix.io", "ufabet168.com", "betmove.com",
    # Piracy / illegal streaming
    "fmovies.to", "fmovies.wtf", "123movies.to", "gomovies.to",
    "putlocker.is", "solarmovie.to", "kissanime.ru", "kissasian.sh",
    "9anime.to", "aniwave.to", "soap2day.rs", "bflix.gg",
    "flixtor.to", "lookmovie.ag", "yesmovies.ag", "cmovies.fc",
])

_BANNED_TLDS: tuple[str, ...] = (
    ".xxx", ".porn", ".adult", ".sex",
    ".casino", ".bet", ".poker",
)

# ─────────────────────────────────────────────────────────────────────────────
# Whitelist
# ─────────────────────────────────────────────────────────────────────────────

_ALLOWED_PROVIDERS: tuple[str, ...] = (
    "youtube.com", "youtu.be", "www.youtube.com",
    "m.youtube.com", "music.youtube.com",
    "open.spotify.com", "spotify.com",
)

_SAFE_AUDIO_EXTS: tuple[str, ...] = (
    ".mp3", ".aac", ".m4a", ".flac", ".wav",
    ".ogg", ".opus", ".webm", ".mka",
)

# ─────────────────────────────────────────────────────────────────────────────
# Result type
# ─────────────────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class ValidationResult:
    ok:     bool
    reason: str = ""

    def __bool__(self) -> bool:
        return self.ok


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _domain(url: str) -> str:
    try:
        return urlparse(url).netloc.lower()
    except Exception:
        return ""


def _is_subdomain(host: str, target: str) -> bool:
    return host == target or host.endswith("." + target)


# ─────────────────────────────────────────────────────────────────────────────
# Content-type cache (async HEAD request)
# ─────────────────────────────────────────────────────────────────────────────

_ct_cache: dict[str, tuple[bool, float]] = {}
_CT_TTL = 300  # seconds


async def _is_audio_content_type(url: str, session: aiohttp.ClientSession | None = None) -> bool:
    now = time.monotonic()
    if url in _ct_cache:
        result, ts = _ct_cache[url]
        if now - ts < _CT_TTL:
            return result

    try:
        timeout = aiohttp.ClientTimeout(total=6)
        if session and not session.closed:
            async with session.head(url, allow_redirects=True, timeout=timeout) as resp:
                ct = resp.headers.get("Content-Type", "").lower()
                is_audio = any(x in ct for x in ("audio", "mpegurl", "mpeg"))
        else:
            async with aiohttp.ClientSession(timeout=timeout) as s:
                async with s.head(url, allow_redirects=True) as resp:
                    ct = resp.headers.get("Content-Type", "").lower()
                    is_audio = any(x in ct for x in ("audio", "mpegurl", "mpeg"))
    except Exception as exc:
        logger.debug("Content-type check failed for %s: %s", url, exc)
        is_audio = False

    _ct_cache[url] = (is_audio, now)
    if len(_ct_cache) > 256:
        cutoff = now - _CT_TTL
        for key in [k for k, v in _ct_cache.items() if v[1] < cutoff]:
            del _ct_cache[key]

    return is_audio


# ─────────────────────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────────────────────

def is_banned(url: str) -> ValidationResult:
    """Synchronous banned-content check. No network I/O."""
    u = url.lower()
    d = _domain(u)

    for pat in _COMPILED_WORD:
        if pat.search(u):
            return ValidationResult(False, f"Blocked: matched banned pattern")

    for pat in _COMPILED_SUB:
        if pat.search(u):
            return ValidationResult(False, f"Blocked: matched banned content")

    for bd in _BANNED_DOMAINS:
        if _is_subdomain(d, bd):
            return ValidationResult(False, f"Blocked: banned domain")

    for extra in config.EXTRA_BANNED_DOMAINS:
        if extra and _is_subdomain(d, extra):
            return ValidationResult(False, f"Blocked: custom banned domain")

    if d and any(d.endswith(tld) for tld in _BANNED_TLDS):
        return ValidationResult(False, f"Blocked: banned domain extension")

    return ValidationResult(True)


def is_allowed_provider(url: str) -> bool:
    d = _domain(url)
    return any(_is_subdomain(d, host) for host in _ALLOWED_PROVIDERS)


def is_direct_audio(url: str) -> bool:
    try:
        path = urlparse(url).path.lower()
        return any(path.endswith(ext) for ext in _SAFE_AUDIO_EXTS)
    except Exception:
        return False


def validate_search_query(query: str) -> ValidationResult:
    """
    Check a plain-text search query for banned keywords.
    Called before sending to YouTube search API.
    """
    for pat in _COMPILED_WORD:
        if pat.search(query):
            return ValidationResult(False, "Search query contains blocked content")
    for pat in _COMPILED_SUB:
        if pat.search(query):
            return ValidationResult(False, "Search query contains blocked content")
    return ValidationResult(True)


async def validate_url(url: str, *, session: aiohttp.ClientSession | None = None) -> ValidationResult:
    """
    Full URL validation pipeline:
      1. Banned-content pattern check
      2. Allowed-provider whitelist
      3. Direct audio file extension
      4. Content-Type header sniff (async, cached)

    Args:
        url:     The URL to validate.
        session: Optional shared aiohttp session to reuse (avoids TCP overhead).
    """
    banned = is_banned(url)
    if not banned:
        return ValidationResult(False, banned.reason)

    if is_allowed_provider(url):
        return ValidationResult(True, "Allowed provider")

    if is_direct_audio(url):
        return ValidationResult(True, "Direct audio file")

    if await _is_audio_content_type(url, session=session):
        return ValidationResult(True, "Audio content-type")

    return ValidationResult(False, "URL is not a recognised audio source")
