"""File version history service: list, diff, restore, prune."""

import difflib

from sqlalchemy import select, func, delete, desc, and_
from sqlalchemy.ext.asyncio import AsyncSession

from obsidian_sync.models.sync import FileVersion, SyncOperation


async def list_file_versions(
    db: AsyncSession, vault_id: str, path: str
) -> list[FileVersion]:
    result = await db.execute(
        select(FileVersion)
        .where(FileVersion.vault_id == vault_id, FileVersion.file_path == path)
        .order_by(FileVersion.version.desc())
    )
    return list(result.scalars().all())


async def get_version(
    db: AsyncSession, vault_id: str, path: str, version: int
) -> FileVersion | None:
    result = await db.execute(
        select(FileVersion).where(
            FileVersion.vault_id == vault_id,
            FileVersion.file_path == path,
            FileVersion.version == version,
        )
    )
    return result.scalar_one_or_none()


def compute_diff(old_text: str, new_text: str) -> str:
    """Compute a unified diff between two text versions."""
    old_lines = old_text.splitlines(keepends=True)
    new_lines = new_text.splitlines(keepends=True)
    diff = difflib.unified_diff(old_lines, new_lines, fromfile="old", tofile="new")
    return "".join(diff)


async def prune_versions(
    db: AsyncSession, vault_id: str, path: str, keep_count: int
) -> int:
    """Delete old versions, keeping the most recent `keep_count`. Returns count deleted."""
    versions = await list_file_versions(db, vault_id, path)
    if len(versions) <= keep_count:
        return 0
    to_delete = versions[keep_count:]
    for fv in to_delete:
        await db.delete(fv)
    await db.flush()
    return len(to_delete)


async def get_deleted_files(db: AsyncSession, vault_id: str) -> list[dict]:
    """Return info about files that have been deleted from a vault.

    Queries SyncOperation where operation_type='delete', then joins with
    FileVersion to get the last version info for each deleted path.
    """
    # Find all paths with a delete operation in this vault
    delete_ops_subq = (
        select(
            SyncOperation.file_path,
            func.max(SyncOperation.created_at).label("deleted_at"),
            SyncOperation.author_id,
        )
        .where(
            SyncOperation.vault_id == vault_id,
            SyncOperation.operation_type == "delete",
        )
        .group_by(SyncOperation.file_path)
        .subquery()
    )

    # For each deleted path, find the latest FileVersion
    max_ver_subq = (
        select(
            FileVersion.file_path,
            func.max(FileVersion.version).label("max_version"),
        )
        .where(FileVersion.vault_id == vault_id)
        .group_by(FileVersion.file_path)
        .subquery()
    )

    result = await db.execute(
        select(
            FileVersion,
            delete_ops_subq.c.deleted_at,
            delete_ops_subq.c.author_id.label("delete_author_id"),
        )
        .join(
            max_ver_subq,
            and_(
                FileVersion.file_path == max_ver_subq.c.file_path,
                FileVersion.version == max_ver_subq.c.max_version,
            ),
        )
        .join(
            delete_ops_subq,
            FileVersion.file_path == delete_ops_subq.c.file_path,
        )
        .where(FileVersion.vault_id == vault_id)
    )

    rows = result.all()
    deleted: list[dict] = []
    for row in rows:
        fv = row[0]
        deleted_at = row[1]
        author_id = row[2]
        deleted.append(
            {
                "path": fv.file_path,
                "deleted_at": deleted_at.isoformat() if deleted_at else "",
                "last_version": fv.version,
                "size_bytes": fv.size_bytes,
                "content_hash": fv.content_hash,
                "author_id": author_id,
            }
        )
    return deleted


async def restore_deleted_file(
    db: AsyncSession, vault_id: str, path: str, author_id: str
) -> FileVersion:
    """Restore a previously deleted file from its version-addressed backup.

    Reads content from .sync/versions/{content_hash}, writes it back to the
    current path in storage, and creates a new FileVersion + SyncOperation.
    """
    from obsidian_sync.services.storage_factory import get_local_vault_storage
    from obsidian_sync.services import sync as sync_service

    # Find the last FileVersion for this path
    fv = await db.execute(
        select(FileVersion)
        .where(FileVersion.vault_id == vault_id, FileVersion.file_path == path)
        .order_by(desc(FileVersion.version))
        .limit(1)
    )
    last_version = fv.scalar_one_or_none()
    if last_version is None:
        raise FileNotFoundError(f"No version history found for {path}")

    # Read content from version-addressed backup
    storage = get_local_vault_storage(vault_id)
    version_path = f".sync/versions/{last_version.content_hash}"
    data = await storage.read(version_path)  # raises FileNotFoundError if missing

    # Write content back to the current path
    await storage.write(path, data, content_hash=last_version.content_hash)

    # Create new FileVersion record
    new_fv = await sync_service.create_file_version(
        db,
        vault_id=vault_id,
        path=path,
        content_hash=last_version.content_hash,
        size_bytes=last_version.size_bytes,
        author_id=author_id,
    )

    # Record sync operation
    await sync_service.record_sync_operation(
        db,
        vault_id=vault_id,
        path=path,
        op_type="create",
        author_id=author_id,
    )

    return new_fv
