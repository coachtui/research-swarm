# Portfolio Holdings Rework — Phase 2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace manually-entered allocation % with automatic computation from shares × price / total portfolio value, add cash as a first-class denominator, introduce signal-driven conditional action plans (trim/add ladders with trigger prices), and surface it all in a reworked HoldingsTab UI.

**Architecture:** Additive Prisma migration adds new fields to Portfolio, Position, and PortfolioAction without removing `currentWeight` (Phase 2b drops it). Two new pure-function services (`allocation.py`, `pricing.py`) keep math isolated and testable. `portfolio_engine.py` gains `generate_action_plan` that reads the latest StockResult signals and emits linked conditional PortfolioAction chains. Three new frontend components (`CashCard`, `ActionPlanCard`, reworked `HoldingsTab`) replace the manual weight input.

**Tech Stack:** Python 3.11+, FastAPI, Pydantic v2, Prisma Client Python (asyncio), Next.js 14 App Router, TypeScript, React Query (@tanstack/react-query), Tailwind CSS, Lucide React icons.

---

## File Map

| File | Action | Purpose |
|---|---|---|
| `db/schema.prisma` | Modify | Add new fields to Portfolio, Position, PortfolioAction |
| `api/models/portfolio.py` | Modify | Add PortfolioBreakdown + extend request/response models |
| `api/services/allocation.py` | Create | Pure allocation math functions |
| `api/services/pricing.py` | Create | Price lookup from StockResult.fullOutput |
| `api/services/portfolio_engine.py` | Modify | Add generate_action_plan + update weight computation |
| `api/routes/portfolio.py` | Modify | New endpoints + updated response helpers |
| `api/routes/portfolio_actions.py` | Create | Execute/cancel conditional actions |
| `api/index.py` | Modify | Register portfolio_actions router |
| `tests/test_allocation.py` | Create | Unit tests for allocation math |
| `tests/test_pricing.py` | Create | Unit tests for price lookup |
| `tests/test_portfolio_engine_plans.py` | Create | Unit tests for generate_action_plan |
| `tests/test_portfolio_actions_route.py` | Create | Integration tests for new endpoints |
| `frontend/types/api.ts` | Modify | Extend Portfolio + PortfolioPosition types |
| `frontend/lib/api/client.ts` | Modify | New API methods |
| `frontend/lib/hooks/usePortfolio.ts` | Modify | New mutations |
| `frontend/components/portfolio/CashCard.tsx` | Create | Cash balance card |
| `frontend/components/portfolio/ActionPlanCard.tsx` | Create | Conditional action ladder card |
| `frontend/components/portfolio/HoldingsTab.tsx` | Modify | Replace manual weight input with computed allocation |

---

## Task 1: Prisma Schema Migration

**Files:**
- Modify: `db/schema.prisma`

This is a purely additive migration — no existing fields are removed or renamed. `currentWeight` remains but is deprecated (Phase 2b removes it).

- [ ] **Step 1: Add new fields to `db/schema.prisma`**

Locate the `model Portfolio` block (around line 554) and add the two new fields before the closing `}`:

```prisma
  cashBalance      Float     @default(0)    @map("cash_balance")
  cashUpdatedAt    DateTime? @map("cash_updated_at")
```

Locate the `model Position` block and add after the `latestRunId` field:

```prisma
  lastKnownPrice         Float?    @map("last_known_price")
  lastPriceAt            DateTime? @map("last_price_at")
  targetWeight           Float     @default(0) @map("target_weight")
  engineSuggestedWeight  Float?    @map("engine_suggested_weight")
```

Locate the `model PortfolioAction` block and add after the `expiresAt` field (before the `@@index` lines):

```prisma
  triggerPrice      Float?             @map("trigger_price")
  triggerCondition  String?            @map("trigger_condition")
  parentActionId    String?            @map("parent_action_id")
  parent            PortfolioAction?   @relation("ActionChain", fields: [parentActionId], references: [id])
  children          PortfolioAction[]  @relation("ActionChain")
```

- [ ] **Step 2: Run migration**

```bash
npx prisma migrate dev --name portfolio-holdings-rework
```

Expected: migration file created in `prisma/migrations/`, Prisma client regenerated.

- [ ] **Step 3: Backfill legacy positions in the migration SQL**

Open the generated migration SQL file (`prisma/migrations/*/migration.sql`) and append after the ALTER TABLE statements:

```sql
-- Backfill: legacy positions with currentWeight set but shares null are watch positions
UPDATE positions
SET
  ownership_status = 'watch',
  shares = 0,
  target_weight = current_weight
WHERE shares IS NULL AND current_weight > 0;
```

- [ ] **Step 4: Re-run migration to apply backfill**

```bash
npx prisma migrate dev
```

Expected: migration applies cleanly.

- [ ] **Step 5: Commit**

```bash
git add db/schema.prisma prisma/migrations/
git commit -m "feat: additive schema migration — portfolio holdings rework (Phase 2a)"
```

---

## Task 2: Pydantic Model Extensions

**Files:**
- Modify: `api/models/portfolio.py`

No TDD needed for pure Pydantic model definitions — they are validated by the route tests in Tasks 6–7.

- [ ] **Step 1: Replace `api/models/portfolio.py` with the extended version**

```python
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
    allocation_pct: Optional[float]   # computed: shares * price / total, as percentage (0-100)
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
    cash_pct: float  # percentage (0-100)
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
    trigger_price: Optional[float]
    trigger_condition: Optional[str]
    parent_action_id: Optional[str]
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
```

- [ ] **Step 2: Commit**

```bash
git add api/models/portfolio.py
git commit -m "feat: extend portfolio Pydantic models for holdings rework"
```

---

## Task 3: Allocation Service (TDD)

**Files:**
- Create: `api/services/allocation.py`
- Create: `tests/test_allocation.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_allocation.py`:

```python
"""Unit tests for allocation pure functions."""
import sys
import types
from unittest.mock import MagicMock

# Stub prisma before any api import
_prisma_stub = types.ModuleType("prisma")
_prisma_stub.Prisma = MagicMock  # type: ignore[attr-defined]
sys.modules.setdefault("prisma", _prisma_stub)

import pytest
from api.services.allocation import (
    compute_allocation_pct,
    compute_market_value,
    compute_portfolio_total,
    compute_portfolio_breakdown,
)
from api.models.portfolio import PositionResponse


def _make_pos(ticker, shares, price, target_weight=0.05):
    """Build a mock Position prisma record."""
    p = MagicMock()
    p.ticker = ticker
    p.shares = shares
    p.lastKnownPrice = price
    p.lastPriceAt = None
    p.targetWeight = target_weight
    p.engineSuggestedWeight = None
    p.costBasis = None
    p.tierState = "none"
    p.thesisState = "intact"
    p.eligibilityState = "pending"
    p.ownershipStatus = "watch"
    p.entryDate = None
    p.quartersHeld = 0
    p.compounderScore = None
    p.lastDrawdown = None
    p.latestRunId = None
    return p


# ── compute_market_value ─────────────────────────────────────────────────────

def test_market_value_normal():
    assert compute_market_value(10, 100.0) == pytest.approx(1000.0)

def test_market_value_null_price():
    assert compute_market_value(10, None) is None

def test_market_value_zero_shares():
    assert compute_market_value(0, 100.0) == pytest.approx(0.0)


# ── compute_portfolio_total ──────────────────────────────────────────────────

def test_portfolio_total_normal():
    positions = [_make_pos("NVDA", 10, 100.0), _make_pos("AAPL", 5, 200.0)]
    total = compute_portfolio_total(positions, cash_balance=500.0)
    assert total == pytest.approx(2500.0)  # 1000 + 1000 + 500

def test_portfolio_total_all_null_prices():
    positions = [_make_pos("NVDA", 10, None), _make_pos("AAPL", 5, None)]
    total = compute_portfolio_total(positions, cash_balance=0.0)
    assert total == pytest.approx(0.0)

def test_portfolio_total_zero_everything():
    assert compute_portfolio_total([], cash_balance=0.0) == pytest.approx(0.0)

def test_portfolio_total_cash_only():
    assert compute_portfolio_total([], cash_balance=10000.0) == pytest.approx(10000.0)


# ── compute_allocation_pct ───────────────────────────────────────────────────

def test_allocation_pct_normal():
    pos = _make_pos("NVDA", 10, 100.0)
    pct = compute_allocation_pct(pos, total_value=1000.0)
    assert pct == pytest.approx(100.0)  # 1000 / 1000 = 100%

def test_allocation_pct_partial():
    pos = _make_pos("NVDA", 10, 100.0)
    pct = compute_allocation_pct(pos, total_value=2000.0)
    assert pct == pytest.approx(50.0)

def test_allocation_pct_null_price():
    pos = _make_pos("NVDA", 10, None)
    assert compute_allocation_pct(pos, total_value=1000.0) is None

def test_allocation_pct_zero_total():
    pos = _make_pos("NVDA", 10, 100.0)
    assert compute_allocation_pct(pos, total_value=0.0) is None

def test_allocation_pct_zero_shares():
    pos = _make_pos("NVDA", 0, 100.0)
    assert compute_allocation_pct(pos, total_value=1000.0) == pytest.approx(0.0)


# ── compute_portfolio_breakdown ──────────────────────────────────────────────

def test_breakdown_normal():
    positions = [_make_pos("NVDA", 10, 100.0), _make_pos("AAPL", 5, 200.0)]

    class FakePortfolio:
        id = "p1"
        name = "Core"
        mandate = "compounder"
        cashBalance = 500.0
        cashUpdatedAt = None
        createdAt = None

    FakePortfolio.positions = positions

    breakdown = compute_portfolio_breakdown(FakePortfolio())
    assert breakdown.total_value == pytest.approx(2500.0)
    assert breakdown.cash_pct == pytest.approx(20.0)  # 500 / 2500 * 100
    assert len(breakdown.positions) == 2
    nvda = next(p for p in breakdown.positions if p.ticker == "NVDA")
    assert nvda.allocation_pct == pytest.approx(40.0)  # 1000 / 2500 * 100
    assert nvda.market_value == pytest.approx(1000.0)

def test_breakdown_zero_portfolio():
    class FakePortfolio:
        id = "p1"
        name = "Core"
        mandate = "compounder"
        cashBalance = 0.0
        cashUpdatedAt = None
        createdAt = None
        positions = []

    breakdown = compute_portfolio_breakdown(FakePortfolio())
    assert breakdown.total_value == pytest.approx(0.0)
    assert breakdown.cash_pct == pytest.approx(0.0)
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_allocation.py -v
```

Expected: `ModuleNotFoundError: No module named 'api.services.allocation'`

- [ ] **Step 3: Implement `api/services/allocation.py`**

```python
"""
Portfolio allocation pure functions.

All functions are stateless — no DB reads. Pass in Prisma records (or mocks).
"""

from __future__ import annotations

from typing import Optional

from api.models.portfolio import PortfolioBreakdown, PositionResponse


def compute_market_value(shares: float, last_known_price: Optional[float]) -> Optional[float]:
    """Return shares * price, or None if price is unavailable."""
    if last_known_price is None:
        return None
    return shares * last_known_price


def compute_portfolio_total(positions, cash_balance: float) -> float:
    """Sum market values of all positions (skipping null prices) plus cash."""
    total = cash_balance
    for pos in positions:
        mv = compute_market_value(pos.shares or 0.0, pos.lastKnownPrice)
        if mv is not None:
            total += mv
    return total


def compute_allocation_pct(position, total_value: float) -> Optional[float]:
    """
    Return position's allocation as a percentage (0-100).

    Returns None if lastKnownPrice is None or total_value is 0.
    Returns 0.0 if shares is 0.
    """
    if total_value == 0.0:
        return None
    mv = compute_market_value(position.shares or 0.0, position.lastKnownPrice)
    if mv is None:
        return None
    return (mv / total_value) * 100.0


def _position_to_response(position, allocation_pct: Optional[float], market_value: Optional[float]) -> PositionResponse:
    return PositionResponse(
        ticker=position.ticker,
        shares=position.shares or 0.0,
        cost_basis=position.costBasis,
        last_known_price=position.lastKnownPrice,
        last_price_at=position.lastPriceAt,
        allocation_pct=allocation_pct,
        market_value=market_value,
        target_weight=position.targetWeight or 0.0,
        engine_suggested_weight=position.engineSuggestedWeight,
        tier_state=position.tierState,
        thesis_state=position.thesisState,
        eligibility_state=position.eligibilityState,
        ownership_status=position.ownershipStatus,
        entry_date=position.entryDate,
        quarters_held=position.quartersHeld,
        compounder_score=position.compounderScore,
        last_drawdown=position.lastDrawdown,
        latest_run_id=position.latestRunId,
    )


def compute_portfolio_breakdown(portfolio) -> PortfolioBreakdown:
    """
    Compute full portfolio breakdown: total value, cash %, and per-position allocations.

    Returns a PortfolioBreakdown with PositionResponse objects that include
    computed allocation_pct and market_value.
    """
    positions = portfolio.positions or []
    cash = portfolio.cashBalance or 0.0
    total = compute_portfolio_total(positions, cash)

    position_responses = []
    for pos in positions:
        mv = compute_market_value(pos.shares or 0.0, pos.lastKnownPrice)
        alloc_pct = compute_allocation_pct(pos, total)
        position_responses.append(_position_to_response(pos, alloc_pct, mv))

    cash_pct = (cash / total * 100.0) if total > 0 else 0.0

    return PortfolioBreakdown(
        total_value=total,
        cash_balance=cash,
        cash_pct=cash_pct,
        positions=position_responses,
    )
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_allocation.py -v
```

Expected: all tests PASS.

- [ ] **Step 5: Commit**

```bash
git add api/services/allocation.py tests/test_allocation.py
git commit -m "feat: allocation pure functions with full test coverage"
```

---

## Task 4: Pricing Service (TDD)

**Files:**
- Create: `api/services/pricing.py`
- Create: `tests/test_pricing.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_pricing.py`:

```python
"""Unit tests for the pricing service."""
import sys
import types
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

_prisma_stub = types.ModuleType("prisma")
_prisma_stub.Prisma = MagicMock  # type: ignore[attr-defined]
sys.modules.setdefault("prisma", _prisma_stub)

import pytest
from api.services.pricing import get_latest_price, refresh_position_prices


def _make_stock_result(current_price: float | None):
    """Build a mock StockResult with price nested in fullOutput."""
    r = MagicMock()
    if current_price is not None:
        r.fullOutput = {
            "quant_output": {
                "technical_indicators": {
                    "moving_averages": {
                        "current_price": current_price
                    }
                }
            }
        }
    else:
        r.fullOutput = {}
    return r


# ── get_latest_price ─────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_get_latest_price_found():
    mock_db = MagicMock()
    mock_db.stockresult.find_first = AsyncMock(return_value=_make_stock_result(142.50))

    with patch("api.services.pricing.get_db", return_value=mock_db):
        price, as_of = await get_latest_price("AAPL", user_id="u1")

    assert price == pytest.approx(142.50)
    assert as_of is not None

@pytest.mark.asyncio
async def test_get_latest_price_no_result():
    mock_db = MagicMock()
    mock_db.stockresult.find_first = AsyncMock(return_value=None)

    with patch("api.services.pricing.get_db", return_value=mock_db):
        price, as_of = await get_latest_price("UNKNOWN", user_id="u1")

    assert price is None
    assert as_of is None

@pytest.mark.asyncio
async def test_get_latest_price_empty_full_output():
    mock_db = MagicMock()
    mock_db.stockresult.find_first = AsyncMock(return_value=_make_stock_result(None))

    with patch("api.services.pricing.get_db", return_value=mock_db):
        price, as_of = await get_latest_price("MSFT", user_id="u1")

    assert price is None
    assert as_of is None


# ── refresh_position_prices ──────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_refresh_position_prices_updates_known():
    mock_db = MagicMock()

    pos1 = MagicMock()
    pos1.id = "pos1"
    pos1.ticker = "NVDA"
    pos1.latestRunId = "run1"

    mock_db.position.find_many = AsyncMock(return_value=[pos1])
    mock_db.stockresult.find_first = AsyncMock(return_value=_make_stock_result(875.0))
    mock_db.position.update = AsyncMock()

    with patch("api.services.pricing.get_db", return_value=mock_db):
        updated, skipped = await refresh_position_prices("portfolio1", user_id="u1")

    assert updated == 1
    assert skipped == 0
    mock_db.position.update.assert_called_once()
    call_kwargs = mock_db.position.update.call_args
    assert call_kwargs.kwargs["data"]["lastKnownPrice"] == pytest.approx(875.0)

@pytest.mark.asyncio
async def test_refresh_position_prices_skips_no_result():
    mock_db = MagicMock()

    pos1 = MagicMock()
    pos1.id = "pos1"
    pos1.ticker = "UNKNOWN"
    pos1.latestRunId = None

    mock_db.position.find_many = AsyncMock(return_value=[pos1])
    mock_db.stockresult.find_first = AsyncMock(return_value=None)
    mock_db.position.update = AsyncMock()

    with patch("api.services.pricing.get_db", return_value=mock_db):
        updated, skipped = await refresh_position_prices("portfolio1", user_id="u1")

    assert updated == 0
    assert skipped == 1
    mock_db.position.update.assert_not_called()
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_pricing.py -v
```

Expected: `ModuleNotFoundError: No module named 'api.services.pricing'`

- [ ] **Step 3: Implement `api/services/pricing.py`**

```python
"""
Pricing service — looks up current prices from StockResult.fullOutput.

Price source: StockResult.fullOutput["quant_output"]["technical_indicators"]
             ["moving_averages"]["current_price"]
Falls back to ti["current_price"] or quant["current_price"].
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional

from api.lib.db import get_db

logger = logging.getLogger(__name__)


def _extract_price_from_full_output(full_output: dict | None) -> Optional[float]:
    """Extract current_price from the nested StockResult.fullOutput structure."""
    if not full_output:
        return None
    quant = full_output.get("quant_output") or {}
    ti = (quant.get("technical_indicators") or {})
    ma = (ti.get("moving_averages") or {})
    price = (
        ma.get("current_price")
        or ti.get("current_price")
        or quant.get("current_price")
    )
    return float(price) if price else None


async def get_latest_price(ticker: str, user_id: str) -> tuple[Optional[float], Optional[datetime]]:
    """
    Return (price, as_of) for the most recent completed StockResult for ticker.

    Returns (None, None) if no result found or fullOutput has no price.
    """
    db = await get_db()
    result = await db.stockresult.find_first(
        where={"userId": user_id, "ticker": ticker, "status": "completed"},
        order={"createdAt": "desc"},
    )
    if not result:
        return None, None

    full_output = result.fullOutput if isinstance(result.fullOutput, dict) else {}
    price = _extract_price_from_full_output(full_output)
    if price is None:
        return None, None

    return price, datetime.now(timezone.utc)


async def refresh_position_prices(portfolio_id: str, user_id: str) -> tuple[int, int]:
    """
    Update lastKnownPrice / lastPriceAt for all positions in a portfolio.

    Returns (updated_count, skipped_count).
    Skipped = no StockResult found or fullOutput has no price.
    """
    db = await get_db()
    positions = await db.position.find_many(where={"portfolioId": portfolio_id})

    updated = 0
    skipped = 0

    for pos in positions:
        price, as_of = await get_latest_price(pos.ticker, user_id)
        if price is None:
            logger.debug("No price for %s — skipping", pos.ticker)
            skipped += 1
            continue

        await db.position.update(
            where={"id": pos.id},
            data={"lastKnownPrice": price, "lastPriceAt": as_of},
        )
        updated += 1

    return updated, skipped
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_pricing.py -v
```

Expected: all tests PASS.

- [ ] **Step 5: Commit**

```bash
git add api/services/pricing.py tests/test_pricing.py
git commit -m "feat: pricing service with StockResult.fullOutput price extraction"
```

---

## Task 5: Engine — Signal-Driven Action Plans (TDD)

**Files:**
- Modify: `api/services/portfolio_engine.py`
- Create: `tests/test_portfolio_engine_plans.py`

This task adds `generate_action_plan` and updates `_to_engine_positions` to use computed weights from shares × price rather than `currentWeight`. The existing `run_portfolio_engine` orchestration is also updated to call price-based weight computation.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_portfolio_engine_plans.py`:

```python
"""Unit tests for generate_action_plan — signal-driven conditional action plans."""
import sys
import types
from unittest.mock import MagicMock

_prisma_stub = types.ModuleType("prisma")
_prisma_stub.Prisma = MagicMock  # type: ignore[attr-defined]
sys.modules.setdefault("prisma", _prisma_stub)

import pytest
from api.services.portfolio_engine import generate_action_plan, classify_posture


def _make_position(
    ticker="NVDA",
    shares=100.0,
    last_known_price=100.0,
    target_weight=0.08,
    thesis_state="intact",
    ownership_status="core_compounder",
):
    pos = MagicMock()
    pos.ticker = ticker
    pos.shares = shares
    pos.lastKnownPrice = last_known_price
    pos.targetWeight = target_weight
    pos.thesisState = thesis_state
    pos.ownershipStatus = ownership_status
    pos.portfolioId = "portfolio1"
    return pos


def _make_stock_result(verdict="buy", fair_value=None, support_level=None):
    """Minimal StockResult fullOutput structure."""
    sr = MagicMock()
    sr.ticker = "NVDA"
    sr.fullOutput = {
        "verdict": verdict,
        "quant_output": {
            "technical_indicators": {
                "moving_averages": {"current_price": 100.0},
                "support_levels": [support_level or 85.0],
            }
        },
        "fundamental_output": {
            "valuation": {
                "fair_value": fair_value or 130.0
            }
        },
    }
    return sr


# ── classify_posture ─────────────────────────────────────────────────────────

def test_classify_posture_over_target_bearish():
    pos = _make_position(shares=130, last_known_price=100.0, target_weight=0.08)
    # current_alloc = 13% vs target 8% — over by 5%. verdict = avoid
    result = classify_posture(pos, current_alloc=0.13, stock_result=_make_stock_result(verdict="avoid"))
    assert result == "over_target_bearish"

def test_classify_posture_over_target_bullish():
    pos = _make_position(shares=130, last_known_price=100.0, target_weight=0.08)
    result = classify_posture(pos, current_alloc=0.13, stock_result=_make_stock_result(verdict="buy"))
    assert result == "over_target_bullish"

def test_classify_posture_below_target_bullish():
    pos = _make_position(shares=50, last_known_price=100.0, target_weight=0.08)
    result = classify_posture(pos, current_alloc=0.04, stock_result=_make_stock_result(verdict="buy"))
    assert result == "below_target_bullish"

def test_classify_posture_thesis_broken():
    pos = _make_position(thesis_state="broken")
    result = classify_posture(pos, current_alloc=0.05, stock_result=_make_stock_result())
    assert result == "thesis_broken"

def test_classify_posture_watch_only():
    pos = _make_position(shares=0, ownership_status="watch")
    result = classify_posture(pos, current_alloc=0.0, stock_result=_make_stock_result())
    assert result == "watch_only"

def test_classify_posture_hold():
    pos = _make_position(shares=80, last_known_price=100.0, target_weight=0.08)
    # 8% alloc, 8% target — within 2% band
    result = classify_posture(pos, current_alloc=0.08, stock_result=_make_stock_result(verdict="hold"))
    assert result == "hold"


# ── generate_action_plan ─────────────────────────────────────────────────────

def test_trim_ladder_over_target_bearish():
    pos = _make_position(shares=130, last_known_price=100.0, target_weight=0.08)
    actions = generate_action_plan(
        position=pos,
        stock_result=_make_stock_result(verdict="avoid"),
        current_alloc=0.13,
        portfolio_id="portfolio1",
    )
    # Must produce at least 2 linked steps
    assert len(actions) >= 2
    # All actions belong to NVDA
    assert all(a["ticker"] == "NVDA" for a in actions)
    # First action has no parent; subsequent ones do
    assert actions[0]["parentActionId"] is None
    assert actions[1]["parentActionId"] is None or actions[1]["parentActionId"] == "__PARENT__"
    # First step has a triggerPrice
    assert actions[0]["triggerPrice"] is not None
    assert actions[0]["triggerCondition"] in ("price_above", "immediate")

def test_entry_ladder_watch_only():
    pos = _make_position(shares=0, ownership_status="watch", target_weight=0.05)
    actions = generate_action_plan(
        position=pos,
        stock_result=_make_stock_result(verdict="buy"),
        current_alloc=0.0,
        portfolio_id="portfolio1",
    )
    assert len(actions) >= 1
    assert all(a["actionType"] in ("INITIATE", "ADD_TIER_20", "ADD_TIER_30") for a in actions)

def test_thesis_broken_exit_plan():
    pos = _make_position(thesis_state="broken", shares=100, last_known_price=100.0)
    actions = generate_action_plan(
        position=pos,
        stock_result=_make_stock_result(verdict="avoid"),
        current_alloc=0.10,
        portfolio_id="portfolio1",
    )
    assert len(actions) == 1
    assert actions[0]["actionType"] == "EXIT_THESIS"
    assert actions[0]["triggerCondition"] == "immediate"

def test_hold_posture_produces_no_actions():
    pos = _make_position(shares=80, last_known_price=100.0, target_weight=0.08)
    actions = generate_action_plan(
        position=pos,
        stock_result=_make_stock_result(verdict="hold"),
        current_alloc=0.08,
        portfolio_id="portfolio1",
    )
    assert actions == []

def test_review_action_when_no_stock_result():
    pos = _make_position()
    actions = generate_action_plan(
        position=pos,
        stock_result=None,
        current_alloc=0.08,
        portfolio_id="portfolio1",
    )
    assert len(actions) == 1
    assert actions[0]["actionType"] == "HOLD"
    assert "No recent analysis" in actions[0]["reasonText"]
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_portfolio_engine_plans.py -v
```

Expected: `ImportError: cannot import name 'generate_action_plan'`

- [ ] **Step 3: Add `classify_posture` and `generate_action_plan` to `api/services/portfolio_engine.py`**

Add the following at the end of `api/services/portfolio_engine.py` (after the existing `_update_position_states` function):

```python

# ── Signal-Driven Action Plans ──────────────────────────────────────────────

_POSTURE_THRESHOLD = 0.02  # 2pp band before over/under target triggers action


def _get_verdict_from_stock_result(stock_result) -> str:
    """Extract verdict string from StockResult.fullOutput. Falls back to 'hold'."""
    if stock_result is None:
        return "hold"
    full_output = stock_result.fullOutput
    if isinstance(full_output, dict):
        return full_output.get("verdict", "hold").lower()
    return "hold"


def _get_fair_value_from_stock_result(stock_result) -> Optional[float]:
    """Extract fair value from fundamental_output.valuation.fair_value."""
    if stock_result is None:
        return None
    fo = stock_result.fullOutput
    if not isinstance(fo, dict):
        return None
    return fo.get("fundamental_output", {}).get("valuation", {}).get("fair_value")


def _get_support_level_from_stock_result(stock_result) -> Optional[float]:
    """Extract first support level from quant_output.technical_indicators.support_levels."""
    if stock_result is None:
        return None
    fo = stock_result.fullOutput
    if not isinstance(fo, dict):
        return None
    levels = (
        fo.get("quant_output", {})
        .get("technical_indicators", {})
        .get("support_levels", [])
    )
    return float(levels[0]) if levels else None


def classify_posture(position, current_alloc: float, stock_result) -> str:
    """
    Classify a position's rebalancing posture based on allocation and signals.

    Returns one of: over_target_bearish | over_target_bullish | below_target_bullish |
                    thesis_broken | watch_only | hold
    """
    if position.thesisState == "broken":
        return "thesis_broken"

    if (position.shares or 0.0) == 0.0 or position.ownershipStatus == "watch":
        return "watch_only"

    target = position.targetWeight or 0.0
    verdict = _get_verdict_from_stock_result(stock_result)
    over_target = current_alloc > target + _POSTURE_THRESHOLD
    under_target = current_alloc < target - _POSTURE_THRESHOLD

    if over_target and verdict == "avoid":
        return "over_target_bearish"
    if over_target:
        return "over_target_bullish"
    if under_target and verdict == "buy":
        return "below_target_bullish"
    return "hold"


def generate_action_plan(
    position,
    stock_result,
    current_alloc: float,
    portfolio_id: str,
) -> list[dict]:
    """
    Generate a conditional action plan for a position.

    Returns a list of action dicts (not yet persisted) suitable for
    db.portfolioaction.create(data=...) calls. The first action in a ladder
    has parentActionId=None; subsequent steps use the sentinel "__PARENT__"
    which the caller replaces with the DB-assigned id of the first action.

    Returns [] for hold posture (no action needed).
    """
    if stock_result is None:
        return [{
            "portfolioId": portfolio_id,
            "ticker": position.ticker,
            "actionType": "HOLD",
            "weightDelta": 0.0,
            "reasonCodes": ["no_analysis"],
            "reasonText": "No recent analysis available — review position manually",
            "triggerCondition": "immediate",
            "triggerPrice": None,
            "parentActionId": None,
            "status": "pending",
        }]

    posture = classify_posture(position, current_alloc, stock_result)
    price = position.lastKnownPrice or 0.0
    verdict = _get_verdict_from_stock_result(stock_result)
    fair_value = _get_fair_value_from_stock_result(stock_result)
    support = _get_support_level_from_stock_result(stock_result)
    target = position.targetWeight or 0.0

    def _action(action_type, weight_delta, trigger_cond, trigger_price, reason_text, parent=None):
        return {
            "portfolioId": portfolio_id,
            "ticker": position.ticker,
            "actionType": action_type,
            "weightDelta": round(weight_delta, 4),
            "reasonCodes": [posture],
            "reasonText": reason_text,
            "triggerCondition": trigger_cond,
            "triggerPrice": round(trigger_price, 2) if trigger_price else None,
            "parentActionId": parent,
            "status": "pending",
        }

    if posture == "hold":
        return []

    if posture == "thesis_broken":
        return [_action(
            "EXIT_THESIS", -current_alloc, "immediate", None,
            "Thesis broken — exit position",
        )]

    if posture == "over_target_bearish":
        # Trim ladder: 3 steps above current price (5%, 10%, 15% premium)
        excess = current_alloc - target
        step = excess / 3.0
        return [
            _action("TRIM_EUPHORIA", -step, "price_above", price * 1.05,
                    f"Over target ({current_alloc:.1%} vs {target:.1%}) with bearish signals — trim first tranche"),
            _action("TRIM_EUPHORIA", -step, "price_above", price * 1.10,
                    "Second trim if price continues higher", parent="__PARENT__"),
            _action("TRIM_EUPHORIA", -step, "price_above", price * 1.15,
                    "Final trim to target weight", parent="__PARENT__"),
        ]

    if posture == "over_target_bullish":
        # Hold but set a high trim trigger using fair value or 20% premium
        trim_target = fair_value if fair_value and fair_value > price else price * 1.20
        excess = current_alloc - target
        return [
            _action("TRIM_CAP", -excess / 2.0, "price_above", trim_target * 0.95,
                    f"Over target but signals bullish — ride position, trim 50% of excess near fair value"),
            _action("TRIM_CAP", -excess / 2.0, "price_above", trim_target,
                    "Trim remaining excess at fair value", parent="__PARENT__"),
        ]

    if posture == "below_target_bullish":
        # Add ladder on pullbacks using support level or 5%/10% discounts
        entry1 = support if support and support < price else price * 0.95
        entry2 = entry1 * 0.95
        gap = target - current_alloc
        return [
            _action("ADD_TIER_20", gap / 2.0, "price_below", entry1,
                    f"Below target ({current_alloc:.1%} vs {target:.1%}) — add first tranche on pullback"),
            _action("ADD_TIER_20", gap / 2.0, "price_below", entry2,
                    "Add remaining gap on deeper pullback", parent="__PARENT__"),
        ]

    if posture == "watch_only":
        entry = support if support and support < (fair_value or price) else price * 0.92
        return [
            _action("INITIATE", target / 2.0, "price_below", entry,
                    f"Watch position — enter first half at pullback to {entry:.2f}"),
            _action("ADD_TIER_20", target / 2.0, "price_below", entry * 0.95,
                    "Add second half on deeper discount", parent="__PARENT__"),
        ]

    return []
```

- [ ] **Step 4: Also update `_to_engine_positions` to accept a pre-computed weights map**

Find the existing `_to_engine_positions` function in `api/services/portfolio_engine.py` and replace it:

```python
def _to_engine_positions(db_positions, weights_map: dict[str, float] | None = None) -> dict[str, "EnginePosition"]:
    """
    Convert Prisma Position records to engine PortfolioPosition dataclass.

    weights_map: ticker → computed allocation fraction (from shares × price / total).
    Falls back to position.currentWeight if not provided (legacy behavior).
    """
    result: dict[str, EnginePosition] = {}
    for pos in db_positions:
        add_tiers = set()
        if pos.addTiersApplied:
            try:
                raw = pos.addTiersApplied if isinstance(pos.addTiersApplied, list) else json.loads(str(pos.addTiersApplied))
                add_tiers = set(float(t) for t in raw)
            except (json.JSONDecodeError, ValueError, TypeError):
                pass

        weight = (weights_map or {}).get(pos.ticker, pos.currentWeight or 0.0)

        result[pos.ticker] = EnginePosition(
            ticker=pos.ticker,
            weight=weight,
            entry_date=pos.entryDate.date() if pos.entryDate else date.today(),
            entry_price=pos.costBasis or 0.0,
            quarters_held=pos.quartersHeld,
            compounder_score=pos.compounderScore or 0.0,
            add_tiers_applied=add_tiers,
            last_drawdown=pos.lastDrawdown or 0.0,
        )
    return result
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
pytest tests/test_portfolio_engine_plans.py -v
```

Expected: all tests PASS.

- [ ] **Step 6: Commit**

```bash
git add api/services/portfolio_engine.py tests/test_portfolio_engine_plans.py
git commit -m "feat: signal-driven action plan generation with posture classification"
```

---

## Task 6: Portfolio Route Changes (TDD)

**Files:**
- Modify: `api/routes/portfolio.py`
- Create: `tests/test_portfolio_actions_route.py` (shared with Task 7)

- [ ] **Step 1: Write tests for new portfolio endpoints**

Create `tests/test_portfolio_actions_route.py`:

```python
"""Integration tests for new portfolio endpoints: refresh-prices, cash, rebalance."""
import sys
import types
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

_prisma_stub = types.ModuleType("prisma")
_prisma_stub.Prisma = MagicMock  # type: ignore[attr-defined]
sys.modules.setdefault("prisma", _prisma_stub)

import pytest
from fastapi.testclient import TestClient


def _make_user(tier="starter"):
    user = MagicMock()
    user.id = "user1"
    user.tier = tier
    user.is_admin = False
    return user


def _make_portfolio(positions=None):
    portfolio = MagicMock()
    portfolio.id = "portfolio1"
    portfolio.userId = "user1"
    portfolio.name = "Core"
    portfolio.mandate = "compounder"
    portfolio.cashBalance = 1000.0
    portfolio.cashUpdatedAt = None
    portfolio.createdAt = datetime(2026, 1, 1, tzinfo=timezone.utc)
    portfolio.positions = positions or []
    return portfolio


def _make_position(ticker="NVDA"):
    pos = MagicMock()
    pos.id = "pos1"
    pos.ticker = ticker
    pos.shares = 10.0
    pos.lastKnownPrice = 100.0
    pos.lastPriceAt = None
    pos.targetWeight = 0.08
    pos.engineSuggestedWeight = 0.07
    pos.costBasis = 90.0
    pos.tierState = "none"
    pos.thesisState = "intact"
    pos.eligibilityState = "eligible"
    pos.ownershipStatus = "core_compounder"
    pos.entryDate = None
    pos.quartersHeld = 4
    pos.compounderScore = 0.72
    pos.lastDrawdown = None
    pos.latestRunId = "run1"
    pos.addTiersApplied = "[]"
    pos.portfolioId = "portfolio1"
    return pos


# ── POST /portfolio/{id}/refresh-prices ─────────────────────────────────────

@pytest.mark.asyncio
async def test_refresh_prices_returns_counts():
    from api.routes.portfolio import router
    from fastapi import FastAPI
    app = FastAPI()
    app.include_router(router, prefix="/api")

    mock_db = MagicMock()
    mock_db.portfolio.find_unique = AsyncMock(return_value=_make_portfolio([_make_position()]))

    user = _make_user()

    with patch("api.routes.portfolio.get_current_user", return_value=user), \
         patch("api.routes.portfolio.get_db", return_value=mock_db), \
         patch("api.routes.portfolio.refresh_position_prices", new_callable=AsyncMock, return_value=(1, 0)):
        client = TestClient(app)
        resp = client.post("/api/portfolio/portfolio1/refresh-prices")

    assert resp.status_code == 200
    data = resp.json()
    assert data["updated"] == 1
    assert data["skipped"] == 0


# ── POST /portfolio/{id}/cash ────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_update_cash_balance():
    from api.routes.portfolio import router
    from fastapi import FastAPI
    app = FastAPI()
    app.include_router(router, prefix="/api")

    mock_db = MagicMock()
    mock_db.portfolio.find_unique = AsyncMock(return_value=_make_portfolio())
    mock_db.portfolio.update = AsyncMock()

    user = _make_user()

    with patch("api.routes.portfolio.get_current_user", return_value=user), \
         patch("api.routes.portfolio.get_db", return_value=mock_db):
        client = TestClient(app)
        resp = client.post("/api/portfolio/portfolio1/cash", json={"amount": 5000.0})

    assert resp.status_code == 200
    assert resp.json()["cash_balance"] == pytest.approx(5000.0)
    mock_db.portfolio.update.assert_called_once()


# ── POST /portfolio/{id}/positions (new — shares required) ──────────────────

@pytest.mark.asyncio
async def test_add_position_requires_shares():
    from api.routes.portfolio import router
    from fastapi import FastAPI
    app = FastAPI()
    app.include_router(router, prefix="/api")

    mock_db = MagicMock()
    mock_db.portfolio.find_unique = AsyncMock(return_value=_make_portfolio())
    mock_db.position.find_first = AsyncMock(return_value=None)
    mock_db.stockresult.find_first = AsyncMock(return_value=None)
    mock_db.position.create = AsyncMock(return_value=_make_position())

    user = _make_user()

    with patch("api.routes.portfolio.get_current_user", return_value=user), \
         patch("api.routes.portfolio.get_db", return_value=mock_db), \
         patch("api.routes.portfolio.has_feature", return_value=True):
        client = TestClient(app)
        # Missing shares → 422
        resp = client.post("/api/portfolio/portfolio1/positions",
                           json={"ticker": "AAPL"})

    assert resp.status_code == 422
```

- [ ] **Step 2: Run tests to verify relevant ones fail as expected**

```bash
pytest tests/test_portfolio_actions_route.py -v 2>&1 | head -40
```

Expected: failures referencing missing imports (`refresh_position_prices` not imported in route, endpoint not found).

- [ ] **Step 3: Update route file imports and helpers**

At the top of `api/routes/portfolio.py`, add these imports after the existing ones:

```python
from api.services.allocation import compute_portfolio_breakdown
from api.services.pricing import refresh_position_prices
from api.models.portfolio import (
    ActionChainResponse,
    UpdateCashRequest,
    # keep existing imports below
    ActionFeedResponse,
    ActionResponse,
    AddPositionRequest,
    CreatePortfolioRequest,
    MarkActionRequest,
    PortfolioListResponse,
    PortfolioResponse,
    PositionResponse,
    UpdatePositionRequest,
)
```

Replace the `_position_response` helper entirely:

```python
def _position_response(pos, allocation_pct=None, market_value=None) -> PositionResponse:
    """Convert a Prisma Position record to PositionResponse."""
    return PositionResponse(
        ticker=pos.ticker,
        shares=pos.shares or 0.0,
        cost_basis=pos.costBasis,
        last_known_price=pos.lastKnownPrice,
        last_price_at=pos.lastPriceAt,
        allocation_pct=allocation_pct,
        market_value=market_value,
        target_weight=pos.targetWeight or 0.0,
        engine_suggested_weight=pos.engineSuggestedWeight,
        tier_state=pos.tierState,
        thesis_state=pos.thesisState,
        eligibility_state=pos.eligibilityState,
        ownership_status=pos.ownershipStatus,
        entry_date=pos.entryDate,
        quarters_held=pos.quartersHeld,
        compounder_score=pos.compounderScore,
        last_drawdown=pos.lastDrawdown,
        latest_run_id=pos.latestRunId,
    )
```

Replace `_portfolio_response` entirely:

```python
def _portfolio_response(portfolio) -> PortfolioResponse:
    """Convert a Prisma Portfolio record (with positions) to PortfolioResponse."""
    breakdown = compute_portfolio_breakdown(portfolio)
    return PortfolioResponse(
        id=portfolio.id,
        name=portfolio.name,
        mandate=portfolio.mandate,
        positions=breakdown.positions,
        total_value=breakdown.total_value,
        cash_balance=breakdown.cash_balance,
        cash_pct=breakdown.cash_pct,
        position_count=len(breakdown.positions),
        created_at=portfolio.createdAt,
    )
```

Replace the `add_position` endpoint entirely:

```python
@router.post("/portfolio/{portfolio_id}/positions", response_model=PositionResponse)
async def add_position(
    portfolio_id: str,
    request: AddPositionRequest,
    user: User = Depends(get_current_user),
):
    """Add a position to a portfolio. Requires shares count."""
    db = await get_db()
    portfolio = await _verify_portfolio_ownership(db, portfolio_id, user.id)

    ticker = request.ticker.upper()

    existing = await db.position.find_first(
        where={"portfolioId": portfolio_id, "ticker": ticker}
    )
    if existing:
        raise HTTPException(status_code=400, detail=f"{ticker} already in portfolio")

    # Auto-populate price from latest StockResult
    from api.services.pricing import get_latest_price
    price, price_at = await get_latest_price(ticker, user.id)

    # Find most recent analysis for latestRunId
    latest_result = await db.stockresult.find_first(
        where={"userId": user.id, "ticker": ticker, "status": "completed"},
        order={"createdAt": "desc"},
    )

    # Engine-suggested weight (placeholder — engine run fills this properly)
    engine_suggested = request.target_weight

    position = await db.position.create(
        data={
            "portfolioId": portfolio_id,
            "ticker": ticker,
            "shares": request.shares,
            "costBasis": request.cost_basis,
            "lastKnownPrice": price,
            "lastPriceAt": price_at,
            "targetWeight": request.target_weight or 0.0,
            "engineSuggestedWeight": engine_suggested,
            "entryDate": datetime.now(timezone.utc),
            "latestRunId": latest_result.runId if latest_result else None,
            "ownershipStatus": "watch" if request.shares == 0 else "watch",
        }
    )
    return _position_response(position)
```

Replace the `update_position` endpoint entirely:

```python
@router.patch("/portfolio/{portfolio_id}/positions/{ticker}", response_model=PositionResponse)
async def update_position(
    portfolio_id: str,
    ticker: str,
    request: UpdatePositionRequest,
    user: User = Depends(get_current_user),
):
    """Update an existing position's shares, cost basis, or target weight."""
    db = await get_db()
    await _verify_portfolio_ownership(db, portfolio_id, user.id)

    ticker = ticker.upper()
    position = await db.position.find_first(
        where={"portfolioId": portfolio_id, "ticker": ticker}
    )
    if not position:
        raise HTTPException(status_code=404, detail=f"{ticker} not found in portfolio")

    update_data = {}
    if request.shares is not None:
        update_data["shares"] = request.shares
    if request.cost_basis is not None:
        update_data["costBasis"] = request.cost_basis
    if request.target_weight is not None:
        update_data["targetWeight"] = request.target_weight

    if not update_data:
        return _position_response(position)

    updated = await db.position.update(
        where={"id": position.id},
        data=update_data,
    )
    return _position_response(updated)
```

- [ ] **Step 4: Add new endpoints to `api/routes/portfolio.py`**

Add after the existing `trigger_engine_run` endpoint:

```python
# ── Refresh Prices ────────────────────────────────────────────────────────────


@router.post("/portfolio/{portfolio_id}/refresh-prices")
async def refresh_prices(
    portfolio_id: str,
    user: User = Depends(get_current_user),
):
    """Refresh lastKnownPrice for all positions from their latest StockResult."""
    db = await get_db()
    await _verify_portfolio_ownership(db, portfolio_id, user.id)
    updated, skipped = await refresh_position_prices(portfolio_id, user.id)
    return {"updated": updated, "skipped": skipped, "portfolio_id": portfolio_id}


# ── Cash Balance ──────────────────────────────────────────────────────────────


@router.post("/portfolio/{portfolio_id}/cash")
async def update_cash(
    portfolio_id: str,
    request: UpdateCashRequest,
    user: User = Depends(get_current_user),
):
    """Update the cash balance for a portfolio."""
    db = await get_db()
    await _verify_portfolio_ownership(db, portfolio_id, user.id)
    now = datetime.now(timezone.utc)
    await db.portfolio.update(
        where={"id": portfolio_id},
        data={"cashBalance": request.amount, "cashUpdatedAt": now},
    )
    return {"cash_balance": request.amount, "updated_at": now.isoformat()}


# ── Rebalance ─────────────────────────────────────────────────────────────────


@router.post("/portfolio/{portfolio_id}/rebalance")
async def rebalance_portfolio(
    portfolio_id: str,
    user: User = Depends(get_current_user),
):
    """
    Run the signal-driven action plan generator for each position.

    Expires existing pending actions, then creates new linked PortfolioAction chains.
    Requires Starter+ (same as engine/run).
    """
    if not has_feature(user, FEAT_PORTFOLIO_ACTIONS):
        raise HTTPException(status_code=403, detail={
            "code": "NOT_ENTITLED",
            "message": "Rebalance requires Starter tier or above",
        })

    db = await get_db()
    portfolio = await _verify_portfolio_ownership(db, portfolio_id, user.id)
    positions = portfolio.positions or []

    if not positions:
        return {"actions_created": 0, "message": "No positions"}

    from api.services.allocation import compute_portfolio_total, compute_allocation_pct
    from api.services.portfolio_engine import generate_action_plan

    cash = portfolio.cashBalance or 0.0
    total = compute_portfolio_total(positions, cash)

    # Expire existing pending plans
    await db.portfolioaction.update_many(
        where={"portfolioId": portfolio_id, "status": "pending"},
        data={"status": "expired"},
    )

    actions_created = 0
    for pos in positions:
        current_alloc = (compute_allocation_pct(pos, total) or 0.0) / 100.0

        # Load latest StockResult
        stock_result = None
        if pos.latestRunId:
            stock_result = await db.stockresult.find_first(
                where={"userId": user.id, "ticker": pos.ticker, "status": "completed"},
                order={"createdAt": "desc"},
            )

        action_dicts = generate_action_plan(
            position=pos,
            stock_result=stock_result,
            current_alloc=current_alloc,
            portfolio_id=portfolio_id,
        )

        # Persist chain: first action is parent, rest reference it
        parent_id = None
        for i, ad in enumerate(action_dicts):
            create_data = {k: v for k, v in ad.items() if k != "parentActionId"}
            if i == 0:
                created = await db.portfolioaction.create(data=create_data)
                parent_id = created.id
            else:
                if ad.get("parentActionId") == "__PARENT__":
                    create_data["parentActionId"] = parent_id
                await db.portfolioaction.create(data=create_data)
            actions_created += 1

    return {"actions_created": actions_created, "portfolio_id": portfolio_id}
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
pytest tests/test_portfolio_actions_route.py -v
```

Expected: all tests PASS.

- [ ] **Step 6: Commit**

```bash
git add api/routes/portfolio.py tests/test_portfolio_actions_route.py
git commit -m "feat: portfolio route — computed allocations, refresh-prices, cash, rebalance endpoints"
```

---

## Task 7: Portfolio Actions Route

**Files:**
- Create: `api/routes/portfolio_actions.py`
- Modify: `api/index.py`

- [ ] **Step 1: Add execute/cancel tests to `tests/test_portfolio_actions_route.py`**

Append to `tests/test_portfolio_actions_route.py`:

```python
# ── POST /actions/{id}/execute ───────────────────────────────────────────────

@pytest.mark.asyncio
async def test_execute_action_marks_executed():
    from api.routes.portfolio_actions import router as actions_router
    from fastapi import FastAPI
    app = FastAPI()
    app.include_router(actions_router, prefix="/api")

    action = MagicMock()
    action.id = "action1"
    action.portfolioId = "portfolio1"
    action.ticker = "NVDA"
    action.status = "pending"
    action.triggerCondition = "immediate"

    mock_db = MagicMock()
    mock_db.portfolioaction.find_unique = AsyncMock(return_value=action)
    mock_db.portfolio.find_unique = AsyncMock(return_value=_make_portfolio())
    mock_db.portfolioaction.update = AsyncMock()

    user = _make_user()

    with patch("api.routes.portfolio_actions.get_current_user", return_value=user), \
         patch("api.routes.portfolio_actions.get_db", return_value=mock_db):
        client = TestClient(app)
        resp = client.post("/api/actions/action1/execute")

    assert resp.status_code == 200
    assert resp.json()["status"] == "executed"
    mock_db.portfolioaction.update.assert_called_once()


@pytest.mark.asyncio
async def test_execute_non_immediate_action_returns_400():
    from api.routes.portfolio_actions import router as actions_router
    from fastapi import FastAPI
    app = FastAPI()
    app.include_router(actions_router, prefix="/api")

    action = MagicMock()
    action.id = "action1"
    action.portfolioId = "portfolio1"
    action.status = "pending"
    action.triggerCondition = "price_above"  # not immediate

    mock_db = MagicMock()
    mock_db.portfolioaction.find_unique = AsyncMock(return_value=action)
    mock_db.portfolio.find_unique = AsyncMock(return_value=_make_portfolio())

    user = _make_user()

    with patch("api.routes.portfolio_actions.get_current_user", return_value=user), \
         patch("api.routes.portfolio_actions.get_db", return_value=mock_db):
        client = TestClient(app)
        resp = client.post("/api/actions/action1/execute")

    assert resp.status_code == 400


# ── POST /actions/{id}/cancel ────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_cancel_action_cascades_to_children():
    from api.routes.portfolio_actions import router as actions_router
    from fastapi import FastAPI
    app = FastAPI()
    app.include_router(actions_router, prefix="/api")

    parent_action = MagicMock()
    parent_action.id = "action1"
    parent_action.portfolioId = "portfolio1"
    parent_action.status = "pending"

    child1 = MagicMock()
    child1.id = "child1"
    child2 = MagicMock()
    child2.id = "child2"

    mock_db = MagicMock()
    mock_db.portfolioaction.find_unique = AsyncMock(return_value=parent_action)
    mock_db.portfolio.find_unique = AsyncMock(return_value=_make_portfolio())
    mock_db.portfolioaction.find_many = AsyncMock(return_value=[child1, child2])
    mock_db.portfolioaction.update_many = AsyncMock()
    mock_db.portfolioaction.update = AsyncMock()

    user = _make_user()

    with patch("api.routes.portfolio_actions.get_current_user", return_value=user), \
         patch("api.routes.portfolio_actions.get_db", return_value=mock_db):
        client = TestClient(app)
        resp = client.post("/api/actions/action1/cancel")

    assert resp.status_code == 200
    # Children cancelled via update_many
    mock_db.portfolioaction.update_many.assert_called_once()
    call_where = mock_db.portfolioaction.update_many.call_args.kwargs["where"]
    assert call_where["parentActionId"] == "action1"
```

- [ ] **Step 2: Run new tests to verify they fail**

```bash
pytest tests/test_portfolio_actions_route.py::test_execute_action_marks_executed -v
```

Expected: `ImportError: cannot import name 'router' from 'api.routes.portfolio_actions'`

- [ ] **Step 3: Create `api/routes/portfolio_actions.py`**

```python
"""
Portfolio action lifecycle endpoints.

Handles execute and cancel for conditional PortfolioAction records
(the signal-driven ladder plans created by the rebalance engine).
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException

from api.dependencies import get_current_user
from api.lib.db import get_db
from api.models.auth import User

logger = logging.getLogger(__name__)

router = APIRouter()


async def _verify_action_ownership(db, action_id: str, user_id: str):
    """Fetch action and verify it belongs to the user's portfolio. Raises 404 if not."""
    action = await db.portfolioaction.find_unique(where={"id": action_id})
    if not action:
        raise HTTPException(status_code=404, detail="Action not found")

    portfolio = await db.portfolio.find_unique(where={"id": action.portfolioId})
    if not portfolio or portfolio.userId != user_id:
        raise HTTPException(status_code=404, detail="Action not found")

    return action


@router.post("/actions/{action_id}/execute")
async def execute_action(
    action_id: str,
    user: User = Depends(get_current_user),
):
    """
    Mark an action as executed.

    Only actions with triggerCondition='immediate' can be manually executed.
    Price-triggered actions are marked executed when the trigger fires.
    """
    db = await get_db()
    action = await _verify_action_ownership(db, action_id, user.id)

    if action.status != "pending":
        raise HTTPException(status_code=400, detail=f"Action already {action.status}")

    if action.triggerCondition not in ("immediate", None):
        raise HTTPException(
            status_code=400,
            detail="Only immediate actions can be manually executed. Price-triggered actions execute when the trigger fires.",
        )

    now = datetime.now(timezone.utc)
    await db.portfolioaction.update(
        where={"id": action_id},
        data={"status": "executed", "executedAt": now},
    )

    return {"action_id": action_id, "status": "executed", "executed_at": now.isoformat()}


@router.post("/actions/{action_id}/cancel")
async def cancel_action(
    action_id: str,
    user: User = Depends(get_current_user),
):
    """
    Cancel an action and all its children.

    Cascades to child steps (actions with parentActionId == action_id).
    """
    db = await get_db()
    action = await _verify_action_ownership(db, action_id, user.id)

    if action.status not in ("pending",):
        raise HTTPException(status_code=400, detail=f"Cannot cancel action with status '{action.status}'")

    # Cancel children first
    await db.portfolioaction.update_many(
        where={"parentActionId": action_id, "status": "pending"},
        data={"status": "cancelled"},
    )

    # Cancel the parent
    await db.portfolioaction.update(
        where={"id": action_id},
        data={"status": "cancelled"},
    )

    return {"action_id": action_id, "status": "cancelled"}
```

- [ ] **Step 4: Register in `api/index.py`**

Find the existing portfolio route registration (around line 72) and add after it:

```python
from api.routes import portfolio_actions as portfolio_actions_route
```

And after the portfolio router include:

```python
app.include_router(portfolio_actions_route.router, prefix="/api", tags=["Portfolio Actions"])
```

- [ ] **Step 5: Run all tests to verify they pass**

```bash
pytest tests/test_portfolio_actions_route.py -v
```

Expected: all tests PASS.

- [ ] **Step 6: Commit**

```bash
git add api/routes/portfolio_actions.py api/index.py
git commit -m "feat: portfolio actions route — execute/cancel with child cascade"
```

---

## Task 8: Frontend Types

**Files:**
- Modify: `frontend/types/api.ts`

- [ ] **Step 1: Replace the Portfolio-related types block in `frontend/types/api.ts`**

Find the block starting with `// ── Portfolio Engine Types` (around line 1538) and replace through the end of `ActionFeed`:

```typescript
// ── Portfolio Engine Types (Compounder Ownership OS v3.1) ──────────────────

export interface Portfolio {
  id: string
  name: string
  mandate: 'compounder' | 'growth' | 'custom'
  positions: PortfolioPosition[]
  total_value: number
  cash_balance: number
  cash_pct: number
  position_count: number
  created_at: string
}

export interface PortfolioListResponse {
  portfolios: Portfolio[]
}

export interface PortfolioPosition {
  ticker: string
  shares: number
  cost_basis: number | null
  last_known_price: number | null
  last_price_at: string | null
  allocation_pct: number | null      // computed %, 0-100
  market_value: number | null        // shares * last_known_price
  target_weight: number              // fraction 0-1, user-set
  engine_suggested_weight: number | null
  tier_state: string
  thesis_state: 'intact' | 'monitoring' | 'broken'
  eligibility_state: 'pending' | 'eligible' | 'disqualified'
  ownership_status: 'core_compounder' | 'watch' | 'disqualified'
  entry_date: string | null
  quarters_held: number
  compounder_score: number | null
  last_drawdown: number | null
  latest_run_id: string | null
}

export type EngineActionType =
  | 'INITIATE'
  | 'ADD_TIER_20'
  | 'ADD_TIER_30'
  | 'ADD_TIER_40'
  | 'ADD_TIER_50'
  | 'TRIM_EUPHORIA'
  | 'TRIM_CAP'
  | 'EXIT_THESIS'
  | 'REPLACE'
  | 'HOLD'

export type EngineActionStatus =
  | 'pending'
  | 'executed'
  | 'ignored'
  | 'expired'
  | 'cancelled'

export type TriggerCondition =
  | 'price_above'
  | 'price_below'
  | 'catalyst_confirmed'
  | 'immediate'

export interface EngineAction {
  id: string
  ticker: string
  action_type: EngineActionType
  weight_delta: number
  reason_codes: string[]
  reason_text: string | null
  status: EngineActionStatus
  signal_snapshot: Record<string, unknown> | null
  trigger_cycle: string | null
  engine_version: string | null
  trigger_price: number | null
  trigger_condition: TriggerCondition | null
  parent_action_id: string | null
  created_at: string
  executed_at: string | null
  expires_at: string | null
}

export interface ActionFeed {
  actions: EngineAction[]
  total: number
  pending_count: number
}
```

- [ ] **Step 2: Verify TypeScript compiles**

```bash
cd frontend && npx tsc --noEmit 2>&1 | head -30
```

Expected: zero errors (or only pre-existing errors unrelated to portfolio types).

- [ ] **Step 3: Commit**

```bash
git add frontend/types/api.ts
git commit -m "feat: extend Portfolio/PortfolioPosition types for holdings rework"
```

---

## Task 9: Frontend API Client

**Files:**
- Modify: `frontend/lib/api/client.ts`

- [ ] **Step 1: Replace the `addPosition` method and add new methods**

Find the `addPosition` method (around line 427) and replace it:

```typescript
  async addPosition(
    portfolioId: string,
    ticker: string,
    shares: number,
    costBasis?: number,
    targetWeight?: number,
  ): Promise<unknown> {
    return this.request(`/api/portfolio/${portfolioId}/positions`, {
      method: 'POST',
      body: JSON.stringify({ ticker, shares, cost_basis: costBasis, target_weight: targetWeight }),
    })
  }
```

Find the `updatePosition` method and replace it:

```typescript
  async updatePosition(
    portfolioId: string,
    ticker: string,
    data: { shares?: number; cost_basis?: number; target_weight?: number },
  ): Promise<unknown> {
    return this.request(`/api/portfolio/${portfolioId}/positions/${ticker}`, {
      method: 'PATCH',
      body: JSON.stringify(data),
    })
  }
```

Add the following new methods after `getPortfolioIntelligence`:

```typescript
  async refreshPortfolioPrices(portfolioId: string): Promise<{ updated: number; skipped: number }> {
    return this.request(`/api/portfolio/${portfolioId}/refresh-prices`, { method: 'POST' })
  }

  async updateCashBalance(portfolioId: string, amount: number): Promise<{ cash_balance: number }> {
    return this.request(`/api/portfolio/${portfolioId}/cash`, {
      method: 'POST',
      body: JSON.stringify({ amount }),
    })
  }

  async rebalancePortfolio(portfolioId: string): Promise<{ actions_created: number }> {
    return this.request(`/api/portfolio/${portfolioId}/rebalance`, { method: 'POST' })
  }

  async executeAction(actionId: string): Promise<{ action_id: string; status: string }> {
    return this.request(`/api/actions/${actionId}/execute`, { method: 'POST' })
  }

  async cancelAction(actionId: string): Promise<{ action_id: string; status: string }> {
    return this.request(`/api/actions/${actionId}/cancel`, { method: 'POST' })
  }
```

- [ ] **Step 2: Verify TypeScript compiles**

```bash
cd frontend && npx tsc --noEmit 2>&1 | head -30
```

Expected: zero new errors.

- [ ] **Step 3: Commit**

```bash
git add frontend/lib/api/client.ts
git commit -m "feat: portfolio API client — shares-based add, cash, refresh-prices, action execute/cancel"
```

---

## Task 10: Frontend Hooks

**Files:**
- Modify: `frontend/lib/hooks/usePortfolio.ts`

- [ ] **Step 1: Replace the `useAddPosition` hook**

Find `useAddPosition` and replace it entirely:

```typescript
/**
 * useAddPosition — mutation to add a new position to an existing portfolio.
 * Now takes shares (not weight) as the primary input.
 */
export function useAddPosition() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({
      portfolioId,
      ticker,
      shares,
      costBasis,
      targetWeight,
    }: {
      portfolioId: string
      ticker: string
      shares: number
      costBasis?: number
      targetWeight?: number
    }) => apiClient.addPosition(portfolioId, ticker, shares, costBasis, targetWeight),
    onSuccess: (_res, { portfolioId }) => {
      queryClient.invalidateQueries({ queryKey: ['portfolio', portfolioId] })
      queryClient.invalidateQueries({ queryKey: ['portfolios'] })
    },
  })
}
```

Find `useUpdatePosition` and replace it:

```typescript
/**
 * useUpdatePosition — mutation to update a position's shares, cost basis, or target weight.
 */
export function useUpdatePosition() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({
      portfolioId,
      ticker,
      data,
    }: {
      portfolioId: string
      ticker: string
      data: { shares?: number; cost_basis?: number; target_weight?: number }
    }) => apiClient.updatePosition(portfolioId, ticker, data),
    onSuccess: (_res, { portfolioId }) => {
      queryClient.invalidateQueries({ queryKey: ['portfolio', portfolioId] })
      queryClient.invalidateQueries({ queryKey: ['portfolios'] })
    },
  })
}
```

- [ ] **Step 2: Add new hooks at the end of the file**

```typescript
/**
 * useRefreshPrices — refresh lastKnownPrice for all positions in a portfolio.
 */
export function useRefreshPrices() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ portfolioId }: { portfolioId: string }) =>
      apiClient.refreshPortfolioPrices(portfolioId),
    onSuccess: (_res, { portfolioId }) => {
      queryClient.invalidateQueries({ queryKey: ['portfolio', portfolioId] })
      queryClient.invalidateQueries({ queryKey: ['portfolios'] })
    },
  })
}

/**
 * useUpdateCash — mutation to update the cash balance for a portfolio.
 */
export function useUpdateCash() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ portfolioId, amount }: { portfolioId: string; amount: number }) =>
      apiClient.updateCashBalance(portfolioId, amount),
    onSuccess: (_res, { portfolioId }) => {
      queryClient.invalidateQueries({ queryKey: ['portfolio', portfolioId] })
      queryClient.invalidateQueries({ queryKey: ['portfolios'] })
    },
  })
}

/**
 * useRebalance — trigger signal-driven rebalance plan generation.
 */
export function useRebalance() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ portfolioId }: { portfolioId: string }) =>
      apiClient.rebalancePortfolio(portfolioId),
    onSuccess: (_res, { portfolioId }) => {
      queryClient.invalidateQueries({ queryKey: ['portfolio-actions', portfolioId] })
      queryClient.invalidateQueries({ queryKey: ['portfolio', portfolioId] })
    },
  })
}

/**
 * useExecuteAction — mark an immediate action as executed.
 */
export function useExecuteAction() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ actionId }: { actionId: string }) => apiClient.executeAction(actionId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['portfolio-actions'] })
    },
  })
}

/**
 * useCancelAction — cancel an action and its child steps.
 */
export function useCancelAction() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ actionId }: { actionId: string }) => apiClient.cancelAction(actionId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['portfolio-actions'] })
    },
  })
}
```

- [ ] **Step 3: Verify TypeScript compiles**

```bash
cd frontend && npx tsc --noEmit 2>&1 | head -30
```

Expected: zero new errors.

- [ ] **Step 4: Commit**

```bash
git add frontend/lib/hooks/usePortfolio.ts
git commit -m "feat: portfolio hooks — shares-based add, cash, refresh-prices, action execute/cancel"
```

---

## Task 11: CashCard Component

**Files:**
- Create: `frontend/components/portfolio/CashCard.tsx`

- [ ] **Step 1: Create `frontend/components/portfolio/CashCard.tsx`**

```typescript
'use client'

import { useState } from 'react'
import { DollarSign, Pencil, Check, X } from 'lucide-react'
import { useUpdateCash } from '@/lib/hooks/usePortfolio'

interface CashCardProps {
  portfolioId: string
  cashBalance: number
  cashPct: number  // 0-100
  totalValue: number
}

export function CashCard({ portfolioId, cashBalance, cashPct, totalValue }: CashCardProps) {
  const [editing, setEditing] = useState(false)
  const [amount, setAmount] = useState('')
  const [error, setError] = useState<string | null>(null)

  const updateCash = useUpdateCash()

  const handleSave = async () => {
    const parsed = parseFloat(amount)
    if (isNaN(parsed) || parsed < 0) {
      setError('Enter a valid cash amount (≥ 0)')
      return
    }
    try {
      await updateCash.mutateAsync({ portfolioId, amount: parsed })
      setEditing(false)
      setError(null)
    } catch {
      setError('Failed to update cash balance')
    }
  }

  const handleEditOpen = () => {
    setAmount(cashBalance.toFixed(2))
    setError(null)
    setEditing(true)
  }

  return (
    <div className="rounded-lg border border-border/60 bg-surface/30 px-4 py-3 flex items-center justify-between gap-4">
      <div className="flex items-center gap-2">
        <DollarSign className="h-4 w-4 text-text-tertiary flex-shrink-0" />
        <div>
          <span className="text-[10px] font-semibold uppercase tracking-wider text-text-tertiary">Cash</span>
          <div className="flex items-baseline gap-2">
            {editing ? (
              <input
                type="number"
                value={amount}
                onChange={e => setAmount(e.target.value)}
                onKeyDown={e => e.key === 'Enter' && handleSave()}
                autoFocus
                min={0}
                step={100}
                className="w-32 px-2 py-1 text-sm bg-surface border border-border rounded text-text-primary font-mono focus:outline-none focus:ring-1 focus:ring-primary"
              />
            ) : (
              <span className="text-sm font-mono font-semibold text-text-primary">
                ${cashBalance.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
              </span>
            )}
            <span className="text-xs text-text-tertiary font-mono">
              {cashPct.toFixed(1)}% of portfolio
            </span>
          </div>
          {error && <p className="text-xs text-error mt-0.5">{error}</p>}
        </div>
      </div>

      <div className="flex items-center gap-1.5">
        {editing ? (
          <>
            <button
              onClick={handleSave}
              disabled={updateCash.isPending}
              className="flex items-center gap-1 h-7 px-2.5 text-xs font-semibold rounded bg-primary text-white hover:bg-primary/90 disabled:opacity-50 transition-colors"
            >
              <Check className="h-3 w-3" />
              {updateCash.isPending ? '...' : 'Save'}
            </button>
            <button
              onClick={() => { setEditing(false); setError(null) }}
              className="h-7 px-2 text-text-tertiary hover:text-text-primary transition-colors"
            >
              <X className="h-3.5 w-3.5" />
            </button>
          </>
        ) : (
          <button
            onClick={handleEditOpen}
            className="text-text-tertiary hover:text-text-primary transition-colors"
            title="Update cash balance"
          >
            <Pencil className="h-3.5 w-3.5" />
          </button>
        )}
      </div>
    </div>
  )
}
```

- [ ] **Step 2: Verify TypeScript compiles**

```bash
cd frontend && npx tsc --noEmit 2>&1 | head -20
```

- [ ] **Step 3: Commit**

```bash
git add frontend/components/portfolio/CashCard.tsx
git commit -m "feat: CashCard component — editable cash balance with portfolio % display"
```

---

## Task 12: ActionPlanCard Component

**Files:**
- Create: `frontend/components/portfolio/ActionPlanCard.tsx`

- [ ] **Step 1: Create `frontend/components/portfolio/ActionPlanCard.tsx`**

```typescript
'use client'

import { useState } from 'react'
import { ChevronDown, ChevronRight, Zap, X, Lock } from 'lucide-react'
import { usePortfolioActions, useExecuteAction, useCancelAction } from '@/lib/hooks/usePortfolio'
import type { EngineAction } from '@/types/api'

interface ActionPlanCardProps {
  portfolioId: string
  ticker: string
}

const ACTION_LABEL: Record<string, string> = {
  TRIM_EUPHORIA: 'Trim',
  TRIM_CAP: 'Trim',
  ADD_TIER_20: 'Add',
  ADD_TIER_30: 'Add',
  ADD_TIER_40: 'Add',
  ADD_TIER_50: 'Add',
  INITIATE: 'Enter',
  EXIT_THESIS: 'Exit',
  HOLD: 'Hold',
  REPLACE: 'Replace',
}

const CONDITION_LABEL: Record<string, string> = {
  price_above: 'at price above',
  price_below: 'at price below',
  catalyst_confirmed: 'when catalyst confirmed',
  immediate: 'immediately',
}

const STATUS_COLOR: Record<string, string> = {
  pending: 'text-warning',
  triggered: 'text-primary',
  executed: 'text-success',
  cancelled: 'text-text-tertiary',
  expired: 'text-text-tertiary',
}

function ActionStep({
  action,
  isChild,
}: {
  action: EngineAction
  isChild?: boolean
}) {
  const execute = useExecuteAction()
  const cancel = useCancelAction()

  const label = ACTION_LABEL[action.action_type] ?? action.action_type
  const condLabel = action.trigger_condition ? CONDITION_LABEL[action.trigger_condition] : ''
  const pct = Math.abs(action.weight_delta * 100).toFixed(1)
  const isImmediate = action.trigger_condition === 'immediate'

  return (
    <div className={`flex items-start gap-3 py-2 ${isChild ? 'pl-4 border-l border-border/40 ml-2' : ''}`}>
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 flex-wrap">
          <span className="text-xs font-semibold text-text-primary">
            {label} {pct}%
          </span>
          {condLabel && (
            <span className="text-xs text-text-tertiary">
              {condLabel}
              {action.trigger_price !== null && (
                <span className="font-mono text-text-secondary ml-1">
                  ${action.trigger_price.toFixed(2)}
                </span>
              )}
            </span>
          )}
          <span className={`text-[10px] font-semibold uppercase ${STATUS_COLOR[action.status] ?? 'text-text-tertiary'}`}>
            {action.status}
          </span>
        </div>
        {action.reason_text && (
          <p className="text-[11px] text-text-tertiary mt-0.5 line-clamp-2">{action.reason_text}</p>
        )}
      </div>

      {action.status === 'pending' && (
        <div className="flex items-center gap-1.5 flex-shrink-0">
          {isImmediate ? (
            <button
              onClick={() => execute.mutate({ actionId: action.id })}
              disabled={execute.isPending}
              title="Execute now"
              className="flex items-center gap-1 h-6 px-2 text-[10px] font-semibold rounded bg-primary/10 text-primary hover:bg-primary/20 disabled:opacity-50 transition-colors"
            >
              <Zap className="h-3 w-3" />
              Execute
            </button>
          ) : (
            <span title="Executes when price trigger fires" className="text-text-tertiary">
              <Lock className="h-3 w-3" />
            </span>
          )}
          <button
            onClick={() => cancel.mutate({ actionId: action.id })}
            disabled={cancel.isPending}
            title="Cancel this step and children"
            className="text-text-tertiary hover:text-error transition-colors"
          >
            <X className="h-3.5 w-3.5" />
          </button>
        </div>
      )}
    </div>
  )
}

export function ActionPlanCard({ portfolioId, ticker }: ActionPlanCardProps) {
  const [expanded, setExpanded] = useState(false)
  const { data: feed } = usePortfolioActions(portfolioId, 'pending')

  const tickerActions = (feed?.actions ?? []).filter(a => a.ticker === ticker)

  if (tickerActions.length === 0) return null

  // Group: parents are actions with no parent_action_id
  const parents = tickerActions.filter(a => a.parent_action_id === null)
  const childrenOf = (parentId: string): EngineAction[] =>
    tickerActions.filter(a => a.parent_action_id === parentId)

  return (
    <div className="border-t border-border/40 bg-surface/20">
      <button
        onClick={() => setExpanded(v => !v)}
        className="w-full flex items-center gap-2 px-4 py-2 text-left hover:bg-surface/40 transition-colors"
      >
        {expanded ? <ChevronDown className="h-3.5 w-3.5 text-text-tertiary" /> : <ChevronRight className="h-3.5 w-3.5 text-text-tertiary" />}
        <span className="text-[11px] font-semibold text-text-secondary">
          Action Plan — {tickerActions.length} step{tickerActions.length !== 1 ? 's' : ''} pending
        </span>
      </button>

      {expanded && (
        <div className="px-4 pb-3 space-y-0.5">
          {parents.map(parent => (
            <div key={parent.id}>
              <ActionStep action={parent} />
              {childrenOf(parent.id).map(child => (
                <ActionStep key={child.id} action={child} isChild />
              ))}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
```

- [ ] **Step 2: Verify TypeScript compiles**

```bash
cd frontend && npx tsc --noEmit 2>&1 | head -20
```

- [ ] **Step 3: Commit**

```bash
git add frontend/components/portfolio/ActionPlanCard.tsx
git commit -m "feat: ActionPlanCard — expandable conditional action ladder with execute/cancel"
```

---

## Task 13: HoldingsTab Rework

**Files:**
- Modify: `frontend/components/portfolio/HoldingsTab.tsx`

- [ ] **Step 1: Rewrite `frontend/components/portfolio/HoldingsTab.tsx`**

```typescript
'use client'

import { useState } from 'react'
import Link from 'next/link'
import { Pencil, Trash2, Check, X, Plus, ChevronDown, RefreshCw, AlertTriangle } from 'lucide-react'
import {
  usePortfolioDetail,
  useAddPosition,
  useUpdatePosition,
  useRemovePosition,
  useRefreshPrices,
  useRebalance,
} from '@/lib/hooks/usePortfolio'
import { CashCard } from './CashCard'
import { ActionPlanCard } from './ActionPlanCard'
import type { PortfolioPosition } from '@/types/api'

const STALE_PRICE_DAYS = 7

function isPriceStale(lastPriceAt: string | null): boolean {
  if (!lastPriceAt) return false
  const diffMs = Date.now() - new Date(lastPriceAt).getTime()
  return diffMs > STALE_PRICE_DAYS * 24 * 60 * 60 * 1000
}

function formatAllocation(pct: number | null): string {
  if (pct === null) return '—'
  return `${pct.toFixed(1)}%`
}

function formatPrice(price: number | null): string {
  if (price === null) return '—'
  return `$${price.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`
}

function formatValue(value: number | null): string {
  if (value === null) return '—'
  if (value >= 1_000_000) return `$${(value / 1_000_000).toFixed(2)}M`
  if (value >= 1_000) return `$${(value / 1_000).toFixed(1)}K`
  return `$${value.toFixed(2)}`
}

/** Delta between current allocation and target, formatted for display. */
function AllocationDelta({ allocationPct, targetWeight }: { allocationPct: number | null; targetWeight: number }) {
  if (allocationPct === null) return <span className="text-text-tertiary">—</span>
  const targetPct = targetWeight * 100
  const delta = allocationPct - targetPct
  if (Math.abs(delta) < 0.5) return <span className="text-text-tertiary">on target</span>
  const color = delta > 2 ? 'text-warning' : delta < -2 ? 'text-primary' : 'text-text-secondary'
  return (
    <span className={`font-mono ${color}`}>
      {delta > 0 ? '+' : ''}{delta.toFixed(1)}%
    </span>
  )
}

export function HoldingsTab({ portfolioId }: { portfolioId: string }) {
  const { data: portfolio, isLoading } = usePortfolioDetail(portfolioId)
  const [addingPosition, setAddingPosition] = useState(false)

  const refreshPrices = useRefreshPrices()
  const rebalance = useRebalance()

  if (isLoading) {
    return <div className="text-sm text-text-tertiary text-center py-8">Loading holdings...</div>
  }

  if (!portfolio) return null

  const allPositions = portfolio.positions
  const holdings = allPositions.filter(p => p.shares > 0)
  const watchlist = allPositions.filter(p => p.shares === 0)
  const sorted = [...holdings].sort((a, b) => (b.allocation_pct ?? 0) - (a.allocation_pct ?? 0))

  return (
    <div className="space-y-3">
      {/* Cash card */}
      <CashCard
        portfolioId={portfolioId}
        cashBalance={portfolio.cash_balance}
        cashPct={portfolio.cash_pct}
        totalValue={portfolio.total_value}
      />

      {/* Summary + controls */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-1.5 text-xs text-text-tertiary">
        <span>
          {holdings.length} holding{holdings.length !== 1 ? 's' : ''}
          {watchlist.length > 0 && ` · ${watchlist.length} watching`}
          <span className="ml-2 font-mono font-semibold text-text-primary">
            {formatValue(portfolio.total_value)} total
          </span>
        </span>
        <div className="flex items-center gap-2 self-start sm:self-auto">
          <button
            onClick={() => refreshPrices.mutate({ portfolioId })}
            disabled={refreshPrices.isPending}
            className="flex items-center gap-1 text-text-tertiary hover:text-text-primary disabled:opacity-50 transition-colors"
            title="Refresh prices from latest analysis"
          >
            <RefreshCw className={`h-3.5 w-3.5 ${refreshPrices.isPending ? 'animate-spin' : ''}`} />
            <span className="hidden sm:inline">Refresh prices</span>
          </button>
          <button
            onClick={() => setAddingPosition(v => !v)}
            className="flex items-center gap-1 text-primary hover:text-primary/80 transition-colors font-semibold"
          >
            <Plus className="h-3 w-3" />
            Add
            <ChevronDown className={`h-3 w-3 transition-transform ${addingPosition ? 'rotate-180' : ''}`} />
          </button>
        </div>
      </div>

      {/* Add position form */}
      {addingPosition && (
        <AddPositionForm
          portfolioId={portfolioId}
          existingTickers={allPositions.map(p => p.ticker)}
          onDone={() => setAddingPosition(false)}
        />
      )}

      {/* Holdings grid */}
      {sorted.length > 0 ? (
        <div className="grid gap-2">
          {sorted.map(pos => (
            <PositionRow key={pos.ticker} portfolioId={portfolioId} position={pos} />
          ))}
        </div>
      ) : (
        !addingPosition && (
          <div className="text-center py-8 text-sm text-text-tertiary">
            No holdings yet — click Add above to get started.
          </div>
        )
      )}

      {/* Watchlist section */}
      {watchlist.length > 0 && (
        <div className="space-y-2">
          <p className="text-[10px] font-semibold uppercase tracking-wider text-text-tertiary">
            Watchlist ({watchlist.length})
          </p>
          <div className="grid gap-2">
            {watchlist.map(pos => (
              <PositionRow key={pos.ticker} portfolioId={portfolioId} position={pos} />
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

// ── Add Position Form ─────────────────────────────────────────────────────────

function AddPositionForm({
  portfolioId,
  existingTickers,
  onDone,
}: {
  portfolioId: string
  existingTickers: string[]
  onDone: () => void
}) {
  const [ticker, setTicker] = useState('')
  const [shares, setShares] = useState('')
  const [costBasis, setCostBasis] = useState('')
  const [targetPct, setTargetPct] = useState('5')
  const [error, setError] = useState<string | null>(null)

  const addPosition = useAddPosition()

  const handleAdd = async () => {
    const t = ticker.trim().toUpperCase()
    if (!t) { setError('Ticker is required'); return }
    if (existingTickers.includes(t)) { setError(`${t} is already in your portfolio`); return }

    const sh = parseFloat(shares)
    if (isNaN(sh) || sh < 0) { setError('Shares must be 0 or more'); return }

    const cb = costBasis ? parseFloat(costBasis) : undefined
    if (costBasis && isNaN(cb!)) { setError('Cost basis must be a valid number'); return }

    const tp = parseFloat(targetPct)
    if (isNaN(tp) || tp < 0 || tp > 100) { setError('Target % must be between 0 and 100'); return }

    try {
      await addPosition.mutateAsync({
        portfolioId,
        ticker: t,
        shares: sh,
        costBasis: cb,
        targetWeight: tp / 100,
      })
      setTicker(''); setShares(''); setCostBasis(''); setTargetPct('5')
      setError(null)
      onDone()
    } catch (err: unknown) {
      setError((err as { message?: string }).message ?? 'Failed to add position')
    }
  }

  return (
    <div className="rounded-lg border border-primary/30 bg-surface/60 px-4 py-3 space-y-3">
      <div className="flex flex-wrap items-end gap-3">
        <div className="flex-1 min-w-[100px]">
          <label className="text-[10px] font-semibold uppercase tracking-wider text-text-tertiary">Ticker</label>
          <input type="text" value={ticker} onChange={e => setTicker(e.target.value.toUpperCase())}
            onKeyDown={e => e.key === 'Enter' && handleAdd()} placeholder="AAPL" autoFocus
            className="w-full mt-1 px-3 py-1.5 text-sm bg-surface border border-border rounded-lg text-text-primary placeholder:text-text-tertiary font-mono focus:outline-none focus:ring-1 focus:ring-primary" />
        </div>
        <div className="w-24">
          <label className="text-[10px] font-semibold uppercase tracking-wider text-text-tertiary">Shares</label>
          <input type="number" value={shares} onChange={e => setShares(e.target.value)} min={0} step={1} placeholder="0"
            className="w-full mt-1 px-3 py-1.5 text-sm bg-surface border border-border rounded-lg text-text-primary font-mono focus:outline-none focus:ring-1 focus:ring-primary" />
        </div>
        <div className="w-28">
          <label className="text-[10px] font-semibold uppercase tracking-wider text-text-tertiary">Cost Basis</label>
          <input type="text" value={costBasis} onChange={e => setCostBasis(e.target.value)} placeholder="Optional"
            className="w-full mt-1 px-3 py-1.5 text-sm bg-surface border border-border rounded-lg text-text-primary placeholder:text-text-tertiary font-mono focus:outline-none focus:ring-1 focus:ring-primary" />
        </div>
        <div className="w-24">
          <label className="text-[10px] font-semibold uppercase tracking-wider text-text-tertiary">Target %</label>
          <input type="number" value={targetPct} onChange={e => setTargetPct(e.target.value)} min={0} max={100} step={0.5}
            className="w-full mt-1 px-3 py-1.5 text-sm bg-surface border border-border rounded-lg text-text-primary font-mono focus:outline-none focus:ring-1 focus:ring-primary" />
        </div>
        <div className="flex items-center gap-2">
          <button onClick={handleAdd} disabled={addPosition.isPending}
            className="flex items-center gap-1 h-[34px] px-3 text-xs font-semibold rounded-lg bg-primary text-white hover:bg-primary/90 disabled:opacity-50 transition-colors">
            <Check className="h-3.5 w-3.5" />
            {addPosition.isPending ? 'Adding...' : 'Add'}
          </button>
          <button onClick={onDone} className="h-[34px] px-2 text-text-tertiary hover:text-text-primary transition-colors">
            <X className="h-3.5 w-3.5" />
          </button>
        </div>
      </div>
      {error && <p className="text-xs text-error">{error}</p>}
    </div>
  )
}

// ── Position Row ──────────────────────────────────────────────────────────────

function PositionRow({ portfolioId, position }: { portfolioId: string; position: PortfolioPosition }) {
  const [editing, setEditing] = useState(false)
  const [confirmingDelete, setConfirmingDelete] = useState(false)
  const [shares, setShares] = useState('')
  const [costBasis, setCostBasis] = useState('')
  const [targetPct, setTargetPct] = useState('')
  const [error, setError] = useState<string | null>(null)

  const updatePosition = useUpdatePosition()
  const removePosition = useRemovePosition()

  const stale = isPriceStale(position.last_price_at)
  const hasNoPrice = position.last_known_price === null

  const handleEditOpen = () => {
    setShares(position.shares.toString())
    setCostBasis(position.cost_basis?.toString() ?? '')
    setTargetPct((position.target_weight * 100).toFixed(1))
    setError(null)
    setConfirmingDelete(false)
    setEditing(true)
  }

  const handleSave = async () => {
    const sh = parseFloat(shares)
    if (isNaN(sh) || sh < 0) { setError('Shares must be 0 or more'); return }

    const data: { shares?: number; cost_basis?: number; target_weight?: number } = { shares: sh }
    if (costBasis !== '') {
      const parsed = parseFloat(costBasis)
      if (!isNaN(parsed)) data.cost_basis = parsed
    }
    const tp = parseFloat(targetPct)
    if (!isNaN(tp) && tp >= 0 && tp <= 100) data.target_weight = tp / 100

    try {
      await updatePosition.mutateAsync({ portfolioId, ticker: position.ticker, data })
      setEditing(false); setError(null)
    } catch (err: unknown) {
      setError((err as { message?: string }).message ?? 'Failed to save')
    }
  }

  const handleRemove = async () => {
    try {
      await removePosition.mutateAsync({ portfolioId, ticker: position.ticker })
    } catch (err: unknown) {
      setConfirmingDelete(false)
      setError((err as { message?: string }).message ?? 'Failed to remove')
    }
  }

  const ownershipColor = {
    core_compounder: 'text-success',
    watch: 'text-warning',
    disqualified: 'text-error',
  }[position.ownership_status] ?? 'text-text-tertiary'

  const ownershipLabel = {
    core_compounder: 'Core',
    watch: 'Watch',
    disqualified: 'DQ',
  }[position.ownership_status] ?? position.ownership_status

  const thesisColor = {
    intact: 'text-success',
    monitoring: 'text-warning',
    broken: 'text-error',
  }[position.thesis_state] ?? 'text-text-tertiary'

  return (
    <div className="rounded-lg border border-border/60 bg-surface/30 overflow-hidden">
      {/* Main row */}
      <div className="flex items-center justify-between px-4 py-3">
        <div className="flex items-center gap-3 min-w-0 flex-wrap">
          <div className="flex items-center gap-2">
            <span className="text-sm font-bold font-mono text-text-primary">{position.ticker}</span>
            <span className={`text-[9px] font-semibold uppercase tracking-wide ${ownershipColor}`}>
              {ownershipLabel}
            </span>
          </div>

          {/* Allocation (computed) */}
          <div className="flex items-center gap-1">
            {hasNoPrice ? (
              <span className="text-xs text-text-tertiary font-mono">—</span>
            ) : (
              <>
                <span className="text-xs font-mono font-semibold text-text-primary">
                  {formatAllocation(position.allocation_pct)}
                </span>
                {stale && (
                  <span title="Price data is stale (>7 days)" className="text-warning">
                    <AlertTriangle className="h-3 w-3" />
                  </span>
                )}
              </>
            )}
          </div>

          {/* Target vs actual delta */}
          <div className="hidden sm:flex items-center gap-1 text-xs text-text-tertiary">
            <span>vs {(position.target_weight * 100).toFixed(1)}% target</span>
            <AllocationDelta allocationPct={position.allocation_pct} targetWeight={position.target_weight} />
          </div>

          {/* Market value */}
          {!hasNoPrice && (
            <span className="hidden md:inline text-xs font-mono text-text-tertiary">
              {formatValue(position.market_value)}
            </span>
          )}

          {/* No price CTA */}
          {hasNoPrice && (
            <span className="text-[10px] text-text-tertiary">No analysis — run a report to get price</span>
          )}
        </div>

        <div className="flex items-center gap-2 sm:gap-3">
          {position.tier_state !== 'none' && (
            <span className="hidden sm:inline-flex text-[9px] font-mono bg-warning/10 text-warning px-1.5 py-0.5 rounded">
              {position.tier_state.toUpperCase()}
            </span>
          )}
          <span className={`text-[9px] font-semibold uppercase ${thesisColor}`}>
            {position.thesis_state}
          </span>
          {position.latest_run_id && !editing && !confirmingDelete && (
            <Link href={`/results/${position.latest_run_id}`} className="text-[10px] text-primary hover:underline">
              Research
            </Link>
          )}

          {confirmingDelete && !editing && (
            <div className="flex items-center gap-2">
              <span className="text-[10px] text-error font-semibold">Remove?</span>
              <button onClick={handleRemove} disabled={removePosition.isPending}
                className="text-[10px] font-semibold text-error hover:text-error/80 disabled:opacity-50">
                {removePosition.isPending ? '...' : 'Yes'}
              </button>
              <button onClick={() => setConfirmingDelete(false)}
                className="text-[10px] font-semibold text-text-tertiary hover:text-text-secondary">No</button>
            </div>
          )}

          <button onClick={editing ? () => setEditing(false) : handleEditOpen}
            className="text-text-tertiary hover:text-text-primary transition-colors"
            title={editing ? 'Cancel edit' : 'Edit position'}>
            {editing ? <X className="h-3.5 w-3.5" /> : <Pencil className="h-3.5 w-3.5" />}
          </button>

          {!editing && (
            <button onClick={() => setConfirmingDelete(v => !v)}
              className={`transition-colors ${confirmingDelete ? 'text-error' : 'text-text-tertiary hover:text-error'}`}
              title="Remove position">
              <Trash2 className="h-3.5 w-3.5" />
            </button>
          )}
        </div>
      </div>

      {/* Inline edit form */}
      {editing && (
        <div className="border-t border-border/40 px-4 py-3 bg-surface/60 space-y-3">
          <div className="flex flex-wrap items-end gap-3">
            <div className="w-24">
              <label className="text-[10px] font-semibold uppercase tracking-wider text-text-tertiary">Shares</label>
              <input type="number" value={shares} onChange={e => setShares(e.target.value)} min={0} step={1} autoFocus
                className="w-full mt-1 px-3 py-1.5 text-sm bg-surface border border-border rounded-lg text-text-primary font-mono focus:outline-none focus:ring-1 focus:ring-primary" />
            </div>
            <div className="w-28">
              <label className="text-[10px] font-semibold uppercase tracking-wider text-text-tertiary">Cost Basis</label>
              <input type="text" value={costBasis} onChange={e => setCostBasis(e.target.value)} placeholder="Optional"
                className="w-full mt-1 px-3 py-1.5 text-sm bg-surface border border-border rounded-lg text-text-primary placeholder:text-text-tertiary font-mono focus:outline-none focus:ring-1 focus:ring-primary" />
            </div>
            <div className="w-24">
              <label className="text-[10px] font-semibold uppercase tracking-wider text-text-tertiary">Target %</label>
              <input type="number" value={targetPct} onChange={e => setTargetPct(e.target.value)} min={0} max={100} step={0.5}
                className="w-full mt-1 px-3 py-1.5 text-sm bg-surface border border-border rounded-lg text-text-primary font-mono focus:outline-none focus:ring-1 focus:ring-primary" />
            </div>
            <button onClick={handleSave} disabled={updatePosition.isPending}
              className="flex items-center gap-1 h-[34px] px-3 text-xs font-semibold rounded-lg bg-primary text-white hover:bg-primary/90 disabled:opacity-50 transition-colors">
              <Check className="h-3.5 w-3.5" />
              {updatePosition.isPending ? 'Saving...' : 'Save'}
            </button>
          </div>
          {error && <p className="text-xs text-error">{error}</p>}
        </div>
      )}

      {/* Action plan ladder (expandable) */}
      <ActionPlanCard portfolioId={portfolioId} ticker={position.ticker} />

      {/* Remove error */}
      {!editing && error && (
        <div className="border-t border-border/40 px-4 py-2 bg-surface/60">
          <p className="text-xs text-error">{error}</p>
        </div>
      )}
    </div>
  )
}
```

- [ ] **Step 2: Verify TypeScript compiles with zero new errors**

```bash
cd frontend && npx tsc --noEmit 2>&1 | head -30
```

- [ ] **Step 3: Run all backend tests to catch any regressions**

```bash
pytest tests/ -v -x 2>&1 | tail -20
```

Expected: all tests pass (no regressions).

- [ ] **Step 4: Commit**

```bash
git add frontend/components/portfolio/HoldingsTab.tsx
git commit -m "feat: HoldingsTab rework — computed allocation %, shares input, cash card, action plan ladders"
```

---

## Final Verification

- [ ] **Run full backend test suite**

```bash
pytest tests/ -v 2>&1 | tail -30
```

Expected: all tests pass, zero failures.

- [ ] **Run TypeScript check**

```bash
cd frontend && npx tsc --noEmit
```

Expected: zero new type errors.

- [ ] **Smoke check: import the new modules**

```bash
cd /path/to/research-swarm && python -c "
from api.services.allocation import compute_portfolio_breakdown
from api.services.pricing import get_latest_price
from api.services.portfolio_engine import generate_action_plan, classify_posture
print('All imports OK')
"
```

Expected: `All imports OK`
