"""
Analysis endpoints for triggering stock analysis jobs.
"""

from fastapi import APIRouter, HTTPException, Depends
from api.models.requests import AnalyzeRequest
from api.models.responses import AnalyzeResponse, JobStatus
from api.dependencies import get_current_user
from api.models.auth import User
from api.services.analysis_service import run_stock_analysis
from api.lib.db import save_analysis_result, get_user_monthly_cost
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

    This endpoint runs a real stock analysis (~4 minutes).
    The analysis uses the full manager agent with fundamentalist, news hound, and quant agents.

    **Authentication required**: Bearer token (Clerk JWT)

    **Rate limits**:
    - Free tier: 10 analyses/month
    - Pro tier: 50 analyses/month
    - Enterprise: Unlimited

    **Returns**: Analysis results with moat score, thesis, and component scores
    """

    # Check user's monthly spending
    monthly_cost = await get_user_monthly_cost(user.id)
    estimated_cost = 0.30

    # Simple quota check (based on free tier $50 limit)
    if monthly_cost + estimated_cost > 50.0:
        raise HTTPException(
            status_code=402,
            detail=f"Monthly budget exceeded. Current: ${monthly_cost:.2f}, Limit: $50.00"
        )

    # Run the analysis (this takes ~4 minutes)
    try:
        result = await run_stock_analysis(
            ticker=request.ticker,
            quarters=request.quarters or ["Q4_2024", "Q1_2025", "Q2_2025", "Q3_2025"],
            news_days_back=request.news_days_back or 30,
            user_id=user.id
        )

        # Save results to database
        if result['status'] == 'completed':
            try:
                saved = await save_analysis_result(
                    user_id=user.id,
                    ticker=request.ticker,
                    result=result
                )
            except Exception as db_error:
                print(f"❌ Database save error: {db_error}")
                import traceback
                traceback.print_exc()
                raise HTTPException(
                    status_code=500,
                    detail=f"Database save failed: {str(db_error)}"
                )

            try:
                return AnalyzeResponse(
                    job_id=saved['run_id'],
                    run_id=saved['run_id'],
                    ticker=request.ticker,
                    status=JobStatus.COMPLETED,
                    estimated_time_minutes=0,  # Already completed
                    created_at=datetime.utcnow(),
                    result=result  # Include full analysis results
                )
            except Exception as response_error:
                print(f"❌ Response creation error: {response_error}")
                import traceback
                traceback.print_exc()
                raise HTTPException(
                    status_code=500,
                    detail=f"Response creation failed: {str(response_error)}"
                )
        else:
            raise HTTPException(
                status_code=500,
                detail=f"Analysis failed: {result.get('error_message', 'Unknown error')}"
            )

    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Analysis error: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail=f"Analysis failed: {str(e)}"
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
