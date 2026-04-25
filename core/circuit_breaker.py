# -*- coding: utf-8 -*-
"""
core/circuit_breaker.py — Circuit Breaker pattern for external API calls.

Implements a thread-safe, asyncio-native circuit breaker with three states:

  CLOSED    → Healthy. All calls pass through normally.
  OPEN      → Tripped. Calls are blocked immediately with CircuitBreakerOpen
              exception. After recovery_window seconds, transitions to HALF-OPEN.
  HALF-OPEN → Probe state. One call is allowed through. If it succeeds, resets
              to CLOSED. If it fails, returns to OPEN.

Usage:
    breaker = CircuitBreaker(name="youtube", failure_threshold=5, recovery_window=60)

    try:
        result = await breaker.call(some_coroutine_func, arg1, arg2)
    except CircuitBreakerOpen as e:
        await channel.send(embed=system_busy_embed())
"""

from __future__ import annotations

import asyncio
import logging
import time
from enum import Enum
from typing import Any, Callable, Coroutine, Optional

logger = logging.getLogger(__name__)


class BreakerState(Enum):
    CLOSED    = "closed"
    OPEN      = "open"
    HALF_OPEN = "half_open"


class CircuitBreakerOpen(Exception):
    """Raised when a call is rejected because the circuit breaker is OPEN."""
    def __init__(self, name: str, retry_after: float) -> None:
        self.name        = name
        self.retry_after = retry_after
        super().__init__(
            f"Circuit breaker '{name}' is OPEN. "
            f"Retry after {retry_after:.0f}s."
        )


class CircuitBreaker:
    """
    Asyncio-native circuit breaker.

    Args:
        name:              Human-readable identifier for logging.
        failure_threshold: Consecutive failures before tripping (default 5).
        recovery_window:   Seconds to stay OPEN before trying HALF-OPEN (default 60).
        success_threshold: Successes in HALF-OPEN to confirm recovery (default 1).
    """

    def __init__(
        self,
        name:              str,
        failure_threshold: int   = 5,
        recovery_window:   float = 60.0,
        success_threshold: int   = 1,
    ) -> None:
        self.name              = name
        self._failure_threshold = failure_threshold
        self._recovery_window   = recovery_window
        self._success_threshold = success_threshold

        self._state:          BreakerState    = BreakerState.CLOSED
        self._failure_count:  int             = 0
        self._success_count:  int             = 0
        self._last_failure_at: Optional[float] = None
        self._lock:           asyncio.Lock    = asyncio.Lock()

    # ── Public API ────────────────────────────────────────────────────────────

    @property
    def state(self) -> BreakerState:
        return self._state

    @property
    def is_open(self) -> bool:
        return self._state == BreakerState.OPEN

    async def call(
        self,
        func: Callable[..., Coroutine[Any, Any, Any]],
        *args: Any,
        **kwargs: Any,
    ) -> Any:
        """
        Execute *func(*args, **kwargs)* through the circuit breaker.

        Raises:
            CircuitBreakerOpen: If the breaker is OPEN and the recovery window
                                has not yet elapsed.
        """
        async with self._lock:
            state = await self._check_state()
            if state == BreakerState.OPEN:
                retry_after = self._retry_after_seconds()
                raise CircuitBreakerOpen(self.name, retry_after)

        try:
            result = await func(*args, **kwargs)
            await self._on_success()
            return result
        except CircuitBreakerOpen:
            raise   # Don't count nested breaker calls as failures
        except Exception as exc:
            await self._on_failure(exc)
            raise

    def reset(self) -> None:
        """Manually reset the breaker to CLOSED state (e.g. after operator fix)."""
        self._state         = BreakerState.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._last_failure_at = None
        logger.info("CircuitBreaker '%s' manually reset to CLOSED.", self.name)

    # ── Internals ─────────────────────────────────────────────────────────────

    async def _check_state(self) -> BreakerState:
        """
        Transition OPEN → HALF-OPEN if recovery_window has elapsed.
        Called under self._lock.
        """
        if self._state == BreakerState.OPEN:
            if self._last_failure_at is not None:
                elapsed = time.monotonic() - self._last_failure_at
                if elapsed >= self._recovery_window:
                    self._state         = BreakerState.HALF_OPEN
                    self._success_count = 0
                    logger.info(
                        "CircuitBreaker '%s': OPEN → HALF-OPEN after %.0fs.",
                        self.name, elapsed,
                    )
        return self._state

    async def _on_success(self) -> None:
        async with self._lock:
            if self._state == BreakerState.HALF_OPEN:
                self._success_count += 1
                if self._success_count >= self._success_threshold:
                    self._state         = BreakerState.CLOSED
                    self._failure_count = 0
                    self._success_count = 0
                    logger.info(
                        "CircuitBreaker '%s': HALF-OPEN → CLOSED (recovered).",
                        self.name,
                    )
            elif self._state == BreakerState.CLOSED:
                # Reset failure streak on any success
                self._failure_count = 0

    async def _on_failure(self, exc: Exception) -> None:
        async with self._lock:
            self._failure_count   += 1
            self._last_failure_at  = time.monotonic()

            if self._state == BreakerState.HALF_OPEN:
                self._state = BreakerState.OPEN
                logger.warning(
                    "CircuitBreaker '%s': HALF-OPEN → OPEN (probe failed: %s).",
                    self.name, exc,
                )
            elif (
                self._state == BreakerState.CLOSED
                and self._failure_count >= self._failure_threshold
            ):
                self._state = BreakerState.OPEN
                logger.error(
                    "CircuitBreaker '%s': CLOSED → OPEN after %d consecutive failures. "
                    "Last error: %s",
                    self.name, self._failure_count, exc,
                )

    def _retry_after_seconds(self) -> float:
        if self._last_failure_at is None:
            return self._recovery_window
        elapsed = time.monotonic() - self._last_failure_at
        return max(0.0, self._recovery_window - elapsed)

    def __repr__(self) -> str:
        return (
            f"<CircuitBreaker name={self.name!r} state={self._state.value} "
            f"failures={self._failure_count}>"
        )
