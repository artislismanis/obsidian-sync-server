"""Tests for file sync operations (Phase 3)."""

import base64
import hashlib

import pytest
from httpx import AsyncClient


async def _setup_and_login(client: AsyncClient) -> str:
    """Helper: create admin and return access token."""
    resp = await client.post(
        "/api/v1/auth/setup",
        json={"username": "admin", "password": "securepass123"},
    )
    return resp.json()["access_token"]


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def _create_vault(client: AsyncClient, token: str, name: str = "Test Vault") -> str:
    resp = await client.post(
        "/api/v1/vaults",
        json={"name": name},
        headers=_auth(token),
    )
    return resp.json()["id"]


def _make_file_payload(path: str, content: str, version: int = 0) -> dict:
    raw = content.encode("utf-8")
    content_b64 = base64.b64encode(raw).decode("ascii")
    content_hash = hashlib.sha256(raw).hexdigest()
    return {
        "path": path,
        "content": content_b64,
        "version": version,
        "content_hash": content_hash,
    }


@pytest.mark.asyncio
async def test_upload_file(client: AsyncClient) -> None:
    token = await _setup_and_login(client)
    vault_id = await _create_vault(client, token)

    payload = _make_file_payload("notes/hello.md", "# Hello World")
    resp = await client.put(
        f"/api/v1/vaults/{vault_id}/files/notes/hello.md",
        json=payload,
        headers=_auth(token),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["path"] == "notes/hello.md"
    assert data["version"] == 1
    assert data["content_hash"] == payload["content_hash"]
    assert data["size_bytes"] == len("# Hello World".encode("utf-8"))


@pytest.mark.asyncio
async def test_download_file(client: AsyncClient) -> None:
    token = await _setup_and_login(client)
    vault_id = await _create_vault(client, token)

    payload = _make_file_payload("test.md", "Test content")
    await client.put(
        f"/api/v1/vaults/{vault_id}/files/test.md",
        json=payload,
        headers=_auth(token),
    )

    resp = await client.get(
        f"/api/v1/vaults/{vault_id}/files/test.md",
        headers=_auth(token),
    )
    assert resp.status_code == 200
    data = resp.json()
    decoded = base64.b64decode(data["content"]).decode("utf-8")
    assert decoded == "Test content"
    assert data["version"] == 1


@pytest.mark.asyncio
async def test_list_files(client: AsyncClient) -> None:
    token = await _setup_and_login(client)
    vault_id = await _create_vault(client, token)

    # Upload two files
    for name in ["a.md", "b.md"]:
        payload = _make_file_payload(name, f"Content of {name}")
        await client.put(
            f"/api/v1/vaults/{vault_id}/files/{name}",
            json=payload,
            headers=_auth(token),
        )

    resp = await client.get(
        f"/api/v1/vaults/{vault_id}/files",
        headers=_auth(token),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["files"]) == 2
    assert data["vault_version"] == 2  # 2 create operations
    paths = [f["path"] for f in data["files"]]
    assert "a.md" in paths
    assert "b.md" in paths


@pytest.mark.asyncio
async def test_delete_file(client: AsyncClient) -> None:
    token = await _setup_and_login(client)
    vault_id = await _create_vault(client, token)

    payload = _make_file_payload("to_delete.md", "Delete me")
    await client.put(
        f"/api/v1/vaults/{vault_id}/files/to_delete.md",
        json=payload,
        headers=_auth(token),
    )

    resp = await client.delete(
        f"/api/v1/vaults/{vault_id}/files/to_delete.md",
        headers=_auth(token),
    )
    assert resp.status_code == 204

    # File should not be downloadable
    resp = await client.get(
        f"/api/v1/vaults/{vault_id}/files/to_delete.md",
        headers=_auth(token),
    )
    # The file version record still exists, but the storage file is gone
    # so the download should fail with 404
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_version_incrementing(client: AsyncClient) -> None:
    token = await _setup_and_login(client)
    vault_id = await _create_vault(client, token)

    # Version 1
    payload = _make_file_payload("doc.md", "Version 1", version=0)
    resp = await client.put(
        f"/api/v1/vaults/{vault_id}/files/doc.md",
        json=payload,
        headers=_auth(token),
    )
    assert resp.json()["version"] == 1

    # Version 2
    payload = _make_file_payload("doc.md", "Version 2", version=1)
    resp = await client.put(
        f"/api/v1/vaults/{vault_id}/files/doc.md",
        json=payload,
        headers=_auth(token),
    )
    assert resp.json()["version"] == 2

    # Version 3
    payload = _make_file_payload("doc.md", "Version 3", version=2)
    resp = await client.put(
        f"/api/v1/vaults/{vault_id}/files/doc.md",
        json=payload,
        headers=_auth(token),
    )
    assert resp.json()["version"] == 3


@pytest.mark.asyncio
async def test_conflict_detection(client: AsyncClient) -> None:
    token = await _setup_and_login(client)
    vault_id = await _create_vault(client, token)

    # Upload version 1
    payload = _make_file_payload("conflict.md", "Original", version=0)
    resp = await client.put(
        f"/api/v1/vaults/{vault_id}/files/conflict.md",
        json=payload,
        headers=_auth(token),
    )
    assert resp.status_code == 200
    assert resp.json()["version"] == 1

    # Try to upload with stale version (0), server has version 1
    payload = _make_file_payload("conflict.md", "Stale update", version=0)
    resp = await client.put(
        f"/api/v1/vaults/{vault_id}/files/conflict.md",
        json=payload,
        headers=_auth(token),
    )
    assert resp.status_code == 409
    assert "conflict" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_operations_recorded(client: AsyncClient) -> None:
    token = await _setup_and_login(client)
    vault_id = await _create_vault(client, token)

    # Create a file
    payload = _make_file_payload("ops.md", "Content", version=0)
    await client.put(
        f"/api/v1/vaults/{vault_id}/files/ops.md",
        json=payload,
        headers=_auth(token),
    )

    # Update the file
    payload = _make_file_payload("ops.md", "Updated content", version=1)
    await client.put(
        f"/api/v1/vaults/{vault_id}/files/ops.md",
        json=payload,
        headers=_auth(token),
    )

    # Delete the file
    await client.delete(
        f"/api/v1/vaults/{vault_id}/files/ops.md",
        headers=_auth(token),
    )

    # Check operations
    resp = await client.get(
        f"/api/v1/vaults/{vault_id}/operations",
        headers=_auth(token),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["vault_version"] == 3
    ops = data["operations"]
    assert len(ops) == 3
    assert ops[0]["operation_type"] == "create"
    assert ops[1]["operation_type"] == "update"
    assert ops[2]["operation_type"] == "delete"


@pytest.mark.asyncio
async def test_operations_since_version(client: AsyncClient) -> None:
    token = await _setup_and_login(client)
    vault_id = await _create_vault(client, token)

    # Create 3 files
    for i in range(3):
        payload = _make_file_payload(f"file{i}.md", f"Content {i}", version=0)
        await client.put(
            f"/api/v1/vaults/{vault_id}/files/file{i}.md",
            json=payload,
            headers=_auth(token),
        )

    # Get operations since version 1 (should get ops 2 and 3)
    resp = await client.get(
        f"/api/v1/vaults/{vault_id}/operations?since=1",
        headers=_auth(token),
    )
    assert resp.status_code == 200
    data = resp.json()
    ops = data["operations"]
    assert len(ops) == 2
    assert ops[0]["version"] == 2
    assert ops[1]["version"] == 3


@pytest.mark.asyncio
async def test_get_nonexistent_file(client: AsyncClient) -> None:
    token = await _setup_and_login(client)
    vault_id = await _create_vault(client, token)

    resp = await client.get(
        f"/api/v1/vaults/{vault_id}/files/nonexistent.md",
        headers=_auth(token),
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_list_files_shows_latest_version(client: AsyncClient) -> None:
    """When a file is updated multiple times, list should show only the latest version."""
    token = await _setup_and_login(client)
    vault_id = await _create_vault(client, token)

    # Create file
    payload = _make_file_payload("evolving.md", "v1", version=0)
    await client.put(
        f"/api/v1/vaults/{vault_id}/files/evolving.md",
        json=payload,
        headers=_auth(token),
    )

    # Update file
    payload = _make_file_payload("evolving.md", "v2", version=1)
    await client.put(
        f"/api/v1/vaults/{vault_id}/files/evolving.md",
        json=payload,
        headers=_auth(token),
    )

    resp = await client.get(
        f"/api/v1/vaults/{vault_id}/files",
        headers=_auth(token),
    )
    data = resp.json()
    assert len(data["files"]) == 1
    assert data["files"][0]["version"] == 2
