"""Entitlement engine: maps subscription tier to feature flags and limits."""

from dataclasses import dataclass
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from obsidian_sync.config import settings
from obsidian_sync.models.billing import Subscription, SubscriptionTier


@dataclass
class Entitlements:
    max_vaults: int | None  # None = unlimited
    max_storage_bytes: int | None
    live_sync: bool
    file_history: bool
    vault_sharing: bool
    external_sync: bool
    max_share_links: int | None

    @classmethod
    def unlimited(cls) -> "Entitlements":
        return cls(
            max_vaults=None,
            max_storage_bytes=None,
            live_sync=True,
            file_history=True,
            vault_sharing=True,
            external_sync=True,
            max_share_links=None,
        )

    @classmethod
    def for_tier(cls, tier: str) -> "Entitlements":
        if tier == SubscriptionTier.team.value:
            return cls(
                max_vaults=None,
                max_storage_bytes=10 * 1024 * 1024 * 1024,  # 10GB
                live_sync=True,
                file_history=True,
                vault_sharing=True,
                external_sync=True,
                max_share_links=None,
            )
        elif tier == SubscriptionTier.pro.value:
            return cls(
                max_vaults=None,
                max_storage_bytes=5 * 1024 * 1024 * 1024,  # 5GB
                live_sync=True,
                file_history=True,
                vault_sharing=False,
                external_sync=True,
                max_share_links=50,
            )
        else:  # free
            return cls(
                max_vaults=1,
                max_storage_bytes=1 * 1024 * 1024 * 1024,  # 1GB
                live_sync=False,
                file_history=False,
                vault_sharing=False,
                external_sync=False,
                max_share_links=5,
            )


async def get_user_entitlements(db: AsyncSession, user_id: str) -> Entitlements:
    """Get the entitlements for a user based on their subscription."""
    if settings.deployment_mode == "self_hosted":
        return Entitlements.unlimited()

    result = await db.execute(
        select(Subscription).where(Subscription.user_id == user_id)
    )
    sub = result.scalar_one_or_none()

    if sub is None:
        return Entitlements.for_tier(SubscriptionTier.free.value)

    if sub.status in ("cancelled", "suspended"):
        return Entitlements.for_tier(SubscriptionTier.free.value)

    return Entitlements.for_tier(sub.tier)
