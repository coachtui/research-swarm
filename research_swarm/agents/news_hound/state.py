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
    sentiment_score: Optional[float]  # Final weighted sentiment score (0-10)
    confidence: Optional[float]  # Confidence level based on article count and quality (0-1)

    # Metadata
    article_count: int  # Total number of articles analyzed
    catalyst_count: int  # Total number of catalysts detected
    tokens_used: int  # Total tokens used in API calls
    processing_time: Optional[float]  # Total processing time in seconds
    cost_estimate: Optional[float]  # Estimated API cost in USD
