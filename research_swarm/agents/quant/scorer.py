"""
Scoring logic for the Quant agent.

Calculates technical and supply chain scores based on quantitative metrics.
"""
from typing import Optional
from loguru import logger

from .models import (
    TechnicalIndicators,
    TechnicalScoreBreakdown,
    SupplyChainGraph,
    SupplyChainScoreBreakdown,
    CrossoverSignal,
    RSISignal,
    VolumeTrend,
    NodeType,
    MACDSignal,
    BollingerPosition,
    StochasticSignal,
)


class TechnicalScorer:
    """
    Scores technical indicators on a 0-10 scale.

    Weights:
    - Trend (30%): SMA 50/200, crossovers
    - Momentum (25%): RSI, MACD, Stochastic
    - Volume (15%): Volume trends, volume profile
    - Relative Strength (20%): Performance vs sector/market
    - Volatility (10%): Bollinger Bands
    """

    def score_technical(self, indicators: TechnicalIndicators) -> TechnicalScoreBreakdown:
        """
        Calculate technical score breakdown.

        Args:
            indicators: TechnicalIndicators model

        Returns:
            TechnicalScoreBreakdown with component scores
        """
        trend_score = self._score_trend(indicators.moving_averages)
        momentum_score = self._score_momentum(
            indicators.rsi,
            indicators.macd,
            indicators.stochastic
        )
        volume_score = self._score_volume(
            indicators.volume,
            indicators.volume_profile
        )
        rs_score = self._score_relative_strength(indicators.relative_strength)
        volatility_score = self._score_volatility(indicators.bollinger_bands)

        return TechnicalScoreBreakdown(
            trend_score=trend_score,
            momentum_score=momentum_score,
            volume_score=volume_score,
            relative_strength_score=rs_score,
            volatility_score=volatility_score,
        )

    def _score_trend(self, ma) -> float:
        """
        Score trend based on moving averages.

        Scoring logic:
        - Golden cross + price above both SMAs: 9-10
        - Price above both SMAs (no crossover): 7-8
        - Price above SMA50 only: 5-6
        - Price between SMAs: 4-5
        - Death cross + price below both SMAs: 1-2
        - Price below both SMAs (no crossover): 2-3
        """
        score = 5.0  # Neutral baseline

        # Check if we have data
        if ma.sma_50 is None or ma.sma_200 is None or ma.current_price is None:
            logger.warning("Insufficient moving average data for scoring")
            return score

        price = ma.current_price
        sma50 = ma.sma_50
        sma200 = ma.sma_200

        # Determine position relative to SMAs
        above_50 = price > sma50
        above_200 = price > sma200
        sma50_above_200 = sma50 > sma200

        # Score based on configuration
        if ma.crossover_signal == CrossoverSignal.GOLDEN_CROSS:
            # Recent golden cross
            if above_50 and above_200:
                score = 9.5  # Strong bullish signal
            else:
                score = 8.0  # Golden cross but price hasn't confirmed
        elif ma.crossover_signal == CrossoverSignal.DEATH_CROSS:
            # Recent death cross
            if not above_50 and not above_200:
                score = 1.5  # Strong bearish signal
            else:
                score = 3.0  # Death cross but price hasn't confirmed
        else:
            # No recent crossover - score based on position
            if above_50 and above_200 and sma50_above_200:
                score = 7.5  # Established uptrend
            elif above_50 and above_200 and not sma50_above_200:
                score = 6.5  # Price strong but SMAs not aligned
            elif above_50 and not above_200:
                score = 5.5  # Mixed signals
            elif not above_50 and above_200:
                score = 4.5  # Weakening
            elif not above_50 and not above_200 and not sma50_above_200:
                score = 2.5  # Established downtrend
            else:
                score = 3.5  # Price weak but SMAs not aligned

        return round(score, 1)

    def _score_momentum(self, rsi, macd, stochastic) -> float:
        """
        Score momentum based on RSI, MACD, and Stochastic.

        Scoring logic combines all three oscillators:
        - RSI: 40% weight
        - MACD: 35% weight
        - Stochastic: 25% weight
        """
        # RSI score (0-10)
        rsi_score = 5.0
        if rsi.rsi_14 is not None:
            rsi_value = rsi.rsi_14
            if 45 <= rsi_value <= 55:
                rsi_score = 10.0
            elif 40 <= rsi_value < 45 or 55 < rsi_value <= 60:
                rsi_score = 9.0
            elif 35 <= rsi_value < 40 or 60 < rsi_value <= 65:
                rsi_score = 7.5
            elif 30 <= rsi_value < 35 or 65 < rsi_value <= 70:
                rsi_score = 6.0
            elif 25 <= rsi_value < 30 or 70 < rsi_value <= 75:
                rsi_score = 5.0
            elif 20 <= rsi_value < 25 or 75 < rsi_value <= 80:
                rsi_score = 4.0
            else:
                rsi_score = 2.5

        # MACD score (0-10)
        macd_score = 5.0
        if macd.macd_signal == MACDSignal.BULLISH:
            # MACD above signal line - bullish momentum
            if macd.histogram and macd.histogram > 0:
                macd_score = 8.5  # Strong bullish
            else:
                macd_score = 7.0  # Mild bullish
        elif macd.macd_signal == MACDSignal.BEARISH:
            # MACD below signal line - bearish momentum
            if macd.histogram and macd.histogram < 0:
                macd_score = 2.5  # Strong bearish
            else:
                macd_score = 4.0  # Mild bearish
        else:
            macd_score = 5.0  # Neutral

        # Stochastic score (0-10)
        stoch_score = 5.0
        if stochastic.k_value is not None:
            k_val = stochastic.k_value
            if stochastic.stochastic_signal == StochasticSignal.OVERSOLD:
                # Oversold - potential bounce (bullish)
                if k_val < 10:
                    stoch_score = 7.5  # Extremely oversold
                else:
                    stoch_score = 6.5  # Oversold
            elif stochastic.stochastic_signal == StochasticSignal.OVERBOUGHT:
                # Overbought - potential pullback (bearish)
                if k_val > 90:
                    stoch_score = 2.5  # Extremely overbought
                else:
                    stoch_score = 3.5  # Overbought
            else:
                # Neutral range (20-80)
                if 40 <= k_val <= 60:
                    stoch_score = 8.0  # Healthy middle range
                else:
                    stoch_score = 6.5  # Moving towards extremes

        # Weighted average
        combined_score = (
            rsi_score * 0.40 +
            macd_score * 0.35 +
            stoch_score * 0.25
        )

        return round(combined_score, 1)

    def _score_volume(self, volume, volume_profile) -> float:
        """
        Score volume trends and volume profile.

        Scoring logic:
        - Volume trend (60% weight)
        - Volume profile (40% weight)
        """
        # Volume trend score
        trend_score = 5.0
        if volume.volume_ratio is not None:
            if volume.volume_trend == VolumeTrend.INCREASING:
                trend_score = 8.0
            elif volume.volume_trend == VolumeTrend.STABLE:
                trend_score = 6.0
            else:  # DECREASING
                trend_score = 4.0

            # Adjust based on volume ratio
            if volume.volume_ratio > 2.0:
                trend_score += 1.5
            elif volume.volume_ratio > 1.5:
                trend_score += 1.0
            elif volume.volume_ratio < 0.5:
                trend_score -= 1.0
            elif volume.volume_ratio < 0.7:
                trend_score -= 0.5

            trend_score = max(0.0, min(10.0, trend_score))

        # Volume profile score (based on key levels quality)
        profile_score = 5.0
        if volume_profile.key_levels:
            # More key levels = better defined support/resistance
            num_levels = len(volume_profile.key_levels)
            if num_levels >= 4:
                profile_score = 8.0
            elif num_levels >= 3:
                profile_score = 7.0
            elif num_levels >= 2:
                profile_score = 6.0
            else:
                profile_score = 5.0

            # Bonus for high concentration at POC
            max_concentration = max([level.volume_concentration for level in volume_profile.key_levels])
            if max_concentration > 0.15:  # >15% volume at one level
                profile_score += 1.0
            elif max_concentration > 0.10:  # >10% volume
                profile_score += 0.5

            profile_score = min(10.0, profile_score)

        # Weighted combination
        combined_score = (trend_score * 0.60) + (profile_score * 0.40)

        return round(combined_score, 1)

    def _score_volatility(self, bollinger) -> float:
        """
        Score volatility based on Bollinger Bands.

        Scoring logic:
        - Low volatility (narrow bands): 7-9 (potential breakout setup)
        - Medium volatility: 5-7 (normal conditions)
        - High volatility (wide bands): 3-5 (risk of whipsaw)
        - Price position relative to bands also factors in
        """
        score = 5.0  # Neutral baseline

        if bollinger.bandwidth is None:
            logger.warning("No Bollinger Band data for scoring")
            return score

        # Base score on bandwidth (volatility)
        bandwidth = bollinger.bandwidth

        if bandwidth < 0.05:  # Very low volatility
            score = 8.5  # Potential breakout setup (high score = good)
        elif bandwidth < 0.10:  # Low volatility
            score = 7.5
        elif bandwidth < 0.15:  # Moderate volatility
            score = 6.5
        elif bandwidth < 0.20:  # Elevated volatility
            score = 5.5
        elif bandwidth < 0.30:  # High volatility
            score = 4.0
        else:  # Extreme volatility
            score = 2.5

        # Adjust based on price position (extreme positions reduce score)
        if bollinger.position == BollingerPosition.ABOVE_UPPER:
            score -= 1.0  # Overbought territory
        elif bollinger.position == BollingerPosition.BELOW_LOWER:
            score -= 1.0  # Oversold territory
        elif bollinger.position == BollingerPosition.MIDDLE:
            score += 0.5  # Stable position

        # Clamp to 0-10
        score = max(0.0, min(10.0, score))

        return round(score, 1)

    def _score_relative_strength(self, rs) -> float:
        """
        Score relative strength vs sector and market.

        Scoring logic:
        - Outperforming both sector and market: 8-10
        - Outperforming one, in-line with other: 6-8
        - In-line with both: 5-6
        - Underperforming one: 3-5
        - Underperforming both: 1-3
        """
        score = 5.0  # Neutral baseline

        # Check for data
        if rs.vs_sector_3m is None or rs.vs_market_3m is None:
            logger.warning("Insufficient relative strength data for scoring")
            return score

        # Use 3-month data (more reliable than 1-month)
        vs_sector = rs.vs_sector_3m
        vs_market = rs.vs_market_3m

        # Score based on outperformance
        if vs_sector > 5 and vs_market > 5:
            score = 9.5  # Strong outperformance
        elif vs_sector > 2 and vs_market > 2:
            score = 8.0  # Moderate outperformance
        elif vs_sector > 0 and vs_market > 0:
            score = 7.0  # Slight outperformance
        elif vs_sector > 0 or vs_market > 0:
            score = 6.0  # Mixed performance
        elif vs_sector > -2 and vs_market > -2:
            score = 5.0  # In-line
        elif vs_sector > -5 and vs_market > -5:
            score = 4.0  # Slight underperformance
        elif vs_sector > -5 or vs_market > -5:
            score = 3.0  # Mixed but weak
        else:
            score = 2.0  # Significant underperformance

        return round(score, 1)


class SupplyChainScorer:
    """
    Scores supply chain resilience on a 0-10 scale.

    Weights:
    - Diversification (30%): Number and diversity of suppliers
    - Tier Depth (20%): Visibility into tier-2/3
    - Critical Path (25%): Resilience of critical paths
    - Hidden Dependencies (25%): Risk from shared dependencies
    """

    def score_supply_chain(self, graph: SupplyChainGraph) -> SupplyChainScoreBreakdown:
        """
        Calculate supply chain score breakdown.

        Args:
            graph: SupplyChainGraph model

        Returns:
            SupplyChainScoreBreakdown with component scores
        """
        diversification_score = self._score_diversification(graph)
        tier_depth_score = self._score_tier_depth(graph)
        critical_path_score = self._score_critical_paths(graph)
        hidden_dep_score = self._score_hidden_dependencies(graph)

        return SupplyChainScoreBreakdown(
            diversification_score=diversification_score,
            tier_depth_score=tier_depth_score,
            critical_path_score=critical_path_score,
            hidden_dependency_score=hidden_dep_score,
        )

    def _score_diversification(self, graph: SupplyChainGraph) -> float:
        """
        Score supplier diversification.

        Scoring logic:
        - 10+ suppliers: 9-10
        - 7-9 suppliers: 7-8
        - 4-6 suppliers: 5-6
        - 2-3 suppliers: 3-4
        - 0-1 suppliers: 1-2
        """
        # Count tier-1 suppliers
        tier1_suppliers = [n for n in graph.nodes if n.node_type == NodeType.SUPPLIER]
        count = len(tier1_suppliers)

        if count >= 10:
            score = 9.5
        elif count >= 7:
            score = 7.5
        elif count >= 4:
            score = 5.5
        elif count >= 2:
            score = 3.5
        elif count == 1:
            score = 2.0
        else:
            score = 1.0

        return round(score, 1)

    def _score_tier_depth(self, graph: SupplyChainGraph) -> float:
        """
        Score tier depth (visibility into supply chain).

        Scoring logic:
        - Depth 3+: 9-10 (excellent visibility)
        - Depth 2: 7-8 (good visibility)
        - Depth 1: 4-5 (limited visibility)
        - Depth 0: 1-2 (no visibility)
        """
        depth = graph.max_depth

        # Count tier-2 nodes
        tier2_count = len([n for n in graph.nodes if n.node_type == NodeType.SUPPLIER_T2])

        if depth >= 3:
            score = 9.5
        elif depth == 2 and tier2_count >= 5:
            score = 8.0
        elif depth == 2 and tier2_count >= 2:
            score = 7.0
        elif depth == 2:
            score = 6.0
        elif depth == 1:
            score = 4.5
        else:
            score = 1.5

        return round(score, 1)

    def _score_critical_paths(self, graph: SupplyChainGraph) -> float:
        """
        Score critical path resilience.

        Scoring logic:
        - Multiple short paths: 9-10 (resilient)
        - Mix of short and long paths: 6-8 (moderate)
        - Few long paths: 3-5 (vulnerable)
        - Single long path: 1-2 (very vulnerable)
        """
        paths = graph.critical_paths

        if not paths:
            return 5.0  # No paths identified

        # Analyze path lengths
        path_lengths = [len(p) for p in paths]
        avg_length = sum(path_lengths) / len(path_lengths)
        max_length = max(path_lengths)
        num_paths = len(paths)

        # Score based on redundancy and length
        if num_paths >= 5 and avg_length <= 3:
            score = 9.0  # Many short paths = resilient
        elif num_paths >= 3 and avg_length <= 4:
            score = 7.5  # Moderate redundancy
        elif num_paths >= 2:
            score = 6.0  # Some redundancy
        elif max_length <= 3:
            score = 5.0  # Single but short path
        else:
            score = 3.0  # Single long path

        return round(score, 1)

    def _score_hidden_dependencies(self, graph: SupplyChainGraph) -> float:
        """
        Score hidden dependency risk (inverse - fewer is better).

        Scoring logic:
        - 0 hidden deps: 10 (no shared dependencies)
        - 1 hidden dep: 7-8 (minor risk)
        - 2-3 hidden deps: 5-6 (moderate risk)
        - 4+ hidden deps: 2-4 (high risk)
        """
        count = len(graph.hidden_dependencies)

        if count == 0:
            score = 10.0
        elif count == 1:
            score = 7.5
        elif count == 2:
            score = 6.0
        elif count == 3:
            score = 5.0
        elif count == 4:
            score = 4.0
        else:
            score = 2.5

        return round(score, 1)
