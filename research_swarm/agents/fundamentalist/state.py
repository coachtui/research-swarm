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
    """

    # Input fields
    ticker: str  # Stock ticker (e.g., "AAPL")
    fiscal_year: int  # Fiscal year to analyze (e.g., 2023)

    # Status tracking
    status: str  # Current workflow status: "initialized", "fetching", "parsing", "analyzing", "scoring", "completed", "error"
    error: Optional[str]  # Error message if status is "error"

    # Raw filing data
    filing_raw: Optional[Dict[str, Any]]  # Raw 10-K filing data from SEC client
    parsed_sections: Optional[Dict[str, str]]  # Parsed 10-K sections (Item 1, 1A, 7, 8)

    # Extracted data
    financial_metrics: Optional[Dict[str, Any]]  # Financial metrics extracted from 10-K
    supply_chain_data: Optional[Dict[str, Any]]  # Supply chain data (customers, suppliers)

    # Analysis results
    financial_analysis: Optional[str]  # Qualitative financial analysis
    financial_health_score: Optional[float]  # Final health score (0-10)
    score_breakdown: Optional[Dict[str, float]]  # Breakdown by component (profitability, growth, etc.)
    confidence: Optional[float]  # Confidence level (0-1)

    # Metadata
    tokens_used: int  # Total tokens used in API calls
    processing_time: Optional[float]  # Total processing time in seconds
