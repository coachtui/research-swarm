"""
Analysis service that wraps the existing manager agent.

This service provides the bridge between the API layer and the
core research_swarm agent orchestration.
"""

from typing import Dict, Any
from research_swarm.agents.manager.graph import analyze_swarm
import time

async def run_stock_analysis(
    ticker: str,
    quarters: list[str],
    news_days_back: int = 30,
    user_id: str = None
) -> Dict[str, Any]:
    """
    Run the full manager agent analysis for a single stock.

    This is the core function that Inngest will call.
    It wraps the existing analyze_swarm function.

    Args:
        ticker: Stock ticker symbol (e.g., "NVDA")
        quarters: List of quarters for TTM analysis
        news_days_back: Days to look back for news
        user_id: User ID for multi-tenant isolation

    Returns:
        Dict containing all analysis results
    """

    start_time = time.time()

    try:
        # Call the existing analyze_swarm function
        # This is synchronous, so we run it directly (no await needed)
        result = analyze_swarm(
            ticker=ticker,
            quarters=quarters,
            news_days_back=news_days_back
        )

        # Extract key metrics from result (ManagerOutput Pydantic model)
        processing_time = time.time() - start_time

        # Extract component scores from moat breakdown
        breakdown = result.moat_breakdown

        # Build response dict
        return {
            "ticker": ticker,
            "status": "completed",

            # Scores (from moat_breakdown - excluding supply chain)
            "moat_score": result.moat_score,
            "financial_health_score": breakdown.financial_health,
            "business_model_moat_score": breakdown.business_model_moat,
            "sentiment_score": breakdown.sentiment_catalysts,
            "technical_score": breakdown.technical_strength,
            # NOTE: supply_chain_score removed per user request

            # Analysis outputs
            "investment_thesis": result.investment_thesis,
            "watchlist_candidate": result.is_watchlist_candidate,

            # Metadata
            "tokens_used": result.tokens_used,
            "cost_usd": sum(result.cost_by_agent.values()),
            "processing_time_seconds": processing_time,

            # Full output for database storage (convert Pydantic to dict)
            "full_output": result.dict()
        }

    except Exception as e:
        # Return error information
        processing_time = time.time() - start_time

        return {
            "ticker": ticker,
            "status": "failed",
            "error_message": str(e),
            "error_type": type(e).__name__,
            "processing_time_seconds": processing_time,
            "full_output": None
        }


def estimate_analysis_cost(ticker: str, quarters: list[str]) -> Dict[str, Any]:
    """
    Estimate the cost and time for analyzing a stock.

    This is based on historical averages from the existing system.
    """

    # Average tokens per stock (from existing data)
    avg_tokens = 15000

    # Model costs (Haiku + Sonnet mix)
    # Haiku: $0.25/M input, $1.25/M output
    # Sonnet: $3/M input, $15/M output
    # Weighted average: ~$0.30 per stock
    avg_cost_usd = 0.30

    # Average time: 5-8 minutes per stock
    avg_time_minutes = 6

    return {
        "ticker": ticker,
        "estimated_tokens": avg_tokens,
        "estimated_cost_usd": avg_cost_usd,
        "estimated_time_minutes": avg_time_minutes,
        "quarters_count": len(quarters)
    }
