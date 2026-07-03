from __future__ import annotations

from dataclasses import asdict

from sqlalchemy import delete, func, select

from app.core.types import TrackMetadata
from app.infrastructure.db.models.guild_queue_item import GuildQueueItem
from app.infrastructure.db.session import get_session


class QueueRepository:
    def __init__(self, session_factory=get_session) -> None:
        self.session_factory = session_factory

    async def get_queue(self, guild_id: int) -> list[TrackMetadata]:
        async with self.session_factory() as session:
            result = await session.execute(
                select(GuildQueueItem).where(GuildQueueItem.guild_id == guild_id).order_by(GuildQueueItem.position)
            )
            rows = result.scalars().all()
            return [TrackMetadata(**row.track_metadata) for row in rows]

    async def append_track(
        self,
        guild_id: int,
        channel_id: int,
        track: TrackMetadata,
        requester_id: int,
    ) -> int:
        async with self.session_factory() as session:
            count = await session.scalar(select(func.count()).select_from(GuildQueueItem).where(GuildQueueItem.guild_id == guild_id))
            position = int(count or 0)
            item = GuildQueueItem(
                guild_id=guild_id,
                channel_id=channel_id,
                requester_id=requester_id,
                position=position,
                track_metadata=asdict(track),
            )
            session.add(item)
            await session.commit()
            await session.refresh(item)
            return position

    async def dequeue(self, guild_id: int):
        async with self.session_factory() as session:
            item = await session.scalar(
                select(GuildQueueItem).where(GuildQueueItem.guild_id == guild_id).order_by(GuildQueueItem.position).limit(1)
            )
            if item is None:
                return None
            await session.execute(delete(GuildQueueItem).where(GuildQueueItem.id == item.id))
            await session.commit()
            return item

    async def clear_queue(self, guild_id: int) -> None:
        async with self.session_factory() as session:
            await session.execute(delete(GuildQueueItem).where(GuildQueueItem.guild_id == guild_id))
            await session.commit()
