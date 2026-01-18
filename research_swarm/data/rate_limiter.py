"""
Rate limiting to respect API free tiers.
"""
import time
from functools import wraps
from collections import defaultdict
from datetime import datetime, timedelta
from research_swarm.logger import logger

class RateLimiter:
    """Simple rate limiter using token bucket algorithm."""

    def __init__(self):
        # Track calls per API
        self.call_counts = defaultdict(list)
        self.limits = {
            "fmp": {"calls": 250, "period": 86400},  # 250/day
            "sec": {"calls": 10, "period": 1},       # 10/second (be nice)
            "yfinance": {"calls": 2, "period": 1},   # 2/second (be respectful)
        }

    def check_limit(self, api: str) -> bool:
        """
        Check if API call is allowed under rate limit.

        Args:
            api: API name ('fmp', 'sec', etc.)

        Returns:
            True if call is allowed
        """
        if api not in self.limits:
            return True  # No limit configured

        limit = self.limits[api]
        now = datetime.now()
        cutoff = now - timedelta(seconds=limit["period"])

        # Remove old timestamps
        self.call_counts[api] = [
            ts for ts in self.call_counts[api] if ts > cutoff
        ]

        # Check if under limit
        if len(self.call_counts[api]) >= limit["calls"]:
            logger.warning(f"Rate limit reached for {api}")
            return False

        return True

    def record_call(self, api: str):
        """Record API call timestamp."""
        self.call_counts[api].append(datetime.now())

    def wait_if_needed(self, api: str):
        """Block until rate limit allows call."""
        while not self.check_limit(api):
            logger.info(f"Rate limited, waiting 1s...")
            time.sleep(1)
        self.record_call(api)

# Global instance
rate_limiter = RateLimiter()

def rate_limited(api: str):
    """Decorator to rate limit function calls."""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            rate_limiter.wait_if_needed(api)
            return func(*args, **kwargs)
        return wrapper
    return decorator
