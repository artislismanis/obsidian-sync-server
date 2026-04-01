"""Vault CRUD service."""

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from obsidian_sync.models.vault import Vault, VaultAccess, VaultRole


async def create_vault(
    db: AsyncSession,
    owner_id: str,
    name: str,
    storage_backend: str = "local",
    encrypted: bool = False,
    encryption_salt: str | None = None,
    encryption_key_hash: str | None = None,
    sync_mode: str = "on_save",
    obsidian_config_sync: str = "settings_only",
) -> Vault:
    vault = Vault(
        name=name,
        owner_id=owner_id,
        storage_backend=storage_backend,
        encrypted=encrypted,
        encryption_salt=encryption_salt,
        encryption_key_hash=encryption_key_hash,
        sync_mode=sync_mode,
        obsidian_config_sync=obsidian_config_sync,
    )
    db.add(vault)
    await db.flush()

    # Owner gets owner access
    access = VaultAccess(
        vault_id=vault.id,
        user_id=owner_id,
        role=VaultRole.owner.value,
        granted_by=owner_id,
    )
    db.add(access)
    await db.flush()
    return vault


async def list_user_vaults(db: AsyncSession, user_id: str) -> list[Vault]:
    """List all vaults a user has access to (owned or shared)."""
    result = await db.execute(
        select(Vault)
        .join(VaultAccess, Vault.id == VaultAccess.vault_id)
        .where(VaultAccess.user_id == user_id, Vault.archived_at.is_(None))
        .order_by(Vault.name)
    )
    return list(result.scalars().all())


async def get_vault(db: AsyncSession, vault_id: str) -> Vault | None:
    result = await db.execute(
        select(Vault).where(Vault.id == vault_id, Vault.archived_at.is_(None))
    )
    return result.scalar_one_or_none()


async def get_user_vault_role(
    db: AsyncSession, vault_id: str, user_id: str
) -> str | None:
    """Get the user's role for a vault, or None if no access."""
    result = await db.execute(
        select(VaultAccess.role).where(
            VaultAccess.vault_id == vault_id,
            VaultAccess.user_id == user_id,
        )
    )
    return result.scalar_one_or_none()


async def update_vault(
    db: AsyncSession,
    vault: Vault,
    name: str | None = None,
    sync_mode: str | None = None,
    obsidian_config_sync: str | None = None,
    retention_policy: str | None = None,
) -> Vault:
    if name is not None:
        vault.name = name
    if sync_mode is not None:
        vault.sync_mode = sync_mode
    if obsidian_config_sync is not None:
        vault.obsidian_config_sync = obsidian_config_sync
    if retention_policy is not None:
        vault.retention_policy = retention_policy
    await db.flush()
    await db.refresh(vault)
    return vault


async def archive_vault(db: AsyncSession, vault: Vault) -> None:
    """Soft-delete a vault."""
    from obsidian_sync.models.base import utcnow

    vault.archived_at = utcnow()
    await db.flush()
