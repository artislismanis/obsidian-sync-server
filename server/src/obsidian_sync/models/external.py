"""External sync configuration model."""

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from obsidian_sync.models.base import Base, TimestampMixin, UUIDMixin


class ExternalSyncConfig(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "external_sync_configs"

    vault_id: Mapped[str] = mapped_column(
        ForeignKey("vaults.id", ondelete="CASCADE"), index=True, unique=True
    )
    provider: Mapped[str] = mapped_column(String(50))  # google_drive, onedrive
    mode: Mapped[str] = mapped_column(String(50))  # mirror, bidirectional
    oauth_token_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)
    remote_folder_id: Mapped[str | None] = mapped_column(String(512), nullable=True)
    last_sync_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    change_token: Mapped[str | None] = mapped_column(String(1024), nullable=True)

    # Relationships
    vault = relationship("Vault", foreign_keys=[vault_id])
