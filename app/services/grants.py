from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user_grant import UserGrant


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
    existing = await session.get(UserGrant, {"user_id": user_id, "scope": scope})
    if existing is None:
        session.add(UserGrant(user_id=user_id, scope=scope))
