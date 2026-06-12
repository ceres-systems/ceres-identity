from typing import Annotated
from uuid import UUID

import jwt
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.responses import JSONResponse
from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db import get_session
from app.models.user import User
from app.schemas.auth import LoginRequest, TokenResponse, UserMe
from app.security.bearer_auth import AccessPayloadDep, user_id_from_payload
from app.security.jwt_tokens import decode_refresh_token, mint_refresh_token
from app.security.passwords import verify_password
from app.security.refresh_store import delete_refresh_jti, get_refresh_meta, store_refresh_jti
from app.security.session_store import create_session, get_session_user_id, revoke_session
from app.services.auth_tokens import mint_user_access_token
from app.services.grants import load_active_grant_scopes
from app.services.grants_cache import cache_user_grants

router = APIRouter(prefix="/v1/auth", tags=["auth"])

SessionDep = Annotated[AsyncSession, Depends(get_session)]


def _redis(request: Request) -> Redis:
    return request.app.state.redis


RedisDep = Annotated[Redis, Depends(_redis)]


def _refresh_ttl_seconds() -> int:
    return settings.refresh_token_expire_days * 24 * 60 * 60


def _refresh_cookie_params(*, max_age: int) -> dict:
    return {
        "key": settings.refresh_cookie_name,
        "httponly": True,
        "samesite": "lax",
        "secure": settings.cookie_secure,
        "max_age": max_age,
        "path": "/",
    }


def _clear_refresh_cookie(response: Response) -> None:
    response.delete_cookie(
        key=settings.refresh_cookie_name,
        path="/",
        httponly=True,
        samesite="lax",
        secure=settings.cookie_secure,
    )


async def _issue_tokens(
    redis: Redis,
    session: AsyncSession,
    user: User,
) -> tuple[str, int, str, int]:
    ttl = _refresh_ttl_seconds()
    session_id = await create_session(redis, user.id, ttl)
    grants = await load_active_grant_scopes(session, user.id)
    await cache_user_grants(redis, user.id, grants, ttl)
    access_token, expires_in = await mint_user_access_token(session, user, session_id)
    refresh_token, jti, refresh_ttl = mint_refresh_token(user.id)
    await store_refresh_jti(redis, jti, user.id, session_id, refresh_ttl)
    return access_token, expires_in, refresh_token, refresh_ttl


@router.post("/login")
async def login(
    body: LoginRequest,
    session: SessionDep,
    redis: RedisDep,
) -> JSONResponse:
    result = await session.execute(select(User).where(User.email == body.email))
    user = result.scalar_one_or_none()
    if user is None or not user.is_active or not verify_password(body.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    access_token, expires_in, refresh_token, ttl = await _issue_tokens(redis, session, user)

    payload = TokenResponse(access_token=access_token, expires_in=expires_in).model_dump()
    resp = JSONResponse(payload)
    resp.set_cookie(value=refresh_token, **_refresh_cookie_params(max_age=ttl))
    return resp


@router.post("/refresh")
async def refresh_tokens(
    request: Request,
    session: SessionDep,
    redis: RedisDep,
) -> JSONResponse:
    raw = request.cookies.get(settings.refresh_cookie_name)
    if not raw:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing refresh token",
        )
    try:
        payload = decode_refresh_token(raw)
        jti = str(payload["jti"])
        sub = str(payload["sub"])
    except (jwt.InvalidTokenError, jwt.ExpiredSignatureError, KeyError, TypeError) as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token",
        ) from exc

    meta = await get_refresh_meta(redis, jti)
    if meta is None or str(meta[0]) != sub:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token revoked or unknown",
        )

    user_id, old_session_id = meta
    await delete_refresh_jti(redis, jti)
    await revoke_session(redis, old_session_id)

    user = await session.get(User, user_id)
    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive",
        )

    access_token, expires_in, refresh_token, ttl = await _issue_tokens(redis, session, user)

    out = JSONResponse(
        TokenResponse(access_token=access_token, expires_in=expires_in).model_dump()
    )
    out.set_cookie(value=refresh_token, **_refresh_cookie_params(max_age=ttl))
    return out


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(request: Request, redis: RedisDep) -> Response:
    resp = Response(status_code=status.HTTP_204_NO_CONTENT)
    raw = request.cookies.get(settings.refresh_cookie_name)
    if raw:
        try:
            payload = decode_refresh_token(raw)
            jti = str(payload["jti"])
            meta = await get_refresh_meta(redis, jti)
            await delete_refresh_jti(redis, jti)
            if meta is not None:
                await revoke_session(redis, meta[1])
        except (jwt.InvalidTokenError, jwt.ExpiredSignatureError, KeyError, TypeError):
            pass
    _clear_refresh_cookie(resp)
    return resp


@router.get("/me", response_model=UserMe)
async def me(
    payload: AccessPayloadDep,
    session: SessionDep,
    redis: RedisDep,
) -> UserMe:
    user_id = user_id_from_payload(payload)
    session_id = UUID(str(payload["sid"]))
    owner = await get_session_user_id(redis, session_id)
    if owner is None or owner != user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session revoked or unknown",
        )

    user = await session.get(User, user_id)
    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive",
        )
    scopes = await load_active_grant_scopes(session, user_id)
    return UserMe(
        id=user.id,
        email=user.email,
        display_name=user.display_name,
        scopes=scopes,
    )
