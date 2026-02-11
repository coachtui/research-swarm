"""Pydantic models for report generation."""

from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class ReportType(str, Enum):
    """Type of report to generate."""

    MARKDOWN = "markdown"
    PDF = "pdf"
    BOTH = "both"


class ReportSection(str, Enum):
    """Sections available in the report."""

    EXECUTIVE_SUMMARY = "executive_summary"
    STOCK_ANALYSIS = "stock_analysis"
    SUPPLY_CHAIN = "supply_chain"
    WATCHLIST = "watchlist"


class ReportConfig(BaseModel):
    """Configuration for report generation."""

    run_id: str = Field(..., description="Run ID to generate report for")
    output_dir: Path = Field(
        default=Path("./reports"), description="Directory to save reports"
    )
    report_type: ReportType = Field(
        default=ReportType.BOTH, description="Type of report to generate"
    )
    sections: List[ReportSection] = Field(
        default_factory=lambda: [
            ReportSection.EXECUTIVE_SUMMARY,
            ReportSection.STOCK_ANALYSIS,
            ReportSection.SUPPLY_CHAIN,
            ReportSection.WATCHLIST,
        ],
        description="Sections to include in the report",
    )
    top_picks_count: int = Field(
        default=3, ge=1, description="Number of top picks to highlight"
    )
    include_charts: bool = Field(
        default=True, description="Whether to generate charts"
    )


class StockReportData(BaseModel):
    """Report data for a single stock."""

    ticker: str = Field(..., description="Stock ticker symbol")
    moat_score: float = Field(..., ge=0, le=10, description="Moat score (0-10)")
    moat_breakdown: Dict[str, float] = Field(
        ..., description="Breakdown of moat score components"
    )
    is_watchlist_candidate: bool = Field(
        ..., description="Whether stock is a watchlist candidate"
    )
    investment_thesis: str = Field(..., description="Investment thesis paragraph")
    key_insights: List[str] = Field(
        ..., min_length=3, max_length=5, description="Top 3-5 investment insights"
    )
    risk_factors: List[str] = Field(
        ..., min_length=3, max_length=5, description="Top 3-5 risk factors"
    )
    synthesis_narrative: str = Field(
        ..., description="Combined analysis narrative"
    )
    supply_chain_nodes: List[Dict] = Field(
        default_factory=list, description="Supply chain graph nodes"
    )
    supply_chain_edges: List[Dict] = Field(
        default_factory=list, description="Supply chain graph edges"
    )
    hidden_dependencies: List[str] = Field(
        default_factory=list, description="Hidden supply chain dependencies"
    )
    processing_time: float = Field(
        ..., ge=0, description="Processing time in seconds"
    )
    cost_usd: float = Field(..., ge=0, description="Cost in USD")
    signal_breakdown: Optional[Dict[str, Any]] = Field(
        None, description="Multi-signal analysis breakdown with divergence detection"
    )

    # Fundamentalist enhancements
    vgm_scores: Optional[Dict[str, Any]] = Field(
        None, description="VGM (Value/Growth/Momentum) scoring breakdown"
    )
    enhanced_moat: Optional[Dict[str, Any]] = Field(
        None, description="Detailed 8-category moat analysis"
    )
    valuation_metrics: Optional[Dict[str, Any]] = Field(
        None, description="Valuation metrics and multiples"
    )
    price_targets: Optional[Dict[str, Any]] = Field(
        None, description="Bull/Base/Bear price target scenarios"
    )
    peer_comparison: Optional[Dict[str, Any]] = Field(
        None, description="Peer comparison and competitive positioning"
    )

    # News Hound enhancements
    earnings_estimates: Optional[Dict[str, Any]] = Field(
        None, description="Earnings estimate revisions and consensus"
    )
    analyst_consensus: Optional[Dict[str, Any]] = Field(
        None, description="Analyst ratings and price targets"
    )
    institutional_activity: Optional[Dict[str, Any]] = Field(
        None, description="Institutional ownership and 13F activity"
    )
    insider_activity: Optional[Dict[str, Any]] = Field(
        None, description="Insider trading activity"
    )
    management_commentary: Optional[Dict[str, Any]] = Field(
        None, description="Management quality and guidance analysis"
    )
    short_interest: Optional[Dict[str, Any]] = Field(
        None, description="Short interest and squeeze risk"
    )
    upcoming_catalysts: Optional[Dict[str, Any]] = Field(
        None, description="Upcoming catalyst calendar"
    )

    # Template alignment enhancements (v2.0)
    rating: Optional[str] = Field(
        None, description="5-tier rating: STRONG BUY/BUY/HOLD/SELL/STRONG SELL"
    )
    rating_score: Optional[float] = Field(
        None, ge=0, le=10, description="Numeric rating score (0-10)"
    )
    risk_level: Optional[str] = Field(
        None, description="Risk classification: Low/Medium/High"
    )
    competitive_moat_enhanced: Optional[Dict[str, Any]] = Field(
        None,
        description="Enhanced competitive analysis with market share, competitor comparison, moat direction",
    )
    structured_risks: Optional[List[Dict[str, Any]]] = Field(
        None,
        description="Risks with severity, likelihood, impact, mitigation",
    )
    upgrade_triggers: Optional[List[Dict[str, str]]] = Field(
        None, description="Specific metrics → action for upgrades"
    )
    downgrade_triggers: Optional[List[Dict[str, str]]] = Field(
        None, description="Specific metrics → action for downgrades"
    )
    recommended_strategy: Optional[Dict[str, Any]] = Field(
        None,
        description="Entry/exit strategy, position sizing, risk/reward analysis",
    )
    valuation_sensitivity: Optional[Dict[str, Any]] = Field(
        None, description="Sensitivity analysis for EPS and P/E changes"
    )
    track_record: Optional[Dict[str, Any]] = Field(
        None, description="Previous report comparison and target achievement"
    )
    conviction_statement: Optional[Dict[str, Any]] = Field(
        None,
        description="Conviction level, bottom line summary, best suited for",
    )
    expected_value_price_target: Optional[float] = Field(
        None, description="Probability-weighted expected value from scenarios"
    )

    # Enhanced report metadata
    coverage_universe: Optional[str] = Field(None, description="Sector/industry coverage")
    peer_comparison_group: Optional[List[str]] = Field(
        None, description="List of peer tickers for comparison"
    )
    next_review_date: Optional[str] = Field(
        None, description="Next scheduled review date"
    )
    earnings_date: Optional[str] = Field(
        None, description="Upcoming earnings date"
    )


class ReportData(BaseModel):
    """Complete data for report generation."""

    run_id: str = Field(..., description="Run ID")
    run_name: Optional[str] = Field(None, description="Optional run name")
    generated_at: datetime = Field(
        default_factory=datetime.now, description="Report generation timestamp"
    )
    analysis_date: str = Field(..., description="Date of analysis (YYYY-MM-DD)")
    analysis_period: str = Field(..., description="Analysis period (e.g., 'TTM Q4 2024 - Q3 2025')")
    quarters: List[str] = Field(default_factory=list, description="Quarters analyzed (for TTM mode)")
    report_version: str = Field(
        default="2.0", description="Report schema version for tracking compatibility"
    )

    # Backward compatibility
    fiscal_year: Optional[int] = Field(None, description="[Deprecated] Fiscal year for annual analysis")
    stocks: List[StockReportData] = Field(
        default_factory=list, description="All analyzed stocks"
    )
    top_picks: List[StockReportData] = Field(
        default_factory=list, description="Top N stocks by moat score"
    )
    watchlist_candidates: List[StockReportData] = Field(
        default_factory=list, description="Stocks meeting watchlist criteria"
    )
    total_stocks: int = Field(..., ge=0, description="Total stocks analyzed")
    completed_count: int = Field(..., ge=0, description="Successfully completed stocks")
    failed_count: int = Field(..., ge=0, description="Failed stock analyses")
    average_moat_score: float = Field(
        ..., ge=0, le=10, description="Average moat score across all stocks"
    )
    total_cost_usd: float = Field(..., ge=0, description="Total cost in USD")
    total_elapsed_seconds: float = Field(
        ..., ge=0, description="Total analysis time in seconds"
    )
    cost_by_ticker: Dict[str, float] = Field(
        default_factory=dict, description="Cost breakdown by ticker"
    )


class ReportOutput(BaseModel):
    """Output from report generation."""

    markdown_path: Optional[Path] = Field(
        None, description="Path to generated Markdown file"
    )
    pdf_path: Optional[Path] = Field(None, description="Path to generated PDF file")
    charts_generated: List[str] = Field(
        default_factory=list, description="Paths to generated chart files"
    )
    generation_time_seconds: float = Field(
        ..., ge=0, description="Time taken to generate report"
    )
    success: bool = Field(..., description="Whether report generation succeeded")
    error_message: Optional[str] = Field(
        None, description="Error message if generation failed"
    )
