# -*- coding: utf-8 -*-
"""models/track.py — Track dataclass."""

from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Optional


@dataclass
class Track:
    title:        str
    url:          str
    duration:     int                     # seconds
    thumbnail:    Optional[str] = None
    uploader:     Optional[str] = None
    view_count:   Optional[int] = None
    upload_date:  Optional[str] = None
    requester_id: int           = 0
    added_at:     datetime      = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )

    # ── Helpers ───────────────────────────────────────────────────────────────

    @property
    def duration_str(self) -> str:
        """Return HH:MM:SS or MM:SS string."""
        s = int(self.duration)
        h, rem = divmod(s, 3600)
        m, sec = divmod(rem, 60)
        if h:
            return f"{h}:{m:02d}:{sec:02d}"
        return f"{m}:{sec:02d}"

    @property
    def short_title(self) -> str:
        """Title truncated to 60 characters."""
        return (self.title[:57] + "…") if len(self.title) > 60 else self.title

    # ── Serialisation ─────────────────────────────────────────────────────────

    def to_dict(self) -> dict:
        data = asdict(self)
        data["added_at"] = self.added_at.isoformat()
        return data

    def to_json(self) -> str:
        return json.dumps(self.to_dict())

    @classmethod
    def from_dict(cls, data: dict) -> "Track":
        if isinstance(data.get("added_at"), str):
            data["added_at"] = datetime.fromisoformat(data["added_at"])
        return cls(**data)

    @classmethod
    def from_json(cls, raw: str) -> "Track":
        return cls.from_dict(json.loads(raw))
