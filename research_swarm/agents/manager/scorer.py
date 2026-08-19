"""
Moat scoring logic for the Manager agent.

Implements the weighted moat score calculation and confidence assessment.
"""
import statistics
from typing import Tuple, Dict
from research_swarm.logger import logger
from .models import QualityScoreBreakdown


class ManagerScorer:
    """
    Handles quality score calculation and confidence assessment.

    Quality Score Formula (v3.0):
    - ROIC/WACC Spread: 25% (when available)
    - Financial Health: 25%
    - Earnings Quality: 20%
    - Valuation Discipline: 15%
    - Sentiment/Catalysts: 10%

    Fallback weights (when ROIC/WACC not yet wired):
    - Financial Health: 30%, Earnings Quality: 25%, Valuation: 25%, Sentiment: 20%

    Watchlist Threshold: quality_score >= 7.0
    """

    WEIGHTS = {
        "roic_wacc_spread": 0.25,
        "financial_health": 0.25,
        "earnings_quality": 0.20,
        "valuation": 0.15,
        "sentiment_catalysts": 0.10,
    }

    # Must match the ManagerOutput validator's expectation (models.py) — these
    # previously disagreed (7.0 vs 8.0), so every stock scoring 7.0-7.99 was
    # flagged here and silently unflagged by the validator.
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
    ) -> Tuple[float, QualityScoreBreakdown, float]:
        """
        Calculate quality score using weighted formula.

        Args:
            financial_health_score: Score from Fundamentalist (0-10)
            sentiment_score: Score from News Hound (0-10)
            technical_score: Score from Quant (0-10)
            supply_chain_score: Ignored — supply chain removed from quality formula
            fundamentalist_confidence: Confidence from Fundamentalist (0-1)
            news_hound_confidence: Confidence from News Hound (0-1)
            quant_confidence: Confidence from Quant (0-1)

        Returns:
            Tuple of (quality_score, breakdown, confidence):
            - quality_score (float): Weighted quality score (0-10)
            - breakdown (QualityScoreBreakdown): Component score breakdown
            - confidence (float): Overall confidence in the score (0-1)
        """
        # Create breakdown object
        breakdown = QualityScoreBreakdown(
            financial_health=financial_health_score,
            sentiment_catalysts=sentiment_score,
            technical_strength=technical_score,
        )

        # Calculate weighted moat score
        moat_score = breakdown.weighted_average()

        # Calculate confidence based on agent score consistency (supply chain excluded)
        confidence = cls.assess_confidence(
            component_scores=[
                financial_health_score,
                sentiment_score,
                technical_score,
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
            component_scores: List of component scores [financial, sentiment, technical, ...]
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
    def determine_watchlist(
        cls,
        moat_score: float,
        valuation_score: float = None,
    ) -> bool:
        """
        Determine if a stock qualifies for the watchlist.

        A watchlist is not "a high score" — it is specifically *a business we
        want to own, at a price we do not yet want to pay*. With quality and
        valuation split into separate axes that becomes directly expressible:
        high quality AND a price that is not yet attractive. When the price IS
        attractive the answer is not to watch it, it is to buy it, and the
        matrix already says STRONG BUY.

        The old scalar threshold (>= 8.0 on the blended composite) could not
        make this distinction — and because the composite contained valuation,
        a rich price pushed a great business *below* the watchlist bar, which
        is precisely backwards.

        Args:
            moat_score: Business quality score, normalized (0-10)
            valuation_score: Valuation axis, normalized (0-10). When absent,
                falls back to a quality-only read.

        Returns:
            bool: True if this is a quality business worth tracking for entry
        """
        if moat_score < cls.QUALITY_HIGH:
            return False
        if valuation_score is None:
            return True
        return cls._valuation_tier(valuation_score) != "attractive"

    @classmethod
    def get_score_interpretation(cls, moat_score: float) -> str:
        """
        Get a human-readable interpretation of the moat score.

        Args:
            moat_score: The calculated moat score (0-10)

        Returns:
            str: Interpretation of the score
        """
        if moat_score >= 7.0:
            return "High Quality - Watchlist Candidate"
        elif moat_score >= 5.5:
            return "Moderate Quality - Hold"
        elif moat_score >= 4.0:
            return "Below Average Quality - Caution"
        else:
            return "Low Quality - Avoid"

    # Tier order for downgrade logic
    _TIER_ORDER = ["STRONG SELL", "SELL", "HOLD", "BUY", "STRONG BUY"]

    # Normalization of the LLM's free-text recommendation vocabulary into the
    # 5-tier rating vocabulary. Single source of truth — previously duplicated
    # (with disagreeing mappings) across graph.py, decision_intelligence.py,
    # and weekly_signal_service.py.
    _REC_NORMALIZE = {"AVOID": "SELL", "BUY NOW": "BUY", "SCALE IN": "HOLD", "WAIT": "HOLD"}

    @classmethod
    def normalize_recommendation(cls, recommendation: str) -> str:
        """Map an LLM recommendation string onto the 5-tier vocabulary."""
        rec = (recommendation or "").strip().upper()
        return cls._REC_NORMALIZE.get(rec, rec)

    @classmethod
    def reconcile_rating(cls, rating: str, llm_recommendation: str = None) -> str:
        """
        Reconcile the deterministic rating with the LLM's recommendation by
        taking the more conservative of the two.

        The moat scorer and the LLM thesis generator can independently arrive
        at different conclusions. When the scorer is more bullish than the LLM
        (which has full narrative context), the badge follows the LLM so the
        rating always matches the written verdict. This is THE reconciliation —
        every surface (web, PDF, portfolio engine, weekly signals) must read a
        rating that has passed through here rather than re-deriving its own.
        """
        if not llm_recommendation or rating not in cls._TIER_ORDER:
            return rating
        rec = cls.normalize_recommendation(llm_recommendation)
        if rec not in cls._TIER_ORDER:
            return rating
        if cls._TIER_ORDER.index(rec) < cls._TIER_ORDER.index(rating):
            return rec
        return rating

    @classmethod
    def derive_rating(
        cls,
        moat_score: float,
        technical_score: float = None,
        llm_recommendation: str = None,
        valuation_score: float = None,
    ) -> Tuple[str, float]:
        """
        Canonical rating derivation: base thresholds + technical override +
        LLM reconciliation, in one place. Use this instead of re-implementing
        thresholds (the audit found six divergent copies).
        """
        rating, score = cls.determine_rating(
            moat_score, technical_score=technical_score, valuation_score=valuation_score
        )
        return cls.reconcile_rating(rating, llm_recommendation), score

    # Tier boundaries on the NORMALIZED scale (centred at 5.0, ~2 points per
    # standard deviation). Roughly thirds: a company one sigma above typical is
    # "high", one sigma below is "low".
    QUALITY_HIGH = 6.5
    QUALITY_LOW = 4.5
    VALUATION_ATTRACTIVE = 6.5
    VALUATION_EXPENSIVE = 4.0

    # quality tier -> valuation tier -> rating.
    #
    # Reading the pair is the point. A single blended score cannot distinguish
    # "excellent business, priced for perfection" from "average business,
    # fairly priced" — both land mid-scale — yet they call for opposite
    # actions. The diagonal is where the two axes disagree, and that is where
    # the judgment lives: high quality at a rich price is a watchlist, not a
    # buy; low quality at a cheap price is a value trap, not a bargain.
    #
    # THE AXES ARE NOT SYMMETRIC, and the matrix reflects that deliberately.
    # Quality is a durable property computed from financials — a business
    # earning 20% on capital will very likely still be earning it next
    # quarter. Valuation is a market state that mean-reverts on a timescale
    # nobody can predict; expensive stocks stay expensive for years, and
    # multiple compression is a poor timing signal. So price alone never
    # produces a sell: every SELL cell requires LOW quality. A rich multiple
    # can withhold a buy, and it can deepen a sell on an already-weak
    # business, but it cannot condemn a healthy one.
    #
    # That distinction also resolves a conflation. To someone who does not own
    # the stock, "expensive" means don't buy — which is HOLD. To an owner,
    # SELL means exit. Sending "exit" when the message is "don't add" is how
    # a framework talks people out of compounders three years early.
    _RATING_MATRIX = {
        "high": {
            "attractive": "STRONG BUY",
            "fair": "BUY",
            "expensive": "HOLD",
        },
        "mid": {
            "attractive": "BUY",
            "fair": "HOLD",
            # Sound business, unattractive price: do not add, do not exit.
            "expensive": "HOLD",
        },
        "low": {
            "attractive": "HOLD",
            # Weak business with no compensating discount — here the quality
            # axis is doing the work and valuation merely declines to rescue it.
            "fair": "SELL",
            "expensive": "STRONG SELL",
        },
    }

    @classmethod
    def _quality_tier(cls, quality_score: float) -> str:
        if quality_score >= cls.QUALITY_HIGH:
            return "high"
        if quality_score >= cls.QUALITY_LOW:
            return "mid"
        return "low"

    @classmethod
    def _valuation_tier(cls, valuation_score: float) -> str:
        if valuation_score >= cls.VALUATION_ATTRACTIVE:
            return "attractive"
        if valuation_score >= cls.VALUATION_EXPENSIVE:
            return "fair"
        return "expensive"

    @classmethod
    def determine_rating(
        cls,
        moat_score: float,
        technical_score: float = None,
        valuation_score: float = None,
    ) -> Tuple[str, float]:
        """
        Derive the 5-tier rating from the quality and valuation axes.

        v4.0. Previously a single blended composite was thresholded at
        8.5/7.0/5.0/3.0. Because that composite averaged five 0-10 components,
        its spread was far narrower than any component's, so observed scores
        clustered in roughly 5.5-7.5 and three of the five tiers were close to
        unreachable — a two-tier system wearing five. Worse, the composite
        contained the valuation score, so quality and cheapness partially
        cancelled and the number could not say which was driving it.

        Quality and valuation are now separate axes read through a matrix.
        STRONG BUY requires a genuinely good business AND an attractive price;
        SELL and STRONG SELL become reachable for weak businesses rather than
        being arithmetically out of range.

        Manager Technical Override (retained):
        When technical_score < 4.0 — a confirmed bearish structure — a BUY or
        better steps down one tier. Strong balance sheets do not stop
        downtrends, so the actionable rating reflects investable reality.

        Args:
            moat_score: Quality score, normalized scale (0-10)
            technical_score: Technical score (0-10); below 4.0 downgrades one tier
            valuation_score: Valuation score, normalized scale (0-10), higher =
                more attractive. When absent the valuation axis is treated as
                "fair", which reduces the matrix to a quality-only read.

        Returns:
            Tuple of (rating_name, numeric_score)
        """
        quality_tier = cls._quality_tier(moat_score)
        valuation_tier = (
            cls._valuation_tier(valuation_score) if valuation_score is not None else "fair"
        )

        base_rating = cls._RATING_MATRIX[quality_tier][valuation_tier]

        # Manager technical override: broken technicals drop the actionable rating
        # one tier for BUY-or-above stocks. HOLD/SELL/STRONG SELL are already cautious.
        if technical_score is not None and technical_score < 4.0:
            idx = cls._TIER_ORDER.index(base_rating)
            if idx >= 3:  # BUY or STRONG BUY → downgrade one step
                base_rating = cls._TIER_ORDER[idx - 1]

        logger.info(
            f"Rating matrix: quality {moat_score:.2f} ({quality_tier}) x "
            f"valuation {valuation_score if valuation_score is None else f'{valuation_score:.2f}'} "
            f"({valuation_tier}) → {base_rating}"
        )
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
