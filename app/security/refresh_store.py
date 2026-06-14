from __future__ import annotations

import uuid

from redis.asyncio import Redis

from app.config import settings
from app.security.redis_async import (
    redis_pipeline_execute,
    redis_sadd,
    redis_smembers,
    redis_srem,
)


def _key(jti: str) -> str:
    return f"{settings.redis_refresh_key_prefix}{jti}"


def _user_refresh_set_key(user_id: uuid.UUID) -> str:
    return (
        f"{settings.redis_user_sessions_key_prefix}{user_id}"
        f"{settings.redis_user_refresh_key_suffix}"
    )


async def store_refresh_jti(
    redis: Redis,
    jti: str,
    user_id: uuid.UUID,
    session_id: uuid.UUID,
    ttl_seconds: int,
) -> None:
    await redis.set(
        _key(jti),
        f"{user_id}:{session_id}",
        ex=ttl_seconds,
    )
    await redis_sadd(redis, _user_refresh_set_key(user_id), jti)


async def get_refresh_meta(
    redis: Redis, jti: str
) -> tuple[uuid.UUID, uuid.UUID] | None:
    raw = await redis.get(_key(jti))
    if raw is None:
        return None
    user_part, session_part = raw.split(":", 1)
    return uuid.UUID(user_part), uuid.UUID(session_part)


async def delete_refresh_jti(redis: Redis, jti: str) -> None:
    raw = await redis.get(_key(jti))
    await redis.delete(_key(jti))
    if raw is None:
        return
    user_id = uuid.UUID(raw.split(":", 1)[0])
    await redis_srem(redis, _user_refresh_set_key(user_id), jti)


async def revoke_refresh_for_user(redis: Redis, user_id: uuid.UUID) -> None:
    jtis = await redis_smembers(redis, _user_refresh_set_key(user_id))
    if not jtis:
        return
    pipe = redis.pipeline()
    for jti in jtis:
        pipe.delete(_key(jti))
    pipe.delete(_user_refresh_set_key(user_id))
    await redis_pipeline_execute(pipe)


async def revoke_refresh_for_user_except_session(
    redis: Redis, user_id: uuid.UUID, *, except_session_id: uuid.UUID
) -> None:
    jtis = await redis_smembers(redis, _user_refresh_set_key(user_id))
    if not jtis:
        return
    keep = str(except_session_id)
    for jti in jtis:
        meta = await get_refresh_meta(redis, jti)
        if meta is None:
            await redis_srem(redis, _user_refresh_set_key(user_id), jti)
            continue
        if str(meta[1]) == keep:
            continue
        await delete_refresh_jti(redis, jti)
