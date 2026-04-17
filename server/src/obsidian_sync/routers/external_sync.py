"""External sync configuration and trigger endpoints."""

import logging

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from obsidian_sync.connectors.google_drive import GoogleDriveConnector
from obsidian_sync.connectors.onedrive import OneDriveConnector
from obsidian_sync.database import get_db
from obsidian_sync.middleware.auth import get_current_user
from obsidian_sync.models.external import ExternalSyncConfig
from obsidian_sync.models.user import User
from obsidian_sync.models.vault import VaultRole
from obsidian_sync.services import vault as vault_service
from obsidian_sync.workers.external_sync import ExternalSyncWorker

logger = logging.getLogger(__name__)

router = APIRouter(tags=["external-sync"])


# ---------- Schemas ----------


class ExternalSyncConfigRequest(BaseModel):
    provider: str = Field(..., pattern=r"^(google_drive|onedrive)$")
    mode: str = Field(default="mirror", pattern=r"^(mirror|bidirectional)$")
    oauth_token: str | None = None
    remote_folder_id: str | None = None


class ExternalSyncConfigResponse(BaseModel):
    id: str
    vault_id: str
    provider: str
    mode: str
    remote_folder_id: str | None
    last_sync_at: str | None
    last_error: str | None
    enabled: bool
    created_at: str
    updated_at: str

    model_config = {"from_attributes": True}


class ExternalSyncTriggerResponse(BaseModel):
    status: str
    last_error: str | None = None


# ---------- Helpers ----------


async def _require_owner_or_admin(
    db: AsyncSession, vault_id: str, user: User
) -> None:
    """Ensure the user has owner or admin role on the vault."""
    vault = await vault_service.get_vault(db, vault_id)
    if vault is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Vault not found"
        )

    role = await vault_service.get_user_vault_role(db, vault_id, user.id)
    if (
        role not in (VaultRole.owner.value, VaultRole.admin.value)
        and not user.is_superadmin
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Owner or admin access required",
        )


def _config_to_response(config: ExternalSyncConfig) -> ExternalSyncConfigResponse:
    return ExternalSyncConfigResponse(
        id=config.id,
        vault_id=config.vault_id,
        provider=config.provider,
        mode=config.mode,
        remote_folder_id=config.remote_folder_id,
        last_sync_at=config.last_sync_at.isoformat() if config.last_sync_at else None,
        last_error=config.last_error,
        enabled=config.enabled,
        created_at=config.created_at.isoformat() if config.created_at else "",
        updated_at=config.updated_at.isoformat() if config.updated_at else "",
    )


def _build_connector(provider: str) -> GoogleDriveConnector | OneDriveConnector:
    """Instantiate the appropriate connector for the provider."""
    if provider == "google_drive":
        return GoogleDriveConnector()
    if provider == "onedrive":
        return OneDriveConnector()
    raise ValueError(f"Unsupported provider: {provider}")


# ---------- Endpoints ----------


@router.get(
    "/api/v1/vaults/{vault_id}/external-sync",
    response_model=ExternalSyncConfigResponse,
)
async def get_external_sync_config(
    vault_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ExternalSyncConfigResponse:
    """Get the external sync configuration for a vault."""
    await _require_owner_or_admin(db, vault_id, current_user)

    result = await db.execute(
        select(ExternalSyncConfig).where(
            ExternalSyncConfig.vault_id == vault_id
        )
    )
    config = result.scalar_one_or_none()
    if config is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="External sync not configured for this vault",
        )

    return _config_to_response(config)


@router.post(
    "/api/v1/vaults/{vault_id}/external-sync",
    response_model=ExternalSyncConfigResponse,
    status_code=status.HTTP_201_CREATED,
)
async def configure_external_sync(
    vault_id: str,
    body: ExternalSyncConfigRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ExternalSyncConfigResponse:
    """Configure (or update) an external sync connector for a vault."""
    await _require_owner_or_admin(db, vault_id, current_user)

    result = await db.execute(
        select(ExternalSyncConfig).where(
            ExternalSyncConfig.vault_id == vault_id
        )
    )
    existing = result.scalar_one_or_none()

    if existing is not None:
        # Update existing config
        existing.provider = body.provider
        existing.mode = body.mode
        if body.oauth_token is not None:
            existing.oauth_token_encrypted = body.oauth_token
        if body.remote_folder_id is not None:
            existing.remote_folder_id = body.remote_folder_id
        existing.enabled = True
        existing.last_error = None
        await db.flush()
        await db.refresh(existing)
        return _config_to_response(existing)

    # Create new config
    config = ExternalSyncConfig(
        vault_id=vault_id,
        provider=body.provider,
        mode=body.mode,
        oauth_token_encrypted=body.oauth_token,
        remote_folder_id=body.remote_folder_id,
        enabled=True,
    )
    db.add(config)
    await db.flush()
    await db.refresh(config)
    return _config_to_response(config)


@router.delete(
    "/api/v1/vaults/{vault_id}/external-sync",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def remove_external_sync(
    vault_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Remove the external sync configuration for a vault."""
    await _require_owner_or_admin(db, vault_id, current_user)

    result = await db.execute(
        select(ExternalSyncConfig).where(
            ExternalSyncConfig.vault_id == vault_id
        )
    )
    config = result.scalar_one_or_none()
    if config is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="External sync not configured for this vault",
        )

    await db.delete(config)
    await db.flush()


@router.post(
    "/api/v1/vaults/{vault_id}/external-sync/trigger",
    response_model=ExternalSyncTriggerResponse,
)
async def trigger_external_sync(
    vault_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ExternalSyncTriggerResponse:
    """Manually trigger an external sync cycle for a vault."""
    await _require_owner_or_admin(db, vault_id, current_user)

    result = await db.execute(
        select(ExternalSyncConfig).where(
            ExternalSyncConfig.vault_id == vault_id
        )
    )
    config = result.scalar_one_or_none()
    if config is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="External sync not configured for this vault",
        )

    if not config.enabled:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="External sync is disabled for this vault",
        )

    # Build connector and authenticate
    connector = _build_connector(config.provider)
    oauth_token = config.oauth_token_encrypted or ""
    folder_arg = config.remote_folder_id or ""

    if config.provider == "google_drive":
        await connector.authenticate(oauth_token, folder_id=folder_arg)  # type: ignore[call-arg]
    elif config.provider == "onedrive":
        await connector.authenticate(oauth_token, folder_path=folder_arg or "/ObsidianSync")  # type: ignore[call-arg]

    worker = ExternalSyncWorker(
        vault_id=vault_id,
        connector=connector,
        mode=config.mode,
    )
    await worker.run_once(db)

    # Refresh config to get updated last_sync_at / last_error
    await db.refresh(config)

    return ExternalSyncTriggerResponse(
        status="completed" if config.last_error is None else "error",
        last_error=config.last_error,
    )
