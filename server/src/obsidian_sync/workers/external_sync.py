"""External sync worker: mirrors or bidirectionally syncs vault data with external connectors."""

import hashlib
import logging
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from obsidian_sync.connectors.base import SyncConnector
from obsidian_sync.models.external import ExternalSyncConfig
from obsidian_sync.models.sync import SyncOperation
from obsidian_sync.services.storage_factory import get_local_vault_storage

logger = logging.getLogger(__name__)


class ExternalSyncWorker:
    """Synchronises a vault with an external connector (Google Drive, OneDrive, etc.).

    Supports two modes:
    - mirror: pushes local changes to the remote connector.
    - bidirectional: also pulls remote changes into the vault.
    """

    def __init__(
        self,
        vault_id: str,
        connector: SyncConnector,
        mode: str = "mirror",
    ) -> None:
        self.vault_id = vault_id
        self.connector = connector
        self.mode = mode

    async def run_once(self, db: AsyncSession) -> None:
        """Execute a single sync cycle."""
        # Load config to get last_sync version and change_token
        result = await db.execute(
            select(ExternalSyncConfig).where(
                ExternalSyncConfig.vault_id == self.vault_id
            )
        )
        config = result.scalar_one_or_none()
        if config is None:
            logger.warning(
                "No ExternalSyncConfig found for vault %s, skipping.",
                self.vault_id,
            )
            return

        if not config.enabled:
            logger.info(
                "External sync disabled for vault %s, skipping.",
                self.vault_id,
            )
            return

        try:
            await self._push_local_changes(db, config)

            if self.mode == "bidirectional":
                await self._pull_remote_changes(db, config)

            # Mark success
            config.last_sync_at = datetime.now(timezone.utc)
            config.last_error = None
            await db.flush()

        except Exception as exc:
            logger.error(
                "External sync error for vault %s: %s",
                self.vault_id,
                exc,
                exc_info=True,
            )
            config.last_error = str(exc)
            await db.flush()

    async def _push_local_changes(
        self, db: AsyncSession, config: ExternalSyncConfig
    ) -> None:
        """Push new local SyncOperations to the external connector."""
        # Determine the version we last synced up to.
        # We use last_sync_at to find operations created after the last sync.
        query = (
            select(SyncOperation)
            .where(SyncOperation.vault_id == self.vault_id)
            .order_by(SyncOperation.version)
        )
        if config.last_sync_at is not None:
            query = query.where(SyncOperation.created_at > config.last_sync_at)

        result = await db.execute(query)
        operations = list(result.scalars().all())

        if not operations:
            logger.debug("No new local operations for vault %s.", self.vault_id)
            return

        storage = get_local_vault_storage(self.vault_id)

        for op in operations:
            try:
                if op.operation_type in ("create", "update"):
                    try:
                        content = await storage.read(op.file_path)
                    except (FileNotFoundError, OSError):
                        logger.warning(
                            "File %s not found in local storage, skipping push.",
                            op.file_path,
                        )
                        continue
                    await self.connector.push_file(op.file_path, content)
                    logger.info(
                        "Pushed %s to external for vault %s.",
                        op.file_path,
                        self.vault_id,
                    )
                elif op.operation_type == "delete":
                    try:
                        await self.connector.delete_file(op.file_path)
                    except Exception as del_err:
                        logger.warning(
                            "Failed to delete %s on external: %s",
                            op.file_path,
                            del_err,
                        )
                    logger.info(
                        "Deleted %s on external for vault %s.",
                        op.file_path,
                        self.vault_id,
                    )
            except Exception as push_err:
                logger.error(
                    "Error pushing %s (op %s) for vault %s: %s",
                    op.file_path,
                    op.operation_type,
                    self.vault_id,
                    push_err,
                )
                # Continue with remaining operations

    async def _pull_remote_changes(
        self, db: AsyncSession, config: ExternalSyncConfig
    ) -> None:
        """Pull changes from the external connector into the vault (bidirectional mode)."""
        change_token = config.change_token or ""
        changed_files, new_token = await self.connector.get_changes_since(change_token)

        config.change_token = new_token

        if not changed_files:
            logger.debug("No remote changes for vault %s.", self.vault_id)
            return

        storage = get_local_vault_storage(self.vault_id)

        for remote_file in changed_files:
            try:
                content = await self.connector.pull_file(remote_file.path)
                content_hash = hashlib.sha256(content).hexdigest()

                # Write to local storage
                await storage.write(
                    remote_file.path, content, content_hash=content_hash
                )

                # Record as a sync operation so other clients see the change
                from obsidian_sync.services.sync import (
                    create_file_version,
                    get_file_version,
                    record_sync_operation,
                )

                existing = await get_file_version(
                    db, self.vault_id, remote_file.path
                )
                op_type = "update" if existing else "create"

                # Use a sentinel author_id for external sync
                author_id = "external-sync"

                await create_file_version(
                    db,
                    vault_id=self.vault_id,
                    path=remote_file.path,
                    content_hash=content_hash,
                    size_bytes=len(content),
                    author_id=author_id,
                )
                await record_sync_operation(
                    db,
                    vault_id=self.vault_id,
                    path=remote_file.path,
                    op_type=op_type,
                    author_id=author_id,
                )
                logger.info(
                    "Pulled %s from external for vault %s.",
                    remote_file.path,
                    self.vault_id,
                )
            except Exception as pull_err:
                logger.error(
                    "Error pulling %s for vault %s: %s",
                    remote_file.path,
                    self.vault_id,
                    pull_err,
                )
                # Continue with remaining files
