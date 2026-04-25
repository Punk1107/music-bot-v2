# -*- coding: utf-8 -*-
"""
tests/test_embeds.py — Unit tests for utils/embeds.py.

Verifies embed factories return correct discord.Embed objects with expected
fields, colors, and structure. No Discord API calls required.
"""

import pytest
import discord

from models.track import Track
from utils.embeds import (
    success_embed, error_embed, info_embed, warning_embed,
    now_playing_embed, track_added_embed, queue_embed, search_results_embed,
)


# ── Fixtures ──────────────────────────────────────────────────────────────────

def make_track(**kwargs) -> Track:
    defaults = dict(
        title="Test Song",
        url="https://youtube.com/watch?v=test",
        duration=240,
        thumbnail="https://img.example.com/thumb.jpg",
        uploader="Test Channel",
        view_count=1_000_000,
    )
    defaults.update(kwargs)
    return Track(**defaults)


# ── Generic embeds ────────────────────────────────────────────────────────────

class TestGenericEmbeds:
    def test_success_embed_color(self):
        e = success_embed("Done", "All good")
        assert e.colour.value == 0x2ECC71

    def test_error_embed_color(self):
        e = error_embed("Failed", "Oops")
        assert e.colour.value == 0xE74C3C

    def test_info_embed_has_title(self):
        e = info_embed("Info", "Some info")
        assert "Info" in e.title

    def test_warning_embed_has_title(self):
        e = warning_embed("Warn", "Something")
        assert "Warn" in e.title

    def test_embeds_have_timestamp(self):
        for fn in (success_embed, error_embed, info_embed, warning_embed):
            e = fn("T", "D")
            assert e.timestamp is not None


# ── now_playing_embed ─────────────────────────────────────────────────────────

class TestNowPlayingEmbed:
    def test_returns_embed(self):
        t = make_track()
        e = now_playing_embed(t)
        assert isinstance(e, discord.Embed)

    def test_uses_accent_color(self):
        t = make_track()
        e = now_playing_embed(t, accent_color=0xABCDEF)
        assert e.colour.value == 0xABCDEF

    def test_default_color_when_no_accent(self):
        import config
        t = make_track()
        e = now_playing_embed(t)
        assert e.colour.value == config.COLOR_NOW_PLAYING

    def test_thumbnail_set(self):
        t = make_track()
        e = now_playing_embed(t)
        assert e.thumbnail.url == t.thumbnail

    def test_has_progress_field(self):
        t = make_track()
        e = now_playing_embed(t, elapsed=60)
        field_names = [f.name for f in e.fields]
        assert any("Progress" in n for n in field_names)

    def test_has_volume_field(self):
        t = make_track()
        e = now_playing_embed(t, volume=1.0)
        field_names = [f.name for f in e.fields]
        assert any("Volume" in n for n in field_names)

    def test_no_thumbnail_when_none(self):
        t = make_track(thumbnail=None)
        e = now_playing_embed(t)
        assert not e.thumbnail.url


# ── track_added_embed ─────────────────────────────────────────────────────────

class TestTrackAddedEmbed:
    def test_is_first_uses_play_color(self):
        t = make_track()
        e = track_added_embed(t, 1, is_first=True)
        assert e.colour.value == 0x1ABC9C

    def test_queued_uses_violet_color(self):
        t = make_track()
        e = track_added_embed(t, 3, is_first=False)
        assert e.colour.value == 0x9B59B6


# ── queue_embed ───────────────────────────────────────────────────────────────

class TestQueueEmbed:
    def test_empty_queue_description(self):
        e = queue_embed([], guild_name="TestGuild")
        assert "empty" in (e.description or "").lower()

    def test_shows_tracks(self):
        tracks = [make_track(title=f"Track {i}") for i in range(3)]
        e = queue_embed(tracks, guild_name="TestGuild")
        assert "Track 0" in (e.description or "")

    def test_pagination_footer(self):
        tracks = [make_track() for _ in range(15)]
        e = queue_embed(tracks, page=2, per_page=10)
        assert "2" in (e.footer.text or "")


# ── search_results_embed ──────────────────────────────────────────────────────

class TestSearchResultsEmbed:
    def test_has_results_in_field(self):
        tracks = [make_track(title=f"Result {i}") for i in range(5)]
        e = search_results_embed(tracks, "test query")
        combined = " ".join(f.value for f in e.fields)
        assert "Result 0" in combined

    def test_title_contains_query(self):
        tracks = [make_track()]
        e = search_results_embed(tracks, "my query")
        assert "my query" in e.title
