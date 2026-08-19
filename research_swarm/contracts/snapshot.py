"""TickerSnapshot — the single input contract for one analysis.

One parallel-IO fetch pass assembles this object; every downstream stage
(compute, interpret, decide) takes it as a typed argument. Design rules:

1. Everything is fetched exactly once. No stage refetches; if a field is
   missing here, it is missing everywhere, visibly.
2. Every section carries provenance (source, fetched_at, status) so
   "missing", "stale", and "degraded fallback" are first-class states —
   never a silent {} or a fabricated default.
3. All money is USD. Currency normalization happens at assembly time and
   is recorded in `fx`, so no consumer ever sees mixed currencies.
4. Filing extractions are keyed by SEC accession number and cached
   independently of the snapshot — they are per-company-per-quarter facts,
   not per-request work.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


# ── Provenance ──────────────────────────────────────────────────────────────


class SectionStatus(str, Enum):
    """Health of one snapshot section. Consumers branch on this, never on
    truthiness of the payload."""

    FRESH = "fresh"            # fetched live or from a within-TTL cache
    CACHED = "cached"          # served from cache, older than ideal but usable
    DEGRADED = "degraded"      # fallback source with reduced fidelity (record which)
    MISSING = "missing"        # provider had nothing for this ticker
    ERROR = "error"            # fetch failed; error recorded in `detail`


class Provenance(BaseModel):
    """Where a section came from and how much to trust it."""

    source: str = Field(..., description="Provider id, e.g. 'yfinance', 'sec_edgar', 'openinsider'")
    status: SectionStatus
    fetched_at: datetime
    detail: Optional[str] = Field(None, description="Fallback reason or error message")


# ── Market data ─────────────────────────────────────────────────────────────


class Quote(BaseModel):
    price: float = Field(..., gt=0, description="Last price, USD")
    market_cap: Optional[float] = Field(None, description="Market cap, USD")
    shares_outstanding: Optional[float] = None
    high_52_week: Optional[float] = None
    low_52_week: Optional[float] = None
    avg_volume_30d: Optional[float] = None
    as_of: datetime


class OHLCVBar(BaseModel):
    date: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float


class PriceHistory(BaseModel):
    """Daily bars for the analysis window, plus benchmark series for
    relative-strength work so the quant stage never refetches."""

    bars: List[OHLCVBar] = Field(default_factory=list)
    benchmark_bars: List[OHLCVBar] = Field(default_factory=list, description="SPY over the same window")
    sector_etf_ticker: Optional[str] = None
    sector_etf_bars: List[OHLCVBar] = Field(default_factory=list)


class FxNormalization(BaseModel):
    """Record of the currency conversion applied at assembly time."""

    reporting_currency: str = Field(..., description="ISO code of the filer's reporting currency")
    fx_rate_to_usd: float = Field(1.0, description="Rate applied to reach USD")
    converted: bool = Field(False, description="False means figures are native USD already")
    rate_as_of: Optional[datetime] = None


# ── Fundamentals ────────────────────────────────────────────────────────────


class FundamentalsTTM(BaseModel):
    """Trailing-twelve-month metrics, USD, percentages in points (12.5 = 12.5%)."""

    revenue: Optional[float] = Field(None, description="TTM revenue, USD millions")
    revenue_growth_yoy_pct: Optional[float] = None
    gross_margin_pct: Optional[float] = None
    operating_margin_pct: Optional[float] = None
    net_margin_pct: Optional[float] = None
    free_cash_flow: Optional[float] = Field(None, description="USD millions")
    capex: Optional[float] = Field(None, description="USD millions")
    rd_expense: Optional[float] = Field(None, description="USD millions")
    cash_and_equivalents: Optional[float] = Field(None, description="USD millions")
    total_debt: Optional[float] = Field(None, description="USD millions, balance-sheet stock")
    debt_to_equity: Optional[float] = None
    current_ratio: Optional[float] = None
    interest_coverage: Optional[float] = None
    roic_pct: Optional[float] = None
    wacc_pct: Optional[float] = None


class ValuationMultiples(BaseModel):
    pe_ttm: Optional[float] = None
    pe_forward: Optional[float] = None
    peg: Optional[float] = None
    price_to_book: Optional[float] = None
    price_to_sales: Optional[float] = None
    ev_to_ebitda: Optional[float] = None
    dividend_yield_pct: Optional[float] = None
    sector_median_pe: Optional[float] = None
    sector_median_source: Optional[str] = Field(
        None, description="Where the sector median came from and its as-of date"
    )


# ── Filings (cached by accession number, shared across requests) ────────────


class FilingExtraction(BaseModel):
    """Structured LLM extraction of one filing. Produced once per filing,
    cached by accession number; snapshots reference these, never raw text."""

    accession_number: str
    form_type: str = Field(..., description="10-K / 10-Q / 20-F / 6-K / 8-K")
    period_end: Optional[str] = Field(None, description="Fiscal period the filing covers")
    filed_at: Optional[datetime] = None
    risk_factors: List[str] = Field(default_factory=list)
    growth_drivers: List[str] = Field(default_factory=list)
    management_outlook: Optional[str] = None
    notable_events: List[str] = Field(default_factory=list, description="8-K material events")
    extraction_model: Optional[str] = Field(None, description="Model id that produced this extraction")


# ── News & sentiment inputs ─────────────────────────────────────────────────


class NewsItem(BaseModel):
    title: str
    source: str
    published_at: datetime
    url: Optional[str] = None
    summary: Optional[str] = None


class NewsBundle(BaseModel):
    query: str = Field(..., description="The actual query sent (company name + ticker)")
    window_days: int = 30
    items: List[NewsItem] = Field(default_factory=list)
    is_mock: bool = Field(False, description="True only in explicit dev/test mode; never silently")


# ── Ownership & positioning ─────────────────────────────────────────────────


class InsiderTransaction(BaseModel):
    insider_name: str
    title: Optional[str] = Field(None, description="Role as reported in the Form 4, not inferred")
    trade_type: str = Field(..., description="Purchase / Sale / Derivative / Gift / Unknown")
    trade_date: datetime
    filing_date: Optional[datetime] = None
    qty: Optional[float] = None
    value_usd: Optional[float] = None
    shares_owned_after: Optional[float] = None
    is_10b51: bool = False


class InstitutionalSnapshot(BaseModel):
    holders_count: Optional[int] = None
    ownership_pct: Optional[float] = None
    net_share_change_qoq: Optional[float] = None
    trend: Optional[str] = Field(None, description="accumulation / distribution / stable")


class ShortInterestSnapshot(BaseModel):
    short_pct_of_float: Optional[float] = None
    days_to_cover: Optional[float] = None
    prior_month_short_pct: Optional[float] = None


class AnalystSnapshot(BaseModel):
    consensus_rating: Optional[str] = None
    num_analysts: Optional[int] = None
    avg_price_target: Optional[float] = None
    high_target: Optional[float] = None
    low_target: Optional[float] = None
    eps_revisions_up_90d: Optional[int] = None
    eps_revisions_down_90d: Optional[int] = None
    target_increases_90d: Optional[int] = None
    target_decreases_90d: Optional[int] = None


class DarkPoolSnapshot(BaseModel):
    ats_share_pct: Optional[float] = None
    weeks_of_data: int = 0
    trend: Optional[str] = None


class EarningsEvent(BaseModel):
    date: datetime
    confirmed: bool = False
    eps_estimate: Optional[float] = None


# ── The snapshot ────────────────────────────────────────────────────────────


class TickerSnapshot(BaseModel):
    """Everything one analysis knows about a ticker, fetched once."""

    ticker: str
    company_name: Optional[str] = None
    sector: Optional[str] = None
    industry: Optional[str] = None
    is_foreign_filer: bool = False
    fx: FxNormalization
    as_of: datetime = Field(..., description="Assembly timestamp; all sections at or before this")

    quote: Optional[Quote] = None
    history: Optional[PriceHistory] = None
    fundamentals: Optional[FundamentalsTTM] = None
    multiples: Optional[ValuationMultiples] = None
    filings: List[FilingExtraction] = Field(default_factory=list)
    news: Optional[NewsBundle] = None
    insider_transactions: List[InsiderTransaction] = Field(default_factory=list)
    institutional: Optional[InstitutionalSnapshot] = None
    short_interest: Optional[ShortInterestSnapshot] = None
    analysts: Optional[AnalystSnapshot] = None
    dark_pool: Optional[DarkPoolSnapshot] = None
    next_earnings: Optional[EarningsEvent] = None

    provenance: Dict[str, Provenance] = Field(
        default_factory=dict,
        description="Keyed by section name ('quote', 'filings', 'news', ...). "
        "Every section above MUST have an entry, including missing ones.",
    )

    # ── Transitional (Phase A) ──────────────────────────────────────────────
    # The legacy shared_swarm_data payloads (raw DataFrames, filing text, etc.)
    # exactly as the agents consume them today. Excluded from serialization.
    # Phases B/C migrate consumers onto the typed sections above, then this
    # field is deleted.
    raw_bundle: Dict[str, Any] = Field(default_factory=dict, exclude=True)

    def completeness_pct(self) -> float:
        """Share of sections that arrived fresh or cached (0-100)."""
        if not self.provenance:
            return 0.0
        ok = sum(
            1 for p in self.provenance.values()
            if p.status in (SectionStatus.FRESH, SectionStatus.CACHED)
        )
        return round(100.0 * ok / len(self.provenance), 1)
