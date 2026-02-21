"""
Quota management service for enforcing plan limits.
Tracks usage per billing period and validates against tier limits.
Supports 30-day rolling billing periods (set by Stripe) and boost purchases.
"""

from datetime import datetime, timezone, timedelta
from typing import Tuple, Dict, Any
from calendar import monthrange

from api.lib.db import get_db
from api.lib.plan_limits import get_tier_limits


def _get_month_start() -> datetime:
    """Get the start of the current month (UTC). Used as fallback when no billing period set."""
    now = datetime.now(timezone.utc)
    return now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)


def _get_month_end(start: datetime) -> datetime:
    """Get the end of the month for a given start date."""
    last_day = monthrange(start.year, start.month)[1]
    return start.replace(day=last_day, hour=23, minute=59, second=59, microsecond=999999)


async def get_or_create_current_quota(user_id: str, tier: str):
    """
    Get or create UsageQuota record for the current billing period.

    For users with an active Stripe subscription, uses the 30-day rolling
    billing period set by Stripe webhooks (User.billingPeriodStart/End).
    Falls back to calendar month for users without a billing period set.

    Args:
        user_id: User UUID
        tier: User tier (starter/investor/trader)

    Returns:
        UsageQuota record for current billing period
    """
    db = await get_db()

    # Fetch user to get their billing period
    user = await db.user.find_unique(where={"id": user_id})

    now = datetime.now(timezone.utc)

    if user and user.billingPeriodStart and user.billingPeriodEnd:
        period_start = user.billingPeriodStart
        # Ensure timezone-aware comparison
        if period_start.tzinfo is None:
            period_start = period_start.replace(tzinfo=timezone.utc)
        period_end = user.billingPeriodEnd
        if period_end.tzinfo is None:
            period_end = period_end.replace(tzinfo=timezone.utc)
    else:
        # Fallback: calendar month for users without a subscription billing period
        period_start = _get_month_start()
        period_end = _get_month_end(period_start)

    # Try to find existing quota for this billing period
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
                "boostAnalysesAdded": 0,
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
    print(f"🔍 check_can_analyze: user_email='{user_email}', tier='{tier}', is_admin={is_admin}")

    # Bypass for admins - unlimited analyses
    if is_admin:
        print(f"✅ Bypassing quota check for admin user: {user_email}")
        return True, ""

    quota = await get_or_create_current_quota(user_id, tier)

    total_available = quota.analysesLimit + quota.boostAnalysesAdded - quota.analysesUsed

    if total_available <= 0:
        period_end = quota.periodEnd
        if period_end.tzinfo is None:
            period_end = period_end.replace(tzinfo=timezone.utc)
        reset_date = period_end.strftime("%b %d, %Y")
        total = quota.analysesLimit + quota.boostAnalysesAdded
        return False, (
            f"You've used all {total} analyses this period (resets {reset_date}). "
            f"Buy a Boost to add 5 more, or upgrade your plan."
        )

    return True, ""


async def check_boost_eligibility(user_id: str, stripe_status: str, tier: str) -> bool:
    """
    Check if a user is eligible to purchase a Boost.

    Boost is only available to:
    - Active paid subscribers (not canceled or past_due)
    - Users who have used at least 1 analysis this period

    Args:
        user_id: User UUID
        stripe_status: Stripe subscription status (active, past_due, canceled, etc.)
        tier: User tier

    Returns:
        True if user can buy boost
    """
    if stripe_status != "active":
        return False

    quota = await get_or_create_current_quota(user_id, tier)
    return quota.analysesUsed >= 1


async def add_boost_analyses(user_id: str, tier: str, count: int = 5) -> None:
    """
    Add boost analyses to user's current billing period quota.

    Args:
        user_id: User UUID
        tier: User tier
        count: Number of analyses to add (default 5)
    """
    quota = await get_or_create_current_quota(user_id, tier)
    db = await get_db()

    await db.usagequota.update(
        where={"id": quota.id},
        data={"boostAnalysesAdded": quota.boostAnalysesAdded + count}
    )


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
            f"Upgrade to Investor or Trader for more slots."
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


async def get_usage_summary(user_id: str, tier: str, stripe_status: str = "") -> Dict[str, Any]:
    """
    Get current usage summary for dashboard display.

    Args:
        user_id: User UUID
        tier: User tier
        stripe_status: Stripe subscription status (for boost eligibility check)

    Returns:
        Dict with usage stats including boost info and billing period
    """
    quota = await get_or_create_current_quota(user_id, tier)

    now = datetime.now(timezone.utc)
    period_end = quota.periodEnd
    if period_end.tzinfo is None:
        period_end = period_end.replace(tzinfo=timezone.utc)

    days_remaining = max(0, (period_end - now).days)
    total_available = max(0, quota.analysesLimit + quota.boostAnalysesAdded - quota.analysesUsed)
    boost_eligible = await check_boost_eligibility(user_id, stripe_status, tier) if stripe_status else False

    return {
        "analyses_used": quota.analysesUsed,
        "analyses_limit": quota.analysesLimit,
        "boost_analyses_added": quota.boostAnalysesAdded,
        "analyses_remaining": total_available,
        "watchlist_count": quota.watchlistCount,
        "watchlist_limit": quota.watchlistLimit,
        "watchlist_remaining": max(0, quota.watchlistLimit - quota.watchlistCount),
        "period_start": quota.periodStart,
        "period_end": quota.periodEnd,
        "billing_period_end": quota.periodEnd,
        "days_remaining": days_remaining,
        "boost_eligible": boost_eligible,
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
