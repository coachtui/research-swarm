"""
News Aggregation Module.

Fetches, filters, and deduplicates news articles for analysis.
"""
import json
from typing import List, Dict, Optional, Set
from difflib import SequenceMatcher
from langchain_anthropic import ChatAnthropic
from research_swarm.logger import logger
from research_swarm.config import settings
from research_swarm.data.news_client import news_client
from research_swarm.agents.news_hound.prompts import (
    NEWS_FILTERING_PROMPT,
    DEDUPLICATION_PROMPT
)
from research_swarm.agents.news_hound.models import NewsArticle


class NewsAggregator:
    """Aggregates and processes news articles for analysis."""

    def __init__(self):
        """Initialize aggregator with LLM model."""
        # Haiku for cost-effective filtering
        self.haiku = ChatAnthropic(
            model="claude-haiku-4-5-20251001",
            api_key=settings.anthropic_api_key,
            temperature=0.0,
        )

        logger.info("NewsAggregator initialized")

    def fetch_news(
        self,
        ticker: str,
        days_back: int = 30,
        company_name: Optional[str] = None,
    ) -> List[NewsArticle]:
        """
        Fetch news articles for a company.

        Args:
            ticker: Stock ticker
            days_back: Number of days to look back
            company_name: Company name for building a precise search query

        Returns:
            List of NewsArticle objects (raw, unfiltered)
        """
        logger.info(f"Fetching news for {ticker} (last {days_back} days)")

        # Fetch from news client (with caching)
        raw_articles = news_client.get_company_news(
            ticker, days_back, company_name=company_name
        )

        # Convert to Pydantic models for validation
        validated_articles = []
        for article_dict in raw_articles:
            try:
                article = NewsArticle(**article_dict)
                validated_articles.append(article)
            except Exception as e:
                logger.debug(f"Failed to validate article: {e}")
                continue

        logger.info(f"Fetched {len(validated_articles)} articles for {ticker}")
        return validated_articles

    def filter_articles(
        self,
        articles: List[NewsArticle],
        ticker: str
    ) -> List[NewsArticle]:
        """
        Filter articles for relevance to the company using Claude Haiku.

        Args:
            articles: List of NewsArticle objects
            ticker: Stock ticker

        Returns:
            Filtered list of relevant articles
        """
        if not articles:
            logger.warning(f"No articles to filter for {ticker}")
            return []

        logger.info(f"Filtering {len(articles)} articles for {ticker}")

        # If few articles, skip filtering to preserve data
        if len(articles) <= 5:
            logger.info("Few articles, skipping filtering")
            return articles

        # Format articles for prompt (title + description only to save tokens)
        articles_text = self._format_articles_for_filtering(articles)

        prompt = NEWS_FILTERING_PROMPT.format(
            ticker=ticker,
            article_count=len(articles),
            articles_text=articles_text
        )

        try:
            response = self.haiku.invoke(prompt)
            response_text = response.content.strip()

            # Extract JSON from response
            json_text = self._extract_json(response_text)
            filter_result = json.loads(json_text)

            relevant_indices = filter_result.get("relevant_indices", [])
            filtered_articles = [articles[i] for i in relevant_indices if i < len(articles)]

            logger.success(
                f"✓ Filtered {len(articles)} → {len(filtered_articles)} relevant articles for {ticker}"
            )
            return filtered_articles

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse filter JSON: {e}")
            logger.debug(f"Response: {response_text[:500]}")
            # On error, return all articles (fail open)
            return articles

        except Exception as e:
            logger.error(f"Error filtering articles: {e}")
            return articles

    def deduplicate(self, articles: List[NewsArticle]) -> List[NewsArticle]:
        """
        Remove duplicate or highly similar articles using title similarity.

        Args:
            articles: List of NewsArticle objects

        Returns:
            Deduplicated list of articles
        """
        if not articles:
            return []

        if len(articles) <= 3:
            # Too few to dedupe effectively
            return articles

        logger.info(f"Deduplicating {len(articles)} articles")

        # Use simple title similarity for fast deduplication
        # More sophisticated: use Claude, but costs more
        unique_articles = []
        seen_titles: Set[str] = set()

        for article in articles:
            title_lower = article.title.lower()

            # Check for exact duplicates first
            if title_lower in seen_titles:
                logger.debug(f"Exact duplicate: {article.title}")
                continue

            # Check for similar titles
            is_duplicate = False
            for seen_title in seen_titles:
                similarity = SequenceMatcher(None, title_lower, seen_title).ratio()
                if similarity > 0.85:  # 85% similarity threshold
                    logger.debug(f"Similar duplicate: {article.title}")
                    is_duplicate = True
                    break

            if not is_duplicate:
                unique_articles.append(article)
                seen_titles.add(title_lower)

        logger.success(
            f"✓ Deduplicated {len(articles)} → {len(unique_articles)} unique articles"
        )
        return unique_articles

    def process_articles(
        self,
        ticker: str,
        days_back: int = 30
    ) -> List[NewsArticle]:
        """
        Full pipeline: fetch, filter, and deduplicate articles.

        Args:
            ticker: Stock ticker
            days_back: Number of days to look back

        Returns:
            Processed list of unique, relevant articles
        """
        logger.info(f"Processing articles for {ticker}")

        # Step 1: Fetch articles
        articles = self.fetch_news(ticker, days_back)

        if not articles:
            logger.warning(f"No articles found for {ticker}")
            return []

        # Step 2: Deduplicate first (reduces API calls for filtering)
        articles = self.deduplicate(articles)

        # Step 3: Filter for relevance
        articles = self.filter_articles(articles, ticker)

        logger.success(
            f"✓ Processed {len(articles)} articles for {ticker} (fetch → dedupe → filter)"
        )

        return articles

    def _format_articles_for_filtering(self, articles: List[NewsArticle]) -> str:
        """
        Format articles for filtering prompt (title + description only).

        Args:
            articles: List of NewsArticle objects

        Returns:
            Formatted articles text
        """
        formatted = []
        for i, article in enumerate(articles):
            # Include title and description only (not full content)
            desc = article.description or "(no description)"
            formatted.append(f"{i}. **{article.title}**\n   {desc}\n")

        return "\n".join(formatted)

    def _format_articles_for_dedup(self, articles: List[NewsArticle]) -> str:
        """
        Format articles for deduplication prompt (titles only).

        Args:
            articles: List of NewsArticle objects

        Returns:
            Formatted articles text
        """
        formatted = []
        for i, article in enumerate(articles):
            formatted.append(f"{i}. {article.title} ({article.source})")

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


# Global aggregator instance
aggregator = NewsAggregator()
