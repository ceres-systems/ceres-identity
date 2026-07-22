from datetime import datetime
from typing import Literal
import uuid

from pydantic import BaseModel, ConfigDict, Field, field_validator


class SiteMemberRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str
    display_name: str
    is_active: bool
    grant_action: Literal["read", "write"]
    has_kiosk_pin: bool = False
    created_at: datetime
    updated_at: datetime


class SiteMemberCreate(BaseModel):
    site_id: uuid.UUID
    email: str = Field(min_length=1, max_length=320)
    grant_action: Literal["read", "write"] = "write"

    @field_validator("email")
    @classmethod
    def normalize_email(cls, v: str) -> str:
        s = v.strip()
        if "@" not in s:
            raise ValueError("Invalid email")
        return s.lower()


class SiteMemberAdd(BaseModel):
    site_id: uuid.UUID
    email: str = Field(min_length=1, max_length=320)
    grant_action: Literal["read", "write"] = "write"

    @field_validator("email")
    @classmethod
    def normalize_email(cls, v: str) -> str:
        s = v.strip()
        if "@" not in s:
            raise ValueError("Invalid email")
        return s.lower()


class SiteMemberUpdate(BaseModel):
    site_id: uuid.UUID
    is_active: bool | None = None
    grant_action: Literal["read", "write"] | None = None
    # Omitted from the JSON body = leave PIN unchanged.
    # Present as null or "" = clear. Present as exactly 4 digits = set.
    kiosk_pin: str | None = Field(default=None, max_length=4)


class SetUserPinRequest(BaseModel):
    """Internal: set or clear a user's kiosk PIN at a site."""

    site_id: uuid.UUID
    pin: str | None = Field(default=None, max_length=4)
