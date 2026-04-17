"""Admin router: server stats, audit log, configuration."""

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from obsidian_sync import __version__
from obsidian_sync.config import settings
from obsidian_sync.database import get_db
from obsidian_sync.middleware.auth import require_superadmin
from obsidian_sync.models.audit import AuditLog
from obsidian_sync.models.user import User
from obsidian_sync.models.vault import Vault
from obsidian_sync.models.sync import FileVersion
from obsidian_sync.websocket.handler import manager

router = APIRouter(prefix="/api/v1/admin", tags=["admin"])


@router.get("/stats")
async def server_stats(
    _: User = Depends(require_superadmin),
    db: AsyncSession = Depends(get_db),
) -> dict:
    user_count = (await db.execute(select(func.count(User.id)))).scalar_one()
    vault_count = (
        await db.execute(
            select(func.count(Vault.id)).where(Vault.archived_at.is_(None))
        )
    ).scalar_one()
    file_count = (await db.execute(select(func.count(FileVersion.id)))).scalar_one()
    total_bytes = (
        await db.execute(select(func.coalesce(func.sum(FileVersion.size_bytes), 0)))
    ).scalar_one()

    return {
        "version": __version__,
        "deployment_mode": settings.deployment_mode,
        "users": user_count,
        "vaults": vault_count,
        "files": file_count,
        "storage_bytes": total_bytes,
        "connected_clients": manager.get_connected_count(),
    }


@router.get("/audit-log")
async def audit_log(
    _: User = Depends(require_superadmin),
    db: AsyncSession = Depends(get_db),
    limit: int = Query(default=50, le=200),
    offset: int = Query(default=0, ge=0),
) -> dict:
    total = (await db.execute(select(func.count(AuditLog.id)))).scalar_one()
    result = await db.execute(
        select(AuditLog)
        .order_by(AuditLog.created_at.desc())
        .offset(offset)
        .limit(limit)
    )
    entries = result.scalars().all()
    return {
        "entries": [
            {
                "id": e.id,
                "actor_id": e.actor_id,
                "action": e.action,
                "resource_type": e.resource_type,
                "resource_id": e.resource_id,
                "details": e.details,
                "ip_address": e.ip_address,
                "created_at": e.created_at.isoformat() if e.created_at else "",
            }
            for e in entries
        ],
        "total": total,
    }


@router.get("/config")
async def server_config(
    _: User = Depends(require_superadmin),
) -> dict:
    return {
        "deployment_mode": settings.deployment_mode,
        "database_url": settings.database_url.split("@")[-1] if "@" in settings.database_url else "(sqlite)",
        "storage_backend": settings.storage_backend,
        "oauth_google": bool(settings.google_client_id),
        "oauth_github": bool(settings.github_client_id),
        "stripe_enabled": bool(settings.stripe_secret_key),
    }
