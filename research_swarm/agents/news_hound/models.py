"""
Pydantic models for News Hound agent outputs.

These models ensure type safety and validation for all news analysis data.
"""
from pydantic import BaseModel, Field, field_validator, model_validator
from typing import List, Optional, Literal
from datetime import datetime
from enum import Enum


class CatalystType(str, Enum):
    """9 catalyst categories for event detection."""
    MA = "M&A"  # Mergers and acquisitions
    CONTRACT = "contract"  # Major contracts/deals
    EXPANSION = "expansion"  # Business/facility expansions
    REGULATORY = "regulatory"  # Regulatory approvals/issues
    PARTNERSHIP = "partnership"  # Strategic partnerships
    PRODUCT_LAUNCH = "product_launch"  # New product launches
    EARNINGS_SURPRISE = "earnings_surprise"  # Earnings beats/misses
    EXECUTIVE_CHANGE = "executive_change"  # Leadership changes
    SUPPLY_CHAIN = "supply_chain"  # Supply chain events


class CatalystImpact(str, Enum):
    """Impact classification for catalyst events."""
    POSITIVE = "positive"
    NEGATIVE = "negative"
    NEUTRAL = "neutral"


class NewsArticle(BaseModel):
    """Validated news article input."""

    title: str = Field(..., min_length=1, description="Article title")
    description: Optional[str] = Field(None, description="Article description/snippet")
    content: Optional[str] = Field(None, description="Full article content (may be truncated)")
    url: str = Field(..., description="Article URL")
    source: str = Field(..., description="Source name")
    published_at: str = Field(..., description="Publication timestamp (ISO format)")
    author: Optional[str] = Field(None, description="Article author")

    @field_validator("published_at")
    @classmethod
    def validate_timestamp(cls, v: str) -> str:
        """Ensure timestamp is valid ISO format."""
        try:
            datetime.fromisoformat(v.replace("Z", "+00:00"))
            return v
        except ValueError:
            # If invalid, return current timestamp
            return datetime.now().isoformat()

    def get_text(self) -> str:
        """Get combined text for analysis (title + description + content)."""
        parts = [self.title]
        if self.description:
            parts.append(self.description)
        if self.content:
            # Truncate content to first 500 chars to save tokens
            parts.append(self.content[:500])
        return " ".join(parts)


class CatalystEvent(BaseModel):
    """Detected catalyst event with metadata."""

    event_type: CatalystType = Field(..., description="Type of catalyst event")
    impact: CatalystImpact = Field(..., description="Impact classification (positive/negative/neutral)")
    description: str = Field(..., min_length=10, description="Description of the event")
    date: Optional[str] = Field(None, description="Event date if mentioned (YYYY-MM-DD)")
    confidence: float = Field(..., ge=0, le=1, description="Confidence in detection (0-1)")
    source_articles: List[str] = Field(
        default_factory=list,
        description="URLs of source articles"
    )

    @field_validator("confidence")
    @classmethod
    def validate_confidence(cls, v: float) -> float:
        """Ensure confidence is between 0 and 1."""
        return max(0.0, min(1.0, v))


class SentimentBreakdown(BaseModel):
    """Breakdown of sentiment analysis into 4 components."""

    overall_tone: float = Field(
        ...,
        ge=0,
        le=10,
        description="Overall tone of news coverage (0=very bearish, 10=very bullish)"
    )
    catalyst_impact: float = Field(
        ...,
        ge=0,
        le=10,
        description="Net impact of detected catalysts (0=very negative, 10=very positive)"
    )
    market_perception: float = Field(
        ...,
        ge=0,
        le=10,
        description="Market and analyst perception (0=very negative, 10=very positive)"
    )
    forward_looking: float = Field(
        ...,
        ge=0,
        le=10,
        description="Forward-looking sentiment (0=very pessimistic, 10=very optimistic)"
    )

    def weighted_average(self) -> float:
        """
        Calculate weighted average sentiment score.

        Weights:
        - overall_tone: 30%
        - catalyst_impact: 30%
        - market_perception: 20%
        - forward_looking: 20%
        """
        return (
            self.overall_tone * 0.30 +
            self.catalyst_impact * 0.30 +
            self.market_perception * 0.20 +
            self.forward_looking * 0.20
        )

    def interpret(self) -> str:
        """Get human-readable sentiment interpretation."""
        score = self.weighted_average()
        if score >= 8.0:
            return "Very Bullish"
        elif score >= 6.5:
            return "Bullish"
        elif score >= 4.5:
            return "Neutral"
        elif score >= 3.0:
            return "Bearish"
        else:
            return "Very Bearish"


class NewsHoundOutput(BaseModel):
    """Final validated output from the News Hound agent."""

    # Input identifiers
    ticker: str = Field(..., description="Stock ticker symbol")
    days_back: int = Field(..., ge=1, le=90, description="Number of days analyzed")
    analysis_date: str = Field(
        default_factory=lambda: datetime.now().isoformat(),
        description="Analysis timestamp"
    )

    # Article metadata
    article_count: int = Field(..., ge=0, description="Total number of articles analyzed")
    articles_filtered: int = Field(..., ge=0, description="Number of articles after filtering")

    # Detected events
    catalyst_events: List[CatalystEvent] = Field(
        default_factory=list,
        description="List of detected catalyst events"
    )

    # Sentiment analysis
    sentiment_analysis: str = Field(
        ...,
        min_length=50,
        description="Nuanced sentiment narrative (2-3 paragraphs)"
    )
    sentiment_breakdown: SentimentBreakdown = Field(
        ...,
        description="Sentiment scores by component"
    )
    sentiment_score: float = Field(
        ...,
        ge=0,
        le=10,
        description="Final weighted sentiment score (0-10)"
    )
    confidence: float = Field(
        ...,
        ge=0,
        le=1,
        description="Confidence in analysis based on article count and quality"
    )

    # Metadata
    tokens_used: int = Field(..., ge=0, description="Total tokens used in API calls")
    processing_time: float = Field(..., ge=0, description="Total processing time in seconds")
    cost_estimate: float = Field(..., ge=0, description="Estimated API cost in USD")

    @model_validator(mode='after')
    def validate_score_matches_breakdown(self):
        """Ensure the sentiment score matches the weighted average of components."""
        expected = self.sentiment_breakdown.weighted_average()
        # Allow small floating point differences
        if abs(self.sentiment_score - expected) > 0.1:
            raise ValueError(
                f"Sentiment score {self.sentiment_score} does not match "
                f"breakdown weighted average {expected:.2f}"
            )
        return self

    @model_validator(mode='after')
    def validate_article_counts(self):
        """Ensure articles_filtered <= article_count."""
        if self.articles_filtered > self.article_count:
            raise ValueError(
                f"Filtered articles ({self.articles_filtered}) cannot exceed "
                f"total articles ({self.article_count})"
            )
        return self

    def get_top_catalysts(self, n: int = 3) -> List[CatalystEvent]:
        """Get top N catalysts sorted by confidence."""
        return sorted(
            self.catalyst_events,
            key=lambda x: x.confidence,
            reverse=True
        )[:n]

    def summary(self) -> str:
        """Generate a concise summary of the analysis."""
        sentiment_label = self.sentiment_breakdown.interpret()
        catalyst_count = len(self.catalyst_events)

        summary_lines = [
            f"News Hound Analysis for {self.ticker} (last {self.days_back} days)",
            "━" * 60,
            f"Articles Analyzed: {self.article_count}",
            f"Sentiment Score: {self.sentiment_score:.1f}/10 ({sentiment_label})",
            f"Confidence: {self.confidence:.2f}",
            f"",
            f"Catalysts Detected: {catalyst_count}",
        ]

        # Add top 3 catalysts
        if catalyst_count > 0:
            summary_lines.append("")
            summary_lines.append("Top Catalysts:")
            for i, event in enumerate(self.get_top_catalysts(3), 1):
                date_str = f" ({event.date})" if event.date else ""
                summary_lines.append(
                    f"{i}. [{event.event_type}] {event.description}{date_str} - "
                    f"{event.impact.capitalize()}"
                )

        # Add sentiment breakdown
        summary_lines.extend([
            "",
            "Sentiment Breakdown:",
            f"- Overall Tone: {self.sentiment_breakdown.overall_tone:.1f}/10",
            f"- Catalyst Impact: {self.sentiment_breakdown.catalyst_impact:.1f}/10",
            f"- Market Perception: {self.sentiment_breakdown.market_perception:.1f}/10",
            f"- Forward Looking: {self.sentiment_breakdown.forward_looking:.1f}/10",
        ])

        # Add metadata
        summary_lines.extend([
            "",
            f"Cost: ${self.cost_estimate:.2f} | Time: {self.processing_time:.0f}s | "
            f"Tokens: {self.tokens_used:,}",
        ])

        return "\n".join(summary_lines)
