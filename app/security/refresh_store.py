from __future__ import annotations

import uuid

from redis.asyncio import Redis

from app.config import settings


def _key(jti: str) -> str:
    return f"{settings.redis_refresh_key_prefix}{jti}"


async def store_refresh_jti(redis: Redis, jti: str, user_id: uuid.UUID, ttl_seconds: int) -> None:
    await redis.set(_key(jti), str(user_id), ex=ttl_seconds)


async def get_refresh_user_id(redis: Redis, jti: str) -> str | None:
    return await redis.get(_key(jti))


async def delete_refresh_jti(redis: Redis, jti: str) -> None:
    await redis.delete(_key(jti))
