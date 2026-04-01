"""Share link model for vault/file sharing."""

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from obsidian_sync.models.base import Base, UUIDMixin


class ShareLink(UUIDMixin, Base):
    __tablename__ = "share_links"

    vault_id: Mapped[str] = mapped_column(
        ForeignKey("vaults.id", ondelete="CASCADE"), index=True
    )
    file_path: Mapped[str | None] = mapped_column(
        String(1024), nullable=True
    )  # null = whole vault
    token: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    created_by: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    permissions: Mapped[str] = mapped_column(
        String(50), default="view"
    )  # "view" or "download"
    password_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    access_count: Mapped[int] = mapped_column(Integer, default=0)
    max_access_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    revoked: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Relationships
    vault = relationship("Vault", foreign_keys=[vault_id])
    creator = relationship("User", foreign_keys=[created_by])
