"""
LangGraph workflow for the Fundamentalist agent.

Orchestrates the analysis pipeline from 10-K fetching to health scoring.
"""
import time
from typing import Dict, Any, Optional
from langgraph.graph import StateGraph, END
from research_swarm.logger import logger
from research_swarm.data.sec_client import sec_client
from research_swarm.data.data_provider_hybrid import hybrid_provider
from research_swarm.agents.fundamentalist.state import FundamentalistState
from research_swarm.agents.fundamentalist.parser import parser
from research_swarm.agents.fundamentalist.analyzer import analyzer
from research_swarm.agents.fundamentalist.scorer import scorer
from research_swarm.agents.fundamentalist.models import (
    FundamentalistOutput,
    ScoreBreakdown,
    BusinessModelScoreBreakdown,
    FinancialMetricsOutput,
    BusinessModelOutput,
)
from research_swarm.agents.fundamentalist.blended_valuation import blended_valuation_calculator
from research_swarm.agents.fundamentalist.fair_value_calibrator import fair_value_calibrator


# ============================================================================
# Helper Functions
# ============================================================================

def _compute_roic_wacc_spread_score(
    stock_info: Dict[str, Any],
    dcf_inputs: Any,
) -> Optional[float]:
    """
    Score ROIC-WACC spread on a 0-10 scale.

    ROIC proxy: returnOnEquity (ROE) from yfinance — decimal (e.g. 0.15 = 15%).
    WACC: derived from beta, market cap, debt, and tax rate using CAPM.

    Spread thresholds (percentage points above/below cost of capital):
      >=10%  → 9.5  Clear structural moat
       7-10% → 8.5  Strong value creation
       5-7%  → 7.5  Good economic profit
       2-5%  → 6.0  Slight edge
       0-2%  → 4.5  Breakeven — no moat
      -3–0%  → 3.0  Mild value destruction
      < -3%  → 1.5  Structural value destruction

    +0.5 persistence bonus when margin trend is stable/expanding and spread > 2%.
    """
    roic = stock_info.get("returnOnEquity")
    if roic is None:
        return None

    beta = (dcf_inputs.beta or stock_info.get("beta") or 1.0)
    risk_free = dcf_inputs.risk_free_rate / 100.0
    erp = dcf_inputs.equity_risk_premium / 100.0
    tax_rate = (dcf_inputs.effective_tax_rate or 21.0) / 100.0

    cost_of_equity = risk_free + beta * erp
    cost_of_debt = risk_free + 0.02

    debt = dcf_inputs.total_debt or 0
    if dcf_inputs.market_cap_millions and dcf_inputs.market_cap_millions > 0:
        equity = dcf_inputs.market_cap_millions * 1_000_000
    else:
        market_cap = stock_info.get("marketCap")
        equity = market_cap if market_cap else max(debt * 3, 1_000_000_000)

    total_capital = equity + debt
    equity_weight = equity / total_capital
    debt_weight = debt / total_capital

    wacc = (equity_weight * cost_of_equity) + (debt_weight * cost_of_debt * (1 - tax_rate))
    wacc = max(0.05, min(wacc, 0.20))

    spread = roic - wacc

    if spread >= 0.10:
        score = 9.5
    elif spread >= 0.07:
        score = 8.5
    elif spread >= 0.05:
        score = 7.5
    elif spread >= 0.02:
        score = 6.0
    elif spread >= 0.00:
        score = 4.5
    elif spread >= -0.03:
        score = 3.0
    else:
        score = 1.5

    if dcf_inputs.operating_margin_trend in ("stable", "expanding") and spread >= 0.02:
        score = min(10.0, score + 0.5)

    logger.info(
        f"ROIC-WACC: ROE={roic*100:.1f}% WACC={wacc*100:.1f}% "
        f"spread={spread*100:+.1f}% → score={score:.1f}/10"
    )
    return round(score, 1)


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

    NEW: Uses pre-fetched shared_swarm_data if available, falls back to direct fetch.

    Args:
        state: Current workflow state

    Returns:
        Updated state with filings_raw, earnings data, and metadata
    """
    state["status"] = "fetching"

    try:
        # NEW: Check for pre-fetched data from Manager
        complete_data = state.get("shared_swarm_data")

        if complete_data:
            logger.info(f"[Node 1-TTM] Using pre-fetched swarm data for {state['ticker']}")
        else:
            # Fallback: Direct fetch (for standalone execution or backward compatibility)
            logger.info(f"[Node 1-TTM] No shared_swarm_data found, fetching directly for {state['ticker']}")
            complete_data = hybrid_provider.get_complete_data(state["ticker"])

        if not complete_data or "filings_raw" not in complete_data:
            state["status"] = "error"
            state["error"] = f"No data bundle returned for {state['ticker']}"
            return state

        # Extract filing data (same format as before)
        ttm_result = complete_data["filings_raw"]
        if ttm_result is None:
            state["status"] = "error"
            state["error"] = f"filings_raw is None for {state['ticker']}"
            return state
        metadata = ttm_result.pop("_metadata", {})

        # Store filings keyed by quarter
        state["filings_raw"] = ttm_result
        state["quarters"] = metadata.get("quarters", [])
        state["analysis_period"] = metadata.get("analysis_period", "")
        state["data_quality"] = metadata.get("data_quality", {})
        state["is_foreign"] = complete_data.get("is_foreign", False)

        available = metadata.get("available_quarters", 0)
        if available == 0:
            # Check if yfinance financial data is available as fallback
            has_yf_data = bool(complete_data.get("quarterly_financials")) or bool(complete_data.get("valuation_metrics"))
            if not has_yf_data:
                state["status"] = "error"
                state["error"] = f"No quarterly filings or financial data found for {state['ticker']}"
                return state
            logger.warning(
                f"No SEC filings found for {state['ticker']} — continuing with yfinance data only (limited analysis)"
            )
        else:
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

        # Store quarterly financials from yfinance (fallback for LLM extraction)
        if complete_data.get("quarterly_financials"):
            state["yfinance_quarterly_financials"] = complete_data["quarterly_financials"]
            logger.info(f"✓ yfinance quarterly financials available ({complete_data['quarterly_financials'].get('quarters_available', 0)}Q)")

    except Exception as e:
        logger.error(f"Failed to fetch data for {state['ticker']}: {e}")
        state["status"] = "error"
        state["error"] = f"Failed to fetch data: {str(e)}"

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

    # Skip if previous node failed
    if state.get("status") == "error":
        return state

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
        else:
            # Fallback: section patterns didn't match (common for foreign filers
            # like MELI whose 20-F uses non-standard headers). Use raw filing
            # text directly — the LLM can extract metrics from unstructured text.
            if len(filing_text) >= 1000:
                truncated = filing_text[:60000]  # ~60k chars is enough context
                parsed_by_quarter[quarter_label] = {"Item 7": truncated}
                logger.warning(
                    f"Section patterns failed for {quarter_label} ({filing_type}), "
                    f"using raw text fallback ({len(truncated):,} chars)"
                )

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

    # Skip if previous node failed
    if state.get("status") == "error":
        return state

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

        # ENHANCEMENT: Supplement missing TTM metrics with yfinance quarterly financials
        yf_financials = state.get("yfinance_quarterly_financials")
        if yf_financials:
            yf_ttm = yf_financials.get("ttm", {})
            supplemented = []

            # Supplement core metrics if missing from LLM extraction
            metric_map = {
                "ttm_revenue": "ttm_revenue",
                "ttm_gross_profit": "ttm_gross_profit",
                "ttm_operating_income": "ttm_operating_income",
                "ttm_net_income": "ttm_net_income",
                "ttm_free_cash_flow": "ttm_free_cash_flow",
                "gross_margin": "gross_margin",
                "operating_margin": "operating_margin",
                "net_margin": "net_margin",
            }

            for state_key, yf_key in metric_map.items():
                current_val = state["ttm_metrics"].get(state_key)
                yf_val = yf_ttm.get(yf_key)
                if current_val is None and yf_val is not None:
                    state["ttm_metrics"][state_key] = yf_val
                    supplemented.append(state_key)

            if supplemented:
                logger.info(f"✓ Supplemented {len(supplemented)} TTM metrics from yfinance: {', '.join(supplemented)}")

        # Fallback to yfinance for revenue_growth_yoy if still missing
        if state["ttm_metrics"].get("revenue_growth_yoy") is None:
            try:
                from research_swarm.data.market_data_client import market_data_client
                info = market_data_client.get_company_info(state["ticker"])
                if info:
                    yf_revenue_growth = info.get("revenueGrowth")
                    if yf_revenue_growth is not None:
                        revenue_growth_pct = yf_revenue_growth * 100
                        state["ttm_metrics"]["revenue_growth_yoy"] = revenue_growth_pct
                        logger.info(f"✓ Using yfinance revenue growth: {revenue_growth_pct:.1f}%")
            except Exception as e:
                logger.warning(f"Could not fetch revenue growth from yfinance: {e}")

        # Also populate legacy financial_metrics for compatibility
        state["financial_metrics"] = {
            "revenue": state["ttm_metrics"].get("ttm_revenue"),
            "gross_margin": state["ttm_metrics"].get("gross_margin"),
            "operating_margin": state["ttm_metrics"].get("operating_margin"),
            "net_margin": state["ttm_metrics"].get("net_margin"),
            "revenue_growth_yoy": state["ttm_metrics"].get("revenue_growth_yoy"),
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

        # Fetch supplemental market data to enrich analysis context
        from research_swarm.data.market_data_client import market_data_client as _mdc
        key_stats = _mdc.get_key_stats(state["ticker"])
        supplemental_market_data = {
            "valuation_metrics": state.get("valuation_metrics"),
            "key_stats": key_stats,
        }

        analysis, tokens = analyzer.analyze_qualitative_ttm(
            state["ticker"],
            state["analysis_period"],
            state["quarters"],
            state["parsed_sections_by_quarter"],
            ttm_metrics,
            quarterly_trends,
            supplemental_market_data=supplemental_market_data,
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

        # Valuation metrics: prefer the shared-bundle copy fetched once by the
        # Manager (already in state) — refetching here could value the stock at
        # a different price than the one Quant/News Hound saw. Fall back to a
        # direct fetch only when the bundle had nothing.
        from research_swarm.data.market_data_client import market_data_client

        valuation_raw = state.get("valuation_metrics") or market_data_client.get_valuation_metrics(state["ticker"])
        current_price = (valuation_raw or {}).get("current_price") or market_data_client.get_current_price(state["ticker"])
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
            import statistics as _statistics

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

                # Supplement DCF inputs with yfinance data not in filing
                if market_data_for_dcf:
                    if not dcf_inputs.beta:
                        dcf_inputs.beta = market_data_for_dcf.get("beta")
                    if not dcf_inputs.market_cap_millions and market_data_for_dcf.get("market_cap_millions"):
                        dcf_inputs.market_cap_millions = market_data_for_dcf.get("market_cap_millions")

                # Supplement operating_margin_history from quarterly_metrics for margin stability
                if not dcf_inputs.operating_margin_history and state.get("quarterly_metrics"):
                    qm_list = state["quarterly_metrics"]
                    margin_history = []
                    for qm in qm_list:
                        rev = qm.get("revenue")
                        op_inc = qm.get("operating_income")
                        if rev and op_inc and rev > 0:
                            margin_history.append((op_inc / rev) * 100)
                    if len(margin_history) >= 2:
                        dcf_inputs.operating_margin_history = margin_history

                # ── Ticker Financials Cache — fill remaining DCF gaps ──────────────
                # When LLM extraction + quarterly_metrics both miss, fetch from cache
                # (DB first, then yfinance, then EDGAR). Cheap on repeat analyses
                # because cached rows are reused for 90 days.
                _needs_margins = not dcf_inputs.operating_margin_history
                _needs_fcf     = not dcf_inputs.fcf_history
                _needs_trend   = not dcf_inputs.operating_margin_trend

                if _needs_margins or _needs_fcf:
                    try:
                        import asyncio as _asyncio
                        import concurrent.futures as _futures
                        from api.services.ticker_financials_service import (
                            get_quarterly_financials as _get_fins,
                            compute_margin_trend as _margin_trend,
                        )
                        # Graph nodes are sync — run the async fetch in a new thread
                        # with its own event loop to avoid conflicts with the running loop.
                        def _run_in_thread():
                            _loop = _asyncio.new_event_loop()
                            try:
                                async def _isolated():
                                    # Dedicated client: the shared pool must never
                                    # bind a connection to this throwaway loop
                                    # (first-invoke incident 2026-07-10 — closed-loop
                                    # poisoning crashed the next main-loop query).
                                    from prisma import Prisma
                                    _db = Prisma()
                                    await _db.connect()
                                    try:
                                        return await _get_fins(
                                            state["ticker"], min_quarters=8, db=_db
                                        )
                                    finally:
                                        await _db.disconnect()
                                return _loop.run_until_complete(_isolated())
                            finally:
                                _loop.close()

                        with _futures.ThreadPoolExecutor(max_workers=1) as _pool:
                            _fin_rows = _pool.submit(_run_in_thread).result(timeout=30)
                        if _fin_rows:
                            # oldest → newest order for trend computation
                            _fin_rows_asc = list(reversed(_fin_rows))

                            if _needs_margins:
                                _mh = [
                                    r["operating_margin"]
                                    for r in _fin_rows_asc
                                    if r.get("operating_margin") is not None
                                ]
                                if len(_mh) >= 2:
                                    dcf_inputs.operating_margin_history = _mh
                                    logger.info(
                                        f"DCF supplement: {state['ticker']} margin history "
                                        f"({len(_mh)} quarters) from financials cache"
                                    )

                            if _needs_fcf:
                                _fh = [
                                    r["free_cash_flow"]
                                    for r in _fin_rows_asc
                                    if r.get("free_cash_flow") is not None
                                ]
                                if len(_fh) >= 2:
                                    dcf_inputs.fcf_history = _fh
                                    logger.info(
                                        f"DCF supplement: {state['ticker']} FCF history "
                                        f"({len(_fh)} quarters) from financials cache"
                                    )
                    except Exception as _fin_exc:
                        logger.warning(
                            f"ticker_financials_service supplement failed for "
                            f"{state['ticker']}: {_fin_exc}"
                        )

                # Derive operating_margin_trend programmatically if still missing
                if _needs_trend and dcf_inputs.operating_margin_history:
                    try:
                        from api.services.ticker_financials_service import compute_margin_trend as _mt
                        dcf_inputs.operating_margin_trend = _mt(dcf_inputs.operating_margin_history)
                    except Exception:
                        pass

                # Backfill financial_metrics.free_cash_flow from the most recent
                # cache row so GrowthQualityClassification FCF tile shows a value.
                if not state.get("financial_metrics", {}).get("free_cash_flow") and dcf_inputs.fcf_history:
                    state["financial_metrics"]["free_cash_flow"] = dcf_inputs.fcf_history[-1]

                # Calculate fair value using blended methodology
                fair_value_price = current_price  # from get_current_price() at top of this node
                if not fair_value_price and market_data_for_dcf:
                    fair_value_price = market_data_for_dcf.get("current_price")

                # Fetch extended stock data: base info + historical financials for EPS normalization
                stock_info = None
                historical_eps = None
                sbc_ratio = None
                currency_info = None   # set inside try; used for DCF normalization below
                try:
                    import yfinance as yf
                    stock = yf.Ticker(state["ticker"])
                    stock_info = stock.info

                    # ── Currency normalization ──────────────────────────────────────────
                    # Must run before any financial field is read from stock_info.
                    # Converts all monetary fields (ebitda, totalDebt, cash, eps, …)
                    # from the company's reporting currency to USD.
                    from research_swarm.data.currency_normalizer import (
                        detect_currency_info,
                        normalize_stock_info_to_usd,
                        normalize_eps_series_to_usd,
                        normalize_series_to_usd,
                    )
                    currency_info = detect_currency_info(state["ticker"], stock_info)
                    stock_info = normalize_stock_info_to_usd(stock_info, currency_info)
                    # Store report-transparency metadata
                    state["currency_normalization"] = currency_info.as_report_meta()
                    if currency_info.is_converted:
                        logger.info(
                            f"✓ Currency: {currency_info.reporting_currency} → USD "
                            f"@ {currency_info.fx_rate:.6f} (date: {currency_info.conversion_date})"
                        )
                    # ───────────────────────────────────────────────────────────────────

                    # Historical EPS: derive from annual income statement / shares outstanding.
                    # income_stmt rows are in the company's reporting currency, so EPS
                    # computed here is in reporting_currency/share.  We then convert to
                    # USD/share so it is consistent with the USD stock price used in P/E.
                    try:
                        income_stmt = stock.income_stmt  # columns = dates, rows = metrics
                        shares = stock_info.get("sharesOutstanding", 0) if stock_info else 0
                        if income_stmt is not None and not income_stmt.empty and shares and shares > 0:
                            for row_name in ["Net Income", "Net Income Common Stockholders"]:
                                if row_name in income_stmt.index:
                                    net_incomes = income_stmt.loc[row_name].dropna().tolist()
                                    historical_eps = [ni / shares for ni in net_incomes if ni is not None]
                                    break
                        # Normalize EPS to USD (no-op for USD reporters)
                        if historical_eps:
                            historical_eps = normalize_eps_series_to_usd(historical_eps, currency_info)
                    except Exception as e:
                        logger.debug(f"Could not compute historical EPS: {e}")

                    # SBC ratio: SBC / EBITDA to penalize high-SBC businesses.
                    # This is a dimensionless ratio — both SBC (from cashflow_stmt) and
                    # EBITDA must be in the *same* currency.  cashflow_stmt is in reporting
                    # currency, so we use the pre-conversion ebitda_original when available
                    # (i.e. when normalization ran), otherwise the current ebitda value.
                    try:
                        cashflow_stmt = stock.cashflow
                        # Prefer original (reporting-currency) EBITDA to keep ratio dimensionless
                        ebitda_for_ratio = (
                            stock_info.get("ebitda_original")
                            or stock_info.get("ebitda", 0)
                            or 0
                        )
                        if cashflow_stmt is not None and not cashflow_stmt.empty and ebitda_for_ratio and ebitda_for_ratio > 0:
                            for sbc_label in ["Stock Based Compensation", "Share Based Compensation Expense",
                                              "Stock-based Compensation", "Share-based Compensation"]:
                                if sbc_label in cashflow_stmt.index:
                                    sbc_val = cashflow_stmt.loc[sbc_label].iloc[0]
                                    if sbc_val is not None:
                                        sbc_ratio = abs(float(sbc_val)) / ebitda_for_ratio
                                    break
                    except Exception as e:
                        logger.debug(f"Could not compute SBC ratio: {e}")

                except Exception as e:
                    logger.debug(f"Could not fetch extended stock info: {e}")

                # ── Fetch 10-year Treasury yield for regime-sensitive EV/EBITDA (Part 2) ──
                ten_year_yield = None
                try:
                    import yfinance as _yf_macro
                    tnx = _yf_macro.Ticker("^TNX")
                    tnx_info = tnx.info
                    ten_year_yield = (
                        tnx_info.get("regularMarketPrice")
                        or tnx_info.get("previousClose")
                    )
                    if ten_year_yield:
                        logger.info(f"10yr Treasury yield: {ten_year_yield:.2f}%")
                except Exception as e:
                    logger.debug(f"Could not fetch 10yr yield (^TNX): {e}")
                # ──────────────────────────────────────────────────────────────────

                # ── Normalize DCF FCF history to USD ───────────────────────────────
                # dcf_inputs.fcf_history is extracted from SEC filing text by an LLM
                # call and is therefore in the company's reporting currency.
                # Normalize it here using the same currency_info resolved above.
                if currency_info is not None and currency_info.is_converted and dcf_inputs and dcf_inputs.fcf_history:
                    from research_swarm.data.currency_normalizer import normalize_series_to_usd as _norm_series
                    dcf_inputs.fcf_history = _norm_series(dcf_inputs.fcf_history, currency_info)
                    logger.debug(
                        f"DCF FCF history normalized to USD "
                        f"({currency_info.reporting_currency} → USD @ {currency_info.fx_rate:.6f})"
                    )
                # ──────────────────────────────────────────────────────────────────

                # Quarterly margin std dev: measures earnings volatility for spread calculation
                quarterly_margin_std = None
                try:
                    qm_list = state.get("quarterly_metrics", [])
                    margins = []
                    for qm in qm_list:
                        rev = qm.get("revenue")
                        op_inc = qm.get("operating_income")
                        if rev and op_inc and rev > 0:
                            margins.append((op_inc / rev) * 100)
                    if len(margins) >= 2:
                        quarterly_margin_std = _statistics.stdev(margins)
                except Exception as e:
                    logger.debug(f"Could not compute quarterly margin std: {e}")

                if fair_value_price and market_data_for_dcf:
                    # Use blended valuation (normalized P/E + quality-adj. EV/EBITDA + DCF)
                    blended_result = blended_valuation_calculator.calculate_fair_value(
                        ticker=state["ticker"],
                        current_price=fair_value_price,
                        valuation_metrics=market_data_for_dcf,
                        dcf_inputs=dcf_inputs if dcf_inputs.fcf_history else None,
                        stock_info=stock_info,
                        historical_eps=historical_eps,
                        sbc_ratio=sbc_ratio,
                        quarterly_margin_std=quarterly_margin_std,
                        ten_year_yield=ten_year_yield,  # Part 2: regime sensitivity
                        effective_probabilities=None,   # Part 5: future signal integration
                    )
                    if blended_result:
                        # Price targets committed as-is — calibration never mutates them
                        state["price_targets"] = blended_result.dict()

                        # Divergence analysis layer: compares FV to analyst consensus
                        # target. Read-only — does NOT modify blended_result or price_targets.
                        analyst_target_data = state.get("shared_swarm_data", {}) or {}
                        analyst_target_data = analyst_target_data.get("price_target", {}) or {}
                        calib_meta = fair_value_calibrator.calibrate(
                            blended_result=blended_result,
                            current_price=fair_value_price,
                            stock_info=stock_info,
                            valuation_metrics=market_data_for_dcf,
                            analyst_target_data=analyst_target_data,
                        )
                        if calib_meta:
                            state["fair_value_calibration"] = calib_meta.model_dump()
                            div_str = (
                                f"{calib_meta.divergence_pct:+.1f}%"
                                if calib_meta.divergence_pct is not None else "n/a"
                            )
                            logger.info(
                                f"✓ Regime: {calib_meta.divergence_state} "
                                f"(FV ${calib_meta.internal_fair_value:.2f} vs "
                                f"consensus ${calib_meta.consensus_target or 0:.2f}, {div_str})"
                                + (" ⚠ STABILITY WARNING" if calib_meta.model_stability_warning else "")
                            )
                        else:
                            state["fair_value_calibration"] = None

                        logger.success(
                            f"✓ Blended Fair Value: "
                            f"Band ${blended_result.fair_value_low:.2f}–${blended_result.fair_value_mid:.2f}–${blended_result.fair_value_high:.2f} "
                            f"| Confidence {blended_result.confidence_score}/100 ({blended_result.confidence}) "
                            f"| {blended_result.price_vs_zone} "
                            f"({blended_result.methodology})"
                        )
                    else:
                        logger.warning("Blended valuation returned None (insufficient data)")
                        state["fair_value_calibration"] = None
                else:
                    logger.warning(f"Skipping valuation: {'no current_price' if not fair_value_price else 'no valuation_metrics'}")

                # v3.0: ROIC-WACC spread score (uses stock_info + dcf_inputs, independent of blended FV)
                if stock_info:
                    roic_wacc = _compute_roic_wacc_spread_score(stock_info, dcf_inputs)
                    if roic_wacc is not None:
                        state["roic_wacc_spread_score"] = roic_wacc

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
# ETF Analysis Function
# ============================================================================

def _analyze_etf_holdings(ticker: str, etf_context: dict) -> "FundamentalistOutput":
    """
    ETF-mode fundamentalist analysis: holdings composition + macro context.
    Replaces SEC filing analysis when the ticker is an ETF.
    """
    import anthropic
    import json

    logger.info(f"[ETF Fundamentalist] Analyzing holdings and macro for {ticker}")
    start_time = time.time()

    client = anthropic.Anthropic()

    fund_name = etf_context.get("fund_name", ticker)
    top_holdings = etf_context.get("top_holdings", [])
    sector_weights = etf_context.get("sector_weights", {})
    aum_billions = etf_context.get("aum_billions")
    expense_ratio = etf_context.get("expense_ratio")
    ytd_return = etf_context.get("ytd_return")
    three_y_return = etf_context.get("3y_return")
    five_y_return = etf_context.get("5y_return")
    w52_high = etf_context.get("52w_high")
    w52_low = etf_context.get("52w_low")
    current_price = etf_context.get("current_price")

    holdings_text = "\n".join([
        f"  {h.get('symbol', '')}: {h.get('weight_pct', 0)}%"
        for h in top_holdings[:10]
    ])
    sector_text = "\n".join([
        f"  {sector}: {weight}%"
        for sector, weight in sector_weights.items()
    ])

    prompt = f"""You are a senior portfolio analyst at a high-level portfolio management firm.
Analyze the following ETF for inclusion in a diversified institutional portfolio.

ETF: {ticker} — {fund_name}
AUM: ${aum_billions}B | Expense Ratio: {expense_ratio}% | Current Price: ${current_price}
52-Week Range: ${w52_low} – ${w52_high}
Returns: YTD {ytd_return}% | 3Y {three_y_return}% | 5Y {five_y_return}%

TOP HOLDINGS:
{holdings_text}

SECTOR ALLOCATION:
{sector_text}

Provide a JSON analysis with EXACTLY these fields:
{{
  "financial_health_score": <float 0-10: macro alignment — how well current macro conditions favor this sector>,
  "earnings_momentum_score": <float 0-10: fund flow momentum and trend strength>,
  "valuation_score": <float 0-10: ETF premium/discount to NAV, expense ratio attractiveness>,
  "concentration_risk_score": <float 0-10: higher = MORE diversified, lower = highly concentrated>,
  "macro_alignment_notes": <string: 2-3 sentences on macro tailwinds/headwinds>,
  "holdings_analysis": <string: 2-3 sentences on top holdings quality and concentration risk>,
  "key_insights": [<3 string bullet points: investment positives>],
  "risk_factors": [<3 string bullet points: investment risks>],
  "confidence": <float 0-1>
}}

Return ONLY the JSON object, no markdown."""

    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1500,
        messages=[{"role": "user", "content": prompt}]
    )

    tokens_used = message.usage.input_tokens + message.usage.output_tokens

    raw_text = message.content[0].text.strip()
    if raw_text.startswith("```"):
        raw_text = raw_text.split("```")[1]
        if raw_text.startswith("json"):
            raw_text = raw_text[4:]
        raw_text = raw_text.strip()

    try:
        analysis = json.loads(raw_text)
    except json.JSONDecodeError as exc:
        logger.error(f"[ETF Fundamentalist] JSON parse failed for {ticker}. Raw: {raw_text[:200]!r}")
        raise ValueError(f"LLM returned unparseable JSON: {exc}") from exc
    processing_time = time.time() - start_time

    # Map ETF scores to FundamentalistOutput fields.
    # financial_health_score → macro alignment (maps to profitability in ScoreBreakdown)
    # earnings_momentum_score → fund flow momentum
    # valuation_score → ETF valuation attractiveness
    # concentration_risk_score → balance sheet proxy (diversification)
    financial_health_score = float(analysis.get("financial_health_score", 5.0))
    earnings_momentum_score = float(analysis.get("earnings_momentum_score", 5.0))
    valuation_score_val = float(analysis.get("valuation_score", 5.0))
    concentration_score = float(analysis.get("concentration_risk_score", 5.0))

    # Build ScoreBreakdown: map ETF dimensions to equity score fields
    # profitability → macro alignment (financial_health_score)
    # growth → earnings momentum
    # balance_sheet → concentration/diversification
    # cash_flow → valuation attractiveness
    score_breakdown = ScoreBreakdown(
        profitability=financial_health_score,
        growth=earnings_momentum_score,
        balance_sheet=concentration_score,
        cash_flow=valuation_score_val,
    )

    # Business model breakdown: use diversification and macro alignment
    business_model_score_breakdown = BusinessModelScoreBreakdown(
        revenue_diversification=concentration_score,
        competitive_moat=financial_health_score,
    )

    # Build qualitative analysis text from LLM output
    key_insights = analysis.get("key_insights", [])
    risk_factors = analysis.get("risk_factors", [])
    financial_analysis = (
        f"ETF Holdings & Macro Analysis — {ticker} ({fund_name})\n\n"
        f"Macro Context: {analysis.get('macro_alignment_notes', '')}\n\n"
        f"Holdings: {analysis.get('holdings_analysis', '')}\n\n"
        f"Key Insights:\n" + "\n".join(f"• {i}" for i in key_insights) + "\n\n"
        f"Risk Factors:\n" + "\n".join(f"• {r}" for r in risk_factors)
    )

    output = FundamentalistOutput(
        ticker=ticker,
        analysis_period=f"ETF Analysis — {fund_name}",
        analysis_mode="etf",
        financial_metrics=FinancialMetricsOutput(),
        business_model_data=BusinessModelOutput(
            moat_characteristics=[
                f"Diversified ETF: {fund_name}",
                f"AUM: ${aum_billions}B",
                f"Expense Ratio: {expense_ratio}%",
            ]
        ),
        financial_analysis=financial_analysis,
        financial_health_score=score_breakdown.weighted_average(),
        score_breakdown=score_breakdown,
        business_model_moat_score=business_model_score_breakdown.weighted_average(),
        business_model_score_breakdown=business_model_score_breakdown,
        earnings_momentum_score=earnings_momentum_score,
        valuation_score=valuation_score_val,
        confidence=float(analysis.get("confidence", 0.7)),
        tokens_used=tokens_used,
        processing_time=processing_time,
    )

    logger.success(f"✓ ETF Fundamentalist complete: {ticker}")
    return output


# ============================================================================
# Main Analysis Function
# ============================================================================

def analyze_company(
    ticker: str,
    quarters: list = None,
    fiscal_year: int = None,
    mode: str = "ttm",
    shared_swarm_data: dict = None,  # NEW: Pre-fetched data from Manager
    etf_context: dict = None,
) -> FundamentalistOutput:
    """
    Analyze a company's financial health.

    Args:
        ticker: Stock ticker (e.g., "AAPL")
        quarters: List of quarters for TTM mode (default: fetch latest 4 quarters)
        fiscal_year: Fiscal year for annual mode (deprecated)
        mode: "ttm" or "annual" (default: "ttm")
        shared_swarm_data: Pre-fetched data bundle from Manager (NEW)
        etf_context: ETF holdings/profile data from Manager (NEW). When provided,
            bypasses SEC filing analysis and runs ETF holdings analysis instead.

    Returns:
        FundamentalistOutput with complete analysis

    Raises:
        ValueError: If analysis fails
    """
    if etf_context is not None:
        return _analyze_etf_holdings(ticker, etf_context)

    # Determine mode
    if fiscal_year is not None:
        mode = "annual"
        logger.warning(f"fiscal_year parameter is deprecated. Using annual mode for {ticker} FY{fiscal_year}")

    if mode == "ttm":
        return _analyze_company_ttm(ticker, quarters, shared_swarm_data)
    else:
        return _analyze_company_annual(ticker, fiscal_year)


def _analyze_company_ttm(ticker: str, quarters: list = None, shared_swarm_data: dict = None) -> FundamentalistOutput:
    """
    Analyze company using TTM (quarterly) data.

    Args:
        ticker: Stock ticker
        quarters: Optional list of quarters (auto-fetched if None)
        shared_swarm_data: Pre-fetched data bundle from Manager (NEW)

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
        "price_targets": None,
        "shared_swarm_data": shared_swarm_data,  # NEW: Pre-fetched data from Manager
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
        PriceTargetScenarios,
        FairValueCalibration,
        CurrencyNormalizationMeta,
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
        roic_wacc_spread_score=final_state.get("roic_wacc_spread_score"),
        valuation_score=final_state.get("valuation_score", 5.0),
        valuation_metrics=ValuationMetrics(**final_state["valuation_metrics"]) if final_state.get("valuation_metrics") else None,
        price_targets=PriceTargetScenarios(**final_state["price_targets"]) if final_state.get("price_targets") else None,
        fair_value_calibration=FairValueCalibration(**final_state["fair_value_calibration"]) if final_state.get("fair_value_calibration") else None,
        currency_normalization=CurrencyNormalizationMeta(**final_state["currency_normalization"]) if final_state.get("currency_normalization") else None,
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
