"""Sync service: file versioning and sync operations."""

from sqlalchemy import select, func, and_, desc
from sqlalchemy.ext.asyncio import AsyncSession

from obsidian_sync.models.sync import FileVersion, SyncOperation


async def get_vault_version(db: AsyncSession, vault_id: str) -> int:
    """Get the latest version number for a vault (max of sync operations)."""
    result = await db.execute(
        select(func.coalesce(func.max(SyncOperation.version), 0)).where(
            SyncOperation.vault_id == vault_id
        )
    )
    return result.scalar_one()


async def get_file_version(
    db: AsyncSession, vault_id: str, path: str
) -> FileVersion | None:
    """Get the latest version of a specific file."""
    result = await db.execute(
        select(FileVersion)
        .where(
            FileVersion.vault_id == vault_id,
            FileVersion.file_path == path,
        )
        .order_by(desc(FileVersion.version))
        .limit(1)
    )
    return result.scalar_one_or_none()


async def create_file_version(
    db: AsyncSession,
    vault_id: str,
    path: str,
    content_hash: str,
    size_bytes: int,
    author_id: str,
) -> FileVersion:
    """Create a new file version, auto-incrementing the version number."""
    current = await get_file_version(db, vault_id, path)
    next_version = (current.version + 1) if current else 1

    file_version = FileVersion(
        vault_id=vault_id,
        file_path=path,
        version=next_version,
        content_hash=content_hash,
        size_bytes=size_bytes,
        author_id=author_id,
    )
    db.add(file_version)
    await db.flush()
    return file_version


async def record_sync_operation(
    db: AsyncSession,
    vault_id: str,
    path: str,
    op_type: str,
    author_id: str,
    payload: str | None = None,
) -> SyncOperation:
    """Record a sync operation, auto-incrementing the vault-level version."""
    vault_ver = await get_vault_version(db, vault_id)
    next_version = vault_ver + 1

    operation = SyncOperation(
        vault_id=vault_id,
        file_path=path,
        operation_type=op_type,
        version=next_version,
        author_id=author_id,
        payload=payload,
    )
    db.add(operation)
    await db.flush()
    return operation


async def get_operations_since(
    db: AsyncSession, vault_id: str, since_version: int
) -> list[SyncOperation]:
    """Get all operations since a given version (for catch-up sync)."""
    result = await db.execute(
        select(SyncOperation)
        .where(
            SyncOperation.vault_id == vault_id,
            SyncOperation.version > since_version,
        )
        .order_by(SyncOperation.version)
    )
    return list(result.scalars().all())


async def detect_conflict(
    db: AsyncSession, vault_id: str, path: str, client_version: int
) -> bool:
    """Returns True if the server version for the file is ahead of client_version."""
    current = await get_file_version(db, vault_id, path)
    if current is None:
        return False
    return current.version > client_version


async def list_vault_files(
    db: AsyncSession, vault_id: str
) -> list[FileVersion]:
    """List the latest version of each file in a vault.

    Uses a subquery to find max version per file_path, then joins back
    to get the full FileVersion rows.
    """
    # Subquery: max version per file_path
    max_version_subq = (
        select(
            FileVersion.file_path,
            func.max(FileVersion.version).label("max_version"),
        )
        .where(FileVersion.vault_id == vault_id)
        .group_by(FileVersion.file_path)
        .subquery()
    )

    result = await db.execute(
        select(FileVersion)
        .join(
            max_version_subq,
            and_(
                FileVersion.file_path == max_version_subq.c.file_path,
                FileVersion.version == max_version_subq.c.max_version,
            ),
        )
        .where(FileVersion.vault_id == vault_id)
        .order_by(FileVersion.file_path)
    )
    return list(result.scalars().all())
