"""User management schemas."""

from pydantic import BaseModel, Field


class UserCreateRequest(BaseModel):
    username: str = Field(min_length=3, max_length=255)
    password: str = Field(min_length=8)
    email: str | None = None
    is_superadmin: bool = False


class UserResponse(BaseModel):
    id: str
    username: str
    email: str | None = None
    is_superadmin: bool
    oauth_provider: str | None = None
    created_at: str
    last_login: str | None = None

    model_config = {"from_attributes": True}


class UserListResponse(BaseModel):
    users: list[UserResponse]
    total: int


class UserUpdateRequest(BaseModel):
    email: str | None = None
    is_superadmin: bool | None = None


class PasswordResetRequest(BaseModel):
    password: str = Field(min_length=8)
