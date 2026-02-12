"""
LangGraph workflow for the Fundamentalist agent.

Orchestrates the analysis pipeline from 10-K fetching to health scoring.
"""
import time
from typing import Dict, Any
from langgraph.graph import StateGraph, END
from research_swarm.logger import logger
from research_swarm.data.sec_client import sec_client
from research_swarm.data.data_provider_hybrid import hybrid_provider
from research_swarm.agents.fundamentalist.state import FundamentalistState
from research_swarm.agents.fundamentalist.parser import parser
from research_swarm.agents.fundamentalist.analyzer import analyzer
from research_swarm.agents.fundamentalist.scorer import scorer
from research_swarm.agents.fundamentalist.models import FundamentalistOutput


# ============================================================================
# Helper Functions
# ============================================================================

def _fetch_earnings_data(ticker: str) -> Dict[str, Any]:
    """
    Fetch all earnings data from yfinance via MarketDataClient.

    Args:
        ticker: Stock ticker

    Returns:
        Dict with keys: recommendations, earnings_history, price_target, earnings_dates
    """
    from research_swarm.data.market_data_client import market_data_client

    try:
        data = {
            "recommendations": market_data_client.get_analyst_recommendations(ticker),
            "earnings_history": market_data_client.get_earnings_history(ticker),
            "price_target": market_data_client.get_analyst_price_target(ticker),
            "earnings_dates": market_data_client.get_earnings_dates(ticker)
        }
        return data
    except Exception as e:
        logger.warning(f"Could not fetch earnings data for {ticker}: {e}")
        return {}


def _parse_earnings_estimates(earnings_raw: Dict) -> Any:
    """
    Parse yfinance earnings history into EarningsEstimateRevision model.

    Args:
        earnings_raw: Dict with earnings_history DataFrame

    Returns:
        EarningsEstimateRevision instance or None
    """
    from research_swarm.agents.news_hound.models import EarningsEstimateRevision
    import pandas as pd

    earnings_history = earnings_raw.get("earnings_history")
    if earnings_history is None or (isinstance(earnings_history, pd.DataFrame) and earnings_history.empty):
        return None

    try:
        # Get last 4 quarters
        recent = earnings_history.head(4) if isinstance(earnings_history, pd.DataFrame) else pd.DataFrame()

        if recent.empty:
            return None

        # Calculate beat pattern and average surprise
        beats = 0
        surprise_pcts = []

        for _, row in recent.iterrows():
            eps_est = row.get("epsEstimate") or row.get("Estimate")
            eps_actual = row.get("epsActual") or row.get("Actual")

            if eps_est is not None and eps_actual is not None:
                if eps_est != 0:
                    surprise_pct = ((eps_actual - eps_est) / abs(eps_est)) * 100
                    surprise_pcts.append(surprise_pct)

                    if eps_actual > eps_est:
                        beats += 1

        beat_pattern = f"Beat {beats}/{len(surprise_pcts)}" if surprise_pcts else ""
        avg_surprise = sum(surprise_pcts) / len(surprise_pcts) if surprise_pcts else None

        return EarningsEstimateRevision(
            beat_pattern=beat_pattern,
            avg_surprise_pct=avg_surprise,
            analyst_coverage=0  # yfinance doesn't provide this directly
        )

    except Exception as e:
        logger.error(f"Error parsing earnings estimates: {e}")
        return None


def _parse_analyst_consensus(earnings_raw: Dict) -> Any:
    """
    Parse yfinance price target and recommendations into AnalystConsensus model.

    Args:
        earnings_raw: Dict with price_target data

    Returns:
        AnalystConsensus instance or None
    """
    from research_swarm.agents.news_hound.models import AnalystConsensus

    price_target = earnings_raw.get("price_target")
    if not price_target:
        return None

    try:
        current_price = price_target.get("current_price")
        target_mean = price_target.get("target_mean")
        recommendation = price_target.get("recommendation")

        # Calculate upside
        upside = None
        if current_price and target_mean and current_price > 0:
            upside = ((target_mean - current_price) / current_price) * 100

        # Map recommendation to consensus rating
        rec_map = {
            "strong_buy": "strong buy", "buy": "buy", "outperform": "buy",
            "hold": "hold", "neutral": "hold",
            "underperform": "sell", "sell": "sell", "strong_sell": "strong sell"
        }
        consensus_rating = rec_map.get(recommendation, "hold") if recommendation else "hold"

        return AnalystConsensus(
            consensus_rating=consensus_rating,
            avg_price_target=target_mean,
            high_price_target=price_target.get("target_high"),
            low_price_target=price_target.get("target_low"),
            target_upside_pct=upside
        )

    except Exception as e:
        logger.error(f"Error parsing analyst consensus: {e}")
        return None


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

        state["financial_metrics"] = metrics.dict()
        state["tokens_used"] = state.get("tokens_used", 0) + tokens

    except Exception as e:
        logger.error(f"Failed to extract metrics: {e}")
        state["status"] = "error"
        state["error"] = f"Failed to extract metrics: {str(e)}"

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
            FinancialMetricsOutput
        )

        if not state.get("financial_metrics"):
            raise ValueError("Missing financial_metrics")

        metrics = FinancialMetricsOutput(**state["financial_metrics"])

        analysis, tokens = analyzer.analyze_qualitative(
            state["ticker"],
            state["fiscal_year"],
            state["parsed_sections"],
            metrics
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
            FinancialMetricsOutput
        )

        if not state.get("financial_metrics"):
            raise ValueError("Missing financial_metrics")

        metrics = FinancialMetricsOutput(**state["financial_metrics"])

        # Score
        overall_score, breakdown, confidence, tokens = scorer.score_health(
            state["ticker"],
            state["fiscal_year"],
            metrics,
            state["financial_analysis"]
        )

        if overall_score is None or breakdown is None or confidence is None:
            raise ValueError("score_health returned None values")

        state["financial_health_score"] = overall_score
        state["score_breakdown"] = breakdown.dict()
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
    Node 1 (TTM): Fetch data from hybrid provider (SEC Edgar + yfinance).

    Args:
        state: Current workflow state

    Returns:
        Updated state with filings_raw, earnings data, and metadata
    """
    logger.info(f"[Node 1-TTM] Fetching data for {state['ticker']} via HybridDataProvider")

    state["status"] = "fetching"

    # Single call replaces separate sec_client + earnings data fetches
    complete_data = hybrid_provider.get_complete_data(state["ticker"])

    # Extract filing data (same format as before)
    ttm_result = complete_data["filings_raw"]
    metadata = ttm_result.pop("_metadata", {})

    # Store filings keyed by quarter
    state["filings_raw"] = ttm_result
    state["quarters"] = metadata.get("quarters", [])
    state["analysis_period"] = metadata.get("analysis_period", "")
    state["data_quality"] = metadata.get("data_quality", {})
    state["is_foreign"] = complete_data.get("is_foreign", False)

    available = metadata.get("available_quarters", 0)
    if available == 0:
        state["status"] = "error"
        state["error"] = f"No quarterly filings found for {state['ticker']}"
        return state

    filer_type = "foreign (20-F/6-K)" if state.get("is_foreign") else "domestic (10-K/10-Q)"
    logger.success(f"✓ Fetched {available}/4 quarterly filings ({filer_type})")

    # Earnings data from hybrid provider
    earnings_data = complete_data.get("earnings_data", {})
    state["earnings_raw_data"] = earnings_data

    # Check if we have any meaningful earnings data (handle DataFrames properly)
    has_data = False
    if earnings_data:
        for v in earnings_data.values():
            if v is not None:
                if hasattr(v, 'empty'):  # DataFrame
                    if not v.empty:
                        has_data = True
                        break
                else:  # Dict or other
                    has_data = True
                    break

    if has_data:
        logger.info(f"✓ Fetched earnings data for {state['ticker']}")
    else:
        logger.warning("No earnings data available (continuing with neutral momentum)")

    # Store valuation metrics from yfinance (used by DCF later)
    if complete_data.get("valuation_metrics"):
        state["valuation_metrics"] = complete_data["valuation_metrics"]

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
        state["quarterly_metrics"] = [m.dict() for m in quarterly_metrics]
        state["ttm_metrics"] = ttm_metrics.dict()
        state["quarterly_trends"] = trends.dict()
        state["tokens_used"] = state.get("tokens_used", 0) + tokens

        # ENHANCEMENT: Fallback to yfinance for revenue_growth_yoy if missing from SEC parsing
        if ttm_metrics.revenue_growth_yoy is None:
            try:
                from research_swarm.data.market_data_client import market_data_client
                info = market_data_client.get_company_info(state["ticker"])
                if info:
                    yf_revenue_growth = info.get("revenueGrowth")
                    if yf_revenue_growth is not None:
                        # Convert to percentage (yfinance returns 0.625 for 62.5%)
                        revenue_growth_pct = yf_revenue_growth * 100
                        state["ttm_metrics"]["revenue_growth_yoy"] = revenue_growth_pct
                        logger.info(f"✓ Using yfinance revenue growth: {revenue_growth_pct:.1f}%")
            except Exception as e:
                logger.warning(f"Could not fetch revenue growth from yfinance: {e}")

        # Also populate legacy financial_metrics for compatibility
        state["financial_metrics"] = {
            "revenue": ttm_metrics.ttm_revenue,
            "gross_margin": ttm_metrics.gross_margin,
            "operating_margin": ttm_metrics.operating_margin,
            "net_margin": ttm_metrics.net_margin,
            "revenue_growth_yoy": state["ttm_metrics"].get("revenue_growth_yoy", ttm_metrics.revenue_growth_yoy),
        }

    except Exception as e:
        logger.error(f"Failed to extract TTM metrics: {e}")
        state["status"] = "error"
        state["error"] = f"Failed to extract TTM metrics: {str(e)}"

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
            QuarterlyTrends
        )

        if not state.get("ttm_metrics"):
            raise ValueError("Missing ttm_metrics")

        ttm_metrics = TTMMetrics(**state["ttm_metrics"])
        quarterly_trends = QuarterlyTrends(**state["quarterly_trends"])

        analysis, tokens = analyzer.analyze_qualitative_ttm(
            state["ticker"],
            state["analysis_period"],
            state["quarters"],
            state["parsed_sections_by_quarter"],
            ttm_metrics,
            quarterly_trends
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


def extract_business_model_ttm_node(state: FundamentalistState) -> FundamentalistState:
    """
    Node 6 (TTM): Extract business model and moat data.

    Args:
        state: Current workflow state

    Returns:
        Updated state with business_model_data
    """
    logger.info(f"[Node 6-TTM] Extracting business model data for {state['ticker']}")

    # Skip if previous node failed
    if state.get("status") == "error":
        return state

    try:
        business_model, tokens = analyzer.extract_business_model_ttm(
            state["ticker"],
            state["analysis_period"],
            state["parsed_sections_by_quarter"]
        )

        if not business_model:
            raise ValueError("extract_business_model_ttm returned None")

        state["business_model_data"] = business_model.dict()
        state["tokens_used"] = state.get("tokens_used", 0) + tokens

    except Exception as e:
        logger.error(f"Failed to extract business model: {e}")
        state["status"] = "error"
        state["error"] = f"Failed to extract business model: {str(e)}"

    return state


def score_business_model_ttm_node(state: FundamentalistState) -> FundamentalistState:
    """
    Node 7 (TTM): Score business model and competitive moat.

    Args:
        state: Current workflow state

    Returns:
        Updated state with business_model_moat_score and breakdown
    """
    logger.info(f"[Node 7-TTM] Scoring business model for {state['ticker']}")

    # Skip if previous node failed
    if state.get("status") == "error":
        return state

    try:
        # Reconstruct Pydantic models
        from research_swarm.agents.fundamentalist.models import BusinessModelOutput

        if not state.get("business_model_data"):
            raise ValueError("Missing business_model_data")

        business_model = BusinessModelOutput(**state["business_model_data"])

        # Score business model
        overall_moat_score, moat_breakdown, enhanced_moat, moat_confidence, tokens = scorer.score_business_model_ttm(
            state["ticker"],
            state["analysis_period"],
            business_model,
            state["financial_analysis"]
        )

        if overall_moat_score is None or moat_breakdown is None:
            raise ValueError("score_business_model_ttm returned None values")

        state["business_model_moat_score"] = overall_moat_score
        state["business_model_score_breakdown"] = moat_breakdown.dict()
        state["enhanced_moat"] = enhanced_moat.dict()
        state["tokens_used"] = state.get("tokens_used", 0) + tokens

        # Update confidence with moat confidence (average with existing)
        if state.get("confidence"):
            state["confidence"] = (state["confidence"] + moat_confidence) / 2

        # NEW: Calculate earnings momentum
        if state.get("earnings_raw_data"):
            from research_swarm.agents.fundamentalist.earnings_calculator import earnings_calculator

            momentum_score, breakdown = earnings_calculator.calculate_momentum_score(
                state["earnings_raw_data"]
            )
            state["earnings_momentum_score"] = momentum_score
            state["earnings_momentum_breakdown"] = breakdown
            logger.info(f"✓ Momentum: {momentum_score:.1f}/10 ({breakdown['classification']})")
        else:
            state["earnings_momentum_score"] = 5.0  # Neutral default
            state["earnings_momentum_breakdown"] = None
            logger.warning("No earnings data - using neutral momentum (5.0)")

        # Fetch valuation metrics from yfinance (primary), SEC filing data (fallback)
        from research_swarm.data.market_data_client import market_data_client

        # Always fetch current price independently — more reliable than full valuation
        current_price = market_data_client.get_current_price(state["ticker"])

        valuation_raw = market_data_client.get_valuation_metrics(state["ticker"])
        if valuation_raw:
            state["valuation_metrics"] = valuation_raw
            valuation_score = market_data_client.calculate_valuation_score(valuation_raw)
            state["valuation_score"] = valuation_score
            logger.info(f"✓ Valuation: {valuation_score:.1f}/10 ({valuation_raw.get('valuation_category', 'N/A')})")
        elif current_price and state.get("ttm_metrics"):
            # Fallback: build valuation from SEC filing data + current price
            ttm = state["ttm_metrics"]
            valuation_raw = market_data_client.build_valuation_from_fundamentals(
                ticker=state["ticker"],
                current_price=current_price,
                ttm_net_income=ttm.get("ttm_net_income"),
                ttm_revenue=ttm.get("ttm_revenue"),
                ttm_free_cash_flow=ttm.get("ttm_free_cash_flow"),
            )
            if valuation_raw:
                state["valuation_metrics"] = valuation_raw
                valuation_score = market_data_client.calculate_valuation_score(valuation_raw)
                state["valuation_score"] = valuation_score
                logger.info(f"✓ Valuation (SEC-derived): {valuation_score:.1f}/10 ({valuation_raw.get('valuation_category', 'N/A')})")
            else:
                state["valuation_metrics"] = None
                state["valuation_score"] = 5.0
                logger.warning("No valuation data - using neutral score (5.0)")
        else:
            state["valuation_metrics"] = None
            state["valuation_score"] = 5.0
            logger.warning("No valuation data - using neutral score (5.0)")

        # NEW: Calculate VGM composite
        from research_swarm.agents.fundamentalist.models import TTMMetrics, QuarterlyTrends

        ttm_metrics = TTMMetrics(**state["ttm_metrics"])
        quarterly_trends = QuarterlyTrends(**state["quarterly_trends"])

        vgm_scores, vgm_tokens = scorer.calculate_vgm_scores(
            state["ticker"],
            ttm_metrics,
            quarterly_trends,
            state["earnings_momentum_score"],
            valuation_metrics=valuation_raw
        )

        state["vgm_scores"] = vgm_scores.dict()
        state["tokens_used"] = state.get("tokens_used", 0) + vgm_tokens

        logger.info(f"✓ VGM: {vgm_scores.vgm_composite:.1f}/10 (V:{vgm_scores.value_score:.1f} G:{vgm_scores.growth_score:.1f} M:{vgm_scores.momentum_score:.1f}) - Style: {vgm_scores.best_fit_style}")

        # NEW: DCF Valuation (only if sufficient filing data)
        try:
            from research_swarm.agents.fundamentalist.sec_edgar_parser import enhanced_parser
            from research_swarm.agents.fundamentalist.dcf_calculator import dcf_calculator

            if state.get("parsed_sections_by_quarter"):
                # Use most recent quarter's filing for DCF inputs
                most_recent = list(state["parsed_sections_by_quarter"].keys())[-1]
                most_recent_sections = state["parsed_sections_by_quarter"][most_recent]
                combined_text = "\n".join(most_recent_sections.values())[:30000]

                # Extract DCF inputs (one Haiku call)
                market_data_for_dcf = state.get("valuation_metrics")
                dcf_inputs, dcf_tokens = enhanced_parser.extract_dcf_inputs(
                    state["ticker"],
                    combined_text,
                    market_data=market_data_for_dcf
                )
                state["tokens_used"] = state.get("tokens_used", 0) + dcf_tokens

                # Supplement with yfinance beta if not extracted from filing
                if not dcf_inputs.beta and market_data_for_dcf:
                    dcf_inputs.beta = market_data_for_dcf.get("beta")

                # Calculate DCF if we have sufficient inputs
                # current_price already fetched independently above (more reliable)
                dcf_price = current_price  # from get_current_price() at top of this node
                if not dcf_price and market_data_for_dcf:
                    dcf_price = market_data_for_dcf.get("current_price")

                if dcf_price and dcf_inputs.fcf_history:
                    dcf_result = dcf_calculator.calculate_dcf(dcf_inputs, dcf_price)
                    if dcf_result:
                        state["price_targets"] = dcf_result.dict()
                        logger.info(f"✓ DCF: Base=${dcf_result.base_target:.2f} "
                                    f"Bull=${dcf_result.bull_target:.2f} Bear=${dcf_result.bear_target:.2f}")
                    else:
                        logger.warning("DCF calculation returned None (insufficient data)")
                else:
                    logger.warning(f"Skipping DCF: {'no current_price' if not dcf_price else 'no fcf_history'}")

                # Also extract structured filing data
                filing_type = "10-K"
                if state.get("is_foreign"):
                    filing_type = "20-F"
                structured_data, struct_tokens = enhanced_parser.extract_structured_data(
                    state["ticker"],
                    combined_text,
                    filing_type=filing_type
                )
                state["structured_filing_data"] = structured_data.dict()
                state["tokens_used"] = state.get("tokens_used", 0) + struct_tokens

        except Exception as e:
            logger.warning(f"DCF/structured extraction failed (non-fatal): {e}")
            # DCF is optional — don't fail the whole analysis

    except Exception as e:
        logger.error(f"Failed to score business model: {e}")
        state["status"] = "error"
        state["error"] = f"Failed to score business model: {str(e)}"

    return state


def score_health_ttm_node(state: FundamentalistState) -> FundamentalistState:
    """
    Node 8 (TTM): Score financial health with trend adjustments.

    Args:
        state: Current workflow state

    Returns:
        Updated state with health score and breakdown
    """
    logger.info(f"[Node 8-TTM] Scoring TTM financial health for {state['ticker']}")

    # Skip if previous node failed
    if state.get("status") == "error":
        return state

    state["status"] = "scoring"

    try:
        # Reconstruct Pydantic models
        from research_swarm.agents.fundamentalist.models import (
            TTMMetrics,
            QuarterlyTrends
        )

        if not state.get("ttm_metrics"):
            raise ValueError("Missing ttm_metrics")

        ttm_metrics = TTMMetrics(**state["ttm_metrics"])
        quarterly_trends = QuarterlyTrends(**state["quarterly_trends"])

        # Score using TTM-aware scorer method
        overall_score, breakdown, confidence, tokens = scorer.score_health_ttm(
            state["ticker"],
            state["analysis_period"],
            ttm_metrics,
            quarterly_trends,
            state["financial_analysis"],
            state["data_quality"]
        )

        if overall_score is None or breakdown is None or confidence is None:
            raise ValueError("score_health_ttm returned None values")

        state["financial_health_score"] = overall_score
        state["score_breakdown"] = breakdown.dict()
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
    workflow.add_node("analyze_qualitative", analyze_qualitative_node)
    workflow.add_node("score_health", score_health_node)

    # Set entry point
    workflow.set_entry_point("fetch_filing")

    # Add edges - sequential flow
    workflow.add_edge("fetch_filing", "parse_sections")
    workflow.add_edge("parse_sections", "extract_metrics")
    workflow.add_edge("extract_metrics", "analyze_qualitative")
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
    workflow.add_node("analyze_qualitative_ttm", analyze_qualitative_ttm_node)
    workflow.add_node("extract_business_model_ttm", extract_business_model_ttm_node)
    workflow.add_node("score_business_model_ttm", score_business_model_ttm_node)
    workflow.add_node("score_health_ttm", score_health_ttm_node)

    # Set entry point
    workflow.set_entry_point("fetch_quarterly_filings")

    # Add edges - sequential flow
    workflow.add_edge("fetch_quarterly_filings", "parse_quarterly_sections")
    workflow.add_edge("parse_quarterly_sections", "extract_metrics_ttm")
    workflow.add_edge("extract_metrics_ttm", "analyze_qualitative_ttm")
    workflow.add_edge("analyze_qualitative_ttm", "extract_business_model_ttm")
    workflow.add_edge("extract_business_model_ttm", "score_business_model_ttm")
    workflow.add_edge("score_business_model_ttm", "score_health_ttm")

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
        "business_model_data": None,
        "business_model_moat_score": None,
        "business_model_score_breakdown": None,
        "enhanced_moat": None,
        "financial_analysis": None,
        "financial_health_score": None,
        "score_breakdown": None,
        "confidence": None,
        "processing_time": None,
        "quarters": quarters or [],
        "analysis_period": "",
        "data_quality": {},
        "is_foreign": None,
        "structured_filing_data": None,
        "price_targets": None,
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
        BusinessModelOutput,
        ScoreBreakdown,
        BusinessModelScoreBreakdown,
        EnhancedMoatBreakdown,
        QuarterlyMetrics,
        TTMMetrics,
        QuarterlyTrends,
        VGMScoreBreakdown,
        ValuationMetrics,
        PriceTargetScenarios
    )

    # Parse earnings data into models
    earnings_estimates = None
    analyst_consensus = None

    if final_state.get("earnings_raw_data"):
        earnings_raw = final_state["earnings_raw_data"]
        earnings_estimates = _parse_earnings_estimates(earnings_raw)
        analyst_consensus = _parse_analyst_consensus(earnings_raw)

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
        business_model_data=BusinessModelOutput(**final_state["business_model_data"]),
        financial_analysis=final_state["financial_analysis"],
        financial_health_score=final_state["financial_health_score"],
        score_breakdown=ScoreBreakdown(**final_state["score_breakdown"]),
        business_model_moat_score=final_state["business_model_moat_score"],
        business_model_score_breakdown=BusinessModelScoreBreakdown(**final_state["business_model_score_breakdown"]),
        enhanced_moat=EnhancedMoatBreakdown(**final_state.get("enhanced_moat", {})) if final_state.get("enhanced_moat") else None,
        vgm_scores=VGMScoreBreakdown(**final_state["vgm_scores"]) if final_state.get("vgm_scores") else None,
        earnings_estimates=earnings_estimates,
        analyst_consensus=analyst_consensus,
        earnings_momentum_score=final_state.get("earnings_momentum_score", 5.0),
        earnings_momentum_breakdown=final_state.get("earnings_momentum_breakdown"),
        valuation_score=final_state.get("valuation_score", 5.0),
        valuation_metrics=ValuationMetrics(**final_state["valuation_metrics"]) if final_state.get("valuation_metrics") else None,
        price_targets=PriceTargetScenarios(**final_state["price_targets"]) if final_state.get("price_targets") else None,
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
        BusinessModelOutput,
        ScoreBreakdown,
        BusinessModelScoreBreakdown
    )

    output = FundamentalistOutput(
        ticker=final_state["ticker"],
        fiscal_year=final_state["fiscal_year"],
        analysis_period=f"FY {fiscal_year}",
        analysis_mode="annual",
        filing_date=final_state["filing_raw"].get("filing_date"),
        financial_metrics=FinancialMetricsOutput(**final_state["financial_metrics"]),
        business_model_data=BusinessModelOutput(**final_state.get("business_model_data", {})),
        financial_analysis=final_state["financial_analysis"],
        financial_health_score=final_state["financial_health_score"],
        score_breakdown=ScoreBreakdown(**final_state["score_breakdown"]),
        business_model_moat_score=final_state.get("business_model_moat_score", 5.0),
        business_model_score_breakdown=BusinessModelScoreBreakdown(**final_state.get("business_model_score_breakdown", {
            "revenue_diversification": 5.0,
            "competitive_moat": 5.0
        })),
        confidence=final_state["confidence"],
        tokens_used=final_state.get("tokens_used", 0),
        processing_time=processing_time
    )

    logger.success(
        f"=== Analysis Complete: {ticker} {fiscal_year} "
        f"(Score: {output.financial_health_score:.2f}, Time: {processing_time:.1f}s) ==="
    )

    return output
