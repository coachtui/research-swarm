"""Pydantic models for orchestration layer."""

from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional
from uuid import uuid4

from pydantic import BaseModel, Field


class StockStatus(str, Enum):
    """Status of individual stock analysis."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    RETRYING = "retrying"


class RunStatus(str, Enum):
    """Status of overall swarm run."""

    INITIALIZED = "initialized"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"


class CostSummary(BaseModel):
    """Cost tracking summary."""

    total_tokens: int = 0
    total_cost_usd: float = 0.0
    cost_by_agent: Dict[str, float] = Field(default_factory=dict)
    cost_by_ticker: Dict[str, float] = Field(default_factory=dict)


class StockResult(BaseModel):
    """Result for a single stock analysis."""

    ticker: str
    status: StockStatus
    retry_count: int = 0
    moat_score: Optional[float] = None  # 0-10
    is_watchlist_candidate: Optional[bool] = None
    investment_thesis: Optional[str] = None
    full_output: Optional[Dict] = None  # ManagerOutput.model_dump()
    tokens_used: int = 0
    cost_usd: float = 0.0
    error_message: Optional[str] = None
    processing_time_seconds: Optional[float] = None


class SwarmRun(BaseModel):
    """Complete swarm run with all stock results."""

    run_id: str = Field(default_factory=lambda: str(uuid4()))
    run_name: Optional[str] = None
    tickers: List[str]
    fiscal_year: int = 2024
    news_days_back: int = 30
    max_retries: int = 3
    status: RunStatus
    stock_results: Dict[str, StockResult] = Field(default_factory=dict)
    total_stocks: int
    completed_count: int = 0
    failed_count: int = 0
    cost_summary: CostSummary = Field(default_factory=CostSummary)
    created_at: datetime = Field(default_factory=datetime.now)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    elapsed_seconds: float = 0.0

    @property
    def success_rate(self) -> float:
        """Calculate success rate as percentage."""
        if self.total_stocks == 0:
            return 0.0
        return (self.completed_count / self.total_stocks) * 100

    @property
    def watchlist_candidates(self) -> List[StockResult]:
        """Get stocks that are watchlist candidates."""
        return [
            result
            for result in self.stock_results.values()
            if result.is_watchlist_candidate
        ]

    @property
    def pending_count(self) -> int:
        """Count of pending stocks."""
        return sum(
            1
            for result in self.stock_results.values()
            if result.status in [StockStatus.PENDING, StockStatus.RETRYING]
        )


class RunEstimate(BaseModel):
    """Estimate for a potential swarm run."""

    tickers: List[str]
    estimated_total_time_human: str
    estimated_cost_usd: float
    within_budget: bool
    runs_remaining_this_month: int
