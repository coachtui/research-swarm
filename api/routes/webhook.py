"""
Webhook endpoints for third-party integrations.
"""
from fastapi import APIRouter, Request, HTTPException, Header
from typing import Optional
import json
import hmac
import hashlib
import os
import logging
from datetime import datetime

from api.lib.db import get_db

router = APIRouter()
logger = logging.getLogger(__name__)


async def verify_clerk_signature(payload: bytes, headers: dict) -> bool:
    """
    Verify Clerk webhook signature using Svix headers.
    """
    webhook_secret = os.getenv("CLERK_WEBHOOK_SECRET", "")

    if not webhook_secret:
        logger.warning("CLERK_WEBHOOK_SECRET not set, skipping signature verification")
        return True  # Allow in development without secret

    svix_id = headers.get("svix-id")
    svix_timestamp = headers.get("svix-timestamp")
    svix_signature = headers.get("svix-signature")

    if not all([svix_id, svix_timestamp, svix_signature]):
        logger.error("Missing Svix headers")
        return False

    # Construct signed content
    signed_content = f"{svix_id}.{svix_timestamp}.{payload.decode()}"

    # Extract signature(s) - Svix sends multiple versions
    signatures = {}
    for sig in svix_signature.split(" "):
        if "," in sig:
            version, signature = sig.split(",", 1)
            signatures[version] = signature

    # Verify v1 signature (most common)
    # Svix format: secret is "whsec_" + base64(raw_key_bytes)
    # Signature = base64(HMAC-SHA256(signed_content, raw_key_bytes))
    if "v1" in signatures:
        import base64
        raw_secret = webhook_secret.removeprefix("whsec_")
        # Add padding in case base64 string is not padded
        key_bytes = base64.b64decode(raw_secret + "==")
        mac = hmac.new(key_bytes, signed_content.encode(), hashlib.sha256)
        expected_signature = base64.b64encode(mac.digest()).decode()

        if hmac.compare_digest(signatures["v1"], expected_signature):
            return True

    logger.error("Signature verification failed")
    return False


@router.post("/clerk")
async def clerk_webhook(
    request: Request,
    svix_id: Optional[str] = Header(None, alias="svix-id"),
    svix_timestamp: Optional[str] = Header(None, alias="svix-timestamp"),
    svix_signature: Optional[str] = Header(None, alias="svix-signature"),
):
    """
    Webhook endpoint for Clerk authentication events.

    Handles:
    - user.created: Create new user in database
    - user.updated: Update existing user
    - user.deleted: Soft delete user (set inactive)
    """
    # Get raw body for signature verification
    body = await request.body()

    # Verify signature
    headers = {
        "svix-id": svix_id,
        "svix-timestamp": svix_timestamp,
        "svix-signature": svix_signature,
    }

    # Always verify webhook signature
    if not await verify_clerk_signature(body, headers):
        raise HTTPException(status_code=401, detail="Invalid webhook signature")

    # Parse event
    try:
        event = json.loads(body)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON payload")

    event_type = event.get("type")
    logger.info(f"Received Clerk webhook: {event_type}")

    db = await get_db()

    try:
        if event_type == "user.created":
            await handle_user_created(db, event)
        elif event_type == "user.updated":
            await handle_user_updated(db, event)
        elif event_type == "user.deleted":
            await handle_user_deleted(db, event)
        else:
            logger.warning(f"Unhandled event type: {event_type}")

    except Exception as e:
        logger.error(f"Error processing webhook: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Webhook processing failed: {str(e)}")

    return {"received": True, "event_type": event_type}


async def handle_user_created(db, event: dict):
    """Handle user.created event."""
    user_data = event["data"]
    clerk_id = user_data["id"]

    # Get primary email
    email_addresses = user_data.get("email_addresses", [])
    primary_email = None
    for email in email_addresses:
        if email.get("id") == user_data.get("primary_email_address_id"):
            primary_email = email.get("email_address")
            break

    if not primary_email and email_addresses:
        primary_email = email_addresses[0].get("email_address")

    # Build full name
    first_name = user_data.get("first_name", "")
    last_name = user_data.get("last_name", "")
    full_name = f"{first_name} {last_name}".strip() or None

    # Check if user already exists
    existing_user = await db.user.find_first(
        where={"clerkId": clerk_id}
    )

    # Determine email verification status for the primary address
    email_verified = False
    for addr in email_addresses:
        if addr.get("id") == user_data.get("primary_email_address_id"):
            email_verified = addr.get("verification", {}).get("status") == "verified"
            break

    if existing_user:
        logger.warning(f"User {clerk_id} already exists, updating instead")
        await db.user.update(
            where={"clerkId": clerk_id},
            data={
                "email": primary_email,
                "fullName": full_name,
                "isActive": True,
                "emailVerified": email_verified,
                "updatedAt": datetime.utcnow(),
            }
        )
    else:
        # Create new user with Free tier (2 lifetime report credits)
        await db.user.create(
            data={
                "clerkId": clerk_id,
                "email": primary_email,
                "fullName": full_name,
                "tier": "free",
                "monthlyBudgetUsd": 200.0,
                "isActive": True,
                "isAdmin": False,
                "emailVerified": email_verified,
            }
        )
        logger.info(f"Created user: {clerk_id} ({primary_email}) [tier=free, email_verified={email_verified}]")


async def handle_user_updated(db, event: dict):
    """Handle user.updated event — syncs email, name, and email_verified status."""
    user_data = event["data"]
    clerk_id = user_data["id"]

    # Get primary email and its verification status
    email_addresses = user_data.get("email_addresses", [])
    primary_email = None
    email_verified = False
    for addr in email_addresses:
        if addr.get("id") == user_data.get("primary_email_address_id"):
            primary_email = addr.get("email_address")
            email_verified = addr.get("verification", {}).get("status") == "verified"
            break

    if not primary_email and email_addresses:
        primary_email = email_addresses[0].get("email_address")

    # Build full name
    first_name = user_data.get("first_name", "")
    last_name = user_data.get("last_name", "")
    full_name = f"{first_name} {last_name}".strip() or None

    # Update user — this also propagates emailVerified so free-tier report #2 unlocks
    await db.user.update(
        where={"clerkId": clerk_id},
        data={
            "email": primary_email,
            "fullName": full_name,
            "emailVerified": email_verified,
            "updatedAt": datetime.utcnow(),
        }
    )
    logger.info(f"Updated user: {clerk_id} (email_verified={email_verified})")


async def handle_user_deleted(db, event: dict):
    """Handle user.deleted event - soft delete."""
    user_data = event["data"]
    clerk_id = user_data["id"]

    # Soft delete - set inactive
    await db.user.update(
        where={"clerkId": clerk_id},
        data={
            "isActive": False,
            "updatedAt": datetime.utcnow(),
        }
    )
    logger.info(f"Soft deleted user: {clerk_id}")
