from __future__ import annotations

import uuid

import fakeredis.aioredis
import jwt
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.db import get_session
from app.models.base import Base
from app.models.user import User
from app.models.user_grant import UserGrant
from app.security.jwt_keys import reset_dev_key_cache_for_tests
from app.security.jwt_tokens import decode_access_token
from app.security.passwords import hash_password
from app.services.scopes import site_grant, tenant_grant


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


async def _seed_user(session_factory, grants: list[str]) -> tuple[str, str]:
    async with session_factory() as session:
        user = User(
            email="user@localhost",
            password_hash=hash_password("password-12chars"),
            display_name="Test User",
        )
        session.add(user)
        await session.flush()
        for scope in grants:
            session.add(UserGrant(user_id=user.id, scope=scope))
        await session.commit()
    return "user@localhost", "password-12chars"


@pytest.mark.asyncio
async def test_login_returns_sid_in_access_token(client) -> None:
    ac, session_factory = client
    tenant_a = uuid.UUID("aaaaaaaa-aaaa-4000-8000-000000000001")
    site_b1 = uuid.UUID("bbbbbbbb-bbbb-4000-8000-000000000001")
    await _seed_user(
        session_factory,
        [tenant_grant(tenant_a, "read"), site_grant(site_b1, "read")],
    )

    res = await ac.post(
        "/v1/auth/login",
        json={"email": "user@localhost", "password": "password-12chars"},
    )
    assert res.status_code == 200
    body = res.json()
    payload = decode_access_token(body["access_token"])
    assert "sid" in payload
    assert "scope" not in payload

    me = await ac.get(
        "/v1/auth/me",
        headers={"Authorization": f"Bearer {body['access_token']}"},
    )
    assert me.status_code == 200
    scopes = me.json()["scopes"]
    assert tenant_grant(tenant_a, "read") in scopes
    assert site_grant(site_b1, "read") in scopes


@pytest.mark.asyncio
async def test_login_rejected_without_grants(client) -> None:
    ac, session_factory = client
    await _seed_user(session_factory, [])

    res = await ac.post(
        "/v1/auth/login",
        json={"email": "user@localhost", "password": "password-12chars"},
    )
    assert res.status_code == 403


@pytest.mark.asyncio
async def test_refresh_reloads_grants(client) -> None:
    ac, session_factory = client
    tenant_id = uuid.uuid4()
    email, password = await _seed_user(session_factory, [tenant_grant(tenant_id, "read")])

    login = await ac.post(
        "/v1/auth/login",
        json={"email": email, "password": password},
    )
    assert login.status_code == 200
    old_payload = decode_access_token(login.json()["access_token"])
    old_sid = old_payload["sid"]

    new_site_id = uuid.uuid4()
    async with session_factory() as session:
        user = await session.scalar(select(User).where(User.email == email))
        assert user is not None
        session.add(UserGrant(user_id=user.id, scope=site_grant(new_site_id, "read")))
        await session.commit()

    refresh = await ac.post("/v1/auth/refresh")
    assert refresh.status_code == 200
    token = refresh.json()["access_token"]
    new_payload = decode_access_token(token)
    assert new_payload["sid"] != old_sid

    me = await ac.get(
        "/v1/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    scopes = me.json()["scopes"]
    assert tenant_grant(tenant_id, "read") in scopes
    assert site_grant(new_site_id, "read") in scopes


@pytest.mark.asyncio
async def test_jwks_endpoint(client) -> None:
    ac, _ = client
    res = await ac.get("/.well-known/jwks.json")
    assert res.status_code == 200
    keys = res.json()["keys"]
    assert keys[0]["kty"] == "RSA"
    assert keys[0]["alg"] == "RS256"
