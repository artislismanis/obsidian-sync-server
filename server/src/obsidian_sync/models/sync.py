"""Sync models: file versions and sync operations."""

import enum

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from obsidian_sync.models.base import Base, UUIDMixin

from datetime import datetime


class OperationType(str, enum.Enum):
    create = "create"
    update = "update"
    delete = "delete"
    rename = "rename"


class FileVersion(UUIDMixin, Base):
    __tablename__ = "file_versions"
    __table_args__ = (
        UniqueConstraint("vault_id", "file_path", "version", name="uq_file_version"),
    )

    vault_id: Mapped[str] = mapped_column(
        ForeignKey("vaults.id", ondelete="CASCADE"), index=True
    )
    file_path: Mapped[str] = mapped_column(String(1024))
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64))  # SHA-256 hex
    size_bytes: Mapped[int] = mapped_column(Integer, default=0)
    author_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Relationships
    vault = relationship("Vault", foreign_keys=[vault_id])
    author = relationship("User", foreign_keys=[author_id])


class SyncOperation(UUIDMixin, Base):
    __tablename__ = "sync_operations"
    __table_args__ = (
        Index("ix_sync_operations_vault_version", "vault_id", "version"),
    )

    vault_id: Mapped[str] = mapped_column(
        ForeignKey("vaults.id", ondelete="CASCADE"), index=True
    )
    file_path: Mapped[str] = mapped_column(String(1024))
    operation_type: Mapped[str] = mapped_column(String(50))
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    author_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    payload: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Relationships
    vault = relationship("Vault", foreign_keys=[vault_id])
    author = relationship("User", foreign_keys=[author_id])
