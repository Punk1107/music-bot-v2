from __future__ import annotations

from datetime import datetime

from sqlalchemy import Column, DateTime, Integer, JSON

from app.infrastructure.db.base import Base


class GuildQueueItem(Base):
    __tablename__ = "guild_queue_items"

    id = Column(Integer, primary_key=True)
    guild_id = Column(Integer, index=True)
    channel_id = Column(Integer)
    requester_id = Column(Integer)
    position = Column(Integer)
    track_metadata = Column(JSON)
    created_at = Column(DateTime, default=datetime.utcnow)
