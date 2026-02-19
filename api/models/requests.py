"""
API request schemas using Pydantic for validation.
"""

from pydantic import BaseModel, Field, field_validator
from typing import List, Optional
import re

_TICKER_RE = re.compile(r'^[A-Z]{1,5}(\.[A-Z]{1,2})?$')

class AnalyzeRequest(BaseModel):
    """
    Request schema for stock analysis.
    """
    ticker: str = Field(
        ...,
        description="Stock ticker symbol (e.g., 'AAPL', 'MSFT')",
        min_length=1,
        max_length=10,
    )

    quarters: List[str] = Field(
        default=["Q4_2024", "Q1_2025", "Q2_2025", "Q3_2025"],
        description="Quarters for TTM analysis (e.g., ['Q4_2024', 'Q1_2025'])",
        min_length=1,
        max_length=8,
    )

    news_days_back: int = Field(
        default=30,
        description="Number of days to look back for news sentiment",
        ge=1,
        le=90,
    )

    @field_validator('ticker')
    @classmethod
    def ticker_uppercase(cls, v: str) -> str:
        v = v.upper().strip()
        if not _TICKER_RE.match(v):
            raise ValueError("Ticker must be 1-5 uppercase letters, optionally followed by a dot and 1-2 letters (e.g. AAPL, BRK.B)")
        return v

    @field_validator('quarters')
    @classmethod
    def validate_quarters(cls, v: List[str]) -> List[str]:
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
        min_length=1,
        max_length=20,
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
    )

    @field_validator('tickers')
    @classmethod
    def tickers_uppercase(cls, v: List[str]) -> List[str]:
        result = []
        for ticker in v:
            t = ticker.upper().strip()
            if not _TICKER_RE.match(t):
                raise ValueError(f"Invalid ticker '{ticker}': must be 1-5 uppercase letters, optionally followed by a dot and 1-2 letters")
            result.append(t)
        return result

    @field_validator('tickers')
    @classmethod
    def validate_unique_tickers(cls, v: List[str]) -> List[str]:
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
