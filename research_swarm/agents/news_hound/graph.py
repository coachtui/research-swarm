"""
LangGraph workflow for the News Hound agent.

Orchestrates the news analysis pipeline from fetching to sentiment scoring.
"""
import time
from typing import Dict, Any
from langgraph.graph import StateGraph, END
from research_swarm.logger import logger
from research_swarm.agents.news_hound.state import NewsHoundState
from research_swarm.agents.news_hound.aggregator import aggregator
from research_swarm.agents.news_hound.analyzer import analyzer
from research_swarm.agents.news_hound.scorer import scorer
from research_swarm.agents.news_hound.models import (
    NewsHoundOutput,
    SentimentBreakdown,
    CatalystEvent
)


# ============================================================================
# Node Functions
# ============================================================================

def fetch_news_node(state: NewsHoundState) -> NewsHoundState:
    """
    Node 1: Fetch news articles from NewsAPI.

    Args:
        state: Current workflow state

    Returns:
        Updated state with articles_raw
    """
    logger.info(f"[Node 1] Fetching news for {state['ticker']} (last {state['days_back']} days)")

    state["status"] = "fetching"

    # Fetch from NewsAPI (via aggregator)
    articles = aggregator.fetch_news(state["ticker"], state["days_back"])

    if not articles:
        logger.warning(f"No articles found for {state['ticker']}")
        # Continue with empty articles (will handle gracefully downstream)
        state["articles_raw"] = []
        state["article_count"] = 0
    else:
        # Convert to dicts for state storage
        state["articles_raw"] = [article.model_dump() for article in articles]
        state["article_count"] = len(articles)
        logger.success(f"✓ Fetched {len(articles)} articles")

    return state


def filter_articles_node(state: NewsHoundState) -> NewsHoundState:
    """
    Node 2: Deduplicate and filter articles for relevance.

    Args:
        state: Current workflow state

    Returns:
        Updated state with articles_filtered
    """
    logger.info(f"[Node 2] Filtering articles for {state['ticker']}")

    state["status"] = "filtering"

    articles_raw = state.get("articles_raw", [])

    if not articles_raw:
        state["articles_filtered"] = []
        logger.warning("No articles to filter")
        return state

    # Reconstruct NewsArticle objects
    from research_swarm.agents.news_hound.models import NewsArticle
    articles = [NewsArticle(**art) for art in articles_raw]

    # Deduplicate
    articles = aggregator.deduplicate(articles)

    # Filter for relevance
    articles = aggregator.filter_articles(articles, state["ticker"])

    # Store filtered articles
    state["articles_filtered"] = [article.model_dump() for article in articles]

    logger.success(f"✓ Filtered to {len(articles)} relevant articles")

    return state


def extract_catalysts_node(state: NewsHoundState) -> NewsHoundState:
    """
    Node 3: Extract catalyst events (9 categories).

    Args:
        state: Current workflow state

    Returns:
        Updated state with catalyst_events
    """
    logger.info(f"[Node 3] Extracting catalysts for {state['ticker']}")

    state["status"] = "extracting"

    articles_filtered = state.get("articles_filtered", [])

    if not articles_filtered:
        state["catalyst_events"] = []
        state["catalyst_count"] = 0
        logger.warning("No articles to extract catalysts from")
        return state

    # Reconstruct NewsArticle objects
    from research_swarm.agents.news_hound.models import NewsArticle
    articles = [NewsArticle(**art) for art in articles_filtered]

    # Extract catalysts
    catalysts, tokens = analyzer.extract_catalysts(articles, state["ticker"], state["days_back"])

    # Store catalysts
    state["catalyst_events"] = [catalyst.model_dump() for catalyst in catalysts]
    state["catalyst_count"] = len(catalysts)
    state["tokens_used"] = state.get("tokens_used", 0) + tokens

    logger.success(f"✓ Extracted {len(catalysts)} catalysts")

    return state


def extract_regulatory_node(state: NewsHoundState) -> NewsHoundState:
    """
    Node 4: Extract regulatory events (optional enhancement).

    Args:
        state: Current workflow state

    Returns:
        Updated state with regulatory_events
    """
    logger.info(f"[Node 4] Extracting regulatory events for {state['ticker']}")

    articles_filtered = state.get("articles_filtered", [])

    if not articles_filtered:
        state["regulatory_events"] = []
        logger.info("No articles to extract regulatory events from")
        return state

    # Reconstruct NewsArticle objects
    from research_swarm.agents.news_hound.models import NewsArticle
    articles = [NewsArticle(**art) for art in articles_filtered]

    # Extract regulatory events
    reg_events, tokens = analyzer.extract_regulatory_events(articles, state["ticker"])

    # Store regulatory events (these will be merged with catalyst_events in final output)
    state["regulatory_events"] = [event.model_dump() for event in reg_events]
    state["tokens_used"] = state.get("tokens_used", 0) + tokens

    # Merge regulatory events into catalyst_events
    catalyst_events = state.get("catalyst_events", [])
    catalyst_events.extend(state["regulatory_events"])
    state["catalyst_events"] = catalyst_events
    state["catalyst_count"] = len(catalyst_events)

    logger.info(f"Added {len(reg_events)} regulatory events (total catalysts: {state['catalyst_count']})")

    return state


def analyze_sentiment_node(state: NewsHoundState) -> NewsHoundState:
    """
    Node 5: Perform nuanced sentiment analysis (Sonnet).

    Args:
        state: Current workflow state

    Returns:
        Updated state with sentiment_analysis
    """
    logger.info(f"[Node 5] Analyzing sentiment for {state['ticker']}")

    state["status"] = "analyzing"

    articles_filtered = state.get("articles_filtered", [])
    catalyst_events = state.get("catalyst_events", [])

    # Handle case of no articles
    if not articles_filtered:
        state["sentiment_analysis"] = (
            f"No news articles were found for {state['ticker']} in the last {state['days_back']} days. "
            "This suggests limited media coverage during this period, which could indicate a lack of "
            "significant news events or a quieter period for the company. A neutral sentiment score of "
            "5.0 is assigned due to insufficient data."
        )
        logger.warning("No articles for sentiment analysis")
        return state

    # Reconstruct objects
    from research_swarm.agents.news_hound.models import NewsArticle, CatalystEvent
    articles = [NewsArticle(**art) for art in articles_filtered]
    catalysts = [CatalystEvent(**cat) for cat in catalyst_events]

    # Perform sentiment analysis
    sentiment_text, tokens = analyzer.analyze_sentiment(
        articles,
        catalysts,
        state["ticker"],
        state["days_back"]
    )

    state["sentiment_analysis"] = sentiment_text
    state["tokens_used"] = state.get("tokens_used", 0) + tokens

    logger.success(f"✓ Generated sentiment analysis ({len(sentiment_text)} chars)")

    return state


def score_sentiment_node(state: NewsHoundState) -> NewsHoundState:
    """
    Node 6: Calculate sentiment score (0-10).

    Args:
        state: Current workflow state

    Returns:
        Updated state with sentiment_score, sentiment_breakdown, confidence
    """
    logger.info(f"[Node 6] Scoring sentiment for {state['ticker']}")

    state["status"] = "scoring"

    article_count = state.get("article_count", 0)
    articles_filtered = state.get("articles_filtered", [])
    catalyst_events = state.get("catalyst_events", [])
    sentiment_analysis = state.get("sentiment_analysis", "")

    # Handle case of no articles - return neutral sentiment
    if article_count == 0 or not articles_filtered:
        logger.warning("No articles - assigning neutral sentiment (5.0)")

        # Neutral breakdown
        breakdown = SentimentBreakdown(
            overall_tone=5.0,
            catalyst_impact=5.0,
            market_perception=5.0,
            forward_looking=5.0
        )

        state["sentiment_score"] = 5.0
        state["sentiment_breakdown"] = breakdown.model_dump()
        state["confidence"] = 0.3  # Low confidence due to no data
        state["status"] = "completed"

        return state

    # Reconstruct objects
    from research_swarm.agents.news_hound.models import CatalystEvent
    catalysts = [CatalystEvent(**cat) for cat in catalyst_events]

    # Score sentiment
    sentiment_score, breakdown, confidence, tokens = scorer.score_sentiment(
        state["ticker"],
        state["days_back"],
        article_count,
        sentiment_analysis,
        catalysts
    )

    state["sentiment_score"] = sentiment_score
    state["sentiment_breakdown"] = breakdown.model_dump()
    state["confidence"] = confidence
    state["tokens_used"] = state.get("tokens_used", 0) + tokens
    state["status"] = "completed"

    logger.success(f"✓ Sentiment scored: {sentiment_score:.2f}/10 (confidence: {confidence:.2f}, total tokens: {state['tokens_used']})")

    return state


def should_continue(state: NewsHoundState) -> str:
    """
    Conditional edge: check if workflow should continue or stop.

    Args:
        state: Current workflow state

    Returns:
        "error" if error occurred, "continue" otherwise
    """
    if state.get("status") == "error":
        return "error"
    return "continue"


# ============================================================================
# Build Workflow Graph
# ============================================================================

def build_news_hound_graph() -> StateGraph:
    """
    Build the LangGraph workflow for News Hound agent.

    Returns:
        Compiled StateGraph
    """
    workflow = StateGraph(NewsHoundState)

    # Add nodes
    workflow.add_node("fetch_news", fetch_news_node)
    workflow.add_node("filter_articles", filter_articles_node)
    workflow.add_node("extract_catalysts", extract_catalysts_node)
    workflow.add_node("extract_regulatory", extract_regulatory_node)
    workflow.add_node("analyze_sentiment", analyze_sentiment_node)
    workflow.add_node("score_sentiment", score_sentiment_node)

    # Set entry point
    workflow.set_entry_point("fetch_news")

    # Add edges - sequential flow
    workflow.add_edge("fetch_news", "filter_articles")
    workflow.add_edge("filter_articles", "extract_catalysts")
    workflow.add_edge("extract_catalysts", "extract_regulatory")
    workflow.add_edge("extract_regulatory", "analyze_sentiment")
    workflow.add_edge("analyze_sentiment", "score_sentiment")

    # Score sentiment is the final node
    workflow.set_finish_point("score_sentiment")

    return workflow.compile()


# ============================================================================
# Main Analysis Function
# ============================================================================

def analyze_company_news(ticker: str, days_back: int = 30) -> NewsHoundOutput:
    """
    Analyze news sentiment and catalysts for a company.

    Args:
        ticker: Stock ticker (e.g., "NVDA")
        days_back: Number of days to look back (default 30)

    Returns:
        NewsHoundOutput with complete analysis

    Raises:
        ValueError: If analysis fails
    """
    logger.info(f"=== Analyzing news for {ticker} (last {days_back} days) ===")

    start_time = time.time()

    # Initialize state
    initial_state: NewsHoundState = {
        "ticker": ticker,
        "days_back": days_back,
        "status": "initialized",
        "error": None,
        "articles_raw": None,
        "articles_filtered": None,
        "catalyst_events": None,
        "regulatory_events": None,
        "sentiment_analysis": None,
        "sentiment_breakdown": None,
        "sentiment_score": None,
        "confidence": None,
        "article_count": 0,
        "catalyst_count": 0,
        "tokens_used": 0,
        "processing_time": None,
        "cost_estimate": None,
    }

    # Build and run workflow
    graph = build_news_hound_graph()
    final_state = graph.invoke(initial_state)

    # Check for errors
    if final_state.get("status") == "error":
        error_msg = final_state.get("error", "Unknown error")
        logger.error(f"Analysis failed: {error_msg}")
        raise ValueError(error_msg)

    # Calculate processing time and cost
    processing_time = time.time() - start_time
    final_state["processing_time"] = processing_time

    # Estimate cost (rough calculation)
    # Haiku: $0.25 per 1M input tokens, $1.25 per 1M output tokens
    # Sonnet: $3 per 1M input tokens, $15 per 1M output tokens
    # Rough estimate: ~40k tokens total, ~$0.20 per analysis
    article_count = final_state.get("article_count", 0)
    if article_count == 0:
        cost_estimate = 0.0
    else:
        # Rough estimate based on article count
        cost_estimate = 0.05 + (article_count * 0.008)  # Base + per article
        cost_estimate = min(cost_estimate, 0.30)  # Cap at $0.30

    final_state["cost_estimate"] = cost_estimate

    # Build output
    from research_swarm.agents.news_hound.models import (
        CatalystEvent,
        SentimentBreakdown
    )

    # Reconstruct catalyst events
    catalyst_events = [
        CatalystEvent(**cat) for cat in final_state.get("catalyst_events", [])
    ]

    # Reconstruct sentiment breakdown
    sentiment_breakdown = SentimentBreakdown(**final_state["sentiment_breakdown"])

    output = NewsHoundOutput(
        ticker=final_state["ticker"],
        days_back=final_state["days_back"],
        article_count=final_state["article_count"],
        articles_filtered=len(final_state.get("articles_filtered", [])),
        catalyst_events=catalyst_events,
        sentiment_analysis=final_state["sentiment_analysis"],
        sentiment_breakdown=sentiment_breakdown,
        sentiment_score=final_state["sentiment_score"],
        confidence=final_state["confidence"],
        tokens_used=final_state.get("tokens_used", 0),
        processing_time=processing_time,
        cost_estimate=cost_estimate
    )

    logger.success(
        f"=== News Analysis Complete: {ticker} "
        f"(Sentiment: {output.sentiment_score:.2f}, "
        f"Catalysts: {len(output.catalyst_events)}, "
        f"Time: {processing_time:.1f}s, "
        f"Cost: ${cost_estimate:.2f}) ==="
    )

    return output
