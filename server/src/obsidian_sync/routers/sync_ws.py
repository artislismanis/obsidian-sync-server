"""WebSocket sync endpoint + connected devices API."""

import logging

from fastapi import APIRouter, Depends, Query, WebSocket, WebSocketDisconnect
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.ext.asyncio import AsyncSession

from obsidian_sync.database import get_db, async_session
from obsidian_sync.services.auth import decode_access_token
from obsidian_sync.services.vault import get_vault, get_user_vault_role
from obsidian_sync.models.vault import VaultRole
from obsidian_sync.websocket.handler import manager
from obsidian_sync.websocket.protocol import handle_message

logger = logging.getLogger(__name__)

router = APIRouter(tags=["sync"])


@router.websocket("/api/v1/sync/{vault_id}")
async def sync_websocket(
    websocket: WebSocket,
    vault_id: str,
    token: str = Query(default=""),
    device_id: str = Query(default=""),
    device_name: str = Query(default=""),
) -> None:
    """WebSocket endpoint for vault sync. Authenticate via ?token=JWT query param.

    Security note: JWT in query string is visible in server access logs and browser
    history. This is a known trade-off — WebSocket doesn't support custom headers
    during the handshake. The short-lived access token (15min) limits exposure.
    Consider using a single-use ticket exchange for production deployments.
    """
    # Authenticate
    try:
        payload = decode_access_token(token)
        user_id = payload["sub"]
    except Exception:
        await websocket.close(code=4001, reason="Invalid token")
        return

    # Check vault access
    async with async_session() as db:
        vault = await get_vault(db, vault_id)
        if vault is None:
            await websocket.close(code=4004, reason="Vault not found")
            return

        role = await get_user_vault_role(db, vault_id, user_id)
        if role is None:
            await websocket.close(code=4003, reason="Access denied")
            return

        # Get username for attribution
        from sqlalchemy import select
        from obsidian_sync.models.user import User
        result = await db.execute(select(User.username).where(User.id == user_id))
        username = result.scalar_one_or_none() or "unknown"

    # Connect
    client = await manager.connect(
        websocket, user_id, vault_id, username,
        device_id=device_id, device_name=device_name,
    )

    try:
        while True:
            data = await websocket.receive_json()

            # Check write permission for mutating operations
            write_ops = {"file_save", "file_delete", "file_rename"}
            if data.get("type") in write_ops and role == VaultRole.read.value:
                await websocket.send_json({
                    "type": "error",
                    "code": "FORBIDDEN",
                    "message": "Read-only access",
                })
                continue

            # Handle message with a fresh DB session
            async with async_session() as db:
                response = await handle_message(client, data, db)
                if response:
                    await websocket.send_json(response)

    except WebSocketDisconnect:
        pass
    except Exception:
        logger.exception(f"WebSocket error for {username} in vault {vault_id}")
    finally:
        manager.disconnect(client)


@router.get("/api/v1/vaults/{vault_id}/devices")
async def list_connected_devices(
    vault_id: str,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """List devices currently connected to a vault via WebSocket."""
    from obsidian_sync.middleware.auth import get_current_user
    from obsidian_sync.database import get_db as _get_db

    clients = manager.get_vault_clients(vault_id)
    return {
        "devices": [
            {
                "device_id": c.device_id,
                "device_name": c.device_name or "Unknown device",
                "username": c.username,
                "user_id": c.user_id,
                "connected_at": c.connected_at,
            }
            for c in clients
        ],
        "count": len(clients),
    }


@router.get("/api/v1/devices")
async def list_all_connected_devices() -> dict:
    """List all currently connected devices across all vaults."""
    clients = manager.get_all_clients()
    return {
        "devices": [
            {
                "device_id": c.device_id,
                "device_name": c.device_name or "Unknown device",
                "username": c.username,
                "vault_id": c.vault_id,
                "connected_at": c.connected_at,
            }
            for c in clients
        ],
        "count": len(clients),
    }
