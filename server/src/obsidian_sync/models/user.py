"""User and authentication models."""

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from obsidian_sync.models.base import Base, TimestampMixin, UUIDMixin


class User(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "users"

    username: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    email: Mapped[str | None] = mapped_column(String(255), unique=True, nullable=True)
    password_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_superadmin: Mapped[bool] = mapped_column(Boolean, default=False)

    # OAuth
    oauth_provider: Mapped[str | None] = mapped_column(
        String(50), nullable=True
    )  # google, github
    oauth_id: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Stripe (SaaS mode)
    stripe_customer_id: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # GDPR
    gdpr_consent_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    deletion_requested_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    last_login: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Relationships
    refresh_tokens: Mapped[list["RefreshToken"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )

    @property
    def has_password(self) -> bool:
        return self.password_hash is not None


class RefreshToken(UUIDMixin, Base):
    __tablename__ = "refresh_tokens"

    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    token_hash: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    revoked: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # Relationships
    user: Mapped[User] = relationship(back_populates="refresh_tokens")


class APIKey(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "api_keys"

    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(255))
    key_hash: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    prefix: Mapped[str] = mapped_column(
        String(8)
    )  # First 8 chars for identification
    last_used_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    revoked: Mapped[bool] = mapped_column(Boolean, default=False)

    user: Mapped[User] = relationship()
