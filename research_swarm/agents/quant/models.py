"""
Pydantic models for Quant agent outputs.

These models ensure type safety and validation for technical analysis,
supply chain graphs, and quantitative scoring.
"""
from pydantic import BaseModel, Field, field_validator, model_validator
from typing import List, Optional, Dict, Literal
from enum import Enum


class CrossoverSignal(str, Enum):
    """Enum for moving average crossover signals."""
    GOLDEN_CROSS = "golden_cross"  # SMA50 crossed above SMA200 (bullish)
    DEATH_CROSS = "death_cross"    # SMA50 crossed below SMA200 (bearish)
    NONE = "none"                   # No recent crossover


class RSISignal(str, Enum):
    """Enum for RSI signals."""
    OVERSOLD = "oversold"      # RSI < 30
    OVERBOUGHT = "overbought"  # RSI > 70
    NEUTRAL = "neutral"        # 30 <= RSI <= 70


class VolumeTrend(str, Enum):
    """Enum for volume trends."""
    INCREASING = "increasing"
    DECREASING = "decreasing"
    STABLE = "stable"


class NodeType(str, Enum):
    """Enum for supply chain node types."""
    ROOT = "root"              # The company being analyzed
    CUSTOMER = "customer"      # Direct customer (tier-1)
    SUPPLIER = "supplier"      # Direct supplier (tier-1)
    SUPPLIER_T2 = "supplier_t2"  # Tier-2 supplier (supplier's supplier)
    SUPPLIER_T3 = "supplier_t3"  # Tier-3 supplier


class RelationType(str, Enum):
    """Enum for supply chain relationship types."""
    SUPPLIES_TO = "supplies_to"
    SUPPLIED_BY = "supplied_by"
    MANUFACTURES_FOR = "manufactures_for"
    DISTRIBUTES_FOR = "distributes_for"


class MovingAverages(BaseModel):
    """Moving average analysis output."""

    sma_50: Optional[float] = Field(None, description="50-day simple moving average")
    sma_200: Optional[float] = Field(None, description="200-day simple moving average")
    current_price: Optional[float] = Field(None, description="Current/latest price")
    crossover_signal: CrossoverSignal = Field(
        CrossoverSignal.NONE,
        description="Golden cross or death cross signal"
    )
    days_since_crossover: Optional[int] = Field(
        None,
        description="Days since the last crossover event"
    )

    @field_validator("sma_50", "sma_200", "current_price", mode="before")
    @classmethod
    def validate_positive_price(cls, v):
        """Ensure prices are positive or None."""
        if v is not None and v <= 0:
            return None
        return v


class RSIData(BaseModel):
    """Relative Strength Index analysis output."""

    rsi_14: Optional[float] = Field(
        None,
        ge=0,
        le=100,
        description="14-day RSI value (0-100)"
    )
    rsi_signal: RSISignal = Field(
        RSISignal.NEUTRAL,
        description="Oversold/overbought/neutral signal"
    )
    interpretation: str = Field(
        ...,
        description="Human-readable interpretation of RSI"
    )


class VolumeAnalysis(BaseModel):
    """Volume trend analysis output."""

    avg_volume_20d: Optional[float] = Field(
        None,
        description="20-day average volume"
    )
    current_volume: Optional[float] = Field(
        None,
        description="Most recent day's volume"
    )
    volume_ratio: Optional[float] = Field(
        None,
        description="Current volume / 20-day average"
    )
    volume_trend: VolumeTrend = Field(
        VolumeTrend.STABLE,
        description="Volume trend direction"
    )

    @field_validator("avg_volume_20d", "current_volume", mode="before")
    @classmethod
    def validate_positive_volume(cls, v):
        """Ensure volumes are positive or None."""
        if v is not None and v < 0:
            return None
        return v


class RelativeStrength(BaseModel):
    """Relative strength vs sector and market."""

    ticker_return_1m: Optional[float] = Field(
        None,
        description="Ticker's 1-month return (%)"
    )
    ticker_return_3m: Optional[float] = Field(
        None,
        description="Ticker's 3-month return (%)"
    )
    sector_return_1m: Optional[float] = Field(
        None,
        description="Sector ETF 1-month return (%)"
    )
    sector_return_3m: Optional[float] = Field(
        None,
        description="Sector ETF 3-month return (%)"
    )
    market_return_1m: Optional[float] = Field(
        None,
        description="SPY (market) 1-month return (%)"
    )
    market_return_3m: Optional[float] = Field(
        None,
        description="SPY (market) 3-month return (%)"
    )
    vs_sector_1m: Optional[float] = Field(
        None,
        description="Outperformance vs sector 1-month (percentage points)"
    )
    vs_sector_3m: Optional[float] = Field(
        None,
        description="Outperformance vs sector 3-month (percentage points)"
    )
    vs_market_1m: Optional[float] = Field(
        None,
        description="Outperformance vs market 1-month (percentage points)"
    )
    vs_market_3m: Optional[float] = Field(
        None,
        description="Outperformance vs market 3-month (percentage points)"
    )


class TechnicalIndicators(BaseModel):
    """Combined technical indicators output."""

    ticker: str = Field(..., description="Stock ticker symbol")
    moving_averages: MovingAverages = Field(..., description="Moving average analysis")
    rsi: RSIData = Field(..., description="RSI analysis")
    volume: VolumeAnalysis = Field(..., description="Volume analysis")
    relative_strength: RelativeStrength = Field(..., description="Relative strength analysis")


class SupplyChainNode(BaseModel):
    """Node in the supply chain graph."""

    id: str = Field(..., description="Unique node identifier")
    name: str = Field(..., description="Company name")
    node_type: NodeType = Field(..., description="Node type (root/customer/supplier/tier-2/tier-3)")
    ticker: Optional[str] = Field(None, description="Stock ticker if publicly traded")
    description: Optional[str] = Field(None, description="Brief description of the relationship")


class SupplyChainEdge(BaseModel):
    """Edge in the supply chain graph."""

    source: str = Field(..., description="Source node ID")
    target: str = Field(..., description="Target node ID")
    relation_type: RelationType = Field(..., description="Type of relationship")
    weight: float = Field(
        1.0,
        ge=0,
        le=1,
        description="Edge weight (0-1, higher = more critical)"
    )
    description: Optional[str] = Field(None, description="Description of the relationship")


class SupplyChainGraph(BaseModel):
    """Complete supply chain graph with metadata."""

    root_ticker: str = Field(..., description="Root company ticker")
    nodes: List[SupplyChainNode] = Field(
        default_factory=list,
        description="List of all nodes in the graph"
    )
    edges: List[SupplyChainEdge] = Field(
        default_factory=list,
        description="List of all edges in the graph"
    )
    max_depth: int = Field(
        ...,
        ge=1,
        description="Maximum tier depth explored"
    )
    hidden_dependencies: List[str] = Field(
        default_factory=list,
        description="List of hidden dependencies identified (tier-2/3 suppliers shared by multiple tier-1s)"
    )
    critical_paths: List[List[str]] = Field(
        default_factory=list,
        description="List of critical paths in the supply chain (list of node IDs)"
    )

    @field_validator("nodes", mode="after")
    @classmethod
    def validate_root_exists(cls, nodes: List[SupplyChainNode]) -> List[SupplyChainNode]:
        """Ensure at least one root node exists."""
        if not nodes:
            raise ValueError("Supply chain graph must have at least one node")
        root_nodes = [n for n in nodes if n.node_type == NodeType.ROOT]
        if not root_nodes:
            raise ValueError("Supply chain graph must have exactly one root node")
        if len(root_nodes) > 1:
            raise ValueError("Supply chain graph must have only one root node")
        return nodes


class TechnicalScoreBreakdown(BaseModel):
    """Breakdown of the technical score components."""

    trend_score: float = Field(
        ...,
        ge=0,
        le=10,
        description="Trend score from moving averages (0-10)"
    )
    momentum_score: float = Field(
        ...,
        ge=0,
        le=10,
        description="Momentum score from RSI (0-10)"
    )
    volume_score: float = Field(
        ...,
        ge=0,
        le=10,
        description="Volume score (0-10)"
    )
    relative_strength_score: float = Field(
        ...,
        ge=0,
        le=10,
        description="Relative strength score (0-10)"
    )

    def weighted_average(self) -> float:
        """
        Calculate weighted average technical score.

        Weights: trend (35%), momentum (25%), volume (15%), relative_strength (25%)
        """
        return (
            self.trend_score * 0.35 +
            self.momentum_score * 0.25 +
            self.volume_score * 0.15 +
            self.relative_strength_score * 0.25
        )


class SupplyChainScoreBreakdown(BaseModel):
    """Breakdown of the supply chain score components."""

    diversification_score: float = Field(
        ...,
        ge=0,
        le=10,
        description="Supplier diversification score (0-10)"
    )
    tier_depth_score: float = Field(
        ...,
        ge=0,
        le=10,
        description="Supply chain tier depth score (0-10)"
    )
    critical_path_score: float = Field(
        ...,
        ge=0,
        le=10,
        description="Critical path resilience score (0-10)"
    )
    hidden_dependency_score: float = Field(
        ...,
        ge=0,
        le=10,
        description="Hidden dependency risk score (0-10)"
    )

    def weighted_average(self) -> float:
        """
        Calculate weighted average supply chain score.

        Weights: diversification (30%), tier_depth (20%), critical_path (25%), hidden_dependency (25%)
        """
        return (
            self.diversification_score * 0.30 +
            self.tier_depth_score * 0.20 +
            self.critical_path_score * 0.25 +
            self.hidden_dependency_score * 0.25
        )


class QuantOutput(BaseModel):
    """Final validated output from the Quant agent."""

    # Input identifiers
    ticker: str = Field(..., description="Stock ticker symbol")
    analysis_date: str = Field(..., description="Date of analysis (YYYY-MM-DD)")

    # Technical analysis
    technical_indicators: TechnicalIndicators = Field(
        ...,
        description="All technical indicators"
    )
    technical_analysis: str = Field(
        ...,
        description="Qualitative technical analysis narrative"
    )
    technical_score: float = Field(
        ...,
        ge=0,
        le=10,
        description="Overall technical score (0-10)"
    )
    technical_breakdown: TechnicalScoreBreakdown = Field(
        ...,
        description="Technical score breakdown by component"
    )

    # Supply chain analysis
    supply_chain_graph: SupplyChainGraph = Field(
        ...,
        description="Supply chain graph with nodes and edges"
    )
    supply_chain_analysis: str = Field(
        ...,
        description="Qualitative supply chain analysis narrative"
    )
    supply_chain_score: float = Field(
        ...,
        ge=0,
        le=10,
        description="Overall supply chain resilience score (0-10)"
    )
    supply_chain_breakdown: SupplyChainScoreBreakdown = Field(
        ...,
        description="Supply chain score breakdown by component"
    )

    # Combined score
    quant_score: float = Field(
        ...,
        ge=0,
        le=10,
        description="Combined quant score (50% technical + 50% supply chain)"
    )
    confidence: float = Field(
        ...,
        ge=0,
        le=1,
        description="Confidence level in the analysis (0-1)"
    )

    # Metadata
    tokens_used: int = Field(..., description="Total tokens used in API calls")
    processing_time: float = Field(..., description="Total processing time in seconds")

    @model_validator(mode='after')
    def validate_scores_match_breakdowns(self):
        """Ensure overall scores match weighted averages of components."""
        # Validate technical score
        expected_technical = self.technical_breakdown.weighted_average()
        if abs(self.technical_score - expected_technical) > 0.1:
            raise ValueError(
                f"Technical score {self.technical_score} does not match "
                f"breakdown weighted average {expected_technical:.2f}"
            )

        # Validate supply chain score
        expected_supply_chain = self.supply_chain_breakdown.weighted_average()
        if abs(self.supply_chain_score - expected_supply_chain) > 0.1:
            raise ValueError(
                f"Supply chain score {self.supply_chain_score} does not match "
                f"breakdown weighted average {expected_supply_chain:.2f}"
            )

        # Validate combined quant score
        expected_quant = (self.technical_score + self.supply_chain_score) / 2
        if abs(self.quant_score - expected_quant) > 0.1:
            raise ValueError(
                f"Quant score {self.quant_score} does not match "
                f"average of technical and supply chain scores {expected_quant:.2f}"
            )

        return self
