import uuid

import jwt
import pytest

from app.security.jwt_keys import jwks_document, reset_dev_key_cache_for_tests
from app.security.jwt_tokens import decode_access_token, mint_access_token
from app.services.scopes import tenant_scope


@pytest.fixture(autouse=True)
def _fresh_keys() -> None:
    reset_dev_key_cache_for_tests()


def test_access_token_carries_aud_scope_and_profile() -> None:
    user_id = uuid.uuid4()
    tenant_id = uuid.uuid4()
    scope_claim = tenant_scope(tenant_id)
    token, expires_in = mint_access_token(
        user_id=user_id,
        email="admin@localhost",
        display_name="Admin",
        scope_claim=scope_claim,
    )
    assert expires_in > 0
    payload = decode_access_token(token)
    assert payload["sub"] == str(user_id)
    assert payload["aud"] == "ceres-api"
    assert payload["iss"] == "ceres-identity"
    assert payload["scope"] == scope_claim
    assert payload["email"] == "admin@localhost"
    assert payload["name"] == "Admin"


def test_jwks_validates_issued_token() -> None:
    user_id = uuid.uuid4()
    token, _ = mint_access_token(
        user_id=user_id,
        email="u@example.com",
        display_name="User",
        scope_claim=tenant_scope(uuid.uuid4()),
    )
    jwk = jwks_document()["keys"][0]
    public_key = jwt.algorithms.RSAAlgorithm.from_jwk(jwk)
    payload = jwt.decode(
        token,
        public_key,
        algorithms=["RS256"],
        audience="ceres-api",
        issuer="ceres-identity",
    )
    assert payload["sub"] == str(user_id)
