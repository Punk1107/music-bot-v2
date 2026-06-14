# -*- coding: utf-8 -*-
"""core/__init__.py"""

from .database import DatabaseManager
from .youtube  import YouTubeExtractor
from .audio    import AudioEffectsProcessor
from .player   import GuildPlayer
from .validator import validate_url, is_banned, is_allowed_provider

# SpotifyExtractor is intentionally NOT imported here at package level.
# spotipy → redis has a known bytecode-compilation failure on Python 3.14.
# spotify.py guards itself with try/except ImportError, but that cannot catch
# crashes inside a transitive dependency. Import it individually in main.py
# so any failure stays isolated and does not crash the whole core package.
try:
    from .spotify import SpotifyExtractor
except Exception:
    # Define a no-op stub so the rest of the codebase can still reference it.
    class SpotifyExtractor:  # type: ignore[no-redef]
        """Stub used when spotipy / redis fail to import (e.g. Python 3.14)."""
        available = False
        def is_spotify_url(self, _: str) -> bool: return False
        async def get_tracks_from_url(self, _: str) -> list: return []

__all__ = [
    "DatabaseManager",
    "YouTubeExtractor",
    "SpotifyExtractor",
    "AudioEffectsProcessor",
    "GuildPlayer",
    "validate_url",
    "is_banned",
    "is_allowed_provider",
]
