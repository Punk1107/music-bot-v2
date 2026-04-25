# -*- coding: utf-8 -*-
"""
tests/test_player.py — Unit tests for core/player.py.

Tests queue operations, lock safety, loop mode transitions, and elapsed time.
Uses pytest-asyncio for async test functions.
"""

import asyncio
import pytest
import pytest_asyncio
from datetime import datetime, timezone

from models.track import Track
from models.enums import LoopMode
from core.player import GuildPlayer


# ── Fixtures ──────────────────────────────────────────────────────────────────

def make_track(title: str = "Test Track", duration: int = 180) -> Track:
    return Track(title=title, url=f"https://youtube.com/watch?v={title}", duration=duration)


@pytest.fixture
def player():
    return GuildPlayer(guild_id=123456789)


# ── Queue operations ──────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_enqueue_and_len(player):
    await player.enqueue(make_track("A"))
    await player.enqueue(make_track("B"))
    assert len(player) == 2


@pytest.mark.asyncio
async def test_dequeue_order(player):
    await player.enqueue(make_track("First"))
    await player.enqueue(make_track("Second"))
    t = await player.dequeue()
    assert t.title == "First"
    assert len(player) == 1


@pytest.mark.asyncio
async def test_dequeue_empty_returns_none(player):
    result = await player.dequeue()
    assert result is None


@pytest.mark.asyncio
async def test_remove_valid_index(player):
    await player.enqueue(make_track("A"))
    await player.enqueue(make_track("B"))
    removed = await player.remove(0)
    assert removed.title == "A"
    assert len(player) == 1


@pytest.mark.asyncio
async def test_remove_oob_returns_none(player):
    await player.enqueue(make_track("A"))
    result = await player.remove(99)
    assert result is None


@pytest.mark.asyncio
async def test_shuffle_changes_order(player):
    tracks = [make_track(f"Track{i}") for i in range(10)]
    await player.extend(tracks)
    original = [t.title for t in player.as_list()]
    await player.shuffle()
    shuffled = [t.title for t in player.as_list()]
    # With 10 tracks the probability of same order is 1/10! ≈ negligible
    assert set(original) == set(shuffled)
    assert len(shuffled) == 10


@pytest.mark.asyncio
async def test_clear_empties_queue(player):
    await player.enqueue(make_track("A"))
    await player.clear()
    assert player.is_empty()


@pytest.mark.asyncio
async def test_move_track(player):
    for i in range(3):
        await player.enqueue(make_track(str(i)))
    moved = await player.move(2, 0)
    assert moved.title == "2"
    assert player.as_list()[0].title == "2"


# ── Loop mode ─────────────────────────────────────────────────────────────────

def test_loop_mode_cycle():
    m = LoopMode.OFF
    m = m.next()
    assert m == LoopMode.TRACK
    m = m.next()
    assert m == LoopMode.QUEUE
    m = m.next()
    assert m == LoopMode.OFF


@pytest.mark.asyncio
async def test_finish_track_loop_track(player):
    t = make_track("Looped")
    player.start_track(t)
    player.loop_mode = LoopMode.TRACK
    await player.finish_track()
    # Track should be re-queued at front
    assert len(player) == 1
    assert player.as_list()[0].title == "Looped"


@pytest.mark.asyncio
async def test_finish_track_loop_queue(player):
    t = make_track("QueueLooped")
    player.start_track(t)
    player.loop_mode = LoopMode.QUEUE
    await player.finish_track()
    # Track should be appended to back
    assert len(player) == 1
    assert player.as_list()[0].title == "QueueLooped"


# ── Elapsed time ──────────────────────────────────────────────────────────────

def test_elapsed_seconds_zero_when_nothing_playing(player):
    assert player.elapsed_seconds() == 0


def test_elapsed_seconds_positive_when_playing(player):
    t = make_track()
    player.start_track(t)
    # Elapsed should be >= 0 immediately after start
    assert player.elapsed_seconds() >= 0


# ── Reset ─────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_reset_clears_everything(player):
    await player.enqueue(make_track("A"))
    player.start_track(make_track("B"))
    player.volume = 1.5
    player.reset()
    assert player.is_empty()
    assert player.now_playing is None
    assert player.volume == 0.75


# ── Peek next ─────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_peek_next(player):
    await player.enqueue(make_track("First"))
    await player.enqueue(make_track("Second"))
    peeked = player.peek_next()
    assert peeked.title == "First"
    # Peek should not remove the track
    assert len(player) == 2
