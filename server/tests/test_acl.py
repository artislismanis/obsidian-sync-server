"""Tests for ACL: role-based access control on vault operations."""

import base64

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


async def _create_vault_and_grant(
    client: AsyncClient,
    admin_token: str,
    user_id: str,
    role: str,
) -> str:
    """Create a vault and grant access to a user. Returns vault_id."""
    vault_resp = await client.post(
        "/api/v1/vaults",
        json={"name": f"Vault for {role}"},
        headers=_auth(admin_token),
    )
    vault_id = vault_resp.json()["id"]

    if role != "none":
        await client.post(
            f"/api/v1/vaults/{vault_id}/sharing",
            json={"user_id": user_id, "role": role},
            headers=_auth(admin_token),
        )
    return vault_id


@pytest.mark.asyncio
async def test_owner_can_do_everything(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """Owner can read, write, manage sharing, and delete vault."""
    admin_token = await _setup_admin(client)

    vault_resp = await client.post(
        "/api/v1/vaults",
        json={"name": "Owner Vault"},
        headers=_auth(admin_token),
    )
    vault_id = vault_resp.json()["id"]

    # Read vault
    resp = await client.get(f"/api/v1/vaults/{vault_id}", headers=_auth(admin_token))
    assert resp.status_code == 200

    # Upload file
    content_hash = "a" * 64
    resp = await client.put(
        f"/api/v1/vaults/{vault_id}/files/test.md",
        json={
            "path": "test.md",
            "content": base64.b64encode(b"hello").decode(),
            "content_hash": content_hash,
            "version": 0,
        },
        headers=_auth(admin_token),
    )
    assert resp.status_code == 200

    # Download file
    resp = await client.get(
        f"/api/v1/vaults/{vault_id}/files/test.md",
        headers=_auth(admin_token),
    )
    assert resp.status_code == 200

    # Manage sharing
    resp = await client.get(
        f"/api/v1/vaults/{vault_id}/sharing",
        headers=_auth(admin_token),
    )
    assert resp.status_code == 200

    # Delete vault
    resp = await client.delete(
        f"/api/v1/vaults/{vault_id}",
        headers=_auth(admin_token),
    )
    assert resp.status_code == 204


@pytest.mark.asyncio
async def test_admin_can_manage_sharing_but_not_delete_vault(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """Admin can manage sharing but cannot delete vault."""
    admin_token = await _setup_admin(client)
    user_id, user_token = await _create_user(client, db_session, "vaultadmin")

    vault_id = await _create_vault_and_grant(
        client, admin_token, user_id, "admin"
    )

    # Admin can manage sharing
    resp = await client.get(
        f"/api/v1/vaults/{vault_id}/sharing",
        headers=_auth(user_token),
    )
    assert resp.status_code == 200

    # Admin can update vault settings
    resp = await client.patch(
        f"/api/v1/vaults/{vault_id}",
        json={"name": "Renamed"},
        headers=_auth(user_token),
    )
    assert resp.status_code == 200

    # Admin cannot delete vault
    resp = await client.delete(
        f"/api/v1/vaults/{vault_id}",
        headers=_auth(user_token),
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_write_user_can_upload_download_but_not_manage_sharing(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """Write user can upload and download files but cannot manage sharing."""
    admin_token = await _setup_admin(client)
    user_id, user_token = await _create_user(client, db_session, "writer")

    vault_id = await _create_vault_and_grant(
        client, admin_token, user_id, "write"
    )

    # Write user can upload
    content_hash = "b" * 64
    resp = await client.put(
        f"/api/v1/vaults/{vault_id}/files/doc.md",
        json={
            "path": "doc.md",
            "content": base64.b64encode(b"content").decode(),
            "content_hash": content_hash,
            "version": 0,
        },
        headers=_auth(user_token),
    )
    assert resp.status_code == 200

    # Write user can download
    resp = await client.get(
        f"/api/v1/vaults/{vault_id}/files/doc.md",
        headers=_auth(user_token),
    )
    assert resp.status_code == 200

    # Write user cannot manage sharing
    resp = await client.get(
        f"/api/v1/vaults/{vault_id}/sharing",
        headers=_auth(user_token),
    )
    assert resp.status_code == 403

    # Write user cannot grant access
    other_id, _ = await _create_user(client, db_session, "other_user")
    resp = await client.post(
        f"/api/v1/vaults/{vault_id}/sharing",
        json={"user_id": other_id, "role": "read"},
        headers=_auth(user_token),
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_read_user_can_only_download(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """Read user can download files but cannot upload."""
    admin_token = await _setup_admin(client)
    user_id, user_token = await _create_user(client, db_session, "reader")

    vault_id = await _create_vault_and_grant(
        client, admin_token, user_id, "read"
    )

    # Owner uploads a file first
    content_hash = "c" * 64
    await client.put(
        f"/api/v1/vaults/{vault_id}/files/readme.md",
        json={
            "path": "readme.md",
            "content": base64.b64encode(b"read me").decode(),
            "content_hash": content_hash,
            "version": 0,
        },
        headers=_auth(admin_token),
    )

    # Read user can download
    resp = await client.get(
        f"/api/v1/vaults/{vault_id}/files/readme.md",
        headers=_auth(user_token),
    )
    assert resp.status_code == 200

    # Read user cannot upload
    resp = await client.put(
        f"/api/v1/vaults/{vault_id}/files/new.md",
        json={
            "path": "new.md",
            "content": base64.b64encode(b"new content").decode(),
            "content_hash": "d" * 64,
            "version": 0,
        },
        headers=_auth(user_token),
    )
    assert resp.status_code == 403

    # Read user cannot manage sharing
    resp = await client.get(
        f"/api/v1/vaults/{vault_id}/sharing",
        headers=_auth(user_token),
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_no_access_user_gets_403(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """User with no access to a vault gets 403."""
    admin_token = await _setup_admin(client)
    user_id, user_token = await _create_user(client, db_session, "outsider")

    vault_id = await _create_vault_and_grant(
        client, admin_token, user_id, "none"
    )

    # Cannot read vault
    resp = await client.get(
        f"/api/v1/vaults/{vault_id}",
        headers=_auth(user_token),
    )
    assert resp.status_code == 403

    # Cannot list files
    resp = await client.get(
        f"/api/v1/vaults/{vault_id}/files",
        headers=_auth(user_token),
    )
    assert resp.status_code == 403

    # Cannot upload
    resp = await client.put(
        f"/api/v1/vaults/{vault_id}/files/test.md",
        json={
            "path": "test.md",
            "content": base64.b64encode(b"nope").decode(),
            "content_hash": "e" * 64,
            "version": 0,
        },
        headers=_auth(user_token),
    )
    assert resp.status_code == 403

    # Cannot manage sharing
    resp = await client.get(
        f"/api/v1/vaults/{vault_id}/sharing",
        headers=_auth(user_token),
    )
    assert resp.status_code == 403
