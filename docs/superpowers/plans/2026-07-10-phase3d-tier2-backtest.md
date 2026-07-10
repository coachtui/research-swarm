# Phase 3D Tier 2 Backtest Harness Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A local CLI backtest that walks Jan 2015 → Jun 2026 week by week, drives the *real* Sleeve A funnel functions on historical bars, and renders a gate verdict against the three pre-committed criteria in the spec (`docs/superpowers/specs/2026-07-10-phase3d-tier2-backtest-design.md`).

**Architecture:** New pure package `execution/backtest/` (ledger, fills, universe, data, metrics, simulator, baselines, report, sensitivity) plus `scripts/backtest_sleeve_a.py`. The event loop calls production functions (`screen_row`, `plan_decisions`, `size_entry`, `extension_state`, `entry_limit_price`, `entry_ttl_days`, `stop_levels`, `classify_regime`, `compute_breadth`) on as-of slices; only calendar/fills/ledger code is backtest-only.

**Tech Stack:** Python 3.11, pandas, yfinance, pyarrow (all already in requirements.txt). No new dependencies.

## Global Constraints

- Run tests with `python3 -m pytest <file> -q --no-cov` (repo addopts force coverage of `research_swarm` otherwise).
- **Never modify** production funnel/indicator/constants modules. The sensitivity sweep patches module attributes at runtime and restores them.
- Whole-share buys only (`qty = int(notional // limit)`) — matches live Alpaca GTC constraint (PR #9).
- Sells fill at next open minus 10 bps slippage; buys fill at `min(open, limit)` only if that day's `low ≤ limit`; no commissions.
- Unit tests never touch the network — yfinance is monkeypatched.
- `data/backtest/` and `reports/backtests/` are gitignored.
- Conviction stand-in: `screen_score × 10` clamped 0–100 (base run); `flat_conviction` config overrides for the no-signal variant.
- Backtest window 2015-01-01 → 2026-06-30; data pull starts 2014-07-01 for indicator warm-up.
- Universe is hybrid: PIT S&P 500 membership ∪ current iShares IJH/IJR holdings. The base run, every baseline, and every sweep run MUST receive the identical `pit`/`static_universe` arguments — a universe mismatch invalidates all relative comparisons.
- Guardrails (`enforce_funnel_guardrails`) are **omitted**: theme/sector tags don't exist historically, so the guardrail would be inert; the report discloses this.

## File map

| File | Task |
|---|---|
| `execution/backtest/__init__.py`, `ledger.py` | 1 |
| `execution/backtest/fills.py` | 2 |
| `execution/backtest/universe.py` | 3 |
| `execution/backtest/data.py` | 4 |
| `execution/backtest/metrics.py` | 5 |
| `execution/backtest/simulator.py` | 6 |
| `execution/backtest/baselines.py` | 7 |
| `execution/backtest/report.py` | 8 |
| `execution/backtest/sensitivity.py` | 9 |
| `scripts/backtest_sleeve_a.py`, `.gitignore` | 10 |

---

### Task 1: Ledger

**Files:**
- Create: `execution/backtest/__init__.py` (empty), `execution/backtest/ledger.py`
- Test: `tests/test_backtest_ledger.py`

**Interfaces:**
- Consumes: nothing (leaf module).
- Produces: `Position(symbol, qty, cost_basis, high_water, atr)` dataclass; `Ledger(starting_cash)` with `.cash: float`, `.positions: Dict[str, Position]`, `.journal: List[dict]`, `.buy(symbol, qty, price, on, reason, atr=0.0)`, `.sell(symbol, qty, price, on, reason)`, `.mark(on, closes) -> float`, `.equity(closes) -> float`, `.equity_series -> pd.Series`. Journal rows: `{"date", "side", "symbol", "qty", "price", "reason"}`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_backtest_ledger.py
from datetime import date

import pytest

from execution.backtest.ledger import Ledger


def test_buy_debits_cash_and_opens_position():
    led = Ledger(10_000.0)
    led.buy("AAA", 10, 50.0, date(2020, 1, 6), "entry_fill", atr=1.5)
    assert led.cash == 9_500.0
    pos = led.positions["AAA"]
    assert (pos.qty, pos.cost_basis, pos.high_water, pos.atr) == (10, 50.0, 50.0, 1.5)
    assert led.journal[-1]["reason"] == "entry_fill"


def test_buy_averages_cost_basis():
    led = Ledger(10_000.0)
    led.buy("AAA", 10, 50.0, date(2020, 1, 6), "entry_fill")
    led.buy("AAA", 10, 60.0, date(2020, 2, 3), "entry_fill")
    assert led.positions["AAA"].qty == 20
    assert led.positions["AAA"].cost_basis == pytest.approx(55.0)


def test_buy_rejects_overspend_and_bad_qty():
    led = Ledger(100.0)
    with pytest.raises(ValueError):
        led.buy("AAA", 3, 50.0, date(2020, 1, 6), "entry_fill")
    with pytest.raises(ValueError):
        led.buy("AAA", 0, 50.0, date(2020, 1, 6), "entry_fill")


def test_sell_partial_then_full_closes_position():
    led = Ledger(10_000.0)
    led.buy("AAA", 10, 50.0, date(2020, 1, 6), "entry_fill")
    led.sell("AAA", 4, 55.0, date(2020, 3, 2), "risk_trim")
    assert led.cash == pytest.approx(9_500.0 + 220.0)
    assert led.positions["AAA"].qty == 6
    led.sell("AAA", 6, 40.0, date(2020, 4, 1), "trailing_stop")
    assert "AAA" not in led.positions
    with pytest.raises(KeyError):
        led.sell("AAA", 1, 40.0, date(2020, 4, 2), "trailing_stop")


def test_sell_rejects_oversell():
    led = Ledger(10_000.0)
    led.buy("AAA", 10, 50.0, date(2020, 1, 6), "entry_fill")
    with pytest.raises(ValueError):
        led.sell("AAA", 11, 55.0, date(2020, 3, 2), "exit")


def test_mark_builds_equity_series():
    led = Ledger(10_000.0)
    led.buy("AAA", 10, 50.0, date(2020, 1, 6), "entry_fill")
    led.mark(date(2020, 1, 6), {"AAA": 52.0})
    led.mark(date(2020, 1, 7), {"AAA": 48.0})
    series = led.equity_series
    assert list(series.values) == [pytest.approx(10_020.0), pytest.approx(9_980.0)]
    assert led.equity({"AAA": 48.0}) == pytest.approx(9_980.0)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_backtest_ledger.py -q --no-cov`
Expected: FAIL — `ModuleNotFoundError: No module named 'execution.backtest'`

- [ ] **Step 3: Implement**

Create empty `execution/backtest/__init__.py`, then:

```python
# execution/backtest/ledger.py
"""Portfolio ledger for the Tier 2 backtest. Whole-share positions, cash,
trade journal, daily equity curve. Knows nothing about markets — callers
pass every price. Raises instead of going negative: an overspend is a
harness bug, never a market outcome."""
from dataclasses import dataclass
from datetime import date
from typing import Dict, List

import pandas as pd


@dataclass
class Position:
    symbol: str
    qty: int
    cost_basis: float   # volume-weighted per-share cost
    high_water: float   # highest close since entry — the stop anchor
    atr: float          # latest ATR, refreshed weekly by the simulator


class Ledger:
    def __init__(self, starting_cash: float) -> None:
        self.cash = float(starting_cash)
        self.positions: Dict[str, Position] = {}
        self.journal: List[dict] = []
        self._dates: List[date] = []
        self._values: List[float] = []

    def buy(self, symbol: str, qty: int, price: float, on: date,
            reason: str, atr: float = 0.0) -> None:
        cost = qty * price
        if qty <= 0:
            raise ValueError(f"buy {symbol}: qty {qty} must be positive")
        if cost > self.cash + 1e-9:
            raise ValueError(f"buy {symbol}: cost {cost:.2f} exceeds cash {self.cash:.2f}")
        self.cash -= cost
        pos = self.positions.get(symbol)
        if pos is None:
            self.positions[symbol] = Position(symbol, qty, price, price, atr)
        else:
            total = pos.qty + qty
            pos.cost_basis = (pos.cost_basis * pos.qty + cost) / total
            pos.qty = total
            pos.atr = atr or pos.atr
        self.journal.append({"date": on, "side": "buy", "symbol": symbol,
                             "qty": qty, "price": price, "reason": reason})

    def sell(self, symbol: str, qty: int, price: float, on: date, reason: str) -> None:
        pos = self.positions[symbol]
        if qty <= 0 or qty > pos.qty:
            raise ValueError(f"sell {symbol}: qty {qty} vs held {pos.qty}")
        self.cash += qty * price
        pos.qty -= qty
        if pos.qty == 0:
            del self.positions[symbol]
        self.journal.append({"date": on, "side": "sell", "symbol": symbol,
                             "qty": qty, "price": price, "reason": reason})

    def equity(self, closes: Dict[str, float]) -> float:
        mv = sum(p.qty * closes[p.symbol] for p in self.positions.values())
        return round(self.cash + mv, 2)

    def mark(self, on: date, closes: Dict[str, float]) -> float:
        eq = self.equity(closes)
        self._dates.append(on)
        self._values.append(eq)
        return eq

    @property
    def equity_series(self) -> pd.Series:
        return pd.Series(self._values, index=pd.DatetimeIndex(self._dates))
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_backtest_ledger.py -q --no-cov`
Expected: 6 passed

- [ ] **Step 5: Commit**

```bash
git add execution/backtest/__init__.py execution/backtest/ledger.py tests/test_backtest_ledger.py
git commit -m "feat(backtest): portfolio ledger with whole-share positions and equity curve"
```

---

### Task 2: Fill rules

**Files:**
- Create: `execution/backtest/fills.py`
- Test: `tests/test_backtest_fills.py`

**Interfaces:**
- Consumes: `stop_levels(high_water, today_close, atr)` from `inngest_app.functions.execution_daily` (importable without the inngest SDK — it lazy-imports).
- Produces: `LimitOrder(symbol, qty, limit, atr, placed, expires, conviction)` dataclass; `try_fill_buy(order, day_open, day_low) -> Optional[float]`; `sell_fill_price(day_open, slippage_bps=10.0) -> float`; `check_stop(high_water, today_close, atr) -> Tuple[float, bool]` (new high-water, triggered).

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_backtest_fills.py
from datetime import date

import pytest

from execution.backtest.fills import LimitOrder, check_stop, sell_fill_price, try_fill_buy


def _order(limit: float) -> LimitOrder:
    return LimitOrder(symbol="AAA", qty=10, limit=limit, atr=1.0,
                      placed=date(2020, 1, 6), expires=date(2020, 1, 13), conviction=60.0)


def test_no_fill_when_low_stays_above_limit():
    assert try_fill_buy(_order(50.0), day_open=52.0, day_low=50.5) is None


def test_intraday_touch_fills_at_limit():
    assert try_fill_buy(_order(50.0), day_open=52.0, day_low=49.0) == 50.0


def test_gap_down_open_fills_at_the_better_open():
    assert try_fill_buy(_order(50.0), day_open=47.0, day_low=46.0) == 47.0


def test_sell_fill_price_applies_slippage():
    assert sell_fill_price(100.0) == pytest.approx(99.9)      # default 10 bps
    assert sell_fill_price(100.0, slippage_bps=0.0) == 100.0


def test_check_stop_ratchets_high_water_up_only():
    hw, hit = check_stop(high_water=100.0, today_close=104.0, atr=2.0)
    assert (hw, hit) == (104.0, False)
    hw, hit = check_stop(high_water=104.0, today_close=101.0, atr=2.0)
    assert (hw, hit) == (104.0, False)          # stop = 104 - 2.5*2 = 99


def test_check_stop_triggers_below_trail():
    # production constant TRAILING_STOP_ATR_MULT = 2.5 → stop = 104 - 5 = 99
    hw, hit = check_stop(high_water=104.0, today_close=98.9, atr=2.0)
    assert (hw, hit) == (104.0, True)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_backtest_fills.py -q --no-cov`
Expected: FAIL — `ModuleNotFoundError` / `ImportError` on `execution.backtest.fills`

- [ ] **Step 3: Implement**

```python
# execution/backtest/fills.py
"""Order lifecycle + honest fill rules mirroring live Alpaca semantics.
Stop math delegates to the production stop_levels — never re-implemented."""
from dataclasses import dataclass
from datetime import date
from typing import Optional, Tuple

from inngest_app.functions.execution_daily import stop_levels

SELL_SLIPPAGE_BPS = 10.0


@dataclass
class LimitOrder:
    symbol: str
    qty: int
    limit: float
    atr: float            # screen-time ATR, seeds the position on fill
    placed: date
    expires: date
    conviction: float = 0.0


def try_fill_buy(order: LimitOrder, day_open: float, day_low: float) -> Optional[float]:
    """GTC limit buy: fills the first day the low trades through the limit,
    at min(open, limit) — a gap-down open fills at the (better) open."""
    if day_low <= order.limit:
        return round(min(day_open, order.limit), 4)
    return None


def sell_fill_price(day_open: float, slippage_bps: float = SELL_SLIPPAGE_BPS) -> float:
    return round(day_open * (1.0 - slippage_bps / 10_000.0), 4)


def check_stop(high_water: float, today_close: float, atr: float) -> Tuple[float, bool]:
    """(new_high_water, triggered). A close that sets a new high-water can
    never trigger — stop_levels ratchets first, exactly as the live cron."""
    hw, stop = stop_levels(high_water, today_close, atr)
    return hw, today_close <= stop
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_backtest_fills.py -q --no-cov`
Expected: 6 passed

- [ ] **Step 5: Commit**

```bash
git add execution/backtest/fills.py tests/test_backtest_fills.py
git commit -m "feat(backtest): limit-buy fill rules and stop check delegating to production stop_levels"
```

---

### Task 3: Universe

**Files:**
- Create: `execution/backtest/universe.py`
- Test: `tests/test_backtest_universe.py`

**Interfaces:**
- Consumes: `FUNNEL_PRICE_FLOOR` (2.0), `THEME_ADV_FLOOR_USD` (1_000_000.0) from `execution.constants`. PIT CSV format is the canonical `ticker,date_added,date_removed` written by the existing `scripts/backtest/data/sp500_constituents.py` downloader.
- Produces: `parse_ishares_csv(path) -> List[str]`; `load_universe(csv_dir) -> List[str]` (sorted union of all CSVs in dir); `load_pit_membership(csv_path) -> pd.DataFrame` (normalized tickers, parsed dates); `members_asof(pit, asof) -> Set[str]`; `eligible_asof(ohlcv, asof, allowed=None) -> List[str]` where `ohlcv: Dict[str, pd.DataFrame]`, `asof: pd.Timestamp`, and `allowed` (when given) restricts consideration to that symbol set.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_backtest_universe.py
import numpy as np
import pandas as pd
import pytest

from execution.backtest.universe import (
    eligible_asof, load_pit_membership, load_universe, members_asof,
    parse_ishares_csv,
)

ISHARES_SAMPLE = """\
iShares Core S&P 500 ETF
Fund Holdings as of,"Jul 08, 2026"
Inception Date,"May 15, 2000"

Ticker,Name,Sector,Asset Class,Market Value,Weight (%)
AAPL,APPLE INC,Information Technology,Equity,"1,000",7.0
BRK.B,BERKSHIRE HATHAWAY INC CLASS B,Financials,Equity,"900",1.7
XTSLA,BLK CSH FND TREASURY SL AGENCY,Cash and/or Derivatives,Money Market,"5",0.0
MSFT,MICROSOFT CORP,Information Technology,Equity,"950",6.5
"""


def test_parse_ishares_csv_skips_preamble_and_non_equity(tmp_path):
    p = tmp_path / "IVV_holdings.csv"
    p.write_text(ISHARES_SAMPLE)
    assert parse_ishares_csv(p) == ["AAPL", "BRK-B", "MSFT"]


def test_load_universe_unions_and_sorts(tmp_path):
    (tmp_path / "a.csv").write_text(ISHARES_SAMPLE)
    (tmp_path / "b.csv").write_text(ISHARES_SAMPLE.replace("MSFT", "NVDA"))
    assert load_universe(tmp_path) == ["AAPL", "BRK-B", "MSFT", "NVDA"]


def _frame(price: float, volume: float, rows: int = 100) -> pd.DataFrame:
    idx = pd.bdate_range("2020-01-01", periods=rows)
    return pd.DataFrame({
        "Open": price, "High": price, "Low": price,
        "Close": np.full(rows, price), "Volume": np.full(rows, volume),
    }, index=idx)


def test_eligible_asof_applies_floors_and_min_history():
    asof = pd.Timestamp("2020-05-01")
    ohlcv = {
        "GOOD": _frame(price=50.0, volume=100_000),      # ADV $5M — passes
        "PENNY": _frame(price=1.5, volume=10_000_000),   # price floor fails
        "ILLIQ": _frame(price=50.0, volume=1_000),       # ADV $50k fails
        "YOUNG": _frame(price=50.0, volume=100_000, rows=30),  # <63 rows fails
    }
    assert eligible_asof(ohlcv, asof) == ["GOOD"]


def test_eligible_asof_uses_only_data_up_to_asof():
    df = _frame(price=50.0, volume=100_000)
    df.loc[df.index > "2020-04-15", "Volume"] = 0.0     # goes illiquid later
    # 2020-04-01: 66 rows of history (≥63) and full-volume ADV → eligible
    assert eligible_asof({"AAA": df}, pd.Timestamp("2020-04-01")) == ["AAA"]
    # 2020-05-15: the 20d ADV window is all zero-volume days → ineligible
    assert eligible_asof({"AAA": df}, pd.Timestamp("2020-05-15")) == []


def test_eligible_asof_respects_allowed_filter():
    asof = pd.Timestamp("2020-05-01")
    ohlcv = {"GOOD": _frame(50.0, 100_000), "ALSO": _frame(50.0, 100_000)}
    assert eligible_asof(ohlcv, asof, allowed={"ALSO"}) == ["ALSO"]
    assert eligible_asof(ohlcv, asof) == ["ALSO", "GOOD"]


PIT_SAMPLE = """\
ticker,date_added,date_removed
AAPL,1982-11-30,
BRK.B,2010-02-16,
TWTR,2018-06-07,2022-10-27
YHOO,1999-12-08,2017-06-19
"""


def test_pit_membership_asof(tmp_path):
    p = tmp_path / "sp500_constituents.csv"
    p.write_text(PIT_SAMPLE)
    pit = load_pit_membership(p)
    assert members_asof(pit, pd.Timestamp("2020-01-01")) == {"AAPL", "BRK-B", "TWTR"}
    assert members_asof(pit, pd.Timestamp("2016-01-01")) == {"AAPL", "BRK-B", "YHOO"}
    assert members_asof(pit, pd.Timestamp("2023-01-01")) == {"AAPL", "BRK-B"}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_backtest_universe.py -q --no-cov`
Expected: FAIL — `ModuleNotFoundError` on `execution.backtest.universe`

- [ ] **Step 3: Implement**

```python
# execution/backtest/universe.py
"""Universe stand-in: point-in-time S&P 500 membership ∪ current iShares
mid/small holdings, per-week floors applied strictly as-of. Mcap floor is
NOT applied (no point-in-time share counts) — ADV is the liquidity proxy;
the report discloses this."""
import csv
from pathlib import Path
from typing import Dict, List, Optional, Set

import pandas as pd

from execution.constants import FUNNEL_PRICE_FLOOR, THEME_ADV_FLOOR_USD

_MIN_ROWS = 63  # matches execution.funnel.screen._MIN_ROWS


def parse_ishares_csv(path: Path) -> List[str]:
    """iShares holdings CSVs carry a preamble; the table starts at the row
    whose first cell is 'Ticker'. Equity rows only; '.'→'-' for yfinance."""
    with open(path, newline="", encoding="utf-8-sig") as fh:
        rows = list(csv.reader(fh))
    header_idx = next(i for i, r in enumerate(rows) if r and r[0].strip() == "Ticker")
    header = rows[header_idx]
    t_col, a_col = header.index("Ticker"), header.index("Asset Class")
    out: List[str] = []
    for r in rows[header_idx + 1:]:
        if len(r) <= max(t_col, a_col) or r[a_col].strip() != "Equity":
            continue
        sym = r[t_col].strip().replace(".", "-").upper()
        if sym and sym != "--":
            out.append(sym)
    return out


def load_universe(csv_dir: Path) -> List[str]:
    syms = set()
    for p in sorted(Path(csv_dir).glob("*.csv")):
        syms.update(parse_ishares_csv(p))
    return sorted(syms)


def load_pit_membership(csv_path: Path) -> pd.DataFrame:
    """Canonical ticker,date_added,date_removed CSV (the format written by
    scripts/backtest/data/sp500_constituents.py --download)."""
    df = pd.read_csv(csv_path, parse_dates=["date_added", "date_removed"])
    df["ticker"] = (df["ticker"].astype(str).str.strip()
                    .str.replace(".", "-", regex=False).str.upper())
    return df


def members_asof(pit: pd.DataFrame, asof: pd.Timestamp) -> Set[str]:
    live = pit[(pit["date_added"] <= asof)
               & (pit["date_removed"].isna() | (pit["date_removed"] > asof))]
    return set(live["ticker"])


def eligible_asof(ohlcv: Dict[str, pd.DataFrame], asof: pd.Timestamp,
                  allowed: Optional[Set[str]] = None) -> List[str]:
    """Price and 20d dollar-ADV floors from data ≤ asof only; `allowed`
    (when given) is the point-in-time membership union."""
    out: List[str] = []
    for sym, df in ohlcv.items():
        if allowed is not None and sym not in allowed:
            continue
        win = df.loc[:asof]
        if len(win) < _MIN_ROWS:
            continue
        price = float(win["Close"].iloc[-1])
        adv = float((win["Close"] * win["Volume"]).tail(20).mean())
        if price >= FUNNEL_PRICE_FLOOR and adv >= THEME_ADV_FLOOR_USD:
            out.append(sym)
    return sorted(out)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_backtest_universe.py -q --no-cov`
Expected: 6 passed

- [ ] **Step 5: Commit**

```bash
git add execution/backtest/universe.py tests/test_backtest_universe.py
git commit -m "feat(backtest): iShares universe parsing and as-of eligibility floors"
```

---

### Task 4: Data cache

**Files:**
- Create: `execution/backtest/data.py`
- Test: `tests/test_backtest_data.py`

**Interfaces:**
- Consumes: `SECTOR_ETFS`, `BENCHMARK`, `EQUAL_WEIGHT`, `VIX` from `execution.constants`; `yfinance` (monkeypatched in tests).
- Produces: `MARKET_SYMBOLS: tuple` (SPY, RSP, ^VIX + 11 sector ETFs); `fetch_ohlcv(symbols, cache_dir, start="2014-07-01", end="2026-07-01", batch_size=100) -> List[str]` (returns symbols that produced data; skips already-cached); `load_ohlcv(cache_dir, min_rows=63) -> Dict[str, pd.DataFrame]` with columns Open/High/Low/Close/Volume.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_backtest_data.py
import numpy as np
import pandas as pd

import execution.backtest.data as data_mod
from execution.backtest.data import MARKET_SYMBOLS, fetch_ohlcv, load_ohlcv


def _fake_download(symbols, **kwargs):
    idx = pd.bdate_range("2020-01-01", periods=80)
    cols = ["Open", "High", "Low", "Close", "Volume"]
    frames = {}
    for s in (symbols if isinstance(symbols, list) else [symbols]):
        frames[s] = pd.DataFrame(
            np.full((80, 5), 10.0), index=idx, columns=cols)
    return pd.concat(frames, axis=1)          # yfinance group_by="ticker" shape


def test_market_symbols_include_benchmarks_and_sectors():
    assert "SPY" in MARKET_SYMBOLS and "RSP" in MARKET_SYMBOLS and "^VIX" in MARKET_SYMBOLS
    assert "XLK" in MARKET_SYMBOLS
    assert len(MARKET_SYMBOLS) == 14


def test_fetch_writes_parquet_and_skips_cached(tmp_path, monkeypatch):
    calls = []
    def spy_download(symbols, **kwargs):
        calls.append(list(symbols))
        return _fake_download(symbols, **kwargs)
    monkeypatch.setattr(data_mod.yf, "download", spy_download)

    got = fetch_ohlcv(["AAA", "BBB"], cache_dir=tmp_path)
    assert sorted(got) == ["AAA", "BBB"]
    assert (tmp_path / "AAA.parquet").exists()

    calls.clear()
    fetch_ohlcv(["AAA", "CCC"], cache_dir=tmp_path)     # AAA cached → only CCC fetched
    assert calls == [["CCC"]]


def test_load_round_trips_and_applies_min_rows(tmp_path, monkeypatch):
    monkeypatch.setattr(data_mod.yf, "download", _fake_download)
    fetch_ohlcv(["AAA", "^VIX"], cache_dir=tmp_path)
    loaded = load_ohlcv(tmp_path)
    assert set(loaded) == {"AAA", "^VIX"}                # ^VIX name round-trips
    assert list(loaded["AAA"].columns) == ["Open", "High", "Low", "Close", "Volume"]
    assert load_ohlcv(tmp_path, min_rows=100) == {}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_backtest_data.py -q --no-cov`
Expected: FAIL — `ModuleNotFoundError` on `execution.backtest.data`

- [ ] **Step 3: Implement**

```python
# execution/backtest/data.py
"""OHLCV download + parquet cache. The only backtest module that touches
the network — and only in fetch_ohlcv. auto_adjust=True: splits/dividends
folded in, matching what the live screen sees from yfinance."""
import logging
from pathlib import Path
from typing import Dict, Iterable, List

import pandas as pd
import yfinance as yf

from execution.constants import BENCHMARK, EQUAL_WEIGHT, SECTOR_ETFS, VIX

logger = logging.getLogger(__name__)

MARKET_SYMBOLS = (BENCHMARK, EQUAL_WEIGHT, VIX, *SECTOR_ETFS)
START, END = "2014-07-01", "2026-07-01"
COLUMNS = ["Open", "High", "Low", "Close", "Volume"]


def _cache_path(cache_dir: Path, sym: str) -> Path:
    return Path(cache_dir) / f"{sym.replace('^', '_IDX_')}.parquet"


def fetch_ohlcv(symbols: Iterable[str], cache_dir: Path,
                start: str = START, end: str = END,
                batch_size: int = 100) -> List[str]:
    cache_dir = Path(cache_dir)
    cache_dir.mkdir(parents=True, exist_ok=True)
    missing = [s for s in symbols if not _cache_path(cache_dir, s).exists()]
    written: List[str] = []
    for i in range(0, len(missing), batch_size):
        chunk = missing[i:i + batch_size]
        data = yf.download(chunk, start=start, end=end, auto_adjust=True,
                           group_by="ticker", progress=False, threads=True)
        for sym in chunk:
            try:
                df = data[sym] if len(chunk) > 1 or isinstance(
                    data.columns, pd.MultiIndex) else data
            except KeyError:
                logger.warning("no data returned for %s", sym)
                continue
            df = df.dropna(how="all")
            if df.empty:
                logger.warning("empty history for %s", sym)
                continue
            df[COLUMNS].to_parquet(_cache_path(cache_dir, sym))
            written.append(sym)
    return written


def load_ohlcv(cache_dir: Path, min_rows: int = 63) -> Dict[str, pd.DataFrame]:
    out: Dict[str, pd.DataFrame] = {}
    for p in sorted(Path(cache_dir).glob("*.parquet")):
        df = pd.read_parquet(p)
        if len(df) >= min_rows:
            out[p.stem.replace("_IDX_", "^")] = df
    return out
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_backtest_data.py -q --no-cov`
Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
git add execution/backtest/data.py tests/test_backtest_data.py
git commit -m "feat(backtest): yfinance batch fetch with parquet cache"
```

---

### Task 5: Metrics

**Files:**
- Create: `execution/backtest/metrics.py`
- Test: `tests/test_backtest_metrics.py`

**Interfaces:**
- Consumes: nothing project-specific.
- Produces: `compute_metrics(equity: pd.Series) -> dict` with keys `cagr, max_drawdown, sharpe, mar, yearly_returns` (`max_drawdown` ≤ 0; `yearly_returns` is `{year_str: float}`); `yearly_log_outperformance(a: pd.Series, b: pd.Series) -> Dict[str, float]` (per calendar year, sum of daily log-return differences on the aligned index).

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_backtest_metrics.py
import math

import numpy as np
import pandas as pd
import pytest

from execution.backtest.metrics import compute_metrics, yearly_log_outperformance


def _series(values, start="2020-01-01"):
    return pd.Series(values, index=pd.bdate_range(start, periods=len(values)))


def test_metrics_on_two_year_doubling():
    idx = pd.DatetimeIndex([pd.Timestamp("2020-01-01"), pd.Timestamp("2022-01-01")])
    m = compute_metrics(pd.Series([100.0, 200.0], index=idx))
    # 731 calendar days (2020 is a leap year), CAGR ≈ √2 − 1
    assert m["cagr"] == pytest.approx(2 ** (365.25 / 731) - 1, rel=1e-3)
    assert m["max_drawdown"] == 0.0


def test_max_drawdown_and_yearly_returns():
    idx = pd.DatetimeIndex(["2020-06-01", "2020-09-01", "2020-12-01", "2021-06-01"])
    m = compute_metrics(pd.Series([100.0, 150.0, 90.0, 120.0], index=idx))
    assert m["max_drawdown"] == pytest.approx(-0.4)          # 150 → 90
    assert m["yearly_returns"]["2020"] == pytest.approx(-0.10)  # 100 → 90
    assert m["yearly_returns"]["2021"] == pytest.approx(120.0 / 90.0 - 1)
    assert m["mar"] == pytest.approx(m["cagr"] / 0.4)


def test_sharpe_zero_vol_is_zero_and_positive_drift_positive():
    flat = compute_metrics(_series([100.0] * 50))
    assert flat["sharpe"] == 0.0
    # deterministic +0.2%/day drift with alternating ±0.5% noise
    rets = [0.002 + (0.005 if i % 2 == 0 else -0.005) for i in range(500)]
    drift = 100 * np.cumprod(1 + np.array(rets))
    assert compute_metrics(_series(list(drift)))["sharpe"] > 0


def test_yearly_log_outperformance():
    a = _series([100, 110, 121], start="2020-12-30")   # spans year boundary
    b = _series([100, 100, 100], start="2020-12-30")
    out = yearly_log_outperformance(a, b)
    total = sum(out.values())
    assert total == pytest.approx(math.log(1.21), rel=1e-9)
    assert set(out) == {"2020", "2021"}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_backtest_metrics.py -q --no-cov`
Expected: FAIL — `ModuleNotFoundError` on `execution.backtest.metrics`

- [ ] **Step 3: Implement**

```python
# execution/backtest/metrics.py
"""Performance metrics on daily equity curves. Sharpe uses rf=0 and √252
annualization; MAR = CAGR / |maxDD|. yearly_log_outperformance feeds gate
criterion 3 (no single year > 50% of total edge)."""
import math
from typing import Dict

import numpy as np
import pandas as pd

TRADING_DAYS = 252


def compute_metrics(equity: pd.Series) -> dict:
    eq = equity.dropna()
    if len(eq) < 2:
        raise ValueError("equity series too short")
    years = (eq.index[-1] - eq.index[0]).days / 365.25
    cagr = (eq.iloc[-1] / eq.iloc[0]) ** (1.0 / years) - 1.0 if years > 0 else 0.0
    dd = eq / eq.cummax() - 1.0
    max_dd = float(dd.min())
    rets = eq.pct_change().dropna()
    std = float(rets.std())
    sharpe = float(rets.mean() / std * math.sqrt(TRADING_DAYS)) if std > 0 else 0.0
    mar = float(cagr / abs(max_dd)) if max_dd < 0 else float("inf")
    # yearly return = year-end value vs prior year-end (first year: vs start)
    yearly: Dict[str, float] = {}
    prev = None
    for year, grp in eq.groupby(eq.index.year):
        start = prev if prev is not None else grp.iloc[0]
        yearly[str(year)] = float(grp.iloc[-1] / start - 1.0)
        prev = grp.iloc[-1]
    return {"cagr": float(cagr), "max_drawdown": max_dd, "sharpe": sharpe,
            "mar": mar, "yearly_returns": yearly}


def yearly_log_outperformance(a: pd.Series, b: pd.Series) -> Dict[str, float]:
    a, b = a.align(b, join="inner")
    diff = np.log(a / a.shift(1)) - np.log(b / b.shift(1))
    diff = diff.dropna()
    return {str(y): float(g.sum()) for y, g in diff.groupby(diff.index.year)}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_backtest_metrics.py -q --no-cov`
Expected: 4 passed

- [ ] **Step 5: Commit**

```bash
git add execution/backtest/metrics.py tests/test_backtest_metrics.py
git commit -m "feat(backtest): equity-curve metrics and yearly log outperformance"
```

---

### Task 6: Simulator (the event loop)

**Files:**
- Create: `execution/backtest/simulator.py`
- Test: `tests/test_backtest_simulator.py`

**Interfaces:**
- Consumes: everything from Tasks 1–3 plus production functions: `screen_row`, `rank_candidates` (`execution.funnel.screen`), `plan_decisions` (`execution.funnel.decisions`), `extension_state`, `entry_limit_price`, `entry_ttl_days`, `size_entry` (`execution.funnel.entries`), `classify_regime` (`execution.indicators.regime`), `compute_breadth` (`execution.indicators.breadth`), constants `REGIME_INVESTED_FRACTION`, `SLEEVE_A_MAX_POSITIONS`, `MIN_TRADE_NOTIONAL`, `BENCHMARK`, `EQUAL_WEIGHT`, `VIX`, `SECTOR_ETFS`.
- Produces: `BacktestConfig(start, end, starting_cash=100_000.0, flat_conviction=None, slippage_bps=10.0)`; `run_backtest(ohlcv, cfg, pit=None, static_universe=None) -> BacktestResult(equity: pd.Series, journal: List[dict], weeks: int)`. `ohlcv` maps symbol → OHLCV frame and must include SPY (plus optionally RSP/^VIX/sector ETFs — regime treats missing inputs as neutral, exactly like production). When `pit` (a `load_pit_membership` frame) is given, the weekly allowed set is `members_asof(pit, today) ∪ set(static_universe or ())`; when `pit` is None the whole `ohlcv` universe is allowed.

**Behavior spec (implementer checklist):**
1. Trading calendar = SPY index restricted to `[cfg.start, cfg.end]`. Week starts = first trading day per ISO week.
2. Daily order: (a) execute queued sells at today's open (slippage applied); (b) process open limit buys — expire (journal `missed_fill`) if `today.date() > expires`, else fill via `try_fill_buy` when today has a bar, skipping (journal `fill_skipped_cash`) if cash can't cover; (c) if week start: run weekly decisions (below); (d) at close: refresh `last_close`, ratchet stops via `check_stop`, queue triggered full exits (`trailing_stop`) for tomorrow's open; force-liquidate positions with no bar for 10 straight days at `last_close` with slippage (`delisted`); (e) `ledger.mark`.
3. Weekly decisions: regime from `compute_breadth` (sector ETF closes ≤ today) + `classify_regime` (SPY closes ≤ today, ^VIX closes ≤ today); screen every `eligible_asof` symbol via `screen_row(sym, df.loc[:today], spy_closes, ENTRY_TAGS, [], [], None)`; conviction = `screen_score × 10` (or `cfg.flat_conviction`); refresh each held position's conviction/ATR from its screen row (missing row → conviction 50, keep old ATR); `plan_decisions(holdings, top-25 candidates, sleeve_equity, SLEEVE_A_MAX_POSITIONS)`; queue exits (cancel any open buy order for exited symbols) and trims (`qty = int(sell_notional // last_close)`, skip qty 0); place entries: `deployable = max(0, REGIME_INVESTED_FRACTION[regime] × equity − position_mv − committed_orders)`, `cash_remaining = cash − committed_orders`, then per entry-queue symbol compute extension state → limit/TTL → `size_entry` → `qty = int(notional // limit)`; skip qty 0 or `qty × limit < MIN_TRADE_NOTIONAL`; skip symbols with an existing open order or pending sell; decrement `deployable`/`cash_remaining` by `qty × limit` after each placement.
4. Never let the ledger raise in normal operation: every buy is pre-checked against cash; every sell qty is clamped to the held qty.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_backtest_simulator.py
"""Synthetic end-to-end: three fake symbols with deterministic paths.
Locks the harness's honesty — accounting identity, no lookahead fills,
stops fire on crashes. Production math is trusted (it has its own tests)."""
import numpy as np
import pandas as pd
import pytest

from execution.backtest.simulator import BacktestConfig, run_backtest


def _make_df(closes: np.ndarray, start="2019-01-01", vol=1_000_000) -> pd.DataFrame:
    idx = pd.bdate_range(start, periods=len(closes))
    close = pd.Series(closes, index=idx)
    return pd.DataFrame({
        "Open": close.shift(1).fillna(close.iloc[0]),
        "High": close * 1.01,
        "Low": close * 0.985,   # deep enough daily range that limits fill
        "Close": close,
        "Volume": float(vol),
    }, index=idx)


def _fixture(n=500):
    rng = np.random.default_rng(42)
    noise = lambda: 1 + 0.002 * rng.standard_normal(n)
    up = 50 * np.cumprod(1.0015 * noise())            # strong uptrend
    flat = np.full(n, 50.0) * np.cumprod(noise())     # drifting flat
    crash = 50 * np.cumprod(1.002 * noise())
    crash[300:] = crash[299] * np.cumprod(np.full(n - 300, 0.97))  # −3%/day cliff
    spy = 300 * np.cumprod(1.0004 * noise())
    return {
        "UPUP": _make_df(up), "FLAT": _make_df(flat), "CRSH": _make_df(crash),
        "SPY": _make_df(spy),
    }


CFG = BacktestConfig(start="2019-06-01", end="2020-11-01", starting_cash=100_000.0)


@pytest.fixture(scope="module")
def result():
    return run_backtest(_fixture(), CFG)


def test_uptrending_symbol_gets_bought(result):
    buys = [j for j in result.journal if j["side"] == "buy"]
    assert any(j["symbol"] == "UPUP" for j in buys)


def test_crash_triggers_trailing_stop_exit(result):
    stops = [j for j in result.journal
             if j["side"] == "sell" and j["reason"] == "trailing_stop"]
    assert any(j["symbol"] == "CRSH" for j in stops)


def test_accounting_identity_and_no_negative_cash(result):
    # replay the journal: cash must never go negative and must reconcile
    cash = CFG.starting_cash
    qty: dict = {}
    for j in result.journal:
        if j["side"] == "buy":
            cash -= j["qty"] * j["price"]
            qty[j["symbol"]] = qty.get(j["symbol"], 0) + j["qty"]
        elif j["side"] == "sell":
            cash += j["qty"] * j["price"]
            qty[j["symbol"]] = qty[j["symbol"]] - j["qty"]
        assert cash > -1e-6, f"negative cash after {j}"
    assert all(q >= 0 for q in qty.values())


def test_no_lookahead_buy_fills(result):
    """Every buy fill must be on a day whose low actually reached the fill
    price, and never above the open (min(open, limit) semantics). Fill
    prices are rounded to 4dp, so allow 1e-4 of rounding slack."""
    data = _fixture()
    for j in result.journal:
        if j["side"] != "buy":
            continue
        bar = data[j["symbol"]].loc[pd.Timestamp(j["date"])]
        assert bar["Low"] <= j["price"] + 1e-4
        assert j["price"] <= bar["Open"] + 1e-4


def test_equity_curve_covers_calendar_and_ends_positive(result):
    data = _fixture()
    cal = data["SPY"].loc[CFG.start:CFG.end].index
    assert len(result.equity) == len(cal)
    assert result.equity.iloc[-1] > 0
    assert result.weeks > 50


def test_pit_membership_restricts_entries():
    pit = pd.DataFrame({"ticker": ["UPUP", "FLAT"],
                        "date_added": [pd.Timestamp("2000-01-01")] * 2,
                        "date_removed": [pd.NaT, pd.NaT]})
    res = run_backtest(_fixture(), CFG, pit=pit)
    buys = {j["symbol"] for j in res.journal if j["side"] == "buy"}
    assert "CRSH" not in buys        # not a PIT member, no static list given
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_backtest_simulator.py -q --no-cov`
Expected: FAIL — `ModuleNotFoundError` on `execution.backtest.simulator`

- [ ] **Step 3: Implement**

```python
# execution/backtest/simulator.py
"""Event-loop simulator: weekly decisions via the production funnel
functions, daily fills/stops between. Only harness concerns live here —
calendars, order queues, the ledger. Decision math is always imported."""
import logging
from dataclasses import dataclass, field
from datetime import timedelta
from typing import Any, Dict, List, Optional

import pandas as pd

from execution.constants import (
    BENCHMARK, EQUAL_WEIGHT, MIN_TRADE_NOTIONAL, REGIME_INVESTED_FRACTION,
    SECTOR_ETFS, SLEEVE_A_MAX_POSITIONS, VIX,
)
from execution.funnel.decisions import plan_decisions
from execution.funnel.entries import (
    entry_limit_price, entry_ttl_days, extension_state, size_entry,
)
from execution.funnel.screen import rank_candidates, screen_row
from execution.indicators.breadth import compute_breadth
from execution.indicators.regime import classify_regime

from execution.backtest.fills import LimitOrder, check_stop, sell_fill_price, try_fill_buy
from execution.backtest.ledger import Ledger
from execution.backtest.universe import eligible_asof, members_asof

logger = logging.getLogger(__name__)

CANDIDATE_POOL = 25
DELIST_AFTER_MISSING_DAYS = 10
ENTRY_TAGS: Dict[str, Any] = {"themes": [], "industries": [], "watchlist": False}
_NON_STOCK = {BENCHMARK, EQUAL_WEIGHT, VIX, *SECTOR_ETFS}


@dataclass
class BacktestConfig:
    start: str = "2015-01-01"
    end: str = "2026-06-30"
    starting_cash: float = 100_000.0
    flat_conviction: Optional[float] = None   # None → screen_score × 10
    slippage_bps: float = 10.0


@dataclass
class BacktestResult:
    equity: pd.Series
    journal: List[dict]
    weeks: int


def _conviction(row: Dict[str, Any], cfg: BacktestConfig) -> float:
    if cfg.flat_conviction is not None:
        return float(cfg.flat_conviction)
    return max(0.0, min(100.0, float(row["screen_score"]) * 10.0))


def _week_starts(cal: pd.DatetimeIndex) -> set:
    firsts: Dict[tuple, pd.Timestamp] = {}
    for ts in cal:
        iso = ts.isocalendar()
        firsts.setdefault((iso.year, iso.week), ts)
    return set(firsts.values())


def run_backtest(ohlcv: Dict[str, pd.DataFrame], cfg: BacktestConfig,
                 pit: Optional[pd.DataFrame] = None,
                 static_universe: Optional[List[str]] = None) -> BacktestResult:
    spy = ohlcv[BENCHMARK]
    cal = spy.loc[cfg.start:cfg.end].index
    weeks = _week_starts(cal)
    stocks = {s: df for s, df in ohlcv.items() if s not in _NON_STOCK}
    static = set(static_universe or ())

    ledger = Ledger(cfg.starting_cash)
    open_orders: List[LimitOrder] = []
    pending_sells: List[dict] = []      # {"symbol","qty","reason"}; qty None → full
    last_close: Dict[str, float] = {}
    missing_days: Dict[str, int] = {}
    n_weeks = 0

    for today in cal:
        # (a) queued sells at the open
        still_pending: List[dict] = []
        for s in pending_sells:
            sym = s["symbol"]
            pos = ledger.positions.get(sym)
            if pos is None:
                continue
            df = stocks[sym]
            if today not in df.index:
                still_pending.append(s)
                continue
            qty = min(pos.qty, s["qty"] or pos.qty)
            px = sell_fill_price(float(df.at[today, "Open"]), cfg.slippage_bps)
            ledger.sell(sym, qty, px, today.date(), s["reason"])
        pending_sells = still_pending

        # (b) limit buys: expiry then fills
        remaining: List[LimitOrder] = []
        for o in open_orders:
            if today.date() > o.expires:
                ledger.journal.append({"date": today.date(), "side": "cancel",
                                       "symbol": o.symbol, "qty": o.qty,
                                       "price": o.limit, "reason": "missed_fill"})
                continue
            df = stocks[o.symbol]
            if today in df.index:
                fill = try_fill_buy(o, float(df.at[today, "Open"]),
                                    float(df.at[today, "Low"]))
                if fill is not None:
                    if o.qty * fill <= ledger.cash:
                        ledger.buy(o.symbol, o.qty, fill, today.date(),
                                   "entry_fill", atr=o.atr)
                        last_close[o.symbol] = float(df.at[today, "Close"])
                        continue
                    ledger.journal.append({"date": today.date(), "side": "cancel",
                                           "symbol": o.symbol, "qty": o.qty,
                                           "price": fill, "reason": "fill_skipped_cash"})
                    continue
            remaining.append(o)
        open_orders = remaining

        # (c) weekly decisions
        if today in weeks:
            n_weeks += 1
            allowed = (members_asof(pit, today) | static) if pit is not None else None
            _weekly(today, ohlcv, stocks, spy, ledger, open_orders,
                    pending_sells, last_close, cfg, allowed)

        # (d) close: stops, delist sweep
        for pos in list(ledger.positions.values()):
            df = stocks[pos.symbol]
            if today in df.index:
                missing_days[pos.symbol] = 0
                close = float(df.at[today, "Close"])
                last_close[pos.symbol] = close
                hw, hit = check_stop(pos.high_water, close, pos.atr)
                pos.high_water = hw
                if hit and not any(s["symbol"] == pos.symbol for s in pending_sells):
                    pending_sells.append({"symbol": pos.symbol, "qty": None,
                                          "reason": "trailing_stop"})
            else:
                missing_days[pos.symbol] = missing_days.get(pos.symbol, 0) + 1
                if missing_days[pos.symbol] >= DELIST_AFTER_MISSING_DAYS:
                    px = sell_fill_price(last_close[pos.symbol], cfg.slippage_bps)
                    ledger.sell(pos.symbol, pos.qty, px, today.date(), "delisted")
                    pending_sells = [s for s in pending_sells
                                     if s["symbol"] != pos.symbol]

        # (e) mark
        ledger.mark(today.date(), last_close)

    return BacktestResult(ledger.equity_series, ledger.journal, n_weeks)


def _weekly(today, ohlcv, stocks, spy, ledger, open_orders, pending_sells,
            last_close, cfg, allowed=None) -> None:
    spy_closes = spy.loc[:today]["Close"]

    etf_closes = {sym: ohlcv[sym].loc[:today]["Close"]
                  for sym in (*SECTOR_ETFS, BENCHMARK, EQUAL_WEIGHT) if sym in ohlcv}
    breadth = compute_breadth(etf_closes)
    vix_closes = ohlcv[VIX].loc[:today]["Close"] if VIX in ohlcv else None
    regime = classify_regime(spy_closes, vix_closes,
                             breadth["pct_above_200dma"])["regime"]

    rows = []
    for sym in eligible_asof(stocks, today, allowed=allowed):
        row = screen_row(sym, stocks[sym].loc[:today], spy_closes,
                         ENTRY_TAGS, [], [], None)
        if row is not None:
            rows.append(row)
    ranked = rank_candidates(rows)
    by_symbol = {r["symbol"]: r for r in ranked}

    holdings = []
    for pos in ledger.positions.values():
        row = by_symbol.get(pos.symbol)
        if row is not None:
            pos.atr = float(row["atr"])
        conv = _conviction(row, cfg) if row is not None else 50.0
        price = float(row["price"]) if row is not None else last_close.get(
            pos.symbol, pos.cost_basis)
        holdings.append({"symbol": pos.symbol, "conviction": conv,
                         "market_value": pos.qty * price})
    position_mv = sum(h["market_value"] for h in holdings)
    sleeve_equity = ledger.cash + position_mv

    held = set(ledger.positions)
    candidates = [{"symbol": r["symbol"], "conviction": _conviction(r, cfg)}
                  for r in ranked[:CANDIDATE_POOL] if r["symbol"] not in held]
    plan = plan_decisions(holdings, candidates, sleeve_equity,
                          SLEEVE_A_MAX_POSITIONS)

    queued = {s["symbol"] for s in pending_sells}
    for e in plan["exits"]:
        open_orders[:] = [o for o in open_orders if o.symbol != e["symbol"]]
        if e["symbol"] not in queued:
            pending_sells.append({"symbol": e["symbol"], "qty": None,
                                  "reason": e["reason"]})
            queued.add(e["symbol"])
    for t in plan["trims"]:
        if t["symbol"] in queued:
            continue
        ref = last_close.get(t["symbol"])
        if not ref:
            continue
        qty = int(t["sell_notional"] // ref)
        if qty > 0:
            pending_sells.append({"symbol": t["symbol"], "qty": qty,
                                  "reason": "risk_trim"})
            queued.add(t["symbol"])

    committed = sum(o.qty * o.limit for o in open_orders)
    invested = REGIME_INVESTED_FRACTION.get(regime, 0.7)
    deployable = max(0.0, invested * sleeve_equity - position_mv - committed)
    cash_remaining = max(0.0, ledger.cash - committed)
    ordered = {o.symbol for o in open_orders}

    for sym in plan["entry_queue"]:
        if sym in ordered or sym in queued:
            continue
        row = by_symbol[sym]
        state = extension_state(float(row["ext_atr"]))
        limit = entry_limit_price(state, float(row["price"]),
                                  float(row["sma20"]), float(row["atr"]))
        if limit <= 0:
            continue
        conv = _conviction(row, cfg)
        notional = size_entry(conv, sleeve_equity,
                              float(row["liquidity_adv_usd"] or 0.0),
                              float(row["atr_pct"]), deployable, cash_remaining)
        qty = int(notional // limit)
        if qty <= 0 or qty * limit < MIN_TRADE_NOTIONAL:
            continue
        ttl = entry_ttl_days(state)
        open_orders.append(LimitOrder(
            symbol=sym, qty=qty, limit=limit, atr=float(row["atr"]),
            placed=today.date(), expires=today.date() + timedelta(days=ttl),
            conviction=conv))
        spent = qty * limit
        deployable = max(0.0, deployable - spent)
        cash_remaining = max(0.0, cash_remaining - spent)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_backtest_simulator.py -q --no-cov`
Expected: 6 passed (module-scoped fixture runs the ~75-week sim once; the PIT test runs a second sim; allow ~1–2 min)

- [ ] **Step 5: Run the full backtest test suite together**

Run: `python3 -m pytest tests/test_backtest_ledger.py tests/test_backtest_fills.py tests/test_backtest_universe.py tests/test_backtest_data.py tests/test_backtest_metrics.py tests/test_backtest_simulator.py -q --no-cov`
Expected: all passed

- [ ] **Step 6: Commit**

```bash
git add execution/backtest/simulator.py tests/test_backtest_simulator.py
git commit -m "feat(backtest): event-loop simulator driving production funnel functions"
```

---

### Task 7: Baselines

**Files:**
- Create: `execution/backtest/baselines.py`
- Test: `tests/test_backtest_baselines.py`

**Interfaces:**
- Consumes: `eligible_asof`, `screen_row`, `rank_candidates`, `BacktestConfig`, constants `BENCHMARK`; `_NON_STOCK` and `ENTRY_TAGS` from `execution.backtest.simulator`.
- Produces: `spy_buy_hold(ohlcv, cfg) -> pd.Series`; `equal_weight_universe(ohlcv, cfg, pit=None, static_universe=None) -> pd.Series` (yearly rebalance); `naive_momentum(ohlcv, cfg, top_n=10, pit=None, static_universe=None) -> pd.Series` (weekly screen top-N, equal weight, no stops/sizing/regime). All daily equity curves starting at `cfg.starting_cash` on the same SPY calendar as `run_backtest`. `pit`/`static_universe` MUST be passed the same values as the base run — baselines on a different universe would invalidate every relative comparison.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_backtest_baselines.py
import numpy as np
import pandas as pd
import pytest

from execution.backtest.baselines import (
    equal_weight_universe, naive_momentum, spy_buy_hold,
)
from execution.backtest.simulator import BacktestConfig


def _make_df(closes, start="2019-01-01", vol=1_000_000):
    idx = pd.bdate_range(start, periods=len(closes))
    close = pd.Series(np.asarray(closes, dtype=float), index=idx)
    return pd.DataFrame({"Open": close.shift(1).fillna(close.iloc[0]),
                         "High": close * 1.01, "Low": close * 0.99,
                         "Close": close, "Volume": float(vol)}, index=idx)


CFG = BacktestConfig(start="2019-06-02", end="2020-06-01", starting_cash=100_000.0)


def _fixture():
    n = 400
    return {
        "AAA": _make_df(50 * 1.001 ** np.arange(n)),     # steady +0.1%/day
        "BBB": _make_df(np.full(n, 50.0)),               # flat
        "SPY": _make_df(300 * 1.0005 ** np.arange(n)),
    }


def test_spy_buy_hold_tracks_spy_exactly():
    data = _fixture()
    eq = spy_buy_hold(data, CFG)
    spy = data["SPY"].loc[CFG.start:CFG.end, "Close"]
    assert eq.iloc[0] == pytest.approx(100_000.0)
    assert eq.iloc[-1] / eq.iloc[0] == pytest.approx(spy.iloc[-1] / spy.iloc[0])


def test_equal_weight_is_mean_of_member_paths():
    # single-calendar-year window: no rebalance boundary, exact arithmetic
    data = _fixture()
    cfg1 = BacktestConfig(start="2019-04-15", end="2019-12-15",
                          starting_cash=100_000.0)
    eq = equal_weight_universe(data, cfg1)
    aaa = data["AAA"].loc[cfg1.start:cfg1.end, "Close"]
    ret_aaa = aaa.iloc[-1] / aaa.iloc[0] - 1.0
    # BBB is flat → portfolio return is exactly half of AAA's
    assert eq.iloc[-1] / eq.iloc[0] - 1.0 == pytest.approx(ret_aaa / 2, rel=1e-6)


def test_naive_momentum_prefers_the_trender():
    data = _fixture()
    eq = naive_momentum(data, CFG, top_n=1)
    ew = equal_weight_universe(data, CFG)
    assert eq.iloc[-1] > ew.iloc[-1]          # holds only AAA, beats the 50/50 mix


def test_baselines_share_the_spy_calendar():
    data = _fixture()
    cal = data["SPY"].loc[CFG.start:CFG.end].index
    for series in (spy_buy_hold(data, CFG), equal_weight_universe(data, CFG),
                   naive_momentum(data, CFG)):
        assert len(series) == len(cal)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_backtest_baselines.py -q --no-cov`
Expected: FAIL — `ModuleNotFoundError` on `execution.backtest.baselines`

- [ ] **Step 3: Implement**

```python
# execution/backtest/baselines.py
"""The three comparison baselines, on the identical universe and calendar.
(a) equal-weight universe, yearly rebalance; (b) naive momentum — same
screen top-N, equal weight, weekly rebalance, no stops/sizing/regime;
(c) SPY buy-and-hold, context only. Fractional shares are fine here —
benchmarks, not simulations of a broker."""
from typing import Dict, List

import pandas as pd

from typing import Optional, Set

from execution.constants import BENCHMARK
from execution.funnel.screen import rank_candidates, screen_row

from execution.backtest.simulator import ENTRY_TAGS, _NON_STOCK, BacktestConfig, _week_starts
from execution.backtest.universe import eligible_asof, members_asof


def _calendar(ohlcv: Dict[str, pd.DataFrame], cfg: BacktestConfig) -> pd.DatetimeIndex:
    return ohlcv[BENCHMARK].loc[cfg.start:cfg.end].index


def _allowed(pit, static_universe, asof) -> Optional[Set[str]]:
    if pit is None:
        return None
    return members_asof(pit, asof) | set(static_universe or ())


def spy_buy_hold(ohlcv: Dict[str, pd.DataFrame], cfg: BacktestConfig) -> pd.Series:
    spy = ohlcv[BENCHMARK].loc[cfg.start:cfg.end, "Close"]
    return cfg.starting_cash * spy / spy.iloc[0]


def _segment_curve(stocks: Dict[str, pd.DataFrame], members: List[str],
                   seg: pd.DatetimeIndex, start_value: float) -> pd.Series:
    """Equal-weight buy-and-hold across `members` over `seg` (daily curve).
    Members without a bar on seg[0] are dropped; prices forward-fill."""
    paths = []
    for sym in members:
        px = stocks[sym]["Close"].reindex(seg).ffill()
        if pd.isna(px.iloc[0]) or px.iloc[0] <= 0:
            continue
        paths.append(px / px.iloc[0])
    if not paths:
        return pd.Series(start_value, index=seg)
    return start_value * pd.concat(paths, axis=1).mean(axis=1)


def equal_weight_universe(ohlcv: Dict[str, pd.DataFrame], cfg: BacktestConfig,
                          pit=None, static_universe=None) -> pd.Series:
    cal = _calendar(ohlcv, cfg)
    stocks = {s: df for s, df in ohlcv.items() if s not in _NON_STOCK}
    parts: List[pd.Series] = []
    value = cfg.starting_cash
    for year, seg in cal.groupby(cal.year).items():
        seg = pd.DatetimeIndex(seg)
        members = eligible_asof(stocks, seg[0],
                                allowed=_allowed(pit, static_universe, seg[0]))
        curve = _segment_curve(stocks, members, seg, value)
        value = float(curve.iloc[-1])
        parts.append(curve)
    return pd.concat(parts)


def naive_momentum(ohlcv: Dict[str, pd.DataFrame], cfg: BacktestConfig,
                   top_n: int = 10, pit=None, static_universe=None) -> pd.Series:
    cal = _calendar(ohlcv, cfg)
    stocks = {s: df for s, df in ohlcv.items() if s not in _NON_STOCK}
    spy_all = ohlcv[BENCHMARK]["Close"]
    starts = sorted(_week_starts(cal))
    parts: List[pd.Series] = []
    value = cfg.starting_cash
    for i, ws in enumerate(starts):
        seg_end = starts[i + 1] if i + 1 < len(starts) else cal[-1]
        seg = cal[(cal >= ws) & (cal <= seg_end)] if i + 1 < len(starts) \
            else cal[cal >= ws]
        rows = []
        for sym in eligible_asof(stocks, ws,
                                 allowed=_allowed(pit, static_universe, ws)):
            row = screen_row(sym, stocks[sym].loc[:ws], spy_all.loc[:ws],
                             ENTRY_TAGS, [], [], None)
            if row is not None:
                rows.append(row)
        members = [r["symbol"] for r in rank_candidates(rows)[:top_n]]
        curve = _segment_curve(stocks, members, pd.DatetimeIndex(seg), value)
        value = float(curve.iloc[-1])
        parts.append(curve.iloc[:-1] if i + 1 < len(starts) else curve)
    return pd.concat(parts)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_backtest_baselines.py -q --no-cov`
Expected: 4 passed

- [ ] **Step 5: Commit**

```bash
git add execution/backtest/baselines.py tests/test_backtest_baselines.py
git commit -m "feat(backtest): equal-weight, naive-momentum, and SPY baselines"
```

---

### Task 8: Report & gate verdict

**Files:**
- Create: `execution/backtest/report.py`
- Test: `tests/test_backtest_report.py`

**Interfaces:**
- Consumes: metric dicts from Task 5.
- Produces: `gate_verdict(base, naive, yearly_outperf, sweep_edges) -> dict` with boolean keys `drawdown_ok, risk_adjusted_ok, robust_ok` and `passed`; `render_report(run_meta, base, baselines, yearly_outperf, sweep_rows, verdict) -> str` (markdown); `write_report(out_dir, markdown, payload) -> Path` (writes `report.md` + `metrics.json`, creates dir). `sweep_edges: List[float]` are Sharpe edges vs naive for each perturbation run; `sweep_rows: List[dict]` are `{"name", "value", "cagr", "max_drawdown", "sharpe", "sharpe_edge"}`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_backtest_report.py
import json

from execution.backtest.report import gate_verdict, render_report, write_report

BASE = {"cagr": 0.12, "max_drawdown": -0.20, "sharpe": 0.9, "mar": 0.6,
        "yearly_returns": {"2020": 0.1}}
NAIVE = {"cagr": 0.14, "max_drawdown": -0.30, "sharpe": 0.8, "mar": 0.47,
         "yearly_returns": {"2020": 0.2}}


def test_gate_passes_when_all_criteria_met():
    v = gate_verdict(BASE, NAIVE, {"2020": 0.04, "2021": 0.05, "2022": 0.03},
                     sweep_edges=[0.05, 0.02, 0.01])
    assert v == {"drawdown_ok": True, "risk_adjusted_ok": True,
                 "robust_ok": True, "passed": True}


def test_gate_fails_on_drawdown():
    base = dict(BASE, max_drawdown=-0.29)          # not ≤ 0.8 × 0.30
    assert not gate_verdict(base, NAIVE, {"2020": 0.1, "2021": 0.1},
                            sweep_edges=[0.1])["drawdown_ok"]


def test_gate_fails_on_risk_adjusted():
    base = dict(BASE, sharpe=0.7)
    assert not gate_verdict(base, NAIVE, {"2020": 0.1, "2021": 0.1},
                            sweep_edges=[0.1])["risk_adjusted_ok"]


def test_gate_fails_when_one_year_dominates_or_edge_flips():
    v = gate_verdict(BASE, NAIVE, {"2020": 0.09, "2021": 0.01},
                     sweep_edges=[0.05])
    assert not v["robust_ok"]                       # 2020 is 90% of the edge
    v = gate_verdict(BASE, NAIVE, {"2020": 0.05, "2021": 0.05},
                     sweep_edges=[0.05, -0.01])
    assert not v["robust_ok"]                       # a perturbation flips sign
    v = gate_verdict(BASE, NAIVE, {"2020": -0.05, "2021": 0.01},
                     sweep_edges=[0.05])
    assert not v["robust_ok"]                       # negative total edge


def test_render_and_write_report(tmp_path):
    yearly = {"2020": 0.04, "2021": 0.05, "2022": 0.03}   # no year > 50% of total
    verdict = gate_verdict(BASE, NAIVE, yearly, sweep_edges=[0.05])
    md = render_report(
        {"window": "2015-01-01 → 2026-06-30", "universe_size": 1400},
        BASE, {"naive_momentum": NAIVE, "equal_weight": NAIVE, "spy": NAIVE},
        yearly,
        [{"name": "stop_mult", "value": 2.0, "cagr": 0.1,
          "max_drawdown": -0.22, "sharpe": 0.85, "sharpe_edge": 0.05}],
        verdict)
    assert "GATE" in md and "survivorship" in md.lower()
    out = write_report(tmp_path / "run1", md, {"base": BASE, "verdict": verdict})
    assert (out / "report.md").read_text().startswith("#")
    assert json.loads((out / "metrics.json").read_text())["verdict"]["passed"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_backtest_report.py -q --no-cov`
Expected: FAIL — `ModuleNotFoundError` on `execution.backtest.report`

- [ ] **Step 3: Implement**

```python
# execution/backtest/report.py
"""Gate verdict (the three pre-committed criteria from the 3D spec) and
the markdown/JSON report. The criteria are code, not prose — they cannot
be reinterpreted after results are seen."""
import json
from pathlib import Path
from typing import Dict, List

DISCLAIMER = (
    "> **Survivorship bias:** the large-cap set uses point-in-time S&P 500 "
    "membership, clean only to the extent yfinance still serves delisted "
    "tickers (coverage reported in the run metadata); the mid/small set is "
    "today's IJH/IJR membership held fixed backwards, so dead companies are "
    "absent and absolute returns are inflated. Every baseline shares the "
    "same universe — only relative conclusions are meaningful. The mcap "
    "floor is not applied historically (no point-in-time share counts); ADV "
    "is the liquidity proxy. Guardrails (theme/sector caps) are omitted — "
    "inert without historical tags."
)


def gate_verdict(base: dict, naive: dict, yearly_outperf: Dict[str, float],
                 sweep_edges: List[float]) -> dict:
    drawdown_ok = abs(base["max_drawdown"]) <= 0.8 * abs(naive["max_drawdown"])
    risk_adjusted_ok = (base["sharpe"] >= naive["sharpe"]
                        and base["mar"] >= naive["mar"])
    total = sum(yearly_outperf.values())
    robust_ok = (total > 0
                 and max(yearly_outperf.values()) <= 0.5 * total
                 and all(e > 0 for e in sweep_edges))
    return {"drawdown_ok": drawdown_ok, "risk_adjusted_ok": risk_adjusted_ok,
            "robust_ok": robust_ok,
            "passed": drawdown_ok and risk_adjusted_ok and robust_ok}


def _metrics_row(name: str, m: dict) -> str:
    return (f"| {name} | {m['cagr']:+.2%} | {m['max_drawdown']:.2%} "
            f"| {m['sharpe']:.2f} | {m['mar']:.2f} |")


def render_report(run_meta: dict, base: dict, baselines: Dict[str, dict],
                  yearly_outperf: Dict[str, float], sweep_rows: List[dict],
                  verdict: dict) -> str:
    lines = ["# Sleeve A Tier 2 Backtest — Gate Report", ""]
    lines += [f"- **{k}:** {v}" for k, v in run_meta.items()]
    lines += ["", DISCLAIMER, "", "## GATE VERDICT", ""]
    labels = {
        "drawdown_ok": "1. Max drawdown ≤ 0.8 × naive momentum's",
        "risk_adjusted_ok": "2. Sharpe and MAR ≥ naive momentum's",
        "robust_ok": "3. No year > 50% of edge; all perturbations keep a positive Sharpe edge",
    }
    for key, label in labels.items():
        lines.append(f"- {'PASS' if verdict[key] else 'FAIL'} — {label}")
    lines += ["", f"**Overall: {'PASS' if verdict['passed'] else 'FAIL'}**", ""]

    lines += ["## Performance", "", "| run | CAGR | maxDD | Sharpe | MAR |",
              "|---|---|---|---|---|", _metrics_row("**funnel (base)**", base)]
    lines += [_metrics_row(name, m) for name, m in baselines.items()]

    lines += ["", "## Yearly returns (funnel base)", "",
              "| year | return |", "|---|---|"]
    lines += [f"| {y} | {r:+.2%} |" for y, r in sorted(
        base["yearly_returns"].items())]

    lines += ["", "## Yearly log outperformance vs naive momentum", "",
              "| year | edge |", "|---|---|"]
    lines += [f"| {y} | {v:+.4f} |" for y, v in sorted(yearly_outperf.items())]

    if sweep_rows:
        lines += ["", "## Sensitivity sweep", "",
                  "| constant | value | CAGR | maxDD | Sharpe | Sharpe edge vs naive |",
                  "|---|---|---|---|---|---|"]
        lines += [(f"| {r['name']} | {r['value']} | {r['cagr']:+.2%} "
                   f"| {r['max_drawdown']:.2%} | {r['sharpe']:.2f} "
                   f"| {r['sharpe_edge']:+.2f} |") for r in sweep_rows]
    return "\n".join(lines) + "\n"


def write_report(out_dir: Path, markdown: str, payload: dict) -> Path:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "report.md").write_text(markdown)
    (out_dir / "metrics.json").write_text(json.dumps(payload, indent=2, default=str))
    return out_dir
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_backtest_report.py -q --no-cov`
Expected: 5 passed

- [ ] **Step 5: Commit**

```bash
git add execution/backtest/report.py tests/test_backtest_report.py
git commit -m "feat(backtest): pre-committed gate verdict and markdown report"
```

---

### Task 9: Sensitivity sweep

**Files:**
- Create: `execution/backtest/sensitivity.py`
- Test: `tests/test_backtest_sensitivity.py`

**Interfaces:**
- Consumes: `run_backtest`, `BacktestConfig`, `compute_metrics`.
- Produces: `patched(module_path, attr, value)` context manager; `SWEEP_SPECS: List[dict]` — each `{"name", "module", "attr", "values"}` (attr may be a tuple for the band pair); `run_sweep(ohlcv, cfg, naive_sharpe, pit=None, static_universe=None) -> List[dict]` returning one row per perturbation run (`{"name", "value", "cagr", "max_drawdown", "sharpe", "sharpe_edge"}`) plus a final `flat_conviction_60` row. `pit`/`static_universe` pass through to every `run_backtest` call.

**Sweep values (±20% of production constants):** `TRAILING_STOP_ATR_MULT` 2.5 → [2.0, 3.0] on `inngest_app.functions.execution_daily`; `EXTENSION_ATR_LIMIT` 1.5 → [1.2, 1.8] on `execution.funnel.entries`; `OUTCOMPETE_MARGIN` 10.0 → [8.0, 12.0] on `execution.funnel.decisions`; `(ENTRY_WEIGHT_MIN, ENTRY_WEIGHT_MAX)` (0.03, 0.12) → [(0.024, 0.096), (0.036, 0.144)] on `execution.funnel.entries`. Patch the *module attribute* (each module did `from execution.constants import X`, so the name lives in the consuming module's namespace).

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_backtest_sensitivity.py
import importlib

import numpy as np
import pandas as pd

from execution.backtest.sensitivity import SWEEP_SPECS, patched, run_sweep
from execution.backtest.simulator import BacktestConfig


def test_patched_sets_and_restores():
    mod = importlib.import_module("execution.funnel.entries")
    original = mod.EXTENSION_ATR_LIMIT
    with patched("execution.funnel.entries", "EXTENSION_ATR_LIMIT", 9.9):
        assert mod.EXTENSION_ATR_LIMIT == 9.9
    assert mod.EXTENSION_ATR_LIMIT == original


def test_patched_handles_tuple_attrs():
    mod = importlib.import_module("execution.funnel.entries")
    orig = (mod.ENTRY_WEIGHT_MIN, mod.ENTRY_WEIGHT_MAX)
    with patched("execution.funnel.entries",
                 ("ENTRY_WEIGHT_MIN", "ENTRY_WEIGHT_MAX"), (0.05, 0.10)):
        assert (mod.ENTRY_WEIGHT_MIN, mod.ENTRY_WEIGHT_MAX) == (0.05, 0.10)
    assert (mod.ENTRY_WEIGHT_MIN, mod.ENTRY_WEIGHT_MAX) == orig


def test_sweep_specs_cover_the_gate_constants():
    names = {s["name"] for s in SWEEP_SPECS}
    assert names == {"stop_mult", "extension_limit", "outcompete_margin", "entry_band"}
    assert all(len(s["values"]) == 2 for s in SWEEP_SPECS)


def test_run_sweep_produces_a_row_per_run(monkeypatch):
    # stub run_backtest: constant equity curve → deterministic metrics
    import execution.backtest.sensitivity as sens

    idx = pd.bdate_range("2020-01-01", periods=300)
    fake = pd.Series(100_000 * 1.0005 ** np.arange(300), index=idx)

    class R:
        equity = fake
        journal = []
        weeks = 60
    monkeypatch.setattr(sens, "run_backtest", lambda ohlcv, cfg, **kw: R())

    rows = run_sweep({}, BacktestConfig(), naive_sharpe=0.5)
    # 4 specs × 2 values + flat_conviction_60 = 9 rows
    assert len(rows) == 9
    assert rows[-1]["name"] == "flat_conviction_60"
    assert all("sharpe_edge" in r for r in rows)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_backtest_sensitivity.py -q --no-cov`
Expected: FAIL — `ModuleNotFoundError` on `execution.backtest.sensitivity`

- [ ] **Step 3: Implement**

```python
# execution/backtest/sensitivity.py
"""Constant-perturbation sweep. Production modules are patched in place
(each consuming module imported the constant by name) and always restored —
the same pattern the unit-test suite uses. Production code is untouched."""
import importlib
from contextlib import contextmanager
from dataclasses import replace
from typing import Dict, List, Union

from execution.backtest.metrics import compute_metrics
from execution.backtest.simulator import BacktestConfig, run_backtest

SWEEP_SPECS: List[dict] = [
    {"name": "stop_mult", "module": "inngest_app.functions.execution_daily",
     "attr": "TRAILING_STOP_ATR_MULT", "values": [2.0, 3.0]},
    {"name": "extension_limit", "module": "execution.funnel.entries",
     "attr": "EXTENSION_ATR_LIMIT", "values": [1.2, 1.8]},
    {"name": "outcompete_margin", "module": "execution.funnel.decisions",
     "attr": "OUTCOMPETE_MARGIN", "values": [8.0, 12.0]},
    {"name": "entry_band", "module": "execution.funnel.entries",
     "attr": ("ENTRY_WEIGHT_MIN", "ENTRY_WEIGHT_MAX"),
     "values": [(0.024, 0.096), (0.036, 0.144)]},
]


@contextmanager
def patched(module_path: str, attr: Union[str, tuple], value):
    mod = importlib.import_module(module_path)
    attrs = attr if isinstance(attr, tuple) else (attr,)
    values = value if isinstance(attr, tuple) else (value,)
    originals = [getattr(mod, a) for a in attrs]
    try:
        for a, v in zip(attrs, values):
            setattr(mod, a, v)
        yield
    finally:
        for a, v in zip(attrs, originals):
            setattr(mod, a, v)


def _row(name: str, value, equity, naive_sharpe: float) -> Dict:
    m = compute_metrics(equity)
    return {"name": name, "value": value, "cagr": m["cagr"],
            "max_drawdown": m["max_drawdown"], "sharpe": m["sharpe"],
            "sharpe_edge": m["sharpe"] - naive_sharpe}


def run_sweep(ohlcv, cfg: BacktestConfig, naive_sharpe: float,
              pit=None, static_universe=None) -> List[dict]:
    rows: List[dict] = []
    for spec in SWEEP_SPECS:
        for value in spec["values"]:
            with patched(spec["module"], spec["attr"], value):
                result = run_backtest(ohlcv, cfg, pit=pit,
                                      static_universe=static_universe)
            rows.append(_row(spec["name"], value, result.equity, naive_sharpe))
    flat = run_backtest(ohlcv, replace(cfg, flat_conviction=60.0),
                        pit=pit, static_universe=static_universe)
    rows.append(_row("flat_conviction_60", 60.0, flat.equity, naive_sharpe))
    return rows
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_backtest_sensitivity.py -q --no-cov`
Expected: 4 passed

- [ ] **Step 5: Commit**

```bash
git add execution/backtest/sensitivity.py tests/test_backtest_sensitivity.py
git commit -m "feat(backtest): constant-perturbation sweep with patch/restore"
```

---

### Task 10: CLI + gitignore

**Files:**
- Create: `scripts/backtest_sleeve_a.py`
- Modify: `.gitignore` (append `data/backtest/` and `reports/backtests/`)
- Test: `tests/test_backtest_cli.py` (arg parsing only — the heavy paths are already covered)

**Interfaces:**
- Consumes: everything above.
- Produces: `python3 scripts/backtest_sleeve_a.py fetch|run|sweep`. `fetch` downloads the PIT S&P 500 constituents CSV (reusing `download_constituents_csv` from `scripts.backtest.data.sp500_constituents`) and the iShares CSVs (both best effort — prints manual instructions on failure), then OHLCV for the union; `run` = base backtest + baselines + report (no sweep, sweep_edges=[]); `sweep` = base + baselines + full sensitivity suite + gated report. Both `run`/`sweep` load the PIT frame when its CSV exists (warn + proceed iShares-only when it doesn't) and pass `pit`/`static_universe` identically to the base run, every baseline, and the sweep. PIT coverage (% of PIT tickers with cached OHLCV) goes into run metadata. `build_parser() -> argparse.ArgumentParser` is importable for the test.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_backtest_cli.py
from scripts.backtest_sleeve_a import build_parser


def test_parser_subcommands_and_defaults():
    p = build_parser()
    ns = p.parse_args(["run"])
    assert ns.command == "run"
    assert ns.start == "2015-01-01" and ns.end == "2026-06-30"
    assert ns.cash == 100_000.0
    ns = p.parse_args(["sweep", "--start", "2018-01-01", "--cash", "50000"])
    assert (ns.command, ns.start, ns.cash) == ("sweep", "2018-01-01", 50_000.0)
    assert build_parser().parse_args(["fetch"]).command == "fetch"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_backtest_cli.py -q --no-cov`
Expected: FAIL — `ModuleNotFoundError: No module named 'scripts.backtest_sleeve_a'` (create `scripts/__init__.py` if scripts/ lacks one and the import fails for that reason)

- [ ] **Step 3: Implement**

```python
# scripts/backtest_sleeve_a.py
"""Phase 3D Tier 2 backtest CLI. Local only — never Railway, never cron.

  python3 scripts/backtest_sleeve_a.py fetch   # universe CSVs + OHLCV cache
  python3 scripts/backtest_sleeve_a.py run     # base run + baselines + report
  python3 scripts/backtest_sleeve_a.py sweep   # + sensitivity suite + gate
"""
import argparse
import logging
import sys
import urllib.request
from datetime import datetime
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from execution.backtest.baselines import (          # noqa: E402
    equal_weight_universe, naive_momentum, spy_buy_hold,
)
from execution.backtest.data import (               # noqa: E402
    MARKET_SYMBOLS, fetch_ohlcv, load_ohlcv,
)
from execution.backtest.metrics import (            # noqa: E402
    compute_metrics, yearly_log_outperformance,
)
from execution.backtest.report import (             # noqa: E402
    gate_verdict, render_report, write_report,
)
from execution.backtest.sensitivity import run_sweep     # noqa: E402
from execution.backtest.simulator import BacktestConfig, run_backtest  # noqa: E402
from execution.backtest.universe import (                # noqa: E402
    load_pit_membership, load_universe,
)
from scripts.backtest.data.sp500_constituents import (   # noqa: E402
    download_constituents_csv,
)

DATA_DIR = REPO / "data" / "backtest"
OHLCV_DIR = DATA_DIR / "ohlcv"
UNIVERSE_DIR = DATA_DIR / "universe"
PIT_CSV = DATA_DIR / "sp500_constituents.csv"
REPORTS_DIR = REPO / "reports" / "backtests"

ISHARES = {
    "IVV": "https://www.ishares.com/us/products/239726/ishares-core-sp-500-etf/1467271812596.ajax?fileType=csv&fileName=IVV_holdings&dataType=fund",
    "IJH": "https://www.ishares.com/us/products/239763/ishares-core-sp-midcap-etf/1467271812596.ajax?fileType=csv&fileName=IJH_holdings&dataType=fund",
    "IJR": "https://www.ishares.com/us/products/239774/ishares-core-sp-smallcap-etf/1467271812596.ajax?fileType=csv&fileName=IJR_holdings&dataType=fund",
}


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Sleeve A Tier 2 backtest")
    sub = p.add_subparsers(dest="command", required=True)
    for name in ("fetch", "run", "sweep"):
        s = sub.add_parser(name)
        s.add_argument("--start", default="2015-01-01")
        s.add_argument("--end", default="2026-06-30")
        s.add_argument("--cash", type=float, default=100_000.0)
    return p


def cmd_fetch(ns) -> None:
    UNIVERSE_DIR.mkdir(parents=True, exist_ok=True)
    if not PIT_CSV.exists():
        try:
            download_constituents_csv(PIT_CSV)
            print("downloaded PIT S&P 500 constituents")
        except Exception as exc:  # noqa: BLE001
            print(f"FAILED to download PIT constituents ({exc}).\n"
                  f"  Run `python3 -m scripts.backtest.data.sp500_constituents "
                  f"--download` or save the canonical CSV as {PIT_CSV}.\n"
                  f"  Proceeding survivorship-biased (iShares only).")
    for name, url in ISHARES.items():
        dest = UNIVERSE_DIR / f"{name}_holdings.csv"
        if dest.exists():
            continue
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            dest.write_bytes(urllib.request.urlopen(req, timeout=60).read())
            print(f"downloaded {name} holdings")
        except Exception as exc:  # noqa: BLE001
            print(f"FAILED to download {name} ({exc}).\n"
                  f"  Download the holdings CSV manually from ishares.com "
                  f"and save it as {dest}")
    universe = set(load_universe(UNIVERSE_DIR))
    if PIT_CSV.exists():
        universe |= set(load_pit_membership(PIT_CSV)["ticker"])
    if not universe:
        sys.exit("no universe sources — fetch aborted")
    print(f"universe: {len(universe)} symbols; fetching OHLCV "
          f"(first run takes a while)…")
    fetch_ohlcv(list(MARKET_SYMBOLS) + sorted(universe), OHLCV_DIR)
    print(f"cache: {len(list(OHLCV_DIR.glob('*.parquet')))} parquet files")


def _load_all(ns):
    ohlcv = load_ohlcv(OHLCV_DIR)
    if "SPY" not in ohlcv:
        sys.exit("no cached data — run `fetch` first")
    cfg = BacktestConfig(start=ns.start, end=ns.end, starting_cash=ns.cash)
    pit = load_pit_membership(PIT_CSV) if PIT_CSV.exists() else None
    static = load_universe(UNIVERSE_DIR)
    if pit is None:
        print("WARNING: no PIT constituents CSV — survivorship-biased run")
    return ohlcv, cfg, pit, static


def cmd_run(ns, with_sweep: bool) -> None:
    ohlcv, cfg, pit, static = _load_all(ns)
    pit_coverage = None
    if pit is not None:
        pit_syms = set(pit["ticker"])
        pit_coverage = round(100.0 * len(pit_syms & set(ohlcv)) / len(pit_syms), 1)
    print(f"universe: {len(ohlcv)} symbols with data; running base backtest…")
    base_res = run_backtest(ohlcv, cfg, pit=pit, static_universe=static)
    base = compute_metrics(base_res.equity)
    print("base done; baselines…")
    naive_eq = naive_momentum(ohlcv, cfg, pit=pit, static_universe=static)
    baselines = {
        "naive_momentum": compute_metrics(naive_eq),
        "equal_weight": compute_metrics(
            equal_weight_universe(ohlcv, cfg, pit=pit, static_universe=static)),
        "spy": compute_metrics(spy_buy_hold(ohlcv, cfg)),
    }
    yearly = yearly_log_outperformance(base_res.equity, naive_eq)
    sweep_rows = []
    if with_sweep:
        print("sensitivity sweep (9 full runs)…")
        sweep_rows = run_sweep(ohlcv, cfg, baselines["naive_momentum"]["sharpe"],
                               pit=pit, static_universe=static)
    edges = [r["sharpe_edge"] for r in sweep_rows if r["name"] != "flat_conviction_60"]
    verdict = gate_verdict(base, baselines["naive_momentum"], yearly, edges)
    meta = {"window": f"{cfg.start} → {cfg.end}", "starting_cash": cfg.starting_cash,
            "symbols": len(ohlcv), "weeks": base_res.weeks,
            "trades": len(base_res.journal),
            "pit_coverage_pct": pit_coverage if pit_coverage is not None
            else "n/a — survivorship-biased run",
            "sweep": "yes" if with_sweep else "no (run `sweep` for the full gate)"}
    md = render_report(meta, base, baselines, yearly, sweep_rows, verdict)
    out = write_report(REPORTS_DIR / datetime.now().strftime("%Y%m%d-%H%M%S"),
                       md, {"meta": meta, "base": base, "baselines": baselines,
                            "yearly_log_outperformance": yearly,
                            "sweep": sweep_rows, "verdict": verdict})
    print(md)
    print(f"written: {out}/report.md")


def main() -> None:
    logging.basicConfig(level=logging.WARNING)
    ns = build_parser().parse_args()
    if ns.command == "fetch":
        cmd_fetch(ns)
    else:
        cmd_run(ns, with_sweep=(ns.command == "sweep"))


if __name__ == "__main__":
    main()
```

Append to `.gitignore`:

```
# Tier 2 backtest artifacts
data/backtest/
reports/backtests/
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_backtest_cli.py -q --no-cov`
Expected: 1 passed

- [ ] **Step 5: Run the entire backtest suite**

Run: `python3 -m pytest tests/test_backtest_*.py -q --no-cov`
Expected: all ~32 tests pass

- [ ] **Step 6: Commit**

```bash
git add scripts/backtest_sleeve_a.py tests/test_backtest_cli.py .gitignore
git commit -m "feat(backtest): CLI (fetch/run/sweep) and artifact gitignore"
```

---

### Task 11: First real run (verification, not code)

**Files:** none created — this validates the harness end-to-end.

- [ ] **Step 1: Fetch data**

Run: `python3 scripts/backtest_sleeve_a.py fetch`
Expected: PIT constituents CSV downloads (~1,100 tickers incl. dead ones), universe of roughly 2,200–2,600 symbols after the IJH/IJR union; parquet cache fills (20–40 min on first run). Many delisted PIT tickers WILL fail the yfinance download — that is the expected coverage gap, logged per symbol and quantified as `pit_coverage_pct` in the run.

- [ ] **Step 2: Base run**

Run: `python3 scripts/backtest_sleeve_a.py run`
Expected: report prints with base + three baselines; sanity-check that trades number in the hundreds, equity curve spans 2015→2026, and the report carries the survivorship disclaimer.

- [ ] **Step 3: Full sweep + gate**

Run: `python3 scripts/backtest_sleeve_a.py sweep`
Expected: 9 additional runs; final report with GATE VERDICT. **Do not tune constants to make the gate pass** — report the verdict as-is to the user either way.

- [ ] **Step 4: Commit nothing** — run artifacts are gitignored. Report findings to the user.

---

## Self-review notes

- **Spec coverage:** hybrid universe incl. PIT S&P 500 membership + coverage measurement (T3, T10), conviction stand-in + flat variant (T6, T9), window/cadence (T6), hybrid architecture + fidelity rule (T6 imports, never re-implements), fill semantics incl. whole shares/gap-down/slippage (T2, T6), delisting sweep (T6), baselines on the identical universe (T7), metrics (T5), pre-committed gate (T8), sensitivity ±20% (T9), CLI + gitignore (T10), first real run (T11). Guardrail omission and the two-tier survivorship story are disclosed in the report (T8 DISCLAIMER).
- **Known simplification:** baselines use fractional shares and no slippage on rebalances — they are benchmarks, not broker simulations; noted in `baselines.py` docstring.
- **Type consistency:** journal rows always `{"date","side","symbol","qty","price","reason"}`; sells with `qty: None` mean full exit and are resolved to the held qty at execution; `sweep_rows` shape matches between `sensitivity._row` and `report.render_report`.
