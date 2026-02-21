"""
Plan limits configuration for tier-based access control.
Defines quotas and features for Starter, Investor, and Trader tiers.
"""

from dataclasses import dataclass
from typing import Tuple


@dataclass
class PlanLimits:
    """
    Configuration for a subscription tier's limits and features.
    """
    analyses_per_month: int
    watchlist_max: int
    concurrent_analyses: int
    priority_queue: bool
    api_access: bool


# Tier limit definitions
TIER_LIMITS = {
    "starter": PlanLimits(
        analyses_per_month=5,    # Starter: $19.99/month for 5 reports
        watchlist_max=999,        # Unlimited watchlist for all tiers
        concurrent_analyses=2,
        priority_queue=True,
        api_access=True
    ),
    "investor": PlanLimits(
        analyses_per_month=15,   # Investor: $39.99/month for 15 reports
        watchlist_max=999,        # Unlimited watchlist for all tiers
        concurrent_analyses=3,
        priority_queue=True,
        api_access=True
    ),
    "trader": PlanLimits(
        analyses_per_month=50,   # Trader: $99.99/month for 50 reports
        watchlist_max=999,        # Unlimited watchlist for all tiers
        concurrent_analyses=5,
        priority_queue=True,
        api_access=True
    )
}


def get_tier_limits(tier: str) -> PlanLimits:
    """
    Get the plan limits for a given tier.

    Args:
        tier: The tier name (starter, investor, trader)

    Returns:
        PlanLimits configuration for the tier

    Defaults to starter tier if tier not found.
    """
    return TIER_LIMITS.get(tier.lower(), TIER_LIMITS["starter"])


def get_analyses_limit(tier: str) -> int:
    """Get monthly analysis limit for a tier."""
    return get_tier_limits(tier).analyses_per_month


def get_watchlist_limit(tier: str) -> int:
    """Get watchlist stock limit for a tier."""
    return get_tier_limits(tier).watchlist_max


def has_api_access(tier: str) -> bool:
    """Check if tier has API access."""
    return get_tier_limits(tier).api_access


def has_priority_queue(tier: str) -> bool:
    """Check if tier has priority queue access."""
    return get_tier_limits(tier).priority_queue
