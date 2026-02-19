"""
Quota management service for enforcing plan limits.
Tracks usage per month and validates against tier limits.
"""

from datetime import datetime, timezone
from typing import Tuple, Dict, Any
from calendar import monthrange

from api.lib.db import get_db
from api.lib.plan_limits import get_tier_limits


def _get_month_start() -> datetime:
    """Get the start of the current month (UTC)."""
    now = datetime.now(timezone.utc)
    return now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)


def _get_month_end(start: datetime) -> datetime:
    """Get the end of the month for a given start date."""
    last_day = monthrange(start.year, start.month)[1]
    return start.replace(day=last_day, hour=23, minute=59, second=59, microsecond=999999)


async def get_or_create_current_quota(user_id: str, tier: str):
    """
    Get or create UsageQuota record for the current month.

    Args:
        user_id: User UUID
        tier: User tier (free/pro/premium)

    Returns:
        UsageQuota record for current month
    """
    db = await get_db()

    # Calculate current month bounds
    period_start = _get_month_start()
    period_end = _get_month_end(period_start)

    # Try to find existing quota for this month
    quota = await db.usagequota.find_first(
        where={
            "userId": user_id,
            "periodStart": period_start
        }
    )

    # Create new quota if doesn't exist
    if not quota:
        limits = get_tier_limits(tier)
        quota = await db.usagequota.create(
            data={
                "userId": user_id,
                "periodStart": period_start,
                "periodEnd": period_end,
                "analysesUsed": 0,
                "watchlistCount": 0,
                "analysesLimit": limits.analyses_per_month,
                "watchlistLimit": limits.watchlist_max
            }
        )

    return quota


async def check_can_analyze(user_id: str, tier: str, user_email: str = "", is_admin: bool = False) -> Tuple[bool, str]:
    """
    Check if user can run another analysis.

    Args:
        user_id: User UUID
        tier: User tier
        user_email: User email (optional, for test account bypass)
        is_admin: Whether user is an admin (bypasses all limits)

    Returns:
        (can_proceed, error_message)
        - can_proceed: True if user has quota remaining
        - error_message: Empty if allowed, error message if denied
    """
    # Debug logging
    print(f"🔍 check_can_analyze: user_email='{user_email}', tier='{tier}', is_admin={is_admin}")

    # Bypass for admins - unlimited analyses
    if is_admin:
        print(f"✅ Bypassing quota check for admin user: {user_email}")
        return True, ""

    quota = await get_or_create_current_quota(user_id, tier)

    if quota.analysesUsed >= quota.analysesLimit:
        return False, (
            f"Monthly analysis limit reached ({quota.analysesLimit}). "
            f"Upgrade to Pro for 20 analyses/month or Premium for 50."
        )

    return True, ""


async def check_can_add_to_watchlist(user_id: str, tier: str, user_email: str = "", is_admin: bool = False) -> Tuple[bool, str]:
    """
    Check if user can add another stock to watchlist.

    Args:
        user_id: User UUID
        tier: User tier
        user_email: User email (optional, for test account bypass)
        is_admin: Whether user is an admin (bypasses all limits)

    Returns:
        (can_proceed, error_message)
    """
    # Debug logging
    print(f"🔍 check_can_add_to_watchlist: user_email='{user_email}', tier='{tier}', is_admin={is_admin}")

    # Bypass for admins - unlimited watchlist
    if is_admin:
        print(f"✅ Bypassing watchlist quota for admin user: {user_email}")
        return True, ""

    # Bypass payment wall for test account
    if user_email and user_email.lower() == "test@example.com":
        print(f"✅ Bypassing watchlist quota for test account: {user_email}")
        return True, ""

    quota = await get_or_create_current_quota(user_id, tier)

    if quota.watchlistCount >= quota.watchlistLimit:
        return False, (
            f"Watchlist limit reached ({quota.watchlistLimit} stocks). "
            f"Upgrade to Pro for 10 slots or Premium for unlimited."
        )

    return True, ""


async def increment_analysis_count(user_id: str, tier: str) -> None:
    """
    Increment analysis counter after successful analysis.

    Args:
        user_id: User UUID
        tier: User tier
    """
    quota = await get_or_create_current_quota(user_id, tier)
    db = await get_db()

    await db.usagequota.update(
        where={"id": quota.id},
        data={"analysesUsed": quota.analysesUsed + 1}
    )


async def increment_watchlist_count(user_id: str, tier: str) -> None:
    """
    Increment watchlist counter after adding stock.

    Args:
        user_id: User UUID
        tier: User tier
    """
    quota = await get_or_create_current_quota(user_id, tier)
    db = await get_db()

    await db.usagequota.update(
        where={"id": quota.id},
        data={"watchlistCount": quota.watchlistCount + 1}
    )


async def decrement_watchlist_count(user_id: str, tier: str) -> None:
    """
    Decrement watchlist counter after removing stock.

    Args:
        user_id: User UUID
        tier: User tier
    """
    quota = await get_or_create_current_quota(user_id, tier)
    db = await get_db()

    # Never go below 0
    new_count = max(0, quota.watchlistCount - 1)

    await db.usagequota.update(
        where={"id": quota.id},
        data={"watchlistCount": new_count}
    )


async def get_usage_summary(user_id: str, tier: str) -> Dict[str, Any]:
    """
    Get current usage summary for dashboard display.

    Args:
        user_id: User UUID
        tier: User tier

    Returns:
        Dict with usage stats:
        - analyses_used: Count of analyses this month
        - analyses_limit: Monthly limit
        - analyses_remaining: Remaining analyses
        - watchlist_count: Current watchlist size
        - watchlist_limit: Max watchlist size
        - watchlist_remaining: Remaining watchlist slots
        - period_start: Period start date
        - period_end: Period end date
        - tier: User tier
    """
    quota = await get_or_create_current_quota(user_id, tier)

    return {
        "analyses_used": quota.analysesUsed,
        "analyses_limit": quota.analysesLimit,
        "analyses_remaining": max(0, quota.analysesLimit - quota.analysesUsed),
        "watchlist_count": quota.watchlistCount,
        "watchlist_limit": quota.watchlistLimit,
        "watchlist_remaining": max(0, quota.watchlistLimit - quota.watchlistCount),
        "period_start": quota.periodStart,
        "period_end": quota.periodEnd,
        "tier": tier
    }


async def get_current_watchlist_size(user_id: str) -> int:
    """
    Get actual watchlist size from database.

    This is the source of truth for watchlist count.
    The UsageQuota.watchlistCount should be synced with this.

    Args:
        user_id: User UUID

    Returns:
        Number of stocks in user's watchlist
    """
    db = await get_db()

    count = await db.watchlist.count(
        where={"userId": user_id}
    )

    return count


async def sync_watchlist_count(user_id: str, tier: str) -> None:
    """
    Sync UsageQuota.watchlistCount with actual watchlist size.

    Call this periodically or when quota seems out of sync.

    Args:
        user_id: User UUID
        tier: User tier
    """
    actual_count = await get_current_watchlist_size(user_id)
    quota = await get_or_create_current_quota(user_id, tier)
    db = await get_db()

    if quota.watchlistCount != actual_count:
        print(f"⚠️  Syncing watchlist count for user {user_id}: {quota.watchlistCount} → {actual_count}")
        await db.usagequota.update(
            where={"id": quota.id},
            data={"watchlistCount": actual_count}
        )
