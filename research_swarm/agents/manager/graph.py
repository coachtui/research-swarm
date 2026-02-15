"""
LangGraph workflow for the Manager agent.

Orchestrates all three research agents and synthesizes findings into
a unified investment analysis with moat scoring.
"""
import time
from datetime import datetime
from typing import Optional, List
from langgraph.graph import StateGraph
from loguru import logger

from research_swarm.agents.fundamentalist import analyze_company, FundamentalistOutput
from research_swarm.agents.news_hound import analyze_company_news, NewsHoundOutput
from research_swarm.agents.quant import analyze_quant, QuantOutput
from research_swarm.orchestration.cost_tracker import CostTracker

from .state import ManagerState
from .analyzer import ManagerAnalyzer
from .scorer import ManagerScorer
from .models import ManagerOutput, MoatScoreBreakdown
from .signal_divergence import calculate_signal_divergence


# Initialize singletons
manager_analyzer = ManagerAnalyzer()
manager_scorer = ManagerScorer()


# ============================================================================
# Node Functions
# ============================================================================

def fetch_swarm_data_node(state: ManagerState) -> ManagerState:
    """
    Node 0: Pre-fetch ALL data for all agents (NEW).

    Eliminates redundant API calls by fetching all data once before agent execution.
    This single fetch replaces ~15+ individual API calls across agents.

    Args:
        state: Current workflow state

    Returns:
        Updated state with shared_swarm_data containing complete data bundle
    """
    from research_swarm.data.data_provider_hybrid import hybrid_provider

    logger.info(f"[Node 0] Pre-fetching swarm data for {state['ticker']}")

    state["status"] = "fetching_data"
    state["node_timestamps"] = {**state.get("node_timestamps", {}), "fetch_swarm_data": time.time()}

    try:
        # Fetch complete data bundle for all agents
        period = "1y"  # Historical data period for Quant agent
        shared_data = hybrid_provider.get_complete_swarm_data(state["ticker"], period=period)

        # Store in state for agents to consume
        state["shared_swarm_data"] = shared_data

        logger.success(
            f"✓ Swarm data fetched: {state['ticker']} "
            f"(Foreign: {shared_data.get('is_foreign', False)})"
        )

    except Exception as e:
        logger.error(f"Failed to fetch swarm data for {state['ticker']}: {e}")
        state["status"] = "error"
        state["error"] = f"Data fetch failed: {str(e)}"

    return state


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
        # Call Fundamentalist agent with TTM parameters
        fundamentalist_output = analyze_company(
            ticker=state["ticker"],
            quarters=state.get("quarters"),
            fiscal_year=state.get("fiscal_year"),  # Backward compatibility
            shared_swarm_data=state.get("shared_swarm_data")  # NEW: Pass pre-fetched data
        )

        # Store output as dict
        state["fundamentalist_output"] = fundamentalist_output.dict()
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

    # Skip if fundamentalist failed (check BEFORE updating status)
    if state.get("status") == "error":
        return state

    state["status"] = "calling_news_hound"
    state["node_timestamps"] = {**state.get("node_timestamps", {}), "call_news_hound": time.time()}

    try:
        # Call News Hound agent
        news_hound_output = analyze_company_news(
            ticker=state["ticker"],
            days_back=state["news_days_back"],
            shared_swarm_data=state.get("shared_swarm_data")  # NEW: Pass pre-fetched data
        )

        # Store output as dict
        state["news_hound_output"] = news_hound_output.dict()
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

    # Skip if previous agents failed (check BEFORE updating status)
    if state.get("status") == "error":
        return state

    state["status"] = "calling_quant"
    state["node_timestamps"] = {**state.get("node_timestamps", {}), "call_quant": time.time()}

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

        # Call Quant agent (supply chain disabled per user request)
        quant_output = analyze_quant(
            ticker=state["ticker"],
            supply_chain_depth=0,  # Disable supply chain analysis
            fundamentalist_supply_chain=None,  # Don't pass supply chain data
            shared_swarm_data=state.get("shared_swarm_data")  # NEW: Pass pre-fetched data
        )

        # Store output as dict
        state["quant_output"] = quant_output.dict()
        state["technical_score"] = quant_output.technical_score
        # Supply chain disabled per user request
        state["supply_chain_score"] = 0.0  # Always 0 since supply chain is disabled

        # Track tokens and time
        state["tokens_used"] = state.get("tokens_used", 0) + quant_output.tokens_used
        state["agent_processing_times"] = {
            **state.get("agent_processing_times", {}),
            "quant": quant_output.processing_time
        }

        logger.success(
            f"✓ Quant complete: {state['ticker']} "
            f"(Technical Score: {quant_output.technical_score:.2f})"
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

    # Skip if previous agents failed (check BEFORE updating status)
    if state.get("status") == "error":
        return state

    # Check that all agent outputs exist
    if not state.get("fundamentalist_output") or not state.get("news_hound_output") or not state.get("quant_output"):
        state["status"] = "error"
        state["error"] = "Missing agent outputs - one or more agents failed"
        logger.error(state["error"])
        return state

    state["status"] = "synthesizing"
    state["node_timestamps"] = {**state.get("node_timestamps", {}), "synthesize_findings": time.time()}

    try:
        # NEW: Extract and deduplicate insights from all agents
        fund_output = state["fundamentalist_output"]
        news_output = state["news_hound_output"]
        quant_output = state["quant_output"]

        # Collect insights from all agents
        all_insights = []
        all_risks = []

        # Fundamentalist insights (if present)
        if fund_output.get("key_insights"):
            all_insights.extend(fund_output["key_insights"])
        if fund_output.get("risk_factors"):
            all_risks.extend(fund_output["risk_factors"])

        # News Hound insights (if present)
        if news_output.get("key_insights"):
            all_insights.extend(news_output["key_insights"])
        if news_output.get("risk_factors"):
            all_risks.extend(news_output["risk_factors"])

        # Quant insights (if present)
        if quant_output.get("key_insights"):
            all_insights.extend(quant_output["key_insights"])
        if quant_output.get("risk_factors"):
            all_risks.extend(quant_output["risk_factors"])

        # Deduplicate insights and risks
        deduplicated_insights = manager_analyzer.deduplicate_insights(all_insights, max_results=5)
        deduplicated_risks = manager_analyzer.deduplicate_insights(all_risks, max_results=5)

        logger.info(f"Deduplicated: {len(all_insights)} insights → {len(deduplicated_insights)}, {len(all_risks)} risks → {len(deduplicated_risks)}")

        # Synthesize findings
        synthesis, tokens = manager_analyzer.synthesize_findings(
            ticker=state["ticker"],
            analysis_date=state["analysis_date"],
            analysis_period=state["analysis_period"],
            fundamentalist_output=state["fundamentalist_output"],
            news_hound_output=state["news_hound_output"],
            quant_output=state["quant_output"],
        )

        # Update state with deduplicated insights (override LLM-generated if present)
        state["synthesis_narrative"] = synthesis.get("synthesis_narrative", "")
        state["key_insights"] = deduplicated_insights if deduplicated_insights else synthesis.get("key_insights", [])
        state["risk_factors"] = deduplicated_risks if deduplicated_risks else synthesis.get("risk_factors", [])

        # NEW v2.0: Extract structured risks and triggers
        state["structured_risks"] = synthesis.get("structured_risks", [])
        state["upgrade_triggers"] = synthesis.get("upgrade_triggers", [])
        state["downgrade_triggers"] = synthesis.get("downgrade_triggers", [])

        # NEW: Extract LLM-generated price targets
        price_targets = synthesis.get("price_targets")
        if price_targets and price_targets.get("base_target"):
            state["price_targets"] = price_targets
            logger.info(f"✓ Price targets: Bull ${price_targets.get('bull_target', 0):.2f} / Base ${price_targets.get('base_target', 0):.2f} / Bear ${price_targets.get('bear_target', 0):.2f}")
        else:
            state["price_targets"] = None

        state["tokens_used"] = state.get("tokens_used", 0) + tokens

        # NEW v2.0: Calculate signal divergence analysis
        signal_breakdown = calculate_signal_divergence(
            fundamentalist_output=state["fundamentalist_output"],
            news_hound_output=state["news_hound_output"],
            quant_output=state["quant_output"]
        )
        if signal_breakdown:
            state["signal_breakdown"] = signal_breakdown
            logger.info(f"✓ Signal divergence: {signal_breakdown['alignment_status']}")

        logger.success(f"✓ Synthesis complete ({tokens} tokens, {len(state.get('structured_risks', []))} structured risks)")

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

    # Skip if previous step failed (check BEFORE updating status)
    if state.get("status") == "error":
        return state

    # Verify required outputs exist
    if not state.get("fundamentalist_output") or not state.get("news_hound_output") or not state.get("quant_output"):
        state["status"] = "error"
        state["error"] = "Missing agent outputs for moat scoring"
        logger.error(state["error"])
        return state

    state["status"] = "scoring"
    state["node_timestamps"] = {**state.get("node_timestamps", {}), "calculate_moat_score": time.time()}

    try:
        # Get component scores
        financial_health_score = state["financial_health_score"]
        sentiment_score = state["sentiment_score"]
        technical_score = state["technical_score"]

        # Get agent confidence levels
        fundamentalist_confidence = state["fundamentalist_output"].get("confidence", 1.0)
        news_hound_confidence = state["news_hound_output"].get("confidence", 1.0)
        quant_confidence = state["quant_output"].get("confidence", 1.0)

        # Get v2.0 scores (earnings momentum, valuation)
        fundamentalist_output = state["fundamentalist_output"]
        earnings_momentum_score = fundamentalist_output.get("earnings_momentum_score")
        valuation_score = fundamentalist_output.get("valuation_score")

        if earnings_momentum_score is None or valuation_score is None:
            raise ValueError(
                f"Missing required v2.0 components for {state['ticker']}: "
                f"earnings_momentum={earnings_momentum_score}, valuation={valuation_score}"
            )

        # Create moat breakdown using v2.0 formula
        logger.info(f"Using v2.0 moat formula (Earnings Momentum + Valuation)")
        breakdown = MoatScoreBreakdown(
            earnings_momentum=earnings_momentum_score,
            financial_health=financial_health_score,
            valuation=valuation_score,
            technical_strength=technical_score,
            sentiment_catalysts=sentiment_score,
        )

        # Calculate moat score
        moat_score = breakdown.weighted_average()

        # Calculate confidence using all v2.0 components
        component_scores = [
            earnings_momentum_score,
            financial_health_score,
            valuation_score,
            technical_score,
            sentiment_score
        ]

        confidence = manager_scorer.assess_confidence(
            component_scores=component_scores,
            agent_confidences={
                "fundamentalist": fundamentalist_confidence,
                "news_hound": news_hound_confidence,
                "quant": quant_confidence,
            },
        )

        # Determine watchlist eligibility
        is_watchlist = manager_scorer.determine_watchlist(moat_score)

        # NEW v2.0: Determine 5-tier rating
        rating, rating_score = manager_scorer.determine_rating(moat_score)

        # NEW v2.0: Determine risk level
        import statistics
        variance = statistics.variance(component_scores) if len(component_scores) > 1 else 0.0
        component_scores_dict = {
            "financial_health": financial_health_score,
            "sentiment": sentiment_score,
            "technical": technical_score,
        }
        if earnings_momentum_score is not None:
            component_scores_dict["earnings_momentum"] = earnings_momentum_score
        if valuation_score is not None:
            component_scores_dict["valuation"] = valuation_score

        risk_level = manager_scorer.determine_risk_level(component_scores_dict, variance)

        # Update state
        state["moat_score"] = moat_score
        state["moat_breakdown"] = breakdown.dict()
        state["confidence"] = confidence
        state["is_watchlist_candidate"] = is_watchlist
        state["rating"] = rating
        state["rating_score"] = rating_score
        state["risk_level"] = risk_level

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

    # Skip if previous step failed (check BEFORE updating status)
    if state.get("status") == "error":
        return state

    # Verify required data exists
    if state.get("key_insights") is None or state.get("risk_factors") is None:
        state["status"] = "error"
        state["error"] = "Missing synthesis data for thesis generation"
        logger.error(state["error"])
        return state

    state["status"] = "generating_thesis"
    state["node_timestamps"] = {**state.get("node_timestamps", {}), "generate_thesis": time.time()}

    try:
        # Get v2.0 component scores from fundamentalist
        fundamentalist_output = state.get("fundamentalist_output", {})
        earnings_momentum_score = fundamentalist_output.get("earnings_momentum_score", 5.0)
        valuation_score = fundamentalist_output.get("valuation_score", 5.0)

        # Generate investment thesis
        thesis, tokens = manager_analyzer.generate_investment_thesis(
            ticker=state["ticker"],
            analysis_date=state["analysis_date"],
            moat_score=state["moat_score"],
            confidence=state["confidence"],
            earnings_momentum_score=earnings_momentum_score,
            financial_health_score=state["financial_health_score"],
            valuation_score=valuation_score,
            sentiment_score=state["sentiment_score"],
            technical_score=state["technical_score"],
            is_watchlist=state["is_watchlist_candidate"],
            synthesis_narrative=state["synthesis_narrative"] or "",
            key_insights=state["key_insights"] or [],
            risk_factors=state["risk_factors"] or [],
            # Enhanced context
            fundamentalist_output=state.get("fundamentalist_output"),
            news_hound_output=state.get("news_hound_output"),
            quant_output=state.get("quant_output"),
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

    7-Node Sequential Workflow (NEW: Data pre-fetching):
    0. fetch_swarm_data → 1. call_fundamentalist → 2. call_news_hound → 3. call_quant
                                                                          ↓
    7. generate_thesis ← 6. calculate_moat ← 5. synthesize_findings ← 4. (from quant)

    Node 0 (NEW) fetches ALL data once, eliminating redundant API calls across agents.

    Returns:
        Compiled StateGraph
    """
    workflow = StateGraph(ManagerState)

    # Add nodes
    workflow.add_node("fetch_swarm_data", fetch_swarm_data_node)  # NEW: Pre-fetch data
    workflow.add_node("call_fundamentalist", call_fundamentalist_node)
    workflow.add_node("call_news_hound", call_news_hound_node)
    workflow.add_node("call_quant", call_quant_node)
    workflow.add_node("synthesize_findings", synthesize_findings_node)
    workflow.add_node("calculate_moat_score", calculate_moat_score_node)
    workflow.add_node("generate_thesis", generate_thesis_node)

    # Set entry point (NEW: Start with data fetch)
    workflow.set_entry_point("fetch_swarm_data")

    # Add edges - sequential flow
    workflow.add_edge("fetch_swarm_data", "call_fundamentalist")  # NEW edge
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
    quarters: List[str] = None,
    fiscal_year: int = None,  # Deprecated - for backward compatibility
    news_days_back: int = 30,
) -> ManagerOutput:
    """
    Perform full swarm analysis on a company.

    This orchestrates all three research agents (Fundamentalist, News Hound, Quant)
    and synthesizes their findings into a unified investment analysis with moat scoring.

    Args:
        ticker: Stock ticker (e.g., "NVDA")
        quarters: Quarters for TTM analysis (e.g., ["Q4_2024", "Q1_2025", "Q2_2025", "Q3_2025"])
        fiscal_year: [Deprecated] Fiscal year for annual analysis (default None)
        news_days_back: Days to look back for news analysis (default 30)

    Returns:
        ManagerOutput with complete swarm analysis and moat score

    Raises:
        ValueError: If analysis fails
    """
    logger.info(f"=== SWARM ANALYSIS START: {ticker} ===")

    start_time = time.time()
    analysis_date = datetime.now().strftime("%Y-%m-%d")

    # Determine analysis period
    if quarters:
        analysis_period = f"TTM {quarters[0].replace('_', ' ')} - {quarters[-1].replace('_', ' ')}"
    elif fiscal_year:
        analysis_period = f"FY {fiscal_year}"
        logger.warning("Using deprecated fiscal_year parameter. Consider using quarters for TTM analysis.")
    else:
        # Default to current year if neither is provided
        current_year = datetime.now().year
        analysis_period = f"FY {current_year}"
        logger.warning(f"No quarters or fiscal_year provided, defaulting to FY {current_year}")

    # Initialize state
    initial_state: ManagerState = {
        "ticker": ticker,
        "quarters": quarters or [],
        "analysis_period": analysis_period,
        "fiscal_year": fiscal_year,  # Keep for backward compatibility
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

    # Calculate costs per agent
    cost_tracker = CostTracker()
    cost_by_agent = {
        "fundamentalist": 0.0,
        "news_hound": 0.0,
        "quant": 0.0,
        "manager": 0.0,
    }

    # Fundamentalist cost (using haiku for scorer + sonnet for analyzer, approximate 50/50 split)
    if final_state.get("fundamentalist_output"):
        fund_tokens = final_state["fundamentalist_output"].get("tokens_used", 0)
        tokens_in = int(fund_tokens * 0.3)
        tokens_out = int(fund_tokens * 0.7)
        # Mix of haiku (scorer) and sonnet (analyzer), use average
        cost_by_agent["fundamentalist"] = (
            cost_tracker.calculate_cost(tokens_in // 2, tokens_out // 2, "haiku") +
            cost_tracker.calculate_cost(tokens_in // 2, tokens_out // 2, "sonnet")
        )

    # News Hound cost (using haiku for scorer + sonnet for analyzer, approximate 50/50 split)
    if final_state.get("news_hound_output"):
        news_tokens = final_state["news_hound_output"].get("tokens_used", 0)
        tokens_in = int(news_tokens * 0.3)
        tokens_out = int(news_tokens * 0.7)
        # Mix of haiku (scorer) and sonnet (analyzer), use average
        cost_by_agent["news_hound"] = (
            cost_tracker.calculate_cost(tokens_in // 2, tokens_out // 2, "haiku") +
            cost_tracker.calculate_cost(tokens_in // 2, tokens_out // 2, "sonnet")
        )

    # Quant cost (using haiku for scorer + sonnet for analyzer, approximate 50/50 split)
    if final_state.get("quant_output"):
        quant_tokens = final_state["quant_output"].get("tokens_used", 0)
        tokens_in = int(quant_tokens * 0.3)
        tokens_out = int(quant_tokens * 0.7)
        # Mix of haiku (scorer) and sonnet (analyzer), use average
        cost_by_agent["quant"] = (
            cost_tracker.calculate_cost(tokens_in // 2, tokens_out // 2, "haiku") +
            cost_tracker.calculate_cost(tokens_in // 2, tokens_out // 2, "sonnet")
        )

    # Manager cost (sonnet for synthesis + thesis generation)
    manager_tokens = final_state.get("tokens_used", 0)
    agent_tokens = sum(
        final_state.get(f"{agent}_output", {}).get("tokens_used", 0)
        for agent in ["fundamentalist", "news_hound", "quant"]
    )
    manager_only_tokens = manager_tokens - agent_tokens
    if manager_only_tokens > 0:
        tokens_in = int(manager_only_tokens * 0.3)
        tokens_out = int(manager_only_tokens * 0.7)
        cost_by_agent["manager"] = cost_tracker.calculate_cost(tokens_in, tokens_out, "sonnet")

    # Inject LLM-generated price_targets into fundamentalist_output
    # so data_extractor picks it up from fundamentalist.get("price_targets")
    if final_state.get("price_targets") and final_state.get("fundamentalist_output"):
        final_state["fundamentalist_output"]["price_targets"] = final_state["price_targets"]

    # Extract VGM scores from fundamentalist_output
    vgm_scores = None
    if final_state.get("fundamentalist_output"):
        vgm_scores = final_state["fundamentalist_output"].get("vgm_scores")

    # Build output
    output = ManagerOutput(
        ticker=final_state["ticker"],
        analysis_date=final_state["analysis_date"],
        analysis_period=final_state["analysis_period"],
        quarters=final_state.get("quarters", []),
        fiscal_year=final_state.get("fiscal_year"),  # Backward compatibility
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
        signal_breakdown=final_state.get("signal_breakdown"),  # v2.0
        vgm_scores=vgm_scores,  # Extract from fundamentalist output
        tokens_used=final_state.get("tokens_used", 0),
        processing_time=processing_time,
        agent_processing_times=final_state.get("agent_processing_times"),
        cost_by_agent=cost_by_agent,
    )

    logger.success(
        f"=== SWARM ANALYSIS COMPLETE: {ticker} "
        f"(Moat: {output.moat_score:.2f}, Watchlist: {output.is_watchlist_candidate}, "
        f"Time: {processing_time:.1f}s, Tokens: {output.tokens_used}) ==="
    )

    return output
