"""
Pydantic models for Manager agent outputs.

These models ensure type safety and validation for the moat scoring
and investment analysis synthesis.
"""
from pydantic import BaseModel, Field, field_validator, model_validator
from typing import List, Dict, Any, Optional, Literal


class QualityScoreBreakdown(BaseModel):
    """
    Breakdown of the quality score components.

    Quality Score formula (v3.0):
    - ROIC/WACC Spread: 25% (when available — economic value creation above cost of capital)
    - Financial Health: 25% (profitability, balance sheet, FCF conversion)
    - Earnings Quality: 20% (estimate revisions, EPS surprise history, margin stability)
    - Valuation Discipline: 15% (P/E, FCF yield, PEG vs sector)
    - Sentiment/Catalysts: 10% (news, analyst consensus)

    Fallback (when roic_wacc_spread is None):
    - Financial Health: 30%, Earnings Quality: 25%, Valuation: 25%, Sentiment: 20%

    Note: Technical strength is retained as a field for the manager's one-tier
    downgrade override in determine_rating(), but does NOT contribute to the
    quality score itself — it is a timing signal, not a quality indicator.
    """

    # v3.0 ROIC/WACC spread component (optional until data pipeline is wired)
    roic_wacc_spread: Optional[float] = Field(
        None,
        ge=0,
        le=10,
        description="ROIC minus WACC spread score from Fundamentalist (0-10)"
    )

    # Core quality components
    earnings_momentum: Optional[float] = Field(
        None,
        ge=0,
        le=10,
        description="Earnings quality score from Fundamentalist (0-10)"
    )
    valuation: Optional[float] = Field(
        None,
        ge=0,
        le=10,
        description="Valuation score from Fundamentalist (0-10)"
    )
    financial_health: float = Field(
        ...,
        ge=0,
        le=10,
        description="Financial health score from Fundamentalist (0-10)"
    )
    sentiment_catalysts: float = Field(
        ...,
        ge=0,
        le=10,
        description="Sentiment score from News Hound (0-10)"
    )

    # Retained for technical override in determine_rating() — not in formula
    technical_strength: Optional[float] = Field(
        None,
        ge=0,
        le=10,
        description="Technical/momentum score from Quant (0-10) — override only"
    )

    def weighted_average(self) -> float:
        """
        Calculate weighted quality score.

        Uses v3.0 formula when roic_wacc_spread is available; falls back to
        redistributed weights when it is not yet populated.

        Returns:
            float: Quality score (0-10)

        Raises:
            ValueError: If required components are missing
        """
        if self.earnings_momentum is None or self.valuation is None:
            raise ValueError(
                "QualityScoreBreakdown requires earnings_momentum and valuation. "
                f"Got earnings_momentum={self.earnings_momentum}, valuation={self.valuation}"
            )

        if self.roic_wacc_spread is not None:
            return (
                self.roic_wacc_spread * 0.25 +
                self.financial_health * 0.25 +
                self.earnings_momentum * 0.20 +
                self.valuation * 0.15 +
                self.sentiment_catalysts * 0.10
            )
        else:
            # Redistribute ROIC weight proportionally until data pipeline is wired
            return (
                self.financial_health * 0.30 +
                self.earnings_momentum * 0.25 +
                self.valuation * 0.25 +
                self.sentiment_catalysts * 0.20
            )


class InvestmentThesisStructured(BaseModel):
    """Structured investment thesis with clear sections for readability."""

    company_overview: str = Field(
        ...,
        min_length=20,
        description="1-2 sentence company description"
    )
    recommendation_summary: str = Field(
        ...,
        min_length=20,
        description="Recommendation + price + overall score with context"
    )
    investment_highlights: List[str] = Field(
        ...,
        min_length=2,
        max_length=4,
        description="2-4 key strengths with specific data"
    )
    valuation_signal_analysis: str = Field(
        ...,
        min_length=50,
        description="2-3 sentences explaining scores and signal convergence/divergence"
    )
    key_risks: List[str] = Field(
        ...,
        min_length=2,
        max_length=3,
        description="2-3 most significant risks with data"
    )
    entry_strategy: str = Field(
        ...,
        min_length=50,
        description="2-3 sentences on tactical guidance and investor fit"
    )


class ManagerOutput(BaseModel):
    """Final validated output from the Manager agent."""

    # Input identifiers
    ticker: str = Field(..., description="Stock ticker symbol")
    analysis_date: str = Field(..., description="Date of analysis (YYYY-MM-DD)")
    analysis_period: str = Field(..., description="Analysis period (e.g., 'TTM Q4 2024 - Q3 2025')")
    quarters: List[str] = Field(default_factory=list, description="Quarters analyzed (for TTM mode)")
    news_days_back: int = Field(..., description="News lookback period in days")

    # Backward compatibility
    fiscal_year: Optional[int] = Field(None, description="[Deprecated] Fiscal year for annual analysis")

    # Individual agent outputs (stored as dicts for serialization)
    fundamentalist_output: Dict[str, Any] = Field(
        ...,
        description="Full output from Fundamentalist agent"
    )
    news_hound_output: Dict[str, Any] = Field(
        ...,
        description="Full output from News Hound agent"
    )
    quant_output: Dict[str, Any] = Field(
        ...,
        description="Full output from Quant agent"
    )

    # Synthesis
    synthesis_narrative: str = Field(
        ...,
        min_length=100,
        description="Combined analysis narrative synthesizing all agent findings"
    )
    key_insights: List[str] = Field(
        ...,
        min_length=3,
        max_length=10,
        description="Top 3-10 investment insights"
    )
    risk_factors: List[str] = Field(
        ...,
        min_length=3,
        max_length=10,
        description="Top 3-5 risk factors"
    )
    investment_thesis: InvestmentThesisStructured = Field(
        ...,
        description="Structured investment thesis with clear sections for readability"
    )
    strategic_catalysts: Optional[List[Dict[str, str]]] = Field(
        None,
        description="3-6 forward-looking strategic developments not yet reflected in financials (labeled as speculative)"
    )

    # Quality scoring
    moat_score: float = Field(
        ...,
        ge=0,
        le=10,
        description="Final quality score (0-10)"
    )
    moat_breakdown: QualityScoreBreakdown = Field(
        ...,
        description="Breakdown of moat score by component"
    )
    confidence: float = Field(
        ...,
        ge=0,
        le=1,
        description="Confidence level in the analysis (0-1)"
    )

    # Signal divergence analysis (v2.0)
    signal_breakdown: Optional[Dict[str, Any]] = Field(
        None,
        description="Signal divergence analysis across 5 key signals"
    )

    # VGM scores (from Fundamentalist agent)
    vgm_scores: Optional[Dict[str, Any]] = Field(
        None,
        description="VGM (Value/Growth/Momentum) scores from Fundamentalist"
    )

    # Investment recommendations (v2.0)
    price_targets: Optional[Dict[str, Any]] = Field(
        None,
        description="12-month price targets (bull/base/bear scenarios with probabilities)"
    )
    structured_risks: Optional[List[Dict[str, Any]]] = Field(
        None,
        description="Structured risk breakdown with severity/likelihood/impact"
    )
    macro_exposure: Optional[Dict[str, Any]] = Field(
        None,
        description="Market state plus the macro themes with a concrete channel to this company"
    )
    upgrade_triggers: Optional[List[Dict[str, str]]] = Field(
        None,
        description="Specific metrics/thresholds that would trigger rating upgrade"
    )
    downgrade_triggers: Optional[List[Dict[str, str]]] = Field(
        None,
        description="Specific metrics/thresholds that would trigger rating downgrade"
    )
    recommendation: Optional[str] = Field(
        None,
        description="Explicit BUY/HOLD/AVOID recommendation from investment thesis"
    )
    rating: Optional[str] = Field(
        None,
        description="5-tier rating (STRONG BUY/BUY/HOLD/SELL/STRONG SELL)"
    )
    rating_score: Optional[float] = Field(
        None,
        description="Numeric rating score (0-100)"
    )
    risk_level: Optional[str] = Field(
        None,
        description="Risk level assessment (Low/Medium/High)"
    )

    # Watchlist eligibility
    is_watchlist_candidate: bool = Field(
        ...,
        description="True if moat_score >= 8 (watchlist threshold)"
    )

    # Fair value calibration metadata
    fair_value_calibration: Optional[Dict[str, Any]] = Field(
        None,
        description="Calibration layer output comparing internal model to market consensus proxy"
    )
    report_qa_flags: Optional[List[Dict[str, Any]]] = Field(
        None,
        description="QA flags for admin review — regime classification, divergence, intervention gates"
    )

    # Metadata
    tokens_used: int = Field(
        ...,
        ge=0,
        description="Total tokens used in API calls across all agents"
    )
    processing_time: float = Field(
        ...,
        ge=0,
        description="Total processing time in seconds"
    )
    agent_processing_times: Optional[Dict[str, float]] = Field(
        None,
        description="Processing time breakdown by agent"
    )
    cost_by_agent: Dict[str, float] = Field(
        default_factory=lambda: {
            "fundamentalist": 0.0,
            "news_hound": 0.0,
            "quant": 0.0,
            "manager": 0.0,
        },
        description="Cost breakdown by agent (USD)"
    )

    @field_validator("key_insights", "risk_factors")
    @classmethod
    def validate_list_items_not_empty(cls, v: List[str]) -> List[str]:
        """Ensure all list items are non-empty strings."""
        if not v:
            raise ValueError("List cannot be empty")
        for item in v:
            if not item or not item.strip():
                raise ValueError("List items cannot be empty strings")
        return v

    @model_validator(mode='after')
    def validate_moat_score_matches_breakdown(self):
        """
        Ensure moat score matches the weighted average of components.
        Auto-correct score mismatches instead of raising ValidationError.
        """
        from research_swarm.logger import logger

        expected_moat = self.moat_breakdown.weighted_average()
        diff = abs(self.moat_score - expected_moat)

        if diff > 0.5:  # Significant mismatch - auto-correct
            logger.warning(
                f"Moat score {self.moat_score} significantly differs from "
                f"breakdown weighted average {expected_moat:.2f}. Auto-correcting."
            )
            self.moat_score = round(expected_moat, 2)
        elif diff > 0.1:  # Minor floating-point difference - accept
            logger.debug(
                f"Moat score has minor difference from breakdown (likely floating point). Accepting."
            )

        return self

    @model_validator(mode='after')
    def validate_watchlist_threshold(self):
        """
        Ensure watchlist candidate flag matches the threshold.
        Auto-correct flag if it doesn't match moat score.
        """
        from research_swarm.logger import logger

        expected_watchlist = self.moat_score >= 8.0
        if self.is_watchlist_candidate != expected_watchlist:
            logger.warning(
                f"Watchlist candidate flag {self.is_watchlist_candidate} "
                f"does not match moat score {self.moat_score} "
                f"(threshold: >= 8.0). Auto-correcting to {expected_watchlist}."
            )
            self.is_watchlist_candidate = expected_watchlist

        return self


class ETFManagerOutput(BaseModel):
    """Final validated output from the Manager agent for ETF analysis."""

    # Identification
    ticker: str = Field(..., description="ETF ticker symbol")
    fund_name: str = Field(..., description="Full fund name")
    analysis_date: str = Field(..., description="Date of analysis (YYYY-MM-DD)")

    # Core recommendation
    allocation_recommendation: Literal["BUY", "HOLD", "REDUCE"] = Field(
        ..., description="Portfolio allocation recommendation"
    )

    # ETF-specific scores (0-10)
    concentration_risk: float = Field(..., ge=0, le=10, description="Holdings concentration risk (higher = more concentrated)")
    sector_momentum: float = Field(..., ge=0, le=10, description="Price and flow momentum score")
    macro_alignment_score: float = Field(..., ge=0, le=10, description="How well current macro conditions favor this sector")
    sentiment_score: float = Field(..., ge=0, le=10, description="News and analyst sentiment score")

    # Holdings and composition
    top_holdings_summary: List[str] = Field(..., min_length=1, description="Top 5 holdings with weight percentages")
    sector_breakdown: Dict[str, float] = Field(..., description="Sector allocation percentages")

    # Fund fundamentals
    expense_ratio: float = Field(..., ge=0, description="Annual expense ratio as a percentage")
    aum_billions: float = Field(..., ge=0, description="Assets under management in billions USD")

    # Qualitative analysis
    pros: List[str] = Field(..., min_length=1, description="Investment positives")
    cons: List[str] = Field(..., min_length=1, description="Investment risks and negatives")
    investment_thesis: str = Field(..., min_length=50, description="Portfolio allocation recommendation narrative")

    # Watchlist
    watchlist_candidate: bool = Field(..., description="True if macro_alignment_score >= 7.5")

    # Metadata
    tokens_used: int = Field(default=0, ge=0, description="Total tokens used")
    processing_time: float = Field(default=0.0, ge=0, description="Processing time in seconds")
    cost_by_agent: Dict[str, float] = Field(
        default_factory=lambda: {"fundamentalist": 0.0, "news_hound": 0.0, "quant": 0.0, "manager": 0.0},
        description="Cost per agent in USD"
    )

    @field_validator("pros", "cons")
    @classmethod
    def validate_list_items_not_empty(cls, v: List[str]) -> List[str]:
        """Ensure all list items are non-empty strings."""
        if not v:
            raise ValueError("List cannot be empty")
        for item in v:
            if not item or not item.strip():
                raise ValueError("List items cannot be empty strings")
        return v

    @model_validator(mode='after')
    def validate_watchlist_threshold(self):
        """
        Ensure watchlist candidate flag matches the threshold.
        Auto-correct flag if it doesn't match macro alignment score.
        """
        from research_swarm.logger import logger

        expected = self.macro_alignment_score >= 7.5
        if self.watchlist_candidate != expected:
            logger.warning(
                f"watchlist_candidate {self.watchlist_candidate} does not match "
                f"macro_alignment_score {self.macro_alignment_score} (threshold >= 7.5). "
                f"Auto-correcting to {expected}."
            )
            self.watchlist_candidate = expected
        return self
