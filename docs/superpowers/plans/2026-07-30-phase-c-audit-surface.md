# Phase C — Audit Surface (This Week Extension) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Persist the position plan and price math the engine already computes, record price-conditional passes, and render all of it on the This Week tab — the owner's weekly audit surface.

**Architecture:** Three write-side additions (a `positionPlan` column filled through the existing journal→fill→provenance pipeline; three price-math keys in the order journal; one optional `reconsider_if` field on passes), one endpoint extension (`GET /autopilot/week` gains `plan`, `entry_forensics`, `market_view`, `reconsider_if`), and a WeekPanel split into `PositionCard` / `DecisionsSection` / `NoBuyBanner`. Records more, shows more, decides nothing.

**Tech Stack:** Python 3.9 (`/usr/bin/python3`), Prisma (hand-written SQL migration), FastAPI/Pydantic, Next.js + TypeScript (shadcn-style components, TanStack Query).

## Global Constraints

- Test command: `/usr/bin/python3 -m pytest <files> --no-cov` (never a venv python).
- Migration: hand-written SQL + `prisma migrate deploy`; **deployed to Neon before merge** (memory `prisma-migrate-dev-broken`). Locally the prisma CLI is unavailable — the migration file is authored and validated by SQL review only; deploy happens at merge time (operator step in the PR body).
- **No behavior change to entries, exits, sizing, stages, or Sleeve B.** This phase records and renders; it never decides. No approval gates (owner ruling 2026-07-20).
- A malformed plan still costs the ladder loudly and never the entry (PR #27 posture). Provenance persistence is best-effort and never sinks the fills sweep.
- The fill path is Inngest: plan persistence gets an idempotency/replay test (PR #12 lesson — inline harnesses hide replay bugs).
- Frontend verification is `npx tsc --noEmit` + `npm run build` in `frontend/` (no frontend test infra exists; not introduced here).
- UI renders every absence as a labeled absence — "no plan recorded (pre-Phase-C entry)", never an empty box or invented data.
- Branch: `feat/phase-c-audit-surface` **already exists** with the spec committed (`0640d3f`); continue on it.
- Commit after every task.

## Key existing anchors (verified on main @ 9730d61)

- Planner passes the full memo action through: `item = {"slug": slug, "stage": stage, **a}` (`execution/thesis/planner.py:105`) — so `position_plan` (attached by `execution/thesis/parser.py` when valid) **already rides the planned entry** into the funnel; the funnel just never reads it.
- Order journal dict: `inngest_app/functions/sleeve_a_funnel.py:585-600`; `price`/`sma20`/`atr` are in scope at `:495-501`.
- Fill path: `execution/sleeve_service.py::apply_fill` stores the journal on EngineTrade and creates positions with `thesis=Json(journal)`; `inngest_app/functions/execution_daily.py:53-84 _persist_position_provenance` copies journal keys onto the EnginePosition row post-fill — that is the hook for `positionPlan`.
- Validated plan shape (`execution/thesis/position_plan.py::validate_plan`): `{"ladder": [{"price": float, "size_pct": float, "why": str}], "thesis_break": str, "exit_plan": {"posture": str, "why": str, "fraction"?: float} | None, "target_weight"?: float}`.
- `_passed_on` (`execution/thesis/parser.py:85-111`) returns `[{"ticker", "reason"}]`; prompt's passed_on schema block at `execution/thesis/prompts.py:198`, rule 7 at `:72`.
- Week endpoint: `api/routes/autopilot.py:436 get_week`, models `WeekPosition`/`WeekAction`/`WeekThesis`/`WeekResponse` at `:342-382`. Memo `market_view` is stored verbatim in the latest `thesis_memo` EngineReport body (`execution/thesis/memo.py::persist_memo`).
- Frontend: `frontend/components/autopilot/WeekPanel.tsx` (254 lines — split target), types at `frontend/types/api.ts:1906-1960`, hook `useWeek` in `frontend/lib/hooks/useAdmin.ts`.
- EnginePosition table: Prisma model `EnginePosition`, no `@@map` → physical table `"EnginePosition"`. Migrations dir pattern: `db/migrations/<YYYYMMDDHHMMSS>_<name>/migration.sql`.

---

### Task 1: Migration + order-journal enrichment (plan + price math)

**Files:**
- Create: `db/migrations/20260730000000_engine_position_plan/migration.sql`
- Modify: `db/schema.prisma` (EnginePosition model)
- Modify: `inngest_app/functions/sleeve_a_funnel.py` (journal dict, ~line 585)
- Test: `tests/test_funnel_entries.py` (append)

**Interfaces:**
- Consumes: planned entry dicts already carrying `position_plan` (planner spread, see anchors).
- Produces (Tasks 2, 4 rely on): order journal dict gains keys `"position_plan"` (validated plan dict or None), `"price"`, `"sma20"`, `"atr"` (floats). Schema column `positionPlan Json?` on EnginePosition.

- [ ] **Step 1: Write the migration**

Create `db/migrations/20260730000000_engine_position_plan/migration.sql`:

```sql
-- Phase C (audit surface): persist the memo's position plan on the position.
-- The plan (ladder rungs, thesis_break, exit posture) has been validated and
-- dropped since PR #27; from this migration on it lands at fill time and the
-- crowded-winner review's "what was our plan entering?" has something to read.
ALTER TABLE "EnginePosition" ADD COLUMN "positionPlan" JSONB;
```

And in `db/schema.prisma`, add to `model EnginePosition` after the `dcaState` line:

```prisma
  positionPlan    Json?    // memo's plan at entry: ladder rungs, thesis_break, exit posture (Phase C)
```

- [ ] **Step 2: Write the failing test**

Append to `tests/test_funnel_entries.py` (match the file's existing fixture style — it already exercises `_handshake_and_enter` with `_planned(...)` helpers; extend the planned-entry fixture with a plan and assert the submitted journal):

```python
# ── Phase C: the order journal carries the plan and its price math ───────────

_PLAN = {"ladder": [{"price": 340.0, "size_pct": 0.5, "why": "first rung"}],
         "thesis_break": "capex guidance cut two quarters running",
         "exit_plan": {"posture": "let_run", "why": "constraint intact"}}


def test_entry_journal_carries_position_plan_and_price_math():
    """Phase C §3.1-3.2: the journal is the vehicle that gets the plan to the
    position row, and the price-math inputs make every limit self-explaining.
    A missing plan journals as None — never invented."""
    db = MagicMock()
    client = MagicMock()
    client.submit_limit_buy = AsyncMock()
    entry = _planned("AEHR")
    entry["position_plan"] = _PLAN
    with patch.object(saf, "check_disqualifiers",
                      new=AsyncMock(return_value={"disqualified": False,
                                                  "checked": True})), \
         patch.object(saf, "_latest_full_signal_id",
                      new=AsyncMock(return_value=None)), \
         patch.object(saf, "write_report", new=AsyncMock()):
        _run(saf._handshake_and_enter(
            db, client, planned_entries=[entry],
            screen_by_symbol={"AEHR": _memo_screen("AEHR")},
            run_date=NOW, sleeve_equity=70_000.0, deployable=49_000.0,
            cash_available=49_000.0, holdings=[], sector_by_symbol={},
            other_sleeve_sector_notional={}, allow_buys=True, step=None,
        ))
    journal = client.submit_limit_buy.call_args.kwargs["journal"]
    assert journal["position_plan"] == _PLAN
    screen = _memo_screen("AEHR")
    assert journal["price"] == float(screen["price"])
    assert journal["sma20"] == float(screen["sma20"])
    assert journal["atr"] == float(screen["atr"])


def test_entry_without_plan_journals_none_not_missing():
    db = MagicMock()
    client = MagicMock()
    client.submit_limit_buy = AsyncMock()
    with patch.object(saf, "check_disqualifiers",
                      new=AsyncMock(return_value={"disqualified": False,
                                                  "checked": True})), \
         patch.object(saf, "_latest_full_signal_id",
                      new=AsyncMock(return_value=None)), \
         patch.object(saf, "write_report", new=AsyncMock()):
        _run(saf._handshake_and_enter(
            db, client, planned_entries=[_planned("AEHR")],
            screen_by_symbol={"AEHR": _memo_screen("AEHR")},
            run_date=NOW, sleeve_equity=70_000.0, deployable=49_000.0,
            cash_available=49_000.0, holdings=[], sector_by_symbol={},
            other_sleeve_sector_notional={}, allow_buys=True, step=None,
        ))
    journal = client.submit_limit_buy.call_args.kwargs["journal"]
    assert "position_plan" in journal and journal["position_plan"] is None
```

Note: `tests/test_funnel_entries.py` may define its own local harness rather than importing from `test_sleeve_a_funnel_cron`. If `_planned` / `_memo_screen` / `_run` / `saf` live in `tests/test_sleeve_a_funnel_cron.py` instead, put these two tests THERE (same code) — whichever file already exercises `_handshake_and_enter`.

- [ ] **Step 3: Run to verify failure**

Run: `/usr/bin/python3 -m pytest tests/test_funnel_entries.py tests/test_sleeve_a_funnel_cron.py --no-cov -q -k "journal_carries or journals_none"`
Expected: FAIL — `KeyError: 'position_plan'`

- [ ] **Step 4: Implement**

In `inngest_app/functions/sleeve_a_funnel.py`, extend the journal dict (~line 585) — after the `"entry_style": entry_style,` line add:

```python
                # Phase C (audit surface): the plan rides the journal to the
                # position row, and the price-math inputs make the limit
                # self-explaining forever (limit = last close for at_market;
                # max(sma20, price − ATR) for on_pullback). A memo entry whose
                # plan was dropped as malformed journals None — the absence is
                # part of the record.
                "position_plan": entry.get("position_plan"),
                "price": price, "sma20": sma20, "atr": atr,
```

- [ ] **Step 5: Run to verify pass**

Run: `/usr/bin/python3 -m pytest tests/test_funnel_entries.py tests/test_sleeve_a_funnel_cron.py --no-cov -q`
Expected: all PASS

- [ ] **Step 6: Commit**

```bash
git add db/migrations/20260730000000_engine_position_plan/migration.sql db/schema.prisma inngest_app/functions/sleeve_a_funnel.py tests/
git commit -m "feat(audit): journal carries the position plan and its price math; positionPlan column"
```

---

### Task 2: Provenance copies the plan to the position (with replay test)

**Files:**
- Modify: `inngest_app/functions/execution_daily.py::_persist_position_provenance` (lines 53-84)
- Test: `tests/test_execution_daily.py` (append)

**Interfaces:**
- Consumes: order journal key `"position_plan"` (Task 1).
- Produces (Task 4 relies on): `EnginePosition.positionPlan` populated after a filled buy whose journal carried a plan; latest plan wins on adds; absent/malformed → column untouched.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_execution_daily.py` (match its existing mock style — it already tests `_persist_position_provenance` or the fills sweep; use the same `SimpleNamespace`/`MagicMock` idioms found there):

```python
# ── Phase C: the plan lands on the position at fill ──────────────────────────
import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import inngest_app.functions.execution_daily as xd

_PLAN = {"ladder": [{"price": 340.0, "size_pct": 0.5, "why": "r"}],
         "thesis_break": "capex cut", "exit_plan": None}


def _order(symbol="AEHR", journal=None):
    return SimpleNamespace(symbol=symbol, journal=journal or {})


def test_provenance_copies_position_plan():
    db = MagicMock()
    db.engineposition.update = AsyncMock()
    order = _order(journal={"sourceTags": {"themes": ["x"]},
                            "position_plan": _PLAN})
    asyncio.run(xd._persist_position_provenance(db, order))
    data = db.engineposition.update.call_args.kwargs["data"]
    assert "positionPlan" in data          # Json-wrapped plan present


def test_provenance_without_plan_leaves_column_untouched():
    """Latest plan wins on adds — but an add with NO plan must not blank the
    plan already on the row. Absent key → no positionPlan in the update."""
    db = MagicMock()
    db.engineposition.update = AsyncMock()
    asyncio.run(xd._persist_position_provenance(
        db, _order(journal={"sourceTags": {"themes": ["x"]},
                            "position_plan": None})))
    data = db.engineposition.update.call_args.kwargs["data"]
    assert "positionPlan" not in data


def test_provenance_is_replay_idempotent():
    """The fills sweep re-runs on Inngest replay (PR #12 lesson). Running the
    provenance copy twice must produce the identical update both times and
    never raise."""
    db = MagicMock()
    db.engineposition.update = AsyncMock()
    order = _order(journal={"position_plan": _PLAN})
    asyncio.run(xd._persist_position_provenance(db, order))
    asyncio.run(xd._persist_position_provenance(db, order))
    first, second = db.engineposition.update.call_args_list
    assert first.kwargs["where"] == second.kwargs["where"]
    assert str(first.kwargs["data"]) == str(second.kwargs["data"])


def test_provenance_still_never_raises():
    db = MagicMock()
    db.engineposition.update = AsyncMock(side_effect=RuntimeError("db down"))
    asyncio.run(xd._persist_position_provenance(
        db, _order(journal={"position_plan": _PLAN})))   # must not raise
```

- [ ] **Step 2: Run to verify failure**

Run: `/usr/bin/python3 -m pytest tests/test_execution_daily.py --no-cov -q -k "provenance"`
Expected: the plan tests FAIL (`positionPlan` never in `data`); the never-raises test may already pass.

- [ ] **Step 3: Implement**

In `_persist_position_provenance`, after the `report_ref` block and before `if not data:`, add:

```python
        # Phase C: the memo's plan at entry — ladder, thesis_break, exit
        # posture — persisted for the life of the position. Latest plan wins
        # (an add that re-states the plan overwrites); an order with no plan
        # leaves the existing column alone rather than blanking it.
        plan = journal.get("position_plan")
        if isinstance(plan, dict):
            from prisma import Json  # noqa: PLC0415

            data["positionPlan"] = Json(plan)
```

- [ ] **Step 4: Run to verify pass**

Run: `/usr/bin/python3 -m pytest tests/test_execution_daily.py --no-cov -q`
Expected: all PASS

- [ ] **Step 5: Commit**

```bash
git add inngest_app/functions/execution_daily.py tests/test_execution_daily.py
git commit -m "feat(audit): fill provenance persists the position plan — latest plan wins, absence never blanks"
```

---

### Task 3: Price-conditional passes (`reconsider_if`)

**Files:**
- Modify: `execution/thesis/parser.py::_passed_on` (lines 85-111)
- Modify: `execution/thesis/prompts.py` (rule 7 at ~line 72; passed_on schema at ~line 198)
- Test: `tests/test_thesis_passed_on.py` (append)

**Interfaces:**
- Consumes: nothing new.
- Produces (Task 4 relies on): `passed_on` items may carry `"reconsider_if": str` (only when non-empty; never fabricated). Prompt teaches the field.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_thesis_passed_on.py` (it already tests `_passed_on` via `parse_memo_response` or directly — match its import style):

```python
# ── Phase C: what would change our mind ──────────────────────────────────────

def test_passed_on_carries_reconsider_if_when_stated():
    out = _passed_on([{"ticker": "mu", "reason": "crowded at $990",
                       "reconsider_if": "below ~$700 or HBM pricing breaks"}],
                     "memory-hbm", [])
    assert out == [{"ticker": "MU", "reason": "crowded at $990",
                    "reconsider_if": "below ~$700 or HBM pricing breaks"}]


def test_passed_on_omits_reconsider_if_when_absent_or_blank():
    """Never fabricated: absent stays absent, whitespace collapses to absent."""
    for raw in ({"ticker": "MU", "reason": "crowded"},
                {"ticker": "MU", "reason": "crowded", "reconsider_if": "  "}):
        out = _passed_on([raw], "memory-hbm", [])
        assert out and "reconsider_if" not in out[0]


def test_prompt_teaches_reconsider_if():
    from execution.thesis.prompts import build_weekly_memo_prompt
    p = build_weekly_memo_prompt({"theses": [], "hypotheses": [], "book": [],
                                  "candidates": {}, "crowdedness": {},
                                  "regime": None, "macro": {},
                                  "method_rulebook": None})
    assert "reconsider_if" in p
    assert "change your mind" in p.lower() or "change our mind" in p.lower()
```

(If `_passed_on` is not imported in that test file yet, add `from execution.thesis.parser import _passed_on` at the top.)

- [ ] **Step 2: Run to verify failure**

Run: `/usr/bin/python3 -m pytest tests/test_thesis_passed_on.py --no-cov -q`
Expected: new tests FAIL (`reconsider_if` stripped by parser; prompt lacks the field)

- [ ] **Step 3: Implement**

In `_passed_on`, replace the final `out.append(...)` line with:

```python
        item = {"ticker": ticker, "reason": reason}
        # Phase C: the memo's own statement of what would change its mind —
        # a price, an evidence condition, or both. Optional; only recorded
        # when stated, never fabricated.
        reconsider = str(p.get("reconsider_if") or "").strip()
        if reconsider:
            item["reconsider_if"] = reconsider
        out.append(item)
```

In `execution/thesis/prompts.py`: extend rule 7 (the "RECORD WHAT YOU DECLINED" instruction, ~line 72) with one sentence:

```
   For each pass, where you can, also state what would change your mind in
   "reconsider_if" — a price ("below ~$700"), an evidence condition
   ("interconnect lead times blowing out"), or both.
```

And in the JSON schema block (~line 198), extend the passed_on item shape:

```python
    "passed_on": [{{
      "ticker": "<TICKER>",
      "reason": "<why you declined>",
      "reconsider_if": "<optional: the price or evidence that would change your mind>"
    }}],
```

(Adjust to the block's exact existing formatting — keep surrounding fields unchanged.)

- [ ] **Step 4: Run to verify pass**

Run: `/usr/bin/python3 -m pytest tests/test_thesis_passed_on.py tests/test_thesis_parser.py tests/test_thesis_prompts.py --no-cov -q`
Expected: all PASS

- [ ] **Step 5: Commit**

```bash
git add execution/thesis/parser.py execution/thesis/prompts.py tests/test_thesis_passed_on.py
git commit -m "feat(audit): passes record what would change the memo's mind (reconsider_if)"
```

---

### Task 4: Week endpoint — plan, forensics, market view

**Files:**
- Modify: `api/routes/autopilot.py` (models `:342-382`, `get_week` `:436+`; new pure helpers)
- Test: `tests/test_autopilot_week.py` (new)

**Interfaces:**
- Consumes: `EnginePosition.positionPlan` (Task 2), journal keys (Task 1), `reconsider_if` on passed_on (Task 3).
- Produces (Task 5 relies on): `WeekPosition` gains `plan: Optional[dict]` and `entry_forensics: Optional[dict]`; `WeekAction` gains `reconsider_if: Optional[str]`; `WeekResponse` gains `market_view: Optional[str]`. Pure helpers `_entry_forensics_map(rows) -> Dict[str, dict]` and `_market_view(row) -> Optional[str]`.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_autopilot_week.py`:

```python
# tests/test_autopilot_week.py
"""Week endpoint assembly helpers (Phase C). Pure functions only — the
route's broker/db joins are exercised in production; these helpers are the
new logic and must not need a live DB."""
from types import SimpleNamespace

from api.routes.autopilot import (
    WeekAction, WeekPosition, WeekResponse, _entry_forensics_map, _market_view,
)


def _report(symbol, created="2026-07-28", **body):
    return SimpleNamespace(createdAt=created,
                           body={"symbol": symbol, **body})


def test_forensics_map_takes_the_latest_row_per_symbol():
    rows = [  # endpoint queries newest-first; first seen wins
        _report("AVGO", created="2026-07-28", limit_price=382.31,
                entry_style="on_pullback", price=391.0, sma20=380.1,
                atr=8.7, dist_200wma=0.96, add_tranche_fraction=1.0),
        _report("AVGO", created="2026-07-21", limit_price=350.0,
                entry_style="at_market", price=350.0),
    ]
    m = _entry_forensics_map(rows)
    f = m["AVGO"]
    assert f["limit_price"] == 382.31 and f["entry_style"] == "on_pullback"
    assert f["price"] == 391.0 and f["sma20"] == 380.1 and f["atr"] == 8.7
    assert f["dist_200wma"] == 0.96 and f["add_tranche_fraction"] == 1.0


def test_forensics_map_tolerates_pre_phase_c_rows():
    """Old entry_order rows lack price/sma20/atr — keys present, values None,
    never a KeyError."""
    m = _entry_forensics_map([_report("MU", limit_price=991.64,
                                      entry_style="at_market")])
    f = m["MU"]
    assert f["limit_price"] == 991.64
    assert f["price"] is None and f["sma20"] is None and f["atr"] is None


def test_forensics_map_skips_rows_without_symbol():
    assert _entry_forensics_map([SimpleNamespace(createdAt="x", body={})]) == {}


def test_market_view_reads_the_memo_body():
    row = SimpleNamespace(body={"market_view": "Buildout mid-cycle; power binds."})
    assert _market_view(row) == "Buildout mid-cycle; power binds."
    assert _market_view(None) is None
    assert _market_view(SimpleNamespace(body={})) is None
    assert _market_view(SimpleNamespace(body=None)) is None


def test_week_models_carry_the_new_fields():
    p = WeekPosition(symbol="AVGO", qty=7, avg_price=382.3, market_value=2695.0,
                     unrealized_pl=19.0, unrealized_plpc=0.007,
                     plan={"ladder": [], "thesis_break": "x", "exit_plan": None},
                     entry_forensics={"limit_price": 382.31})
    assert p.plan["thesis_break"] == "x"
    a = WeekAction(ticker="MU", outcome="passed_on", reason="crowded",
                   reconsider_if="below ~$700")
    assert a.reconsider_if == "below ~$700"
    w = WeekResponse(week="2026-07-28", broker_ok=False,
                     market_view="nothing attractive this week")
    assert w.market_view.startswith("nothing")
    # and all three default to None/absent-safe for old data
    assert WeekPosition(symbol="X", qty=0, avg_price=0, market_value=0,
                        unrealized_pl=0, unrealized_plpc=0).plan is None
```

- [ ] **Step 2: Run to verify failure**

Run: `/usr/bin/python3 -m pytest tests/test_autopilot_week.py --no-cov -q`
Expected: FAIL — `ImportError: cannot import name '_entry_forensics_map'`

- [ ] **Step 3: Implement in `api/routes/autopilot.py`**

Model additions:

```python
# WeekPosition gains (after why_this_expression):
    plan: Optional[dict] = None              # positionPlan verbatim, or None
    entry_forensics: Optional[dict] = None   # latest entry_order journal slice

# WeekAction gains (after conviction):
    reconsider_if: Optional[str] = None

# WeekResponse gains (after macro_reasoning):
    market_view: Optional[str] = None        # the memo's own words, verbatim
```

New pure helpers (place above `get_week`):

```python
_FORENSIC_KEYS = ("limit_price", "entry_style", "price", "sma20", "atr",
                  "dist_200wma", "add_tranche_fraction")


def _entry_forensics_map(rows) -> Dict[str, dict]:
    """symbol -> the latest entry_order journal's price story. Rows arrive
    newest-first; first occurrence per symbol wins. Pre-Phase-C rows lack the
    math inputs — keys are always present, values None (a labeled absence,
    per the spec's degrade posture)."""
    out: Dict[str, dict] = {}
    for r in rows:
        body = r.body or {}
        symbol = body.get("symbol")
        if not symbol or symbol in out:
            continue
        out[symbol] = {k: body.get(k) for k in _FORENSIC_KEYS}
    return out


def _market_view(row) -> Optional[str]:
    """The memo's 3-6-sentence read, verbatim from the latest thesis_memo
    journal row. Never recomputed, never summarized."""
    body = getattr(row, "body", None) or {}
    view = body.get("market_view")
    return view if isinstance(view, str) and view.strip() else None
```

In `get_week`, wire them in:

```python
    # after pos_rows is built:
    forensic_rows = await db.enginereport.find_many(
        where={"type": "entry_order"}, order={"createdAt": "desc"}, take=200)
    forensics = _entry_forensics_map(forensic_rows)

    memo_report = await db.enginereport.find_first(
        where={"type": "thesis_memo"}, order={"createdAt": "desc"})

    # in the positions loop, add to WeekPosition(...):
            plan=(getattr(meta, "positionPlan", None) or None),
            entry_forensics=forensics.get(p["symbol"]),

    # in the passed_on loop, extend WeekAction(...):
            reconsider_if=p.get("reconsider_if"),

    # in WeekResponse(...):
        market_view=_market_view(memo_report),
```

- [ ] **Step 4: Run to verify pass**

Run: `/usr/bin/python3 -m pytest tests/test_autopilot_week.py --no-cov -q` then the sweep `/usr/bin/python3 -m pytest tests/test_thesis_*.py tests/test_funnel_*.py tests/test_sleeve_a_funnel_cron.py tests/test_execution_daily.py --no-cov -q`
Expected: all PASS, no new failures

- [ ] **Step 5: Commit**

```bash
git add api/routes/autopilot.py tests/test_autopilot_week.py
git commit -m "feat(audit): week endpoint serves plan, entry forensics, reconsider_if, market view"
```

---

### Task 5: Frontend — PositionCard, DecisionsSection, NoBuyBanner

**Files:**
- Modify: `frontend/types/api.ts` (`WeekPosition`/`WeekAction`/`WeekResponse` interfaces, ~lines 1906-1960)
- Create: `frontend/components/autopilot/PositionCard.tsx`
- Create: `frontend/components/autopilot/DecisionsSection.tsx`
- Create: `frontend/components/autopilot/NoBuyBanner.tsx`
- Modify: `frontend/components/autopilot/WeekPanel.tsx` (recompose; move `PositionRow`/`ActionRow` logic into the new components)

**Interfaces:**
- Consumes: Task 4's response fields (`plan`, `entry_forensics`, `reconsider_if`, `market_view`).
- Produces: components consumed only by `WeekPanel`.

- [ ] **Step 1: Extend the types**

In `frontend/types/api.ts`:

```typescript
// add to WeekPosition:
  plan?: {
    ladder: { price: number; size_pct: number; why: string }[]
    thesis_break: string
    exit_plan?: { posture: string; why: string; fraction?: number } | null
    target_weight?: number
  } | null
  entry_forensics?: {
    limit_price?: number | null
    entry_style?: string | null
    price?: number | null
    sma20?: number | null
    atr?: number | null
    dist_200wma?: number | null
    add_tranche_fraction?: number | null
  } | null

// add to WeekAction:
  reconsider_if?: string | null

// add to WeekResponse:
  market_view?: string | null
```

- [ ] **Step 2: Create `frontend/components/autopilot/PositionCard.tsx`**

Move `PositionRow`'s rendering here and extend it into the expandable dossier. Full component:

```tsx
'use client'

import { useState } from 'react'
import { Badge } from '@/components/ui/badge'
import type { WeekPosition } from '@/types/api'

const money = (n: number | null | undefined) =>
  n == null ? '—' : n.toLocaleString('en-US', { style: 'currency', currency: 'USD', maximumFractionDigits: 2 })

function Why({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <p className="mt-1.5 text-sm text-muted-foreground max-w-[70ch]">
      <span className="uppercase text-[0.62rem] tracking-wider font-semibold text-primary mr-2">{label}</span>
      {children}
    </p>
  )
}

/** "pullback limit $382.31 = price $391.00 − ATR $8.70, floored at SMA20 $380.10" */
function priceMathSentence(f: NonNullable<WeekPosition['entry_forensics']>): string | null {
  if (f.limit_price == null) return null
  if (f.entry_style === 'on_pullback' && f.price != null && f.atr != null && f.sma20 != null) {
    return `pullback limit ${money(f.limit_price)} = price ${money(f.price)} − ATR ${money(f.atr)}, floored at SMA20 ${money(f.sma20)}`
  }
  if (f.entry_style === 'at_market') {
    return `at-market limit ${money(f.limit_price)} = last close at decision`
  }
  return `limit ${money(f.limit_price)}${f.entry_style ? ` (${f.entry_style})` : ''}`
}

function Ladder({ plan, current }: { plan: NonNullable<WeekPosition['plan']>; current: number }) {
  const rungs = [...plan.ladder].sort((a, b) => b.price - a.price)
  return (
    <div className="mt-2 border-l-2 border-muted pl-3 flex flex-col gap-1">
      {rungs.map((r, i) => (
        <div key={i} className="flex flex-wrap items-baseline gap-x-2 text-sm">
          <span className="font-mono tabular-nums">{money(r.price)}</span>
          <span className="text-xs text-muted-foreground">×{(r.size_pct * 100).toFixed(0)}%</span>
          {current >= r.price ? (
            <Badge variant="secondary" className="text-[0.6rem]">below current</Badge>
          ) : (
            <Badge variant="warning" className="text-[0.6rem]">above current</Badge>
          )}
          <span className="text-xs text-muted-foreground">{r.why}</span>
        </div>
      ))}
      <div className="text-xs text-muted-foreground">
        current ≈ <span className="font-mono">{money(current)}</span>
      </div>
    </div>
  )
}

export function PositionCard({ p }: { p: WeekPosition }) {
  const [open, setOpen] = useState(false)
  const up = p.unrealized_pl >= 0
  const currentPrice = p.qty > 0 ? p.market_value / p.qty : 0
  const f = p.entry_forensics
  const math = f ? priceMathSentence(f) : null

  return (
    <div className="border-b last:border-b-0 py-3">
      <button type="button" onClick={() => setOpen(!open)} className="w-full text-left">
        <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
          <span className="font-mono font-semibold">{p.symbol}</span>
          {p.sleeve && <Badge variant="secondary" className="text-[0.65rem]">Sleeve {p.sleeve}</Badge>}
          {p.themes.map((t) => (
            <Badge key={t} variant="secondary" className="text-[0.65rem]">{t}</Badge>
          ))}
          {p.plan ? (
            <Badge variant="secondary" className="text-[0.65rem]">plan</Badge>
          ) : (
            p.sleeve === 'A' && <Badge variant="warning" className="text-[0.65rem]">no plan</Badge>
          )}
          <span className="ml-auto font-mono text-sm tabular-nums text-muted-foreground">
            {p.qty} sh · {money(p.market_value)}
          </span>
          <span className={`font-mono text-sm tabular-nums ${up ? 'text-emerald-600' : 'text-red-600'}`}>
            {up ? '+' : ''}{p.unrealized_pl.toFixed(0)} ({(p.unrealized_plpc * 100).toFixed(1)}%)
          </span>
        </div>
      </button>

      {p.why_now && <Why label="Why now">{p.why_now}</Why>}
      {p.why_this_expression && <Why label="Why this name">{p.why_this_expression}</Why>}

      {open && (
        <div className="mt-2 rounded-md bg-muted/40 px-3 py-2">
          {math && <Why label="Why this price">{math}</Why>}
          {p.plan ? (
            <>
              <Why label="Thesis breaks if">{p.plan.thesis_break}</Why>
              {p.plan.exit_plan && (
                <Why label={`Exit posture · ${p.plan.exit_plan.posture.replace(/_/g, ' ')}`}>
                  {p.plan.exit_plan.why}
                </Why>
              )}
              {p.plan.ladder.length > 0 && <Ladder plan={p.plan} current={currentPrice} />}
            </>
          ) : (
            <p className="mt-1.5 text-sm italic text-muted-foreground">
              No plan recorded (pre–Phase C entry). The next memo action on this
              name will persist one.
            </p>
          )}
        </div>
      )}
    </div>
  )
}
```

- [ ] **Step 3: Create `frontend/components/autopilot/DecisionsSection.tsx`**

Move `ActionRow` here and extend with `reconsider_if`:

```tsx
'use client'

import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import type { WeekAction } from '@/types/api'

const OUTCOME_LABEL: Record<string, string> = {
  not_placed: 'authorised, not placed',
  exited: 'exited',
  passed_on: 'considered, passed',
}

function ActionRow({ a }: { a: WeekAction }) {
  return (
    <div className="border-b last:border-b-0 py-2.5">
      <div className="flex flex-wrap items-baseline gap-x-3">
        <span className="font-mono font-semibold">{a.ticker}</span>
        {a.slug && <Badge variant="secondary" className="text-[0.65rem]">{a.slug}</Badge>}
        {a.role && <Badge variant="secondary" className="text-[0.65rem]">{a.role.replace('_', ' ')}</Badge>}
        {a.conviction != null && (
          <span className="font-mono text-xs text-muted-foreground">conviction {a.conviction.toFixed(2)}</span>
        )}
        <span className="ml-auto text-[0.65rem] uppercase tracking-wider font-semibold text-muted-foreground">
          {OUTCOME_LABEL[a.outcome] ?? a.outcome}
        </span>
      </div>
      {a.reason && <p className="mt-1 text-sm text-muted-foreground max-w-[70ch]">{a.reason}</p>}
      {a.reconsider_if && (
        <p className="mt-1 text-sm text-muted-foreground max-w-[70ch]">
          <span className="uppercase text-[0.62rem] tracking-wider font-semibold text-primary mr-2">
            Would change our mind
          </span>
          {a.reconsider_if}
        </p>
      )}
    </div>
  )
}

export function DecisionsSection({ actions }: { actions: WeekAction[] }) {
  if (actions.length === 0) return null
  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="text-xs uppercase tracking-wider text-muted-foreground">
          Decided, not held
        </CardTitle>
      </CardHeader>
      <CardContent>
        {actions.map((a, i) => <ActionRow key={`${a.ticker}-${i}`} a={a} />)}
      </CardContent>
    </Card>
  )
}
```

- [ ] **Step 4: Create `frontend/components/autopilot/NoBuyBanner.tsx`**

```tsx
'use client'

import { Card, CardContent } from '@/components/ui/card'
import type { WeekResponse } from '@/types/api'

/** A week with zero buys is a DECISION, not an empty page. Rendered only when
 * the memo ran (market_view exists) and placed no entries. */
export function NoBuyBanner({ week }: { week: WeekResponse }) {
  const boughtSomething =
    week.open_orders.some((o) => o.side === 'buy') ||
    week.actions.some((a) => a.outcome === 'not_placed') ||
    week.positions.some((p) => p.why_now != null)
  if (boughtSomething || !week.market_view) return null
  return (
    <Card className="border-amber-300/60 dark:border-amber-800/60">
      <CardContent className="py-4">
        <div className="text-[0.65rem] uppercase tracking-wider font-semibold text-amber-700 dark:text-amber-400">
          Nothing at attractive prices this week
        </div>
        <p className="mt-1.5 text-sm text-muted-foreground max-w-[80ch]">{week.market_view}</p>
      </CardContent>
    </Card>
  )
}
```

- [ ] **Step 5: Recompose `WeekPanel.tsx`**

- Delete the local `PositionRow` and `ActionRow` functions and the local `OUTCOME_LABEL`.
- Import and use the three new components: `<NoBuyBanner week={w} />` directly under the header card; `<PositionCard p={p} />` where `PositionRow` was; `<DecisionsSection actions={w.actions} />` where the actions card was.
- Add a market-view line to the header card when present (below the regime/macro line):

```tsx
{w.market_view && (
  <p className="text-sm text-muted-foreground max-w-[80ch]">{w.market_view}</p>
)}
```

- [ ] **Step 6: Verify**

Run: `cd frontend && npx tsc --noEmit && npm run build`
Expected: zero type errors, build succeeds.

- [ ] **Step 7: Commit**

```bash
git add frontend/types/api.ts frontend/components/autopilot/ 
git commit -m "feat(audit): This Week renders the plan, price math, passes, and the no-buy week"
```

---

### Task 6: Sweep, docs, PR

**Files:**
- Modify: `current-phase.md`

- [ ] **Step 1: Full regression sweep**

Run: `/usr/bin/python3 -m pytest tests/test_thesis_*.py tests/test_funnel_*.py tests/test_sleeve_a_funnel_cron.py tests/test_thirteenf_study_cron.py tests/test_execution_daily.py tests/test_autopilot_week.py --no-cov -q`
Expected: 0 failures.

- [ ] **Step 2: Update `current-phase.md`**

Replace the "Next: Phase C — memo-trail admin UI." line with:

```markdown
Phase C (audit surface) is built: the This Week tab is now the weekly audit.
Position plans persist at fill (ladder, thesis_break, exit posture — the
crowded-winner review finally has "what was our plan entering?" to read);
every order journals its price math (price/SMA20/ATR beside the limit they
produced); passes record what would change the memo's mind (reconsider_if);
and the UI renders each position's dossier, every decision with its
reasoning, and a zero-buy week as a deliberate call quoting the memo's
market view. Records more, shows more, decides nothing. Deferred (spec §5):
rung resting orders, fill attribution, theme trails, rulebook UI.
Spec: docs/superpowers/specs/2026-07-30-phase-c-audit-surface-design.md.

Next: place ladder rungs as resting orders (after watching plans render),
or surface the A-vs-B-vs-SPY scorecard.
```

Also update the header lines: title → "Phase C complete (Audit Surface)", `**Branch/PR**: feat/phase-c-audit-surface`.

- [ ] **Step 3: Commit, push, PR**

```bash
git add current-phase.md
git commit -m "docs: record Phase C (audit surface) in current-phase.md"
git push -u origin feat/phase-c-audit-surface
gh pr create --base main --title "feat(audit): Phase C — This Week becomes the audit surface" --body "$(cat <<'EOF'
## Summary
- Position plans persist at fill (`positionPlan` column; journal → provenance pipeline) — the memo's ladder, thesis_break, and exit posture survive for the life of the position instead of being validated and dropped
- Every order journals its price math (price/SMA20/ATR beside the limit) — "why $382.31" is answerable from the record forever
- Passes record `reconsider_if` — the memo's own statement of what would change its mind
- `GET /autopilot/week` serves plan + entry forensics + market_view + reconsider_if; degrades label absences, never invents
- This Week renders each position's expandable dossier (ladder vs current price, exit posture, thesis-break, price math), the decisions list, and a zero-buy week as a deliberate call
- Records more, shows more, **decides nothing** — no change to entries, exits, sizing, stages, or Sleeve B

## Test plan
- [ ] Backend sweep green (thesis/funnel/cron/daily/week suites)
- [ ] `cd frontend && npx tsc --noEmit && npm run build`
- [ ] Replay-idempotency test on plan provenance (Inngest fills path)

## Operator steps (BEFORE merge)
- [ ] `python3 -m prisma migrate deploy` against Neon (adds nullable `positionPlan` JSONB — additive, no backfill)
- [ ] After merge + Railway deploy: Inngest re-sync once the new build's mount line appears in logs

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

---

## Self-Review

**1. Spec coverage:** §3.1 persist plan → Tasks 1 (journal + column) + 2 (provenance copy, latest-wins, never-blanks); §3.2 price math → Task 1; §3.3 reconsider_if → Task 3; §4.1 endpoint fields + degrade → Task 4; §4.2 three components incl. no-plan label, no-buy banner, price-math sentence, no hit/pending attribution → Task 5; §5 deferrals → absent from all tasks by design, restated in Task 6's docs; §6 failure posture → Tasks 2 (never raises, best-effort) and 4 (labeled absences); §7 testing incl. replay test and tsc/build → Tasks 2 and 5; migration-before-merge → Global Constraints + PR body operator step.

**2. Placeholder scan:** clean — every step has runnable code or exact commands. Two intentional adaptive notes (Task 1's "whichever file exercises `_handshake_and_enter`", Task 3's "match the block's exact formatting") direct the implementer to real anchors rather than guessing line content that may drift.

**3. Type consistency:** journal keys `position_plan`/`price`/`sma20`/`atr` flow Task 1 → 2 → 4 → 5 (`entry_forensics` echoes `_FORENSIC_KEYS`); plan shape `{ladder: [{price, size_pct, why}], thesis_break, exit_plan{posture, why, fraction?}, target_weight?}` matches `validate_plan` and is identical in Task 4's model comment and Task 5's TS types; `reconsider_if` spelled identically in parser, prompt, model, TS type, and component; `market_view` consistent across helper, model, TS, and banner.
