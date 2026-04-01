"""Vault request/response schemas."""

from pydantic import BaseModel, Field


class VaultCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    storage_backend: str = "local"
    encrypted: bool = False
    encryption_salt: str | None = None
    sync_mode: str = "on_save"
    obsidian_config_sync: str = "settings_only"


class VaultUpdateRequest(BaseModel):
    name: str | None = None
    sync_mode: str | None = None
    obsidian_config_sync: str | None = None
    retention_policy: str | None = None


class VaultResponse(BaseModel):
    id: str
    name: str
    owner_id: str
    storage_backend: str
    encrypted: bool
    sync_mode: str
    obsidian_config_sync: str
    created_at: str
    updated_at: str

    model_config = {"from_attributes": True}


class VaultListResponse(BaseModel):
    vaults: list[VaultResponse]
    total: int
