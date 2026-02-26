"""
Analysis endpoints for triggering stock analysis jobs.
"""

import asyncio
import traceback
from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks, Header
from typing import Optional

from api.models.requests import AnalyzeRequest
from api.models.responses import AnalyzeResponse, JobStatus
from api.dependencies import get_current_user
from api.lib.entitlement_middleware import require_limit
from api.lib.entitlement_resolver import EntitlementContext
from api.models.auth import User
from api.services.analysis_service import run_stock_analysis
from api.lib.db import save_analysis_result, create_pending_run, update_run_failed, get_db
from api.services.quota_service import check_can_analyze, increment_analysis_count

router = APIRouter()

# Window in which a completed analysis for the same user+ticker is reused (no credit consumed)
_DEDUP_WINDOW_MINUTES = 60


async def _find_recent_completed_run(user_id: str, ticker: str) -> Optional[str]:
    """
    Return the run_id of a completed analysis for the same user+ticker within
    the deduplication window, or None if no such run exists.

    This prevents charging a credit when the same ticker is re-submitted within
    the configured window (default 60 minutes).
    """
    db = await get_db()
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=_DEDUP_WINDOW_MINUTES)
    recent = await db.run.find_first(
        where={
            "userId": user_id,
            "status": "completed",
            "createdAt": {"gte": cutoff},
            "stockResults": {
                "some": {
                    "ticker": ticker.upper(),
                    "status": "completed",
                }
            },
        },
        order={"createdAt": "desc"},
    )
    return recent.id if recent else None


async def _run_analysis_background(
    run_id: str,
    user_id: str,
    user_tier: str,
    ticker: str,
    quarters: list,
    news_days_back: int,
    device_id: str = "",
):
    """
    Background task: run the full analysis and save result to DB.

    Runs after the HTTP response has already been returned to the client.
    The client polls GET /api/runs/{run_id} to check status.

    On success, increments the usage counter (idempotent via UsageRecord).
    On failure, does NOT decrement or consume any credit.
    """
    print(f"🚀 [BG] Starting analysis for {ticker} (run_id={run_id})")
    try:
        result = await run_stock_analysis(
            ticker=ticker,
            quarters=quarters,
            news_days_back=news_days_back,
            user_id=user_id
        )
        print(f"✅ [BG] Analysis complete for {ticker}, status: {result['status']}")

        if result['status'] == 'completed':
            await save_analysis_result(
                user_id=user_id,
                ticker=ticker,
                result=result,
                run_id=run_id
            )
            print(f"💾 [BG] Saved {ticker} to database")
            try:
                await increment_analysis_count(
                    user_id,
                    user_tier,
                    run_id=run_id,
                    device_id=device_id,
                )
            except Exception as quota_error:
                print(f"⚠️  [BG] Failed to increment quota: {quota_error}")
        else:
            error_msg = result.get('error_message', 'Analysis failed')
            print(f"❌ [BG] Analysis failed for {ticker}: {error_msg}")
            await update_run_failed(run_id, error_msg)

    except Exception as e:
        print(f"❌ [BG] Unhandled error for {ticker}: {e}")
        traceback.print_exc()
        try:
            await update_run_failed(run_id, str(e))
        except Exception as db_err:
            print(f"❌ [BG] Also failed to update run status: {db_err}")


@router.post("/analyze", response_model=AnalyzeResponse)
async def analyze_stock(
    request: AnalyzeRequest,
    background_tasks: BackgroundTasks,
    user: User = Depends(get_current_user),
    # Daily limit guard — increments UsageCounter on success, 429 if exceeded
    _ent: EntitlementContext = Depends(require_limit("limits.runs.daily")),
    # Device identifier for free-tier anti-abuse (set by frontend in localStorage)
    x_device_id: Optional[str] = Header(None, alias="X-Device-ID"),
):
    """
    Trigger a single stock analysis.

    Returns immediately with a run_id. The analysis runs as a background task.
    Poll GET /api/runs/{run_id} to check status and retrieve results.

    **Authentication required**: Bearer token (Clerk JWT)

    **Rate limits** (enforced by entitlement engine, per UTC day):
    - Starter tier:  10 runs/day
    - Investor tier: 50 runs/day
    - Trader tier:   250 runs/day

    **Free tier**:
    - 2 lifetime report credits total.
    - Report #1 allowed immediately; report #2 requires email verification.
    - Same-ticker deduplication within 60 minutes reuses existing report (no credit).
    """
    device_id = (x_device_id or "").strip()

    # Same-ticker deduplication: if a completed report exists within the window,
    # return it without consuming a credit.
    if not user.is_admin:
        existing_run_id = await _find_recent_completed_run(user.id, request.ticker)
        if existing_run_id:
            print(f"♻️  Reusing recent run {existing_run_id} for {request.ticker} (dedup)")
            return AnalyzeResponse(
                job_id=existing_run_id,
                run_id=existing_run_id,
                ticker=request.ticker,
                status=JobStatus.COMPLETED,
                estimated_time_minutes=0,
                created_at=datetime.utcnow(),
                result=None,
            )

    # Quota / credit check — admins bypass, free uses lifetime credits, paid uses monthly quota
    can_analyze, error_msg = await check_can_analyze(
        user.id,
        str(user.tier.value) if hasattr(user.tier, "value") else str(user.tier),
        user.email,
        user.is_admin,
        stripe_status=user.stripe_subscription_status or "",
        email_verified=user.email_verified,
        device_id=device_id,
    )
    if not can_analyze:
        raise HTTPException(status_code=402, detail=error_msg)

    quarters = request.quarters or ["Q4_2024", "Q1_2025", "Q2_2025", "Q3_2025"]
    news_days_back = request.news_days_back or 30

    # Create Run record immediately so client can start polling
    run_id = await create_pending_run(user.id, request.ticker, news_days_back)
    print(f"📋 Created pending run {run_id} for {request.ticker}")

    tier_str = str(user.tier.value) if hasattr(user.tier, "value") else str(user.tier)

    # Queue the analysis — runs after this HTTP response is sent
    background_tasks.add_task(
        _run_analysis_background,
        run_id=run_id,
        user_id=user.id,
        user_tier=tier_str,
        ticker=request.ticker,
        quarters=quarters,
        news_days_back=news_days_back,
        device_id=device_id,
    )

    # Return immediately — frontend redirects to /results/{run_id} which polls
    return AnalyzeResponse(
        job_id=run_id,
        run_id=run_id,
        ticker=request.ticker,
        status=JobStatus.RUNNING,
        estimated_time_minutes=4,
        created_at=datetime.utcnow(),
        result=None,
    )

@router.post("/analyze/batch", response_model=AnalyzeResponse)
async def analyze_batch(
    request: AnalyzeRequest,  # Will support multiple tickers in Phase 2
    user: User = Depends(get_current_user)
):
    """
    Trigger batch analysis of multiple stocks.

    **Phase 2 feature** - Currently returns 501 Not Implemented.
    """
    raise HTTPException(
        status_code=501,
        detail="Batch analysis will be available in Phase 2"
    )
