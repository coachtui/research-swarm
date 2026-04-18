# Portfolio Holdings Rework — Phase 2 Design

**Date:** 2026-04-18
**Status:** Approved, ready for implementation plan
**Depends on:** Phase 1 complete (WeeklySignal pipeline, weekly_batch)

---

## Goal

Rework the portfolio holdings section so that:

1. Allocation % is computed automatically from `shares × lastKnownPrice / totalPortfolioValue` — never manually entered
2. Cash is a first-class denominator in portfolio value
3. Prices are sourced from the latest `StockResult` with a manual refresh button; no live streaming
4. The engine proposes conditional, multi-step action plans (trim ladders, add ladders, exit plans) derived from the latest analysis report signals — not mechanical weight-delta rebalancing
5. Target allocation is engine-suggested (from compounder score + conviction) but user-overridable; both values are stored

---

## Architecture & Data Flow

```
User adds position
  └─ enters: ticker, shares, costBasis (optional), entryDate (optional)
  └─ server fetches latest StockResult.currentPrice → stores as lastKnownPrice, lastPriceAt
  └─ engine computes engineSuggestedWeight from compounder score + conviction
  └─ targetWeight defaults to engineSuggestedWeight (user can override inline)

User views holdings
  └─ frontend computes live allocation per row:
       allocation% = (shares × lastKnownPrice) / (Σ positions + cashBalance)
  └─ "Refresh prices" button → backend pulls latest StockResult per ticker
       → updates lastKnownPrice, lastPriceAt

Weekly batch / manual "Rebalance" button
  └─ for each position:
       ├─ load latest StockResult (signals, catalysts, technicals, targets)
       ├─ compute currentAllocation (live)
       ├─ classify posture (over_target_bearish | over_target_bullish |
       │    below_target_bullish | thesis_broken | watch_only)
       └─ emit linked PortfolioAction chain (parent + children with triggerPrice)

Price check (manual refresh or future cron)
  └─ for each pending action with triggerPrice:
       └─ if condition met → mark status='triggered', surface to user
```

---

## Schema Changes

### `Portfolio` — add cash
```prisma
model Portfolio {
  // existing fields unchanged
  cashBalance      Float     @default(0)    @map("cash_balance")
  cashUpdatedAt    DateTime? @map("cash_updated_at")
}
```

### `Position` — real holdings, real prices, target split

Add fields:
```prisma
lastKnownPrice         Float?    @map("last_known_price")
lastPriceAt            DateTime? @map("last_price_at")
targetWeight           Float     @default(0) @map("target_weight")
engineSuggestedWeight  Float?    @map("engine_suggested_weight")
```

- `shares` is now required on position create (was optional)
- `currentWeight` is **deprecated** — removed in a follow-up migration (Phase 2b) after backfill

### `PortfolioAction` — conditional, linked plans

Add fields:
```prisma
triggerPrice      Float?   @map("trigger_price")
triggerCondition  String?  @map("trigger_condition")
  // values: 'price_above' | 'price_below' | 'catalyst_confirmed' | 'immediate'
parentActionId    String?  @map("parent_action_id")
parent            PortfolioAction?  @relation("ActionChain", fields: [parentActionId], references: [id])
children          PortfolioAction[] @relation("ActionChain")
status            String   @default("pending")
  // values: 'pending' | 'triggered' | 'executed' | 'expired' | 'cancelled'
expiresAt         DateTime? @map("expires_at")
```

### Migration path

**Phase 2a (this spec — additive only):**
1. Add `cashBalance`, `cashUpdatedAt` to `Portfolio`
2. Add `lastKnownPrice`, `lastPriceAt`, `targetWeight`, `engineSuggestedWeight` to `Position`
3. Add action chain fields to `PortfolioAction`
4. Backfill: positions with `currentWeight > 0` and `shares = null` → `ownershipStatus = 'watch'`, `shares = 0`, `targetWeight = currentWeight`
5. `currentWeight` remains in schema (ignored by new code paths)

**Phase 2b (follow-up, separate PR):**
- Drop `currentWeight` from schema after all clients are off it

---

## Backend Components

### `api/services/pricing.py` (new)

- `get_latest_price(ticker) -> tuple[float | None, datetime | None]` — reads `StockResult.currentPrice` for most recent run
- `refresh_position_prices(portfolio_id: str) -> None` — loops positions, updates `lastKnownPrice` / `lastPriceAt`
- `refresh_ticker_price(ticker: str, force_analyze: bool = False)` — if `force_analyze`, enqueues `analyze_stock` Inngest job and returns job ID; otherwise just pulls latest cached price

### `api/services/allocation.py` (new)

Pure functions, no DB reads:
- `compute_portfolio_total(positions: list[Position], cash_balance: float) -> float`
- `compute_allocation(position: Position, total_value: float) -> float` — `(shares × lastKnownPrice) / total_value`; returns 0.0 if `lastKnownPrice` is None or `total_value == 0`
- `compute_portfolio_breakdown(portfolio: Portfolio) -> PortfolioBreakdown` — returns total, cash_pct, per-position allocation_pct and market_value

`PortfolioBreakdown` is a Pydantic model defined in `api/models/portfolio.py` alongside existing portfolio models.

### `api/services/portfolio_engine.py` (modified)

Replace mechanical `weightDelta` action generation:
- New `generate_action_plan(position, stock_result, current_alloc, target_alloc) -> list[PortfolioAction]`
- Dispatch by posture:
  - `over_target_bearish` → trim ladder (2–3 steps above current price, descending size)
  - `over_target_bullish` → hold + trailing trim triggers at upper targets from report
  - `below_target_bullish` → add ladder on pullbacks keyed to support levels
  - `thesis_broken` → exit plan (full trim at market or on bounce)
  - `watch_only` (shares = 0) → entry ladder using report's fair value gap levels
- Each step gets `triggerPrice`, `triggerCondition`, `parentActionId`, `reasonText` referencing specific signals from the StockResult report
- Engine is called per position by both weekly batch and the manual rebalance endpoint

### `api/routes/portfolio.py` (modified)

- `POST /portfolio/positions` — requires `shares`; auto-populates `lastKnownPrice` from `StockResult`; computes `engineSuggestedWeight`; sets `targetWeight = engineSuggestedWeight`
- `PATCH /portfolio/positions/{id}` — allow updating `shares`, `targetWeight`, `costBasis`
- `GET /portfolio/{id}` — response includes computed `allocationPct`, `marketValue` per position, `totalValue`, `cashPct`
- `POST /portfolio/{id}/refresh-prices` — triggers `refresh_position_prices`
- `POST /portfolio/{id}/cash` — body `{ amount: float }`; updates `cashBalance`, `cashUpdatedAt`
- `POST /portfolio/{id}/rebalance` — runs engine on-demand per position; returns new action plan chains

### `api/routes/portfolio_actions.py` (new)

- `GET /portfolio/{id}/actions?status=pending` — returns action chains grouped by parent
- `POST /actions/{id}/execute` — marks step `status='executed'`; logs fill
- `POST /actions/{id}/cancel` — marks step and all children `status='cancelled'`

---

## Frontend Components

### `HoldingsTab.tsx` (modified)

- Remove manual weight input (`currentWeight` / `w / 100` conversion)
- Add `shares` field on position create form
- `targetWeight` shown as editable number/slider, defaulting to `engineSuggestedWeight`
- `allocationPct` is readonly, computed from API response
- New columns: current value ($), target %, delta from target (colored indicator)
- "Refresh prices" button top-right of table
- Amber stale-price badge on rows where `lastPriceAt` > 7 days old
- Watch-list positions (shares = 0) rendered in a separate collapsible section below holdings

### `CashCard.tsx` (new)

Small card above holdings table: cash balance ($), cash % of portfolio, "Update" button.

### `ActionPlanCard.tsx` (new)

Per-position card (expandable from holdings row) showing the pending plan as a visual ladder:
- Each step: action type, size (% of position), trigger condition, price level, reason snippet from report
- Status badge per step: pending / triggered / executed / cancelled
- Execute button (enabled only on `triggerCondition = 'immediate'`)
- Cancel button per step (cascades to children)

### `usePortfolio.ts` (modified)

- `useRefreshPrices(portfolioId)` — mutation calling `POST /portfolio/{id}/refresh-prices`
- `useExecuteAction(actionId)` — mutation calling `POST /actions/{id}/execute`
- `useCancelAction(actionId)` — mutation calling `POST /actions/{id}/cancel`
- `useCashBalance(portfolioId)` — mutation calling `POST /portfolio/{id}/cash`
- Existing `usePortfolio` query response extended with computed allocations from backend

---

## Error Handling

| Scenario | Behavior |
|---|---|
| `StockResult` has no price for ticker | Position saves with `lastKnownPrice = null`; frontend shows "—" for allocation%; shows "Run analysis" CTA |
| `lastPriceAt` > 7 days | Amber warning badge on that row; engine still runs but annotates plan's `reasonText` with price date |
| All positions null price + cash = 0 | `compute_portfolio_total` returns 0; `compute_allocation` returns 0.0 (no division by zero) |
| Engine produces no plan | Emits single action: `actionType='review'`, `triggerCondition='immediate'`, `reasonText='No recent analysis available — review manually'` |
| Parent action cancelled | API cancels all children in the same request (application-layer cascade, not DB cascade) |
| Position with `ownershipStatus='watch'` | Excluded from allocation math; shown in Watchlist section; engine generates entry ladders |

---

## Testing Strategy

### Backend (TDD)

- `tests/test_allocation.py` — unit tests for all three allocation functions: zero cash, zero shares, null price, all-null portfolio
- `tests/test_portfolio_engine.py` — unit tests for `generate_action_plan` using mocked StockResult fixtures per posture: over_target_bearish, over_target_bullish, below_target_bullish, thesis_broken, watch_only
- `tests/test_portfolio_route.py` — integration tests: position create with auto-price lookup, refresh-prices endpoint, rebalance endpoint, cash update, action cancel cascade
- `tests/test_pricing.py` — unit tests for `get_latest_price`: no StockResult, stale price, fresh price

### Frontend

- `HoldingsTab` renders "—" when `lastKnownPrice` is null
- `HoldingsTab` shows amber badge when `lastPriceAt` > 7 days
- `ActionPlanCard` renders correct ladder order; Execute button disabled on non-immediate steps
- `usePortfolio` hook returns computed allocations from API response

### Migration

- Seeded positions with legacy `currentWeight` set and `shares = null` → after backfill: `ownershipStatus = 'watch'`, `shares = 0`, `targetWeight = legacy currentWeight`

---

## Out of Scope for Phase 2

- Live price streaming / websocket price feed
- Automated trigger execution (system executes trades) — triggers surface to user only
- Brokerage API integration
- Performance tracking / P&L history (Phase 3)
- `currentWeight` drop from schema (Phase 2b, separate migration PR)
