# Monday Batch Audit UI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give the admin dashboard a "Monday Batch" sub-tab next to the existing "Sunday Outlook" tab, showing the weekly-batch funnel's stage counts (screened → advanced → escalated → swarm) and the resulting per-ticker rows for any past run.

**Architecture:** A new `WeeklyBatchRun` Prisma model stores one funnel-summary row per Monday run, written by a new Inngest step in `weekly_batch.py`. Two admin-gated FastAPI endpoints expose it (list of past runs, detail-with-joined-signals for one run). A new React component renders it, following `MarketOutlookPanel.tsx`'s existing patterns exactly, wired into `admin/page.tsx` as a nested tab.

**Tech Stack:** FastAPI + Pydantic, Prisma (`prisma-client-py`), Inngest Python SDK, Next.js App Router, React Query, Tailwind (existing `Card`/`Badge`/`Skeleton` primitives).

**Spec:** `docs/superpowers/specs/2026-07-12-monday-batch-audit-ui-design.md`

## Global Constraints

- Prisma migrations: hand-write SQL in `db/migrations/<timestamp>_<name>/migration.sql` and run `python3 -m prisma validate --schema db/schema.prisma && python3 -m prisma generate --schema db/schema.prisma`. **Never** run `prisma migrate dev` — the shadow-DB baseline always fails in this repo. `python3 -m prisma migrate deploy --schema db/schema.prisma` requires `DATABASE_URL`, which is not set in the local dev environment — that step runs against Neon separately (post-merge), not as part of this plan.
- Prisma Python client model accessors are the model name fully lowercased, no underscores (e.g. `WeeklySignal` → `db.weeklysignal`, `MarketOutlook` → `db.marketoutlook`). `WeeklyBatchRun` → `db.weeklybatchrun`.
- `from prisma import Json` must be deferred to call time inside functions (not module-level import) — the real client isn't always generated in the test/CI environment; `tests/conftest.py` installs a stub with `Json = MagicMock` so this works everywhere.
- Backend response models use explicit snake_case Pydantic fields (no alias generator) — mapping from Prisma's camelCase attributes happens in a dedicated `*_row_to_response` function, matching `api/routes/autopilot.py`'s existing style.
- Frontend: no new UI primitives — reuse `Card`, `CardHeader`, `CardTitle`, `CardContent`, `Badge`, `Skeleton` from `frontend/components/ui/*` and `formatDate` from `frontend/lib/utils/formatting`. No shadcn `Select` exists in this repo; use a native `<select>`.

---

### Task 1: `WeeklyBatchRun` schema + migration

**Files:**
- Modify: `db/schema.prisma` (append new model near `MarketOutlook`, after line 925)
- Create: `db/migrations/20260712000000_add_weekly_batch_run/migration.sql`

**Interfaces:**
- Produces: Prisma model `WeeklyBatchRun` with client accessor `db.weeklybatchrun`, fields `id, runDate, status, abortReason, universeSize, advancedCount, watchlistExtras, quantStored, quantFailed, escalationSwarm, escalationReuse, escalationHold, swarmCap, outcomes, createdAt`.

- [ ] **Step 1: Add the model to `db/schema.prisma`**

Insert immediately after the `MarketOutlook` model's closing `}` (after line 925, before the `ThemeBasket` section comment):

```prisma
model WeeklyBatchRun {
  id                 String   @id @default(cuid())
  runDate            DateTime // Monday the batch ran (UTC)

  status             String   // "completed" | "aborted"
  abortReason        String?  // e.g. "empty_candidates"

  // Funnel-stage counts (Monday batch audit trail)
  universeSize       Int?     // raw screener universe size (~191)
  advancedCount      Int?     // top-N ∪ watchlist that passed the screener stage
  watchlistExtras    Int?     // subset of advancedCount added via watchlist, not top-N
  quantStored        Int?
  quantFailed        Int?
  escalationSwarm    Int?
  escalationReuse    Int?
  escalationHold     Int?
  swarmCap           Int?     // BATCH_MAX_SWARM_RUNS at run time, for context
  outcomes           Json?    // {ticker: "full"|"reused"|"step_failed"|...}, escalated tickers only

  createdAt          DateTime @default(now())

  @@index([runDate])
}
```

- [ ] **Step 2: Write the migration SQL**

Create `db/migrations/20260712000000_add_weekly_batch_run/migration.sql`:

```sql
-- CreateTable
CREATE TABLE "WeeklyBatchRun" (
    "id" TEXT NOT NULL,
    "runDate" TIMESTAMP(3) NOT NULL,
    "status" TEXT NOT NULL,
    "abortReason" TEXT,
    "universeSize" INTEGER,
    "advancedCount" INTEGER,
    "watchlistExtras" INTEGER,
    "quantStored" INTEGER,
    "quantFailed" INTEGER,
    "escalationSwarm" INTEGER,
    "escalationReuse" INTEGER,
    "escalationHold" INTEGER,
    "swarmCap" INTEGER,
    "outcomes" JSONB,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "WeeklyBatchRun_pkey" PRIMARY KEY ("id")
);

-- CreateIndex
CREATE INDEX "WeeklyBatchRun_runDate_idx" ON "WeeklyBatchRun"("runDate");
```

- [ ] **Step 3: Validate and regenerate the Prisma client**

Run: `python3 -m prisma validate --schema db/schema.prisma && python3 -m prisma generate --schema db/schema.prisma`
Expected: both commands exit 0; `generate` prints a line confirming the Python client was generated.

- [ ] **Step 4: Commit**

```bash
git add db/schema.prisma db/migrations/20260712000000_add_weekly_batch_run/
git commit -m "feat(db): add WeeklyBatchRun model for Monday batch audit trail"
```

---

### Task 2: `execution/batch_run_service.py` — pure record building + DB service

**Files:**
- Create: `execution/batch_run_service.py`
- Create: `tests/test_execution_batch_run_service.py`

**Interfaces:**
- Consumes: nothing from other tasks (pure module + `db` object at runtime).
- Produces (used by Task 3 and Task 4):
  - `build_batch_run_record(run_date: datetime, status: str, *, abort_reason: Optional[str] = None, universe_size: Optional[int] = None, advanced_count: Optional[int] = None, watchlist_extras: Optional[int] = None, quant_stored: Optional[int] = None, quant_failed: Optional[int] = None, escalation_swarm: Optional[int] = None, escalation_reuse: Optional[int] = None, escalation_hold: Optional[int] = None, swarm_cap: Optional[int] = None, outcomes: Optional[Dict[str, str]] = None) -> Dict[str, Any]`
  - `summarize_batch_run(*, universe_size: int, candidates: List[Dict[str, Any]], watchlist_extras: int, quant: Dict[str, Any], decisions: List[Dict[str, Any]], swarm_cap: int, outcomes: Dict[str, str]) -> Dict[str, Any]` — reduces weekly_batch's in-memory funnel state into `build_batch_run_record`'s kwargs.
  - `async store_batch_run(db, record: Dict[str, Any]) -> Any` (the created row)
  - `async get_latest_batch_run(db) -> Optional[Any]`
  - `async get_batch_run(db, run_date: datetime) -> Optional[Any]`
  - `async list_batch_runs(db, limit: int = 12) -> List[Any]`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_execution_batch_run_service.py`:

```python
"""Tests for execution/batch_run_service.py (db mocked)."""
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from execution.batch_run_service import (
    build_batch_run_record,
    get_batch_run,
    get_latest_batch_run,
    list_batch_runs,
    store_batch_run,
    summarize_batch_run,
)

RUN_DATE = datetime(2026, 7, 13, tzinfo=timezone.utc)


def test_build_record_completed_status():
    record = build_batch_run_record(
        RUN_DATE, "completed",
        universe_size=191, advanced_count=23, watchlist_extras=3,
        quant_stored=22, quant_failed=1,
        escalation_swarm=3, escalation_reuse=2, escalation_hold=17,
        swarm_cap=5, outcomes={"AAPL": "full"},
    )
    assert record["runDate"] == RUN_DATE
    assert record["status"] == "completed"
    assert record["abortReason"] is None
    assert record["universeSize"] == 191
    assert record["advancedCount"] == 23
    assert record["watchlistExtras"] == 3
    assert record["quantStored"] == 22
    assert record["quantFailed"] == 1
    assert record["escalationSwarm"] == 3
    assert record["escalationReuse"] == 2
    assert record["escalationHold"] == 17
    assert record["swarmCap"] == 5
    assert record["outcomes"] == {"AAPL": "full"}


def test_build_record_aborted_status_defaults_counts_to_none():
    record = build_batch_run_record(
        RUN_DATE, "aborted", abort_reason="empty_candidates",
        universe_size=0, advanced_count=0, watchlist_extras=0,
    )
    assert record["status"] == "aborted"
    assert record["abortReason"] == "empty_candidates"
    assert record["universeSize"] == 0
    assert record["advancedCount"] == 0
    assert record["quantStored"] is None
    assert record["escalationSwarm"] is None
    assert record["outcomes"] is None


def test_summarize_batch_run_counts_decisions_by_action():
    decisions = [
        {"ticker": "AAPL", "action": "swarm"},
        {"ticker": "MSFT", "action": "swarm"},
        {"ticker": "NVDA", "action": "reuse"},
        {"ticker": "TSLA", "action": "hold"},
        {"ticker": "AMD", "action": "hold"},
    ]
    quant = {"stored": 22, "failed": 1}
    outcomes = {"AAPL": "full", "MSFT": "step_failed", "NVDA": "reused"}

    counts = summarize_batch_run(
        universe_size=191, candidates=[{}] * 23, watchlist_extras=3,
        quant=quant, decisions=decisions, swarm_cap=5, outcomes=outcomes,
    )

    assert counts["universe_size"] == 191
    assert counts["advanced_count"] == 23
    assert counts["watchlist_extras"] == 3
    assert counts["quant_stored"] == 22
    assert counts["quant_failed"] == 1
    assert counts["escalation_swarm"] == 2
    assert counts["escalation_reuse"] == 1
    assert counts["escalation_hold"] == 2
    assert counts["swarm_cap"] == 5
    assert counts["outcomes"] == outcomes


def test_summarize_batch_run_zero_decisions():
    counts = summarize_batch_run(
        universe_size=191, candidates=[{}] * 5, watchlist_extras=0,
        quant={"stored": 5, "failed": 0}, decisions=[], swarm_cap=5, outcomes={},
    )
    assert counts["escalation_swarm"] == 0
    assert counts["escalation_reuse"] == 0
    assert counts["escalation_hold"] == 0
    assert counts["outcomes"] == {}


@pytest.mark.asyncio
async def test_store_batch_run_creates_row_and_wraps_outcomes_json():
    db = MagicMock()
    db.weeklybatchrun.create = AsyncMock(return_value="row")
    record = build_batch_run_record(
        RUN_DATE, "completed", universe_size=191, outcomes={"AAPL": "full"},
    )
    result = await store_batch_run(db, record)
    assert result == "row"
    data = db.weeklybatchrun.create.call_args.kwargs["data"]
    assert data["status"] == "completed"
    # prisma.Json is stubbed by conftest; assert it was wrapped (not the raw dict)
    assert data["outcomes"] is not record["outcomes"]


@pytest.mark.asyncio
async def test_store_batch_run_omits_none_outcomes():
    db = MagicMock()
    db.weeklybatchrun.create = AsyncMock(return_value="row")
    record = build_batch_run_record(RUN_DATE, "aborted", abort_reason="empty_candidates")
    await store_batch_run(db, record)
    data = db.weeklybatchrun.create.call_args.kwargs["data"]
    assert "outcomes" not in data


@pytest.mark.asyncio
async def test_get_latest_batch_run_orders_by_run_date_desc():
    db = MagicMock()
    db.weeklybatchrun.find_first = AsyncMock(return_value="latest")
    assert await get_latest_batch_run(db) == "latest"
    kwargs = db.weeklybatchrun.find_first.call_args.kwargs
    assert kwargs["order"] == {"runDate": "desc"}


@pytest.mark.asyncio
async def test_get_batch_run_filters_by_run_date():
    db = MagicMock()
    db.weeklybatchrun.find_first = AsyncMock(return_value="row")
    assert await get_batch_run(db, RUN_DATE) == "row"
    kwargs = db.weeklybatchrun.find_first.call_args.kwargs
    assert kwargs["where"] == {"runDate": RUN_DATE}


@pytest.mark.asyncio
async def test_list_batch_runs_orders_desc_and_clamps_limit():
    db = MagicMock()
    db.weeklybatchrun.find_many = AsyncMock(return_value=["a", "b"])
    result = await list_batch_runs(db, limit=999)
    assert result == ["a", "b"]
    kwargs = db.weeklybatchrun.find_many.call_args.kwargs
    assert kwargs["order"] == {"runDate": "desc"}
    assert kwargs["take"] == 52
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_execution_batch_run_service.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'execution.batch_run_service'`

- [ ] **Step 3: Implement `execution/batch_run_service.py`**

```python
"""Build, store, and read WeeklyBatchRun funnel-summary records.

build_batch_run_record and summarize_batch_run are pure (unit-testable, no
prisma). store/get/list are the only DB touchpoints and wrap the outcomes
Json column at the edge — same split as execution/outlook_service.py.
"""
from datetime import datetime
from typing import Any, Dict, List, Optional


def build_batch_run_record(
    run_date: datetime,
    status: str,
    *,
    abort_reason: Optional[str] = None,
    universe_size: Optional[int] = None,
    advanced_count: Optional[int] = None,
    watchlist_extras: Optional[int] = None,
    quant_stored: Optional[int] = None,
    quant_failed: Optional[int] = None,
    escalation_swarm: Optional[int] = None,
    escalation_reuse: Optional[int] = None,
    escalation_hold: Optional[int] = None,
    swarm_cap: Optional[int] = None,
    outcomes: Optional[Dict[str, str]] = None,
) -> Dict[str, Any]:
    return {
        "runDate": run_date,
        "status": status,
        "abortReason": abort_reason,
        "universeSize": universe_size,
        "advancedCount": advanced_count,
        "watchlistExtras": watchlist_extras,
        "quantStored": quant_stored,
        "quantFailed": quant_failed,
        "escalationSwarm": escalation_swarm,
        "escalationReuse": escalation_reuse,
        "escalationHold": escalation_hold,
        "swarmCap": swarm_cap,
        "outcomes": outcomes,
    }


def summarize_batch_run(
    *,
    universe_size: int,
    candidates: List[Dict[str, Any]],
    watchlist_extras: int,
    quant: Dict[str, Any],
    decisions: List[Dict[str, Any]],
    swarm_cap: int,
    outcomes: Dict[str, str],
) -> Dict[str, Any]:
    """Reduce weekly_batch's in-memory funnel state to build_batch_run_record kwargs."""
    return {
        "universe_size": universe_size,
        "advanced_count": len(candidates),
        "watchlist_extras": watchlist_extras,
        "quant_stored": quant["stored"],
        "quant_failed": quant["failed"],
        "escalation_swarm": sum(1 for d in decisions if d["action"] == "swarm"),
        "escalation_reuse": sum(1 for d in decisions if d["action"] == "reuse"),
        "escalation_hold": sum(1 for d in decisions if d["action"] == "hold"),
        "swarm_cap": swarm_cap,
        "outcomes": outcomes,
    }


async def store_batch_run(db, record: Dict[str, Any]) -> Any:
    from prisma import Json  # runtime-only dependency

    data = dict(record)
    if data.get("outcomes") is None:
        data.pop("outcomes", None)
    else:
        data["outcomes"] = Json(data["outcomes"])
    return await db.weeklybatchrun.create(data=data)


async def get_latest_batch_run(db) -> Optional[Any]:
    return await db.weeklybatchrun.find_first(order={"runDate": "desc"})


async def get_batch_run(db, run_date: datetime) -> Optional[Any]:
    return await db.weeklybatchrun.find_first(where={"runDate": run_date})


async def list_batch_runs(db, limit: int = 12) -> List[Any]:
    return await db.weeklybatchrun.find_many(
        order={"runDate": "desc"}, take=max(1, min(limit, 52))
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_execution_batch_run_service.py -v`
Expected: PASS (10 tests)

- [ ] **Step 5: Commit**

```bash
git add execution/batch_run_service.py tests/test_execution_batch_run_service.py
git commit -m "feat(execution): add WeeklyBatchRun record building and DB service"
```

---

### Task 3: Persist funnel summary from `weekly_batch.py`

**Files:**
- Modify: `inngest_app/functions/weekly_batch.py`

**Interfaces:**
- Consumes: `execution.batch_run_service.{build_batch_run_record, summarize_batch_run, store_batch_run}` (Task 2).

- [ ] **Step 1: Change `run_screener`'s return shape to also carry the universe size**

In `inngest_app/functions/weekly_batch.py`, find the `run_screener` function (return type currently `List[Dict[str, Any]]`) and its call site. Replace this block:

```python
        async def run_screener() -> List[Dict[str, Any]]:
            screener = StockScreener(
                market_client=MarketDataClient(),
                insider_client=OpenInsiderClient(),
            )
            universe = StockScreener.load_universe()
            scored = await asyncio.to_thread(screener.screen_all, universe)

            db = await get_db()
            wl_rows = await db.watchlist.find_many(distinct=["ticker"])
            watchlisted = {w.ticker.upper() for w in wl_rows}

            top = scored[:_MAX_CANDIDATES]
            top_tickers = {st.ticker for st in top}
            extra = [
                st for st in scored
                if st.ticker in watchlisted and st.ticker not in top_tickers
            ]
            advancing = top + extra
            sector_map = StockScreener.load_sector_map()
            logger.info(
                "Screener advancing %d tickers (%d watchlist extras)",
                len(advancing), len(extra),
            )
            return [
                {
                    "ticker": st.ticker,
                    "score": st.score,
                    "sector": sector_map.get(st.ticker),
                    "on_watchlist": st.ticker in watchlisted,
                    "has_insider_buying": st.signals.has_insider_buying,
                    "weekly_price_change_pct": st.signals.weekly_price_change_pct,
                    "days_to_earnings": st.signals.days_to_earnings,
                    "days_since_earnings": st.signals.days_since_earnings,
                }
                for st in advancing
            ]

        candidates: List[Dict[str, Any]] = await step.run(
            "screen-universe", run_screener
        )

        if not candidates:
            logger.error("Screener returned no candidates — aborting batch")
            return {"status": "aborted", "reason": "empty_candidates"}
```

with:

```python
        async def run_screener() -> Dict[str, Any]:
            screener = StockScreener(
                market_client=MarketDataClient(),
                insider_client=OpenInsiderClient(),
            )
            universe = StockScreener.load_universe()
            scored = await asyncio.to_thread(screener.screen_all, universe)

            db = await get_db()
            wl_rows = await db.watchlist.find_many(distinct=["ticker"])
            watchlisted = {w.ticker.upper() for w in wl_rows}

            top = scored[:_MAX_CANDIDATES]
            top_tickers = {st.ticker for st in top}
            extra = [
                st for st in scored
                if st.ticker in watchlisted and st.ticker not in top_tickers
            ]
            advancing = top + extra
            sector_map = StockScreener.load_sector_map()
            logger.info(
                "Screener advancing %d tickers (%d watchlist extras)",
                len(advancing), len(extra),
            )
            return {
                "universe_size": len(universe),
                "watchlist_extras": len(extra),
                "candidates": [
                    {
                        "ticker": st.ticker,
                        "score": st.score,
                        "sector": sector_map.get(st.ticker),
                        "on_watchlist": st.ticker in watchlisted,
                        "has_insider_buying": st.signals.has_insider_buying,
                        "weekly_price_change_pct": st.signals.weekly_price_change_pct,
                        "days_to_earnings": st.signals.days_to_earnings,
                        "days_since_earnings": st.signals.days_since_earnings,
                    }
                    for st in advancing
                ],
            }

        screen_result: Dict[str, Any] = await step.run(
            "screen-universe", run_screener
        )
        candidates: List[Dict[str, Any]] = screen_result["candidates"]
        universe_size: int = screen_result["universe_size"]
        watchlist_extras: int = screen_result["watchlist_extras"]

        if not candidates:
            logger.error("Screener returned no candidates — aborting batch")

            async def persist_aborted_summary() -> None:
                from api.lib.db import get_db  # noqa: PLC0415
                from execution.batch_run_service import (  # noqa: PLC0415
                    build_batch_run_record, store_batch_run,
                )
                try:
                    record = build_batch_run_record(
                        run_date, "aborted",
                        abort_reason="empty_candidates",
                        universe_size=universe_size,
                        advanced_count=0,
                        watchlist_extras=watchlist_extras,
                    )
                    await store_batch_run(await get_db(), record)
                except Exception as exc:
                    logger.exception("Failed to persist aborted batch-run summary")
                    from execution.alerts import send_failure_alert  # noqa: PLC0415
                    await send_failure_alert(
                        "Batch-run summary persist failed (aborted path)",
                        f"{type(exc).__name__}: {exc}", source="weekly_batch")

            await step.run("persist-batch-summary", persist_aborted_summary)
            return {"status": "aborted", "reason": "empty_candidates"}
```

- [ ] **Step 2: Add the completion-path persist step**

Find the final section of `weekly_batch`:

```python
        # ── Final step: fire batch/completed for (dormant) downstream fns ────
        # send_event is itself a step tool — never wrap it in step.run
        # (nested steps are a non-retriable SDK error).
        await step.send_event(
```

Insert immediately before it:

```python
        # ── Persist funnel-stage summary for the admin audit view ────────────
        async def persist_batch_summary() -> None:
            from api.lib.db import get_db  # noqa: PLC0415
            from execution.batch_run_service import (  # noqa: PLC0415
                build_batch_run_record, store_batch_run, summarize_batch_run,
            )
            try:
                counts = summarize_batch_run(
                    universe_size=universe_size, candidates=candidates,
                    watchlist_extras=watchlist_extras, quant=quant,
                    decisions=decisions, swarm_cap=_MAX_SWARM_RUNS, outcomes=outcomes,
                )
                record = build_batch_run_record(run_date, "completed", **counts)
                await store_batch_run(await get_db(), record)
            except Exception as exc:
                logger.exception("Failed to persist batch-run summary")
                from execution.alerts import send_failure_alert  # noqa: PLC0415
                await send_failure_alert(
                    "Batch-run summary persist failed", f"{type(exc).__name__}: {exc}",
                    source="weekly_batch")

        await step.run("persist-batch-summary", persist_batch_summary)

```

(Keep the existing `# ── Final step: fire batch/completed ...` comment and `step.send_event(...)` call unchanged, right after this new block.)

- [ ] **Step 3: Verify the module still imports cleanly and the registration tests pass**

Run: `python3 -m pytest tests/test_weekly_batch_registration.py -v`
Expected: PASS (3 tests) — confirms the edit didn't break guarded registration or `ACTIVE_FUNCTIONS` wiring.

Note: `weekly_batch.py`'s internal step closures have no direct unit-test harness in this codebase (only `build_batch_run_record`/`summarize_batch_run`/`store_batch_run`, tested in Task 2, and this registration check, exist as coverage) — this matches the file's existing test coverage pattern (see `tests/test_weekly_batch_registration.py`, which only checks import/registration, not step logic).

- [ ] **Step 4: Commit**

```bash
git add inngest_app/functions/weekly_batch.py
git commit -m "feat(weekly-batch): persist funnel-summary row for the admin audit view"
```

---

### Task 4: Admin API endpoints

**Files:**
- Modify: `api/routes/autopilot.py`
- Modify: `tests/test_autopilot_routes.py`

**Interfaces:**
- Consumes: `execution.batch_run_service.{get_batch_run, get_latest_batch_run, list_batch_runs}` (Task 2).
- Produces (used by Task 6): `GET /api/autopilot/batch-runs?limit=<int>` → `List[WeeklyBatchRunSummary]`; `GET /api/autopilot/batch-runs/detail?run_date=<iso>` (query param optional, defaults to latest) → `WeeklyBatchRunDetail`.

Note: the spec described `/batch-runs/latest` and `/batch-runs/{run_date}` as two path-based routes. Implementing this as one endpoint with an optional `run_date` query param avoids two path-routing pitfalls (route-ordering between a literal `/latest` segment and a `{run_date}` matcher, and URL-encoding `+`/`:` characters from ISO datetimes in a path segment) while producing the identical behavior the spec asked for.

- [ ] **Step 1: Write the failing tests**

In `tests/test_autopilot_routes.py`, add near the top (after the existing imports, before `RUN_DATE = ...`):

```python
from api.routes.autopilot import (
    MarketOutlookResponse, outlook_row_to_response, router,
    WeeklyBatchRunDetail, WeeklyBatchRunSummary,
    batch_run_row_to_summary, batch_run_row_to_detail,
)
```

(Replace the existing single-line `from api.routes.autopilot import MarketOutlookResponse, outlook_row_to_response, router` import with the block above.)

Then append this new test module content to the end of the file:

```python
# ── Monday batch audit trail ────────────────────────────────────────────────

BATCH_RUN_DATE = datetime(2026, 7, 13, tzinfo=timezone.utc)


def _make_batch_run_row(**overrides) -> SimpleNamespace:
    defaults = dict(
        id="run1",
        runDate=BATCH_RUN_DATE,
        status="completed",
        abortReason=None,
        universeSize=191,
        advancedCount=23,
        watchlistExtras=3,
        quantStored=22,
        quantFailed=1,
        escalationSwarm=3,
        escalationReuse=2,
        escalationHold=17,
        swarmCap=5,
        outcomes={"AAPL": "full"},
    )
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


def _make_signal_row(**overrides) -> SimpleNamespace:
    defaults = dict(
        ticker="AAPL",
        tier="full",
        verdict="buy",
        screenerScore=8.2,
        escalationScore=3.1,
        escalationReasons=["prior_buy", "post_earnings"],
        quantSignals={"has_insider_buying": True},
    )
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


class TestBatchRunRowToSummary:
    def test_maps_camel_to_snake(self):
        row = _make_batch_run_row()
        result = batch_run_row_to_summary(row)
        assert isinstance(result, WeeklyBatchRunSummary)
        assert result.id == "run1"
        assert result.run_date == BATCH_RUN_DATE
        assert result.status == "completed"
        assert result.universe_size == 191
        assert result.advanced_count == 23
        assert result.watchlist_extras == 3
        assert result.quant_stored == 22
        assert result.quant_failed == 1
        assert result.escalation_swarm == 3
        assert result.escalation_reuse == 2
        assert result.escalation_hold == 17
        assert result.swarm_cap == 5

    def test_aborted_row(self):
        row = _make_batch_run_row(
            status="aborted", abortReason="empty_candidates",
            advancedCount=0, quantStored=None, escalationSwarm=None,
        )
        result = batch_run_row_to_summary(row)
        assert result.status == "aborted"
        assert result.abort_reason == "empty_candidates"
        assert result.quant_stored is None


class TestBatchRunRowToDetail:
    def test_includes_outcomes_and_signals(self):
        row = _make_batch_run_row()
        signal_rows = [_make_signal_row(), _make_signal_row(ticker="MSFT", tier="quant", verdict=None)]
        result = batch_run_row_to_detail(row, signal_rows)
        assert isinstance(result, WeeklyBatchRunDetail)
        assert result.outcomes == {"AAPL": "full"}
        assert len(result.signals) == 2
        assert result.signals[0].ticker == "AAPL"
        assert result.signals[0].escalation_reasons == ["prior_buy", "post_earnings"]
        assert result.signals[1].tier == "quant"
        assert result.signals[1].verdict is None


class TestGetBatchRunsEndpoint:
    def test_returns_summaries_newest_first(self):
        newer = _make_batch_run_row(id="run2", runDate=datetime(2026, 7, 13, tzinfo=timezone.utc))
        older = _make_batch_run_row(id="run1", runDate=datetime(2026, 7, 6, tzinfo=timezone.utc))
        app = _admin_app()
        mock_db = MagicMock()
        mock_db.weeklybatchrun.find_many = AsyncMock(return_value=[newer, older])
        with _patch_db(db=mock_db):
            resp = TestClient(app).get("/api/autopilot/batch-runs")
        assert resp.status_code == 200
        data = resp.json()
        assert [row["id"] for row in data] == ["run2", "run1"]

    def test_passes_limit_through(self):
        app = _admin_app()
        mock_db = MagicMock()
        mock_db.weeklybatchrun.find_many = AsyncMock(return_value=[])
        with _patch_db(db=mock_db):
            resp = TestClient(app).get("/api/autopilot/batch-runs", params={"limit": 4})
        assert resp.status_code == 200
        _, kwargs = mock_db.weeklybatchrun.find_many.call_args
        assert kwargs["take"] == 4


class TestGetBatchRunDetailEndpoint:
    def test_defaults_to_latest_when_no_run_date(self):
        row = _make_batch_run_row()
        app = _admin_app()
        mock_db = MagicMock()
        mock_db.weeklybatchrun.find_first = AsyncMock(return_value=row)
        mock_db.weeklysignal.find_many = AsyncMock(return_value=[_make_signal_row()])
        with _patch_db(db=mock_db):
            resp = TestClient(app).get("/api/autopilot/batch-runs/detail")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "run1"
        assert data["signals"][0]["ticker"] == "AAPL"
        _, kwargs = mock_db.weeklybatchrun.find_first.call_args
        assert kwargs["order"] == {"runDate": "desc"}

    def test_looks_up_specific_run_date(self):
        row = _make_batch_run_row()
        app = _admin_app()
        mock_db = MagicMock()
        mock_db.weeklybatchrun.find_first = AsyncMock(return_value=row)
        mock_db.weeklysignal.find_many = AsyncMock(return_value=[])
        with _patch_db(db=mock_db):
            resp = TestClient(app).get(
                "/api/autopilot/batch-runs/detail",
                params={"run_date": "2026-07-13T00:00:00+00:00"},
            )
        assert resp.status_code == 200
        _, kwargs = mock_db.weeklybatchrun.find_first.call_args
        assert kwargs["where"] == {"runDate": BATCH_RUN_DATE}

    def test_returns_404_when_no_runs(self):
        app = _admin_app()
        mock_db = MagicMock()
        mock_db.weeklybatchrun.find_first = AsyncMock(return_value=None)
        with _patch_db(db=mock_db):
            resp = TestClient(app).get("/api/autopilot/batch-runs/detail")
        assert resp.status_code == 404
        assert resp.json()["detail"] == "No batch run available yet"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_autopilot_routes.py -v`
Expected: FAIL — `ImportError: cannot import name 'WeeklyBatchRunSummary' from 'api.routes.autopilot'`

- [ ] **Step 3: Implement the response models, mappers, and endpoints**

In `api/routes/autopilot.py`, add this import alongside the existing `from execution.outlook_service import get_latest_outlook` line:

```python
from execution.batch_run_service import (
    get_batch_run, get_latest_batch_run, list_batch_runs,
)
```

Then, immediately after the `get_engine_reports` endpoint (after its closing line, before the `# ── Phase 2: broker linking + sleeve control ────` comment), insert:

```python
# ── Monday batch audit trail ────────────────────────────────────────────────

class WeeklyBatchRunSummary(BaseModel):
    """One WeeklyBatchRun row, counts only — powers the history picker."""
    id: str
    run_date: datetime
    status: str
    abort_reason: Optional[str]
    universe_size: Optional[int]
    advanced_count: Optional[int]
    watchlist_extras: Optional[int]
    quant_stored: Optional[int]
    quant_failed: Optional[int]
    escalation_swarm: Optional[int]
    escalation_reuse: Optional[int]
    escalation_hold: Optional[int]
    swarm_cap: Optional[int]


class WeeklySignalRow(BaseModel):
    """One WeeklySignal row for a batch-run week, admin audit shape."""
    ticker: str
    tier: str
    verdict: Optional[str]
    screener_score: Optional[float]
    escalation_score: Optional[float]
    escalation_reasons: Optional[List[str]]
    quant_signals: Optional[dict]


class WeeklyBatchRunDetail(WeeklyBatchRunSummary):
    """One WeeklyBatchRun row plus its WeeklySignal rows for that week."""
    outcomes: Optional[Dict[str, str]]
    signals: List[WeeklySignalRow]


def batch_run_row_to_summary(row) -> WeeklyBatchRunSummary:
    """Map a Prisma WeeklyBatchRun row (camelCase) to WeeklyBatchRunSummary (snake_case)."""
    return WeeklyBatchRunSummary(
        id=row.id,
        run_date=row.runDate,
        status=row.status,
        abort_reason=row.abortReason,
        universe_size=row.universeSize,
        advanced_count=row.advancedCount,
        watchlist_extras=row.watchlistExtras,
        quant_stored=row.quantStored,
        quant_failed=row.quantFailed,
        escalation_swarm=row.escalationSwarm,
        escalation_reuse=row.escalationReuse,
        escalation_hold=row.escalationHold,
        swarm_cap=row.swarmCap,
    )


def weekly_signal_row_to_response(row) -> WeeklySignalRow:
    """Map a Prisma WeeklySignal row (camelCase) to WeeklySignalRow (snake_case)."""
    return WeeklySignalRow(
        ticker=row.ticker,
        tier=row.tier,
        verdict=row.verdict,
        screener_score=row.screenerScore,
        escalation_score=row.escalationScore,
        escalation_reasons=row.escalationReasons,
        quant_signals=row.quantSignals,
    )


def batch_run_row_to_detail(row, signal_rows) -> WeeklyBatchRunDetail:
    """Combine a WeeklyBatchRun row with its week's WeeklySignal rows."""
    summary = batch_run_row_to_summary(row)
    return WeeklyBatchRunDetail(
        **summary.model_dump(),
        outcomes=row.outcomes,
        signals=[weekly_signal_row_to_response(r) for r in signal_rows],
    )


@router.get("/autopilot/batch-runs", response_model=List[WeeklyBatchRunSummary])
async def get_batch_runs(limit: int = 12, admin: User = Depends(require_admin)):
    """History list of past weekly-batch runs, newest first."""
    db = await get_db()
    rows = await list_batch_runs(db, limit=limit)
    return [batch_run_row_to_summary(r) for r in rows]


@router.get("/autopilot/batch-runs/detail", response_model=WeeklyBatchRunDetail)
async def get_batch_run_detail(
    run_date: Optional[datetime] = None, admin: User = Depends(require_admin)
):
    """One weekly-batch run with its WeeklySignal rows joined in.

    Omit run_date for the most recent run.
    """
    db = await get_db()
    row = await get_batch_run(db, run_date) if run_date else await get_latest_batch_run(db)
    if row is None:
        raise HTTPException(status_code=404, detail="No batch run available yet")
    signal_rows = await db.weeklysignal.find_many(where={"runDate": row.runDate})
    return batch_run_row_to_detail(row, signal_rows)
```

Also add `Dict` to the existing `from typing import List, Optional` import line (making it `from typing import Dict, List, Optional`).

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_autopilot_routes.py -v`
Expected: PASS (all tests, including the pre-existing ones)

- [ ] **Step 5: Commit**

```bash
git add api/routes/autopilot.py tests/test_autopilot_routes.py
git commit -m "feat(api): add admin endpoints for the Monday batch audit trail"
```

---

### Task 5: Frontend types

**Files:**
- Modify: `frontend/types/api.ts`

**Interfaces:**
- Produces (used by Task 6, 7): `WeeklyBatchRunSummary`, `WeeklySignalRow`, `WeeklyBatchRunDetail`.

- [ ] **Step 1: Add the types**

In `frontend/types/api.ts`, immediately after the `MarketOutlookResponse` interface (after its closing `}`, before `export class ApiError`), insert:

```typescript
// ─── Autopilot weekly batch run (Monday funnel audit, admin) ──────────────

export interface WeeklyBatchRunSummary {
  id: string
  run_date: string
  status: 'completed' | 'aborted'
  abort_reason: string | null
  universe_size: number | null
  advanced_count: number | null
  watchlist_extras: number | null
  quant_stored: number | null
  quant_failed: number | null
  escalation_swarm: number | null
  escalation_reuse: number | null
  escalation_hold: number | null
  swarm_cap: number | null
}

export interface WeeklySignalRow {
  ticker: string
  tier: string
  verdict: string | null
  screener_score: number | null
  escalation_score: number | null
  escalation_reasons: string[] | null
  quant_signals: Record<string, unknown> | null
}

export interface WeeklyBatchRunDetail extends WeeklyBatchRunSummary {
  outcomes: Record<string, string> | null
  signals: WeeklySignalRow[]
}
```

- [ ] **Step 2: Verify the file still type-checks**

Run: `cd frontend && npx tsc --noEmit`
Expected: no new errors (pre-existing errors, if any, are unrelated to this file — compare against a run before this change if unsure).

- [ ] **Step 3: Commit**

```bash
git add frontend/types/api.ts
git commit -m "feat(types): add WeeklyBatchRun types"
```

---

### Task 6: Frontend API client + React Query hooks

**Files:**
- Modify: `frontend/lib/api/client.ts`
- Modify: `frontend/lib/hooks/useAdmin.ts`

**Interfaces:**
- Consumes: `WeeklyBatchRunSummary`, `WeeklyBatchRunDetail` (Task 5).
- Produces (used by Task 7): `apiClient.getWeeklyBatchRuns(limit?)`, `apiClient.getWeeklyBatchRunDetail(runDate?)`, `useWeeklyBatchRuns()`, `useWeeklyBatchRunDetail(runDate?)`.

- [ ] **Step 1: Add client methods**

In `frontend/lib/api/client.ts`, add `WeeklyBatchRunSummary` and `WeeklyBatchRunDetail` to the first `import type { ... } from '@/types/api'` block (alongside `MarketOutlookResponse`).

Then, immediately after the existing `getEngineReports` method, insert:

```typescript
  async getWeeklyBatchRuns(limit = 12): Promise<WeeklyBatchRunSummary[]> {
    return this.request(`/api/autopilot/batch-runs?limit=${limit}`)
  }

  async getWeeklyBatchRunDetail(runDate?: string): Promise<WeeklyBatchRunDetail> {
    const suffix = runDate ? `?run_date=${encodeURIComponent(runDate)}` : ''
    return this.request(`/api/autopilot/batch-runs/detail${suffix}`)
  }
```

- [ ] **Step 2: Add React Query hooks**

In `frontend/lib/hooks/useAdmin.ts`, add `WeeklyBatchRunSummary` and `WeeklyBatchRunDetail` to the `import type { ... } from '@/types/api'` block.

Add two new query-key builders to `adminKeys` (after the existing `engineReports` line):

```typescript
  batchRuns: () => [...adminKeys.all, 'batchRuns'] as const,
  batchRunDetail: (runDate?: string) => [...adminKeys.all, 'batchRunDetail', runDate ?? 'latest'] as const,
```

Then, immediately after the `useEngineReports` function, insert:

```typescript
/**
 * History list of past Monday weekly-batch runs, newest first.
 */
export function useWeeklyBatchRuns() {
  return useQuery({
    queryKey: adminKeys.batchRuns(),
    queryFn: () => apiClient.getWeeklyBatchRuns(),
    staleTime: 1000 * 60 * 5, // 5 minutes
  })
}

/**
 * One weekly-batch run's funnel summary + ticker rows. Omit runDate for the
 * most recent run (404 until the first Monday run lands).
 */
export function useWeeklyBatchRunDetail(runDate?: string) {
  return useQuery({
    queryKey: adminKeys.batchRunDetail(runDate),
    queryFn: () => apiClient.getWeeklyBatchRunDetail(runDate),
    staleTime: 1000 * 60 * 5, // 5 minutes
    retry: (failureCount, error) => (error as any)?.status === 404 ? false : failureCount < 1,
  })
}
```

- [ ] **Step 3: Verify type-check**

Run: `cd frontend && npx tsc --noEmit`
Expected: no new errors.

- [ ] **Step 4: Commit**

```bash
git add frontend/lib/api/client.ts frontend/lib/hooks/useAdmin.ts
git commit -m "feat(frontend): add API client + hooks for the Monday batch audit trail"
```

---

### Task 7: `WeeklyBatchPanel` component

**Files:**
- Create: `frontend/components/autopilot/WeeklyBatchPanel.tsx`

**Interfaces:**
- Consumes: `useWeeklyBatchRuns`, `useWeeklyBatchRunDetail` (Task 6); `WeeklyBatchRunDetail`, `WeeklyBatchRunSummary`, `WeeklySignalRow` (Task 5); `Card`/`CardHeader`/`CardTitle`/`CardContent` from `@/components/ui/card`; `Badge` from `@/components/ui/badge`; `Skeleton` from `@/components/ui/skeleton`; `formatDate` from `@/lib/utils/formatting`.
- Produces (used by Task 8): `export function WeeklyBatchPanel()`.

- [ ] **Step 1: Create the component**

```tsx
import { useMemo, useState } from 'react'
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Skeleton } from '@/components/ui/skeleton'
import { useWeeklyBatchRuns, useWeeklyBatchRunDetail } from '@/lib/hooks/useAdmin'
import { formatDate } from '@/lib/utils/formatting'
import type {
  WeeklyBatchRunDetail,
  WeeklyBatchRunSummary,
  WeeklySignalRow,
} from '@/types/api'

type SortDir = 'asc' | 'desc'

const SIGNAL_SORT_DEFAULTS: Partial<Record<keyof WeeklySignalRow, SortDir>> = {
  ticker: 'asc',
  tier: 'asc',
  verdict: 'asc',
  screener_score: 'desc',
  escalation_score: 'desc',
}

function SortIndicator({ active, dir }: { active: boolean; dir: SortDir }) {
  if (!active) return null
  return <span className="ml-1">{dir === 'asc' ? '▲' : '▼'}</span>
}

const TIER_BADGE_VARIANT: Record<string, 'success' | 'warning' | 'secondary'> = {
  full: 'success',
  quant: 'secondary',
  engine_light: 'warning',
}

function FunnelStat({ label, value, sub }: { label: string; value: number | null; sub?: string }) {
  return (
    <div className="flex flex-col">
      <span className="text-text-tertiary text-xs uppercase tracking-wide">{label}</span>
      <span className="text-text-primary font-medium">{value ?? 'n/a'}</span>
      {sub && <span className="text-text-tertiary text-xs">{sub}</span>}
    </div>
  )
}

function FunnelArrow() {
  return <span className="text-text-tertiary">→</span>
}

function SortableHeader({
  field, label, sort, onSort, align,
}: {
  field: keyof WeeklySignalRow
  label: string
  sort: { field: keyof WeeklySignalRow; dir: SortDir }
  onSort: (field: keyof WeeklySignalRow) => void
  align: 'left' | 'right'
}) {
  return (
    <th className={`${align === 'right' ? 'text-right' : 'text-left'} py-2 px-2 font-medium`}>
      <button
        type="button"
        onClick={() => onSort(field)}
        className={`flex items-center hover:text-text-primary ${align === 'right' ? 'justify-end w-full' : ''}`}
      >
        {label}
        <SortIndicator active={sort.field === field} dir={sort.dir} />
      </button>
    </th>
  )
}

export function WeeklyBatchPanel() {
  const { data: runs } = useWeeklyBatchRuns()
  const [selectedRunDate, setSelectedRunDate] = useState<string | undefined>(undefined)
  const { data, isLoading, error } = useWeeklyBatchRunDetail(selectedRunDate)

  if (isLoading) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Monday Batch</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="space-y-4">
            {[1, 2, 3].map((i) => (
              <Skeleton key={i} className="h-16" />
            ))}
          </div>
        </CardContent>
      </Card>
    )
  }

  if (error && (error as any).status === 404) {
    return (
      <Card>
        <CardContent className="py-12 text-center">
          <p className="text-text-secondary">
            No batch run yet — first one generates Monday morning.
          </p>
        </CardContent>
      </Card>
    )
  }

  if (error || !data) {
    return (
      <Card>
        <CardContent className="py-12 text-center">
          <p className="text-text-secondary">Failed to load batch run</p>
        </CardContent>
      </Card>
    )
  }

  return (
    <WeeklyBatchContent
      run={data}
      history={runs ?? []}
      selectedRunDate={selectedRunDate}
      onSelectRunDate={setSelectedRunDate}
    />
  )
}

function WeeklyBatchContent({
  run,
  history,
  selectedRunDate,
  onSelectRunDate,
}: {
  run: WeeklyBatchRunDetail
  history: WeeklyBatchRunSummary[]
  selectedRunDate: string | undefined
  onSelectRunDate: (runDate: string | undefined) => void
}) {
  const [signalSort, setSignalSort] = useState<{ field: keyof WeeklySignalRow; dir: SortDir }>({
    field: 'escalation_score',
    dir: 'desc',
  })

  function toggleSignalSort(field: keyof WeeklySignalRow) {
    setSignalSort((prev) =>
      prev.field === field
        ? { field, dir: prev.dir === 'asc' ? 'desc' : 'asc' }
        : { field, dir: SIGNAL_SORT_DEFAULTS[field] ?? 'asc' }
    )
  }

  const sortedSignals = useMemo(() => {
    const rows = [...run.signals]
    const { field, dir } = signalSort
    rows.sort((a, b) => {
      const av = a[field]
      const bv = b[field]
      if (av === null && bv === null) return 0
      if (av === null) return 1
      if (bv === null) return -1
      if (typeof av === 'string' && typeof bv === 'string') {
        return dir === 'asc' ? av.localeCompare(bv) : bv.localeCompare(av)
      }
      return dir === 'asc' ? (av as number) - (bv as number) : (bv as number) - (av as number)
    })
    return rows
  }, [run.signals, signalSort])

  const totalEscalated =
    run.escalation_swarm !== null && run.escalation_reuse !== null && run.escalation_hold !== null
      ? run.escalation_swarm + run.escalation_reuse + run.escalation_hold
      : null

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader>
          <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2">
            <CardTitle>Monday Batch</CardTitle>
            <div className="flex items-center gap-2">
              <span className="text-sm text-text-secondary">Week of {formatDate(run.run_date)}</span>
              {history.length > 1 && (
                <select
                  className="text-sm bg-surface border border-surface-elevated rounded px-2 py-1"
                  value={selectedRunDate ?? history[0]?.run_date ?? ''}
                  onChange={(e) => {
                    const val = e.target.value
                    onSelectRunDate(val === history[0]?.run_date ? undefined : val)
                  }}
                >
                  {history.map((h) => (
                    <option key={h.id} value={h.run_date}>
                      {formatDate(h.run_date)} ({h.status})
                    </option>
                  ))}
                </select>
              )}
            </div>
          </div>
        </CardHeader>
        <CardContent className="space-y-4">
          {run.status === 'aborted' ? (
            <div className="flex items-center gap-2 text-sm text-error">
              <Badge variant="error">Aborted</Badge>
              <span>{run.abort_reason ?? 'unknown reason'}</span>
            </div>
          ) : (
            <div className="flex flex-wrap items-center gap-4 text-sm">
              <FunnelStat label="Screened" value={run.universe_size} />
              <FunnelArrow />
              <FunnelStat
                label="Advanced"
                value={run.advanced_count}
                sub={run.watchlist_extras ? `${run.watchlist_extras} watchlist` : undefined}
              />
              <FunnelArrow />
              <FunnelStat
                label="Quant stored"
                value={run.quant_stored}
                sub={run.quant_failed ? `${run.quant_failed} failed` : undefined}
              />
              <FunnelArrow />
              <FunnelStat
                label="Escalated"
                value={totalEscalated}
                sub={`${run.escalation_swarm ?? 0} swarm / ${run.escalation_reuse ?? 0} reuse / ${run.escalation_hold ?? 0} hold`}
              />
              <FunnelArrow />
              <FunnelStat
                label="Swarm used"
                value={run.escalation_swarm}
                sub={run.swarm_cap !== null ? `of ${run.swarm_cap} cap` : undefined}
              />
            </div>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Escalated Tickers</CardTitle>
        </CardHeader>
        <CardContent>
          {run.signals.length === 0 ? (
            <p className="text-sm text-text-secondary">No escalated tickers this run.</p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-xs">
                <thead>
                  <tr className="border-b border-surface-elevated text-text-secondary uppercase tracking-wide">
                    <SortableHeader field="ticker" label="Ticker" sort={signalSort} onSort={toggleSignalSort} align="left" />
                    <SortableHeader field="tier" label="Tier" sort={signalSort} onSort={toggleSignalSort} align="left" />
                    <SortableHeader field="verdict" label="Verdict" sort={signalSort} onSort={toggleSignalSort} align="left" />
                    <SortableHeader field="screener_score" label="Screener" sort={signalSort} onSort={toggleSignalSort} align="right" />
                    <SortableHeader field="escalation_score" label="Escalation" sort={signalSort} onSort={toggleSignalSort} align="right" />
                    <th className="text-left py-2 pl-2 font-medium">Reasons</th>
                  </tr>
                </thead>
                <tbody>
                  {sortedSignals.map((row) => (
                    <tr key={row.ticker} className="border-b border-surface-elevated/30">
                      <td className="py-2 pr-3 text-text-primary font-medium">{row.ticker}</td>
                      <td className="py-2 px-2">
                        <Badge variant={TIER_BADGE_VARIANT[row.tier] ?? 'secondary'}>{row.tier}</Badge>
                      </td>
                      <td className="py-2 px-2 text-text-secondary">{row.verdict ?? 'n/a'}</td>
                      <td className="text-right py-2 px-2 text-text-secondary">
                        {row.screener_score !== null ? row.screener_score.toFixed(2) : 'n/a'}
                      </td>
                      <td className="text-right py-2 px-2 text-text-secondary">
                        {row.escalation_score !== null ? row.escalation_score.toFixed(2) : 'n/a'}
                      </td>
                      <td className="py-2 pl-2 text-text-tertiary">
                        {row.escalation_reasons?.join(', ') ?? '—'}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  )
}
```

- [ ] **Step 2: Verify type-check**

Run: `cd frontend && npx tsc --noEmit`
Expected: no new errors.

- [ ] **Step 3: Commit**

```bash
git add frontend/components/autopilot/WeeklyBatchPanel.tsx
git commit -m "feat(frontend): add WeeklyBatchPanel component"
```

---

### Task 8: Wire into the admin page as a nested tab

**Files:**
- Modify: `frontend/app/admin/page.tsx`

**Interfaces:**
- Consumes: `WeeklyBatchPanel` (Task 7).

- [ ] **Step 1: Import the component**

Add, alongside the existing `import { MarketOutlookPanel } from '@/components/autopilot/MarketOutlookPanel'` line:

```typescript
import { WeeklyBatchPanel } from '@/components/autopilot/WeeklyBatchPanel'
```

- [ ] **Step 2: Nest sub-tabs inside the Outlook tab**

Replace:

```typescript
          <TabsContent value="outlook">
            <div className="space-y-6">
              <MarketOutlookPanel />
              <EngineJournalPanel />
            </div>
          </TabsContent>
```

with:

```typescript
          <TabsContent value="outlook">
            <Tabs defaultValue="sunday" className="space-y-4">
              <TabsList>
                <TabsTrigger value="sunday">Sunday Outlook</TabsTrigger>
                <TabsTrigger value="monday">Monday Batch</TabsTrigger>
              </TabsList>
              <TabsContent value="sunday">
                <div className="space-y-6">
                  <MarketOutlookPanel />
                  <EngineJournalPanel />
                </div>
              </TabsContent>
              <TabsContent value="monday">
                <WeeklyBatchPanel />
              </TabsContent>
            </Tabs>
          </TabsContent>
```

(This nests the same way the existing `portfolio` tab already nests its own `Tabs` — see lines 137–162 of the current file — so no new patterns are introduced.)

- [ ] **Step 3: Verify type-check**

Run: `cd frontend && npx tsc --noEmit`
Expected: no new errors.

- [ ] **Step 4: Commit**

```bash
git add frontend/app/admin/page.tsx
git commit -m "feat(admin): nest Monday Batch under the Outlook tab"
```

---

### Task 9: Manual verification

**Files:** none (verification only)

- [ ] **Step 1: Run the full backend test suite**

Run: `python3 -m pytest tests/ -v 2>&1 | tail -50`
Expected: all tests pass (or the same pre-existing failures as before this branch, if any — compare against a baseline run on `main` if unsure).

- [ ] **Step 2: Start the frontend dev server and the backend API, log in as admin, and visually check the new tab**

Start the backend and frontend per this repo's existing dev-server instructions (check for a project `run`/dev skill or `README-API.md` / `QUICKSTART-API.md` if unfamiliar with the exact commands). Navigate to `/admin`, open the "Outlook" tab, confirm "Sunday Outlook" / "Monday Batch" sub-tabs render, and that "Monday Batch" shows either the empty state (no `WeeklyBatchRun` rows exist yet locally) or real data if a batch run has been persisted to the connected database.

- [ ] **Step 3: Report results**

Summarize: test suite pass/fail counts, whether the UI rendered correctly, and any deviations from this plan discovered during implementation.
