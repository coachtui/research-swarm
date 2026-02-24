"""
Versioned entitlement configuration — entitlements.v1

Defines the complete feature-flag and numeric-limit matrix for every
subscription tier. This is the ONLY place tier capabilities are defined.
Application logic must never hardcode tier checks; always derive from here.

Tier progression:
  starter  → Awareness Engine        (observe, orient)
  investor → Decision Intelligence   (decide, size conceptually)
  trader   → Allocation & Execution  (deploy, manage capital)

Flag naming: domain.subdomain.action  (action ∈ {read,write,create,delete,export})
"""

ENTITLEMENT_VERSION = "entitlements.v1"

# ── Grace period ────────────────────────────────────────────────────────────
GRACE_PERIOD_DAYS = 3  # Days of access after payment failure before downgrade

# ── Subscription states that grant full tier access ─────────────────────────
ACTIVE_STATUSES = {"active", "trialing"}

# ── Subscription states that immediately revoke premium access ───────────────
UNPAID_STATUSES = {"unpaid", "uncollectible"}

# ── All known feature flags (exhaustive registry) ───────────────────────────
ALL_FLAGS = [
    # Report depth
    "report.snapshot.read",
    "report.full.read",
    # Signals
    "signals.divergence.read",
    # Scenarios
    "scenarios.basic.read",
    # Expected value
    "ev.summary.read",
    "ev.engine.read",
    # Probabilistic engine
    "probability.engine.read",
    # Risk diagnostics
    "risk.stopprob.read",
    "risk.stability.read",
    "risk.noise.read",
    "risk.efficiency.read",
    # Allocation / execution
    "allocation.sizing.write",
    # Portfolio
    "portfolio.risk.read",
    "portfolio.factors.read",
    "portfolio.correlation.read",
    # Monitoring
    "monitoring.trade.read",
]

# ── Starter flags ────────────────────────────────────────────────────────────
_STARTER_FLAGS: dict = {
    "report.snapshot.read":    True,
    "report.full.read":        False,
    "signals.divergence.read": True,
    "scenarios.basic.read":    True,
    "ev.summary.read":         True,
    "ev.engine.read":          False,
    "probability.engine.read": False,
    "risk.stopprob.read":      False,
    "risk.stability.read":     False,
    "risk.noise.read":         False,
    "risk.efficiency.read":    False,
    "allocation.sizing.write": False,
    "portfolio.risk.read":     False,
    "portfolio.factors.read":  False,
    "portfolio.correlation.read": False,
    "monitoring.trade.read":   False,
}

# ── Investor flags — all starter flags, plus decision-intelligence layer ─────
_INVESTOR_FLAGS: dict = {
    **_STARTER_FLAGS,
    "report.full.read":        True,
    "ev.engine.read":          True,
    "probability.engine.read": True,
    "risk.stopprob.read":      True,
    "risk.stability.read":     True,
    "risk.noise.read":         True,
    "risk.efficiency.read":    True,
}

# ── Trader flags — all investor flags, plus execution infrastructure ─────────
_TRADER_FLAGS: dict = {
    **_INVESTOR_FLAGS,
    "allocation.sizing.write":    True,
    "portfolio.risk.read":        True,
    "portfolio.factors.read":     True,
    "portfolio.correlation.read": True,
    "monitoring.trade.read":      True,
}

# ── Admin — unrestricted access to every flag ─────────────────────────────────
_ADMIN_FLAGS: dict = {flag: True for flag in ALL_FLAGS}

# ── Versioned tier config (single source of truth) ───────────────────────────
TIER_CONFIG: dict = {
    "version": ENTITLEMENT_VERSION,
    "tiers": {
        "starter": {
            "flags": _STARTER_FLAGS,
            "limits": {
                "limits.runs.daily":    10,
                "limits.history.days":  7,
            },
        },
        "investor": {
            "flags": _INVESTOR_FLAGS,
            "limits": {
                "limits.runs.daily":    50,
                "limits.history.days":  90,
            },
        },
        "trader": {
            "flags": _TRADER_FLAGS,
            "limits": {
                "limits.runs.daily":    250,
                "limits.history.days":  365,
            },
        },
    },
}

ADMIN_ENTITLEMENT: dict = {
    "flags":   _ADMIN_FLAGS,
    "limits":  {"limits.runs.daily": 9999, "limits.history.days": 9999},
    "version": ENTITLEMENT_VERSION,
}

# ── Public helpers ────────────────────────────────────────────────────────────

def get_flags_for_tier(tier: str) -> dict:
    """Return a copy of feature flags for a tier. Defaults to starter."""
    return dict(
        TIER_CONFIG["tiers"]
        .get(tier.lower(), TIER_CONFIG["tiers"]["starter"])["flags"]
    )


def get_limits_for_tier(tier: str) -> dict:
    """Return a copy of numeric limits for a tier. Defaults to starter."""
    return dict(
        TIER_CONFIG["tiers"]
        .get(tier.lower(), TIER_CONFIG["tiers"]["starter"])["limits"]
    )
