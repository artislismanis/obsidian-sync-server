"""File version history router."""

import base64

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from obsidian_sync.database import get_db
from obsidian_sync.middleware.auth import get_current_user
from obsidian_sync.models.user import User
from obsidian_sync.services import history as history_service
from obsidian_sync.services import sync as sync_service
from obsidian_sync.services import vault as vault_service
from obsidian_sync.services.storage_factory import get_local_vault_storage

router = APIRouter(prefix="/api/v1/vaults", tags=["history"])


@router.get("/{vault_id}/files/{path:path}/history")
async def list_versions(
    vault_id: str,
    path: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    role = await vault_service.get_user_vault_role(db, vault_id, current_user.id)
    if role is None and not current_user.is_superadmin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")

    versions = await history_service.list_file_versions(db, vault_id, path)
    return {
        "versions": [
            {
                "version": v.version,
                "content_hash": v.content_hash,
                "size_bytes": v.size_bytes,
                "author_id": v.author_id,
                "created_at": v.created_at.isoformat() if v.created_at else "",
            }
            for v in versions
        ]
    }


@router.get("/{vault_id}/files/{path:path}/history/{version}")
async def get_version_content(
    vault_id: str,
    path: str,
    version: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    role = await vault_service.get_user_vault_role(db, vault_id, current_user.id)
    if role is None and not current_user.is_superadmin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")

    fv = await history_service.get_version(db, vault_id, path, version)
    if fv is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Version not found")

    storage = get_local_vault_storage(vault_id)
    version_path = f".sync/versions/{fv.content_hash}"
    try:
        data = await storage.read(version_path)
    except FileNotFoundError:
        try:
            data = await storage.read(path)
        except FileNotFoundError:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Version content not found")

    return {
        "version": fv.version,
        "content": base64.b64encode(data).decode("ascii"),
        "content_hash": fv.content_hash,
        "size_bytes": fv.size_bytes,
    }


@router.get("/{vault_id}/files/{path:path}/diff")
async def diff_versions(
    vault_id: str,
    path: str,
    v1: int = Query(..., description="Older version"),
    v2: int = Query(..., description="Newer version"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    role = await vault_service.get_user_vault_role(db, vault_id, current_user.id)
    if role is None and not current_user.is_superadmin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")

    fv1 = await history_service.get_version(db, vault_id, path, v1)
    fv2 = await history_service.get_version(db, vault_id, path, v2)
    if not fv1 or not fv2:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Version not found")

    storage = get_local_vault_storage(vault_id)
    try:
        data1 = await storage.read(path)
        data2 = await storage.read(path)
    except FileNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File content not found")

    diff = history_service.compute_diff(data1.decode("utf-8", errors="replace"), data2.decode("utf-8", errors="replace"))
    return {"diff": diff, "v1": v1, "v2": v2}


@router.post("/{vault_id}/files/{path:path}/restore/{version}")
async def restore_version(
    vault_id: str,
    path: str,
    version: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    from obsidian_sync.models.vault import VaultRole

    role = await vault_service.get_user_vault_role(db, vault_id, current_user.id)
    if role not in (VaultRole.owner.value, VaultRole.admin.value, VaultRole.write.value) and not current_user.is_superadmin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Write access required")

    fv = await history_service.get_version(db, vault_id, path, version)
    if fv is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Version not found")

    storage = get_local_vault_storage(vault_id)
    try:
        data = await storage.read(path)
    except FileNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File content not found")

    new_fv = await sync_service.create_file_version(
        db, vault_id, path, fv.content_hash, fv.size_bytes, current_user.id
    )
    await sync_service.record_sync_operation(
        db, vault_id, path, "update", current_user.id
    )

    return {"version": new_fv.version, "restored_from": version}
