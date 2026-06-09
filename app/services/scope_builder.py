from __future__ import annotations

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.services.grants import load_active_grant_scopes
from app.services.scopes import ADMIN_SCOPE


def scope_claim_from_grant_list(scopes: list[str]) -> str:
    if ADMIN_SCOPE in scopes:
        return ADMIN_SCOPE
    return " ".join(scopes)


async def build_scope_claim(session: AsyncSession, user_id: uuid.UUID) -> str:
    scopes = await load_active_grant_scopes(session, user_id)
    return scope_claim_from_grant_list(scopes)


def scopes_from_claim(scope_claim: str) -> list[str]:
    if not scope_claim:
        return []
    return scope_claim.split()
