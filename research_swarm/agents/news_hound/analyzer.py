"""
News Analysis Module.

Extracts catalyst events and performs sentiment analysis on news articles.
"""
import json
from typing import List, Dict, Any
from langchain_anthropic import ChatAnthropic
from research_swarm.logger import logger
from research_swarm.config import settings
from research_swarm.agents.news_hound.prompts import (
    CATALYST_EXTRACTION_PROMPT,
    REGULATORY_EXTRACTION_PROMPT,
    SENTIMENT_ANALYSIS_PROMPT
)
from research_swarm.agents.news_hound.models import (
    NewsArticle,
    CatalystEvent
)


class NewsAnalyzer:
    """Analyzes news articles to extract catalysts and sentiment."""

    def __init__(self):
        """Initialize analyzer with LLM models."""
        # Haiku for cost-effective extraction
        self.haiku = ChatAnthropic(
            model="claude-3-5-haiku-20241022",
            api_key=settings.anthropic_api_key,
            temperature=0.0,
        )

        # Sonnet for nuanced sentiment analysis
        self.sonnet = ChatAnthropic(
            model="claude-3-sonnet-20240229",
            api_key=settings.anthropic_api_key,
            temperature=0.3,
        )

        logger.info("NewsAnalyzer initialized")

    def extract_catalysts(
        self,
        articles: List[NewsArticle],
        ticker: str,
        days_back: int
    ) -> List[CatalystEvent]:
        """
        Extract catalyst events from news articles (9 categories).

        Args:
            articles: List of NewsArticle objects
            ticker: Stock ticker
            days_back: Number of days analyzed

        Returns:
            List of CatalystEvent objects
        """
        if not articles:
            logger.warning(f"No articles to analyze for catalysts for {ticker}")
            return []

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

            logger.success(f"✓ Extracted {len(catalysts)} catalysts for {ticker}")
            return catalysts

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse catalyst JSON: {e}")
            logger.debug(f"Response: {response_text[:500]}")
            return []

        except Exception as e:
            logger.error(f"Error extracting catalysts: {e}")
            return []

    def extract_regulatory_events(
        self,
        articles: List[NewsArticle],
        ticker: str
    ) -> List[CatalystEvent]:
        """
        Extract regulatory events from news articles with high detail.

        Args:
            articles: List of NewsArticle objects
            ticker: Stock ticker

        Returns:
            List of CatalystEvent objects (regulatory type)
        """
        if not articles:
            return []

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
                logger.success(f"✓ Extracted {len(reg_events)} regulatory events for {ticker}")
            else:
                logger.info(f"No regulatory events detected for {ticker}")

            return reg_events

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse regulatory JSON: {e}")
            logger.debug(f"Response: {response_text[:500]}")
            return []

        except Exception as e:
            logger.error(f"Error extracting regulatory events: {e}")
            return []

    def analyze_sentiment(
        self,
        articles: List[NewsArticle],
        catalyst_events: List[CatalystEvent],
        ticker: str,
        days_back: int
    ) -> str:
        """
        Perform nuanced sentiment analysis on news coverage.

        Args:
            articles: List of NewsArticle objects
            catalyst_events: Detected catalyst events
            ticker: Stock ticker
            days_back: Number of days analyzed

        Returns:
            Sentiment analysis narrative (2-3 paragraphs)
        """
        if not articles:
            logger.warning(f"No articles for sentiment analysis for {ticker}")
            return "No news articles available for sentiment analysis."

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

            logger.success(
                f"✓ Generated sentiment analysis for {ticker} ({len(sentiment_analysis)} chars)"
            )
            return sentiment_analysis

        except Exception as e:
            logger.error(f"Error in sentiment analysis: {e}")
            return f"Error performing sentiment analysis: {str(e)}"

    def batch_analyze(
        self,
        articles: List[NewsArticle],
        ticker: str,
        days_back: int
    ) -> Dict[str, Any]:
        """
        Perform all analysis steps in batch: catalysts, regulatory, sentiment.

        Args:
            articles: List of NewsArticle objects
            ticker: Stock ticker
            days_back: Number of days analyzed

        Returns:
            Dict with all analysis results
        """
        logger.info(f"Batch analyzing {len(articles)} articles for {ticker}")

        # Extract all catalysts (including regulatory via main extraction)
        catalysts = self.extract_catalysts(articles, ticker, days_back)

        # Additional pass for regulatory events if needed (optional enhancement)
        # For now, regulatory events are part of catalyst extraction

        # Perform sentiment analysis
        sentiment_analysis = self.analyze_sentiment(articles, catalysts, ticker, days_back)

        return {
            "catalyst_events": catalysts,
            "sentiment_analysis": sentiment_analysis
        }

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
        Extract JSON from text that may contain markdown code blocks.

        Args:
            text: Response text potentially containing JSON

        Returns:
            Extracted JSON string
        """
        # Remove markdown code blocks if present
        if "```json" in text:
            start = text.find("```json") + 7
            end = text.find("```", start)
            text = text[start:end]
        elif "```" in text:
            start = text.find("```") + 3
            end = text.find("```", start)
            text = text[start:end]

        return text.strip()


# Global analyzer instance
analyzer = NewsAnalyzer()
