"""
State schema for the Manager agent.

Defines the TypedDict for LangGraph state management.
"""
from typing import TypedDict, Optional, Dict, List, Any


class ManagerState(TypedDict, total=False):
    """
    State for the Manager agent workflow.

    This state is passed between nodes in the LangGraph workflow,
    with each node updating relevant fields as it processes the data.
    """

    # Input fields
    ticker: str  # Stock ticker (e.g., "NVDA")
    fiscal_year: int  # Fiscal year for fundamentalist analysis
    news_days_back: int  # Number of days to look back for news analysis (default 30)
    analysis_date: str  # Date of analysis (YYYY-MM-DD)

    # Status tracking
    status: str  # Current workflow status: "initialized", "calling_fundamentalist", "calling_news_hound", "calling_quant", "synthesizing", "scoring", "generating_thesis", "completed", "error"
    error: Optional[str]  # Error message if status is "error"

    # Agent outputs (stored as dicts for serialization)
    fundamentalist_output: Optional[Dict[str, Any]]  # Full output from Fundamentalist agent
    news_hound_output: Optional[Dict[str, Any]]  # Full output from News Hound agent
    quant_output: Optional[Dict[str, Any]]  # Full output from Quant agent

    # Extracted component scores for moat calculation
    financial_health_score: Optional[float]  # From Fundamentalist (0-10)
    sentiment_score: Optional[float]  # From News Hound (0-10)
    technical_score: Optional[float]  # From Quant (0-10)
    supply_chain_score: Optional[float]  # From Quant (0-10)

    # Synthesis results
    synthesis_narrative: Optional[str]  # Combined analysis narrative
    key_insights: Optional[List[str]]  # Top 3-5 investment insights
    risk_factors: Optional[List[str]]  # Top 3-5 risk factors

    # Moat scoring
    moat_score: Optional[float]  # Final moat score (0-10)
    moat_breakdown: Optional[Dict[str, float]]  # Breakdown by component
    confidence: Optional[float]  # Confidence level (0-1)
    is_watchlist_candidate: Optional[bool]  # True if moat_score >= 8

    # Investment thesis
    investment_thesis: Optional[str]  # One-paragraph investment thesis

    # Metadata
    tokens_used: int  # Total tokens used in API calls (default 0)
    processing_time: Optional[float]  # Total processing time in seconds
    node_timestamps: Optional[Dict[str, float]]  # Timestamp when each node started
    agent_processing_times: Optional[Dict[str, float]]  # Processing time per agent
