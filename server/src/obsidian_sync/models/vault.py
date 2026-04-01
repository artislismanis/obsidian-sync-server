"""Vault and access control models."""

from sqlalchemy import Boolean, Enum, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from obsidian_sync.models.base import Base, TimestampMixin, UUIDMixin

import enum
from datetime import datetime


class VaultRole(str, enum.Enum):
    owner = "owner"
    admin = "admin"
    write = "write"
    read = "read"


class SyncMode(str, enum.Enum):
    on_save = "on_save"
    live = "live"
    both = "both"


class ObsidianConfigSync(str, enum.Enum):
    all = "all"
    settings_only = "settings_only"
    none = "none"


class StorageBackendType(str, enum.Enum):
    local = "local"
    s3 = "s3"


class Vault(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "vaults"

    name: Mapped[str] = mapped_column(String(255))
    owner_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )

    # Storage
    storage_backend: Mapped[str] = mapped_column(
        String(50), default=StorageBackendType.local.value
    )
    storage_config: Mapped[str | None] = mapped_column(
        Text, nullable=True
    )  # JSON, encrypted credentials

    # Encryption
    encrypted: Mapped[bool] = mapped_column(Boolean, default=False)
    encryption_salt: Mapped[str | None] = mapped_column(String(255), nullable=True)
    encryption_key_hash: Mapped[str | None] = mapped_column(
        String(255), nullable=True
    )

    # Sync settings
    sync_mode: Mapped[str] = mapped_column(
        String(50), default=SyncMode.on_save.value
    )
    obsidian_config_sync: Mapped[str] = mapped_column(
        String(50), default=ObsidianConfigSync.settings_only.value
    )

    # Retention
    retention_policy: Mapped[str | None] = mapped_column(
        Text, nullable=True
    )  # JSON: {"type": "count"|"days", "value": int}

    # Soft delete
    archived_at: Mapped[datetime | None] = mapped_column(nullable=True)

    # Relationships
    owner = relationship("User", foreign_keys=[owner_id])
    access_list: Mapped[list["VaultAccess"]] = relationship(
        back_populates="vault", cascade="all, delete-orphan"
    )


class VaultAccess(Base):
    __tablename__ = "vault_access"

    vault_id: Mapped[str] = mapped_column(
        ForeignKey("vaults.id", ondelete="CASCADE"), primary_key=True
    )
    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    role: Mapped[str] = mapped_column(String(50))
    granted_at: Mapped[datetime] = mapped_column(
        server_default=func.now()
    )
    granted_by: Mapped[str | None] = mapped_column(
        ForeignKey("users.id"), nullable=True
    )

    # Relationships
    vault: Mapped[Vault] = relationship(back_populates="access_list")
    user = relationship("User", foreign_keys=[user_id])
