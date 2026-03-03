"""
Pydantic request/response models for the Portfolio API.

Supports the Compounder Ownership OS v3.1 — portfolio-first capital ownership system.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


# ── Request Models ───────────────────────────────────────────────────────────


class CreatePortfolioRequest(BaseModel):
    name: str = "Core"
    mandate: str = "compounder"  # "compounder" | "growth" | "custom"


class AddPositionRequest(BaseModel):
    ticker: str
    weight: float = Field(ge=0.0, le=1.0, description="Position weight as fraction (0.0 – 1.0)")
    cost_basis: Optional[float] = None
    shares: Optional[float] = None


class UpdatePositionRequest(BaseModel):
    weight: Optional[float] = Field(None, ge=0.0, le=1.0)
    cost_basis: Optional[float] = None
    shares: Optional[float] = None


class MarkActionRequest(BaseModel):
    status: str = Field(description="New status: 'executed' or 'ignored'")
    override_weight: Optional[float] = Field(
        None, ge=0.0, le=1.0,
        description="Override the weight delta when executing (optional)",
    )


# ── Response Models ──────────────────────────────────────────────────────────


class PositionResponse(BaseModel):
    ticker: str
    current_weight: float
    cost_basis: Optional[float]
    shares: Optional[float]
    tier_state: str
    thesis_state: str
    eligibility_state: str
    ownership_status: str
    entry_date: Optional[datetime]
    quarters_held: int
    compounder_score: Optional[float]
    last_drawdown: Optional[float]
    latest_run_id: Optional[str]

    class Config:
        from_attributes = True


class PortfolioResponse(BaseModel):
    id: str
    name: str
    mandate: str
    positions: list[PositionResponse]
    total_weight: float
    position_count: int
    created_at: datetime

    class Config:
        from_attributes = True


class PortfolioListResponse(BaseModel):
    portfolios: list[PortfolioResponse]


class ActionResponse(BaseModel):
    id: str
    ticker: str
    action_type: str
    weight_delta: float
    reason_codes: list[str]
    reason_text: Optional[str]
    status: str
    signal_snapshot: Optional[dict[str, Any]]
    trigger_cycle: Optional[str]
    engine_version: Optional[str]
    created_at: datetime
    executed_at: Optional[datetime]
    expires_at: Optional[datetime]

    class Config:
        from_attributes = True


class ActionFeedResponse(BaseModel):
    actions: list[ActionResponse]
    total: int
    pending_count: int
