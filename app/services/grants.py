from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Literal

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.models.user_grant import UserGrant
from app.services.grant_normalize import normalize_grants
from app.services.scopes import site_grant


async def load_active_grant_scopes(
    session: AsyncSession, user_id: uuid.UUID
) -> list[str]:
    now = datetime.now(timezone.utc)
    stmt = (
        select(UserGrant.scope)
        .where(UserGrant.user_id == user_id)
        .where(or_(UserGrant.expires_at.is_(None), UserGrant.expires_at > now))
        .order_by(UserGrant.scope)
    )
    result = await session.execute(stmt)
    return [row[0] for row in result.all()]


async def ensure_grant(
    session: AsyncSession, user_id: uuid.UUID, scope: str
) -> None:
    normalized = normalize_grants([scope])
    if not normalized:
        return
    scope = normalized[0]
    existing = await session.get(UserGrant, {"user_id": user_id, "scope": scope})
    if existing is None:
        session.add(UserGrant(user_id=user_id, scope=scope))


async def remove_grant(
    session: AsyncSession, user_id: uuid.UUID, scope: str
) -> bool:
    existing = await session.get(UserGrant, {"user_id": user_id, "scope": scope})
    if existing is None:
        return False
    await session.delete(existing)
    return True


async def set_site_grant(
    session: AsyncSession,
    user_id: uuid.UUID,
    site_id: uuid.UUID,
    action: Literal["read", "write"],
) -> None:
    read_scope = site_grant(site_id, "read")
    write_scope = site_grant(site_id, "write")
    if action == "write":
        await remove_grant(session, user_id, read_scope)
        await ensure_grant(session, user_id, write_scope)
    else:
        await remove_grant(session, user_id, write_scope)
        await ensure_grant(session, user_id, read_scope)


async def list_users_for_site(
    session: AsyncSession, site_id: uuid.UUID
) -> list[tuple[User, Literal["read", "write"]]]:
    read_scope = site_grant(site_id, "read")
    write_scope = site_grant(site_id, "write")
    stmt = (
        select(User, UserGrant.scope)
        .join(UserGrant, UserGrant.user_id == User.id)
        .where(UserGrant.scope.in_([read_scope, write_scope]))
        .order_by(User.display_name, User.email)
    )
    result = await session.execute(stmt)
    rows: list[tuple[User, Literal["read", "write"]]] = []
    for user, scope in result.all():
        action: Literal["read", "write"] = "write" if scope == write_scope else "read"
        rows.append((user, action))
    return rows


async def remove_site_membership(
    session: AsyncSession, user_id: uuid.UUID, site_id: uuid.UUID
) -> bool:
    removed = False
    for action in ("read", "write"):
        if await remove_grant(session, user_id, site_grant(site_id, action)):
            removed = True
    return removed


async def get_site_member_grant_action(
    session: AsyncSession, user_id: uuid.UUID, site_id: uuid.UUID
) -> Literal["read", "write"] | None:
    write_scope = site_grant(site_id, "write")
    read_scope = site_grant(site_id, "read")
    if await session.get(UserGrant, {"user_id": user_id, "scope": write_scope}) is not None:
        return "write"
    if await session.get(UserGrant, {"user_id": user_id, "scope": read_scope}) is not None:
        return "read"
    return None
