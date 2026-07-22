from typing import Self
import uuid

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class LoginRequest(BaseModel):
    email: str = Field(min_length=1, max_length=320)
    password: str = Field(min_length=1, max_length=256)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, v: str) -> str:
        s = v.strip()
        if "@" not in s:
            raise ValueError("Invalid email")
        return s.lower()


class PinLoginRequest(BaseModel):
    """Kiosk PIN login. PIN is unique per site — site_id selects the namespace."""

    site_id: uuid.UUID
    pin: str = Field(min_length=4, max_length=4)

    @field_validator("pin")
    @classmethod
    def digits_only(cls, v: str) -> str:
        if not v.isdigit():
            raise ValueError("PIN must be exactly 4 digits")
        return v


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int


class UserMe(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str
    display_name: str
    scopes: list[str]


class ProfileUpdateRequest(BaseModel):
    display_name: str | None = Field(default=None, min_length=1, max_length=255)
    email: str | None = Field(default=None, min_length=1, max_length=320)

    @field_validator("display_name")
    @classmethod
    def normalize_display_name(cls, v: str | None) -> str | None:
        if v is None:
            return None
        s = v.strip()
        if not s:
            raise ValueError("Display name cannot be empty")
        return s

    @field_validator("email")
    @classmethod
    def normalize_email(cls, v: str | None) -> str | None:
        if v is None:
            return None
        s = v.strip()
        if "@" not in s:
            raise ValueError("Invalid email")
        return s.lower()

    @model_validator(mode="after")
    def require_one_field(self) -> Self:
        if self.display_name is None and self.email is None:
            raise ValueError("At least one field must be provided")
        return self


class PasswordChangeRequest(BaseModel):
    current_password: str = Field(min_length=1, max_length=256)
    new_password: str = Field(min_length=1, max_length=256)
