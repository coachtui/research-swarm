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

    from research_swarm.data.analyst_revision_calculator import calculate_revision_metrics

    try:
        # Phase A: all data comes from the pre-assembled bundle. Missing means
        # the provider had nothing (visible in snapshot provenance) — no
        # mid-run direct fetches, which tripled upstream load exactly when a
        # provider was already failing.
        shared_data = state.get("shared_swarm_data", {})
        estimates_data = shared_data.get("analyst_estimates")
        recommendations_data = shared_data.get("earnings_data", {}).get("recommendations")
        upgrades_downgrades = shared_data.get("upgrades_downgrades")

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


    try:
        # Phase A: read only from the pre-assembled bundle (no mid-run fetches)
        shared_data = state.get("shared_swarm_data", {})
        recommendations_data = shared_data.get("earnings_data", {}).get("recommendations")
        price_targets = shared_data.get("earnings_data", {}).get("price_target")

        # Pure calculation — no LLM (the old Haiku call just copied these
        # numbers into JSON)
        from research_swarm.agents.news_hound.signal_calculators import calculate_analyst_consensus
        state["analyst_consensus"] = calculate_analyst_consensus(recommendations_data, price_targets)

        logger.success(f"✓ Analyst consensus analyzed (deterministic)")

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


    try:
        # Phase A: read only from the pre-assembled bundle (no mid-run fetches)
        shared_data = state.get("shared_swarm_data", {})
        institutional_data = shared_data.get("institutional_holders")

        # Pure calculation — no LLM
        from research_swarm.agents.news_hound.signal_calculators import calculate_institutional_activity
        state["institutional_activity"] = calculate_institutional_activity(institutional_data)

        logger.success(f"✓ Institutional activity analyzed (deterministic)")

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


    try:
        # Check for pre-fetched data from Manager's fetch_swarm_data_node
        shared_data = state.get("shared_swarm_data", {})
        dark_pool_data = shared_data.get("dark_pool_data")

        # Pure calculation — no LLM (baseline z-score math was already
        # deterministic; the model call only narrated it)
        from research_swarm.agents.news_hound.signal_calculators import calculate_dark_pool_activity
        state["dark_pool_activity"] = calculate_dark_pool_activity(dark_pool_data)

        logger.success(f"✓ Dark pool activity analyzed (deterministic)")

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
        # Pull market cap and float from pre-fetched shared data (best-effort)
        shared_data = state.get("shared_swarm_data") or {}
        company_info = shared_data.get("company_info") or {}
        short_data = shared_data.get("short_interest") or {}
        market_cap = company_info.get("market_cap")        # dollars from yfinance
        float_shares = short_data.get("float_shares")     # share count

        # Phase A: OpenInsider transactions are fetched by the snapshot
        # assembler (concurrently with the main bundle), never mid-run here.
        transactions = shared_data.get("openinsider_transactions")

        # Calculate insider score using 5-component institutional framework
        insider_result = openinsider_client.calculate_insider_score(
            transactions,
            state["ticker"],
            market_cap=market_cap,
            float_shares=float_shares,
        )

        # Format result for state storage
        result = {
            "buy_transactions": insider_result["buy_transactions"],
            "sell_transactions": insider_result["sell_transactions"],
            "net_value_usd": insider_result["net_value"],
            "insider_sentiment": insider_result["sentiment"],
            "key_transactions": insider_result["key_transactions"],
            "insider_score": insider_result["score"],
            "insider_confidence_index": insider_result.get("insider_confidence_index"),
            "has_data": insider_result["has_data"],
            "divergence_ready_bearish": insider_result.get("divergence_ready_bearish", False),
            "divergence_ready_bullish": insider_result.get("divergence_ready_bullish", False),
            "cluster_buying_present": insider_result.get("cluster_buying_present", False),
            "activity_summary": insider_result.get("activity_summary"),
            # Component breakdown
            "layer1_net_float": insider_result.get("layer1_net_float"),
            "layer2_holdings": insider_result.get("layer2_holdings"),
            "layer3_cluster": insider_result.get("layer3_cluster"),
            "layer4_seniority": insider_result.get("layer4_seniority"),
            "layer5_decay": insider_result.get("layer5_decay"),
        }

        # Store in state
        state["insider_activity"] = result
        # No LLM tokens used - pure calculation
        state["tokens_used"] = state.get("tokens_used", 0)

        if result["has_data"]:
            activity = result.get("activity_summary") or {}
            logger.success(
                f"✓ Insider activity analyzed: {result['insider_score']:.1f}/10 "
                f"(ICI={result.get('insider_confidence_index', 'N/A')}) — "
                f"{result['buy_transactions']} buys, {result['sell_transactions']} sells, "
                f"net ${result['net_value_usd']:,.0f} — {activity.get('cluster_status', '')}"
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
            "insider_confidence_index": 50.0,
            "has_data": False,
            "divergence_ready_bearish": False,
            "divergence_ready_bullish": False,
            "cluster_buying_present": False,
            "activity_summary": None,
            "layer1_net_float": None,
            "layer2_holdings": None,
            "layer3_cluster": None,
            "layer4_seniority": None,
            "layer5_decay": None,
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


    try:
        # Phase A: read only from the pre-assembled bundle (no mid-run fetches)
        shared_data = state.get("shared_swarm_data", {})
        short_data = shared_data.get("short_interest")

        # Pure calculation — no LLM (the old prompt asked Haiku to copy six
        # numbers into JSON and apply a hardcoded threshold table)
        from research_swarm.agents.news_hound.signal_calculators import calculate_short_interest
        state["short_interest"] = calculate_short_interest(short_data)

        logger.success(f"✓ Short interest analyzed (deterministic)")

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

    from research_swarm.agents.news_hound.models import CatalystEvent

    try:
        # Phase A: read only from the pre-assembled bundle (no mid-run fetches)
        shared_data = state.get("shared_swarm_data", {})
        earnings_dates = shared_data.get("earnings_data", {}).get("earnings_dates")

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

    # Perform sentiment analysis (inject ETF addendum if present)
    sentiment_text, tokens = analyzer.analyze_sentiment(
        articles,
        catalysts,
        state["ticker"],
        state["days_back"],
        system_addendum=state.get("etf_system_addendum", "")
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

def analyze_company_news(
    ticker: str,
    days_back: int = 30,
    shared_swarm_data: dict = None,
    etf_context: dict = None,
) -> NewsHoundOutput:
    """
    Analyze news sentiment and catalysts for a company or ETF.

    Args:
        ticker: Stock ticker (e.g., "NVDA") or ETF symbol (e.g., "SPY")
        days_back: Number of days to look back (default 30)
        shared_swarm_data: Pre-fetched data bundle from Manager
        etf_context: Optional ETF context dict with fund_name and sector_weights (for ETF mode)

    Returns:
        NewsHoundOutput with complete analysis

    Raises:
        ValueError: If analysis fails
    """
    logger.info(f"=== Analyzing news for {ticker} (last {days_back} days) ===")

    start_time = time.time()

    # Phase A: the graph nodes never fetch mid-run. When the caller didn't
    # supply an equity bundle (standalone run, or the ETF path whose bundle
    # only carries etf_data), assemble the market sections once, up front.
    if not shared_swarm_data or "short_interest" not in shared_swarm_data:
        from research_swarm.data.snapshot_assembler import assemble_market_bundle
        market_bundle = assemble_market_bundle(ticker)
        shared_swarm_data = {**market_bundle, **(shared_swarm_data or {})}

    # ETF mode: build sector context to enrich news analysis
    etf_system_addendum = ""
    if etf_context:
        fund_name = etf_context.get("fund_name", ticker)
        sector_weights = etf_context.get("sector_weights", {})
        top_sectors = sorted(sector_weights.items(), key=lambda x: x[1], reverse=True)[:2]
        sector_names = [s[0] for s in top_sectors]
        etf_system_addendum = f"""

IMPORTANT: You are analyzing an ETF ({ticker} — {fund_name}), not a single company.
Focus on:
- Sector-level macro events, policy changes, and rate environment impacts for sectors: {', '.join(sector_names)}
- Fund flow trends for this ETF or sector
- Earnings cycle momentum for the underlying sector
- Regulatory or thematic tailwinds/headwinds for this sector
Do NOT focus on individual company earnings unless it represents a major sector theme."""

        logger.info(f"[ETF News Hound] Enriched with sector context: {sector_names}")

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
        "etf_system_addendum": etf_system_addendum,  # NEW: ETF sector context enrichment
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
