import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class SiteMemberRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str
    display_name: str
    is_active: bool
    grant_action: Literal["read", "write"]
    created_at: datetime
    updated_at: datetime


class SiteMemberCreate(BaseModel):
    site_id: uuid.UUID
    email: str = Field(min_length=1, max_length=320)
    password: str = Field(min_length=8, max_length=256)
    display_name: str = Field(min_length=1, max_length=255)
    grant_action: Literal["read", "write"] = "write"
    is_active: bool = True

    @field_validator("email")
    @classmethod
    def normalize_email(cls, v: str) -> str:
        s = v.strip()
        if "@" not in s:
            raise ValueError("Invalid email")
        return s.lower()


class SiteMemberUpdate(BaseModel):
    site_id: uuid.UUID
    display_name: str | None = Field(default=None, min_length=1, max_length=255)
    password: str | None = Field(default=None, min_length=8, max_length=256)
    is_active: bool | None = None
    grant_action: Literal["read", "write"] | None = None
