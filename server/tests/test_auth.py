"""Tests for authentication: setup, login, refresh, tokens."""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_setup_creates_admin(client: AsyncClient) -> None:
    """First-run setup should create an admin and return tokens."""
    response = await client.post(
        "/api/v1/auth/setup",
        json={"username": "admin", "password": "securepass123", "email": "admin@test.com"},
    )
    assert response.status_code == 201
    data = response.json()
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["token_type"] == "bearer"


@pytest.mark.asyncio
async def test_setup_only_once(client: AsyncClient) -> None:
    """Setup should fail if already completed."""
    await client.post(
        "/api/v1/auth/setup",
        json={"username": "admin", "password": "securepass123"},
    )
    response = await client.post(
        "/api/v1/auth/setup",
        json={"username": "admin2", "password": "securepass123"},
    )
    assert response.status_code == 409


@pytest.mark.asyncio
async def test_login_success(client: AsyncClient) -> None:
    """Login with correct credentials returns tokens."""
    await client.post(
        "/api/v1/auth/setup",
        json={"username": "admin", "password": "securepass123"},
    )
    response = await client.post(
        "/api/v1/auth/login",
        json={"username": "admin", "password": "securepass123"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert "refresh_token" in data


@pytest.mark.asyncio
async def test_login_wrong_password(client: AsyncClient) -> None:
    """Login with wrong password returns 401."""
    await client.post(
        "/api/v1/auth/setup",
        json={"username": "admin", "password": "securepass123"},
    )
    response = await client.post(
        "/api/v1/auth/login",
        json={"username": "admin", "password": "wrongpass"},
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_login_nonexistent_user(client: AsyncClient) -> None:
    """Login with nonexistent user returns 401."""
    response = await client.post(
        "/api/v1/auth/login",
        json={"username": "nobody", "password": "pass"},
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_refresh_token_rotation(client: AsyncClient) -> None:
    """Refresh token should be rotated (old invalidated, new issued)."""
    setup_resp = await client.post(
        "/api/v1/auth/setup",
        json={"username": "admin", "password": "securepass123"},
    )
    refresh_token = setup_resp.json()["refresh_token"]

    # Use refresh token
    refresh_resp = await client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": refresh_token},
    )
    assert refresh_resp.status_code == 200
    new_data = refresh_resp.json()
    assert new_data["refresh_token"] != refresh_token

    # Old refresh token should be invalidated
    reuse_resp = await client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": refresh_token},
    )
    assert reuse_resp.status_code == 401


@pytest.mark.asyncio
async def test_access_token_authenticates(client: AsyncClient) -> None:
    """Access token should allow authenticated requests."""
    setup_resp = await client.post(
        "/api/v1/auth/setup",
        json={"username": "admin", "password": "securepass123"},
    )
    token = setup_resp.json()["access_token"]

    response = await client.get(
        "/api/v1/vaults",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_no_auth_returns_401(client: AsyncClient) -> None:
    """Requests without auth should return 401."""
    response = await client.get("/api/v1/vaults")
    assert response.status_code in (401, 403)


@pytest.mark.asyncio
async def test_invalid_token_returns_401(client: AsyncClient) -> None:
    """Invalid JWT should return 401."""
    response = await client.get(
        "/api/v1/vaults",
        headers={"Authorization": "Bearer invalid.token.here"},
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_create_api_key(client: AsyncClient) -> None:
    """Creating an API key should return the key value."""
    setup_resp = await client.post(
        "/api/v1/auth/setup",
        json={"username": "admin", "password": "securepass123"},
    )
    token = setup_resp.json()["access_token"]

    response = await client.post(
        "/api/v1/auth/api-keys",
        json={"name": "test-key"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "test-key"
    assert data["key"].startswith("oss_")
    assert data["prefix"] == data["key"][:12]


@pytest.mark.asyncio
async def test_api_key_authenticates(client: AsyncClient) -> None:
    """API key should authenticate requests."""
    setup_resp = await client.post(
        "/api/v1/auth/setup",
        json={"username": "admin", "password": "securepass123"},
    )
    token = setup_resp.json()["access_token"]

    key_resp = await client.post(
        "/api/v1/auth/api-keys",
        json={"name": "test-key"},
        headers={"Authorization": f"Bearer {token}"},
    )
    api_key = key_resp.json()["key"]

    response = await client.get(
        "/api/v1/vaults",
        headers={"X-API-Key": api_key},
    )
    assert response.status_code == 200
