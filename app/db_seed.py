from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.user import User
from app.security.passwords import hash_password
from app.services.grants import ensure_grant
from app.services.scopes import tenant_scope


async def ensure_bootstrap_seed(session: AsyncSession) -> None:
    if not settings.bootstrap_seed:
        return

    email = settings.seed_email
    result = await session.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()
    if user is None:
        user = User(
            email=email,
            password_hash=hash_password(settings.seed_password_value()),
            display_name=settings.seed_display_name,
        )
        session.add(user)
        await session.flush()

    await ensure_grant(session, user.id, tenant_scope(settings.seed_default_tenant_id))
