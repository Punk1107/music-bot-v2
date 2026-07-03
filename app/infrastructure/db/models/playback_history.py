from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, Integer, JSON

from app.infrastructure.db.base import Base


class PlaybackHistory(Base):
    __tablename__ = "playback_history"

    id = Column(Integer, primary_key=True)
    guild_id = Column(Integer, index=True)
    requester_id = Column(Integer)
    track_metadata = Column(JSON)
    skipped = Column(Boolean, default=False)
    played_at = Column(DateTime, default=datetime.utcnow)
