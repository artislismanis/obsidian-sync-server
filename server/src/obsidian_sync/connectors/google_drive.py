"""Google Drive sync connector."""

import json
import logging
from datetime import datetime, timezone

import httpx

from obsidian_sync.connectors.base import RemoteFile

logger = logging.getLogger(__name__)

DRIVE_API = "https://www.googleapis.com/drive/v3"
UPLOAD_API = "https://www.googleapis.com/upload/drive/v3"


class GoogleDriveConnector:
    """Google Drive sync via Drive API v3."""

    def __init__(self) -> None:
        self._token = ""
        self._folder_id = ""
        self._client: httpx.AsyncClient | None = None

    async def authenticate(self, oauth_token: str, folder_id: str = "") -> None:
        self._token = oauth_token
        self._folder_id = folder_id
        self._client = httpx.AsyncClient(
            headers={"Authorization": f"Bearer {self._token}"},
            timeout=30.0,
        )

    async def _ensure_folder(self, name: str = "ObsidianSync") -> str:
        """Get or create the sync folder. Returns folder ID."""
        if self._folder_id:
            return self._folder_id

        assert self._client is not None
        # Search for existing folder
        resp = await self._client.get(
            f"{DRIVE_API}/files",
            params={
                "q": f"name='{name}' and mimeType='application/vnd.google-apps.folder' and trashed=false",
                "fields": "files(id)",
            },
        )
        data = resp.json()
        if data.get("files"):
            self._folder_id = data["files"][0]["id"]
            return self._folder_id

        # Create folder
        resp = await self._client.post(
            f"{DRIVE_API}/files",
            json={"name": name, "mimeType": "application/vnd.google-apps.folder"},
        )
        self._folder_id = resp.json()["id"]
        return self._folder_id

    async def push_file(self, remote_path: str, content: bytes) -> str:
        assert self._client is not None
        folder_id = await self._ensure_folder()

        # Check if file exists
        resp = await self._client.get(
            f"{DRIVE_API}/files",
            params={
                "q": f"name='{remote_path}' and '{folder_id}' in parents and trashed=false",
                "fields": "files(id)",
            },
        )
        existing = resp.json().get("files", [])

        if existing:
            # Update existing file
            file_id = existing[0]["id"]
            resp = await self._client.patch(
                f"{UPLOAD_API}/files/{file_id}",
                params={"uploadType": "media"},
                content=content,
                headers={"Content-Type": "application/octet-stream"},
            )
            return file_id
        else:
            # Create new file
            metadata = json.dumps({"name": remote_path, "parents": [folder_id]})
            # Simple upload for files < 5MB
            boundary = "obsidian_sync_boundary"
            body = (
                f"--{boundary}\r\n"
                f"Content-Type: application/json\r\n\r\n"
                f"{metadata}\r\n"
                f"--{boundary}\r\n"
                f"Content-Type: application/octet-stream\r\n\r\n"
            ).encode() + content + f"\r\n--{boundary}--".encode()

            resp = await self._client.post(
                f"{UPLOAD_API}/files",
                params={"uploadType": "multipart"},
                content=body,
                headers={"Content-Type": f"multipart/related; boundary={boundary}"},
            )
            return resp.json().get("id", "")

    async def pull_file(self, remote_path: str) -> bytes:
        assert self._client is not None
        folder_id = await self._ensure_folder()

        resp = await self._client.get(
            f"{DRIVE_API}/files",
            params={
                "q": f"name='{remote_path}' and '{folder_id}' in parents and trashed=false",
                "fields": "files(id)",
            },
        )
        files = resp.json().get("files", [])
        if not files:
            raise FileNotFoundError(f"File not found on Drive: {remote_path}")

        file_id = files[0]["id"]
        resp = await self._client.get(
            f"{DRIVE_API}/files/{file_id}", params={"alt": "media"}
        )
        return resp.content

    async def list_files(self, prefix: str = "") -> list[RemoteFile]:
        assert self._client is not None
        folder_id = await self._ensure_folder()

        resp = await self._client.get(
            f"{DRIVE_API}/files",
            params={
                "q": f"'{folder_id}' in parents and trashed=false",
                "fields": "files(id,name,size,modifiedTime)",
                "pageSize": 1000,
            },
        )
        data = resp.json()
        return [
            RemoteFile(
                path=f.get("name", ""),
                size=int(f.get("size", 0)),
                modified=datetime.fromisoformat(f["modifiedTime"].replace("Z", "+00:00"))
                if f.get("modifiedTime")
                else None,
                remote_id=f.get("id", ""),
            )
            for f in data.get("files", [])
        ]

    async def delete_file(self, remote_path: str) -> None:
        assert self._client is not None
        folder_id = await self._ensure_folder()

        resp = await self._client.get(
            f"{DRIVE_API}/files",
            params={
                "q": f"name='{remote_path}' and '{folder_id}' in parents and trashed=false",
                "fields": "files(id)",
            },
        )
        for f in resp.json().get("files", []):
            await self._client.delete(f"{DRIVE_API}/files/{f['id']}")

    async def get_changes_since(
        self, change_token: str
    ) -> tuple[list[RemoteFile], str]:
        """Poll for changes using the Changes API."""
        assert self._client is not None

        if not change_token:
            # Get initial change token
            resp = await self._client.get(f"{DRIVE_API}/changes/startPageToken")
            return [], resp.json().get("startPageToken", "")

        resp = await self._client.get(
            f"{DRIVE_API}/changes",
            params={
                "pageToken": change_token,
                "fields": "changes(file(id,name,size,modifiedTime,trashed)),newStartPageToken",
            },
        )
        data = resp.json()
        changed = [
            RemoteFile(
                path=c["file"].get("name", ""),
                size=int(c["file"].get("size", 0)),
                remote_id=c["file"].get("id", ""),
            )
            for c in data.get("changes", [])
            if "file" in c and not c["file"].get("trashed")
        ]
        new_token = data.get("newStartPageToken", change_token)
        return changed, new_token
