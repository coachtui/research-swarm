"""
LangGraph workflow for the Fundamentalist agent.

Orchestrates the analysis pipeline from 10-K fetching to health scoring.
"""
import time
from typing import Dict, Any
from langgraph.graph import StateGraph, END
from research_swarm.logger import logger
from research_swarm.data.sec_client import sec_client
from research_swarm.agents.fundamentalist.state import FundamentalistState
from research_swarm.agents.fundamentalist.parser import parser
from research_swarm.agents.fundamentalist.analyzer import analyzer
from research_swarm.agents.fundamentalist.scorer import scorer
from research_swarm.agents.fundamentalist.models import FundamentalistOutput


# ============================================================================
# Node Functions
# ============================================================================

def fetch_filing_node(state: FundamentalistState) -> FundamentalistState:
    """
    Node 1: Fetch 10-K filing from SEC.

    Args:
        state: Current workflow state

    Returns:
        Updated state with filing_raw
    """
    logger.info(f"[Node 1] Fetching 10-K for {state['ticker']} {state['fiscal_year']}")

    state["status"] = "fetching"

    # Fetch from SEC
    filing = sec_client.get_10k_filing(state["ticker"], state["fiscal_year"])

    if not filing:
        state["status"] = "error"
        state["error"] = f"Failed to fetch 10-K for {state['ticker']} {state['fiscal_year']}"
        logger.error(state["error"])
        return state

    state["filing_raw"] = filing
    logger.success(f"✓ Fetched 10-K ({filing.get('text_length', 0):,} chars)")

    return state


def parse_sections_node(state: FundamentalistState) -> FundamentalistState:
    """
    Node 2: Parse 10-K sections (Items 1, 1A, 7, 8).

    Args:
        state: Current workflow state

    Returns:
        Updated state with parsed_sections
    """
    logger.info(f"[Node 2] Parsing 10-K sections for {state['ticker']}")

    state["status"] = "parsing"

    filing = state["filing_raw"]
    filing_text = filing.get("text", "")

    # Parse sections
    parsed = parser.parse_filing(
        state["ticker"],
        state["fiscal_year"],
        filing_text
    )

    if not parsed or all(not v for v in parsed.values()):
        state["status"] = "error"
        state["error"] = "Failed to parse any sections from 10-K"
        logger.error(state["error"])
        return state

    state["parsed_sections"] = parsed
    logger.success(f"✓ Parsed {len([v for v in parsed.values() if v])} sections")

    return state


def extract_metrics_node(state: FundamentalistState) -> FundamentalistState:
    """
    Node 3: Extract financial metrics.

    Args:
        state: Current workflow state

    Returns:
        Updated state with financial_metrics
    """
    logger.info(f"[Node 3] Extracting financial metrics for {state['ticker']}")

    state["status"] = "analyzing"

    try:
        metrics, tokens = analyzer.extract_metrics(
            state["ticker"],
            state["fiscal_year"],
            state["parsed_sections"]
        )

        if not metrics or metrics.revenue is None:
            raise ValueError("extract_metrics returned empty or None (revenue is None)")

        state["financial_metrics"] = metrics.model_dump()
        state["tokens_used"] = state.get("tokens_used", 0) + tokens

    except Exception as e:
        logger.error(f"Failed to extract metrics: {e}")
        state["status"] = "error"
        state["error"] = f"Failed to extract metrics: {str(e)}"

    return state


def extract_supply_chain_node(state: FundamentalistState) -> FundamentalistState:
    """
    Node 4: Extract supply chain data.

    Args:
        state: Current workflow state

    Returns:
        Updated state with supply_chain_data
    """
    logger.info(f"[Node 4] Extracting supply chain data for {state['ticker']}")

    # Skip if previous node failed
    if state.get("status") == "error":
        return state

    try:
        supply_chain, tokens = analyzer.extract_supply_chain(
            state["ticker"],
            state["fiscal_year"],
            state["parsed_sections"]
        )

        if not supply_chain:
            raise ValueError("extract_supply_chain returned None")

        state["supply_chain_data"] = supply_chain.model_dump()
        state["tokens_used"] = state.get("tokens_used", 0) + tokens

    except Exception as e:
        logger.error(f"Failed to extract supply chain: {e}")
        state["status"] = "error"
        state["error"] = f"Failed to extract supply chain: {str(e)}"

    return state


def analyze_qualitative_node(state: FundamentalistState) -> FundamentalistState:
    """
    Node 5: Perform qualitative analysis.

    Args:
        state: Current workflow state

    Returns:
        Updated state with financial_analysis
    """
    logger.info(f"[Node 5] Performing qualitative analysis for {state['ticker']}")

    # Skip if previous node failed
    if state.get("status") == "error":
        return state

    try:
        # Reconstruct Pydantic models from state dicts
        from research_swarm.agents.fundamentalist.models import (
            FinancialMetricsOutput,
            SupplyChainOutput
        )

        if not state.get("financial_metrics") or not state.get("supply_chain_data"):
            raise ValueError("Missing financial_metrics or supply_chain_data")

        metrics = FinancialMetricsOutput(**state["financial_metrics"])
        supply_chain = SupplyChainOutput(**state["supply_chain_data"])

        analysis, tokens = analyzer.analyze_qualitative(
            state["ticker"],
            state["fiscal_year"],
            state["parsed_sections"],
            metrics,
            supply_chain
        )

        if not analysis:
            raise ValueError("analyze_qualitative returned None")

        state["financial_analysis"] = analysis
        state["tokens_used"] = state.get("tokens_used", 0) + tokens

    except Exception as e:
        logger.error(f"Failed qualitative analysis: {e}")
        state["status"] = "error"
        state["error"] = f"Failed qualitative analysis: {str(e)}"

    return state


def score_health_node(state: FundamentalistState) -> FundamentalistState:
    """
    Node 6: Score financial health.

    Args:
        state: Current workflow state

    Returns:
        Updated state with health score and breakdown
    """
    logger.info(f"[Node 6] Scoring financial health for {state['ticker']}")

    # Skip if previous node failed
    if state.get("status") == "error":
        return state

    state["status"] = "scoring"

    try:
        # Reconstruct Pydantic models
        from research_swarm.agents.fundamentalist.models import (
            FinancialMetricsOutput,
            SupplyChainOutput
        )

        if not state.get("financial_metrics") or not state.get("supply_chain_data"):
            raise ValueError("Missing financial_metrics or supply_chain_data")

        metrics = FinancialMetricsOutput(**state["financial_metrics"])
        supply_chain = SupplyChainOutput(**state["supply_chain_data"])

        # Score
        overall_score, breakdown, confidence, tokens = scorer.score_health(
            state["ticker"],
            state["fiscal_year"],
            metrics,
            supply_chain,
            state["financial_analysis"]
        )

        if overall_score is None or breakdown is None or confidence is None:
            raise ValueError("score_health returned None values")

        state["financial_health_score"] = overall_score
        state["score_breakdown"] = breakdown.model_dump()
        state["confidence"] = confidence
        state["tokens_used"] = state.get("tokens_used", 0) + tokens
        state["status"] = "completed"

        logger.success(f"✓ Analysis complete: {state['ticker']} score = {overall_score:.2f} ({state['tokens_used']} total tokens)")

    except Exception as e:
        logger.error(f"Failed to score health: {e}")
        state["status"] = "error"
        state["error"] = f"Failed to score health: {str(e)}"

    return state


def should_continue(state: FundamentalistState) -> str:
    """
    Conditional edge: check if workflow should continue or stop.

    Args:
        state: Current workflow state

    Returns:
        "error" if error occurred, "continue" otherwise
    """
    if state.get("status") == "error":
        return "error"
    return "continue"


# ============================================================================
# TTM-SPECIFIC NODE FUNCTIONS
# ============================================================================

def fetch_quarterly_filings_node(state: FundamentalistState) -> FundamentalistState:
    """
    Node 1 (TTM): Fetch trailing 4 quarters of filings.

    Args:
        state: Current workflow state

    Returns:
        Updated state with filings_raw and metadata
    """
    logger.info(f"[Node 1-TTM] Fetching quarterly filings for {state['ticker']}")

    state["status"] = "fetching"

    # Use SEC client to get TTM filings
    ttm_result = sec_client.get_ttm_filings(state["ticker"])

    # Extract metadata (with underscore prefix)
    metadata = ttm_result.pop("_metadata", {})

    # Store filings keyed by quarter
    state["filings_raw"] = ttm_result
    state["quarters"] = metadata.get("quarters", [])
    state["analysis_period"] = metadata.get("analysis_period", "")
    state["data_quality"] = metadata.get("data_quality", {})

    available = metadata.get("available_quarters", 0)
    if available == 0:
        state["status"] = "error"
        state["error"] = f"No quarterly filings found for {state['ticker']}"
        return state

    logger.success(f"✓ Fetched {available}/4 quarterly filings")
    return state


def parse_quarterly_sections_node(state: FundamentalistState) -> FundamentalistState:
    """
    Node 2 (TTM): Parse sections for each quarter.

    Args:
        state: Current workflow state

    Returns:
        Updated state with parsed_sections_by_quarter
    """
    logger.info(f"[Node 2-TTM] Parsing quarterly sections for {state['ticker']}")

    state["status"] = "parsing"

    parsed_by_quarter = {}
    for quarter_label, filing in state["filings_raw"].items():
        if filing is None:
            continue

        filing_text = filing.get("text", "")
        if len(filing_text) < 1000:
            logger.warning(f"Insufficient text for {quarter_label}")
            continue

        # Pass filing type from metadata
        filing_type = filing.get("filing_type", "10-K")

        parsed = parser.parse_filing(
            state["ticker"],
            filing.get("year", 0),
            filing_text,
            filing_type=filing_type
        )

        if parsed and any(v for v in parsed.values()):
            parsed_by_quarter[quarter_label] = parsed

    if not parsed_by_quarter:
        state["status"] = "error"
        state["error"] = "Failed to parse any quarterly sections"
        return state

    state["parsed_sections_by_quarter"] = parsed_by_quarter
    logger.success(f"✓ Parsed {len(parsed_by_quarter)} quarters")
    return state


def extract_metrics_ttm_node(state: FundamentalistState) -> FundamentalistState:
    """
    Node 3 (TTM): Extract quarterly metrics and calculate TTM.

    Args:
        state: Current workflow state

    Returns:
        Updated state with quarterly_metrics, ttm_metrics, and quarterly_trends
    """
    logger.info(f"[Node 3-TTM] Extracting TTM metrics for {state['ticker']}")

    state["status"] = "analyzing"

    try:
        quarterly_metrics, ttm_metrics, trends, tokens = analyzer.extract_metrics_quarterly(
            state["ticker"],
            state["analysis_period"],
            state["quarters"],
            state["parsed_sections_by_quarter"]
        )

        # Store as dicts for state
        state["quarterly_metrics"] = [m.model_dump() for m in quarterly_metrics]
        state["ttm_metrics"] = ttm_metrics.model_dump()
        state["quarterly_trends"] = trends.model_dump()
        state["tokens_used"] = state.get("tokens_used", 0) + tokens

        # Also populate legacy financial_metrics for compatibility
        state["financial_metrics"] = {
            "revenue": ttm_metrics.ttm_revenue,
            "gross_margin": ttm_metrics.gross_margin,
            "operating_margin": ttm_metrics.operating_margin,
            "net_margin": ttm_metrics.net_margin,
            "revenue_growth_yoy": ttm_metrics.revenue_growth_yoy,
        }

    except Exception as e:
        logger.error(f"Failed to extract TTM metrics: {e}")
        state["status"] = "error"
        state["error"] = f"Failed to extract TTM metrics: {str(e)}"

    return state


def extract_supply_chain_ttm_node(state: FundamentalistState) -> FundamentalistState:
    """
    Node 4 (TTM): Extract supply chain data from most recent quarter.

    Args:
        state: Current workflow state

    Returns:
        Updated state with supply_chain_data
    """
    logger.info(f"[Node 4-TTM] Extracting supply chain data for {state['ticker']}")

    # Skip if previous node failed
    if state.get("status") == "error":
        return state

    try:
        # Supply chain data comes from 10-K only (has Item 1 and Item 1A)
        # Find the most recent 10-K filing from the quarters
        ten_k_quarter = None
        ten_k_parsed = {}

        for quarter_label in reversed(state["quarters"]):
            filing = state["filings_raw"].get(quarter_label)
            if filing and filing.get("filing_type") == "10-K":
                ten_k_quarter = quarter_label
                ten_k_parsed = state["parsed_sections_by_quarter"].get(quarter_label, {})
                break

        if not ten_k_quarter:
            logger.warning("No 10-K filing found for supply chain extraction")
            # Create empty supply chain data
            from research_swarm.agents.fundamentalist.models import SupplyChainOutput
            supply_chain = SupplyChainOutput()
            tokens = 0
        else:
            supply_chain, tokens = analyzer.extract_supply_chain(
                state["ticker"],
                0,  # fiscal_year not needed for supply chain
                ten_k_parsed
            )

        if not supply_chain:
            raise ValueError("extract_supply_chain returned None")

        state["supply_chain_data"] = supply_chain.model_dump()
        state["tokens_used"] = state.get("tokens_used", 0) + tokens

    except Exception as e:
        logger.error(f"Failed to extract supply chain: {e}")
        state["status"] = "error"
        state["error"] = f"Failed to extract supply chain: {str(e)}"

    return state


def analyze_qualitative_ttm_node(state: FundamentalistState) -> FundamentalistState:
    """
    Node 5 (TTM): Perform qualitative analysis with TTM context.

    Args:
        state: Current workflow state

    Returns:
        Updated state with financial_analysis
    """
    logger.info(f"[Node 5-TTM] Performing TTM qualitative analysis for {state['ticker']}")

    # Skip if previous node failed
    if state.get("status") == "error":
        return state

    try:
        # Reconstruct Pydantic models from state dicts
        from research_swarm.agents.fundamentalist.models import (
            TTMMetrics,
            QuarterlyTrends,
            SupplyChainOutput
        )

        if not state.get("ttm_metrics") or not state.get("supply_chain_data"):
            raise ValueError("Missing ttm_metrics or supply_chain_data")

        ttm_metrics = TTMMetrics(**state["ttm_metrics"])
        quarterly_trends = QuarterlyTrends(**state["quarterly_trends"])
        supply_chain = SupplyChainOutput(**state["supply_chain_data"])

        analysis, tokens = analyzer.analyze_qualitative_ttm(
            state["ticker"],
            state["analysis_period"],
            state["quarters"],
            state["parsed_sections_by_quarter"],
            ttm_metrics,
            quarterly_trends,
            supply_chain
        )

        if not analysis:
            raise ValueError("analyze_qualitative_ttm returned None")

        state["financial_analysis"] = analysis
        state["tokens_used"] = state.get("tokens_used", 0) + tokens

    except Exception as e:
        logger.error(f"Failed TTM qualitative analysis: {e}")
        state["status"] = "error"
        state["error"] = f"Failed TTM qualitative analysis: {str(e)}"

    return state


def score_health_ttm_node(state: FundamentalistState) -> FundamentalistState:
    """
    Node 6 (TTM): Score financial health with trend adjustments.

    Args:
        state: Current workflow state

    Returns:
        Updated state with health score and breakdown
    """
    logger.info(f"[Node 6-TTM] Scoring TTM financial health for {state['ticker']}")

    # Skip if previous node failed
    if state.get("status") == "error":
        return state

    state["status"] = "scoring"

    try:
        # Reconstruct Pydantic models
        from research_swarm.agents.fundamentalist.models import (
            TTMMetrics,
            QuarterlyTrends,
            SupplyChainOutput
        )

        if not state.get("ttm_metrics") or not state.get("supply_chain_data"):
            raise ValueError("Missing ttm_metrics or supply_chain_data")

        ttm_metrics = TTMMetrics(**state["ttm_metrics"])
        quarterly_trends = QuarterlyTrends(**state["quarterly_trends"])
        supply_chain = SupplyChainOutput(**state["supply_chain_data"])

        # Score using TTM-aware scorer method (will be implemented in Phase 6)
        overall_score, breakdown, confidence, tokens = scorer.score_health_ttm(
            state["ticker"],
            state["analysis_period"],
            ttm_metrics,
            quarterly_trends,
            supply_chain,
            state["financial_analysis"],
            state["data_quality"]
        )

        if overall_score is None or breakdown is None or confidence is None:
            raise ValueError("score_health_ttm returned None values")

        state["financial_health_score"] = overall_score
        state["score_breakdown"] = breakdown.model_dump()
        state["confidence"] = confidence
        state["tokens_used"] = state.get("tokens_used", 0) + tokens
        state["status"] = "completed"

        logger.success(f"✓ TTM Analysis complete: {state['ticker']} score = {overall_score:.2f} ({state['tokens_used']} total tokens)")

    except Exception as e:
        logger.error(f"Failed to score TTM health: {e}")
        state["status"] = "error"
        state["error"] = f"Failed to score TTM health: {str(e)}"

    return state


# ============================================================================
# Build Workflow Graph
# ============================================================================

def build_fundamentalist_graph() -> StateGraph:
    """
    Build the LangGraph workflow for Fundamentalist agent.

    Returns:
        Compiled StateGraph
    """
    workflow = StateGraph(FundamentalistState)

    # Add nodes
    workflow.add_node("fetch_filing", fetch_filing_node)
    workflow.add_node("parse_sections", parse_sections_node)
    workflow.add_node("extract_metrics", extract_metrics_node)
    workflow.add_node("extract_supply_chain", extract_supply_chain_node)
    workflow.add_node("analyze_qualitative", analyze_qualitative_node)
    workflow.add_node("score_health", score_health_node)

    # Set entry point
    workflow.set_entry_point("fetch_filing")

    # Add edges - sequential flow
    workflow.add_edge("fetch_filing", "parse_sections")
    workflow.add_edge("parse_sections", "extract_metrics")
    workflow.add_edge("extract_metrics", "extract_supply_chain")
    workflow.add_edge("extract_supply_chain", "analyze_qualitative")
    workflow.add_edge("analyze_qualitative", "score_health")

    # Score health is the final node
    workflow.set_finish_point("score_health")

    return workflow.compile()


def build_fundamentalist_graph_ttm() -> StateGraph:
    """
    Build the LangGraph workflow for Fundamentalist agent (TTM mode).

    Returns:
        Compiled StateGraph for TTM analysis
    """
    workflow = StateGraph(FundamentalistState)

    # Add TTM-specific nodes
    workflow.add_node("fetch_quarterly_filings", fetch_quarterly_filings_node)
    workflow.add_node("parse_quarterly_sections", parse_quarterly_sections_node)
    workflow.add_node("extract_metrics_ttm", extract_metrics_ttm_node)
    workflow.add_node("extract_supply_chain_ttm", extract_supply_chain_ttm_node)
    workflow.add_node("analyze_qualitative_ttm", analyze_qualitative_ttm_node)
    workflow.add_node("score_health_ttm", score_health_ttm_node)

    # Set entry point
    workflow.set_entry_point("fetch_quarterly_filings")

    # Add edges - sequential flow
    workflow.add_edge("fetch_quarterly_filings", "parse_quarterly_sections")
    workflow.add_edge("parse_quarterly_sections", "extract_metrics_ttm")
    workflow.add_edge("extract_metrics_ttm", "extract_supply_chain_ttm")
    workflow.add_edge("extract_supply_chain_ttm", "analyze_qualitative_ttm")
    workflow.add_edge("analyze_qualitative_ttm", "score_health_ttm")

    # Score health is the final node
    workflow.set_finish_point("score_health_ttm")

    return workflow.compile()


# ============================================================================
# Main Analysis Function
# ============================================================================

def analyze_company(
    ticker: str,
    quarters: list = None,
    fiscal_year: int = None,
    mode: str = "ttm"
) -> FundamentalistOutput:
    """
    Analyze a company's financial health.

    Args:
        ticker: Stock ticker (e.g., "AAPL")
        quarters: List of quarters for TTM mode (default: fetch latest 4 quarters)
        fiscal_year: Fiscal year for annual mode (deprecated)
        mode: "ttm" or "annual" (default: "ttm")

    Returns:
        FundamentalistOutput with complete analysis

    Raises:
        ValueError: If analysis fails
    """
    # Determine mode
    if fiscal_year is not None:
        mode = "annual"
        logger.warning(f"fiscal_year parameter is deprecated. Using annual mode for {ticker} FY{fiscal_year}")

    if mode == "ttm":
        return _analyze_company_ttm(ticker, quarters)
    else:
        return _analyze_company_annual(ticker, fiscal_year)


def _analyze_company_ttm(ticker: str, quarters: list = None) -> FundamentalistOutput:
    """
    Analyze company using TTM (quarterly) data.

    Args:
        ticker: Stock ticker
        quarters: Optional list of quarters (auto-fetched if None)

    Returns:
        FundamentalistOutput with TTM analysis
    """
    logger.info(f"=== Analyzing {ticker} (TTM Mode) ===")

    start_time = time.time()

    # Initialize TTM state
    initial_state: FundamentalistState = {
        "ticker": ticker,
        "analysis_mode": "ttm",
        "status": "initialized",
        "tokens_used": 0,
        "error": None,
        "filings_raw": None,
        "parsed_sections_by_quarter": None,
        "quarterly_metrics": None,
        "ttm_metrics": None,
        "quarterly_trends": None,
        "supply_chain_data": None,
        "financial_analysis": None,
        "financial_health_score": None,
        "score_breakdown": None,
        "confidence": None,
        "processing_time": None,
        "quarters": quarters or [],
        "analysis_period": "",
        "data_quality": {},
    }

    # Build and run TTM workflow
    graph = build_fundamentalist_graph_ttm()
    final_state = graph.invoke(initial_state)

    # Check for errors
    if final_state.get("status") == "error":
        error_msg = final_state.get("error", "Unknown error")
        logger.error(f"TTM Analysis failed: {error_msg}")
        raise ValueError(error_msg)

    # Calculate processing time
    processing_time = time.time() - start_time
    final_state["processing_time"] = processing_time

    # Build output
    from research_swarm.agents.fundamentalist.models import (
        FinancialMetricsOutput,
        SupplyChainOutput,
        ScoreBreakdown,
        QuarterlyMetrics,
        TTMMetrics,
        QuarterlyTrends
    )

    # Get filing dates
    filing_dates = {}
    for quarter, filing in final_state.get("filings_raw", {}).items():
        if filing:
            filing_dates[quarter] = filing.get("filing_date", "")

    output = FundamentalistOutput(
        ticker=final_state["ticker"],
        analysis_period=final_state["analysis_period"],
        quarters_analyzed=final_state["quarters"],
        analysis_mode="ttm",
        filing_date=filing_dates.get(final_state["quarters"][-1]) if final_state["quarters"] else None,
        filing_dates=filing_dates,
        quarterly_metrics=[QuarterlyMetrics(**q) for q in final_state.get("quarterly_metrics", [])],
        ttm_metrics=TTMMetrics(**final_state["ttm_metrics"]) if final_state.get("ttm_metrics") else None,
        quarterly_trends=QuarterlyTrends(**final_state["quarterly_trends"]) if final_state.get("quarterly_trends") else None,
        data_quality=final_state.get("data_quality", {}),
        financial_metrics=FinancialMetricsOutput(**final_state["financial_metrics"]),
        supply_chain_data=SupplyChainOutput(**final_state["supply_chain_data"]),
        financial_analysis=final_state["financial_analysis"],
        financial_health_score=final_state["financial_health_score"],
        score_breakdown=ScoreBreakdown(**final_state["score_breakdown"]),
        confidence=final_state["confidence"],
        tokens_used=final_state.get("tokens_used", 0),
        processing_time=processing_time
    )

    logger.success(
        f"=== TTM Analysis Complete: {ticker} "
        f"(Score: {output.financial_health_score:.2f}, Time: {processing_time:.1f}s) ==="
    )

    return output


def _analyze_company_annual(ticker: str, fiscal_year: int) -> FundamentalistOutput:
    """
    Analyze company using annual (10-K) data.

    Args:
        ticker: Stock ticker
        fiscal_year: Fiscal year

    Returns:
        FundamentalistOutput with annual analysis
    """
    logger.info(f"=== Analyzing {ticker} Fiscal Year {fiscal_year} (Annual Mode) ===")

    start_time = time.time()

    # Initialize state
    initial_state: FundamentalistState = {
        "ticker": ticker,
        "fiscal_year": fiscal_year,
        "analysis_mode": "annual",
        "status": "initialized",
        "tokens_used": 0,
        "error": None,
        "filing_raw": None,
        "parsed_sections": None,
        "financial_metrics": None,
        "supply_chain_data": None,
        "financial_analysis": None,
        "financial_health_score": None,
        "score_breakdown": None,
        "confidence": None,
        "processing_time": None,
    }

    # Build and run workflow
    graph = build_fundamentalist_graph()
    final_state = graph.invoke(initial_state)

    # Check for errors
    if final_state.get("status") == "error":
        error_msg = final_state.get("error", "Unknown error")
        logger.error(f"Analysis failed: {error_msg}")
        raise ValueError(error_msg)

    # Calculate processing time
    processing_time = time.time() - start_time
    final_state["processing_time"] = processing_time

    # Build output
    from research_swarm.agents.fundamentalist.models import (
        FinancialMetricsOutput,
        SupplyChainOutput,
        ScoreBreakdown
    )

    output = FundamentalistOutput(
        ticker=final_state["ticker"],
        fiscal_year=final_state["fiscal_year"],
        analysis_period=f"FY {fiscal_year}",
        analysis_mode="annual",
        filing_date=final_state["filing_raw"].get("filing_date"),
        financial_metrics=FinancialMetricsOutput(**final_state["financial_metrics"]),
        supply_chain_data=SupplyChainOutput(**final_state["supply_chain_data"]),
        financial_analysis=final_state["financial_analysis"],
        financial_health_score=final_state["financial_health_score"],
        score_breakdown=ScoreBreakdown(**final_state["score_breakdown"]),
        confidence=final_state["confidence"],
        tokens_used=final_state.get("tokens_used", 0),
        processing_time=processing_time
    )

    logger.success(
        f"=== Analysis Complete: {ticker} {fiscal_year} "
        f"(Score: {output.financial_health_score:.2f}, Time: {processing_time:.1f}s) ==="
    )

    return output
