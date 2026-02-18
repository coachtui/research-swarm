"""
Watchlist-related Pydantic models for API requests and responses.
"""

from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime


class WatchlistItem(BaseModel):
    """
    A single stock in the user's watchlist with tracking metadata.
    """
    id: str = Field(..., description="Watchlist item UUID")
    ticker: str = Field(..., description="Stock ticker symbol")
    company_name: Optional[str] = Field(None, description="Company name")

    # Timestamps
    added_at: datetime = Field(..., description="When stock was added to watchlist")
    last_checked_at: Optional[datetime] = Field(None, description="Last refresh timestamp")

    # Score tracking
    initial_moat_score: Optional[float] = Field(None, description="Score when added")
    latest_moat_score: Optional[float] = Field(None, description="Most recent score")
    score_change: Optional[float] = Field(None, description="Change from initial to latest")
    latest_analysis_date: Optional[datetime] = Field(None, description="Date of latest analysis")

    # Additional metadata
    notes: Optional[str] = Field(None, description="User notes")
    days_since_update: Optional[int] = Field(None, description="Days since last analysis")
    can_refresh: bool = Field(default=True, description="Whether user can refresh (has quota)")

    # Analysis references
    initial_analysis_run_id: Optional[str] = Field(None, description="Initial analysis run ID")
    latest_analysis_run_id: Optional[str] = Field(None, description="Latest analysis run ID")

    class Config:
        json_schema_extra = {
            "example": {
                "id": "550e8400-e29b-41d4-a716-446655440000",
                "ticker": "AAPL",
                "company_name": "Apple Inc.",
                "added_at": "2026-02-01T00:00:00Z",
                "last_checked_at": "2026-02-14T00:00:00Z",
                "initial_moat_score": 7.5,
                "latest_moat_score": 8.2,
                "score_change": 0.7,
                "latest_analysis_date": "2026-02-14T00:00:00Z",
                "notes": "Strong earnings momentum",
                "days_since_update": 1,
                "can_refresh": True,
                "initial_analysis_run_id": "abc123",
                "latest_analysis_run_id": "def456"
            }
        }


class WatchlistResponse(BaseModel):
    """
    Response containing user's watchlist items.
    """
    items: List[WatchlistItem] = Field(..., description="List of watchlist items")
    total: int = Field(..., description="Total count")

    class Config:
        json_schema_extra = {
            "example": {
                "items": [
                    {
                        "id": "550e8400-e29b-41d4-a716-446655440000",
                        "ticker": "AAPL",
                        "company_name": "Apple Inc.",
                        "added_at": "2026-02-01T00:00:00Z",
                        "latest_moat_score": 8.2,
                        "score_change": 0.7,
                        "days_since_update": 1,
                        "can_refresh": True
                    }
                ],
                "total": 1
            }
        }


class AddToWatchlistRequest(BaseModel):
    """
    Request to add a stock to watchlist.
    """
    ticker: str = Field(..., min_length=1, max_length=10, description="Stock ticker symbol")
    company_name: Optional[str] = Field(None, max_length=200, description="Company name (optional)")
    notes: Optional[str] = Field(None, max_length=1000, description="User notes (optional)")
    analysis_run_id: Optional[str] = Field(None, description="Run ID if adding from existing analysis")

    class Config:
        json_schema_extra = {
            "example": {
                "ticker": "AAPL",
                "company_name": "Apple Inc.",
                "notes": "Strong buy signal"
            }
        }


class UpdateNotesRequest(BaseModel):
    """
    Request to update notes on a watchlist item.
    """
    notes: str = Field(..., max_length=1000, description="Updated notes")

    class Config:
        json_schema_extra = {
            "example": {
                "notes": "Updated: earnings beat expectations"
            }
        }


class RefreshWatchlistResponse(BaseModel):
    """
    Response from refreshing a watchlist item.
    """
    success: bool = Field(..., description="Whether refresh succeeded")
    new_score: Optional[float] = Field(None, description="New moat score")
    old_score: Optional[float] = Field(None, description="Previous score")
    score_change: Optional[float] = Field(None, description="Change in score")
    run_id: Optional[str] = Field(None, description="Analysis run ID")

    class Config:
        json_schema_extra = {
            "example": {
                "success": True,
                "new_score": 8.5,
                "old_score": 8.2,
                "score_change": 0.3,
                "run_id": "abc123"
            }
        }


class WatchlistStatsResponse(BaseModel):
    """
    Dashboard statistics for watchlist.
    """
    watchlist_count: int = Field(..., description="Number of stocks in watchlist")
    watchlist_limit: int = Field(..., description="Max stocks allowed")
    avg_score: Optional[float] = Field(None, description="Average moat score")
    divergence_count: int = Field(default=0, description="Count with divergence detected")
    needs_refresh_count: int = Field(default=0, description="Count needing refresh (>7 days)")

    class Config:
        json_schema_extra = {
            "example": {
                "watchlist_count": 3,
                "watchlist_limit": 3,
                "avg_score": 7.8,
                "divergence_count": 1,
                "needs_refresh_count": 0
            }
        }
