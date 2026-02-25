"""
Feature flag entitlements — unit tests for api/lib/entitlements.py.

Coverage:
  - Tier flag matrix correctness (all tiers, all new flags)
  - has_feature() correct for each tier
  - _effective_tier() admin override
  - _effective_tier() Stripe inactive-status downgrade
  - ALL_FEATURES list completeness
  - upgrade_hint() accuracy

Run with:
    pytest tests/test_feature_flags.py -v
"""

import pytest
from unittest.mock import MagicMock

from api.lib.entitlements import (
    has_feature,
    upgrade_hint,
    _effective_tier,
    ALL_FEATURES,
    FEAT_REPORT_CORE,
    FEAT_SIZING_SUMMARY,
    FEAT_REPORT_PDF,
    FEAT_SIGNAL_METRICS,
    FEAT_STOP_PROB_DETAIL,
    FEAT_REPORT_TRADE_SETUP,
    FEAT_ENGINE_DIAGNOSTICS,
    FEAT_SCENARIO_WEIGHTS,
    FEAT_MULTIPLIER_STACK,
    FEAT_RISK_MATRIX_FULL,
)


# ── Test helpers ──────────────────────────────────────────────────────────────

def make_user(tier: str, is_admin: bool = False, stripe_status: str | None = None):
    """Build a minimal mock User with the fields entitlements.py reads."""
    u = MagicMock()
    u.tier.value = tier
    u.is_admin = is_admin
    u.stripe_subscription_status = stripe_status
    return u


# ── ALL_FEATURES completeness ─────────────────────────────────────────────────

class TestAllFeaturesList:
    """ALL_FEATURES must enumerate every flag constant."""

    ALL_EXPECTED = [
        FEAT_REPORT_CORE,
        FEAT_SIZING_SUMMARY,
        FEAT_REPORT_PDF,
        FEAT_SIGNAL_METRICS,
        FEAT_STOP_PROB_DETAIL,
        FEAT_REPORT_TRADE_SETUP,
        FEAT_ENGINE_DIAGNOSTICS,
        FEAT_SCENARIO_WEIGHTS,
        FEAT_MULTIPLIER_STACK,
        FEAT_RISK_MATRIX_FULL,
    ]

    def test_all_flags_in_all_features(self):
        for flag in self.ALL_EXPECTED:
            assert flag in ALL_FEATURES, f"Flag '{flag}' missing from ALL_FEATURES"

    def test_no_duplicates(self):
        assert len(ALL_FEATURES) == len(set(ALL_FEATURES)), "ALL_FEATURES has duplicates"


# ── _effective_tier() ─────────────────────────────────────────────────────────

class TestEffectiveTier:
    """Admin override and Stripe inactive-status downgrade."""

    def test_admin_always_gets_trader(self):
        assert _effective_tier(make_user("starter", is_admin=True)) == "trader"

    def test_admin_overrides_investor(self):
        assert _effective_tier(make_user("investor", is_admin=True)) == "trader"

    def test_canceled_downgrades_to_starter(self):
        assert _effective_tier(make_user("investor", stripe_status="canceled")) == "starter"

    def test_past_due_downgrades_to_starter(self):
        assert _effective_tier(make_user("trader", stripe_status="past_due")) == "starter"

    def test_unpaid_downgrades_to_starter(self):
        assert _effective_tier(make_user("trader", stripe_status="unpaid")) == "starter"

    def test_incomplete_expired_downgrades_to_starter(self):
        assert _effective_tier(make_user("investor", stripe_status="incomplete_expired")) == "starter"

    def test_active_trader_keeps_tier(self):
        assert _effective_tier(make_user("trader", stripe_status="active")) == "trader"

    def test_active_investor_keeps_tier(self):
        assert _effective_tier(make_user("investor", stripe_status="active")) == "investor"

    def test_no_stripe_status_keeps_tier(self):
        """No Stripe status = not subscribed via Stripe (e.g. manually assigned tier)."""
        assert _effective_tier(make_user("investor")) == "investor"

    def test_starter_no_stripe_status_stays_starter(self):
        assert _effective_tier(make_user("starter")) == "starter"

    def test_admin_ignores_inactive_stripe_status(self):
        """Admin override trumps Stripe downgrade."""
        u = make_user("starter", is_admin=True, stripe_status="canceled")
        assert _effective_tier(u) == "trader"


# ── Starter entitlements ──────────────────────────────────────────────────────

class TestStarterEntitlements:
    def test_has_core(self):
        assert has_feature(make_user("starter"), FEAT_REPORT_CORE)

    def test_has_sizing_summary(self):
        assert has_feature(make_user("starter"), FEAT_SIZING_SUMMARY)

    def test_lacks_pdf(self):
        assert not has_feature(make_user("starter"), FEAT_REPORT_PDF)

    def test_lacks_signal_metrics(self):
        assert not has_feature(make_user("starter"), FEAT_SIGNAL_METRICS)

    def test_lacks_stop_prob_detail(self):
        assert not has_feature(make_user("starter"), FEAT_STOP_PROB_DETAIL)

    def test_lacks_trade_setup(self):
        assert not has_feature(make_user("starter"), FEAT_REPORT_TRADE_SETUP)

    def test_lacks_engine_diagnostics(self):
        assert not has_feature(make_user("starter"), FEAT_ENGINE_DIAGNOSTICS)

    def test_lacks_scenario_weights(self):
        assert not has_feature(make_user("starter"), FEAT_SCENARIO_WEIGHTS)

    def test_lacks_multiplier_stack(self):
        assert not has_feature(make_user("starter"), FEAT_MULTIPLIER_STACK)

    def test_lacks_risk_matrix_full(self):
        assert not has_feature(make_user("starter"), FEAT_RISK_MATRIX_FULL)


# ── Investor entitlements ─────────────────────────────────────────────────────

class TestInvestorEntitlements:
    def test_inherits_core(self):
        assert has_feature(make_user("investor"), FEAT_REPORT_CORE)

    def test_inherits_sizing_summary(self):
        assert has_feature(make_user("investor"), FEAT_SIZING_SUMMARY)

    def test_has_pdf(self):
        assert has_feature(make_user("investor"), FEAT_REPORT_PDF)

    def test_has_signal_metrics(self):
        assert has_feature(make_user("investor"), FEAT_SIGNAL_METRICS)

    def test_has_stop_prob_detail(self):
        assert has_feature(make_user("investor"), FEAT_STOP_PROB_DETAIL)

    def test_lacks_trade_setup(self):
        assert not has_feature(make_user("investor"), FEAT_REPORT_TRADE_SETUP)

    def test_lacks_engine_diagnostics(self):
        assert not has_feature(make_user("investor"), FEAT_ENGINE_DIAGNOSTICS)

    def test_lacks_scenario_weights(self):
        assert not has_feature(make_user("investor"), FEAT_SCENARIO_WEIGHTS)

    def test_lacks_multiplier_stack(self):
        assert not has_feature(make_user("investor"), FEAT_MULTIPLIER_STACK)

    def test_lacks_risk_matrix_full(self):
        assert not has_feature(make_user("investor"), FEAT_RISK_MATRIX_FULL)


# ── Trader entitlements ───────────────────────────────────────────────────────

class TestTraderEntitlements:
    """Trader must have every single flag."""

    ALL_FLAGS = [
        FEAT_REPORT_CORE, FEAT_SIZING_SUMMARY, FEAT_REPORT_PDF,
        FEAT_SIGNAL_METRICS, FEAT_STOP_PROB_DETAIL, FEAT_REPORT_TRADE_SETUP,
        FEAT_ENGINE_DIAGNOSTICS, FEAT_SCENARIO_WEIGHTS,
        FEAT_MULTIPLIER_STACK, FEAT_RISK_MATRIX_FULL,
    ]

    @pytest.mark.parametrize("flag", ALL_FLAGS)
    def test_trader_has_flag(self, flag):
        assert has_feature(make_user("trader"), flag), f"Trader should have {flag}"


# ── Admin bypass ──────────────────────────────────────────────────────────────

class TestAdminBypass:
    """Admins get Trader-level access regardless of stored tier."""

    def test_admin_starter_gets_engine_diagnostics(self):
        assert has_feature(make_user("starter", is_admin=True), FEAT_ENGINE_DIAGNOSTICS)

    def test_admin_starter_gets_trade_setup(self):
        assert has_feature(make_user("starter", is_admin=True), FEAT_REPORT_TRADE_SETUP)

    def test_admin_investor_gets_multiplier_stack(self):
        assert has_feature(make_user("investor", is_admin=True), FEAT_MULTIPLIER_STACK)


# ── Stripe downgrade: feature revocation ─────────────────────────────────────

class TestStripeDowngrade:
    def test_canceled_investor_loses_pdf(self):
        u = make_user("investor", stripe_status="canceled")
        assert not has_feature(u, FEAT_REPORT_PDF)

    def test_canceled_investor_loses_signal_metrics(self):
        u = make_user("investor", stripe_status="canceled")
        assert not has_feature(u, FEAT_SIGNAL_METRICS)

    def test_canceled_trader_loses_engine_diagnostics(self):
        u = make_user("trader", stripe_status="canceled")
        assert not has_feature(u, FEAT_ENGINE_DIAGNOSTICS)

    def test_canceled_investor_keeps_core(self):
        """Downgraded to Starter still gets core."""
        u = make_user("investor", stripe_status="canceled")
        assert has_feature(u, FEAT_REPORT_CORE)

    def test_past_due_loses_paid_features(self):
        u = make_user("trader", stripe_status="past_due")
        assert not has_feature(u, FEAT_REPORT_PDF)
        assert not has_feature(u, FEAT_ENGINE_DIAGNOSTICS)

    def test_admin_ignores_canceled(self):
        u = make_user("investor", is_admin=True, stripe_status="canceled")
        assert has_feature(u, FEAT_ENGINE_DIAGNOSTICS)


# ── upgrade_hint() ────────────────────────────────────────────────────────────

class TestUpgradeHint:
    def test_core_requires_starter(self):
        assert upgrade_hint(FEAT_REPORT_CORE) == "starter"

    def test_sizing_requires_starter(self):
        assert upgrade_hint(FEAT_SIZING_SUMMARY) == "starter"

    def test_pdf_requires_investor(self):
        assert upgrade_hint(FEAT_REPORT_PDF) == "investor"

    def test_signal_metrics_requires_investor(self):
        assert upgrade_hint(FEAT_SIGNAL_METRICS) == "investor"

    def test_stop_prob_requires_investor(self):
        assert upgrade_hint(FEAT_STOP_PROB_DETAIL) == "investor"

    def test_engine_diagnostics_requires_trader(self):
        assert upgrade_hint(FEAT_ENGINE_DIAGNOSTICS) == "trader"

    def test_scenario_weights_requires_trader(self):
        assert upgrade_hint(FEAT_SCENARIO_WEIGHTS) == "trader"

    def test_multiplier_stack_requires_trader(self):
        assert upgrade_hint(FEAT_MULTIPLIER_STACK) == "trader"

    def test_risk_matrix_requires_trader(self):
        assert upgrade_hint(FEAT_RISK_MATRIX_FULL) == "trader"
