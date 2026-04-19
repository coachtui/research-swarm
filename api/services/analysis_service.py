"""
Analysis service that wraps the existing manager agent.

This service provides the bridge between the API layer and the
core research_swarm agent orchestration.
"""

from typing import Dict, Any
import asyncio
import time

# NOTE: research_swarm.agents.manager.graph is intentionally NOT imported at module
# level. It pulls in the entire LangGraph/LangChain/agent stack (yfinance, pandas,
# numpy, anthropic SDK, all sub-agents) which takes 15-40s to import cold.
# Importing it at module level hangs uvicorn worker startup past Railway's 60s
# healthcheck window, causing all healthcheck probes to return "service unavailable".
#
# EXCEPTION: market_data_client is imported at module level so that tests can patch
# it via api.services.analysis_service.market_data_client.
# analyze_swarm is defined as a module-level function (lazy-loading internally) so
# tests can patch it via api.services.analysis_service.analyze_swarm.
from research_swarm.data.market_data_client import MarketDataClient
from research_swarm.agents.manager.models import ETFManagerOutput

market_data_client = MarketDataClient()


def analyze_swarm(*args, **kwargs):
    """
    Module-level wrapper around research_swarm analyze_swarm.

    Defined here (not imported directly) so the name is stable and patchable
    by tests via `api.services.analysis_service.analyze_swarm`, while still
    deferring the heavy import to first call.
    """
    from research_swarm.agents.manager.graph import analyze_swarm as _analyze_swarm
    return _analyze_swarm(*args, **kwargs)


async def run_stock_analysis(
    ticker: str,
    quarters: list[str],
    news_days_back: int = 30,
    user_id: str = None
) -> Dict[str, Any]:
    """
    Run the full manager agent analysis for a single stock or ETF.

    This is the core function that Inngest will call.
    It wraps the existing analyze_swarm function.

    Args:
        ticker: Stock ticker symbol (e.g., "NVDA") or ETF ticker (e.g., "SPY")
        quarters: List of quarters for TTM analysis
        news_days_back: Days to look back for news
        user_id: User ID for multi-tenant isolation

    Returns:
        Dict containing all analysis results
    """

    start_time = time.time()

    try:
        # Detect ETF — cached 7 days, cheap call
        loop = asyncio.get_event_loop()
        company_info = await loop.run_in_executor(
            None, market_data_client.get_company_info, ticker
        )
        is_etf = (company_info or {}).get("quote_type") == "ETF"

        # analyze_swarm is synchronous (~4 minutes). Run it in a thread pool
        # so the asyncio event loop stays free to serve health checks and other
        # requests during the long analysis — prevents Railway 503s.
        result = await loop.run_in_executor(
            None,
            lambda: analyze_swarm(
                ticker=ticker,
                quarters=quarters,
                news_days_back=news_days_back,
                is_etf=is_etf,
            )
        )

        # Extract key metrics from result
        processing_time = time.time() - start_time

        # ETF response shape
        if isinstance(result, ETFManagerOutput):
            return {
                "ticker": ticker,
                "status": "completed",
                "instrument_type": "ETF",
                "allocation_recommendation": result.allocation_recommendation,
                "concentration_risk": result.concentration_risk,
                "sector_momentum": result.sector_momentum,
                "macro_alignment_score": result.macro_alignment_score,
                "sentiment_score": result.sentiment_score,
                "fund_name": result.fund_name,
                "top_holdings_summary": result.top_holdings_summary,
                "sector_breakdown": result.sector_breakdown,
                "expense_ratio": result.expense_ratio,
                "aum_billions": result.aum_billions,
                "pros": result.pros,
                "cons": result.cons,
                "investment_thesis": result.investment_thesis,
                "watchlist_candidate": result.watchlist_candidate,
                "tokens_used": result.tokens_used,
                "cost_usd": sum(result.cost_by_agent.values()) if result.cost_by_agent else 0.0,
                "processing_time_seconds": processing_time,
                "full_output": result.model_dump(),
            }

        # Equity response shape (existing)
        # Extract component scores from moat breakdown
        breakdown = result.moat_breakdown

        # Build response dict
        return {
            "ticker": ticker,
            "status": "completed",

            # Scores (from moat_breakdown v2.0)
            "moat_score": result.moat_score,
            "financial_health_score": breakdown.financial_health,
            "business_model_moat_score": breakdown.earnings_momentum,  # v2.0: earnings_momentum replaces business_model_moat
            "sentiment_score": breakdown.sentiment_catalysts,
            "technical_score": breakdown.technical_strength,

            # Analysis outputs (convert Pydantic models to dicts)
            "investment_thesis": result.investment_thesis.model_dump(),
            "watchlist_candidate": result.is_watchlist_candidate,

            # Metadata
            "tokens_used": result.tokens_used,
            "cost_usd": sum(result.cost_by_agent.values()),
            "processing_time_seconds": processing_time,

            # Full output for database storage (convert Pydantic to dict)
            "full_output": result.model_dump()
        }

    except Exception as e:
        # Log the actual error for debugging
        import traceback
        print(f"❌ Analysis service error for {ticker}: {type(e).__name__}: {e}")
        traceback.print_exc()

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
