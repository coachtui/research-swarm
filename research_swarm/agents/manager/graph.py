"""
LangGraph workflow for the Manager agent.

Orchestrates all three research agents and synthesizes findings into
a unified investment analysis with moat scoring.
"""
import time
from datetime import datetime
from typing import Optional
from langgraph.graph import StateGraph
from loguru import logger

from research_swarm.agents.fundamentalist import analyze_company, FundamentalistOutput
from research_swarm.agents.news_hound import analyze_company_news, NewsHoundOutput
from research_swarm.agents.quant import analyze_quant, QuantOutput

from .state import ManagerState
from .analyzer import ManagerAnalyzer
from .scorer import ManagerScorer
from .models import ManagerOutput, MoatScoreBreakdown


# Initialize singletons
manager_analyzer = ManagerAnalyzer()
manager_scorer = ManagerScorer()


# ============================================================================
# Node Functions
# ============================================================================

def call_fundamentalist_node(state: ManagerState) -> ManagerState:
    """
    Node 1: Call Fundamentalist agent.

    Args:
        state: Current workflow state

    Returns:
        Updated state with fundamentalist_output and financial_health_score
    """
    logger.info(f"[Node 1] Calling Fundamentalist agent for {state['ticker']}")

    state["status"] = "calling_fundamentalist"
    state["node_timestamps"] = {**state.get("node_timestamps", {}), "call_fundamentalist": time.time()}

    try:
        # Call Fundamentalist agent
        fundamentalist_output = analyze_company(
            ticker=state["ticker"],
            fiscal_year=state["fiscal_year"]
        )

        # Store output as dict
        state["fundamentalist_output"] = fundamentalist_output.model_dump()
        state["financial_health_score"] = fundamentalist_output.financial_health_score

        # Track tokens and time
        state["tokens_used"] = state.get("tokens_used", 0) + fundamentalist_output.tokens_used
        state["agent_processing_times"] = {
            **state.get("agent_processing_times", {}),
            "fundamentalist": fundamentalist_output.processing_time
        }

        logger.success(
            f"✓ Fundamentalist complete: {state['ticker']} "
            f"(Score: {fundamentalist_output.financial_health_score:.2f})"
        )

    except Exception as e:
        logger.error(f"Fundamentalist agent failed: {e}")
        state["status"] = "error"
        state["error"] = f"Fundamentalist agent failed: {str(e)}"

    return state


def call_news_hound_node(state: ManagerState) -> ManagerState:
    """
    Node 2: Call News Hound agent.

    Args:
        state: Current workflow state

    Returns:
        Updated state with news_hound_output and sentiment_score
    """
    logger.info(f"[Node 2] Calling News Hound agent for {state['ticker']}")

    state["status"] = "calling_news_hound"
    state["node_timestamps"] = {**state.get("node_timestamps", {}), "call_news_hound": time.time()}

    # Skip if fundamentalist failed
    if state.get("status") == "error":
        return state

    try:
        # Call News Hound agent
        news_hound_output = analyze_company_news(
            ticker=state["ticker"],
            days_back=state["news_days_back"]
        )

        # Store output as dict
        state["news_hound_output"] = news_hound_output.model_dump()
        state["sentiment_score"] = news_hound_output.sentiment_score

        # Track tokens and time
        state["tokens_used"] = state.get("tokens_used", 0) + news_hound_output.tokens_used
        state["agent_processing_times"] = {
            **state.get("agent_processing_times", {}),
            "news_hound": news_hound_output.processing_time
        }

        logger.success(
            f"✓ News Hound complete: {state['ticker']} "
            f"(Score: {news_hound_output.sentiment_score:.2f})"
        )

    except Exception as e:
        logger.error(f"News Hound agent failed: {e}")
        state["status"] = "error"
        state["error"] = f"News Hound agent failed: {str(e)}"

    return state


def call_quant_node(state: ManagerState) -> ManagerState:
    """
    Node 3: Call Quant agent (with supply chain data from Fundamentalist).

    Args:
        state: Current workflow state

    Returns:
        Updated state with quant_output, technical_score, and supply_chain_score
    """
    logger.info(f"[Node 3] Calling Quant agent for {state['ticker']}")

    state["status"] = "calling_quant"
    state["node_timestamps"] = {**state.get("node_timestamps", {}), "call_quant": time.time()}

    # Skip if previous agents failed
    if state.get("status") == "error":
        return state

    try:
        # Get supply chain data from Fundamentalist output
        fundamentalist_supply_chain = None
        if state.get("fundamentalist_output"):
            fund_output_dict = state["fundamentalist_output"]
            supply_chain_dict = fund_output_dict.get("supply_chain")

            if supply_chain_dict:
                # Reconstruct FundamentalistOutput to get SupplyChainOutput
                fund_output = FundamentalistOutput(**fund_output_dict)
                fundamentalist_supply_chain = fund_output.supply_chain

        # Call Quant agent
        quant_output = analyze_quant(
            ticker=state["ticker"],
            supply_chain_depth=2,
            fundamentalist_supply_chain=fundamentalist_supply_chain
        )

        # Store output as dict
        state["quant_output"] = quant_output.model_dump()
        state["technical_score"] = quant_output.technical_score
        state["supply_chain_score"] = quant_output.supply_chain_score

        # Track tokens and time
        state["tokens_used"] = state.get("tokens_used", 0) + quant_output.tokens_used
        state["agent_processing_times"] = {
            **state.get("agent_processing_times", {}),
            "quant": quant_output.processing_time
        }

        logger.success(
            f"✓ Quant complete: {state['ticker']} "
            f"(Tech: {quant_output.technical_score:.2f}, SC: {quant_output.supply_chain_score:.2f})"
        )

    except Exception as e:
        logger.error(f"Quant agent failed: {e}")
        state["status"] = "error"
        state["error"] = f"Quant agent failed: {str(e)}"

    return state


def synthesize_findings_node(state: ManagerState) -> ManagerState:
    """
    Node 4: Synthesize findings from all agents using LLM (Sonnet).

    Args:
        state: Current workflow state

    Returns:
        Updated state with synthesis_narrative, key_insights, and risk_factors
    """
    logger.info(f"[Node 4] Synthesizing findings for {state['ticker']}")

    state["status"] = "synthesizing"
    state["node_timestamps"] = {**state.get("node_timestamps", {}), "synthesize_findings": time.time()}

    # Skip if previous agents failed
    if state.get("status") == "error":
        return state

    try:
        # Synthesize findings
        synthesis, tokens = manager_analyzer.synthesize_findings(
            ticker=state["ticker"],
            analysis_date=state["analysis_date"],
            fiscal_year=state["fiscal_year"],
            fundamentalist_output=state["fundamentalist_output"],
            news_hound_output=state["news_hound_output"],
            quant_output=state["quant_output"],
        )

        # Update state
        state["synthesis_narrative"] = synthesis.get("synthesis_narrative", "")
        state["key_insights"] = synthesis.get("key_insights", [])
        state["risk_factors"] = synthesis.get("risk_factors", [])
        state["tokens_used"] = state.get("tokens_used", 0) + tokens

        logger.success(f"✓ Synthesis complete ({tokens} tokens)")

    except Exception as e:
        logger.error(f"Synthesis failed: {e}")
        state["status"] = "error"
        state["error"] = f"Synthesis failed: {str(e)}"

    return state


def calculate_moat_score_node(state: ManagerState) -> ManagerState:
    """
    Node 5: Calculate moat score using weighted formula.

    Args:
        state: Current workflow state

    Returns:
        Updated state with moat_score, moat_breakdown, confidence, and is_watchlist_candidate
    """
    logger.info(f"[Node 5] Calculating moat score for {state['ticker']}")

    state["status"] = "scoring"
    state["node_timestamps"] = {**state.get("node_timestamps", {}), "calculate_moat_score": time.time()}

    # Skip if previous step failed
    if state.get("status") == "error":
        return state

    try:
        # Get component scores
        financial_health_score = state["financial_health_score"]
        sentiment_score = state["sentiment_score"]
        technical_score = state["technical_score"]
        supply_chain_score = state["supply_chain_score"]

        # Get agent confidence levels
        fundamentalist_confidence = state["fundamentalist_output"].get("confidence", 1.0)
        news_hound_confidence = state["news_hound_output"].get("confidence", 1.0)
        quant_confidence = state["quant_output"].get("confidence", 1.0)

        # Calculate moat score
        moat_score, breakdown, confidence = manager_scorer.calculate_moat_score(
            financial_health_score=financial_health_score,
            sentiment_score=sentiment_score,
            technical_score=technical_score,
            supply_chain_score=supply_chain_score,
            fundamentalist_confidence=fundamentalist_confidence,
            news_hound_confidence=news_hound_confidence,
            quant_confidence=quant_confidence,
        )

        # Determine watchlist eligibility
        is_watchlist = manager_scorer.determine_watchlist(moat_score)

        # Update state
        state["moat_score"] = moat_score
        state["moat_breakdown"] = breakdown.model_dump()
        state["confidence"] = confidence
        state["is_watchlist_candidate"] = is_watchlist

        logger.success(
            f"✓ Moat score calculated: {state['ticker']} "
            f"(Score: {moat_score:.2f}, Watchlist: {is_watchlist}, Confidence: {confidence:.0%})"
        )

    except Exception as e:
        logger.error(f"Moat scoring failed: {e}")
        state["status"] = "error"
        state["error"] = f"Moat scoring failed: {str(e)}"

    return state


def generate_thesis_node(state: ManagerState) -> ManagerState:
    """
    Node 6: Generate investment thesis using LLM (Sonnet).

    Args:
        state: Current workflow state

    Returns:
        Updated state with investment_thesis
    """
    logger.info(f"[Node 6] Generating investment thesis for {state['ticker']}")

    state["status"] = "generating_thesis"
    state["node_timestamps"] = {**state.get("node_timestamps", {}), "generate_thesis": time.time()}

    # Skip if previous step failed
    if state.get("status") == "error":
        return state

    try:
        # Generate investment thesis
        thesis, tokens = manager_analyzer.generate_investment_thesis(
            ticker=state["ticker"],
            analysis_date=state["analysis_date"],
            moat_score=state["moat_score"],
            confidence=state["confidence"],
            financial_health_score=state["financial_health_score"],
            sentiment_score=state["sentiment_score"],
            technical_score=state["technical_score"],
            supply_chain_score=state["supply_chain_score"],
            is_watchlist=state["is_watchlist_candidate"],
            synthesis_narrative=state["synthesis_narrative"],
            key_insights=state["key_insights"],
            risk_factors=state["risk_factors"],
        )

        # Update state
        state["investment_thesis"] = thesis.get("investment_thesis", "")
        state["tokens_used"] = state.get("tokens_used", 0) + tokens
        state["status"] = "completed"

        logger.success(f"✓ Investment thesis generated ({tokens} tokens)")

    except Exception as e:
        logger.error(f"Thesis generation failed: {e}")
        state["status"] = "error"
        state["error"] = f"Thesis generation failed: {str(e)}"

    return state


# ============================================================================
# Build Workflow Graph
# ============================================================================

def build_manager_graph() -> StateGraph:
    """
    Build the LangGraph workflow for Manager agent.

    6-Node Sequential Workflow:
    1. call_fundamentalist → 2. call_news_hound → 3. call_quant
                                                      ↓
    6. generate_thesis ← 5. calculate_moat ← 4. synthesize_findings

    Returns:
        Compiled StateGraph
    """
    workflow = StateGraph(ManagerState)

    # Add nodes
    workflow.add_node("call_fundamentalist", call_fundamentalist_node)
    workflow.add_node("call_news_hound", call_news_hound_node)
    workflow.add_node("call_quant", call_quant_node)
    workflow.add_node("synthesize_findings", synthesize_findings_node)
    workflow.add_node("calculate_moat_score", calculate_moat_score_node)
    workflow.add_node("generate_thesis", generate_thesis_node)

    # Set entry point
    workflow.set_entry_point("call_fundamentalist")

    # Add edges - sequential flow
    workflow.add_edge("call_fundamentalist", "call_news_hound")
    workflow.add_edge("call_news_hound", "call_quant")
    workflow.add_edge("call_quant", "synthesize_findings")
    workflow.add_edge("synthesize_findings", "calculate_moat_score")
    workflow.add_edge("calculate_moat_score", "generate_thesis")

    # Generate thesis is the final node
    workflow.set_finish_point("generate_thesis")

    return workflow.compile()


# ============================================================================
# Main Analysis Function
# ============================================================================

def analyze_swarm(
    ticker: str,
    fiscal_year: int = 2024,
    news_days_back: int = 30,
) -> ManagerOutput:
    """
    Perform full swarm analysis on a company.

    This orchestrates all three research agents (Fundamentalist, News Hound, Quant)
    and synthesizes their findings into a unified investment analysis with moat scoring.

    Args:
        ticker: Stock ticker (e.g., "NVDA")
        fiscal_year: Fiscal year for fundamentalist analysis (default 2024)
        news_days_back: Days to look back for news analysis (default 30)

    Returns:
        ManagerOutput with complete swarm analysis and moat score

    Raises:
        ValueError: If analysis fails
    """
    logger.info(f"=== SWARM ANALYSIS START: {ticker} ===")

    start_time = time.time()
    analysis_date = datetime.now().strftime("%Y-%m-%d")

    # Initialize state
    initial_state: ManagerState = {
        "ticker": ticker,
        "fiscal_year": fiscal_year,
        "news_days_back": news_days_back,
        "analysis_date": analysis_date,
        "status": "initialized",
        "error": None,
        "fundamentalist_output": None,
        "news_hound_output": None,
        "quant_output": None,
        "financial_health_score": None,
        "sentiment_score": None,
        "technical_score": None,
        "supply_chain_score": None,
        "synthesis_narrative": None,
        "key_insights": None,
        "risk_factors": None,
        "moat_score": None,
        "moat_breakdown": None,
        "confidence": None,
        "is_watchlist_candidate": None,
        "investment_thesis": None,
        "tokens_used": 0,
        "processing_time": None,
        "node_timestamps": {},
        "agent_processing_times": {},
    }

    # Build and run workflow
    graph = build_manager_graph()
    final_state = graph.invoke(initial_state)

    # Check for errors
    if final_state.get("status") == "error":
        error_msg = final_state.get("error", "Unknown error")
        logger.error(f"Swarm analysis failed: {error_msg}")
        raise ValueError(error_msg)

    # Calculate processing time
    processing_time = time.time() - start_time
    final_state["processing_time"] = processing_time

    # Build output
    output = ManagerOutput(
        ticker=final_state["ticker"],
        analysis_date=final_state["analysis_date"],
        fiscal_year=final_state["fiscal_year"],
        news_days_back=final_state["news_days_back"],
        fundamentalist_output=final_state["fundamentalist_output"],
        news_hound_output=final_state["news_hound_output"],
        quant_output=final_state["quant_output"],
        synthesis_narrative=final_state["synthesis_narrative"],
        key_insights=final_state["key_insights"],
        risk_factors=final_state["risk_factors"],
        investment_thesis=final_state["investment_thesis"],
        moat_score=final_state["moat_score"],
        moat_breakdown=MoatScoreBreakdown(**final_state["moat_breakdown"]),
        confidence=final_state["confidence"],
        is_watchlist_candidate=final_state["is_watchlist_candidate"],
        tokens_used=final_state.get("tokens_used", 0),
        processing_time=processing_time,
        agent_processing_times=final_state.get("agent_processing_times"),
    )

    logger.success(
        f"=== SWARM ANALYSIS COMPLETE: {ticker} "
        f"(Moat: {output.moat_score:.2f}, Watchlist: {output.is_watchlist_candidate}, "
        f"Time: {processing_time:.1f}s, Tokens: {output.tokens_used}) ==="
    )

    return output
