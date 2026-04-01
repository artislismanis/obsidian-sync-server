"""WebSocket sync handler — manages connections and routes messages."""

import logging
from dataclasses import dataclass

from fastapi import WebSocket

logger = logging.getLogger(__name__)


@dataclass
class ConnectedClient:
    websocket: WebSocket
    user_id: str
    vault_id: str
    username: str


class ConnectionManager:
    """Manages WebSocket connections grouped by vault."""

    def __init__(self) -> None:
        # vault_id -> list of connected clients
        self._connections: dict[str, list[ConnectedClient]] = {}

    async def connect(
        self, websocket: WebSocket, user_id: str, vault_id: str, username: str
    ) -> ConnectedClient:
        await websocket.accept()
        client = ConnectedClient(
            websocket=websocket, user_id=user_id, vault_id=vault_id, username=username
        )
        if vault_id not in self._connections:
            self._connections[vault_id] = []
        self._connections[vault_id].append(client)
        logger.info(f"Client {username} connected to vault {vault_id}")
        return client

    def disconnect(self, client: ConnectedClient) -> None:
        vault_conns = self._connections.get(client.vault_id, [])
        if client in vault_conns:
            vault_conns.remove(client)
        if not vault_conns:
            self._connections.pop(client.vault_id, None)
        logger.info(f"Client {client.username} disconnected from vault {client.vault_id}")

    async def broadcast_to_vault(
        self, vault_id: str, message: dict, exclude_user_id: str | None = None
    ) -> None:
        """Send a message to all clients connected to a vault, optionally excluding one."""
        for client in self._connections.get(vault_id, []):
            if client.user_id == exclude_user_id:
                continue
            try:
                await client.websocket.send_json(message)
            except Exception:
                logger.warning(f"Failed to send to client {client.username}")

    def get_vault_clients(self, vault_id: str) -> list[ConnectedClient]:
        return list(self._connections.get(vault_id, []))

    def get_connected_count(self) -> int:
        return sum(len(clients) for clients in self._connections.values())


# Singleton
manager = ConnectionManager()
