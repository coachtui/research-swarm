"""
Pydantic models for News Hound agent outputs.

These models ensure type safety and validation for all news analysis data.
"""
from pydantic import BaseModel, Field, field_validator, model_validator
from typing import List, Optional, Literal, Dict, Any
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


class EarningsEstimateRevision(BaseModel):
    """Earnings estimate revision data (PRIMARY SIGNAL per Zacks model)."""

    # Current consensus estimates
    current_quarter_eps: Optional[float] = Field(None, description="Current quarter EPS estimate")
    current_fy_eps: Optional[float] = Field(None, description="Current fiscal year EPS estimate")
    next_fy_eps: Optional[float] = Field(None, description="Next fiscal year EPS estimate")

    # Revisions (90 days)
    upward_revisions: Optional[int] = Field(default=0, description="Number of upward revisions (90 days)")
    downward_revisions: Optional[int] = Field(default=0, description="Number of downward revisions (90 days)")
    net_revision_direction: str = Field(default="neutral", description="Strongly Positive/Positive/Neutral/Negative/Strongly Negative")
    consensus_change_pct: Optional[float] = Field(default=None, description="% change in consensus estimate (90 days)")

    # Estimate quality
    analyst_coverage: Optional[int] = Field(default=0, description="Number of analysts covering")
    estimate_dispersion: str = Field(default="medium", description="Low/Medium/High")
    estimate_agreement: Optional[float] = Field(default=0.5, ge=0, le=1, description="% of estimates within tight range")

    @model_validator(mode='before')
    @classmethod
    def replace_none_with_defaults(cls, data):
        """Replace None values with defaults for LLM-generated nulls."""
        if isinstance(data, dict):
            # Integer/Float fields
            if data.get('upward_revisions') is None:
                data['upward_revisions'] = 0
            if data.get('downward_revisions') is None:
                data['downward_revisions'] = 0
            if data.get('analyst_coverage') is None:
                data['analyst_coverage'] = 0
            if data.get('estimate_agreement') is None:
                data['estimate_agreement'] = 0.5

            # String fields
            if data.get('net_revision_direction') is None:
                data['net_revision_direction'] = "neutral"
            if data.get('estimate_dispersion') is None:
                data['estimate_dispersion'] = "medium"
            if data.get('beat_pattern') is None:
                data['beat_pattern'] = ""
            if data.get('momentum') is None:
                data['momentum'] = "stable"
        return data

    # EPS surprise history (last 4 quarters)
    q1_surprise_pct: Optional[float] = Field(None, description="Q-1 EPS surprise %")
    q2_surprise_pct: Optional[float] = Field(None, description="Q-2 EPS surprise %")
    q3_surprise_pct: Optional[float] = Field(None, description="Q-3 EPS surprise %")
    q4_surprise_pct: Optional[float] = Field(None, description="Q-4 EPS surprise %")
    avg_surprise_pct: Optional[float] = Field(None, description="Average surprise %")
    beat_pattern: str = Field("", description="e.g., 'Beat 4/4', 'Beat 3/4', etc.")

    # Growth trajectory
    current_year_growth_pct: Optional[float] = Field(None, description="Current year EPS growth %")
    next_year_growth_pct: Optional[float] = Field(None, description="Next year EPS growth %")
    momentum: str = Field("stable", description="Accelerating/Stable/Decelerating")
    two_year_cagr: Optional[float] = Field(None, description="Two-year EPS CAGR %")


class AnalystConsensus(BaseModel):
    """Analyst ratings and price target consensus."""

    # Current ratings distribution
    strong_buy: int = Field(0, description="Number of Strong Buy ratings")
    buy: int = Field(0, description="Number of Buy ratings")
    hold: int = Field(0, description="Number of Hold ratings")
    sell: int = Field(0, description="Number of Sell ratings")
    strong_sell: int = Field(0, description="Number of Strong Sell ratings")
    consensus_rating: str = Field("hold", description="Overall consensus (Strong Buy/Buy/Hold/Sell/Strong Sell)")

    # Price targets
    avg_price_target: Optional[float] = Field(None, description="Average analyst price target")
    high_price_target: Optional[float] = Field(None, description="Highest price target")
    low_price_target: Optional[float] = Field(None, description="Lowest price target")
    target_upside_pct: Optional[float] = Field(None, description="% upside to avg target from current price")

    # Recent changes (90 days)
    upgrades: Optional[int] = Field(default=0, description="Number of upgrades")
    downgrades: Optional[int] = Field(default=0, description="Number of downgrades")
    new_coverage: Optional[int] = Field(default=0, description="Number of new coverage initiations")
    rating_momentum: str = Field(default="stable", description="Improving/Stable/Deteriorating")
    target_trend: str = Field(default="stable", description="Rising/Stable/Falling")

    # Confidence
    consensus_confidence: str = Field(default="medium", description="High/Medium/Low")

    @model_validator(mode='before')
    @classmethod
    def replace_none_with_defaults(cls, data):
        """Replace None values with defaults for LLM-generated nulls."""
        if isinstance(data, dict):
            # Integer fields
            if data.get('upgrades') is None:
                data['upgrades'] = 0
            if data.get('downgrades') is None:
                data['downgrades'] = 0
            if data.get('new_coverage') is None:
                data['new_coverage'] = 0

            # String fields
            if data.get('consensus_rating') is None:
                data['consensus_rating'] = "hold"
            if data.get('rating_momentum') is None:
                data['rating_momentum'] = "stable"
            if data.get('target_trend') is None:
                data['target_trend'] = "stable"
            if data.get('consensus_confidence') is None:
                data['consensus_confidence'] = "medium"
        return data


class InstitutionalActivity(BaseModel):
    """Institutional ownership and 13F tracking (Smart Money)."""

    # Current ownership
    institutional_ownership_pct: Optional[float] = Field(default=None, description="% of shares held by institutions")
    qoq_change_pct: Optional[float] = Field(default=None, description="Quarter-over-quarter change in ownership %")
    num_holders: Optional[int] = Field(default=0, description="Number of institutional holders")
    trend: str = Field(default="stable", description="Accumulation/Distribution/Stable")

    @model_validator(mode='before')
    @classmethod
    def replace_none_with_defaults(cls, data):
        """Replace None values with defaults for LLM-generated nulls."""
        if isinstance(data, dict):
            # Integer fields
            if data.get('num_holders') is None:
                data['num_holders'] = 0

            # String fields
            if data.get('trend') is None:
                data['trend'] = "stable"
            if data.get('institutional_sentiment') is None:
                data['institutional_sentiment'] = "neutral"
        return data

    # Top 5 holders
    top_holders: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Top 5 institutional holders with % ownership and recent changes"
    )

    # Notable 13F activity
    notable_activity: List[str] = Field(
        default_factory=list,
        description="Notable smart money moves (e.g., 'Berkshire added 15%')"
    )

    # Sentiment
    institutional_sentiment: str = Field("neutral", description="Strongly Bullish/Bullish/Neutral/Bearish")


class DarkPoolActivity(BaseModel):
    """Dark pool (ATS) trading activity from FINRA OTC Transparency Portal."""

    # Volume metrics
    avg_ats_pct: Optional[float] = Field(None, description="Average % traded off-exchange (last 30 days)")
    trend: str = Field("stable", description="increasing/stable/decreasing")
    trend_pct_change: Optional[float] = Field(None, description="% change in ATS volume (recent vs prior 15 days)")
    peak_week: Optional[str] = Field(None, description="Week with highest ATS % (YYYY-MM-DD)")
    peak_ats_pct: Optional[float] = Field(None, description="Peak ATS % value")

    # Venue analysis
    major_venues: List[str] = Field(
        default_factory=list,
        description="Top 3 dark pool venues by volume"
    )
    venue_concentration: str = Field("medium", description="high/medium/low - concentration in top venues")

    # Pattern detection
    notable_patterns: List[str] = Field(
        default_factory=list,
        description="Unusual patterns (e.g., 'Sudden spike to 40% week of 2/14', 'Sustained elevated activity')"
    )

    # Sentiment
    dark_pool_sentiment: str = Field("neutral", description="bullish/neutral/bearish")
    confidence: str = Field("medium", description="high/medium/low - LLM confidence")

    @model_validator(mode='before')
    @classmethod
    def replace_none_with_defaults(cls, data):
        """Replace None values with defaults for LLM-generated nulls."""
        if isinstance(data, dict):
            # String fields
            if data.get('trend') is None:
                data['trend'] = "stable"
            if data.get('venue_concentration') is None:
                data['venue_concentration'] = "medium"
            if data.get('dark_pool_sentiment') is None:
                data['dark_pool_sentiment'] = "neutral"
            if data.get('confidence') is None:
                data['confidence'] = "medium"
        return data


class InsiderActivity(BaseModel):
    """Insider trading activity (6 months)."""

    # Transaction summary
    buy_transactions: int = Field(default=0, description="Number of buy transactions")
    buy_shares: int = Field(default=0, description="Total shares bought")
    buy_value_usd: float = Field(default=0.0, description="Total value of buys in USD")

    sell_transactions: int = Field(default=0, description="Number of sell transactions")
    sell_shares: int = Field(default=0, description="Total shares sold")
    sell_value_usd: float = Field(default=0.0, description="Total value of sells in USD")

    net_shares: int = Field(default=0, description="Net shares (buys - sells)")
    net_value_usd: float = Field(default=0.0, description="Net value in USD")

    # Notable transactions
    notable_transactions: List[str] = Field(
        default_factory=list,
        description="Notable insider transactions (e.g., 'CEO bought $2M at $50 on 2024-12-15')"
    )

    # Ownership
    insider_ownership_pct: Optional[float] = Field(None, description="Total insider ownership %")
    ceo_ownership_pct: Optional[float] = Field(None, description="CEO ownership %")
    ownership_trend: str = Field("stable", description="Increasing/Stable/Decreasing")

    # Sentiment
    insider_sentiment: str = Field("neutral", description="Bullish/Neutral/Bearish")
    confidence: str = Field("medium", description="High/Medium/Low - based on transaction patterns")

    @model_validator(mode='before')
    @classmethod
    def replace_none_with_defaults(cls, data):
        """Replace None values with defaults for LLM-generated nulls."""
        if isinstance(data, dict):
            # Integer/Float fields
            if data.get('buy_transactions') is None:
                data['buy_transactions'] = 0
            if data.get('buy_shares') is None:
                data['buy_shares'] = 0
            if data.get('buy_value_usd') is None:
                data['buy_value_usd'] = 0.0
            if data.get('sell_transactions') is None:
                data['sell_transactions'] = 0
            if data.get('sell_shares') is None:
                data['sell_shares'] = 0
            if data.get('sell_value_usd') is None:
                data['sell_value_usd'] = 0.0
            if data.get('net_shares') is None:
                data['net_shares'] = 0
            if data.get('net_value_usd') is None:
                data['net_value_usd'] = 0.0

            # String fields
            if data.get('ownership_trend') is None:
                data['ownership_trend'] = "stable"
            if data.get('insider_sentiment') is None:
                data['insider_sentiment'] = "neutral"
            if data.get('confidence') is None:
                data['confidence'] = "medium"
        return data


class ManagementCommentary(BaseModel):
    """Management commentary and tone analysis from earnings calls and guidance."""

    # Guidance track record
    guidance_last_quarter: Optional[str] = Field(None, description="Last quarter guidance vs reality (Beat/Met/Missed)")
    guidance_reliability: str = Field("medium", description="High (consistently accurate) / Medium / Low (frequently wrong)")
    current_guidance: Optional[str] = Field(None, description="Current quarter/year guidance if provided")
    guidance_change: Optional[str] = Field(None, description="Raised/Maintained/Lowered/Withdrawn")

    # Tone assessment from earnings calls
    tone_assessment: str = Field("neutral", description="Confident/Cautious/Defensive/Evasive")
    tone_evidence: List[str] = Field(
        default_factory=list,
        description="Specific quotes or behaviors indicating tone"
    )

    # Red flags
    red_flag_language: List[str] = Field(
        default_factory=list,
        description="Concerning phrases like 'challenging environment', 'macro headwinds', 'one-time charges'"
    )
    has_red_flags: bool = Field(False, description="True if significant red flags detected")

    # Capital allocation quality
    capital_allocation_quality: str = Field("medium", description="High (shareholder-friendly) / Medium / Low (value-destructive)")
    capex_discipline: Optional[str] = Field(None, description="Disciplined/Moderate/Aggressive")
    shareholder_returns: Optional[str] = Field(None, description="Buybacks, dividends, or other returns to shareholders")

    # Innovation and competitive positioning
    innovation_mentions: int = Field(0, description="Count of innovation/R&D/new product mentions")
    competitive_position: str = Field("neutral", description="Strengthening/Stable/Weakening")

    # Overall management quality signal
    management_quality_score: float = Field(5.0, ge=0, le=10, description="Overall management quality (0-10)")
    confidence: str = Field("medium", description="High/Medium/Low")

    @model_validator(mode='before')
    @classmethod
    def replace_none_with_defaults(cls, data):
        """Replace None values with defaults for LLM-generated nulls."""
        if isinstance(data, dict):
            # Integer fields
            if data.get('innovation_mentions') is None:
                data['innovation_mentions'] = 0

            # Float fields
            if data.get('management_quality_score') is None:
                data['management_quality_score'] = 5.0

            # Boolean fields
            if data.get('has_red_flags') is None:
                data['has_red_flags'] = False

            # String fields
            if data.get('guidance_reliability') is None:
                data['guidance_reliability'] = "medium"
            if data.get('tone_assessment') is None:
                data['tone_assessment'] = "neutral"
            if data.get('capital_allocation_quality') is None:
                data['capital_allocation_quality'] = "medium"
            if data.get('competitive_position') is None:
                data['competitive_position'] = "neutral"
            if data.get('confidence') is None:
                data['confidence'] = "medium"
        return data


class ShortInterest(BaseModel):
    """Short interest tracking and squeeze risk assessment."""

    # Current short metrics
    short_interest_pct: Optional[float] = Field(None, description="Short interest as % of float")
    short_interest_shares: Optional[int] = Field(None, description="Total shares sold short")
    days_to_cover: Optional[float] = Field(None, description="Days to cover (short interest / avg daily volume)")

    # Trend
    short_interest_trend: str = Field("stable", description="Increasing/Stable/Decreasing")
    mom_change_pct: Optional[float] = Field(None, description="Month-over-month change in short interest %")

    # Squeeze risk assessment
    squeeze_risk: str = Field("low", description="High/Medium/Low - based on short % and days to cover")
    squeeze_triggers: List[str] = Field(
        default_factory=list,
        description="Potential squeeze triggers (e.g., 'Upcoming earnings', 'High short %, low float')"
    )

    # Notable short activity
    notable_short_activity: List[str] = Field(
        default_factory=list,
        description="Notable short seller reports or activism"
    )

    # Sentiment
    short_sentiment: str = Field("neutral", description="Bullish (decreasing shorts) / Neutral / Bearish (increasing shorts)")

    @model_validator(mode='before')
    @classmethod
    def replace_none_with_defaults(cls, data):
        """Replace None values with defaults for LLM-generated nulls."""
        if isinstance(data, dict):
            # String fields
            if data.get('short_interest_trend') is None:
                data['short_interest_trend'] = "stable"
            if data.get('squeeze_risk') is None:
                data['squeeze_risk'] = "low"
            if data.get('short_sentiment') is None:
                data['short_sentiment'] = "neutral"
        return data


class UpcomingCatalyst(BaseModel):
    """Upcoming catalyst event."""

    event_type: str = Field(..., description="Type of catalyst (earnings, FDA decision, product launch, etc.)")
    event_date: Optional[str] = Field(None, description="Expected date (YYYY-MM-DD) or timeframe")
    description: str = Field(..., min_length=10, description="Description of the catalyst")
    potential_impact: str = Field("medium", description="High/Medium/Low")
    impact_direction: str = Field("neutral", description="Positive/Negative/Neutral")
    confidence: float = Field(0.5, ge=0, le=1, description="Confidence in date/occurrence (0-1)")


class UpcomingCatalysts(BaseModel):
    """Upcoming catalyst calendar (next 6 months)."""

    # Next earnings date
    next_earnings_date: Optional[str] = Field(None, description="Next earnings announcement date (YYYY-MM-DD)")
    earnings_confirmed: bool = Field(False, description="True if date is confirmed, False if estimated")

    # Other upcoming catalysts
    catalysts: List[UpcomingCatalyst] = Field(
        default_factory=list,
        description="Upcoming catalyst events (earnings, FDA, product launches, etc.)"
    )

    # Catalyst density
    catalyst_density: str = Field("medium", description="High (many upcoming events) / Medium / Low (few events)")
    outlook: str = Field("neutral", description="Positive (bullish catalysts) / Neutral / Negative (bearish)")

    @model_validator(mode='before')
    @classmethod
    def replace_none_with_defaults(cls, data):
        """Replace None values with defaults for LLM-generated nulls."""
        if isinstance(data, dict):
            # Boolean fields
            if data.get('earnings_confirmed') is None:
                data['earnings_confirmed'] = False

            # String fields
            if data.get('catalyst_density') is None:
                data['catalyst_density'] = "medium"
            if data.get('outlook') is None:
                data['outlook'] = "neutral"
        return data


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

    # NEW: Earnings & Analyst Data (PRIMARY SIGNALS)
    earnings_estimates: Optional[EarningsEstimateRevision] = Field(None, description="Earnings estimate revisions (PRIMARY SIGNAL)")
    analyst_consensus: Optional[AnalystConsensus] = Field(None, description="Analyst ratings and price targets")
    institutional_activity: Optional[InstitutionalActivity] = Field(None, description="Smart money / 13F activity")
    dark_pool_activity: Optional[DarkPoolActivity] = Field(None, description="Dark pool (ATS) trading activity from FINRA")
    insider_activity: Optional[InsiderActivity] = Field(None, description="Insider trading activity (6 months)")

    # NEW: Management Quality & Market Dynamics
    management_commentary: Optional[ManagementCommentary] = Field(None, description="Management tone and guidance quality")
    short_interest: Optional[ShortInterest] = Field(None, description="Short interest tracking and squeeze risk")
    upcoming_catalysts: Optional[UpcomingCatalysts] = Field(None, description="Upcoming catalyst calendar (6 months)")

    # Metadata
    tokens_used: int = Field(..., ge=0, description="Total tokens used in API calls")
    processing_time: float = Field(..., ge=0, description="Total processing time in seconds")
    cost_estimate: float = Field(..., ge=0, description="Estimated API cost in USD")

    @model_validator(mode='after')
    def validate_score_matches_breakdown(self):
        """
        Ensure the sentiment score matches the weighted average of components.
        Auto-correct score mismatches instead of raising ValidationError.
        """
        expected = self.sentiment_breakdown.weighted_average()
        diff = abs(self.sentiment_score - expected)

        if diff > 0.5:  # Significant mismatch - auto-correct
            logger.warning(
                f"Sentiment score {self.sentiment_score} significantly differs from "
                f"breakdown weighted average {expected:.2f}. Auto-correcting to breakdown value."
            )
            # SELF-HEAL: Set to expected value
            self.sentiment_score = round(expected, 2)
        elif diff > 0.1:  # Minor floating-point difference - accept
            logger.debug(
                f"Sentiment score {self.sentiment_score} has minor difference from "
                f"breakdown {expected:.2f} (likely floating point). Accepting."
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
