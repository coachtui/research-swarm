"""
Plan limits configuration for tier-based access control.
Defines quotas and features for Free, Pro, and Premium tiers.
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
    # Free tier temporarily disabled
    # "free": PlanLimits(
    #     analyses_per_month=3,
    #     watchlist_max=999,
    #     concurrent_analyses=1,
    #     priority_queue=False,
    #     api_access=False
    # ),
    "pro": PlanLimits(
        analyses_per_month=10,  # Pro: $19.99/month for 10 reports
        watchlist_max=999,  # Unlimited watchlist for all tiers
        concurrent_analyses=3,
        priority_queue=True,
        api_access=True
    ),
    "premium": PlanLimits(
        analyses_per_month=30,  # Premium: $49.99/month for 30 reports
        watchlist_max=999,  # Unlimited watchlist for all tiers
        concurrent_analyses=5,
        priority_queue=True,
        api_access=True
    )
}


def get_tier_limits(tier: str) -> PlanLimits:
    """
    Get the plan limits for a given tier.

    Args:
        tier: The tier name (pro, premium)

    Returns:
        PlanLimits configuration for the tier

    Defaults to pro tier if tier not found (free tier disabled).
    """
    return TIER_LIMITS.get(tier.lower(), TIER_LIMITS["pro"])


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
