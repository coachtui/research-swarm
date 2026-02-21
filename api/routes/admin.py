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


# --- Endpoints ---

@router.get("/admin/metrics", response_model=PlatformMetrics)
async def get_platform_metrics(admin: User = Depends(require_admin)):
    """
    Get platform-wide usage metrics.

    Admin-only endpoint for monitoring overall platform health.
    """
    # Ensure fresh DB connection
    from api.lib.db import _db_client
    global _db_client
    try:
        db = await get_db()
        if not db.is_connected():
            await db.disconnect()
            await db.connect()
    except Exception:
        _db_client = None
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
    # Ensure fresh DB connection
    from api.lib.db import _db_client
    global _db_client
    try:
        db = await get_db()
        if not db.is_connected():
            await db.disconnect()
            await db.connect()
    except Exception:
        _db_client = None
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

    # Ensure fresh DB connection
    from api.lib.db import _db_client
    global _db_client
    try:
        db = await get_db()
        if not db.is_connected():
            await db.disconnect()
            await db.connect()
    except Exception:
        _db_client = None
        db = await get_db()

    # Check if user exists
    user = await db.user.find_unique(where={"id": user_id})
    if not user:
        raise HTTPException(404, "User not found")

    # Update tier
    updated_user = await db.user.update(
        where={"id": user_id},
        data={"tier": request.new_tier}
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
    # Ensure fresh DB connection
    from api.lib.db import _db_client
    global _db_client

    try:
        db = await get_db()
        if not db.is_connected():
            print("⚠️  DB connection closed, reconnecting...")
            await db.disconnect()
            await db.connect()
    except Exception as e:
        print(f"⚠️  DB connection error, forcing fresh connection: {e}")
        _db_client = None
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
    # Ensure fresh DB connection
    from api.lib.db import _db_client
    global _db_client
    try:
        db = await get_db()
        if not db.is_connected():
            await db.disconnect()
            await db.connect()
    except Exception:
        _db_client = None
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
