"""
Earnings momentum calculator for the Fundamentalist agent.

Calculates composite momentum score from:
- Estimate revisions (40% weight) - PRIMARY SIGNAL
- Surprise pattern (35% weight)
- Analyst sentiment (25% weight)
"""
from typing import Optional, Dict, Tuple, Any
import pandas as pd
from research_swarm.logger import logger


class EarningsCalculator:
    """Calculates earnings momentum score from analyst data."""

    def calculate_momentum_score(
        self,
        earnings_data: Optional[Dict[str, Any]]
    ) -> Tuple[float, Dict[str, Any]]:
        """
        Calculate composite momentum score (0-10).

        Formula:
            momentum = (
                estimate_revisions * 0.57 +  # PRIMARY SIGNAL
                surprise_pattern * 0.43
            )

        Analyst sentiment (ratings/price targets) is intentionally excluded here.
        It is captured as a dedicated signal in the signal_divergence layer, where
        it belongs. Counting it here AND in divergence double-weighted consensus errors.

        Args:
            earnings_data: Dict with keys:
                - recommendations: DataFrame from yfinance
                - earnings_history: DataFrame from yfinance
                - price_target: Dict from yfinance
                - earnings_dates: DataFrame from yfinance

        Returns:
            Tuple of (momentum_score, breakdown_dict)
        """
        if not earnings_data:
            logger.warning("No earnings data provided, returning neutral momentum")
            return self._neutral_momentum()

        # Calculate 2 components
        revision_score = self._score_estimate_revisions(earnings_data)
        surprise_score = self._score_surprise_pattern(earnings_data)

        # Weighted composite
        momentum_score = (
            revision_score * 0.57 +
            surprise_score * 0.43
        )

        # Classify momentum
        if momentum_score >= 7.0:
            classification = "Accelerating"
        elif momentum_score >= 4.0:
            classification = "Stable"
        else:
            classification = "Decelerating"

        breakdown = {
            "momentum_score": round(momentum_score, 1),
            "classification": classification,
            "estimate_revision_score": round(revision_score, 1),
            "surprise_pattern_score": round(surprise_score, 1),
        }

        logger.debug(f"Momentum breakdown: {breakdown}")
        return momentum_score, breakdown

    def _score_estimate_revisions(self, earnings_data: Dict) -> float:
        """
        Score EPS estimate revisions (0-10).

        Primary source is yfinance's `eps_revisions` frame — the count of
        analysts raising vs lowering their EPS estimates over the last 30 days.
        That is the actual estimate-revision series this signal is named for.

        The previous implementation branched on `Action` or `To Grade` /
        `From Grade` columns of the recommendations frame. Modern yfinance
        returns the SUMMARY frame instead (period, strongBuy, buy, hold, sell,
        strongSell), so neither branch ever matched, `total` was always 0, and
        the function returned a constant 5.0 — for a leg carrying 57% of
        earnings momentum, itself ~20-25% of the quality score. The composite
        was mathematically confined to [3.49, 7.15] on an advertised 0-10.

        Falls back to the legacy grade inference when revisions are absent, so
        tickers with thin estimate coverage still get whatever signal exists.

        Returns:
            Score from 0-10
        """
        revision_score = self._score_from_eps_revisions(earnings_data.get("eps_revisions"))
        if revision_score is not None:
            return revision_score

        recommendations = earnings_data.get("recommendations")
        if recommendations is None or (isinstance(recommendations, pd.DataFrame) and recommendations.empty):
            logger.debug("No recommendations data, using neutral revision score")
            return 5.0

        try:
            # Analyze recent recommendations (last 30 rows, ~3-6 months)
            recent = recommendations.tail(30) if isinstance(recommendations, pd.DataFrame) else pd.DataFrame()

            if recent.empty:
                return 5.0

            # Count upgrades vs downgrades
            upgrades = 0
            downgrades = 0

            if "Action" in recent.columns:
                upgrades = len(recent[recent["Action"].str.lower().str.contains("up", na=False)])
                downgrades = len(recent[recent["Action"].str.lower().str.contains("down", na=False)])
            elif "To Grade" in recent.columns and "From Grade" in recent.columns:
                # Infer from grade changes
                grade_values = {
                    "strong buy": 5, "buy": 4, "outperform": 4,
                    "hold": 3, "neutral": 3,
                    "underperform": 2, "sell": 1, "strong sell": 0
                }

                for _, row in recent.iterrows():
                    to_grade = str(row.get("To Grade", "")).lower()
                    from_grade = str(row.get("From Grade", "")).lower()

                    to_val = grade_values.get(to_grade, 3)
                    from_val = grade_values.get(from_grade, 3)

                    if to_val > from_val:
                        upgrades += 1
                    elif to_val < from_val:
                        downgrades += 1

            # Calculate net revision score
            total = upgrades + downgrades
            if total == 0:
                return 5.0

            upgrade_ratio = upgrades / total

            # Score based on upgrade ratio
            if upgrade_ratio > 0.7:  # >70% upgrades
                score = 9.0
            elif upgrade_ratio > 0.6:  # >60% upgrades
                score = 7.5
            elif upgrade_ratio > 0.5:  # >50% upgrades
                score = 6.0
            elif upgrade_ratio >= 0.4:  # Balanced
                score = 5.0
            elif upgrade_ratio >= 0.3:  # More downgrades
                score = 4.0
            else:  # Mostly downgrades
                score = 2.0

            logger.debug(f"Revision score: {score:.1f} (upgrades: {upgrades}, downgrades: {downgrades})")
            return score

        except Exception as e:
            logger.error(f"Error scoring estimate revisions: {e}")
            return 5.0

    # Annual estimate periods drive valuation; quarterly noise does not.
    _REVISION_PERIODS = ("0y", "+1y")
    _MIN_REVISION_SAMPLE = 3

    def _score_from_eps_revisions(self, revisions) -> Optional[float]:
        """Score net revision breadth from yfinance's eps_revisions frame.

        Breadth is normalized — (up - down) / (up + down) — rather than a raw
        net count, so a 40-analyst mega-cap and a 5-analyst small cap are on
        the same scale. Returns None when the frame is missing or the sample
        is too small to read, so the caller can fall back.
        """
        if revisions is None:
            return None

        try:
            if isinstance(revisions, pd.DataFrame):
                if revisions.empty:
                    return None
                rows = revisions.to_dict(orient="index")
            elif isinstance(revisions, dict):
                rows = revisions
            else:
                return None

            up = down = 0
            for period, values in rows.items():
                if str(period) not in self._REVISION_PERIODS:
                    continue
                if not isinstance(values, dict):
                    continue
                up += int(values.get("upLast30days") or 0)
                down += int(values.get("downLast30days") or 0)

            total = up + down
            if total < self._MIN_REVISION_SAMPLE:
                logger.debug(f"EPS revision sample too small ({total}) — falling back")
                return None

            breadth = (up - down) / total

            # Bands are centred on roughly +0.4, not 0. Aggregate revision
            # breadth is right-skewed — sell-side analysts raise estimates more
            # often than they cut — so a symmetric scale puts most of the market
            # in the top bucket and discriminates no better than the constant it
            # replaced. Measured across an 18-name spread the observed median
            # breadth was ~+0.5, so a merely positive tape scores mid-range and
            # only near-unanimous revisions reach the top.
            if breadth >= 0.90:
                score = 9.0
            elif breadth >= 0.75:
                score = 8.0
            elif breadth >= 0.55:
                score = 7.0
            elif breadth >= 0.35:
                score = 6.0
            elif breadth >= 0.15:
                score = 5.0
            elif breadth >= -0.10:
                score = 4.0
            elif breadth >= -0.35:
                score = 3.0
            else:
                score = 2.0

            logger.info(
                f"EPS revisions (30d, annual periods): {up} up / {down} down "
                f"→ breadth {breadth:+.2f} → score {score:.1f}/10"
            )
            return score

        except Exception as e:
            logger.warning(f"Could not score EPS revisions: {e}")
            return None

    def _score_surprise_pattern(self, earnings_data: Dict) -> float:
        """
        Score earnings surprise pattern (0-10).

        Analyzes last 4 quarters:
        - Beat vs miss pattern
        - Average surprise %

        Args:
            earnings_data: Dict with earnings_history DataFrame

        Returns:
            Score from 0-10
        """
        earnings_history = earnings_data.get("earnings_history")
        if earnings_history is None or (isinstance(earnings_history, pd.DataFrame) and earnings_history.empty):
            logger.debug("No earnings history, using neutral surprise score")
            return 5.0

        try:
            # Get last 4 quarters
            recent = earnings_history.head(4) if isinstance(earnings_history, pd.DataFrame) else pd.DataFrame()

            if recent.empty:
                return 5.0

            beats = 0
            surprise_pcts = []

            for _, row in recent.iterrows():
                # Check if beat or miss
                eps_est = row.get("epsEstimate") or row.get("Estimate")
                eps_actual = row.get("epsActual") or row.get("Actual")

                if eps_est is not None and eps_actual is not None:
                    # Calculate surprise %
                    if eps_est != 0:
                        surprise_pct = ((eps_actual - eps_est) / abs(eps_est)) * 100
                        surprise_pcts.append(surprise_pct)

                        if eps_actual > eps_est:
                            beats += 1

            if len(surprise_pcts) == 0:
                return 5.0

            # Calculate metrics
            beat_ratio = beats / len(surprise_pcts)
            avg_surprise = sum(surprise_pcts) / len(surprise_pcts)

            # Score based on beat pattern and avg surprise
            if beat_ratio == 1.0 and avg_surprise > 5.0:  # Beat 4/4 with >5% avg
                score = 10.0
            elif beat_ratio == 1.0:  # Beat 4/4
                score = 8.5
            elif beat_ratio >= 0.75 and avg_surprise > 0:  # Beat 3/4 with positive avg
                score = 7.0
            elif beat_ratio >= 0.75:  # Beat 3/4
                score = 6.0
            elif beat_ratio >= 0.5:  # Mixed
                score = 5.0
            elif beat_ratio >= 0.25:  # More misses
                score = 3.5
            else:  # Mostly misses
                score = 1.5

            logger.debug(f"Surprise score: {score:.1f} (beats: {beats}/{len(surprise_pcts)}, avg: {avg_surprise:.1f}%)")
            return score

        except Exception as e:
            logger.error(f"Error scoring surprise pattern: {e}")
            return 5.0

    def _score_analyst_sentiment(self, earnings_data: Dict) -> float:
        """
        Score analyst sentiment (0-10).

        Uses:
        - Ratings distribution (Strong Buy/Buy/Hold/Sell/Strong Sell)
        - Price target upside %

        Args:
            earnings_data: Dict with price_target data

        Returns:
            Score from 0-10
        """
        price_target = earnings_data.get("price_target")
        if not price_target:
            logger.debug("No price target data, using neutral sentiment score")
            return 5.0

        try:
            current_price = price_target.get("current_price")
            target_mean = price_target.get("target_mean")
            recommendation = price_target.get("recommendation")

            # Calculate price target upside
            upside_pct = 0.0
            if current_price and target_mean and current_price > 0:
                upside_pct = ((target_mean - current_price) / current_price) * 100

            # Score based on recommendation
            rec_score = 5.0  # Default neutral
            if recommendation:
                rec_map = {
                    "strong buy": 9.0, "buy": 7.5, "outperform": 7.0,
                    "hold": 5.0, "neutral": 5.0,
                    "underperform": 3.0, "sell": 2.0, "strong sell": 1.0
                }
                rec_score = rec_map.get(recommendation.lower(), 5.0)

            # Score based on upside
            if upside_pct > 30:  # >30% upside
                upside_score = 10.0
            elif upside_pct > 20:  # >20% upside
                upside_score = 8.0
            elif upside_pct > 10:  # >10% upside
                upside_score = 6.5
            elif upside_pct > 0:  # Positive upside
                upside_score = 5.5
            elif upside_pct > -10:  # Small downside
                upside_score = 4.0
            else:  # Significant downside
                upside_score = 2.0

            # Weighted average (recommendation 60%, upside 40%)
            score = rec_score * 0.6 + upside_score * 0.4

            logger.debug(f"Sentiment score: {score:.1f} (rec: {recommendation}, upside: {upside_pct:.1f}%)")
            return score

        except Exception as e:
            logger.error(f"Error scoring analyst sentiment: {e}")
            return 5.0

    def _neutral_momentum(self) -> Tuple[float, Dict[str, Any]]:
        """Return neutral momentum when no data available."""
        return 5.0, {
            "momentum_score": 5.0,
            "classification": "Stable",
            "estimate_revision_score": 5.0,
            "surprise_pattern_score": 5.0,
        }


# Global instance
earnings_calculator = EarningsCalculator()
