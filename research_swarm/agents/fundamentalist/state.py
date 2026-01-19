"""
State schema for the Fundamentalist agent.

Defines the TypedDict for LangGraph state management.
"""
from typing import TypedDict, Optional, Dict, List, Any


class FundamentalistState(TypedDict, total=False):
    """
    State for the Fundamentalist agent workflow.

    This state is passed between nodes in the LangGraph workflow,
    with each node updating relevant fields as it processes the data.

    Supports both TTM (quarterly) and annual (10-K) analysis modes.
    """

    # Input fields
    ticker: str  # Stock ticker (e.g., "AAPL")

    # TTM mode fields (primary)
    quarters: List[str]  # Quarters to analyze (e.g., ["Q4_2024", "Q1_2025", "Q2_2025", "Q3_2025"])
    analysis_period: str  # Analysis period description (e.g., "TTM Q4 2024 - Q3 2025")
    analysis_mode: str  # "ttm" or "annual" (for backward compatibility)

    # Backward compatibility - deprecated
    fiscal_year: Optional[int]  # [Deprecated] Fiscal year for annual mode (e.g., 2023)

    # Status tracking
    status: str  # Current workflow status: "initialized", "fetching", "parsing", "analyzing", "scoring", "completed", "error"
    error: Optional[str]  # Error message if status is "error"

    # Raw filing data - TTM mode
    filings_raw: Optional[Dict[str, Dict[str, Any]]]  # Raw filings keyed by quarter (e.g., {"Q4_2024": {...}, "Q1_2025": {...}})
    parsed_sections_by_quarter: Optional[Dict[str, Dict[str, str]]]  # Parsed sections keyed by quarter

    # Raw filing data - Annual mode (backward compatibility)
    filing_raw: Optional[Dict[str, Any]]  # Raw 10-K filing data from SEC client
    parsed_sections: Optional[Dict[str, str]]  # Parsed 10-K sections (Item 1, 1A, 7, 8)

    # Extracted data - TTM mode
    financial_metrics_by_quarter: Optional[Dict[str, Dict[str, Any]]]  # Metrics keyed by quarter
    quarterly_trends: Optional[Dict[str, Any]]  # Quarter-over-quarter trends
    ttm_metrics: Optional[Dict[str, Any]]  # Aggregated TTM metrics

    # Extracted data - Annual mode (backward compatibility)
    financial_metrics: Optional[Dict[str, Any]]  # Financial metrics extracted from 10-K
    supply_chain_data: Optional[Dict[str, Any]]  # Supply chain data (customers, suppliers)

    # Analysis results (shared by both modes)
    financial_analysis: Optional[str]  # Qualitative financial analysis
    financial_health_score: Optional[float]  # Final health score (0-10)
    score_breakdown: Optional[Dict[str, float]]  # Breakdown by component (profitability, growth, etc.)
    confidence: Optional[float]  # Confidence level (0-1)

    # Data quality tracking (TTM mode)
    data_quality: Optional[Dict[str, str]]  # Quarter -> "10-Q" | "10-K" | "missing"

    # Metadata
    tokens_used: int  # Total tokens used in API calls
    processing_time: Optional[float]  # Total processing time in seconds
