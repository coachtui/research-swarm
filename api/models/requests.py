"""
API request schemas using Pydantic for validation.
"""

from pydantic import BaseModel, Field, validator
from typing import List, Optional

class AnalyzeRequest(BaseModel):
    """
    Request schema for stock analysis.
    """
    ticker: str = Field(
        ...,
        description="Stock ticker symbol (e.g., 'AAPL', 'MSFT')",
        min_length=1,
        max_length=10,
        example="NVDA"
    )

    quarters: List[str] = Field(
        default=["Q4_2024", "Q1_2025", "Q2_2025", "Q3_2025"],
        description="Quarters for TTM analysis (e.g., ['Q4_2024', 'Q1_2025'])",
        min_items=1,
        max_items=8,
        example=["Q4_2024", "Q1_2025", "Q2_2025", "Q3_2025"]
    )

    news_days_back: int = Field(
        default=30,
        description="Number of days to look back for news sentiment",
        ge=1,
        le=90,
        example=30
    )

    @validator('ticker')
    def ticker_uppercase(cls, v):
        """Convert ticker to uppercase."""
        return v.upper().strip()

    @validator('quarters')
    def validate_quarters(cls, v):
        """Validate quarter format."""
        for quarter in v:
            if not quarter.startswith('Q') or '_' not in quarter:
                raise ValueError(
                    f"Invalid quarter format: {quarter}. "
                    "Expected format: Q1_2025, Q2_2025, etc."
                )
        return v

    class Config:
        json_schema_extra = {
            "example": {
                "ticker": "NVDA",
                "quarters": ["Q4_2024", "Q1_2025", "Q2_2025", "Q3_2025"],
                "news_days_back": 30
            }
        }

class BatchAnalyzeRequest(BaseModel):
    """
    Request schema for batch stock analysis (Phase 2).
    """
    tickers: List[str] = Field(
        ...,
        description="List of stock ticker symbols",
        min_items=1,
        max_items=20,
        example=["NVDA", "AMD", "INTC"]
    )

    quarters: List[str] = Field(
        default=["Q4_2024", "Q1_2025", "Q2_2025", "Q3_2025"],
        description="Quarters for TTM analysis"
    )

    news_days_back: int = Field(
        default=30,
        description="Number of days to look back for news sentiment",
        ge=1,
        le=90
    )

    run_name: Optional[str] = Field(
        None,
        description="Optional name for this batch run",
        max_length=100,
        example="Semiconductor Sector Analysis"
    )

    @validator('tickers')
    def tickers_uppercase(cls, v):
        """Convert all tickers to uppercase."""
        return [ticker.upper().strip() for ticker in v]

    @validator('tickers')
    def validate_unique_tickers(cls, v):
        """Ensure tickers are unique."""
        if len(v) != len(set(v)):
            raise ValueError("Duplicate tickers found in request")
        return v

    class Config:
        json_schema_extra = {
            "example": {
                "tickers": ["NVDA", "AMD", "INTC"],
                "quarters": ["Q4_2024", "Q1_2025", "Q2_2025", "Q3_2025"],
                "news_days_back": 30,
                "run_name": "Semiconductor Analysis"
            }
        }
