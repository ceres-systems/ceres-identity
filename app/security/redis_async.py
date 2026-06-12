"""Typed wrappers for redis.asyncio commands with sync/async union stubs."""

from __future__ import annotations

from collections.abc import Awaitable, Set
from typing import cast

from redis.asyncio import Redis
from redis.asyncio.client import Pipeline


async def redis_sadd(redis: Redis, key: str, *values: str) -> int:
    return await cast(Awaitable[int], redis.sadd(key, *values))


async def redis_srem(redis: Redis, key: str, *values: str) -> int:
    return await cast(Awaitable[int], redis.srem(key, *values))


async def redis_smembers(redis: Redis, key: str) -> Set[str]:
    return await cast(Awaitable[Set[str]], redis.smembers(key))


async def redis_pipeline_execute(pipe: Pipeline) -> list[object]:
    return await cast(Awaitable[list[object]], pipe.execute())
