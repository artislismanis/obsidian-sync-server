"""Billing router: Stripe checkout, portal, webhooks. Only active in SaaS mode."""

import json

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from obsidian_sync.config import settings
from obsidian_sync.database import get_db
from obsidian_sync.middleware.auth import get_current_user
from obsidian_sync.models.user import User
from obsidian_sync.services import billing as billing_service
from obsidian_sync.services.entitlement import get_user_entitlements

router = APIRouter(prefix="/api/v1/billing", tags=["billing"])


def _require_saas() -> None:
    if settings.deployment_mode != "saas" or not settings.stripe_secret_key:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Billing not available")


@router.get("/subscription")
async def get_subscription(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    _require_saas()
    entitlements = await get_user_entitlements(db, current_user.id)
    return {
        "user_id": current_user.id,
        "entitlements": {
            "max_vaults": entitlements.max_vaults,
            "max_storage_bytes": entitlements.max_storage_bytes,
            "live_sync": entitlements.live_sync,
            "file_history": entitlements.file_history,
            "vault_sharing": entitlements.vault_sharing,
            "external_sync": entitlements.external_sync,
        },
    }


@router.post("/checkout")
async def create_checkout(
    body: dict,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    _require_saas()
    tier = body.get("tier", "pro")
    success_url = body.get("success_url", f"{settings.stripe_secret_key}/billing?success=true")
    cancel_url = body.get("cancel_url", f"{settings.stripe_secret_key}/billing?cancelled=true")

    url = await billing_service.create_checkout_session(
        db, current_user.id, tier, success_url, cancel_url
    )
    return {"checkout_url": url}


@router.post("/portal")
async def create_portal(
    body: dict,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    _require_saas()
    return_url = body.get("return_url", "/billing")
    url = await billing_service.create_portal_session(db, current_user.id, return_url)
    return {"portal_url": url}


@router.post("/webhooks")
async def stripe_webhook(request: Request, db: AsyncSession = Depends(get_db)) -> dict:
    """Handle Stripe webhook events."""
    _require_saas()

    payload = await request.body()
    sig_header = request.headers.get("stripe-signature", "")

    try:
        import stripe
        stripe.api_key = settings.stripe_secret_key
        event = stripe.Webhook.construct_event(
            payload, sig_header, settings.stripe_webhook_secret
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Webhook error: {e}")

    await billing_service.handle_webhook_event(db, event["type"], event["data"])
    return {"received": True}
