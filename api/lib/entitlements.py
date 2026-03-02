"""
Backend entitlement feature flags for DVRG.

Feature matrix — Clarity Layer (Starter) / Discipline Layer (Investor) / Edge Layer (Trader):

  Core (all tiers):
    feature.report.core                  → Free, Starter, Investor, Trader
    feature.report.sizing_summary        → Free, Starter, Investor, Trader  (allocation % + rationale)

  Investor+ (Discipline Layer):
    feature.report.export_pdf            → Investor, Trader
    feature.report.signal_metrics        → Investor, Trader            (σ, noise score, stop prob headline)
    feature.report.stop_probability_detail → Investor, Trader          (decomposition table)
    feature.report.full_scenario_table   → Investor, Trader            (full bear/base/bull prob table)
    feature.report.capital_deployment_path → Investor, Trader          (3-stage tranche deployment)
    feature.report.thesis_break_monitor  → Investor, Trader            (thesis break section)
    feature.report.structural_quality_full → Investor, Trader          (moat + quality breakdown)
    feature.report.stop_probability_basic → Investor, Trader           (stop prob headline — alias)
    feature.deployment.structural_update → Investor, Trader

  Trader only (Edge Layer):
    feature.report.trade_setup           → Trader only
    feature.report.engine_diagnostics    → Trader only                 (full panels + driver ranking)
    feature.report.scenario_weights      → Trader only                 (model vs effective weights)
    feature.report.multiplier_stack      → Trader only                 (multiplier list + product)
    feature.report.risk_matrix_full      → Trader only                 (full portfolio interaction metrics)
    feature.report.ev_stability_panel    → Trader only                 (EV stability diagnostics)
    feature.report.probability_reliability → Trader only               (probability reliability scores)
    feature.report.stop_probability_advanced → Trader only             (advanced stop decomposition)
    feature.report.universe_context      → Trader only                 (universe percentile context)
    feature.report.percentile_ranks      → Trader only                 (percentile rank overlays)
    feature.report.sensitivity_band      → Trader only                 (sensitivity band visualization)
    feature.report.horizon_normalization → Trader only                 (horizon efficiency scores)

  Free tier has identical report content to Starter (same feature flags).
  The difference is how generation is gated: lifetime credits (2 total) vs. monthly quota.

Usage:
    from api.lib.entitlements import has_feature

    if not has_feature(user, FEAT_SIGNAL_METRICS):
        raise HTTPException(403, {"code": "NOT_ENTITLED", ...})
"""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from api.models.auth import User

# ── Feature flag constants ─────────────────────────────────────────────────

# Core — all tiers
FEAT_REPORT_CORE            = "feature.report.core"
FEAT_SIZING_SUMMARY         = "feature.report.sizing_summary"

# Investor+ — Discipline Layer
FEAT_REPORT_PDF                  = "feature.report.export_pdf"
FEAT_SIGNAL_METRICS              = "feature.report.signal_metrics"
FEAT_STOP_PROB_DETAIL            = "feature.report.stop_probability_detail"
FEAT_FULL_SCENARIO_TABLE         = "feature.report.full_scenario_table"
FEAT_CAPITAL_DEPLOYMENT_PATH     = "feature.report.capital_deployment_path"
FEAT_THESIS_BREAK_MONITOR        = "feature.report.thesis_break_monitor"
FEAT_STRUCTURAL_QUALITY_FULL     = "feature.report.structural_quality_full"
FEAT_STOP_PROB_BASIC             = "feature.report.stop_probability_basic"
FEAT_DEPLOYMENT_STRUCTURAL       = "feature.deployment.structural_update"

# Trader only — Edge Layer
FEAT_REPORT_TRADE_SETUP          = "feature.report.trade_setup"
FEAT_ENGINE_DIAGNOSTICS          = "feature.report.engine_diagnostics"
FEAT_SCENARIO_WEIGHTS            = "feature.report.scenario_weights"
FEAT_MULTIPLIER_STACK            = "feature.report.multiplier_stack"
FEAT_RISK_MATRIX_FULL            = "feature.report.risk_matrix_full"
FEAT_EV_STABILITY_PANEL          = "feature.report.ev_stability_panel"
FEAT_PROBABILITY_RELIABILITY     = "feature.report.probability_reliability"
FEAT_STOP_PROB_ADVANCED          = "feature.report.stop_probability_advanced"
FEAT_UNIVERSE_CONTEXT            = "feature.report.universe_context"
FEAT_PERCENTILE_RANKS            = "feature.report.percentile_ranks"
FEAT_SENSITIVITY_BAND            = "feature.report.sensitivity_band"
FEAT_HORIZON_NORMALIZATION       = "feature.report.horizon_normalization"

# ── Ordered list of all flags (used by /api/entitlements response) ─────────
ALL_FEATURES: list[str] = [
    # Core
    FEAT_REPORT_CORE,
    FEAT_SIZING_SUMMARY,
    # Investor+
    FEAT_REPORT_PDF,
    FEAT_SIGNAL_METRICS,
    FEAT_STOP_PROB_DETAIL,
    FEAT_FULL_SCENARIO_TABLE,
    FEAT_CAPITAL_DEPLOYMENT_PATH,
    FEAT_THESIS_BREAK_MONITOR,
    FEAT_STRUCTURAL_QUALITY_FULL,
    FEAT_STOP_PROB_BASIC,
    FEAT_DEPLOYMENT_STRUCTURAL,
    # Trader only
    FEAT_REPORT_TRADE_SETUP,
    FEAT_ENGINE_DIAGNOSTICS,
    FEAT_SCENARIO_WEIGHTS,
    FEAT_MULTIPLIER_STACK,
    FEAT_RISK_MATRIX_FULL,
    FEAT_EV_STABILITY_PANEL,
    FEAT_PROBABILITY_RELIABILITY,
    FEAT_STOP_PROB_ADVANCED,
    FEAT_UNIVERSE_CONTEXT,
    FEAT_PERCENTILE_RANKS,
    FEAT_SENSITIVITY_BAND,
    FEAT_HORIZON_NORMALIZATION,
]

# ── Tier entitlement matrix ────────────────────────────────────────────────
_INVESTOR_PLUS: set[str] = {
    FEAT_REPORT_PDF,
    FEAT_SIGNAL_METRICS,
    FEAT_STOP_PROB_DETAIL,
    FEAT_FULL_SCENARIO_TABLE,
    FEAT_CAPITAL_DEPLOYMENT_PATH,
    FEAT_THESIS_BREAK_MONITOR,
    FEAT_STRUCTURAL_QUALITY_FULL,
    FEAT_STOP_PROB_BASIC,
    FEAT_DEPLOYMENT_STRUCTURAL,
}

_TRADER_ONLY: set[str] = {
    FEAT_REPORT_TRADE_SETUP,
    FEAT_ENGINE_DIAGNOSTICS,
    FEAT_SCENARIO_WEIGHTS,
    FEAT_MULTIPLIER_STACK,
    FEAT_RISK_MATRIX_FULL,
    FEAT_EV_STABILITY_PANEL,
    FEAT_PROBABILITY_RELIABILITY,
    FEAT_STOP_PROB_ADVANCED,
    FEAT_UNIVERSE_CONTEXT,
    FEAT_PERCENTILE_RANKS,
    FEAT_SENSITIVITY_BAND,
    FEAT_HORIZON_NORMALIZATION,
}

_CORE: set[str] = {FEAT_REPORT_CORE, FEAT_SIZING_SUMMARY}

_ENTITLEMENTS: dict[str, set[str]] = {
    # Free tier: identical content to Starter (gating is credit-based, not feature-based)
    "free":     _CORE.copy(),
    "starter":  _CORE.copy(),
    "investor": _CORE | _INVESTOR_PLUS,
    "trader":   _CORE | _INVESTOR_PLUS | _TRADER_ONLY,
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
    # Inactive Stripe subscription: paid users drop to starter, free users stay free
    if stripe_status and stripe_status in _INACTIVE_STATUSES:
        return "free" if tier == "free" else "starter"

    return tier


def has_feature(user: "User", feature: str) -> bool:
    """
    Return True if the user is entitled to the given feature flag.

    Args:
        user: Authenticated User model instance.
        feature: One of the FEAT_* constants defined in this module.
    """
    tier = _effective_tier(user)
    return feature in _ENTITLEMENTS.get(tier, _ENTITLEMENTS["free"])


def upgrade_hint(feature: str) -> str:
    """Return the minimum tier name needed to access a feature."""
    for tier in ("starter", "investor", "trader"):
        if feature in _ENTITLEMENTS.get(tier, set()):
            return tier
    return "trader"
