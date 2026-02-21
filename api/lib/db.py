"""
Database client and helper functions.

This module provides the Prisma database client and utility functions
for interacting with the Neon Postgres database.
"""

from prisma import Prisma
from typing import Optional
from contextlib import asynccontextmanager
import json

# Global Prisma client instance
_db_client: Optional[Prisma] = None

async def get_db() -> Prisma:
    """
    Get or create the database client with automatic reconnection.

    This is the dependency injection function for FastAPI routes.
    Usage:
        db: Prisma = Depends(get_db)
    """
    global _db_client

    if _db_client is None:
        # Create Prisma client with extended timeouts (60s connect, 120s query)
        _db_client = Prisma(
            http={'timeout': 120.0}  # 120 second timeout for long queries
        )
        await _db_client.connect()
    else:
        # Check if connection is still alive
        try:
            if not _db_client.is_connected():
                await _db_client.disconnect()
                await _db_client.connect()
        except Exception:
            # Connection is stale, recreate client
            try:
                await _db_client.disconnect()
            except:
                pass
            _db_client = Prisma(
                http={'timeout': 120.0}
            )
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
            "tier": "starter",
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

async def create_pending_run(user_id: str, ticker: str, news_days_back: int = 30) -> str:
    """
    Create a Run record with status 'running' and return its ID immediately.
    Used by the background task pattern so the API can return a run_id before
    the analysis completes.
    """
    db = await get_db()
    run = await db.run.create(
        data={
            "userId": user_id,
            "tickers": [ticker],
            "status": "running",
            "totalStocks": 1,
            "completedCount": 0,
            "failedCount": 0,
            "progressPercent": 0.0,
            "newsDaysBack": news_days_back,
            "quarters": [],
        }
    )
    return run.id


async def update_run_failed(run_id: str, error_message: str) -> None:
    """Mark a Run as failed with an error message."""
    from datetime import datetime
    global _db_client
    # Force fresh connection — this is called after a long analysis
    if _db_client:
        try:
            await _db_client.disconnect()
        except Exception:
            pass
    _db_client = None
    db = await get_db()
    await db.run.update(
        where={"id": run_id},
        data={
            "status": "failed",
            "completedAt": datetime.utcnow(),
            "progressPercent": 100.0,
            "failedCount": 1,
        }
    )
    # Create a minimal failed StockResult so the results page can show the error
    run = await db.run.find_unique(where={"id": run_id})
    ticker = run.tickers[0] if run and run.tickers else "UNKNOWN"
    await db.stockresult.create(
        data={
            "runId": run_id,
            "ticker": ticker,
            "status": "failed",
            "errorMessage": error_message,
        }
    )


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
    global _db_client

    # CRITICAL: Force fresh connection BEFORE saving
    # Stock analysis takes 4+ minutes, exceeding Prisma connection timeout
    print(f"⚠️  Forcing fresh database connection for {ticker}...")
    if _db_client:
        try:
            await _db_client.disconnect()
        except Exception as e:
            print(f"   (Disconnect error ignored: {e})")
    _db_client = None

    # Get brand new connection
    db = await get_db()
    print(f"✅ Fresh database connection established")

    # Retry logic for connection timeouts
    max_retries = 2
    for attempt in range(max_retries):
        try:
            # Use the fresh connection we created above
            if attempt > 0:
                print(f"⚠️  Retry {attempt}/{max_retries}: Re-attempting save...")
                # Connection is already fresh, just retry the operation

            # Create or update run
            final_status = "completed" if result['status'] == 'completed' else "failed"
            if run_id is None:
                run = await db.run.create(
                    data={
                        "userId": user_id,
                        "tickers": [ticker],
                        "status": final_status,
                        "totalStocks": 1,
                        "completedCount": 1 if result['status'] == 'completed' else 0,
                        "failedCount": 0 if result['status'] == 'completed' else 1,
                        "progressPercent": 100.0,
                        "totalCostUsd": result.get('cost_usd', 0.0),
                        "quarters": [],
                        "newsDaysBack": 30
                    }
                )
                run_id = run.id
            else:
                # Update the pre-existing "running" run to completed/failed
                from datetime import datetime
                await db.run.update(
                    where={"id": run_id},
                    data={
                        "status": final_status,
                        "completedAt": datetime.utcnow(),
                        "progressPercent": 100.0,
                        "completedCount": 1 if result['status'] == 'completed' else 0,
                        "failedCount": 0 if result['status'] == 'completed' else 1,
                        "totalCostUsd": result.get('cost_usd', 0.0),
                    }
                )

            # Create stock result (excluding supply chain per user request)
            # Serialize full_output to JSON if it exists
            full_output = result.get('full_output')
            if full_output and isinstance(full_output, dict):
                full_output = json.dumps(full_output)

            # Serialize investment_thesis if it's a Pydantic model
            investment_thesis = result.get('investment_thesis')
            if investment_thesis is not None:
                # Check if it's a Pydantic model (has model_dump method)
                if hasattr(investment_thesis, 'model_dump'):
                    investment_thesis = json.dumps(investment_thesis.model_dump())
                elif isinstance(investment_thesis, dict):
                    investment_thesis = json.dumps(investment_thesis)
                # If it's already a string, leave it as is

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
                    "investmentThesis": investment_thesis,
                    "fullOutput": full_output,
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

            print(f"✅ Successfully saved analysis for {ticker} to database")
            return {
                "run_id": run_id,
                "result_id": stock_result.id,
                "ticker": ticker,
                "status": result['status']
            }

        except Exception as e:
            error_msg = str(e)
            # Check if it's a connection error
            if "connection" in error_msg.lower() or "closed" in error_msg.lower():
                if attempt < max_retries - 1:
                    print(f"❌ Database connection error (attempt {attempt + 1}/{max_retries}): {e}")
                    continue
                else:
                    print(f"❌ Failed after {max_retries} attempts: {e}")
                    raise
            else:
                # Not a connection error, raise immediately
                raise

async def get_user_monthly_cost(user_id: str) -> float:
    """
    Get user's total spending for the current month.
    """
    from datetime import datetime

    # Force reconnect to handle long-running timeouts
    global _db_client
    try:
        db = await get_db()

        # Ensure connection is active
        if not db.is_connected():
            print("⚠️  Database connection closed, reconnecting...")
            await db.disconnect()
            await db.connect()
    except Exception as conn_error:
        print(f"⚠️  Connection error: {conn_error}, creating fresh connection...")
        _db_client = None
        db = await get_db()

    # Get start of current month
    now = datetime.utcnow()
    month_start = datetime(now.year, now.month, 1)

    # Get all cost logs for this month
    costs = await db.costlog.find_many(
        where={
            "userId": user_id,
            "timestamp": {"gte": month_start}
        }
    )

    # Sum the costs
    total = sum(cost.costUsd for cost in costs) if costs else 0.0
    return total

async def get_or_create_cli_user() -> str:
    """
    Get or create the default CLI user for local analysis runs.

    This user is used when running analysis via the CLI instead of the API.
    All CLI-generated analyses are associated with this user so they appear
    in the frontend.

    Returns:
        str: The user ID of the CLI user
    """
    db = await get_db()

    # Ensure connection is active
    if not db.is_connected():
        await db.connect()

    CLI_USER_EMAIL = "cli@local.research-swarm"

    # Check if CLI user already exists
    user = await db.user.find_unique(where={"email": CLI_USER_EMAIL})

    if not user:
        # Create CLI user with enterprise tier (no budget limits)
        user = await db.user.create(
            data={
                "clerkId": "cli-local-user",
                "email": CLI_USER_EMAIL,
                "fullName": "CLI User",
                "tier": "enterprise",
                "monthlyBudgetUsd": 999999.0,
                "isActive": True
            }
        )

    return user.id
