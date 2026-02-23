"""
News Analysis Module.

Extracts catalyst events and performs sentiment analysis on news articles.
"""
import json
import math
import pandas as pd
from typing import List, Dict, Any, Tuple, Optional
from langchain_anthropic import ChatAnthropic
from research_swarm.logger import logger
from research_swarm.config import settings
from research_swarm.utils import extract_token_usage
from research_swarm.agents.news_hound.prompts import (
    CATALYST_EXTRACTION_PROMPT,
    REGULATORY_EXTRACTION_PROMPT,
    SENTIMENT_ANALYSIS_PROMPT,
    EARNINGS_ESTIMATE_REVISION_PROMPT,
    ANALYST_CONSENSUS_PROMPT,
    INSTITUTIONAL_ACTIVITY_PROMPT,
    INSIDER_ACTIVITY_PROMPT,
    SHORT_INTEREST_PROMPT,
    UPCOMING_CATALYSTS_PROMPT,
    MANAGEMENT_COMMENTARY_PROMPT
)
from research_swarm.agents.news_hound.models import (
    NewsArticle,
    CatalystEvent,
    EarningsEstimateRevision,
    AnalystConsensus,
    InstitutionalActivity,
    InsiderActivity,
    ManagementCommentary,
    ShortInterest,
    UpcomingCatalysts
)


class NewsAnalyzer:
    """Analyzes news articles to extract catalysts and sentiment."""

    def __init__(self):
        """Initialize analyzer with LLM models."""
        # Haiku for cost-effective extraction
        self.haiku = ChatAnthropic(
            model="claude-haiku-4-5-20251001",
            api_key=settings.anthropic_api_key,
            temperature=0.0,
        )

        # Sonnet for nuanced sentiment analysis
        self.sonnet = ChatAnthropic(
            model="claude-sonnet-4-6",
            api_key=settings.anthropic_api_key,
            temperature=0.3,
        )

        logger.info("NewsAnalyzer initialized")

    def extract_catalysts(
        self,
        articles: List[NewsArticle],
        ticker: str,
        days_back: int
    ) -> Tuple[List[CatalystEvent], int]:
        """
        Extract catalyst events from news articles (9 categories).

        Args:
            articles: List of NewsArticle objects
            ticker: Stock ticker
            days_back: Number of days analyzed

        Returns:
            Tuple of (List of CatalystEvent objects, tokens_used)
        """
        if not articles:
            logger.warning(f"No articles to analyze for catalysts for {ticker}")
            return [], 0

        logger.info(f"Extracting catalysts from {len(articles)} articles for {ticker}")

        # Format articles for prompt (truncate content to first 500 chars)
        articles_text = self._format_articles_for_analysis(articles)

        prompt = CATALYST_EXTRACTION_PROMPT.format(
            ticker=ticker,
            days_back=days_back,
            articles_text=articles_text
        )

        try:
            response = self.haiku.invoke(prompt)
            response_text = response.content.strip()
            tokens_used = extract_token_usage(response.response_metadata)

            # Extract JSON from response
            json_text = self._extract_json(response_text)
            catalyst_data = json.loads(json_text)

            # Parse catalysts into Pydantic models
            catalysts = []
            for cat_dict in catalyst_data.get("catalysts", []):
                try:
                    catalyst = CatalystEvent(**cat_dict)
                    catalysts.append(catalyst)
                except Exception as e:
                    logger.debug(f"Failed to validate catalyst: {e}")
                    continue

            logger.success(f"✓ Extracted {len(catalysts)} catalysts for {ticker} ({tokens_used} tokens)")
            return catalysts, tokens_used

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse catalyst JSON: {e}")
            logger.debug(f"Response: {response_text[:500]}")
            # Return empty list but track tokens used (API was called)
            return [], tokens_used

        except Exception as e:
            logger.error(f"Error extracting catalysts: {e}")
            # Return 0 tokens for general errors (API call may not have completed)
            return [], 0

    def extract_regulatory_events(
        self,
        articles: List[NewsArticle],
        ticker: str
    ) -> Tuple[List[CatalystEvent], int]:
        """
        Extract regulatory events from news articles with high detail.

        Args:
            articles: List of NewsArticle objects
            ticker: Stock ticker

        Returns:
            Tuple of (List of CatalystEvent objects (regulatory type), tokens_used)
        """
        if not articles:
            return [], 0

        logger.info(f"Extracting regulatory events from {len(articles)} articles for {ticker}")

        # Format articles for prompt
        articles_text = self._format_articles_for_analysis(articles)

        prompt = REGULATORY_EXTRACTION_PROMPT.format(
            ticker=ticker,
            articles_text=articles_text
        )

        try:
            response = self.haiku.invoke(prompt)
            response_text = response.content.strip()
            tokens_used = extract_token_usage(response.response_metadata)

            # Extract JSON from response
            json_text = self._extract_json(response_text)
            reg_data = json.loads(json_text)

            # Parse regulatory events into Pydantic models
            reg_events = []
            for event_dict in reg_data.get("regulatory_events", []):
                try:
                    event = CatalystEvent(**event_dict)
                    reg_events.append(event)
                except Exception as e:
                    logger.debug(f"Failed to validate regulatory event: {e}")
                    continue

            if reg_events:
                logger.success(f"✓ Extracted {len(reg_events)} regulatory events for {ticker} ({tokens_used} tokens)")
            else:
                logger.info(f"No regulatory events detected for {ticker}")

            return reg_events, tokens_used

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse regulatory JSON: {e}")
            logger.debug(f"Response: {response_text[:500]}")
            # Return empty list but track tokens used (API was called)
            return [], tokens_used

        except Exception as e:
            logger.error(f"Error extracting regulatory events: {e}")
            # Return 0 tokens for general errors (API call may not have completed)
            return [], 0

    def analyze_sentiment(
        self,
        articles: List[NewsArticle],
        catalyst_events: List[CatalystEvent],
        ticker: str,
        days_back: int
    ) -> Tuple[str, int]:
        """
        Perform nuanced sentiment analysis on news coverage.

        Args:
            articles: List of NewsArticle objects
            catalyst_events: Detected catalyst events
            ticker: Stock ticker
            days_back: Number of days analyzed

        Returns:
            Tuple of (sentiment analysis narrative, tokens_used)
        """
        if not articles:
            logger.warning(f"No articles for sentiment analysis for {ticker}")
            return "No news articles available for sentiment analysis.", 0

        logger.info(f"Analyzing sentiment for {ticker} ({len(articles)} articles, {len(catalyst_events)} catalysts)")

        # Format articles for prompt (limit to first 20 to control token usage)
        articles_subset = articles[:20]
        articles_text = self._format_articles_for_analysis(articles_subset)

        # Format catalyst events
        catalysts_text = self._format_catalysts_for_prompt(catalyst_events)

        prompt = SENTIMENT_ANALYSIS_PROMPT.format(
            ticker=ticker,
            days_back=days_back,
            article_count=len(articles),
            articles_text=articles_text,
            catalyst_events=catalysts_text
        )

        try:
            response = self.sonnet.invoke(prompt)
            sentiment_analysis = response.content.strip()
            tokens_used = extract_token_usage(response.response_metadata)

            logger.success(
                f"✓ Generated sentiment analysis for {ticker} ({len(sentiment_analysis)} chars, {tokens_used} tokens)"
            )
            return sentiment_analysis, tokens_used

        except Exception as e:
            logger.error(f"Error in sentiment analysis: {e}")
            return f"Error performing sentiment analysis: {str(e)}", 0

    def batch_analyze(
        self,
        articles: List[NewsArticle],
        ticker: str,
        days_back: int
    ) -> Tuple[Dict[str, Any], int]:
        """
        Perform all analysis steps in batch: catalysts, regulatory, sentiment.

        Args:
            articles: List of NewsArticle objects
            ticker: Stock ticker
            days_back: Number of days analyzed

        Returns:
            Tuple of (Dict with all analysis results, total_tokens_used)
        """
        logger.info(f"Batch analyzing {len(articles)} articles for {ticker}")
        total_tokens = 0

        # Extract all catalysts (including regulatory via main extraction)
        catalysts, cat_tokens = self.extract_catalysts(articles, ticker, days_back)
        total_tokens += cat_tokens

        # Additional pass for regulatory events if needed (optional enhancement)
        # For now, regulatory events are part of catalyst extraction

        # Perform sentiment analysis
        sentiment_analysis, sent_tokens = self.analyze_sentiment(articles, catalysts, ticker, days_back)
        total_tokens += sent_tokens

        return {
            "catalyst_events": catalysts,
            "sentiment_analysis": sentiment_analysis
        }, total_tokens

    def _format_articles_for_analysis(
        self,
        articles: List[NewsArticle],
        max_articles: int = 30
    ) -> str:
        """
        Format articles for analysis prompts.

        Args:
            articles: List of NewsArticle objects
            max_articles: Maximum number of articles to include

        Returns:
            Formatted articles text
        """
        formatted = []

        # Limit to max_articles to control token usage
        articles_subset = articles[:max_articles]

        for i, article in enumerate(articles_subset, 1):
            # Get combined text (title + description + truncated content)
            text = article.get_text()

            # Truncate to 600 chars total
            if len(text) > 600:
                text = text[:600] + "..."

            formatted.append(
                f"{i}. **{article.title}** ({article.source}, {article.published_at[:10]})\n"
                f"   {text}\n"
                f"   URL: {article.url}\n"
            )

        if len(articles) > max_articles:
            formatted.append(f"\n... and {len(articles) - max_articles} more articles")

        return "\n".join(formatted)

    def _format_catalysts_for_prompt(self, catalysts: List[CatalystEvent]) -> str:
        """
        Format catalyst events for sentiment analysis prompt.

        Args:
            catalysts: List of CatalystEvent objects

        Returns:
            Formatted catalysts text
        """
        if not catalysts:
            return "No catalyst events detected."

        formatted = []
        for i, catalyst in enumerate(catalysts, 1):
            date_str = f" ({catalyst.date})" if catalyst.date else ""
            formatted.append(
                f"{i}. [{catalyst.event_type}] {catalyst.description}{date_str}\n"
                f"   Impact: {catalyst.impact} | Confidence: {catalyst.confidence:.2f}"
            )

        return "\n".join(formatted)

    def _extract_json(self, text: str) -> str:
        """
        Extract JSON from text that may contain markdown code blocks or preamble text.

        Args:
            text: Response text potentially containing JSON

        Returns:
            Extracted JSON string
        """
        text = text.strip()

        # Try markdown code blocks first
        if "```json" in text:
            start = text.find("```json") + 7
            end = text.find("```", start)
            if end > start:
                return text[start:end].strip()
        elif "```" in text:
            start = text.find("```") + 3
            end = text.find("```", start)
            if end > start:
                return text[start:end].strip()

        # Fallback: find JSON object boundaries (handles preamble text before JSON)
        first_brace = text.find("{")
        last_brace = text.rfind("}")
        if first_brace != -1 and last_brace > first_brace:
            return text[first_brace:last_brace + 1]

        # Last resort: return as-is and let json.loads fail with useful error
        return text

    def analyze_earnings_estimates(
        self,
        estimates_data: Optional[pd.DataFrame],
        recommendations_data: Optional[pd.DataFrame],
        ticker: str,
        analysis_date: str
    ) -> Tuple[Dict[str, Any], int]:
        """
        Analyze earnings estimate revisions (PRIMARY SIGNAL).

        Args:
            estimates_data: DataFrame from get_earnings_estimates()
            recommendations_data: DataFrame from get_analyst_recommendations()
            ticker: Stock ticker
            analysis_date: Analysis date

        Returns:
            Tuple of (earnings_estimates_dict, tokens_used)
        """
        from research_swarm.agents.news_hound.prompts import EARNINGS_ESTIMATE_REVISION_PROMPT
        from research_swarm.data.analyst_data_formatter import format_yf_analyst_recommendations

        logger.info(f"Analyzing earnings estimates for {ticker}")

        # Format data for prompt
        estimates_text = "No forward estimates available"
        if estimates_data is not None and not estimates_data.empty:
            estimates_text = estimates_data.to_string()

        recommendations_text = "No recent analyst activity"
        if recommendations_data is not None and not recommendations_data.empty:
            recommendations_text = recommendations_data.to_string()

        # Build prompt
        prompt = EARNINGS_ESTIMATE_REVISION_PROMPT.format(
            ticker=ticker,
            analysis_date=analysis_date,
            estimate_data=estimates_text,
            earnings_news="No earnings-related news available for estimate revision context",
            recent_recommendations=recommendations_text
        )

        try:
            # Use Sonnet for this critical PRIMARY SIGNAL analysis
            response = self.sonnet.invoke(prompt)
            response_text = response.content.strip()
            tokens_used = extract_token_usage(response.response_metadata)

            # Extract JSON from response
            json_text = self._extract_json(response_text)
            result = json.loads(json_text)

            logger.info(f"✓ Earnings estimates analyzed ({tokens_used} tokens)")
            return result, tokens_used

        except Exception as e:
            logger.error(f"Error analyzing earnings estimates: {e}")
            # Return neutral defaults
            return {
                "current_quarter_eps": None,
                "current_fy_eps": None,
                "next_fy_eps": None,
                "upward_revisions": 0,
                "downward_revisions": 0,
                "net_revision_direction": "neutral",
                "analyst_coverage": 0,
                "estimate_dispersion": "unknown",
                "estimate_agreement": 0.5,
                "surprise_history": [],
                "beat_pattern": "unknown",
                "current_year_growth_pct": None,
                "next_year_growth_pct": None,
                "momentum": "neutral",
                "two_year_cagr": None
            }, 0

    def analyze_analyst_consensus(
        self,
        recommendations_data: Optional[pd.DataFrame],
        price_targets: Optional[Dict[str, Any]],
        ticker: str,
        analysis_date: str
    ) -> Tuple[Dict[str, Any], int]:
        """
        Analyze analyst consensus ratings and price targets.

        Args:
            recommendations_data: DataFrame from get_analyst_recommendations()
            price_targets: Dict from get_analyst_price_target()
            ticker: Stock ticker
            analysis_date: Analysis date

        Returns:
            Tuple of (analyst_consensus_dict, tokens_used)
        """
        from research_swarm.agents.news_hound.prompts import ANALYST_CONSENSUS_PROMPT
        from research_swarm.data.analyst_data_formatter import (
            format_yf_analyst_recommendations,
            format_yf_price_targets
        )

        logger.info(f"Analyzing analyst consensus for {ticker}")

        # Format data for prompt
        recommendations_text = "No analyst recommendations available"
        if recommendations_data is not None and not recommendations_data.empty:
            recommendations_text = recommendations_data.to_string()

        targets_text = "No price target data available"
        if price_targets:
            targets_text = format_yf_price_targets(price_targets)

        # Build prompt
        prompt = ANALYST_CONSENSUS_PROMPT.format(
            ticker=ticker,
            analysis_date=analysis_date,
            analyst_data=f"{recommendations_text}\n\n**Price Targets:**\n{targets_text}",
            analyst_news="No recent analyst actions from news"
        )

        try:
            # Use Haiku for this extraction task
            response = self.haiku.invoke(prompt)
            response_text = response.content.strip()
            tokens_used = extract_token_usage(response.response_metadata)

            # Extract JSON from response
            json_text = self._extract_json(response_text)
            result = json.loads(json_text)

            logger.info(f"✓ Analyst consensus analyzed ({tokens_used} tokens)")
            return result, tokens_used

        except Exception as e:
            logger.error(f"Error analyzing analyst consensus: {e}")
            return {
                "strong_buy": 0,
                "buy": 0,
                "hold": 0,
                "sell": 0,
                "strong_sell": 0,
                "consensus_rating": "hold",
                "avg_price_target": None,
                "high_price_target": None,
                "low_price_target": None,
                "target_upside_pct": None,
                "upgrades_90d": 0,
                "downgrades_90d": 0,
                "new_coverage_90d": 0,
                "rating_momentum": "neutral",
                "consensus_confidence": 0.5
            }, 0

    def analyze_institutional_activity(
        self,
        institutional_data: Optional[pd.DataFrame],
        ticker: str,
        analysis_date: str
    ) -> Tuple[Dict[str, Any], int]:
        """
        Analyze institutional activity (13F smart money flows).

        Args:
            institutional_data: DataFrame from get_institutional_holders()
            ticker: Stock ticker
            analysis_date: Analysis date

        Returns:
            Tuple of (institutional_activity_dict, tokens_used)
        """
        from research_swarm.agents.news_hound.prompts import INSTITUTIONAL_ACTIVITY_PROMPT
        from research_swarm.data.analyst_data_formatter import format_yf_institutional_holders

        logger.info(f"Analyzing institutional activity for {ticker}")

        # Format data for prompt
        institutional_text = "No institutional holdings data available"
        if institutional_data is not None and not institutional_data.empty:
            institutional_text = format_yf_institutional_holders(
                institutional_data.to_dict(orient="records")
            )

        # Build prompt
        prompt = INSTITUTIONAL_ACTIVITY_PROMPT.format(
            ticker=ticker,
            analysis_date=analysis_date,
            filing_data=institutional_text,
            institutional_news="No recent institutional activity from news"
        )

        try:
            # Use Haiku for this extraction task
            response = self.haiku.invoke(prompt)
            response_text = response.content.strip()
            tokens_used = extract_token_usage(response.response_metadata)

            # Extract JSON from response
            json_text = self._extract_json(response_text)
            result = json.loads(json_text)

            logger.info(f"✓ Institutional activity analyzed ({tokens_used} tokens)")
            return result, tokens_used

        except Exception as e:
            logger.error(f"Error analyzing institutional activity: {e}")
            return {
                "institutional_ownership_pct": None,
                "qoq_change_pct": None,
                "num_holders": 0,
                "top_holders": [],
                "notable_activity": [],
                "institutional_sentiment": "neutral"
            }, 0

    def analyze_dark_pool_activity(
        self,
        dark_pool_data: Optional[List[Dict]],
        institutional_context: Optional[str],
        ticker: str,
        analysis_date: str
    ) -> Tuple[Dict[str, Any], int]:
        """
        Analyze dark pool (ATS) activity from FINRA data.

        Args:
            dark_pool_data: List of weekly dark pool records from FINRA
            institutional_context: Context from 13F data (for cross-reference)
            ticker: Stock ticker
            analysis_date: Analysis date

        Returns:
            Tuple of (dark_pool_activity_dict, tokens_used)
        """
        from research_swarm.agents.news_hound.prompts import DARK_POOL_ACTIVITY_PROMPT

        logger.info(f"Analyzing dark pool activity for {ticker}")

        # --- Pre-compute stock-specific baseline before LLM call ---
        # Requires >= 5 weeks; recent = last 4 weeks, baseline = everything older.
        baseline_avg_ats_pct: float | None = None
        baseline_std_ats_pct: float | None = None
        z_score: float | None = None
        baseline_context = "No historical baseline available (need >= 5 weeks of data)"

        if dark_pool_data:
            ats_pcts_all = [w["ats_pct"] for w in dark_pool_data if w.get("ats_pct") is not None]
            if len(ats_pcts_all) >= 5:
                recent_window = ats_pcts_all[-4:]
                baseline_window = ats_pcts_all[:-4]
                recent_avg = sum(recent_window) / len(recent_window)
                b_avg = sum(baseline_window) / len(baseline_window)
                variance = sum((x - b_avg) ** 2 for x in baseline_window) / len(baseline_window)
                b_std = math.sqrt(variance) if variance > 0 else 1.0
                baseline_avg_ats_pct = round(b_avg, 2)
                baseline_std_ats_pct = round(b_std, 2)
                z_score = round((recent_avg - b_avg) / b_std, 2) if b_std > 0 else 0.0
                deviation_pp = round(recent_avg - b_avg, 2)
                direction = "above" if deviation_pp >= 0 else "below"
                normal_lo = round(b_avg - 2 * b_std, 1)
                normal_hi = round(b_avg + 2 * b_std, 1)
                baseline_context = (
                    f"Historical baseline ({len(baseline_window)} weeks): "
                    f"avg={baseline_avg_ats_pct}% ATS, std={baseline_std_ats_pct}%. "
                    f"Current 4-week avg ({recent_avg:.1f}%) is "
                    f"{abs(deviation_pp):.1f}pp {direction} baseline "
                    f"(z-score: {z_score:+.2f}). "
                    f"This stock's normal ATS range is approx {normal_lo}%–{normal_hi}%."
                )
                logger.debug(
                    f"Dark pool baseline for {ticker}: avg={baseline_avg_ats_pct}% "
                    f"std={baseline_std_ats_pct}% z={z_score:+.2f}"
                )

        # Format raw weekly data for prompt
        if dark_pool_data:
            dark_pool_text = "Weekly Dark Pool Data (FINRA):\n"
            for week in dark_pool_data:
                dark_pool_text += f"- Week ending {week.get('week_ending', 'N/A')}: "
                ats_pct = week.get('ats_pct')
                dark_pool_text += f"{ats_pct:.1f}% off-exchange " if ats_pct is not None else "N/A% off-exchange "
                dark_pool_text += f"({week.get('ats_shares', 0):,} shares), "
                venues = week.get('venues', [])
                if venues:
                    dark_pool_text += f"Top venues: {', '.join(venues[:3])}\n"
                else:
                    dark_pool_text += "\n"
        else:
            dark_pool_text = "No dark pool data available from FINRA"

        # Build prompt
        prompt = DARK_POOL_ACTIVITY_PROMPT.format(
            ticker=ticker,
            analysis_date=analysis_date,
            dark_pool_data=dark_pool_text,
            institutional_context=institutional_context or "No 13F context available",
            baseline_context=baseline_context
        )

        try:
            # Use Haiku for cost-effective analysis
            response = self.haiku.invoke(prompt)
            response_text = response.content.strip()
            tokens_used = extract_token_usage(response.response_metadata)

            # Extract JSON from response
            json_text = self._extract_json(response_text)
            result = json.loads(json_text)

            # Inject pre-computed baseline stats so signal_divergence can use them
            result["baseline_avg_ats_pct"] = baseline_avg_ats_pct
            result["baseline_std_ats_pct"] = baseline_std_ats_pct
            result["z_score"] = z_score

            logger.info(f"✓ Dark pool activity analyzed ({tokens_used} tokens)")
            return result, tokens_used

        except Exception as e:
            logger.error(f"Error analyzing dark pool activity: {e}")
            return {
                "avg_ats_pct": None,
                "trend": "stable",
                "trend_pct_change": None,
                "peak_week": None,
                "peak_ats_pct": None,
                "major_venues": [],
                "venue_concentration": "medium",
                "notable_patterns": [],
                "dark_pool_sentiment": "neutral",
                "confidence": "low",
                "baseline_avg_ats_pct": baseline_avg_ats_pct,
                "baseline_std_ats_pct": baseline_std_ats_pct,
                "z_score": z_score,
            }, 0

    def analyze_insider_activity(
        self,
        insider_data: Optional[pd.DataFrame],
        ticker: str,
        analysis_date: str
    ) -> Tuple[Dict[str, Any], int]:
        """
        Analyze insider trading activity.

        Args:
            insider_data: DataFrame from get_insider_transactions()
            ticker: Stock ticker
            analysis_date: Analysis date

        Returns:
            Tuple of (insider_activity_dict, tokens_used)
        """
        from research_swarm.agents.news_hound.prompts import INSIDER_ACTIVITY_PROMPT
        from research_swarm.data.analyst_data_formatter import format_yf_insider_transactions

        logger.info(f"Analyzing insider activity for {ticker}")

        # Format data for prompt
        insider_text = "No insider transactions available"
        if insider_data is not None and not insider_data.empty:
            insider_text = format_yf_insider_transactions(
                insider_data.to_dict(orient="records")
            )

        # Build prompt
        prompt = INSIDER_ACTIVITY_PROMPT.format(
            ticker=ticker,
            transaction_data=insider_text,
            insider_news="No recent insider trading news"
        )

        try:
            # Use Haiku for this extraction task
            response = self.haiku.invoke(prompt)
            response_text = response.content.strip()
            tokens_used = extract_token_usage(response.response_metadata)

            # Extract JSON from response
            json_text = self._extract_json(response_text)
            result = json.loads(json_text)

            logger.info(f"✓ Insider activity analyzed ({tokens_used} tokens)")
            return result, tokens_used

        except Exception as e:
            logger.error(f"Error analyzing insider activity: {e}")
            return {
                "buy_transactions": 0,
                "sell_transactions": 0,
                "buy_shares": 0,
                "sell_shares": 0,
                "buy_value": 0,
                "sell_value": 0,
                "notable_transactions": [],
                "insider_ownership_pct": None,
                "ceo_ownership_pct": None,
                "ownership_trend": "stable",
                "insider_sentiment": "neutral",
                "confidence": 0.5
            }, 0

    def analyze_short_interest(
        self,
        short_data: Optional[Dict[str, Any]],
        ticker: str,
        analysis_date: str
    ) -> Tuple[Dict[str, Any], int]:
        """
        Analyze short interest and squeeze risk.

        Args:
            short_data: Dict from get_short_interest()
            ticker: Stock ticker
            analysis_date: Analysis date

        Returns:
            Tuple of (short_interest_dict, tokens_used)
        """
        from research_swarm.agents.news_hound.prompts import SHORT_INTEREST_PROMPT

        logger.info(f"Analyzing short interest for {ticker}")

        # Format data for prompt
        short_text = "No short interest data available"
        if short_data:
            # yfinance returns shortPercentOfFloat as a decimal fraction (e.g. 0.034 = 3.4%)
            raw_pct = short_data.get('short_percent_float')
            pct_str = f"{raw_pct * 100:.2f}" if raw_pct is not None else "N/A"

            def fmt_shares(val):
                return f"{int(val):,}" if val is not None else "N/A"

            short_text = f"""
Short % of Float: {pct_str}%
Shares Short: {fmt_shares(short_data.get('shares_short'))}
Shares Short (Prior Month): {fmt_shares(short_data.get('shares_short_prior_month'))}
Days to Cover: {short_data.get('short_ratio', 'N/A')}
Float Shares: {fmt_shares(short_data.get('float_shares'))}
Shares Outstanding: {fmt_shares(short_data.get('shares_outstanding'))}
"""

        # Build prompt
        prompt = SHORT_INTEREST_PROMPT.format(
            ticker=ticker,
            analysis_date=analysis_date,
            short_data=short_text,
            short_news="No recent short seller news or reports"
        )

        try:
            # Use Haiku for this extraction task
            response = self.haiku.invoke(prompt)
            response_text = response.content.strip()
            tokens_used = extract_token_usage(response.response_metadata)

            # Extract JSON from response
            json_text = self._extract_json(response_text)
            result = json.loads(json_text)

            logger.info(f"✓ Short interest analyzed ({tokens_used} tokens)")
            return result, tokens_used

        except Exception as e:
            logger.error(f"Error analyzing short interest: {e}")
            return {
                "short_interest_pct": None,
                "short_interest_shares": None,
                "days_to_cover": None,
                "short_interest_trend": "unknown",
                "mom_change_pct": None,
                "squeeze_risk": "unknown",
                "short_sentiment": "neutral",
                "squeeze_triggers": [],
                "notable_short_activity": []
            }, 0

    def analyze_upcoming_catalysts(
        self,
        earnings_dates: Optional[pd.DataFrame],
        catalyst_events: List[CatalystEvent],
        ticker: str,
        analysis_date: str
    ) -> Tuple[Dict[str, Any], int]:
        """
        Analyze upcoming catalysts calendar.

        Args:
            earnings_dates: DataFrame from get_earnings_dates()
            catalyst_events: List of CatalystEvent from news
            ticker: Stock ticker
            analysis_date: Analysis date

        Returns:
            Tuple of (upcoming_catalysts_dict, tokens_used)
        """
        from research_swarm.agents.news_hound.prompts import UPCOMING_CATALYSTS_PROMPT

        logger.info(f"Analyzing upcoming catalysts for {ticker}")

        # Format earnings calendar
        earnings_text = "No upcoming earnings dates available"
        if earnings_dates is not None and not earnings_dates.empty:
            earnings_text = earnings_dates.to_string()

        # Format detected catalysts
        detected_text = "No detected catalysts from news"
        if catalyst_events:
            detected_text = "\n".join([
                f"- {cat.event_type}: {cat.description} ({cat.impact})"
                for cat in catalyst_events[:10]
            ])

        # Build prompt
        prompt = UPCOMING_CATALYSTS_PROMPT.format(
            ticker=ticker,
            analysis_date=analysis_date,
            earnings_calendar=earnings_text,
            upcoming_events_news=detected_text,
            company_announcements="No recent company announcements available"
        )

        try:
            # Use Haiku for this extraction task
            response = self.haiku.invoke(prompt)
            response_text = response.content.strip()
            tokens_used = extract_token_usage(response.response_metadata)

            # Extract JSON from response
            json_text = self._extract_json(response_text)
            result = json.loads(json_text)

            logger.info(f"✓ Upcoming catalysts analyzed ({tokens_used} tokens)")
            return result, tokens_used

        except Exception as e:
            logger.error(f"Error analyzing upcoming catalysts: {e}")
            return {
                "events": [],
                "next_earnings_date": None,
                "next_earnings_importance": "medium",
                "near_term_catalysts": [],
                "medium_term_catalysts": [],
                "catalyst_density": "low"
            }, 0

    def analyze_management_commentary(
        self,
        earnings_articles: List[NewsArticle],
        ticker: str,
        analysis_date: str
    ) -> Tuple[Dict[str, Any], int]:
        """
        Analyze management commentary and guidance quality.

        Args:
            earnings_articles: News articles about earnings calls
            ticker: Stock ticker
            analysis_date: Analysis date

        Returns:
            Tuple of (management_commentary_dict, tokens_used)
        """
        from research_swarm.agents.news_hound.prompts import MANAGEMENT_COMMENTARY_PROMPT

        logger.info(f"Analyzing management commentary for {ticker}")

        # Format earnings-related articles
        articles_text = "No earnings-related news available"
        if earnings_articles:
            articles_text = self._format_articles_for_analysis(earnings_articles, max_articles=10)

        # Build prompt
        prompt = MANAGEMENT_COMMENTARY_PROMPT.format(
            ticker=ticker,
            analysis_date=analysis_date,
            earnings_call_data="No earnings call transcripts available",
            management_news=articles_text,
            guidance_history="No guidance history available"
        )

        try:
            # Use Sonnet for this nuanced analysis
            response = self.sonnet.invoke(prompt)
            response_text = response.content.strip()
            tokens_used = extract_token_usage(response.response_metadata)

            # Extract JSON from response
            json_text = self._extract_json(response_text)
            result = json.loads(json_text)

            logger.info(f"✓ Management commentary analyzed ({tokens_used} tokens)")
            return result, tokens_used

        except Exception as e:
            logger.error(f"Error analyzing management commentary: {e}")
            return {
                "guidance_raised": False,
                "guidance_lowered": False,
                "guidance_maintained": True,
                "management_tone": "neutral",
                "transparency": "medium",
                "key_themes": [],
                "red_flag_language": [],
                "guidance_track_record": "unknown",
                "capital_allocation_quality": "unknown",
                "strategic_clarity": "medium"
            }, 0


# Global analyzer instance
analyzer = NewsAnalyzer()
