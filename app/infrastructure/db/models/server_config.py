from __future__ import annotations

from sqlalchemy import Boolean, Column, Integer

from app.infrastructure.db.base import Base


class ServerConfig(Base):
    __tablename__ = "server_configs"

    guild_id = Column(Integer, primary_key=True)
    announce_songs = Column(Boolean, default=True)
    effects_enabled = Column(Boolean, default=True)
    max_queue_size = Column(Integer, default=100)
