"""
Tests for the Quant agent.
"""
import pytest
import pandas as pd
import numpy as np
from research_swarm.agents.quant import (
    analyze_quant,
    MovingAverages,
    RSIData,
    VolumeAnalysis,
    TechnicalScoreBreakdown,
    SupplyChainScoreBreakdown,
    SupplyChainNode,
    SupplyChainGraph,
    QuantOutput,
    CrossoverSignal,
    RSISignal,
    VolumeTrend,
    NodeType,
)
from research_swarm.agents.quant.technical import calculate_sma, calculate_rsi
from research_swarm.agents.fundamentalist.models import SupplyChainOutput


# ============================================================================
# Unit Tests: Pydantic Models
# ============================================================================

def test_technical_score_breakdown_weighted_average():
    """Test that technical score weighted average calculation is correct."""
    breakdown = TechnicalScoreBreakdown(
        trend_score=8.0,
        momentum_score=7.0,
        volume_score=6.0,
        relative_strength_score=8.0
    )

    expected = (
        8.0 * 0.35 +  # trend: 35%
        7.0 * 0.25 +  # momentum: 25%
        6.0 * 0.15 +  # volume: 15%
        8.0 * 0.25    # relative_strength: 25%
    )

    assert abs(breakdown.weighted_average() - expected) < 0.01
    assert abs(breakdown.weighted_average() - 7.45) < 0.01


def test_supply_chain_score_breakdown_weighted_average():
    """Test that supply chain score weighted average calculation is correct."""
    breakdown = SupplyChainScoreBreakdown(
        diversification_score=8.0,
        tier_depth_score=7.0,
        critical_path_score=6.0,
        hidden_dependency_score=9.0
    )

    expected = (
        8.0 * 0.30 +  # diversification: 30%
        7.0 * 0.20 +  # tier_depth: 20%
        6.0 * 0.25 +  # critical_path: 25%
        9.0 * 0.25    # hidden_dependency: 25%
    )

    assert abs(breakdown.weighted_average() - expected) < 0.01
    assert abs(breakdown.weighted_average() - 7.55) < 0.01


def test_score_breakdown_validation():
    """Test that scores must be between 0 and 10."""
    # Valid scores
    breakdown = TechnicalScoreBreakdown(
        trend_score=0.0,
        momentum_score=5.0,
        volume_score=10.0,
        relative_strength_score=7.5
    )
    assert breakdown.trend_score == 0.0
    assert breakdown.volume_score == 10.0

    # Invalid scores should raise validation error
    with pytest.raises(ValueError):
        TechnicalScoreBreakdown(
            trend_score=-1.0,
            momentum_score=5.0,
            volume_score=5.0,
            relative_strength_score=5.0
        )

    with pytest.raises(ValueError):
        TechnicalScoreBreakdown(
            trend_score=11.0,
            momentum_score=5.0,
            volume_score=5.0,
            relative_strength_score=5.0
        )


def test_quant_output_score_validation():
    """Test that overall scores must match breakdown weighted averages."""
    from research_swarm.agents.quant.models import (
        TechnicalIndicators,
        RelativeStrength,
    )

    tech_breakdown = TechnicalScoreBreakdown(
        trend_score=8.0,
        momentum_score=7.0,
        volume_score=6.0,
        relative_strength_score=8.0
    )
    expected_tech_score = tech_breakdown.weighted_average()

    sc_breakdown = SupplyChainScoreBreakdown(
        diversification_score=8.0,
        tier_depth_score=7.0,
        critical_path_score=6.0,
        hidden_dependency_score=9.0
    )
    expected_sc_score = sc_breakdown.weighted_average()

    expected_quant_score = (expected_tech_score + expected_sc_score) / 2

    # Create minimal technical indicators
    tech_indicators = TechnicalIndicators(
        ticker="TEST",
        moving_averages=MovingAverages(crossover_signal=CrossoverSignal.NONE),
        rsi=RSIData(rsi_signal=RSISignal.NEUTRAL, interpretation="Test"),
        volume=VolumeAnalysis(volume_trend=VolumeTrend.STABLE),
        relative_strength=RelativeStrength()
    )

    # Create minimal supply chain graph
    sc_graph = SupplyChainGraph(
        root_ticker="TEST",
        nodes=[SupplyChainNode(id="TEST", name="TEST", node_type=NodeType.ROOT)],
        max_depth=1
    )

    # Valid: all scores match breakdowns
    output = QuantOutput(
        ticker="TEST",
        analysis_date="2024-01-01",
        technical_indicators=tech_indicators,
        technical_analysis="Test analysis",
        technical_score=expected_tech_score,
        technical_breakdown=tech_breakdown,
        supply_chain_graph=sc_graph,
        supply_chain_analysis="Test analysis",
        supply_chain_score=expected_sc_score,
        supply_chain_breakdown=sc_breakdown,
        quant_score=expected_quant_score,
        confidence=0.9,
        tokens_used=100,
        processing_time=1.0
    )
    assert output.quant_score == pytest.approx(expected_quant_score, abs=0.01)

    # Invalid: technical score doesn't match breakdown
    with pytest.raises(ValueError, match="Technical score"):
        QuantOutput(
            ticker="TEST",
            analysis_date="2024-01-01",
            technical_indicators=tech_indicators,
            technical_analysis="Test",
            technical_score=5.0,  # Wrong score
            technical_breakdown=tech_breakdown,
            supply_chain_graph=sc_graph,
            supply_chain_analysis="Test",
            supply_chain_score=expected_sc_score,
            supply_chain_breakdown=sc_breakdown,
            quant_score=(5.0 + expected_sc_score) / 2,
            confidence=0.9,
            tokens_used=100,
            processing_time=1.0
        )


def test_moving_averages_validation():
    """Test MovingAverages validation."""
    # Negative prices should be converted to None
    ma = MovingAverages(
        sma_50=-100.0,  # Should become None
        sma_200=200.0,
        current_price=150.0,
        crossover_signal=CrossoverSignal.GOLDEN_CROSS
    )
    assert ma.sma_50 is None
    assert ma.sma_200 == 200.0


def test_rsi_data_validation():
    """Test RSIData validation."""
    # RSI must be between 0 and 100
    rsi = RSIData(
        rsi_14=75.5,
        rsi_signal=RSISignal.OVERBOUGHT,
        interpretation="Overbought"
    )
    assert rsi.rsi_14 == 75.5

    # Invalid RSI should raise validation error
    with pytest.raises(ValueError):
        RSIData(
            rsi_14=101.0,  # > 100
            rsi_signal=RSISignal.NEUTRAL,
            interpretation="Test"
        )

    with pytest.raises(ValueError):
        RSIData(
            rsi_14=-1.0,  # < 0
            rsi_signal=RSISignal.NEUTRAL,
            interpretation="Test"
        )


# ============================================================================
# Unit Tests: Technical Indicator Calculations
# ============================================================================

def test_calculate_sma():
    """Test SMA calculation."""
    prices = pd.Series([100, 102, 104, 103, 105, 107, 106, 108, 110, 109])

    # 5-period SMA
    sma_5 = calculate_sma(prices, 5)

    # Check that first 4 values are NaN (not enough data)
    assert pd.isna(sma_5.iloc[0:4]).all()

    # Check that 5th value is average of first 5 prices
    expected_5th = (100 + 102 + 104 + 103 + 105) / 5
    assert sma_5.iloc[4] == pytest.approx(expected_5th, abs=0.01)

    # Check last value (last 5 values: 107, 106, 108, 110, 109)
    expected_last = (107 + 106 + 108 + 110 + 109) / 5
    assert sma_5.iloc[-1] == pytest.approx(expected_last, abs=0.01)


def test_calculate_rsi():
    """Test RSI calculation."""
    # Create price series with known pattern
    # Uptrend: should have RSI > 50
    prices_up = pd.Series([100, 102, 104, 106, 108, 110, 112, 114, 116, 118] + [120] * 10)
    rsi_up = calculate_rsi(prices_up, period=14)

    # RSI should be high for uptrend
    assert rsi_up.iloc[-1] > 60

    # Downtrend: should have RSI < 50
    prices_down = pd.Series([120, 118, 116, 114, 112, 110, 108, 106, 104, 102] + [100] * 10)
    rsi_down = calculate_rsi(prices_down, period=14)

    # RSI should be low for downtrend
    assert rsi_down.iloc[-1] < 40


def test_supply_chain_graph_validation():
    """Test that SupplyChainGraph must have exactly one root node."""
    # Valid: one root node
    graph = SupplyChainGraph(
        root_ticker="NVDA",
        nodes=[
            SupplyChainNode(id="NVDA", name="NVIDIA", node_type=NodeType.ROOT, ticker="NVDA"),
            SupplyChainNode(id="TSM", name="TSMC", node_type=NodeType.SUPPLIER, ticker="TSM"),
        ],
        max_depth=1
    )
    assert len(graph.nodes) == 2

    # Invalid: no root node
    with pytest.raises(ValueError, match="root node"):
        SupplyChainGraph(
            root_ticker="NVDA",
            nodes=[
                SupplyChainNode(id="TSM", name="TSMC", node_type=NodeType.SUPPLIER, ticker="TSM"),
            ],
            max_depth=1
        )

    # Invalid: no nodes at all
    with pytest.raises(ValueError, match="at least one node"):
        SupplyChainGraph(
            root_ticker="NVDA",
            nodes=[],
            max_depth=1
        )


def test_enums():
    """Test enum values."""
    assert CrossoverSignal.GOLDEN_CROSS.value == "golden_cross"
    assert RSISignal.OVERSOLD.value == "oversold"
    assert VolumeTrend.INCREASING.value == "increasing"
    assert NodeType.ROOT.value == "root"


# ============================================================================
# Integration Tests
# ============================================================================

@pytest.mark.integration
def test_analyze_nvda_technical():
    """Integration test: Full technical analysis for NVDA."""
    from research_swarm.agents.quant.technical import TechnicalAnalyzer

    analyzer = TechnicalAnalyzer()

    # Analyze NVDA
    indicators = analyzer.analyze_ticker("NVDA", period="1y")

    # Verify structure
    assert indicators.ticker == "NVDA"
    assert indicators.moving_averages is not None
    assert indicators.rsi is not None
    assert indicators.volume is not None
    assert indicators.relative_strength is not None

    # Verify technical indicators have values
    assert indicators.moving_averages.current_price is not None
    assert indicators.moving_averages.current_price > 0


@pytest.mark.integration
def test_analyze_quant_full_workflow():
    """Integration test: Full quant workflow for NVDA."""
    # Create mock fundamentalist supply chain data
    fund_sc = SupplyChainOutput(
        major_suppliers=["TSMC", "Samsung", "Micron"],
        major_customers=["Data centers", "Gaming", "Automotive"]
    )

    # Run full analysis
    result = analyze_quant("NVDA", supply_chain_depth=2, fundamentalist_supply_chain=fund_sc)

    # Verify output structure
    assert result.ticker == "NVDA"
    assert 0 <= result.quant_score <= 10
    assert 0 <= result.technical_score <= 10
    assert 0 <= result.supply_chain_score <= 10
    assert 0 <= result.confidence <= 1

    # Verify quant score is average of technical and supply chain
    expected_quant = (result.technical_score + result.supply_chain_score) / 2
    assert abs(result.quant_score - expected_quant) < 0.1

    # Verify technical indicators
    assert result.technical_indicators is not None
    assert result.technical_indicators.ticker == "NVDA"

    # Verify supply chain graph
    assert result.supply_chain_graph is not None
    assert result.supply_chain_graph.root_ticker == "NVDA"
    assert len(result.supply_chain_graph.nodes) > 0

    # Verify analyses are present
    assert len(result.technical_analysis) > 100  # Should be substantial
    assert len(result.supply_chain_analysis) > 100

    print(f"\n✓ NVDA Quant Score: {result.quant_score:.2f}/10")
    print(f"  - Technical: {result.technical_score:.2f}/10")
    print(f"  - Supply Chain: {result.supply_chain_score:.2f}/10")
    print(f"  - Confidence: {result.confidence:.2f}")
    print(f"  - Tokens: {result.tokens_used}")
    print(f"  - Time: {result.processing_time:.1f}s")


@pytest.mark.integration
def test_nvda_tsmc_asml_chain():
    """Integration test: Verify NVDA → TSMC → ASML supply chain mapping."""
    # Create fundamentalist supply chain with known suppliers
    fund_sc = SupplyChainOutput(
        major_suppliers=["TSMC", "Samsung", "Micron Technology"],
        major_customers=["Data centers", "Gaming"]
    )

    # Run analysis with depth=2 to capture tier-2
    result = analyze_quant("NVDA", supply_chain_depth=2, fundamentalist_supply_chain=fund_sc)

    # Extract node names
    node_names = [n.name.upper() for n in result.supply_chain_graph.nodes]

    # Verify NVDA is root
    root_nodes = [n for n in result.supply_chain_graph.nodes if n.node_type == NodeType.ROOT]
    assert len(root_nodes) == 1
    assert root_nodes[0].ticker == "NVDA"

    # Verify TSMC is in the graph (tier-1 supplier)
    assert any("TSMC" in name or "TAIWAN SEMICONDUCTOR" in name for name in node_names), \
        f"TSMC not found in nodes: {node_names}"

    # Verify ASML is in the graph (tier-2 supplier to TSMC)
    assert any("ASML" in name for name in node_names), \
        f"ASML not found in nodes: {node_names}"

    # Verify graph depth
    assert result.supply_chain_graph.max_depth >= 2

    # Verify tier-2 nodes exist
    tier2_nodes = [n for n in result.supply_chain_graph.nodes if n.node_type == NodeType.SUPPLIER_T2]
    assert len(tier2_nodes) > 0, "No tier-2 suppliers found"

    print(f"\n✓ Supply Chain Mapped:")
    print(f"  - Total Nodes: {len(result.supply_chain_graph.nodes)}")
    print(f"  - Tier-1 Suppliers: {len([n for n in result.supply_chain_graph.nodes if n.node_type == NodeType.SUPPLIER])}")
    print(f"  - Tier-2 Suppliers: {len(tier2_nodes)}")
    print(f"  - Edges: {len(result.supply_chain_graph.edges)}")
    print(f"  - Hidden Dependencies: {len(result.supply_chain_graph.hidden_dependencies)}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
