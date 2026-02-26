"""
Authentication endpoints.
"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
import os
import logging
import requests as _requests

from api.models.auth import User
from api.dependencies import get_current_user

logger = logging.getLogger(__name__)
router = APIRouter()

_CLERK_API_BASE = "https://api.clerk.com/v1"


class UserResponse(BaseModel):
    """Current user information."""
    id: str
    email: str
    full_name: str | None
    tier: str
    is_active: bool
    is_admin: bool


@router.post("/auth/resend-verification", status_code=200)
async def resend_verification_email(current_user: User = Depends(get_current_user)):
    """
    Trigger a Clerk verification email for the authenticated user's primary email address.

    Called by PaywallModal when a free-tier user needs to verify their email
    to unlock their second free report.
    """
    secret_key = os.getenv("CLERK_SECRET_KEY", "")
    if not secret_key:
        raise HTTPException(status_code=503, detail="Email service not configured")

    headers = {
        "Authorization": f"Bearer {secret_key}",
        "Content-Type": "application/json",
    }

    # 1. Fetch the user's Clerk profile to get their primary email address ID
    try:
        user_resp = _requests.get(
            f"{_CLERK_API_BASE}/users/{current_user.clerk_id}",
            headers=headers,
            timeout=10,
        )
        user_resp.raise_for_status()
        clerk_user = user_resp.json()
    except _requests.RequestException as exc:
        logger.error("Clerk API error fetching user %s: %s", current_user.clerk_id, exc)
        raise HTTPException(status_code=502, detail="Could not reach Clerk API")

    primary_email_id: str | None = clerk_user.get("primary_email_address_id")
    if not primary_email_id:
        raise HTTPException(status_code=400, detail="No primary email address found")

    # 2. Trigger prepare_verification (sends/resends the verification email)
    try:
        verify_resp = _requests.post(
            f"{_CLERK_API_BASE}/email_addresses/{primary_email_id}/prepare_verification",
            headers=headers,
            json={"strategy": "email_link"},
            timeout=10,
        )
        verify_resp.raise_for_status()
    except _requests.RequestException as exc:
        logger.error(
            "Clerk prepare_verification error for email_id=%s: %s", primary_email_id, exc
        )
        raise HTTPException(status_code=502, detail="Could not send verification email")

    logger.info("Resent verification email for user %s", current_user.id)
    return {"sent": True}


@router.get("/auth/me", response_model=UserResponse)
async def get_me(current_user: User = Depends(get_current_user)):
    """
    Get the currently authenticated user's information.

    This endpoint is used by the frontend to:
    - Check if the user is authenticated
    - Get the user's admin status
    - Redirect admin users to the admin dashboard
    """
    response = UserResponse(
        id=current_user.id,
        email=current_user.email,
        full_name=current_user.full_name,
        tier=current_user.tier,
        is_active=current_user.is_active,
        is_admin=current_user.is_admin
    )
    logger.info("📤 /auth/me returning: user_id=%s is_admin=%s", current_user.id, response.is_admin)
    return response
