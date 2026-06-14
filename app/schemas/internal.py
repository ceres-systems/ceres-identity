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
