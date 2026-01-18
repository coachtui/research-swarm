"""
Pydantic models for Fundamentalist agent outputs.

These models ensure type safety and validation for all extracted data.
"""
from pydantic import BaseModel, Field, field_validator, model_validator
from typing import List, Optional, Dict


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


class SupplyChainOutput(BaseModel):
    """Supply chain data extracted from 10-K."""

    # Major customers
    major_customers: List[str] = Field(
        default_factory=list,
        description="List of major customers mentioned in the 10-K"
    )
    customer_concentration: Optional[str] = Field(
        None,
        description="Description of customer concentration risk"
    )

    # Major suppliers
    major_suppliers: List[str] = Field(
        default_factory=list,
        description="List of major suppliers/partners mentioned"
    )
    supplier_dependencies: Optional[str] = Field(
        None,
        description="Description of critical supplier dependencies"
    )

    # Geographic exposure
    geographic_revenue: Dict[str, float] = Field(
        default_factory=dict,
        description="Revenue by geographic region (in millions USD or %)"
    )
    geographic_risks: List[str] = Field(
        default_factory=list,
        description="Geographic/geopolitical risks mentioned"
    )


class ScoreBreakdown(BaseModel):
    """Breakdown of the financial health score."""

    profitability: float = Field(..., ge=0, le=10, description="Profitability score (0-10)")
    growth: float = Field(..., ge=0, le=10, description="Growth score (0-10)")
    balance_sheet: float = Field(..., ge=0, le=10, description="Balance sheet strength score (0-10)")
    cash_flow: float = Field(..., ge=0, le=10, description="Cash flow score (0-10)")
    supply_chain: float = Field(..., ge=0, le=10, description="Supply chain resilience score (0-10)")

    def weighted_average(self) -> float:
        """
        Calculate weighted average score.

        Weights: profitability (25%), growth (20%), balance_sheet (20%),
                 cash_flow (15%), supply_chain (20%)
        """
        return (
            self.profitability * 0.25 +
            self.growth * 0.20 +
            self.balance_sheet * 0.20 +
            self.cash_flow * 0.15 +
            self.supply_chain * 0.20
        )


class FundamentalistOutput(BaseModel):
    """Final validated output from the Fundamentalist agent."""

    # Input identifiers
    ticker: str = Field(..., description="Stock ticker symbol")
    fiscal_year: int = Field(..., description="Fiscal year analyzed")
    filing_date: Optional[str] = Field(None, description="SEC filing date")

    # Extracted data
    financial_metrics: FinancialMetricsOutput = Field(..., description="Extracted financial metrics")
    supply_chain_data: SupplyChainOutput = Field(..., description="Supply chain analysis")

    # Analysis
    financial_analysis: str = Field(..., description="Qualitative financial analysis")

    # Scoring
    financial_health_score: float = Field(..., ge=0, le=10, description="Overall financial health score (0-10)")
    score_breakdown: ScoreBreakdown = Field(..., description="Score breakdown by component")
    confidence: float = Field(..., ge=0, le=1, description="Confidence level in the analysis (0-1)")

    # Metadata
    tokens_used: int = Field(..., description="Total tokens used in API calls")
    processing_time: float = Field(..., description="Total processing time in seconds")

    @model_validator(mode='after')
    def validate_score_matches_breakdown(self):
        """Ensure the overall score matches the weighted average of components."""
        expected = self.score_breakdown.weighted_average()
        # Allow small floating point differences
        if abs(self.financial_health_score - expected) > 0.1:
            raise ValueError(
                f"Health score {self.financial_health_score} does not match "
                f"breakdown weighted average {expected:.2f}"
            )
        return self
