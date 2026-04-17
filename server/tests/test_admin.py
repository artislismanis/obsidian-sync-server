"""Tests for admin and user management endpoints."""

import pytest
from httpx import AsyncClient


async def _setup_admin(client: AsyncClient) -> str:
    resp = await client.post(
        "/api/v1/auth/setup",
        json={"username": "admin", "password": "securepass123"},
    )
    return resp.json()["access_token"]


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


# --- User CRUD ---


@pytest.mark.asyncio
async def test_list_users(client: AsyncClient) -> None:
    token = await _setup_admin(client)
    resp = await client.get("/api/v1/users", headers=_auth(token))
    assert resp.status_code == 200
    assert resp.json()["total"] == 1
    assert resp.json()["users"][0]["username"] == "admin"


@pytest.mark.asyncio
async def test_create_user(client: AsyncClient) -> None:
    token = await _setup_admin(client)
    resp = await client.post(
        "/api/v1/users",
        json={"username": "newuser", "password": "testpass123"},
        headers=_auth(token),
    )
    assert resp.status_code == 201
    assert resp.json()["username"] == "newuser"
    assert resp.json()["is_superadmin"] is False


@pytest.mark.asyncio
async def test_create_duplicate_user(client: AsyncClient) -> None:
    token = await _setup_admin(client)
    await client.post(
        "/api/v1/users",
        json={"username": "dup", "password": "testpass123"},
        headers=_auth(token),
    )
    resp = await client.post(
        "/api/v1/users",
        json={"username": "dup", "password": "testpass123"},
        headers=_auth(token),
    )
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_get_user(client: AsyncClient) -> None:
    token = await _setup_admin(client)
    create_resp = await client.post(
        "/api/v1/users",
        json={"username": "lookup", "password": "testpass123", "email": "lookup@test.com"},
        headers=_auth(token),
    )
    user_id = create_resp.json()["id"]
    resp = await client.get(f"/api/v1/users/{user_id}", headers=_auth(token))
    assert resp.status_code == 200
    assert resp.json()["email"] == "lookup@test.com"


@pytest.mark.asyncio
async def test_update_user(client: AsyncClient) -> None:
    token = await _setup_admin(client)
    create_resp = await client.post(
        "/api/v1/users",
        json={"username": "updateme", "password": "testpass123"},
        headers=_auth(token),
    )
    user_id = create_resp.json()["id"]
    resp = await client.patch(
        f"/api/v1/users/{user_id}",
        json={"email": "updated@test.com"},
        headers=_auth(token),
    )
    assert resp.status_code == 200
    assert resp.json()["email"] == "updated@test.com"


@pytest.mark.asyncio
async def test_delete_user(client: AsyncClient) -> None:
    token = await _setup_admin(client)
    create_resp = await client.post(
        "/api/v1/users",
        json={"username": "deleteme", "password": "testpass123"},
        headers=_auth(token),
    )
    user_id = create_resp.json()["id"]
    resp = await client.delete(f"/api/v1/users/{user_id}", headers=_auth(token))
    assert resp.status_code == 204
    resp = await client.get(f"/api/v1/users/{user_id}", headers=_auth(token))
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_cannot_delete_self(client: AsyncClient) -> None:
    token = await _setup_admin(client)
    # Get admin user ID from list
    list_resp = await client.get("/api/v1/users", headers=_auth(token))
    admin_id = list_resp.json()["users"][0]["id"]
    resp = await client.delete(f"/api/v1/users/{admin_id}", headers=_auth(token))
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_reset_password(client: AsyncClient) -> None:
    token = await _setup_admin(client)
    create_resp = await client.post(
        "/api/v1/users",
        json={"username": "resetme", "password": "oldpass12345"},
        headers=_auth(token),
    )
    user_id = create_resp.json()["id"]
    resp = await client.patch(
        f"/api/v1/users/{user_id}/password",
        json={"password": "newpass12345"},
        headers=_auth(token),
    )
    assert resp.status_code == 204
    login_resp = await client.post(
        "/api/v1/auth/login",
        json={"username": "resetme", "password": "newpass12345"},
    )
    assert login_resp.status_code == 200


@pytest.mark.asyncio
async def test_non_admin_cannot_list_users(client: AsyncClient) -> None:
    admin_token = await _setup_admin(client)
    await client.post(
        "/api/v1/users",
        json={"username": "normie", "password": "testpass123"},
        headers=_auth(admin_token),
    )
    login_resp = await client.post(
        "/api/v1/auth/login",
        json={"username": "normie", "password": "testpass123"},
    )
    user_token = login_resp.json()["access_token"]
    resp = await client.get("/api/v1/users", headers=_auth(user_token))
    assert resp.status_code == 403


# --- Admin Stats ---


@pytest.mark.asyncio
async def test_admin_stats(client: AsyncClient) -> None:
    token = await _setup_admin(client)
    resp = await client.get("/api/v1/admin/stats", headers=_auth(token))
    assert resp.status_code == 200
    data = resp.json()
    assert data["users"] >= 1
    assert "vaults" in data
    assert "connected_clients" in data
    assert "storage_bytes" in data


@pytest.mark.asyncio
async def test_admin_audit_log(client: AsyncClient) -> None:
    token = await _setup_admin(client)
    resp = await client.get("/api/v1/admin/audit-log", headers=_auth(token))
    assert resp.status_code == 200
    assert "entries" in resp.json()
    assert "total" in resp.json()


@pytest.mark.asyncio
async def test_admin_config(client: AsyncClient) -> None:
    token = await _setup_admin(client)
    resp = await client.get("/api/v1/admin/config", headers=_auth(token))
    assert resp.status_code == 200
    data = resp.json()
    assert "deployment_mode" in data
    assert "storage_backend" in data


# --- GDPR ---


@pytest.mark.asyncio
async def test_gdpr_export(client: AsyncClient) -> None:
    token = await _setup_admin(client)
    resp = await client.get("/api/v1/account/export", headers=_auth(token))
    assert resp.status_code == 200
    data = resp.json()
    assert data["user"]["username"] == "admin"
    assert "vaults" in data


@pytest.mark.asyncio
async def test_gdpr_deletion_flow(client: AsyncClient) -> None:
    token = await _setup_admin(client)

    # Request deletion
    resp = await client.delete("/api/v1/account/delete", headers=_auth(token))
    assert resp.status_code == 200
    assert resp.json()["status"] == "deletion_requested"

    # Idempotent
    resp = await client.delete("/api/v1/account/delete", headers=_auth(token))
    assert resp.json()["status"] == "already_requested"

    # Cancel
    resp = await client.post("/api/v1/account/cancel-deletion", headers=_auth(token))
    assert resp.status_code == 200
    assert resp.json()["status"] == "cancelled"


@pytest.mark.asyncio
async def test_gdpr_consent(client: AsyncClient) -> None:
    token = await _setup_admin(client)
    resp = await client.post("/api/v1/account/consent", headers=_auth(token))
    assert resp.status_code == 200
    assert "gdpr_consent_at" in resp.json()
