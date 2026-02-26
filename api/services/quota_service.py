"""
Quota management service for enforcing plan limits.

Paid tiers (starter/investor/trader): monthly rolling quota via UsageQuota.
Free tier: lifetime credit quota via FreeReportCredit (2 total reports).

Anti-abuse:
  - Device-level tracking via DeviceFreeUsage (max 2 free reports per device).
  - Email verification required for free report #2.
  - Idempotency via UsageRecord (unique per generation_id/run_id).
"""

from datetime import datetime, timezone, timedelta
from typing import Tuple, Dict, Any
from calendar import monthrange

from api.lib.db import get_db
from api.lib.plan_limits import get_tier_limits

# Threshold above which we warn paid users they are approaching their limit
_WARN_THRESHOLD = 0.80  # 80%

# Maximum free reports per device before blocking additional accounts
_DEVICE_FREE_LIMIT = 2


def _get_month_start() -> datetime:
    """Get the start of the current month (UTC). Used as fallback when no billing period set."""
    now = datetime.now(timezone.utc)
    return now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)


def _get_month_end(start: datetime) -> datetime:
    """Get the end of the month for a given start date."""
    last_day = monthrange(start.year, start.month)[1]
    return start.replace(day=last_day, hour=23, minute=59, second=59, microsecond=999999)


# ── Free-tier helpers ─────────────────────────────────────────────────────────

async def get_or_create_free_credits(user_id: str):
    """
    Get or create the FreeReportCredit record for a free-tier user.

    Returns the record with creditsTotal / creditsUsed fields.
    """
    db = await get_db()
    credit = await db.freereportcredit.find_unique(where={"userId": user_id})
    if not credit:
        credit = await db.freereportcredit.create(
            data={"userId": user_id, "creditsTotal": 2, "creditsUsed": 0}
        )
    return credit


async def check_device_limit(device_id: str) -> bool:
    """
    Return True if the given device_id has exhausted the device-level free limit.

    Conservative threshold: _DEVICE_FREE_LIMIT reports across ALL accounts on this device.
    """
    if not device_id:
        return False
    db = await get_db()
    record = await db.devicefreeusage.find_unique(where={"deviceId": device_id})
    return bool(record and record.totalFreeReports >= _DEVICE_FREE_LIMIT)


async def increment_device_usage(device_id: str) -> None:
    """Increment the per-device free report counter."""
    if not device_id:
        return
    db = await get_db()
    existing = await db.devicefreeusage.find_unique(where={"deviceId": device_id})
    if existing:
        await db.devicefreeusage.update(
            where={"deviceId": device_id},
            data={
                "totalFreeReports": existing.totalFreeReports + 1,
                "lastUsedAt": datetime.now(timezone.utc),
            },
        )
    else:
        await db.devicefreeusage.create(
            data={
                "deviceId": device_id,
                "totalFreeReports": 1,
                "lastUsedAt": datetime.now(timezone.utc),
            }
        )


async def check_can_analyze_free(
    user_id: str,
    email_verified: bool,
    device_id: str = "",
) -> Tuple[bool, str, str]:
    """
    Check whether a free-tier user may generate a report.

    Returns:
        (can_proceed: bool, message: str, error_code: str)

    error_code values:
        ""                   – allowed
        "DEVICE_LIMIT"       – device has exceeded free report threshold
        "EMAIL_REQUIRED"     – report #2 needs verified email
        "CREDITS_EXHAUSTED"  – all 2 free reports used
    """
    # Account cycling detection: check device before granting credits
    if await check_device_limit(device_id):
        return (
            False,
            "Free trial limit reached on this device. Upgrade to continue.",
            "DEVICE_LIMIT",
        )

    credit = await get_or_create_free_credits(user_id)

    # Report #2 requires a verified email address
    if credit.creditsUsed >= 1 and not email_verified:
        return (
            False,
            "Verify your email to unlock your second free report.",
            "EMAIL_REQUIRED",
        )

    if credit.creditsUsed >= credit.creditsTotal:
        return (
            False,
            f"You've used all {credit.creditsTotal} free reports. Upgrade to continue.",
            "CREDITS_EXHAUSTED",
        )

    return True, "", ""


async def increment_free_credit_used(
    user_id: str,
    run_id: str,
    device_id: str = "",
) -> None:
    """
    Consume one free credit.

    Idempotent: a UsageRecord keyed on run_id prevents double-counting on
    retry or page refresh.  Also increments the device-level counter.
    """
    db = await get_db()

    # Idempotency guard — if a record already exists for this run, bail out
    existing = await db.usagerecord.find_unique(where={"generationId": run_id})
    if existing:
        return

    credit = await get_or_create_free_credits(user_id)
    await db.freereportcredit.update(
        where={"id": credit.id},
        data={"creditsUsed": credit.creditsUsed + 1},
    )
    await db.usagerecord.create(
        data={
            "generationId": run_id,
            "userId": user_id,
            "planAtTime": "free",
            "usageType": "free_credit",
        }
    )
    await increment_device_usage(device_id)


# ── Paid-tier helpers ─────────────────────────────────────────────────────────

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


async def check_can_analyze(
    user_id: str,
    tier: str,
    user_email: str = "",
    is_admin: bool = False,
    stripe_status: str = "",
    email_verified: bool = False,
    device_id: str = "",
) -> Tuple[bool, str]:
    """
    Check if user can run another analysis.

    For free-tier users this checks lifetime credits; for paid tiers it
    checks the monthly quota + Stripe subscription status.

    Returns:
        (can_proceed: bool, error_message: str)
    """
    print(
        f"🔍 check_can_analyze: user_email='{user_email}', tier='{tier}', "
        f"is_admin={is_admin}, stripe_status='{stripe_status}', "
        f"email_verified={email_verified}"
    )

    # Admins bypass all checks
    if is_admin:
        print(f"✅ Bypassing quota check for admin user: {user_email}")
        return True, ""

    # Free tier: credit-based gating
    if tier == "free":
        can, msg, _code = await check_can_analyze_free(user_id, email_verified, device_id)
        return can, msg

    # Paid tiers: require an active Stripe subscription
    _PAID_STATUSES = {"active", "trialing"}
    if stripe_status not in _PAID_STATUSES:
        print(f"❌ No active subscription for {user_email}: stripe_status='{stripe_status}'")
        return False, (
            "An active subscription is required to run analyses. "
            "Please purchase a plan at dvrg.io to get started."
        )

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


async def check_can_add_to_watchlist(
    user_id: str,
    tier: str,
    user_email: str = "",
    is_admin: bool = False,
) -> Tuple[bool, str]:
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

    # Free tier: use their own limit (5 max)
    if tier == "free":
        db = await get_db()
        count = await db.watchlist.count(where={"userId": user_id})
        limit = get_tier_limits("free").watchlist_max
        if count >= limit:
            return False, (
                f"Watchlist limit reached ({limit} stocks on Free plan). "
                f"Upgrade to Starter for unlimited watchlist slots."
            )
        return True, ""

    quota = await get_or_create_current_quota(user_id, tier)

    if quota.watchlistCount >= quota.watchlistLimit:
        return False, (
            f"Watchlist limit reached ({quota.watchlistLimit} stocks). "
            f"Upgrade to Investor or Trader for more slots."
        )

    return True, ""


async def increment_analysis_count(
    user_id: str,
    tier: str,
    run_id: str = "",
    device_id: str = "",
) -> None:
    """
    Record successful analysis completion.

    Free tier: consumes one lifetime credit (idempotent via UsageRecord).
    Paid tiers: increments monthly UsageQuota counter (also idempotent via UsageRecord).

    Args:
        user_id: User UUID
        tier: User tier at time of analysis
        run_id: Run UUID — used for idempotency
        device_id: Device identifier — used for device anti-abuse tracking on free tier
    """
    if tier == "free":
        if run_id:
            await increment_free_credit_used(user_id, run_id, device_id)
        return

    # Paid tier: idempotency check
    if run_id:
        db = await get_db()
        existing = await db.usagerecord.find_unique(where={"generationId": run_id})
        if existing:
            return  # Already counted
        await db.usagerecord.create(
            data={
                "generationId": run_id,
                "userId": user_id,
                "planAtTime": tier,
                "usageType": "monthly_report",
            }
        )

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
    if tier == "free":
        return  # Free tier uses live DB count, not UsageQuota
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
    if tier == "free":
        return  # Free tier uses live DB count
    quota = await get_or_create_current_quota(user_id, tier)
    db = await get_db()

    # Never go below 0
    new_count = max(0, quota.watchlistCount - 1)

    await db.usagequota.update(
        where={"id": quota.id},
        data={"watchlistCount": new_count}
    )


async def get_usage_summary(
    user_id: str,
    tier: str,
    stripe_status: str = "",
    is_admin: bool = False,
) -> Dict[str, Any]:
    """
    Get current usage summary for dashboard display.

    For free tier returns credit-based fields.
    For paid tiers returns monthly quota fields with an at_warning_threshold flag
    when usage has reached 80% of the monthly limit.

    Args:
        user_id: User UUID
        tier: User tier
        stripe_status: Stripe subscription status (for boost eligibility check)
        is_admin: If True, returns unlimited quota values

    Returns:
        Dict with usage stats including boost info and billing period
    """
    # ── Admin ──────────────────────────────────────────────────────────────────
    if is_admin:
        try:
            quota = await get_or_create_current_quota(
                user_id, tier if tier not in ("free",) else "starter"
            )
        except Exception:
            quota = None

        now = datetime.now(timezone.utc)
        period_end = getattr(quota, "periodEnd", now + timedelta(days=30))
        if hasattr(period_end, "tzinfo") and period_end.tzinfo is None:
            period_end = period_end.replace(tzinfo=timezone.utc)
        days_remaining = max(0, (period_end - now).days)

        return {
            "plan": "admin",
            "analyses_used": getattr(quota, "analysesUsed", 0),
            "analyses_limit": 9999,
            "boost_analyses_added": 0,
            "analyses_remaining": 9999,
            "watchlist_count": getattr(quota, "watchlistCount", 0),
            "watchlist_limit": 9999,
            "watchlist_remaining": 9999,
            "period_start": getattr(quota, "periodStart", now),
            "period_end": period_end,
            "billing_period_end": period_end,
            "days_remaining": days_remaining,
            "boost_eligible": False,
            "tier": tier,
            "is_free_tier": False,
            "at_warning_threshold": False,
            "report_credits_total": None,
            "report_credits_used": None,
            "report_credits_remaining": None,
        }

    # ── Free tier ──────────────────────────────────────────────────────────────
    if tier == "free":
        credit = await get_or_create_free_credits(user_id)
        credits_remaining = max(0, credit.creditsTotal - credit.creditsUsed)
        db = await get_db()
        wl_count = await db.watchlist.count(where={"userId": user_id})
        wl_limit = get_tier_limits("free").watchlist_max
        return {
            "plan": "free",
            "tier": "free",
            "is_free_tier": True,
            "report_credits_total": credit.creditsTotal,
            "report_credits_used": credit.creditsUsed,
            "report_credits_remaining": credits_remaining,
            # Aliases used by existing UI components
            "analyses_used": credit.creditsUsed,
            "analyses_limit": credit.creditsTotal,
            "analyses_remaining": credits_remaining,
            "period_start": None,
            "period_end": None,
            "billing_period_end": None,
            "days_remaining": None,
            "boost_eligible": False,
            "boost_analyses_added": 0,
            "watchlist_count": wl_count,
            "watchlist_limit": wl_limit,
            "watchlist_remaining": max(0, wl_limit - wl_count),
            "at_warning_threshold": False,
        }

    # ── Paid tiers ─────────────────────────────────────────────────────────────
    quota = await get_or_create_current_quota(user_id, tier)

    now = datetime.now(timezone.utc)
    period_end = quota.periodEnd
    if period_end.tzinfo is None:
        period_end = period_end.replace(tzinfo=timezone.utc)

    days_remaining = max(0, (period_end - now).days)
    boost_eligible = await check_boost_eligibility(user_id, stripe_status, tier) if stripe_status else False

    total_limit = quota.analysesLimit + quota.boostAnalysesAdded
    total_available = max(0, total_limit - quota.analysesUsed)

    # 80% warning threshold
    at_warning = (
        total_limit > 0
        and quota.analysesUsed / total_limit >= _WARN_THRESHOLD
        and total_available > 0
    )

    return {
        "plan": tier,
        "tier": tier,
        "is_free_tier": False,
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
        "at_warning_threshold": at_warning,
        "report_credits_total": None,
        "report_credits_used": None,
        "report_credits_remaining": None,
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
    if tier == "free":
        return  # Free tier always reads live from DB
    actual_count = await get_current_watchlist_size(user_id)
    quota = await get_or_create_current_quota(user_id, tier)
    db = await get_db()

    if quota.watchlistCount != actual_count:
        print(f"⚠️  Syncing watchlist count for user {user_id}: {quota.watchlistCount} → {actual_count}")
        await db.usagequota.update(
            where={"id": quota.id},
            data={"watchlistCount": actual_count}
        )
