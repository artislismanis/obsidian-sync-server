"""Yjs document manager — in-memory placeholder for live sync.

Manages Yjs document states per vault+file. This is a placeholder
implementation using simple byte concatenation. Production will use
pycrdt for proper CRDT merging.
"""

import logging

logger = logging.getLogger(__name__)


class YjsDocumentManager:
    """Manages in-memory Yjs document states keyed by (vault_id, file_path)."""

    def __init__(self) -> None:
        # (vault_id, file_path) -> accumulated update bytes
        self._states: dict[tuple[str, str], bytes] = {}

    def store_update(
        self, vault_id: str, file_path: str, update_bytes: bytes
    ) -> None:
        """Store a Yjs update for a vault file.

        In the placeholder implementation updates are concatenated.
        Production will apply them to a pycrdt Y.Doc.
        """
        key = (vault_id, file_path)
        existing = self._states.get(key, b"")
        self._states[key] = existing + update_bytes
        logger.debug(
            "Stored Yjs update for %s/%s (%d bytes)",
            vault_id,
            file_path,
            len(update_bytes),
        )

    def get_state(self, vault_id: str, file_path: str) -> bytes | None:
        """Return the current accumulated state for a vault file, or None."""
        return self._states.get((vault_id, file_path))

    def clear(self, vault_id: str, file_path: str) -> None:
        """Remove stored state for a vault file."""
        self._states.pop((vault_id, file_path), None)

    def clear_vault(self, vault_id: str) -> None:
        """Remove all stored states for a vault."""
        keys_to_remove = [k for k in self._states if k[0] == vault_id]
        for key in keys_to_remove:
            del self._states[key]


# Singleton instance
yjs_manager = YjsDocumentManager()
