import json
import time
from typing import Any, Protocol

from redis.asyncio import Redis


class Cache(Protocol):
    async def get(self, key: str) -> Any | None: ...
    async def set(self, key: str, value: Any) -> None: ...
    async def delete(self, key: str) -> None: ...


class MemoryCache:
    def __init__(self, ttl_seconds: int) -> None:
        self.ttl_seconds = ttl_seconds
        self.entries: dict[str, tuple[Any, float]] = {}

    async def get(self, key: str) -> Any | None:
        entry = self.entries.get(key)
        if entry is None:
            return None
        value, expires_at = entry
        if expires_at < time.monotonic():
            del self.entries[key]
            return None
        return value

    async def set(self, key: str, value: Any) -> None:
        self.entries[key] = (value, time.monotonic() + self.ttl_seconds)

    async def delete(self, key: str) -> None:
        self.entries.pop(key, None)


class RedisCache:
    def __init__(self, url: str, ttl_seconds: int) -> None:
        self.client = Redis.from_url(url, socket_timeout=0.5)
        self.ttl_seconds = ttl_seconds

    async def get(self, key: str) -> Any | None:
        raw = await self.client.get(key)
        return None if raw is None else json.loads(raw)

    async def set(self, key: str, value: Any) -> None:
        await self.client.set(key, json.dumps(value, default=str), ex=self.ttl_seconds)

    async def delete(self, key: str) -> None:
        await self.client.delete(key)

    async def close(self) -> None:
        await self.client.aclose()
