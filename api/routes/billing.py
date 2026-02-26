"""
POST /api/billing/refresh

Force-sync subscription state from the Stripe API and recompute entitlements.

Prevents "I paid but still locked" support tickets caused by webhook delivery
delays or race conditions. Backend queries Stripe directly — never trusts client.

GET /api/billing/entitlements

Returns the current user's active entitlements (flags + limits) for
informational / debugging purposes. The frontend may use this to render
upgrade prompts, but must never rely on it for access control decisions.
"""

import os
import stripe
import logging
from datetime import datetime, timezone, timedelta

from fastapi import APIRouter, HTTPException, Depends
from prisma import Prisma

from api.dependencies import get_current_user
from api.lib.db import get_db
from api.lib.entitlement_config import GRACE_PERIOD_DAYS
from api.lib.entitlement_middleware import load_entitlements
from api.lib.entitlement_resolver import EntitlementContext, persist_entitlements
from api.models.auth import User

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/billing", tags=["Billing"])

stripe.api_key = os.getenv("STRIPE_SECRET_KEY")

# Price → tier mapping (duplicated from stripe.py to avoid circular imports)
_PRICE_TO_TIER: dict = {
    os.getenv("STRIPE_STARTER_PRICE_ID"):  "starter",
    os.getenv("STRIPE_INVESTOR_PRICE_ID"): "investor",
    os.getenv("STRIPE_TRADER_PRICE_ID"):   "trader",
}
_TIER_RANK: dict = {"starter": 0, "investor": 1, "trader": 2}


# ── GET /billing/entitlements ─────────────────────────────────────────────────

@router.get("/entitlements")
async def get_entitlements(
    ctx: EntitlementContext = Depends(load_entitlements),
):
    """
    Return the current user's computed entitlements.

    Informational endpoint — safe to expose to the frontend for rendering
    upgrade prompts. Access control decisions are always made server-side.
    """
    return {
        "user_id":             ctx.user_id,
        "tier":                ctx.tier,
        "flags":               ctx.flags,
        "limits":              ctx.limits,
        "subscription_status": ctx.subscription_status,
        "is_admin":            ctx.is_admin,
        "version":             ctx.version,
    }


# ── POST /billing/refresh ─────────────────────────────────────────────────────

@router.post("/refresh")
async def billing_refresh(
    current_user: User = Depends(get_current_user),
    db: Prisma = Depends(get_db),
):
    """
    Force-sync subscription state from Stripe and recompute entitlements.

    Steps:
      1. Query Stripe API for all subscriptions on the customer.
      2. Pick the highest-tier active/trialing/past_due subscription.
      3. Update the User row with current subscription fields.
      4. Recompute and persist Entitlement row.
      5. Return the resolved tier, flags, and limits.

    Use this when a user reports being locked out after a successful payment.
    """
    user_db = await db.user.find_unique(where={"id": current_user.id})
    if not user_db:
        raise HTTPException(404, "User not found")

    # No Stripe customer → nothing to sync
    if not user_db.stripeCustomerId:
        ctx = await persist_entitlements(user_db, db)
        return {
            "status": "no_stripe_customer",
            "tier":   ctx.tier,
            "flags":  ctx.flags,
            "limits": ctx.limits,
        }

    # Query Stripe
    try:
        subscriptions = stripe.Subscription.list(
            customer=user_db.stripeCustomerId,
            status="all",
            limit=10,
            expand=["data.items.data.price"],
        )
    except stripe.error.StripeError as e:
        logger.error("Stripe API error during billing/refresh for %s: %s", current_user.id, e)
        raise HTTPException(502, "Could not reach Stripe. Try again shortly.")

    # Pick highest-tier eligible subscription
    best_sub = None
    best_rank = -1

    for sub in subscriptions.data:
        if sub.status not in ("active", "trialing", "past_due"):
            continue
        price_id = sub["items"]["data"][0]["price"]["id"]
        tier = _PRICE_TO_TIER.get(price_id, "starter")
        rank = _TIER_RANK.get(tier, 0)
        if rank > best_rank:
            best_sub = sub
            best_rank = rank

    if best_sub is None:
        # No eligible subscription — downgrade paid users gracefully.
        # Free users (never subscribed) must NOT have their tier changed.
        current_tier = user_db.tier if hasattr(user_db, "tier") else "free"
        downgrade_tier = "free" if current_tier == "free" else "starter"
        await db.user.update(
            where={"id": current_user.id},
            data={
                "tier":                    downgrade_tier,
                "stripeSubscriptionStatus": "canceled",
                "isActive":                True,
            },
        )
        user_db = await db.user.find_unique(where={"id": current_user.id})
        ctx = await persist_entitlements(user_db, db)
        return {
            "status": "no_active_subscription",
            "tier":   ctx.tier,
            "flags":  ctx.flags,
            "limits": ctx.limits,
        }

    # Sync user with the best subscription
    price_id         = best_sub["items"]["data"][0]["price"]["id"]
    tier             = _PRICE_TO_TIER.get(price_id, "starter")
    status           = best_sub.status
    period_start     = datetime.fromtimestamp(best_sub.current_period_start, tz=timezone.utc)
    period_end       = datetime.fromtimestamp(best_sub.current_period_end, tz=timezone.utc)
    cancel_at_end    = bool(best_sub.cancel_at_period_end)

    # Grace window: set on past_due, clear otherwise
    grace_until = None
    if status == "past_due":
        grace_until = datetime.now(timezone.utc) + timedelta(days=GRACE_PERIOD_DAYS)

    update_data: dict = {
        "tier":                    tier,
        "stripeSubscriptionId":    best_sub.id,
        "stripeSubscriptionStatus": status,
        "stripePriceId":           price_id,
        "subscriptionEndDate":     period_end,
        "billingPeriodStart":      period_start,
        "billingPeriodEnd":        period_end,
        "cancelAtPeriodEnd":       cancel_at_end,
        "isActive":                status in ("active", "trialing"),
    }
    if grace_until:
        update_data["graceUntil"] = grace_until
    else:
        update_data["graceUntil"] = None  # clear stale grace window

    await db.user.update(where={"id": current_user.id}, data=update_data)

    user_db = await db.user.find_unique(where={"id": current_user.id})
    ctx = await persist_entitlements(user_db, db)

    logger.info(
        "billing_refresh | user=%s tier=%s status=%s cancel_at_end=%s",
        current_user.id, ctx.tier, status, cancel_at_end,
    )

    return {
        "status":               "synced",
        "stripe_status":        status,
        "tier":                 ctx.tier,
        "cancel_at_period_end": cancel_at_end,
        "period_end":           period_end.isoformat(),
        "flags":                ctx.flags,
        "limits":               ctx.limits,
        "version":              ctx.version,
    }
