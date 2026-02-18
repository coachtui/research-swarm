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
        state["articles_raw"] = [article.dict() for article in articles]
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
    state["articles_filtered"] = [article.dict() for article in articles]

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
    state["catalyst_events"] = [catalyst.dict() for catalyst in catalysts]
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
    state["regulatory_events"] = [event.dict() for event in reg_events]
    state["tokens_used"] = state.get("tokens_used", 0) + tokens

    # Merge regulatory events into catalyst_events
    catalyst_events = state.get("catalyst_events", [])
    catalyst_events.extend(state["regulatory_events"])
    state["catalyst_events"] = catalyst_events
    state["catalyst_count"] = len(catalyst_events)

    logger.info(f"Added {len(reg_events)} regulatory events (total catalysts: {state['catalyst_count']})")

    return state


def extract_8k_events_node(state: NewsHoundState) -> NewsHoundState:
    """
    Node 4b: Extract material events from SEC 8-K filings.

    8-K filings disclose material events between quarterly reports
    (M&A, officer changes, material agreements, etc.). These are
    official SEC disclosures — harder signals than news articles.

    Args:
        state: Current workflow state

    Returns:
        Updated state with sec_material_events merged into catalyst_events
    """
    logger.info(f"[Node 4b] Extracting SEC 8-K material events for {state['ticker']}")

    shared_data = state.get("shared_swarm_data") or {}
    filings_8k = shared_data.get("recent_8k_filings")

    if not filings_8k or not filings_8k.get("filings"):
        state["sec_8k_filings"] = []
        state["sec_material_events"] = []
        logger.info(f"No 8-K filings available for {state['ticker']}")
        return state

    filings_list = filings_8k["filings"]
    state["sec_8k_filings"] = filings_list

    # Build text summary for LLM extraction
    filings_text_parts = []
    for filing in filings_list:
        filing_date = filing.get("filing_date", "Unknown")
        items = filing.get("items", {})
        for item_num, item_text in items.items():
            # Truncate individual items for prompt efficiency
            truncated = item_text[:2000] if len(item_text) > 2000 else item_text
            filings_text_parts.append(
                f"**Filing Date: {filing_date} — Item {item_num}**\n{truncated}"
            )

    if not filings_text_parts:
        state["sec_material_events"] = []
        logger.info(f"No parseable 8-K items for {state['ticker']}")
        return state

    filings_text = "\n\n---\n\n".join(filings_text_parts)

    # Use Haiku for cost-efficient extraction
    from research_swarm.agents.news_hound.prompts import SEC_8K_EXTRACTION_PROMPT
    from langchain_anthropic import ChatAnthropic
    import json as json_module

    try:
        llm = ChatAnthropic(model="claude-haiku-4-5-20251001", temperature=0, max_tokens=2000)
        prompt = SEC_8K_EXTRACTION_PROMPT.format(
            ticker=state["ticker"],
            filings_text=filings_text,
        )
        response = llm.invoke(prompt)
        tokens = response.usage_metadata.get("total_tokens", 0) if hasattr(response, "usage_metadata") and response.usage_metadata else 500

        # Parse response
        content = response.content.strip()
        # Handle markdown code blocks
        if content.startswith("```"):
            content = content.split("```")[1]
            if content.startswith("json"):
                content = content[4:]
            content = content.strip()

        parsed = json_module.loads(content)
        material_events = parsed.get("material_events", [])

        # Convert to catalyst event format for consistency
        catalyst_events = state.get("catalyst_events", []) or []
        for event in material_events:
            catalyst_events.append({
                "event_type": event.get("event_type", "other"),
                "impact": event.get("impact", "neutral"),
                "description": f"[SEC 8-K] {event.get('description', '')}",
                "date": event.get("date"),
                "confidence": event.get("confidence", 0.95),
                "source_urls": [],
                "sec_item": event.get("sec_item"),
                "severity": event.get("severity", "medium"),
            })

        state["sec_material_events"] = material_events
        state["catalyst_events"] = catalyst_events
        state["catalyst_count"] = len(catalyst_events)
        state["tokens_used"] = state.get("tokens_used", 0) + tokens

        logger.success(f"✓ Extracted {len(material_events)} material events from 8-K filings for {state['ticker']}")

    except Exception as e:
        logger.warning(f"8-K extraction failed for {state['ticker']}: {e}")
        state["sec_material_events"] = []

    return state


def analyze_earnings_estimates_node(state: NewsHoundState) -> NewsHoundState:
    """
    Node 5: Analyze earnings estimate revisions (PRIMARY SIGNAL).

    Args:
        state: Current workflow state

    Returns:
        Updated state with earnings_estimates
    """
    logger.info(f"[Node 5] Analyzing earnings estimates for {state['ticker']}")

    state["status"] = "analyzing_earnings"

    from research_swarm.data.market_data_client import market_data_client
    from research_swarm.data.analyst_revision_calculator import calculate_revision_metrics

    try:
        # NEW: Get from shared data first, fallback to direct fetch
        shared_data = state.get("shared_swarm_data", {})
        estimates_data = shared_data.get("analyst_estimates")
        recommendations_data = shared_data.get("earnings_data", {}).get("recommendations")

        # Fallback if not in shared data
        if estimates_data is None:
            logger.debug("Fetching earnings estimates directly (no shared data)")
            estimates_data = market_data_client.get_earnings_estimates(state["ticker"])
        if recommendations_data is None:
            logger.debug("Fetching analyst recommendations directly (no shared data)")
            recommendations_data = market_data_client.get_analyst_recommendations(state["ticker"])

        # CRITICAL FIX: Fetch upgrades/downgrades data for revision detection
        logger.debug("Fetching upgrades/downgrades data for revision metrics")
        upgrades_downgrades = market_data_client.get_upgrades_downgrades(
            state["ticker"],
            days_back=90  # Last 3 months
        )

        # Calculate revision metrics from upgrades/downgrades
        revision_metrics = calculate_revision_metrics(upgrades_downgrades)

        # Analyze with LLM
        result, tokens = analyzer.analyze_earnings_estimates(
            estimates_data,
            recommendations_data,
            state["ticker"],
            state.get("analysis_date", "")
        )

        # CRITICAL: Override LLM-generated revision metrics with calculated metrics
        result["upward_revisions"] = revision_metrics["upward_revisions"]
        result["downward_revisions"] = revision_metrics["downward_revisions"]
        result["net_revision_direction"] = revision_metrics["net_revision_direction"]
        result["momentum"] = revision_metrics["momentum"]

        # Store in state
        state["earnings_estimates"] = result
        state["tokens_used"] = state.get("tokens_used", 0) + tokens

        logger.success(f"✓ Earnings estimates analyzed (revisions: {revision_metrics['upward_revisions']} up, {revision_metrics['downward_revisions']} down)")

    except Exception as e:
        logger.error(f"Error in earnings estimates node: {e}")
        state["earnings_estimates"] = None

    return state


def analyze_analyst_consensus_node(state: NewsHoundState) -> NewsHoundState:
    """
    Node 6: Analyze analyst consensus and price targets.

    Args:
        state: Current workflow state

    Returns:
        Updated state with analyst_consensus
    """
    logger.info(f"[Node 6] Analyzing analyst consensus for {state['ticker']}")

    state["status"] = "analyzing_consensus"

    from research_swarm.data.market_data_client import market_data_client

    try:
        # NEW: Get from shared data first, fallback to direct fetch
        shared_data = state.get("shared_swarm_data", {})
        recommendations_data = shared_data.get("earnings_data", {}).get("recommendations")
        price_targets = shared_data.get("earnings_data", {}).get("price_target")

        # Fallback if not in shared data
        if recommendations_data is None:
            logger.debug("Fetching analyst recommendations directly (no shared data)")
            recommendations_data = market_data_client.get_analyst_recommendations(state["ticker"])
        if price_targets is None:
            logger.debug("Fetching price targets directly (no shared data)")
            price_targets = market_data_client.get_analyst_price_target(state["ticker"])

        # Analyze with LLM
        result, tokens = analyzer.analyze_analyst_consensus(
            recommendations_data,
            price_targets,
            state["ticker"],
            state.get("analysis_date", "")
        )

        # Store in state
        state["analyst_consensus"] = result
        state["tokens_used"] = state.get("tokens_used", 0) + tokens

        logger.success(f"✓ Analyst consensus analyzed")

    except Exception as e:
        logger.error(f"Error in analyst consensus node: {e}")
        state["analyst_consensus"] = None

    return state


def analyze_institutional_activity_node(state: NewsHoundState) -> NewsHoundState:
    """
    Node 7: Analyze institutional activity (13F smart money).

    Args:
        state: Current workflow state

    Returns:
        Updated state with institutional_activity
    """
    logger.info(f"[Node 7] Analyzing institutional activity for {state['ticker']}")

    state["status"] = "analyzing_institutional"

    from research_swarm.data.market_data_client import market_data_client

    try:
        # NEW: Get from shared data first, fallback to direct fetch
        shared_data = state.get("shared_swarm_data", {})
        institutional_data = shared_data.get("institutional_holders")

        # Fallback if not in shared data
        if institutional_data is None:
            logger.debug("Fetching institutional holders directly (no shared data)")
            institutional_data = market_data_client.get_institutional_holders(state["ticker"])

        # Analyze with LLM
        result, tokens = analyzer.analyze_institutional_activity(
            institutional_data,
            state["ticker"],
            state.get("analysis_date", "")
        )

        # Store in state
        state["institutional_activity"] = result
        state["tokens_used"] = state.get("tokens_used", 0) + tokens

        logger.success(f"✓ Institutional activity analyzed")

    except Exception as e:
        logger.error(f"Error in institutional activity node: {e}")
        state["institutional_activity"] = None

    return state


def analyze_dark_pool_activity_node(state: NewsHoundState) -> NewsHoundState:
    """
    Node 7b: Analyze dark pool (ATS) activity from FINRA data.

    Args:
        state: Current workflow state

    Returns:
        Updated state with dark_pool_activity
    """
    logger.info(f"[Node 7b] Analyzing dark pool activity for {state['ticker']}")

    state["status"] = "analyzing_dark_pool"

    from research_swarm.data.finra_client import finra_client

    try:
        # Check for pre-fetched data from Manager's fetch_swarm_data_node
        shared_data = state.get("shared_swarm_data", {})
        dark_pool_data = shared_data.get("dark_pool_data")

        # Fallback: Fetch directly if not in shared data
        if dark_pool_data is None:
            logger.debug("Fetching dark pool data directly from FINRA (no shared data)")
            dark_pool_data = finra_client.get_dark_pool_activity(state["ticker"], weeks_back=4)

        # Get institutional context for cross-reference
        institutional_context = None
        if state.get("institutional_activity"):
            inst_data = state["institutional_activity"]
            institutional_context = (
                f"Institutional ownership: {inst_data.get('institutional_ownership_pct', 'N/A')}%, "
                f"Trend: {inst_data.get('trend', 'unknown')}, "
                f"Sentiment: {inst_data.get('institutional_sentiment', 'neutral')}"
            )

        # Analyze with LLM
        result, tokens = analyzer.analyze_dark_pool_activity(
            dark_pool_data,
            institutional_context,
            state["ticker"],
            state.get("analysis_date", "")
        )

        # Store in state
        state["dark_pool_activity"] = result
        state["tokens_used"] = state.get("tokens_used", 0) + tokens

        logger.success(f"✓ Dark pool activity analyzed")

    except Exception as e:
        logger.error(f"Error in dark pool activity node: {e}")
        state["dark_pool_activity"] = None

    return state


def analyze_insider_activity_node(state: NewsHoundState) -> NewsHoundState:
    """
    Node 8: Analyze insider trading activity using OpenInsider.

    Args:
        state: Current workflow state

    Returns:
        Updated state with insider_activity
    """
    logger.info(f"[Node 8] Analyzing insider activity for {state['ticker']}")

    state["status"] = "analyzing_insider"

    from research_swarm.data.openinsider_client import openinsider_client

    try:
        # Fetch insider transactions from OpenInsider (more reliable than yfinance)
        transactions = openinsider_client.get_insider_transactions(
            state["ticker"],
            days_back=365  # 1 year lookback
        )

        # Calculate insider score using new scoring system
        insider_result = openinsider_client.calculate_insider_score(
            transactions,
            state["ticker"]
        )

        # Format result to match expected structure
        result = {
            "buy_transactions": insider_result["buy_transactions"],
            "sell_transactions": insider_result["sell_transactions"],
            "net_value_usd": insider_result["net_value"],
            "insider_sentiment": insider_result["sentiment"],
            "key_transactions": insider_result["key_transactions"],
            "insider_score": insider_result["score"],  # NEW: Direct score (0-10)
            "has_data": insider_result["has_data"]
        }

        # Store in state
        state["insider_activity"] = result
        # No LLM tokens used - pure calculation
        state["tokens_used"] = state.get("tokens_used", 0)

        if result["has_data"]:
            logger.success(
                f"✓ Insider activity analyzed: {result['insider_score']:.1f}/10 "
                f"({result['buy_transactions']} buys, {result['sell_transactions']} sells, "
                f"net ${result['net_value_usd']:,.0f})"
            )
        else:
            logger.info(f"No insider data available for {state['ticker']}")

    except Exception as e:
        logger.error(f"Error in insider activity node: {e}")
        import traceback
        traceback.print_exc()
        # Return neutral default
        state["insider_activity"] = {
            "buy_transactions": 0,
            "sell_transactions": 0,
            "net_value_usd": 0.0,
            "insider_sentiment": "neutral",
            "key_transactions": [],
            "insider_score": 5.0,
            "has_data": False
        }

    return state


def analyze_short_interest_node(state: NewsHoundState) -> NewsHoundState:
    """
    Node 9: Analyze short interest and squeeze risk.

    Args:
        state: Current workflow state

    Returns:
        Updated state with short_interest
    """
    logger.info(f"[Node 9] Analyzing short interest for {state['ticker']}")

    state["status"] = "analyzing_short"

    from research_swarm.data.market_data_client import market_data_client

    try:
        # NEW: Get from shared data first, fallback to direct fetch
        shared_data = state.get("shared_swarm_data", {})
        short_data = shared_data.get("short_interest")

        # Fallback if not in shared data
        if short_data is None:
            logger.debug("Fetching short interest directly (no shared data)")
            short_data = market_data_client.get_short_interest(state["ticker"])

        # Analyze with LLM
        result, tokens = analyzer.analyze_short_interest(
            short_data,
            state["ticker"],
            state.get("analysis_date", "")
        )

        # Store in state
        state["short_interest"] = result
        state["tokens_used"] = state.get("tokens_used", 0) + tokens

        logger.success(f"✓ Short interest analyzed")

    except Exception as e:
        logger.error(f"Error in short interest node: {e}")
        state["short_interest"] = None

    return state


def analyze_upcoming_catalysts_node(state: NewsHoundState) -> NewsHoundState:
    """
    Node 10: Analyze upcoming catalysts calendar.

    Args:
        state: Current workflow state

    Returns:
        Updated state with upcoming_catalysts
    """
    logger.info(f"[Node 10] Analyzing upcoming catalysts for {state['ticker']}")

    state["status"] = "analyzing_catalysts"

    from research_swarm.data.market_data_client import market_data_client
    from research_swarm.agents.news_hound.models import CatalystEvent

    try:
        # NEW: Get from shared data first, fallback to direct fetch
        shared_data = state.get("shared_swarm_data", {})
        earnings_dates = shared_data.get("earnings_data", {}).get("earnings_dates")

        # Fallback if not in shared data
        if earnings_dates is None:
            logger.debug("Fetching earnings dates directly (no shared data)")
            earnings_dates = market_data_client.get_earnings_dates(state["ticker"])

        # Get detected catalyst events
        catalyst_events = []
        if state.get("catalyst_events"):
            catalyst_events = [CatalystEvent(**cat) for cat in state["catalyst_events"]]

        # Analyze with LLM
        result, tokens = analyzer.analyze_upcoming_catalysts(
            earnings_dates,
            catalyst_events,
            state["ticker"],
            state.get("analysis_date", "")
        )

        # Store in state
        state["upcoming_catalysts"] = result
        state["tokens_used"] = state.get("tokens_used", 0) + tokens

        logger.success(f"✓ Upcoming catalysts analyzed")

    except Exception as e:
        logger.error(f"Error in upcoming catalysts node: {e}")
        state["upcoming_catalysts"] = None

    return state


def analyze_management_commentary_node(state: NewsHoundState) -> NewsHoundState:
    """
    Node 11: Analyze management commentary and guidance.

    Args:
        state: Current workflow state

    Returns:
        Updated state with management_commentary
    """
    logger.info(f"[Node 11] Analyzing management commentary for {state['ticker']}")

    state["status"] = "analyzing_management"

    from research_swarm.agents.news_hound.models import NewsArticle

    try:
        # Get earnings-related articles from filtered articles
        articles_filtered = state.get("articles_filtered", [])
        if articles_filtered:
            articles = [NewsArticle(**art) for art in articles_filtered]
            # Filter for earnings-related articles
            earnings_articles = [art for art in articles if any(
                keyword in art.title.lower() or (art.description and keyword in art.description.lower())
                for keyword in ["earnings", "guidance", "outlook", "forecast", "quarter"]
            )]
        else:
            earnings_articles = []

        # Analyze with LLM
        result, tokens = analyzer.analyze_management_commentary(
            earnings_articles,
            state["ticker"],
            state.get("analysis_date", "")
        )

        # Store in state
        state["management_commentary"] = result
        state["tokens_used"] = state.get("tokens_used", 0) + tokens

        logger.success(f"✓ Management commentary analyzed")

    except Exception as e:
        logger.error(f"Error in management commentary node: {e}")
        state["management_commentary"] = None

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
        state["sentiment_breakdown"] = breakdown.dict()
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
    state["sentiment_breakdown"] = breakdown.dict()
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
    workflow.add_node("extract_8k_events", extract_8k_events_node)
    # New analyst data nodes
    workflow.add_node("analyze_earnings", analyze_earnings_estimates_node)
    workflow.add_node("analyze_consensus", analyze_analyst_consensus_node)
    workflow.add_node("analyze_institutional", analyze_institutional_activity_node)
    workflow.add_node("analyze_dark_pool", analyze_dark_pool_activity_node)  # NEW: Dark pool node
    workflow.add_node("analyze_insider", analyze_insider_activity_node)
    workflow.add_node("analyze_short", analyze_short_interest_node)
    workflow.add_node("analyze_catalysts", analyze_upcoming_catalysts_node)
    workflow.add_node("analyze_management", analyze_management_commentary_node)
    # Sentiment nodes
    workflow.add_node("analyze_sentiment", analyze_sentiment_node)
    workflow.add_node("score_sentiment", score_sentiment_node)

    # Set entry point
    workflow.set_entry_point("fetch_news")

    # Add edges - sequential flow
    workflow.add_edge("fetch_news", "filter_articles")
    workflow.add_edge("filter_articles", "extract_catalysts")
    workflow.add_edge("extract_catalysts", "extract_regulatory")
    # Wire 8-K extraction and analyst data nodes
    workflow.add_edge("extract_regulatory", "extract_8k_events")
    workflow.add_edge("extract_8k_events", "analyze_earnings")
    workflow.add_edge("analyze_earnings", "analyze_consensus")
    workflow.add_edge("analyze_consensus", "analyze_institutional")
    workflow.add_edge("analyze_institutional", "analyze_dark_pool")  # NEW: Wire dark pool after institutional
    workflow.add_edge("analyze_dark_pool", "analyze_insider")  # NEW: Connect dark pool to insider
    workflow.add_edge("analyze_insider", "analyze_short")
    workflow.add_edge("analyze_short", "analyze_catalysts")
    workflow.add_edge("analyze_catalysts", "analyze_management")
    workflow.add_edge("analyze_management", "analyze_sentiment")
    # Final sentiment nodes
    workflow.add_edge("analyze_sentiment", "score_sentiment")

    # Score sentiment is the final node
    workflow.set_finish_point("score_sentiment")

    return workflow.compile()


# ============================================================================
# Main Analysis Function
# ============================================================================

def analyze_company_news(ticker: str, days_back: int = 30, shared_swarm_data: dict = None) -> NewsHoundOutput:
    """
    Analyze news sentiment and catalysts for a company.

    Args:
        ticker: Stock ticker (e.g., "NVDA")
        days_back: Number of days to look back (default 30)
        shared_swarm_data: Pre-fetched data bundle from Manager (NEW)

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
        "shared_swarm_data": shared_swarm_data,  # NEW: Pre-fetched data from Manager
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
        SentimentBreakdown,
        EarningsEstimateRevision,
        AnalystConsensus,
        InstitutionalActivity,
        InsiderActivity,
        ManagementCommentary,
        ShortInterest,
        UpcomingCatalysts
    )

    # Reconstruct catalyst events
    catalyst_events = [
        CatalystEvent(**cat) for cat in final_state.get("catalyst_events", [])
    ]

    # Reconstruct sentiment breakdown
    sentiment_breakdown = SentimentBreakdown(**final_state["sentiment_breakdown"])

    # Reconstruct new analyst data models
    earnings_estimates = None
    if final_state.get("earnings_estimates"):
        earnings_estimates = EarningsEstimateRevision(**final_state["earnings_estimates"])

    analyst_consensus = None
    if final_state.get("analyst_consensus"):
        analyst_consensus = AnalystConsensus(**final_state["analyst_consensus"])

    institutional_activity = None
    if final_state.get("institutional_activity"):
        institutional_activity = InstitutionalActivity(**final_state["institutional_activity"])

    dark_pool_activity = None
    if final_state.get("dark_pool_activity"):
        from research_swarm.agents.news_hound.models import DarkPoolActivity
        dark_pool_activity = DarkPoolActivity(**final_state["dark_pool_activity"])

    insider_activity = None
    if final_state.get("insider_activity"):
        insider_activity = InsiderActivity(**final_state["insider_activity"])

    management_commentary = None
    if final_state.get("management_commentary"):
        management_commentary = ManagementCommentary(**final_state["management_commentary"])

    short_interest = None
    if final_state.get("short_interest"):
        short_interest = ShortInterest(**final_state["short_interest"])

    upcoming_catalysts = None
    if final_state.get("upcoming_catalysts"):
        upcoming_catalysts = UpcomingCatalysts(**final_state["upcoming_catalysts"])

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
        # New analyst data fields
        earnings_estimates=earnings_estimates,
        analyst_consensus=analyst_consensus,
        institutional_activity=institutional_activity,
        dark_pool_activity=dark_pool_activity,
        insider_activity=insider_activity,
        management_commentary=management_commentary,
        short_interest=short_interest,
        upcoming_catalysts=upcoming_catalysts,
        # Metadata
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
