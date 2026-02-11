"""
Analysis endpoints for triggering stock analysis jobs.
"""

from fastapi import APIRouter, HTTPException, Depends
from api.models.requests import AnalyzeRequest
from api.models.responses import AnalyzeResponse, JobStatus
from api.dependencies import get_current_user
from api.models.auth import User
import uuid
from datetime import datetime

router = APIRouter()

@router.post("/analyze", response_model=AnalyzeResponse)
async def analyze_stock(
    request: AnalyzeRequest,
    user: User = Depends(get_current_user)
):
    """
    Trigger a single stock analysis.

    This endpoint queues an Inngest job for long-running analysis.
    The job typically takes 5-8 minutes per stock.

    **Authentication required**: Bearer token (Clerk JWT)

    **Rate limits**:
    - Free tier: 10 analyses/month
    - Pro tier: 50 analyses/month
    - Enterprise: Unlimited

    **Returns**: Job ID and status for polling
    """

    # TODO: Implement quota check
    # await check_user_quota(user, estimated_cost=0.30)

    # TODO: Trigger Inngest job
    # job = await inngest_client.send({
    #     "name": "analyze_stock",
    #     "data": {
    #         "user_id": user.id,
    #         "ticker": request.ticker,
    #         "quarters": request.quarters,
    #         "news_days_back": request.news_days_back
    #     }
    # })

    # For now, return mock response
    job_id = str(uuid.uuid4())

    return AnalyzeResponse(
        job_id=job_id,
        run_id=job_id,
        ticker=request.ticker,
        status=JobStatus.QUEUED,
        estimated_time_minutes=6,
        created_at=datetime.utcnow()
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
