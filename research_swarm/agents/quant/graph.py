"""
LangGraph workflow for the Quant agent.

Orchestrates the quantitative analysis pipeline from market data to scoring.
"""
import time
from datetime import datetime
from typing import Optional
from langgraph.graph import StateGraph, END
from loguru import logger

from research_swarm.data import market_data_client
from research_swarm.data.supply_chain_knowledge import supply_chain_kb
from research_swarm.agents.fundamentalist.models import SupplyChainOutput as FundamentalistSupplyChain
from .state import QuantState
from .technical import TechnicalAnalyzer
from .supply_chain import SupplyChainGraphBuilder
from .analyzer import QuantAnalyzer
from .scorer import TechnicalScorer, SupplyChainScorer
from .models import (
    TechnicalIndicators,
    SupplyChainGraph,
    QuantOutput,
    TechnicalScoreBreakdown,
    SupplyChainScoreBreakdown,
)


# Initialize singletons
technical_analyzer = TechnicalAnalyzer()
graph_builder = SupplyChainGraphBuilder()
quant_analyzer = QuantAnalyzer()
technical_scorer = TechnicalScorer()
supply_chain_scorer = SupplyChainScorer()


# ============================================================================
# Node Functions
# ============================================================================

def fetch_market_data_node(state: QuantState) -> QuantState:
    """
    Node 1: Fetch historical market data from yfinance.

    Args:
        state: Current workflow state

    Returns:
        Updated state with historical_data
    """
    logger.info(f"[Node 1] Fetching market data for {state['ticker']}")

    state["status"] = "fetching_data"
    state["node_timestamps"] = {**state.get("node_timestamps", {}), "fetch_market_data": time.time()}

    # Fetch historical data
    period = state.get("data_period", "1y")
    df = market_data_client.get_historical_data(state["ticker"], period=period)

    if df.empty:
        state["status"] = "error"
        state["error"] = f"No market data available for {state['ticker']}"
        logger.error(state["error"])
        return state

    state["historical_data"] = df
    state["data_period"] = period
    logger.success(f"✓ Fetched {len(df)} days of market data")

    return state


def calculate_indicators_node(state: QuantState) -> QuantState:
    """
    Node 2: Calculate technical indicators (SMA, RSI, volume, relative strength).

    Args:
        state: Current workflow state

    Returns:
        Updated state with technical indicators
    """
    logger.info(f"[Node 2] Calculating technical indicators for {state['ticker']}")

    state["status"] = "calculating_indicators"
    state["node_timestamps"] = {**state.get("node_timestamps", {}), "calculate_indicators": time.time()}

    # Calculate all indicators
    indicators = technical_analyzer.analyze_ticker(
        state["ticker"],
        period=state.get("data_period", "1y")
    )

    # Store in state as dict
    state["technical_indicators"] = indicators.model_dump()
    state["moving_averages"] = indicators.moving_averages.model_dump()
    state["rsi"] = indicators.rsi.model_dump()
    state["volume"] = indicators.volume.model_dump()
    state["relative_strength"] = indicators.relative_strength.model_dump()

    logger.success(f"✓ Calculated technical indicators")

    return state


def build_supply_chain_node(state: QuantState) -> QuantState:
    """
    Node 3: Build supply chain graph (from fundamentalist data if available).

    Args:
        state: Current workflow state

    Returns:
        Updated state with supply_chain_graph
    """
    logger.info(f"[Node 3] Building supply chain graph for {state['ticker']}")

    state["status"] = "building_graph"
    state["node_timestamps"] = {**state.get("node_timestamps", {}), "build_supply_chain": time.time()}

    # Get supply chain depth
    max_depth = state.get("supply_chain_depth", 2)

    # Check if fundamentalist data is available
    if state.get("fundamentalist_supply_chain"):
        # Reconstruct FundamentalistSupplyChain from dict
        fund_sc_data = state["fundamentalist_supply_chain"]
        fund_sc = FundamentalistSupplyChain(**fund_sc_data)
        logger.info("Using fundamentalist supply chain data")
    else:
        # Create empty supply chain (no fundamentalist data)
        fund_sc = FundamentalistSupplyChain()
        logger.warning("No fundamentalist supply chain data - building basic graph")

    # Build graph
    supply_chain_graph = graph_builder.build_from_fundamentalist_data(
        root_ticker=state["ticker"],
        supply_chain_data=fund_sc,
        max_depth=max_depth
    )

    # Store in state
    state["supply_chain_graph"] = supply_chain_graph.model_dump()

    logger.success(
        f"✓ Built supply chain graph: "
        f"{len(supply_chain_graph.nodes)} nodes, "
        f"{len(supply_chain_graph.edges)} edges, "
        f"depth={supply_chain_graph.max_depth}"
    )

    return state


def identify_hidden_deps_node(state: QuantState) -> QuantState:
    """
    Node 4: Identify hidden dependencies using LLM (Haiku).

    Args:
        state: Current workflow state

    Returns:
        Updated state with hidden dependencies analysis
    """
    logger.info(f"[Node 4] Identifying hidden dependencies for {state['ticker']}")

    state["node_timestamps"] = {**state.get("node_timestamps", {}), "identify_hidden_deps": time.time()}

    # Reconstruct supply chain graph
    supply_chain_graph = SupplyChainGraph(**state["supply_chain_graph"])

    # Analyze hidden dependencies
    hidden_deps, tokens = quant_analyzer.analyze_hidden_dependencies(
        ticker=state["ticker"],
        analysis_date=state["analysis_date"],
        supply_chain_graph=supply_chain_graph
    )

    # Update state
    state["hidden_dependencies_analysis"] = hidden_deps.get("summary", "")
    state["tokens_used"] = state.get("tokens_used", 0) + tokens

    logger.success(f"✓ Analyzed hidden dependencies ({tokens} tokens)")

    return state


def analyze_combined_node(state: QuantState) -> QuantState:
    """
    Node 5: Generate narrative analyses using LLM (Sonnet).

    Args:
        state: Current workflow state

    Returns:
        Updated state with technical and supply chain narratives
    """
    logger.info(f"[Node 5] Generating analysis narratives for {state['ticker']}")

    state["status"] = "analyzing"
    state["node_timestamps"] = {**state.get("node_timestamps", {}), "analyze_combined": time.time()}

    # Reconstruct models
    technical_indicators = TechnicalIndicators(**state["technical_indicators"])
    supply_chain_graph = SupplyChainGraph(**state["supply_chain_graph"])

    # Generate technical analysis
    technical_analysis, tech_tokens = quant_analyzer.generate_technical_analysis(
        ticker=state["ticker"],
        analysis_date=state["analysis_date"],
        indicators=technical_indicators
    )
    state["technical_analysis"] = technical_analysis
    state["tokens_used"] = state.get("tokens_used", 0) + tech_tokens

    # Generate supply chain analysis
    sc_analysis, sc_tokens = quant_analyzer.generate_supply_chain_analysis(
        ticker=state["ticker"],
        analysis_date=state["analysis_date"],
        supply_chain_graph=supply_chain_graph
    )
    state["supply_chain_analysis"] = sc_analysis
    state["tokens_used"] = state.get("tokens_used", 0) + sc_tokens

    logger.success(
        f"✓ Generated analyses "
        f"({tech_tokens + sc_tokens} tokens)"
    )

    return state


def score_quant_node(state: QuantState) -> QuantState:
    """
    Node 6: Calculate quantitative scores.

    Args:
        state: Current workflow state

    Returns:
        Updated state with scores
    """
    logger.info(f"[Node 6] Scoring quantitative metrics for {state['ticker']}")

    state["status"] = "scoring"
    state["node_timestamps"] = {**state.get("node_timestamps", {}), "score_quant": time.time()}

    # Reconstruct models
    technical_indicators = TechnicalIndicators(**state["technical_indicators"])
    supply_chain_graph = SupplyChainGraph(**state["supply_chain_graph"])

    # Score technical
    technical_breakdown = technical_scorer.score_technical(technical_indicators)
    technical_score = technical_breakdown.weighted_average()

    # Score supply chain
    supply_chain_breakdown = supply_chain_scorer.score_supply_chain(supply_chain_graph)
    supply_chain_score = supply_chain_breakdown.weighted_average()

    # Combined quant score (50/50 weight)
    quant_score = (technical_score + supply_chain_score) / 2

    # Calculate confidence based on data availability
    confidence = _calculate_confidence(technical_indicators, supply_chain_graph)

    # Update state
    state["technical_score"] = technical_score
    state["technical_breakdown"] = technical_breakdown.model_dump()
    state["supply_chain_score"] = supply_chain_score
    state["supply_chain_breakdown"] = supply_chain_breakdown.model_dump()
    state["quant_score"] = quant_score
    state["confidence"] = confidence
    state["status"] = "completed"

    logger.success(
        f"✓ Scoring complete: {state['ticker']} "
        f"(Quant={quant_score:.2f}, Tech={technical_score:.2f}, SC={supply_chain_score:.2f})"
    )

    return state


def _calculate_confidence(
    indicators: TechnicalIndicators,
    graph: SupplyChainGraph
) -> float:
    """
    Calculate confidence level based on data completeness.

    Args:
        indicators: Technical indicators
        graph: Supply chain graph

    Returns:
        Confidence level (0-1)
    """
    confidence = 1.0

    # Reduce confidence for missing technical data
    if indicators.moving_averages.sma_50 is None:
        confidence -= 0.1
    if indicators.moving_averages.sma_200 is None:
        confidence -= 0.1
    if indicators.rsi.rsi_14 is None:
        confidence -= 0.1
    if indicators.volume.volume_ratio is None:
        confidence -= 0.05
    if indicators.relative_strength.vs_sector_3m is None:
        confidence -= 0.1
    if indicators.relative_strength.vs_market_3m is None:
        confidence -= 0.05

    # Reduce confidence for limited supply chain data
    if len(graph.nodes) <= 1:
        confidence -= 0.2
    elif len(graph.nodes) <= 3:
        confidence -= 0.1

    if graph.max_depth < 2:
        confidence -= 0.1

    return max(0.0, min(1.0, confidence))


def should_continue(state: QuantState) -> str:
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

def build_quant_graph() -> StateGraph:
    """
    Build the LangGraph workflow for Quant agent.

    Returns:
        Compiled StateGraph
    """
    workflow = StateGraph(QuantState)

    # Add nodes
    workflow.add_node("fetch_market_data", fetch_market_data_node)
    workflow.add_node("calculate_indicators", calculate_indicators_node)
    workflow.add_node("build_supply_chain", build_supply_chain_node)
    workflow.add_node("identify_hidden_deps", identify_hidden_deps_node)
    workflow.add_node("analyze_combined", analyze_combined_node)
    workflow.add_node("score_quant", score_quant_node)

    # Set entry point
    workflow.set_entry_point("fetch_market_data")

    # Add edges - sequential flow
    workflow.add_edge("fetch_market_data", "calculate_indicators")
    workflow.add_edge("calculate_indicators", "build_supply_chain")
    workflow.add_edge("build_supply_chain", "identify_hidden_deps")
    workflow.add_edge("identify_hidden_deps", "analyze_combined")
    workflow.add_edge("analyze_combined", "score_quant")

    # Score quant is the final node
    workflow.set_finish_point("score_quant")

    return workflow.compile()


# ============================================================================
# Main Analysis Function
# ============================================================================

def analyze_quant(
    ticker: str,
    supply_chain_depth: int = 2,
    fundamentalist_supply_chain: Optional[FundamentalistSupplyChain] = None
) -> QuantOutput:
    """
    Perform quantitative analysis on a company.

    Args:
        ticker: Stock ticker (e.g., "NVDA")
        supply_chain_depth: Maximum supply chain tier depth (default 2)
        fundamentalist_supply_chain: Optional supply chain data from Fundamentalist agent

    Returns:
        QuantOutput with complete quantitative analysis

    Raises:
        ValueError: If analysis fails
    """
    logger.info(f"=== Analyzing {ticker} (Quant) ===")

    start_time = time.time()
    analysis_date = datetime.now().strftime("%Y-%m-%d")

    # Initialize state
    initial_state: QuantState = {
        "ticker": ticker,
        "analysis_date": analysis_date,
        "supply_chain_depth": supply_chain_depth,
        "status": "initialized",
        "tokens_used": 0,
        "error": None,
        "historical_data": None,
        "data_period": "1y",
        "technical_indicators": None,
        "moving_averages": None,
        "rsi": None,
        "volume": None,
        "relative_strength": None,
        "fundamentalist_supply_chain": fundamentalist_supply_chain.model_dump() if fundamentalist_supply_chain else None,
        "supply_chain_graph": None,
        "networkx_graph": None,
        "technical_analysis": None,
        "supply_chain_analysis": None,
        "hidden_dependencies_analysis": None,
        "technical_score": None,
        "technical_breakdown": None,
        "supply_chain_score": None,
        "supply_chain_breakdown": None,
        "quant_score": None,
        "confidence": None,
        "processing_time": None,
        "node_timestamps": {},
    }

    # Build and run workflow
    graph = build_quant_graph()
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
    output = QuantOutput(
        ticker=final_state["ticker"],
        analysis_date=final_state["analysis_date"],
        technical_indicators=TechnicalIndicators(**final_state["technical_indicators"]),
        technical_analysis=final_state["technical_analysis"],
        technical_score=final_state["technical_score"],
        technical_breakdown=TechnicalScoreBreakdown(**final_state["technical_breakdown"]),
        supply_chain_graph=SupplyChainGraph(**final_state["supply_chain_graph"]),
        supply_chain_analysis=final_state["supply_chain_analysis"],
        supply_chain_score=final_state["supply_chain_score"],
        supply_chain_breakdown=SupplyChainScoreBreakdown(**final_state["supply_chain_breakdown"]),
        quant_score=final_state["quant_score"],
        confidence=final_state["confidence"],
        tokens_used=final_state.get("tokens_used", 0),
        processing_time=processing_time
    )

    logger.success(
        f"=== Quant Analysis Complete: {ticker} "
        f"(Score: {output.quant_score:.2f}, Time: {processing_time:.1f}s, Tokens: {output.tokens_used}) ==="
    )

    return output
