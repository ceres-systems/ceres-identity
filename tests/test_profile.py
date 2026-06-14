from __future__ import annotations

import uuid

import pytest
from sqlalchemy import select

from app.models.user import User
from app.models.user_grant import UserGrant
from app.security.jwt_tokens import decode_access_token
from app.security.passwords import hash_password, verify_password
from app.services.scopes import site_grant


async def _seed_user(session_factory, *, email: str = "user@localhost") -> tuple[str, str]:
    async with session_factory() as session:
        user = User(
            email=email,
            password_hash=hash_password("old-password-12"),
            display_name="Test User",
        )
        session.add(user)
        await session.flush()
        session.add(UserGrant(user_id=user.id, scope=site_grant(uuid.uuid4(), "read")))
        await session.commit()
    return email, "old-password-12"


async def _login(ac, email: str, password: str) -> str:
    res = await ac.post(
        "/v1/auth/login",
        json={"email": email, "password": password},
    )
    assert res.status_code == 200
    return res.json()["access_token"]


@pytest.mark.asyncio
async def test_update_display_name(client) -> None:
    ac, session_factory = client
    email, password = await _seed_user(session_factory)
    token = await _login(ac, email, password)

    res = await ac.patch(
        "/v1/auth/me",
        headers={"Authorization": f"Bearer {token}"},
        json={"display_name": "Updated Name"},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["display_name"] == "Updated Name"
    assert body["email"] == email

    async with session_factory() as session:
        user = await session.scalar(select(User).where(User.email == email))
        assert user is not None
        assert user.display_name == "Updated Name"


@pytest.mark.asyncio
async def test_update_email(client) -> None:
    ac, session_factory = client
    email, password = await _seed_user(session_factory)
    token = await _login(ac, email, password)

    res = await ac.patch(
        "/v1/auth/me",
        headers={"Authorization": f"Bearer {token}"},
        json={"email": "new@localhost"},
    )
    assert res.status_code == 200
    assert res.json()["email"] == "new@localhost"


@pytest.mark.asyncio
async def test_update_email_conflict(client) -> None:
    ac, session_factory = client
    email, password = await _seed_user(session_factory)
    await _seed_user(session_factory, email="taken@localhost")
    token = await _login(ac, email, password)

    res = await ac.patch(
        "/v1/auth/me",
        headers={"Authorization": f"Bearer {token}"},
        json={"email": "taken@localhost"},
    )
    assert res.status_code == 409
    assert res.json()["detail"] == "Email already registered"


@pytest.mark.asyncio
async def test_update_me_requires_field(client) -> None:
    ac, session_factory = client
    email, password = await _seed_user(session_factory)
    token = await _login(ac, email, password)

    res = await ac.patch(
        "/v1/auth/me",
        headers={"Authorization": f"Bearer {token}"},
        json={},
    )
    assert res.status_code == 422


@pytest.mark.asyncio
async def test_change_password(client) -> None:
    ac, session_factory = client
    email, password = await _seed_user(session_factory)
    token = await _login(ac, email, password)

    res = await ac.patch(
        "/v1/auth/password",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "current_password": password,
            "new_password": "new-password-12",
        },
    )
    assert res.status_code == 204

    async with session_factory() as session:
        user = await session.scalar(select(User).where(User.email == email))
        assert user is not None
        assert verify_password("new-password-12", user.password_hash)

    login_old = await ac.post(
        "/v1/auth/login",
        json={"email": email, "password": password},
    )
    assert login_old.status_code == 401

    login_new = await ac.post(
        "/v1/auth/login",
        json={"email": email, "password": "new-password-12"},
    )
    assert login_new.status_code == 200


@pytest.mark.asyncio
async def test_change_password_wrong_current(client) -> None:
    ac, session_factory = client
    email, password = await _seed_user(session_factory)
    token = await _login(ac, email, password)

    res = await ac.patch(
        "/v1/auth/password",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "current_password": "wrong-password",
            "new_password": "new-password-12",
        },
    )
    assert res.status_code == 401
    assert res.json()["detail"] == "Current password is incorrect"


@pytest.mark.asyncio
async def test_change_password_keeps_current_session(client) -> None:
    ac, session_factory = client
    email, password = await _seed_user(session_factory)
    token = await _login(ac, email, password)
    sid = decode_access_token(token)["sid"]

    res = await ac.patch(
        "/v1/auth/password",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "current_password": password,
            "new_password": "new-password-12",
        },
    )
    assert res.status_code == 204

    me = await ac.get(
        "/v1/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert me.status_code == 200
    assert decode_access_token(token)["sid"] == sid

    refresh = await ac.post("/v1/auth/refresh")
    assert refresh.status_code == 200
