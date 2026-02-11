"""
API response schemas using Pydantic for serialization.
"""

from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime
from enum import Enum

class JobStatus(str, Enum):
    """Job execution status."""
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

class AnalyzeResponse(BaseModel):
    """
    Response schema for analysis job creation.
    """
    job_id: str = Field(..., description="Unique job identifier")
    run_id: str = Field(..., description="Run identifier (same as job_id for single stock)")
    ticker: str = Field(..., description="Stock ticker being analyzed")
    status: JobStatus = Field(..., description="Current job status")
    estimated_time_minutes: int = Field(..., description="Estimated completion time in minutes")
    created_at: datetime = Field(..., description="Job creation timestamp")
    websocket_url: Optional[str] = Field(None, description="WebSocket URL for real-time updates (Phase 2)")
    result: Optional[Dict[str, Any]] = Field(None, description="Full analysis results (when completed)")

    class Config:
        json_schema_extra = {
            "example": {
                "job_id": "550e8400-e29b-41d4-a716-446655440000",
                "run_id": "550e8400-e29b-41d4-a716-446655440000",
                "ticker": "NVDA",
                "status": "queued",
                "estimated_time_minutes": 6,
                "created_at": "2026-02-10T20:30:00Z"
            }
        }

class StockResultSummary(BaseModel):
    """
    Summary of a single stock analysis result.
    """
    ticker: str
    status: JobStatus
    moat_score: Optional[float] = Field(None, ge=0, le=10)
    is_watchlist_candidate: Optional[bool] = None
    investment_thesis: Optional[str] = None
    cost_usd: Optional[float] = None
    processing_time_seconds: Optional[float] = None
    error_message: Optional[str] = None

class RunSummary(BaseModel):
    """
    Summary of a run for list view.
    """
    id: str
    ticker: str
    status: str
    created_at: datetime
    completed_at: Optional[datetime] = None
    total_cost_usd: Optional[float] = None
    stock_count: int = 0

class RunResponse(BaseModel):
    """
    Detailed response for a single run.
    """
    id: str
    status: str
    tickers: List[str]
    total_cost_usd: Optional[float] = None
    created_at: datetime
    completed_at: Optional[datetime] = None
    results: List[Dict[str, Any]] = []

    class Config:
        json_schema_extra = {
            "example": {
                "run_id": "550e8400-e29b-41d4-a716-446655440000",
                "run_name": "Semiconductor Analysis",
                "status": "running",
                "tickers": ["NVDA", "AMD", "INTC"],
                "total_stocks": 3,
                "completed_count": 1,
                "failed_count": 0,
                "progress_percent": 33.3,
                "current_ticker": "AMD",
                "stock_results": [
                    {
                        "ticker": "NVDA",
                        "status": "completed",
                        "moat_score": 8.5,
                        "is_watchlist_candidate": True,
                        "cost_usd": 0.45
                    }
                ],
                "total_cost_usd": 0.45,
                "created_at": "2026-02-10T20:30:00Z"
            }
        }

class RunListResponse(BaseModel):
    """
    Paginated list of runs.
    """
    total: int = Field(..., description="Total number of runs")
    limit: int = Field(..., description="Number of runs in this response")
    offset: int = Field(..., description="Pagination offset")
    runs: List[RunSummary] = Field(..., description="List of runs")

    class Config:
        json_schema_extra = {
            "example": {
                "total": 45,
                "limit": 20,
                "offset": 0,
                "runs": []
            }
        }

class ErrorResponse(BaseModel):
    """
    Standard error response format.
    """
    error: str = Field(..., description="Error type")
    detail: str = Field(..., description="Detailed error message")
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    request_id: Optional[str] = None

    class Config:
        json_schema_extra = {
            "example": {
                "error": "QuotaExceeded",
                "detail": "Monthly budget of $200 exceeded. Current spending: $205.30",
                "timestamp": "2026-02-10T20:30:00Z"
            }
        }
