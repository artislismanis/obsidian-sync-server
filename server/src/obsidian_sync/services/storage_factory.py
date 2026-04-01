"""Storage backend factory — returns the appropriate backend for a vault."""

import json

from obsidian_sync.config import settings
from obsidian_sync.storage.base import StorageBackend
from obsidian_sync.storage.local import LocalStorage
from obsidian_sync.storage.s3 import S3Storage


def get_storage_backend(vault: object) -> StorageBackend:  # type: ignore[return]
    """Return a StorageBackend instance based on the vault's storage_backend field.

    Args:
        vault: A Vault model instance (or any object with storage_backend,
               storage_config, and id attributes).

    Returns:
        A LocalStorage or S3Storage instance.

    Raises:
        ValueError: If the storage_backend type is unsupported.
    """
    backend_type: str = getattr(vault, "storage_backend", "local")

    if backend_type == "local":
        vault_id: str = getattr(vault, "id", "")
        root = f"{settings.storage_local_path}/{vault_id}/current"
        return LocalStorage(root)

    if backend_type == "s3":
        config_raw: str | None = getattr(vault, "storage_config", None)
        if not config_raw:
            raise ValueError("S3 storage backend requires storage_config")
        config: dict = json.loads(config_raw)
        return S3Storage(
            bucket=config["bucket"],
            prefix=config.get("prefix", ""),
            region=config.get("region", "us-east-1"),
            aws_access_key_id=config.get("aws_access_key_id"),
            aws_secret_access_key=config.get("aws_secret_access_key"),
        )

    raise ValueError(f"Unsupported storage backend: {backend_type}")


def get_local_vault_storage(vault_id: str) -> LocalStorage:
    """Shortcut: get a LocalStorage instance for a vault by ID.

    Used when the vault object isn't available (e.g., WebSocket handlers).
    For production, prefer get_storage_backend(vault) which respects the vault's
    configured storage type.
    """
    return LocalStorage(f"{settings.storage_local_path}/{vault_id}/current")
