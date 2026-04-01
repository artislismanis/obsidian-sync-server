"""Sync request/response schemas."""

from pydantic import BaseModel, Field


class FileSyncRequest(BaseModel):
    path: str = Field(min_length=1)
    content: str  # base64-encoded
    version: int = Field(ge=0)
    content_hash: str = Field(min_length=64, max_length=64)


class FileSyncResponse(BaseModel):
    path: str
    version: int
    content_hash: str
    size_bytes: int
    author_id: str
    created_at: str

    model_config = {"from_attributes": True}


class FileListResponse(BaseModel):
    files: list[FileSyncResponse]
    vault_version: int


class SyncOperationResponse(BaseModel):
    id: str
    vault_id: str
    file_path: str
    operation_type: str
    version: int
    author_id: str
    created_at: str

    model_config = {"from_attributes": True}


class SyncOperationsListResponse(BaseModel):
    operations: list[SyncOperationResponse]
    vault_version: int
