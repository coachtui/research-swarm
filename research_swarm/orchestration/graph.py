"""LangGraph workflow for batch stock analysis orchestration."""

import time
from datetime import datetime
from typing import List, Literal, Optional

from langgraph.graph import END, StateGraph

# Import analyze_swarm inside functions to avoid circular dependency
from ..logger import logger
from .cost_tracker import CostTracker
from .error_handler import RetryConfig, RetryError, RetryHandler, is_retryable_error
from .models import CostSummary, RunStatus, StockResult, StockStatus, SwarmRun
from .persistence import PersistenceManager
from .state import SwarmOrchestrationState


# ============================================================================
# Node Functions
# ============================================================================


def initialize_run(state: SwarmOrchestrationState) -> SwarmOrchestrationState:
    """Initialize a new swarm run.

    Sets up initial state, creates database records, and prepares stock results.
    """
    logger.info(f"Initializing run {state['run_id']} with {len(state['tickers'])} stocks")

    # Initialize stock results as pending
    stock_results = {}
    for ticker in state["tickers"]:
        stock_results[ticker] = StockResult(
            ticker=ticker,
            status=StockStatus.PENDING,
        )

    # Create persistence manager with user_id
    user_id = state.get("user_id")
    persistence = PersistenceManager(user_id=user_id)
    swarm_run = SwarmRun(
        run_id=state["run_id"],
        run_name=state.get("run_name"),
        tickers=state["tickers"],
        analysis_period=state["analysis_period"],
        quarters=state.get("quarters", []),
        fiscal_year=state.get("fiscal_year"),  # Backward compatibility
        news_days_back=state["news_days_back"],
        max_retries=state["max_retries"],
        status=RunStatus.INITIALIZED,
        stock_results=stock_results,
        total_stocks=len(state["tickers"]),
        started_at=datetime.now(),
    )
    persistence.create_run(swarm_run)

    state["stock_results"] = stock_results
    state["status"] = RunStatus.RUNNING
    state["completed_count"] = 0
    state["failed_count"] = 0
    state["start_time"] = time.time()

    # Update run status to running
    persistence.update_run_status(
        state["run_id"],
        RunStatus.RUNNING,
        started_at=datetime.now(),
    )

    logger.info("Run initialized successfully")
    return state


def select_next_ticker(state: SwarmOrchestrationState) -> SwarmOrchestrationState:
    """Select the next ticker to analyze.

    Finds the next pending or retrying stock.
    """
    # Find next pending or retrying ticker
    next_ticker = None
    for ticker, result in state["stock_results"].items():
        if result.status in [StockStatus.PENDING, StockStatus.RETRYING]:
            next_ticker = ticker
            break

    state["current_ticker"] = next_ticker

    if next_ticker:
        logger.info(f"Selected next ticker: {next_ticker}")
    else:
        logger.info("No more pending tickers")

    return state


def analyze_stock(state: SwarmOrchestrationState) -> SwarmOrchestrationState:
    """Analyze a single stock using the manager's analyze_swarm function.

    Includes retry logic for transient failures.
    """
    ticker = state["current_ticker"]
    if not ticker:
        logger.error("No ticker selected for analysis")
        return state

    logger.info(f"=== Analyzing {ticker} ===")

    # Get current result
    result = state["stock_results"][ticker]
    result.status = StockStatus.IN_PROGRESS

    # Update persistence
    user_id = state.get("user_id")
    persistence = PersistenceManager(user_id=user_id)
    persistence.update_stock_result(state["run_id"], result)

    # Setup retry handler
    retry_config = RetryConfig(max_retries=state["max_retries"])
    retry_handler = RetryHandler(retry_config)

    # Setup cost tracker
    cost_tracker = CostTracker()

    # Track processing time
    start_time = time.time()

    try:

        def analyze_with_retry():
            """Wrapper for retry logic."""
            from ..agents.manager.graph import analyze_swarm
            return analyze_swarm(
                ticker=ticker,
                quarters=state.get("quarters"),
                fiscal_year=state.get("fiscal_year"),  # Backward compatibility
                news_days_back=state["news_days_back"],
            )

        def on_retry_callback(attempt: int, exception: Exception):
            """Callback for retry attempts."""
            result.retry_count = attempt + 1
            result.status = StockStatus.RETRYING
            result.error_message = str(exception)
            persistence.update_stock_result(state["run_id"], result)

        # Execute with retry
        manager_output = retry_handler.execute(
            analyze_with_retry,
            on_retry=on_retry_callback,
        )

        # Extract results
        processing_time = time.time() - start_time

        result.status = StockStatus.COMPLETED
        result.moat_score = manager_output.moat_score
        result.is_watchlist_candidate = manager_output.is_watchlist_candidate
        result.investment_thesis = manager_output.investment_thesis
        result.full_output = manager_output.dict()
        result.tokens_used = manager_output.tokens_used
        result.processing_time_seconds = processing_time
        result.error_message = None

        # Use pre-calculated costs from ManagerOutput (accounts for mixed Haiku/Sonnet models)
        cost = sum(manager_output.cost_by_agent.values())
        result.cost_usd = cost

        # Update cost summary
        cost_summary = state.get("cost_summary") or CostSummary()
        cost_summary.total_tokens += manager_output.tokens_used
        cost_summary.total_cost_usd += cost

        if ticker not in cost_summary.cost_by_ticker:
            cost_summary.cost_by_ticker[ticker] = 0.0
        cost_summary.cost_by_ticker[ticker] += cost

        # Log cost to persistence
        persistence.log_cost(
            run_id=state["run_id"],
            ticker=ticker,
            agent_name="manager",
            tokens_total=manager_output.tokens_used,
            cost_usd=cost,
        )

        state["cost_summary"] = cost_summary
        state["completed_count"] += 1

        logger.info(
            f"✓ {ticker} completed: moat={result.moat_score:.1f}, "
            f"watchlist={result.is_watchlist_candidate}, "
            f"cost=${cost:.4f}, time={processing_time:.1f}s"
        )

    except RetryError as e:
        # All retries exhausted
        processing_time = time.time() - start_time

        result.status = StockStatus.FAILED
        result.error_message = str(e.last_exception)
        result.processing_time_seconds = processing_time

        state["failed_count"] += 1

        logger.error(
            f"✗ {ticker} failed after {e.attempt_count} attempts: {e.last_exception}"
        )

    except Exception as e:
        # Unexpected error
        processing_time = time.time() - start_time

        result.status = StockStatus.FAILED
        result.error_message = str(e)
        result.processing_time_seconds = processing_time

        state["failed_count"] += 1
        state["last_error"] = str(e)

        logger.error(f"✗ {ticker} failed with unexpected error: {e}")

    # Update stock result in persistence
    persistence.update_stock_result(state["run_id"], result)
    persistence.update_cost_summary(state["run_id"], state["cost_summary"])

    # Update run counts
    persistence.update_run_status(
        state["run_id"],
        RunStatus.RUNNING,
        completed_count=state["completed_count"],
        failed_count=state["failed_count"],
    )

    return state


def check_completion(
    state: SwarmOrchestrationState,
) -> Literal["continue", "complete"]:
    """Check if all stocks are processed.

    Returns:
        "continue" if there are pending stocks, "complete" otherwise
    """
    # Count pending/retrying stocks
    pending_count = sum(
        1
        for result in state["stock_results"].values()
        if result.status in [StockStatus.PENDING, StockStatus.RETRYING]
    )

    if pending_count > 0:
        logger.info(f"{pending_count} stocks remaining")
        return "continue"
    else:
        logger.info("All stocks processed")
        return "complete"


def finalize_run(state: SwarmOrchestrationState) -> SwarmOrchestrationState:
    """Finalize the run and update final statistics."""
    logger.info("Finalizing run...")

    # Calculate elapsed time
    if state.get("start_time"):
        state["elapsed_seconds"] = time.time() - state["start_time"]

    # Determine final status
    if state["failed_count"] == 0:
        final_status = RunStatus.COMPLETED
    elif state["completed_count"] == 0:
        final_status = RunStatus.FAILED
    else:
        final_status = RunStatus.COMPLETED  # Partial success

    state["status"] = final_status

    # Update persistence
    user_id = state.get("user_id")
    persistence = PersistenceManager(user_id=user_id)
    persistence.update_run_status(
        state["run_id"],
        final_status,
        completed_count=state["completed_count"],
        failed_count=state["failed_count"],
        elapsed_seconds=state["elapsed_seconds"],
        completed_at=datetime.now(),
    )
    persistence.update_cost_summary(state["run_id"], state["cost_summary"])

    # Log summary
    logger.info(
        f"Run {state['run_id']} finalized: "
        f"{state['completed_count']}/{len(state['tickers'])} completed, "
        f"{state['failed_count']} failed, "
        f"${state['cost_summary'].total_cost_usd:.2f} cost, "
        f"{state['elapsed_seconds']:.0f}s elapsed"
    )

    # Log watchlist candidates
    watchlist = [
        r.ticker
        for r in state["stock_results"].values()
        if r.is_watchlist_candidate
    ]
    if watchlist:
        logger.info(f"Watchlist candidates: {', '.join(watchlist)}")

    return state


# ============================================================================
# Graph Construction
# ============================================================================


def build_orchestration_graph() -> StateGraph:
    """Build the LangGraph workflow for orchestration.

    Returns:
        Compiled LangGraph StateGraph
    """
    workflow = StateGraph(SwarmOrchestrationState)

    # Add nodes
    workflow.add_node("initialize_run", initialize_run)
    workflow.add_node("select_next_ticker", select_next_ticker)
    workflow.add_node("analyze_stock", analyze_stock)
    workflow.add_node("finalize_run", finalize_run)

    # Add edges
    workflow.set_entry_point("initialize_run")
    workflow.add_edge("initialize_run", "select_next_ticker")
    workflow.add_edge("select_next_ticker", "analyze_stock")
    workflow.add_conditional_edges(
        "analyze_stock",
        check_completion,
        {
            "continue": "select_next_ticker",
            "complete": "finalize_run",
        },
    )
    workflow.add_edge("finalize_run", END)

    return workflow.compile()


# ============================================================================
# Public API
# ============================================================================


def run_batch(
    tickers: List[str],
    quarters: List[str] = None,
    fiscal_year: int = None,  # Deprecated - for backward compatibility
    news_days_back: int = 30,
    max_retries: int = 3,
    run_name: Optional[str] = None,
    user_id: Optional[str] = None,
) -> SwarmRun:
    """Run a batch analysis on multiple stocks.

    Args:
        tickers: List of stock tickers to analyze
        quarters: Quarters for TTM analysis (e.g., ["Q4_2024", "Q1_2025", "Q2_2025", "Q3_2025"])
        fiscal_year: [Deprecated] Fiscal year for annual analysis
        news_days_back: Days to look back for news analysis
        max_retries: Maximum retry attempts per stock
        run_name: Optional name for the run
        user_id: User ID for Neon persistence (auto-fetched if not provided)

    Returns:
        SwarmRun with complete results
    """
    from uuid import uuid4
    from datetime import datetime as dt
    import asyncio

    logger.info(f"Starting batch run with {len(tickers)} stocks")

    # Get or create CLI user if user_id not provided
    if not user_id:
        from api.lib.db import get_or_create_cli_user
        user_id = asyncio.run(get_or_create_cli_user())
        logger.info(f"Using CLI user: {user_id}")

    # Generate run ID
    run_id = str(uuid4())

    # Determine analysis period
    if quarters:
        analysis_period = f"TTM {quarters[0].replace('_', ' ')} - {quarters[-1].replace('_', ' ')}"
    elif fiscal_year:
        analysis_period = f"FY {fiscal_year}"
        logger.warning("Using deprecated fiscal_year parameter. Consider using quarters for TTM analysis.")
    else:
        # Default to current year
        current_year = dt.now().year
        analysis_period = f"FY {current_year}"
        logger.warning(f"No quarters or fiscal_year provided, defaulting to FY {current_year}")

    # Initialize state
    initial_state: SwarmOrchestrationState = {
        "run_id": run_id,
        "run_name": run_name,
        "tickers": tickers,
        "analysis_period": analysis_period,
        "quarters": quarters or [],
        "fiscal_year": fiscal_year,  # Backward compatibility
        "news_days_back": news_days_back,
        "max_retries": max_retries,
        "status": RunStatus.INITIALIZED,
        "current_ticker": None,
        "stock_results": {},
        "completed_count": 0,
        "failed_count": 0,
        "cost_summary": CostSummary(),
        "start_time": None,
        "elapsed_seconds": 0.0,
        "last_error": None,
        "user_id": user_id,  # Add user_id for persistence
    }

    # Build and run graph
    graph = build_orchestration_graph()
    final_state = graph.invoke(initial_state)

    # Load final results from persistence
    persistence = PersistenceManager(user_id=user_id)
    swarm_run = persistence.get_run(run_id)

    return swarm_run


def resume_batch(run_id: str) -> SwarmRun:
    """Resume a paused or failed batch run.

    Args:
        run_id: Run ID to resume

    Returns:
        SwarmRun with updated results
    """
    logger.info(f"Resuming run {run_id}")

    # Get CLI user for persistence
    import asyncio
    from api.lib.db import get_or_create_cli_user
    user_id = asyncio.run(get_or_create_cli_user())

    # Load run from persistence
    persistence = PersistenceManager(user_id=user_id)
    swarm_run = persistence.get_run(run_id)

    if not swarm_run:
        raise ValueError(f"Run {run_id} not found")

    if swarm_run.pending_count == 0:
        logger.warning(f"Run {run_id} has no pending stocks")
        return swarm_run

    # Convert to state
    state: SwarmOrchestrationState = {
        "run_id": swarm_run.run_id,
        "run_name": swarm_run.run_name,
        "tickers": swarm_run.tickers,
        "analysis_period": swarm_run.analysis_period,
        "quarters": swarm_run.quarters,
        "fiscal_year": swarm_run.fiscal_year,  # Backward compatibility
        "news_days_back": swarm_run.news_days_back,
        "max_retries": swarm_run.max_retries,
        "status": RunStatus.RUNNING,
        "current_ticker": None,
        "stock_results": swarm_run.stock_results,
        "completed_count": swarm_run.completed_count,
        "failed_count": swarm_run.failed_count,
        "cost_summary": swarm_run.cost_summary,
        "start_time": time.time(),
        "elapsed_seconds": swarm_run.elapsed_seconds,
        "last_error": None,
    }

    # Update status to running
    persistence.update_run_status(run_id, RunStatus.RUNNING)

    # Continue from select_next_ticker
    graph = build_orchestration_graph()

    # We need to skip initialize_run, so we'll build a partial graph
    # For simplicity, we'll reconstruct the state and run the full graph
    # The select_next_ticker will pick up where it left off
    final_state = graph.invoke(state)

    # Load final results
    swarm_run = persistence.get_run(run_id)

    return swarm_run


def get_run_history(limit: int = 20, user_id: Optional[str] = None) -> List[SwarmRun]:
    """Get recent run history.

    Args:
        limit: Maximum number of runs to return
        user_id: User ID (auto-fetched if not provided)

    Returns:
        List of SwarmRun objects, most recent first
    """
    import asyncio
    if not user_id:
        from api.lib.db import get_or_create_cli_user
        user_id = asyncio.run(get_or_create_cli_user())

    persistence = PersistenceManager(user_id=user_id)
    return persistence.get_run_history(limit)


def get_resumable_runs(user_id: Optional[str] = None) -> List[SwarmRun]:
    """Get runs that can be resumed.

    Args:
        user_id: User ID (auto-fetched if not provided)

    Returns:
        List of SwarmRun objects with pending stocks
    """
    import asyncio
    if not user_id:
        from api.lib.db import get_or_create_cli_user
        user_id = asyncio.run(get_or_create_cli_user())

    persistence = PersistenceManager(user_id=user_id)
    return persistence.get_resumable_runs()


def estimate_cost(
    tickers: List[str],
    tokens_per_stock: int = 15000,
) -> dict:
    """Estimate cost for a batch run.

    Args:
        tickers: List of stock tickers
        tokens_per_stock: Estimated tokens per stock (default 15k)

    Returns:
        Dictionary with cost estimate
    """
    from .models import RunEstimate

    ticker_count = len(tickers)
    estimated_cost = CostTracker.estimate_run_cost(ticker_count, tokens_per_stock)

    # Estimate time (rough: 6 minutes per stock)
    estimated_minutes = ticker_count * 6
    estimated_time_human = (
        f"{estimated_minutes} minutes"
        if estimated_minutes < 60
        else f"{estimated_minutes / 60:.1f} hours"
    )

    # Check budget
    monthly_budget = 200.0
    budget_check = CostTracker.check_budget(estimated_cost, monthly_budget)

    return RunEstimate(
        tickers=tickers,
        estimated_total_time_human=estimated_time_human,
        estimated_cost_usd=estimated_cost,
        within_budget=budget_check["within_budget"],
        runs_remaining_this_month=budget_check["runs_remaining_this_month"],
    )
