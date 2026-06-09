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
from app.security.refresh_store import delete_refresh_jti, get_refresh_user_id, store_refresh_jti
from app.services.auth_tokens import mint_user_access_token, scopes_for_user_from_claim

router = APIRouter(prefix="/v1/auth", tags=["auth"])

SessionDep = Annotated[AsyncSession, Depends(get_session)]


def _redis(request: Request) -> Redis:
    return request.app.state.redis


RedisDep = Annotated[Redis, Depends(_redis)]


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

    access_token, expires_in = await mint_user_access_token(session, user)
    refresh_token, jti, ttl = mint_refresh_token(user.id)
    await store_refresh_jti(redis, jti, user.id, ttl)

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

    owner = await get_refresh_user_id(redis, jti)
    if owner is None or owner != sub:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token revoked or unknown",
        )

    await delete_refresh_jti(redis, jti)
    user_id = UUID(sub)
    user = await session.get(User, user_id)
    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive",
        )

    access_token, expires_in = await mint_user_access_token(session, user)
    refresh_token, new_jti, ttl = mint_refresh_token(user.id)
    await store_refresh_jti(redis, new_jti, user.id, ttl)

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
            await delete_refresh_jti(redis, jti)
        except (jwt.InvalidTokenError, jwt.ExpiredSignatureError, KeyError, TypeError):
            pass
    _clear_refresh_cookie(resp)
    return resp


@router.get("/me", response_model=UserMe)
async def me(payload: AccessPayloadDep, session: SessionDep) -> UserMe:
    user_id = user_id_from_payload(payload)
    user = await session.get(User, user_id)
    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive",
        )
    scope_claim = str(payload.get("scope", ""))
    return UserMe(
        id=user.id,
        email=user.email,
        display_name=user.display_name,
        scopes=scopes_for_user_from_claim(scope_claim),
    )
