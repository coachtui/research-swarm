# Entry-Mechanics Experiments Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add weekly-requote and capitulation-valve entry mechanics as opt-in harness flags to the Tier 2 backtest, race them (alone, plus `OUTCOMPETE_MARGIN 8`, plus combined) against the base run, and re-render the pre-committed gate for the combined config.

**Architecture:** Two booleans on `BacktestConfig` gate all new simulator behavior (flags off ⇒ behavior unchanged); constants (`PATIENT_LIMIT_TTL_WEEKS 1`, `OUTCOMPETE_MARGIN 8`) are injected per-run with the existing `patched` context manager. A new `execution/backtest/experiments.py` orchestrates the race and the recentred sweep; a new `experiments` CLI subcommand runs it end to end.

**Tech Stack:** Python 3, pandas, pytest. No new dependencies.

## Global Constraints

- Backtest-only: no file under `execution/funnel/`, `execution/constants.py`, or `inngest_app/` may be modified.
- Flags-off behavior identical: the existing test suite must pass untouched.
- Gate criteria are the parent spec's, verbatim — rendered by the existing `gate_verdict`/`render_report`, never reimplemented.
- Journal reasons introduced: `requote` (cancel), `capitulation_entry` (buy). Existing reasons unchanged.
- Market buys pay 10 bps adverse slippage at next open; limit buys still pay none.
- Spec: `docs/superpowers/specs/2026-07-10-phase3d-entry-mechanics-experiments-design.md`.

---

### Task 1: Market-buy fill price (`fills.py`)

**Files:**
- Modify: `execution/backtest/fills.py`
- Test: `tests/test_backtest_fills.py` (append)

**Interfaces:**
- Produces: `buy_fill_price(day_open: float, slippage_bps: float = 10.0) -> float` — used by Task 3's simulator changes.

- [ ] **Step 1: Write the failing test** — append to `tests/test_backtest_fills.py`:

```python
def test_buy_fill_price_adds_adverse_slippage():
    from execution.backtest.fills import buy_fill_price
    assert buy_fill_price(100.0) == 100.1          # default 10 bps against us
    assert buy_fill_price(100.0, 0.0) == 100.0
    assert buy_fill_price(33.3333, 10.0) == 33.3666
```

- [ ] **Step 2: Run to verify it fails** — `python3 -m pytest tests/test_backtest_fills.py -q` → ImportError on `buy_fill_price`.

- [ ] **Step 3: Implement** — in `execution/backtest/fills.py`, after `sell_fill_price`:

```python
def buy_fill_price(day_open: float, slippage_bps: float = SELL_SLIPPAGE_BPS) -> float:
    """Market buys pay slippage; limit buys don't (the limit is the bound)."""
    return round(day_open * (1.0 + slippage_bps / 10_000.0), 4)
```

- [ ] **Step 4: Run to verify it passes** — same command, all green.
- [ ] **Step 5: Commit** — `git add execution/backtest/fills.py tests/test_backtest_fills.py && git commit -m "feat(backtest): market-buy fill price with adverse slippage"`

---

### Task 2: Config flags + valve helpers (`simulator.py`)

**Files:**
- Modify: `execution/backtest/simulator.py`
- Test: `tests/test_backtest_simulator_variants.py` (create)

**Interfaces:**
- Produces: `BacktestConfig.requote_weekly: bool = False`, `BacktestConfig.capitulation_valve: bool = False`; `valve_armed(miss: Optional[dict], conviction: float) -> bool`; `_record_miss(missed: Dict[str, dict], order: LimitOrder) -> None`. Miss dict shape: `{"count": int, "conviction": float}`.

- [ ] **Step 1: Write the failing tests** — create `tests/test_backtest_simulator_variants.py`:

```python
# tests/test_backtest_simulator_variants.py
"""Entry-mechanics variants (requote / capitulation valve). Synthetic
fixture: one permanently *extended* uptrend whose patient limit never
fills — the exact pathology the 41% missed-fill finding points at."""
import numpy as np
import pandas as pd
import pytest

from execution.backtest.fills import LimitOrder
from execution.backtest.simulator import (
    BacktestConfig, run_backtest, valve_armed, _record_miss,
)


def test_config_flags_default_off():
    cfg = BacktestConfig()
    assert cfg.requote_weekly is False
    assert cfg.capitulation_valve is False


def test_valve_armed_rules():
    assert not valve_armed(None, 60.0)                              # never missed
    assert not valve_armed({"count": 1, "conviction": 60.0}, 60.0)  # one miss only
    assert not valve_armed({"count": 2, "conviction": 61.0}, 60.0)  # conviction dropped
    assert valve_armed({"count": 2, "conviction": 60.0}, 60.0)      # not lower: equal ok
    assert valve_armed({"count": 3, "conviction": 55.0}, 60.0)      # higher ok


def test_record_miss_counts_and_tracks_conviction():
    missed = {}
    order = LimitOrder("XY", 10, 50.0, 1.0,
                       pd.Timestamp("2020-01-06").date(),
                       pd.Timestamp("2020-01-13").date(), conviction=70.0)
    _record_miss(missed, order)
    _record_miss(missed, order)
    assert missed["XY"] == {"count": 2, "conviction": 70.0}
```

- [ ] **Step 2: Run to verify it fails** — `python3 -m pytest tests/test_backtest_simulator_variants.py -q` → ImportError (`valve_armed`).

- [ ] **Step 3: Implement** — in `execution/backtest/simulator.py`:

Add to imports (`typing` already imports `Optional`): nothing new needed.

Extend `BacktestConfig`:

```python
@dataclass
class BacktestConfig:
    start: str = "2015-01-01"
    end: str = "2026-06-30"
    starting_cash: float = 100_000.0
    flat_conviction: Optional[float] = None   # None → screen_score × 10
    slippage_bps: float = 10.0
    requote_weekly: bool = False        # experiment A: weekly fresh limits
    capitulation_valve: bool = False    # experiment B: market entry after 2 misses
```

Add below `_conviction`:

```python
def valve_armed(miss: Optional[dict], conviction: float) -> bool:
    """Two consecutive missed quotes and conviction not lower than the last one."""
    return miss is not None and miss["count"] >= 2 and conviction >= miss["conviction"]


def _record_miss(missed: Dict[str, dict], order: LimitOrder) -> None:
    m = missed.setdefault(order.symbol, {"count": 0, "conviction": 0.0})
    m["count"] += 1
    m["conviction"] = order.conviction
```

- [ ] **Step 4: Run to verify it passes** — same command, 3 tests green. Also `python3 -m pytest tests/test_backtest_simulator.py -q` (untouched suite still green).
- [ ] **Step 5: Commit** — `git add execution/backtest/simulator.py tests/test_backtest_simulator_variants.py && git commit -m "feat(backtest): variant config flags and valve arming helpers"`

---

### Task 3: Requote + valve mechanics in the event loop (`simulator.py`)

**Files:**
- Modify: `execution/backtest/simulator.py` (`run_backtest` and `_weekly`)
- Test: `tests/test_backtest_simulator_variants.py` (append)

**Interfaces:**
- Consumes: `buy_fill_price` (Task 1), flags/helpers (Task 2).
- Produces: journal rows `{"side": "cancel", "reason": "requote"}` and `{"side": "buy", "reason": "capitulation_entry"}`; `_weekly` gains `market_buys: List[dict]` and `missed: Dict[str, dict]` params (market-buy dict shape: `{"symbol", "qty", "ref_price", "atr", "conviction"}`).

- [ ] **Step 1: Write the failing tests** — append to `tests/test_backtest_simulator_variants.py`:

```python
def _steep_df(n=260, start="2019-01-01", rate=1.015, p0=20.0, vol=1_000_000):
    """Tight-range 1.5%/day uptrend: price runs ~9 ATR above SMA20, so the
    entry is always 'extended' and the patient limit (price − ATR) sits
    below every subsequent low — the quote can never fill."""
    idx = pd.bdate_range(start, periods=n)
    close = pd.Series(p0 * rate ** np.arange(n), index=idx)
    op = close.shift(1).fillna(close.iloc[0])
    return pd.DataFrame({"Open": op, "High": close * 1.001, "Low": op * 0.999,
                         "Close": close, "Volume": float(vol)}, index=idx)


def _mild_df(n=260, start="2019-01-01", p0=300.0, vol=1_000_000):
    rng = np.random.default_rng(7)
    idx = pd.bdate_range(start, periods=n)
    close = pd.Series(p0 * np.cumprod(1.0004 * (1 + 0.002 * rng.standard_normal(n))),
                      index=idx)
    op = close.shift(1).fillna(close.iloc[0])
    return pd.DataFrame({"Open": op, "High": close * 1.005, "Low": op * 0.995,
                         "Close": close, "Volume": float(vol)}, index=idx)


def _ext_fixture():
    return {"EXTD": _steep_df(), "SPY": _mild_df()}


VCFG = BacktestConfig(start="2019-06-01", end="2019-12-15",
                      starting_cash=100_000.0, flat_conviction=60.0)


def test_extended_quote_never_fills_in_base():
    res = run_backtest(_ext_fixture(), VCFG)
    assert not [j for j in res.journal if j["side"] == "buy"]
    assert [j for j in res.journal if j["reason"] == "missed_fill"]
    assert not [j for j in res.journal if j["reason"] == "requote"]


def test_requote_cancels_and_refreshes_weekly():
    from execution.backtest.sensitivity import patched
    from dataclasses import replace
    cfg = replace(VCFG, requote_weekly=True)
    with patched("execution.funnel.entries", "PATIENT_LIMIT_TTL_WEEKS", 1):
        res = run_backtest(_ext_fixture(), cfg)
    requotes = [j for j in res.journal if j["reason"] == "requote"]
    assert len(requotes) >= 3
    assert all(j["side"] == "cancel" for j in requotes)
    # each fresh quote is struck off the *new* week's (higher) SMA20/ATR:
    # the cancelled limits must ratchet upward with the trend
    limits = [j["price"] for j in requotes if j["symbol"] == "EXTD"]
    assert limits == sorted(limits) and limits[-1] > limits[0]


def test_valve_fires_after_two_misses_at_next_open_plus_slippage():
    from dataclasses import replace
    data = _ext_fixture()
    res = run_backtest(data, replace(VCFG, capitulation_valve=True))
    valve = [j for j in res.journal if j["reason"] == "capitulation_entry"]
    assert valve, "valve never fired"
    first = valve[0]
    misses = [j for j in res.journal if j["reason"] == "missed_fill"
              and j["symbol"] == first["symbol"] and j["date"] < first["date"]]
    assert len(misses) >= 2
    bar = data[first["symbol"]].loc[pd.Timestamp(first["date"])]
    assert first["price"] == pytest.approx(float(bar["Open"]) * 1.001, rel=1e-6)
    # half of the flat-60 band (≈8.4% of equity) minus whole-share rounding
    notional = first["qty"] * first["price"]
    assert 0.02 * VCFG.starting_cash <= notional <= 0.045 * VCFG.starting_cash


def test_combined_requote_misses_arm_the_valve_faster():
    from execution.backtest.sensitivity import patched
    from dataclasses import replace
    cfg = replace(VCFG, requote_weekly=True, capitulation_valve=True)
    with patched("execution.funnel.entries", "PATIENT_LIMIT_TTL_WEEKS", 1):
        res = run_backtest(_ext_fixture(), cfg)
    valve = [j for j in res.journal if j["reason"] == "capitulation_entry"]
    assert valve
    # requote cadence: 2 misses accumulate in ~2 weeks, so the first valve
    # entry lands within 5 weeks of the window start (valve-alone needs ~7)
    assert (valve[0]["date"] - pd.Timestamp(VCFG.start).date()).days <= 35
    # once held, no further quotes: at most one valve entry per symbol
    assert len([j for j in valve if j["symbol"] == "EXTD"]) == 1
```

- [ ] **Step 2: Run to verify the new ones fail** — `python3 -m pytest tests/test_backtest_simulator_variants.py -q`. `test_extended_quote_never_fills_in_base` should already PASS (locks the pathology exists); the requote/valve/combined tests FAIL (no such journal reasons yet). If `test_extended_quote_never_fills_in_base` fails instead, stop and fix the fixture (steeper `rate`, or longer warm-up) until the base run demonstrably strands the quote — the variants are meaningless without the pathology.

- [ ] **Step 3: Implement in `run_backtest`** — replace the state block and daily loop pieces:

After `pending_sells: List[dict] = []` add:

```python
    pending_market_buys: List[dict] = []   # {"symbol","qty","ref_price","atr","conviction"}
    missed: Dict[str, dict] = {}           # symbol → {"count", "conviction"}
```

After the `(a)` queued-sells block (immediately after `pending_sells = still_pending`), insert:

```python
        # (a2) capitulation market buys at the open (+ adverse slippage)
        still_buys: List[dict] = []
        for b in pending_market_buys:
            df = stocks[b["symbol"]]
            if today not in df.index:
                still_buys.append(b)
                continue
            px = buy_fill_price(float(df.at[today, "Open"]), cfg.slippage_bps)
            if b["qty"] * px <= ledger.cash:
                ledger.buy(b["symbol"], b["qty"], px, today.date(),
                           "capitulation_entry", atr=b["atr"])
                last_close[b["symbol"]] = float(df.at[today, "Close"])
            else:
                ledger.journal.append({"date": today.date(), "side": "cancel",
                                       "symbol": b["symbol"], "qty": b["qty"],
                                       "price": px, "reason": "fill_skipped_cash"})
        pending_market_buys = still_buys
```

Import `buy_fill_price` in the existing `from execution.backtest.fills import ...` line.

In the `(b)` expiry branch, after the `missed_fill` journal append (before `continue`):

```python
                if cfg.capitulation_valve:
                    _record_miss(missed, o)
```

In the `(b)` fill branch, right after `ledger.buy(...)`/`last_close[...] = ...`:

```python
                        missed.pop(o.symbol, None)
```

Update the `(c)` weekly call:

```python
            _weekly(today, ohlcv, stocks, spy, ledger, open_orders,
                    pending_sells, pending_market_buys, missed,
                    last_close, cfg, allowed)
```

- [ ] **Step 4: Implement in `_weekly`** — signature becomes:

```python
def _weekly(today, ohlcv, stocks, spy, ledger, open_orders, pending_sells,
            market_buys, missed, last_close, cfg, allowed=None) -> None:
```

After the trims block (after the last `queued.add(t["symbol"])` line) and **before** the `committed = ...` line, insert:

```python
    wanted = set(plan["entry_queue"])
    if cfg.requote_weekly:
        # a still-queued name gets a fresh quote off the new week's screen —
        # cancel the stale order here; the entry loop below re-quotes it
        for o in [o for o in open_orders if o.symbol in wanted]:
            open_orders.remove(o)
            ledger.journal.append({"date": today.date(), "side": "cancel",
                                   "symbol": o.symbol, "qty": o.qty,
                                   "price": o.limit, "reason": "requote"})
            if cfg.capitulation_valve:
                _record_miss(missed, o)
    if cfg.capitulation_valve:
        # a streak is *consecutive* misses: break it when the symbol has no
        # standing quote, no pending valve entry, and no place in the queue
        standing = {o.symbol for o in open_orders} | wanted | {
            b["symbol"] for b in market_buys}
        for sym in [s for s in missed if s not in standing]:
            del missed[sym]
```

Change the `committed`/`ordered` lines to reserve pending valve entries too:

```python
    committed = (sum(o.qty * o.limit for o in open_orders)
                 + sum(b["qty"] * b["ref_price"] for b in market_buys))
    invested = REGIME_INVESTED_FRACTION.get(regime, 0.7)
    deployable = max(0.0, invested * sleeve_equity - position_mv - committed)
    cash_remaining = max(0.0, ledger.cash - committed)
    ordered = {o.symbol for o in open_orders} | {b["symbol"] for b in market_buys}
```

In the entry loop, after `notional = size_entry(...)` and before `qty = int(notional // limit)`, insert:

```python
        if cfg.capitulation_valve and valve_armed(missed.get(sym), conv):
            price = float(row["price"])
            qty = int((notional / 2.0) // price)
            if qty > 0 and qty * price >= MIN_TRADE_NOTIONAL:
                market_buys.append({"symbol": sym, "qty": qty, "ref_price": price,
                                    "atr": float(row["atr"]), "conviction": conv})
                missed.pop(sym, None)
                spent = qty * price
                deployable = max(0.0, deployable - spent)
                cash_remaining = max(0.0, cash_remaining - spent)
                continue
            # half-notional under the trade floor: no valve entry, streak stands
```

- [ ] **Step 5: Run to verify it passes** — `python3 -m pytest tests/test_backtest_simulator_variants.py tests/test_backtest_simulator.py -q` → all green (flags-off suite must be untouched).
- [ ] **Step 6: Full backtest suite** — `python3 -m pytest tests/test_backtest_*.py -q` → all green.
- [ ] **Step 7: Commit** — `git add execution/backtest/simulator.py tests/test_backtest_simulator_variants.py && git commit -m "feat(backtest): weekly-requote and capitulation-valve entry mechanics"`

---

### Task 4: Race driver (`experiments.py`)

**Files:**
- Create: `execution/backtest/experiments.py`
- Test: `tests/test_backtest_experiments.py` (create)

**Interfaces:**
- Consumes: `run_backtest`, `BacktestConfig`, `BacktestResult` (simulator); `patched`, `_row` (sensitivity); `compute_metrics`, `trade_stats` (metrics).
- Produces: `VARIANTS: List[dict]`, `COMBINED_SWEEP_SPECS: List[dict]`, `run_variant(ohlcv, cfg, variant, pit=None, static_universe=None) -> BacktestResult`, `fill_diagnostics(journal) -> dict`, `race_row(name, result, naive_sharpe, starting_cash) -> dict`, `run_combined_sweep(ohlcv, cfg, naive_sharpe, pit=None, static_universe=None) -> List[dict]`.

- [ ] **Step 1: Write the failing tests** — create `tests/test_backtest_experiments.py`:

```python
# tests/test_backtest_experiments.py
"""Race-driver logic on stubs — no full simulations here."""
import importlib

import numpy as np
import pandas as pd

import execution.backtest.experiments as exp
from execution.backtest.simulator import BacktestConfig


def _fake_result(journal=()):
    idx = pd.bdate_range("2020-01-01", periods=300)

    class R:
        equity = pd.Series(100_000 * 1.0005 ** np.arange(300), index=idx)
        journal = list(journal)
        weeks = 60
    return R()


def test_variants_cover_the_owner_approved_matrix():
    names = [v["name"] for v in exp.VARIANTS]
    assert names == ["requote", "valve", "margin8", "combined"]
    combined = exp.VARIANTS[-1]
    assert combined["cfg"] == {"requote_weekly": True, "capitulation_valve": True}
    assert (exp.ENTRIES, "PATIENT_LIMIT_TTL_WEEKS", 1) in combined["patches"]
    assert (exp.DECISIONS, "OUTCOMPETE_MARGIN", 8.0) in combined["patches"]


def test_combined_sweep_recentred_on_margin_8():
    spec = next(s for s in exp.COMBINED_SWEEP_SPECS
                if s["name"] == "outcompete_margin")
    assert spec["values"] == [6.4, 9.6]          # ±20% of 8, not of 10
    assert {s["name"] for s in exp.COMBINED_SWEEP_SPECS} == {
        "stop_mult", "extension_limit", "outcompete_margin", "entry_band"}


def test_run_variant_applies_flags_and_patches(monkeypatch):
    seen = {}

    def spy_run(ohlcv, cfg, **kw):
        entries = importlib.import_module(exp.ENTRIES)
        decisions = importlib.import_module(exp.DECISIONS)
        seen.update(requote=cfg.requote_weekly, valve=cfg.capitulation_valve,
                    ttl=entries.PATIENT_LIMIT_TTL_WEEKS,
                    margin=decisions.OUTCOMPETE_MARGIN)
        return _fake_result()
    monkeypatch.setattr(exp, "run_backtest", spy_run)

    combined = next(v for v in exp.VARIANTS if v["name"] == "combined")
    exp.run_variant({}, BacktestConfig(), combined)
    assert seen == {"requote": True, "valve": True, "ttl": 1, "margin": 8.0}
    # and everything restored afterwards
    assert importlib.import_module(exp.ENTRIES).PATIENT_LIMIT_TTL_WEEKS == 2
    assert importlib.import_module(exp.DECISIONS).OUTCOMPETE_MARGIN == 10.0


def test_run_combined_sweep_keeps_flags_on_and_yields_nine_rows(monkeypatch):
    calls = []

    def spy_run(ohlcv, cfg, **kw):
        decisions = importlib.import_module(exp.DECISIONS)
        calls.append((cfg.requote_weekly, cfg.capitulation_valve,
                      cfg.flat_conviction, decisions.OUTCOMPETE_MARGIN))
        return _fake_result()
    monkeypatch.setattr(exp, "run_backtest", spy_run)

    rows = exp.run_combined_sweep({}, BacktestConfig(), naive_sharpe=0.5)
    assert len(rows) == 9                       # 4 specs × 2 + flat-60
    assert rows[-1]["name"] == "flat_conviction_60"
    assert all(c[0] and c[1] for c in calls)    # every run carries both flags
    assert calls[-1][2] == 60.0                 # flat-60 run
    margins = {c[3] for c in calls}
    assert margins == {6.4, 9.6, 8.0}           # 8 except when itself swept


def _journal():
    d = pd.Timestamp("2020-02-03").date()
    return ([{"date": d, "side": "buy", "symbol": "A", "qty": 1, "price": 10.0,
              "reason": "entry_fill"}] * 3
            + [{"date": d, "side": "buy", "symbol": "B", "qty": 1, "price": 10.0,
                "reason": "capitulation_entry"}]
            + [{"date": d, "side": "cancel", "symbol": "C", "qty": 1, "price": 10.0,
                "reason": "missed_fill"}] * 2
            + [{"date": d, "side": "cancel", "symbol": "D", "qty": 1, "price": 10.0,
                "reason": "requote"}] * 5
            + [{"date": d, "side": "sell", "symbol": "A", "qty": 1, "price": 11.0,
                "reason": "trailing_stop"}])


def test_fill_diagnostics_counts_terminal_outcomes():
    d = exp.fill_diagnostics(_journal())
    assert d == {"entry_fills": 3, "valve_entries": 1, "missed_fill_cancels": 2,
                 "requote_cancels": 5, "missed_fill_rate": round(2 / 6, 4)}


def test_race_row_shape():
    r = exp.race_row("combined", _fake_result(_journal()), naive_sharpe=0.5,
                     starting_cash=100_000.0)
    for key in ("name", "cagr", "max_drawdown", "sharpe", "mar", "sharpe_edge",
                "entry_fills", "valve_entries", "missed_fill_cancels",
                "requote_cancels", "missed_fill_rate", "avg_exposure",
                "yearly_returns"):
        assert key in r
    assert r["name"] == "combined"
    assert r["sharpe_edge"] == r["sharpe"] - 0.5
```

- [ ] **Step 2: Run to verify it fails** — `python3 -m pytest tests/test_backtest_experiments.py -q` → ModuleNotFoundError.

- [ ] **Step 3: Implement** — create `execution/backtest/experiments.py`:

```python
"""Entry-mechanics experiment race (Phase 3D follow-up spec). Variants are
harness flags plus patched constants — production code untouched. Base and
naive momentum re-run in-process so every race row shares one code path;
the combined config gets the full pre-committed gate, with the ±20% sweep
recentred on its active constants."""
from contextlib import ExitStack
from dataclasses import replace
from typing import Dict, List

from execution.backtest.metrics import compute_metrics, trade_stats
from execution.backtest.sensitivity import _row, patched
from execution.backtest.simulator import BacktestConfig, BacktestResult, run_backtest

ENTRIES = "execution.funnel.entries"
DECISIONS = "execution.funnel.decisions"

VARIANTS: List[dict] = [
    {"name": "requote", "cfg": {"requote_weekly": True},
     "patches": [(ENTRIES, "PATIENT_LIMIT_TTL_WEEKS", 1)]},
    {"name": "valve", "cfg": {"capitulation_valve": True}, "patches": []},
    {"name": "margin8", "cfg": {},
     "patches": [(DECISIONS, "OUTCOMPETE_MARGIN", 8.0)]},
    {"name": "combined",
     "cfg": {"requote_weekly": True, "capitulation_valve": True},
     "patches": [(ENTRIES, "PATIENT_LIMIT_TTL_WEEKS", 1),
                 (DECISIONS, "OUTCOMPETE_MARGIN", 8.0)]},
]

# sensitivity.SWEEP_SPECS recentred on the combined config: ±20% of the
# *active* values, so outcompete sweeps 6.4/9.6 around 8 (stop 2.5 and
# extension 1.5 are unchanged by the variants; their ±20% stays 2.0/3.0
# and 1.2/1.8).
COMBINED_SWEEP_SPECS: List[dict] = [
    {"name": "stop_mult", "module": "inngest_app.functions.execution_daily",
     "attr": "TRAILING_STOP_ATR_MULT", "values": [2.0, 3.0]},
    {"name": "extension_limit", "module": ENTRIES,
     "attr": "EXTENSION_ATR_LIMIT", "values": [1.2, 1.8]},
    {"name": "outcompete_margin", "module": DECISIONS,
     "attr": "OUTCOMPETE_MARGIN", "values": [6.4, 9.6]},
    {"name": "entry_band", "module": ENTRIES,
     "attr": ("ENTRY_WEIGHT_MIN", "ENTRY_WEIGHT_MAX"),
     "values": [(0.024, 0.096), (0.036, 0.144)]},
]


def run_variant(ohlcv, cfg: BacktestConfig, variant: dict,
                pit=None, static_universe=None) -> BacktestResult:
    vcfg = replace(cfg, **variant["cfg"])
    with ExitStack() as stack:
        for mod, attr, val in variant["patches"]:
            stack.enter_context(patched(mod, attr, val))
        return run_backtest(ohlcv, vcfg, pit=pit, static_universe=static_universe)


def fill_diagnostics(journal: List[dict]) -> Dict:
    """Missed-fill rate over *terminal* quote outcomes: a requote chain ends
    in either a fill (limit or valve) or one final missed_fill, so requote
    cancels are reported but excluded from the denominator."""
    fills = sum(1 for j in journal
                if j["side"] == "buy" and j["reason"] == "entry_fill")
    valve = sum(1 for j in journal
                if j["side"] == "buy" and j["reason"] == "capitulation_entry")
    missed = sum(1 for j in journal
                 if j["side"] == "cancel" and j["reason"] == "missed_fill")
    requotes = sum(1 for j in journal
                   if j["side"] == "cancel" and j["reason"] == "requote")
    terminal = fills + valve + missed
    return {"entry_fills": fills, "valve_entries": valve,
            "missed_fill_cancels": missed, "requote_cancels": requotes,
            "missed_fill_rate": round(missed / terminal, 4) if terminal else None}


def race_row(name: str, result: BacktestResult, naive_sharpe: float,
             starting_cash: float) -> dict:
    m = compute_metrics(result.equity)
    stats = trade_stats(result.journal, result.equity, starting_cash)
    return {"name": name, "cagr": m["cagr"], "max_drawdown": m["max_drawdown"],
            "sharpe": m["sharpe"], "mar": m["mar"],
            "sharpe_edge": m["sharpe"] - naive_sharpe,
            **fill_diagnostics(result.journal),
            "avg_exposure": stats["avg_exposure"],
            "yearly_returns": m["yearly_returns"]}


def run_combined_sweep(ohlcv, cfg: BacktestConfig, naive_sharpe: float,
                       pit=None, static_universe=None) -> List[dict]:
    combined = next(v for v in VARIANTS if v["name"] == "combined")
    ccfg = replace(cfg, **combined["cfg"])
    rows: List[dict] = []
    for spec in COMBINED_SWEEP_SPECS:
        for value in spec["values"]:
            with ExitStack() as stack:
                for mod, attr, val in combined["patches"]:
                    stack.enter_context(patched(mod, attr, val))
                stack.enter_context(patched(spec["module"], spec["attr"], value))
                result = run_backtest(ohlcv, ccfg, pit=pit,
                                      static_universe=static_universe)
            rows.append(_row(spec["name"], value, result.equity, naive_sharpe))
    with ExitStack() as stack:
        for mod, attr, val in combined["patches"]:
            stack.enter_context(patched(mod, attr, val))
        flat = run_backtest(ohlcv, replace(ccfg, flat_conviction=60.0),
                            pit=pit, static_universe=static_universe)
    rows.append(_row("flat_conviction_60", 60.0, flat.equity, naive_sharpe))
    return rows
```

- [ ] **Step 4: Run to verify it passes** — `python3 -m pytest tests/test_backtest_experiments.py -q` → green.
- [ ] **Step 5: Commit** — `git add execution/backtest/experiments.py tests/test_backtest_experiments.py && git commit -m "feat(backtest): experiment race driver with recentred combined sweep"`

---

### Task 5: Race report rendering (`report.py`)

**Files:**
- Modify: `execution/backtest/report.py`
- Test: `tests/test_backtest_report.py` (append)

**Interfaces:**
- Consumes: race rows (Task 4 `race_row` shape).
- Produces: `render_experiments_report(run_meta: dict, race_rows: List[dict], gate_md: str) -> str`.

- [ ] **Step 1: Write the failing test** — append to `tests/test_backtest_report.py`:

```python
def test_render_experiments_report_race_table_and_embedded_gate():
    from execution.backtest.report import render_experiments_report
    row = {"name": "combined", "cagr": 0.13, "max_drawdown": -0.16,
           "sharpe": 1.05, "mar": 0.8, "sharpe_edge": 0.28,
           "entry_fills": 900, "valve_entries": 40, "missed_fill_cancels": 200,
           "requote_cancels": 800, "missed_fill_rate": 0.1754,
           "avg_exposure": 0.51, "yearly_returns": {"2020": 0.2}}
    md = render_experiments_report({"window": "w"}, [row], "GATE-SECTION")
    assert "Entry-Mechanics Experiments" in md
    assert "| combined | +13.00% | -16.00% | 1.05 | 0.80 | +0.28 " in md
    assert "| 900 | 40 | 200 | 800 | 17.5% | 0.51 |" in md
    assert md.rstrip().endswith("GATE-SECTION")
    assert "backtest-only" in md.lower()
```

- [ ] **Step 2: Run to verify it fails** — `python3 -m pytest tests/test_backtest_report.py -q` → ImportError.

- [ ] **Step 3: Implement** — append to `execution/backtest/report.py`:

```python
SCOPE_LOCK = ("> **Scope lock:** backtest-only. No production funnel or "
              "live-engine change follows from this report regardless of "
              "the verdict; promotion is a separate owner decision.")


def render_experiments_report(run_meta: dict, race_rows: List[dict],
                              gate_md: str) -> str:
    lines = ["# Sleeve A Tier 2 Backtest — Entry-Mechanics Experiments", ""]
    lines += [f"- **{k}:** {v}" for k, v in run_meta.items()]
    lines += ["", SCOPE_LOCK, "", DISCLAIMER, "", "## Race", "",
              "| variant | CAGR | maxDD | Sharpe | MAR | edge vs naive "
              "| fills | valve | missed | requotes | missed rate | exposure |",
              "|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for r in race_rows:
        rate = (f"{r['missed_fill_rate']:.1%}"
                if r["missed_fill_rate"] is not None else "n/a")
        lines.append(
            f"| {r['name']} | {r['cagr']:+.2%} | {r['max_drawdown']:.2%} "
            f"| {r['sharpe']:.2f} | {r['mar']:.2f} | {r['sharpe_edge']:+.2f} "
            f"| {r['entry_fills']} | {r['valve_entries']} "
            f"| {r['missed_fill_cancels']} | {r['requote_cancels']} "
            f"| {rate} | {r['avg_exposure']} |")
    lines += ["", "## Combined-config gate "
              "(pre-committed criteria, sweep recentred on the combined constants)",
              "", gate_md]
    return "\n".join(lines) + "\n"
```

- [ ] **Step 4: Run to verify it passes** — `python3 -m pytest tests/test_backtest_report.py -q` → green. Adjust the test's expected substrings only if a formatting assumption (not the content) was wrong.
- [ ] **Step 5: Commit** — `git add execution/backtest/report.py tests/test_backtest_report.py && git commit -m "feat(backtest): experiments race report renderer"`

---

### Task 6: CLI `experiments` subcommand + spec wording fix

**Files:**
- Modify: `scripts/backtest_sleeve_a.py`
- Modify: `docs/superpowers/specs/2026-07-10-phase3d-entry-mechanics-experiments-design.md`
- Test: `tests/test_backtest_cli.py` (append)

**Interfaces:**
- Consumes: everything from Tasks 4–5, plus existing `_load_all`, `naive_momentum`, `equal_weight_universe`, `spy_buy_hold`, `gate_verdict`, `render_report`, `yearly_log_outperformance`.
- Produces: `python3 scripts/backtest_sleeve_a.py experiments` → `reports/backtests/<ts>-experiments/experiments.md` + `experiments.json` + `trades_<variant>.csv` per run; `_check_base_integrity(base_m: dict) -> Optional[bool]`.

- [ ] **Step 1: Write the failing tests** — append to `tests/test_backtest_cli.py` (follow that file's existing import/monkeypatch style — read it first):

```python
def test_parser_accepts_experiments_subcommand():
    from scripts.backtest_sleeve_a import build_parser
    ns = build_parser().parse_args(["experiments"])
    assert ns.command == "experiments"
    assert ns.start == "2015-01-01"


def test_check_base_integrity(tmp_path, capsys, monkeypatch):
    import json
    import scripts.backtest_sleeve_a as cli
    ref = tmp_path / "metrics.json"
    ref.write_text(json.dumps(
        {"base": {"cagr": 0.12, "sharpe": 0.95, "max_drawdown": -0.166}}))
    ok = cli._check_base_integrity(
        {"cagr": 0.12, "sharpe": 0.95, "max_drawdown": -0.166}, reference=ref)
    assert ok is True
    ok = cli._check_base_integrity(
        {"cagr": 0.12, "sharpe": 0.90, "max_drawdown": -0.166}, reference=ref)
    assert ok is False
    assert "MISMATCH" in capsys.readouterr().out
    assert cli._check_base_integrity({"cagr": 0.1, "sharpe": 1.0,
                                      "max_drawdown": -0.1},
                                     reference=tmp_path / "absent.json") is None
```

- [ ] **Step 2: Run to verify it fails** — `python3 -m pytest tests/test_backtest_cli.py -q` → FAIL (unknown subcommand / missing `_check_base_integrity`).

- [ ] **Step 3: Implement** — in `scripts/backtest_sleeve_a.py`:

Add imports:

```python
import json

from execution.backtest.experiments import (              # noqa: E402
    VARIANTS, race_row, run_combined_sweep, run_variant,
)
from execution.backtest.report import render_experiments_report  # noqa: E402
```

(merge into the existing import blocks; `render_experiments_report` joins the existing `report` import line).

Update the docstring's command list and `build_parser`'s loop: `for name in ("fetch", "run", "sweep", "experiments"):`.

Add before `cmd_run`:

```python
REFERENCE_RUN = REPORTS_DIR / "20260710-115422" / "metrics.json"


def _check_base_integrity(base_m: dict, reference: Path = REFERENCE_RUN):
    """The race re-runs base in-process; if it no longer reproduces the
    committed 2026-07-10 gate run, say so loudly (code drift on the base
    path) but keep going — the race stays internally consistent."""
    if not reference.exists():
        print("base integrity: no reference run to compare against")
        return None
    ref = json.loads(reference.read_text())["base"]
    ok = all(abs(base_m[k] - ref[k]) < 1e-9
             for k in ("cagr", "sharpe", "max_drawdown"))
    print(f"base integrity vs {reference.parent.name}: "
          + ("MATCH" if ok else
             f"MISMATCH — sharpe {base_m['sharpe']:.4f} vs ref {ref['sharpe']:.4f}"))
    return ok


def cmd_experiments(ns) -> None:
    ohlcv, cfg, pit, static = _load_all(ns)
    print(f"universe: {len(ohlcv)} symbols; entry-mechanics race "
          f"(6 runs + 9-run combined sweep)…")
    base_res = run_backtest(ohlcv, cfg, pit=pit, static_universe=static)
    base_m = compute_metrics(base_res.equity)
    integrity = _check_base_integrity(base_m)
    print("base done; naive momentum…")
    naive_eq = naive_momentum(ohlcv, cfg, pit=pit, static_universe=static)
    naive_m = compute_metrics(naive_eq)
    rows = [race_row("base", base_res, naive_m["sharpe"], cfg.starting_cash)]
    results = {"base": base_res}
    for variant in VARIANTS:
        print(f"variant: {variant['name']}…")
        res = run_variant(ohlcv, cfg, variant, pit=pit, static_universe=static)
        results[variant["name"]] = res
        rows.append(race_row(variant["name"], res, naive_m["sharpe"],
                             cfg.starting_cash))
    print("combined-config sensitivity sweep (9 runs)…")
    sweep_rows = run_combined_sweep(ohlcv, cfg, naive_m["sharpe"],
                                    pit=pit, static_universe=static)

    combined_res = results["combined"]
    combined_m = compute_metrics(combined_res.equity)
    yearly = yearly_log_outperformance(combined_res.equity, naive_eq)
    edges = [r["sharpe_edge"] for r in sweep_rows
             if r["name"] != "flat_conviction_60"]
    verdict = gate_verdict(combined_m, naive_m, yearly, edges)
    baselines = {
        "naive_momentum": naive_m,
        "equal_weight": compute_metrics(
            equal_weight_universe(ohlcv, cfg, pit=pit, static_universe=static)),
        "spy": compute_metrics(spy_buy_hold(ohlcv, cfg)),
    }
    gate_meta = {"config": "combined — requote (TTL 1w) + capitulation valve "
                 "+ OUTCOMPETE_MARGIN 8",
                 "window": f"{cfg.start} → {cfg.end}",
                 **trade_stats(combined_res.journal, combined_res.equity,
                               cfg.starting_cash)}
    gate_md = render_report(gate_meta, combined_m, baselines, yearly,
                            sweep_rows, verdict)

    meta = {"window": f"{cfg.start} → {cfg.end}",
            "starting_cash": cfg.starting_cash, "symbols": len(ohlcv),
            "base_matches_20260710-115422": integrity,
            "spec": "docs/superpowers/specs/"
                    "2026-07-10-phase3d-entry-mechanics-experiments-design.md"}
    md = render_experiments_report(meta, rows, gate_md)
    out = REPORTS_DIR / (datetime.now().strftime("%Y%m%d-%H%M%S") + "-experiments")
    out.mkdir(parents=True, exist_ok=True)
    (out / "experiments.md").write_text(md)
    (out / "experiments.json").write_text(json.dumps(
        {"meta": meta, "race": rows, "combined_gate": {
            "metrics": combined_m, "baselines": baselines,
            "yearly_log_outperformance": yearly, "sweep": sweep_rows,
            "verdict": verdict}}, indent=2, default=str))
    import pandas as pd
    for name, res in results.items():
        pd.DataFrame(res.journal).to_csv(out / f"trades_{name}.csv", index=False)
    print(md)
    print(f"written: {out}/experiments.md")
```

Add `trade_stats` to the existing metrics import if not present. Update `main()`:

```python
    if ns.command == "fetch":
        cmd_fetch(ns)
    elif ns.command == "experiments":
        cmd_experiments(ns)
    else:
        cmd_run(ns, with_sweep=(ns.command == "sweep"))
```

- [ ] **Step 4: Amend the spec's integrity wording** — in the spec, change the base-comparability row and the testing bullet from "asserts base metrics match/equal" to "checks base metrics against `20260710-115422` and reports MATCH/MISMATCH loudly (recorded in the report meta); a mismatch does not abort — the race is internally consistent because every row shares the in-process code path". Reason: a hard assert would kill a ~4 h detached run over a signal that is diagnostic, not invalidating.

- [ ] **Step 5: Run to verify it passes** — `python3 -m pytest tests/test_backtest_cli.py -q` → green.
- [ ] **Step 6: Full suite** — `python3 -m pytest tests/test_backtest_*.py tests/test_reports.py -q` → all green.
- [ ] **Step 7: Commit** — `git add scripts/backtest_sleeve_a.py tests/test_backtest_cli.py docs/superpowers/specs/2026-07-10-phase3d-entry-mechanics-experiments-design.md && git commit -m "feat(backtest): experiments CLI — entry-mechanics race + combined-config gate"`

---

### Task 7: Launch the race detached, monitor, report

**Files:**
- No source changes. Output: `reports/backtests/<ts>-experiments/`.

- [ ] **Step 1: Smoke-run the wiring on a short window** (~minutes, catches crashes before the 4 h run):

```bash
cd /Users/tui/dvrg && python3 scripts/backtest_sleeve_a.py experiments \
  --start 2024-01-01 --end 2024-12-31 2>&1 | tail -30
```

Expected: completes, writes `experiments.md` with a 5-row race table and an embedded gate section (verdict values on a 1-year window are meaningless — only checking the plumbing).

- [ ] **Step 2: Launch the full run detached** (nohup + disown — survives harness kills, as established for the sweep):

```bash
cd /Users/tui/dvrg && nohup python3 scripts/backtest_sleeve_a.py experiments \
  > /tmp/experiments_race.log 2>&1 & disown
```

- [ ] **Step 3: Monitor periodically** (~hourly): process alive (`pgrep -f "backtest_sleeve_a.py experiments"`), log tail advancing. ETA ≈ 15 sims × ~15 min ≈ 3.5–4 h.

- [ ] **Step 4: On completion** — read `experiments.md`; report to owner: race table, combined-config gate verdict **as-is**, honest interpretation (did requote/valve convert the 41% missed fills; at what cost), reminder that no production change follows regardless. Update `.superpowers/sdd` progress ledger and auto-memory (`autopilot-execution-layer.md`).

---

## Self-Review

- **Spec coverage:** A → Tasks 2–3 (flag + TTL patch in VARIANTS); B → Tasks 1–3; C → Task 4 (VARIANTS/margin8); race + recentred sweep + gate → Tasks 4–6; detached run + as-is reporting → Task 7; integrity check → Task 6 (with the wording amendment folded in). No gaps.
- **Placeholders:** none — every step carries runnable code/commands.
- **Type consistency:** miss dict `{"count", "conviction"}` consistent across Tasks 2–3; market-buy dict `{"symbol","qty","ref_price","atr","conviction"}` consistent between `_weekly` and the daily fill step; `race_row` keys match the Task 5 renderer and its test.
