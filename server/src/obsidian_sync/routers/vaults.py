"""Vault CRUD router."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from obsidian_sync.database import get_db
from obsidian_sync.middleware.auth import get_current_user
from obsidian_sync.models.user import User
from obsidian_sync.models.vault import VaultRole
from obsidian_sync.schemas.vault import (
    VaultCreateRequest,
    VaultListResponse,
    VaultResponse,
    VaultUpdateRequest,
)
from obsidian_sync.services import vault as vault_service

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
