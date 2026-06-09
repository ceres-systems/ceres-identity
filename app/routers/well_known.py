from fastapi import APIRouter

from app.security.jwt_keys import jwks_document

router = APIRouter(tags=["well-known"])


@router.get("/.well-known/jwks.json")
def jwks() -> dict:
    return jwks_document()
