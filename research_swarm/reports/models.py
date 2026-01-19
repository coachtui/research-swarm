"""Pydantic models for report generation."""

from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional

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
