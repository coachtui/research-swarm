"""
GET /api/entitlements

Returns a resolved feature-flag payload for the authenticated user.
Derives everything from the User object — no extra DB hit beyond the initial
auth lookup. Handles admin override and Stripe inactive-status downgrade.

Frontend can cache this response for ~5 minutes and use it to gate UI sections
without duplicating the tier-hierarchy logic client-side.
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
            "feature.report.export_pdf": true,
            "feature.report.signal_metrics": true,
            ...
          },
          "limits": {
            "analyses_per_month": 15,
            "concurrent_analyses": 3,
            "watchlist_max": 999
          }
        }

    Notes:
    - `tier` is the *effective* tier after applying admin override and Stripe
      downgrade — may differ from the stored User.tier when the subscription
      is inactive.
    - `active` is false when the Stripe subscription is in a terminal/delinquent
      state (canceled, past_due, unpaid, incomplete_expired).
    - All known feature flags are included in `features`; missing flags default
      to false on the client side.
    """
    tier = _effective_tier(user)
    granted = _ENTITLEMENTS.get(tier, _ENTITLEMENTS["starter"])

    stripe_status = user.stripe_subscription_status
    active = stripe_status not in _INACTIVE_STATUSES if stripe_status else True

    limits = get_tier_limits(tier)

    return {
        "tier": tier,
        "active": active,
        "features": {flag: (flag in granted) for flag in ALL_FEATURES},
        "limits": {
            "analyses_per_month": limits.analyses_per_month,
            "concurrent_analyses": limits.concurrent_analyses,
            "watchlist_max": limits.watchlist_max,
        },
    }
