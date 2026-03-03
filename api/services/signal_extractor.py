"""
Signal Extractor — bridges StockResult.fullOutput to CompounderEngine SignalInput.

Converts the report-driven agent output into the signal contract consumed by
the portfolio engine. This is the translation layer between the research pipeline
and the ownership system.

Usage:
    from api.services.signal_extractor import extract_signal_from_full_output

    signal = extract_signal_from_full_output(
        ticker="AAPL",
        full_output=stock_result.fullOutput,
        moat_score=stock_result.moatScore or 0.0,
        sector="Technology",
        current_price=175.50,
    )
"""

from __future__ import annotations

import logging
from typing import Optional

from api.lib.compounder_owner_v3 import SignalInput

logger = logging.getLogger(__name__)


def extract_signal_from_full_output(
    ticker: str,
    full_output: dict,
    moat_score: float,
    sector: str = "Unknown",
    current_price: float = 0.0,
) -> SignalInput:
    """
    Convert a StockResult's full_output dict to a SignalInput for the CompounderEngine.

    Extracts from three agent output dicts:
      - fundamentalist_output → financial metrics (revenue, margins, FCF)
      - quant_output → technical indicators (52-week high, 200DMA)
      - news_hound_output → earnings revision signal

    Returns a SignalInput dataclass ready for engine consumption.
    """
    fund = full_output.get("fundamentalist_output") or {}
    quant = full_output.get("quant_output") or {}
    news = full_output.get("news_hound_output") or {}

    # ── Financial metrics from fundamentalist ────────────────────────────────
    fm = fund.get("financial_metrics") or {}

    revenue_3y_cagr = _safe_float(fm.get("revenue_cagr_3y") or fm.get("revenue_3y_cagr"))
    revenue_growth_yoy = _safe_float(fm.get("revenue_growth_yoy") or fm.get("revenue_growth"))
    revenue_growth_persistence = _safe_int(fm.get("revenue_growth_persistence"))
    gross_margin = _safe_float(fm.get("gross_margin"))
    fcf_margin = _safe_float(fm.get("fcf_margin") or fm.get("free_cash_flow_margin"))

    # Margin trend: check for explicit field or derive from financial_analysis
    margin_trend = _extract_margin_trend(fm, fund)

    # ── Earnings revision from news hound ────────────────────────────────────
    earnings_est = news.get("earnings_estimates") or {}
    eps_revision_positive = bool(earnings_est.get("net_positive_revisions", False))
    # Fallback: check revision direction
    if not eps_revision_positive:
        revisions = earnings_est.get("revisions") or {}
        up = revisions.get("up_last_30d", 0) or 0
        down = revisions.get("down_last_30d", 0) or 0
        eps_revision_positive = up > down

    # ── Technical indicators from quant ──────────────────────────────────────
    ti = quant.get("technical_indicators") or {}
    ma = ti.get("moving_averages") or {}

    high_252d = _safe_float(
        ti.get("high_52_week")
        or ti.get("week_52_high")
        or ma.get("high_252d")
    )
    ma_200d = _safe_float(
        ma.get("sma_200")
        or ti.get("sma_200")
        or ma.get("ma_200d")
    )

    # If current_price not provided, try to get from quant output
    if current_price <= 0:
        current_price = _safe_float(
            ma.get("current_price")
            or ti.get("current_price")
            or quant.get("current_price")
        ) or 0.0

    return SignalInput(
        ticker=ticker,
        revenue_3y_cagr=revenue_3y_cagr,
        revenue_growth_yoy=revenue_growth_yoy,
        revenue_growth_persistence=revenue_growth_persistence,
        gross_margin=gross_margin,
        fcf_margin=fcf_margin,
        moat_score=moat_score,
        margin_trend=margin_trend,
        eps_revision_positive=eps_revision_positive,
        sector=sector,
        current_price=current_price,
        high_252d=high_252d,
        ma_200d=ma_200d,
    )


# ── Helpers ──────────────────────────────────────────────────────────────────


def _safe_float(val) -> Optional[float]:
    """Safely convert a value to float, returning None on failure."""
    if val is None:
        return None
    try:
        return float(val)
    except (ValueError, TypeError):
        return None


def _safe_int(val) -> Optional[int]:
    """Safely convert a value to int, returning None on failure."""
    if val is None:
        return None
    try:
        return int(val)
    except (ValueError, TypeError):
        return None


def _extract_margin_trend(fm: dict, fund: dict) -> str:
    """
    Determine margin trend from financial metrics.

    Checks for explicit margin_trend field, or derives from gross_margin_change.
    Falls back to "unknown".
    """
    # Explicit field
    trend = fm.get("margin_trend")
    if trend and isinstance(trend, str) and trend in ("expanding", "stable", "contracting"):
        return trend

    # Derive from gross margin change (if available)
    gm_change = _safe_float(fm.get("gross_margin_change") or fm.get("margin_change_yoy"))
    if gm_change is not None:
        if gm_change > 1.0:
            return "expanding"
        elif gm_change < -1.0:
            return "contracting"
        else:
            return "stable"

    # Check score breakdown for clues
    score_breakdown = fund.get("score_breakdown") or {}
    profitability = _safe_float(score_breakdown.get("profitability"))
    if profitability is not None:
        if profitability >= 7.0:
            return "expanding"
        elif profitability <= 4.0:
            return "contracting"
        else:
            return "stable"

    return "unknown"
