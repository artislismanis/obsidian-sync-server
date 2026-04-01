"""Sharing request/response schemas."""

from pydantic import BaseModel, Field


class GrantAccessRequest(BaseModel):
    user_id: str
    role: str = Field(pattern=r"^(admin|write|read)$")


class UpdateRoleRequest(BaseModel):
    role: str = Field(pattern=r"^(admin|write|read)$")


class VaultAccessResponse(BaseModel):
    vault_id: str
    user_id: str
    role: str
    granted_at: str
    granted_by: str | None = None

    model_config = {"from_attributes": True}


class VaultAccessListResponse(BaseModel):
    access: list[VaultAccessResponse]


class CreateShareLinkRequest(BaseModel):
    file_path: str | None = None
    permissions: str = Field(default="view", pattern=r"^(view|download)$")
    expires_in_hours: int | None = None  # hours until expiry
    password: str | None = None
    max_access_count: int | None = None


class ShareLinkResponse(BaseModel):
    id: str
    vault_id: str
    file_path: str | None = None
    token: str | None = None  # only returned on creation
    permissions: str
    expires_at: str | None = None
    access_count: int
    max_access_count: int | None = None
    revoked: bool
    created_at: str
    created_by: str

    model_config = {"from_attributes": True}


class ShareLinkListResponse(BaseModel):
    links: list[ShareLinkResponse]


class ShareLinkAccessResponse(BaseModel):
    vault_id: str
    file_path: str | None = None
    permissions: str
    content: str | None = None  # base64-encoded file content for download
    files: list[str] | None = None  # file list for vault-level links


class ShareLinkPasswordRequest(BaseModel):
    password: str
