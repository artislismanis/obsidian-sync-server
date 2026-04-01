"""Tests for sharing: vault access management and share links."""

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from obsidian_sync.services import auth as auth_service


async def _setup_admin(client: AsyncClient) -> str:
    """Create admin and return access token."""
    resp = await client.post(
        "/api/v1/auth/setup",
        json={"username": "admin", "password": "securepass123"},
    )
    return resp.json()["access_token"]


async def _create_user(
    client: AsyncClient, db: AsyncSession, username: str
) -> tuple[str, str]:
    """Create a non-admin user and return (user_id, access_token)."""
    user = await auth_service.create_admin_user(db, username, "testpass123")
    user.is_superadmin = False
    await db.commit()
    resp = await client.post(
        "/api/v1/auth/login",
        json={"username": username, "password": "testpass123"},
    )
    token = resp.json()["access_token"]
    return user.id, token


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_grant_vault_access(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    admin_token = await _setup_admin(client)
    user_id, _ = await _create_user(client, db_session, "reader")

    # Create vault
    vault_resp = await client.post(
        "/api/v1/vaults",
        json={"name": "Shared Vault"},
        headers=_auth(admin_token),
    )
    vault_id = vault_resp.json()["id"]

    # Grant access
    resp = await client.post(
        f"/api/v1/vaults/{vault_id}/sharing",
        json={"user_id": user_id, "role": "read"},
        headers=_auth(admin_token),
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["user_id"] == user_id
    assert data["role"] == "read"


@pytest.mark.asyncio
async def test_revoke_vault_access(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    admin_token = await _setup_admin(client)
    user_id, user_token = await _create_user(client, db_session, "reader")

    vault_resp = await client.post(
        "/api/v1/vaults",
        json={"name": "Shared Vault"},
        headers=_auth(admin_token),
    )
    vault_id = vault_resp.json()["id"]

    # Grant then revoke
    await client.post(
        f"/api/v1/vaults/{vault_id}/sharing",
        json={"user_id": user_id, "role": "read"},
        headers=_auth(admin_token),
    )
    resp = await client.delete(
        f"/api/v1/vaults/{vault_id}/sharing/{user_id}",
        headers=_auth(admin_token),
    )
    assert resp.status_code == 204

    # User should no longer have access
    resp = await client.get(
        f"/api/v1/vaults/{vault_id}",
        headers=_auth(user_token),
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_list_vault_access(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    admin_token = await _setup_admin(client)
    user_id, _ = await _create_user(client, db_session, "writer")

    vault_resp = await client.post(
        "/api/v1/vaults",
        json={"name": "Shared Vault"},
        headers=_auth(admin_token),
    )
    vault_id = vault_resp.json()["id"]

    # Grant access
    await client.post(
        f"/api/v1/vaults/{vault_id}/sharing",
        json={"user_id": user_id, "role": "write"},
        headers=_auth(admin_token),
    )

    resp = await client.get(
        f"/api/v1/vaults/{vault_id}/sharing",
        headers=_auth(admin_token),
    )
    assert resp.status_code == 200
    data = resp.json()
    # Should include owner + the granted user
    assert len(data["access"]) == 2


@pytest.mark.asyncio
async def test_read_user_cannot_grant_access(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    admin_token = await _setup_admin(client)
    user_id, user_token = await _create_user(client, db_session, "reader")
    other_id, _ = await _create_user(client, db_session, "other")

    vault_resp = await client.post(
        "/api/v1/vaults",
        json={"name": "Shared Vault"},
        headers=_auth(admin_token),
    )
    vault_id = vault_resp.json()["id"]

    # Grant read access to user
    await client.post(
        f"/api/v1/vaults/{vault_id}/sharing",
        json={"user_id": user_id, "role": "read"},
        headers=_auth(admin_token),
    )

    # Read user tries to grant access => 403
    resp = await client.post(
        f"/api/v1/vaults/{vault_id}/sharing",
        json={"user_id": other_id, "role": "read"},
        headers=_auth(user_token),
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_create_share_link_with_expiry(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    admin_token = await _setup_admin(client)

    vault_resp = await client.post(
        "/api/v1/vaults",
        json={"name": "Link Vault"},
        headers=_auth(admin_token),
    )
    vault_id = vault_resp.json()["id"]

    resp = await client.post(
        f"/api/v1/vaults/{vault_id}/share-links",
        json={
            "file_path": "notes/readme.md",
            "permissions": "view",
            "expires_in_hours": 24,
        },
        headers=_auth(admin_token),
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["token"] is not None
    assert data["expires_at"] is not None
    assert data["permissions"] == "view"
    assert data["file_path"] == "notes/readme.md"


@pytest.mark.asyncio
async def test_verify_share_link_valid(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    admin_token = await _setup_admin(client)

    vault_resp = await client.post(
        "/api/v1/vaults",
        json={"name": "Link Vault"},
        headers=_auth(admin_token),
    )
    vault_id = vault_resp.json()["id"]

    # Create a vault-level share link
    link_resp = await client.post(
        f"/api/v1/vaults/{vault_id}/share-links",
        json={"permissions": "view", "expires_in_hours": 24},
        headers=_auth(admin_token),
    )
    raw_token = link_resp.json()["token"]

    # Access the share link (no files yet, so we get empty list)
    resp = await client.get(f"/api/v1/share/{raw_token}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["vault_id"] == vault_id
    assert data["permissions"] == "view"


@pytest.mark.asyncio
async def test_verify_share_link_expired(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """Expired share link should return 404."""
    admin_token = await _setup_admin(client)

    vault_resp = await client.post(
        "/api/v1/vaults",
        json={"name": "Link Vault"},
        headers=_auth(admin_token),
    )
    vault_id = vault_resp.json()["id"]

    # Create share link that expires immediately (0 hours => already expired after creation)
    from datetime import datetime, timezone

    from obsidian_sync.services import sharing as sharing_service

    # Directly create an expired link
    expired_at = datetime(2020, 1, 1, tzinfo=timezone.utc)
    link, raw_token = await sharing_service.create_share_link(
        db_session,
        vault_id=vault_id,
        file_path=None,
        created_by="fake-user",
        permissions="view",
        expires_at=expired_at,
    )
    await db_session.commit()

    resp = await client.get(f"/api/v1/share/{raw_token}")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_verify_share_link_revoked(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    admin_token = await _setup_admin(client)

    vault_resp = await client.post(
        "/api/v1/vaults",
        json={"name": "Link Vault"},
        headers=_auth(admin_token),
    )
    vault_id = vault_resp.json()["id"]

    link_resp = await client.post(
        f"/api/v1/vaults/{vault_id}/share-links",
        json={"permissions": "view"},
        headers=_auth(admin_token),
    )
    link_id = link_resp.json()["id"]
    raw_token = link_resp.json()["token"]

    # Revoke
    resp = await client.delete(
        f"/api/v1/vaults/{vault_id}/share-links/{link_id}",
        headers=_auth(admin_token),
    )
    assert resp.status_code == 204

    # Access should fail
    resp = await client.get(f"/api/v1/share/{raw_token}")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_public_share_link_access(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """Public share link should be accessible without authentication."""
    admin_token = await _setup_admin(client)

    vault_resp = await client.post(
        "/api/v1/vaults",
        json={"name": "Public Vault"},
        headers=_auth(admin_token),
    )
    vault_id = vault_resp.json()["id"]

    link_resp = await client.post(
        f"/api/v1/vaults/{vault_id}/share-links",
        json={"permissions": "view"},
        headers=_auth(admin_token),
    )
    raw_token = link_resp.json()["token"]

    # Access without any auth headers
    resp = await client.get(f"/api/v1/share/{raw_token}")
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_password_protected_share_link(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    admin_token = await _setup_admin(client)

    vault_resp = await client.post(
        "/api/v1/vaults",
        json={"name": "Protected Vault"},
        headers=_auth(admin_token),
    )
    vault_id = vault_resp.json()["id"]

    link_resp = await client.post(
        f"/api/v1/vaults/{vault_id}/share-links",
        json={"permissions": "view", "password": "s3cret"},
        headers=_auth(admin_token),
    )
    raw_token = link_resp.json()["token"]

    # Access without password => 401
    resp = await client.get(f"/api/v1/share/{raw_token}")
    assert resp.status_code == 401

    # Access with wrong password => 401
    resp = await client.get(
        f"/api/v1/share/{raw_token}", params={"password": "wrong"}
    )
    assert resp.status_code == 401

    # Access with correct password => 200
    resp = await client.get(
        f"/api/v1/share/{raw_token}", params={"password": "s3cret"}
    )
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_share_link_max_access_count(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    admin_token = await _setup_admin(client)

    vault_resp = await client.post(
        "/api/v1/vaults",
        json={"name": "Limited Vault"},
        headers=_auth(admin_token),
    )
    vault_id = vault_resp.json()["id"]

    link_resp = await client.post(
        f"/api/v1/vaults/{vault_id}/share-links",
        json={"permissions": "view", "max_access_count": 2},
        headers=_auth(admin_token),
    )
    raw_token = link_resp.json()["token"]

    # First two accesses should work
    resp = await client.get(f"/api/v1/share/{raw_token}")
    assert resp.status_code == 200
    resp = await client.get(f"/api/v1/share/{raw_token}")
    assert resp.status_code == 200

    # Third access should fail
    resp = await client.get(f"/api/v1/share/{raw_token}")
    assert resp.status_code == 404
