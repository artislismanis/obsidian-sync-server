"""Tests for vault CRUD operations."""

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


@pytest.mark.asyncio
async def test_create_vault(client: AsyncClient) -> None:
    token = await _setup_and_login(client)
    response = await client.post(
        "/api/v1/vaults",
        json={"name": "My Vault"},
        headers=_auth(token),
    )
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "My Vault"
    assert data["storage_backend"] == "local"
    assert data["encrypted"] is False
    assert data["sync_mode"] == "on_save"
    assert data["obsidian_config_sync"] == "settings_only"


@pytest.mark.asyncio
async def test_list_vaults(client: AsyncClient) -> None:
    token = await _setup_and_login(client)
    await client.post(
        "/api/v1/vaults", json={"name": "Vault 1"}, headers=_auth(token)
    )
    await client.post(
        "/api/v1/vaults", json={"name": "Vault 2"}, headers=_auth(token)
    )

    response = await client.get("/api/v1/vaults", headers=_auth(token))
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 2
    assert len(data["vaults"]) == 2


@pytest.mark.asyncio
async def test_get_vault(client: AsyncClient) -> None:
    token = await _setup_and_login(client)
    create_resp = await client.post(
        "/api/v1/vaults", json={"name": "Test Vault"}, headers=_auth(token)
    )
    vault_id = create_resp.json()["id"]

    response = await client.get(f"/api/v1/vaults/{vault_id}", headers=_auth(token))
    assert response.status_code == 200
    assert response.json()["name"] == "Test Vault"


@pytest.mark.asyncio
async def test_get_nonexistent_vault(client: AsyncClient) -> None:
    token = await _setup_and_login(client)
    response = await client.get(
        "/api/v1/vaults/nonexistent-id", headers=_auth(token)
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_update_vault(client: AsyncClient) -> None:
    token = await _setup_and_login(client)
    create_resp = await client.post(
        "/api/v1/vaults", json={"name": "Old Name"}, headers=_auth(token)
    )
    vault_id = create_resp.json()["id"]

    response = await client.patch(
        f"/api/v1/vaults/{vault_id}",
        json={"name": "New Name", "sync_mode": "both"},
        headers=_auth(token),
    )
    assert response.status_code == 200
    assert response.json()["name"] == "New Name"
    assert response.json()["sync_mode"] == "both"


@pytest.mark.asyncio
async def test_delete_vault(client: AsyncClient) -> None:
    token = await _setup_and_login(client)
    create_resp = await client.post(
        "/api/v1/vaults", json={"name": "To Delete"}, headers=_auth(token)
    )
    vault_id = create_resp.json()["id"]

    response = await client.delete(f"/api/v1/vaults/{vault_id}", headers=_auth(token))
    assert response.status_code == 204

    # Vault should no longer appear in list
    list_resp = await client.get("/api/v1/vaults", headers=_auth(token))
    assert list_resp.json()["total"] == 0


@pytest.mark.asyncio
async def test_create_encrypted_vault(client: AsyncClient) -> None:
    token = await _setup_and_login(client)
    response = await client.post(
        "/api/v1/vaults",
        json={
            "name": "Secret Vault",
            "encrypted": True,
            "encryption_salt": "random-salt-value",
        },
        headers=_auth(token),
    )
    assert response.status_code == 201
    assert response.json()["encrypted"] is True


@pytest.mark.asyncio
async def test_create_vault_with_config_sync_options(client: AsyncClient) -> None:
    token = await _setup_and_login(client)

    for mode in ["all", "settings_only", "none"]:
        response = await client.post(
            "/api/v1/vaults",
            json={"name": f"Vault {mode}", "obsidian_config_sync": mode},
            headers=_auth(token),
        )
        assert response.status_code == 201
        assert response.json()["obsidian_config_sync"] == mode
