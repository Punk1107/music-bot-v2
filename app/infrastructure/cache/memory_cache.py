from __future__ import annotations

from time import time
from typing import Any


class MemoryCache:
    def __init__(self) -> None:
        self._store: dict[str, tuple[Any, float | None]] = {}

    def get(self, key: str) -> Any | None:
        value = self._store.get(key)
        if value is None:
            return None
        payload, expires_at = value
        if expires_at is not None and time() >= expires_at:
            self._store.pop(key, None)
            return None
        return payload

    def set(self, key: str, value: Any, ttl: float | None = None) -> None:
        expires_at = None if ttl is None else time() + ttl
        self._store[key] = (value, expires_at)

    def delete(self, key: str) -> None:
        self._store.pop(key, None)
