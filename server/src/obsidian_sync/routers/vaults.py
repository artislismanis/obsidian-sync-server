"""Vault CRUD router."""

import base64

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from obsidian_sync.config import settings
from obsidian_sync.database import get_db
from obsidian_sync.middleware.auth import get_current_user
from obsidian_sync.models.user import User
from obsidian_sync.models.vault import VaultRole
from obsidian_sync.schemas.sync import (
    FileListResponse,
    FileSyncRequest,
    FileSyncResponse,
    SyncOperationResponse,
    SyncOperationsListResponse,
)
from obsidian_sync.schemas.vault import (
    VaultCreateRequest,
    VaultListResponse,
    VaultResponse,
    VaultUpdateRequest,
)
from obsidian_sync.services import sync as sync_service
from obsidian_sync.services import vault as vault_service
from obsidian_sync.storage.local import LocalStorage

router = APIRouter(prefix="/api/v1/vaults", tags=["vaults"])


def _vault_to_response(vault) -> VaultResponse:  # type: ignore[no-untyped-def]
    return VaultResponse(
        id=vault.id,
        name=vault.name,
        owner_id=vault.owner_id,
        storage_backend=vault.storage_backend,
        encrypted=vault.encrypted,
        sync_mode=vault.sync_mode,
        obsidian_config_sync=vault.obsidian_config_sync,
        created_at=vault.created_at.isoformat() if vault.created_at else "",
        updated_at=vault.updated_at.isoformat() if vault.updated_at else "",
    )


@router.get("", response_model=VaultListResponse)
async def list_vaults(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    vaults = await vault_service.list_user_vaults(db, current_user.id)
    return {
        "vaults": [_vault_to_response(v) for v in vaults],
        "total": len(vaults),
    }


@router.post("", response_model=VaultResponse, status_code=status.HTTP_201_CREATED)
async def create_vault(
    body: VaultCreateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> VaultResponse:
    vault = await vault_service.create_vault(
        db,
        owner_id=current_user.id,
        name=body.name,
        storage_backend=body.storage_backend,
        encrypted=body.encrypted,
        encryption_salt=body.encryption_salt,
        sync_mode=body.sync_mode,
        obsidian_config_sync=body.obsidian_config_sync,
    )
    return _vault_to_response(vault)


@router.get("/{vault_id}", response_model=VaultResponse)
async def get_vault(
    vault_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> VaultResponse:
    vault = await vault_service.get_vault(db, vault_id)
    if vault is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Vault not found")

    role = await vault_service.get_user_vault_role(db, vault_id, current_user.id)
    if role is None and not current_user.is_superadmin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")

    return _vault_to_response(vault)


@router.patch("/{vault_id}", response_model=VaultResponse)
async def update_vault(
    vault_id: str,
    body: VaultUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> VaultResponse:
    vault = await vault_service.get_vault(db, vault_id)
    if vault is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Vault not found")

    role = await vault_service.get_user_vault_role(db, vault_id, current_user.id)
    if role not in (VaultRole.owner.value, VaultRole.admin.value) and not current_user.is_superadmin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Owner or admin access required")

    vault = await vault_service.update_vault(
        db, vault,
        name=body.name,
        sync_mode=body.sync_mode,
        obsidian_config_sync=body.obsidian_config_sync,
        retention_policy=body.retention_policy,
    )
    return _vault_to_response(vault)


@router.delete("/{vault_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_vault(
    vault_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    vault = await vault_service.get_vault(db, vault_id)
    if vault is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Vault not found")

    role = await vault_service.get_user_vault_role(db, vault_id, current_user.id)
    if role != VaultRole.owner.value and not current_user.is_superadmin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Owner access required")

    await vault_service.archive_vault(db, vault)


def _get_vault_storage(vault_id: str) -> LocalStorage:
    """Get the storage backend for a vault."""
    root = f"{settings.storage_local_path}/{vault_id}/current"
    return LocalStorage(root)


def _file_version_to_response(fv) -> FileSyncResponse:  # type: ignore[no-untyped-def]
    return FileSyncResponse(
        path=fv.file_path,
        version=fv.version,
        content_hash=fv.content_hash,
        size_bytes=fv.size_bytes,
        author_id=fv.author_id,
        created_at=fv.created_at.isoformat() if fv.created_at else "",
    )


@router.get("/{vault_id}/files", response_model=FileListResponse)
async def list_vault_files(
    vault_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    vault = await vault_service.get_vault(db, vault_id)
    if vault is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Vault not found")

    role = await vault_service.get_user_vault_role(db, vault_id, current_user.id)
    if role is None and not current_user.is_superadmin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")

    files = await sync_service.list_vault_files(db, vault_id)
    vault_version = await sync_service.get_vault_version(db, vault_id)
    return {
        "files": [_file_version_to_response(f) for f in files],
        "vault_version": vault_version,
    }


@router.get("/{vault_id}/files/{path:path}")
async def get_file(
    vault_id: str,
    path: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    vault = await vault_service.get_vault(db, vault_id)
    if vault is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Vault not found")

    role = await vault_service.get_user_vault_role(db, vault_id, current_user.id)
    if role is None and not current_user.is_superadmin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")

    file_version = await sync_service.get_file_version(db, vault_id, path)
    if file_version is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found")

    storage = _get_vault_storage(vault_id)
    try:
        data = await storage.read(path)
    except (FileNotFoundError, OSError):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="File not found in storage"
        )

    return {
        "path": path,
        "content": base64.b64encode(data).decode("ascii"),
        "version": file_version.version,
        "content_hash": file_version.content_hash,
        "size_bytes": file_version.size_bytes,
    }


@router.put("/{vault_id}/files/{path:path}", response_model=FileSyncResponse)
async def upload_file(
    vault_id: str,
    path: str,
    body: FileSyncRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> FileSyncResponse:
    vault = await vault_service.get_vault(db, vault_id)
    if vault is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Vault not found")

    role = await vault_service.get_user_vault_role(db, vault_id, current_user.id)
    if role not in (VaultRole.owner.value, VaultRole.admin.value, VaultRole.write.value) and not current_user.is_superadmin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Write access required")

    # Conflict detection
    conflict = await sync_service.detect_conflict(db, vault_id, path, body.version)
    if conflict:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Conflict: server has a newer version",
        )

    # Decode content
    try:
        raw_data = base64.b64decode(body.content)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid base64 content"
        )

    # Determine operation type
    existing = await sync_service.get_file_version(db, vault_id, path)
    op_type = "update" if existing else "create"

    # Store file
    storage = _get_vault_storage(vault_id)
    await storage.write(path, raw_data, content_hash=body.content_hash)

    # Create file version record
    file_version = await sync_service.create_file_version(
        db,
        vault_id=vault_id,
        path=path,
        content_hash=body.content_hash,
        size_bytes=len(raw_data),
        author_id=current_user.id,
    )

    # Record sync operation
    await sync_service.record_sync_operation(
        db,
        vault_id=vault_id,
        path=path,
        op_type=op_type,
        author_id=current_user.id,
    )

    return _file_version_to_response(file_version)


@router.delete("/{vault_id}/files/{path:path}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_file(
    vault_id: str,
    path: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    vault = await vault_service.get_vault(db, vault_id)
    if vault is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Vault not found")

    role = await vault_service.get_user_vault_role(db, vault_id, current_user.id)
    if role not in (VaultRole.owner.value, VaultRole.admin.value, VaultRole.write.value) and not current_user.is_superadmin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Write access required")

    file_version = await sync_service.get_file_version(db, vault_id, path)
    if file_version is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found")

    # Remove from storage
    storage = _get_vault_storage(vault_id)
    await storage.delete(path)

    # Record sync operation
    await sync_service.record_sync_operation(
        db,
        vault_id=vault_id,
        path=path,
        op_type="delete",
        author_id=current_user.id,
    )


@router.get("/{vault_id}/operations", response_model=SyncOperationsListResponse)
async def get_operations(
    vault_id: str,
    since: int = 0,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    vault = await vault_service.get_vault(db, vault_id)
    if vault is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Vault not found")

    role = await vault_service.get_user_vault_role(db, vault_id, current_user.id)
    if role is None and not current_user.is_superadmin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")

    operations = await sync_service.get_operations_since(db, vault_id, since)
    vault_version = await sync_service.get_vault_version(db, vault_id)
    return {
        "operations": [
            SyncOperationResponse(
                id=op.id,
                vault_id=op.vault_id,
                file_path=op.file_path,
                operation_type=op.operation_type,
                version=op.version,
                author_id=op.author_id,
                created_at=op.created_at.isoformat() if op.created_at else "",
            )
            for op in operations
        ],
        "vault_version": vault_version,
    }
