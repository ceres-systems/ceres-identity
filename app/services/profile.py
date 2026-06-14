from __future__ import annotations

import uuid

from fastapi import HTTPException, status
from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.schemas.auth import PasswordChangeRequest, ProfileUpdateRequest
from app.security.passwords import hash_password, verify_password
from app.security.refresh_store import revoke_refresh_for_user_except_session
from app.security.session_store import revoke_other_user_sessions


async def update_user_profile(
    session: AsyncSession,
    user: User,
    body: ProfileUpdateRequest,
) -> User:
    changed = False

    if body.display_name is not None and body.display_name != user.display_name:
        user.display_name = body.display_name
        changed = True

    if body.email is not None and body.email != user.email:
        existing = await session.scalar(
            select(User).where(User.email == body.email, User.id != user.id)
        )
        if existing is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Email already registered",
            )
        user.email = body.email
        changed = True

    if not changed:
        return user

    await session.commit()
    await session.refresh(user)
    return user


async def change_user_password(
    session: AsyncSession,
    redis: Redis,
    user: User,
    body: PasswordChangeRequest,
    *,
    current_session_id: uuid.UUID,
) -> None:
    if not verify_password(body.current_password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Current password is incorrect",
        )

    user.password_hash = hash_password(body.new_password)
    await session.commit()

    await revoke_other_user_sessions(redis, user.id, except_session_id=current_session_id)
    await revoke_refresh_for_user_except_session(
        redis, user.id, except_session_id=current_session_id
    )
