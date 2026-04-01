"""Base protocol for external sync connectors."""

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol


@dataclass
class RemoteFile:
    path: str
    size: int
    modified: datetime | None = None
    remote_id: str = ""


class SyncConnector(Protocol):
    """Interface for external service sync (Google Drive, OneDrive, etc.)."""

    async def authenticate(self, oauth_token: str) -> None: ...

    async def push_file(self, remote_path: str, content: bytes) -> str:
        """Upload a file. Returns remote file ID."""
        ...

    async def pull_file(self, remote_path: str) -> bytes:
        """Download a file by remote path."""
        ...

    async def list_files(self, prefix: str = "") -> list[RemoteFile]:
        """List files in the remote folder."""
        ...

    async def delete_file(self, remote_path: str) -> None: ...

    async def get_changes_since(self, token: str) -> tuple[list[RemoteFile], str]:
        """Get changes since a change token. Returns (changed_files, new_token)."""
        ...
