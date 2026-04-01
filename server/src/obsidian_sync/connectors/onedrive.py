"""OneDrive sync connector via Microsoft Graph API."""

import logging
from datetime import datetime

import httpx

from obsidian_sync.connectors.base import RemoteFile

logger = logging.getLogger(__name__)

GRAPH_API = "https://graph.microsoft.com/v1.0"


class OneDriveConnector:
    """OneDrive sync via Microsoft Graph API."""

    def __init__(self) -> None:
        self._token = ""
        self._folder_path = "/ObsidianSync"
        self._client: httpx.AsyncClient | None = None

    async def authenticate(self, oauth_token: str, folder_path: str = "/ObsidianSync") -> None:
        self._token = oauth_token
        self._folder_path = folder_path
        self._client = httpx.AsyncClient(
            headers={"Authorization": f"Bearer {self._token}"},
            timeout=30.0,
        )

    def _item_path(self, path: str) -> str:
        """Build Graph API path for a file in the sync folder."""
        full = f"{self._folder_path}/{path}".replace("//", "/")
        return f"{GRAPH_API}/me/drive/root:{full}"

    async def push_file(self, remote_path: str, content: bytes) -> str:
        assert self._client is not None
        url = f"{self._item_path(remote_path)}:/content"
        resp = await self._client.put(
            url, content=content, headers={"Content-Type": "application/octet-stream"}
        )
        resp.raise_for_status()
        return resp.json().get("id", "")

    async def pull_file(self, remote_path: str) -> bytes:
        assert self._client is not None
        url = f"{self._item_path(remote_path)}:/content"
        resp = await self._client.get(url, follow_redirects=True)
        resp.raise_for_status()
        return resp.content

    async def list_files(self, prefix: str = "") -> list[RemoteFile]:
        assert self._client is not None
        folder = self._folder_path
        if prefix:
            folder = f"{folder}/{prefix}"

        url = f"{GRAPH_API}/me/drive/root:{folder}:/children"
        resp = await self._client.get(
            url, params={"$select": "id,name,size,lastModifiedDateTime,file"}
        )

        if resp.status_code == 404:
            return []

        resp.raise_for_status()
        data = resp.json()

        return [
            RemoteFile(
                path=item.get("name", ""),
                size=item.get("size", 0),
                modified=datetime.fromisoformat(
                    item["lastModifiedDateTime"].replace("Z", "+00:00")
                )
                if item.get("lastModifiedDateTime")
                else None,
                remote_id=item.get("id", ""),
            )
            for item in data.get("value", [])
            if "file" in item  # Skip folders
        ]

    async def delete_file(self, remote_path: str) -> None:
        assert self._client is not None
        url = self._item_path(remote_path)
        resp = await self._client.delete(url)
        if resp.status_code != 404:
            resp.raise_for_status()

    async def get_changes_since(
        self, delta_url: str
    ) -> tuple[list[RemoteFile], str]:
        """Use the Microsoft Graph delta API for change tracking."""
        assert self._client is not None

        if not delta_url:
            url = f"{GRAPH_API}/me/drive/root:{self._folder_path}:/delta"
        else:
            url = delta_url

        resp = await self._client.get(url)
        resp.raise_for_status()
        data = resp.json()

        changed = [
            RemoteFile(
                path=item.get("name", ""),
                size=item.get("size", 0),
                remote_id=item.get("id", ""),
            )
            for item in data.get("value", [])
            if "file" in item and not item.get("deleted")
        ]

        # Get next delta link
        next_url = data.get("@odata.deltaLink", data.get("@odata.nextLink", delta_url))
        return changed, next_url
