from __future__ import annotations
from typing import Literal
import uuid

from fastapi import HTTPException, status
from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.site_pin import SitePin
from app.models.user import User
from app.schemas.internal import (
    SiteMemberAdd,
    SiteMemberCreate,
    SiteMemberRead,
    SiteMemberUpdate,
)
from app.security.passwords import hash_password
from app.security.pins import hash_pin, validate_pin
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


def _to_read(
    user: User,
    grant_action: Literal["read", "write"],
    *,
    has_kiosk_pin: bool,
) -> SiteMemberRead:
    return SiteMemberRead(
        id=user.id,
        email=user.email,
        display_name=user.display_name,
        is_active=user.is_active,
        grant_action=grant_action,
        has_kiosk_pin=has_kiosk_pin,
        created_at=user.created_at,
        updated_at=user.updated_at,
    )


async def _user_ids_with_pin(
    session: AsyncSession, site_id: uuid.UUID
) -> set[uuid.UUID]:
    result = await session.execute(
        select(SitePin.user_id).where(SitePin.site_id == site_id)
    )
    return set(result.scalars().all())


async def _set_site_pin(
    session: AsyncSession,
    *,
    site_id: uuid.UUID,
    user_id: uuid.UUID,
    pin: str | None,
) -> None:
    """Set or clear this user's PIN at ``site_id``. Clash → 409."""
    existing = await session.get(SitePin, {"site_id": site_id, "user_id": user_id})
    if pin is None or pin == "":
        if existing is not None:
            await session.delete(existing)
        return

    try:
        validate_pin(pin)
    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(error),
        ) from error

    digest = hash_pin(pin, site_id=site_id)
    clash = await session.scalar(
        select(SitePin).where(
            SitePin.site_id == site_id,
            SitePin.pin_hmac == digest,
            SitePin.user_id != user_id,
        )
    )
    if clash is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This PIN is already assigned to another user at this site",
        )

    if existing is None:
        session.add(SitePin(site_id=site_id, user_id=user_id, pin_hmac=digest))
    else:
        existing.pin_hmac = digest


async def list_site_members(
    session: AsyncSession, site_id: uuid.UUID
) -> list[SiteMemberRead]:
    rows = await list_users_for_site(session, site_id)
    pin_users = await _user_ids_with_pin(session, site_id)
    return [
        _to_read(user, action, has_kiosk_pin=user.id in pin_users)
        for user, action in rows
    ]


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
    return _to_read(user, body.grant_action, has_kiosk_pin=False)


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
    pin_users = await _user_ids_with_pin(session, body.site_id)
    return _to_read(user, body.grant_action, has_kiosk_pin=user.id in pin_users)


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

    # kiosk_pin: omit (not in model_fields_set) = unchanged;
    # present as null or "" = clear; 4 digits = set.
    if "kiosk_pin" in body.model_fields_set:
        await _set_site_pin(
            session, site_id=body.site_id, user_id=user_id, pin=body.kiosk_pin
        )
        changed_auth = True

    await session.commit()
    await session.refresh(user)

    if changed_auth:
        await revoke_user_auth(redis, user_id)

    pin_users = await _user_ids_with_pin(session, body.site_id)
    return _to_read(user, current_action, has_kiosk_pin=user_id in pin_users)


async def set_user_pin(
    session: AsyncSession,
    redis: Redis,
    user_id: uuid.UUID,
    site_id: uuid.UUID,
    pin: str | None,
) -> None:
    """Set or clear a user's kiosk PIN for a site (internal API)."""
    user = await session.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    membership = await get_site_member_grant_action(session, user_id, site_id)
    if membership is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User is not a member of this site",
        )

    await _set_site_pin(session, site_id=site_id, user_id=user_id, pin=pin)
    await session.commit()
    await revoke_user_auth(redis, user_id)


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

    # Drop the site PIN with membership — login is site-scoped.
    site_pin = await session.get(SitePin, {"site_id": site_id, "user_id": user_id})
    if site_pin is not None:
        await session.delete(site_pin)

    await session.commit()
    await revoke_user_auth(redis, user_id)

    remaining = await load_active_grant_scopes(session, user_id)
    if not remaining and user.is_active:
        user.is_active = False
        await session.commit()
