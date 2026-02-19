"""
Pydantic models for Fundamentalist agent outputs.

These models ensure type safety and validation for all extracted data.
"""
from pydantic import BaseModel, Field, field_validator, model_validator
from typing import List, Optional, Dict, Any
from research_swarm.logger import logger


# Stub for backward compatibility with Quant agent
# Supply chain analysis was removed from Fundamentalist agent
class SupplyChainOutput(BaseModel):
    """Stub model for backward compatibility. Supply chain analysis removed from Fundamentalist."""
    pass


class FinancialMetricsOutput(BaseModel):
    """Financial metrics extracted from 10-K."""

    # Revenue metrics
    revenue: Optional[float] = Field(None, description="Total revenue in millions USD")
    revenue_growth_yoy: Optional[float] = Field(None, description="Year-over-year revenue growth rate (%)")

    # Profitability metrics
    gross_margin: Optional[float] = Field(None, description="Gross profit margin (%)")
    operating_margin: Optional[float] = Field(None, description="Operating profit margin (%)")
    net_margin: Optional[float] = Field(None, description="Net profit margin (%)")

    # Debt metrics
    debt_to_equity: Optional[float] = Field(None, description="Debt to equity ratio")
    current_ratio: Optional[float] = Field(None, description="Current assets / current liabilities")
    interest_coverage: Optional[float] = Field(None, description="EBIT / interest expense")

    # Investment metrics
    rd_expense: Optional[float] = Field(None, description="R&D expense in millions USD")
    rd_as_pct_revenue: Optional[float] = Field(None, description="R&D as % of revenue")
    capex: Optional[float] = Field(None, description="Capital expenditures in millions USD")
    capex_as_pct_revenue: Optional[float] = Field(None, description="CapEx as % of revenue")

    # Cash flow metrics
    free_cash_flow: Optional[float] = Field(None, description="Free cash flow in millions USD")
    cash_and_equivalents: Optional[float] = Field(None, description="Cash and cash equivalents in millions USD")

    @field_validator("revenue", "rd_expense", "capex", "free_cash_flow", "cash_and_equivalents", mode="before")
    @classmethod
    def validate_positive(cls, v):
        """Ensure monetary values are positive or None."""
        if v is not None and v < 0:
            return None
        return v


class BusinessModelOutput(BaseModel):
    """Business model and revenue stream analysis extracted from 10-K."""

    # Revenue streams
    revenue_streams: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="List of revenue streams with name, percentage, and description"
    )

    # Business segments
    business_segments: Dict[str, Optional[float]] = Field(
        default_factory=dict,
        description="Revenue by business segment (% or millions USD). None if not specified."
    )

    # Revenue concentration
    revenue_concentration: Optional[str] = Field(
        None,
        description="Assessment of revenue concentration risk across products/services"
    )

    # Competitive moats
    moat_characteristics: List[str] = Field(
        default_factory=list,
        description="List of competitive moats (network effects, switching costs, brand, scale, IP, etc.)"
    )

    @field_validator("business_segments", mode="before")
    @classmethod
    def clean_business_segments(cls, v):
        """Clean business segments dict - remove non-numeric values."""
        if not isinstance(v, dict):
            return {}

        cleaned = {}
        for key, value in v.items():
            if value is None:
                cleaned[key] = None
            elif isinstance(value, (int, float)):
                cleaned[key] = float(value) if value >= 0 else None
            # Skip string values - LLM sometimes returns descriptions instead of numbers
        return cleaned


class QuarterlyMetrics(BaseModel):
    """Financial metrics for a single quarter."""
    quarter: str = Field(..., description="Quarter label (e.g., 'Q3_2025')")
    period_end_date: Optional[str] = Field(None, description="Fiscal period end date")

    # Core metrics (in millions USD)
    revenue: Optional[float] = Field(None, description="Quarterly revenue")
    gross_profit: Optional[float] = Field(None, description="Quarterly gross profit")
    operating_income: Optional[float] = Field(None, description="Quarterly operating income")
    net_income: Optional[float] = Field(None, description="Quarterly net income")

    # Cash flow
    operating_cash_flow: Optional[float] = Field(None, description="Operating cash flow")
    free_cash_flow: Optional[float] = Field(None, description="Free cash flow")


class TTMMetrics(BaseModel):
    """Trailing Twelve Month aggregated metrics."""
    quarters_included: List[str] = Field(..., description="Quarters in TTM calculation")

    # Aggregated TTM figures (in millions USD)
    ttm_revenue: Optional[float] = Field(None, description="TTM total revenue")
    ttm_gross_profit: Optional[float] = Field(None, description="TTM gross profit")
    ttm_operating_income: Optional[float] = Field(None, description="TTM operating income")
    ttm_net_income: Optional[float] = Field(None, description="TTM net income")
    ttm_free_cash_flow: Optional[float] = Field(None, description="TTM free cash flow")

    # Calculated margins (percentages)
    gross_margin: Optional[float] = Field(None, description="Gross margin %")
    operating_margin: Optional[float] = Field(None, description="Operating margin %")
    net_margin: Optional[float] = Field(None, description="Net margin %")

    # Growth (vs prior TTM if calculable)
    revenue_growth_yoy: Optional[float] = Field(None, description="YoY revenue growth %")


class QuarterlyTrends(BaseModel):
    """Quarter-over-quarter trend analysis."""
    # Revenue trend (chronological order, oldest to newest)
    revenue_trend: List[Optional[float]] = Field(default_factory=list)
    margin_trend: List[Optional[float]] = Field(default_factory=list)

    # Calculated trends
    trend_direction: str = Field("stable", description="'improving', 'stable', or 'declining'")
    sequential_growth_rates: List[Optional[float]] = Field(default_factory=list, description="QoQ growth rates")

    # Momentum indicator
    momentum_score: float = Field(5.0, ge=0, le=10, description="Trend momentum 0-10")


class TTMAnalysisOutput(BaseModel):
    """Extended output for TTM analysis mode."""
    quarterly_metrics: List[QuarterlyMetrics] = Field(default_factory=list)
    ttm_metrics: TTMMetrics
    quarterly_trends: QuarterlyTrends
    data_quality: Dict[str, str] = Field(default_factory=dict)


class ScoreBreakdown(BaseModel):
    """Breakdown of the financial health score."""

    profitability: float = Field(..., ge=0, le=10, description="Profitability score (0-10)")
    growth: float = Field(..., ge=0, le=10, description="Growth score (0-10)")
    balance_sheet: float = Field(..., ge=0, le=10, description="Balance sheet strength score (0-10)")
    cash_flow: float = Field(..., ge=0, le=10, description="Cash flow score (0-10)")

    def weighted_average(self) -> float:
        """
        Calculate weighted average score.

        Weights: profitability (30%), growth (25%), balance_sheet (25%), cash_flow (20%)
        """
        return (
            self.profitability * 0.30 +
            self.growth * 0.25 +
            self.balance_sheet * 0.25 +
            self.cash_flow * 0.20
        )


class BusinessModelScoreBreakdown(BaseModel):
    """Breakdown of the business model moat score."""

    revenue_diversification: float = Field(..., ge=0, le=10, description="Revenue stream diversification score (0-10)")
    competitive_moat: float = Field(..., ge=0, le=10, description="Competitive advantages and moat strength score (0-10)")

    def weighted_average(self) -> float:
        """
        Calculate weighted average score.

        Weights: revenue_diversification (50%), competitive_moat (50%)
        """
        return (
            self.revenue_diversification * 0.50 +
            self.competitive_moat * 0.50
        )


class EnhancedMoatBreakdown(BaseModel):
    """Detailed breakdown of competitive moats across 8 categories."""

    network_effects: float = Field(0.0, ge=0, le=10, description="Network effects strength (0-10)")
    switching_costs: float = Field(0.0, ge=0, le=10, description="Customer switching costs (0-10)")
    brand_power: float = Field(0.0, ge=0, le=10, description="Brand strength and pricing power (0-10)")
    cost_advantages: float = Field(0.0, ge=0, le=10, description="Structural cost advantages (0-10)")
    scale_economies: float = Field(0.0, ge=0, le=10, description="Economies of scale (0-10)")
    intangible_assets: float = Field(0.0, ge=0, le=10, description="Patents, IP, data assets (0-10)")
    regulatory_barriers: float = Field(0.0, ge=0, le=10, description="Regulatory or licensing moats (0-10)")
    distribution_advantages: float = Field(0.0, ge=0, le=10, description="Distribution network or channel control (0-10)")

    # Overall assessment
    moat_width: str = Field("narrow", description="Wide/Moderate/Narrow/None")
    moat_durability: str = Field("medium", description="High/Medium/Low")

    def composite_score(self) -> float:
        """Calculate weighted composite moat score."""
        scores = [
            self.network_effects, self.switching_costs, self.brand_power,
            self.cost_advantages, self.scale_economies, self.intangible_assets,
            self.regulatory_barriers, self.distribution_advantages
        ]
        # Average of non-zero scores (some moats may not apply)
        active_scores = [s for s in scores if s > 0]
        return sum(active_scores) / len(active_scores) if active_scores else 0.0


class ValuationMetrics(BaseModel):
    """Valuation metrics and multiples."""

    # Current market data
    current_price: Optional[float] = Field(None, description="Current stock price")
    market_cap_millions: Optional[float] = Field(None, description="Market capitalization in millions USD")
    enterprise_value_millions: Optional[float] = Field(None, description="Enterprise value in millions USD")

    # Core multiples
    pe_ratio: Optional[float] = Field(None, description="Price-to-Earnings ratio (TTM)")
    forward_pe: Optional[float] = Field(None, description="Forward P/E ratio")
    peg_ratio: Optional[float] = Field(None, description="Price/Earnings-to-Growth ratio")
    pb_ratio: Optional[float] = Field(None, description="Price-to-Book ratio")
    ps_ratio: Optional[float] = Field(None, description="Price-to-Sales ratio")
    ev_ebitda: Optional[float] = Field(None, description="EV/EBITDA multiple")

    # Peer comparison
    sector_avg_pe: Optional[float] = Field(None, description="Sector average P/E")
    sector_avg_ev_ebitda: Optional[float] = Field(None, description="Sector average EV/EBITDA")
    pe_premium_discount: Optional[float] = Field(None, description="% premium/discount to sector P/E")

    # Dividend (if applicable)
    dividend_yield: Optional[float] = Field(None, description="Dividend yield %")
    payout_ratio: Optional[float] = Field(None, description="Dividend payout ratio %")

    # Assessment
    valuation_category: str = Field("fair", description="Deep Discount/Discount/Fair/Premium/Extreme Premium")


class PeerComparison(BaseModel):
    """Peer comparison metrics."""

    sector: str = Field(..., description="Sector classification")
    industry: str = Field(..., description="Industry classification")

    # Peer companies
    peers: List[str] = Field(default_factory=list, description="List of peer tickers")

    # Comparative metrics (company vs peer average)
    revenue_growth_rank: Optional[int] = Field(None, description="Rank among peers (1=best)")
    profit_margin_rank: Optional[int] = Field(None, description="Rank among peers")
    roic_rank: Optional[int] = Field(None, description="Rank among peers")
    valuation_rank: Optional[int] = Field(None, description="Rank among peers (1=cheapest)")

    # Relative strength
    competitive_position: str = Field("challenger", description="Market Leader/Strong #2/Challenger/Laggard")
    market_share_estimate: Optional[float] = Field(None, description="Estimated market share %")

    # NEW v2.0: Enhanced competitive analysis
    market_share_rank: Optional[int] = Field(None, description="Market share rank (1=leader)")
    top_competitor: Optional[str] = Field(None, description="Main competitor ticker symbol")
    vs_top_competitor: Optional[Dict[str, Any]] = Field(
        None,
        description="Comparison metrics vs top competitor (revenue, margins, growth, etc.)"
    )
    competitive_intensity: str = Field(
        "Moderate",
        description="Competitive intensity: Low/Moderate/High/Extreme"
    )
    pricing_power_evidence: Optional[List[str]] = Field(
        None,
        description="Evidence of pricing power (e.g., margin expansion, price increases)"
    )
    moat_direction: str = Field(
        "Stable",
        description="Moat direction: Widening/Stable/Narrowing"
    )
    key_threats: Optional[List[str]] = Field(
        None,
        description="Top 3 competitive threats"
    )


class VGMScoreBreakdown(BaseModel):
    """VGM (Value/Growth/Momentum) composite scoring."""

    # Value Score (0-10)
    value_score: float = Field(..., ge=0, le=10, description="Value score based on multiples")
    value_grade: str = Field(..., description="A/B/C/D/F grade")
    value_rationale: str = Field(..., description="Why this value score")

    # Growth Score (0-10)
    growth_score: float = Field(..., ge=0, le=10, description="Growth score based on trajectory")
    growth_grade: str = Field(..., description="A/B/C/D/F grade")
    growth_rationale: str = Field(..., description="Why this growth score")

    # Momentum Score (0-10)
    momentum_score: float = Field(..., ge=0, le=10, description="Momentum score based on trends")
    momentum_grade: str = Field(..., description="A/B/C/D/F grade")
    momentum_rationale: str = Field(..., description="Why this momentum score")

    # Composite VGM Score
    vgm_composite: float = Field(..., ge=0, le=10, description="Weighted VGM composite score")
    vgm_grade: str = Field(..., description="Overall A/B/C/D/F grade")

    # Investment style
    best_fit_style: str = Field(..., description="Value/Growth/Momentum/Quality/Blend/Income")

    def calculate_composite(self, value_weight=0.33, growth_weight=0.33, momentum_weight=0.34) -> float:
        """Calculate weighted VGM composite."""
        return (
            self.value_score * value_weight +
            self.growth_score * growth_weight +
            self.momentum_score * momentum_weight
        )


class PriceTargetScenarios(BaseModel):
    """Price target scenarios with bull/base/bear cases and intrinsic value range."""

    # ── Intrinsic Value Range (uncertainty-aware) ──────────────────────────────
    fair_value_low: float = Field(..., description="Lower bound of intrinsic value range")
    fair_value_mid: float = Field(..., description="Midpoint of intrinsic value range (blended fair value)")
    fair_value_high: float = Field(..., description="Upper bound of intrinsic value range")
    fair_value_zone_label: str = Field("Intrinsic Value Zone", description="Label for the fair value band")

    # ── Confidence ─────────────────────────────────────────────────────────────
    confidence_score: int = Field(
        50, ge=5, le=100,
        description="Valuation reliability score 0–100 (not bullish/bearish sentiment)"
    )
    confidence: str = Field(
        "Moderate",
        description="High (≥75) / Moderate (≥45) / Low (<45)"
    )
    uncertainty_drivers: List[str] = Field(
        default_factory=list,
        description="3–6 bullets explaining key sources of valuation uncertainty"
    )

    # ── Price vs. Zone ─────────────────────────────────────────────────────────
    premium_vs_mid: Optional[float] = Field(
        None,
        description="(price − mid) / mid — positive = trading above intrinsic midpoint"
    )
    deviation_vs_price: Optional[float] = Field(
        None,
        description="(price − mid) / price — price-relative deviation"
    )
    price_vs_zone: str = Field(
        "Within Intrinsic Value Band",
        description="Within Intrinsic Value Band / Price Above Intrinsic Value Band / Price Below Intrinsic Value Band"
    )

    # ── Scenario Targets (backward-compatible) ────────────────────────────────
    base_target: float = Field(..., description="Base case 12-month price target")
    base_assumptions: str = Field(..., description="Key assumptions for base case")
    base_probability: float = Field(0.5, ge=0, le=1, description="Probability of base case")

    bull_target: float = Field(..., description="Bull case 12-month price target")
    bull_assumptions: str = Field(..., description="Key assumptions for bull case")
    bull_probability: float = Field(0.25, ge=0, le=1, description="Probability of bull case")

    bear_target: float = Field(..., description="Bear case 12-month price target")
    bear_assumptions: str = Field(..., description="Key assumptions for bear case")
    bear_probability: float = Field(0.25, ge=0, le=1, description="Probability of bear case")

    # ── Valuation methodology ──────────────────────────────────────────────────
    methodology: str = Field(..., description="DCF/P/E Multiple/Sum-of-parts/Comparable")

    def expected_value(self) -> float:
        """Calculate probability-weighted expected value."""
        return (
            self.base_target * self.base_probability +
            self.bull_target * self.bull_probability +
            self.bear_target * self.bear_probability
        )


class FilingExtraction(BaseModel):
    """Structured data extracted from a SEC filing via LLM."""

    business_description: Optional[str] = Field(None, description="2-3 sentence summary of what the company does")
    risk_factors: List[str] = Field(default_factory=list, description="Top 5 material risk factors")
    financial_metrics: Dict[str, Any] = Field(default_factory=dict, description="Key financial figures extracted from filing")
    management_outlook: Optional[str] = Field(None, description="Management's forward guidance summary")
    competitive_position: Optional[str] = Field(None, description="Market position and key advantages")
    growth_drivers: List[str] = Field(default_factory=list, description="Top 3-5 growth catalysts")
    filing_type: str = Field("10-K", description="Source filing type: 10-K, 20-F, 10-Q, or 6-K")


class DCFInputs(BaseModel):
    """Inputs for DCF valuation model, extracted from SEC filings."""

    fcf_history: List[float] = Field(default_factory=list, description="3-5 years of FCF in millions USD")
    revenue_growth_rate: Optional[float] = Field(None, description="Recent YoY revenue growth as percentage")
    operating_margin_trend: Optional[str] = Field(None, description="expanding, stable, or contracting")
    operating_margin_history: Optional[List[float]] = Field(None, description="Historical operating margins (%) for stability factor")
    capex_as_pct_revenue: Optional[float] = Field(None, description="CapEx as percentage of revenue")
    effective_tax_rate: Optional[float] = Field(None, description="Effective tax rate as percentage")
    total_debt: Optional[float] = Field(None, description="Total debt in millions USD")
    cash_and_equivalents: Optional[float] = Field(None, description="Cash and equivalents in millions USD")
    shares_outstanding: Optional[float] = Field(None, description="Shares outstanding in millions")
    market_cap_millions: Optional[float] = Field(None, description="Market cap in millions USD (for accurate WACC equity weight)")
    beta: Optional[float] = Field(None, description="Stock beta (from yfinance)")
    risk_free_rate: float = Field(4.5, description="Risk-free rate (10Y Treasury)")
    equity_risk_premium: float = Field(5.5, description="Equity risk premium")


class FundamentalistOutput(BaseModel):
    """Final validated output from the Fundamentalist agent."""

    # Input identifiers
    ticker: str = Field(..., description="Stock ticker symbol")

    # Analysis period - supports both TTM and annual modes
    analysis_period: str = Field(..., description="Analysis period (e.g., 'TTM Q4 2024 - Q3 2025' or 'FY 2024')")
    quarters_analyzed: List[str] = Field(default_factory=list, description="Quarters analyzed (empty for annual mode)")
    analysis_mode: str = Field("ttm", description="'ttm' or 'annual'")

    # Filing dates
    filing_date: Optional[str] = Field(None, description="Most recent filing date")
    filing_dates: Dict[str, str] = Field(default_factory=dict, description="Filing dates by quarter")

    # Backward compatibility - deprecated
    fiscal_year: Optional[int] = Field(None, description="[Deprecated] Fiscal year analyzed (for annual mode)")

    # TTM-specific data
    quarterly_metrics: List[QuarterlyMetrics] = Field(default_factory=list)
    ttm_metrics: Optional[TTMMetrics] = None
    quarterly_trends: Optional[QuarterlyTrends] = None
    data_quality: Dict[str, str] = Field(default_factory=dict, description="Quarter -> '10-Q' | '10-K' | 'missing'")

    # Extracted data - preserved for backward compatibility
    financial_metrics: FinancialMetricsOutput = Field(..., description="Extracted financial metrics")
    business_model_data: BusinessModelOutput = Field(..., description="Business model and revenue stream analysis")

    # Analysis
    financial_analysis: str = Field(..., description="Qualitative financial analysis")

    # Scoring
    financial_health_score: float = Field(..., ge=0, le=10, description="Overall financial health score (0-10)")
    score_breakdown: ScoreBreakdown = Field(..., description="Score breakdown by component")
    business_model_moat_score: float = Field(..., ge=0, le=10, description="Business model and revenue moat score (0-10)")
    business_model_score_breakdown: BusinessModelScoreBreakdown = Field(..., description="Business model score breakdown")
    confidence: float = Field(..., ge=0, le=1, description="Confidence level in the analysis (0-1)")

    # NEW: VGM and Valuation Analysis
    vgm_scores: Optional[VGMScoreBreakdown] = Field(None, description="VGM (Value/Growth/Momentum) scores")
    valuation_metrics: Optional[ValuationMetrics] = Field(None, description="Valuation metrics and multiples")
    peer_comparison: Optional[PeerComparison] = Field(None, description="Peer comparison analysis")
    enhanced_moat: Optional[EnhancedMoatBreakdown] = Field(None, description="Detailed moat category breakdown")
    price_targets: Optional[PriceTargetScenarios] = Field(None, description="Price target scenarios")

    # Earnings momentum data (from NewsHound models, reused)
    earnings_estimates: Optional[Any] = Field(None, description="Earnings estimate revisions (EarningsEstimateRevision)")
    analyst_consensus: Optional[Any] = Field(None, description="Analyst ratings and price targets (AnalystConsensus)")

    # NEW v2.0: Earnings momentum scoring
    earnings_momentum_score: float = Field(
        0.0,
        ge=0,
        le=10,
        description="Earnings momentum score from EarningsCalculator (0-10)"
    )
    earnings_momentum_breakdown: Optional[Dict[str, Any]] = Field(
        None,
        description="Breakdown of earnings momentum components (revisions, surprises, sentiment)"
    )
    valuation_score: float = Field(
        5.0,
        ge=0,
        le=10,
        description="Valuation score based on multiples vs sector (0-10)"
    )

    # Metadata
    tokens_used: int = Field(..., description="Total tokens used in API calls")
    processing_time: float = Field(..., description="Total processing time in seconds")

    @model_validator(mode='after')
    def validate_score_matches_breakdown(self):
        """
        Ensure the overall scores match the weighted average of components.
        Auto-correct score mismatches instead of raising ValidationError.
        """
        # Validate financial health score
        expected_health = self.score_breakdown.weighted_average()
        diff_health = abs(self.financial_health_score - expected_health)

        if diff_health > 0.5:  # Significant mismatch - auto-correct
            logger.warning(
                f"Financial health score {self.financial_health_score} significantly differs from "
                f"breakdown weighted average {expected_health:.2f}. Auto-correcting."
            )
            self.financial_health_score = round(expected_health, 2)
        elif diff_health > 0.1:  # Minor floating-point difference - accept
            logger.debug(
                f"Financial health score has minor difference from breakdown (likely floating point). Accepting."
            )

        # Validate business model moat score
        expected_moat = self.business_model_score_breakdown.weighted_average()
        diff_moat = abs(self.business_model_moat_score - expected_moat)

        if diff_moat > 0.5:  # Significant mismatch - auto-correct
            logger.warning(
                f"Business model moat score {self.business_model_moat_score} significantly differs from "
                f"breakdown weighted average {expected_moat:.2f}. Auto-correcting."
            )
            self.business_model_moat_score = round(expected_moat, 2)
        elif diff_moat > 0.1:  # Minor floating-point difference - accept
            logger.debug(
                f"Business model moat score has minor difference from breakdown (likely floating point). Accepting."
            )

        return self
