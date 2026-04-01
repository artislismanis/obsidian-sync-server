"""Sharing and ACL router: vault access management and share links."""

import base64
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from obsidian_sync.config import settings
from obsidian_sync.database import get_db
from obsidian_sync.middleware.auth import get_current_user
from obsidian_sync.models.user import User
from obsidian_sync.models.vault import VaultRole
from obsidian_sync.schemas.sharing import (
    CreateShareLinkRequest,
    GrantAccessRequest,
    ShareLinkAccessResponse,
    ShareLinkListResponse,
    ShareLinkPasswordRequest,
    ShareLinkResponse,
    UpdateRoleRequest,
    VaultAccessListResponse,
    VaultAccessResponse,
)
from obsidian_sync.services import audit as audit_service
from obsidian_sync.services import sharing as sharing_service
from obsidian_sync.services import sync as sync_service
from obsidian_sync.services import vault as vault_service
from obsidian_sync.storage.local import LocalStorage

router = APIRouter(tags=["sharing"])


def _get_vault_storage(vault_id: str) -> LocalStorage:
    """Get the storage backend for a vault."""
    root = f"{settings.storage_local_path}/{vault_id}/current"
    return LocalStorage(root)


async def _require_vault_role(
    db: AsyncSession,
    vault_id: str,
    user: User,
    min_roles: set[str],
) -> str:
    """Check that the user has one of the required roles. Returns the role."""
    vault = await vault_service.get_vault(db, vault_id)
    if vault is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Vault not found"
        )

    role = await vault_service.get_user_vault_role(db, vault_id, user.id)
    if role is None and not user.is_superadmin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Access denied"
        )
    if role not in min_roles and not user.is_superadmin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions"
        )
    return role or ""


def _access_to_response(access) -> VaultAccessResponse:  # type: ignore[no-untyped-def]
    return VaultAccessResponse(
        vault_id=access.vault_id,
        user_id=access.user_id,
        role=access.role,
        granted_at=access.granted_at.isoformat() if access.granted_at else "",
        granted_by=access.granted_by,
    )


def _link_to_response(
    link, token: str | None = None  # type: ignore[no-untyped-def]
) -> ShareLinkResponse:
    return ShareLinkResponse(
        id=link.id,
        vault_id=link.vault_id,
        file_path=link.file_path,
        token=token,
        permissions=link.permissions,
        expires_at=link.expires_at.isoformat() if link.expires_at else None,
        access_count=link.access_count,
        max_access_count=link.max_access_count,
        revoked=link.revoked,
        created_at=link.created_at.isoformat() if link.created_at else "",
        created_by=link.created_by,
    )


# --- Vault Access (ACL) Endpoints ---


@router.get(
    "/api/v1/vaults/{vault_id}/sharing",
    response_model=VaultAccessListResponse,
)
async def list_vault_access(
    vault_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    await _require_vault_role(
        db, vault_id, current_user, {VaultRole.owner.value, VaultRole.admin.value}
    )
    access_list = await sharing_service.list_vault_access(db, vault_id)
    return {"access": [_access_to_response(a) for a in access_list]}


@router.post(
    "/api/v1/vaults/{vault_id}/sharing",
    response_model=VaultAccessResponse,
    status_code=status.HTTP_201_CREATED,
)
async def grant_access(
    vault_id: str,
    body: GrantAccessRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> VaultAccessResponse:
    await _require_vault_role(
        db, vault_id, current_user, {VaultRole.owner.value, VaultRole.admin.value}
    )
    access = await sharing_service.grant_vault_access(
        db, vault_id, body.user_id, body.role, current_user.id
    )
    await audit_service.log_action(
        db,
        actor_id=current_user.id,
        action="grant_access",
        resource_type="vault",
        resource_id=vault_id,
    )
    return _access_to_response(access)


@router.patch(
    "/api/v1/vaults/{vault_id}/sharing/{user_id}",
    response_model=VaultAccessResponse,
)
async def update_role(
    vault_id: str,
    user_id: str,
    body: UpdateRoleRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> VaultAccessResponse:
    await _require_vault_role(
        db, vault_id, current_user, {VaultRole.owner.value, VaultRole.admin.value}
    )
    access = await sharing_service.update_vault_role(db, vault_id, user_id, body.role)
    if access is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Access entry not found"
        )
    await audit_service.log_action(
        db,
        actor_id=current_user.id,
        action="update_role",
        resource_type="vault",
        resource_id=vault_id,
    )
    return _access_to_response(access)


@router.delete(
    "/api/v1/vaults/{vault_id}/sharing/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def revoke_access(
    vault_id: str,
    user_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    await _require_vault_role(
        db, vault_id, current_user, {VaultRole.owner.value, VaultRole.admin.value}
    )
    await sharing_service.revoke_vault_access(db, vault_id, user_id)
    await audit_service.log_action(
        db,
        actor_id=current_user.id,
        action="revoke_access",
        resource_type="vault",
        resource_id=vault_id,
    )


# --- Share Link Endpoints ---


@router.post(
    "/api/v1/vaults/{vault_id}/share-links",
    response_model=ShareLinkResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_share_link(
    vault_id: str,
    body: CreateShareLinkRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ShareLinkResponse:
    await _require_vault_role(
        db,
        vault_id,
        current_user,
        {VaultRole.owner.value, VaultRole.admin.value, VaultRole.write.value},
    )

    expires_at = None
    if body.expires_in_hours is not None:
        expires_at = datetime.now(timezone.utc) + timedelta(hours=body.expires_in_hours)

    link, raw_token = await sharing_service.create_share_link(
        db,
        vault_id=vault_id,
        file_path=body.file_path,
        created_by=current_user.id,
        permissions=body.permissions,
        expires_at=expires_at,
        password=body.password,
        max_access=body.max_access_count,
    )
    await audit_service.log_action(
        db,
        actor_id=current_user.id,
        action="create_share_link",
        resource_type="share_link",
        resource_id=link.id,
    )
    return _link_to_response(link, token=raw_token)


@router.get(
    "/api/v1/vaults/{vault_id}/share-links",
    response_model=ShareLinkListResponse,
)
async def list_share_links(
    vault_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    await _require_vault_role(
        db,
        vault_id,
        current_user,
        {VaultRole.owner.value, VaultRole.admin.value, VaultRole.write.value},
    )
    links = await sharing_service.list_share_links(db, vault_id)
    return {"links": [_link_to_response(link) for link in links]}


@router.delete(
    "/api/v1/vaults/{vault_id}/share-links/{link_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def revoke_share_link(
    vault_id: str,
    link_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    await _require_vault_role(
        db,
        vault_id,
        current_user,
        {VaultRole.owner.value, VaultRole.admin.value},
    )
    success = await sharing_service.revoke_share_link(db, link_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Share link not found"
        )
    await audit_service.log_action(
        db,
        actor_id=current_user.id,
        action="revoke_share_link",
        resource_type="share_link",
        resource_id=link_id,
    )


# --- Public Share Link Access ---


@router.get("/api/v1/share/{token}")
async def access_share_link(
    token: str,
    password: str | None = None,
    db: AsyncSession = Depends(get_db),
) -> ShareLinkAccessResponse:
    """Public endpoint: access a shared resource via token."""
    link = await sharing_service.verify_share_link(db, token)
    if link is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Share link not found or expired",
        )

    # Check password
    if link.password_hash is not None:
        if password is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Password required",
            )
        if not sharing_service.verify_share_link_password(link, password):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid password",
            )

    vault_id = link.vault_id

    # File-level share
    if link.file_path is not None:
        if link.permissions == "download":
            storage = _get_vault_storage(vault_id)
            try:
                data = await storage.read(link.file_path)
                content = base64.b64encode(data).decode("ascii")
            except (FileNotFoundError, OSError):
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="File not found in storage",
                )
            return ShareLinkAccessResponse(
                vault_id=vault_id,
                file_path=link.file_path,
                permissions=link.permissions,
                content=content,
            )
        else:
            return ShareLinkAccessResponse(
                vault_id=vault_id,
                file_path=link.file_path,
                permissions=link.permissions,
            )

    # Vault-level share: list files
    files = await sync_service.list_vault_files(db, vault_id)
    file_paths = [f.file_path for f in files]
    return ShareLinkAccessResponse(
        vault_id=vault_id,
        file_path=None,
        permissions=link.permissions,
        files=file_paths,
    )
