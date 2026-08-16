"""
News Analysis Module.

Extracts catalyst events and performs sentiment analysis on news articles.
"""
import json
import math
import pandas as pd
from typing import List, Dict, Any, Tuple, Optional
from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage
from research_swarm.logger import logger
from research_swarm.config import settings
from research_swarm.utils import extract_token_usage
from research_swarm.agents.news_hound.prompts import (
    EARNINGS_ESTIMATE_REVISION_PROMPT,
    UPCOMING_CATALYSTS_PROMPT,
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
            max_tokens=4096,
        )

        # Sonnet for nuanced sentiment analysis
        # max_tokens must be set explicitly — LangChain defaults to 1024 and
        # silently truncates the narrative output.
        self.sonnet = ChatAnthropic(
            model="claude-sonnet-4-6",
            api_key=settings.anthropic_api_key,
            temperature=0.3,
            max_tokens=8192,
        )

        logger.info("NewsAnalyzer initialized")

    def interpret_news(
        self,
        articles: List[NewsArticle],
        ticker: str,
        days_back: int,
        analysis_date: str = "",
        system_addendum: str = "",
    ) -> Tuple[Dict[str, Any], int]:
        """
        One structured Sonnet call over the article set producing catalysts
        (regulatory included), the sentiment narrative + 4-dimension breakdown,
        and management commentary. Replaces five separate LLM calls (catalyst
        extraction, regulatory extraction, sentiment narrative, sentiment
        scoring, management commentary) that each re-read the same articles.

        Returns:
            Tuple of (interpretation dict, tokens_used). The dict carries:
            catalysts (List[CatalystEvent]), sentiment_narrative (str),
            sentiment_breakdown (dict), sentiment_confidence (float),
            management_commentary (dict | None).
        """
        from research_swarm.agents.news_hound.prompts import NEWS_INTERPRETATION_PROMPT

        empty: Dict[str, Any] = {
            "catalysts": [],
            "sentiment_narrative": "",
            "sentiment_breakdown": None,
            "sentiment_confidence": None,
            "management_commentary": None,
        }
        if not articles:
            logger.warning(f"No articles to interpret for {ticker}")
            return empty, 0

        logger.info(f"Interpreting {len(articles)} articles for {ticker} (single pass)")

        articles_text = self._format_articles_for_analysis(articles)
        prompt = NEWS_INTERPRETATION_PROMPT.format(
            ticker=ticker,
            analysis_date=analysis_date,
            days_back=days_back,
            article_count=len(articles),
            articles_text=articles_text,
        )
        if system_addendum:
            prompt = prompt + "\n\n" + system_addendum

        tokens_used = 0
        try:
            response = self.sonnet.invoke([HumanMessage(content=[{
                "type": "text",
                "text": prompt,
                "cache_control": {"type": "ephemeral"},
            }])])
            tokens_used = extract_token_usage(response.response_metadata)
            data = json.loads(self._extract_json(response.content.strip()))

            catalysts: List[CatalystEvent] = []
            for cat_dict in data.get("catalysts", []):
                try:
                    catalysts.append(CatalystEvent(**cat_dict))
                except Exception as e:
                    logger.debug(f"Failed to validate catalyst: {e}")

            result = {
                "catalysts": catalysts,
                "sentiment_narrative": data.get("sentiment_narrative") or "",
                "sentiment_breakdown": data.get("sentiment_breakdown"),
                "sentiment_confidence": data.get("sentiment_confidence"),
                "management_commentary": data.get("management_commentary"),
            }
            logger.success(
                f"✓ Interpreted news for {ticker}: {len(catalysts)} catalysts, "
                f"narrative {len(result['sentiment_narrative'])} chars ({tokens_used} tokens)"
            )
            return result, tokens_used

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse news interpretation JSON: {e}")
            return empty, tokens_used
        except Exception as e:
            logger.error(f"Error interpreting news: {e}")
            return empty, tokens_used

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
            result = self._filter_past_catalysts(result, analysis_date)

            logger.info(f"✓ Upcoming catalysts analyzed ({tokens_used} tokens)")
            return result, tokens_used

        except Exception as e:
            logger.error(f"Error analyzing upcoming catalysts: {e}")
            # Match the success-path schema so downstream consumers
            # (catalyst calendar formatter, next-catalyst summary, frontend)
            # never see a divergent shape.
            return {
                "outlook": "Neutral",
                "catalysts": [],
                "catalyst_density": "low",
                "earnings_confirmed": False,
                "next_earnings_date": None,
            }, 0

    @staticmethod
    def _filter_past_catalysts(result: Dict[str, Any], analysis_date: str) -> Dict[str, Any]:
        """Drop calendar entries dated before the analysis date.

        The prompt instructs the model to only return future events, but stale
        earnings-calendar cache entries can leak through (e.g. a Q1 earnings
        date returned as "upcoming" in July). Entries whose dates don't parse
        as YYYY-MM-DD (e.g. "2026-Q3") are kept.
        """
        from datetime import date

        try:
            cutoff = date.fromisoformat(str(analysis_date)[:10])
        except ValueError:
            return result

        def is_future(value: Any) -> bool:
            try:
                return date.fromisoformat(str(value)[:10]) >= cutoff
            except (TypeError, ValueError):
                return True

        catalysts = result.get("catalysts")
        if isinstance(catalysts, list):
            kept = [
                c for c in catalysts
                if not isinstance(c, dict) or is_future(c.get("event_date"))
            ]
            if len(kept) < len(catalysts):
                logger.warning(
                    f"Dropped {len(catalysts) - len(kept)} past-dated catalyst(s) from calendar"
                )
            result["catalysts"] = kept

        next_earnings = result.get("next_earnings_date")
        if next_earnings and not is_future(next_earnings):
            logger.warning(f"next_earnings_date {next_earnings} is in the past — clearing")
            result["next_earnings_date"] = None
            result["earnings_confirmed"] = False

        return result

analyzer = NewsAnalyzer()
