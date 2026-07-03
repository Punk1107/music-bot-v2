from __future__ import annotations

import time
from enum import Enum
from typing import Any, Awaitable, Callable


class CircuitBreakerState(Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class CircuitBreakerOpen(Exception):
    pass


class CircuitBreaker:
    def __init__(self, failure_threshold: int = 5, recovery_timeout: float = 60.0) -> None:
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.failure_count = 0
        self.last_failure_at: float | None = None
        self.state = CircuitBreakerState.CLOSED

    def allow_request(self) -> bool:
        if self.state != CircuitBreakerState.OPEN:
            return True
        if self.last_failure_at is None:
            return False
        if time.monotonic() - self.last_failure_at >= self.recovery_timeout:
            self.state = CircuitBreakerState.HALF_OPEN
            return True
        return False

    def record_success(self) -> None:
        self.failure_count = 0
        self.last_failure_at = None
        self.state = CircuitBreakerState.CLOSED

    def record_failure(self) -> None:
        self.failure_count += 1
        self.last_failure_at = time.monotonic()
        if self.failure_count >= self.failure_threshold:
            self.state = CircuitBreakerState.OPEN

    async def call(self, func: Callable[..., Awaitable[Any]], *args: Any, **kwargs: Any) -> Any:
        if not self.allow_request():
            raise CircuitBreakerOpen("Circuit breaker is open")
        try:
            result = await func(*args, **kwargs)
        except Exception:
            self.record_failure()
            raise
        self.record_success()
        return result
