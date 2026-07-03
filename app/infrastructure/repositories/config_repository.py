from __future__ import annotations

from sqlalchemy import select

from app.infrastructure.db.models.server_config import ServerConfig
from app.infrastructure.db.session import get_session


class ConfigRepository:
    def __init__(self, session_factory=get_session) -> None:
        self.session_factory = session_factory

    async def get_config(self, guild_id: int) -> ServerConfig | None:
        async with self.session_factory() as session:
            result = await session.execute(select(ServerConfig).where(ServerConfig.guild_id == guild_id))
            return result.scalar_one_or_none()

    async def save_config(self, config: ServerConfig) -> ServerConfig:
        async with self.session_factory() as session:
            session.add(config)
            await session.commit()
            await session.refresh(config)
            return config
