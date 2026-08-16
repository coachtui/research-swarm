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

analyzer = NewsAnalyzer()
