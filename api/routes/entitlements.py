"""
GET  /api/entitlements         — feature-flag payload for the authenticated user
POST /api/entitlements/ensure  — idempotently create missing entitlement state

GET derives everything from the User object; handles admin override and Stripe
inactive-status downgrade.  Frontend can cache the response for ~5 minutes.

POST /ensure is a lightweight "make sure the user's Neon rows exist" endpoint.
Call it on first signed-in load of /analyze so the FreeReportCredit row is
always present even when the Clerk webhook was delayed or missed.
"""

from fastapi import APIRouter, Depends

from api.dependencies import get_current_user
from api.lib.entitlements import (
    ALL_FEATURES,
    _ENTITLEMENTS,
    _INACTIVE_STATUSES,
    _effective_tier,
)
from api.lib.plan_limits import get_tier_limits
from api.models.auth import User
from api.services.quota_service import get_usage_summary, get_or_create_free_credits

router = APIRouter(tags=["entitlements"])


@router.get("/entitlements")
async def get_entitlements(user: User = Depends(get_current_user)) -> dict:
    """
    Resolve and return feature flags + quota limits for the current user.

    Response shape:
        {
          "tier": "investor",
          "active": true,
          "features": {
            "feature.report.core": true,
            "feature.report.signal_metrics": true,
            ...
          },
          "limits": {
            "analyses_per_month": 15,
            "concurrent_analyses": 3,
            "watchlist_max": 999,
            "is_credit_based": false,
            "free_credits_total": 0
          },
          "usage": {
            "analyses_used": 3,
            "analyses_remaining": 12,
            "analyses_limit": 15,
            "report_credits_total": null,
            "report_credits_used": null,
            "report_credits_remaining": null,
            "is_free_tier": false,
            "at_warning_threshold": false
          }
        }

    Notes:
    - `tier` is the *effective* tier after applying admin override and Stripe
      downgrade — may differ from the stored User.tier when the subscription
      is inactive.
    - `active` is false when the Stripe subscription is in a terminal/delinquent
      state (canceled, past_due, unpaid, incomplete_expired).
    - Free-tier users: `usage.is_free_tier=true`, credit fields are populated;
      monthly fields (analyses_limit, etc.) mirror credits for compatibility.
    - All known feature flags are included in `features`; missing flags default
      to false on the client side.
    """
    tier = _effective_tier(user)
    granted = _ENTITLEMENTS.get(tier, _ENTITLEMENTS["free"])

    stripe_status = user.stripe_subscription_status
    active = stripe_status not in _INACTIVE_STATUSES if stripe_status else True

    limits = get_tier_limits(tier)

    # Fetch live usage so frontend always has accurate credit/quota counts
    user_tier_str = str(user.tier.value) if hasattr(user.tier, "value") else str(user.tier)
    usage = await get_usage_summary(
        user.id,
        user_tier_str,
        stripe_status=stripe_status or "",
        is_admin=user.is_admin,
    )

    return {
        "tier": tier,
        "active": active,
        "features": {flag: (flag in granted) for flag in ALL_FEATURES},
        "limits": {
            "analyses_per_month": limits.analyses_per_month,
            "concurrent_analyses": limits.concurrent_analyses,
            "watchlist_max": limits.watchlist_max,
            "is_credit_based": limits.is_credit_based,
            "free_credits_total": limits.free_credits_total,
        },
        "usage": {
            "analyses_used": usage.get("analyses_used", 0),
            "analyses_remaining": usage.get("analyses_remaining", 0),
            "analyses_limit": usage.get("analyses_limit", 0),
            "report_credits_total": usage.get("report_credits_total"),
            "report_credits_used": usage.get("report_credits_used"),
            "report_credits_remaining": usage.get("report_credits_remaining"),
            "is_free_tier": usage.get("is_free_tier", False),
            "at_warning_threshold": usage.get("at_warning_threshold", False),
        },
    }


@router.post("/entitlements/ensure", status_code=200)
async def ensure_entitlements(user: User = Depends(get_current_user)) -> dict:
    """
    Idempotently ensure the user's entitlement rows exist in Neon.

    Intended to be called on first signed-in load of /analyze so the
    FreeReportCredit row is present even if the Clerk webhook was delayed
    or missed during account creation.

    - Free-tier users: creates FreeReportCredit(2 credits) if missing.
    - Paid-tier users: no-op (their quota is managed by Stripe webhooks).
    - Returns: { "ensured": true, "tier": "<effective tier>" }
    """
    user_tier_str = str(user.tier.value) if hasattr(user.tier, "value") else str(user.tier)

    if user_tier_str == "free":
        await get_or_create_free_credits(user.id)

    tier = _effective_tier(user)
    return {"ensured": True, "tier": tier}
