# -*- coding: utf-8 -*-
"""
config.py — Centralised configuration & logging setup for Music Bot V2.

All constants are loaded from the environment (via .env).
Import this module first in every other module that needs settings.
"""

import os
import sys
import logging
from pathlib import Path
from dotenv import load_dotenv

# ── Load .env ─────────────────────────────────────────────────────────────────
load_dotenv()

# ── Discord ───────────────────────────────────────────────────────────────────
TOKEN: str = os.getenv("DISCORD_TOKEN", "")
APP_ID: int | None = int(os.getenv("APP_ID")) if os.getenv("APP_ID") else None

if not TOKEN:
    raise RuntimeError("DISCORD_TOKEN is not set. Please configure your .env file.")

# ── Spotify (optional) ────────────────────────────────────────────────────────
SPOTIFY_CLIENT_ID: str = os.getenv("SPOTIFY_CLIENT_ID", "")
SPOTIFY_CLIENT_SECRET: str = os.getenv("SPOTIFY_CLIENT_SECRET", "")

# ── Database ──────────────────────────────────────────────────────────────────
DATABASE_PATH: str = os.getenv("DATABASE_PATH", "data/musicbot.db")

# ── Bot limits ────────────────────────────────────────────────────────────────
MAX_QUEUE_SIZE: int      = int(os.getenv("MAX_QUEUE_SIZE",    "100"))
MAX_USER_QUEUE: int      = int(os.getenv("MAX_USER_QUEUE",    "15"))
MAX_TRACK_LENGTH: int    = int(os.getenv("MAX_TRACK_LENGTH",  "10800"))  # 3 h
IDLE_TIMEOUT: int        = int(os.getenv("IDLE_TIMEOUT",      "300"))    # 5 min
HISTORY_DAYS: int        = int(os.getenv("HISTORY_DAYS",      "30"))

# ── Rate limiting ─────────────────────────────────────────────────────────────
RATE_LIMIT_WINDOW: int       = 60   # seconds
RATE_LIMIT_MAX_REQUESTS: int = 20

# ── yt-dlp ────────────────────────────────────────────────────────────────────
YTDL_CACHE_TIMEOUT: int  = 300   # seconds
YTDL_CACHE_MAX_SIZE: int = 50
YTDL_RETRIES: int        = 3
YTDL_TIMEOUT: float      = 25.0
YTDL_STREAM_TIMEOUT: float = 15.0  # faster timeout for stream URL resolution
YTDL_AUDIO_FORMAT: str   = "bestaudio[ext=m4a]/bestaudio[ext=webm]/bestaudio/best"

# ── Error handling ────────────────────────────────────────────────────────────
SKIP_ERROR_LIMIT: int    = 5    # max consecutive broken tracks before stopping

# ── Embed colours ────────────────────────────────────────────────────────────
COLOR_PRIMARY   = 0x5865F2   # Blurple
COLOR_SUCCESS   = 0x57F287   # Green
COLOR_WARNING   = 0xFEE75C   # Yellow
COLOR_ERROR     = 0xED4245   # Red
COLOR_INFO      = 0x5865F2   # Blurple

# ── Extra banned domains from env (comma-separated) ──────────────────────────
EXTRA_BANNED_DOMAINS: list[str] = [
    d.strip().lower()
    for d in os.getenv("EXTRA_BANNED_DOMAINS", "").split(",")
    if d.strip()
]

# ─────────────────────────────────────────────────────────────────────────────
# Logging
# ─────────────────────────────────────────────────────────────────────────────

class _ColoredFormatter(logging.Formatter):
    _COLORS = {
        "DEBUG":    "\033[36m",
        "INFO":     "\033[32m",
        "WARNING":  "\033[33m",
        "ERROR":    "\033[31m",
        "CRITICAL": "\033[35m",
    }
    _RESET = "\033[0m"

    def format(self, record: logging.LogRecord) -> str:
        color = self._COLORS.get(record.levelname, self._RESET)
        record.levelname = f"{color}{record.levelname:<8}{self._RESET}"
        record.name      = f"\033[94m{record.name:<20}{self._RESET}"
        return super().format(record)


def setup_logging(level: int = logging.INFO) -> None:
    """Call once at startup to configure root logger."""
    Path("logs").mkdir(exist_ok=True)

    root = logging.getLogger()
    root.setLevel(logging.DEBUG)

    fmt_plain = logging.Formatter(
        "%(asctime)s | %(name)s | %(levelname)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    fmt_color = _ColoredFormatter(
        "%(asctime)s | %(name)s | %(levelname)s | %(message)s",
        datefmt="%H:%M:%S",
    )

    # Console
    ch = logging.StreamHandler(sys.stdout)
    ch.setLevel(level)
    ch.setFormatter(fmt_color)

    # Full log file
    fh = logging.FileHandler("logs/musicbot.log", encoding="utf-8")
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(fmt_plain)

    # Error-only log file
    eh = logging.FileHandler("logs/errors.log", encoding="utf-8")
    eh.setLevel(logging.ERROR)
    eh.setFormatter(fmt_plain)

    root.addHandler(ch)
    root.addHandler(fh)
    root.addHandler(eh)

    # Suppress noisy third-party loggers
    for name in ("discord", "discord.voice_state", "asyncio", "yt_dlp"):
        logging.getLogger(name).setLevel(logging.WARNING)
    logging.getLogger("discord.voice_state").setLevel(logging.ERROR)
    logging.getLogger("yt_dlp").setLevel(logging.ERROR)
