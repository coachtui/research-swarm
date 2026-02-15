"""
Run management endpoints for checking status and retrieving results.
"""

from fastapi import APIRouter, HTTPException, Depends
from api.models.responses import RunResponse, RunListResponse, RunSummary
from api.dependencies import get_current_user
from api.models.auth import User
from api.lib.db import get_db
from api.lib.decision_intelligence import enrich_with_decision_intelligence
from typing import Optional

router = APIRouter()

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
    user: User = Depends(get_current_user)
):
    """
    Get detailed information about a specific run.

    **Returns**:
    - Run metadata (status, progress, costs)
    - Stock results (if completed)
    - Error information (if failed)
    """

    db = await get_db()

    # Query database for run with results
    run = await db.run.find_unique(
        where={"id": run_id},
        include={"stockResults": True}
    )

    if not run:
        raise HTTPException(status_code=404, detail="Run not found")

    # Verify user owns this run
    if run.userId != user.id:
        raise HTTPException(status_code=403, detail="Access denied")

    # Format response
    results = []
    if run.stockResults:
        for result in run.stockResults:
            # Enrich fullOutput with decision intelligence on-the-fly
            full_output = result.fullOutput
            if full_output and result.moatScore is not None:
                full_output = enrich_with_decision_intelligence(
                    full_output, result.moatScore
                )

            results.append({
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
                "full_output": full_output
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
    """

    # TODO: Cancel Inngest job if running
    # TODO: Delete from database

    raise HTTPException(
        status_code=501,
        detail="Delete functionality pending implementation"
    )
