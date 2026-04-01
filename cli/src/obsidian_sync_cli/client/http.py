"""HTTP client for the sync server REST API."""

import base64
import hashlib
from typing import Any

import httpx

from obsidian_sync_cli.config import CLIConfig


class SyncHTTPClient:
    def __init__(self, config: CLIConfig) -> None:
        self.config = config
        self._client = httpx.AsyncClient(
            base_url=config.server.server_url.rstrip("/"),
            timeout=30.0,
        )

    async def close(self) -> None:
        await self._client.aclose()

    def _auth_headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.config.server.access_token}"}

    async def _request(self, method: str, path: str, **kwargs: Any) -> httpx.Response:
        resp = await self._client.request(method, path, headers=self._auth_headers(), **kwargs)

        # Auto-refresh on 401
        if resp.status_code == 401:
            if await self._refresh_token():
                resp = await self._client.request(method, path, headers=self._auth_headers(), **kwargs)

        resp.raise_for_status()
        return resp

    async def _refresh_token(self) -> bool:
        try:
            resp = await self._client.post(
                "/api/v1/auth/refresh",
                json={"refresh_token": self.config.server.refresh_token},
            )
            if resp.status_code == 200:
                data = resp.json()
                self.config.server.access_token = data["access_token"]
                self.config.server.refresh_token = data["refresh_token"]
                self.config.save()
                return True
        except Exception:
            pass
        return False

    async def login(self, username: str, password: str) -> dict:
        resp = await self._client.post(
            "/api/v1/auth/login",
            json={"username": username, "password": password},
        )
        resp.raise_for_status()
        data = resp.json()
        self.config.server.access_token = data["access_token"]
        self.config.server.refresh_token = data["refresh_token"]
        self.config.save()
        return data

    async def list_vaults(self) -> list[dict]:
        resp = await self._request("GET", "/api/v1/vaults")
        return resp.json().get("vaults", [])

    async def list_files(self, vault_id: str) -> dict:
        resp = await self._request("GET", f"/api/v1/vaults/{vault_id}/files")
        return resp.json()

    async def upload_file(
        self, vault_id: str, path: str, content: bytes, version: int = 0
    ) -> dict:
        content_hash = hashlib.sha256(content).hexdigest()
        b64 = base64.b64encode(content).decode()
        resp = await self._request(
            "PUT",
            f"/api/v1/vaults/{vault_id}/files/{path}",
            json={
                "path": path,
                "content": b64,
                "version": version,
                "content_hash": content_hash,
            },
        )
        return resp.json()

    async def download_file(self, vault_id: str, path: str) -> tuple[bytes, int]:
        resp = await self._request("GET", f"/api/v1/vaults/{vault_id}/files/{path}")
        data = resp.json()
        content = base64.b64decode(data["content"])
        return content, data["version"]

    async def delete_file(self, vault_id: str, path: str) -> None:
        await self._request("DELETE", f"/api/v1/vaults/{vault_id}/files/{path}")
