"""AnalysisReport — the single output contract for one analysis.

This object is produced once at analysis time and then only ever read:
it IS the API response, IS the persisted JSON, and IS the source for the
generated frontend types. Design rules:

1. Every derived value (rating, targets, sizing) is computed exactly once,
   here, by `decide()`. Readers — web, PDF, portfolio engine, weekly
   signals, backtests — never re-derive.
2. LLM output arrives as structured fields (tool use), never as prose that
   gets re-parsed. Prose fields are terminal: rendered, not read.
3. Nothing is fabricated to fill a gap. A missing value is None plus a
   provenance/QA flag; the UI renders an honest empty state.
4. Percentages are in points everywhere (2.5 means 2.5%). No field in this
   contract is a 0-1 fraction; that convention mismatch caused real bugs.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional

from pydantic import BaseModel, Field


# ── Shared enums ────────────────────────────────────────────────────────────


class Rating(str, Enum):
    STRONG_BUY = "STRONG BUY"
    BUY = "BUY"
    HOLD = "HOLD"
    SELL = "SELL"
    STRONG_SELL = "STRONG SELL"


class Direction(str, Enum):
    BULLISH = "bullish"
    NEUTRAL = "neutral"
    BEARISH = "bearish"


class RiskLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


# ── Scores (deterministic, from compute stage) ──────────────────────────────


class ScoreComponent(BaseModel):
    """One weighted component of the quality score. Weights are recorded so
    the formula is auditable from the report itself."""

    name: str
    score: float = Field(..., ge=0, le=10)
    weight: float = Field(..., ge=0, le=1)
    basis: Optional[str] = Field(None, description="One line: what drove this score")


class Scores(BaseModel):
    quality_score: float = Field(..., ge=0, le=10, description="The headline 0-10 score")
    components: List[ScoreComponent] = Field(
        ..., description="Weighted components; weights sum to 1.0"
    )
    technical_score: Optional[float] = Field(
        None, ge=0, le=10,
        description="Tracked separately; gates the rating but is not in quality_score",
    )
    confidence: float = Field(..., ge=0, le=1, description="Analysis confidence, data-driven")


# ── Signals (deterministic, from compute stage) ─────────────────────────────


class Signal(BaseModel):
    """One of the positioning/momentum signals (sentiment, revisions,
    insider, institutional, short interest, dark pool, technicals)."""

    name: str
    direction: Direction
    score: Optional[float] = Field(None, ge=0, le=10)
    evidence: Optional[str] = Field(None, description="One factual line, e.g. '4 buys / 1 sale, net +$2.1M'")
    has_data: bool = True


class Divergence(BaseModel):
    """Cross-signal divergence read (e.g. news bearish vs institutions buying)."""

    detected: bool = False
    kind: Optional[str] = Field(None, description="e.g. 'sentiment-vs-flows', 'fundamentals-vs-price'")
    score: Optional[float] = Field(None, ge=0, le=10)
    summary: Optional[str] = None


# ── Valuation & targets (deterministic where possible) ──────────────────────


class TargetCase(BaseModel):
    target: float
    probability: float = Field(..., ge=0, le=1)
    assumptions: str


class PriceTargets(BaseModel):
    current_price: float
    fair_value_low: Optional[float] = None
    fair_value_mid: Optional[float] = None
    fair_value_high: Optional[float] = None
    bull: Optional[TargetCase] = None
    base: Optional[TargetCase] = None
    bear: Optional[TargetCase] = None
    probability_weighted_ev: Optional[float] = Field(
        None, description="Computed here once; the UI must not recompute it"
    )
    methodology: str = Field(..., description="DCF / multiples / comparables / heuristic")
    confidence_score: int = Field(..., ge=0, le=100)
    is_heuristic: bool = Field(
        False,
        description="True when targets were derived from a scoring heuristic rather "
        "than a valuation model. The UI must label these differently.",
    )

    # ── DVRG divergence-weighted target provenance ──────────────────────────
    persistence_probability: Optional[float] = Field(
        None, ge=0, le=1,
        description="Probability the premium/consensus regime persists over 12 months",
    )
    reversion_anchor: Optional[float] = Field(
        None, description="Intrinsic fair value midpoint (multiple-reversion anchor)"
    )
    persistence_anchor: Optional[float] = Field(
        None, description="Analyst consensus mean target (premium-persistence anchor)"
    )
    basis_note: Optional[str] = Field(
        None, description="One-line explanation of how the base target was derived"
    )


# ── Narrative (LLM structured output — terminal, never re-parsed) ───────────


class Thesis(BaseModel):
    headline: str = Field(..., description="One sentence: the call and the core reason")
    narrative: str = Field(..., description="The full synthesis narrative")
    key_insights: List[str] = Field(default_factory=list, description="3-6 bullets")
    bull_case: str
    bear_case: str
    what_would_change_our_mind: List[str] = Field(
        default_factory=list, description="Concrete falsifiers for the thesis"
    )


class Risk(BaseModel):
    description: str
    severity: RiskLevel
    likelihood: RiskLevel
    mitigation: Optional[str] = None


class Catalyst(BaseModel):
    description: str
    expected_date: Optional[str] = Field(None, description="ISO date or textual window, e.g. '2026-Q4'")
    direction: Direction = Direction.NEUTRAL


# ── Decision (computed once by decide(), read by everyone) ──────────────────


class TrancheStage(BaseModel):
    stage: int
    allocation_pct: float = Field(..., description="Percentage points of portfolio")
    trigger: str


class Decision(BaseModel):
    """The single authoritative 'what to do'. Every consumer reads this;
    none re-derives it."""

    rating: Rating
    rating_basis: str = Field(
        ..., description="One line: score, thresholds, and any overrides applied "
        "(e.g. 'quality 7.4 → BUY; technical 3.8 gated to HOLD')"
    )
    risk_level: RiskLevel
    conviction: str = Field(..., description="High / Medium / Low, rule-derived")
    is_watchlist_candidate: bool

    entry_zone_low: Optional[float] = None
    entry_zone_high: Optional[float] = None
    stop_loss: Optional[float] = None
    starter_allocation_pct: Optional[float] = Field(
        None, description="Percentage points (2.5 means 2.5% of portfolio)"
    )
    max_allocation_pct: Optional[float] = None
    tranche_plan: List[TrancheStage] = Field(default_factory=list)

    upgrade_triggers: List[str] = Field(default_factory=list)
    downgrade_triggers: List[str] = Field(default_factory=list)
    thesis_break_conditions: List[str] = Field(default_factory=list)


# ── Run metadata ────────────────────────────────────────────────────────────


class QAFlag(BaseModel):
    code: str = Field(..., description="Stable machine code, e.g. 'targets_heuristic', 'news_missing'")
    message: str


class RunMeta(BaseModel):
    analysis_id: str
    schema_version: int = 1
    created_at: datetime
    models_used: Dict[str, str] = Field(
        default_factory=dict, description="stage → model id, e.g. {'synthesis': 'claude-sonnet-5'}"
    )
    tokens_total: int = Field(0, description="Total tokens (agents track a single sum today)")
    tokens_input: int = 0
    tokens_output: int = 0
    tokens_cache_read: int = 0
    cost_usd: float = 0.0
    duration_seconds: float = 0.0
    data_completeness_pct: float = Field(0.0, description="From TickerSnapshot.completeness_pct()")
    qa_flags: List[QAFlag] = Field(default_factory=list)


# ── The report ──────────────────────────────────────────────────────────────


class MacroTheme(BaseModel):
    """A live macro/geopolitical theme with a concrete channel to this company.

    Sourced from the shared, company-neutral macro brief and filtered by the
    deterministic exposure join, so the reader can see both what is happening
    in the world and why it reaches this particular name."""

    name: str
    summary: Optional[str] = None
    status: str = Field(..., description="escalating | stable | de-escalating")
    direction: str = Field(..., description="headwind | tailwind | mixed")
    transmission: str = Field(..., description="Mechanism by which it reaches company results")
    why_relevant: str = Field(..., description="The concrete link to this company")
    relevance: str = Field(..., description="high | moderate")
    confidence: str = Field(..., description="high | medium | low")
    evidence: Optional[str] = None


class MacroContext(BaseModel):
    """Market state plus the themes that apply to this company."""

    regime: Optional[str] = Field(None, description="risk-on | risk-off | mixed")
    regime_rationale: Optional[str] = None
    backdrop: Optional[str] = None
    themes: List[MacroTheme] = Field(default_factory=list)
    themes_considered: int = Field(
        0, description="How many themes were screened before exposure filtering"
    )
    market_return_1m: Optional[float] = Field(None, description="S&P 500 1-month return %")
    market_return_3m: Optional[float] = Field(None, description="S&P 500 3-month return %")
    vix_level: Optional[float] = None
    yield_curve_slope: Optional[float] = Field(None, description="10Y minus 3M, in pp")
    sector_leaders: List[str] = Field(default_factory=list)
    sector_laggards: List[str] = Field(default_factory=list)
    as_of: Optional[str] = None


class AnalysisReport(BaseModel):
    """The complete result of one ticker analysis. Persisted verbatim;
    served verbatim; rendered without re-derivation."""

    ticker: str
    company_name: Optional[str] = None
    sector: Optional[str] = None
    industry: Optional[str] = None
    as_of: datetime

    scores: Scores
    signals: List[Signal] = Field(default_factory=list)
    divergence: Optional[Divergence] = None
    targets: Optional[PriceTargets] = None
    thesis: Thesis
    risks: List[Risk] = Field(default_factory=list)
    catalysts: List[Catalyst] = Field(default_factory=list)
    decision: Decision
    macro: Optional[MacroContext] = None
    meta: RunMeta

    previous: Optional["PreviousAnalysisDelta"] = None


class PreviousAnalysisDelta(BaseModel):
    """What changed since this user's last analysis of the same ticker.
    Comparable because both sides are persisted AnalysisReports."""

    prior_analysis_id: str
    prior_date: datetime
    days_since: int
    rating_change: Optional[str] = Field(None, description="e.g. 'HOLD → BUY'; None if unchanged")
    quality_score_change: Optional[float] = None
    price_change_pct: Optional[float] = None
    new_risks: List[str] = Field(default_factory=list)
    resolved_risks: List[str] = Field(default_factory=list)
    summary: Optional[str] = None


AnalysisReport.model_rebuild()
