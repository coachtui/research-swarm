"""
Watchlist management endpoints.
"""

from fastapi import APIRouter, HTTPException, Depends
from datetime import datetime, timezone
from typing import Optional

from api.models.watchlist import (
    WatchlistItem,
    WatchlistResponse,
    AddToWatchlistRequest,
    UpdateNotesRequest,
    RefreshWatchlistResponse,
    WatchlistStatsResponse
)
from api.models.auth import User
from api.dependencies import get_current_user
from api.lib.db import get_db, save_analysis_result
from api.services.quota_service import (
    check_can_add_to_watchlist,
    check_can_analyze,
    increment_watchlist_count,
    decrement_watchlist_count,
    increment_analysis_count,
    get_usage_summary
)


router = APIRouter()


def _calculate_days_since(date: Optional[datetime]) -> Optional[int]:
    """Calculate days since a given date."""
    if not date:
        return None
    delta = datetime.now(timezone.utc) - date
    return delta.days


@router.get("/watchlist", response_model=WatchlistResponse)
async def get_watchlist(user: User = Depends(get_current_user)):
    """
    Get user's full watchlist with enriched data.

    Returns list of stocks with current scores, score changes, and metadata.
    """
    db = await get_db()

    items = await db.watchlist.find_many(
        where={"userId": user.id},
        order={"addedAt": "desc"}
    )

    # Check if user can refresh (has quota remaining)
    can_refresh, _ = await check_can_analyze(
        user.id,
        user.tier,
        user.email,
        user.is_admin,
        stripe_status=user.stripe_subscription_status or ""
    )

    # Enrich each item with calculated fields
    enriched_items = []
    for item in items:
        enriched = WatchlistItem(
            id=item.id,
            ticker=item.ticker,
            company_name=item.companyName,
            added_at=item.addedAt,
            last_checked_at=item.lastCheckedAt,
            initial_moat_score=item.initialMoatScore,
            latest_moat_score=item.latestMoatScore,
            score_change=item.scoreChange,
            latest_analysis_date=item.latestAnalysisDate,
            notes=item.notes,
            days_since_update=_calculate_days_since(item.latestAnalysisDate),
            can_refresh=can_refresh,
            initial_analysis_run_id=item.initialAnalysisRunId,
            latest_analysis_run_id=item.latestAnalysisRunId
        )
        enriched_items.append(enriched)

    return WatchlistResponse(items=enriched_items, total=len(enriched_items))


@router.post("/watchlist")
async def add_to_watchlist(
    request: AddToWatchlistRequest,
    user: User = Depends(get_current_user)
):
    """
    Add a stock to the user's watchlist.

    Enforces plan limits and creates default alert rule.
    """
    db = await get_db()

    # Normalize ticker to uppercase
    ticker = request.ticker.upper()

    # Check if already in watchlist
    existing = await db.watchlist.find_first(
        where={"userId": user.id, "ticker": ticker}
    )
    if existing:
        raise HTTPException(status_code=400, detail=f"{ticker} is already in your watchlist")

    # Check plan limits (admins bypass)
    can_add, error_msg = await check_can_add_to_watchlist(user.id, user.tier, user.email, user.is_admin)
    if not can_add:
        raise HTTPException(status_code=402, detail=error_msg)

    # Find most recent analysis for this ticker by this user
    latest_result = await db.stockresult.find_first(
        where={"userId": user.id, "ticker": ticker, "status": "completed"},
        order={"createdAt": "desc"}
    )

    # Create watchlist entry
    watchlist_item = await db.watchlist.create(
        data={
            "userId": user.id,
            "ticker": ticker,
            "companyName": request.company_name,
            "notes": request.notes,
            "initialMoatScore": latest_result.moatScore if latest_result else None,
            "initialAnalysisRunId": latest_result.runId if latest_result else None,
            "latestMoatScore": latest_result.moatScore if latest_result else None,
            "latestAnalysisRunId": latest_result.runId if latest_result else None,
            "latestAnalysisDate": latest_result.createdAt if latest_result else None,
            "scoreChange": 0.0
        }
    )

    # Increment quota counter
    await increment_watchlist_count(user.id, user.tier)

    # Create default alert rule (score change > 1.0 point)
    try:
        await db.alertrule.create(
            data={
                "userId": user.id,
                "ticker": ticker,
                "alertType": "score_change",
                "threshold": 1.0,
                "isActive": True
            }
        )
    except Exception as e:
        print(f"⚠️  Failed to create alert rule: {e}")

    return {
        "success": True,
        "item": {
            "id": watchlist_item.id,
            "ticker": watchlist_item.ticker,
            "company_name": watchlist_item.companyName,
            "added_at": watchlist_item.addedAt
        }
    }


@router.delete("/watchlist/{ticker}")
async def remove_from_watchlist(
    ticker: str,
    user: User = Depends(get_current_user)
):
    """
    Remove a stock from the watchlist.

    Also deletes associated alert rules.
    """
    db = await get_db()

    ticker = ticker.upper()

    # Delete watchlist item
    deleted = await db.watchlist.delete_many(
        where={"userId": user.id, "ticker": ticker}
    )

    if deleted == 0:
        raise HTTPException(status_code=404, detail=f"{ticker} not found in watchlist")

    # Delete associated alert rules
    try:
        await db.alertrule.delete_many(
            where={"userId": user.id, "ticker": ticker}
        )
    except Exception as e:
        print(f"⚠️  Failed to delete alert rules: {e}")

    # Decrement quota counter
    await decrement_watchlist_count(user.id, user.tier)

    return {"success": True, "ticker": ticker}


@router.post("/watchlist/{ticker}/refresh", response_model=RefreshWatchlistResponse)
async def refresh_watchlist_item(
    ticker: str,
    user: User = Depends(get_current_user)
):
    """
    Trigger new analysis to refresh a watchlist item.

    Runs full analysis, updates scores, and checks for alert triggers.
    """
    db = await get_db()

    ticker = ticker.upper()

    # Check if in watchlist
    watchlist_item = await db.watchlist.find_first(
        where={"userId": user.id, "ticker": ticker}
    )
    if not watchlist_item:
        raise HTTPException(status_code=404, detail=f"{ticker} not found in watchlist")

    # Check analysis quota
    can_analyze, error_msg = await check_can_analyze(user.id, user.tier, user.email, user.is_admin)
    if not can_analyze:
        raise HTTPException(status_code=402, detail=error_msg)

    # Trigger analysis (reuse existing analyze logic)
    from api.services.analysis_service import run_stock_analysis

    try:
        result = await run_stock_analysis(
            ticker=ticker,
            quarters=["Q4_2024", "Q1_2025", "Q2_2025", "Q3_2025"],
            news_days_back=30,
            user_id=user.id
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")

    if result['status'] != 'completed':
        error_msg = result.get('error_message', 'Analysis failed')
        raise HTTPException(status_code=500, detail=f"Analysis failed: {error_msg}")

    # Save to database
    saved = await save_analysis_result(user.id, ticker, result)

    # Update watchlist item with new score
    new_score = result.get('moat_score')
    old_score = watchlist_item.latestMoatScore or watchlist_item.initialMoatScore or 0.0
    score_change = (new_score - old_score) if new_score else 0.0

    await db.watchlist.update(
        where={"id": watchlist_item.id},
        data={
            "latestMoatScore": new_score,
            "latestAnalysisRunId": saved['run_id'],
            "latestAnalysisDate": datetime.now(timezone.utc),
            "lastCheckedAt": datetime.now(timezone.utc),
            "scoreChange": score_change
        }
    )

    # Check if score change triggers alert
    if abs(score_change) >= 1.0:
        await _trigger_score_change_alert(user, ticker, old_score, new_score, saved['run_id'])

    # Increment analysis counter
    await increment_analysis_count(user.id, user.tier)

    return RefreshWatchlistResponse(
        success=True,
        new_score=new_score,
        old_score=old_score,
        score_change=score_change,
        run_id=saved['run_id']
    )


@router.patch("/watchlist/{ticker}/notes")
async def update_notes(
    ticker: str,
    request: UpdateNotesRequest,
    user: User = Depends(get_current_user)
):
    """
    Update user notes for a watchlist item.
    """
    db = await get_db()

    ticker = ticker.upper()

    # Check if exists
    existing = await db.watchlist.find_first(
        where={"userId": user.id, "ticker": ticker}
    )
    if not existing:
        raise HTTPException(status_code=404, detail=f"{ticker} not found in watchlist")

    # Update notes
    await db.watchlist.update(
        where={"id": existing.id},
        data={"notes": request.notes}
    )

    return {"success": True, "ticker": ticker, "notes": request.notes}


@router.get("/usage")
async def get_usage(user: User = Depends(get_current_user)):
    """
    Get current usage and quota for the user.

    Returns analyses used/limit, boost info, watchlist count/limit, and billing period info.
    """
    try:
        # Fetch stripe status from DB for boost eligibility check
        db = await get_db()
        user_db = await db.user.find_unique(where={"id": user.id})
        stripe_status = (user_db.stripeSubscriptionStatus or "") if user_db else ""

        usage = await get_usage_summary(user.id, user.tier, stripe_status, is_admin=user.is_admin)
        return usage
    except Exception as e:
        print(f"❌ Error fetching usage for user {user.id}: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch usage data: {str(e)}"
        )


@router.get("/watchlist/stats", response_model=WatchlistStatsResponse)
async def get_watchlist_stats(user: User = Depends(get_current_user)):
    """
    Get dashboard statistics for watchlist.

    Returns counts, averages, and quota info.
    """
    db = await get_db()

    # Get watchlist items
    items = await db.watchlist.find_many(
        where={"userId": user.id}
    )

    # Calculate stats
    count = len(items)
    scores = [item.latestMoatScore for item in items if item.latestMoatScore is not None]
    avg_score = sum(scores) / len(scores) if scores else None

    # Count items needing refresh (>7 days old)
    needs_refresh = sum(
        1 for item in items
        if item.latestAnalysisDate and _calculate_days_since(item.latestAnalysisDate) > 7
    )

    # Get quota info for limit
    usage = await get_usage_summary(user.id, user.tier)

    return WatchlistStatsResponse(
        watchlist_count=count,
        watchlist_limit=usage['watchlist_limit'],
        avg_score=round(avg_score, 1) if avg_score else None,
        divergence_count=0,  # TODO: Track divergence when analysis includes it
        needs_refresh_count=needs_refresh
    )


async def _trigger_score_change_alert(user: User, ticker: str, old_score: float, new_score: float, run_id: str):
    """
    Internal helper to trigger and log score change alert.

    Checks user preferences and alert rules before sending.
    """
    db = await get_db()

    # Check if user has alerts enabled
    try:
        prefs = await db.userpreferences.find_unique(where={"userId": user.id})
        if prefs and not prefs.emailAlerts:
            return  # User disabled alerts
    except Exception:
        pass  # If preferences don't exist, assume alerts are enabled

    # Check if alert rule is active
    alert_rule = await db.alertrule.find_first(
        where={
            "userId": user.id,
            "ticker": ticker,
            "alertType": "score_change",
            "isActive": True
        }
    )
    if not alert_rule:
        return  # No active rule

    # Send email alert
    from api.services.email_service import send_score_change_alert

    email_sent = False
    email_error = None

    try:
        success, error = await send_score_change_alert(
            user.email, ticker, old_score, new_score, run_id
        )
        email_sent = success
        email_error = error if not success else None

        if success:
            print(f"✅ Alert email sent to {user.email} for {ticker}")
        else:
            print(f"❌ Alert email failed for {user.email}: {error}")
    except Exception as e:
        email_error = str(e)
        print(f"❌ Exception sending alert: {e}")

    # Log alert to history
    try:
        await db.alerthistory.create(
            data={
                "userId": user.id,
                "ticker": ticker,
                "alertType": "score_change",
                "message": f"Score changed from {old_score:.1f} to {new_score:.1f}",
                "runId": run_id,
                "emailSent": email_sent,
                "emailError": email_error
            }
        )
    except Exception as e:
        print(f"⚠️  Failed to log alert: {e}")
