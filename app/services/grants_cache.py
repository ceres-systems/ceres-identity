from __future__ import annotations

import json
import uuid

from redis.asyncio import Redis

from app.config import settings
from app.security.refresh_store import revoke_refresh_for_user
from app.security.session_store import revoke_all_user_sessions


def _grants_key(user_id: uuid.UUID) -> str:
    return f"{settings.redis_grants_key_prefix}{user_id}"


async def cache_user_grants(
    redis: Redis, user_id: uuid.UUID, scopes: list[str], ttl_seconds: int
) -> None:
    await redis.set(_grants_key(user_id), json.dumps(scopes), ex=ttl_seconds)


async def invalidate_user_grants(redis: Redis, user_id: uuid.UUID) -> None:
    await redis.delete(_grants_key(user_id))


async def revoke_user_auth(redis: Redis, user_id: uuid.UUID) -> None:
    await invalidate_user_grants(redis, user_id)
    await revoke_all_user_sessions(redis, user_id)
    await revoke_refresh_for_user(redis, user_id)
