"""Sharing service: vault access management and share links."""

import hashlib
import hmac
import secrets
from datetime import datetime, timezone

from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from obsidian_sync.config import settings
from obsidian_sync.models.sharing import ShareLink
from obsidian_sync.models.vault import VaultAccess


def _hmac_token(token: str) -> str:
    """Sign a token with HMAC-SHA256 using the server secret."""
    return hmac.new(
        settings.secret_key.encode(),
        token.encode(),
        hashlib.sha256,
    ).hexdigest()


# --- Vault Access (ACL) ---


async def grant_vault_access(
    db: AsyncSession,
    vault_id: str,
    user_id: str,
    role: str,
    granted_by: str,
) -> VaultAccess:
    """Grant a user access to a vault with the specified role."""
    # Check if access already exists
    result = await db.execute(
        select(VaultAccess).where(
            VaultAccess.vault_id == vault_id,
            VaultAccess.user_id == user_id,
        )
    )
    existing = result.scalar_one_or_none()
    if existing is not None:
        existing.role = role
        existing.granted_by = granted_by
        await db.flush()
        return existing

    access = VaultAccess(
        vault_id=vault_id,
        user_id=user_id,
        role=role,
        granted_by=granted_by,
    )
    db.add(access)
    await db.flush()
    return access


async def revoke_vault_access(
    db: AsyncSession,
    vault_id: str,
    user_id: str,
) -> None:
    """Remove a user's access to a vault."""
    await db.execute(
        delete(VaultAccess).where(
            VaultAccess.vault_id == vault_id,
            VaultAccess.user_id == user_id,
        )
    )
    await db.flush()


async def list_vault_access(
    db: AsyncSession,
    vault_id: str,
) -> list[VaultAccess]:
    """List all users with access to a vault."""
    result = await db.execute(
        select(VaultAccess).where(VaultAccess.vault_id == vault_id)
    )
    return list(result.scalars().all())


async def update_vault_role(
    db: AsyncSession,
    vault_id: str,
    user_id: str,
    new_role: str,
) -> VaultAccess | None:
    """Update a user's role for a vault."""
    result = await db.execute(
        select(VaultAccess).where(
            VaultAccess.vault_id == vault_id,
            VaultAccess.user_id == user_id,
        )
    )
    access = result.scalar_one_or_none()
    if access is None:
        return None
    access.role = new_role
    await db.flush()
    return access


# --- Share Links ---


async def create_share_link(
    db: AsyncSession,
    vault_id: str,
    file_path: str | None,
    created_by: str,
    permissions: str = "view",
    expires_at: datetime | None = None,
    password: str | None = None,
    max_access: int | None = None,
) -> tuple[ShareLink, str]:
    """Create a share link. Returns (ShareLink, raw_token)."""
    raw_token = secrets.token_urlsafe(32)
    token_hash = _hmac_token(raw_token)

    password_hash = None
    if password:
        import bcrypt

        password_hash = bcrypt.hashpw(
            password.encode(), bcrypt.gensalt(rounds=12)
        ).decode()

    link = ShareLink(
        vault_id=vault_id,
        file_path=file_path,
        token=token_hash,
        created_by=created_by,
        permissions=permissions,
        password_hash=password_hash,
        expires_at=expires_at,
        max_access_count=max_access,
    )
    db.add(link)
    await db.flush()
    return link, raw_token


async def verify_share_link(
    db: AsyncSession,
    token: str,
) -> ShareLink | None:
    """Verify a share link token. Returns the ShareLink if valid, None otherwise."""
    token_hash = _hmac_token(token)
    result = await db.execute(
        select(ShareLink).where(
            ShareLink.token == token_hash,
            ShareLink.revoked == False,  # noqa: E712
        )
    )
    link = result.scalar_one_or_none()
    if link is None:
        return None

    # Check expiry
    if link.expires_at is not None:
        expires_at = link.expires_at
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        if expires_at < datetime.now(timezone.utc):
            return None

    # Check max access count
    if link.max_access_count is not None and link.access_count >= link.max_access_count:
        return None

    # Increment access count
    link.access_count += 1
    await db.flush()
    return link


async def revoke_share_link(
    db: AsyncSession,
    link_id: str,
) -> bool:
    """Revoke a share link. Returns True if found and revoked."""
    result = await db.execute(
        select(ShareLink).where(ShareLink.id == link_id)
    )
    link = result.scalar_one_or_none()
    if link is None:
        return False
    link.revoked = True
    await db.flush()
    return True


async def list_share_links(
    db: AsyncSession,
    vault_id: str,
) -> list[ShareLink]:
    """List all share links for a vault."""
    result = await db.execute(
        select(ShareLink).where(ShareLink.vault_id == vault_id)
    )
    return list(result.scalars().all())


def verify_share_link_password(link: ShareLink, password: str) -> bool:
    """Verify a password against a share link's password hash."""
    if link.password_hash is None:
        return True
    import bcrypt

    return bcrypt.checkpw(password.encode(), link.password_hash.encode())
