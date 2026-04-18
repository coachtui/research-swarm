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
    shares: float = Field(ge=0.0, description="Number of shares held (0 for watch position)")
    cost_basis: Optional[float] = None
    target_weight: Optional[float] = Field(None, ge=0.0, le=1.0, description="Target allocation as fraction")


class UpdatePositionRequest(BaseModel):
    shares: Optional[float] = Field(None, ge=0.0)
    cost_basis: Optional[float] = None
    target_weight: Optional[float] = Field(None, ge=0.0, le=1.0)


class UpdateCashRequest(BaseModel):
    amount: float = Field(ge=0.0, description="Cash balance in dollars")


class MarkActionRequest(BaseModel):
    status: str = Field(description="New status: 'executed' or 'ignored'")
    override_weight: Optional[float] = Field(
        None, ge=0.0, le=1.0,
        description="Override the weight delta when executing (optional)",
    )


# ── Response Models ──────────────────────────────────────────────────────────


class PositionResponse(BaseModel):
    ticker: str
    shares: float
    cost_basis: Optional[float]
    last_known_price: Optional[float]
    last_price_at: Optional[datetime]
    allocation_pct: Optional[float]   # computed: shares * price / total, as fraction (0.0-1.0)
    market_value: Optional[float]     # shares * last_known_price
    target_weight: float              # user-set target as fraction (0.0-1.0)
    engine_suggested_weight: Optional[float]
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


class PortfolioBreakdown(BaseModel):
    total_value: float
    cash_balance: float
    cash_pct: float  # fraction (0-1)
    positions: list[PositionResponse]


class PortfolioResponse(BaseModel):
    id: str
    name: str
    mandate: str
    positions: list[PositionResponse]
    total_value: float
    cash_balance: float
    cash_pct: float
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
    trigger_price: Optional[float] = None
    trigger_condition: Optional[str] = None
    parent_action_id: Optional[str] = None
    created_at: datetime
    executed_at: Optional[datetime]
    expires_at: Optional[datetime]

    class Config:
        from_attributes = True


class ActionFeedResponse(BaseModel):
    actions: list[ActionResponse]
    total: int
    pending_count: int


class ActionChainResponse(BaseModel):
    """A parent action with its child steps."""
    parent: ActionResponse
    children: list[ActionResponse]
