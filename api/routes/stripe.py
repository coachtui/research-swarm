"""
Stripe subscription and payment routes.

Handles checkout sessions, boost purchases, customer portal, and webhook events.
"""

import os
import stripe
from fastapi import APIRouter, HTTPException, Request, Depends
from fastapi.responses import JSONResponse
from datetime import datetime, timezone
from typing import Dict, Any

from api.dependencies import get_current_user
from api.lib.db import get_db
from api.models.auth import User
from api.services.quota_service import check_boost_eligibility, add_boost_analyses, get_or_create_current_quota
from prisma import Prisma

router = APIRouter(prefix="/stripe", tags=["stripe"])

# Initialize Stripe
stripe.api_key = os.getenv("STRIPE_SECRET_KEY")
STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET")

# Price IDs for subscription tiers
STARTER_PRICE_ID = os.getenv("STRIPE_STARTER_PRICE_ID")
INVESTOR_PRICE_ID = os.getenv("STRIPE_INVESTOR_PRICE_ID")
TRADER_PRICE_ID = os.getenv("STRIPE_TRADER_PRICE_ID")
BOOST_PRICE_ID = os.getenv("STRIPE_BOOST_PRICE_ID")

SUBSCRIPTION_PRICE_IDS = {STARTER_PRICE_ID, INVESTOR_PRICE_ID, TRADER_PRICE_ID}

PRICE_TO_TIER = {
    STARTER_PRICE_ID: "starter",
    INVESTOR_PRICE_ID: "investor",
    TRADER_PRICE_ID: "trader",
}

FRONTEND_URL = os.getenv("NEXT_PUBLIC_API_URL", "http://localhost:3000")


@router.post("/create-checkout-session")
async def create_checkout_session(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Prisma = Depends(get_db)
):
    """
    Create a Stripe Checkout session for a subscription plan.

    **Request body**:
    - price_id: Stripe price ID (starter, investor, or trader)

    **Returns**: Checkout session URL
    """
    body = await request.json()
    price_id = body.get("price_id")

    if not price_id:
        raise HTTPException(400, "price_id is required")

    if price_id not in SUBSCRIPTION_PRICE_IDS:
        raise HTTPException(400, "Invalid price_id — use a subscription price ID, not a boost price ID")

    try:
        user_db = await db.user.find_unique(where={"id": current_user.id})

        if user_db.stripeCustomerId:
            customer_id = user_db.stripeCustomerId
        else:
            customer = stripe.Customer.create(
                email=current_user.email,
                metadata={
                    "user_id": current_user.id,
                    "clerk_id": current_user.clerk_id
                }
            )
            customer_id = customer.id
            await db.user.update(
                where={"id": current_user.id},
                data={"stripeCustomerId": customer_id}
            )

        checkout_session = stripe.checkout.Session.create(
            customer=customer_id,
            mode="subscription",
            payment_method_types=["card"],
            line_items=[{"price": price_id, "quantity": 1}],
            success_url=f"{FRONTEND_URL}/dashboard?success=true",
            cancel_url=f"{FRONTEND_URL}/dashboard?canceled=true",
            metadata={"user_id": current_user.id}
        )

        return {"checkout_url": checkout_session.url}

    except stripe.error.StripeError as e:
        raise HTTPException(500, f"Stripe error: {str(e)}")
    except Exception as e:
        raise HTTPException(500, f"Error creating checkout session: {str(e)}")


@router.post("/create-boost-session")
async def create_boost_session(
    current_user: User = Depends(get_current_user),
    db: Prisma = Depends(get_db)
):
    """
    Create a Stripe Checkout session for a one-time Boost purchase.

    Only available to active paid subscribers who have used at least 1 analysis.

    **Returns**:
    - checkout_url: Stripe Checkout URL
    - warn_expiry: True if billing period ends in <7 days
    - days_remaining: Days left in current billing period
    """
    # Fetch user with subscription status
    user_db = await db.user.find_unique(where={"id": current_user.id})
    stripe_status = user_db.stripeSubscriptionStatus or ""

    # Check eligibility
    eligible = await check_boost_eligibility(current_user.id, stripe_status, current_user.tier)
    if not eligible:
        raise HTTPException(
            403,
            "Boost is only available to active subscribers who have used at least 1 analysis this period."
        )

    # Check days remaining for expiry warning
    quota = await get_or_create_current_quota(current_user.id, current_user.tier)
    now = datetime.now(timezone.utc)
    period_end = quota.periodEnd
    if period_end.tzinfo is None:
        period_end = period_end.replace(tzinfo=timezone.utc)
    days_remaining = max(0, (period_end - now).days)
    warn_expiry = days_remaining < 7

    try:
        if not user_db.stripeCustomerId:
            raise HTTPException(400, "No Stripe customer found. Please subscribe to a plan first.")

        checkout_session = stripe.checkout.Session.create(
            customer=user_db.stripeCustomerId,
            mode="payment",
            payment_method_types=["card"],
            line_items=[{"price": BOOST_PRICE_ID, "quantity": 1}],
            success_url=f"{FRONTEND_URL}/dashboard?boost=success",
            cancel_url=f"{FRONTEND_URL}/dashboard?canceled=true",
            metadata={
                "product_type": "boost",
                "user_id": current_user.id,
                "analyses_count": "5"
            }
        )

        return {
            "checkout_url": checkout_session.url,
            "warn_expiry": warn_expiry,
            "days_remaining": days_remaining
        }

    except stripe.error.StripeError as e:
        raise HTTPException(500, f"Stripe error: {str(e)}")
    except Exception as e:
        raise HTTPException(500, f"Error creating boost session: {str(e)}")


@router.post("/create-portal-session")
async def create_portal_session(
    current_user: User = Depends(get_current_user),
    db: Prisma = Depends(get_db)
):
    """
    Create a Stripe Customer Portal session for managing subscription.

    **Returns**: Portal session URL
    """
    try:
        user_db = await db.user.find_unique(where={"id": current_user.id})

        if not user_db.stripeCustomerId:
            raise HTTPException(400, "No active subscription found")

        portal_session = stripe.billing_portal.Session.create(
            customer=user_db.stripeCustomerId,
            return_url=f"{FRONTEND_URL}/dashboard"
        )

        return {"portal_url": portal_session.url}

    except stripe.error.StripeError as e:
        raise HTTPException(500, f"Stripe error: {str(e)}")
    except Exception as e:
        raise HTTPException(500, f"Error creating portal session: {str(e)}")


@router.post("/webhook")
async def stripe_webhook(request: Request, db: Prisma = Depends(get_db)):
    """
    Handle Stripe webhook events for subscription and payment management.

    **Events handled**:
    - customer.subscription.created
    - customer.subscription.updated
    - customer.subscription.deleted
    - invoice.payment_succeeded
    - invoice.payment_failed
    - checkout.session.completed (for boost one-time purchases)
    """
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature")

    if not sig_header:
        raise HTTPException(400, "Missing stripe-signature header")

    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, STRIPE_WEBHOOK_SECRET
        )
    except ValueError:
        raise HTTPException(400, "Invalid payload")
    except stripe.error.SignatureVerificationError:
        raise HTTPException(400, "Invalid signature")

    event_type = event["type"]
    data = event["data"]["object"]

    if event_type == "customer.subscription.created":
        await handle_subscription_created(data, db)
    elif event_type == "customer.subscription.updated":
        await handle_subscription_updated(data, db)
    elif event_type == "customer.subscription.deleted":
        await handle_subscription_deleted(data, db)
    elif event_type == "invoice.payment_succeeded":
        await handle_payment_succeeded(data, db)
    elif event_type == "invoice.payment_failed":
        await handle_payment_failed(data, db)
    elif event_type == "checkout.session.completed":
        await handle_checkout_completed(data, db)

    return JSONResponse({"status": "success"})


async def handle_subscription_created(subscription: Dict[str, Any], db: Prisma):
    """Handle new subscription creation. Sets tier, status, and billing period."""
    customer_id = subscription["customer"]
    subscription_id = subscription["id"]
    status = subscription["status"]
    price_id = subscription["items"]["data"][0]["price"]["id"]
    period_start = datetime.fromtimestamp(subscription["current_period_start"], tz=timezone.utc)
    period_end = datetime.fromtimestamp(subscription["current_period_end"], tz=timezone.utc)

    tier = PRICE_TO_TIER.get(price_id, "starter")

    await db.user.update(
        where={"stripeCustomerId": customer_id},
        data={
            "stripeSubscriptionId": subscription_id,
            "stripeSubscriptionStatus": status,
            "stripePriceId": price_id,
            "subscriptionEndDate": period_end,
            "billingPeriodStart": period_start,
            "billingPeriodEnd": period_end,
            "tier": tier,
            "isActive": status in ["active", "trialing"]
        }
    )


async def handle_subscription_updated(subscription: Dict[str, Any], db: Prisma):
    """Handle subscription updates (renewals, tier changes, cancellation scheduling)."""
    customer_id = subscription["customer"]
    subscription_id = subscription["id"]
    status = subscription["status"]
    price_id = subscription["items"]["data"][0]["price"]["id"]
    period_start = datetime.fromtimestamp(subscription["current_period_start"], tz=timezone.utc)
    period_end = datetime.fromtimestamp(subscription["current_period_end"], tz=timezone.utc)

    tier = PRICE_TO_TIER.get(price_id, "starter")

    await db.user.update(
        where={"stripeCustomerId": customer_id},
        data={
            "stripeSubscriptionId": subscription_id,
            "stripeSubscriptionStatus": status,
            "stripePriceId": price_id,
            "subscriptionEndDate": period_end,
            "billingPeriodStart": period_start,
            "billingPeriodEnd": period_end,
            "tier": tier,
            "isActive": status in ["active", "trialing"]
        }
    )


async def handle_subscription_deleted(subscription: Dict[str, Any], db: Prisma):
    """Handle subscription cancellation. Marks user inactive."""
    customer_id = subscription["customer"]

    await db.user.update(
        where={"stripeCustomerId": customer_id},
        data={
            "stripeSubscriptionStatus": "canceled",
            "isActive": False,
            "tier": "starter"  # Downgrade to lowest tier but mark inactive
        }
    )


async def handle_payment_succeeded(invoice: Dict[str, Any], db: Prisma):
    """
    Handle successful payment.
    For subscription renewals: reactivate account and update billing period dates.
    A new UsageQuota record will be auto-created on the next API request.
    """
    customer_id = invoice["customer"]
    subscription_id = invoice.get("subscription")

    if subscription_id:
        # Retrieve subscription to get updated period dates
        try:
            subscription = stripe.Subscription.retrieve(subscription_id)
            new_period_start = datetime.fromtimestamp(
                subscription["current_period_start"], tz=timezone.utc
            )
            new_period_end = datetime.fromtimestamp(
                subscription["current_period_end"], tz=timezone.utc
            )

            await db.user.update(
                where={"stripeCustomerId": customer_id},
                data={
                    "stripeSubscriptionStatus": "active",
                    "isActive": True,
                    "billingPeriodStart": new_period_start,
                    "billingPeriodEnd": new_period_end,
                    "subscriptionEndDate": new_period_end
                }
            )
        except Exception as e:
            # Fallback: just reactivate without updating period dates
            print(f"⚠️  Could not retrieve subscription for period update: {e}")
            await db.user.update(
                where={"stripeCustomerId": customer_id},
                data={
                    "stripeSubscriptionStatus": "active",
                    "isActive": True
                }
            )


async def handle_payment_failed(invoice: Dict[str, Any], db: Prisma):
    """Handle failed payment — mark as past_due and disable access."""
    customer_id = invoice["customer"]

    await db.user.update(
        where={"stripeCustomerId": customer_id},
        data={
            "stripeSubscriptionStatus": "past_due",
            "isActive": False
        }
    )


async def handle_checkout_completed(session: Dict[str, Any], db: Prisma):
    """
    Handle completed Stripe Checkout sessions.
    For boost purchases: credit 5 analyses to user's current billing period.
    """
    metadata = session.get("metadata", {})
    product_type = metadata.get("product_type")

    if product_type == "boost":
        user_id = metadata.get("user_id")
        analyses_count = int(metadata.get("analyses_count", "5"))

        if not user_id:
            print("⚠️  Boost checkout completed but no user_id in metadata")
            return

        # Look up user to get their tier
        user = await db.user.find_unique(where={"id": user_id})
        if not user:
            print(f"⚠️  Boost checkout: user {user_id} not found")
            return

        await add_boost_analyses(user_id, user.tier, analyses_count)
        print(f"✅ Boost: added {analyses_count} analyses for user {user_id}")
