from typing import Self
import uuid

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def _secret_value(secret: SecretStr) -> str:
    return secret.get_secret_value()


def _optional_secret_value(secret: SecretStr | None) -> str | None:
    if secret is None:
        return None
    return _secret_value(secret)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="CERES_IDENTITY_", extra="ignore")

    database_url: str = Field(description="Async SQLAlchemy URL (postgresql+asyncpg://...)")
    redis_url: str = Field(description="Redis URL for refresh-token allowlist")

    jwt_issuer: str = "ceres-identity"
    jwt_audience: str = "ceres-api"
    jwt_key_id: str = "ceres-identity-1"

    access_token_expire_minutes: int = 15
    refresh_token_expire_days: int = 14
    refresh_jwt_secret: SecretStr = Field(description="HS256 secret for refresh tokens")
    internal_api_key: SecretStr = Field(description="Shared key for internal admin API")
    pin_hmac_secret: SecretStr | None = Field(
        default=None,
        description=(
            "HMAC secret for kiosk PIN lookup. When unset, derived as "
            "'ceres-pin-hmac:' + refresh_jwt_secret (see security/pins.py)."
        ),
    )
    redis_refresh_key_prefix: str = "ceres:identity:refresh:"
    redis_session_key_prefix: str = "ceres:identity:session:"
    redis_grants_key_prefix: str = "ceres:identity:grants:"
    redis_user_sessions_key_prefix: str = "ceres:identity:user:"
    redis_user_refresh_key_suffix: str = ":refresh_jtis"
    refresh_cookie_name: str = "ceres_identity_refresh"
    cookie_secure: bool = False

    jwt_private_key_pem: SecretStr | None = Field(
        default=None,
        description="RS256 private key PEM; generated in dev when unset",
    )

    db_create_tables: bool = False
    bootstrap_seed: bool = False

    seed_email: str = "admin@localhost"
    seed_password: SecretStr | None = Field(
        default=None,
        description="Plaintext password for seed user when bootstrap_seed is true",
    )
    seed_display_name: str = "Admin"
    seed_default_tenant_id: uuid.UUID = Field(
        default=uuid.UUID("00000000-0000-4000-8000-000000000001"),
        validation_alias="CERES_SEED_DEFAULT_TENANT_ID",
    )

    @field_validator("seed_password", mode="before")
    @classmethod
    def empty_seed_password_to_none(cls, v: object) -> object:
        if v == "":
            return None
        return v

    @model_validator(mode="after")
    def validate_secrets_and_bootstrap(self) -> Self:
        if len(self.refresh_jwt_secret_value()) < 32:
            raise ValueError("CERES_IDENTITY_REFRESH_JWT_SECRET must be at least 32 characters")
        if len(self.internal_api_key_value()) < 32:
            raise ValueError("CERES_IDENTITY_INTERNAL_API_KEY must be at least 32 characters")
        if self.bootstrap_seed and self.seed_password is None:
            raise ValueError(
                "CERES_IDENTITY_SEED_PASSWORD is required when "
                "CERES_IDENTITY_BOOTSTRAP_SEED is true"
            )
        return self

    def refresh_jwt_secret_value(self) -> str:
        return _secret_value(self.refresh_jwt_secret)

    def internal_api_key_value(self) -> str:
        return _secret_value(self.internal_api_key)

    def pin_hmac_secret_value(self) -> str | None:
        return _optional_secret_value(self.pin_hmac_secret)

    def seed_password_value(self) -> str:
        if self.seed_password is None:
            raise RuntimeError(
                "CERES_IDENTITY_SEED_PASSWORD is required when bootstrap seed creates the user"
            )
        return _secret_value(self.seed_password)

    def jwt_private_key_pem_value(self) -> str | None:
        return _optional_secret_value(self.jwt_private_key_pem)


settings = Settings()  # type: ignore[call-arg]
