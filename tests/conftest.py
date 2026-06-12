from __future__ import annotations

import os

os.environ.setdefault(
    "CERES_IDENTITY_DATABASE_URL",
    "sqlite+aiosqlite:///:memory:",
)
os.environ.setdefault(
    "CERES_IDENTITY_REDIS_URL",
    "redis://127.0.0.1:6379/15",
)
os.environ.setdefault(
    "CERES_IDENTITY_REFRESH_JWT_SECRET",
    "unit-test-refresh-secret-at-least-thirty-two-characters",
)
os.environ.setdefault(
    "CERES_IDENTITY_INTERNAL_API_KEY",
    "unit-test-internal-api-key-at-least-thirty-two-characters",
)
os.environ.setdefault("CERES_IDENTITY_BOOTSTRAP_SEED", "false")
os.environ.setdefault(
    "CERES_SEED_DEFAULT_TENANT_ID",
    "00000000-0000-4000-8000-000000000001",
)

import fakeredis.aioredis
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.db import get_session
from app.models.base import Base
from app.security.jwt_keys import reset_dev_key_cache_for_tests


@pytest.fixture
async def client():
    reset_dev_key_cache_for_tests()
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async def override_get_session():
        async with session_factory() as session:
            yield session

    fake_redis = fakeredis.aioredis.FakeRedis(decode_responses=True)

    from app.main import app

    app.dependency_overrides[get_session] = override_get_session
    app.state.redis = fake_redis

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac, session_factory

    app.dependency_overrides.clear()
    await engine.dispose()
