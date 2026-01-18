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
)


class TechnicalScorer:
    """
    Scores technical indicators on a 0-10 scale.

    Weights:
    - Trend (35%): SMA 50/200, crossovers
    - Momentum (25%): RSI
    - Volume (15%): Volume trends
    - Relative Strength (25%): Performance vs sector/market
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
        momentum_score = self._score_momentum(indicators.rsi)
        volume_score = self._score_volume(indicators.volume)
        rs_score = self._score_relative_strength(indicators.relative_strength)

        return TechnicalScoreBreakdown(
            trend_score=trend_score,
            momentum_score=momentum_score,
            volume_score=volume_score,
            relative_strength_score=rs_score,
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

    def _score_momentum(self, rsi) -> float:
        """
        Score momentum based on RSI.

        Scoring logic:
        - RSI 40-60: 8-10 (neutral/healthy)
        - RSI 30-40 or 60-70: 6-8 (mild extremes)
        - RSI < 30 (oversold): 4-6 (potential reversal)
        - RSI > 70 (overbought): 4-6 (potential reversal)
        - RSI < 20 or > 80: 2-4 (extreme conditions)
        """
        score = 5.0  # Neutral baseline

        if rsi.rsi_14 is None:
            logger.warning("No RSI data for scoring")
            return score

        rsi_value = rsi.rsi_14

        # Score based on RSI ranges
        if 45 <= rsi_value <= 55:
            score = 10.0  # Perfectly neutral
        elif 40 <= rsi_value < 45 or 55 < rsi_value <= 60:
            score = 9.0  # Slightly off-neutral, healthy
        elif 35 <= rsi_value < 40 or 60 < rsi_value <= 65:
            score = 7.5  # Mild momentum
        elif 30 <= rsi_value < 35 or 65 < rsi_value <= 70:
            score = 6.0  # Approaching extremes
        elif 25 <= rsi_value < 30 or 70 < rsi_value <= 75:
            score = 5.0  # Oversold/overbought territory
        elif 20 <= rsi_value < 25 or 75 < rsi_value <= 80:
            score = 4.0  # Deep oversold/overbought
        else:  # < 20 or > 80
            score = 2.5  # Extreme conditions

        return round(score, 1)

    def _score_volume(self, volume) -> float:
        """
        Score volume trends.

        Scoring logic:
        - Increasing volume: 7-10 (confirms price action)
        - Stable volume: 5-7 (neutral)
        - Decreasing volume: 3-5 (lack of conviction)
        - High volume ratio (>1.5x): Bonus points
        """
        score = 5.0  # Neutral baseline

        # Check for data
        if volume.volume_ratio is None:
            logger.warning("No volume data for scoring")
            return score

        # Base score on trend
        if volume.volume_trend == VolumeTrend.INCREASING:
            score = 8.0
        elif volume.volume_trend == VolumeTrend.STABLE:
            score = 6.0
        else:  # DECREASING
            score = 4.0

        # Adjust based on volume ratio
        if volume.volume_ratio > 2.0:
            score += 1.5  # Very high volume
        elif volume.volume_ratio > 1.5:
            score += 1.0  # High volume
        elif volume.volume_ratio < 0.5:
            score -= 1.0  # Very low volume
        elif volume.volume_ratio < 0.7:
            score -= 0.5  # Low volume

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
