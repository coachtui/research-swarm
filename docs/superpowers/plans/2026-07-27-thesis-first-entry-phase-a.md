# Thesis-First Entry — Phase A Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the Sleeve A funnel's RS-driven entry selection with a weekly LLM thesis memo that is the only buy authority (spec: docs/superpowers/specs/2026-07-27-thesis-first-entry-redesign-design.md, §1–§4, §6–§8).

**Architecture:** New `execution/thesis/` package (prompts, parser, planner, ledger, memo orchestration) + a `ThesisEvidence` append-only table + `stage` on ThemeBasket. The Monday cron (`inngest_app/functions/sleeve_a_funnel.py`) keeps its skeleton; its entry path is rewired: memo (paid, memoized step) → parse/plan (pure) → diligence (veto-only) → size → limit orders. The industry-ETF universe channel and the challenger/entry-queue logic are deleted.

**Tech Stack:** Python 3.9 (`/usr/bin/python3`), prisma-client-py, inngest-py 0.5.x, anthropic SDK (server-side `web_search_20250305`), pytest.

## Global Constraints

- Test runner: `/usr/bin/python3 -m pytest --no-cov` (never .venv). Baseline ~95 environmental failures on main — diff the failure LIST, not counts, before/after.
- The cron NEVER raises: every step catches, journals `engine_failure`, degrades. Memo parse failure = loud journal + no-op week (spec §7).
- Paid LLM calls live in their OWN memoized Inngest step, separate from persist (re-bill lesson). `_run_step` closures must not call `step.run` themselves.
- NEVER touch `REGIME_INVESTED_FRACTION`, Sleeve B code, or the strategist payload.
- Migrations: hand-write SQL under `db/migrations/<timestamp>_<name>/migration.sql`; deploy with `python3 -m prisma migrate deploy` (never `migrate dev`).
- Memo output schema is EXACTLY spec §3.2 — do not add fields the spec doesn't have.
- Branch off `main` (after the spec branch merges); use a worktree at execution time.

---

### Task 1: Thesis constants

**Files:**
- Modify: `execution/constants.py` (append after the thesis-hold block, ~line 140)
- Test: `tests/test_thesis_constants.py`

**Interfaces:**
- Produces: `THESIS_MEMO_MODEL: str`, `THESIS_WEB_SEARCH_MAX_USES: int`, `THESIS_STAGES: tuple`, `ENTRY_LEGAL_STAGES: tuple`, `THESIS_ROLES: tuple`, `ROLE_BANDS: dict[str, tuple[float, float]]`, `THESIS_LEDGER_WEEKS: int` — used by Tasks 3–10.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_thesis_constants.py
from execution.constants import (
    ENTRY_LEGAL_STAGES, ENTRY_WEIGHT_MAX, ENTRY_WEIGHT_MIN, ROLE_BANDS,
    THESIS_LEDGER_WEEKS, THESIS_MEMO_MODEL, THESIS_ROLES, THESIS_STAGES,
    THESIS_WEB_SEARCH_MAX_USES,
)


def test_stage_ladder_order_and_entry_legality():
    assert THESIS_STAGES == ("pre_consensus", "catching_on", "crowded", "priced")
    assert ENTRY_LEGAL_STAGES == ("pre_consensus", "catching_on")
    assert set(ENTRY_LEGAL_STAGES) < set(THESIS_STAGES)


def test_role_bands_inside_entry_band_and_ordered():
    assert set(ROLE_BANDS) == set(THESIS_ROLES) == {"anchor", "pure_play", "catalyst"}
    for lo, hi in ROLE_BANDS.values():
        assert ENTRY_WEIGHT_MIN <= lo < hi <= ENTRY_WEIGHT_MAX
    assert ROLE_BANDS["anchor"][1] == ENTRY_WEIGHT_MAX      # anchors top of band
    assert ROLE_BANDS["catalyst"][0] == ENTRY_WEIGHT_MIN    # catalysts bottom


def test_memo_call_settings():
    assert THESIS_MEMO_MODEL == "claude-sonnet-5"
    assert THESIS_WEB_SEARCH_MAX_USES == 15
    assert THESIS_LEDGER_WEEKS == 8
```

- [ ] **Step 2: Run test to verify it fails**

Run: `/usr/bin/python3 -m pytest tests/test_thesis_constants.py -v --no-cov`
Expected: FAIL with ImportError (names not defined).

- [ ] **Step 3: Write minimal implementation** — append to `execution/constants.py`:

```python
# ── Thesis-first entry redesign (spec 2026-07-27-thesis-first-entry-redesign) ─
# The weekly memo is the ONLY buy authority. Stages gate entry legality;
# crowded/priced fire reviews (existing sell authority), never auto-sell.
THESIS_MEMO_MODEL = "claude-sonnet-5"
THESIS_WEB_SEARCH_MAX_USES = 15     # pointed at leading indicators, not news
THESIS_STAGES = ("pre_consensus", "catching_on", "crowded", "priced")
ENTRY_LEGAL_STAGES = ("pre_consensus", "catching_on")
THESIS_ROLES = ("anchor", "pure_play", "catalyst")
# conviction 0..1 maps linearly inside the role's band (of sleeve equity);
# every ceiling in size_thesis_entry only shrinks.
ROLE_BANDS = {
    "anchor": (0.08, ENTRY_WEIGHT_MAX),
    "pure_play": (0.05, 0.09),
    "catalyst": (ENTRY_WEIGHT_MIN, 0.05),
}
THESIS_LEDGER_WEEKS = 8             # memo context window into its own past
```

- [ ] **Step 4: Run test to verify it passes**

Run: `/usr/bin/python3 -m pytest tests/test_thesis_constants.py -v --no-cov`
Expected: 3 PASS.

- [ ] **Step 5: Commit**

```bash
git add execution/constants.py tests/test_thesis_constants.py
git commit -m "feat(thesis): stage ladder, role bands, memo-call constants"
```

---

### Task 2: ThesisEvidence table + ThemeBasket.stage

**Files:**
- Create: `db/migrations/20260727000000_thesis_evidence/migration.sql`
- Modify: `db/schema.prisma` (ThemeBasket model + new model)

**Interfaces:**
- Produces: prisma model `ThesisEvidence` (`db.thesisevidence`) with fields `id, createdAt, kind, themeSlug, hypothesisKey, week, stage, body`; `ThemeBasket.stage: String?`. Consumed by Tasks 3, 7, 9.

- [ ] **Step 1: Write the migration SQL**

```sql
-- db/migrations/20260727000000_thesis_evidence/migration.sql
ALTER TABLE "ThemeBasket" ADD COLUMN "stage" TEXT;

CREATE TABLE "ThesisEvidence" (
    "id" TEXT NOT NULL,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "kind" TEXT NOT NULL,
    "themeSlug" TEXT,
    "hypothesisKey" TEXT,
    "week" TEXT NOT NULL,
    "stage" TEXT,
    "body" JSONB NOT NULL,
    CONSTRAINT "ThesisEvidence_pkey" PRIMARY KEY ("id")
);

CREATE INDEX "ThesisEvidence_themeSlug_createdAt_idx"
    ON "ThesisEvidence"("themeSlug", "createdAt");
CREATE INDEX "ThesisEvidence_kind_createdAt_idx"
    ON "ThesisEvidence"("kind", "createdAt");
```

- [ ] **Step 2: Update `db/schema.prisma`** — add `stage String?` to `model ThemeBasket`, and append:

```prisma
model ThesisEvidence {
  id            String   @id @default(cuid())
  createdAt     DateTime @default(now())
  kind          String   // weekly_memo | hypothesis | study_digest
  themeSlug     String?
  hypothesisKey String?
  week          String   // ISO date of the pass's Monday
  stage         String?
  body          Json

  @@index([themeSlug, createdAt])
  @@index([kind, createdAt])
}
```

- [ ] **Step 3: Validate and regenerate**

Run: `python3 -m prisma validate && python3 -m prisma generate`
Expected: both succeed.

- [ ] **Step 4: Commit** (deploy to Neon happens at merge time, per PR body)

```bash
git add db/schema.prisma db/migrations/20260727000000_thesis_evidence/migration.sql
git commit -m "feat(db): ThesisEvidence ledger + ThemeBasket.stage"
```

---

### Task 3: Evidence ledger module

**Files:**
- Create: `execution/thesis/__init__.py` (empty), `execution/thesis/ledger.py`
- Test: `tests/test_thesis_ledger.py`

**Interfaces:**
- Consumes: `db.thesisevidence` (Task 2), `THESIS_LEDGER_WEEKS` (Task 1).
- Produces:
  - `async append_evidence(db, kind: str, body: dict, *, theme_slug=None, hypothesis_key=None, week: str, stage=None) -> None` (never raises)
  - `async load_ledger_context(db, active_slugs: list[str], weeks: int = THESIS_LEDGER_WEEKS) -> dict` returning `{"by_theme": {slug: [row-dicts newest-first]}, "hypotheses": [row-dicts], "study_digest": row-dict | None}`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_thesis_ledger.py
import asyncio
from types import SimpleNamespace

from execution.thesis.ledger import append_evidence, load_ledger_context


class _Table:
    def __init__(self, rows=None):
        self.rows = rows or []
        self.created = []

    async def create(self, data):
        self.created.append(data)

    async def find_many(self, where=None, order=None, take=None):
        return self.rows[: take or len(self.rows)]


def _row(kind, slug=None, key=None, stage=None):
    return SimpleNamespace(
        kind=kind, themeSlug=slug, hypothesisKey=key, week="2026-07-27",
        stage=stage, body={"x": 1}, createdAt=None,
    )


def test_append_writes_one_row_and_never_raises():
    db = SimpleNamespace(thesisevidence=_Table())
    asyncio.run(append_evidence(
        db, "weekly_memo", {"evidence": []}, theme_slug="dc-energy",
        week="2026-07-27", stage="pre_consensus"))
    assert db.thesisevidence.created[0]["kind"] == "weekly_memo"
    assert db.thesisevidence.created[0]["themeSlug"] == "dc-energy"

    class _Boom:
        async def create(self, data):
            raise RuntimeError("db down")
    asyncio.run(append_evidence(  # must swallow, not raise
        SimpleNamespace(thesisevidence=_Boom()), "weekly_memo", {}, week="w"))


def test_load_groups_by_theme_and_splits_kinds():
    rows = [_row("weekly_memo", slug="dc-energy", stage="catching_on"),
            _row("hypothesis", key="hbm-packaging"),
            _row("study_digest"),
            _row("weekly_memo", slug="photonics", stage="crowded")]
    db = SimpleNamespace(thesisevidence=_Table(rows))
    out = asyncio.run(load_ledger_context(db, ["dc-energy", "photonics"]))
    assert [r["stage"] for r in out["by_theme"]["dc-energy"]] == ["catching_on"]
    assert out["hypotheses"][0]["hypothesisKey"] == "hbm-packaging"
    assert out["study_digest"]["kind"] == "study_digest"


def test_load_degrades_to_empty_on_failure():
    class _Boom:
        async def find_many(self, **kw):
            raise RuntimeError("db down")
    out = asyncio.run(load_ledger_context(SimpleNamespace(thesisevidence=_Boom()), ["a"]))
    assert out == {"by_theme": {"a": []}, "hypotheses": [], "study_digest": None}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `/usr/bin/python3 -m pytest tests/test_thesis_ledger.py -v --no-cov`
Expected: FAIL with ModuleNotFoundError.

- [ ] **Step 3: Implement `execution/thesis/ledger.py`**

```python
"""Append-only thesis evidence ledger (spec §6).

The memo's memory: prior memos, hypothesis observations, and the latest 13F
study digest. Reads degrade to empty (memo runs stateless with a journaled
warning — spec §7); writes swallow failures (a broken ledger must never
block the pass — the journal row still records the memo verbatim).
"""
import logging
from typing import Any, Dict, List, Optional

from execution.constants import THESIS_LEDGER_WEEKS

logger = logging.getLogger(__name__)


def _to_dict(r: Any) -> Dict[str, Any]:
    return {"kind": r.kind, "themeSlug": r.themeSlug,
            "hypothesisKey": r.hypothesisKey, "week": r.week,
            "stage": r.stage, "body": r.body}


async def append_evidence(
    db, kind: str, body: Dict[str, Any], *, theme_slug: Optional[str] = None,
    hypothesis_key: Optional[str] = None, week: str, stage: Optional[str] = None,
) -> None:
    from prisma import Json  # noqa: PLC0415 — runtime-only dependency

    try:
        await db.thesisevidence.create(data={
            "kind": kind, "themeSlug": theme_slug, "hypothesisKey": hypothesis_key,
            "week": week, "stage": stage, "body": Json(body)})
    except Exception:  # noqa: BLE001
        logger.exception("thesis ledger: append failed (%s/%s)", kind, theme_slug)


async def load_ledger_context(
    db, active_slugs: List[str], weeks: int = THESIS_LEDGER_WEEKS,
) -> Dict[str, Any]:
    by_theme: Dict[str, List[Dict[str, Any]]] = {s: [] for s in active_slugs}
    hypotheses: List[Dict[str, Any]] = []
    study: Optional[Dict[str, Any]] = None
    try:
        # Bounded fetch, newest first; weeks × (themes + hypotheses) rows is
        # small. prisma-client-py has no Json path filters — Python match.
        rows = await db.thesisevidence.find_many(
            order={"createdAt": "desc"}, take=weeks * (len(active_slugs) + 10))
        for r in rows:
            d = _to_dict(r)
            if d["kind"] == "weekly_memo" and d["themeSlug"] in by_theme:
                if len(by_theme[d["themeSlug"]]) < weeks:
                    by_theme[d["themeSlug"]].append(d)
            elif d["kind"] == "hypothesis":
                hypotheses.append(d)
            elif d["kind"] == "study_digest" and study is None:
                study = d
    except Exception:  # noqa: BLE001
        logger.exception("thesis ledger: load failed — memo runs stateless")
    return {"by_theme": by_theme, "hypotheses": hypotheses, "study_digest": study}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `/usr/bin/python3 -m pytest tests/test_thesis_ledger.py -v --no-cov`
Expected: 3 PASS.

- [ ] **Step 5: Commit**

```bash
git add execution/thesis/__init__.py execution/thesis/ledger.py tests/test_thesis_ledger.py
git commit -m "feat(thesis): append-only evidence ledger with degrade-to-empty reads"
```

---

### Task 4: Weekly memo prompt

**Files:**
- Create: `execution/thesis/prompts.py`
- Test: `tests/test_thesis_prompts.py`

**Interfaces:**
- Consumes: constants (Task 1).
- Produces: `build_weekly_memo_prompt(packet: dict) -> str`. Packet keys (all optional-tolerant): `theses` (list of dicts: slug, name, thesis, stage, metadata{binding_constraint, leading_indicators}, constituents, ledger), `hypotheses`, `book` (list: symbol, qty, avg_price, themes, unrealized_plpc), `crowdedness` ({theme_rankings, sector_rankings, industry_rankings}), `candidates` ({ticker: numbers-packet dict incl. dist_200wma, rsi14}), `study_digest`, `regime`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_thesis_prompts.py
import json

from execution.thesis.prompts import build_weekly_memo_prompt

_PACKET = {
    "theses": [{
        "slug": "dc-energy", "name": "DC Energy", "stage": "pre_consensus",
        "thesis": "power binds the buildout",
        "metadata": {"binding_constraint": "grid interconnect",
                     "leading_indicators": ["turbine lead times", "PPA announcements"]},
        "constituents": [{"ticker": "BE", "confidence": 0.8}],
        "ledger": [{"week": "2026-07-20", "stage": "pre_consensus",
                    "body": {"evidence_this_week": ["watched turbine lead times"]}}],
    }],
    "hypotheses": [{"hypothesisKey": "hbm-packaging",
                    "body": {"hypothesis": "packaging binds next"}}],
    "book": [{"symbol": "MU", "qty": 5, "avg_price": 991.64,
              "themes": ["memory-hbm"], "unrealized_plpc": 0.04}],
    "crowdedness": {"theme_rankings": [{"slug": "photonics", "score": 0.0437, "rank_change": 4}]},
    "candidates": {"BE": {"dist_200wma": -0.05, "rsi14": 41.0,
                          "fair_value_gap_pct": 22.0, "short_pct_float": 0.08}},
    "study_digest": {"body": {"rules": ["deliver-now power repriced first"]}},
    "regime": "neutral",
}


def test_prompt_carries_ledger_indicators_and_inversion_framing():
    p = build_weekly_memo_prompt(_PACKET)
    assert "turbine lead times" in p          # leading indicators verbatim
    assert "watched turbine lead times" in p  # ledger excerpt (reconciliation)
    assert "already priced" in p              # crowdedness inversion framing
    assert "reconcile" in p.lower()
    assert "deliver-now power repriced first" in p  # study digest rules


def test_prompt_states_output_schema_and_stage_rules():
    p = build_weekly_memo_prompt(_PACKET)
    for token in ('"stage"', '"why_now"', '"why_this_expression"',
                  '"entry_style"', '"hypothesis_updates"', '"market_view"',
                  "pre_consensus", "catching_on", "crowded", "priced",
                  "unverified"):
        assert token in p
    assert "ONLY a JSON object" in p


def test_prompt_survives_empty_packet():
    p = build_weekly_memo_prompt({})
    assert "ONLY a JSON object" in p and "no active theses" in p
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `/usr/bin/python3 -m pytest tests/test_thesis_prompts.py -v --no-cov`
Expected: FAIL with ModuleNotFoundError.

- [ ] **Step 3: Implement `execution/thesis/prompts.py`**

```python
"""Weekly thesis-memo prompt (spec §3). The memo is the only buy authority.

Framing that is load-bearing:
- RS/momentum/200wMA distance are presented as CROWDEDNESS — "how much of
  the repricing already happened". Hot = late = entries close, exits open.
- The memo must reconcile its own prior predictions before acting.
- The BE anatomy is the calibration example for pre-consensus entries.
"""
import json
from typing import Any, Dict

from execution.constants import (
    ENTRY_LEGAL_STAGES, THESIS_ROLES, THESIS_STAGES,
)

_INVERSION = """## How to read the market data below (this is load-bearing)
The relative-strength rankings, RSI, and distance-above-200-week-MA are
CROWDEDNESS gauges — they measure how much of the repricing has ALREADY
happened, i.e. how much the news has caught on. Hot = late. A thesis whose
evidence is confirming while its names still show weak RS and sit near
their 200-week MA is the HIGHEST-priority setup (calibration example: Bloom
Energy under $100 — thesis visible in turbine lead times and power
contracts long before the tape confirmed; the buyer who waited for
relative strength paid $105+ after the hype). Never justify an entry BY
price strength. Entering "because it is working" is the failure mode this
fund exists to avoid."""

_METHOD = """## Your job this week
1. RECONCILE: for each thesis, compare what last week's memo expected (its
   ledger below) against what actually happened. State it.
2. EVIDENCE: web-search the SPECIFIC leading indicators listed per thesis
   (power contracts, lead times, capex, physical commitments) — not
   generic news. Cite what you find.
3. STAGE each thesis: {stages}. Entries are legal ONLY in
   {legal}. crowded/priced does not sell — it sends
   holdings to review.
4. ACT: enter/add only where evidence confirms BEFORE consensus; prefer
   the constituent that has NOT repriced. Every enter/add states role
   ({roles}), one falsifiable why_now sentence, one
   why_this_expression sentence (why this name, not the obvious one), a
   conviction 0.0-1.0, and entry_style ("at_market" | "on_pullback" — you
   have each candidate's ATR context and 200-week distance; extended names
   wait for the pullback).
5. HYPOTHESES: update each next-constraint hypothesis from its indicators;
   graduate one to a theme only when they confirm.
6. If web search was unavailable or you could not verify this week's
   evidence, mark the affected observations "unverified" and propose NO
   pre_consensus entries — evidence-gated entries need verified evidence.
"No action" everywhere is a perfectly good, expected answer.""".format(
    stages=" -> ".join(THESIS_STAGES),
    legal=" and ".join(ENTRY_LEGAL_STAGES),
    roles=" | ".join(THESIS_ROLES),
)


def _j(x: Any) -> str:
    return json.dumps(x, indent=1, default=str) if x else "none"


def build_weekly_memo_prompt(packet: Dict[str, Any]) -> str:
    theses = packet.get("theses") or []
    theses_block = _j(theses) if theses else "no active theses"
    return f"""You are the portfolio brain of a long-horizon systematic fund. Your weekly
memo is the fund's ONLY entry authority; mechanics validate and size, they
never select. You hold until a thesis is priced or broken.

{_INVERSION}

{_METHOD}

## Active theses (with each one's own ledger — reconcile before acting)
{theses_block}

## Next-constraint hypotheses (ledger)
{_j(packet.get("hypotheses"))}

## Current book (entry basis matters: you add on thesis-confirmed weakness)
{_j(packet.get("book"))}

## Crowdedness gauges — what is already priced
{_j(packet.get("crowdedness"))}

## Candidate numbers packet (visible, never voting; dist_200wma is
## fractional distance above the 200-week MA — 1.0 means +100%)
{_j(packet.get("candidates"))}

## Latest 13F study digest (method rules from studying trusted funds —
## curriculum, never tickers to copy)
{_j(packet.get("study_digest"))}

## Regime context (information only): {packet.get("regime") or "unknown"}

Respond with ONLY a JSON object, no other text:
{{
  "theses": [{{
    "slug": "<existing slug>",
    "evidence_this_week": ["<observation with source>"],
    "stage": "pre_consensus" | "catching_on" | "crowded" | "priced",
    "stage_rationale": "<1-2 sentences citing evidence>",
    "actions": [{{
      "action": "enter" | "add" | "review" | "hold",
      "ticker": "<SYMBOL>",
      "role": "anchor" | "pure_play" | "catalyst",
      "why_now": "<1 falsifiable sentence>",
      "why_this_expression": "<1 sentence>",
      "conviction": <float 0.0-1.0>,
      "entry_style": "at_market" | "on_pullback"
    }}]
  }}],
  "hypothesis_updates": [{{
    "hypothesis": "<existing or new, one sentence>",
    "indicator_observations": ["<observation>"],
    "verdict": "confirming" | "unclear" | "disconfirmed" | "graduate_to_theme"
  }}],
  "market_view": "<3-6 sentences: where we are in the buildout, what binds next>"
}}"""
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `/usr/bin/python3 -m pytest tests/test_thesis_prompts.py -v --no-cov`
Expected: 3 PASS.

- [ ] **Step 5: Commit**

```bash
git add execution/thesis/prompts.py tests/test_thesis_prompts.py
git commit -m "feat(thesis): weekly memo prompt — crowdedness inversion, reconciliation, BE calibration"
```

---

### Task 5: Memo parser (loud on drift)

**Files:**
- Create: `execution/thesis/parser.py`
- Test: `tests/test_thesis_parser.py`

**Interfaces:**
- Consumes: `_extract_json`, `_TICKER_RE` from `execution/themes/parser.py`; constants (Task 1).
- Produces: `class MemoParseError(Exception)`; `parse_memo_response(raw: str) -> dict` returning `{"theses": [...], "hypothesis_updates": [...], "market_view": str, "skipped": [reasons]}`. RAISES `MemoParseError` when no JSON extracts OR `"theses"` is missing/not a list (spec §7: schema drift = loud no-op week — stricter than the delta parser's soft posture, deliberately). Malformed individual items are skipped with reasons, never guessed.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_thesis_parser.py
import json

import pytest

from execution.thesis.parser import MemoParseError, parse_memo_response

_GOOD = {
    "theses": [{
        "slug": "dc-energy", "evidence_this_week": ["EIA queue data"],
        "stage": "catching_on", "stage_rationale": "contracts accelerating",
        "actions": [{"action": "enter", "ticker": "BE", "role": "anchor",
                     "why_now": "turbine slots sold out", "why_this_expression": "delivers now",
                     "conviction": 0.8, "entry_style": "on_pullback"}],
    }],
    "hypothesis_updates": [{"hypothesis": "packaging binds next",
                            "indicator_observations": ["CoWoS bookings"],
                            "verdict": "confirming"}],
    "market_view": "power still binds.",
}


def test_good_memo_parses_clean():
    out = parse_memo_response(json.dumps(_GOOD))
    assert out["skipped"] == []
    assert out["theses"][0]["actions"][0]["ticker"] == "BE"
    assert out["hypothesis_updates"][0]["verdict"] == "confirming"
    assert out["market_view"] == "power still binds."


def test_missing_theses_key_raises_loud():
    with pytest.raises(MemoParseError):
        parse_memo_response(json.dumps({"market_view": "hi"}))
    with pytest.raises(MemoParseError):
        parse_memo_response("no json here at all")


def test_bad_items_skip_with_reasons_never_guess():
    bad = {
        "theses": [
            {"slug": "dc-energy", "stage": "mooning", "actions": []},        # bad stage
            {"slug": "x", "stage": "priced",
             "actions": [{"action": "enter", "ticker": "be!", "role": "anchor",
                          "why_now": "w", "why_this_expression": "e",
                          "conviction": 0.5, "entry_style": "at_market"}]},  # bad ticker
            {"slug": "y", "stage": "crowded",
             "actions": [{"action": "enter", "ticker": "OK", "role": "hero",
                          "why_now": "w", "why_this_expression": "e",
                          "conviction": 0.5, "entry_style": "at_market"}]},  # bad role
            {"slug": "z", "stage": "pre_consensus",
             "actions": [{"action": "enter", "ticker": "OK", "role": "anchor",
                          "conviction": 2.0, "entry_style": "at_market"}]},  # missing why + bad conviction
        ],
        "hypothesis_updates": [{"hypothesis": "h", "verdict": "definitely"}],  # bad verdict
        "market_view": "",
    }
    out = parse_memo_response(json.dumps(bad))
    kept_actions = [a for t in out["theses"] for a in t["actions"]]
    assert kept_actions == []                 # every bad action skipped
    assert out["hypothesis_updates"] == []
    assert len(out["skipped"]) >= 5
    # thesis rows with valid stages survive even when their actions are skipped
    assert {t["slug"] for t in out["theses"]} == {"x", "y", "z"}


def test_hold_and_review_need_no_role_or_style():
    memo = {"theses": [{"slug": "s", "stage": "crowded", "stage_rationale": "r",
                        "evidence_this_week": [],
                        "actions": [{"action": "review", "ticker": "MU"},
                                    {"action": "hold", "ticker": "BE"}]}],
            "hypothesis_updates": [], "market_view": "v"}
    out = parse_memo_response(json.dumps(memo))
    assert [a["action"] for a in out["theses"][0]["actions"]] == ["review", "hold"]
    assert out["skipped"] == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `/usr/bin/python3 -m pytest tests/test_thesis_parser.py -v --no-cov`
Expected: FAIL with ModuleNotFoundError.

- [ ] **Step 3: Implement `execution/thesis/parser.py`**

```python
"""Strict parsing of the weekly thesis memo (spec §3.2, §7).

Posture: LOUDER than the theme parsers. The memo is the only buy authority,
so a response whose top-level shape drifted is a no-op week, not a quiet
zero — MemoParseError propagates to the cron which journals engine_failure
and places nothing. Individual malformed items skip with reasons.
"""
import logging
from typing import Any, Dict, List

from execution.constants import THESIS_ROLES, THESIS_STAGES
from execution.themes.parser import ThemeParseError, _extract_json, _TICKER_RE

logger = logging.getLogger(__name__)

_ACTIONS = {"enter", "add", "review", "hold"}
_ENTRY_ACTIONS = {"enter", "add"}
_STYLES = {"at_market", "on_pullback"}
_VERDICTS = {"confirming", "unclear", "disconfirmed", "graduate_to_theme"}


class MemoParseError(Exception):
    """Memo unusable — no JSON, or the top-level schema drifted."""


def _action(raw: Any, slug: str, skipped: List[str]) -> Dict[str, Any] | None:
    if not isinstance(raw, dict):
        skipped.append(f"{slug}: action is not an object")
        return None
    action = raw.get("action")
    ticker = str(raw.get("ticker") or "").strip().upper()
    if action not in _ACTIONS:
        skipped.append(f"{slug}: unknown action {action!r}")
        return None
    if not _TICKER_RE.match(ticker):
        skipped.append(f"{slug}: bad ticker {raw.get('ticker')!r}")
        return None
    out = {"action": action, "ticker": ticker}
    if action in _ENTRY_ACTIONS:
        role, style = raw.get("role"), raw.get("entry_style")
        why_now = str(raw.get("why_now") or "").strip()
        why_expr = str(raw.get("why_this_expression") or "").strip()
        try:
            conviction = float(raw.get("conviction"))
        except (TypeError, ValueError):
            conviction = -1.0
        if role not in THESIS_ROLES:
            skipped.append(f"{slug}/{ticker}: bad role {role!r}")
            return None
        if style not in _STYLES:
            skipped.append(f"{slug}/{ticker}: bad entry_style {style!r}")
            return None
        if not why_now or not why_expr:
            skipped.append(f"{slug}/{ticker}: missing why_now/why_this_expression")
            return None
        if not 0.0 <= conviction <= 1.0:
            skipped.append(f"{slug}/{ticker}: conviction out of range")
            return None
        out.update({"role": role, "entry_style": style, "why_now": why_now,
                    "why_this_expression": why_expr, "conviction": conviction})
    return out


def parse_memo_response(raw: str) -> Dict[str, Any]:
    try:
        obj = _extract_json(raw)
    except ThemeParseError as exc:
        raise MemoParseError(str(exc)) from exc
    theses_raw = obj.get("theses")
    if not isinstance(theses_raw, list):
        raise MemoParseError(
            f'"theses" missing or not a list — top-level keys {sorted(map(str, obj))}')

    skipped: List[str] = []
    theses: List[Dict[str, Any]] = []
    for t in theses_raw:
        if not isinstance(t, dict) or not t.get("slug"):
            skipped.append("thesis item without slug")
            continue
        slug = str(t["slug"]).strip()
        stage = t.get("stage")
        if stage not in THESIS_STAGES:
            skipped.append(f"{slug}: bad stage {stage!r}")
            continue
        actions = [a for a_raw in (t.get("actions") or [])
                   if (a := _action(a_raw, slug, skipped)) is not None]
        theses.append({
            "slug": slug, "stage": stage,
            "stage_rationale": str(t.get("stage_rationale") or ""),
            "evidence_this_week": [str(e) for e in (t.get("evidence_this_week") or [])],
            "actions": actions,
        })

    updates: List[Dict[str, Any]] = []
    for h in (obj.get("hypothesis_updates") or []):
        if not isinstance(h, dict) or not h.get("hypothesis"):
            skipped.append("hypothesis update without hypothesis text")
            continue
        if h.get("verdict") not in _VERDICTS:
            skipped.append(f"hypothesis {str(h['hypothesis'])[:40]!r}: bad verdict")
            continue
        updates.append({
            "hypothesis": str(h["hypothesis"]).strip(),
            "indicator_observations": [str(o) for o in (h.get("indicator_observations") or [])],
            "verdict": h["verdict"],
        })

    return {"theses": theses, "hypothesis_updates": updates,
            "market_view": str(obj.get("market_view") or ""), "skipped": skipped}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `/usr/bin/python3 -m pytest tests/test_thesis_parser.py -v --no-cov`
Expected: 4 PASS. (Python 3.9 note: the walrus-in-comprehension is fine; `Dict[str, Any] | None` is NOT — use `Optional[Dict[str, Any]]` in the annotation.)

- [ ] **Step 5: Fix the annotation for 3.9** — change `_action`'s return annotation to `Optional[Dict[str, Any]]` and import `Optional`. Re-run; expected 4 PASS.

- [ ] **Step 6: Commit**

```bash
git add execution/thesis/parser.py tests/test_thesis_parser.py
git commit -m "feat(thesis): memo parser — loud on top-level drift, skip-with-reason per item"
```

---

### Task 6: Planner — stage legality, sizing, entry pricing

**Files:**
- Create: `execution/thesis/planner.py`
- Test: `tests/test_thesis_planner.py`

**Interfaces:**
- Consumes: parser output shape (Task 5); constants (Task 1); `MIN_TRADE_NOTIONAL`, `VOL_CEILING_SLEEVE_RISK`, `ADV_POSITION_CAP_PCT`, `PATIENT_LIMIT_TTL_WEEKS` from `execution.constants`.
- Produces (all pure):
  - `size_thesis_entry(role: str, conviction: float, sleeve_equity: float, adv_usd: float, atr_pct: float, deployable_remaining: float, cash_available: float) -> float`
  - `entry_price_and_ttl(entry_style: str, price: float, sma20: float, atr: float) -> Tuple[float, int]`
  - `plan_from_memo(memo: dict, held_symbols: set, screened_symbols: set) -> dict` returning `{"entries": [...], "adds": [...], "reviews": [symbols], "stage_updates": {slug: stage}, "rejected": [{"ticker", "slug", "reason"}]}` — entry/add items carry `slug, stage, ticker, role, conviction, entry_style, why_now, why_this_expression`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_thesis_planner.py
from execution.constants import MIN_TRADE_NOTIONAL, ROLE_BANDS
from execution.thesis.planner import (
    entry_price_and_ttl, plan_from_memo, size_thesis_entry,
)

_EQ = 70_000.0


def test_role_bands_scale_with_conviction_and_ceilings_only_shrink():
    hi = size_thesis_entry("anchor", 1.0, _EQ, 50e6, 0.02, 1e9, 1e9)
    lo = size_thesis_entry("catalyst", 0.0, _EQ, 50e6, 0.02, 1e9, 1e9)
    assert hi == round(ROLE_BANDS["anchor"][1] * _EQ, 2)
    assert lo == round(ROLE_BANDS["catalyst"][0] * _EQ, 2)
    # vol ceiling binds a twitchy name: 0.0075/0.10 * eq = 5,250 < anchor band
    assert size_thesis_entry("anchor", 1.0, _EQ, 50e6, 0.10, 1e9, 1e9) == 5250.0
    # cash binds
    assert size_thesis_entry("anchor", 1.0, _EQ, 50e6, 0.02, 1e9, 900.0) == 900.0
    # dust drops
    assert size_thesis_entry("anchor", 1.0, _EQ, 50e6, 0.02, 1e9,
                             MIN_TRADE_NOTIONAL - 1) == 0.0
    assert size_thesis_entry("anchor", 1.0, 0.0, 50e6, 0.02, 1e9, 1e9) == 0.0


def test_entry_pricing_styles():
    assert entry_price_and_ttl("at_market", 100.0, 95.0, 4.0) == (100.0, 7)
    assert entry_price_and_ttl("on_pullback", 100.0, 95.0, 4.0) == (96.0, 14)
    assert entry_price_and_ttl("on_pullback", 100.0, 98.0, 4.0) == (98.0, 14)


def _memo(stage, action="enter", ticker="BE"):
    return {"theses": [{"slug": "dc-energy", "stage": stage,
                        "stage_rationale": "r", "evidence_this_week": [],
                        "actions": [{"action": action, "ticker": ticker,
                                     "role": "anchor", "conviction": 0.7,
                                     "entry_style": "at_market",
                                     "why_now": "w", "why_this_expression": "e"}]}],
            "hypothesis_updates": [], "market_view": "v", "skipped": []}


def test_stage_gates_entries_but_not_reviews():
    ok = plan_from_memo(_memo("catching_on"), set(), {"BE"})
    assert [e["ticker"] for e in ok["entries"]] == ["BE"]
    assert ok["stage_updates"] == {"dc-energy": "catching_on"}

    late = plan_from_memo(_memo("crowded"), set(), {"BE"})
    assert late["entries"] == []
    assert late["rejected"][0]["reason"] == "stage_not_entry_legal"

    rev = plan_from_memo(_memo("crowded", action="review", ticker="MU"), {"MU"}, set())
    assert rev["reviews"] == ["MU"]


def test_universe_and_book_gates():
    out = plan_from_memo(_memo("pre_consensus"), set(), set())      # not screened
    assert out["rejected"][0]["reason"] == "not_in_validated_universe"
    out = plan_from_memo(_memo("pre_consensus"), {"BE"}, {"BE"})    # already held
    assert out["entries"] == [] and out["rejected"][0]["reason"] == "enter_already_held"
    out = plan_from_memo(_memo("pre_consensus", action="add"), set(), {"BE"})
    assert out["adds"] == [] and out["rejected"][0]["reason"] == "add_not_held"
    out = plan_from_memo(_memo("pre_consensus", action="add"), {"BE"}, {"BE"})
    assert [a["ticker"] for a in out["adds"]] == ["BE"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `/usr/bin/python3 -m pytest tests/test_thesis_planner.py -v --no-cov`
Expected: FAIL with ModuleNotFoundError.

- [ ] **Step 3: Implement `execution/thesis/planner.py`**

```python
"""Memo → validated order intents (pure — spec §4).

Mechanics size and validate; they never select. Stage legality, the
screened-universe gate (which already enforced Alpaca-tradable + ADV/mcap/
price floors upstream), and the book gates are the only rejections here —
each rejection is journaled by the cron so the memo can learn from it.
"""
from typing import Any, Dict, List, Set, Tuple

from execution.constants import (
    ADV_POSITION_CAP_PCT, ENTRY_LEGAL_STAGES, MIN_TRADE_NOTIONAL,
    PATIENT_LIMIT_TTL_WEEKS, ROLE_BANDS, VOL_CEILING_SLEEVE_RISK,
)


def size_thesis_entry(
    role: str, conviction: float, sleeve_equity: float, adv_usd: float,
    atr_pct: float, deployable_remaining: float, cash_available: float,
) -> float:
    """Role band scaled by conviction; every ceiling only shrinks."""
    if atr_pct is None or atr_pct <= 0 or sleeve_equity <= 0:
        return 0.0
    lo, hi = ROLE_BANDS[role]
    notional = (lo + (hi - lo) * max(0.0, min(1.0, conviction))) * sleeve_equity
    notional = min(notional, VOL_CEILING_SLEEVE_RISK / atr_pct * sleeve_equity)
    notional = min(notional, ADV_POSITION_CAP_PCT * max(adv_usd or 0.0, 0.0))
    notional = min(notional, max(deployable_remaining, 0.0), max(cash_available, 0.0))
    return round(notional, 2) if notional >= MIN_TRADE_NOTIONAL else 0.0


def entry_price_and_ttl(
    entry_style: str, price: float, sma20: float, atr: float,
) -> Tuple[float, int]:
    """at_market = limit at last close, 1-week TTL; on_pullback = the
    patient retracement limit (max(sma20, price - ATR)), 2-week TTL."""
    if entry_style == "on_pullback":
        return round(max(sma20, price - atr), 2), PATIENT_LIMIT_TTL_WEEKS * 7
    return round(price, 2), 7


def plan_from_memo(
    memo: Dict[str, Any], held_symbols: Set[str], screened_symbols: Set[str],
) -> Dict[str, Any]:
    entries: List[Dict[str, Any]] = []
    adds: List[Dict[str, Any]] = []
    reviews: List[str] = []
    rejected: List[Dict[str, str]] = []
    stage_updates: Dict[str, str] = {}

    for t in memo.get("theses", []):
        slug, stage = t["slug"], t["stage"]
        stage_updates[slug] = stage
        for a in t.get("actions", []):
            ticker, action = a["ticker"], a["action"]
            if action == "hold":
                continue
            if action == "review":
                if ticker in held_symbols and ticker not in reviews:
                    reviews.append(ticker)
                continue
            # enter/add
            if stage not in ENTRY_LEGAL_STAGES:
                rejected.append({"ticker": ticker, "slug": slug,
                                 "reason": "stage_not_entry_legal"})
                continue
            if action == "enter" and ticker in held_symbols:
                rejected.append({"ticker": ticker, "slug": slug,
                                 "reason": "enter_already_held"})
                continue
            if action == "add" and ticker not in held_symbols:
                rejected.append({"ticker": ticker, "slug": slug,
                                 "reason": "add_not_held"})
                continue
            if ticker not in screened_symbols:
                rejected.append({"ticker": ticker, "slug": slug,
                                 "reason": "not_in_validated_universe"})
                continue
            item = {"slug": slug, "stage": stage, **a}
            (entries if action == "enter" else adds).append(item)

    return {"entries": entries, "adds": adds, "reviews": reviews,
            "stage_updates": stage_updates, "rejected": rejected}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `/usr/bin/python3 -m pytest tests/test_thesis_planner.py -v --no-cov`
Expected: 4 PASS.

- [ ] **Step 5: Commit**

```bash
git add execution/thesis/planner.py tests/test_thesis_planner.py
git commit -m "feat(thesis): planner — stage legality, role-band sizing, entry-style pricing"
```

---

### Task 7: Memo orchestration + new report types

**Files:**
- Create: `execution/thesis/memo.py`
- Modify: `execution/reporting.py` (REPORT_TYPES)
- Test: `tests/test_thesis_memo.py`

**Interfaces:**
- Consumes: `_call_llm`, `_current_theme_state` from `execution.themes.discovery`; ledger (Task 3); prompt (Task 4); constants.
- Produces:
  - `SOURCE = "thesis_memo_weekly"`
  - `async gather_memo_packet(db, outlook: dict, book: list, candidates: dict) -> dict` (packet shape of Task 4)
  - `reason_memo(packet: dict, llm_call=None) -> str` — `THESIS_MEMO_MODEL`, web search ON, `max_uses=THESIS_WEB_SEARCH_MAX_USES`
  - `async persist_memo(db, week: str, raw: str, memo: dict) -> None` — journals `thesis_memo` EngineReport + appends one `weekly_memo` ledger row per thesis and one `hypothesis` row per update.
- New REPORT_TYPES entries: `"thesis_memo", "study_digest", "entry_rejected"`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_thesis_memo.py
import asyncio
from types import SimpleNamespace

from execution.reporting import REPORT_TYPES
from execution.thesis import memo as memo_mod


def test_new_report_types_registered():
    assert {"thesis_memo", "study_digest", "entry_rejected"} <= REPORT_TYPES


def test_reason_memo_uses_sonnet_with_search(monkeypatch):
    calls = {}

    def fake_call(model, prompt, use_web_search=False, max_uses=0):
        calls.update(model=model, search=use_web_search, max_uses=max_uses,
                     prompt=prompt)
        return '{"theses": [], "hypothesis_updates": [], "market_view": "v"}'

    out = memo_mod.reason_memo({"theses": []}, llm_call=fake_call)
    assert "ONLY a JSON object" in calls["prompt"]
    assert calls["model"] == "claude-sonnet-5" and calls["search"] is True
    assert calls["max_uses"] == 15 and out.startswith("{")


def test_persist_memo_journals_and_appends(monkeypatch):
    writes, appends = [], []

    async def fake_write(*a, **kw):
        writes.append(a)

    async def fake_append(db, kind, body, **kw):
        appends.append((kind, kw.get("theme_slug"), kw.get("hypothesis_key")))

    monkeypatch.setattr(memo_mod, "write_report", fake_write)
    monkeypatch.setattr(memo_mod, "append_evidence", fake_append)
    parsed = {"theses": [{"slug": "dc-energy", "stage": "catching_on",
                          "stage_rationale": "r", "evidence_this_week": ["e"],
                          "actions": []}],
              "hypothesis_updates": [{"hypothesis": "packaging binds next",
                                      "indicator_observations": [],
                                      "verdict": "unclear"}],
              "market_view": "v", "skipped": []}
    asyncio.run(memo_mod.persist_memo(SimpleNamespace(), "2026-07-27", "raw", parsed))
    assert writes and writes[0][0] == "thesis_memo"
    assert ("weekly_memo", "dc-energy", None) in appends
    assert any(k == "hypothesis" and h == "packaging-binds-next"
               for k, _, h in appends)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `/usr/bin/python3 -m pytest tests/test_thesis_memo.py -v --no-cov`
Expected: FAIL (module missing / types missing).

- [ ] **Step 3: Add the three types to `execution/reporting.py`** — inside `REPORT_TYPES`, after the thesis-hold line:

```python
    # Thesis-first entry redesign (2026-07-27)
    "thesis_memo", "study_digest", "entry_rejected",
```

- [ ] **Step 4: Implement `execution/thesis/memo.py`**

```python
"""Weekly thesis memo: gather → reason (paid) → persist (spec §3).

reason_memo is the PAID call — the cron runs it in its own memoized step.
gather/persist are cheap and deterministic given their inputs.
"""
import logging
import re
from typing import Any, Dict, List, Optional

from execution.constants import THESIS_MEMO_MODEL, THESIS_WEB_SEARCH_MAX_USES
from execution.reporting import write_report
from execution.themes.discovery import _call_llm, _current_theme_state
from execution.thesis.ledger import append_evidence, load_ledger_context
from execution.thesis.prompts import build_weekly_memo_prompt

logger = logging.getLogger(__name__)

SOURCE = "thesis_memo_weekly"
_KEY_RE = re.compile(r"[^a-z0-9]+")


def hypothesis_key(text: str) -> str:
    """Stable slug key for a hypothesis sentence (first 60 chars)."""
    return _KEY_RE.sub("-", text.lower()).strip("-")[:60]


async def gather_memo_packet(
    db, outlook: Dict[str, Any], book: List[Dict[str, Any]],
    candidates: Dict[str, Dict[str, Any]],
) -> Dict[str, Any]:
    themes = await _current_theme_state(db, include_retired=False)
    active = [{**t, "constituents": [c for c in t["constituents"]
                                     if c["status"] == "active"]}
              for t in themes]
    ledger = await load_ledger_context(db, [t["slug"] for t in active])
    for t in active:
        t["ledger"] = ledger["by_theme"].get(t["slug"], [])
        t["stage"] = t.get("stage")  # present when Task 9 threads it through
    crowd = {
        "theme_rankings": (outlook.get("themeRankings") or {}).get("rankings"),
        "sector_rankings": outlook.get("sectorRankings"),
        "industry_rankings": (outlook.get("industryRankings") or {}).get("rankings"),
    }
    return {"theses": active, "hypotheses": ledger["hypotheses"],
            "study_digest": ledger["study_digest"], "book": book,
            "candidates": candidates, "crowdedness": crowd,
            "regime": outlook.get("regime")}


def reason_memo(packet: Dict[str, Any], llm_call=None) -> str:
    call = llm_call or _call_llm
    return call(THESIS_MEMO_MODEL, build_weekly_memo_prompt(packet),
                use_web_search=True, max_uses=THESIS_WEB_SEARCH_MAX_USES)


async def persist_memo(db, week: str, raw: str, memo: Dict[str, Any]) -> None:
    """Journal the memo verbatim + append ledger rows. write_report and
    append_evidence both swallow their own failures."""
    await write_report(
        "thesis_memo", "info", SOURCE,
        f"weekly memo: {len(memo['theses'])} theses, "
        f"{sum(len(t['actions']) for t in memo['theses'])} actions, "
        f"{len(memo['skipped'])} skipped",
        {"raw": raw, "market_view": memo["market_view"],
         "skipped": memo["skipped"]}, db=db)
    for t in memo["theses"]:
        await append_evidence(
            db, "weekly_memo",
            {"evidence_this_week": t["evidence_this_week"],
             "stage_rationale": t["stage_rationale"], "actions": t["actions"]},
            theme_slug=t["slug"], week=week, stage=t["stage"])
    for h in memo["hypothesis_updates"]:
        await append_evidence(
            db, "hypothesis", h, hypothesis_key=hypothesis_key(h["hypothesis"]),
            week=week)
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `/usr/bin/python3 -m pytest tests/test_thesis_memo.py -v --no-cov`
Expected: 3 PASS.

- [ ] **Step 6: Commit**

```bash
git add execution/thesis/memo.py execution/reporting.py tests/test_thesis_memo.py
git commit -m "feat(thesis): memo orchestration (gather/reason/persist) + report types"
```

---

### Task 8: Delete the industry-RS universe channel

**Files:**
- Modify: `execution/funnel/universe.py` (delete `fetch_industry_holdings`, ~lines 104–126)
- Modify: `inngest_app/functions/sleeve_a_funnel.py` `_assemble` (~lines 862–890)
- Test: `tests/test_funnel_universe.py`, `tests/test_sleeve_a_funnel_cron.py`

**Interfaces:**
- Consumes: existing `merge_sources(theme_members, industry_holdings, watchlist, holdings)`.
- Produces: `_assemble` now calls `merge_sources(theme_members, {}, watchlist, holdings)` — industry tags become permanently empty; provenance/tag shape unchanged so guardrails and journal code need no edits.

- [ ] **Step 1: Write the failing test** — add to `tests/test_sleeve_a_funnel_cron.py` (follow the file's existing fake-db fixtures for `_assemble`):

```python
def test_assemble_has_no_industry_channel(monkeypatch):
    """Founding-premise regression guard: no formula-picked universe source.
    The industry-ETF top-holdings channel is DELETED (spec §2) — a symbol may
    enter the universe only via themes, watchlist, or being held."""
    import inngest_app.functions.sleeve_a_funnel as cron
    import execution.funnel.universe as universe

    assert not hasattr(universe, "fetch_industry_holdings")
    # _assemble's counts no longer report an industry_holdings source
    # (exercise _assemble with the file's existing fake db fixture and
    # assert "industry_holdings" not in result["counts"])
```

- [ ] **Step 2: Run to verify it fails**

Run: `/usr/bin/python3 -m pytest tests/test_sleeve_a_funnel_cron.py -k industry_channel -v --no-cov`
Expected: FAIL (`fetch_industry_holdings` exists).

- [ ] **Step 3: Implement** — delete `fetch_industry_holdings` from `universe.py` (and its `FUNNEL_INDUSTRY_TOP_N` / `FUNNEL_HOLDINGS_PER_ETF` imports); in `_assemble`, drop the `fetch_industry_holdings` import and the `asyncio.to_thread(...)` call, pass `{}` as `industry_holdings` to `merge_sources`, and remove `"industry_holdings"` from `counts`. Update the module docstring: universe = theme constituents + watchlist + holdings. Delete the `fetch_industry_holdings` tests in `tests/test_funnel_universe.py`.

- [ ] **Step 4: Run the affected suites**

Run: `/usr/bin/python3 -m pytest tests/test_funnel_universe.py tests/test_sleeve_a_funnel_cron.py -v --no-cov`
Expected: PASS (minus deleted tests); no new failures vs baseline list.

- [ ] **Step 5: Commit**

```bash
git add execution/funnel/universe.py inngest_app/functions/sleeve_a_funnel.py tests/test_funnel_universe.py tests/test_sleeve_a_funnel_cron.py
git commit -m "feat(funnel)!: delete industry-RS universe channel — themes/watchlist/holdings only"
```

---

### Task 9: Cron wiring — memo steps, stage persistence, review handoff

**Files:**
- Modify: `inngest_app/functions/sleeve_a_funnel.py` (`_decide_and_execute`, ~line 1146; register new steps in the main run flow)
- Test: `tests/test_sleeve_a_funnel_cron.py`

**Interfaces:**
- Consumes: Tasks 5–7 (`parse_memo_response`/`MemoParseError`, `plan_from_memo`, `gather_memo_packet`/`reason_memo`/`persist_memo`), `_run_step` (line 79).
- Produces: `_decide_and_execute` gains the memo pipeline; a module-level helper `_memo_pipeline(db, outlook, book, candidates, run_date, step) -> Optional[dict]` (None = unusable memo = no-op week) used by the cron; `memo_plan["reviews"]` + crowded/priced stage-updates feed stage A's trigger collection under the new trigger name `"memo_stage"`.

- [ ] **Step 1: Write the failing tests** — add to `tests/test_sleeve_a_funnel_cron.py`:

```python
def test_memo_pipeline_parse_failure_is_noop_week(monkeypatch):
    """MemoParseError → engine_failure journal + None (no orders), never a raise."""
    import asyncio
    import inngest_app.functions.sleeve_a_funnel as cron

    async def fake_gather(db, outlook, book, candidates):
        return {"theses": []}
    monkeypatch.setattr(cron, "gather_memo_packet", fake_gather)
    monkeypatch.setattr(cron, "reason_memo", lambda packet: "NOT JSON")
    journaled = []

    async def fake_journal(db, rtype, sev, title, body):
        journaled.append((rtype, sev))
    monkeypatch.setattr(cron, "_journal", fake_journal)

    out = asyncio.run(cron._memo_pipeline(None, {}, [], {}, RUN_DATE, step=None))
    assert out is None
    assert ("engine_failure", "critical") in journaled


def test_memo_pipeline_persists_stages_and_returns_plan(monkeypatch):
    import asyncio, json
    import inngest_app.functions.sleeve_a_funnel as cron

    raw = json.dumps({"theses": [{"slug": "dc-energy", "stage": "crowded",
                                  "stage_rationale": "r", "evidence_this_week": [],
                                  "actions": [{"action": "review", "ticker": "MU"}]}],
                      "hypothesis_updates": [], "market_view": "v"})

    async def fake_gather(db, outlook, book, candidates):
        return {"theses": []}
    async def fake_persist(db, week, raw_memo, memo):
        pass
    stage_writes = []

    class _TB:
        async def update(self, where, data):
            stage_writes.append((where["slug"], data["stage"]))
    monkeypatch.setattr(cron, "gather_memo_packet", fake_gather)
    monkeypatch.setattr(cron, "reason_memo", lambda packet: raw)
    monkeypatch.setattr(cron, "persist_memo", fake_persist)

    db = SimpleNamespace(themebasket=_TB())   # reuse the file's fake-db idiom
    plan = asyncio.run(cron._memo_pipeline(db, {}, [], {}, RUN_DATE, step=None))
    assert plan["reviews"] == ["MU"] or plan["reviews"] == []  # MU only if held — see step 3
    assert ("dc-energy", "crowded") in stage_writes
```

(Adapt `RUN_DATE`/`SimpleNamespace` to the file's existing fixtures; the second test's `held_symbols` comes from the `book` argument — pass `book=[{"symbol": "MU", ...}]` and assert `plan["reviews"] == ["MU"]`.)

- [ ] **Step 2: Run to verify they fail**

Run: `/usr/bin/python3 -m pytest tests/test_sleeve_a_funnel_cron.py -k memo_pipeline -v --no-cov`
Expected: FAIL (`_memo_pipeline` not defined).

- [ ] **Step 3: Implement `_memo_pipeline`** in `sleeve_a_funnel.py` (module level, near `_decide_and_execute`); add imports `from execution.thesis.memo import gather_memo_packet, persist_memo, reason_memo`, `from execution.thesis.parser import MemoParseError, parse_memo_response`, `from execution.thesis.planner import plan_from_memo`:

```python
async def _memo_pipeline(
    db, outlook: Dict[str, Any], book: List[Dict[str, Any]],
    candidates: Dict[str, Dict[str, Any]], run_date: datetime, step,
) -> Optional[Dict[str, Any]]:
    """Gather → memo (PAID, own memoized step) → parse → plan → persist.

    Returns the plan dict, or None for an unusable memo — the caller treats
    None as a no-op week (spec §7): entries skipped, everything else (fills,
    reviews already triggered, exits) proceeds. NEVER raises."""
    import asyncio  # noqa: PLC0415

    try:
        packet = await gather_memo_packet(db, outlook, book, candidates)
    except Exception:  # noqa: BLE001
        logger.exception("thesis memo: gather failed")
        await _journal(db, "engine_failure", "critical",
                       "memo gather failed — no-op week", {"stage": "memo-gather"})
        return None
    try:
        raw = await _run_step(step, "thesis-memo",
                              lambda: asyncio.to_thread(reason_memo, packet))
    except Exception:  # noqa: BLE001
        logger.exception("thesis memo: paid call failed")
        await _journal(db, "engine_failure", "critical",
                       "memo LLM call failed — no-op week", {"stage": "thesis-memo"})
        return None
    try:
        memo = parse_memo_response(raw)
    except MemoParseError as exc:
        await _journal(db, "engine_failure", "critical",
                       f"memo schema drift — no-op week: {exc}",
                       {"stage": "memo-parse", "raw_head": raw[:2000]})
        return None

    held = {p["symbol"] for p in book}
    plan = plan_from_memo(memo, held, set(candidates))
    for r in plan["rejected"]:
        await _journal(db, "entry_rejected", "info",
                       f"{r['ticker']}: memo entry rejected — {r['reason']}", r)

    week = run_date.date().isoformat()

    async def _persist() -> Dict[str, Any]:
        await persist_memo(db, week, raw, memo)
        for slug, stage in plan["stage_updates"].items():
            try:
                await db.themebasket.update(where={"slug": slug},
                                            data={"stage": stage})
            except Exception:  # noqa: BLE001
                logger.exception("stage persist failed for %s", slug)
        return {"persisted": True}

    await _run_step(step, "memo-persist", _persist)
    return plan
```

- [ ] **Step 4: Wire into `_decide_and_execute`:** after `holdings = _build_holdings()` (~line 1223) build the two memo inputs and call the pipeline:

```python
    book = [{"symbol": h["symbol"], "qty": h["qty"],
             "avg_price": None,  # filled from pos_rows where available
             "themes": (h.get("source_tags") or {}).get("themes", []),
             "market_value": h["market_value"]} for h in holdings]
    candidates_packet = {
        sym: {
            "dist_200wma": screen.get("dist_200wma"),
            "rsi14": (light_rows.get(sym) or {}).get("rsi14"),
            "fair_value_gap_pct": (light_rows.get(sym) or {}).get("fair_value_gap_pct"),
            "valuation_score": (light_rows.get(sym) or {}).get("valuation_score"),
            "insider_score": (light_rows.get(sym) or {}).get("insider_score"),
            "dark_pool_score": (light_rows.get(sym) or {}).get("dark_pool_score"),
            "short_pct_float": (light_rows.get(sym) or {}).get("short_pct_float"),
            "atr_pct": screen.get("atr_pct"), "price": screen.get("price"),
            "themes": (screen.get("tags") or {}).get("themes", []),
        } for sym, screen in by_symbol.items()
    }
    memo_plan = await _memo_pipeline(db, outlook_ctx, book, candidates_packet,
                                     run_date, step)
```

(`outlook_ctx` is the same unwrapped outlook dict `_screen` receives.) Then:
- In stage A's trigger collection, union `memo_plan["reviews"]` (when memo_plan is not None) plus every holding whose sourcing theme's new stage is in `("crowded", "priced")` into the triggered set under the name `"memo_stage"` — same journaling path as the other five triggers.
- `plan_decisions` is now called with `candidates=[]` (entries no longer come from it; its exits/trims survive untouched — full strip happens in Task 11).
- The entry call becomes `_handshake_and_enter(db, client, memo_plan["entries"] + memo_plan["adds"] if memo_plan else [], ...)` — signature updated in Task 10.
- Add `memo": {"status": "ok" | "noop", "entries_planned": len(...)}` to the `funnel_summary` body.

- [ ] **Step 5: Run the cron suite**

Run: `/usr/bin/python3 -m pytest tests/test_sleeve_a_funnel_cron.py -v --no-cov`
Expected: new tests PASS; pre-existing tests still pass (entry-queue tests break here → they are rewritten in Tasks 10–11; if any fail at this point, mark with the Task 10/11 rewrite note rather than deleting silently).

- [ ] **Step 6: Commit**

```bash
git add inngest_app/functions/sleeve_a_funnel.py tests/test_sleeve_a_funnel_cron.py
git commit -m "feat(cron): memo pipeline — paid memoized step, stage persist, memo_stage reviews"
```

---

### Task 10: `_handshake_and_enter` takes planned entries

**Files:**
- Modify: `inngest_app/functions/sleeve_a_funnel.py` `_handshake_and_enter` (~lines 377–570)
- Test: `tests/test_sleeve_a_funnel_cron.py`

**Interfaces:**
- Consumes: planner entry items (Task 6): `{slug, stage, ticker, role, conviction, entry_style, why_now, why_this_expression}`; `size_thesis_entry`, `entry_price_and_ttl` (Task 6).
- Produces: new signature `_handshake_and_enter(db, client, planned_entries: List[Dict], screen_by_symbol: Dict[str, Dict], run_date, sleeve_equity, deployable, cash_available, holdings, sector_by_symbol, other_sleeve_sector_notional, allow_buys, step) -> List[Dict]`. Diligence is VETO-ONLY (SELL/AVOID verdict or unusable data); no conviction recompute, no formula gate.

- [ ] **Step 1: Write the failing tests** (follow the file's existing `_handshake_and_enter` test fixtures — fake client, fake db, monkeypatched `reuse_or_budget`):

```python
def test_entry_carries_memo_provenance_and_pullback_pricing(monkeypatch):
    """A planned on_pullback entry submits at max(sma20, price-atr), 14d TTL,
    and journals why_now/role/stage — the after-the-fact audit trail."""
    # planned_entries = [{"slug": "dc-energy", "stage": "catching_on",
    #                     "ticker": "BE", "role": "anchor", "conviction": 0.8,
    #                     "entry_style": "on_pullback", "why_now": "w",
    #                     "why_this_expression": "e"}]
    # screen_by_symbol = {"BE": {"price": 100.0, "sma20": 95.0, "atr": 4.0,
    #                            "atr_pct": 0.04, "liquidity_adv_usd": 5e7,
    #                            "tags": {"themes": ["dc-energy"]}}}
    # monkeypatch reuse_or_budget → {"action": "reuse", "signals": {"verdict": "buy"}}
    # assert client.submitted[0]["limit_price"] == 96.0
    # assert (client.submitted[0]["expires_at"] - RUN_DATE).days == 14
    # assert journal body has why_now == "w", role == "anchor", stage == "catching_on"


def test_sell_verdict_is_the_only_diligence_veto(monkeypatch):
    # same setup, signals {"verdict": "sell"} → no order, exit_sell_verdict journal
    # and signals {"verdict": None} (hold/absent) → order still places
```

- [ ] **Step 2: Run to verify they fail** — expected: TypeError (old signature) / assertion failures.

- [ ] **Step 3: Rewrite `_handshake_and_enter`** keeping intact: the budget gate (`reuse_or_budget`), the paid-analyze-in-own-step block (`handshake-analyze-{sym}`), `persist_full`, the guardrail call + `running_holdings` accumulation, the deterministic `coid`, and the deployable/cash decrement. Replace the selection-era parts:

```python
    for entry in planned_entries:
        sym = entry["ticker"]
        screen = screen_by_symbol.get(sym) or {}
        # ... budget gate + analyze/persist EXACTLY as before (veto-only) ...
        verdict = str((signals or {}).get("verdict") or "").strip().lower()
        if verdict in ("sell", "avoid"):
            await _journal(db, "exit_sell_verdict", "info",
                           f"{sym}: memo entry vetoed by diligence verdict",
                           {"symbol": sym, "verdict": verdict})
            continue
        try:
            price, sma20 = float(screen["price"]), float(screen["sma20"])
            atr, atr_pct = float(screen["atr"]), float(screen["atr_pct"])
        except (KeyError, TypeError, ValueError):
            await _journal(db, "engine_failure", "warning",
                           f"{sym}: screen row incomplete — cannot size", {"symbol": sym})
            continue
        limit, ttl = entry_price_and_ttl(entry["entry_style"], price, sma20, atr)
        notional = size_thesis_entry(
            entry["role"], entry["conviction"], sleeve_equity,
            float(screen.get("liquidity_adv_usd") or 0.0), atr_pct,
            deployable_remaining, cash_remaining)
        # ... guardrails + submit as before; journal gains:
        #     "role", "stage", "why_now", "why_this_expression",
        #     "memo_conviction": entry["conviction"], "entry_style": entry["entry_style"]
```

Remove: the `compute_conviction` recompute, `_conviction_input_from_signals` usage here, `extension_state`/`entry_limit_price`/`entry_ttl_days` imports if now unused.

- [ ] **Step 4: Run the cron suite** — new tests PASS; rewrite the old handshake tests that asserted conviction-gating to assert veto-only behavior instead.

- [ ] **Step 5: Commit**

```bash
git add inngest_app/functions/sleeve_a_funnel.py tests/test_sleeve_a_funnel_cron.py
git commit -m "feat(cron)!: entries from memo plan — diligence is veto-only, memo provenance journaled"
```

---

### Task 11: Strip challenger/entry-queue logic from `plan_decisions`

**Files:**
- Modify: `execution/funnel/decisions.py`
- Test: `tests/test_funnel_decisions.py`

**Interfaces:**
- Produces: `plan_decisions(holdings, sleeve_equity, max_positions, trim_ceiling=...) -> {"exits", "trims", "notes"}` — `candidates`/`evictions` parameters and `entry_queue` output DELETED. Callers: `_decide_and_execute` (updated in Task 9 to pass no candidates — update its call here to the new signature) and `execution/backtest/simulator.py` (update its call; the backtest's entry loop is out of scope for correctness — pass its candidate handling through its own local code or mark the simulator entry path deprecated with a comment; it must still import).

- [ ] **Step 1: Write the failing test** — rewrite `tests/test_funnel_decisions.py`: keep every exit/trim case; delete outcompete/hysteresis/entry-queue cases; add:

```python
def test_no_entry_authority_remains():
    """Founding-premise guard: plan_decisions can exit and trim, never enter."""
    import inspect
    from execution.funnel.decisions import plan_decisions
    sig = inspect.signature(plan_decisions)
    assert "candidates" not in sig.parameters and "evictions" not in sig.parameters
    out = plan_decisions([], 1000.0, 15)
    assert set(out) == {"exits", "trims", "notes"}
```

- [ ] **Step 2: Run to verify it fails.**

- [ ] **Step 3: Implement** — delete the challenger sort, the outcompete loop, `OUTCOMPETE_MARGIN` import, `entry_queue`, `evictions` flag; keep sell-verdict/theme-review exits and the trim block byte-identical. Update the two callers' call sites. Update the module docstring: "Priority: sell-verdict → failed theme review → risk trim. Entries belong to the thesis memo (spec 2026-07-27)."

- [ ] **Step 4: Run** `tests/test_funnel_decisions.py`, `tests/test_sleeve_a_funnel_cron.py`, and `/usr/bin/python3 -m pytest tests/ -k simulator --no-cov` — PASS / no new failures vs baseline.

- [ ] **Step 5: Commit**

```bash
git add execution/funnel/decisions.py execution/backtest/simulator.py tests/test_funnel_decisions.py inngest_app/functions/sleeve_a_funnel.py
git commit -m "feat(funnel)!: plan_decisions loses entry authority — exits and trims only"
```

---

### Task 12: End-to-end cron test, replay test, full-suite diff

**Files:**
- Test: `tests/test_sleeve_a_funnel_cron.py`

**Interfaces:** consumes everything above; produces no new API.

- [ ] **Step 1: Write the end-to-end tests** using the file's existing full-cron harness (fake db, fake broker, `step=None`) plus its replay-simulating step class (from the thesis-hold redesign work):

```python
def test_full_pass_no_op_memo_places_nothing():
    # fake LLM returns {"theses": [<all holds>], "hypothesis_updates": [], "market_view": "v"}
    # → zero submit calls, one thesis_memo journal, funnel_summary memo.status == "ok",
    #   ledger rows appended per thesis


def test_full_pass_memo_entry_places_order_with_provenance():
    # fake LLM returns one catching_on enter (at_market) for a screened symbol
    # → exactly one limit buy at round(price, 2), journal carries why_now + stage,
    #   deployable/cash decremented, coid == f"shadow-A-{sym}-{run_date:%Y%m%d}"


def test_replay_does_not_rebill_memo():
    # replay-simulating step: run the pass twice with the same step memo cache;
    # the fake LLM call counter must be 1 (thesis-memo step memoized), orders
    # not duplicated (coid guard)
```

- [ ] **Step 2: Run to verify they fail, then fix wiring until they pass.**

Run: `/usr/bin/python3 -m pytest tests/test_sleeve_a_funnel_cron.py -v --no-cov`

- [ ] **Step 3: Full-suite regression diff**

Run: `/usr/bin/python3 -m pytest tests/ --no-cov -q 2>&1 | tail -30`
Expected: failure LIST identical to the pre-branch baseline (~95 environmental) — diff the names, not the counts.

- [ ] **Step 4: Commit**

```bash
git add tests/test_sleeve_a_funnel_cron.py
git commit -m "test(cron): end-to-end memo pass + replay no-rebill guarantee"
```

---

## Post-merge operator steps (PR body checklist)

1. `python3 -m prisma migrate deploy` against Neon BEFORE merging (regenerated client reads `stage`/`ThesisEvidence`).
2. Merge → Railway deploy → wait for "Inngest handler mounted" in logs → Inngest re-sync.
3. First Monday 16:00 UTC pass: expect one `thesis_memo` journal row, `ThesisEvidence` rows per active theme, stage values on ThemeBasket, and entries ONLY with memo provenance. A no-action memo is a healthy outcome.
4. Weekly owner audit: read the memo journal next to Alpaca orders — grade the reasoning, not just P&L.

## Known follow-ups (explicitly out of scope here)

- Phase B (13F study pass) and Phase C (admin memo-trail UI) — separate plans.
- Ticker↔company cross-check on memo entries (open engine-wide item; memo entries are gated to the screened universe in the meantime).
- `FULL_RUNS_PER_WEEK`/light-run budget resizing once memo shortlists shrink the universe in practice.
- Backtest simulator still models the old entry path (imports fixed in Task 11; behavioral update only if the simulator is ever used again — spec §1: paper account is the test bed).
