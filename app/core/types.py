from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class TrackMetadata:
    id: str
    title: str
    duration: int
    source: str
    url: str
    requester_id: int
    thumbnail_url: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class EnqueueResult:
    track: TrackMetadata
    position: int
