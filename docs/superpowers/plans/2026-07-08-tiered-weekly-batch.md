# Tiered Weekly Batch Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the dormant full-swarm weekly batch with a tiered funnel — free screener over 191 names → free quant-only WeeklySignal snapshots for top 20 ∪ watchlisted → weighted escalation → at most 5 paid swarm analyses — capping spend at ~$8/month.

**Architecture:** One Inngest function (`weekly-batch`, Monday 03:00 UTC) with durable steps: load-outlook → screen-universe → quant-snapshots → compute-escalation → per-ticker reuse/analyze steps → batch/completed event. Escalation scoring is a pure-function module. Quant rows are written `tier="quant"` and upgraded in place to `tier="full"` when analyzed. Spec: `docs/superpowers/specs/2026-07-08-tiered-batch-design.md`.

**Tech Stack:** Python 3, FastAPI, Inngest Python SDK (guarded registration), Prisma (prisma-client-py, asyncio), yfinance via `MarketDataClient`, pytest.

## Global Constraints

- `prisma migrate dev` is BROKEN in this repo (shadow-DB baseline failure). Hand-write migration SQL, apply with `python3 -m prisma migrate deploy --schema=db/schema.prisma`. Regenerate client with `python3 -m prisma generate --schema=db/schema.prisma`.
- Railway installs **only** `requirements.txt`. This plan adds no new dependencies — do not add any.
- All tests must pass with NO network and NO `prisma` package importable (the local venv lacks it) — mock every client and DB. No LLM/dollar spend in CI; `run_stock_analysis` is always mocked.
- Inngest modules must keep the guarded-registration pattern: import cleanly (function = `None`) when the `inngest` SDK or its imports are unavailable.
- Env defaults (exact): `BATCH_MAX_CANDIDATES=20`, `BATCH_MAX_SWARM_RUNS=5`, `BATCH_ESCALATION_THRESHOLD=2.0`.
- Escalation weights (exact, module constants): prior buy +3.0, post-earnings (≤5 days) +2.5, outlook top-3 sector +2.0, screener-score divergence ≥3.0 pts +2.0, watchlist +1.5.
- WeeklySignal DB columns are camelCase with no `@map` (e.g. `"runDate"`); follow that convention for new columns.
- Test command: `python3 -m pytest <file> -v` from `/Users/tui/dvrg`.
- Commit after every task. Work on branch `tiered-batch` (create from `main` at Task 1 Step 1).

---

### Task 1: Schema + migration — tier, escalation audit, quant signals

**Files:**
- Modify: `db/schema.prisma` (WeeklySignal model, lines ~824–869)
- Create: `db/migrations/20260709000000_add_weekly_signal_tier/migration.sql`

**Interfaces:**
- Produces: WeeklySignal columns `tier` (String, default `"full"`), `escalationScore` (Float?), `escalationReasons` (Json?), `quantSignals` (Json?). Later tasks read/write these via prisma field names of the same spelling.

- [ ] **Step 1: Create the branch**

```bash
git checkout main && git pull && git checkout -b tiered-batch
```

- [ ] **Step 2: Add the columns to the model**

In `db/schema.prisma`, inside `model WeeklySignal`, immediately after the `screenerScore` field block, add:

```prisma
  // Tiered batch (2026-07-08 design)
  tier              String  @default("full") // "quant" | "full"
  escalationScore   Float?  // audit: weighted escalation score this run
  escalationReasons Json?   // audit: e.g. ["prior_buy", "post_earnings"]
  quantSignals      Json?   // {has_insider_buying, weekly_price_change_pct, days_to_earnings, days_since_earnings, on_watchlist}
```

And add `@@index([tier])` next to the existing `@@index([ticker])`.

- [ ] **Step 3: Write the migration SQL**

Create `db/migrations/20260709000000_add_weekly_signal_tier/migration.sql`:

```sql
-- Tiered batch: quant vs full rows, escalation audit trail
ALTER TABLE "weekly_signals" ADD COLUMN "tier" TEXT NOT NULL DEFAULT 'full';
ALTER TABLE "weekly_signals" ADD COLUMN "escalationScore" DOUBLE PRECISION;
ALTER TABLE "weekly_signals" ADD COLUMN "escalationReasons" JSONB;
ALTER TABLE "weekly_signals" ADD COLUMN "quantSignals" JSONB;

CREATE INDEX "weekly_signals_tier_idx" ON "weekly_signals"("tier");
```

- [ ] **Step 4: Validate schema and regenerate the client**

```bash
python3 -m prisma validate --schema=db/schema.prisma
python3 -m prisma generate --schema=db/schema.prisma
```

Expected: both succeed. If `prisma` is not importable in this venv, `validate` alone passing is acceptable — note it and move on (generate runs in production during deploy).

- [ ] **Step 5: Commit**

```bash
git add db/schema.prisma db/migrations/20260709000000_add_weekly_signal_tier/migration.sql
git commit -m "feat(batch): add tier + escalation audit columns to WeeklySignal"
```

---

### Task 2: Screener — post-earnings signal, scored results, bounded concurrency

**Files:**
- Modify: `research_swarm/data/screener.py`
- Test: `tests/test_screener.py`

**Interfaces:**
- Consumes: nothing new.
- Produces:
  - `ScreenerSignals` gains field `days_since_earnings: Optional[int] = None` (None = no earnings report in the lookback window).
  - `@dataclass ScoredTicker: ticker: str; score: float; signals: ScreenerSignals`
  - `StockScreener.screen_all(self, universe: List[str], max_workers: int = 8) -> List[ScoredTicker]` — ALL tickers scored, sorted score desc, signals collected concurrently.
  - `StockScreener.screen(self, universe, max_candidates=25) -> List[str]` — unchanged signature, now a thin wrapper over `screen_all`.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_screener.py`:

```python
import pandas as pd
from datetime import datetime, timedelta, timezone

from research_swarm.data.screener import ScoredTicker


def _mock_clients(insider=None, ret=None, earnings=None):
    market = MagicMock()
    market.calculate_return.side_effect = ret or (lambda t, days: 0.0)
    market.get_earnings_dates.side_effect = earnings or (lambda t: None)
    ins = MagicMock()
    ins.get_insider_transactions.side_effect = insider or (lambda t, days_back: [])
    return market, ins


class TestDaysSinceEarnings:
    def test_past_earnings_sets_days_since(self):
        now = datetime.now(timezone.utc)
        df = pd.DataFrame(index=pd.DatetimeIndex([now - timedelta(days=3)], tz="UTC"))
        market, ins = _mock_clients(earnings=lambda t: df)
        screener = StockScreener(market_client=market, insider_client=ins)
        signals = screener._collect_signals("AAPL")
        assert signals.days_since_earnings == 3
        assert signals.days_to_earnings is None

    def test_no_earnings_leaves_none(self):
        market, ins = _mock_clients()
        screener = StockScreener(market_client=market, insider_client=ins)
        signals = screener._collect_signals("AAPL")
        assert signals.days_since_earnings is None

    def test_default_field_keeps_positional_construction_working(self):
        s = ScreenerSignals("X", False, None, 0.0)
        assert s.days_since_earnings is None


class TestScreenAll:
    def test_returns_all_tickers_scored_desc(self):
        # MSFT gets insider buying (+3.0), AAPL gets nothing
        market, ins = _mock_clients(
            insider=lambda t, days_back: [{"transaction_type": "P"}] if t == "MSFT" else []
        )
        screener = StockScreener(market_client=market, insider_client=ins)
        result = screener.screen_all(["AAPL", "MSFT"])
        assert len(result) == 2
        assert result[0].ticker == "MSFT" and result[0].score >= 3.0
        assert result[1].ticker == "AAPL"
        assert isinstance(result[0], ScoredTicker)
        assert result[0].signals.has_insider_buying is True

    def test_screen_delegates_to_screen_all(self):
        market, ins = _mock_clients(
            insider=lambda t, days_back: [{"transaction_type": "P"}] if t == "MSFT" else []
        )
        screener = StockScreener(market_client=market, insider_client=ins)
        assert screener.screen(["AAPL", "MSFT"], max_candidates=1) == ["MSFT"]

    def test_concurrent_run_completes_for_many_tickers(self):
        market, ins = _mock_clients()
        screener = StockScreener(market_client=market, insider_client=ins)
        universe = [f"T{i}" for i in range(40)]
        result = screener.screen_all(universe, max_workers=8)
        assert sorted(st.ticker for st in result) == sorted(universe)
```

- [ ] **Step 2: Run tests to verify the new ones fail**

Run: `python3 -m pytest tests/test_screener.py -v`
Expected: existing tests PASS; new tests FAIL (`ImportError: cannot import name 'ScoredTicker'`).

- [ ] **Step 3: Implement**

In `research_swarm/data/screener.py`:

(a) Add the field to `ScreenerSignals` (keep the existing four fields first so positional construction still works):

```python
@dataclass
class ScreenerSignals:
    ticker: str
    has_insider_buying: bool
    days_to_earnings: Optional[int]  # None = no upcoming earnings in 30d
    weekly_price_change_pct: Optional[float]  # None = data unavailable
    days_since_earnings: Optional[int] = None  # None = no recent report
```

(b) Add after `ScreenerSignals`:

```python
@dataclass
class ScoredTicker:
    ticker: str
    score: float
    signals: ScreenerSignals
```

(c) In `_collect_signals`, replace the earnings `try` block body with (adds the past-dates branch; keeps the guard style):

```python
        days_since_earnings = None  # type: Optional[int]
        try:
            earnings_df = self._market.get_earnings_dates(ticker)
            if earnings_df is not None and not earnings_df.empty:
                from datetime import datetime, timezone
                now = datetime.now(timezone.utc)
                future_dates = [
                    d for d in earnings_df.index
                    if hasattr(d, "tzinfo") and d > now
                ]
                past_dates = [
                    d for d in earnings_df.index
                    if hasattr(d, "tzinfo") and d <= now
                ]
                if future_dates:
                    next_earnings = min(future_dates)
                    days_to_earnings = (next_earnings - now).days
                if past_dates:
                    last_earnings = max(past_dates)
                    days_since_earnings = (now - last_earnings).days
        except Exception as e:
            logger.debug("Earnings data error for %s: %s", ticker, e)
```

and pass `days_since_earnings=days_since_earnings` in the returned `ScreenerSignals(...)`.

(d) Replace `screen()` with:

```python
    def screen_all(self, universe: List[str], max_workers: int = 8) -> List[ScoredTicker]:
        """Score every ticker in universe (signals collected concurrently),
        sorted score descending. ~570 network calls for the full universe —
        the thread pool keeps this inside Inngest's 15-minute step limit."""
        from concurrent.futures import ThreadPoolExecutor

        with ThreadPoolExecutor(max_workers=max_workers) as pool:
            all_signals = list(pool.map(self._collect_signals, universe))

        scored = [ScoredTicker(s.ticker, score_ticker(s), s) for s in all_signals]
        scored.sort(key=lambda st: st.score, reverse=True)
        for st in scored:
            logger.debug("Screener %s: score=%.1f", st.ticker, st.score)
        return scored

    def screen(self, universe: List[str], max_candidates: int = 25) -> List[str]:
        """Top max_candidates tickers by screener score (highest first)."""
        return [st.ticker for st in self.screen_all(universe)[:max_candidates]]
```

- [ ] **Step 4: Run all screener tests**

Run: `python3 -m pytest tests/test_screener.py -v`
Expected: ALL PASS (old and new).

- [ ] **Step 5: Commit**

```bash
git add research_swarm/data/screener.py tests/test_screener.py
git commit -m "feat(screener): post-earnings signal, ScoredTicker results, concurrent collection"
```

---

### Task 3: Sector map — annotate the universe, expose a loader

**Files:**
- Create: `scripts/add_sectors_to_universe.py`
- Modify: `research_swarm/data/universes/sp500_universe.json` (script output)
- Modify: `research_swarm/data/screener.py` (loader)
- Test: `tests/test_screener.py`

**Interfaces:**
- Produces: `StockScreener.load_sector_map() -> Dict[str, str]` (static method) — uppercase ticker → SPDR sector name. Sector names MUST match `execution/constants.py` `SECTOR_ETFS` values exactly: `Technology, Energy, Financials, Health Care, Industrials, Consumer Discretionary, Consumer Staples, Utilities, Materials, Real Estate, Communication Services` (these are the `sector` values inside `MarketOutlook.sectorRankings`).

- [ ] **Step 1: Write the failing test**

Append to `tests/test_screener.py`:

```python
class TestSectorMap:
    def test_load_sector_map_returns_spdr_sectors(self):
        sector_map = StockScreener.load_sector_map()
        # coverage: the vast majority of the 191-name universe is annotated
        assert len(sector_map) >= 170
        assert sector_map["AAPL"] == "Technology"
        valid = {
            "Technology", "Energy", "Financials", "Health Care", "Industrials",
            "Consumer Discretionary", "Consumer Staples", "Utilities",
            "Materials", "Real Estate", "Communication Services",
        }
        assert set(sector_map.values()) <= valid

    def test_load_universe_shape_unchanged(self):
        universe = StockScreener.load_universe()
        assert len(universe) == 191
        assert all(isinstance(t, str) for t in universe)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_screener.py::TestSectorMap -v`
Expected: FAIL (`AttributeError: ... has no attribute 'load_sector_map'`).

- [ ] **Step 3: Write the one-off annotation script**

Create `scripts/add_sectors_to_universe.py`:

```python
"""One-off: annotate sp500_universe.json with SPDR-style sector names via yfinance.

Adds a top-level "sectors" object {ticker: sector} alongside the existing
"tickers" list (which is left untouched). Resumable — reruns skip tickers
already annotated. Sector names are normalized to the SPDR names used by
MarketOutlook.sectorRankings (see execution/constants.py SECTOR_ETFS).
"""
import json
import time
from pathlib import Path

import yfinance as yf

UNIVERSE = (
    Path(__file__).resolve().parents[1]
    / "research_swarm" / "data" / "universes" / "sp500_universe.json"
)

YF_TO_SPDR = {
    "Technology": "Technology",
    "Financial Services": "Financials",
    "Healthcare": "Health Care",
    "Consumer Cyclical": "Consumer Discretionary",
    "Consumer Defensive": "Consumer Staples",
    "Communication Services": "Communication Services",
    "Industrials": "Industrials",
    "Energy": "Energy",
    "Utilities": "Utilities",
    "Basic Materials": "Materials",
    "Real Estate": "Real Estate",
}


def main() -> None:
    data = json.loads(UNIVERSE.read_text())
    sectors = data.get("sectors", {})
    missing = [t for t in data["tickers"] if t not in sectors]
    print(f"{len(missing)} tickers to annotate")

    for ticker in missing:
        try:
            raw = yf.Ticker(ticker).info.get("sector")
        except Exception as e:
            print(f"ERROR   {ticker}: {e}")
            continue
        mapped = YF_TO_SPDR.get(raw)
        if mapped:
            sectors[ticker] = mapped
            print(f"ok      {ticker}: {mapped}")
        else:
            print(f"UNMAPPED {ticker}: {raw!r}")
        time.sleep(0.3)  # be polite to Yahoo

    data["sectors"] = dict(sorted(sectors.items()))
    UNIVERSE.write_text(json.dumps(data, indent=2) + "\n")
    print(f"done: {len(sectors)}/{len(data['tickers'])} annotated")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run the script (real network — this is data generation, not a test)**

Run: `python3 scripts/add_sectors_to_universe.py`
Expected: final line `done: N/191 annotated` with N ≥ 170. Rerun once if transient Yahoo errors left N short. Tickers that stay unmapped simply never receive outlook-sector escalation points — acceptable.

- [ ] **Step 5: Add the loader**

In `research_swarm/data/screener.py`, inside `StockScreener` next to `load_universe`:

```python
    @staticmethod
    def load_sector_map() -> Dict[str, str]:
        """Uppercase ticker → SPDR sector name (matches MarketOutlook
        sectorRankings 'sector' values). Tickers without annotation are absent."""
        with open(_UNIVERSE_PATH) as f:
            data = json.load(f)
        return {str(t).upper(): s for t, s in data.get("sectors", {}).items()}
```

Add `Dict` to the existing `typing` import.

- [ ] **Step 6: Run tests**

Run: `python3 -m pytest tests/test_screener.py -v`
Expected: ALL PASS.

- [ ] **Step 7: Commit**

```bash
git add scripts/add_sectors_to_universe.py research_swarm/data/universes/sp500_universe.json research_swarm/data/screener.py tests/test_screener.py
git commit -m "feat(screener): sector map for outlook-favored escalation trigger"
```

---

### Task 4: Escalation module — pure weighted scoring

**Files:**
- Create: `research_swarm/data/escalation.py`
- Test: `tests/test_escalation.py`

**Interfaces:**
- Consumes: nothing (pure module — no I/O, no DB, no imports beyond stdlib).
- Produces (exact — Task 6 depends on these):

```python
@dataclass EscalationCandidate:
    ticker: str
    screener_score: float
    sector: Optional[str] = None
    prior_screener_score: Optional[float] = None
    prior_verdict: Optional[str] = None
    days_since_earnings: Optional[int] = None
    on_watchlist: bool = False
    has_fresh_report: bool = False

@dataclass EscalationContext:
    favored_sectors: frozenset  # SPDR sector names; empty = no/stale outlook

@dataclass EscalationDecision:
    ticker: str
    score: float
    reasons: List[str]
    action: str  # "swarm" | "reuse" | "hold"

escalation_score(candidate, context) -> Tuple[float, List[str]]
select_escalations(candidates, context, cap=5, threshold=2.0) -> List[EscalationDecision]
```

`select_escalations` returns one decision per candidate, same order as input. Reason strings (exact): `"prior_buy"`, `"post_earnings"`, `"outlook_sector"`, `"score_divergence"`, `"watchlist"`.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_escalation.py`:

```python
"""Tests for the pure escalation scoring module."""
from research_swarm.data.escalation import (
    EscalationCandidate,
    EscalationContext,
    escalation_score,
    select_escalations,
)

CTX = EscalationContext(favored_sectors=frozenset({"Technology", "Energy", "Financials"}))
EMPTY_CTX = EscalationContext(favored_sectors=frozenset())


def cand(**kw):
    return EscalationCandidate(ticker=kw.pop("ticker", "AAPL"),
                               screener_score=kw.pop("screener_score", 5.0), **kw)


class TestEscalationScore:
    def test_no_triggers_scores_zero(self):
        score, reasons = escalation_score(cand(), EMPTY_CTX)
        assert score == 0.0 and reasons == []

    def test_prior_buy(self):
        score, reasons = escalation_score(cand(prior_verdict="buy"), EMPTY_CTX)
        assert score == 3.0 and reasons == ["prior_buy"]

    def test_prior_hold_does_not_trigger(self):
        score, _ = escalation_score(cand(prior_verdict="hold"), EMPTY_CTX)
        assert score == 0.0

    def test_post_earnings_within_5_days(self):
        score, reasons = escalation_score(cand(days_since_earnings=5), EMPTY_CTX)
        assert score == 2.5 and reasons == ["post_earnings"]

    def test_earnings_6_days_ago_does_not_trigger(self):
        score, _ = escalation_score(cand(days_since_earnings=6), EMPTY_CTX)
        assert score == 0.0

    def test_outlook_favored_sector(self):
        score, reasons = escalation_score(cand(sector="Technology"), CTX)
        assert score == 2.0 and reasons == ["outlook_sector"]

    def test_unfavored_sector_does_not_trigger(self):
        score, _ = escalation_score(cand(sector="Utilities"), CTX)
        assert score == 0.0

    def test_no_outlook_means_no_sector_points(self):
        score, _ = escalation_score(cand(sector="Technology"), EMPTY_CTX)
        assert score == 0.0

    def test_divergence_up(self):
        score, reasons = escalation_score(
            cand(screener_score=6.0, prior_screener_score=3.0), EMPTY_CTX)
        assert score == 2.0 and reasons == ["score_divergence"]

    def test_divergence_down_also_triggers(self):
        score, _ = escalation_score(
            cand(screener_score=1.0, prior_screener_score=4.5), EMPTY_CTX)
        assert score == 2.0

    def test_small_move_does_not_trigger(self):
        score, _ = escalation_score(
            cand(screener_score=5.0, prior_screener_score=3.0), EMPTY_CTX)
        assert score == 0.0

    def test_no_prior_score_means_no_divergence(self):
        score, _ = escalation_score(cand(screener_score=9.0), EMPTY_CTX)
        assert score == 0.0

    def test_watchlist(self):
        score, reasons = escalation_score(cand(on_watchlist=True), EMPTY_CTX)
        assert score == 1.5 and reasons == ["watchlist"]

    def test_triggers_sum(self):
        score, reasons = escalation_score(
            cand(prior_verdict="buy", days_since_earnings=2, on_watchlist=True), EMPTY_CTX)
        assert score == 3.0 + 2.5 + 1.5
        assert reasons == ["prior_buy", "post_earnings", "watchlist"]


class TestSelectEscalations:
    def test_watchlist_alone_stays_below_threshold(self):
        decisions = select_escalations([cand(on_watchlist=True)], EMPTY_CTX)
        assert decisions[0].action == "hold"

    def test_exactly_threshold_escalates(self):
        decisions = select_escalations([cand(sector="Technology")], CTX)  # 2.0
        assert decisions[0].action == "swarm"

    def test_cap_takes_top_by_score(self):
        cands = [cand(ticker=f"T{i}", prior_verdict="buy") for i in range(4)]
        cands += [cand(ticker=f"E{i}", days_since_earnings=1) for i in range(3)]
        decisions = select_escalations(cands, EMPTY_CTX, cap=5)
        swarm = {d.ticker for d in decisions if d.action == "swarm"}
        # all four prior-buys (3.0) beat post-earnings (2.5); one earnings pick fills slot 5
        assert {"T0", "T1", "T2", "T3"} <= swarm and len(swarm) == 5

    def test_tiebreak_is_deterministic(self):
        cands = [cand(ticker="BBB", prior_verdict="buy", screener_score=5.0),
                 cand(ticker="AAA", prior_verdict="buy", screener_score=5.0)]
        first = select_escalations(cands, EMPTY_CTX, cap=1)
        second = select_escalations(list(reversed(cands)), EMPTY_CTX, cap=1)
        pick1 = [d.ticker for d in first if d.action == "swarm"]
        pick2 = [d.ticker for d in second if d.action == "swarm"]
        assert pick1 == pick2 == ["AAA"]  # ticker asc breaks the tie

    def test_fresh_report_reuses_without_consuming_slot(self):
        cands = [cand(ticker=f"T{i}", prior_verdict="buy") for i in range(5)]
        cands.append(cand(ticker="FRESH", prior_verdict="buy", has_fresh_report=True))
        decisions = select_escalations(cands, EMPTY_CTX, cap=5)
        by = {d.ticker: d for d in decisions}
        assert by["FRESH"].action == "reuse"
        assert sum(1 for d in decisions if d.action == "swarm") == 5

    def test_fresh_report_below_threshold_holds(self):
        decisions = select_escalations(
            [cand(on_watchlist=True, has_fresh_report=True)], EMPTY_CTX)
        assert decisions[0].action == "hold"

    def test_every_candidate_gets_a_decision_in_input_order(self):
        cands = [cand(ticker="A"), cand(ticker="B", prior_verdict="buy")]
        decisions = select_escalations(cands, EMPTY_CTX)
        assert [d.ticker for d in decisions] == ["A", "B"]
        assert decisions[0].score == 0.0 and decisions[1].score == 3.0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_escalation.py -v`
Expected: FAIL (`ModuleNotFoundError: No module named 'research_swarm.data.escalation'`).

- [ ] **Step 3: Implement the module**

Create `research_swarm/data/escalation.py`:

```python
"""Escalation scoring — decides which quant-tier tickers earn paid swarm analysis.

Pure functions only: no I/O, no DB, no LLM. The weekly batch builds
EscalationCandidate objects from screener output + prior WeeklySignal rows and
feeds them here. Spec: docs/superpowers/specs/2026-07-08-tiered-batch-design.md
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional, Tuple

# Trigger weights (spec-fixed; tune only with escalationReasons audit data)
W_PRIOR_BUY = 3.0
W_POST_EARNINGS = 2.5
W_OUTLOOK_SECTOR = 2.0
W_DIVERGENCE = 2.0
W_WATCHLIST = 1.5

POST_EARNINGS_MAX_DAYS = 5
DIVERGENCE_MIN_DELTA = 3.0
DEFAULT_THRESHOLD = 2.0
DEFAULT_CAP = 5


@dataclass
class EscalationCandidate:
    ticker: str
    screener_score: float
    sector: Optional[str] = None
    prior_screener_score: Optional[float] = None
    prior_verdict: Optional[str] = None
    days_since_earnings: Optional[int] = None
    on_watchlist: bool = False
    has_fresh_report: bool = False


@dataclass
class EscalationContext:
    favored_sectors: frozenset = field(default_factory=frozenset)


@dataclass
class EscalationDecision:
    ticker: str
    score: float
    reasons: List[str]
    action: str  # "swarm" | "reuse" | "hold"


def escalation_score(
    candidate: EscalationCandidate, context: EscalationContext
) -> Tuple[float, List[str]]:
    """Weighted trigger score and the reasons that fired, in fixed order."""
    score = 0.0
    reasons: List[str] = []

    if candidate.prior_verdict == "buy":
        score += W_PRIOR_BUY
        reasons.append("prior_buy")

    if (
        candidate.days_since_earnings is not None
        and candidate.days_since_earnings <= POST_EARNINGS_MAX_DAYS
    ):
        score += W_POST_EARNINGS
        reasons.append("post_earnings")

    if candidate.sector and candidate.sector in context.favored_sectors:
        score += W_OUTLOOK_SECTOR
        reasons.append("outlook_sector")

    if (
        candidate.prior_screener_score is not None
        and abs(candidate.screener_score - candidate.prior_screener_score)
        >= DIVERGENCE_MIN_DELTA
    ):
        score += W_DIVERGENCE
        reasons.append("score_divergence")

    if candidate.on_watchlist:
        score += W_WATCHLIST
        reasons.append("watchlist")

    return score, reasons


def select_escalations(
    candidates: List[EscalationCandidate],
    context: EscalationContext,
    cap: int = DEFAULT_CAP,
    threshold: float = DEFAULT_THRESHOLD,
) -> List[EscalationDecision]:
    """One decision per candidate (input order preserved).

    Qualified (score >= threshold) candidates with a fresh user report are
    marked "reuse" — free, no cap slot. The remaining qualified candidates
    rank by (score desc, screener_score desc, ticker asc); the top `cap`
    become "swarm". Everything else is "hold".
    """
    by_ticker = {c.ticker: c for c in candidates}
    decisions = []
    for c in candidates:
        score, reasons = escalation_score(c, context)
        action = "hold"
        if score >= threshold and c.has_fresh_report:
            action = "reuse"
        decisions.append(EscalationDecision(c.ticker, score, reasons, action))

    contenders = [d for d in decisions if d.action == "hold" and d.score >= threshold]
    contenders.sort(
        key=lambda d: (-d.score, -by_ticker[d.ticker].screener_score, d.ticker)
    )
    for d in contenders[:cap]:
        d.action = "swarm"

    return decisions
```

- [ ] **Step 4: Run tests**

Run: `python3 -m pytest tests/test_escalation.py -v`
Expected: ALL PASS.

- [ ] **Step 5: Commit**

```bash
git add research_swarm/data/escalation.py tests/test_escalation.py
git commit -m "feat(batch): pure weighted escalation scoring module"
```

---

### Task 5: WeeklySignalService — quant snapshots, upgrades, priors, fresh-report reuse

**Files:**
- Modify: `api/services/weekly_signal_service.py`
- Test: `tests/test_weekly_signal_service.py`

**Interfaces:**
- Consumes: `extract_signals_from_result` (already in this module); `MarketContext` (already imported).
- Produces (exact — Task 6 depends on these; all methods on `WeeklySignalService`, keyword-only args):

```python
async get_prior_context(ticker: str, before: datetime) -> Dict[str, Any]
    # {"prior_screener_score": float|None,   ← most recent row, ANY tier
    #  "prior_verdict": str|None,            ← most recent row WITH a verdict
    #  "prior_ev_probability": float|None}   ← same full row
async store_quant_snapshot(*, ticker, run_date, screener_score, current_price,
                           quant_signals: Dict, market_context: MarketContext,
                           prior_ctx: Dict) -> None   # upserts tier="quant" row
async record_escalation(*, ticker, run_date, score: float, reasons: List[str]) -> None
async upgrade_to_full(*, ticker, run_date, result: Dict, escalation_score: float,
                      escalation_reasons: List[str]) -> bool  # False if result unusable
async find_fresh_result(ticker: str, max_age_days: int = 7) -> Optional[Dict[str, Any]]
```

- [ ] **Step 1: Add the guarded Json import**

At the top of `api/services/weekly_signal_service.py`, after the existing imports:

```python
try:
    from prisma import Json
except Exception:  # prisma client not generated in this environment (e.g. local venv)
    def Json(value):  # type: ignore[misc]
        return value
```

(Required so the module keeps importing in the prisma-less local venv while production writes proper `Json` values.)

- [ ] **Step 2: Write the failing tests**

Append to `tests/test_weekly_signal_service.py`:

```python
from datetime import timedelta

from api.services.market_context_service import MarketContext


def _mock_db():
    db = MagicMock()
    db.weeklysignal.find_first = AsyncMock(return_value=None)
    db.weeklysignal.upsert = AsyncMock()
    db.weeklysignal.update = AsyncMock()
    db.stockresult.find_first = AsyncMock(return_value=None)
    return db


RUN_DATE = datetime(2026, 7, 13, tzinfo=timezone.utc)
MC = MarketContext(es_change_pct=1.0, nq_change_pct=2.0, dow_change_pct=0.5)


class TestGetPriorContext:
    @pytest.mark.asyncio
    async def test_splits_any_tier_score_from_full_tier_verdict(self):
        db = _mock_db()
        prior_any = MagicMock(screenerScore=4.0)
        prior_full = MagicMock(verdict="buy", evProbability=0.7)
        db.weeklysignal.find_first = AsyncMock(side_effect=[prior_any, prior_full])
        service = WeeklySignalService(db=db)
        ctx = await service.get_prior_context("AAPL", before=RUN_DATE)
        assert ctx == {
            "prior_screener_score": 4.0,
            "prior_verdict": "buy",
            "prior_ev_probability": 0.7,
        }
        # second lookup must exclude verdict-less quant rows
        _, second_call = db.weeklysignal.find_first.call_args_list
        assert second_call.kwargs["where"]["verdict"] == {"not": None}

    @pytest.mark.asyncio
    async def test_no_history_returns_nones(self):
        service = WeeklySignalService(db=_mock_db())
        ctx = await service.get_prior_context("AAPL", before=RUN_DATE)
        assert ctx == {
            "prior_screener_score": None,
            "prior_verdict": None,
            "prior_ev_probability": None,
        }


class TestStoreQuantSnapshot:
    @pytest.mark.asyncio
    async def test_upserts_quant_row_with_continuity(self):
        db = _mock_db()
        service = WeeklySignalService(db=db)
        await service.store_quant_snapshot(
            ticker="AAPL", run_date=RUN_DATE, screener_score=5.5,
            current_price=175.2,
            quant_signals={"has_insider_buying": True},
            market_context=MC,
            prior_ctx={"prior_screener_score": 2.0, "prior_verdict": "buy",
                       "prior_ev_probability": 0.7},
        )
        kwargs = db.weeklysignal.upsert.call_args.kwargs
        assert kwargs["where"] == {
            "ticker_runDate": {"ticker": "AAPL", "runDate": RUN_DATE}
        }
        create = kwargs["data"]["create"]
        assert create["tier"] == "quant"
        assert create["verdict"] is None
        assert create["screenerScore"] == 5.5
        assert create["currentPrice"] == 175.2
        assert create["priorVerdict"] == "buy"
        assert create["priorEvProbability"] == 0.7
        assert create["esChangePct"] == 1.0


class TestRecordEscalation:
    @pytest.mark.asyncio
    async def test_updates_row_with_score_and_reasons(self):
        db = _mock_db()
        service = WeeklySignalService(db=db)
        await service.record_escalation(
            ticker="AAPL", run_date=RUN_DATE, score=5.5, reasons=["prior_buy"])
        kwargs = db.weeklysignal.update.call_args.kwargs
        assert kwargs["where"] == {
            "ticker_runDate": {"ticker": "AAPL", "runDate": RUN_DATE}
        }
        assert kwargs["data"]["escalationScore"] == 5.5


class TestUpgradeToFull:
    @pytest.mark.asyncio
    async def test_completed_result_updates_row_to_full(self):
        db = _mock_db()
        service = WeeklySignalService(db=db)
        ok = await service.upgrade_to_full(
            ticker="AAPL", run_date=RUN_DATE, result=SAMPLE_RESULT,
            escalation_score=5.5, escalation_reasons=["prior_buy"])
        assert ok is True
        kwargs = db.weeklysignal.update.call_args.kwargs
        data = kwargs["data"]
        assert data["tier"] == "full"
        assert data["verdict"] == "buy"
        assert data["fairValue"] == 213.50
        assert data["escalationScore"] == 5.5

    @pytest.mark.asyncio
    async def test_failed_result_returns_false_without_update(self):
        db = _mock_db()
        service = WeeklySignalService(db=db)
        ok = await service.upgrade_to_full(
            ticker="AAPL", run_date=RUN_DATE, result={"status": "failed"},
            escalation_score=5.5, escalation_reasons=[])
        assert ok is False
        db.weeklysignal.update.assert_not_awaited()


class TestFindFreshResult:
    @pytest.mark.asyncio
    async def test_returns_full_output_with_status_defaulted(self):
        db = _mock_db()
        row = MagicMock(fullOutput={"verdict": "buy"})
        db.stockresult.find_first = AsyncMock(return_value=row)
        service = WeeklySignalService(db=db)
        result = await service.find_fresh_result("AAPL")
        assert result == {"verdict": "buy", "status": "completed"}
        where = db.stockresult.find_first.call_args.kwargs["where"]
        assert where["ticker"] == "AAPL"
        assert where["status"] == "completed"
        assert "gte" in where["createdAt"]

    @pytest.mark.asyncio
    async def test_no_row_or_empty_output_returns_none(self):
        service = WeeklySignalService(db=_mock_db())
        assert await service.find_fresh_result("AAPL") is None
        db = _mock_db()
        db.stockresult.find_first = AsyncMock(return_value=MagicMock(fullOutput=None))
        assert await WeeklySignalService(db=db).find_fresh_result("AAPL") is None
```

- [ ] **Step 3: Run tests to verify the new ones fail**

Run: `python3 -m pytest tests/test_weekly_signal_service.py -v`
Expected: existing tests PASS; new tests FAIL (`AttributeError` on the new methods).

- [ ] **Step 4: Implement the methods**

Add to `WeeklySignalService` (after `store_signal`; also add `from datetime import timedelta, timezone` alongside the existing `datetime` import, and `List` to typing imports):

```python
    async def _get_prior_full_signal(
        self, ticker: str, before: datetime
    ) -> Optional[Any]:
        """Most recent row that carries a verdict — the continuity source.
        Quant rows have verdict=None and must not blank out priorVerdict."""
        try:
            return await self._db.weeklysignal.find_first(
                where={
                    "ticker": ticker,
                    "runDate": {"lt": before},
                    "verdict": {"not": None},
                },
                order={"runDate": "desc"},
            )
        except Exception as e:
            logger.warning("Could not fetch prior full signal for %s: %s", ticker, e)
            return None

    async def get_prior_context(self, ticker: str, before: datetime) -> Dict[str, Any]:
        """Prior-week context for continuity and divergence detection."""
        prior_any = await self._get_prior_week_signal(ticker, before=before)
        prior_full = await self._get_prior_full_signal(ticker, before=before)
        return {
            "prior_screener_score": prior_any.screenerScore if prior_any else None,
            "prior_verdict": prior_full.verdict if prior_full else None,
            "prior_ev_probability": prior_full.evProbability if prior_full else None,
        }

    async def store_quant_snapshot(
        self,
        *,
        ticker: str,
        run_date: datetime,
        screener_score: float,
        current_price: Optional[float],
        quant_signals: Dict[str, Any],
        market_context: MarketContext,
        prior_ctx: Dict[str, Any],
    ) -> None:
        """Upsert a free (no-LLM) tier="quant" WeeklySignal row."""
        data = {
            "ticker": ticker,
            "runDate": run_date,
            "tier": "quant",
            "verdict": None,
            "currentPrice": current_price,
            "screenerScore": screener_score,
            "quantSignals": Json(quant_signals),
            "esChangePct": market_context.es_change_pct,
            "nqChangePct": market_context.nq_change_pct,
            "dowChangePct": market_context.dow_change_pct,
            "priorVerdict": prior_ctx.get("prior_verdict"),
            "priorEvProbability": prior_ctx.get("prior_ev_probability"),
        }
        await self._db.weeklysignal.upsert(
            where={"ticker_runDate": {"ticker": ticker, "runDate": run_date}},
            data={"create": data, "update": {k: v for k, v in data.items()
                                             if k not in ("ticker", "runDate")}},
        )

    async def record_escalation(
        self, *, ticker: str, run_date: datetime, score: float, reasons: List[str]
    ) -> None:
        """Stamp the escalation audit trail on an existing row."""
        try:
            await self._db.weeklysignal.update(
                where={"ticker_runDate": {"ticker": ticker, "runDate": run_date}},
                data={"escalationScore": score, "escalationReasons": Json(reasons)},
            )
        except Exception as e:
            logger.warning("Could not record escalation for %s: %s", ticker, e)

    async def upgrade_to_full(
        self,
        *,
        ticker: str,
        run_date: datetime,
        result: Dict[str, Any],
        escalation_score: float,
        escalation_reasons: List[str],
    ) -> bool:
        """Upgrade a quant row in place with full-analysis fields.
        Returns False (row stays tier="quant") if the result is unusable."""
        signals = extract_signals_from_result(result, ticker=ticker)
        if signals is None:
            logger.info("Not upgrading %s — analysis did not complete", ticker)
            return False
        await self._db.weeklysignal.update(
            where={"ticker_runDate": {"ticker": ticker, "runDate": run_date}},
            data={
                "tier": "full",
                "verdict": signals.get("verdict"),
                "currentPrice": signals.get("currentPrice"),
                "fairValue": signals.get("fairValue"),
                "fairValueGapPct": signals.get("fair_value_gap_pct"),
                "evProbability": signals.get("ev_probability"),
                "stopLossProbability": signals.get("stop_loss_probability"),
                "insiderScore": signals.get("insiderScore"),
                "darkPoolScore": signals.get("darkPoolScore"),
                "sentimentScore": signals.get("sentimentScore"),
                "synthesisSummary": signals.get("synthesis_summary"),
                "catalystSummary": signals.get("catalystSummary"),
                "positionSizeRec": signals.get("positionSizeRec"),
                "escalationScore": escalation_score,
                "escalationReasons": Json(escalation_reasons),
            },
        )
        logger.info("Upgraded %s to full (verdict=%s)", ticker, signals.get("verdict"))
        return True

    async def find_fresh_result(
        self, ticker: str, max_age_days: int = 7
    ) -> Optional[Dict[str, Any]]:
        """Most recent completed user analysis within max_age_days, as a result
        dict compatible with extract_signals_from_result. None if absent."""
        cutoff = datetime.now(timezone.utc) - timedelta(days=max_age_days)
        try:
            row = await self._db.stockresult.find_first(
                where={
                    "ticker": ticker,
                    "status": "completed",
                    "createdAt": {"gte": cutoff},
                },
                order={"createdAt": "desc"},
            )
        except Exception as e:
            logger.warning("Fresh-result lookup failed for %s: %s", ticker, e)
            return None
        if row is None or not row.fullOutput:
            return None
        result = dict(row.fullOutput)
        result.setdefault("status", "completed")
        return result
```

- [ ] **Step 5: Run tests**

Run: `python3 -m pytest tests/test_weekly_signal_service.py -v`
Expected: ALL PASS.

- [ ] **Step 6: Commit**

```bash
git add api/services/weekly_signal_service.py tests/test_weekly_signal_service.py
git commit -m "feat(signals): quant snapshots, tier upgrades, prior context, fresh-report reuse"
```

---

### Task 6: Rewrite weekly_batch.py and register it

**Files:**
- Modify: `inngest_app/functions/weekly_batch.py` (full rewrite of the function body; keep the guarded-registration skeleton)
- Modify: `inngest_app/index.py`
- Test: `tests/test_weekly_batch_registration.py` (create)

**Interfaces:**
- Consumes: `StockScreener.screen_all` / `load_universe` / `load_sector_map` (Task 2/3), `select_escalations` / `EscalationCandidate` / `EscalationContext` (Task 4), `WeeklySignalService.get_prior_context` / `store_quant_snapshot` / `record_escalation` / `upgrade_to_full` / `find_fresh_result` (Task 5), `run_stock_analysis` (existing), `MarketContextService` / `MarketDataClient` / `get_db` (existing).
- Produces: registered Inngest function `weekly-batch` in `ACTIVE_FUNCTIONS`.

- [ ] **Step 1: Write the failing registration test**

Create `tests/test_weekly_batch_registration.py`:

```python
"""Guarded-registration checks for the tiered weekly batch."""
import pytest


def test_module_imports_cleanly_without_optional_deps():
    """Must never raise at import time — even without inngest/prisma installed."""
    import inngest_app.functions.weekly_batch as wb  # noqa: F401


def test_registers_when_deps_available():
    pytest.importorskip("inngest")
    pytest.importorskip("prisma")
    from inngest_app.functions.weekly_batch import weekly_batch
    assert weekly_batch is not None


def test_active_functions_includes_weekly_batch_when_registered():
    from inngest_app.functions.weekly_batch import weekly_batch
    from inngest_app.index import ACTIVE_FUNCTIONS
    if weekly_batch is not None:
        assert weekly_batch in ACTIVE_FUNCTIONS
    else:
        assert weekly_batch not in ACTIVE_FUNCTIONS
```

- [ ] **Step 2: Run it to establish the baseline**

Run: `python3 -m pytest tests/test_weekly_batch_registration.py -v`
Expected: first test PASS (module already guards). Second and third depend on the venv: in the prisma-less local venv the second SKIPs and the third passes trivially (`weekly_batch` is `None`); in a fully-provisioned env the third FAILs because the dormant function isn't registered. Either way this is just the baseline — proceed.

- [ ] **Step 3: Rewrite the batch function**

Replace the entire contents of `inngest_app/functions/weekly_batch.py` with:

```python
"""
Tiered weekly batch: screener → quant snapshots → escalation → capped swarm.

Fires Monday 03:00 UTC (Sunday 11 PM ET), 7 hours after the Sunday 20:00 UTC
MarketOutlook cron, so a fresh outlook exists.

Funnel (docs/superpowers/specs/2026-07-08-tiered-batch-design.md):
  191 names, free screener
    → top BATCH_MAX_CANDIDATES ∪ watchlisted: free quant rows (tier="quant")
    → weighted escalation scoring (free)
    → ≤ BATCH_MAX_SWARM_RUNS paid swarm analyses (rows upgraded to "full").
Fresh user reports (<7d) are reused at zero cost and consume no cap slot.
Failed swarm slots are NOT refunded — runs stay deterministic and bounded.
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_MAX_CANDIDATES = int(os.getenv("BATCH_MAX_CANDIDATES", "20"))
_MAX_SWARM_RUNS = int(os.getenv("BATCH_MAX_SWARM_RUNS", "5"))
_ESCALATION_THRESHOLD = float(os.getenv("BATCH_ESCALATION_THRESHOLD", "2.0"))
_OUTLOOK_MAX_AGE_DAYS = 8
_FRESH_REPORT_MAX_AGE_DAYS = 7
_TOP_SECTORS = 3
_QUARTERS = ["Q4_2024", "Q1_2025", "Q2_2025", "Q3_2025"]
_NEWS_DAYS_BACK = 30


def _get_batch_user_id() -> str:
    """Return BATCH_SYSTEM_USER_ID, raising at call time (not module load) if unset."""
    uid = os.getenv("BATCH_SYSTEM_USER_ID", "")
    if not uid:
        raise RuntimeError(
            "BATCH_SYSTEM_USER_ID env var is not set. "
            "Set it to the UUID of your admin user in the User table."
        )
    return uid


def _register_inngest_function():
    """Register the Inngest function. Called at module load only when the
    inngest client is importable (i.e. not during unit-test collection)."""
    import inngest as inngest_sdk  # noqa: PLC0415 — pip SDK (module-level Trigger* classes)

    from inngest_app.client import inngest_client  # noqa: PLC0415

    if inngest_client is None:
        raise RuntimeError("inngest pip SDK not available — client is None")

    from api.lib.db import get_db  # noqa: PLC0415
    from api.services.analysis_service import run_stock_analysis  # noqa: PLC0415
    from api.services.market_context_service import MarketContextService  # noqa: PLC0415
    from api.services.weekly_signal_service import WeeklySignalService  # noqa: PLC0415
    from research_swarm.data.escalation import (  # noqa: PLC0415
        EscalationCandidate,
        EscalationContext,
        select_escalations,
    )
    from research_swarm.data.market_data_client import MarketDataClient  # noqa: PLC0415
    from research_swarm.data.openinsider_client import OpenInsiderClient  # noqa: PLC0415
    from research_swarm.data.screener import StockScreener  # noqa: PLC0415

    @inngest_client.create_function(
        fn_id="weekly-batch",
        trigger=inngest_sdk.TriggerCron(cron="0 3 * * 1"),  # Monday 03:00 UTC = Sunday 11 PM ET
        name="Weekly Batch Analysis (Tiered)",
        retries=1,
    )
    async def weekly_batch(ctx: "inngest_sdk.Context") -> Dict[str, Any]:
        step = ctx.step  # steps live on ctx in the current SDK

        run_date = datetime.now(timezone.utc).replace(
            hour=0, minute=0, second=0, microsecond=0
        )

        # ── Step 1: latest market outlook → favored sectors ─────────────────
        async def load_outlook() -> Dict[str, Any]:
            db = await get_db()
            outlook = await db.marketoutlook.find_first(order={"runDate": "desc"})
            if outlook is None:
                logger.warning("No MarketOutlook row — outlook trigger disabled")
                return {"favored_sectors": [], "outlook_run_date": None}
            age = datetime.now(timezone.utc) - outlook.runDate.replace(
                tzinfo=timezone.utc
            )
            if age > timedelta(days=_OUTLOOK_MAX_AGE_DAYS):
                logger.warning(
                    "MarketOutlook is %s old — outlook trigger disabled", age
                )
                return {"favored_sectors": [], "outlook_run_date": None}
            rankings = sorted(
                outlook.sectorRankings, key=lambda r: r["score"], reverse=True
            )
            favored = [r["sector"] for r in rankings[:_TOP_SECTORS]]
            return {
                "favored_sectors": favored,
                "outlook_run_date": outlook.runDate.isoformat(),
            }

        outlook: Dict[str, Any] = await step.run("load-outlook", load_outlook)

        # ── Step 2: screen all 191 names; advance top N ∪ watchlisted ────────
        async def run_screener() -> List[Dict[str, Any]]:
            screener = StockScreener(
                market_client=MarketDataClient(),
                insider_client=OpenInsiderClient(),
            )
            universe = StockScreener.load_universe()
            scored = screener.screen_all(universe)

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

        # ── Step 3: free quant snapshots (tier="quant") ──────────────────────
        async def write_quant_snapshots() -> Dict[str, Any]:
            db = await get_db()
            service = WeeklySignalService(db=db)
            market_client = MarketDataClient()
            market_context = MarketContextService(
                market_client=market_client
            ).get_context()

            priors: Dict[str, Dict[str, Any]] = {}
            stored = failed = 0
            for c in candidates:
                try:
                    prior_ctx = await service.get_prior_context(
                        c["ticker"], before=run_date
                    )
                    priors[c["ticker"]] = prior_ctx
                    await service.store_quant_snapshot(
                        ticker=c["ticker"],
                        run_date=run_date,
                        screener_score=c["score"],
                        current_price=market_client.get_current_price(c["ticker"]),
                        quant_signals={
                            "has_insider_buying": c["has_insider_buying"],
                            "weekly_price_change_pct": c["weekly_price_change_pct"],
                            "days_to_earnings": c["days_to_earnings"],
                            "days_since_earnings": c["days_since_earnings"],
                            "on_watchlist": c["on_watchlist"],
                        },
                        market_context=market_context,
                        prior_ctx=prior_ctx,
                    )
                    stored += 1
                except Exception as e:
                    logger.error("Quant snapshot failed for %s: %s", c["ticker"], e)
                    failed += 1
            return {"stored": stored, "failed": failed, "priors": priors}

        quant: Dict[str, Any] = await step.run(
            "quant-snapshots", write_quant_snapshots
        )

        # ── Step 4: weighted escalation (free) ───────────────────────────────
        async def compute_escalation() -> List[Dict[str, Any]]:
            db = await get_db()
            service = WeeklySignalService(db=db)
            context = EscalationContext(
                favored_sectors=frozenset(outlook["favored_sectors"])
            )
            escalation_candidates = []
            for c in candidates:
                prior = quant["priors"].get(c["ticker"], {})
                fresh = await service.find_fresh_result(
                    c["ticker"], max_age_days=_FRESH_REPORT_MAX_AGE_DAYS
                )
                escalation_candidates.append(
                    EscalationCandidate(
                        ticker=c["ticker"],
                        screener_score=c["score"],
                        sector=c.get("sector"),
                        prior_screener_score=prior.get("prior_screener_score"),
                        prior_verdict=prior.get("prior_verdict"),
                        days_since_earnings=c.get("days_since_earnings"),
                        on_watchlist=c.get("on_watchlist", False),
                        has_fresh_report=fresh is not None,
                    )
                )
            decisions = select_escalations(
                escalation_candidates,
                context,
                cap=_MAX_SWARM_RUNS,
                threshold=_ESCALATION_THRESHOLD,
            )
            for d in decisions:
                await service.record_escalation(
                    ticker=d.ticker, run_date=run_date,
                    score=d.score, reasons=d.reasons,
                )
            logger.info(
                "Escalation: %d swarm, %d reuse, %d hold",
                sum(1 for d in decisions if d.action == "swarm"),
                sum(1 for d in decisions if d.action == "reuse"),
                sum(1 for d in decisions if d.action == "hold"),
            )
            return [
                {"ticker": d.ticker, "score": d.score,
                 "reasons": d.reasons, "action": d.action}
                for d in decisions
            ]

        decisions: List[Dict[str, Any]] = await step.run(
            "compute-escalation", compute_escalation
        )

        reuse_list = [d for d in decisions if d["action"] == "reuse"]
        swarm_list = [d for d in decisions if d["action"] == "swarm"]
        outcomes: Dict[str, str] = {}

        # ── Steps 5a: zero-cost reuse of fresh user reports ──────────────────
        for d in reuse_list:
            async def reuse_one(dd: Dict[str, Any] = d) -> str:
                db = await get_db()
                service = WeeklySignalService(db=db)
                result = await service.find_fresh_result(
                    dd["ticker"], max_age_days=_FRESH_REPORT_MAX_AGE_DAYS
                )
                if result is None:  # report aged out / vanished — stay quant
                    return "reuse_missing"
                ok = await service.upgrade_to_full(
                    ticker=dd["ticker"], run_date=run_date, result=result,
                    escalation_score=dd["score"],
                    escalation_reasons=dd["reasons"],
                )
                return "reused" if ok else "reuse_unusable"

            outcomes[d["ticker"]] = await step.run(
                f"reuse-{d['ticker'].lower()}", reuse_one
            )

        # ── Steps 5b: paid swarm analyses (the ONLY paid stage) ──────────────
        if swarm_list:
            batch_user_id = _get_batch_user_id()
            for d in swarm_list:
                async def analyze_one(dd: Dict[str, Any] = d) -> str:
                    logger.info("Batch analyzing %s", dd["ticker"])
                    result = await run_stock_analysis(
                        ticker=dd["ticker"],
                        quarters=_QUARTERS,
                        news_days_back=_NEWS_DAYS_BACK,
                        user_id=batch_user_id,
                    )
                    db = await get_db()
                    service = WeeklySignalService(db=db)
                    ok = await service.upgrade_to_full(
                        ticker=dd["ticker"], run_date=run_date, result=result,
                        escalation_score=dd["score"],
                        escalation_reasons=dd["reasons"],
                    )
                    return "full" if ok else "analysis_failed"

                outcomes[d["ticker"]] = await step.run(
                    f"analyze-{d['ticker'].lower()}", analyze_one
                )

        # ── Final step: fire batch/completed for (dormant) downstream fns ────
        async def fire_batch_event() -> None:
            await step.send_event("batch-completed-event", {
                "name": "batch/completed",
                "data": {
                    "run_date": run_date.isoformat(),
                    "ticker_count": sum(
                        1 for v in outcomes.values() if v in ("full", "reused")
                    ),
                },
            })

        await step.run("fire-batch-completed", fire_batch_event)

        return {
            "status": "completed",
            "run_date": run_date.isoformat(),
            "candidates": len(candidates),
            "quant_stored": quant["stored"],
            "quant_failed": quant["failed"],
            "swarm": len(swarm_list),
            "reused": len(reuse_list),
            "outcomes": outcomes,
        }

    return weekly_batch


try:
    weekly_batch = _register_inngest_function()
except Exception:
    # inngest pip package not available (e.g. during unit tests) — no-op.
    weekly_batch = None  # type: ignore[assignment]
```

- [ ] **Step 4: Register it**

In `inngest_app/index.py`:

(a) Uncomment/replace the dormant import block so it reads:

```python
from inngest_app.functions.weekly_batch import weekly_batch
from inngest_app.functions.weekly_outlook import weekly_market_outlook

# Dormant roster — intentionally NOT registered (need real batch data first):
# from inngest_app.functions.send_teaser_digest import send_teaser_digest
# from inngest_app.functions.send_watchlist_alerts import send_watchlist_alerts
# from inngest_app.functions.analyze_stock import analyze_stock
```

(b) Update the registry:

```python
ACTIVE_FUNCTIONS = [
    fn for fn in [weekly_market_outlook, weekly_batch] if fn is not None
]
```

(c) Update the module docstring's "register ONLY weekly_market_outlook" sentence to say the tiered `weekly_batch` is now registered too (2026-07-08 tiered-batch plan).

- [ ] **Step 5: Run the registration tests and the full suite**

Run: `python3 -m pytest tests/test_weekly_batch_registration.py tests/test_inngest_mount.py -v`
Expected: PASS (third test passes in both venv states).

Run: `python3 -m pytest tests/ -x -q`
Expected: full suite PASSES.

- [ ] **Step 6: Commit**

```bash
git add inngest_app/functions/weekly_batch.py inngest_app/index.py tests/test_weekly_batch_registration.py
git commit -m "feat(batch): tiered weekly batch — screener, quant tier, capped escalation"
```

---

### Task 7: Downstream surfaces filter to tier="full"

**Files:**
- Modify: `api/routes/weekly_signals.py` (4 queries: ~lines 120, 135, 163, 199)
- Modify: `api/services/alert_delivery_service.py` (~line 49)
- Test: `tests/test_weekly_signals_route.py`, `tests/test_alert_delivery_service.py` (existing — fix if broken)

**Interfaces:**
- Consumes: WeeklySignal `tier` column (Task 1).
- Produces: leaderboard, track record, preview, and alert delivery only ever see full-analysis rows.

- [ ] **Step 1: Add the filters**

In `api/routes/weekly_signals.py`:

```python
# leaderboard — latest run lookup (~line 120):
latest = await db.weeklysignal.find_first(
    where={"tier": "full"}, order={"runDate": "desc"}
)

# leaderboard — rows (~line 135): add "tier": "full" to the existing where:
where={"runDate": run_date, "tier": "full"},

# track record (~line 163): add a where clause:
signals = await db.weeklysignal.find_many(
    where={"tier": "full"},
    order={"runDate": "desc"},
    take=limit,
)

# preview (~line 199): add "tier": "full" to the existing where:
where={"ticker": ticker.upper(), "tier": "full"},
```

In `api/services/alert_delivery_service.py` (~line 49), add `"tier": "full"`:

```python
    signals = await db.weeklysignal.find_many(
        where={"runDate": run_date, "tier": "full"},
    )
```

- [ ] **Step 2: Run the affected suites**

Run: `python3 -m pytest tests/test_weekly_signals_route.py tests/test_alert_delivery_service.py -v`
Expected: PASS. If a test asserts on exact `where` kwargs, update the expected dict to include `"tier": "full"` — the behavioral intent (quant rows invisible downstream) is the new correct expectation.

- [ ] **Step 3: Commit**

```bash
git add api/routes/weekly_signals.py api/services/alert_delivery_service.py tests/
git commit -m "feat(signals): downstream surfaces only see tier=full rows"
```

---

### Task 8: Merge, migrate, deploy, production smoke

**Files:** none new — operational task.

**Interfaces:**
- Consumes: everything above, Railway service `web` in project `shimmering-liberation`, Inngest app `research-swarm`.

- [ ] **Step 1: Full local suite green**

Run: `python3 -m pytest tests/ -q`
Expected: ALL PASS.

- [ ] **Step 2: Open and merge the PR**

```bash
git push -u origin tiered-batch
gh pr create --title "Tiered weekly batch: quant tier + capped escalation" \
  --body "Implements docs/superpowers/specs/2026-07-08-tiered-batch-design.md — screener over 191 names, free tier=quant WeeklySignal rows for top 20 ∪ watchlist, weighted escalation (cap 5, threshold 2.0), fresh-report reuse, tier=full upgrades. Downstream surfaces filter tier=full.

🤖 Generated with [Claude Code](https://claude.com/claude-code)"
```

Wait for user review/merge (or merge if pre-authorized), then `git checkout main && git pull`.

- [ ] **Step 3: Verify production env vars**

```bash
railway link --project shimmering-liberation --environment production --service web
railway variables --service web | grep -E "BATCH_SYSTEM_USER_ID|DATABASE_URL|INNGEST"
```

Expected: `BATCH_SYSTEM_USER_ID` present (the batch raises without it — set it to the admin user's UUID if missing), `INNGEST_SIGNING_KEY` present.

- [ ] **Step 4: Apply the migration to production**

With the production `DATABASE_URL` exported (pull via `railway variables`):

```bash
DATABASE_URL="<prod url>" python3 -m prisma migrate deploy --schema=db/schema.prisma
```

Expected: `1 migration applied: 20260709000000_add_weekly_signal_tier`. (Remember: `migrate dev` must NOT be used.)

- [ ] **Step 5: Confirm Railway deploy mounts both functions**

After Railway auto-deploys main:

```bash
railway logs --service web | grep -i inngest | tail -5
```

Expected: handler mounted at `/api/inngest` with **2** functions. Then in the Inngest dashboard (app `research-swarm`), re-sync the app and confirm `weekly-batch` appears alongside `weekly-market-outlook`.

- [ ] **Step 6: Manual smoke run**

Invoke `weekly-batch` from the Inngest dashboard. After it completes, verify against the production DB:

```sql
-- expect ~20 quant + ≤5 full for today's run_date
SELECT tier, COUNT(*) FROM weekly_signals
WHERE "runDate" >= NOW() - INTERVAL '1 day' GROUP BY tier;

-- audit trail sanity: reasons present on scored rows
SELECT ticker, tier, "escalationScore", "escalationReasons"
FROM weekly_signals WHERE "runDate" >= NOW() - INTERVAL '1 day'
ORDER BY "escalationScore" DESC NULLS LAST LIMIT 10;

-- spend check: swarm cost for the run window under $3
SELECT COALESCE(SUM(cost_usd), 0) FROM stock_results
WHERE created_at >= NOW() - INTERVAL '2 hours';
```

Expected: quant+full row counts as designed; escalation reasons look sane; total cost < $3. Also confirm `GET /api/weekly-signals/leaderboard` returns only rows with verdicts.

- [ ] **Step 7: Update memory**

Update `/Users/tui/.claude/projects/-Users-tui-dvrg/memory/autopilot-execution-layer.md`: tiered batch is live (2 active Inngest functions); digest/alerts remain dormant pending their own plans.
