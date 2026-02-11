"""
Database client and helper functions.

This module provides the Prisma database client and utility functions
for interacting with the Neon Postgres database.
"""

from prisma import Prisma
from typing import Optional
from contextlib import asynccontextmanager

# Global Prisma client instance
_db_client: Optional[Prisma] = None

async def get_db() -> Prisma:
    """
    Get or create the database client.

    This is the dependency injection function for FastAPI routes.
    Usage:
        db: Prisma = Depends(get_db)
    """
    global _db_client

    if _db_client is None:
        _db_client = Prisma()
        await _db_client.connect()

    return _db_client

@asynccontextmanager
async def db_session():
    """
    Context manager for database sessions.

    Usage:
        async with db_session() as db:
            user = await db.user.find_unique(where={"id": user_id})
    """
    db = await get_db()
    try:
        yield db
    finally:
        # Connection is kept alive (connection pooling)
        pass

async def close_db():
    """
    Close the database connection.
    Call this on application shutdown.
    """
    global _db_client

    if _db_client is not None:
        await _db_client.disconnect()
        _db_client = None

# Helper functions for common operations

async def create_test_user(email: str = "test@example.com", full_name: str = "Test User") -> dict:
    """
    Create a test user in the database.
    Useful for development and testing.
    """
    db = await get_db()

    # Check if user already exists
    existing = await db.user.find_unique(where={"email": email})
    if existing:
        return {
            "id": existing.id,
            "email": existing.email,
            "full_name": existing.fullName,
            "tier": existing.tier,
            "created": False
        }

    # Create new user
    user = await db.user.create(
        data={
            "clerkId": f"test_{email.split('@')[0]}",
            "email": email,
            "fullName": full_name,
            "tier": "free",
            "monthlyBudgetUsd": 200.0,
            "isActive": True
        }
    )

    return {
        "id": user.id,
        "email": user.email,
        "full_name": user.fullName,
        "tier": user.tier,
        "created": True
    }

async def save_analysis_result(
    user_id: str,
    ticker: str,
    result: dict,
    run_id: Optional[str] = None
) -> dict:
    """
    Save stock analysis result to database.

    Args:
        user_id: User ID who requested the analysis
        ticker: Stock ticker symbol
        result: Analysis result from analysis_service
        run_id: Optional run ID (creates new run if not provided)

    Returns:
        Dictionary with run_id and result_id
    """
    db = await get_db()

    # Create or get run
    if run_id is None:
        run = await db.run.create(
            data={
                "userId": user_id,
                "tickers": [ticker],
                "status": "completed" if result['status'] == 'completed' else "failed",
                "totalStocks": 1,
                "completedCount": 1 if result['status'] == 'completed' else 0,
                "failedCount": 0 if result['status'] == 'completed' else 1,
                "progressPercent": 100.0,
                "totalCostUsd": result.get('cost_usd', 0.0),
                "quarters": [],  # Will be populated from result
                "newsDaysBack": 30
            }
        )
        run_id = run.id

    # Create stock result (excluding supply chain per user request)
    stock_result = await db.stockresult.create(
        data={
            "runId": run_id,
            "ticker": ticker,
            "status": result['status'],
            "moatScore": result.get('moat_score'),
            "financialHealthScore": result.get('financial_health_score'),
            "businessModelMoatScore": result.get('business_model_moat_score'),
            "sentimentScore": result.get('sentiment_score'),
            "technicalScore": result.get('technical_score'),
            # supplyChainScore excluded - not used
            "isWatchlistCandidate": result.get('watchlist_candidate', False),
            "investmentThesis": result.get('investment_thesis'),
            "fullOutput": result.get('full_output'),
            "tokensUsed": result.get('tokens_used', 0),
            "costUsd": result.get('cost_usd', 0.0),
            "processingTimeSeconds": result.get('processing_time_seconds'),
            "errorMessage": result.get('error_message')
        }
    )

    # Log costs
    if result.get('cost_usd', 0) > 0:
        await db.costlog.create(
            data={
                "userId": user_id,
                "runId": run_id,
                "ticker": ticker,
                "agent": "manager",  # Full analysis uses manager
                "tokensTotal": result.get('tokens_used', 0),
                "costUsd": result.get('cost_usd', 0.0)
            }
        )

    return {
        "run_id": run_id,
        "result_id": stock_result.id,
        "ticker": ticker,
        "status": result['status']
    }

async def get_user_monthly_cost(user_id: str) -> float:
    """
    Get user's total spending for the current month.
    """
    from datetime import datetime

    db = await get_db()

    # Get start of current month
    now = datetime.utcnow()
    month_start = datetime(now.year, now.month, 1)

    # Sum costs for this month
    result = await db.costlog.aggregate(
        where={
            "userId": user_id,
            "timestamp": {"gte": month_start}
        },
        _sum={"costUsd": True}
    )

    return result._sum.get('costUsd', 0.0) or 0.0
