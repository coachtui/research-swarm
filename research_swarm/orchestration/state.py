"""LangGraph state definition for orchestration workflow."""

from typing import Dict, List, Optional, TypedDict

from .models import CostSummary, RunStatus, StockResult


class SwarmOrchestrationState(TypedDict):
    """State for the orchestration workflow.

    This TypedDict is used by LangGraph to track the complete state
    of a batch stock analysis run.
    """

    # Run metadata
    run_id: str
    run_name: Optional[str]
    tickers: List[str]
    analysis_period: str
    quarters: List[str]
    news_days_back: int
    max_retries: int

    # Backward compatibility
    fiscal_year: Optional[int]

    # Run status
    status: RunStatus
    current_ticker: Optional[str]

    # Results tracking
    stock_results: Dict[str, StockResult]
    completed_count: int
    failed_count: int

    # Cost tracking
    cost_summary: CostSummary

    # Timing
    start_time: Optional[float]
    elapsed_seconds: float

    # Error handling
    last_error: Optional[str]
