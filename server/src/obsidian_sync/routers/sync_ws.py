"""WebSocket sync endpoint."""

import logging

from fastapi import APIRouter, Depends, Query, WebSocket, WebSocketDisconnect
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
    client = await manager.connect(websocket, user_id, vault_id, username)

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
