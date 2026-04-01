"""Billing and subscription models."""

import enum
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, BigInteger
from sqlalchemy.orm import Mapped, mapped_column, relationship

from obsidian_sync.models.base import Base, TimestampMixin, UUIDMixin


class SubscriptionTier(str, enum.Enum):
    free = "free"
    pro = "pro"
    team = "team"


class SubscriptionStatus(str, enum.Enum):
    active = "active"
    past_due = "past_due"
    cancelled = "cancelled"
    suspended = "suspended"


class Subscription(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "subscriptions"

    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), unique=True, index=True
    )
    stripe_subscription_id: Mapped[str | None] = mapped_column(
        String(255), nullable=True
    )
    tier: Mapped[str] = mapped_column(String(50), default=SubscriptionTier.free.value)
    status: Mapped[str] = mapped_column(
        String(50), default=SubscriptionStatus.active.value
    )
    max_storage_bytes: Mapped[int] = mapped_column(
        BigInteger, default=1 * 1024 * 1024 * 1024  # 1GB free tier
    )
    current_period_end: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    user = relationship("User", foreign_keys=[user_id])
