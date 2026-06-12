from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

import jwt

from app.config import settings
from app.security.jwt_keys import private_key_pem, public_key

ACCESS_TYP = "access"
REFRESH_TYP = "refresh"


def mint_access_token(
    *,
    user_id: uuid.UUID,
    session_id: uuid.UUID,
    email: str,
    display_name: str,
) -> tuple[str, int]:
    now = datetime.now(timezone.utc)
    exp = now + timedelta(minutes=settings.access_token_expire_minutes)
    payload: dict[str, Any] = {
        "iss": settings.jwt_issuer,
        "sub": str(user_id),
        "sid": str(session_id),
        "aud": settings.jwt_audience,
        "email": email,
        "name": display_name,
        "typ": ACCESS_TYP,
        "iat": int(now.timestamp()),
        "exp": int(exp.timestamp()),
    }
    token = jwt.encode(
        payload,
        private_key_pem(),
        algorithm="RS256",
        headers={"kid": settings.jwt_key_id},
    )
    expires_in = int((exp - now).total_seconds())
    return token, expires_in


def decode_access_token(token: str) -> dict[str, Any]:
    payload = jwt.decode(
        token,
        public_key(),
        algorithms=["RS256"],
        audience=settings.jwt_audience,
        issuer=settings.jwt_issuer,
        options={"require": ["exp", "sub", "sid", "aud", "typ"]},
    )
    if payload.get("typ") != ACCESS_TYP:
        raise jwt.InvalidTokenError("Not an access token")
    return payload


def mint_refresh_token(user_id: uuid.UUID) -> tuple[str, str, int]:
    now = datetime.now(timezone.utc)
    exp = now + timedelta(days=settings.refresh_token_expire_days)
    jti = str(uuid.uuid4())
    ttl = int((exp - now).total_seconds())
    payload: dict[str, Any] = {
        "sub": str(user_id),
        "typ": REFRESH_TYP,
        "jti": jti,
        "iat": int(now.timestamp()),
        "exp": int(exp.timestamp()),
    }
    token = jwt.encode(
        payload,
        settings.refresh_jwt_secret_value(),
        algorithm="HS256",
    )
    return token, jti, ttl


def decode_refresh_token(token: str) -> dict[str, Any]:
    payload = jwt.decode(
        token,
        settings.refresh_jwt_secret_value(),
        algorithms=["HS256"],
        options={"require": ["exp", "sub", "typ", "jti"]},
    )
    if payload.get("typ") != REFRESH_TYP:
        raise jwt.InvalidTokenError("Not a refresh token")
    return payload
