from typing import Annotated

from fastapi import Header, HTTPException, status

from app.config import settings


def verify_internal_api_key(
    x_ceres_internal_key: Annotated[str | None, Header()] = None,
) -> None:
    if x_ceres_internal_key is None or not x_ceres_internal_key.strip():
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing internal API key",
        )
    expected = settings.internal_api_key_value()
    if x_ceres_internal_key != expected:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid internal API key",
        )
