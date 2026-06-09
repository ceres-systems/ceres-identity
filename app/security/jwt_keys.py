from __future__ import annotations

import json
import uuid
from functools import lru_cache

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from jwt.algorithms import RSAAlgorithm

from app.config import settings

_cached_dev_pem: str | None = None


def _load_or_generate_private_pem() -> str:
    global _cached_dev_pem  # pylint: disable=global-statement
    configured = settings.jwt_private_key_pem_value()
    if configured:
        return configured
    if _cached_dev_pem is None:
        private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        _cached_dev_pem = private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        ).decode("ascii")
    return _cached_dev_pem


@lru_cache
def private_key_pem() -> str:
    return _load_or_generate_private_pem()


@lru_cache
def public_key():
    private_key = serialization.load_pem_private_key(
        private_key_pem().encode("ascii"),
        password=None,
    )
    return private_key.public_key()


def jwks_document() -> dict:
    jwk = json.loads(RSAAlgorithm.to_jwk(public_key()))
    jwk.update(
        {
            "kid": settings.jwt_key_id,
            "use": "sig",
            "alg": "RS256",
        }
    )
    return {"keys": [jwk]}


def reset_dev_key_cache_for_tests() -> None:
    global _cached_dev_pem  # pylint: disable=global-statement
    _cached_dev_pem = None
    private_key_pem.cache_clear()
    public_key.cache_clear()
