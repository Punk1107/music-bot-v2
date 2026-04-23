# -*- coding: utf-8 -*-
"""
utils/rate_limiter.py — Per-user, per-guild command rate limiter.
"""

from __future__ import annotations

import time
from collections import deque

import config


class RateLimiter:
    """
    Sliding-window rate limiter.

    Stores timestamps of recent invocations per (guild_id, user_id) pair.
    """

    def __init__(
        self,
        window:      int = config.RATE_LIMIT_WINDOW,
        max_requests: int = config.RATE_LIMIT_MAX_REQUESTS,
    ) -> None:
        self._window:       int                                  = window
        self._max_requests: int                                  = max_requests
        self._buckets:      dict[tuple[int, int], deque[float]]  = {}

    def is_rate_limited(self, guild_id: int, user_id: int) -> bool:
        """
        Return True if the user has exceeded the rate limit.
        Side-effect: records this invocation timestamp.
        """
        key = (guild_id, user_id)
        now = time.monotonic()

        if key not in self._buckets:
            self._buckets[key] = deque()

        bucket = self._buckets[key]

        # Prune timestamps outside the window
        while bucket and now - bucket[0] > self._window:
            bucket.popleft()

        if len(bucket) >= self._max_requests:
            return True

        bucket.append(now)
        return False

    def retry_after(self, guild_id: int, user_id: int) -> float:
        """
        Seconds until the oldest request falls out of the window.
        Returns 0 if not rate-limited.
        """
        key = (guild_id, user_id)
        bucket = self._buckets.get(key)
        if not bucket:
            return 0.0
        now = time.monotonic()
        oldest = bucket[0]
        remaining = self._window - (now - oldest)
        return max(0.0, remaining)
