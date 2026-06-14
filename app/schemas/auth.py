import uuid

from pydantic import BaseModel, ConfigDict, Field, field_validator


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
