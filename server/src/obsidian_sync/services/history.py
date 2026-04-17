"""File version history service: list, diff, restore, prune."""

import difflib

from sqlalchemy import select, func, delete
from sqlalchemy.ext.asyncio import AsyncSession

from obsidian_sync.models.sync import FileVersion


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
