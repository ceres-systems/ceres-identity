from __future__ import annotations

import uuid

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.security.jwt_tokens import mint_access_token
from app.services.grants import load_active_grant_scopes


async def mint_user_access_token(
    session: AsyncSession,
    user: User,
    session_id: uuid.UUID,
) -> tuple[str, int]:
    grants = await load_active_grant_scopes(session, user.id)
    if not grants:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account has no active grants",
        )
    return mint_access_token(
        user_id=user.id,
        session_id=session_id,
        email=user.email,
        display_name=user.display_name,
    )
