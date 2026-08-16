"""Deterministic financial digest (Phase B3).

Replaces the Sonnet qualitative-analysis call. The digest is a factual
composition of the TTM metrics, quarterly trends, and the cached per-filing
extractions (risk factors, growth drivers, management outlook) — every line
grounded in computed or extracted data. The Manager's synthesis call, which
sees all agents' material at once, writes the actual interpretive narrative.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from research_swarm.agents.fundamentalist.models import QuarterlyTrends, TTMMetrics


def _fmt_musd(value: Optional[float]) -> str:
    if value is None:
        return "N/A"
    if abs(value) >= 1000:
        return f"${value / 1000:.1f}B"
    return f"${value:.0f}M"


def _fmt_pct(value: Optional[float]) -> str:
    return f"{value:.1f}%" if value is not None else "N/A"


def build_financial_digest(
    ticker: str,
    analysis_period: str,
    ttm_metrics: TTMMetrics,
    quarterly_trends: QuarterlyTrends,
    filing_extractions: Optional[Dict[str, Optional[Dict[str, Any]]]] = None,
    valuation_metrics: Optional[Dict[str, Any]] = None,
) -> str:
    lines: List[str] = [
        f"Financial profile for {ticker} ({analysis_period}):",
        "",
        f"TTM revenue {_fmt_musd(ttm_metrics.ttm_revenue)}"
        + (f" ({_fmt_pct(ttm_metrics.revenue_growth_yoy)} YoY)" if ttm_metrics.revenue_growth_yoy is not None else "")
        + f"; gross margin {_fmt_pct(ttm_metrics.gross_margin)}, "
        f"operating margin {_fmt_pct(ttm_metrics.operating_margin)}, "
        f"net margin {_fmt_pct(ttm_metrics.net_margin)}.",
        f"TTM net income {_fmt_musd(ttm_metrics.ttm_net_income)}; "
        f"free cash flow {_fmt_musd(ttm_metrics.ttm_free_cash_flow)}.",
        f"Sequential revenue trend: {quarterly_trends.trend_direction}"
        + (
            " (QoQ growth: "
            + ", ".join(
                f"{g:+.1f}%" if g is not None else "n/a"
                for g in quarterly_trends.sequential_growth_rates
            )
            + ")."
            if quarterly_trends.sequential_growth_rates
            else "."
        ),
    ]

    if valuation_metrics:
        pe = valuation_metrics.get("pe_ratio")
        category = valuation_metrics.get("valuation_category")
        if pe is not None or category:
            lines.append(
                "Valuation: "
                + (f"P/E {pe:.1f}" if pe is not None else "P/E N/A")
                + (f", categorized {category}." if category else ".")
            )

    # Most recent filing's qualitative extraction (cached per accession)
    latest = None
    for extraction in reversed(list((filing_extractions or {}).values())):
        if extraction:
            latest = extraction
            break
    if latest:
        outlook = latest.get("management_outlook")
        if outlook:
            lines.extend(["", f"Management outlook (from most recent filing): {outlook}"])
        drivers = latest.get("growth_drivers") or []
        if drivers:
            lines.extend(["", "Growth drivers (from filings):"])
            lines.extend(f"- {d}" for d in drivers[:3])
        risks = latest.get("risk_factors") or []
        if risks:
            lines.extend(["", "Key risk factors (from filings):"])
            lines.extend(f"- {r}" for r in risks[:5])

    return "\n".join(lines)
