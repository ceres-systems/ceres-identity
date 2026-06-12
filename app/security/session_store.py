from __future__ import annotations

import uuid

from redis.asyncio import Redis

from app.config import settings
from app.security.redis_async import redis_pipeline_execute, redis_sadd, redis_smembers, redis_srem


def _session_key(session_id: uuid.UUID) -> str:
    return f"{settings.redis_session_key_prefix}{session_id}"


def _user_sessions_key(user_id: uuid.UUID) -> str:
    return f"{settings.redis_user_sessions_key_prefix}{user_id}:sessions"


async def create_session(
    redis: Redis, user_id: uuid.UUID, ttl_seconds: int
) -> uuid.UUID:
    session_id = uuid.uuid4()
    await redis.set(_session_key(session_id), str(user_id), ex=ttl_seconds)
    await redis_sadd(redis, _user_sessions_key(user_id), str(session_id))
    return session_id


async def get_session_user_id(redis: Redis, session_id: uuid.UUID) -> uuid.UUID | None:
    raw = await redis.get(_session_key(session_id))
    if raw is None:
        return None
    return uuid.UUID(raw)


async def revoke_session(redis: Redis, session_id: uuid.UUID) -> None:
    user_raw = await redis.get(_session_key(session_id))
    await redis.delete(_session_key(session_id))
    if user_raw is not None:
        await redis_srem(redis, _user_sessions_key(uuid.UUID(user_raw)), str(session_id))


async def revoke_all_user_sessions(redis: Redis, user_id: uuid.UUID) -> None:
    session_ids = await redis_smembers(redis, _user_sessions_key(user_id))
    if not session_ids:
        return
    pipe = redis.pipeline()
    for sid in session_ids:
        pipe.delete(f"{settings.redis_session_key_prefix}{sid}")
    pipe.delete(_user_sessions_key(user_id))
    await redis_pipeline_execute(pipe)
