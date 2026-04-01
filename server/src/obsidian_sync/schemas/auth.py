"""Auth request/response schemas."""

from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=255)
    password: str = Field(min_length=1)


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int


class RefreshRequest(BaseModel):
    refresh_token: str


class SetupRequest(BaseModel):
    username: str = Field(min_length=3, max_length=255)
    password: str = Field(min_length=8)
    email: str | None = None


class APIKeyCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=255)


class APIKeyResponse(BaseModel):
    id: str
    name: str
    prefix: str
    key: str | None = None  # Only returned on creation
    created_at: str
