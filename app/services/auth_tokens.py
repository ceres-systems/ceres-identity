from __future__ import annotations

import uuid

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.services.scope_builder import build_scope_claim, scopes_from_claim
from app.security.jwt_tokens import mint_access_token


async def mint_user_access_token(session: AsyncSession, user: User) -> tuple[str, int]:
    scope_claim = await build_scope_claim(session, user.id)
    if not scope_claim:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account has no active grants",
        )
    return mint_access_token(
        user_id=user.id,
        email=user.email,
        display_name=user.display_name,
        scope_claim=scope_claim,
    )


def scopes_for_user_from_claim(scope_claim: str) -> list[str]:
    return scopes_from_claim(scope_claim)
