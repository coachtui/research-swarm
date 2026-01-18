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

    Moat score formula (from master-plan.md):
    - Financial Health (Fundamentalist): 30%
    - Sentiment/Catalysts (News Hound): 20%
    - Technical Strength (Quant): 20%
    - Supply Chain Position (Quant): 30%
    """

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
        description="Technical score from Quant (0-10)"
    )
    supply_chain_position: float = Field(
        ...,
        ge=0,
        le=10,
        description="Supply chain score from Quant (0-10)"
    )

    def weighted_average(self) -> float:
        """
        Calculate weighted average moat score.

        Weights:
        - Financial Health: 30%
        - Sentiment/Catalysts: 20%
        - Technical Strength: 20%
        - Supply Chain Position: 30%

        Returns:
            float: Moat score (0-10)
        """
        return (
            self.financial_health * 0.30 +
            self.sentiment_catalysts * 0.20 +
            self.technical_strength * 0.20 +
            self.supply_chain_position * 0.30
        )


class ManagerOutput(BaseModel):
    """Final validated output from the Manager agent."""

    # Input identifiers
    ticker: str = Field(..., description="Stock ticker symbol")
    analysis_date: str = Field(..., description="Date of analysis (YYYY-MM-DD)")
    fiscal_year: int = Field(..., description="Fiscal year analyzed")
    news_days_back: int = Field(..., description="News lookback period in days")

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
        """Ensure moat score matches the weighted average of components."""
        expected_moat = self.moat_breakdown.weighted_average()
        if abs(self.moat_score - expected_moat) > 0.1:
            raise ValueError(
                f"Moat score {self.moat_score} does not match "
                f"breakdown weighted average {expected_moat:.2f}"
            )
        return self

    @model_validator(mode='after')
    def validate_watchlist_threshold(self):
        """Ensure watchlist candidate flag matches the threshold."""
        expected_watchlist = self.moat_score >= 8.0
        if self.is_watchlist_candidate != expected_watchlist:
            raise ValueError(
                f"Watchlist candidate flag {self.is_watchlist_candidate} "
                f"does not match moat score {self.moat_score} "
                f"(threshold: >= 8.0)"
            )
        return self
