"""
Admin dashboard endpoints for platform management.
"""

from fastapi import APIRouter, HTTPException, Depends
from datetime import datetime, timezone, timedelta
from typing import Optional, List
from pydantic import BaseModel

from api.models.auth import User
from api.dependencies import require_admin
from api.lib.db import get_db


router = APIRouter()


# --- Response Models ---

class PlatformMetrics(BaseModel):
    """Platform-wide metrics for admin dashboard."""
    users: dict
    analyses: dict
    watchlist_adoption_rate: float


class UserWithUsage(BaseModel):
    """User with usage statistics."""
    id: str
    email: str
    full_name: Optional[str]
    tier: str
    is_active: bool
    is_admin: bool
    created_at: datetime
    watchlist_count: int
    analyses_used: int
    analyses_limit: int


class AnalysisRecord(BaseModel):
    """Analysis record for admin view."""
    run_id: str
    user_email: str
    ticker: str
    status: str
    moat_score: Optional[float]
    created_at: datetime
    cost_usd: float


class CostSummary(BaseModel):
    """Cost summary by time period for admin dashboard."""
    today: float
    week: float
    month: float
    year: float
    all_time: float
    analyses_today: int
    analyses_week: int
    analyses_month: int
    analyses_year: int
    analyses_all_time: int


class UpdateTierRequest(BaseModel):
    """Request to update user tier."""
    new_tier: str


class DailyCostPoint(BaseModel):
    date: str          # YYYY-MM-DD
    cost_usd: float
    analyses: int


class MonthlyCostPoint(BaseModel):
    month: str         # YYYY-MM
    cost_usd: float
    analyses: int
    estimated_revenue: float


class RevenueTimeSeries(BaseModel):
    daily: List[DailyCostPoint]          # last 30 days
    monthly: List[MonthlyCostPoint]      # last 12 months
    estimated_mrr: float                 # current MRR from active subscribers
    current_month_cost: float
    current_month_profit: float          # MRR - current month cost
    profit_margin_pct: float             # profit / MRR × 100
    tier_breakdown: dict                 # {tier: {users, monthly_revenue}}


# --- Endpoints ---

@router.get("/admin/metrics", response_model=PlatformMetrics)
async def get_platform_metrics(admin: User = Depends(require_admin)):
    """
    Get platform-wide usage metrics.

    Admin-only endpoint for monitoring overall platform health.
    """
    db = await get_db()

    # User counts by tier
    total_users = await db.user.count()
    starter_users = await db.user.count(where={"tier": "starter"})
    investor_users = await db.user.count(where={"tier": "investor"})
    trader_users = await db.user.count(where={"tier": "trader"})
    free_users = await db.user.count(where={"tier": "free"})  # legacy count

    # Analysis counts
    total_analyses = await db.stockresult.count(where={"status": "completed"})

    # Get analyses from today (midnight UTC)
    today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    analyses_today = await db.stockresult.count(where={
        "status": "completed",
        "createdAt": {"gte": today_start}
    })

    # Watchlist adoption (users who have at least one watchlist item)
    watchlist_items = await db.watchlist.find_many()
    unique_users_with_watchlist = set([item.userId for item in watchlist_items])
    watchlist_adoption_rate = len(unique_users_with_watchlist) / total_users if total_users > 0 else 0

    return PlatformMetrics(
        users={
            "total": total_users,
            "free": free_users,
            "starter": starter_users,
            "investor": investor_users,
            "trader": trader_users
        },
        analyses={
            "total": total_analyses,
            "today": analyses_today
        },
        watchlist_adoption_rate=watchlist_adoption_rate
    )


@router.get("/admin/users")
async def list_all_users(
    admin: User = Depends(require_admin),
    limit: int = 50,
    offset: int = 0
):
    """
    List all users with usage statistics.

    Admin-only endpoint for user management.
    """
    db = await get_db()

    # Get users
    users = await db.user.find_many(
        skip=offset,
        take=limit,
        order={"createdAt": "desc"}
    )

    # Enrich each user with usage stats
    enriched_users = []
    for user in users:
        # Get current month quota
        from api.services.quota_service import get_or_create_current_quota
        quota = await get_or_create_current_quota(user.id, user.tier)

        enriched_users.append(UserWithUsage(
            id=user.id,
            email=user.email,
            full_name=user.fullName,
            tier=user.tier,
            is_active=user.isActive,
            is_admin=user.isAdmin,
            created_at=user.createdAt,
            watchlist_count=quota.watchlistCount,
            analyses_used=quota.analysesUsed,
            analyses_limit=quota.analysesLimit
        ))

    total_count = await db.user.count()

    return {
        "users": enriched_users,
        "total": total_count,
        "limit": limit,
        "offset": offset
    }


@router.patch("/admin/users/{user_id}/tier")
async def update_user_tier(
    user_id: str,
    request: UpdateTierRequest,
    admin: User = Depends(require_admin)
):
    """
    Update a user's subscription tier.

    Admin-only endpoint for manual tier management.
    """
    if request.new_tier not in ["starter", "investor", "trader"]:
        raise HTTPException(400, "Invalid tier. Must be one of: starter, investor, trader")

    db = await get_db()

    # Check if user exists
    user = await db.user.find_unique(where={"id": user_id})
    if not user:
        raise HTTPException(404, "User not found")

    # Update tier and mark subscription as active (admin-granted access bypasses Stripe)
    updated_user = await db.user.update(
        where={"id": user_id},
        data={
            "tier": request.new_tier,
            "stripeSubscriptionStatus": "active",
        }
    )

    return {
        "success": True,
        "user": {
            "id": updated_user.id,
            "email": updated_user.email,
            "tier": updated_user.tier
        }
    }


@router.get("/admin/analyses")
async def list_all_analyses(
    admin: User = Depends(require_admin),
    limit: int = 100,
    ticker: Optional[str] = None
):
    """
    View all analyses across users.

    Admin-only endpoint for QA and monitoring.
    """
    db = await get_db()

    try:
        # Build where clause
        where = {"status": "completed"}
        if ticker:
            where["ticker"] = ticker.upper()

        # Get analyses with user info (include run relation to get user email)
        results = await db.stockresult.find_many(
            where=where,
            take=limit,
            include={
                "run": {
                    "include": {
                        "user": True
                    }
                }
            },
            order={"createdAt": "desc"}
        )

        # Format response
        analyses = []
        for result in results:
            analyses.append(AnalysisRecord(
                run_id=result.runId,
                user_email=result.run.user.email if result.run and result.run.user else "Unknown",
                ticker=result.ticker,
                status=result.status,
                moat_score=result.moatScore,
                created_at=result.createdAt,
                cost_usd=result.costUsd
            ))

        return {"analyses": analyses, "total": len(analyses)}

    except Exception as e:
        print(f"❌ Error fetching admin analyses: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch analyses: {str(e)}"
        )


@router.get("/admin/costs", response_model=CostSummary)
async def get_cost_summary(admin: User = Depends(require_admin)):
    """
    Get cost summary across different time periods.

    Admin-only endpoint for tracking platform costs per run.
    Returns running tallies for today, week, month, year, and all-time.
    """
    db = await get_db()

    # Calculate time boundaries
    now = datetime.now(timezone.utc)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    week_start = today_start - timedelta(days=now.weekday())
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    year_start = now.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)

    # Fetch all completed analyses once (more efficient than multiple queries)
    all_results = await db.stockresult.find_many(
        where={"status": "completed"}
    )

    # Filter results by time period in Python
    today_results = [r for r in all_results if r.createdAt >= today_start]
    week_results = [r for r in all_results if r.createdAt >= week_start]
    month_results = [r for r in all_results if r.createdAt >= month_start]
    year_results = [r for r in all_results if r.createdAt >= year_start]

    # Calculate costs and counts
    today_cost = sum(r.costUsd or 0 for r in today_results)
    analyses_today = len(today_results)

    week_cost = sum(r.costUsd or 0 for r in week_results)
    analyses_week = len(week_results)

    month_cost = sum(r.costUsd or 0 for r in month_results)
    analyses_month = len(month_results)

    year_cost = sum(r.costUsd or 0 for r in year_results)
    analyses_year = len(year_results)

    all_time_cost = sum(r.costUsd or 0 for r in all_results)

    return CostSummary(
        today=today_cost,
        week=week_cost,
        month=month_cost,
        year=year_cost,
        all_time=all_time_cost,
        analyses_today=analyses_today,
        analyses_week=analyses_week,
        analyses_month=analyses_month,
        analyses_year=analyses_year,
        analyses_all_time=len(all_results)
    )


# Subscription pricing by tier (USD/month)
_TIER_PRICE = {
    "starter": 19.99,
    "investor": 39.99,
    "trader": 99.99,
    "free": 0.0,
}


@router.get("/admin/revenue", response_model=RevenueTimeSeries)
async def get_revenue_timeseries(admin: User = Depends(require_admin)):
    """
    Revenue and profit timeseries for the admin dashboard.

    Returns daily AI costs (last 30 days), monthly cost/revenue (last 12 months),
    and estimated MRR derived from active subscriber tier counts.
    """
    from collections import defaultdict

    db = await get_db()

    now = datetime.now(timezone.utc)

    # ── 1. Fetch all completed results ──────────────────────────────────────
    cutoff_30d = now - timedelta(days=30)
    cutoff_12m = now - timedelta(days=365)

    all_results = await db.stockresult.find_many(
        where={"status": "completed", "createdAt": {"gte": cutoff_12m}}
    )

    # ── 2. Daily aggregation (last 30 days) ─────────────────────────────────
    daily_buckets: dict = defaultdict(lambda: {"cost_usd": 0.0, "analyses": 0})
    for r in all_results:
        if r.createdAt >= cutoff_30d:
            day_key = r.createdAt.strftime("%Y-%m-%d")
            daily_buckets[day_key]["cost_usd"] += r.costUsd or 0.0
            daily_buckets[day_key]["analyses"] += 1

    # Fill every day in the window even if no data
    daily_points: list[DailyCostPoint] = []
    for offset_days in range(29, -1, -1):
        d = (now - timedelta(days=offset_days)).strftime("%Y-%m-%d")
        bucket = daily_buckets.get(d, {"cost_usd": 0.0, "analyses": 0})
        daily_points.append(DailyCostPoint(
            date=d,
            cost_usd=round(bucket["cost_usd"], 4),
            analyses=bucket["analyses"],
        ))

    # ── 3. Monthly aggregation (last 12 months) ──────────────────────────────
    monthly_buckets: dict = defaultdict(lambda: {"cost_usd": 0.0, "analyses": 0})
    for r in all_results:
        month_key = r.createdAt.strftime("%Y-%m")
        monthly_buckets[month_key]["cost_usd"] += r.costUsd or 0.0
        monthly_buckets[month_key]["analyses"] += 1

    # Collect last 12 calendar months
    monthly_points: list[MonthlyCostPoint] = []
    for offset_months in range(11, -1, -1):
        # Step back by offset_months months
        target = now.replace(day=1) - timedelta(days=offset_months * 30)
        month_key = target.strftime("%Y-%m")
        bucket = monthly_buckets.get(month_key, {"cost_usd": 0.0, "analyses": 0})
        monthly_points.append(MonthlyCostPoint(
            month=month_key,
            cost_usd=round(bucket["cost_usd"], 4),
            analyses=bucket["analyses"],
            estimated_revenue=0.0,  # filled in step 4
        ))

    # ── 4. MRR from active subscriber counts ────────────────────────────────
    users_by_tier: dict[str, int] = {}
    for tier in _TIER_PRICE:
        users_by_tier[tier] = await db.user.count(where={"tier": tier})

    tier_breakdown = {}
    estimated_mrr = 0.0
    for tier, price in _TIER_PRICE.items():
        count = users_by_tier.get(tier, 0)
        monthly_rev = round(count * price, 2)
        estimated_mrr += monthly_rev
        tier_breakdown[tier] = {"users": count, "monthly_revenue": monthly_rev}

    estimated_mrr = round(estimated_mrr, 2)

    # Back-fill estimated_revenue into monthly points
    # (We approximate: each historical month has the same MRR as today.
    #  Accurate historical MRR would require a payment-event table.)
    for mp in monthly_points:
        mp.estimated_revenue = estimated_mrr

    # ── 5. Current month profit ──────────────────────────────────────────────
    current_month_key = now.strftime("%Y-%m")
    current_month_cost = round(
        monthly_buckets.get(current_month_key, {}).get("cost_usd", 0.0), 4
    )
    current_month_profit = round(estimated_mrr - current_month_cost, 2)
    profit_margin_pct = (
        round(current_month_profit / estimated_mrr * 100, 1) if estimated_mrr > 0 else 0.0
    )

    return RevenueTimeSeries(
        daily=daily_points,
        monthly=monthly_points,
        estimated_mrr=estimated_mrr,
        current_month_cost=current_month_cost,
        current_month_profit=current_month_profit,
        profit_margin_pct=profit_margin_pct,
        tier_breakdown=tier_breakdown,
    )


# ── Public example report management ─────────────────────────────────────────

class SetPublicExampleRequest(BaseModel):
    """Mark a stock result as the public example for its ticker."""
    result_id: str


@router.post("/admin/example-report/approve")
async def approve_public_example(
    request: SetPublicExampleRequest,
    admin: User = Depends(require_admin),
):
    """
    Mark a completed stock result as the public example shown on the landing page.

    Clears the flag on any prior approved result for the same ticker first,
    so at most one result per ticker is the active example at any time.

    Admin-only.
    """
    db = await get_db()

    # Fetch the target result
    result = await db.stockresult.find_first(
        where={"id": request.result_id, "status": "completed"},
    )
    if not result:
        raise HTTPException(status_code=404, detail="Completed stock result not found")

    # Clear any existing public example for the same ticker
    await db.stockresult.update_many(
        where={"ticker": result.ticker, "isPublicExample": True},
        data={"isPublicExample": False},
    )

    # Set the new example
    updated = await db.stockresult.update(
        where={"id": request.result_id},
        data={"isPublicExample": True},
    )

    return {
        "ok": True,
        "result_id": updated.id,
        "ticker": updated.ticker,
        "created_at": updated.createdAt,
    }


@router.delete("/admin/example-report/{ticker}")
async def clear_public_example(
    ticker: str,
    admin: User = Depends(require_admin),
):
    """
    Remove the public-example flag for a ticker.

    After this call the landing page preview falls back to the most recent
    completed run for that ticker.

    Admin-only.
    """
    ticker = ticker.upper()
    db = await get_db()

    cleared = await db.stockresult.update_many(
        where={"ticker": ticker, "isPublicExample": True},
        data={"isPublicExample": False},
    )

    return {"ok": True, "ticker": ticker, "cleared": cleared.count}
