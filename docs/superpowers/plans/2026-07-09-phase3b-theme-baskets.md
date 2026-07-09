# Phase 3B: LLM Theme Baskets + EngineReport Journal — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** LLM-discovered theme baskets (Situational-Awareness reasoning engine, auto-applied with caps) ranked in the Sunday outlook, plus the EngineReport in-app journal that replaces email as the engine's only channel.

**Architecture:** New `execution/themes/` package (discovery/validation/lifecycle) + two Inngest crons feed `ThemeBasket`/`ThemeConstituent` tables; a new outlook pass ranks equal-weight synthetic basket indices into `MarketOutlook.themeRankings`; every mutation and engine event lands in the new `EngineReport` table, surfaced at `GET /api/autopilot/reports` and on the admin tab.

**Tech Stack:** Python 3 / FastAPI / prisma-client-py 0.15 / Inngest 0.5.x / yfinance / native `anthropic` SDK (web_search server tool) / Next.js frontend.

**Spec:** `docs/superpowers/specs/2026-07-09-phase3b-theme-baskets-design.md` — read it before starting any task.

## Global Constraints

- Work on branch `autopilot-phase3b` (create in Task 1).
- Run tests with `python3 -m pytest ...` (bare `python` is not on PATH). The repo has ~76 pre-existing failures on main in the FULL suite — only the test files you touch must be green.
- `prisma migrate dev` is broken (shadow-DB baseline). Hand-write migration SQL; deploys use `python3 -m prisma migrate deploy`. NEVER run migrate dev.
- After editing `db/schema.prisma`, run `python3 -m prisma generate` (regenerates the client used by tests via the real import; tests/conftest.py installs a prisma stub only when the real client is unimportable).
- `requirements.txt` is the ONLY file Railway installs — any new runtime dep goes there.
- Sleeve B control-group contract: nothing in this plan may change Sleeve B inputs. The strategist must never see theme data (Task 12 enforces + tests).
- Never-raise posture: journal writes, alerts, and every theme pass degrade to "no effect + log/journal"; they must never crash a cron or block the outlook.
- Tests NEVER call live LLM/web-search/yfinance/DB. Stub at module seams (imports are function-local everywhere in `execution/` precisely to allow this).
- Prisma Json? columns: bare `None` in create() raises — always OMIT None Json fields (see `store_outlook` for the canonical guard).
- Commit after every task with the message given in its final step. Do not push until the final task.

## File Map (what this plan creates/modifies)

```
db/schema.prisma                                    modify  (3 models + 1 column)
db/migrations/20260709000003_add_theme_baskets_engine_report/migration.sql  create
execution/constants.py                              modify  (Phase 3B block)
execution/reporting.py                              create  (EngineReport writer)
execution/alerts.py                                 rewrite (journal wrapper, async)
execution/research_feed.py                          create  (read-only research bridge)
execution/themes/{__init__,validation,parser,prompts,lifecycle,discovery,delta}.py  create
execution/indicators/theme_strength.py              create
execution/market_data.py                            modify  (fetch_closes_batch)
execution/outlook_service.py                        modify  (themeRankings field)
inngest_app/functions/theme_discovery_monthly.py    create
inngest_app/functions/theme_delta_weekly.py         create
inngest_app/functions/weekly_outlook.py             modify  (theme step + async alerts)
inngest_app/functions/execution_daily.py            modify  (breaker_event, transition-only)
inngest_app/functions/execution_weekly.py           modify  (rebalance_summary)
inngest_app/index.py                                modify  (register 2 crons)
api/routes/autopilot.py                             modify  (reports endpoint + theme fields)
requirements.txt                                    modify  (anthropic)
frontend/types/api.ts                               modify
frontend/lib/... (apiClient + useAdmin hooks)       modify
frontend/components/autopilot/MarketOutlookPanel.tsx  modify (Leading Themes card)
frontend/components/autopilot/EngineJournalPanel.tsx  create
frontend/app/admin/page.tsx                         modify
tests/test_execution_reporting.py                   create
tests/test_execution_alerts.py                      rewrite
tests/test_execution_research_feed.py               create
tests/test_theme_validation.py                      create
tests/test_theme_parser.py                          create
tests/test_theme_prompts.py                         create
tests/test_theme_lifecycle.py                       create
tests/test_theme_discovery.py                       create
tests/test_theme_crons.py                           create
tests/test_execution_theme_strength.py              create
tests/test_execution_strategist.py                  modify  (isolation test)
tests/test_execution_outlook_service.py             modify
tests/test_autopilot_routes.py                      modify
tests/test_execution_daily.py, test_execution_weekly.py  modify
```

---

### Task 1: Schema, migration, seed themes

**Files:**
- Modify: `db/schema.prisma` (after the MarketOutlook model block, ~line 924; and inside MarketOutlook after `sizeStyle`, line 916)
- Create: `db/migrations/20260709000003_add_theme_baskets_engine_report/migration.sql`
- Modify: `execution/constants.py` (append Phase 3B block at end)

**Interfaces:**
- Produces: Prisma models `ThemeBasket`, `ThemeConstituent`, `EngineReport`; `MarketOutlook.themeRankings Json?`; constants `MAX_ACTIVE_THEMES=12`, `MIN_THEME_CONSTITUENTS=5`, `MAX_THEME_CONSTITUENTS=20`, `THEME_ADV_FLOOR_USD`, `THEME_MCAP_FLOOR_USD`, `DELTA_AUTO_APPLY_CONFIDENCE=0.7`, `THEME_ROTATION_MIN_RANK_GAIN=5`, `THEME_HISTORY_WEEKS=12`, `THEME_REASONING_MODEL`, `THEME_DELTA_MODEL`, `THEME_WEB_SEARCH_MAX_USES=8`

- [ ] **Step 1: Create branch**

```bash
cd /Users/tui/dvrg && git checkout -b autopilot-phase3b
```

- [ ] **Step 2: Add models to `db/schema.prisma`**

Inside `model MarketOutlook`, directly under the `sizeStyle` line (916):

```prisma
  themeRankings      Json?    // Phase 3B: {rankings, rotations, missing, history} — Sleeve A only
```

After the MarketOutlook model's closing brace + the Phase 2 comment block header, add:

```prisma
// ── Phase 3B: LLM-discovered theme baskets + engine journal ─────────────────
// Sleeve-A-only signal objects. Theme membership NEVER buys a stock.

model ThemeBasket {
  id             String    @id @default(cuid())
  slug           String    @unique          // "photonics", "gas-turbines"
  name           String
  status         String    @default("active") // "active" | "retired"
  origin         String    // "seed" | "engine"
  thesis         String    // demand-chain reasoning from the monthly pass
  confidence     Float     @default(0.5)
  metadata       Json?     // {binding_constraint, consensus_gap_notes, leading_indicators}
  lastReasonedAt DateTime?
  createdAt      DateTime  @default(now())
  retiredAt      DateTime?
  constituents   ThemeConstituent[]
}

model ThemeConstituent {
  id         String    @id @default(cuid())
  themeId    String
  theme      ThemeBasket @relation(fields: [themeId], references: [id], onDelete: Cascade)
  ticker     String
  exposure   String    // stated exposure, one sentence with evidence
  confidence Float
  status     String    @default("active") // "active" | "removed"
  source     String    // "reasoning" | "delta"
  validation Json?     // {adv, market_cap, price, validated_at}
  addedAt    DateTime  @default(now())
  removedAt  DateTime?

  @@unique([themeId, ticker])
}

model EngineReport {
  id        String   @id @default(cuid())
  createdAt DateTime @default(now())
  type      String   // theme_proposal | membership_change | theme_retired |
                     // validation_failure | engine_failure | rebalance_summary | breaker_event
  severity  String   // "info" | "warning" | "critical"
  source    String   // originating cron/module
  title     String
  body      Json

  @@index([createdAt])
  @@index([type])
}
```

- [ ] **Step 3: Write the migration SQL**

Create `db/migrations/20260709000003_add_theme_baskets_engine_report/migration.sql`:

```sql
-- Phase 3B: theme baskets + engine journal. Additive; themeRankings nullable.

CREATE TABLE "ThemeBasket" (
    "id" TEXT NOT NULL,
    "slug" TEXT NOT NULL,
    "name" TEXT NOT NULL,
    "status" TEXT NOT NULL DEFAULT 'active',
    "origin" TEXT NOT NULL,
    "thesis" TEXT NOT NULL,
    "confidence" DOUBLE PRECISION NOT NULL DEFAULT 0.5,
    "metadata" JSONB,
    "lastReasonedAt" TIMESTAMP(3),
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "retiredAt" TIMESTAMP(3),
    CONSTRAINT "ThemeBasket_pkey" PRIMARY KEY ("id")
);
CREATE UNIQUE INDEX "ThemeBasket_slug_key" ON "ThemeBasket"("slug");

CREATE TABLE "ThemeConstituent" (
    "id" TEXT NOT NULL,
    "themeId" TEXT NOT NULL,
    "ticker" TEXT NOT NULL,
    "exposure" TEXT NOT NULL,
    "confidence" DOUBLE PRECISION NOT NULL,
    "status" TEXT NOT NULL DEFAULT 'active',
    "source" TEXT NOT NULL,
    "validation" JSONB,
    "addedAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "removedAt" TIMESTAMP(3),
    CONSTRAINT "ThemeConstituent_pkey" PRIMARY KEY ("id")
);
CREATE UNIQUE INDEX "ThemeConstituent_themeId_ticker_key" ON "ThemeConstituent"("themeId", "ticker");
ALTER TABLE "ThemeConstituent" ADD CONSTRAINT "ThemeConstituent_themeId_fkey"
    FOREIGN KEY ("themeId") REFERENCES "ThemeBasket"("id") ON DELETE CASCADE ON UPDATE CASCADE;

CREATE TABLE "EngineReport" (
    "id" TEXT NOT NULL,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "type" TEXT NOT NULL,
    "severity" TEXT NOT NULL,
    "source" TEXT NOT NULL,
    "title" TEXT NOT NULL,
    "body" JSONB NOT NULL,
    CONSTRAINT "EngineReport_pkey" PRIMARY KEY ("id")
);
CREATE INDEX "EngineReport_createdAt_idx" ON "EngineReport"("createdAt");
CREATE INDEX "EngineReport_type_idx" ON "EngineReport"("type");

ALTER TABLE "MarketOutlook" ADD COLUMN "themeRankings" JSONB;

-- Seed the six owner niches. origin='seed', no constituents — the first
-- monthly reasoning pass populates them. Seeds compete equally thereafter.
INSERT INTO "ThemeBasket" ("id", "slug", "name", "status", "origin", "thesis", "confidence") VALUES
('seed_photonics',    'photonics',    'Photonics & Optical Interconnect', 'active', 'seed', 'Seed hypothesis: networking/interconnect is a scaling bottleneck; optical I/O demand compounds with cluster size.', 0.5),
('seed_memory_hbm',   'memory-hbm',   'Memory & HBM',                     'active', 'seed', 'Seed hypothesis: HBM demand is the near-term binding constraint on accelerator output.', 0.5),
('seed_data_centers', 'data-centers', 'Data Center Buildout',             'active', 'seed', 'Seed hypothesis: datacenter construction/cooling/REITs re-rate as cluster capex scales ~0.5 OOM/yr.', 0.5),
('seed_dc_energy',    'dc-energy',    'Energy for Data Centers',          'active', 'seed', 'Seed hypothesis: power is the single biggest supply-side constraint; generation and grid beneficiaries re-rate.', 0.5),
('seed_space',        'space',        'Space',                            'active', 'seed', 'Seed hypothesis: launch-cost decline compounds into new space infrastructure demand.', 0.5),
('seed_chips',        'chips',        'Semiconductors & Fab Chain',       'active', 'seed', 'Seed hypothesis: AI chip demand exceeds leading-edge capacity by 2028; fab chain must expand at multiples of historical pace.', 0.5);
```

- [ ] **Step 4: Regenerate the prisma client and validate**

```bash
cd /Users/tui/dvrg && python3 -m prisma validate --schema db/schema.prisma && python3 -m prisma generate --schema db/schema.prisma
```

Expected: `The schema at db/schema.prisma is valid` then generation success. (Do NOT run `migrate deploy` now — production migration is a go-live step, listed in the final checklist.)

- [ ] **Step 5: Append Phase 3B constants to `execution/constants.py`**

```python
# ── Phase 3B: LLM-discovered theme baskets (Sleeve A signal layer 3) ─────────
# Theme membership NEVER buys a stock — themes pick hunting grounds only.
MAX_ACTIVE_THEMES = 12
MIN_THEME_CONSTITUENTS = 5          # validated names required to activate/rank
MAX_THEME_CONSTITUENTS = 20         # bounds the Sunday batch download (≤240 tickers)
THEME_ADV_FLOOR_USD = 1_000_000.0   # avg daily dollar volume floor
THEME_MCAP_FLOOR_USD = 100_000_000.0
DELTA_AUTO_APPLY_CONFIDENCE = 0.7   # weekly delta below this journals but doesn't apply
THEME_ROTATION_MIN_RANK_GAIN = 5    # same scale as industries
THEME_HISTORY_WEEKS = 12            # sparkline series length (current membership)
THEME_REASONING_MODEL = "claude-sonnet-5"
THEME_DELTA_MODEL = "claude-haiku-4-5"
THEME_WEB_SEARCH_MAX_USES = 8
```

- [ ] **Step 6: Run the schema-adjacent tests to confirm nothing broke**

```bash
python3 -m pytest tests/test_execution_outlook_service.py tests/test_autopilot_routes.py -q
```

Expected: PASS (no code touched yet — this is a canary for the regenerated client).

- [ ] **Step 7: Commit**

```bash
git add db/schema.prisma db/migrations/20260709000003_add_theme_baskets_engine_report execution/constants.py
git commit -m "feat(autopilot): ThemeBasket/ThemeConstituent/EngineReport schema + seed themes (3B)"
```

---

### Task 2: `execution/reporting.py` — the EngineReport writer

**Files:**
- Create: `execution/reporting.py`
- Test: `tests/test_execution_reporting.py`

**Interfaces:**
- Produces: `async write_report(report_type: str, severity: str, source: str, title: str, body: dict, db=None) -> Optional[str]` — returns the new row id, or None on any failure (never raises). Also constants `REPORT_TYPES: frozenset`, `SEVERITIES: frozenset`.
- Consumes: `api.lib.db.get_db` (lazily, only when `db` arg is None), `prisma.Json`.

- [ ] **Step 1: Write the failing tests**

`tests/test_execution_reporting.py`:

```python
"""EngineReport writer: never raises, always JSON-wraps body."""
import pytest

from execution.reporting import REPORT_TYPES, SEVERITIES, write_report


class _StubEngineReport:
    def __init__(self, fail=False):
        self.fail = fail
        self.created = []

    async def create(self, data):
        if self.fail:
            raise RuntimeError("db down")
        self.created.append(data)
        class Row: id = "rep_1"
        return Row()


class _StubDb:
    def __init__(self, fail=False):
        self.enginereport = _StubEngineReport(fail=fail)


@pytest.mark.asyncio
async def test_write_report_creates_row_and_returns_id():
    db = _StubDb()
    rid = await write_report("engine_failure", "critical", "unit-test",
                             "something broke", {"detail": "boom"}, db=db)
    assert rid == "rep_1"
    data = db.enginereport.created[0]
    assert data["type"] == "engine_failure"
    assert data["severity"] == "critical"
    assert data["source"] == "unit-test"
    assert data["title"] == "something broke"


@pytest.mark.asyncio
async def test_write_report_never_raises_on_db_failure():
    rid = await write_report("engine_failure", "critical", "unit-test",
                             "boom", {}, db=_StubDb(fail=True))
    assert rid is None


@pytest.mark.asyncio
async def test_write_report_tolerates_unknown_type_and_none_body():
    db = _StubDb()
    rid = await write_report("mystery_type", "loud", "unit-test", "t", None, db=db)
    assert rid == "rep_1"  # soft validation: log-and-write, never block


def test_report_type_vocabulary_matches_spec():
    assert REPORT_TYPES == frozenset({
        "theme_proposal", "membership_change", "theme_retired",
        "validation_failure", "engine_failure", "rebalance_summary",
        "breaker_event",
    })
    assert SEVERITIES == frozenset({"info", "warning", "critical"})
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
python3 -m pytest tests/test_execution_reporting.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'execution.reporting'`

- [ ] **Step 3: Implement `execution/reporting.py`**

```python
"""EngineReport journal writer — the engine's only channel to the owner.

Never raises: a broken journal must never block the engine (the engine's
failure posture is inaction + report, and inaction still happened). Unknown
types/severities are logged and written as-is — the journal is append-only
and freeform enough to absorb drift.
"""
import logging
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

REPORT_TYPES = frozenset({
    "theme_proposal", "membership_change", "theme_retired",
    "validation_failure", "engine_failure", "rebalance_summary",
    "breaker_event",
})
SEVERITIES = frozenset({"info", "warning", "critical"})


async def write_report(
    report_type: str,
    severity: str,
    source: str,
    title: str,
    body: Optional[Dict[str, Any]],
    db=None,
) -> Optional[str]:
    """Append one EngineReport row. Returns the row id, or None on failure."""
    try:
        if report_type not in REPORT_TYPES:
            logger.warning("EngineReport: unknown type %r (writing anyway)", report_type)
        if severity not in SEVERITIES:
            logger.warning("EngineReport: unknown severity %r (writing anyway)", severity)
        from prisma import Json  # noqa: PLC0415 — runtime-only dependency

        if db is None:
            from api.lib.db import get_db  # noqa: PLC0415
            db = await get_db()
        row = await db.enginereport.create(data={
            "type": report_type,
            "severity": severity,
            "source": source,
            "title": title,
            "body": Json(body or {}),
        })
        return row.id
    except Exception:
        logger.exception("EngineReport write failed: %s — %s", report_type, title)
        return None
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
python3 -m pytest tests/test_execution_reporting.py -v
```

Expected: 4 PASS. If `prisma.Json` import fails in the test env, the conftest stub provides it — check `tests/conftest.py` before changing anything.

- [ ] **Step 5: Commit**

```bash
git add execution/reporting.py tests/test_execution_reporting.py
git commit -m "feat(autopilot): EngineReport journal writer (never-raise)"
```

---

### Task 3: `alerts.py` → journal (async), update every call site

**Files:**
- Rewrite: `execution/alerts.py`
- Modify: `inngest_app/functions/weekly_outlook.py` (`compute_extended_signals` + its caller, and the two other `send_failure_alert` uses if present)
- Modify: `inngest_app/functions/execution_daily.py`, `inngest_app/functions/execution_weekly.py` (await the now-async alert)
- Test: rewrite `tests/test_execution_alerts.py`; update any test touching `compute_extended_signals` or stubbing `send_failure_alert`

**Interfaces:**
- Produces: `async send_failure_alert(subject: str, body: str, source: str = "engine") -> Dict[str, str]` — status `"journaled"` or `"error"`. Email path DELETED.
- Produces: `compute_extended_signals(closes_extra) -> Tuple[Dict[str, Any], List[Tuple[str, str]]]` (was `(closes_extra, alert)` returning dict) — now returns `(out, failures)`; the async caller journals each failure.
- Consumes: `execution.reporting.write_report` (Task 2).

- [ ] **Step 1: Find every call site first**

```bash
grep -rn "send_failure_alert\|compute_extended_signals" --include="*.py" /Users/tui/dvrg/execution /Users/tui/dvrg/inngest_app /Users/tui/dvrg/tests
```

Expected call sites: `weekly_outlook.py` (compute_extended_signals + caller), `execution_daily.py` (~3: on_failure handler, reconcile-frozen, breaker trip), `execution_weekly.py` (~1: unfilled orders), plus tests. Every production call site becomes `await send_failure_alert(...)` — all of them already live inside `async def` step functions EXCEPT the sync helper `compute_extended_signals`, which is why its signature changes to return failures instead of calling the alert itself.

- [ ] **Step 2: Write the failing tests**

Replace `tests/test_execution_alerts.py` with:

```python
"""Failure alerts land in the EngineReport journal (email path deleted)."""
import pytest

import execution.alerts as alerts


@pytest.mark.asyncio
async def test_alert_writes_engine_failure_report(monkeypatch):
    calls = {}

    async def fake_write_report(report_type, severity, source, title, body, db=None):
        calls.update(type=report_type, severity=severity, source=source,
                     title=title, body=body)
        return "rep_1"

    monkeypatch.setattr(alerts, "write_report", fake_write_report)
    result = await alerts.send_failure_alert("subj", "detail", source="unit")
    assert result == {"status": "journaled"}
    assert calls["type"] == "engine_failure"
    assert calls["severity"] == "critical"
    assert calls["source"] == "unit"
    assert calls["title"] == "subj"
    assert calls["body"] == {"detail": "detail"}


@pytest.mark.asyncio
async def test_alert_reports_error_when_journal_fails(monkeypatch):
    async def fake_write_report(*a, **k):
        return None

    monkeypatch.setattr(alerts, "write_report", fake_write_report)
    result = await alerts.send_failure_alert("subj", "detail")
    assert result == {"status": "error"}


def test_resend_is_gone():
    import inspect
    src = inspect.getsource(alerts)
    assert "resend" not in src
    assert "RESEND_API_KEY" not in src
```

- [ ] **Step 3: Run tests to verify they fail**

```bash
python3 -m pytest tests/test_execution_alerts.py -v
```

Expected: FAIL — old sync signature / resend still present.

- [ ] **Step 4: Rewrite `execution/alerts.py`**

```python
"""Failure alerts for the execution layer — journal-only (Phase 3B).

Email is dead: alerts land as EngineReport rows of type "engine_failure".
NEVER raises — a broken journal must not break the engine (the failure
posture is inaction + report, and inaction still happened; write_report
itself already swallows all errors).
"""
import logging
from typing import Dict

from execution.reporting import write_report

logger = logging.getLogger(__name__)


async def send_failure_alert(subject: str, body: str, source: str = "engine") -> Dict[str, str]:
    logger.warning("Autopilot alert: %s — %s", subject, body)
    report_id = await write_report(
        "engine_failure", "critical", source, subject, {"detail": body}
    )
    return {"status": "journaled" if report_id else "error"}
```

- [ ] **Step 5: Refactor `compute_extended_signals` in `weekly_outlook.py`**

Replace the existing function (it currently takes `(closes_extra, alert)`) with:

```python
def compute_extended_signals(closes_extra) -> "tuple[Dict[str, Any], list]":
    """Phase 3A industry + size/style passes.

    Each pass degrades independently to None. Returns (out, failures) where
    failures is a list of (subject, detail) for the async caller to journal —
    this helper stays sync/pure so it remains unit-testable.
    """
    from execution.indicators.industry_strength import rank_industries  # noqa: PLC0415
    from execution.indicators.size_style import compute_size_style  # noqa: PLC0415

    out: Dict[str, Any] = {"industry": None, "size_style": None}
    failures: list = []
    try:
        out["industry"] = rank_industries(closes_extra)
    except Exception as exc:
        logger.exception("Outlook industry pass failed")
        failures.append(("Outlook industry pass failed", f"{type(exc).__name__}: {exc}"))
    try:
        out["size_style"] = compute_size_style(closes_extra)
    except Exception as exc:
        logger.exception("Outlook size/style pass failed")
        failures.append(("Outlook size/style pass failed", f"{type(exc).__name__}: {exc}"))
    return out, failures
```

In `compute_indicators` (inside the Inngest function), replace
`extended = compute_extended_signals(closes_extra, send_failure_alert)` with:

```python
            extended, ext_failures = compute_extended_signals(closes_extra)
            for subject, detail in ext_failures:
                await send_failure_alert(subject, detail, source="weekly_market_outlook")
```

- [ ] **Step 6: Await the alert at every other call site**

In `execution_daily.py` and `execution_weekly.py`, every `send_failure_alert(...)` becomes `await send_failure_alert(..., source="execution_daily")` (or `"execution_weekly"`). All sites are inside `async def` functions (including the `on_failure` handler) — verify with the Step 1 grep output. Do NOT change any other logic in these files (Task 15 adds the typed journal entries).

- [ ] **Step 7: Fix the tests that stubbed the old sync alert**

```bash
python3 -m pytest tests/test_execution_alerts.py tests/test_execution_daily.py tests/test_execution_weekly.py tests/test_execution_outlook_service.py -q 2>&1 | tail -20
```

Update failing stubs: monkeypatched `send_failure_alert` fakes must become `async def` fakes; tests calling `compute_extended_signals(closes, alert)` must call `compute_extended_signals(closes)` and unpack `(out, failures)` — assert on `failures` instead of alert-callable capture. Re-run until green.

- [ ] **Step 8: Commit**

```bash
git add execution/alerts.py inngest_app/functions tests/
git commit -m "feat(autopilot): failure alerts write EngineReport journal — email path deleted"
```

---

### Task 4: `execution/research_feed.py` — read-only research bridge

**Files:**
- Create: `execution/research_feed.py`
- Test: `tests/test_execution_research_feed.py`

**Interfaces:**
- Produces: `async get_research_context(db) -> Dict[str, list]` returning `{"watchlist": [tickers], "supply_chain": [names], "news_entities": [names]}` — every list possibly empty, never raises.
- This is the ONLY module in `execution/` allowed to read research-flow tables (`Watchlist`, `StockResult`) — the isolation rule from the original execution-layer spec.
- Consumed by: Task 9 (`discovery.gather_monthly_context`).

- [ ] **Step 1: Confirm the model field names**

```bash
grep -n "model StockResult" -A 30 /Users/tui/dvrg/db/schema.prisma | grep -n "createdAt\|fullOutput\|ticker"
```

Expected: `fullOutput Json? @map("full_output")` and a `createdAt` (or similar timestamp) field — if the timestamp field differs, use the actual name in the `order=` below.

- [ ] **Step 2: Write the failing tests**

`tests/test_execution_research_feed.py`:

```python
"""research_feed: defensive, read-only, schema-drift-proof."""
import pytest

from execution.research_feed import _collect_names_by_keys, get_research_context


def test_collector_finds_nested_supply_chain_keys():
    blob = {"agents": {"fundamentalist": {
        "customers": ["NVDA", "Super Micro"], "suppliers": ["TSMC"],
        "other": {"key_suppliers": ["SK Hynix"]},
    }}}
    out: list = []
    _collect_names_by_keys(blob, ("customers", "suppliers", "key_customers", "key_suppliers"), out)
    assert set(out) == {"NVDA", "Super Micro", "TSMC", "SK Hynix"}


def test_collector_ignores_non_list_and_non_str_values():
    out: list = []
    _collect_names_by_keys({"customers": "NVDA", "suppliers": [1, {"x": 1}, "AMD"]},
                           ("customers", "suppliers"), out)
    assert out == ["AMD"]


class _Table:
    def __init__(self, rows=None, fail=False):
        self._rows, self._fail = rows or [], fail

    async def find_many(self, **kwargs):
        if self._fail:
            raise RuntimeError("db down")
        return self._rows


class _Row:
    def __init__(self, **kw):
        self.__dict__.update(kw)


@pytest.mark.asyncio
async def test_context_is_all_empty_on_db_failure():
    class Db:
        watchlist = _Table(fail=True)
        stockresult = _Table(fail=True)
    ctx = await get_research_context(Db())
    assert ctx == {"watchlist": [], "supply_chain": [], "news_entities": []}


@pytest.mark.asyncio
async def test_context_dedupes_and_uppercases_watchlist():
    class Db:
        watchlist = _Table(rows=[_Row(ticker="aehr"), _Row(ticker="AEHR"), _Row(ticker="VIAV")])
        stockresult = _Table(rows=[_Row(fullOutput=None)])
    ctx = await get_research_context(Db())
    assert ctx["watchlist"] == ["AEHR", "VIAV"]
```

- [ ] **Step 3: Run tests to verify they fail**

```bash
python3 -m pytest tests/test_execution_research_feed.py -v
```

Expected: FAIL — module not found.

- [ ] **Step 4: Implement `execution/research_feed.py`**

```python
"""Read-only bridge from the execution layer to research artifacts.

The ONLY module in execution/ allowed to touch research-flow tables
(Watchlist, StockResult) — the isolation rule from the execution-layer spec.
Everything is best-effort: any failure or schema drift returns empty lists,
never raises. Extraction walks fullOutput recursively by key name so the
known formatter/schema drift (see manager-formatter-schema-drift) cannot
break it — unknown shapes just yield nothing.
"""
import logging
from typing import Any, Dict, List, Sequence

logger = logging.getLogger(__name__)

_SUPPLY_CHAIN_KEYS = ("customers", "suppliers", "key_customers", "key_suppliers")
_NEWS_ENTITY_KEYS = ("entities", "related_companies", "tickers_mentioned", "companies_mentioned")


def _collect_names_by_keys(obj: Any, keys: Sequence[str], out: List[str]) -> None:
    """Recursively collect string-list values under any of `keys`."""
    if isinstance(obj, dict):
        for k, v in obj.items():
            if isinstance(k, str) and k.lower() in keys and isinstance(v, list):
                out.extend(x.strip() for x in v if isinstance(x, str) and x.strip())
            else:
                _collect_names_by_keys(v, keys, out)
    elif isinstance(obj, list):
        for item in obj:
            _collect_names_by_keys(item, keys, out)


def _dedupe(items: List[str], limit: int) -> List[str]:
    seen, out = set(), []
    for x in items:
        key = x.upper()
        if key not in seen:
            seen.add(key)
            out.append(x)
        if len(out) >= limit:
            break
    return out


async def get_research_context(db, max_reports: int = 25, max_names: int = 60) -> Dict[str, List[str]]:
    watchlist: List[str] = []
    supply_chain: List[str] = []
    news_entities: List[str] = []

    try:
        rows = await db.watchlist.find_many(take=200, order={"addedAt": "desc"})
        watchlist = _dedupe([(r.ticker or "").upper() for r in rows if getattr(r, "ticker", None)], 200)
    except Exception:
        logger.exception("research_feed: watchlist read failed")

    try:
        reports = await db.stockresult.find_many(take=max_reports, order={"createdAt": "desc"})
        for row in reports:
            blob = getattr(row, "fullOutput", None)
            if not blob:
                continue
            _collect_names_by_keys(blob, _SUPPLY_CHAIN_KEYS, supply_chain)
            _collect_names_by_keys(blob, _NEWS_ENTITY_KEYS, news_entities)
    except Exception:
        logger.exception("research_feed: stock_results read failed")

    return {
        "watchlist": watchlist,
        "supply_chain": _dedupe(supply_chain, max_names),
        "news_entities": _dedupe(news_entities, max_names),
    }
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
python3 -m pytest tests/test_execution_research_feed.py -v
```

Expected: 4 PASS.

- [ ] **Step 6: Commit**

```bash
git add execution/research_feed.py tests/test_execution_research_feed.py
git commit -m "feat(autopilot): read-only research_feed bridge for theme discovery grounding"
```

---

### Task 5: `execution/themes/validation.py` — data validates every symbol

**Files:**
- Create: `execution/themes/__init__.py` (empty) and `execution/themes/validation.py`
- Test: `tests/test_theme_validation.py`

**Interfaces:**
- Produces: `validate_ticker(ticker: str) -> Optional[Dict]` — None on ANY gate failure, else `{"adv", "market_cap", "price", "validated_at"}`; `validate_tickers(tickers: Iterable[str]) -> Dict[str, Optional[Dict]]` (uppercased, deduped keys). Sync (yfinance is sync; callers run it inside their own Inngest step like every other fetch in this codebase).
- Consumes: `THEME_ADV_FLOOR_USD`, `THEME_MCAP_FLOOR_USD` from constants.

- [ ] **Step 1: Write the failing tests**

`tests/test_theme_validation.py`:

```python
"""Ticker validation gates: hallucinated/illiquid/small names die here."""
import sys
import types

import pandas as pd
import pytest


def _install_yf_stub(monkeypatch, hist=None, mcap=None, raise_on_init=False):
    stub = types.ModuleType("yfinance")

    class FakeTicker:
        def __init__(self, symbol):
            if raise_on_init:
                raise RuntimeError("no such ticker")
            self.fast_info = {"market_cap": mcap}

        def history(self, period):
            return hist

    stub.Ticker = FakeTicker
    monkeypatch.setitem(sys.modules, "yfinance", stub)


def _good_history(days=70, price=50.0, volume=1_000_000):
    idx = pd.date_range("2026-03-01", periods=days, freq="B")
    return pd.DataFrame({"Close": [price] * days, "Volume": [volume] * days}, index=idx)


def test_valid_ticker_passes(monkeypatch):
    _install_yf_stub(monkeypatch, hist=_good_history(), mcap=2_000_000_000)
    from execution.themes.validation import validate_ticker
    result = validate_ticker("aehr")
    assert result is not None
    assert result["market_cap"] == 2_000_000_000
    assert result["adv"] == pytest.approx(50.0 * 1_000_000)
    assert result["price"] == 50.0


def test_unresolvable_ticker_fails(monkeypatch):
    _install_yf_stub(monkeypatch, raise_on_init=True)
    from execution.themes.validation import validate_ticker
    assert validate_ticker("DRAM") is None


def test_empty_history_fails(monkeypatch):
    _install_yf_stub(monkeypatch, hist=pd.DataFrame(), mcap=2_000_000_000)
    from execution.themes.validation import validate_ticker
    assert validate_ticker("XXXX") is None


def test_low_adv_fails(monkeypatch):
    _install_yf_stub(monkeypatch, hist=_good_history(price=2.0, volume=1000), mcap=2_000_000_000)
    from execution.themes.validation import validate_ticker
    assert validate_ticker("TINY") is None


def test_small_mcap_fails(monkeypatch):
    _install_yf_stub(monkeypatch, hist=_good_history(), mcap=50_000_000)
    from execution.themes.validation import validate_ticker
    assert validate_ticker("MICRO") is None


def test_validate_tickers_dedupes_and_uppercases(monkeypatch):
    _install_yf_stub(monkeypatch, hist=_good_history(), mcap=2_000_000_000)
    from execution.themes.validation import validate_tickers
    out = validate_tickers(["aehr", "AEHR", "viav"])
    assert set(out) == {"AEHR", "VIAV"}
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
python3 -m pytest tests/test_theme_validation.py -v
```

Expected: FAIL — module not found.

- [ ] **Step 3: Implement `execution/themes/validation.py`** (and `touch execution/themes/__init__.py`)

```python
"""yfinance validation for proposed theme constituents.

LLM ticker lists hallucinate; stale/renamed symbols exist. Every proposed
symbol passes these gates before it can enter a basket: resolvable, real
price history, ADV floor, market-cap floor. None means REJECT — the caller
journals it; nothing is ever guessed.
"""
import logging
from datetime import datetime, timezone
from typing import Dict, Iterable, Optional

from execution.constants import THEME_ADV_FLOOR_USD, THEME_MCAP_FLOOR_USD

logger = logging.getLogger(__name__)

_MIN_HISTORY_DAYS = 20  # a listing younger than ~a month can't clear ADV math


def validate_ticker(ticker: str) -> Optional[Dict]:
    import yfinance as yf  # noqa: PLC0415 — runtime-only dependency

    try:
        t = yf.Ticker(ticker)
        hist = t.history(period="3mo")
        if hist is None or getattr(hist, "empty", True) or "Close" not in hist:
            return None
        closes = hist["Close"].dropna()
        if len(closes) < _MIN_HISTORY_DAYS:
            return None
        volumes = hist["Volume"].reindex(closes.index).fillna(0) if "Volume" in hist else None
        if volumes is None:
            return None
        adv = float((closes * volumes).tail(63).mean())
        if adv < THEME_ADV_FLOOR_USD:
            return None

        mcap = None
        try:
            fast = getattr(t, "fast_info", None)
            if fast is not None:
                mcap = fast.get("market_cap") if hasattr(fast, "get") else getattr(fast, "market_cap", None)
        except Exception:
            mcap = None
        if not mcap:
            return None  # no cap data → cannot clear the floor → reject
        if float(mcap) < THEME_MCAP_FLOOR_USD:
            return None

        return {
            "adv": round(adv, 2),
            "market_cap": float(mcap),
            "price": float(closes.iloc[-1]),
            "validated_at": datetime.now(timezone.utc).isoformat(),
        }
    except Exception:
        logger.warning("theme validation error for %s", ticker, exc_info=True)
        return None


def validate_tickers(tickers: Iterable[str]) -> Dict[str, Optional[Dict]]:
    unique = list(dict.fromkeys(t.strip().upper() for t in tickers if t and t.strip()))
    return {t: validate_ticker(t) for t in unique}
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
python3 -m pytest tests/test_theme_validation.py -v
```

Expected: 6 PASS.

- [ ] **Step 5: Commit**

```bash
git add execution/themes tests/test_theme_validation.py
git commit -m "feat(autopilot): theme constituent validation gates (ADV/mcap/resolvability)"
```

---

### Task 6: `execution/themes/parser.py` — strict, skip-don't-guess parsing

**Files:**
- Create: `execution/themes/parser.py`
- Test: `tests/test_theme_parser.py`

**Interfaces:**
- Produces:
  - `parse_monthly_response(text: str) -> {"themes": [ThemeProposal], "skipped": [str]}` where ThemeProposal = `{"slug", "name", "action" ("add"|"keep"|"retire"), "thesis", "confidence" (float 0-1), "metadata" (dict), "constituents": [{"ticker","exposure","confidence"}]}`
  - `parse_delta_response(text: str) -> {"themes": [{"slug", "add": [constituent], "remove": [{"ticker","reason","confidence"}]}], "skipped": [str]}`
  - `ThemeParseError` — raised only when NO JSON object can be extracted at all (whole-response failure; item-level problems are skipped + listed).
- Consumed by: Task 9 discovery/delta.

- [ ] **Step 1: Write the failing tests**

`tests/test_theme_parser.py`:

```python
"""LLM output parsing: manager-schema-drift lesson — skip, never guess."""
import pytest

from execution.themes.parser import (
    ThemeParseError,
    parse_delta_response,
    parse_monthly_response,
)

GOOD_MONTHLY = """Here is my analysis.
```json
{"themes": [
  {"slug": "gas-turbines", "name": "Gas Turbines & Generation", "action": "add",
   "thesis": "Power is the binding constraint.", "confidence": 0.8,
   "metadata": {"binding_constraint": "turbine lead times"},
   "constituents": [
     {"ticker": "GEV", "exposure": "Gas turbine OEM", "confidence": 0.9},
     {"ticker": "bad ticker!!", "exposure": "x", "confidence": 0.9},
     {"ticker": "PSIX", "exposure": "Gensets for DC power", "confidence": 0.7}
   ]},
  {"slug": "photonics", "action": "keep", "name": "Photonics",
   "thesis": "Optical I/O bottleneck.", "confidence": 0.75, "constituents": []},
  {"slug": "Bad Slug", "action": "add", "name": "x", "thesis": "x",
   "confidence": 0.9, "constituents": []},
  {"slug": "space", "action": "hold", "name": "Space", "thesis": "x",
   "confidence": 0.5, "constituents": []},
  {"slug": "memory-hbm", "action": "retire", "name": "Memory", "thesis": "priced in",
   "confidence": "very high", "constituents": []}
]}
```"""


def test_monthly_happy_path_and_item_skips():
    out = parse_monthly_response(GOOD_MONTHLY)
    slugs = [t["slug"] for t in out["themes"]]
    assert slugs == ["gas-turbines", "photonics"]
    gt = out["themes"][0]
    assert [c["ticker"] for c in gt["constituents"]] == ["GEV", "PSIX"]
    # 3 skips: Bad Slug, invalid action "hold", non-float confidence
    assert len(out["skipped"]) >= 3


def test_monthly_no_json_raises():
    with pytest.raises(ThemeParseError):
        parse_monthly_response("I could not complete the analysis, sorry.")


def test_monthly_missing_required_field_skips_theme():
    out = parse_monthly_response('{"themes": [{"slug": "x-theme", "action": "add"}]}')
    assert out["themes"] == []
    assert len(out["skipped"]) == 1


def test_delta_parses_adds_and_removes():
    raw = ('{"themes": [{"slug": "photonics", '
           '"add": [{"ticker": "lasr", "exposure": "Laser subsystems", "confidence": 0.8}], '
           '"remove": [{"ticker": "VIAV", "reason": "exposure now immaterial", "confidence": 0.9}]}]}')
    out = parse_delta_response(raw)
    theme = out["themes"][0]
    assert theme["add"][0]["ticker"] == "LASR"
    assert theme["remove"][0]["ticker"] == "VIAV"


def test_confidence_clamped_to_unit_interval():
    raw = ('{"themes": [{"slug": "chips", "name": "Chips", "action": "keep", '
           '"thesis": "t", "confidence": 1.7, "constituents": []}]}')
    out = parse_monthly_response(raw)
    assert out["themes"][0]["confidence"] == 1.0
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
python3 -m pytest tests/test_theme_parser.py -v
```

Expected: FAIL — module not found.

- [ ] **Step 3: Implement `execution/themes/parser.py`**

```python
"""Strict parsing of theme-discovery LLM output.

Posture (manager-schema-drift lesson): unknown fields are ignored; any item
missing a required field or failing shape checks is SKIPPED and listed in
"skipped" with a reason — never a crash, never a silent guess. Only a
response with no extractable JSON at all raises ThemeParseError.
"""
import json
import logging
import re
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

VALID_ACTIONS = {"add", "keep", "retire"}
_SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9-]{1,40}$")
_TICKER_RE = re.compile(r"^[A-Z][A-Z0-9.\-]{0,9}$")


class ThemeParseError(Exception):
    """No JSON object could be extracted from the response."""


def _extract_json(text: str) -> Dict[str, Any]:
    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    candidate = fenced.group(1) if fenced else None
    if candidate is None:
        start, end = text.find("{"), text.rfind("}")
        if start == -1 or end <= start:
            raise ThemeParseError("no JSON object in response")
        candidate = text[start:end + 1]
    try:
        obj = json.loads(candidate)
    except json.JSONDecodeError as exc:
        raise ThemeParseError(f"unparseable JSON: {exc}") from exc
    if not isinstance(obj, dict):
        raise ThemeParseError("top-level JSON is not an object")
    return obj


def _clamped_confidence(value: Any) -> Optional[float]:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return max(0.0, min(1.0, float(value)))


def _parse_constituent(raw: Any, skipped: List[str], context: str) -> Optional[Dict[str, Any]]:
    if not isinstance(raw, dict):
        skipped.append(f"{context}: constituent not an object")
        return None
    ticker = str(raw.get("ticker", "")).strip().upper()
    exposure = raw.get("exposure")
    confidence = _clamped_confidence(raw.get("confidence"))
    if not _TICKER_RE.match(ticker):
        skipped.append(f"{context}: invalid ticker {raw.get('ticker')!r}")
        return None
    if not isinstance(exposure, str) or not exposure.strip():
        skipped.append(f"{context}/{ticker}: missing exposure")
        return None
    if confidence is None:
        skipped.append(f"{context}/{ticker}: invalid confidence")
        return None
    return {"ticker": ticker, "exposure": exposure.strip(), "confidence": confidence}


def parse_monthly_response(text: str) -> Dict[str, Any]:
    obj = _extract_json(text)
    themes: List[Dict[str, Any]] = []
    skipped: List[str] = []
    for raw in obj.get("themes") or []:
        if not isinstance(raw, dict):
            skipped.append("theme entry not an object")
            continue
        slug = str(raw.get("slug", "")).strip()
        action = str(raw.get("action", "")).strip().lower()
        name = raw.get("name")
        thesis = raw.get("thesis")
        confidence = _clamped_confidence(raw.get("confidence"))
        if not _SLUG_RE.match(slug):
            skipped.append(f"invalid slug {raw.get('slug')!r}")
            continue
        if action not in VALID_ACTIONS:
            skipped.append(f"{slug}: invalid action {raw.get('action')!r}")
            continue
        if not isinstance(name, str) or not name.strip() or not isinstance(thesis, str) or not thesis.strip():
            skipped.append(f"{slug}: missing name/thesis")
            continue
        if confidence is None:
            skipped.append(f"{slug}: invalid confidence")
            continue
        constituents = []
        for c in raw.get("constituents") or []:
            parsed = _parse_constituent(c, skipped, slug)
            if parsed is not None:
                constituents.append(parsed)
        metadata = raw.get("metadata") if isinstance(raw.get("metadata"), dict) else {}
        themes.append({
            "slug": slug, "name": name.strip(), "action": action,
            "thesis": thesis.strip(), "confidence": confidence,
            "metadata": metadata, "constituents": constituents,
        })
    return {"themes": themes, "skipped": skipped}


def parse_delta_response(text: str) -> Dict[str, Any]:
    obj = _extract_json(text)
    themes: List[Dict[str, Any]] = []
    skipped: List[str] = []
    for raw in obj.get("themes") or []:
        if not isinstance(raw, dict):
            skipped.append("delta entry not an object")
            continue
        slug = str(raw.get("slug", "")).strip()
        if not _SLUG_RE.match(slug):
            skipped.append(f"invalid slug {raw.get('slug')!r}")
            continue
        adds = []
        for c in raw.get("add") or []:
            parsed = _parse_constituent(c, skipped, slug)
            if parsed is not None:
                adds.append(parsed)
        removes = []
        for c in raw.get("remove") or []:
            if not isinstance(c, dict):
                skipped.append(f"{slug}: remove entry not an object")
                continue
            ticker = str(c.get("ticker", "")).strip().upper()
            confidence = _clamped_confidence(c.get("confidence"))
            if not _TICKER_RE.match(ticker) or confidence is None:
                skipped.append(f"{slug}: invalid remove {c.get('ticker')!r}")
                continue
            removes.append({"ticker": ticker,
                            "reason": str(c.get("reason", "")).strip(),
                            "confidence": confidence})
        themes.append({"slug": slug, "add": adds, "remove": removes})
    return {"themes": themes, "skipped": skipped}
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
python3 -m pytest tests/test_theme_parser.py -v
```

Expected: 6 PASS.

- [ ] **Step 5: Commit**

```bash
git add execution/themes/parser.py tests/test_theme_parser.py
git commit -m "feat(autopilot): strict theme LLM-output parser (skip-don't-guess)"
```

---

### Task 7: `execution/themes/prompts.py` — the Situational Awareness prompts

**Files:**
- Create: `execution/themes/prompts.py`
- Test: `tests/test_theme_prompts.py`

**Interfaces:**
- Produces: `build_monthly_prompt(context: Dict) -> str`, `build_delta_prompt(context: Dict) -> str`.
- `context` for monthly: `{"active_themes": [{"slug","name","thesis","confidence","origin","constituents":[{"ticker","exposure","confidence"}]}], "retired_themes": [{"slug","name","retired_reason"}], "latest_rankings": list|None, "research": {"watchlist": [...], "supply_chain": [...], "news_entities": [...]}}`.
- `context` for delta: `{"active_themes": [...]}` (same shape) only.
- Consumed by: Task 9.

- [ ] **Step 1: Write the failing tests**

`tests/test_theme_prompts.py`:

```python
"""Prompts encode the SA method + hard caps so the LLM pre-filters."""
from execution.constants import (
    MAX_ACTIVE_THEMES,
    MAX_THEME_CONSTITUENTS,
    MIN_THEME_CONSTITUENTS,
)
from execution.themes.prompts import build_delta_prompt, build_monthly_prompt

CONTEXT = {
    "active_themes": [{
        "slug": "photonics", "name": "Photonics", "origin": "seed",
        "thesis": "Optical I/O bottleneck", "confidence": 0.6,
        "constituents": [{"ticker": "LASR", "exposure": "Laser subsystems", "confidence": 0.8}],
    }],
    "retired_themes": [],
    "latest_rankings": [{"slug": "photonics", "score": 0.02, "rank_1m": 1}],
    "research": {"watchlist": ["AEHR"], "supply_chain": ["SK Hynix"], "news_entities": ["CoreWeave"]},
}


def test_monthly_prompt_encodes_sa_method_and_caps():
    p = build_monthly_prompt(CONTEXT)
    for anchor in ("demand chain", "binding constraint", "consensus",
                   "leading indicators", "log space"):
        assert anchor in p.lower(), anchor
    assert str(MAX_ACTIVE_THEMES) in p
    assert str(MIN_THEME_CONSTITUENTS) in p
    assert str(MAX_THEME_CONSTITUENTS) in p
    # current state + research grounding present
    assert "photonics" in p and "LASR" in p and "AEHR" in p and "SK Hynix" in p
    # output contract
    assert '"action"' in p and '"retire"' in p and '"constituents"' in p


def test_monthly_prompt_tolerates_empty_context():
    p = build_monthly_prompt({"active_themes": [], "retired_themes": [],
                              "latest_rankings": None,
                              "research": {"watchlist": [], "supply_chain": [], "news_entities": []}})
    assert "none yet" in p.lower()


def test_delta_prompt_is_constituent_only():
    p = build_delta_prompt({"active_themes": CONTEXT["active_themes"]})
    assert "photonics" in p and "LASR" in p
    assert '"add"' in p and '"remove"' in p
    assert "retire" not in p.lower().replace('"remove"', "")  # no theme-level actions
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
python3 -m pytest tests/test_theme_prompts.py -v
```

Expected: FAIL — module not found.

- [ ] **Step 3: Implement `execution/themes/prompts.py`**

```python
"""Prompts for theme discovery — Aschenbrenner's Situational Awareness method.

The monthly prompt is a reasoning engine, not a lookup: it walks the AI
demand chain, finds binding constraints, scores the consensus gap, and only
then proposes themes/constituents. Caps and floors are stated so the model
pre-filters instead of burning validation calls.
"""
import json
from typing import Any, Dict, List

from execution.constants import (
    MAX_ACTIVE_THEMES,
    MAX_THEME_CONSTITUENTS,
    MIN_THEME_CONSTITUENTS,
    THEME_ADV_FLOOR_USD,
    THEME_MCAP_FLOOR_USD,
)

_SA_METHOD = """## Method (follow it in order — this is how you reason)

1. TRUST TRENDLINES IN LOG SPACE. Extrapolate compute/capex/power/revenue
   exponentials mechanically from multi-year data. The burden of proof is on
   "the trend breaks", not "the trend continues".
2. WALK THE DERIVATIVE DEMAND CHAIN. AI revenue -> capex -> accelerators ->
   (logic fab, HBM/memory, advanced packaging, networking/optics) ->
   datacenters -> power -> gas/turbines/grid/transformers/land. Map the
   chain AS IT IS TODAY — links appear and disappear as buildout progresses.
3. FIND THE BINDING CONSTRAINT. For each link ask: how long is the lead
   time, how much spare capacity exists? Alpha concentrates in the link with
   the longest lead time and the least spare capacity.
4. SCORE THE CONSENSUS GAP. Compare trend-implied demand with what sell-side
   and incumbent forecasts assume. A theme that is already priced in is not
   a theme. Use web search to check CURRENT forecasts, capex announcements,
   power contracts, and fab/packaging expansion news — your training data is
   stale by definition.
5. WATCH PHYSICAL COMMITMENTS. Power contracts, transformer scrambles,
   greenfield fab/packaging plants, giant GPU orders, rig counts — physical
   commitments lead reported financials by 1-3 years. Name the leading
   indicators to watch for every theme you propose.
"""


def _themes_block(themes: List[Dict[str, Any]]) -> str:
    if not themes:
        return "none yet — the seed themes below have no constituents until you populate them"
    lines = []
    for t in themes:
        cons = ", ".join(f"{c['ticker']} ({c['confidence']:.2f})" for c in t.get("constituents", []))
        lines.append(f"- {t['slug']} [{t.get('origin', 'engine')}] conf={t['confidence']:.2f}: "
                     f"{t['thesis']} | constituents: {cons or 'NONE'}")
    return "\n".join(lines)


def build_monthly_prompt(context: Dict[str, Any]) -> str:
    research = context.get("research") or {}
    rankings = context.get("latest_rankings")
    retired = context.get("retired_themes") or []
    return f"""You are the theme-discovery engine of a long-horizon systematic fund.
Your job: maintain a list of investable THEMES — links in the AI buildout
demand chain where a binding constraint creates a multi-year re-rating — and
the public-company CONSTITUENTS with material exposure to each.

{_SA_METHOD}

## Current theme list (you maintain this — seeds compete equally)
{_themes_block(context.get("active_themes") or [])}

## Retired themes (reactivate only with new evidence)
{json.dumps(retired) if retired else "none"}

## Latest theme rankings (relative strength vs SPY, if available)
{json.dumps(rankings) if rankings else "none yet"}

## Internal research context (owner's watchlist + supply-chain names seen in research)
- Watchlist tickers: {", ".join(research.get("watchlist") or []) or "none"}
- Supply-chain names from recent reports: {", ".join(research.get("supply_chain") or []) or "none"}
- News-entity names from recent reports: {", ".join(research.get("news_entities") or []) or "none"}

## Hard rules
- At most {MAX_ACTIVE_THEMES} active themes. A new theme must be MORE
  compelling than the weakest incumbent, which you should then retire.
- A theme needs at least {MIN_THEME_CONSTITUENTS} listed, liquid US-traded
  constituents (ADV >= ${THEME_ADV_FLOOR_USD:,.0f}/day, market cap >=
  ${THEME_MCAP_FLOOR_USD:,.0f}) or it cannot activate. Propose up to
  {MAX_THEME_CONSTITUENTS} per theme, strongest exposure first.
- Every constituent must have REAL, MATERIAL exposure stated in one
  falsifiable sentence with evidence. No ETFs, no foreign-only listings.
  Small caps with pure exposure beat megacaps with diluted exposure —
  surfacing what cap-weighted ETFs hide is the point.
- Every theme needs: which demand-chain link it is, why the constraint sits
  there, the consensus gap, and 2-4 leading indicators to watch (put these
  in metadata).
- "keep" themes: restate the full constituent list you want (it replaces the
  current one). "retire": say why (priced in, constraint resolved, thesis
  broken).

Respond with ONLY a JSON object, no other text:
{{
  "themes": [
    {{
      "slug": "<kebab-case>",
      "name": "<display name>",
      "action": "add" | "keep" | "retire",
      "thesis": "<demand-chain link + binding constraint + consensus gap, 2-4 sentences>",
      "confidence": <float 0.0-1.0>,
      "metadata": {{
        "binding_constraint": "<one line>",
        "consensus_gap_notes": "<one line>",
        "leading_indicators": ["<indicator>", ...]
      }},
      "constituents": [
        {{"ticker": "<SYMBOL>", "exposure": "<one falsifiable sentence>", "confidence": <float>}}
      ]
    }}
  ]
}}"""


def build_delta_prompt(context: Dict[str, Any]) -> str:
    return f"""You maintain the constituent lists of a systematic fund's theme baskets.
This is the WEEKLY DELTA pass: propose constituent additions/removals only.
Do NOT propose new themes and do NOT touch theme-level fields.

## Active themes and current constituents
{_themes_block(context.get("active_themes") or [])}

## Rules
- Suggest a change only when you have a concrete reason (new listing, lost
  exposure, acquisition, delisting, materially better pure-play).
- Additions need REAL, MATERIAL exposure stated in one falsifiable sentence.
  US-listed, liquid names only (ADV >= ${THEME_ADV_FLOOR_USD:,.0f}/day,
  market cap >= ${THEME_MCAP_FLOOR_USD:,.0f}). Max {MAX_THEME_CONSTITUENTS}
  constituents per theme.
- No changes is a perfectly good answer: return an empty themes list.

Respond with ONLY a JSON object, no other text:
{{
  "themes": [
    {{
      "slug": "<existing theme slug>",
      "add": [{{"ticker": "<SYMBOL>", "exposure": "<sentence>", "confidence": <float>}}],
      "remove": [{{"ticker": "<SYMBOL>", "reason": "<sentence>", "confidence": <float>}}]
    }}
  ]
}}"""
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
python3 -m pytest tests/test_theme_prompts.py -v
```

Expected: 3 PASS.

- [ ] **Step 5: Commit**

```bash
git add execution/themes/prompts.py tests/test_theme_prompts.py
git commit -m "feat(autopilot): SA-method discovery prompts (monthly reasoning + weekly delta)"
```

---

### Task 8: `execution/themes/lifecycle.py` — apply rules (pure plan + DB apply)

**Files:**
- Create: `execution/themes/lifecycle.py`
- Test: `tests/test_theme_lifecycle.py`

**Interfaces:**
- Produces (pure, unit-tested heavily):
  - `plan_monthly_actions(current: List[dict], proposals: List[dict], validation: Dict[str, Optional[dict]]) -> {"actions": [Action], "rejected": [str]}`
  - `plan_delta_actions(current: List[dict], deltas: List[dict], validation: Dict[str, Optional[dict]]) -> {"actions": [Action], "rejected": [str]}`
  - `current` theme shape: `{"slug","status","origin","confidence","constituents":[{"ticker","status"}]}` (active themes AND retired ones — the planner needs both for reactivation).
  - Action kinds (dicts, JSON-serializable):
    - `{"kind": "activate_theme", "slug", "name", "thesis", "confidence", "metadata", "constituents": [{"ticker","exposure","confidence","validation"}], "reactivated": bool, "dethroned": Optional[slug]}`
    - `{"kind": "update_theme", "slug", "thesis", "confidence", "metadata", "add": [constituent], "remove": [ticker]}`
    - `{"kind": "retire_theme", "slug", "reason"}`
    - `{"kind": "journal_only", "slug", "title", "detail"}` (below-threshold deltas)
- Produces (DB edge): `async apply_actions(db, actions: List[dict], source: str) -> {"applied": int, "reports": int}` — writes rows + one EngineReport per action via `write_report` (Task 2).
- Consumes: constants caps; `execution.reporting.write_report`.

- [ ] **Step 1: Write the failing tests for the pure planner**

`tests/test_theme_lifecycle.py`:

```python
"""Lifecycle rules: caps, dethrone, activation floor, delta gate."""
import pytest

from execution.themes.lifecycle import plan_delta_actions, plan_monthly_actions

VALID = {"adv": 5e6, "market_cap": 5e8, "price": 20.0, "validated_at": "2026-07-09T00:00:00Z"}


def _proposal(slug, action="add", confidence=0.8, n_constituents=6):
    return {
        "slug": slug, "name": slug.title(), "action": action,
        "thesis": "t", "confidence": confidence, "metadata": {},
        "constituents": [
            {"ticker": f"T{i}{slug[:2].upper()}", "exposure": "x", "confidence": 0.9 - i * 0.01}
            for i in range(n_constituents)
        ],
    }


def _validation_for(proposals, valid=True):
    out = {}
    for p in proposals:
        for c in p["constituents"]:
            out[c["ticker"]] = VALID if valid else None
    return out


def _current(slug, status="active", confidence=0.5, origin="seed", tickers=()):
    return {"slug": slug, "status": status, "origin": origin, "confidence": confidence,
            "constituents": [{"ticker": t, "status": "active"} for t in tickers]}


def test_add_activates_with_enough_valid_constituents():
    props = [_proposal("gas-turbines")]
    plan = plan_monthly_actions([], props, _validation_for(props))
    acts = plan["actions"]
    assert len(acts) == 1 and acts[0]["kind"] == "activate_theme"
    assert len(acts[0]["constituents"]) == 6
    assert acts[0]["dethroned"] is None


def test_add_rejected_below_min_valid_constituents():
    props = [_proposal("gas-turbines", n_constituents=6)]
    validation = _validation_for(props, valid=False)
    plan = plan_monthly_actions([], props, validation)
    assert plan["actions"] == []
    assert any("gas-turbines" in r for r in plan["rejected"])


def test_constituents_capped_at_max_by_confidence():
    props = [_proposal("chips-x", n_constituents=25)]
    plan = plan_monthly_actions([], props, _validation_for(props))
    kept = plan["actions"][0]["constituents"]
    assert len(kept) == 20
    assert kept == sorted(kept, key=lambda c: -c["confidence"])


def test_at_cap_dethrones_weakest_incumbent():
    current = [_current(f"t{i}", confidence=0.3 + i * 0.05) for i in range(12)]
    props = [_proposal("gas-turbines", confidence=0.9)]
    plan = plan_monthly_actions(current, props, _validation_for(props))
    act = plan["actions"][-1]
    assert act["kind"] == "activate_theme" and act["dethroned"] == "t0"
    retires = [a for a in plan["actions"] if a["kind"] == "retire_theme"]
    assert retires and retires[0]["slug"] == "t0"


def test_at_cap_weaker_proposal_rejected():
    current = [_current(f"t{i}", confidence=0.8) for i in range(12)]
    props = [_proposal("weak-theme", confidence=0.5)]
    plan = plan_monthly_actions(current, props, _validation_for(props))
    assert all(a["kind"] != "activate_theme" for a in plan["actions"])
    assert any("weak-theme" in r for r in plan["rejected"])


def test_retire_only_applies_to_active_theme():
    current = [_current("photonics")]
    props = [_proposal("photonics", action="retire"), _proposal("ghost", action="retire")]
    plan = plan_monthly_actions(current, props, {})
    kinds = [(a["kind"], a["slug"]) for a in plan["actions"]]
    assert ("retire_theme", "photonics") in kinds
    assert not any(s == "ghost" for _, s in kinds)


def test_reactivation_flagged_for_retired_slug():
    current = [_current("space", status="retired")]
    props = [_proposal("space", action="add")]
    plan = plan_monthly_actions(current, props, _validation_for(props))
    assert plan["actions"][0]["reactivated"] is True


def test_keep_produces_update_with_diff():
    current = [_current("photonics", tickers=("LASR", "VIAV"))]
    props = [_proposal("photonics", action="keep", n_constituents=6)]
    props[0]["constituents"][0] = {"ticker": "LASR", "exposure": "x", "confidence": 0.9}
    plan = plan_monthly_actions(current, props, _validation_for(props))
    act = plan["actions"][0]
    assert act["kind"] == "update_theme"
    assert "VIAV" in act["remove"]
    assert all(c["ticker"] != "LASR" for c in act["add"])  # unchanged, not re-added


def test_delta_below_threshold_is_journal_only():
    current = [_current("photonics", tickers=("LASR",))]
    deltas = [{"slug": "photonics",
               "add": [{"ticker": "NEWT", "exposure": "x", "confidence": 0.6}],
               "remove": []}]
    plan = plan_delta_actions(current, deltas, {"NEWT": VALID})
    assert plan["actions"][0]["kind"] == "journal_only"


def test_delta_above_threshold_applies_and_respects_cap():
    current = [_current("photonics", tickers=tuple(f"C{i}" for i in range(20)))]
    deltas = [{"slug": "photonics",
               "add": [{"ticker": "NEWT", "exposure": "x", "confidence": 0.9}],
               "remove": []}]
    plan = plan_delta_actions(current, deltas, {"NEWT": VALID})
    assert plan["actions"] == []  # at MAX_THEME_CONSTITUENTS — add rejected
    assert any("NEWT" in r for r in plan["rejected"])


def test_delta_for_unknown_theme_rejected():
    plan = plan_delta_actions([], [{"slug": "ghost", "add": [], "remove": []}], {})
    assert plan["actions"] == []
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
python3 -m pytest tests/test_theme_lifecycle.py -v
```

Expected: FAIL — module not found.

- [ ] **Step 3: Implement `execution/themes/lifecycle.py`**

```python
"""Theme lifecycle: pure planning + DB apply.

plan_* are pure functions (heavily unit-tested); apply_actions is the only
DB touchpoint. Rules (spec):
- activation requires >= MIN_THEME_CONSTITUENTS validated names
- at MAX_ACTIVE_THEMES a proposal must beat the lowest-confidence incumbent
  (which gets retired — "dethroned")
- retirement only via explicit proposal; validation attrition never retires
- weekly deltas auto-apply at >= DELTA_AUTO_APPLY_CONFIDENCE, else journal-only
- every applied action becomes an EngineReport entry (the veto surface)
"""
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from execution.constants import (
    DELTA_AUTO_APPLY_CONFIDENCE,
    MAX_ACTIVE_THEMES,
    MAX_THEME_CONSTITUENTS,
    MIN_THEME_CONSTITUENTS,
)
from execution.reporting import write_report

logger = logging.getLogger(__name__)


def _validated_constituents(proposal: Dict, validation: Dict[str, Optional[Dict]]) -> List[Dict]:
    valid = []
    for c in proposal.get("constituents", []):
        v = validation.get(c["ticker"])
        if v is not None:
            valid.append({**c, "validation": v})
    valid.sort(key=lambda c: -c["confidence"])
    return valid[:MAX_THEME_CONSTITUENTS]


def plan_monthly_actions(
    current: List[Dict], proposals: List[Dict], validation: Dict[str, Optional[Dict]],
) -> Dict[str, Any]:
    actions: List[Dict] = []
    rejected: List[str] = []
    by_slug = {t["slug"]: t for t in current}
    active = {t["slug"] for t in current if t["status"] == "active"}
    # live confidence view, mutated as retires/dethrones land this pass
    confidence = {t["slug"]: t["confidence"] for t in current if t["status"] == "active"}

    retires = [p for p in proposals if p["action"] == "retire"]
    keeps = [p for p in proposals if p["action"] == "keep"]
    adds = sorted((p for p in proposals if p["action"] == "add"),
                  key=lambda p: -p["confidence"])

    for p in retires:
        if p["slug"] not in active:
            rejected.append(f"{p['slug']}: retire ignored — not an active theme")
            continue
        actions.append({"kind": "retire_theme", "slug": p["slug"], "reason": p["thesis"]})
        active.discard(p["slug"])
        confidence.pop(p["slug"], None)

    for p in keeps:
        if p["slug"] not in active:
            rejected.append(f"{p['slug']}: keep ignored — not an active theme")
            continue
        valid = _validated_constituents(p, validation)
        proposed = {c["ticker"] for c in valid}
        existing = {c["ticker"] for c in by_slug[p["slug"]]["constituents"]
                    if c["status"] == "active"}
        actions.append({
            "kind": "update_theme", "slug": p["slug"], "thesis": p["thesis"],
            "confidence": p["confidence"], "metadata": p.get("metadata") or {},
            "add": [c for c in valid if c["ticker"] not in existing],
            "remove": sorted(existing - proposed),
        })
        confidence[p["slug"]] = p["confidence"]

    for p in adds:
        if p["slug"] in active:
            rejected.append(f"{p['slug']}: add ignored — already active (use keep)")
            continue
        valid = _validated_constituents(p, validation)
        if len(valid) < MIN_THEME_CONSTITUENTS:
            rejected.append(
                f"{p['slug']}: only {len(valid)} validated constituents "
                f"(need {MIN_THEME_CONSTITUENTS})")
            continue
        dethroned = None
        if len(active) >= MAX_ACTIVE_THEMES:
            weakest = min(confidence, key=confidence.get) if confidence else None
            if weakest is None or p["confidence"] <= confidence[weakest]:
                rejected.append(
                    f"{p['slug']}: at cap and confidence {p['confidence']:.2f} does not "
                    f"beat weakest incumbent")
                continue
            dethroned = weakest
            actions.append({"kind": "retire_theme", "slug": weakest,
                            "reason": f"dethroned by higher-confidence theme {p['slug']}"})
            active.discard(weakest)
            confidence.pop(weakest, None)
        prior = by_slug.get(p["slug"])
        actions.append({
            "kind": "activate_theme", "slug": p["slug"], "name": p["name"],
            "thesis": p["thesis"], "confidence": p["confidence"],
            "metadata": p.get("metadata") or {}, "constituents": valid,
            "reactivated": bool(prior and prior["status"] == "retired"),
            "dethroned": dethroned,
        })
        active.add(p["slug"])
        confidence[p["slug"]] = p["confidence"]

    return {"actions": actions, "rejected": rejected}


def plan_delta_actions(
    current: List[Dict], deltas: List[Dict], validation: Dict[str, Optional[Dict]],
) -> Dict[str, Any]:
    actions: List[Dict] = []
    rejected: List[str] = []
    by_slug = {t["slug"]: t for t in current if t["status"] == "active"}

    for d in deltas:
        theme = by_slug.get(d["slug"])
        if theme is None:
            rejected.append(f"{d['slug']}: delta ignored — not an active theme")
            continue
        existing = {c["ticker"] for c in theme["constituents"] if c["status"] == "active"}
        adds, removes = [], []
        for c in d.get("add", []):
            if c["confidence"] < DELTA_AUTO_APPLY_CONFIDENCE:
                actions.append({"kind": "journal_only", "slug": d["slug"],
                                "title": f"delta below threshold: +{c['ticker']}",
                                "detail": f"{c['exposure']} (confidence {c['confidence']:.2f})"})
                continue
            if c["ticker"] in existing:
                rejected.append(f"{d['slug']}: +{c['ticker']} already a constituent")
                continue
            if validation.get(c["ticker"]) is None:
                rejected.append(f"{d['slug']}: +{c['ticker']} failed validation")
                continue
            if len(existing) + len(adds) >= MAX_THEME_CONSTITUENTS:
                rejected.append(f"{d['slug']}: +{c['ticker']} rejected — at constituent cap")
                continue
            adds.append({**c, "validation": validation[c["ticker"]]})
        for c in d.get("remove", []):
            if c["confidence"] < DELTA_AUTO_APPLY_CONFIDENCE:
                actions.append({"kind": "journal_only", "slug": d["slug"],
                                "title": f"delta below threshold: -{c['ticker']}",
                                "detail": f"{c.get('reason', '')} (confidence {c['confidence']:.2f})"})
                continue
            if c["ticker"] not in existing:
                rejected.append(f"{d['slug']}: -{c['ticker']} not a constituent")
                continue
            removes.append(c["ticker"])
        if adds or removes:
            actions.append({"kind": "update_theme", "slug": d["slug"], "thesis": None,
                            "confidence": None, "metadata": None,
                            "add": adds, "remove": removes})

    return {"actions": actions, "rejected": rejected}


# ── DB edge ──────────────────────────────────────────────────────────────────

async def apply_actions(db, actions: List[Dict], source: str) -> Dict[str, int]:
    """Apply planned actions + journal each one. Item failures are logged and
    journaled but never abort the batch."""
    from prisma import Json  # noqa: PLC0415

    now = datetime.now(timezone.utc)
    applied = reports = 0
    for act in actions:
        try:
            if act["kind"] == "journal_only":
                await write_report("theme_proposal", "info", source, act["title"],
                                   {"slug": act["slug"], "detail": act["detail"],
                                    "applied": False}, db=db)
                reports += 1
                continue

            if act["kind"] == "retire_theme":
                await db.themebasket.update(
                    where={"slug": act["slug"]},
                    data={"status": "retired", "retiredAt": now})
                await write_report("theme_retired", "warning", source,
                                   f"theme retired: {act['slug']}",
                                   {"slug": act["slug"], "reason": act["reason"]}, db=db)

            elif act["kind"] == "activate_theme":
                theme = await db.themebasket.upsert(
                    where={"slug": act["slug"]},
                    data={
                        "create": {"slug": act["slug"], "name": act["name"],
                                   "status": "active", "origin": "engine",
                                   "thesis": act["thesis"], "confidence": act["confidence"],
                                   "metadata": Json(act["metadata"]), "lastReasonedAt": now},
                        "update": {"status": "active", "retiredAt": None,
                                   "name": act["name"], "thesis": act["thesis"],
                                   "confidence": act["confidence"],
                                   "metadata": Json(act["metadata"]), "lastReasonedAt": now},
                    })
                for c in act["constituents"]:
                    await db.themeconstituent.upsert(
                        where={"themeId_ticker": {"themeId": theme.id, "ticker": c["ticker"]}},
                        data={
                            "create": {"themeId": theme.id, "ticker": c["ticker"],
                                       "exposure": c["exposure"], "confidence": c["confidence"],
                                       "status": "active", "source": "reasoning",
                                       "validation": Json(c["validation"])},
                            "update": {"status": "active", "removedAt": None,
                                       "exposure": c["exposure"], "confidence": c["confidence"],
                                       "validation": Json(c["validation"])},
                        })
                await write_report(
                    "theme_proposal", "info", source,
                    f"theme activated: {act['slug']}"
                    + (" (reactivated)" if act["reactivated"] else ""),
                    {k: act[k] for k in ("slug", "thesis", "confidence", "metadata",
                                          "reactivated", "dethroned")}
                    | {"constituents": [{"ticker": c["ticker"], "exposure": c["exposure"],
                                          "confidence": c["confidence"]}
                                         for c in act["constituents"]]},
                    db=db)

            elif act["kind"] == "update_theme":
                theme = await db.themebasket.find_unique(where={"slug": act["slug"]})
                if theme is None:
                    continue
                update_data = {"lastReasonedAt": now}
                if act.get("thesis") is not None:
                    update_data.update({"thesis": act["thesis"],
                                        "confidence": act["confidence"],
                                        "metadata": Json(act["metadata"])})
                await db.themebasket.update(where={"slug": act["slug"]}, data=update_data)
                for c in act.get("add", []):
                    await db.themeconstituent.upsert(
                        where={"themeId_ticker": {"themeId": theme.id, "ticker": c["ticker"]}},
                        data={
                            "create": {"themeId": theme.id, "ticker": c["ticker"],
                                       "exposure": c["exposure"], "confidence": c["confidence"],
                                       "status": "active", "source": source_kind(source),
                                       "validation": Json(c["validation"])},
                            "update": {"status": "active", "removedAt": None,
                                       "exposure": c["exposure"], "confidence": c["confidence"],
                                       "validation": Json(c["validation"])},
                        })
                for ticker in act.get("remove", []):
                    await db.themeconstituent.update_many(
                        where={"themeId": theme.id, "ticker": ticker},
                        data={"status": "removed", "removedAt": now})
                if act.get("add") or act.get("remove"):
                    await write_report(
                        "membership_change", "info", source,
                        f"membership change: {act['slug']} "
                        f"(+{len(act.get('add', []))}/-{len(act.get('remove', []))})",
                        {"slug": act["slug"],
                         "added": [{"ticker": c["ticker"], "exposure": c["exposure"],
                                    "confidence": c["confidence"]} for c in act.get("add", [])],
                         "removed": act.get("remove", [])},
                        db=db)

            applied += 1
            reports += 1
        except Exception:
            logger.exception("apply_actions: %s failed for %s", act.get("kind"), act.get("slug"))
            await write_report("engine_failure", "critical", source,
                               f"failed to apply {act.get('kind')} for {act.get('slug')}",
                               {"action": {k: v for k, v in act.items() if k != "constituents"}},
                               db=db)
    return {"applied": applied, "reports": reports}


def source_kind(source: str) -> str:
    return "delta" if "delta" in source else "reasoning"
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
python3 -m pytest tests/test_theme_lifecycle.py -v
```

Expected: 12 PASS. (apply_actions is exercised via Task 9's discovery tests with a stub db — the pure planner carries the logic risk.)

- [ ] **Step 5: Commit**

```bash
git add execution/themes/lifecycle.py tests/test_theme_lifecycle.py
git commit -m "feat(autopilot): theme lifecycle planner + DB apply with journaled mutations"
```

---

### Task 9: `discovery.py` + `delta.py` — orchestration + the LLM call

**Files:**
- Create: `execution/themes/discovery.py`, `execution/themes/delta.py`
- Modify: `requirements.txt` (add `anthropic>=0.40.0` after the langchain block)
- Test: `tests/test_theme_discovery.py`

**Interfaces:**
- Produces in `discovery.py` (each maps to one Inngest step in Task 10):
  - `async gather_monthly_context(db) -> Dict` (JSON-serializable; shape = Task 7's monthly context)
  - `reason_monthly(context: Dict, llm_call=None) -> str` (the PAID call — sync, one invocation)
  - `parse_and_validate_monthly(raw: str) -> {"proposals": [...], "validation": {...}, "skipped": [...]}`
  - `async apply_monthly(db, bundle: Dict) -> Dict` (re-reads current themes, plans, applies, journals skips/rejections as `validation_failure`)
  - `_call_llm(model: str, prompt: str, use_web_search: bool = False, max_uses: int = 8) -> str` — native `anthropic` SDK; the ONLY function that talks to the API.
- Produces in `delta.py`: `async gather_delta_context(db) -> Dict`, `reason_delta(context, llm_call=None) -> str`, `parse_and_validate_delta(raw) -> Dict`, `async apply_delta(db, bundle) -> Dict`.
- Consumes: Tasks 4-8 (`get_research_context`, `validate_tickers`, parser, prompts, lifecycle), `get_latest_outlook`.

- [ ] **Step 1: Add the dependency**

In `requirements.txt`, after `langchain-core>=0.3.0` (line 11), add:

```
anthropic>=0.40.0
```

(Already installed transitively via langchain-anthropic; pinning it makes the direct usage explicit. Verify: `python3 -c "import anthropic; print(anthropic.__version__)"`.)

- [ ] **Step 2: Write the failing tests**

`tests/test_theme_discovery.py`:

```python
"""Discovery orchestration with stubbed LLM + validation + db."""
import pytest

import execution.themes.discovery as discovery
import execution.themes.delta as delta_mod

RAW = ('{"themes": [{"slug": "gas-turbines", "name": "Gas Turbines", "action": "add", '
       '"thesis": "power constraint", "confidence": 0.8, "metadata": {}, "constituents": ['
       + ", ".join(f'{{"ticker": "T{i}GT", "exposure": "x", "confidence": 0.9}}' for i in range(6))
       + "]}]}")

VALID = {"adv": 5e6, "market_cap": 5e8, "price": 20.0, "validated_at": "2026-07-09T00:00:00Z"}


def test_reason_monthly_uses_web_search_model(monkeypatch):
    seen = {}

    def fake_llm(model, prompt, use_web_search=False, max_uses=8):
        seen.update(model=model, use_web_search=use_web_search, max_uses=max_uses,
                    prompt=prompt)
        return RAW

    out = discovery.reason_monthly({"active_themes": [], "retired_themes": [],
                                    "latest_rankings": None,
                                    "research": {"watchlist": [], "supply_chain": [],
                                                 "news_entities": []}},
                                   llm_call=fake_llm)
    assert out == RAW
    assert seen["model"] == "claude-sonnet-5"
    assert seen["use_web_search"] is True and seen["max_uses"] == 8
    assert "demand chain" in seen["prompt"].lower()


def test_parse_and_validate_monthly(monkeypatch):
    monkeypatch.setattr(discovery, "validate_tickers",
                        lambda tickers: {t: VALID for t in tickers})
    bundle = discovery.parse_and_validate_monthly(RAW)
    assert len(bundle["proposals"]) == 1
    assert len(bundle["validation"]) == 6
    assert bundle["skipped"] == []


def test_reason_delta_uses_cheap_model_no_search(monkeypatch):
    seen = {}

    def fake_llm(model, prompt, use_web_search=False, max_uses=8):
        seen.update(model=model, use_web_search=use_web_search)
        return '{"themes": []}'

    delta_mod.reason_delta({"active_themes": []}, llm_call=fake_llm)
    assert seen["model"] == "claude-haiku-4-5"
    assert seen["use_web_search"] is False


class _Themes:
    def __init__(self, rows):
        self._rows = rows

    async def find_many(self, **kwargs):
        return self._rows


@pytest.mark.asyncio
async def test_apply_monthly_journals_skips_and_applies(monkeypatch):
    reports, planned = [], {}

    async def fake_write_report(t, sev, src, title, body, db=None):
        reports.append((t, title))
        return "rep"

    async def fake_apply_actions(db, actions, source):
        planned["actions"] = actions
        return {"applied": len(actions), "reports": len(actions)}

    monkeypatch.setattr(discovery, "write_report", fake_write_report)
    monkeypatch.setattr(discovery, "apply_actions", fake_apply_actions)

    class Db:
        themebasket = _Themes([])

    bundle = {"proposals": [{"slug": "gas-turbines", "name": "GT", "action": "add",
                             "thesis": "t", "confidence": 0.8, "metadata": {},
                             "constituents": [{"ticker": f"T{i}GT", "exposure": "x",
                                               "confidence": 0.9} for i in range(6)]}],
              "validation": {f"T{i}GT": VALID for i in range(6)},
              "skipped": ["bad item"]}
    summary = await discovery.apply_monthly(Db(), bundle)
    assert summary["applied"] == 1
    assert any(t == "validation_failure" for t, _ in reports)  # skips journaled
    assert planned["actions"][0]["kind"] == "activate_theme"
```

- [ ] **Step 3: Run tests to verify they fail**

```bash
python3 -m pytest tests/test_theme_discovery.py -v
```

Expected: FAIL — modules not found.

- [ ] **Step 4: Implement `execution/themes/discovery.py`**

```python
"""Monthly theme-discovery pass: gather -> reason (paid) -> validate -> apply.

Each function maps to ONE Inngest step (Task 10) so the paid LLM call is
memoized separately from apply — a retry after a failed apply must never
re-bill the reasoning call (tiered-batch lesson).
"""
import logging
import os
from typing import Any, Dict, Optional

from execution.constants import (
    THEME_REASONING_MODEL,
    THEME_WEB_SEARCH_MAX_USES,
)
from execution.reporting import write_report
from execution.research_feed import get_research_context
from execution.themes.lifecycle import apply_actions, plan_monthly_actions
from execution.themes.parser import parse_monthly_response
from execution.themes.prompts import build_monthly_prompt
from execution.themes.validation import validate_tickers

logger = logging.getLogger(__name__)

SOURCE = "theme_discovery_monthly"


def _anthropic_api_key() -> str:
    try:
        from research_swarm.config import settings  # noqa: PLC0415
        return settings.anthropic_api_key or os.getenv("ANTHROPIC_API_KEY", "")
    except ImportError:
        return os.getenv("ANTHROPIC_API_KEY", "")


def _call_llm(model: str, prompt: str, use_web_search: bool = False, max_uses: int = 8) -> str:
    """One native-SDK call. Server-side web_search when requested."""
    import anthropic  # noqa: PLC0415

    client = anthropic.Anthropic(api_key=_anthropic_api_key())
    kwargs: Dict[str, Any] = {
        "model": model,
        "max_tokens": 8192,
        "messages": [{"role": "user", "content": prompt}],
    }
    if use_web_search:
        kwargs["tools"] = [{"type": "web_search_20250305", "name": "web_search",
                            "max_uses": max_uses}]
    response = client.messages.create(**kwargs)
    return "".join(
        block.text for block in response.content
        if getattr(block, "type", "") == "text"
    )


async def _current_theme_state(db, include_retired: bool = True) -> list:
    where = None if include_retired else {"status": "active"}
    rows = await db.themebasket.find_many(
        where=where, include={"constituents": True}, order={"createdAt": "asc"})
    return [{
        "slug": r.slug, "name": r.name, "status": r.status, "origin": r.origin,
        "thesis": r.thesis, "confidence": r.confidence,
        "constituents": [
            {"ticker": c.ticker, "exposure": c.exposure,
             "confidence": c.confidence, "status": c.status}
            for c in (r.constituents or [])
        ],
    } for r in rows]


async def gather_monthly_context(db) -> Dict[str, Any]:
    themes = await _current_theme_state(db)
    active = [{**t, "constituents": [c for c in t["constituents"] if c["status"] == "active"]}
              for t in themes if t["status"] == "active"]
    retired = [{"slug": t["slug"], "name": t["name"]} for t in themes if t["status"] == "retired"]

    latest_rankings = None
    try:
        from execution.outlook_service import get_latest_outlook  # noqa: PLC0415
        row = await get_latest_outlook(db)
        blob = getattr(row, "themeRankings", None) if row else None
        latest_rankings = blob.get("rankings") if isinstance(blob, dict) else None
    except Exception:
        logger.exception("gather_monthly_context: rankings unavailable")

    research = await get_research_context(db)
    return {"active_themes": active, "retired_themes": retired,
            "latest_rankings": latest_rankings, "research": research}


def reason_monthly(context: Dict[str, Any], llm_call=None) -> str:
    call = llm_call or _call_llm
    prompt = build_monthly_prompt(context)
    return call(THEME_REASONING_MODEL, prompt, use_web_search=True,
                max_uses=THEME_WEB_SEARCH_MAX_USES)


def parse_and_validate_monthly(raw: str) -> Dict[str, Any]:
    parsed = parse_monthly_response(raw)
    tickers = [c["ticker"] for p in parsed["themes"] for c in p["constituents"]]
    validation = validate_tickers(tickers) if tickers else {}
    return {"proposals": parsed["themes"], "validation": validation,
            "skipped": parsed["skipped"]}


async def apply_monthly(db, bundle: Dict[str, Any]) -> Dict[str, Any]:
    current = await _current_theme_state(db)
    plan = plan_monthly_actions(current, bundle["proposals"], bundle["validation"])
    summary = await apply_actions(db, plan["actions"], SOURCE)

    problems = bundle["skipped"] + plan["rejected"]
    rejected_tickers = sorted(t for t, v in bundle["validation"].items() if v is None)
    if problems or rejected_tickers:
        await write_report(
            "validation_failure", "warning", SOURCE,
            f"monthly pass: {len(problems)} skipped/rejected, "
            f"{len(rejected_tickers)} tickers failed validation",
            {"skipped": problems, "failed_tickers": rejected_tickers}, db=db)
    return {**summary, "rejected": len(problems), "failed_tickers": len(rejected_tickers)}
```

- [ ] **Step 5: Implement `execution/themes/delta.py`**

```python
"""Weekly constituent-delta pass — cheap model, no web search, adds/drops only."""
import logging
from typing import Any, Dict

from execution.constants import THEME_DELTA_MODEL
from execution.reporting import write_report
from execution.themes.discovery import _call_llm, _current_theme_state
from execution.themes.lifecycle import apply_actions, plan_delta_actions
from execution.themes.parser import parse_delta_response
from execution.themes.prompts import build_delta_prompt
from execution.themes.validation import validate_tickers

logger = logging.getLogger(__name__)

SOURCE = "theme_delta_weekly"


async def gather_delta_context(db) -> Dict[str, Any]:
    themes = await _current_theme_state(db, include_retired=False)
    active = [{**t, "constituents": [c for c in t["constituents"] if c["status"] == "active"]}
              for t in themes if t["status"] == "active"]
    return {"active_themes": active}


def reason_delta(context: Dict[str, Any], llm_call=None) -> str:
    call = llm_call or _call_llm
    return call(THEME_DELTA_MODEL, build_delta_prompt(context), use_web_search=False)


def parse_and_validate_delta(raw: str) -> Dict[str, Any]:
    parsed = parse_delta_response(raw)
    tickers = [c["ticker"] for t in parsed["themes"] for c in t.get("add", [])]
    validation = validate_tickers(tickers) if tickers else {}
    return {"deltas": parsed["themes"], "validation": validation,
            "skipped": parsed["skipped"]}


async def apply_delta(db, bundle: Dict[str, Any]) -> Dict[str, Any]:
    current = await _current_theme_state(db, include_retired=False)
    plan = plan_delta_actions(current, bundle["deltas"], bundle["validation"])
    summary = await apply_actions(db, plan["actions"], SOURCE)
    problems = bundle["skipped"] + plan["rejected"]
    if problems:
        await write_report("validation_failure", "warning", SOURCE,
                           f"delta pass: {len(problems)} skipped/rejected",
                           {"skipped": problems}, db=db)
    return {**summary, "rejected": len(problems)}
```

- [ ] **Step 6: Run tests to verify they pass**

```bash
python3 -m pytest tests/test_theme_discovery.py -v
```

Expected: 4 PASS.

- [ ] **Step 7: Commit**

```bash
git add execution/themes/discovery.py execution/themes/delta.py requirements.txt tests/test_theme_discovery.py
git commit -m "feat(autopilot): theme discovery/delta orchestration + native anthropic web_search call"
```

---

### Task 10: Inngest crons `theme_discovery_monthly` + `theme_delta_weekly`

**Files:**
- Create: `inngest_app/functions/theme_discovery_monthly.py`, `inngest_app/functions/theme_delta_weekly.py`
- Modify: `inngest_app/index.py` (imports + ACTIVE_FUNCTIONS + docstring note)
- Test: `tests/test_theme_crons.py`

**Interfaces:**
- Consumes: Task 9's four-step functions per pass.
- Produces: Inngest functions `theme-discovery-monthly` (cron `0 12 1 * *`) and `theme-delta-weekly` (cron `0 14 * * 6`), both registered in `ACTIVE_FUNCTIONS` (total goes 4 → 6).
- CRITICAL step layout: `gather-context` → `reason` (the paid call, its own memoized step) → `parse-validate` → `apply`. A retry after a failed apply must hit the memoized reason result, not re-bill.

- [ ] **Step 1: Read the working reference implementations**

```bash
sed -n 1,60p /Users/tui/dvrg/inngest_app/functions/execution_daily.py
```

Mirror EXACTLY: the guarded `_register_inngest_function()` pattern, `ctx.step.run` usage, and the `on_failure` kwarg signature that execution_daily uses (it is verified working on the deployed SDK). Do not invent API shapes — copy from this file.

- [ ] **Step 2: Write the failing tests**

`tests/test_theme_crons.py`:

```python
"""Cron modules: guarded registration + registry membership."""
import importlib


def test_modules_import_without_inngest_runtime():
    m1 = importlib.import_module("inngest_app.functions.theme_discovery_monthly")
    m2 = importlib.import_module("inngest_app.functions.theme_delta_weekly")
    # Attribute exists either way; None only when the pip SDK is absent.
    assert hasattr(m1, "theme_discovery_monthly")
    assert hasattr(m2, "theme_delta_weekly")


def test_registered_in_active_functions():
    import inngest_app.index as idx
    src = open("inngest_app/index.py").read()
    assert "theme_discovery_monthly" in src
    assert "theme_delta_weekly" in src
    # When the SDK is importable in this env, both register:
    try:
        import inngest  # noqa: F401
        names = {getattr(f, "id", None) or getattr(getattr(f, "_opts", None), "fn_id", "")
                 for f in idx.ACTIVE_FUNCTIONS}
        assert len(idx.ACTIVE_FUNCTIONS) == 6
    except ImportError:
        pass
```

- [ ] **Step 3: Run tests to verify they fail**

```bash
python3 -m pytest tests/test_theme_crons.py -v
```

Expected: FAIL — modules not found.

- [ ] **Step 4: Implement `inngest_app/functions/theme_discovery_monthly.py`**

```python
"""
Theme discovery — monthly SA reasoning pass (Autopilot Phase 3B).

Cron: 1st of month 12:00 UTC (clear of Sunday 20:00 outlook, Monday 15:00
rebalance, Saturday 14:00 delta). Steps: gather -> reason (PAID, memoized
alone) -> parse+validate -> apply. End-to-end failure = no changes this
cycle + engine_failure journal entry via on_failure; the outlook and
Sleeve B never notice.
"""
from __future__ import annotations

import logging
from typing import Any, Dict

logger = logging.getLogger(__name__)


def _register_inngest_function():
    import inngest as inngest_sdk  # noqa: PLC0415

    from inngest_app.client import inngest_client  # noqa: PLC0415

    # Mirror execution_daily.py's on_failure signature exactly (verified on
    # the deployed SDK version).
    async def _on_failure(ctx: "inngest_sdk.Context") -> None:
        from execution.alerts import send_failure_alert  # noqa: PLC0415
        await send_failure_alert(
            "theme discovery monthly failed",
            str(getattr(ctx, "event", "")),
            source="theme_discovery_monthly",
        )

    @inngest_client.create_function(
        fn_id="theme-discovery-monthly",
        trigger=inngest_sdk.TriggerCron(cron="0 12 1 * *"),
        name="Theme Discovery (monthly reasoning pass)",
        retries=1,
        on_failure=_on_failure,
    )
    async def theme_discovery_monthly(ctx: "inngest_sdk.Context") -> Dict[str, Any]:
        step = ctx.step

        async def gather() -> Dict[str, Any]:
            from api.lib.db import get_db  # noqa: PLC0415
            from execution.themes.discovery import gather_monthly_context  # noqa: PLC0415
            return await gather_monthly_context(await get_db())

        context = await step.run("gather-context", gather)

        async def reason() -> str:
            from execution.themes.discovery import reason_monthly  # noqa: PLC0415
            return reason_monthly(context)

        raw = await step.run("reason", reason)  # PAID — memoized alone

        async def validate() -> Dict[str, Any]:
            from execution.themes.discovery import parse_and_validate_monthly  # noqa: PLC0415
            return parse_and_validate_monthly(raw)

        bundle = await step.run("parse-validate", validate)

        async def apply() -> Dict[str, Any]:
            from api.lib.db import get_db  # noqa: PLC0415
            from execution.themes.discovery import apply_monthly  # noqa: PLC0415
            return await apply_monthly(await get_db(), bundle)

        summary = await step.run("apply", apply)
        logger.info("theme discovery monthly: %s", summary)
        return summary

    return theme_discovery_monthly


try:
    theme_discovery_monthly = _register_inngest_function()
except Exception:
    theme_discovery_monthly = None  # type: ignore[assignment]
```

- [ ] **Step 5: Implement `inngest_app/functions/theme_delta_weekly.py`**

Same skeleton with these substitutions: module docstring "weekly constituent delta pass (cheap model, no web search). Saturdays 14:00 UTC so Sunday's ranking sees fresh membership; 14:00 avoids colliding with the monthly pass when the 1st falls on a Saturday."; `fn_id="theme-delta-weekly"`, `cron="0 14 * * 6"`, `name="Theme Delta (weekly constituent pass)"`, alert subject "theme delta weekly failed", `source="theme_delta_weekly"`, and the four step bodies import from `execution.themes.delta`: `gather_delta_context`, `reason_delta`, `parse_and_validate_delta`, `apply_delta`. Function/attribute name `theme_delta_weekly` throughout.

- [ ] **Step 6: Register in `inngest_app/index.py`**

Add imports after the existing four:

```python
from inngest_app.functions.theme_discovery_monthly import theme_discovery_monthly
from inngest_app.functions.theme_delta_weekly import theme_delta_weekly
```

Extend the roster:

```python
ACTIVE_FUNCTIONS = [
    fn
    for fn in [weekly_market_outlook, weekly_batch, execution_daily, execution_weekly,
               theme_discovery_monthly, theme_delta_weekly]
    if fn is not None
]
```

Append to the module docstring: `Owner decision (2026-07-09, Phase 3B): register theme_discovery_monthly and theme_delta_weekly (docs/superpowers/specs/2026-07-09-phase3b-theme-baskets-design.md).`

- [ ] **Step 7: Run tests to verify they pass**

```bash
python3 -m pytest tests/test_theme_crons.py -v
```

Expected: 2 PASS.

- [ ] **Step 8: Commit**

```bash
git add inngest_app tests/test_theme_crons.py
git commit -m "feat(autopilot): monthly discovery + weekly delta Inngest crons (paid step memoized alone)"
```

---

### Task 11: Synthetic basket ranking — `theme_strength.py` + batch fetch

**Files:**
- Modify: `execution/market_data.py` (add `fetch_closes_batch`)
- Create: `execution/indicators/theme_strength.py`
- Test: `tests/test_execution_theme_strength.py`

**Interfaces:**
- Produces: `fetch_closes_batch(tickers: List[str], period: str = "1y") -> Dict[str, pd.Series]` — ONE `yf.download` call for up to 240 tickers (never per-ticker loops; the Sunday cron fetch-count rider).
- Produces: `rank_themes(themes: List[Dict], closes: Dict[str, pd.Series], spy: pd.Series) -> Dict` where `themes = [{"slug","name","confidence","tickers":[...]}]`, returning `{"rankings", "rotations", "missing", "history"}`:
  - `rankings`: `rank_sectors(..., label_key="theme")` output + `slug`, `confidence`, `constituent_count` per entry
  - `rotations`: `detect_rotations(min_rank_gain=THEME_ROTATION_MIN_RANK_GAIN, label_key="theme")`
  - `missing`: `[{"slug", "reason"}]` for themes with < MIN_THEME_CONSTITUENTS index-eligible names or insufficient index history
  - `history`: `{slug: [{"weeks_ago", "score", "rank"}, ...]}` — trailing THEME_HISTORY_WEEKS, computed from CURRENT membership (sparkline only; NEVER backtest input)
- Consumes: `compute_relative_strength`, `rank_sectors`, `detect_rotations` from `sector_strength.py` (parameterized 3A API), `WINDOWS`, `BENCHMARK`.

- [ ] **Step 1: Write the failing tests**

`tests/test_execution_theme_strength.py`:

```python
"""Equal-weight synthetic basket index + RS ranking + sparkline history."""
import numpy as np
import pandas as pd
import pytest

from execution.indicators.theme_strength import build_theme_index, rank_themes

N = 200  # > 126+1 everywhere


def _series(daily_return, days=N, start=100.0):
    return pd.Series(start * (1 + daily_return) ** np.arange(days))


def _theme(slug, tickers):
    return {"slug": slug, "name": slug.title(), "confidence": 0.8, "tickers": list(tickers)}


def test_index_is_equal_weight_of_normalized_series():
    closes = {"A": _series(0.002, start=10.0), "B": _series(0.002, start=1000.0)}
    index, eligible = build_theme_index(closes)
    assert eligible == ["A", "B"]
    # both legs identical in return space -> index equals either normalized leg
    expected = _series(0.002, start=1.0)
    assert np.allclose(index.values, expected.values / expected.values[0])


def test_short_history_constituent_excluded():
    closes = {"A": _series(0.002), "B": _series(0.002, days=30)}
    _, eligible = build_theme_index(closes)
    assert eligible == ["A"]


def test_rank_themes_orders_by_relative_strength():
    spy = _series(0.001)
    closes = {f"H{i}": _series(0.003) for i in range(5)}
    closes.update({f"L{i}": _series(-0.001) for i in range(5)})
    themes = [_theme("hot", [f"H{i}" for i in range(5)]),
              _theme("cold", [f"L{i}" for i in range(5)])]
    out = rank_themes(themes, closes, spy)
    assert [r["slug"] for r in out["rankings"]] == ["hot", "cold"]
    top = out["rankings"][0]
    assert top["theme"] == "Hot" and top["confidence"] == 0.8
    assert top["constituent_count"] == 5
    assert out["missing"] == []


def test_theme_below_min_constituents_goes_missing():
    spy = _series(0.001)
    closes = {"A": _series(0.002), "B": _series(0.002)}
    out = rank_themes([_theme("thin", ["A", "B", "GONE1", "GONE2", "GONE3"])], closes, spy)
    assert out["rankings"] == []
    assert out["missing"][0]["slug"] == "thin"
    assert "2" in out["missing"][0]["reason"]


def test_history_has_12_weekly_points_with_ranks():
    spy = _series(0.001)
    closes = {f"H{i}": _series(0.003) for i in range(5)}
    closes.update({f"L{i}": _series(-0.001) for i in range(5)})
    themes = [_theme("hot", [f"H{i}" for i in range(5)]),
              _theme("cold", [f"L{i}" for i in range(5)])]
    out = rank_themes(themes, closes, spy)
    hot = out["history"]["hot"]
    assert len(hot) == 12
    assert hot[-1]["weeks_ago"] == 0
    assert all(p["rank"] == 1 for p in hot)  # hot dominates every week


def test_missing_ticker_series_tolerated():
    spy = _series(0.001)
    closes = {f"H{i}": _series(0.003) for i in range(5)}
    themes = [_theme("hot", [f"H{i}" for i in range(5)] + ["ABSENT"])]
    out = rank_themes(themes, closes, spy)
    assert out["rankings"][0]["constituent_count"] == 5
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
python3 -m pytest tests/test_execution_theme_strength.py -v
```

Expected: FAIL — module not found.

- [ ] **Step 3: Implement `execution/indicators/theme_strength.py`**

```python
"""Theme basket synthetic index + relative strength ranking (Phase 3B).

Equal weight is the point: a $400M photonics mover counts as much as RMBS —
this surfaces broad small-cap theme moves a cap-weighted proxy would hide.
Pure functions; same parameterized RS math as sectors/industries.

history is computed from CURRENT membership over trailing weeks — sparkline
context only. It answers "how did today's basket perform", NOT "when would
the engine have flagged this". The 3D backtest must only use live-recorded
MarketOutlook rows (spec-bound).
"""
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd

from execution.constants import (
    BENCHMARK,
    MIN_THEME_CONSTITUENTS,
    THEME_HISTORY_WEEKS,
    THEME_ROTATION_MIN_RANK_GAIN,
    WINDOWS,
)
from execution.indicators.sector_strength import (
    compute_relative_strength,
    detect_rotations,
    rank_sectors,
)

_MIN_LEN = max(WINDOWS.values()) + 1
_TRADING_DAYS_PER_WEEK = 5


def build_theme_index(
    constituent_closes: Dict[str, pd.Series],
) -> Tuple[Optional[pd.Series], List[str]]:
    """Equal-weight index: mean of normalized (first=1.0) close series over the
    common tail. Constituents shorter than the longest RS window are excluded."""
    eligible = {
        t: s.dropna().reset_index(drop=True)
        for t, s in constituent_closes.items()
        if s is not None and len(s.dropna()) >= _MIN_LEN
    }
    if not eligible:
        return None, []
    common = min(len(s) for s in eligible.values())
    normed = []
    for t in sorted(eligible):
        tail = eligible[t].iloc[-common:].reset_index(drop=True)
        normed.append(tail / tail.iloc[0])
    index = pd.concat(normed, axis=1).mean(axis=1)
    return index, sorted(eligible)


def _score_history(
    idx_closes: Dict[str, pd.Series], label_map: Dict[str, str],
) -> Dict[str, List[Dict[str, Any]]]:
    out: Dict[str, List[Dict[str, Any]]] = {slug: [] for slug in label_map}
    for weeks_ago in range(THEME_HISTORY_WEEKS - 1, -1, -1):
        offset = weeks_ago * _TRADING_DAYS_PER_WEEK
        truncated = {}
        for key, s in idx_closes.items():
            if offset == 0:
                truncated[key] = s
            elif len(s) > offset:
                truncated[key] = s.iloc[:-offset]
        rel = compute_relative_strength(truncated, etf_map=label_map)
        if not rel:
            continue
        ranked = rank_sectors(rel, etf_map=label_map, label_key="theme")
        for position, r in enumerate(ranked, start=1):
            out[r["etf"]].append(
                {"weeks_ago": weeks_ago, "score": r["score"], "rank": position})
    return out


def rank_themes(
    themes: List[Dict[str, Any]],
    closes: Dict[str, pd.Series],
    spy: pd.Series,
) -> Dict[str, Any]:
    idx_closes: Dict[str, pd.Series] = {BENCHMARK: spy}
    label_map: Dict[str, str] = {}
    meta: Dict[str, Dict[str, Any]] = {}
    missing: List[Dict[str, str]] = []

    for theme in themes:
        series = {t: closes.get(t) for t in theme["tickers"]}
        index, eligible = build_theme_index(
            {t: s for t, s in series.items() if s is not None})
        if index is None or len(eligible) < MIN_THEME_CONSTITUENTS:
            missing.append({
                "slug": theme["slug"],
                "reason": f"only {len(eligible)} index-eligible constituents "
                          f"(need {MIN_THEME_CONSTITUENTS})"})
            continue
        idx_closes[theme["slug"]] = index
        label_map[theme["slug"]] = theme["name"]
        meta[theme["slug"]] = {"confidence": theme.get("confidence"),
                               "constituent_count": len(eligible)}

    rel = compute_relative_strength(idx_closes, etf_map=label_map)
    for slug in list(label_map):
        if slug not in rel:  # truncated common tail fell below the RS window
            missing.append({"slug": slug, "reason": "insufficient index history"})
            label_map.pop(slug)
            meta.pop(slug)

    rankings = rank_sectors(rel, etf_map=label_map, label_key="theme")
    for r in rankings:
        r["slug"] = r["etf"]
        r.update(meta[r["etf"]])
    rotations = detect_rotations(
        rankings, min_rank_gain=THEME_ROTATION_MIN_RANK_GAIN, label_key="theme")
    history = _score_history(idx_closes, label_map) if label_map else {}
    return {"rankings": rankings, "rotations": rotations,
            "missing": missing, "history": history}
```

- [ ] **Step 4: Add `fetch_closes_batch` to `execution/market_data.py`**

Append:

```python
def fetch_closes_batch(tickers, period: str = "1y") -> Dict[str, pd.Series]:
    """ONE yf.download for many tickers (theme constituents — up to ~240).

    Best-effort: missing/empty tickers are simply absent. Bypasses the
    per-ticker MarketDataClient deliberately — 240 sequential cached fetches
    in the Sunday cron is the failure mode this avoids.
    """
    import yfinance as yf  # noqa: PLC0415

    unique = sorted({t.upper() for t in tickers if t})
    if not unique:
        return {}
    try:
        df = yf.download(unique, period=period, auto_adjust=True,
                         progress=False, group_by="ticker", threads=True)
    except Exception:
        logger.exception("fetch_closes_batch: download failed")
        return {}
    if df is None or df.empty:
        return {}
    out: Dict[str, pd.Series] = {}
    if not isinstance(df.columns, pd.MultiIndex):  # single-ticker shape
        series = df.get("Close")
        if series is not None and not series.dropna().empty:
            out[unique[0]] = series.dropna().reset_index(drop=True)
        return out
    for ticker in unique:
        try:
            series = df[ticker]["Close"].dropna()
        except (KeyError, IndexError):
            continue
        if not series.empty:
            out[ticker] = series.reset_index(drop=True)
    return out
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
python3 -m pytest tests/test_execution_theme_strength.py tests/test_execution_market_data.py -v
```

Expected: new tests PASS; existing market_data tests still PASS (pure addition).

- [ ] **Step 6: Commit**

```bash
git add execution/indicators/theme_strength.py execution/market_data.py tests/test_execution_theme_strength.py
git commit -m "feat(autopilot): equal-weight theme basket ranking + 12-week sparkline history"
```

---

### Task 12: Wire themes into the Sunday outlook (isolated, degrade-to-null)

**Files:**
- Modify: `inngest_app/functions/weekly_outlook.py` (new step + strategist blacklist)
- Modify: `execution/outlook_service.py` (`build_outlook_record` + `store_outlook`)
- Test: modify `tests/test_execution_outlook_service.py`, `tests/test_execution_strategist.py`

**Interfaces:**
- Consumes: `rank_themes`, `fetch_closes_batch` (Task 11), `send_failure_alert` (Task 3).
- Produces: `MarketOutlook.themeRankings` populated (or omitted) every Sunday; `build_outlook_record` maps `indicators["themes"] -> "themeRankings"`.
- HARD CONTRACT: the strategist payload must never contain theme data; theme-pass failure must never block the sector outlook.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_execution_outlook_service.py` (match its existing fixture style — read the file first):

```python
def test_build_outlook_record_maps_theme_rankings():
    # reuse the file's existing indicators/strategist fixtures
    indicators = _indicators_fixture()          # existing helper in this file
    indicators["themes"] = {"rankings": [], "rotations": [], "missing": [], "history": {}}
    record = build_outlook_record(RUN_DATE, indicators, _strategist_fixture())
    assert record["themeRankings"] == indicators["themes"]


def test_build_outlook_record_theme_rankings_none_when_absent():
    record = build_outlook_record(RUN_DATE, _indicators_fixture(), _strategist_fixture())
    assert record["themeRankings"] is None


@pytest.mark.asyncio
async def test_store_outlook_omits_none_theme_rankings():
    db = _FakeDb()                              # existing stub in this file
    record = build_outlook_record(RUN_DATE, _indicators_fixture(), _strategist_fixture())
    await store_outlook(db, record)
    assert "themeRankings" not in db.marketoutlook.last_create_data
```

(If the file's helpers have different names, adapt the three tests to its actual fixtures — the assertions are the contract.)

In `tests/test_execution_strategist.py`, extend `test_prompt_isolated_from_sleeve_a_extended_signals` (line 40): add `"themes": {"rankings": [{"theme": "Photonics", "score": 0.02}]}` to `payload_with_extended`, and add `assert "themes" not in extended_prompt` and `assert "Photonics" not in extended_prompt`.

- [ ] **Step 2: Run tests to verify they fail**

```bash
python3 -m pytest tests/test_execution_outlook_service.py tests/test_execution_strategist.py -v
```

Expected: new tests FAIL (`themeRankings` KeyError / prompt not yet guaranteed).

- [ ] **Step 3: Update `execution/outlook_service.py`**

In `build_outlook_record`'s returned dict, after `"sizeStyle": indicators.get("size_style"),` add:

```python
        "themeRankings": indicators.get("themes"),
```

In `store_outlook`, extend the omission loop tuple:

```python
    for field in ("sectorRankings", "rotationFlags", "breadth",
                  "industryRankings", "sizeStyle", "themeRankings"):
```

- [ ] **Step 4: Add the theme step to `weekly_outlook.py`**

Insert between the strategist step and the store step (themes deliberately run AFTER the strategist — structurally impossible for the LLM to see them):

```python
        # Step 2.5: theme rankings (Phase 3B — Sleeve-A-only; degrades to None)
        async def compute_theme_rankings() -> "Optional[Dict[str, Any]]":
            from api.lib.db import get_db  # noqa: PLC0415
            from execution.alerts import send_failure_alert  # noqa: PLC0415
            from execution.constants import BENCHMARK  # noqa: PLC0415
            from execution.indicators.theme_strength import rank_themes  # noqa: PLC0415
            from execution.market_data import (  # noqa: PLC0415
                fetch_closes_batch, fetch_history_for,
            )
            try:
                db = await get_db()
                rows = await db.themebasket.find_many(
                    where={"status": "active"}, include={"constituents": True})
                themes = [{
                    "slug": r.slug, "name": r.name, "confidence": r.confidence,
                    "tickers": [c.ticker for c in (r.constituents or [])
                                if c.status == "active"],
                } for r in rows]
                themes = [t for t in themes if t["tickers"]]
                if not themes:
                    return None  # pre-first-discovery state: seeds have no constituents
                all_tickers = sorted({t for th in themes for t in th["tickers"]})
                closes = fetch_closes_batch(all_tickers)
                spy = fetch_history_for([BENCHMARK]).get(BENCHMARK)
                if spy is None:
                    raise RuntimeError("SPY history unavailable for theme pass")
                return rank_themes(themes, closes, spy)
            except Exception as exc:
                logger.exception("Outlook theme pass failed")
                await send_failure_alert(
                    "Outlook theme pass failed", f"{type(exc).__name__}: {exc}",
                    source="weekly_market_outlook")
                return None

        themes_result = await step.run("compute-theme-rankings", compute_theme_rankings)
```

In the store step, change the record construction to merge themes:

```python
            record = build_outlook_record(
                run_date, {**indicators, "themes": themes_result}, strategist)
```

In `strategist_step`, future-proof the blacklist:

```python
            payload = {k: v for k, v in indicators.items()
                       if k not in ("industry", "size_style", "themes")}
```

Add `Optional` to the module's `typing` import if missing.

- [ ] **Step 5: Run the outlook-adjacent suites**

```bash
python3 -m pytest tests/test_execution_outlook_service.py tests/test_execution_strategist.py tests/test_execution_industry_strength.py -v
```

Expected: ALL PASS (incl. the extended isolation test).

- [ ] **Step 6: Commit**

```bash
git add inngest_app/functions/weekly_outlook.py execution/outlook_service.py tests/
git commit -m "feat(autopilot): themeRankings in Sunday outlook — post-strategist step, degrade-to-null"
```

---

### Task 13: API — `/autopilot/reports` + theme fields on the outlook response

**Files:**
- Modify: `api/routes/autopilot.py`
- Test: modify `tests/test_autopilot_routes.py`

**Interfaces:**
- Produces: `GET /api/autopilot/reports?limit=&type=&severity=` (admin-gated) returning newest-first `EngineReportResponse[]`; `MarketOutlookResponse` gains `theme_rankings`, `theme_rotations`, `theme_missing`, `theme_history` (all Optional, None for legacy rows).
- Also applies the carried 3A rider: industry key access via `.get()` instead of direct subscripts.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_autopilot_routes.py` (match its existing row-stub style — read the file's existing `outlook_row_to_response` tests first):

```python
def test_outlook_response_includes_theme_fields():
    row = _outlook_row()  # existing stub factory in this file
    row.themeRankings = {
        "rankings": [{"slug": "photonics", "theme": "Photonics", "score": 0.02,
                      "rank_1m": 1, "rank_3m": 2, "rank_6m": 2, "rs_1m": 0.01,
                      "rs_3m": 0.02, "rs_6m": 0.03, "rank_change": 1, "etf": "photonics",
                      "confidence": 0.8, "constituent_count": 7}],
        "rotations": [], "missing": [], "history": {"photonics": []},
    }
    resp = outlook_row_to_response(row)
    assert resp.theme_rankings[0]["slug"] == "photonics"
    assert resp.theme_rotations == []
    assert resp.theme_history == {"photonics": []}


def test_outlook_response_theme_fields_none_for_legacy_rows():
    row = _outlook_row()
    row.themeRankings = None
    resp = outlook_row_to_response(row)
    assert resp.theme_rankings is None
    assert resp.theme_history is None


def test_outlook_response_survives_partial_theme_blob():
    row = _outlook_row()
    row.themeRankings = {"rankings": []}  # drifted blob missing keys
    resp = outlook_row_to_response(row)
    assert resp.theme_rankings == []
    assert resp.theme_rotations is None  # .get() hardening, no KeyError


def test_engine_report_response_mapping():
    from api.routes.autopilot import engine_report_row_to_response
    row = _Row(id="r1", createdAt=datetime(2026, 7, 9), type="membership_change",
               severity="info", source="theme_delta_weekly", title="t", body={"a": 1})
    resp = engine_report_row_to_response(row)
    assert resp.type == "membership_change" and resp.body == {"a": 1}
```

Also add an endpoint test for `/api/autopilot/reports` following the file's existing pattern for admin-gated endpoints (same auth override + stub db it uses for `/autopilot/outlook`): stub `db.enginereport.find_many` to return two rows, assert 200, newest-first passthrough, and that `type=`/`severity=` land in the `where` kwargs.

- [ ] **Step 2: Run tests to verify they fail**

```bash
python3 -m pytest tests/test_autopilot_routes.py -v
```

Expected: new tests FAIL.

- [ ] **Step 3: Implement in `api/routes/autopilot.py`**

Extend `MarketOutlookResponse`:

```python
    # Phase 3B theme baskets — None until the first post-3B outlook runs
    theme_rankings: Optional[List[dict]] = None
    theme_rotations: Optional[List[dict]] = None
    theme_missing: Optional[List[dict]] = None
    theme_history: Optional[dict] = None
```

In `outlook_row_to_response`, harden industry access (3A rider) and add themes:

```python
    industry = getattr(row, "industryRankings", None) or None
    themes = getattr(row, "themeRankings", None) or None
    return MarketOutlookResponse(
        ...existing fields...,
        industry_rankings=industry.get("rankings") if industry else None,
        industry_rotations=industry.get("rotations") if industry else None,
        industry_missing=industry.get("missing") if industry else None,
        size_style=getattr(row, "sizeStyle", None),
        theme_rankings=themes.get("rankings") if themes else None,
        theme_rotations=themes.get("rotations") if themes else None,
        theme_missing=themes.get("missing") if themes else None,
        theme_history=themes.get("history") if themes else None,
    )
```

Add the reports endpoint (below the outlook endpoint, above the Phase 2 section):

```python
class EngineReportResponse(BaseModel):
    """One EngineReport journal row."""
    id: str
    created_at: datetime
    type: str
    severity: str
    source: str
    title: str
    body: dict


def engine_report_row_to_response(row) -> EngineReportResponse:
    return EngineReportResponse(
        id=row.id, created_at=row.createdAt, type=row.type,
        severity=row.severity, source=row.source, title=row.title,
        body=row.body or {},
    )


@router.get("/autopilot/reports", response_model=List[EngineReportResponse])
async def get_engine_reports(
    limit: int = 50,
    type: Optional[str] = None,
    severity: Optional[str] = None,
    admin: User = Depends(require_admin),
):
    """Engine journal feed, newest first. The owner's veto surface."""
    db = await get_db()
    where: dict = {}
    if type:
        where["type"] = type
    if severity:
        where["severity"] = severity
    rows = await db.enginereport.find_many(
        where=where or None,
        take=max(1, min(limit, 200)),
        order={"createdAt": "desc"},
    )
    return [engine_report_row_to_response(r) for r in rows]
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
python3 -m pytest tests/test_autopilot_routes.py -v
```

Expected: ALL PASS (existing + new).

- [ ] **Step 5: Commit**

```bash
git add api/routes/autopilot.py tests/test_autopilot_routes.py
git commit -m "feat(autopilot): /autopilot/reports journal endpoint + theme fields on outlook API"
```

---

### Task 14: Frontend — Leading Themes card + Engine Journal feed

**Files:**
- Modify: `frontend/types/api.ts` (~line 1121, next to MarketOutlookResponse)
- Modify: the apiClient (find it: `grep -rn "getMarketOutlook" frontend/lib --include="*.ts"`) and `frontend/lib/hooks/useAdmin.ts`
- Modify: `frontend/components/autopilot/MarketOutlookPanel.tsx`
- Create: `frontend/components/autopilot/EngineJournalPanel.tsx`
- Modify: `frontend/app/admin/page.tsx` (mount the journal panel next to MarketOutlookPanel)

**Interfaces:**
- Consumes: Task 13's response shapes.
- Produces: `ThemeRanking`, `ThemeRotationFlag`, `ThemeMissing`, `ThemeHistoryPoint`, `EngineReportEntry` types; `useEngineReports()` hook; two UI surfaces.
- No backend/frontend test runner exists for these components — verification is `npx tsc --noEmit`.

- [ ] **Step 1: Add types to `frontend/types/api.ts`**

Insert before `MarketOutlookResponse`:

```typescript
export interface ThemeRanking {
  etf: string // slug (synthetic index key)
  slug: string
  theme: string
  rs_1m: number
  rs_3m: number
  rs_6m: number
  rank_1m: number
  rank_3m: number
  rank_6m: number
  rank_change: number
  score: number
  confidence: number
  constituent_count: number
}

export interface ThemeRotationFlag {
  etf: string
  theme: string
  direction: 'into' | 'out_of'
  rank_change: number
}

export interface ThemeMissing {
  slug: string
  reason: string
}

export interface ThemeHistoryPoint {
  weeks_ago: number
  score: number
  rank: number
}

export interface EngineReportEntry {
  id: string
  created_at: string
  type: string
  severity: 'info' | 'warning' | 'critical'
  source: string
  title: string
  body: Record<string, unknown>
}
```

Extend `MarketOutlookResponse`:

```typescript
  theme_rankings: ThemeRanking[] | null
  theme_rotations: ThemeRotationFlag[] | null
  theme_missing: ThemeMissing[] | null
  theme_history: Record<string, ThemeHistoryPoint[]> | null
```

- [ ] **Step 2: apiClient method + hook**

In the apiClient class (same file/pattern as `getMarketOutlook` — copy its request-helper usage and auth handling exactly):

```typescript
  async getEngineReports(params?: { type?: string; severity?: string; limit?: number }): Promise<EngineReportEntry[]> {
    const q = new URLSearchParams()
    if (params?.type) q.set('type', params.type)
    if (params?.severity) q.set('severity', params.severity)
    if (params?.limit) q.set('limit', String(params.limit))
    const suffix = q.toString() ? `?${q.toString()}` : ''
    return this.request(`/api/autopilot/reports${suffix}`)
  }
```

(If the class's request helper is named differently — e.g. `this.fetchJson` — use that name; `getMarketOutlook` is the template.)

In `frontend/lib/hooks/useAdmin.ts`, after `useMarketOutlook` (line 89):

```typescript
/**
 * Engine journal feed (theme changes, failures, rebalance summaries)
 */
export function useEngineReports(type?: string) {
  return useQuery({
    queryKey: [...adminKeys.all, 'engineReports', type ?? 'all'],
    queryFn: () => apiClient.getEngineReports({ type, limit: 50 }),
    staleTime: 1000 * 60 * 5,
  })
}
```

(Check how `adminKeys` is structured at the top of the file; if it's a keys object with methods, add `engineReports: (type: string) => [...adminKeys.all, 'engineReports', type] as const` and use it.)

- [ ] **Step 3: Leading Themes card in `MarketOutlookPanel.tsx`**

Destructure the new fields in `MarketOutlookContent` (`theme_rankings`, `theme_rotations`, `theme_missing`, `theme_history`). Add below the Leading Industries card, following its exact Card/heading/row idiom (read that card's JSX first and mirror it):

```tsx
{theme_rankings && theme_rankings.length > 0 && (
  <Card>
    <CardHeader>
      <CardTitle>Leading Themes</CardTitle>
    </CardHeader>
    <CardContent>
      <div className="space-y-2">
        {theme_rankings.map((t, i) => (
          <div key={t.slug} className="flex items-center justify-between gap-3 text-sm">
            <div className="flex items-center gap-2 min-w-0">
              <span className="text-text-secondary w-5 shrink-0">{i + 1}</span>
              <span className="truncate">{t.theme}</span>
              <span className="text-text-secondary text-xs shrink-0">
                {t.constituent_count} names
              </span>
              {t.rank_change >= 5 && <Badge variant="success">rotating in</Badge>}
              {t.rank_change <= -5 && <Badge variant="error">rotating out</Badge>}
            </div>
            <div className="flex items-center gap-3 shrink-0">
              <ThemeSparkline points={theme_history?.[t.slug] ?? []} />
              <span className="tabular-nums">{t.score >= 0 ? '+' : ''}{t.score.toFixed(4)}</span>
            </div>
          </div>
        ))}
        {theme_missing && theme_missing.length > 0 && (
          <p className="text-xs text-text-secondary pt-2">
            Not ranked: {theme_missing.map((m) => `${m.slug} (${m.reason})`).join('; ')}
          </p>
        )}
      </div>
    </CardContent>
  </Card>
)}
```

Add the sparkline helper in the same file (pure inline SVG, no deps):

```tsx
function ThemeSparkline({ points }: { points: ThemeHistoryPoint[] }) {
  if (points.length < 2) return null
  const scores = points.map((p) => p.score)
  const min = Math.min(...scores)
  const max = Math.max(...scores)
  const span = max - min || 1
  const coords = points
    .map((p, i) => `${(i / (points.length - 1)) * 60},${18 - ((p.score - min) / span) * 16}`)
    .join(' ')
  return (
    <svg width="60" height="20" className="text-accent shrink-0" aria-hidden="true">
      <polyline points={coords} fill="none" stroke="currentColor" strokeWidth="1.5" />
    </svg>
  )
}
```

Import `ThemeHistoryPoint` (and the other new types as needed) from `@/types/api`.

- [ ] **Step 4: Create `frontend/components/autopilot/EngineJournalPanel.tsx`**

```tsx
'use client'

import { useState } from 'react'
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Skeleton } from '@/components/ui/skeleton'
import { useEngineReports } from '@/lib/hooks/useAdmin'
import { formatDate } from '@/lib/utils/formatting'
import type { EngineReportEntry } from '@/types/api'

const SEVERITY_DOT: Record<EngineReportEntry['severity'], string> = {
  info: 'bg-text-secondary',
  warning: 'bg-yellow-500',
  critical: 'bg-red-500',
}

function EntryRow({ entry }: { entry: EngineReportEntry }) {
  const [open, setOpen] = useState(false)
  return (
    <div className="py-2 border-b border-border last:border-b-0">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="flex w-full items-center gap-2 text-left text-sm"
      >
        <span className={`h-2 w-2 rounded-full shrink-0 ${SEVERITY_DOT[entry.severity]}`} />
        <Badge variant="secondary">{entry.type.replace(/_/g, ' ')}</Badge>
        <span className="truncate flex-1">{entry.title}</span>
        <span className="text-xs text-text-secondary shrink-0">
          {formatDate(entry.created_at)}
        </span>
      </button>
      {open && (
        <pre className="mt-2 max-h-64 overflow-auto rounded bg-surface-secondary p-3 text-xs">
          {JSON.stringify(entry.body, null, 2)}
        </pre>
      )}
    </div>
  )
}

export function EngineJournalPanel() {
  const { data, isLoading, error } = useEngineReports()

  return (
    <Card>
      <CardHeader>
        <CardTitle>Engine Journal</CardTitle>
      </CardHeader>
      <CardContent>
        {isLoading && (
          <div className="space-y-2">
            {[1, 2, 3].map((i) => (
              <Skeleton key={i} className="h-8" />
            ))}
          </div>
        )}
        {error && <p className="text-text-secondary text-sm">Failed to load journal</p>}
        {data && data.length === 0 && (
          <p className="text-text-secondary text-sm">
            Nothing yet — entries appear when the engine changes themes, rebalances, or fails.
          </p>
        )}
        {data && data.map((entry) => <EntryRow key={entry.id} entry={entry} />)}
      </CardContent>
    </Card>
  )
}
```

(Verify `border-border`, `bg-surface-secondary`, and `Badge` variant names against what MarketOutlookPanel/theme already use in this repo; substitute the repo's actual tokens if they differ.)

- [ ] **Step 5: Mount in `frontend/app/admin/page.tsx`**

Find where `<MarketOutlookPanel />` renders and add `<EngineJournalPanel />` directly below it, importing from `@/components/autopilot/EngineJournalPanel`.

- [ ] **Step 6: Typecheck**

```bash
cd /Users/tui/dvrg/frontend && npx tsc --noEmit
```

Expected: clean (or only pre-existing errors — verify by running the same command on the base branch if anything looks unrelated).

- [ ] **Step 7: Commit**

```bash
git add frontend
git commit -m "feat(autopilot): Leading Themes card + Engine Journal feed on admin tab"
```

---

### Task 15: Typed journal entries in the execution crons (+ frozen re-alert fix)

**Files:**
- Modify: `inngest_app/functions/execution_daily.py` (breaker_event on transitions ONLY — closes the Phase 2 "re-alerts while frozen" rider)
- Modify: `inngest_app/functions/execution_weekly.py` (one rebalance_summary at the end)
- Test: modify `tests/test_execution_daily.py`, `tests/test_execution_weekly.py`

**Interfaces:**
- Consumes: `write_report` (Task 2), `get_sleeve_state` (existing `execution/sleeve_service.py`).
- Produces: `breaker_event` entries (critical) only when Sleeve B transitions active→frozen or active→halted; `rebalance_summary` entry (info) per weekly run.

- [ ] **Step 1: Read the two functions in full**

```bash
sed -n 1,200p /Users/tui/dvrg/inngest_app/functions/execution_daily.py
sed -n 200,310p /Users/tui/dvrg/inngest_app/functions/execution_weekly.py
```

Locate: (a) the reconcile-mismatch branch (~line 119-137) that sets `frozen` and alerts, (b) the circuit-breaker branch (~line 170-195), (c) execution_weekly's final summary construction (~line 300-308).

- [ ] **Step 2: Write the failing tests**

In `tests/test_execution_daily.py`, following the file's existing step-stub pattern (read its fixtures first):

```python
@pytest.mark.asyncio
async def test_frozen_transition_writes_breaker_event_once(monkeypatch):
    """First mismatch day: breaker_event written. Second day (already frozen):
    NO new breaker_event, NO repeat alert — the Phase 2 rider."""
    # arrange the file's existing reconcile-mismatch fixture twice:
    # day 1 with sleeve state status="active", day 2 with status="frozen";
    # capture write_report calls via an async fake on the module under test.
    # assert exactly one ("breaker_event", "critical") call across both days.


@pytest.mark.asyncio
async def test_breaker_trip_writes_breaker_event(monkeypatch):
    """active -> halted transition writes one breaker_event with equity stats."""
```

In `tests/test_execution_weekly.py`:

```python
@pytest.mark.asyncio
async def test_weekly_run_writes_rebalance_summary(monkeypatch):
    """A completed rebalance writes one rebalance_summary EngineReport whose
    body contains the orders/fills/regime the run returned."""
```

Fill the three test bodies concretely against the fixtures those files actually use — the docstrings above are the contracts to assert; the arrange code must reuse the files' existing stub helpers rather than inventing new ones.

- [ ] **Step 3: Run tests to verify they fail**

```bash
python3 -m pytest tests/test_execution_daily.py tests/test_execution_weekly.py -v
```

Expected: new tests FAIL.

- [ ] **Step 4: Implement in `execution_daily.py`**

Reconcile-mismatch branch — check prior status BEFORE freezing, journal only on transition:

```python
            if mismatches:
                from execution.reporting import write_report  # noqa: PLC0415
                from execution.sleeve_service import get_sleeve_state  # noqa: PLC0415
                state = await get_sleeve_state(db, SLEEVE_B)
                was_frozen = state is not None and state.status == "frozen"
                await set_sleeve_status(db, SLEEVE_B, "frozen", "; ".join(mismatches))
                if not was_frozen:
                    await send_failure_alert(
                        "position reconciliation mismatch — Sleeve B frozen",
                        "\n".join(mismatches), source="execution_daily")
                    await write_report(
                        "breaker_event", "critical", "execution_daily",
                        "Sleeve B frozen: reconciliation mismatch",
                        {"transition": "active->frozen", "mismatches": mismatches}, db=db)
                return {"status": "frozen", "mismatches": recon["mismatches"]}
```

Circuit-breaker branch — the existing code already alerts only on the active→halted transition; add alongside the existing `send_failure_alert`:

```python
                await write_report(
                    "breaker_event", "critical", "execution_daily",
                    "Sleeve B circuit breaker tripped",
                    {"transition": "active->halted",
                     "rule": "-15pp vs SPY since inception"}, db=db)
```

(Import `write_report` function-locally in that step like every other import in the file; include the sleeve/SPY return numbers the branch already has in scope in the body dict.)

- [ ] **Step 5: Implement in `execution_weekly.py`**

Immediately before `return summary` (~line 308), inside the same step that builds `summary`:

```python
        async def journal_summary() -> Dict[str, Any]:
            from api.lib.db import get_db  # noqa: PLC0415
            from execution.reporting import write_report  # noqa: PLC0415
            await write_report(
                "rebalance_summary", "info", "execution_weekly",
                f"Sleeve B rebalance — {summary.get('status', 'ok')}",
                summary, db=await get_db())
            return {"journaled": True}

        await step.run("journal-rebalance-summary", journal_summary)
        return summary
```

(If `summary` is built inside a step and returned, place the journal step after it with the summary in scope — match the file's actual structure found in Step 1; the contract is ONE rebalance_summary row per completed weekly run, containing the run's summary dict.)

- [ ] **Step 6: Run tests to verify they pass**

```bash
python3 -m pytest tests/test_execution_daily.py tests/test_execution_weekly.py -v
```

Expected: ALL PASS (existing + new).

- [ ] **Step 7: Full touched-suite sweep + commit**

```bash
python3 -m pytest tests/test_execution_reporting.py tests/test_execution_alerts.py \
  tests/test_execution_research_feed.py tests/test_theme_validation.py \
  tests/test_theme_parser.py tests/test_theme_prompts.py tests/test_theme_lifecycle.py \
  tests/test_theme_discovery.py tests/test_theme_crons.py \
  tests/test_execution_theme_strength.py tests/test_execution_outlook_service.py \
  tests/test_execution_strategist.py tests/test_autopilot_routes.py \
  tests/test_execution_daily.py tests/test_execution_weekly.py \
  tests/test_execution_market_data.py -q
```

Expected: ALL PASS.

```bash
git add inngest_app tests
git commit -m "feat(autopilot): breaker_event + rebalance_summary journal entries; frozen re-alert fix"
```

---

## Go-Live Checklist (operator steps — after all tasks green)

Execution order matters; this mirrors the 3A go-live exactly:

1. Push branch, open PR against main. Review package = full branch diff.
2. **BEFORE merging:** apply the migration to Neon prod:
   `python3 -m prisma migrate deploy --schema db/schema.prisma`
   (merge auto-deploys Railway; the regenerated client SELECTs the new
   columns — an un-migrated DB would break every MarketOutlook read/write
   including weekly batch and Sleeve B preflight.)
3. Verify `ANTHROPIC_API_KEY` is set on Railway (it is — the strategist uses
   it); no new env vars are required.
4. Merge PR → Railway auto-deploys → check `/api/health` returns 200.
5. Re-sync the Inngest app: 6 functions must appear
   (weekly-market-outlook, weekly-batch, execution-daily, execution-weekly,
   theme-discovery-monthly, theme-delta-weekly).
6. **Manually invoke `theme-discovery-monthly` once** (Inngest dashboard →
   function → Invoke). The cron won't fire until the 1st of next month and
   the six seed themes have no constituents until the first reasoning pass
   runs. Verify: ThemeBasket rows gain constituents; EngineReport rows
   appear; check the Engine Journal panel.
7. Confirm cost posture: one sonnet+web-search call (~$1-3); weekly haiku
   deltas from Saturday.
8. Next Sunday 20:00 UTC: verify `themeRankings` lands on the new
   MarketOutlook row and the Leading Themes card renders.

## Out of Scope (do not build here)

- Candidate universe wiring / any trading effect (3C).
- Small-cap execution guardrails: %-of-ADV sizing, limit orders, vol stops (3C).
- Backtest harness (3D) — and it must use only live-recorded outlook rows.
- Journal ack/read-state UI, full dashboard (Phase 4).
- The dormant outlook email step in weekly_outlook.py stays as-is (skipped
  without OWNER_EMAIL) — only alerts.py's email path is deleted in 3B.





