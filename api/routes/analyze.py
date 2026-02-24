"""
Analysis endpoints for triggering stock analysis jobs.
"""

import asyncio
import traceback
from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks
from api.models.requests import AnalyzeRequest
from api.models.responses import AnalyzeResponse, JobStatus
from api.dependencies import get_current_user
from api.lib.entitlement_middleware import require_limit
from api.lib.entitlement_resolver import EntitlementContext
from api.models.auth import User
from api.services.analysis_service import run_stock_analysis
from api.lib.db import save_analysis_result, create_pending_run, update_run_failed
from api.services.quota_service import check_can_analyze, increment_analysis_count
from datetime import datetime

router = APIRouter()

async def _run_analysis_background(
    run_id: str,
    user_id: str,
    user_tier: str,
    ticker: str,
    quarters: list,
    news_days_back: int,
):
    """
    Background task: run the full analysis and save result to DB.

    Runs after the HTTP response has already been returned to the client.
    The client polls GET /api/runs/{run_id} to check status.
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
                await increment_analysis_count(user_id, user_tier)
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
    """
    # Also check monthly quota (existing system) — admins bypass
    can_analyze, error_msg = await check_can_analyze(
        user.id, user.tier, user.email, user.is_admin,
        stripe_status=user.stripe_subscription_status or ""
    )
    if not can_analyze:
        raise HTTPException(status_code=402, detail=error_msg)

    quarters = request.quarters or ["Q4_2024", "Q1_2025", "Q2_2025", "Q3_2025"]
    news_days_back = request.news_days_back or 30

    # Create Run record immediately so client can start polling
    run_id = await create_pending_run(user.id, request.ticker, news_days_back)
    print(f"📋 Created pending run {run_id} for {request.ticker}")

    # Queue the analysis — runs after this HTTP response is sent
    background_tasks.add_task(
        _run_analysis_background,
        run_id=run_id,
        user_id=user.id,
        user_tier=user.tier,
        ticker=request.ticker,
        quarters=quarters,
        news_days_back=news_days_back,
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
