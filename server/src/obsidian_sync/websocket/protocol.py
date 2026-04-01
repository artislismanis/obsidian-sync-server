"""WebSocket sync protocol — message types and routing."""

import base64
import hashlib
import json
import logging
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from obsidian_sync.config import settings
from obsidian_sync.services import sync as sync_service
from obsidian_sync.storage.local import LocalStorage
from obsidian_sync.websocket.handler import ConnectedClient, manager

logger = logging.getLogger(__name__)


def _get_vault_storage(vault_id: str) -> LocalStorage:
    return LocalStorage(f"{settings.storage_local_path}/{vault_id}/current")


async def handle_message(
    client: ConnectedClient, data: dict, db: AsyncSession
) -> dict | None:
    """Route a WebSocket message to the appropriate handler. Returns a response dict or None."""
    msg_type = data.get("type")

    handlers = {
        "file_save": _handle_file_save,
        "file_delete": _handle_file_delete,
        "file_rename": _handle_file_rename,
        "pull": _handle_pull,
        "ping": _handle_ping,
    }

    handler = handlers.get(msg_type)
    if handler is None:
        return {"type": "error", "code": "UNKNOWN_TYPE", "message": f"Unknown message type: {msg_type}"}

    try:
        return await handler(client, data, db)
    except Exception as e:
        logger.exception(f"Error handling {msg_type}")
        return {"type": "error", "code": "INTERNAL_ERROR", "message": str(e)}


async def _handle_file_save(
    client: ConnectedClient, data: dict, db: AsyncSession
) -> dict:
    path = data.get("path", "")
    content_b64 = data.get("content", "")
    client_version = data.get("version", 0)
    content_hash = data.get("content_hash", "")

    if not path or not content_b64:
        return {"type": "error", "code": "BAD_REQUEST", "message": "Missing path or content"}

    # Decode content
    try:
        content = base64.b64decode(content_b64)
    except Exception:
        return {"type": "error", "code": "BAD_REQUEST", "message": "Invalid base64 content"}

    # Compute hash if not provided
    if not content_hash:
        content_hash = hashlib.sha256(content).hexdigest()

    # Check for conflicts
    if client_version > 0 and await sync_service.detect_conflict(db, client.vault_id, path, client_version):
        return {
            "type": "conflict",
            "path": path,
            "server_version": (await sync_service.get_file_version(db, client.vault_id, path)).version
            if await sync_service.get_file_version(db, client.vault_id, path)
            else 0,
            "your_version": client_version,
        }

    # Store file
    storage = _get_vault_storage(client.vault_id)
    await storage.write(path, content, content_hash)

    # Create version record
    fv = await sync_service.create_file_version(
        db, client.vault_id, path, content_hash, len(content), client.user_id
    )

    # Record operation
    op_type = "update" if client_version > 0 else "create"
    await sync_service.record_sync_operation(
        db, client.vault_id, path, op_type, client.user_id
    )

    await db.commit()

    # Broadcast to other clients
    await manager.broadcast_to_vault(
        client.vault_id,
        {
            "type": "file_changed",
            "path": path,
            "version": fv.version,
            "content": content_b64,
            "author": client.username,
        },
        exclude_user_id=client.user_id,
    )

    return {
        "type": "file_changed",
        "path": path,
        "version": fv.version,
        "content_hash": content_hash,
    }


async def _handle_file_delete(
    client: ConnectedClient, data: dict, db: AsyncSession
) -> dict:
    path = data.get("path", "")
    if not path:
        return {"type": "error", "code": "BAD_REQUEST", "message": "Missing path"}

    # Delete from storage
    storage = _get_vault_storage(client.vault_id)
    if await storage.exists(path):
        await storage.delete(path)

    # Record operation
    op = await sync_service.record_sync_operation(
        db, client.vault_id, path, "delete", client.user_id
    )
    await db.commit()

    # Broadcast
    await manager.broadcast_to_vault(
        client.vault_id,
        {"type": "file_deleted", "path": path, "version": op.version, "author": client.username},
        exclude_user_id=client.user_id,
    )

    return {"type": "file_deleted", "path": path, "version": op.version}


async def _handle_file_rename(
    client: ConnectedClient, data: dict, db: AsyncSession
) -> dict:
    old_path = data.get("old_path", "")
    new_path = data.get("new_path", "")
    if not old_path or not new_path:
        return {"type": "error", "code": "BAD_REQUEST", "message": "Missing old_path or new_path"}

    storage = _get_vault_storage(client.vault_id)

    # Move file in storage
    if await storage.exists(old_path):
        content = await storage.read(old_path)
        await storage.write(new_path, content)
        await storage.delete(old_path)

    # Record operation
    op = await sync_service.record_sync_operation(
        db, client.vault_id, old_path, "rename", client.user_id,
        payload=json.dumps({"new_path": new_path}),
    )
    await db.commit()

    # Broadcast
    await manager.broadcast_to_vault(
        client.vault_id,
        {
            "type": "file_renamed",
            "old_path": old_path,
            "new_path": new_path,
            "version": op.version,
        },
        exclude_user_id=client.user_id,
    )

    return {"type": "file_renamed", "old_path": old_path, "new_path": new_path, "version": op.version}


async def _handle_pull(
    client: ConnectedClient, data: dict, db: AsyncSession
) -> dict:
    since_version = data.get("since_version", 0)
    operations = await sync_service.get_operations_since(db, client.vault_id, since_version)
    vault_version = await sync_service.get_vault_version(db, client.vault_id)

    return {
        "type": "sync_complete",
        "vault_version": vault_version,
        "operations": [
            {
                "type": op.operation_type,
                "path": op.file_path,
                "version": op.version,
                "payload": op.payload,
            }
            for op in operations
        ],
    }


async def _handle_ping(
    client: ConnectedClient, data: dict, db: AsyncSession
) -> dict:
    return {"type": "pong"}
