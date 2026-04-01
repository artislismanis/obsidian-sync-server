"""Local filesystem storage backend."""

import hashlib
import os
from datetime import datetime, timezone
from pathlib import Path

import aiofiles
import aiofiles.os

from obsidian_sync.storage.base import StorageBackend, StorageEntry, StorageStat


class LocalStorage:
    """Stores vault files on the local filesystem."""

    def __init__(self, root_path: str) -> None:
        self.root = Path(root_path)

    def _resolve(self, path: str) -> Path:
        """Resolve a vault-relative path to an absolute path, preventing traversal."""
        resolved = (self.root / path).resolve()
        if not str(resolved).startswith(str(self.root.resolve())):
            raise ValueError(f"Path traversal attempt: {path}")
        return resolved

    async def read(self, path: str) -> bytes:
        full_path = self._resolve(path)
        async with aiofiles.open(full_path, "rb") as f:
            return await f.read()

    async def write(self, path: str, data: bytes, content_hash: str = "") -> None:
        full_path = self._resolve(path)
        full_path.parent.mkdir(parents=True, exist_ok=True)
        async with aiofiles.open(full_path, "wb") as f:
            await f.write(data)

    async def delete(self, path: str) -> None:
        full_path = self._resolve(path)
        if full_path.is_file():
            await aiofiles.os.remove(full_path)

    async def exists(self, path: str) -> bool:
        full_path = self._resolve(path)
        return full_path.exists()

    async def list(self, prefix: str = "") -> list[StorageEntry]:
        target = self._resolve(prefix) if prefix else self.root
        if not target.exists():
            return []

        entries = []
        for item in sorted(target.iterdir()):
            rel_path = str(item.relative_to(self.root))
            stat = item.stat()
            entries.append(
                StorageEntry(
                    path=rel_path,
                    size=stat.st_size if item.is_file() else 0,
                    is_dir=item.is_dir(),
                    modified=datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc),
                )
            )
        return entries

    async def stat(self, path: str) -> StorageStat:
        full_path = self._resolve(path)
        if not full_path.exists():
            raise FileNotFoundError(f"File not found: {path}")
        file_stat = full_path.stat()

        # Compute hash for files
        content_hash = None
        if full_path.is_file():
            async with aiofiles.open(full_path, "rb") as f:
                data = await f.read()
                content_hash = hashlib.sha256(data).hexdigest()

        return StorageStat(
            size=file_stat.st_size,
            modified=datetime.fromtimestamp(file_stat.st_mtime, tz=timezone.utc),
            content_hash=content_hash,
        )
