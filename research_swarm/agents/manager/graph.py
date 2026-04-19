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
from research_swarm.data.market_data_client import market_data_client

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
    """Node 0: Pre-fetch ALL data for all agents."""
    is_etf = state.get("is_etf", False)
    logger.info(f"[Node 0] Pre-fetching swarm data for {state['ticker']} (is_etf={is_etf})")

    state["status"] = "fetching_data"
    state["node_timestamps"] = {**state.get("node_timestamps", {}), "fetch_swarm_data": time.time()}

    try:
        if is_etf:
            # ETF path: fetch holdings, AUM, expense ratio, sector weights
            etf_data = market_data_client.get_etf_info(state["ticker"])
            if not etf_data:
                raise ValueError(f"Could not fetch ETF info for {state['ticker']}")

            state["shared_swarm_data"] = {
                "is_etf": True,
                "etf_data": etf_data,
            }
            logger.success(f"✓ ETF data fetched: {state['ticker']} AUM=${etf_data.get('aum_billions')}B")
        else:
            # Equity path: existing hybrid provider fetch
            from research_swarm.data.data_provider_hybrid import hybrid_provider
            period = "1y"
            shared_data = hybrid_provider.get_complete_swarm_data(state["ticker"], period=period)
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


def call_fundamentalist_node(state: ManagerState) -> dict:
    """
    Node 1: Call Fundamentalist agent.

    Args:
        state: Current workflow state

    Returns:
        Partial state update (only modified fields to avoid parallel update conflicts)
    """
    logger.info(f"[Node 1] Calling Fundamentalist agent for {state['ticker']}")

    try:
        # Call Fundamentalist agent with TTM parameters
        fundamentalist_output = analyze_company(
            ticker=state["ticker"],
            quarters=state.get("quarters"),
            fiscal_year=state.get("fiscal_year"),  # Backward compatibility
            shared_swarm_data=state.get("shared_swarm_data"),  # NEW: Pass pre-fetched data
            etf_context=state.get("shared_swarm_data", {}).get("etf_data") if state.get("is_etf") else None,
        )

        logger.success(
            f"✓ Fundamentalist complete: {state['ticker']} "
            f"(Score: {fundamentalist_output.financial_health_score:.2f})"
        )

        # Return only the fields this node modifies (avoid parallel update conflicts)
        # Note: tokens_used, node_timestamps, agent_processing_times handled in sync node
        return {
            "fundamentalist_output": fundamentalist_output.dict(),
            "financial_health_score": fundamentalist_output.financial_health_score,
        }

    except Exception as e:
        logger.error(f"Fundamentalist agent failed: {e}")
        return {
            "fundamentalist_error": f"Fundamentalist agent failed: {str(e)}",
        }


def call_news_hound_node(state: ManagerState) -> dict:
    """
    Node 2: Call News Hound agent (PARALLEL).

    Args:
        state: Current workflow state

    Returns:
        Partial state update (only modified fields to avoid parallel update conflicts)
    """
    logger.info(f"[Node 2] Calling News Hound agent for {state['ticker']}")

    try:
        # Call News Hound agent
        news_hound_output = analyze_company_news(
            ticker=state["ticker"],
            days_back=state["news_days_back"],
            shared_swarm_data=state.get("shared_swarm_data"),  # Pass pre-fetched data
            etf_context=state.get("shared_swarm_data", {}).get("etf_data") if state.get("is_etf") else None,  # Pass ETF sector context if available
        )

        logger.success(
            f"✓ News Hound complete: {state['ticker']} "
            f"(Score: {news_hound_output.sentiment_score:.2f})"
        )

        # Return only the fields this node modifies (avoid parallel update conflicts)
        # Note: tokens_used, node_timestamps, agent_processing_times handled in sync node
        return {
            "news_hound_output": news_hound_output.dict(),
            "sentiment_score": news_hound_output.sentiment_score,
        }

    except Exception as e:
        logger.error(f"News Hound agent failed: {e}")
        return {
            "news_hound_error": f"News Hound agent failed: {str(e)}",
        }


def call_quant_node(state: ManagerState) -> dict:
    """
    Node 3: Call Quant agent (PARALLEL).

    Note: Supply chain analysis is disabled. If re-enabled, would need
    to run after Fundamentalist instead of in parallel.

    Args:
        state: Current workflow state

    Returns:
        Partial state update (only modified fields to avoid parallel update conflicts)
    """
    logger.info(f"[Node 3] Calling Quant agent for {state['ticker']}")

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
            shared_swarm_data=state.get("shared_swarm_data"),  # NEW: Pass pre-fetched data
            etf_context=state.get("shared_swarm_data", {}).get("etf_data") if state.get("is_etf") else None,
        )

        logger.success(
            f"✓ Quant complete: {state['ticker']} "
            f"(Technical Score: {quant_output.technical_score:.2f})"
        )

        # Return only the fields this node modifies (avoid parallel update conflicts)
        # Note: tokens_used, node_timestamps, agent_processing_times handled in sync node
        return {
            "quant_output": quant_output.dict(),
            "technical_score": quant_output.technical_score,
            "supply_chain_score": 0.0,  # Always 0 since supply chain is disabled
        }

    except Exception as e:
        logger.error(f"Quant agent failed: {e}")
        return {
            "quant_error": f"Quant agent failed: {str(e)}",
        }


def check_agents_complete_node(state: ManagerState) -> ManagerState:
    """
    Node 4: Check that all three agents completed successfully.

    This synchronization node waits for all parallel agents to complete
    and verifies no errors occurred before proceeding to synthesis.

    Args:
        state: Current workflow state

    Returns:
        Updated state with error status if any agent failed
    """
    logger.info(f"[Node 4] Checking agent completion for {state['ticker']}")

    state["node_timestamps"] = {**state.get("node_timestamps", {}), "check_agents_complete": time.time()}

    # Check that all agent outputs exist
    missing_agents = []
    if not state.get("fundamentalist_output"):
        missing_agents.append("Fundamentalist")
    if not state.get("news_hound_output"):
        missing_agents.append("News Hound")
    if not state.get("quant_output"):
        missing_agents.append("Quant")

    if missing_agents:
        state["status"] = "error"
        # Collect root causes from per-agent error fields (set by parallel nodes)
        root_causes = [
            state[k] for k in ("fundamentalist_error", "news_hound_error", "quant_error")
            if state.get(k)
        ]
        state["error"] = f"Missing agent outputs: {', '.join(missing_agents)}"
        if root_causes:
            state["error"] += f" | Root cause: {'; '.join(root_causes)}"
        logger.error(state["error"])
        return state

    # Check if any agent reported an error
    errors = []
    if state.get("fundamentalist_output", {}).get("error"):
        errors.append(f"Fundamentalist: {state['fundamentalist_output']['error']}")
    if state.get("news_hound_output", {}).get("error"):
        errors.append(f"News Hound: {state['news_hound_output']['error']}")
    if state.get("quant_output", {}).get("error"):
        errors.append(f"Quant: {state['quant_output']['error']}")

    if errors:
        state["status"] = "error"
        state["error"] = "Agent errors: " + "; ".join(errors)
        logger.error(state["error"])
        return state

    # All agents completed successfully
    state["status"] = "agents_complete"

    # Aggregate tokens from all agents
    total_tokens = state.get("tokens_used", 0)
    if state.get("fundamentalist_output"):
        total_tokens += state["fundamentalist_output"].get("tokens_used", 0)
    if state.get("news_hound_output"):
        total_tokens += state["news_hound_output"].get("tokens_used", 0)
    if state.get("quant_output"):
        total_tokens += state["quant_output"].get("tokens_used", 0)

    state["tokens_used"] = total_tokens

    # Aggregate agent processing times
    agent_times = state.get("agent_processing_times", {})
    if state.get("fundamentalist_output"):
        agent_times["fundamentalist"] = state["fundamentalist_output"].get("processing_time", 0)
    if state.get("news_hound_output"):
        agent_times["news_hound"] = state["news_hound_output"].get("processing_time", 0)
    if state.get("quant_output"):
        agent_times["quant"] = state["quant_output"].get("processing_time", 0)

    state["agent_processing_times"] = agent_times

    # Consensus target fallback: if fundamentalist calibration has no consensus_target
    # (yfinance returned no targetMeanPrice), try the news_hound's LLM-extracted avg_price_target.
    # Both agents are fully complete at this fan-in point, so all data is available.
    try:
        fv_calib = (state.get("fundamentalist_output") or {}).get("fair_value_calibration")
        if isinstance(fv_calib, dict) and fv_calib.get("consensus_target") is None:
            nh_consensus = (state.get("news_hound_output") or {}).get("analyst_consensus")
            fallback_target = (nh_consensus or {}).get("avg_price_target") if isinstance(nh_consensus, dict) else None
            if fallback_target and float(fallback_target) > 0:
                internal_fv = fv_calib.get("internal_fair_value", 0)
                consensus_target = round(float(fallback_target), 2)
                divergence_ratio = round(internal_fv / consensus_target, 4) if consensus_target else None
                divergence_pct = round((internal_fv - consensus_target) / consensus_target * 100.0, 1) if consensus_target else None
                # Classify using same ±20% threshold as FairValueCalibrator.ALIGNED_THRESHOLD
                if divergence_ratio is not None:
                    if divergence_ratio < 0.80:
                        divergence_state = "Model-Conservative Regime"
                    elif divergence_ratio > 1.20:
                        divergence_state = "Model-Driven Upside Scenario"
                    else:
                        divergence_state = "Consensus Validated ✓"
                else:
                    divergence_state = "No Consensus Data"
                # Derive analyst count from rating distribution (AnalystConsensus has no num_analysts field)
                num_analysts = None
                if isinstance(nh_consensus, dict):
                    rating_total = sum(
                        nh_consensus.get(k, 0) or 0
                        for k in ("strong_buy", "buy", "hold", "sell", "strong_sell")
                    )
                    if rating_total > 0:
                        num_analysts = rating_total
                # Patch the calibration dict in-place
                state["fundamentalist_output"]["fair_value_calibration"].update({
                    "consensus_target": consensus_target,
                    "num_analysts": num_analysts,
                    "divergence_ratio": divergence_ratio,
                    "divergence_pct": divergence_pct,
                    "divergence_state": divergence_state,
                })
                logger.info(
                    f"[fan-in] Patched consensus_target from news_hound: "
                    f"${consensus_target} → divergence_state={divergence_state}"
                )
    except Exception as _patch_err:
        logger.warning(f"[fan-in] Consensus fallback patch failed (non-fatal): {_patch_err}")

    logger.success(f"✓ All agents complete for {state['ticker']} (Total tokens: {total_tokens})")

    return state


def synthesize_findings_node(state: ManagerState) -> ManagerState:
    """
    Node 5: Synthesize findings from all agents using LLM (Sonnet).

    Args:
        state: Current workflow state

    Returns:
        Updated state with synthesis_narrative, key_insights, and risk_factors
    """
    logger.info(f"[Node 5] Synthesizing findings for {state['ticker']}")

    # Skip if previous check failed
    if state.get("status") == "error":
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
            quant_output=state["quant_output"],
            is_adr=state.get("shared_swarm_data", {}).get("is_foreign", False),
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
    Node 6: Calculate moat score using weighted formula.

    Args:
        state: Current workflow state

    Returns:
        Updated state with moat_score, moat_breakdown, confidence, and is_watchlist_candidate
    """
    logger.info(f"[Node 6] Calculating moat score for {state['ticker']}")

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

        # P0: Apply data integrity confidence penalty from signal_breakdown
        # Missing data signals silently inflated confidence — now we penalize explicitly
        signal_breakdown = state.get("signal_breakdown", {})
        data_integrity_factor = signal_breakdown.get("data_integrity_confidence_factor", 1.0)
        if data_integrity_factor < 1.0:
            original_confidence = confidence
            confidence = round(confidence * data_integrity_factor, 4)
            missing_count = signal_breakdown.get("missing_signal_count", 0)
            logger.info(
                f"Confidence adjusted for data integrity: {original_confidence:.3f} → {confidence:.3f} "
                f"({missing_count} missing signals, factor={data_integrity_factor:.3f})"
            )

        # P1: Apply RSI extreme condition penalty if present
        rsi_flag = signal_breakdown.get("rsi_extreme_flag")
        if rsi_flag:
            rsi_penalty = rsi_flag.get("confidence_penalty", 0.10)
            original_confidence = confidence
            confidence = round(max(0.0, confidence * (1.0 - rsi_penalty)), 4)
            logger.info(
                f"Confidence adjusted for RSI extreme ({rsi_flag['rsi_value']}): "
                f"{original_confidence:.3f} → {confidence:.3f}"
            )

        # Determine watchlist eligibility
        is_watchlist = manager_scorer.determine_watchlist(moat_score)

        # NEW v2.0: Determine 5-tier rating (with manager technical override)
        rating, rating_score = manager_scorer.determine_rating(
            moat_score, technical_score=technical_score
        )

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
    Node 7: Generate investment thesis using LLM (Sonnet).

    Args:
        state: Current workflow state

    Returns:
        Updated state with investment_thesis
    """
    logger.info(f"[Node 7] Generating investment thesis for {state['ticker']}")

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
            rating=state.get("rating", "HOLD"),
            # Enhanced context
            fundamentalist_output=state.get("fundamentalist_output"),
            news_hound_output=state.get("news_hound_output"),
            quant_output=state.get("quant_output"),
        )

        # Update state
        state["investment_thesis"] = thesis.get("investment_thesis", {
            "company_overview": "Error",
            "recommendation_summary": "HOLD",
            "investment_highlights": ["Error generating thesis"],
            "valuation_signal_analysis": "Error",
            "key_risks": ["Error generating thesis"],
            "entry_strategy": "Error"
        })
        state["recommendation"] = thesis.get("recommendation", "HOLD")
        state["strategic_catalysts"] = thesis.get("strategic_catalysts", None)
        state["tokens_used"] = state.get("tokens_used", 0) + tokens
        state["status"] = "completed"

        # ── Recommendation-Rating Alignment Check ──────────────────────────────
        # Compute alignment between the moat scorer's rating and the LLM recommendation.
        # A gap of ≥1 tier means these two systems disagreed. Log for model improvement.
        # The decision_intelligence layer will auto-reconcile the badge to the more
        # conservative value, so the user-facing report will always be consistent.
        _TIER_ORDER = ["STRONG SELL", "SELL", "HOLD", "BUY", "STRONG BUY"]
        _REC_NORMALIZE = {"AVOID": "SELL", "BUY NOW": "BUY", "SCALE IN": "HOLD", "WAIT": "HOLD"}
        scorer_rating = state.get("rating", "HOLD")
        llm_rec = state.get("recommendation", "HOLD")
        llm_rec_normalized = _REC_NORMALIZE.get(llm_rec.upper(), llm_rec.upper())
        if scorer_rating in _TIER_ORDER and llm_rec_normalized in _TIER_ORDER:
            scorer_idx = _TIER_ORDER.index(scorer_rating)
            llm_idx = _TIER_ORDER.index(llm_rec_normalized)
            alignment_gap = abs(scorer_idx - llm_idx)
            if alignment_gap == 0:
                logger.info(f"✓ Rating alignment: scorer={scorer_rating} == LLM={llm_rec} (aligned)")
            else:
                logger.warning(
                    f"⚠ Rating alignment gap detected: scorer={scorer_rating} vs LLM={llm_rec} "
                    f"(normalized: {llm_rec_normalized}, gap={alignment_gap} tiers) "
                    f"— badge will auto-reconcile to more conservative ({llm_rec_normalized if llm_idx < scorer_idx else scorer_rating})"
                )

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

    8-Node Parallel Workflow (NEW: Parallel agent execution):

                                    ┌→ call_fundamentalist ─┐
    0. fetch_swarm_data ─────────┼→ call_news_hound ──────┤→ 4. check_agents_complete
                                    └→ call_quant ──────────┘
                                                               ↓
    8. generate_thesis ← 7. calculate_moat ← 6. synthesize_findings ← 5. (from check)

    Node 0 fetches ALL data once, then all three research agents run in parallel.
    Node 4 synchronizes and verifies all agents completed successfully.

    Returns:
        Compiled StateGraph
    """
    workflow = StateGraph(ManagerState)

    # Add nodes
    workflow.add_node("fetch_swarm_data", fetch_swarm_data_node)  # Node 0: Pre-fetch data
    workflow.add_node("call_fundamentalist", call_fundamentalist_node)  # Node 1: Parallel
    workflow.add_node("call_news_hound", call_news_hound_node)  # Node 2: Parallel
    workflow.add_node("call_quant", call_quant_node)  # Node 3: Parallel
    workflow.add_node("check_agents_complete", check_agents_complete_node)  # Node 4: Sync point
    workflow.add_node("synthesize_findings", synthesize_findings_node)  # Node 5
    workflow.add_node("calculate_moat_score", calculate_moat_score_node)  # Node 6
    workflow.add_node("generate_thesis", generate_thesis_node)  # Node 7

    # Set entry point
    workflow.set_entry_point("fetch_swarm_data")

    # Add edges - parallel fan-out from fetch_swarm_data
    workflow.add_edge("fetch_swarm_data", "call_fundamentalist")
    workflow.add_edge("fetch_swarm_data", "call_news_hound")
    workflow.add_edge("fetch_swarm_data", "call_quant")

    # Add edges - fan-in to check_agents_complete (synchronization point)
    workflow.add_edge("call_fundamentalist", "check_agents_complete")
    workflow.add_edge("call_news_hound", "check_agents_complete")
    workflow.add_edge("call_quant", "check_agents_complete")

    # Add edges - sequential flow after synchronization
    workflow.add_edge("check_agents_complete", "synthesize_findings")
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
    is_etf: bool = False,
) -> ManagerOutput:
    """
    Perform full swarm analysis on a company.

    This orchestrates all three research agents (Fundamentalist, News Hound, Quant)
    in parallel, then synthesizes their findings into a unified investment analysis
    with moat scoring.

    Args:
        ticker: Stock ticker (e.g., "NVDA")
        quarters: Quarters for TTM analysis (e.g., ["Q4_2024", "Q1_2025", "Q2_2025", "Q3_2025"])
        fiscal_year: [Deprecated] Fiscal year for annual analysis (default None)
        news_days_back: Days to look back for news analysis (default 30)
        is_etf: True when analyzing an ETF (routes to ETF pipeline) (default False)

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
        "is_etf": is_etf,
        "etf_synthesis": None,
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
        "recommendation": None,
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

    # Extract VGM scores from fundamentalist_output
    vgm_scores = None
    if final_state.get("fundamentalist_output"):
        vgm_scores = final_state["fundamentalist_output"].get("vgm_scores")

    # Extract fair value calibration from fundamentalist_output
    fair_value_calibration = None
    report_qa_flags = []
    if final_state.get("fundamentalist_output"):
        fair_value_calibration = final_state["fundamentalist_output"].get("fair_value_calibration")
        if fair_value_calibration:
            report_qa_flags.append({
                "type": "fair_value_calibration",
                "ticker": final_state["ticker"],
                "regime": fair_value_calibration.get("regime"),
                "divergence_state": fair_value_calibration.get("divergence_state"),
                "divergence_pct": fair_value_calibration.get("divergence_pct"),
                "gates_triggered": fair_value_calibration.get("gates_triggered", []),
                "internal_fair_value": fair_value_calibration.get("internal_fair_value"),
                "consensus_proxy": fair_value_calibration.get("consensus_proxy"),
                "blended_fair_value": fair_value_calibration.get("blended_fair_value"),
                "intervention_applied": fair_value_calibration.get("intervention_applied"),
            })

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
        strategic_catalysts=final_state.get("strategic_catalysts"),
        moat_score=final_state["moat_score"],
        moat_breakdown=MoatScoreBreakdown(**final_state["moat_breakdown"]),
        confidence=final_state["confidence"],
        is_watchlist_candidate=final_state["is_watchlist_candidate"],
        signal_breakdown=final_state.get("signal_breakdown"),  # v2.0
        vgm_scores=vgm_scores,  # Extract from fundamentalist output
        # Investment recommendations (v2.0)
        price_targets=final_state.get("price_targets"),
        structured_risks=final_state.get("structured_risks"),
        upgrade_triggers=final_state.get("upgrade_triggers"),
        downgrade_triggers=final_state.get("downgrade_triggers"),
        recommendation=final_state.get("recommendation"),
        rating=final_state.get("rating"),
        rating_score=final_state.get("rating_score"),
        risk_level=final_state.get("risk_level"),
        fair_value_calibration=fair_value_calibration,
        report_qa_flags=report_qa_flags if report_qa_flags else None,
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
