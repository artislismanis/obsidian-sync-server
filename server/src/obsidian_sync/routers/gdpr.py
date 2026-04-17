"""GDPR compliance router: data export, account deletion, consent."""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from obsidian_sync.database import get_db
from obsidian_sync.middleware.auth import get_current_user
from obsidian_sync.models.user import User
from obsidian_sync.models.vault import Vault, VaultAccess
from obsidian_sync.models.sync import FileVersion, SyncOperation
from obsidian_sync.services import vault as vault_service

router = APIRouter(prefix="/api/v1/account", tags=["gdpr"])


@router.get("/export")
async def request_data_export(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Export all user data as a JSON summary. Full file export is async (future)."""
    vaults = await vault_service.list_user_vaults(db, current_user.id)
    vault_data = []
    for v in vaults:
        files_result = await db.execute(
            select(FileVersion.file_path, FileVersion.version, FileVersion.size_bytes)
            .where(FileVersion.vault_id == v.id)
            .order_by(FileVersion.file_path)
        )
        files = [{"path": r[0], "version": r[1], "size_bytes": r[2]} for r in files_result.all()]
        vault_data.append({
            "id": v.id,
            "name": v.name,
            "storage_backend": v.storage_backend,
            "encrypted": v.encrypted,
            "file_count": len(files),
            "files": files,
        })

    return {
        "user": {
            "id": current_user.id,
            "username": current_user.username,
            "email": current_user.email,
            "is_superadmin": current_user.is_superadmin,
            "oauth_provider": current_user.oauth_provider,
            "created_at": current_user.created_at.isoformat() if current_user.created_at else "",
            "gdpr_consent_at": current_user.gdpr_consent_at.isoformat() if current_user.gdpr_consent_at else None,
        },
        "vaults": vault_data,
    }


@router.delete("/delete")
async def request_account_deletion(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Request account deletion. Sets a 30-day grace period before permanent deletion."""
    if current_user.deletion_requested_at:
        return {
            "status": "already_requested",
            "deletion_requested_at": current_user.deletion_requested_at.isoformat(),
            "message": "Account deletion already requested. Data will be permanently deleted after 30 days.",
        }

    current_user.deletion_requested_at = datetime.now(timezone.utc)
    await db.flush()

    return {
        "status": "deletion_requested",
        "deletion_requested_at": current_user.deletion_requested_at.isoformat(),
        "message": "Account scheduled for deletion in 30 days. Log in again to cancel.",
    }


@router.post("/cancel-deletion")
async def cancel_deletion(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    if not current_user.deletion_requested_at:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No deletion requested")

    current_user.deletion_requested_at = None
    await db.flush()
    return {"status": "cancelled", "message": "Account deletion cancelled."}


@router.post("/consent")
async def record_consent(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    current_user.gdpr_consent_at = datetime.now(timezone.utc)
    await db.flush()
    return {
        "status": "recorded",
        "gdpr_consent_at": current_user.gdpr_consent_at.isoformat(),
    }
