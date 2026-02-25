"""
Normalized PDF view models for institutional-grade report generation.

PdfStockModel and PdfRunModel are canonical, deterministic representations
of ReportData/StockReportData scoped to a specific user tier. They:

  - Always have an InvestmentThesisStructured (never a raw string)
  - Omit Trader-only fields for Investor-tier exports
  - Handle missing/None fields gracefully (callers never need to guard)
  - Provide a clean, stable API for the PDF template

Tier feature matrix:
  Starter  → cannot export PDF (enforced upstream in api/routes/reports.py)
  Investor → core + decision_framework + conviction_position
  Trader   → above + enhanced_trade_setup + fund_tech_divergence
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

from research_swarm.agents.manager.models import InvestmentThesisStructured


# ────────────────────────────────────────────────────────────────────────────
# Per-stock normalized model
# ────────────────────────────────────────────────────────────────────────────

@dataclass
class PdfStockModel:
    # ── Identity ───────────────────────────────────────────────────────────
    ticker: str
    rating: str                         # e.g. "STRONG BUY"
    risk_level: str                     # "Low" | "Medium" | "High"
    moat_score: float
    rating_score: Optional[float]
    is_watchlist_candidate: bool

    # ── Investment thesis (always structured after normalization) ──────────
    investment_thesis: Optional[InvestmentThesisStructured]

    # ── Moat scoring ──────────────────────────────────────────────────────
    moat_breakdown: Dict[str, float]    # {earnings_momentum, financial_health, ...}

    # ── Key bullets ───────────────────────────────────────────────────────
    key_insights: List[str]
    # structured_risks preferred; falls back to risk_factors list
    structured_risks: Optional[List[Dict[str, Any]]]
    risk_factors: List[str]

    # ── Valuation snapshot ─────────────────────────────────────────────────
    valuation_metrics: Optional[Dict[str, Any]]
    price_targets: Optional[Dict[str, Any]]
    analyst_consensus: Optional[Dict[str, Any]]
    valuation_sensitivity: Optional[Dict[str, Any]]

    # ── Catalyst snapshot ──────────────────────────────────────────────────
    upcoming_catalysts: Optional[Dict[str, Any]]
    earnings_estimates: Optional[Dict[str, Any]]

    # ── Smart money / short interest ───────────────────────────────────────
    institutional_activity: Optional[Dict[str, Any]]
    insider_activity: Optional[Dict[str, Any]]
    short_interest: Optional[Dict[str, Any]]
    management_commentary: Optional[Dict[str, Any]]

    # ── Decision intelligence (Investor+) ──────────────────────────────────
    decision_framework: Optional[Dict[str, Any]]
    conviction_position: Optional[Dict[str, Any]]
    conviction_statement: Optional[Dict[str, Any]]

    # ── Trader-only (None for Investor tier) ──────────────────────────────
    enhanced_trade_setup: Optional[Dict[str, Any]]
    fund_tech_divergence: Optional[Dict[str, Any]]

    # ── Supporting data ────────────────────────────────────────────────────
    enhanced_moat: Optional[Dict[str, Any]]
    vgm_scores: Optional[Dict[str, Any]]
    peer_comparison: Optional[Dict[str, Any]]
    signal_breakdown: Optional[Dict[str, Any]]
    upgrade_triggers: Optional[List[Dict[str, str]]]
    downgrade_triggers: Optional[List[Dict[str, str]]]
    recommended_strategy: Optional[Dict[str, Any]]
    track_record: Optional[Dict[str, Any]]


# ────────────────────────────────────────────────────────────────────────────
# Run-level normalized model
# ────────────────────────────────────────────────────────────────────────────

@dataclass
class PdfRunModel:
    # ── Run identity ───────────────────────────────────────────────────────
    run_id: str
    run_name: Optional[str]
    generated_at: datetime
    analysis_date: str
    analysis_period: str

    # ── Summary stats ──────────────────────────────────────────────────────
    total_stocks: int
    completed_count: int
    failed_count: int
    average_moat_score: float
    total_cost_usd: float

    # ── Cohorts ────────────────────────────────────────────────────────────
    top_picks: List[PdfStockModel]
    watchlist_candidates: List[PdfStockModel]
    remaining_stocks: List[PdfStockModel]

    # ── Tier context ───────────────────────────────────────────────────────
    tier: str                           # "investor" | "trader"
    include_trade_setup: bool           # True only for trader tier


# ────────────────────────────────────────────────────────────────────────────
# Builder
# ────────────────────────────────────────────────────────────────────────────

def build_pdf_model(report_data: "ReportData", tier: str) -> PdfRunModel:  # noqa: F821
    """
    Convert a ReportData + tier string into a clean PdfRunModel.

    Tier-based redaction:
      - Investor: omits enhanced_trade_setup and fund_tech_divergence
      - Trader:   includes all fields
      - Starter:  should never reach here (blocked upstream)
    """
    tier = (tier or "investor").lower()
    include_trade_setup = (tier == "trader")

    top_tickers = {s.ticker for s in report_data.top_picks}
    watchlist_tickers = {s.ticker for s in report_data.watchlist_candidates}

    top_picks = [_normalize_stock(s, include_trade_setup) for s in report_data.top_picks]
    watchlist_candidates = [
        _normalize_stock(s, include_trade_setup)
        for s in report_data.watchlist_candidates
        if s.ticker not in top_tickers
    ]
    remaining_stocks = [
        _normalize_stock(s, include_trade_setup)
        for s in report_data.stocks
        if s.ticker not in top_tickers and s.ticker not in watchlist_tickers
    ]

    return PdfRunModel(
        run_id=report_data.run_id,
        run_name=report_data.run_name,
        generated_at=report_data.generated_at,
        analysis_date=report_data.analysis_date,
        analysis_period=report_data.analysis_period,
        total_stocks=report_data.total_stocks,
        completed_count=report_data.completed_count,
        failed_count=report_data.failed_count,
        average_moat_score=report_data.average_moat_score,
        total_cost_usd=report_data.total_cost_usd,
        top_picks=top_picks,
        watchlist_candidates=watchlist_candidates,
        remaining_stocks=remaining_stocks,
        tier=tier,
        include_trade_setup=include_trade_setup,
    )


def _normalize_stock(stock: "StockReportData", include_trade_setup: bool) -> PdfStockModel:  # noqa: F821
    """Convert one StockReportData → PdfStockModel, applying tier redaction."""
    # Resolve investment_thesis (validator already normalised it; handle legacy None)
    thesis = stock.investment_thesis
    if not isinstance(thesis, InvestmentThesisStructured):
        thesis = None  # will render gracefully as no-thesis

    # Prefer structured risks; fall back to plain risk_factors list
    structured_risks = stock.structured_risks or None
    risk_factors = list(stock.risk_factors or [])

    return PdfStockModel(
        ticker=stock.ticker,
        rating=stock.rating or _derive_rating(stock.moat_score),
        risk_level=stock.risk_level or "Medium",
        moat_score=stock.moat_score or 0.0,
        rating_score=stock.rating_score,
        is_watchlist_candidate=stock.is_watchlist_candidate or False,

        investment_thesis=thesis,
        moat_breakdown=_safe_dict(stock.moat_breakdown),
        key_insights=list(stock.key_insights or []),
        structured_risks=structured_risks,
        risk_factors=risk_factors,

        valuation_metrics=stock.valuation_metrics,
        price_targets=stock.price_targets,
        analyst_consensus=stock.analyst_consensus,
        valuation_sensitivity=stock.valuation_sensitivity,

        upcoming_catalysts=stock.upcoming_catalysts,
        earnings_estimates=stock.earnings_estimates,

        institutional_activity=stock.institutional_activity,
        insider_activity=stock.insider_activity,
        short_interest=stock.short_interest,
        management_commentary=stock.management_commentary,

        decision_framework=stock.decision_framework,
        conviction_position=stock.conviction_position,
        conviction_statement=stock.conviction_statement,

        # Trader-only gating
        enhanced_trade_setup=stock.enhanced_trade_setup if include_trade_setup else None,
        fund_tech_divergence=stock.fund_tech_divergence if include_trade_setup else None,

        enhanced_moat=stock.enhanced_moat,
        vgm_scores=stock.vgm_scores,
        peer_comparison=stock.peer_comparison,
        signal_breakdown=stock.signal_breakdown,
        upgrade_triggers=stock.upgrade_triggers or [],
        downgrade_triggers=stock.downgrade_triggers or [],
        recommended_strategy=stock.recommended_strategy,
        track_record=stock.track_record,
    )


def _safe_dict(v: Any) -> Dict[str, float]:
    """Return a dict of floats from moat_breakdown (dict or Pydantic model)."""
    if v is None:
        return {}
    if hasattr(v, "model_dump"):
        return {k: float(val) for k, val in v.model_dump().items() if val is not None}
    if isinstance(v, dict):
        return {k: float(val) for k, val in v.items() if val is not None}
    return {}


def _derive_rating(moat_score: Optional[float]) -> str:
    ms = moat_score or 5.0
    if ms >= 8.5:
        return "STRONG BUY"
    if ms >= 7.0:
        return "BUY"
    if ms >= 5.0:
        return "HOLD"
    if ms >= 3.5:
        return "SELL"
    return "STRONG SELL"
