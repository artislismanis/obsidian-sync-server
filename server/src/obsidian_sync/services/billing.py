"""Stripe billing service."""

import logging
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from obsidian_sync.config import settings
from obsidian_sync.models.billing import Subscription, SubscriptionStatus, SubscriptionTier
from obsidian_sync.models.user import User

logger = logging.getLogger(__name__)


def _get_stripe():  # type: ignore[no-untyped-def]
    """Lazy import stripe to avoid dependency in self-hosted mode."""
    try:
        import stripe
        stripe.api_key = settings.stripe_secret_key
        return stripe
    except ImportError:
        raise RuntimeError("Stripe not installed. Run: pip install stripe")


async def create_checkout_session(
    db: AsyncSession, user_id: str, tier: str, success_url: str, cancel_url: str
) -> str:
    """Create a Stripe Checkout session. Returns the session URL."""
    stripe = _get_stripe()

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one()

    # Get or create Stripe customer
    if not user.stripe_customer_id:
        customer = stripe.Customer.create(
            email=user.email,
            metadata={"user_id": user_id},
        )
        user.stripe_customer_id = customer.id
        await db.flush()

    # Map tier to price ID (configured via env vars in production)
    price_map = {
        "pro": settings.stripe_secret_key and "price_pro_placeholder",
        "team": settings.stripe_secret_key and "price_team_placeholder",
    }

    session = stripe.checkout.Session.create(
        customer=user.stripe_customer_id,
        mode="subscription",
        line_items=[{"price": price_map.get(tier, ""), "quantity": 1}],
        success_url=success_url,
        cancel_url=cancel_url,
    )
    return session.url


async def create_portal_session(db: AsyncSession, user_id: str, return_url: str) -> str:
    """Create a Stripe Customer Portal session. Returns the session URL."""
    stripe = _get_stripe()

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one()

    if not user.stripe_customer_id:
        raise ValueError("No Stripe customer for this user")

    session = stripe.billing_portal.Session.create(
        customer=user.stripe_customer_id,
        return_url=return_url,
    )
    return session.url


async def handle_webhook_event(db: AsyncSession, event_type: str, data: dict) -> None:
    """Process a Stripe webhook event."""
    if event_type == "customer.subscription.created":
        await _handle_subscription_update(db, data)
    elif event_type == "customer.subscription.updated":
        await _handle_subscription_update(db, data)
    elif event_type == "customer.subscription.deleted":
        await _handle_subscription_deleted(db, data)
    elif event_type == "invoice.payment_failed":
        await _handle_payment_failed(db, data)
    else:
        logger.debug(f"Unhandled webhook event: {event_type}")


async def _handle_subscription_update(db: AsyncSession, data: dict) -> None:
    stripe_sub = data.get("object", {})
    stripe_sub_id = stripe_sub.get("id")
    customer_id = stripe_sub.get("customer")
    status = stripe_sub.get("status", "active")

    # Find user by Stripe customer ID
    result = await db.execute(
        select(User).where(User.stripe_customer_id == customer_id)
    )
    user = result.scalar_one_or_none()
    if not user:
        logger.warning(f"No user for Stripe customer {customer_id}")
        return

    # Determine tier from price
    items = stripe_sub.get("items", {}).get("data", [])
    tier = SubscriptionTier.free.value
    for item in items:
        price_id = item.get("price", {}).get("id", "")
        if "team" in price_id:
            tier = SubscriptionTier.team.value
        elif "pro" in price_id:
            tier = SubscriptionTier.pro.value

    # Storage limits by tier
    storage_map = {
        SubscriptionTier.free.value: 1 * 1024**3,
        SubscriptionTier.pro.value: 5 * 1024**3,
        SubscriptionTier.team.value: 10 * 1024**3,
    }

    # Upsert subscription
    sub_result = await db.execute(
        select(Subscription).where(Subscription.user_id == user.id)
    )
    sub = sub_result.scalar_one_or_none()

    if sub:
        sub.stripe_subscription_id = stripe_sub_id
        sub.tier = tier
        sub.status = _map_status(status)
        sub.max_storage_bytes = storage_map.get(tier, 1 * 1024**3)
        if stripe_sub.get("current_period_end"):
            sub.current_period_end = datetime.fromtimestamp(
                stripe_sub["current_period_end"], tz=timezone.utc
            )
    else:
        sub = Subscription(
            user_id=user.id,
            stripe_subscription_id=stripe_sub_id,
            tier=tier,
            status=_map_status(status),
            max_storage_bytes=storage_map.get(tier, 1 * 1024**3),
        )
        db.add(sub)

    await db.flush()


async def _handle_subscription_deleted(db: AsyncSession, data: dict) -> None:
    stripe_sub = data.get("object", {})
    customer_id = stripe_sub.get("customer")

    result = await db.execute(
        select(User).where(User.stripe_customer_id == customer_id)
    )
    user = result.scalar_one_or_none()
    if not user:
        return

    sub_result = await db.execute(
        select(Subscription).where(Subscription.user_id == user.id)
    )
    sub = sub_result.scalar_one_or_none()
    if sub:
        sub.status = SubscriptionStatus.cancelled.value
        sub.tier = SubscriptionTier.free.value
        await db.flush()


async def _handle_payment_failed(db: AsyncSession, data: dict) -> None:
    invoice = data.get("object", {})
    customer_id = invoice.get("customer")

    result = await db.execute(
        select(User).where(User.stripe_customer_id == customer_id)
    )
    user = result.scalar_one_or_none()
    if not user:
        return

    sub_result = await db.execute(
        select(Subscription).where(Subscription.user_id == user.id)
    )
    sub = sub_result.scalar_one_or_none()
    if sub:
        sub.status = SubscriptionStatus.past_due.value
        await db.flush()


def _map_status(stripe_status: str) -> str:
    mapping = {
        "active": SubscriptionStatus.active.value,
        "past_due": SubscriptionStatus.past_due.value,
        "canceled": SubscriptionStatus.cancelled.value,
        "unpaid": SubscriptionStatus.suspended.value,
    }
    return mapping.get(stripe_status, SubscriptionStatus.active.value)
