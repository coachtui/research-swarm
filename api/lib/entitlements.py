"""
Backend entitlement feature flags for DVRG.

Feature matrix:
  feature.report.core         → Starter, Investor, Trader
  feature.report.export_pdf   → Investor, Trader
  feature.report.trade_setup  → Trader only

Usage:
    from api.lib.entitlements import FEAT_REPORT_PDF, has_feature

    if not has_feature(user, FEAT_REPORT_PDF):
        raise HTTPException(403, {"code": "NOT_ENTITLED", ...})
"""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from api.models.auth import User

# ── Feature flag constants ─────────────────────────────────────────────────
FEAT_REPORT_CORE = "feature.report.core"
FEAT_REPORT_PDF = "feature.report.export_pdf"
FEAT_REPORT_TRADE_SETUP = "feature.report.trade_setup"

# ── Tier entitlement matrix ────────────────────────────────────────────────
_ENTITLEMENTS: dict[str, set[str]] = {
    "starter": {FEAT_REPORT_CORE},
    "investor": {FEAT_REPORT_CORE, FEAT_REPORT_PDF},
    "trader": {FEAT_REPORT_CORE, FEAT_REPORT_PDF, FEAT_REPORT_TRADE_SETUP},
}

# Stripe statuses that revoke paid-tier features
_INACTIVE_STATUSES: frozenset[str] = frozenset({
    "canceled", "past_due", "unpaid", "incomplete_expired",
})


def _effective_tier(user: "User") -> str:
    """
    Return the tier that should be used for entitlement checks.

    Admins are never downgraded.
    Users whose Stripe subscription is in an inactive status are treated as
    Starter for entitlement purposes (no grace period here; implement above if
    needed).
    """
    if user.is_admin:
        return "trader"  # admins get everything

    tier = str(user.tier.value).lower() if hasattr(user.tier, "value") else str(user.tier).lower()

    stripe_status = user.stripe_subscription_status
    if stripe_status and stripe_status in _INACTIVE_STATUSES:
        return "starter"

    return tier


def has_feature(user: "User", feature: str) -> bool:
    """
    Return True if the user is entitled to the given feature flag.

    Args:
        user: Authenticated User model instance.
        feature: One of the FEAT_* constants defined in this module.
    """
    tier = _effective_tier(user)
    return feature in _ENTITLEMENTS.get(tier, _ENTITLEMENTS["starter"])


def upgrade_hint(feature: str) -> str:
    """Return the minimum tier name needed to access a feature."""
    for tier in ("starter", "investor", "trader"):
        if feature in _ENTITLEMENTS.get(tier, set()):
            return tier
    return "trader"
