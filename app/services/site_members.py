from __future__ import annotations

import uuid
from typing import Literal

from fastapi import HTTPException, status
from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.schemas.internal import (
    SiteMemberAdd,
    SiteMemberCreate,
    SiteMemberRead,
    SiteMemberUpdate,
)
from app.security.passwords import hash_password
from app.services.grants import (
    get_site_member_grant_action,
    list_users_for_site,
    load_active_grant_scopes,
    remove_site_membership,
    set_site_grant,
)
from app.services.grants_cache import revoke_user_auth

# Temporary until invite/onboarding sets credentials; login still requires 8+ chars.
INVITED_USER_DEFAULT_PASSWORD = "1234"


def _display_name_from_email(email: str) -> str:
    local = email.split("@", 1)[0].strip()
    return local or email


def _to_read(user: User, grant_action: Literal["read", "write"]) -> SiteMemberRead:
    return SiteMemberRead(
        id=user.id,
        email=user.email,
        display_name=user.display_name,
        is_active=user.is_active,
        grant_action=grant_action,
        created_at=user.created_at,
        updated_at=user.updated_at,
    )


async def list_site_members(
    session: AsyncSession, site_id: uuid.UUID
) -> list[SiteMemberRead]:
    rows = await list_users_for_site(session, site_id)
    return [_to_read(user, action) for user, action in rows]


async def create_site_member(
    session: AsyncSession,
    redis: Redis,
    body: SiteMemberCreate,
) -> SiteMemberRead:
    existing = await session.scalar(select(User).where(User.email == body.email))
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already registered",
        )

    user = User(
        email=body.email,
        password_hash=hash_password(INVITED_USER_DEFAULT_PASSWORD),
        display_name=_display_name_from_email(body.email),
        is_active=True,
    )
    session.add(user)
    await session.flush()
    await set_site_grant(session, user.id, body.site_id, body.grant_action)
    await session.commit()
    await session.refresh(user)
    return _to_read(user, body.grant_action)


async def add_site_member(
    session: AsyncSession,
    redis: Redis,
    body: SiteMemberAdd,
) -> SiteMemberRead:
    user = await session.scalar(select(User).where(User.email == body.email))
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    current_action = await get_site_member_grant_action(session, user.id, body.site_id)
    if current_action is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Already a member of this site",
        )

    await set_site_grant(session, user.id, body.site_id, body.grant_action)
    await session.commit()
    await session.refresh(user)
    await revoke_user_auth(redis, user.id)
    return _to_read(user, body.grant_action)


async def update_site_member(
    session: AsyncSession,
    redis: Redis,
    user_id: uuid.UUID,
    body: SiteMemberUpdate,
) -> SiteMemberRead:
    user = await session.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    current_action = await get_site_member_grant_action(session, user_id, body.site_id)
    if current_action is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User is not a member of this site",
        )

    changed_auth = False
    if body.is_active is not None and body.is_active != user.is_active:
        user.is_active = body.is_active
        changed_auth = True
    if body.grant_action is not None and body.grant_action != current_action:
        await set_site_grant(session, user_id, body.site_id, body.grant_action)
        current_action = body.grant_action
        changed_auth = True

    await session.commit()
    await session.refresh(user)

    if changed_auth:
        await revoke_user_auth(redis, user_id)

    return _to_read(user, current_action)


async def delete_site_member(
    session: AsyncSession,
    redis: Redis,
    user_id: uuid.UUID,
    site_id: uuid.UUID,
) -> None:
    user = await session.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    removed = await remove_site_membership(session, user_id, site_id)
    if not removed:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User is not a member of this site",
        )

    await session.commit()
    await revoke_user_auth(redis, user_id)

    remaining = await load_active_grant_scopes(session, user_id)
    if not remaining and user.is_active:
        user.is_active = False
        await session.commit()
