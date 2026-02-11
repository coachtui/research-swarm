"""
Pydantic models for Manager agent outputs.

These models ensure type safety and validation for the moat scoring
and investment analysis synthesis.
"""
from pydantic import BaseModel, Field, field_validator, model_validator
from typing import List, Dict, Any, Optional


class MoatScoreBreakdown(BaseModel):
    """
    Breakdown of the moat score components.

    NEW Moat score formula (v2.0):
    - Earnings Momentum: 25%
    - Financial Health: 25%
    - Valuation: 20%
    - Technical/Momentum: 15%
    - Sentiment: 15%

    LEGACY Moat score formula (v1.0 - deprecated):
    - Financial Health: 25%
    - Business Model Moat: 25%
    - Sentiment/Catalysts: 15%
    - Technical Strength: 15%
    - Supply Chain Position: 20%
    """

    # New v2.0 components (Optional for backward compatibility)
    earnings_momentum: Optional[float] = Field(
        None,
        ge=0,
        le=10,
        description="Earnings momentum score from Fundamentalist (0-10)"
    )
    valuation: Optional[float] = Field(
        None,
        ge=0,
        le=10,
        description="Valuation score from Fundamentalist (0-10)"
    )

    # Shared components (present in both v1.0 and v2.0)
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
    technical_strength: float = Field(
        ...,
        ge=0,
        le=10,
        description="Technical/momentum score from Quant (0-10)"
    )

    # Legacy v1.0 components (Optional for backward compatibility)
    business_model_moat: Optional[float] = Field(
        None,
        ge=0,
        le=10,
        description="[v1.0 Legacy] Business model and revenue moat score from Fundamentalist (0-10)"
    )
    supply_chain_position: Optional[float] = Field(
        None,
        ge=0,
        le=10,
        description="[v1.0 Legacy] Supply chain score from Quant (0-10)"
    )

    def weighted_average(self) -> float:
        """
        Calculate weighted average moat score.

        Uses v2.0 formula if new components present, else falls back to v1.0 formula.

        v2.0 Weights:
        - Earnings Momentum: 25%
        - Financial Health: 25%
        - Valuation: 20%
        - Technical/Momentum: 15%
        - Sentiment: 15%

        v1.0 Weights (legacy):
        - Financial Health: 25%
        - Business Model Moat: 25%
        - Sentiment/Catalysts: 15%
        - Technical Strength: 15%
        - Supply Chain Position: 20%

        Returns:
            float: Moat score (0-10)
        """
        # Use v2.0 formula if new components are present
        if self.earnings_momentum is not None and self.valuation is not None:
            return (
                self.earnings_momentum * 0.25 +
                self.financial_health * 0.25 +
                self.valuation * 0.20 +
                self.technical_strength * 0.15 +
                self.sentiment_catalysts * 0.15
            )

        # Fall back to v1.0 formula for backward compatibility
        if self.business_model_moat is not None and self.supply_chain_position is not None:
            return (
                self.financial_health * 0.25 +
                self.business_model_moat * 0.25 +
                self.sentiment_catalysts * 0.15 +
                self.technical_strength * 0.15 +
                self.supply_chain_position * 0.20
            )

        # If neither v1.0 nor v2.0 components complete, raise error
        raise ValueError(
            "MoatScoreBreakdown requires either v2.0 components "
            "(earnings_momentum, valuation) or v1.0 components "
            "(business_model_moat, supply_chain_position)"
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
        max_length=5,
        description="Top 3-5 investment insights"
    )
    risk_factors: List[str] = Field(
        ...,
        min_length=3,
        max_length=5,
        description="Top 3-5 risk factors"
    )
    investment_thesis: str = Field(
        ...,
        min_length=50,
        description="One-paragraph investment thesis with buy/hold/avoid recommendation"
    )

    # Moat scoring
    moat_score: float = Field(
        ...,
        ge=0,
        le=10,
        description="Final moat score (0-10)"
    )
    moat_breakdown: MoatScoreBreakdown = Field(
        ...,
        description="Breakdown of moat score by component"
    )
    confidence: float = Field(
        ...,
        ge=0,
        le=1,
        description="Confidence level in the analysis (0-1)"
    )

    # Watchlist eligibility
    is_watchlist_candidate: bool = Field(
        ...,
        description="True if moat_score >= 8 (watchlist threshold)"
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
