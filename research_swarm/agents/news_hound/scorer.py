"""
Sentiment Scoring Module.

Scores news sentiment across 4 dimensions and calculates overall sentiment score.
"""
import json
from typing import Tuple, List
from langchain_anthropic import ChatAnthropic
from research_swarm.logger import logger
from research_swarm.config import settings
from research_swarm.utils import extract_token_usage
from research_swarm.agents.news_hound.models import (
    NewsArticle,
    CatalystEvent,
    SentimentBreakdown
)


class SentimentScorer:
    """Scores news sentiment across multiple dimensions."""

    def __init__(self):
        """Initialize scorer with Haiku model."""
        # Use Haiku for efficient scoring
        self.haiku = ChatAnthropic(
            model="claude-haiku-4-5-20251001",
            api_key=settings.anthropic_api_key,
            temperature=0.3,
        )
        logger.info("SentimentScorer initialized with Haiku")

    def calculate_confidence(
        self,
        articles: List[NewsArticle],
        catalyst_events: List[CatalystEvent]
    ) -> float:
        """
        Calculate confidence level based on data quality.

        Confidence factors:
        - Article count (more articles = higher confidence)
        - Catalyst detection (clear events = higher confidence)
        - Source diversity (diverse sources = higher confidence)

        Args:
            articles: List of NewsArticle objects
            catalyst_events: List of CatalystEvent objects

        Returns:
            Confidence score (0.0 - 1.0)
        """
        # Base confidence from article count
        article_count = len(articles)
        if article_count == 0:
            return 0.0
        elif article_count >= 20:
            article_confidence = 0.95
        elif article_count >= 10:
            article_confidence = 0.85
        elif article_count >= 5:
            article_confidence = 0.70
        else:
            article_confidence = 0.50

        # Boost from catalyst detection
        catalyst_count = len(catalyst_events)
        if catalyst_count >= 5:
            catalyst_boost = 0.05
        elif catalyst_count >= 3:
            catalyst_boost = 0.03
        elif catalyst_count >= 1:
            catalyst_boost = 0.01
        else:
            catalyst_boost = -0.05  # Penalty for no catalysts

        # Boost from source diversity
        unique_sources = len(set(article.source for article in articles))
        if unique_sources >= 10:
            source_boost = 0.05
        elif unique_sources >= 5:
            source_boost = 0.03
        else:
            source_boost = 0.0

        # Calculate total confidence
        confidence = article_confidence + catalyst_boost + source_boost

        # Clamp to [0.3, 0.95] range
        confidence = max(0.3, min(0.95, confidence))

        return confidence

    def _format_catalysts(self, catalysts: List[CatalystEvent]) -> str:
        """
        Format catalyst events for scoring prompt.

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

    def _default_scores(self) -> Tuple[float, SentimentBreakdown, float, int]:
        """
        Return default scores when scoring fails.

        Returns neutral sentiment (5.0) across all dimensions.

        Returns:
            Tuple of (default_score, default_breakdown, low_confidence, zero_tokens)
        """
        breakdown = SentimentBreakdown(
            overall_tone=5.0,
            catalyst_impact=5.0,
            market_perception=5.0,
            forward_looking=5.0
        )
        return 5.0, breakdown, 0.3, 0

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


# Global scorer instance
scorer = SentimentScorer()
