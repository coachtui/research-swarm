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
    quarters: List[str]  # Quarters for TTM analysis (e.g., ["Q4_2024", "Q1_2025", "Q2_2025", "Q3_2025"])
    analysis_period: str  # Analysis period description (e.g., "TTM Q4 2024 - Q3 2025")
    news_days_back: int  # Number of days to look back for news analysis (default 30)
    analysis_date: str  # Date of analysis (YYYY-MM-DD)

    # Shared data layer (NEW: eliminates redundant API calls)
    shared_swarm_data: Optional[Dict[str, Any]]  # Pre-fetched data bundle for all agents

    # ETF mode flag — set by analysis_service when quoteType == "ETF"
    is_etf: bool  # True when analyzing an ETF (routes to ETF pipeline)
    etf_synthesis: Optional[Dict[str, Any]]  # ETF synthesis results (only set when is_etf=True)

    # Backward compatibility
    fiscal_year: Optional[int]  # Deprecated - for backward compatibility only

    # Status tracking
    status: str  # Current workflow status: "initialized", "calling_fundamentalist", "calling_news_hound", "calling_quant", "synthesizing", "scoring", "generating_thesis", "completed", "error"
    error: Optional[str]  # Error message if status is "error"

    # Per-agent error fields for parallel execution (avoids concurrent write conflicts)
    fundamentalist_error: Optional[str]
    news_hound_error: Optional[str]
    quant_error: Optional[str]

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
    signal_breakdown: Optional[Dict[str, Any]]  # Signal divergence analysis (v2.0)

    # Moat scoring
    moat_score: Optional[float]  # Final moat score (0-10)
    moat_breakdown: Optional[Dict[str, float]]  # Breakdown by component
    confidence: Optional[float]  # Confidence level (0-1)
    is_watchlist_candidate: Optional[bool]  # True if moat_score >= 8

    # Investment thesis
    investment_thesis: Optional[str]  # One-paragraph investment thesis
    recommendation: Optional[str]  # BUY/HOLD/AVOID from investment thesis
    strategic_catalysts: Optional[List[Dict[str, str]]]  # 3-6 forward-looking strategic developments

    # v2.0 enhancements
    rating: Optional[str]  # 5-tier rating: STRONG BUY/BUY/HOLD/SELL/STRONG SELL
    rating_score: Optional[float]  # Numeric rating score (0-10)
    risk_level: Optional[str]  # Risk classification: Low/Medium/High
    structured_risks: Optional[List[Dict[str, Any]]]  # Risks with severity, likelihood, impact, mitigation
    upgrade_triggers: Optional[List[Dict[str, str]]]  # Specific metrics → action for upgrades
    downgrade_triggers: Optional[List[Dict[str, str]]]  # Specific metrics → action for downgrades
    price_targets: Optional[Dict[str, Any]]  # Bull/Base/Bear price target scenarios
    conviction_statement: Optional[Dict[str, Any]]  # Conviction level, bottom line, best suited for
    fair_value_calibration: Optional[Dict[str, Any]]  # FairValueCalibration metadata from fundamentalist
    report_qa_flags: Optional[List[Dict[str, Any]]]  # QA flags for admin review

    # Metadata
    tokens_used: int  # Total tokens used in API calls (default 0)
    processing_time: Optional[float]  # Total processing time in seconds
    node_timestamps: Optional[Dict[str, float]]  # Timestamp when each node started
    agent_processing_times: Optional[Dict[str, float]]  # Processing time per agent
