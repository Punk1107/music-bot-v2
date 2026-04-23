# -*- coding: utf-8 -*-
"""
core/player.py — Per-guild music player state.

GuildPlayer encapsulates everything that belongs to one Discord guild:
queue, current track, loop mode, active effects, volume, and seek position.

V3 Changes:
  - asyncio.Lock on all queue-mutating operations to prevent race conditions
    when multiple users press buttons simultaneously.
  - All mutating queue methods are now async (enqueue, extend, dequeue,
    remove, shuffle, clear, finish_track).
  - last_channel_id field stores the last voice channel ID for self-healing
    reconnect logic in the music cog.
  - queue_lock exposed publicly so callers can acquire it for multi-step
    atomic operations (e.g. move = remove + insert).
"""

from __future__ import annotations

import asyncio
import random
from collections import deque
from datetime import datetime, timezone
from typing import Optional

from models.enums import AudioEffect, LoopMode
from models.track import Track


class GuildPlayer:
    """
    Mutable state container for a single guild's music session.

    All queue-mutating methods acquire self.queue_lock — safe for concurrent
    Discord interaction events on the asyncio event loop.
    """

    def __init__(self, guild_id: int) -> None:
        self.guild_id: int = guild_id

        # ── Queue ──────────────────────────────────────────────────────────────
        self._queue: deque[Track] = deque()
        self.queue_lock: asyncio.Lock = asyncio.Lock()

        # ── Now-playing ───────────────────────────────────────────────────────
        self.now_playing:        Optional[Track]        = None
        self.play_start_time:    Optional[datetime]     = None
        self.now_playing_msg:    Optional[object]       = None  # discord.Message
        self.now_playing_msg_id: Optional[int]          = None  # fallback ID

        # ── Controls ───────────────────────────────────────────────────────────
        self.loop_mode:     LoopMode           = LoopMode.OFF
        self.effects:       list[AudioEffect]  = []
        self.volume:        float              = 0.75
        self.seek_position: int                = 0
        self.quality:       str                = "MEDIUM"

        # ── Background tasks ───────────────────────────────────────────────────
        self.progress_task: Optional[asyncio.Task] = None
        self.idle_since:    Optional[datetime]      = None

        # ── Channel references ─────────────────────────────────────────────────
        self.text_channel:    Optional[object] = None  # discord.TextChannel
        self.last_channel_id: Optional[int]    = None  # last VC id for reconnect

        # ── Cached accent color from thumbnail ────────────────────────────────
        self.accent_color: Optional[int] = None  # 0xRRGGBB or None → default

    # ── Queue management (all async, all locked) ──────────────────────────────

    async def enqueue(self, track: Track) -> None:
        async with self.queue_lock:
            self._queue.append(track)

    async def extend(self, tracks: list[Track]) -> None:
        async with self.queue_lock:
            self._queue.extend(tracks)

    async def dequeue(self) -> Optional[Track]:
        """Pop the next track from the front of the queue."""
        async with self.queue_lock:
            return self._queue.popleft() if self._queue else None

    async def remove(self, index: int) -> Optional[Track]:
        """Remove and return the track at *index* (0-based). Returns None if OOB."""
        async with self.queue_lock:
            if index < 0 or index >= len(self._queue):
                return None
            lst = list(self._queue)
            track = lst.pop(index)
            self._queue = deque(lst)
            return track

    async def shuffle(self) -> None:
        async with self.queue_lock:
            lst = list(self._queue)
            random.shuffle(lst)
            self._queue = deque(lst)

    async def clear(self) -> None:
        async with self.queue_lock:
            self._queue.clear()

    async def move(self, from_idx: int, to_idx: int) -> Optional[Track]:
        """
        Move the track at *from_idx* to *to_idx* (0-based).
        Returns the moved Track or None if indices are invalid.
        Atomic — holds the lock for the full read-modify-write.
        """
        async with self.queue_lock:
            n = len(self._queue)
            if not (0 <= from_idx < n) or not (0 <= to_idx < n):
                return None
            lst = list(self._queue)
            track = lst.pop(from_idx)
            lst.insert(to_idx, track)
            self._queue = deque(lst)
            return track

    # ── Queue queries (read-only — no lock needed) ────────────────────────────

    def as_list(self) -> list[Track]:
        return list(self._queue)

    def __len__(self) -> int:
        return len(self._queue)

    def is_empty(self) -> bool:
        return len(self._queue) == 0

    def queue_duration(self) -> int:
        """Sum of all queued track durations in seconds."""
        return sum(t.duration for t in self._queue)

    def peek_next(self) -> Optional[Track]:
        """Return the next track without removing it. None if queue empty."""
        return self._queue[0] if self._queue else None

    # ── Now-playing helpers ───────────────────────────────────────────────────

    def start_track(self, track: Track) -> None:
        self.now_playing     = track
        self.play_start_time = datetime.now(timezone.utc)
        # Reset accent color — will be resolved for the new track
        self.accent_color = None

    def elapsed_seconds(self) -> int:
        """Seconds since the current track started (0 if nothing is playing)."""
        if self.now_playing is None or self.play_start_time is None:
            return 0
        delta = datetime.now(timezone.utc) - self.play_start_time
        return int(delta.total_seconds()) + self.seek_position

    async def finish_track(self) -> Optional[Track]:
        """
        Mark the current track as finished and advance the state.

        In TRACK loop mode the same track is re-queued at the front.
        In QUEUE loop mode the track is appended to the back.
        Returns the track that just finished (or None).

        Holds the queue_lock for the appendleft/append operations.
        """
        finished = self.now_playing
        if finished is None:
            return None

        if self.loop_mode == LoopMode.TRACK:
            async with self.queue_lock:
                self._queue.appendleft(finished)
        elif self.loop_mode == LoopMode.QUEUE:
            async with self.queue_lock:
                self._queue.append(finished)

        self.now_playing     = None
        self.play_start_time = None
        self.seek_position   = 0
        return finished

    def clear_now_playing_msg(self) -> None:
        """Clear the now-playing message reference and ID."""
        self.now_playing_msg    = None
        self.now_playing_msg_id = None

    # ── Effect helpers ────────────────────────────────────────────────────────

    def toggle_effect(self, effect: AudioEffect) -> bool:
        """Toggle *effect*. Returns True if now enabled, False if disabled."""
        if effect in self.effects:
            self.effects.remove(effect)
            return False
        self.effects.append(effect)
        return True

    def clear_effects(self) -> None:
        self.effects.clear()

    # ── Reset ─────────────────────────────────────────────────────────────────

    def reset(self) -> None:
        """Full reset — called on /stop or bot disconnect."""
        self._queue.clear()
        self.now_playing        = None
        self.play_start_time    = None
        self.seek_position      = 0
        self.loop_mode          = LoopMode.OFF
        self.effects.clear()
        self.volume             = 0.75
        self.quality            = "MEDIUM"
        self.idle_since         = None
        self.now_playing_msg    = None
        self.now_playing_msg_id = None
        self.accent_color       = None
        if self.progress_task and not self.progress_task.done():
            self.progress_task.cancel()
        self.progress_task = None
