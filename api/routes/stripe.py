"""
Stripe subscription routes.

Handles checkout sessions, customer portal, and webhook events.
"""

import os
import stripe
from fastapi import APIRouter, HTTPException, Request, Depends
from fastapi.responses import JSONResponse
from datetime import datetime
from typing import Dict, Any

from api.dependencies import get_current_user
from api.lib.db import get_db
from api.models.auth import User
from prisma import Prisma

router = APIRouter(prefix="/stripe", tags=["stripe"])

# Initialize Stripe
stripe.api_key = os.getenv("STRIPE_SECRET_KEY")
STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET")
PRO_PRICE_ID = os.getenv("STRIPE_PRO_PRICE_ID")
PREMIUM_PRICE_ID = os.getenv("STRIPE_PREMIUM_PRICE_ID")


@router.post("/create-checkout-session")
async def create_checkout_session(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Prisma = Depends(get_db)
):
    """
    Create a Stripe Checkout session for subscription.

    **Request body**:
    - price_id: Stripe price ID (pro or premium)

    **Returns**: Checkout session URL
    """
    body = await request.json()
    price_id = body.get("price_id")

    if not price_id:
        raise HTTPException(400, "price_id is required")

    if price_id not in [PRO_PRICE_ID, PREMIUM_PRICE_ID]:
        raise HTTPException(400, "Invalid price_id")

    try:
        # Get or create Stripe customer
        user_db = await db.user.find_unique(where={"id": current_user.id})

        if user_db.stripeCustomerId:
            customer_id = user_db.stripeCustomerId
        else:
            # Create new Stripe customer
            customer = stripe.Customer.create(
                email=current_user.email,
                metadata={
                    "user_id": current_user.id,
                    "clerk_id": current_user.clerk_id
                }
            )
            customer_id = customer.id

            # Save customer ID to database
            await db.user.update(
                where={"id": current_user.id},
                data={"stripeCustomerId": customer_id}
            )

        # Create checkout session
        checkout_session = stripe.checkout.Session.create(
            customer=customer_id,
            mode="subscription",
            payment_method_types=["card"],
            line_items=[{
                "price": price_id,
                "quantity": 1
            }],
            success_url=f"{os.getenv('NEXT_PUBLIC_API_URL', 'http://localhost:3000')}/dashboard?success=true",
            cancel_url=f"{os.getenv('NEXT_PUBLIC_API_URL', 'http://localhost:3000')}/dashboard?canceled=true",
            metadata={
                "user_id": current_user.id
            }
        )

        return {"checkout_url": checkout_session.url}

    except stripe.error.StripeError as e:
        raise HTTPException(500, f"Stripe error: {str(e)}")
    except Exception as e:
        raise HTTPException(500, f"Error creating checkout session: {str(e)}")


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

        # Create portal session
        portal_session = stripe.billing_portal.Session.create(
            customer=user_db.stripeCustomerId,
            return_url=f"{os.getenv('NEXT_PUBLIC_API_URL', 'http://localhost:3000')}/dashboard"
        )

        return {"portal_url": portal_session.url}

    except stripe.error.StripeError as e:
        raise HTTPException(500, f"Stripe error: {str(e)}")
    except Exception as e:
        raise HTTPException(500, f"Error creating portal session: {str(e)}")


@router.post("/webhook")
async def stripe_webhook(request: Request, db: Prisma = Depends(get_db)):
    """
    Handle Stripe webhook events for subscription management.

    **Events handled**:
    - customer.subscription.created
    - customer.subscription.updated
    - customer.subscription.deleted
    - invoice.payment_succeeded
    - invoice.payment_failed
    """
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature")

    if not sig_header:
        raise HTTPException(400, "Missing stripe-signature header")

    try:
        # Verify webhook signature
        event = stripe.Webhook.construct_event(
            payload, sig_header, STRIPE_WEBHOOK_SECRET
        )
    except ValueError:
        raise HTTPException(400, "Invalid payload")
    except stripe.error.SignatureVerificationError:
        raise HTTPException(400, "Invalid signature")

    # Handle the event
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

    return JSONResponse({"status": "success"})


async def handle_subscription_created(subscription: Dict[str, Any], db: Prisma):
    """Handle new subscription creation."""
    customer_id = subscription["customer"]
    subscription_id = subscription["id"]
    status = subscription["status"]
    price_id = subscription["items"]["data"][0]["price"]["id"]
    current_period_end = datetime.fromtimestamp(subscription["current_period_end"])

    # Determine tier from price ID
    tier = "pro" if price_id == PRO_PRICE_ID else "premium"

    # Update user in database
    await db.user.update(
        where={"stripeCustomerId": customer_id},
        data={
            "stripeSubscriptionId": subscription_id,
            "stripeSubscriptionStatus": status,
            "stripePriceId": price_id,
            "subscriptionEndDate": current_period_end,
            "tier": tier,
            "isActive": status == "active"
        }
    )


async def handle_subscription_updated(subscription: Dict[str, Any], db: Prisma):
    """Handle subscription updates (renewals, changes, cancellations)."""
    customer_id = subscription["customer"]
    subscription_id = subscription["id"]
    status = subscription["status"]
    price_id = subscription["items"]["data"][0]["price"]["id"]
    current_period_end = datetime.fromtimestamp(subscription["current_period_end"])

    # Determine tier from price ID
    tier = "pro" if price_id == PRO_PRICE_ID else "premium"

    # Update user in database
    await db.user.update(
        where={"stripeCustomerId": customer_id},
        data={
            "stripeSubscriptionId": subscription_id,
            "stripeSubscriptionStatus": status,
            "stripePriceId": price_id,
            "subscriptionEndDate": current_period_end,
            "tier": tier,
            "isActive": status in ["active", "trialing"]
        }
    )


async def handle_subscription_deleted(subscription: Dict[str, Any], db: Prisma):
    """Handle subscription cancellation."""
    customer_id = subscription["customer"]

    # Downgrade user to free tier (or disable access)
    await db.user.update(
        where={"stripeCustomerId": customer_id},
        data={
            "stripeSubscriptionStatus": "canceled",
            "isActive": False,  # Disable access when subscription is canceled
            "tier": "pro"  # Keep tier but mark as inactive
        }
    )


async def handle_payment_succeeded(invoice: Dict[str, Any], db: Prisma):
    """Handle successful payment."""
    customer_id = invoice["customer"]
    subscription_id = invoice.get("subscription")

    if subscription_id:
        # Reactivate subscription if it was past_due
        await db.user.update(
            where={"stripeCustomerId": customer_id},
            data={
                "stripeSubscriptionStatus": "active",
                "isActive": True
            }
        )


async def handle_payment_failed(invoice: Dict[str, Any], db: Prisma):
    """Handle failed payment."""
    customer_id = invoice["customer"]

    # Mark subscription as past_due
    await db.user.update(
        where={"stripeCustomerId": customer_id},
        data={
            "stripeSubscriptionStatus": "past_due",
            "isActive": False  # Disable access on payment failure
        }
    )
