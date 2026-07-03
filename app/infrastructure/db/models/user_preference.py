from __future__ import annotations

from sqlalchemy import Column, Integer, JSON

from app.infrastructure.db.base import Base


class UserPreference(Base):
    __tablename__ = "user_preferences"

    id = Column(Integer, primary_key=True)
    guild_id = Column(Integer, index=True)
    user_id = Column(Integer, index=True)
    preferences = Column(JSON, default=dict)
