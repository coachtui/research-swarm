"""Pydantic response models for WeeklySignal API endpoints."""
from __future__ import annotations

from datetime import datetime
from typing import Dict, List, Optional

from pydantic import BaseModel, ConfigDict


class WeeklySignalPublic(BaseModel):
    """Fields returned to all users — no auth required."""

    model_config = ConfigDict(from_attributes=True)

    ticker: str
    verdict: Optional[str] = None
    fair_value_gap_pct: Optional[float] = None
    synthesis_summary: Optional[str] = None
    run_date: datetime
    current_price: Optional[float] = None
    screener_score: Optional[float] = None
    es_change_pct: Optional[float] = None
    nq_change_pct: Optional[float] = None
    dow_change_pct: Optional[float] = None
    prior_verdict: Optional[str] = None  # needed for Verdict Upgrade lens


class WeeklySignalFull(WeeklySignalPublic):
    """All fields — returned only to Starter+ users."""

    fair_value: Optional[float] = None
    ev_probability: Optional[float] = None
    stop_loss_probability: Optional[float] = None
    insider_score: Optional[float] = None
    dark_pool_score: Optional[float] = None
    sentiment_score: Optional[float] = None
    catalyst_summary: Optional[str] = None
    position_size_rec: Optional[str] = None
    prior_ev_probability: Optional[float] = None


class MarketContextOut(BaseModel):
    es_change_pct: Optional[float]
    nq_change_pct: Optional[float]
    dow_change_pct: Optional[float]


class LeaderboardResponse(BaseModel):
    run_date: Optional[datetime]
    market_context: MarketContextOut
    rows: List[WeeklySignalPublic]  # WeeklySignalFull is a subtype — valid here
    total: int


class TrackRecordStats(BaseModel):
    analyzed: int
    buy: int
    hold: int
    avoid: int


class TrackRecordWeek(BaseModel):
    run_date: datetime
    stats: TrackRecordStats
    rows: List[WeeklySignalPublic]


class TrackRecordResponse(BaseModel):
    weeks: List[TrackRecordWeek]
    total_weeks: int
