from __future__ import annotations

try:
    import redis.asyncio as aioredis
except Exception:  # pragma: no cover
    aioredis = None


class RedisClient:
    def __init__(self, url: str) -> None:
        if aioredis is None:
            raise RuntimeError("redis.asyncio is unavailable")
        self._redis = aioredis.from_url(url, decode_responses=True)

    async def get(self, key: str):
        return await self._redis.get(key)

    async def set(self, key: str, value: str, expire: int | None = None) -> None:
        await self._redis.set(key, value, ex=expire)

    async def delete(self, key: str) -> None:
        await self._redis.delete(key)

    async def close(self) -> None:
        await self._redis.close()
