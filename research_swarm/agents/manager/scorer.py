"""
Moat scoring logic for the Manager agent.

Implements the weighted moat score calculation and confidence assessment.
"""
import statistics
from typing import Tuple, Dict
from .models import MoatScoreBreakdown


class ManagerScorer:
    """
    Handles moat score calculation and confidence assessment.

    Moat Formula (from master-plan.md):
    - Financial Health (Fundamentalist): 30%
    - Sentiment/Catalysts (News Hound): 20%
    - Technical Strength (Quant): 20%
    - Supply Chain Position (Quant): 30%

    Watchlist Threshold: moat_score >= 8.0
    """

    # Moat component weights
    WEIGHTS = {
        "financial_health": 0.30,
        "sentiment_catalysts": 0.20,
        "technical_strength": 0.20,
        "supply_chain_position": 0.30,
    }

    WATCHLIST_THRESHOLD = 8.0

    @classmethod
    def calculate_moat_score(
        cls,
        financial_health_score: float,
        sentiment_score: float,
        technical_score: float,
        supply_chain_score: float,
        fundamentalist_confidence: float = 1.0,
        news_hound_confidence: float = 1.0,
        quant_confidence: float = 1.0,
    ) -> Tuple[float, MoatScoreBreakdown, float]:
        """
        Calculate moat score using weighted formula.

        Args:
            financial_health_score: Score from Fundamentalist (0-10)
            sentiment_score: Score from News Hound (0-10)
            technical_score: Score from Quant (0-10)
            supply_chain_score: Score from Quant (0-10)
            fundamentalist_confidence: Confidence from Fundamentalist (0-1)
            news_hound_confidence: Confidence from News Hound (0-1)
            quant_confidence: Confidence from Quant (0-1)

        Returns:
            Tuple of (moat_score, breakdown, confidence):
            - moat_score (float): Weighted moat score (0-10)
            - breakdown (MoatScoreBreakdown): Component score breakdown
            - confidence (float): Overall confidence in the score (0-1)
        """
        # Create breakdown object
        breakdown = MoatScoreBreakdown(
            financial_health=financial_health_score,
            sentiment_catalysts=sentiment_score,
            technical_strength=technical_score,
            supply_chain_position=supply_chain_score,
        )

        # Calculate weighted moat score
        moat_score = breakdown.weighted_average()

        # Calculate confidence based on agent score consistency and agent confidences
        confidence = cls.assess_confidence(
            component_scores=[
                financial_health_score,
                sentiment_score,
                technical_score,
                supply_chain_score,
            ],
            agent_confidences={
                "fundamentalist": fundamentalist_confidence,
                "news_hound": news_hound_confidence,
                "quant": quant_confidence,
            },
        )

        return moat_score, breakdown, confidence

    @classmethod
    def assess_confidence(
        cls,
        component_scores: list[float],
        agent_confidences: Dict[str, float],
    ) -> float:
        """
        Assess confidence in the moat score based on:
        1. Score consistency across agents (low variance = high confidence)
        2. Individual agent confidence levels

        Formula:
        - Base confidence = average of agent confidences
        - Variance penalty = (1 - normalized_variance)
        - Final confidence = base_confidence * variance_penalty

        Args:
            component_scores: List of component scores [financial, sentiment, technical, supply_chain]
            agent_confidences: Dict of agent confidence levels

        Returns:
            float: Overall confidence (0-1)
        """
        # Calculate base confidence from agent confidences
        base_confidence = statistics.mean(agent_confidences.values())

        # Calculate variance in component scores
        if len(component_scores) < 2:
            # Not enough scores to calculate variance
            return base_confidence

        score_variance = statistics.variance(component_scores)

        # Normalize variance to [0, 1] range
        # Max variance is when scores are at extremes (0 and 10)
        # variance([0, 10]) ≈ 50, variance([0, 0, 10, 10]) = 33.33
        # Use 40 as a reasonable max variance for 4 scores
        max_variance = 40.0
        normalized_variance = min(score_variance / max_variance, 1.0)

        # Calculate variance penalty (low variance = less penalty)
        variance_penalty = 1.0 - (normalized_variance * 0.5)  # Max 50% penalty

        # Combine base confidence with variance penalty
        final_confidence = base_confidence * variance_penalty

        # Ensure confidence is in [0, 1] range
        return max(0.0, min(1.0, final_confidence))

    @classmethod
    def determine_watchlist(cls, moat_score: float) -> bool:
        """
        Determine if a stock qualifies for the watchlist.

        Args:
            moat_score: The calculated moat score (0-10)

        Returns:
            bool: True if moat_score >= WATCHLIST_THRESHOLD
        """
        return moat_score >= cls.WATCHLIST_THRESHOLD

    @classmethod
    def get_score_interpretation(cls, moat_score: float) -> str:
        """
        Get a human-readable interpretation of the moat score.

        Args:
            moat_score: The calculated moat score (0-10)

        Returns:
            str: Interpretation of the score
        """
        if moat_score >= 8.0:
            return "Strong - Watchlist Candidate"
        elif moat_score >= 6.0:
            return "Moderate - Hold"
        elif moat_score >= 4.0:
            return "Weak - Caution"
        else:
            return "Very Weak - Avoid"

    # Tier order for downgrade logic
    _TIER_ORDER = ["STRONG SELL", "SELL", "HOLD", "BUY", "STRONG BUY"]

    @classmethod
    def determine_rating(
        cls,
        moat_score: float,
        technical_score: float = None,
    ) -> Tuple[str, float]:
        """
        Convert moat score to 5-tier rating system with manager-level adjustment.

        Base Rating Methodology (v2.0):
        - STRONG BUY (8.5-10.0): High conviction, all signals align
        - BUY (7.0-8.4): Positive outlook, minor concerns
        - HOLD (5.0-6.9): Mixed signals, wait for clarity
        - SELL (3.0-4.9): Deteriorating fundamentals or Extreme Structural Premium with weakening thesis
        - STRONG SELL (0-2.9): Broken thesis, exit immediately

        Manager Technical Override:
        When technical_score < 4.0 (clearly bearish chart structure), the manager
        steps the rating down one tier. A fundamentally strong company in a confirmed
        technical breakdown is not actionably a BUY — strong balance sheets don't
        stop downtrends. The rating is downgraded to reflect the current investable
        reality, not just the long-term quality.

        Args:
            moat_score: The calculated moat score (0-10)
            technical_score: Technical/momentum score from quant agent (0-10). When
                provided and below 4.0, triggers a one-tier downgrade.

        Returns:
            Tuple of (rating_name, numeric_score)
        """
        # Base rating from moat score
        if moat_score >= 8.5:
            base_rating = "STRONG BUY"
        elif moat_score >= 7.0:
            base_rating = "BUY"
        elif moat_score >= 5.0:
            base_rating = "HOLD"
        elif moat_score >= 3.0:
            base_rating = "SELL"
        else:
            base_rating = "STRONG SELL"

        # Manager technical override: broken technicals drop the actionable rating
        # one tier for BUY-or-above stocks. HOLD/SELL/STRONG SELL are already cautious.
        if technical_score is not None and technical_score < 4.0:
            idx = cls._TIER_ORDER.index(base_rating)
            if idx >= 3:  # BUY or STRONG BUY → downgrade one step
                base_rating = cls._TIER_ORDER[idx - 1]

        return base_rating, moat_score

    @classmethod
    def determine_risk_level(
        cls,
        component_scores: Dict[str, float],
        variance: float
    ) -> str:
        """
        Determine risk level based on score variance and component scores.

        Classification:
        - Low Risk: Low variance (<5.0) + high average score (>=7.0)
          Signals are aligned and strong
        - High Risk: High variance (>20.0) OR low average score (<4.0)
          Signals divergent or fundamentals weak
        - Medium Risk: Everything else
          Moderate variance or moderate scores

        Args:
            component_scores: Dict of component scores (e.g., financial_health, sentiment, etc.)
            variance: Variance of component scores

        Returns:
            str: "Low" | "Medium" | "High"
        """
        # Calculate average score across components
        if not component_scores:
            return "Medium"  # Default if no scores provided

        avg_score = statistics.mean(component_scores.values())

        # Low variance + high scores = Low risk
        if variance < 5.0 and avg_score >= 7.0:
            return "Low"

        # High variance OR low scores = High risk
        if variance > 20.0 or avg_score < 4.0:
            return "High"

        # Everything else = Medium risk
        return "Medium"
