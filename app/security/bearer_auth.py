from __future__ import annotations

import uuid
from typing import Annotated

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.security.jwt_tokens import decode_access_token

_bearer = HTTPBearer(auto_error=False)
BearerDep = Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)]


def require_access_payload(creds: BearerDep) -> dict:
    if creds is None or creds.scheme.lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )
    try:
        return decode_access_token(creds.credentials)
    except (jwt.InvalidTokenError, jwt.ExpiredSignatureError) as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        ) from exc


AccessPayloadDep = Annotated[dict, Depends(require_access_payload)]


def user_id_from_payload(payload: dict) -> uuid.UUID:
    return uuid.UUID(str(payload["sub"]))
