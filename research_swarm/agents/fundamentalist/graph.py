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

    metrics = analyzer.extract_metrics(
        state["ticker"],
        state["fiscal_year"],
        state["parsed_sections"]
    )

    state["financial_metrics"] = metrics.model_dump()

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

    supply_chain = analyzer.extract_supply_chain(
        state["ticker"],
        state["fiscal_year"],
        state["parsed_sections"]
    )

    state["supply_chain_data"] = supply_chain.model_dump()

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

    # Reconstruct Pydantic models from state dicts
    from research_swarm.agents.fundamentalist.models import (
        FinancialMetricsOutput,
        SupplyChainOutput
    )

    metrics = FinancialMetricsOutput(**state["financial_metrics"])
    supply_chain = SupplyChainOutput(**state["supply_chain_data"])

    analysis = analyzer.analyze_qualitative(
        state["ticker"],
        state["fiscal_year"],
        state["parsed_sections"],
        metrics,
        supply_chain
    )

    state["financial_analysis"] = analysis

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

    state["status"] = "scoring"

    # Reconstruct Pydantic models
    from research_swarm.agents.fundamentalist.models import (
        FinancialMetricsOutput,
        SupplyChainOutput
    )

    metrics = FinancialMetricsOutput(**state["financial_metrics"])
    supply_chain = SupplyChainOutput(**state["supply_chain_data"])

    # Score
    overall_score, breakdown, confidence = scorer.score_health(
        state["ticker"],
        state["fiscal_year"],
        metrics,
        supply_chain,
        state["financial_analysis"]
    )

    state["financial_health_score"] = overall_score
    state["score_breakdown"] = breakdown.model_dump()
    state["confidence"] = confidence
    state["status"] = "completed"

    logger.success(f"✓ Analysis complete: {state['ticker']} score = {overall_score:.2f}")

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


# ============================================================================
# Main Analysis Function
# ============================================================================

def analyze_company(ticker: str, fiscal_year: int) -> FundamentalistOutput:
    """
    Analyze a company's financial health from its 10-K filing.

    Args:
        ticker: Stock ticker (e.g., "AAPL")
        fiscal_year: Fiscal year to analyze (e.g., 2023)

    Returns:
        FundamentalistOutput with complete analysis

    Raises:
        ValueError: If analysis fails
    """
    logger.info(f"=== Analyzing {ticker} Fiscal Year {fiscal_year} ===")

    start_time = time.time()

    # Initialize state
    initial_state: FundamentalistState = {
        "ticker": ticker,
        "fiscal_year": fiscal_year,
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
