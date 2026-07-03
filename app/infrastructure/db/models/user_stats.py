from __future__ import annotations

from sqlalchemy import Column, Integer

from app.infrastructure.db.base import Base


class UserStats(Base):
    __tablename__ = "user_stats"

    id = Column(Integer, primary_key=True)
    guild_id = Column(Integer, index=True)
    user_id = Column(Integer, index=True)
    tracks_played = Column(Integer, default=0)
