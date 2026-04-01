"""Storage backend protocol and types."""

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol


@dataclass
class StorageEntry:
    path: str
    size: int
    is_dir: bool
    modified: datetime | None = None


@dataclass
class StorageStat:
    size: int
    modified: datetime | None = None
    content_hash: str | None = None


class StorageBackend(Protocol):
    """Protocol for vault storage backends. All paths are vault-relative."""

    async def read(self, path: str) -> bytes: ...

    async def write(self, path: str, data: bytes, content_hash: str = "") -> None: ...

    async def delete(self, path: str) -> None: ...

    async def exists(self, path: str) -> bool: ...

    async def list(self, prefix: str = "") -> list[StorageEntry]: ...

    async def stat(self, path: str) -> StorageStat: ...
