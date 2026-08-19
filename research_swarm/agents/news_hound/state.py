"""
State schema for the News Hound agent.

Defines the TypedDict for LangGraph state management.
"""
from typing import TypedDict, Optional, Dict, List, Any


class NewsHoundState(TypedDict, total=False):
    """
    State for the News Hound agent workflow.

    This state is passed between nodes in the LangGraph workflow,
    with each node updating relevant fields as it processes news data.
    """

    # Input fields
    ticker: str  # Stock ticker (e.g., "NVDA")
    days_back: int  # Number of days to look back for news (default 30)
    analysis_date: str  # Analysis date (YYYY-MM-DD) — anchors catalyst-date rules

    # Shared data layer (NEW: eliminates redundant API calls)
    shared_swarm_data: Optional[Dict[str, Any]]  # Pre-fetched data bundle from Manager
    etf_system_addendum: Optional[str]  # ETF sector context enrichment for LLM prompts

    # Status tracking
    status: str  # Current workflow status: "initialized", "fetching", "filtering", "extracting", "analyzing", "scoring", "completed", "error"
    error: Optional[str]  # Error message if status is "error"

    # Raw news data
    articles_raw: Optional[List[Dict[str, Any]]]  # Raw articles from NewsAPI
    articles_filtered: Optional[List[Dict[str, Any]]]  # Filtered/deduplicated articles

    # Extracted events
    catalyst_events: Optional[List[Dict[str, Any]]]  # Detected catalyst events
    regulatory_events: Optional[List[Dict[str, Any]]]  # Regulatory events

    # Sentiment analysis
    sentiment_analysis: Optional[str]  # Nuanced sentiment narrative (2-3 paragraphs)
    sentiment_breakdown: Optional[Dict[str, float]]  # 4 component scores (0-10 each)
    sentiment_breakdown_raw: Optional[Dict[str, float]]  # Raw breakdown from interpret_news (Phase B)
    sentiment_confidence_raw: Optional[float]  # Confidence from interpret_news (Phase B)
    sentiment_score: Optional[float]  # Final weighted sentiment score (0-10)
    confidence: Optional[float]  # Confidence level based on article count and quality (0-1)

    # Advanced analytics (Critical Analyst + Smart Money)
    earnings_estimates: Optional[Dict[str, Any]]  # Earnings estimate revision analysis
    analyst_consensus: Optional[Dict[str, Any]]  # Analyst ratings and price targets
    institutional_activity: Optional[Dict[str, Any]]  # Smart money / 13F tracking
    dark_pool_activity: Optional[Dict[str, Any]]  # Dark pool (ATS) trading activity from FINRA
    insider_activity: Optional[Dict[str, Any]]  # Insider trading activity

    # Management quality & market dynamics
    management_commentary: Optional[Dict[str, Any]]  # Management tone and guidance quality
    short_interest: Optional[Dict[str, Any]]  # Short interest tracking and squeeze risk
    upcoming_catalysts: Optional[Dict[str, Any]]  # Upcoming catalyst calendar (6 months)

    # SEC 8-K material events
    sec_8k_filings: Optional[List[Dict[str, Any]]]  # Raw 8-K filings from SEC Edgar
    sec_material_events: Optional[List[Dict[str, Any]]]  # Categorized material events from 8-K

    # Metadata
    article_count: int  # Total number of articles analyzed
    catalyst_count: int  # Total number of catalysts detected
    tokens_used: int  # Total tokens used in API calls
    processing_time: Optional[float]  # Total processing time in seconds
    cost_estimate: Optional[float]  # Estimated API cost in USD
