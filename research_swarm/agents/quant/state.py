"""
State schema for the Quant agent.

Defines the TypedDict for LangGraph state management.
"""
from typing import TypedDict, Optional, Dict, List, Any
import pandas as pd


class QuantState(TypedDict, total=False):
    """
    State for the Quant agent workflow.

    This state is passed between nodes in the LangGraph workflow,
    with each node updating relevant fields as it processes the data.
    """

    # Input fields
    ticker: str  # Stock ticker (e.g., "NVDA")
    analysis_date: str  # Date of analysis (YYYY-MM-DD)
    supply_chain_depth: int  # Maximum supply chain tier depth to explore (default 2)

    # Shared data layer (NEW: eliminates redundant API calls)
    shared_swarm_data: Optional[Dict[str, Any]]  # Pre-fetched data bundle from Manager

    # Status tracking
    status: str  # Current workflow status: "initialized", "fetching_data", "calculating_indicators", "building_graph", "analyzing", "scoring", "completed", "error"
    error: Optional[str]  # Error message if status is "error"

    # Market data
    historical_data: Optional[pd.DataFrame]  # Historical OHLCV data from yfinance
    data_period: str  # Data period fetched (e.g., "1y")

    # Technical indicators
    technical_indicators: Optional[Dict[str, Any]]  # Technical indicators dict (will be converted to TechnicalIndicators model)
    moving_averages: Optional[Dict[str, Any]]  # SMA 50/200, crossover signals
    rsi: Optional[Dict[str, Any]]  # RSI analysis
    volume: Optional[Dict[str, Any]]  # Volume analysis
    relative_strength: Optional[Dict[str, Any]]  # Relative strength vs sector/market

    # Supply chain data
    fundamentalist_supply_chain: Optional[Dict[str, Any]]  # Supply chain data from Fundamentalist agent (optional)
    supply_chain_graph: Optional[Dict[str, Any]]  # Supply chain graph dict (nodes, edges, hidden dependencies)
    networkx_graph: Optional[Any]  # NetworkX DiGraph object (not serializable, for internal use)

    # Analysis results
    technical_analysis: Optional[str]  # Qualitative technical analysis narrative
    supply_chain_analysis: Optional[str]  # Qualitative supply chain analysis narrative
    hidden_dependencies_analysis: Optional[str]  # LLM analysis of hidden dependencies

    # Scoring
    technical_score: Optional[float]  # Overall technical score (0-10)
    technical_breakdown: Optional[Dict[str, float]]  # Technical score breakdown (trend, momentum, volume, RS)
    supply_chain_score: Optional[float]  # Overall supply chain score (0-10)
    supply_chain_breakdown: Optional[Dict[str, float]]  # Supply chain score breakdown
    quant_score: Optional[float]  # Combined quant score (0-10)
    confidence: Optional[float]  # Confidence level (0-1)

    # Metadata
    tokens_used: int  # Total tokens used in API calls (default 0)
    processing_time: Optional[float]  # Total processing time in seconds
    node_timestamps: Optional[Dict[str, float]]  # Timestamp when each node started (for debugging)
