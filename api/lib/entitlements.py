"""
Backend entitlement feature flags for DVRG.

Feature matrix:
  feature.report.core                  → Starter, Investor, Trader
  feature.report.sizing_summary        → Starter, Investor, Trader  (allocation % + rationale)
  feature.report.signal_metrics        → Investor, Trader            (σ, noise score, stop prob headline)
  feature.report.stop_probability_detail → Investor, Trader          (decomposition table)
  feature.report.trade_setup           → Trader only
  feature.report.engine_diagnostics    → Trader only                 (full panels + driver ranking)
  feature.report.scenario_weights      → Trader only                 (model vs effective weights)
  feature.report.multiplier_stack      → Trader only                 (multiplier list + product)
  feature.report.risk_matrix_full      → Trader only                 (full portfolio interaction metrics)

Usage:
    from api.lib.entitlements import has_feature

    if not has_feature(user, FEAT_SIGNAL_METRICS):
        raise HTTPException(403, {"code": "NOT_ENTITLED", ...})
"""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from api.models.auth import User

# ── Feature flag constants ─────────────────────────────────────────────────
FEAT_REPORT_CORE            = "feature.report.core"
FEAT_SIZING_SUMMARY         = "feature.report.sizing_summary"
FEAT_SIGNAL_METRICS         = "feature.report.signal_metrics"
FEAT_STOP_PROB_DETAIL       = "feature.report.stop_probability_detail"
FEAT_REPORT_TRADE_SETUP     = "feature.report.trade_setup"
FEAT_ENGINE_DIAGNOSTICS     = "feature.report.engine_diagnostics"
FEAT_SCENARIO_WEIGHTS       = "feature.report.scenario_weights"
FEAT_MULTIPLIER_STACK       = "feature.report.multiplier_stack"
FEAT_RISK_MATRIX_FULL       = "feature.report.risk_matrix_full"

# ── Ordered list of all flags (used by /api/entitlements response) ─────────
ALL_FEATURES: list[str] = [
    FEAT_REPORT_CORE,
    FEAT_SIZING_SUMMARY,
    FEAT_SIGNAL_METRICS,
    FEAT_STOP_PROB_DETAIL,
    FEAT_REPORT_TRADE_SETUP,
    FEAT_ENGINE_DIAGNOSTICS,
    FEAT_SCENARIO_WEIGHTS,
    FEAT_MULTIPLIER_STACK,
    FEAT_RISK_MATRIX_FULL,
]

# ── Tier entitlement matrix ────────────────────────────────────────────────
_ENTITLEMENTS: dict[str, set[str]] = {
    "starter": {
        FEAT_REPORT_CORE,
        FEAT_SIZING_SUMMARY,
    },
    "investor": {
        FEAT_REPORT_CORE,
        FEAT_SIZING_SUMMARY,
        FEAT_SIGNAL_METRICS,
        FEAT_STOP_PROB_DETAIL,
    },
    "trader": {
        FEAT_REPORT_CORE,
        FEAT_SIZING_SUMMARY,
        FEAT_SIGNAL_METRICS,
        FEAT_STOP_PROB_DETAIL,
        FEAT_REPORT_TRADE_SETUP,
        FEAT_ENGINE_DIAGNOSTICS,
        FEAT_SCENARIO_WEIGHTS,
        FEAT_MULTIPLIER_STACK,
        FEAT_RISK_MATRIX_FULL,
    },
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
