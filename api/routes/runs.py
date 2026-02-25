"""
Run management endpoints for checking status and retrieving results.
"""

import json
from fastapi import APIRouter, HTTPException, Depends
from api.models.responses import RunResponse, RunListResponse, RunSummary
from api.dependencies import get_current_user
from api.lib.entitlement_middleware import load_entitlements
from api.lib.entitlement_resolver import EntitlementContext
from api.models.auth import User
from api.lib.db import get_db
from api.lib.decision_intelligence import enrich_with_decision_intelligence
from typing import Optional

router = APIRouter()

# Keys in full_output that are safe to return on the Starter (snapshot) tier.
# Everything NOT in this set is stripped before the response leaves the server.
_SNAPSHOT_KEYS = {
    "ticker",
    "current_price",
    "fair_value",
    "moat_score",
    "financial_health_score",
    "sentiment_score",
    "signal_divergence",        # surface-level divergence summary only
    "recommendation",
    "summary",                  # short one-liner summary
    "ev_summary",               # EV summary (not full engine)
    "scenarios_basic",
    "previous_analysis_delta",  # longitudinal delta is safe
}


def _shape_snapshot(full_output: dict) -> dict:
    """
    Return a reduced view of full_output safe for Starter-tier users.

    Strips decision-intelligence layers, full thesis, probabilistic engine,
    risk diagnostics, and execution infrastructure. The set of keys exposed
    maps to report.snapshot.read capabilities defined in TIER_CONFIG.
    """
    return {k: v for k, v in full_output.items() if k in _SNAPSHOT_KEYS}

@router.get("/preview/nvda")
async def get_nvda_preview():
    """
    Public endpoint — returns the latest completed NVDA analysis run without auth.
    Used for the landing-page 'See Example Report' feature.
    """
    db = await get_db()

    # Prefer an admin-approved public example; fall back to most-recent completed run.
    result = await db.stockresult.find_first(
        where={"ticker": "NVDA", "status": "completed", "isPublicExample": True},
        order={"createdAt": "desc"},
        include={"run": True},
    )
    if not result:
        result = await db.stockresult.find_first(
            where={"ticker": "NVDA", "status": "completed"},
            order={"createdAt": "desc"},
            include={"run": True},
        )

    if not result or not result.run:
        raise HTTPException(status_code=404, detail="No NVDA preview available")

    run = result.run

    full_output = result.fullOutput
    if isinstance(full_output, str):
        try:
            full_output = json.loads(full_output)
        except (json.JSONDecodeError, ValueError):
            full_output = None

    if full_output and result.moatScore is not None:
        full_output = enrich_with_decision_intelligence(full_output, result.moatScore)

    return {
        "id": run.id,
        "status": run.status,
        "tickers": run.tickers,
        "total_cost_usd": run.totalCostUsd,
        "created_at": run.createdAt,
        "completed_at": run.completedAt,
        "results": [{
            "ticker": result.ticker,
            "status": result.status,
            "moat_score": result.moatScore,
            "financial_health_score": result.financialHealthScore,
            "business_model_moat_score": result.businessModelMoatScore,
            "sentiment_score": result.sentimentScore,
            "technical_score": result.technicalScore,
            "watchlist_candidate": result.isWatchlistCandidate,
            "investment_thesis": result.investmentThesis,
            "cost_usd": result.costUsd,
            "tokens_used": result.tokensUsed,
            "processing_time_seconds": result.processingTimeSeconds,
            "error_message": result.errorMessage,
            "created_at": result.createdAt,
            "full_output": full_output,
            "_entitlement_tier": "investor",
            "_report_full_allowed": True,
        }],
    }


@router.get("/runs", response_model=RunListResponse)
async def list_runs(
    user: User = Depends(get_current_user),
    limit: int = 20,
    offset: int = 0,
    status: Optional[str] = None
):
    """
    List all runs for the authenticated user.

    **Query parameters**:
    - `limit`: Number of runs to return (default: 20, max: 100)
    - `offset`: Pagination offset (default: 0)
    - `status`: Filter by status (queued, running, completed, failed)
    """

    # Handle potential connection timeout
    from api.lib.db import _db_client
    global _db_client

    try:
        db = await get_db()
        if not db.is_connected():
            await db.disconnect()
            await db.connect()
    except Exception:
        _db_client = None  # Force fresh connection
        db = await get_db()

    # Build query filters
    where_clause = {"userId": user.id}
    if status:
        where_clause["status"] = status

    # Query database for user's runs
    runs = await db.run.find_many(
        where=where_clause,
        skip=offset,
        take=min(limit, 100),
        order={"createdAt": "desc"},
        include={"stockResults": True}
    )

    # Get total count
    total = await db.run.count(where=where_clause)

    # Convert to response format
    run_list = []
    for run in runs:
        run_list.append({
            "id": run.id,
            "ticker": run.tickers[0] if run.tickers else "",
            "status": run.status,
            "created_at": run.createdAt,
            "completed_at": run.completedAt,
            "total_cost_usd": run.totalCostUsd,
            "stock_count": len(run.stockResults) if run.stockResults else 0,
        })

    return RunListResponse(
        total=total,
        limit=limit,
        offset=offset,
        runs=run_list
    )

@router.get("/runs/{run_id}", response_model=RunResponse)
async def get_run(
    run_id: str,
    user: User = Depends(get_current_user),
    ent: EntitlementContext = Depends(load_entitlements),
):
    """
    Get detailed information about a specific run.

    **Returns**:
    - Run metadata (status, progress, costs)
    - Stock results (if completed)
    - Error information (if failed)
    """

    # Handle potential connection timeout after long-running analysis
    from api.lib.db import _db_client
    global _db_client

    try:
        db = await get_db()
        if not db.is_connected():
            await db.disconnect()
            await db.connect()
    except Exception:
        _db_client = None  # Force fresh connection
        db = await get_db()

    # Query database for run with results
    run = await db.run.find_unique(
        where={"id": run_id},
        include={"stockResults": True}
    )

    if not run:
        raise HTTPException(status_code=404, detail="Run not found")

    # Verify user owns this run or is an admin
    if run.userId != user.id and not user.is_admin:
        raise HTTPException(status_code=403, detail="Access denied")

    # Determine response depth from entitlements
    full_report_allowed = ent.has_flag("report.full.read")

    # Format response
    results = []
    if run.stockResults:
        for result in run.stockResults:
            # Enrich fullOutput with decision intelligence on-the-fly
            full_output = result.fullOutput
            # Handle double-serialized fullOutput (json.dumps stored in Json column)
            if isinstance(full_output, str):
                try:
                    full_output = json.loads(full_output)
                except (json.JSONDecodeError, ValueError):
                    full_output = None
            if full_output and result.moatScore is not None:
                full_output = enrich_with_decision_intelligence(
                    full_output, result.moatScore
                )

            # Response shaping: Starter tier receives snapshot only.
            # Deep analytical layers (decision intelligence, full thesis, etc.)
            # are stripped server-side — never rely on frontend hiding alone.
            if not full_report_allowed and full_output is not None:
                # Return only the snapshot-safe subset
                full_output = _shape_snapshot(full_output)
                investment_thesis = None  # Full thesis is investor+
            else:
                investment_thesis = result.investmentThesis

            results.append({
                "ticker": result.ticker,
                "status": result.status,
                "moat_score": result.moatScore,
                "financial_health_score": result.financialHealthScore,
                "business_model_moat_score": result.businessModelMoatScore,
                "sentiment_score": result.sentimentScore,
                "technical_score": result.technicalScore,
                "watchlist_candidate": result.isWatchlistCandidate,
                "investment_thesis": investment_thesis,
                "cost_usd": result.costUsd,
                "tokens_used": result.tokensUsed,
                "processing_time_seconds": result.processingTimeSeconds,
                "error_message": result.errorMessage,
                "created_at": result.createdAt,
                "full_output": full_output,
                # Communicate tier constraints to the frontend for upgrade prompts
                "_entitlement_tier": ent.tier,
                "_report_full_allowed": full_report_allowed,
            })

    return RunResponse(
        id=run.id,
        status=run.status,
        tickers=run.tickers,
        total_cost_usd=run.totalCostUsd,
        created_at=run.createdAt,
        completed_at=run.completedAt,
        results=results
    )

@router.delete("/runs/{run_id}")
async def delete_run(
    run_id: str,
    user: User = Depends(get_current_user)
):
    """
    Delete a run and all associated results.

    **Note**: This also cancels the job if it's still running.
    **Admin-only**: Admins can delete any run.
    """
    # Handle potential connection timeout
    from api.lib.db import _db_client
    global _db_client

    try:
        db = await get_db()
        if not db.is_connected():
            await db.disconnect()
            await db.connect()
    except Exception:
        _db_client = None  # Force fresh connection
        db = await get_db()

    # Check if run exists
    run = await db.run.find_unique(where={"id": run_id})
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")

    # Verify user owns this run or is an admin
    if run.userId != user.id and not user.is_admin:
        raise HTTPException(status_code=403, detail="Access denied")

    # TODO: Cancel Inngest job if running
    # TODO: Delete from database

    raise HTTPException(
        status_code=501,
        detail="Delete functionality pending implementation"
    )
