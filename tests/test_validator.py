# -*- coding: utf-8 -*-
"""
tests/test_validator.py — Unit tests for core/validator.py.

Tests URL/query validation logic without any Discord or yt-dlp calls.
Runs synchronously (no async needed for the sync helpers).
"""

import pytest
from core.validator import (
    is_banned, is_allowed_provider, is_direct_audio,
    validate_search_query, ValidationResult,
)


# ── is_banned() ───────────────────────────────────────────────────────────────

class TestIsBanned:
    def test_clean_youtube_url(self):
        r = is_banned("https://www.youtube.com/watch?v=dQw4w9WgXcQ")
        assert r.ok is True

    def test_nsfw_domain(self):
        r = is_banned("https://pornhub.com/video/123")
        assert r.ok is False

    def test_banned_word_in_url(self):
        r = is_banned("https://example.com/hentai/video")
        assert r.ok is False

    def test_gambling_domain(self):
        r = is_banned("https://1xbet.com/match/12345")
        assert r.ok is False

    def test_banned_tld_xxx(self):
        r = is_banned("https://example.xxx/video")
        assert r.ok is False

    def test_piracy_domain(self):
        r = is_banned("https://fmovies.to/watch/movie")
        assert r.ok is False

    def test_clean_spotify_url(self):
        r = is_banned("https://open.spotify.com/track/abc123")
        assert r.ok is True

    def test_clean_direct_audio(self):
        r = is_banned("https://cdn.example.com/audio.mp3")
        assert r.ok is True


# ── is_allowed_provider() ─────────────────────────────────────────────────────

class TestIsAllowedProvider:
    def test_youtube_allowed(self):
        assert is_allowed_provider("https://www.youtube.com/watch?v=abc") is True

    def test_youtu_be_allowed(self):
        assert is_allowed_provider("https://youtu.be/abc") is True

    def test_spotify_allowed(self):
        assert is_allowed_provider("https://open.spotify.com/track/xyz") is True

    def test_random_domain_not_allowed(self):
        assert is_allowed_provider("https://example.com/audio.mp3") is False


# ── is_direct_audio() ─────────────────────────────────────────────────────────

class TestIsDirectAudio:
    @pytest.mark.parametrize("ext", [".mp3", ".aac", ".m4a", ".flac", ".wav", ".ogg", ".opus", ".webm"])
    def test_audio_extensions(self, ext):
        assert is_direct_audio(f"https://cdn.example.com/file{ext}") is True

    def test_non_audio_extension(self):
        assert is_direct_audio("https://example.com/video.mp4") is False

    def test_youtube_url_not_direct(self):
        assert is_direct_audio("https://youtu.be/dQw4w9WgXcQ") is False


# ── validate_search_query() ───────────────────────────────────────────────────

class TestValidateSearchQuery:
    def test_clean_query(self):
        r = validate_search_query("lofi hip hop beats to relax")
        assert r.ok is True

    def test_nsfw_keyword(self):
        r = validate_search_query("pornhub music playlist")
        assert r.ok is False

    def test_thai_nsfw_keyword(self):
        r = validate_search_query("เว็บพนัน online")
        assert r.ok is False

    def test_empty_query_passes(self):
        # Empty query: no patterns match → OK (caller handles length check separately)
        r = validate_search_query("")
        assert r.ok is True

    def test_gambling_keyword(self):
        r = validate_search_query("casino music 2024")
        assert r.ok is False
