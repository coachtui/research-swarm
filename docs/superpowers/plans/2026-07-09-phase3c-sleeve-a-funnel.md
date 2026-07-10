# Phase 3C — Sleeve A Funnel + Small-Cap Guardrails (Shadow Mode) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the complete Sleeve A candidate funnel — dynamic universe, free screen, two-tier commissioned research, conviction ranking, guarded entries/exits — running weekly in shadow mode (no order reaches Alpaca; Phase 3D flips it live via a broker-client swap).

**Architecture:** New `execution/funnel/` package of pure functions + one new Inngest cron (`sleeve-a-funnel`, Mon 16:00 UTC) + new Sleeve A duties on the existing `execution_daily` cron. Shadow execution via a `ShadowBrokerClient` that satisfies the same result shapes as `AlpacaPaperClient` and fills standing limit orders against real daily bars. Light research runs import swarm pure functions (never copy); full runs reuse the exact tiered-batch path (`run_stock_analysis` + `WeeklySignalService.upgrade_to_full`).

**Tech Stack:** Python 3.9+ (`python3` — bare `python` not on PATH), prisma-client-py, inngest-py 0.5.x, yfinance, pandas, anthropic SDK, pytest.

**Spec:** docs/superpowers/specs/2026-07-09-phase3c-sleeve-a-funnel-design.md (owner-approved; authoritative on any conflict).

## Global Constraints

- Branch: `autopilot-phase3c` off `main`. TDD every task: failing test → implement → pass → commit.
- **Shadow mode:** nothing in this plan may submit an order to Alpaca for Sleeve A. Sleeve A's broker is `ShadowBrokerClient` only.
- **Sleeve B untouched:** zero edits to `execution/engine/sleeve_b.py`, `execution/engine/orders.py`, `execution/indicators/{regime,breadth,sector_strength}.py`, `inngest_app/functions/execution_weekly.py`. Task 14 enforces this.
- **Degrade, never block:** any per-name failure skips the name + journals; any pass-level failure journals `engine_failure` and returns; the cron never raises out.
- **Journal writes** go through `execution.reporting.write_report` (never raises). New types added in Task 11.
- **Inngest rules (hard-won):** `step.send_event` never wrapped in `step.run`; paid/analyze and persist are SEPARATE steps; single `ctx: inngest.Context` arg; `inngest.TriggerCron`; guarded registration (module exports `None` when SDK absent).
- **prisma-client-py Json rule:** OMIT `None` Json fields on create/update (never pass bare `None`).
- **Migrations:** hand-write SQL + `python3 -m prisma migrate deploy` (bundled python CLI; `migrate dev` is broken in this repo — see memory `prisma-migrate-dev-broken`).
- **Test infra:** `python3 -m pytest`; `tests/conftest.py` installs a MagicMock `prisma` stub only when the real client is unimportable; import `market_data_client` via `importlib.import_module("research_swarm.data.market_data_client")` in tests (the package `__init__` shadows the module name with a singleton instance).
- **Sync-blocking calls** (yfinance, data clients, LLM SDK) inside async crons: wrap in `asyncio.to_thread`.
- Constants exactly as in spec §13 (Task 1). Tuning = constants change + spec note, never inline literals.

## File Map

**Create:**
- `db/migrations/20260709000003_sleeve_a_funnel/migration.sql` — 3 ALTER TABLEs
- `execution/funnel/__init__.py`
- `execution/funnel/universe.py` — merge/tag sources, floors, industry-ETF holdings fetch
- `execution/funnel/screen.py` — ATR, screen scores, light-run slot selection
- `execution/funnel/light_runner.py` — numbers-only research run + `engine_light` persist
- `execution/funnel/conviction.py` — the conviction formula (pure)
- `execution/funnel/entries.py` — extension check, limit pricing, sizing ceilings (pure)
- `execution/funnel/decisions.py` — weekly exit/entry planner (pure)
- `execution/funnel/research_budget.py` — DB-backed budget counts + full-run handshake
- `execution/broker/shadow_client.py` — ShadowBrokerClient + fill/expiry evaluation
- `inngest_app/functions/sleeve_a_funnel.py` — the Monday cron
- `tests/test_funnel_universe.py`, `tests/test_funnel_screen.py`, `tests/test_funnel_light_runner.py`, `tests/test_funnel_conviction.py`, `tests/test_funnel_entries.py`, `tests/test_funnel_decisions.py`, `tests/test_funnel_budget.py`, `tests/test_shadow_client.py`, `tests/test_funnel_guardrails.py`, `tests/test_sleeve_a_funnel_cron.py`, `tests/test_sleeve_a_daily.py`, `tests/test_phase3c_isolation.py`

**Modify:**
- `db/schema.prisma` — EnginePosition +5 cols, EngineTrade +2 cols, SleeveState +1 col
- `execution/constants.py` — Phase 3C block
- `execution/reporting.py` — new REPORT_TYPES
- `execution/engine/guardrails.py` — `enforce_funnel_guardrails` (new function; existing `enforce_guardrails` untouched)
- `execution/market_data.py` — `fetch_ohlcv_batch`
- `execution/sleeve_service.py` — `init_sleeve_state` gains `mode`; `get_sleeve_state` unchanged
- `inngest_app/functions/execution_daily.py` — Sleeve A steps (fills, stops, snapshot, breaker)
- `inngest_app/index.py` — register `sleeve_a_funnel` (7 active functions)
- `tests/test_inngest_registration.py` — count 6 → 7

---

### Task 1: Constants, schema, migration

**Files:**
- Modify: `execution/constants.py`, `db/schema.prisma`
- Create: `db/migrations/20260709000003_sleeve_a_funnel/migration.sql`
- Test: `tests/test_funnel_constants.py`

**Interfaces:**
- Produces: every constant below (later tasks import from `execution.constants`); columns `EnginePosition.{convictionScore,stopPrice,highWaterClose,sourceTags,reportRef}`, `EngineTrade.{limitPrice,expiresAt}`, `SleeveState.mode`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_funnel_constants.py
"""Phase 3C constants exist and are internally consistent."""
from execution import constants as c


def test_funnel_constants_exist_and_cohere():
    assert c.SLEEVE_A == "A"
    assert c.SLEEVE_A_FRACTION == 0.70
    assert 0 < c.ENTRY_WEIGHT_MIN < c.ENTRY_WEIGHT_MAX < c.RISK_TRIM_CEILING
    assert c.RISK_TRIM_TARGET == c.ENTRY_WEIGHT_MAX
    assert c.SLEEVE_A_TARGET_POSITIONS <= c.SLEEVE_A_MAX_POSITIONS
    assert c.LIGHT_RUNS_PER_WEEK > c.FULL_RUNS_PER_WEEK
    assert c.EXTENSION_ATR_LIMIT > 0 and c.TRAILING_STOP_ATR_MULT > c.EXTENSION_ATR_LIMIT
    assert 0 < c.ADV_POSITION_CAP_PCT < 0.05
    assert 0 < c.VOL_CEILING_SLEEVE_RISK < 0.02
    assert c.FUNNEL_MCAP_FLOOR >= c.THEME_MCAP_FLOOR_USD
    assert abs(sum(c.CONVICTION_WEIGHTS.values()) - 1.0) < 1e-9
    assert abs(sum(c.SCREEN_WEIGHTS.values()) - 1.0) < 1e-9
    assert 0 < c.SMALL_CAP_HAIRCUT_MIN_MULT < 1.0
    assert 0 < c.STALENESS_DECAY_PER_WEEK < 0.1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_funnel_constants.py -v`
Expected: FAIL with `AttributeError: ... has no attribute 'SLEEVE_A'`

- [ ] **Step 3: Append the Phase 3C block to `execution/constants.py`**

```python
# ── Phase 3C: Sleeve A funnel + small-cap guardrails (SHADOW MODE) ──────────
# Spec: docs/superpowers/specs/2026-07-09-phase3c-sleeve-a-funnel-design.md
# Sleeve A places NO real orders until the Phase 3D backtest gate flips it.
SLEEVE_A = "A"
SLEEVE_A_FRACTION = 0.70            # share of account equity Sleeve A manages
SLEEVE_A_TARGET_POSITIONS = 10      # intended book shape — NEVER a forcing rule
SLEEVE_A_MAX_POSITIONS = 15         # hard cap
ENTRY_WEIGHT_MIN = 0.03             # conviction band at entry (of sleeve equity)
ENTRY_WEIGHT_MAX = 0.12
RISK_TRIM_CEILING = 0.20            # only above this is a winner ever trimmed…
RISK_TRIM_TARGET = 0.12             # …back to here; journaled risk_trim, not a signal

LIGHT_RUNS_PER_WEEK = 20            # numbers-only runs (~$0.10–0.15 each)
FULL_RUNS_PER_WEEK = 2              # entry handshake budget (~$0.51 avg each)
HOLDING_STALE_WEEKS = 6             # holding report older than this claims a light slot
FRESH_REPORT_DAYS = 7               # reports younger than this ride free

EXTENSION_ATR_LIMIT = 1.5           # >this many ATRs above 20d SMA ⇒ "extended"
PATIENT_LIMIT_TTL_WEEKS = 2         # extended entries wait this long for a pullback
TRAILING_STOP_ATR_MULT = 2.5        # stop = high-water close − this × ATR
ADV_POSITION_CAP_PCT = 0.01         # position ≤ 1% of 20d dollar ADV
VOL_CEILING_SLEEVE_RISK = 0.0075    # 1-ATR day move costs ≤ 0.75% of sleeve
SMALL_CAP_HAIRCUT_BELOW = 1_000_000_000.0   # conviction haircut under $1B mcap
SMALL_CAP_HAIRCUT_MIN_MULT = 0.70   # haircut floor (at/below FUNNEL_MCAP_FLOOR)
OUTCOMPETE_MARGIN = 10.0            # challenger must beat weakest holding by this
MAX_THEME_PCT_OF_SLEEVE = 0.35      # aggregate cap per theme (overlaps double-count)
FUNNEL_MCAP_FLOOR = 150_000_000.0
FUNNEL_PRICE_FLOOR = 2.0
FUNNEL_INDUSTRY_TOP_N = 5           # industries whose ETF holdings enter the universe
FUNNEL_HOLDINGS_PER_ETF = 10
STALENESS_DECAY_PER_WEEK = 0.02     # conviction multiplier loss per week of report age
STALENESS_DECAY_FLOOR = 0.60
CONVICTION_BUY_BONUS = 5.0          # points (0–100 scale); SELL is a veto, not a score
LIGHT_SENTIMENT_MODEL = "claude-haiku-4-5"
LIGHT_SENTIMENT_MAX_HEADLINES = 25

# Weights must each sum to 1.0 (tested).
CONVICTION_WEIGHTS = {
    "fair_value_gap": 0.30,
    "fundamental": 0.20,
    "flow": 0.20,
    "momentum": 0.20,
    "hunting_ground": 0.10,
}
SCREEN_WEIGHTS = {
    "momentum": 0.40,
    "trend": 0.20,
    "liquidity": 0.15,
    "quality": 0.15,
    "hunting_ground": 0.10,
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_funnel_constants.py -v`
Expected: PASS

- [ ] **Step 5: Edit `db/schema.prisma`**

In `model EnginePosition`, after `thesis Json`:

```prisma
  // Phase 3C — Sleeve A funnel (all nullable; Sleeve B rows never set them)
  convictionScore Float?
  stopPrice       Float?   // ATR trailing stop, updated daily
  highWaterClose  Float?   // trailing-stop anchor
  sourceTags      Json?    // {themes: [slug], industries: [key], watchlist: bool}
  reportRef       String?  // WeeklySignal id of the full run that justified entry
```

In `model EngineTrade`, after `status String ...`:

```prisma
  // Phase 3C — shadow limit orders. status additionally takes:
  // "shadow_open" | "shadow_filled" | "shadow_expired" | "shadow_canceled"
  limitPrice Float?
  expiresAt  DateTime?
```

In `model SleeveState`, after `statusReason String?`:

```prisma
  mode String @default("live") // "live" | "shadow" — Sleeve A starts shadow (Phase 3C)
```

- [ ] **Step 6: Write the migration**

```sql
-- db/migrations/20260709000003_sleeve_a_funnel/migration.sql
-- Phase 3C: Sleeve A funnel columns (all nullable / defaulted — no backfill).
ALTER TABLE "EnginePosition"
  ADD COLUMN "convictionScore" DOUBLE PRECISION,
  ADD COLUMN "stopPrice" DOUBLE PRECISION,
  ADD COLUMN "highWaterClose" DOUBLE PRECISION,
  ADD COLUMN "sourceTags" JSONB,
  ADD COLUMN "reportRef" TEXT;

ALTER TABLE "EngineTrade"
  ADD COLUMN "limitPrice" DOUBLE PRECISION,
  ADD COLUMN "expiresAt" TIMESTAMP(3);

ALTER TABLE "SleeveState"
  ADD COLUMN "mode" TEXT NOT NULL DEFAULT 'live';
```

Note: table names here are the Prisma model names (these models have no `@@map`) — matches the Phase 2 migration style. Verify against `db/migrations/20260709000001_*/migration.sql` before committing; if that file quotes differently, follow it.

- [ ] **Step 7: Validate schema + regenerate client**

Run: `python3 -m prisma validate --schema db/schema.prisma && python3 -m prisma generate --schema db/schema.prisma`
Expected: `The schema ... is valid` then successful generate. (Do NOT run `migrate dev`.)

- [ ] **Step 8: Run the execution test suite for regressions**

Run: `python3 -m pytest tests/test_execution_daily.py tests/test_execution_weekly.py tests/test_autopilot_routes.py -q`
Expected: all pass (new columns are nullable; stub is MagicMock-based and field-agnostic)

- [ ] **Step 9: Commit**

```bash
git checkout -b autopilot-phase3c
git add execution/constants.py db/schema.prisma db/migrations/20260709000003_sleeve_a_funnel/ tests/test_funnel_constants.py
git commit -m "feat(autopilot): Phase 3C constants + funnel schema columns (shadow mode)"
```

---

### Task 2: `execution/funnel/universe.py` — assemble + tag + floors

**Files:**
- Create: `execution/funnel/__init__.py` (empty), `execution/funnel/universe.py`
- Test: `tests/test_funnel_universe.py`

**Interfaces:**
- Consumes: `execution.constants` (Task 1); `db.themebasket` / `db.watchlist` via `execution.research_feed.get_research_context` is NOT used here — watchlist comes in as a plain list (the cron passes it; research_feed stays the only reader of research tables).
- Produces:
  - `merge_sources(theme_members: Dict[str, List[str]], industry_holdings: Dict[str, List[str]], watchlist: List[str], holdings: List[str]) -> Dict[str, Dict[str, Any]]` — `{symbol: {"themes": [slugs], "industries": [etfs], "watchlist": bool, "holding": bool}}`, ETF/benchmark symbols excluded, symbols upper-cased.
  - `apply_floors(tagged: Dict[str, Dict], metrics: Dict[str, Dict]) -> Tuple[Dict[str, Dict], List[Dict]]` — metrics per symbol: `{"adv_usd": float|None, "market_cap": float|None, "price": float|None}`. Returns (kept, excluded) where each excluded item is `{"symbol", "reason"}`. Unknown market cap passes (floors are sanity nets); unknown price/ADV excludes with `"no_price_data"`.
  - `fetch_industry_holdings(industry_rankings: List[Dict], top_n: int, per_etf: int) -> Dict[str, List[str]]` — yfinance `Ticker(etf).funds_data.top_holdings` (a DataFrame indexed by symbol), guarded per ETF: any failure → that ETF contributes `[]`.
  - `async load_theme_members(db) -> Dict[str, List[str]]` — active constituents of active baskets.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_funnel_universe.py
"""Universe assembly: merge/tag/dedupe/floors. Pure functions — no network."""
from execution.funnel.universe import apply_floors, merge_sources


def _tags(**over):
    base = {"themes": [], "industries": [], "watchlist": False, "holding": False}
    base.update(over)
    return base


def test_merge_tags_and_dedupes_across_sources():
    tagged = merge_sources(
        theme_members={"photonics": ["aehr", "LASR"], "memory-hbm": ["RMBS", "AEHR"]},
        industry_holdings={"SMH": ["NVDA", "RMBS"]},
        watchlist=["nvda", "VIAV"],
        holdings=["LASR"],
    )
    assert tagged["AEHR"] == _tags(themes=["memory-hbm", "photonics"])
    assert tagged["RMBS"] == _tags(themes=["memory-hbm"], industries=["SMH"])
    assert tagged["NVDA"] == _tags(industries=["SMH"], watchlist=True)
    assert tagged["LASR"] == _tags(themes=["photonics"], holding=True)
    assert tagged["VIAV"] == _tags(watchlist=True)


def test_merge_excludes_signal_instruments():
    tagged = merge_sources(
        theme_members={}, industry_holdings={"SMH": ["SMH", "SPY", "XLK", "IWM", "NVDA"]},
        watchlist=["RSP"], holdings=[],
    )
    assert set(tagged) == {"NVDA"}


def test_floors_exclude_and_journal_reasons():
    tagged = {
        "OK": _tags(), "THIN": _tags(), "TINY": _tags(), "PENNY": _tags(), "DARK": _tags(),
        "NOCAP": _tags(),
    }
    metrics = {
        "OK":    {"adv_usd": 5e6, "market_cap": 5e8, "price": 20.0},
        "THIN":  {"adv_usd": 5e5, "market_cap": 5e8, "price": 20.0},
        "TINY":  {"adv_usd": 5e6, "market_cap": 9e7, "price": 20.0},
        "PENNY": {"adv_usd": 5e6, "market_cap": 5e8, "price": 1.5},
        "DARK":  {"adv_usd": None, "market_cap": 5e8, "price": None},
        "NOCAP": {"adv_usd": 5e6, "market_cap": None, "price": 20.0},
    }
    kept, excluded = apply_floors(tagged, metrics)
    assert set(kept) == {"OK", "NOCAP"}          # unknown mcap passes (sanity net)
    reasons = {e["symbol"]: e["reason"] for e in excluded}
    assert reasons == {
        "THIN": "adv_below_floor", "TINY": "mcap_below_floor",
        "PENNY": "price_below_floor", "DARK": "no_price_data",
    }
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_funnel_universe.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'execution.funnel'`

- [ ] **Step 3: Implement**

```python
# execution/funnel/__init__.py
```

```python
# execution/funnel/universe.py
"""Sleeve A candidate universe: merge tagged sources, apply sanity floors.

Themes/industries/watchlist pick the hunting grounds; nothing here buys a
stock. Every symbol keeps provenance tags — the guardrails' theme-overlap
caps and the journal both need to know WHY a name is in the universe.
"""
import logging
from typing import Any, Dict, Iterable, List, Tuple

from execution.constants import (
    BENCHMARK, EQUAL_WEIGHT, FUNNEL_HOLDINGS_PER_ETF, FUNNEL_INDUSTRY_TOP_N,
    FUNNEL_MCAP_FLOOR, FUNNEL_PRICE_FLOOR, INDUSTRY_ETFS, SECTOR_ETFS,
    SIZE_STYLE_ETFS, THEME_ADV_FLOOR_USD,
)

logger = logging.getLogger(__name__)

_INSTRUMENTS = (
    set(SECTOR_ETFS) | set(INDUSTRY_ETFS) | set(SIZE_STYLE_ETFS)
    | {BENCHMARK, EQUAL_WEIGHT}
)


def _blank() -> Dict[str, Any]:
    return {"themes": [], "industries": [], "watchlist": False, "holding": False}


def merge_sources(
    theme_members: Dict[str, List[str]],
    industry_holdings: Dict[str, List[str]],
    watchlist: Iterable[str],
    holdings: Iterable[str],
) -> Dict[str, Dict[str, Any]]:
    tagged: Dict[str, Dict[str, Any]] = {}

    def _get(sym: str) -> Dict[str, Any]:
        s = sym.strip().upper()
        if not s or s in _INSTRUMENTS:
            return {}
        return tagged.setdefault(s, _blank())

    for slug, members in sorted(theme_members.items()):
        for sym in members:
            t = _get(sym)
            if t and slug not in t["themes"]:
                t["themes"].append(slug)
    for etf, members in sorted(industry_holdings.items()):
        for sym in members:
            t = _get(sym)
            if t and etf not in t["industries"]:
                t["industries"].append(etf)
    for sym in watchlist:
        t = _get(sym)
        if t:
            t["watchlist"] = True
    for sym in holdings:
        t = _get(sym)
        if t:
            t["holding"] = True
    for t in tagged.values():
        t["themes"].sort()
        t["industries"].sort()
    return tagged


def apply_floors(
    tagged: Dict[str, Dict[str, Any]], metrics: Dict[str, Dict[str, Any]],
) -> Tuple[Dict[str, Dict[str, Any]], List[Dict[str, str]]]:
    """Sanity floors. Unknown market cap passes (net, not gate); unknown
    price/ADV excludes — we cannot screen what we cannot price."""
    kept: Dict[str, Dict[str, Any]] = {}
    excluded: List[Dict[str, str]] = []
    for sym, tags in tagged.items():
        m = metrics.get(sym) or {}
        adv, mcap, price = m.get("adv_usd"), m.get("market_cap"), m.get("price")
        if price is None or adv is None:
            excluded.append({"symbol": sym, "reason": "no_price_data"})
        elif adv < THEME_ADV_FLOOR_USD:
            excluded.append({"symbol": sym, "reason": "adv_below_floor"})
        elif mcap is not None and mcap < FUNNEL_MCAP_FLOOR:
            excluded.append({"symbol": sym, "reason": "mcap_below_floor"})
        elif price < FUNNEL_PRICE_FLOOR:
            excluded.append({"symbol": sym, "reason": "price_below_floor"})
        else:
            kept[sym] = tags
    return kept, excluded


def fetch_industry_holdings(
    industry_rankings: List[Dict[str, Any]],
    top_n: int = FUNNEL_INDUSTRY_TOP_N,
    per_etf: int = FUNNEL_HOLDINGS_PER_ETF,
) -> Dict[str, List[str]]:
    """Top holdings of the top-N ranked industry ETFs. Guarded per ETF —
    a failed fetch contributes nothing (degrade, never block)."""
    import yfinance as yf  # local import: keep module importable without network deps

    out: Dict[str, List[str]] = {}
    ranked = sorted(
        (r for r in industry_rankings if r.get("etf")),
        key=lambda r: r.get("rank_1m") if r.get("rank_1m") is not None else 999,
    )[:top_n]
    for row in ranked:
        etf = row["etf"]
        try:
            th = yf.Ticker(etf).funds_data.top_holdings  # DataFrame indexed by symbol
            out[etf] = [str(s).upper() for s in list(th.index)[:per_etf]]
        except Exception:  # noqa: BLE001 — one ETF must not sink assembly
            logger.exception("funnel universe: holdings fetch failed for %s", etf)
            out[etf] = []
    return out


async def load_theme_members(db) -> Dict[str, List[str]]:
    """Active constituents of active baskets. Empty dict on any failure."""
    try:
        baskets = await db.themebasket.find_many(
            where={"status": "active"}, include={"constituents": True},
        )
        return {
            b.slug: [c.ticker for c in (b.constituents or []) if c.status == "active"]
            for b in baskets
        }
    except Exception:  # noqa: BLE001
        logger.exception("funnel universe: theme member load failed")
        return {}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_funnel_universe.py -v`
Expected: 3 PASS

- [ ] **Step 5: Commit**

```bash
git add execution/funnel/ tests/test_funnel_universe.py
git commit -m "feat(autopilot): funnel universe assembly — tagged sources + sanity floors"
```

---

### Task 3: `execution/funnel/screen.py` + `fetch_ohlcv_batch` — the free screen

**Files:**
- Create: `execution/funnel/screen.py`
- Modify: `execution/market_data.py` (add `fetch_ohlcv_batch`)
- Test: `tests/test_funnel_screen.py`

**Interfaces:**
- Consumes: `apply_floors`-kept tags (Task 2); `execution.market_data.fetch_ohlcv_batch`.
- Produces:
  - `fetch_ohlcv_batch(tickers, period="1y") -> Dict[str, pd.DataFrame]` in `execution/market_data.py` — columns `Open/High/Low/Close/Volume`, NaN rows dropped, empty frames omitted. Same yf.download batching style as `fetch_closes_batch`.
  - `compute_atr(df: pd.DataFrame, period: int = 14) -> Optional[float]` — Wilder ATR, latest value; None if < period+1 rows.
  - `screen_row(symbol, df, spy_closes, tags, top_themes, top_industries, quality: Optional[float]) -> Optional[Dict]` — returns `{symbol, screen_score, momentum, trend, liquidity_adv_usd, quality, hunting_bonus, price, atr, atr_pct, ext_atr, sma20, tags}`; None if insufficient history (< 63 rows).
  - `rank_candidates(rows) -> List[Dict]` — descending `screen_score`.
  - `select_light_slots(ranked, fresh_symbols: set, stale_holdings: List[str], budget: int) -> Dict[str, List[str]]` — `{"light": [...], "free_ride": [...], "over_budget": [...]}`; stale holdings claim slots first; fresh-report names ride free.
  - `ext_atr` (ATR-units above 20d SMA) is THE extension input Task 6 consumes.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_funnel_screen.py
"""Free screen: ATR, scores, slot selection. Synthetic frames — no network."""
import numpy as np
import pandas as pd
import pytest

from execution.funnel.screen import (
    compute_atr, rank_candidates, screen_row, select_light_slots,
)


def _frame(days=260, drift=0.0005, vol=0.01, start=50.0, volume=1_000_000, seed=7):
    rng = np.random.default_rng(seed)
    close = start * np.cumprod(1 + drift + vol * rng.standard_normal(days))
    high = close * (1 + np.abs(vol * rng.standard_normal(days)))
    low = close * (1 - np.abs(vol * rng.standard_normal(days)))
    idx = pd.bdate_range(end="2026-07-06", periods=days)
    return pd.DataFrame(
        {"Open": close, "High": high, "Low": low, "Close": close,
         "Volume": np.full(days, float(volume))}, index=idx,
    )


def _tags(**over):
    base = {"themes": [], "industries": [], "watchlist": False, "holding": False}
    base.update(over)
    return base


def test_atr_positive_and_none_when_short():
    assert compute_atr(_frame()) > 0
    assert compute_atr(_frame(days=10)) is None


def test_screen_row_shape_and_momentum_ordering():
    spy = _frame(drift=0.0003, seed=1)["Close"]
    hot = screen_row("HOT", _frame(drift=0.004, seed=2), spy, _tags(), [], [], None)
    cold = screen_row("COLD", _frame(drift=-0.002, seed=3), spy, _tags(), [], [], None)
    assert hot["momentum"] > cold["momentum"]
    assert hot["screen_score"] > cold["screen_score"]
    for key in ("price", "atr", "atr_pct", "ext_atr", "sma20", "liquidity_adv_usd"):
        assert hot[key] is not None
    assert screen_row("SHORT", _frame(days=30), spy, _tags(), [], [], None) is None


def test_hunting_ground_bonus_breaks_ties():
    spy = _frame(seed=1)["Close"]
    df = _frame(seed=4)
    themed = screen_row("A", df, spy, _tags(themes=["photonics"]), ["photonics"], [], None)
    plain = screen_row("B", df, spy, _tags(), ["photonics"], [], None)
    assert themed["hunting_bonus"] > plain["hunting_bonus"]
    assert themed["screen_score"] > plain["screen_score"]


def test_quality_neutral_when_missing():
    spy = _frame(seed=1)["Close"]
    df = _frame(seed=5)
    missing = screen_row("A", df, spy, _tags(), [], [], None)
    assert missing["quality"] == 5.0  # neutral — never disqualifying


def test_select_light_slots_stale_holdings_first_and_budget():
    ranked = [{"symbol": s} for s in ["N1", "N2", "N3", "FRESH", "N4"]]
    out = select_light_slots(
        ranked, fresh_symbols={"FRESH"}, stale_holdings=["HOLD1"], budget=3,
    )
    assert out["light"] == ["HOLD1", "N1", "N2"]     # stale holding claims slot 1
    assert out["free_ride"] == ["FRESH"]
    assert out["over_budget"] == ["N3", "N4"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_funnel_screen.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'execution.funnel.screen'`

- [ ] **Step 3: Add `fetch_ohlcv_batch` to `execution/market_data.py`**

Append after `fetch_closes_batch` (mirror its download call style — read that function first and reuse its yf.download kwargs):

```python
def fetch_ohlcv_batch(tickers: Iterable[str], period: str = "1y") -> Dict[str, "pd.DataFrame"]:
    """Batched OHLCV download. Returns {ticker: DataFrame[Open,High,Low,Close,Volume]}.
    Tickers with no data are omitted — callers treat absence as 'skip this name'."""
    import yfinance as yf  # noqa: PLC0415 — heavy import stays local

    symbols = [t for t in dict.fromkeys(tickers) if t]
    if not symbols:
        return {}
    raw = yf.download(
        tickers=" ".join(symbols), period=period, interval="1d",
        group_by="ticker", auto_adjust=True, progress=False, threads=True,
    )
    out: Dict[str, pd.DataFrame] = {}
    for sym in symbols:
        try:
            df = raw[sym] if len(symbols) > 1 else raw
            df = df[["Open", "High", "Low", "Close", "Volume"]].dropna()
            if not df.empty:
                out[sym] = df
        except Exception:  # noqa: BLE001 — one bad ticker must not sink the batch
            continue
    return out
```

- [ ] **Step 4: Implement `execution/funnel/screen.py`**

```python
# execution/funnel/screen.py
"""Free quant screen — zero LLM. Ranks the assembled universe; picks who
earns a light run. ext_atr computed here is the extension-check input."""
import logging
import math
from typing import Any, Dict, List, Optional, Set

import pandas as pd

from execution.constants import SCREEN_WEIGHTS, WINDOWS

logger = logging.getLogger(__name__)

_MIN_ROWS = 63  # need a full 3m window


def compute_atr(df: pd.DataFrame, period: int = 14) -> Optional[float]:
    if df is None or len(df) < period + 1:
        return None
    high, low, close = df["High"], df["Low"], df["Close"]
    prev_close = close.shift(1)
    tr = pd.concat(
        [high - low, (high - prev_close).abs(), (low - prev_close).abs()], axis=1
    ).max(axis=1)
    atr = tr.ewm(alpha=1.0 / period, adjust=False).mean().iloc[-1]
    return float(atr) if math.isfinite(atr) and atr > 0 else None


def _window_rs(closes: pd.Series, spy: pd.Series, days: int) -> Optional[float]:
    if len(closes) < days + 1 or len(spy) < days + 1:
        return None
    r = closes.iloc[-1] / closes.iloc[-days - 1] - 1.0
    b = spy.iloc[-1] / spy.iloc[-days - 1] - 1.0
    return float(r - b)


def screen_row(
    symbol: str, df: pd.DataFrame, spy_closes: pd.Series, tags: Dict[str, Any],
    top_themes: List[str], top_industries: List[str], quality: Optional[float],
) -> Optional[Dict[str, Any]]:
    if df is None or len(df) < _MIN_ROWS:
        return None
    closes = df["Close"]
    price = float(closes.iloc[-1])
    atr = compute_atr(df)
    if atr is None or price <= 0:
        return None

    rs_1m = _window_rs(closes, spy_closes, WINDOWS["1m"])
    rs_3m = _window_rs(closes, spy_closes, WINDOWS["3m"])
    atr_pct = atr / price
    # momentum: mean of available RS windows, scaled by inverse vol (twitchy
    # names don't win on noise), mapped to 0..10 around 0 RS.
    rs_vals = [v for v in (rs_1m, rs_3m) if v is not None]
    raw_mom = (sum(rs_vals) / len(rs_vals)) / max(atr_pct, 0.005) if rs_vals else 0.0
    momentum = max(0.0, min(10.0, 5.0 + raw_mom))

    sma20 = float(closes.rolling(20).mean().iloc[-1])
    sma50 = float(closes.rolling(50).mean().iloc[-1]) if len(closes) >= 50 else sma20
    ext_atr = (price - sma20) / atr
    trend = 5.0 + (2.5 if price > sma50 else -2.5) + max(-2.5, min(2.5, ext_atr))
    trend = max(0.0, min(10.0, trend))

    adv_usd = float((closes * df["Volume"]).tail(20).mean())
    liquidity = max(0.0, min(10.0, math.log10(max(adv_usd, 1.0)) - 4.0))  # $10M ADV ≈ 3

    hunting = 0.0
    if any(t in top_themes for t in tags.get("themes", [])):
        hunting += 5.0
    if any(i in top_industries for i in tags.get("industries", [])):
        hunting += 3.0
    if tags.get("watchlist"):
        hunting += 2.0
    hunting = min(10.0, hunting)

    q = 5.0 if quality is None else max(0.0, min(10.0, float(quality)))
    score = (
        SCREEN_WEIGHTS["momentum"] * momentum + SCREEN_WEIGHTS["trend"] * trend
        + SCREEN_WEIGHTS["liquidity"] * liquidity + SCREEN_WEIGHTS["quality"] * q
        + SCREEN_WEIGHTS["hunting_ground"] * hunting
    )
    return {
        "symbol": symbol, "screen_score": round(score, 3), "momentum": momentum,
        "trend": trend, "liquidity_adv_usd": adv_usd, "quality": q,
        "hunting_bonus": hunting, "price": price, "atr": atr, "atr_pct": atr_pct,
        "ext_atr": ext_atr, "sma20": sma20, "tags": tags,
    }


def rank_candidates(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return sorted(rows, key=lambda r: r["screen_score"], reverse=True)


def select_light_slots(
    ranked: List[Dict[str, Any]], fresh_symbols: Set[str],
    stale_holdings: List[str], budget: int,
) -> Dict[str, List[str]]:
    light: List[str] = [s for s in stale_holdings[:budget]]
    free_ride: List[str] = []
    over_budget: List[str] = []
    for row in ranked:
        sym = row["symbol"]
        if sym in light:
            continue
        if sym in fresh_symbols:
            free_ride.append(sym)
        elif len(light) < budget:
            light.append(sym)
        else:
            over_budget.append(sym)
    return {"light": light, "free_ride": free_ride, "over_budget": over_budget}
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_funnel_screen.py tests/test_execution_market_data.py -v`
Expected: all PASS (market_data regression included — `fetch_ohlcv_batch` must not disturb existing fetchers)

- [ ] **Step 6: Commit**

```bash
git add execution/funnel/screen.py execution/market_data.py tests/test_funnel_screen.py
git commit -m "feat(autopilot): free quant screen + batched OHLCV fetch"
```

---

### Task 4: `execution/funnel/light_runner.py` — numbers-only research runs

**Files:**
- Create: `execution/funnel/light_runner.py`
- Test: `tests/test_funnel_light_runner.py`

**Interfaces:**
- Consumes: a screen row dict from Task 3 (`price`, `atr_pct`, `tags`, `liquidity_adv_usd`); swarm pure functions (import-only): `research_swarm.agents.fundamentalist.blended_valuation.BlendedValuationCalculator.calculate_fair_value(ticker, current_price, valuation_metrics, stock_info=...) -> Optional[PriceTargetScenarios]` (use `.fair_value_mid`), `research_swarm.agents.fundamentalist.scorer.HealthScorer.calculate_valuation_score(valuation_metrics) -> Tuple[float, Dict]`, `research_swarm.data.openinsider_client.OpenInsiderClient.{get_insider_transactions, calculate_insider_score}`, `research_swarm.data.finra_client.FINRAClient.{get_dark_pool_activity, calculate_dark_pool_metrics}`, `research_swarm.data.news_client.news_client.get_company_news(ticker, days_back, max_results)`, `research_swarm.agents.quant.technical.calculate_rsi`. Valuation metrics via the `market_data_client` singleton's `get_valuation_metrics(ticker)` (import with `importlib.import_module` — package attr is shadowed).
- Produces:
  - `async light_run_one(ticker: str, screen: Dict, llm_call=None) -> Dict[str, Any]` — always returns a dict (fields None on per-source failure): `{ticker, current_price, market_cap, fair_value, fair_value_gap_pct, valuation_score, insider_score, dark_pool_score, short_pct_float, sentiment_score, rsi14}`. Never raises.
  - `sentiment_from_headlines(headlines: List[str], llm_call) -> Optional[float]` — 0–10 or None.
  - `async persist_light_signal(db, run_date: datetime, light: Dict, screen_score: float) -> str` — returns `"stored" | "kept_full" | "failed"`. Upserts `WeeklySignal` on `(ticker, runDate)`; an existing `tier="full"` row is NEVER downgraded. Rows are marked engine-commissioned via `escalationReasons = ["sleeve_a_funnel"]` (Task 10's budget counter keys on this).

**Confirm-before-code (one-time reads, no output changes):** the exact score key returned by `OpenInsiderClient.calculate_insider_score` (research_swarm/data/openinsider_client.py:222) and `FINRAClient.calculate_dark_pool_metrics` (research_swarm/data/finra_client.py:374) — the extractor below tries the documented candidates defensively either way, but log which key is live in your task report.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_funnel_light_runner.py
"""Light runner: numbers only, every source guarded, never raises."""
import asyncio
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from execution.funnel import light_runner as lr

RUN_DATE = datetime(2026, 7, 13, tzinfo=timezone.utc)
SCREEN = {"price": 20.0, "atr_pct": 0.04, "screen_score": 6.5,
          "liquidity_adv_usd": 5e6, "tags": {"themes": ["photonics"]}}


def test_sentiment_parses_score_line():
    assert lr.sentiment_from_headlines(["Up"], lambda p: "SCORE: 7.5") == 7.5
    assert lr.sentiment_from_headlines(["Up"], lambda p: "garbage") is None
    assert lr.sentiment_from_headlines([], lambda p: "SCORE: 9") is None  # no news → None, no LLM call


def test_light_run_survives_every_source_failing():
    with patch.object(lr, "_gather_market_numbers", side_effect=RuntimeError("boom")), \
         patch.object(lr, "_gather_flow_numbers", side_effect=RuntimeError("boom")), \
         patch.object(lr, "_gather_headlines", side_effect=RuntimeError("boom")):
        out = asyncio.get_event_loop().run_until_complete(
            lr.light_run_one("AEHR", SCREEN, llm_call=lambda p: "SCORE: 5")
        )
    assert out["ticker"] == "AEHR"
    assert out["current_price"] == 20.0          # screen price survives
    assert out["fair_value"] is None and out["insider_score"] is None
    assert out["sentiment_score"] is None


def test_persist_never_downgrades_full_row():
    db = MagicMock()
    db.weeklysignal.find_unique = AsyncMock(return_value=MagicMock(tier="full"))
    db.weeklysignal.upsert = AsyncMock()
    out = asyncio.get_event_loop().run_until_complete(
        lr.persist_light_signal(db, RUN_DATE, {"ticker": "NVDA"}, 6.5)
    )
    assert out == "kept_full"
    db.weeklysignal.upsert.assert_not_called()


def test_persist_upserts_engine_light():
    db = MagicMock()
    db.weeklysignal.find_unique = AsyncMock(return_value=None)
    db.weeklysignal.upsert = AsyncMock()
    light = {"ticker": "AEHR", "current_price": 20.0, "fair_value": 26.0,
             "fair_value_gap_pct": 30.0, "insider_score": 7.0, "dark_pool_score": None,
             "sentiment_score": 6.0, "market_cap": 4.2e8, "rsi14": 55.0,
             "short_pct_float": 0.03, "valuation_score": 6.0}
    out = asyncio.get_event_loop().run_until_complete(
        lr.persist_light_signal(db, RUN_DATE, light, 6.5)
    )
    assert out == "stored"
    kwargs = db.weeklysignal.upsert.call_args.kwargs
    assert kwargs["where"] == {"ticker_runDate": {"ticker": "AEHR", "runDate": RUN_DATE}}
    created = kwargs["data"]["create"]
    assert created["tier"] == "engine_light"
    assert created["verdict"] is None or "verdict" not in created  # verdicts belong to the manager
    assert created["currentPrice"] == 20.0 and created["fairValueGapPct"] == 30.0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_funnel_light_runner.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Implement**

```python
# execution/funnel/light_runner.py
"""Numbers-only research run (~$0.10–0.15): every data pull the swarm does,
none of the prose. Imports swarm pure functions — NEVER copies the math
(manager-formatter drift lesson). One Haiku call total (headline sentiment).

Every gather is guarded: a source failing yields None fields, never an
exception — the funnel treats missing numbers as neutral, not fatal.
"""
import asyncio
import importlib
import logging
import re
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

from execution.constants import (
    LIGHT_SENTIMENT_MAX_HEADLINES, LIGHT_SENTIMENT_MODEL,
)

logger = logging.getLogger(__name__)

_SCORE_RE = re.compile(r"SCORE:\s*([0-9]+(?:\.[0-9]+)?)")
_SCORE_KEYS = ("score", "insider_score", "overall_score", "dark_pool_score", "composite_score")


def _pick_score(d: Any) -> Optional[float]:
    if not isinstance(d, dict):
        return None
    for k in _SCORE_KEYS:
        v = d.get(k)
        if isinstance(v, (int, float)):
            return float(v)
    return None


def _gather_market_numbers(ticker: str, current_price: float) -> Dict[str, Any]:
    """Fair value + valuation score + mcap/short%/RSI inputs. Sync — call via to_thread."""
    import yfinance as yf  # noqa: PLC0415
    from research_swarm.agents.fundamentalist.blended_valuation import (  # noqa: PLC0415
        BlendedValuationCalculator,
    )
    from research_swarm.agents.fundamentalist.scorer import HealthScorer  # noqa: PLC0415

    mdc = importlib.import_module("research_swarm.data.market_data_client").market_data_client
    valuation_metrics = mdc.get_valuation_metrics(ticker) or {}
    info: Dict[str, Any] = {}
    try:
        info = yf.Ticker(ticker).info or {}
    except Exception:  # noqa: BLE001
        logger.warning("light_run %s: yf info failed", ticker)

    fair_value = None
    scenarios = BlendedValuationCalculator().calculate_fair_value(
        ticker, current_price, valuation_metrics, stock_info=info or None,
    )
    if scenarios is not None:
        fair_value = float(scenarios.fair_value_mid)

    valuation_score = None
    try:
        valuation_score, _ = HealthScorer().calculate_valuation_score(valuation_metrics)
    except Exception:  # noqa: BLE001
        logger.warning("light_run %s: valuation score failed", ticker)

    return {
        "fair_value": fair_value,
        "valuation_score": valuation_score,
        "market_cap": info.get("marketCap"),
        "short_pct_float": info.get("shortPercentOfFloat"),
    }


def _gather_flow_numbers(ticker: str, market_cap: Optional[float]) -> Dict[str, Any]:
    """Insider + dark pool from the same clients the swarm uses. Sync."""
    from research_swarm.data.finra_client import FINRAClient  # noqa: PLC0415
    from research_swarm.data.openinsider_client import OpenInsiderClient  # noqa: PLC0415

    insider_score = dark_pool_score = None
    try:
        oi = OpenInsiderClient()
        tx = oi.get_insider_transactions(ticker)
        if tx:
            insider_score = _pick_score(
                oi.calculate_insider_score(tx, ticker, market_cap=market_cap)
            )
    except Exception:  # noqa: BLE001
        logger.warning("light_run %s: insider fetch failed", ticker)
    try:
        fc = FINRAClient()
        dp = fc.get_dark_pool_activity(ticker)
        if dp:
            dark_pool_score = _pick_score(fc.calculate_dark_pool_metrics(dp, ticker))
    except Exception:  # noqa: BLE001
        logger.warning("light_run %s: dark pool fetch failed", ticker)
    return {"insider_score": insider_score, "dark_pool_score": dark_pool_score}


def _gather_headlines(ticker: str) -> List[str]:
    from research_swarm.data.news_client import news_client  # noqa: PLC0415

    articles = news_client.get_company_news(
        ticker, days_back=14, max_results=LIGHT_SENTIMENT_MAX_HEADLINES
    ) or []
    return [a.get("title", "") for a in articles if a.get("title")]


def default_llm_call(prompt: str) -> str:
    import os  # noqa: PLC0415
    import anthropic  # noqa: PLC0415

    client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY", ""))
    msg = client.messages.create(
        model=LIGHT_SENTIMENT_MODEL, max_tokens=64,
        messages=[{"role": "user", "content": prompt}],
    )
    return "".join(b.text for b in msg.content if getattr(b, "type", "") == "text")


def sentiment_from_headlines(
    headlines: List[str], llm_call: Callable[[str], str],
) -> Optional[float]:
    if not headlines:
        return None
    prompt = (
        "Score the aggregate news sentiment for a stock from these headlines, "
        "0 (very bearish) to 10 (very bullish). Reply with EXACTLY one line: "
        "SCORE: <number>\n\n" + "\n".join(f"- {h}" for h in headlines)
    )
    try:
        m = _SCORE_RE.search(llm_call(prompt))
        if not m:
            return None
        return max(0.0, min(10.0, float(m.group(1))))
    except Exception:  # noqa: BLE001
        logger.warning("light sentiment call failed")
        return None


def _rsi14(screen: Dict[str, Any]) -> Optional[float]:
    df = screen.get("df")
    if df is None or len(df) < 15:
        return None
    from research_swarm.agents.quant.technical import calculate_rsi  # noqa: PLC0415

    try:
        return float(calculate_rsi(df["Close"]).iloc[-1])
    except Exception:  # noqa: BLE001
        return None


async def light_run_one(
    ticker: str, screen: Dict[str, Any], llm_call: Optional[Callable[[str], str]] = None,
) -> Dict[str, Any]:
    llm_call = llm_call or default_llm_call
    price = float(screen["price"])
    out: Dict[str, Any] = {
        "ticker": ticker, "current_price": price, "market_cap": None,
        "fair_value": None, "fair_value_gap_pct": None, "valuation_score": None,
        "insider_score": None, "dark_pool_score": None, "short_pct_float": None,
        "sentiment_score": None, "rsi14": _rsi14(screen),
    }
    try:
        out.update(await asyncio.to_thread(_gather_market_numbers, ticker, price))
    except Exception:  # noqa: BLE001
        logger.exception("light_run %s: market numbers failed", ticker)
    try:
        out.update(await asyncio.to_thread(_gather_flow_numbers, ticker, out["market_cap"]))
    except Exception:  # noqa: BLE001
        logger.exception("light_run %s: flow numbers failed", ticker)
    try:
        headlines = await asyncio.to_thread(_gather_headlines, ticker)
        out["sentiment_score"] = await asyncio.to_thread(
            sentiment_from_headlines, headlines, llm_call
        )
    except Exception:  # noqa: BLE001
        logger.exception("light_run %s: sentiment failed", ticker)
    if out["fair_value"] is not None and price > 0:
        out["fair_value_gap_pct"] = round((out["fair_value"] - price) / price * 100, 2)
    return out


async def persist_light_signal(
    db, run_date: datetime, light: Dict[str, Any], screen_score: float,
) -> str:
    """Upsert an engine_light WeeklySignal row. NEVER downgrade a full row."""
    from prisma import Json  # noqa: PLC0415 — runtime-only dependency

    ticker = light["ticker"]
    try:
        existing = await db.weeklysignal.find_unique(
            where={"ticker_runDate": {"ticker": ticker, "runDate": run_date}}
        )
        if existing is not None and getattr(existing, "tier", "") == "full":
            return "kept_full"
        payload: Dict[str, Any] = {
            "tier": "engine_light",
            "currentPrice": light.get("current_price"),
            "fairValue": light.get("fair_value"),
            "fairValueGapPct": light.get("fair_value_gap_pct"),
            "insiderScore": light.get("insider_score"),
            "darkPoolScore": light.get("dark_pool_score"),
            "sentimentScore": light.get("sentiment_score"),
            "screenerScore": screen_score,
            "escalationReasons": Json(["sleeve_a_funnel"]),
            "quantSignals": Json({
                "rsi14": light.get("rsi14"),
                "short_pct_float": light.get("short_pct_float"),
                "valuation_score": light.get("valuation_score"),
                "market_cap": light.get("market_cap"),
            }),
        }
        await db.weeklysignal.upsert(
            where={"ticker_runDate": {"ticker": ticker, "runDate": run_date}},
            data={"create": {"ticker": ticker, "runDate": run_date, **payload},
                  "update": payload},
        )
        return "stored"
    except Exception:  # noqa: BLE001
        logger.exception("light_run %s: persist failed", ticker)
        return "failed"
```

Note for the implementer: the screen row passed by the cron (Task 12) carries the name's OHLCV frame under key `"df"` — `screen_row` output from Task 3 does not include it; the cron attaches it (`row["df"] = ohlcv[sym]`) before calling `light_run_one`. `_rsi14` treats it as optional either way.

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_funnel_light_runner.py -v`
Expected: 4 PASS

- [ ] **Step 5: Commit**

```bash
git add execution/funnel/light_runner.py tests/test_funnel_light_runner.py
git commit -m "feat(autopilot): light runner — swarm math imported, one Haiku call, engine_light rows"
```

---

### Task 5: `execution/funnel/conviction.py` — the ranking formula

**Files:**
- Create: `execution/funnel/conviction.py`
- Test: `tests/test_funnel_conviction.py`

**Interfaces:**
- Consumes: light/full signal numbers (Task 4 output or a full `WeeklySignal` row's fields) + screen row fields.
- Produces: `compute_conviction(i: Dict[str, Any]) -> Dict[str, Any]` returning `{"score": float 0–100, "vetoed": bool, "veto_reason": Optional[str], "components": Dict[str, float], "multipliers": Dict[str, float]}`. Input keys (all optional except none): `fair_value_gap_pct, valuation_score, financial_health, earnings_momentum, insider_score, dark_pool_score, sentiment_score, short_pct_float, momentum, hunting_bonus, market_cap, verdict, report_age_days`. Missing/None inputs score neutral (50 for their component) — missing data is never a veto. Task 7 ranks holdings and candidates with THIS function only.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_funnel_conviction.py
"""Conviction: one pure formula for candidates and holdings."""
from execution.constants import (
    CONVICTION_BUY_BONUS, SMALL_CAP_HAIRCUT_MIN_MULT, STALENESS_DECAY_FLOOR,
)
from execution.funnel.conviction import compute_conviction

RICH = dict(fair_value_gap_pct=30.0, valuation_score=7.0, insider_score=8.0,
            dark_pool_score=6.0, sentiment_score=6.0, momentum=8.0,
            hunting_bonus=8.0, market_cap=5e9, verdict=None, report_age_days=0)


def test_sell_verdict_is_absolute_veto():
    out = compute_conviction({**RICH, "verdict": "SELL"})
    assert out["vetoed"] is True and out["score"] == 0.0
    assert out["veto_reason"] == "sell_verdict"
    assert compute_conviction({**RICH, "verdict": "avoid"})["vetoed"] is True


def test_buy_bonus_and_hold_silent():
    hold = compute_conviction({**RICH, "verdict": "HOLD"})
    none_ = compute_conviction(RICH)
    buy = compute_conviction({**RICH, "verdict": "buy"})
    assert hold["score"] == none_["score"]
    assert buy["score"] == min(100.0, none_["score"] + CONVICTION_BUY_BONUS)


def test_fair_value_gap_moves_score():
    cheap = compute_conviction({**RICH, "fair_value_gap_pct": 40.0})
    rich_px = compute_conviction({**RICH, "fair_value_gap_pct": -20.0})
    assert cheap["score"] > rich_px["score"]


def test_small_cap_haircut_bounds():
    mega = compute_conviction({**RICH, "market_cap": 5e10})
    tiny = compute_conviction({**RICH, "market_cap": 1.5e8})
    assert mega["multipliers"]["haircut"] == 1.0
    assert tiny["multipliers"]["haircut"] == SMALL_CAP_HAIRCUT_MIN_MULT
    assert tiny["score"] < mega["score"]
    unknown = compute_conviction({**RICH, "market_cap": None})
    assert unknown["multipliers"]["haircut"] == 1.0  # unknown mcap: no haircut


def test_staleness_decays_to_floor():
    fresh = compute_conviction(RICH)
    old = compute_conviction({**RICH, "report_age_days": 700})
    assert old["multipliers"]["staleness"] == STALENESS_DECAY_FLOOR
    assert old["score"] < fresh["score"]


def test_all_none_inputs_score_neutral_not_crash():
    out = compute_conviction({})
    assert out["vetoed"] is False and 0.0 < out["score"] <= 100.0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_funnel_conviction.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Implement**

```python
# execution/funnel/conviction.py
"""One conviction formula for candidates AND holdings (0–100).

Ratings are not gates (BUY is ~15% of production reports): the categorical
verdict only matters at the extremes — SELL vetoes, BUY nudges. Missing data
is neutral, never disqualifying: the funnel ranks with what it has.
"""
from typing import Any, Dict, Optional

from execution.constants import (
    CONVICTION_BUY_BONUS, CONVICTION_WEIGHTS, FUNNEL_MCAP_FLOOR,
    SMALL_CAP_HAIRCUT_BELOW, SMALL_CAP_HAIRCUT_MIN_MULT,
    STALENESS_DECAY_FLOOR, STALENESS_DECAY_PER_WEEK,
)

_SELL_VERDICTS = {"sell", "avoid"}
_BUY_VERDICTS = {"buy", "strong_buy"}


def _clamp(v: float, lo: float = 0.0, hi: float = 100.0) -> float:
    return max(lo, min(hi, v))


def _tens(*vals: Optional[float]) -> float:
    """Mean of available 0–10 scores mapped to 0–100; neutral 50 when empty."""
    have = [float(v) for v in vals if v is not None]
    return _clamp(sum(have) / len(have) * 10.0) if have else 50.0


def _fv_component(gap_pct: Optional[float]) -> float:
    if gap_pct is None:
        return 50.0
    return _clamp(50.0 + float(gap_pct))  # +30% gap → 80; −20% → 30


def _haircut(market_cap: Optional[float]) -> float:
    if market_cap is None or market_cap >= SMALL_CAP_HAIRCUT_BELOW:
        return 1.0
    span = SMALL_CAP_HAIRCUT_BELOW - FUNNEL_MCAP_FLOOR
    frac = max(0.0, (float(market_cap) - FUNNEL_MCAP_FLOOR) / span)
    return SMALL_CAP_HAIRCUT_MIN_MULT + (1.0 - SMALL_CAP_HAIRCUT_MIN_MULT) * frac


def _staleness(report_age_days: Optional[float]) -> float:
    weeks = max(0.0, float(report_age_days or 0)) / 7.0
    return max(STALENESS_DECAY_FLOOR, 1.0 - STALENESS_DECAY_PER_WEEK * weeks)


def compute_conviction(i: Dict[str, Any]) -> Dict[str, Any]:
    verdict = (i.get("verdict") or "").strip().lower()
    if verdict in _SELL_VERDICTS:
        return {"score": 0.0, "vetoed": True, "veto_reason": "sell_verdict",
                "components": {}, "multipliers": {}}

    short_inverse = None
    if i.get("short_pct_float") is not None:
        # 0% short → 10; ≥20% short → 0 (crowded shorts are a risk, not a thesis)
        short_inverse = _clamp(10.0 - float(i["short_pct_float"]) * 50.0, 0.0, 10.0)

    components = {
        "fair_value_gap": _fv_component(i.get("fair_value_gap_pct")),
        "fundamental": _tens(i.get("valuation_score"), i.get("financial_health"),
                             i.get("earnings_momentum")),
        "flow": _tens(i.get("insider_score"), i.get("dark_pool_score"),
                      i.get("sentiment_score"), short_inverse),
        "momentum": _tens(i.get("momentum")),
        "hunting_ground": _tens(i.get("hunting_bonus")),
    }
    base = sum(CONVICTION_WEIGHTS[k] * components[k] for k in CONVICTION_WEIGHTS)
    if verdict in _BUY_VERDICTS:
        base += CONVICTION_BUY_BONUS
    multipliers = {"haircut": _haircut(i.get("market_cap")),
                   "staleness": _staleness(i.get("report_age_days"))}
    score = _clamp(base) * multipliers["haircut"] * multipliers["staleness"]
    return {"score": round(score, 2), "vetoed": False, "veto_reason": None,
            "components": components, "multipliers": multipliers}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_funnel_conviction.py -v`
Expected: 6 PASS

- [ ] **Step 5: Commit**

```bash
git add execution/funnel/conviction.py tests/test_funnel_conviction.py
git commit -m "feat(autopilot): conviction formula — SELL veto, BUY bonus, haircut + staleness decay"
```

---

### Task 6: `execution/funnel/entries.py` — extension check, limit pricing, sizing

**Files:**
- Create: `execution/funnel/entries.py`
- Test: `tests/test_funnel_entries.py`

**Interfaces:**
- Consumes: screen row fields (`price`, `sma20`, `atr`, `atr_pct`, `ext_atr`, `liquidity_adv_usd`), conviction score (Task 5).
- Produces (all pure; Task 7's planner and Task 12's cron call these):
  - `extension_state(ext_atr: float) -> str` — `"normal" | "extended"` at `EXTENSION_ATR_LIMIT`.
  - `entry_limit_price(state, price, sma20, atr) -> float` — normal: last close; extended: `max(sma20, price − atr)` (rounded to cents).
  - `entry_ttl_days(state) -> int` — normal 7; extended `PATIENT_LIMIT_TTL_WEEKS * 7`.
  - `size_entry(conviction, sleeve_equity, adv_usd, atr_pct, deployable_remaining, cash_available) -> float` — notional in dollars, 0.0 when the survivor is under `MIN_TRADE_NOTIONAL`. Ceilings only shrink: band → vol ceiling → ADV cap → deployable → cash.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_funnel_entries.py
"""Entry mechanics: no chasing, no market orders, ceilings shrink only."""
import pytest

from execution.constants import (
    ADV_POSITION_CAP_PCT, ENTRY_WEIGHT_MAX, ENTRY_WEIGHT_MIN,
    EXTENSION_ATR_LIMIT, MIN_TRADE_NOTIONAL, PATIENT_LIMIT_TTL_WEEKS,
    VOL_CEILING_SLEEVE_RISK,
)
from execution.funnel.entries import (
    entry_limit_price, entry_ttl_days, extension_state, size_entry,
)

SLEEVE = 70_000.0


def test_extension_threshold():
    assert extension_state(EXTENSION_ATR_LIMIT - 0.1) == "normal"
    assert extension_state(EXTENSION_ATR_LIMIT + 0.1) == "extended"


def test_limit_prices_never_chase():
    assert entry_limit_price("normal", 20.0, 19.0, 1.0) == 20.0
    # extended: retracement limit at the higher of sma20 / close − 1 ATR
    assert entry_limit_price("extended", 24.0, 21.5, 2.0) == 22.0   # close−ATR wins
    assert entry_limit_price("extended", 24.0, 23.0, 2.0) == 23.0   # sma20 wins
    assert entry_ttl_days("normal") == 7
    assert entry_ttl_days("extended") == PATIENT_LIMIT_TTL_WEEKS * 7


def test_size_band_tracks_conviction():
    lo = size_entry(0.0, SLEEVE, adv_usd=1e9, atr_pct=0.01,
                    deployable_remaining=SLEEVE, cash_available=SLEEVE)
    hi = size_entry(100.0, SLEEVE, adv_usd=1e9, atr_pct=0.01,
                    deployable_remaining=SLEEVE, cash_available=SLEEVE)
    assert lo == pytest.approx(ENTRY_WEIGHT_MIN * SLEEVE)
    assert hi == pytest.approx(ENTRY_WEIGHT_MAX * SLEEVE)


def test_vol_ceiling_binds_wild_names():
    # 10% daily ATR: cap = 0.0075/0.10 = 7.5% of sleeve < 12% band top
    n = size_entry(100.0, SLEEVE, adv_usd=1e9, atr_pct=0.10,
                   deployable_remaining=SLEEVE, cash_available=SLEEVE)
    assert n == pytest.approx(VOL_CEILING_SLEEVE_RISK / 0.10 * SLEEVE)


def test_adv_ceiling_binds_thin_names():
    # $500k ADV: cap = 1% = $5k, below the 12% band top ($8.4k of $70k sleeve)
    n = size_entry(100.0, SLEEVE, adv_usd=500_000.0, atr_pct=0.01,
                   deployable_remaining=SLEEVE, cash_available=SLEEVE)
    assert n == pytest.approx(ADV_POSITION_CAP_PCT * 500_000.0)  # $5k


def test_deployable_cash_and_dust():
    assert size_entry(100.0, SLEEVE, 1e9, 0.01, deployable_remaining=1_000.0,
                      cash_available=SLEEVE) == pytest.approx(1_000.0)
    assert size_entry(100.0, SLEEVE, 1e9, 0.01, deployable_remaining=SLEEVE,
                      cash_available=200.0) == pytest.approx(200.0)
    assert size_entry(100.0, SLEEVE, 1e9, 0.01, deployable_remaining=MIN_TRADE_NOTIONAL - 1,
                      cash_available=SLEEVE) == 0.0


def test_zero_or_missing_atr_pct_returns_zero():
    assert size_entry(80.0, SLEEVE, 1e9, 0.0, SLEEVE, SLEEVE) == 0.0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_funnel_entries.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Implement**

```python
# execution/funnel/entries.py
"""Entry mechanics. Qualification ('good company?') and execution ('this
price, this week?') are different questions — the extension check answers
the second. Limit orders only; a missed fill is a journal entry, not a loss."""
from execution.constants import (
    ADV_POSITION_CAP_PCT, ENTRY_WEIGHT_MAX, ENTRY_WEIGHT_MIN,
    EXTENSION_ATR_LIMIT, MIN_TRADE_NOTIONAL, PATIENT_LIMIT_TTL_WEEKS,
    VOL_CEILING_SLEEVE_RISK,
)


def extension_state(ext_atr: float) -> str:
    return "extended" if ext_atr > EXTENSION_ATR_LIMIT else "normal"


def entry_limit_price(state: str, price: float, sma20: float, atr: float) -> float:
    if state == "extended":
        return round(max(sma20, price - atr), 2)
    return round(price, 2)


def entry_ttl_days(state: str) -> int:
    return PATIENT_LIMIT_TTL_WEEKS * 7 if state == "extended" else 7


def size_entry(
    conviction: float, sleeve_equity: float, adv_usd: float, atr_pct: float,
    deployable_remaining: float, cash_available: float,
) -> float:
    """Conviction maps onto the 3–12% band; every ceiling only shrinks."""
    if atr_pct is None or atr_pct <= 0 or sleeve_equity <= 0:
        return 0.0
    band = ENTRY_WEIGHT_MIN + (ENTRY_WEIGHT_MAX - ENTRY_WEIGHT_MIN) * (
        max(0.0, min(100.0, conviction)) / 100.0
    )
    notional = band * sleeve_equity
    notional = min(notional, VOL_CEILING_SLEEVE_RISK / atr_pct * sleeve_equity)
    notional = min(notional, ADV_POSITION_CAP_PCT * max(adv_usd or 0.0, 0.0))
    notional = min(notional, max(deployable_remaining, 0.0), max(cash_available, 0.0))
    return round(notional, 2) if notional >= MIN_TRADE_NOTIONAL else 0.0
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_funnel_entries.py -v`
Expected: 7 PASS

- [ ] **Step 5: Commit**

```bash
git add execution/funnel/entries.py tests/test_funnel_entries.py
git commit -m "feat(autopilot): entry mechanics — extension check, patient limits, shrink-only sizing"
```

---

### Task 7: `execution/funnel/decisions.py` — the weekly exit/entry planner

**Files:**
- Create: `execution/funnel/decisions.py`
- Modify: `execution/constants.py` (one constant)
- Test: `tests/test_funnel_decisions.py`

**Interfaces:**
- Consumes: conviction dicts (Task 5). ATR stops are NOT here — they are a daily-cron duty (Task 13). This planner covers the weekly exits: sell-verdict, theme-review, outcompeted, risk-trim — then queues entries.
- Produces: `plan_decisions(holdings: List[Dict], candidates: List[Dict], sleeve_equity: float, max_positions: int) -> Dict`.
  - Holding input: `{symbol, market_value: float, conviction: float, vetoed: bool, theme_review_failed: bool}` (`theme_review_failed` is precomputed by the cron: every holding whose ONLY sourcing themes are retired gets a fresh full run, is re-scored with `hunting_bonus=0.0`, and fails review when that score < `RETIRED_THEME_EXIT_CONVICTION`).
  - Candidate input: `{symbol, conviction: float, vetoed: bool}`.
  - Returns `{"exits": [{symbol, reason}], "trims": [{symbol, sell_notional, reason}], "entry_queue": [symbol, ...], "notes": [str]}` — exits reasons: `"sell_verdict" | "theme_review_failed" | "outcompeted"`; entry_queue is ordered by conviction desc and sized to open book slots AFTER planned exits; vetoed candidates never enter; a candidate already held never enters.
- New constant: `RETIRED_THEME_EXIT_CONVICTION = 50.0`.

- [ ] **Step 1: Add the constant + extend the constants test**

Append to the Phase 3C block in `execution/constants.py`:

```python
RETIRED_THEME_EXIT_CONVICTION = 50.0  # review re-score (hunting_bonus=0) must clear this
```

Append to `tests/test_funnel_constants.py::test_funnel_constants_exist_and_cohere`:

```python
    assert 0 < c.RETIRED_THEME_EXIT_CONVICTION < 100
```

Run: `python3 -m pytest tests/test_funnel_constants.py -v` — PASS

- [ ] **Step 2: Write the failing tests**

```python
# tests/test_funnel_decisions.py
"""Weekly planner: exits carry the discipline, winners run, no churn."""
from execution.constants import OUTCOMPETE_MARGIN, RISK_TRIM_CEILING, RISK_TRIM_TARGET
from execution.funnel.decisions import plan_decisions

SLEEVE = 70_000.0


def _h(sym, mv, conv, vetoed=False, review_failed=False):
    return {"symbol": sym, "market_value": mv, "conviction": conv,
            "vetoed": vetoed, "theme_review_failed": review_failed}


def _c(sym, conv, vetoed=False):
    return {"symbol": sym, "conviction": conv, "vetoed": vetoed}


def test_sell_verdict_and_failed_review_exit():
    out = plan_decisions(
        [_h("BAD", 5_000, 0.0, vetoed=True), _h("DEAD", 5_000, 40.0, review_failed=True),
         _h("OK", 5_000, 70.0)],
        [], SLEEVE, max_positions=15,
    )
    reasons = {e["symbol"]: e["reason"] for e in out["exits"]}
    assert reasons == {"BAD": "sell_verdict", "DEAD": "theme_review_failed"}


def test_risk_trim_only_above_ceiling_no_maintenance_rebalance():
    big = SLEEVE * (RISK_TRIM_CEILING + 0.02)           # 22% → trim
    drifted = SLEEVE * 0.16                             # 16% winner → untouched
    out = plan_decisions([_h("BIG", big, 80.0), _h("WIN", drifted, 75.0)], [], SLEEVE, 15)
    assert out["exits"] == []
    assert len(out["trims"]) == 1
    t = out["trims"][0]
    assert t["symbol"] == "BIG" and t["reason"] == "risk_trim"
    assert t["sell_notional"] == round(big - RISK_TRIM_TARGET * SLEEVE, 2)


def test_outcompete_needs_margin():
    holds = [_h("WEAK", 5_000, 50.0), _h("MID", 5_000, 70.0)]
    # book full at 2; challenger inside the margin → no churn
    close = plan_decisions(holds, [_c("CH1", 50.0 + OUTCOMPETE_MARGIN - 1)], SLEEVE, 2)
    assert close["exits"] == [] and close["entry_queue"] == []
    # challenger clears the margin → swap weakest
    swap = plan_decisions(holds, [_c("CH2", 50.0 + OUTCOMPETE_MARGIN + 1)], SLEEVE, 2)
    assert {e["symbol"]: e["reason"] for e in swap["exits"]} == {"WEAK": "outcompeted"}
    assert swap["entry_queue"] == ["CH2"]


def test_entry_queue_fills_open_slots_by_conviction():
    out = plan_decisions(
        [_h("H1", 5_000, 70.0)],
        [_c("A", 90.0), _c("B", 80.0), _c("VETO", 95.0, vetoed=True), _c("H1", 99.0)],
        SLEEVE, max_positions=3,
    )
    assert out["entry_queue"] == ["A", "B"]   # veto blocked, held name blocked, 2 slots


def test_exit_frees_slot_for_entry():
    out = plan_decisions(
        [_h("BAD", 5_000, 0.0, vetoed=True), _h("OK", 5_000, 70.0)],
        [_c("NEW", 60.0)], SLEEVE, max_positions=2,
    )
    assert out["entry_queue"] == ["NEW"]
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_funnel_decisions.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 4: Implement**

```python
# execution/funnel/decisions.py
"""Weekly decision planner (pure). Priority: sell-verdict → failed theme
review → outcompeted → risk trim → entries. No maintenance rebalancing:
between the entry band and the trim ceiling, winners run untouched."""
from typing import Any, Dict, List

from execution.constants import (
    OUTCOMPETE_MARGIN, RISK_TRIM_CEILING, RISK_TRIM_TARGET,
)


def plan_decisions(
    holdings: List[Dict[str, Any]], candidates: List[Dict[str, Any]],
    sleeve_equity: float, max_positions: int,
) -> Dict[str, Any]:
    exits: List[Dict[str, str]] = []
    notes: List[str] = []

    for h in holdings:
        if h.get("vetoed"):
            exits.append({"symbol": h["symbol"], "reason": "sell_verdict"})
        elif h.get("theme_review_failed"):
            exits.append({"symbol": h["symbol"], "reason": "theme_review_failed"})
    exited = {e["symbol"] for e in exits}
    survivors = [h for h in holdings if h["symbol"] not in exited]

    held = {h["symbol"] for h in holdings}
    challengers = sorted(
        (c for c in candidates if not c.get("vetoed") and c["symbol"] not in held),
        key=lambda c: c["conviction"], reverse=True,
    )

    # Outcompete: while the book is full, the strongest challenger may evict
    # the weakest survivor only by clearing the hysteresis margin.
    entry_queue: List[str] = []
    book = sorted(survivors, key=lambda h: h["conviction"])
    for ch in challengers:
        if len(book) + len(entry_queue) < max_positions:
            entry_queue.append(ch["symbol"])
            continue
        if not book:
            break
        weakest = book[0]
        if ch["conviction"] >= weakest["conviction"] + OUTCOMPETE_MARGIN:
            exits.append({"symbol": weakest["symbol"], "reason": "outcompeted"})
            book.pop(0)
            entry_queue.append(ch["symbol"])
        else:
            notes.append(
                f"{ch['symbol']}: blocked — inside hysteresis margin vs {weakest['symbol']}"
            )
            break  # ordered by conviction: nobody weaker can clear it either

    trims: List[Dict[str, Any]] = []
    if sleeve_equity > 0:
        exited = {e["symbol"] for e in exits}
        for h in holdings:
            if h["symbol"] in exited:
                continue
            weight = h["market_value"] / sleeve_equity
            if weight > RISK_TRIM_CEILING:
                trims.append({
                    "symbol": h["symbol"],
                    "sell_notional": round(
                        h["market_value"] - RISK_TRIM_TARGET * sleeve_equity, 2
                    ),
                    "reason": "risk_trim",
                })
    return {"exits": exits, "trims": trims, "entry_queue": entry_queue, "notes": notes}
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_funnel_decisions.py tests/test_funnel_constants.py -v`
Expected: all PASS

- [ ] **Step 6: Commit**

```bash
git add execution/funnel/decisions.py execution/constants.py tests/test_funnel_decisions.py tests/test_funnel_constants.py
git commit -m "feat(autopilot): weekly decision planner — veto/review/outcompete exits, risk trims, entry queue"
```

---

### Task 8: `execution/broker/shadow_client.py` + position-math extraction

**Files:**
- Create: `execution/broker/shadow_client.py`
- Modify: `execution/sleeve_service.py` (extract pure `position_after_fill`; `apply_fill` behavior unchanged)
- Test: `tests/test_shadow_client.py`

**Interfaces:**
- Consumes: `execution.broker.base.BrokerOrderResult`; `EngineTrade`/`EnginePosition`/`SleeveState` tables.
- Produces:
  - `position_after_fill(qty0: float, avg0: float, fill_qty: float, price: float, side: str) -> Tuple[float, float]` in `sleeve_service.py` — the ONE place position/avg-entry math lives; `apply_fill` refactored to call it (existing tests prove parity).
  - `evaluate_fill(side: str, limit_price: float, day_high: float, day_low: float, expired: bool) -> str` — pure honesty rule: `"filled"` only if the market traded through the limit (buy: `day_low <= limit`; sell: `day_high >= limit`); else `"expired"` when past TTL; else `"open"`. A fill on the expiry day wins over expiry.
  - `class ShadowBrokerClient(db, sleeve="A")`:
    - `async submit_limit_buy(symbol, qty, limit_price, expires_at, journal, client_order_id) -> BrokerOrderResult` — ONE EngineTrade row, `status="shadow_open"`, `brokerOrderId=client_order_id`. Idempotent: an existing row with that id short-circuits (Inngest retry safety). Deterministic ids come from the cron: `f"shadow-{sleeve}-{symbol}-{run_date:%Y%m%d}"`.
    - `async submit_shadow_sell(symbol, qty, fill_price, journal, client_order_id) -> BrokerOrderResult` — immediate `shadow_filled` row at the given price (weekly exits/trims fill at that day's close; the daily stop fill price is Task 13's rule), position reduced via `position_after_fill`, returns result with cash delta applied by the caller pattern below.
    - `async get_open_orders() -> List[Any]` — `shadow_open` rows for the sleeve.
    - `async settle_open_order(order_row, day_high, day_low, now) -> Dict` — applies `evaluate_fill`; on fill: update row to `shadow_filled` at `fillPrice=limitPrice`, upsert position, return `{"status": "filled", "cash_delta": -qty*limit}`; on expiry: `{"status": "expired", "cash_delta": 0.0}`; open: `{"status": "open", "cash_delta": 0.0}`.
  - All writes never raise (log + return `{"status": "error"}`); cash ledger updates stay with the CALLER (cron) via `update_sleeve_cash`, mirroring how the weekly Sleeve B cron owns its ledger.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_shadow_client.py
"""Shadow broker: honesty rule, idempotent submits, one row per order."""
import asyncio
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock

from execution.broker.shadow_client import ShadowBrokerClient, evaluate_fill
from execution.sleeve_service import position_after_fill

NOW = datetime(2026, 7, 14, 21, 15, tzinfo=timezone.utc)


def test_position_math():
    assert position_after_fill(0.0, 0.0, 10.0, 20.0, "buy") == (10.0, 20.0)
    qty, avg = position_after_fill(10.0, 20.0, 10.0, 30.0, "buy")
    assert (qty, round(avg, 4)) == (20.0, 25.0)
    assert position_after_fill(20.0, 25.0, 5.0, 40.0, "sell") == (15.0, 25.0)


def test_evaluate_fill_honesty_rule():
    # buy fills only if the day's low traded through the limit
    assert evaluate_fill("buy", 20.0, day_high=25.0, day_low=19.5, expired=False) == "filled"
    assert evaluate_fill("buy", 20.0, day_high=25.0, day_low=20.5, expired=False) == "open"
    assert evaluate_fill("buy", 20.0, day_high=25.0, day_low=20.5, expired=True) == "expired"
    # a fill on the expiry day still wins
    assert evaluate_fill("buy", 20.0, day_high=25.0, day_low=19.9, expired=True) == "filled"
    assert evaluate_fill("sell", 30.0, day_high=30.1, day_low=25.0, expired=False) == "filled"


def _db_with(order_lookup=None):
    db = MagicMock()
    db.enginetrade.find_first = AsyncMock(return_value=order_lookup)
    db.enginetrade.create = AsyncMock(return_value=MagicMock(id="t1"))
    db.enginetrade.update = AsyncMock()
    db.engineposition.find_unique = AsyncMock(return_value=None)
    db.engineposition.upsert = AsyncMock()
    db.engineposition.delete = AsyncMock()
    return db


def test_submit_limit_buy_is_idempotent():
    db = _db_with(order_lookup=MagicMock(id="dup", status="shadow_open"))
    client = ShadowBrokerClient(db, sleeve="A")
    res = asyncio.get_event_loop().run_until_complete(
        client.submit_limit_buy("AEHR", 100.0, 20.0, NOW + timedelta(days=7),
                                {"why": "test"}, "shadow-A-AEHR-20260713")
    )
    assert res.status == "shadow_open"
    db.enginetrade.create.assert_not_called()


def test_settle_fills_at_limit_and_reports_cash_delta():
    db = _db_with()
    client = ShadowBrokerClient(db, sleeve="A")
    order = MagicMock(id="o1", symbol="AEHR", side="buy", qty=100.0,
                      limitPrice=20.0, expiresAt=NOW + timedelta(days=5))
    out = asyncio.get_event_loop().run_until_complete(
        client.settle_open_order(order, day_high=22.0, day_low=19.0, now=NOW)
    )
    assert out["status"] == "filled" and out["cash_delta"] == -2000.0
    upd = db.enginetrade.update.call_args.kwargs
    assert upd["data"]["status"] == "shadow_filled" and upd["data"]["fillPrice"] == 20.0
    db.engineposition.upsert.assert_called_once()


def test_settle_expires_quietly():
    db = _db_with()
    client = ShadowBrokerClient(db, sleeve="A")
    order = MagicMock(id="o1", symbol="AEHR", side="buy", qty=100.0,
                      limitPrice=20.0, expiresAt=NOW - timedelta(days=1))
    out = asyncio.get_event_loop().run_until_complete(
        client.settle_open_order(order, day_high=22.0, day_low=21.0, now=NOW)
    )
    assert out == {"status": "expired", "cash_delta": 0.0}
    db.engineposition.upsert.assert_not_called()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_shadow_client.py -v`
Expected: FAIL with `ImportError` (no `shadow_client`, no `position_after_fill`)

- [ ] **Step 3: Extract `position_after_fill` in `execution/sleeve_service.py`**

Add above `apply_fill`:

```python
def position_after_fill(
    qty0: float, avg0: float, fill_qty: float, price: float, side: str,
) -> "Tuple[float, float]":
    """Pure position math shared by real (apply_fill) and shadow fills.
    Buys re-weight the average entry; sells never touch it."""
    if side == "buy":
        qty1 = qty0 + fill_qty
        avg1 = ((qty0 * avg0) + (fill_qty * price)) / qty1 if qty1 > 0 else 0.0
        return qty1, avg1
    return max(qty0 - fill_qty, 0.0), avg0
```

Then, inside `apply_fill`, replace the inline qty/avgEntryPrice arithmetic in its position-upsert branch with a call to `position_after_fill` — read `execution/sleeve_service.py:100-160` first and keep every branch (create/update/delete-on-zero) byte-for-byte in behavior. Add `Tuple` to the module's `typing` import.

Run: `python3 -m pytest tests/test_execution_daily.py tests/test_execution_weekly.py tests/test_shadow_client.py::test_position_math -v`
Expected: PASS (parity proven by the existing suites)

- [ ] **Step 4: Implement `execution/broker/shadow_client.py`**

```python
# execution/broker/shadow_client.py
"""Shadow broker for Sleeve A (Phase 3C). Same result shapes as
AlpacaPaperClient, but orders are EngineTrade rows and fills come from real
daily bars under the honesty rule: a shadow order fills ONLY if the market
traded through its limit, always AT the limit — no generous fills, so the
3D backtest comparison stays honest. Phase 3D flips Sleeve A live by
swapping this client for AlpacaPaperClient. Nothing here talks to Alpaca."""
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from execution.broker.base import BrokerOrderResult
from execution.sleeve_service import position_after_fill

logger = logging.getLogger(__name__)


def evaluate_fill(
    side: str, limit_price: float, day_high: float, day_low: float, expired: bool,
) -> str:
    traded_through = (day_low <= limit_price) if side == "buy" else (day_high >= limit_price)
    if traded_through:
        return "filled"
    return "expired" if expired else "open"


class ShadowBrokerClient:
    def __init__(self, db, sleeve: str = "A"):
        self._db = db
        self._sleeve = sleeve

    async def submit_limit_buy(
        self, symbol: str, qty: float, limit_price: float, expires_at: datetime,
        journal: Dict[str, Any], client_order_id: str,
    ) -> BrokerOrderResult:
        from prisma import Json  # noqa: PLC0415

        existing = await self._db.enginetrade.find_first(
            where={"brokerOrderId": client_order_id}
        )
        if existing is None:
            await self._db.enginetrade.create(data={
                "sleeve": self._sleeve, "symbol": symbol, "side": "buy",
                "qty": qty, "notional": round(qty * limit_price, 2),
                "limitPrice": limit_price, "expiresAt": expires_at,
                "brokerOrderId": client_order_id, "status": "shadow_open",
                "journal": Json(journal or {}),
            })
        return BrokerOrderResult(
            order_id=client_order_id, symbol=symbol, side="buy",
            status="shadow_open", filled_qty=0.0, filled_avg_price=None,
        )

    async def submit_shadow_sell(
        self, symbol: str, qty: float, fill_price: float,
        journal: Dict[str, Any], client_order_id: str,
    ) -> BrokerOrderResult:
        from prisma import Json  # noqa: PLC0415

        existing = await self._db.enginetrade.find_first(
            where={"brokerOrderId": client_order_id}
        )
        if existing is None:
            await self._db.enginetrade.create(data={
                "sleeve": self._sleeve, "symbol": symbol, "side": "sell",
                "qty": qty, "fillPrice": fill_price, "limitPrice": None,
                "brokerOrderId": client_order_id, "status": "shadow_filled",
                "journal": Json(journal or {}),
            })
            await self._reduce_position(symbol, qty, fill_price)
        return BrokerOrderResult(
            order_id=client_order_id, symbol=symbol, side="sell",
            status="shadow_filled", filled_qty=qty, filled_avg_price=fill_price,
        )

    async def get_open_orders(self) -> List[Any]:
        return await self._db.enginetrade.find_many(
            where={"sleeve": self._sleeve, "status": "shadow_open"}
        )

    async def settle_open_order(
        self, order: Any, day_high: float, day_low: float, now: datetime,
    ) -> Dict[str, Any]:
        try:
            expires = order.expiresAt
            expired = bool(expires is not None and now > expires)
            verdict = evaluate_fill(order.side, order.limitPrice, day_high, day_low, expired)
            if verdict == "open":
                return {"status": "open", "cash_delta": 0.0}
            if verdict == "expired":
                await self._db.enginetrade.update(
                    where={"id": order.id}, data={"status": "shadow_expired"}
                )
                return {"status": "expired", "cash_delta": 0.0}
            await self._db.enginetrade.update(
                where={"id": order.id},
                data={"status": "shadow_filled", "fillPrice": order.limitPrice},
            )
            if order.side == "buy":
                await self._increase_position(order.symbol, order.qty, order.limitPrice)
                return {"status": "filled", "cash_delta": -round(order.qty * order.limitPrice, 2)}
            await self._reduce_position(order.symbol, order.qty, order.limitPrice)
            return {"status": "filled", "cash_delta": round(order.qty * order.limitPrice, 2)}
        except Exception:  # noqa: BLE001 — a broken settle must not sink the sweep
            logger.exception("shadow settle failed for order %s", getattr(order, "id", "?"))
            return {"status": "error", "cash_delta": 0.0}

    async def _increase_position(self, symbol: str, qty: float, price: float) -> None:
        row = await self._db.engineposition.find_unique(
            where={"sleeve_symbol": {"sleeve": self._sleeve, "symbol": symbol}}
        )
        qty0 = float(getattr(row, "qty", 0.0) or 0.0)
        avg0 = float(getattr(row, "avgEntryPrice", 0.0) or 0.0)
        qty1, avg1 = position_after_fill(qty0, avg0, qty, price, "buy")
        from prisma import Json  # noqa: PLC0415

        await self._db.engineposition.upsert(
            where={"sleeve_symbol": {"sleeve": self._sleeve, "symbol": symbol}},
            data={
                "create": {"sleeve": self._sleeve, "symbol": symbol, "qty": qty1,
                           "avgEntryPrice": avg1, "thesis": Json({}),
                           "highWaterClose": price, "stopPrice": None},
                "update": {"qty": qty1, "avgEntryPrice": avg1},
            },
        )

    async def _reduce_position(self, symbol: str, qty: float, price: float) -> None:
        row = await self._db.engineposition.find_unique(
            where={"sleeve_symbol": {"sleeve": self._sleeve, "symbol": symbol}}
        )
        if row is None:
            logger.warning("shadow sell with no position: %s", symbol)
            return
        qty1, avg1 = position_after_fill(float(row.qty), float(row.avgEntryPrice),
                                         qty, price, "sell")
        if qty1 <= 0:
            await self._db.engineposition.delete(
                where={"sleeve_symbol": {"sleeve": self._sleeve, "symbol": symbol}}
            )
        else:
            await self._db.engineposition.update(
                where={"sleeve_symbol": {"sleeve": self._sleeve, "symbol": symbol}},
                data={"qty": qty1, "avgEntryPrice": avg1},
            )
```

Note: the cron (Task 12) sets `convictionScore/sourceTags/reportRef/thesis/stopPrice` on the position row right after a fill lands — the shadow client keeps only qty/price math so it stays broker-shaped.

- [ ] **Step 5: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_shadow_client.py tests/test_execution_daily.py tests/test_execution_weekly.py -v`
Expected: all PASS

- [ ] **Step 6: Commit**

```bash
git add execution/broker/shadow_client.py execution/sleeve_service.py tests/test_shadow_client.py
git commit -m "feat(autopilot): ShadowBrokerClient — honesty-rule fills, idempotent orders, shared position math"
```

---

### Task 9: `enforce_funnel_guardrails` — theme overlap + cross-sleeve sector caps

**Files:**
- Modify: `execution/engine/guardrails.py` (ADD a function; `enforce_guardrails` untouched)
- Test: `tests/test_funnel_guardrails.py`

**Interfaces:**
- Consumes: entry orders shaped `{symbol, side: "buy", notional, tags: {themes: [...]}, sector: Optional[str]}` (the cron resolves sector from `TickerMeta` and passes it in — guardrails stay pure/DB-free).
- Produces: `enforce_funnel_guardrails(orders, sleeve_equity, account_equity, cash_available, holdings, other_sleeve_sector_notional, allow_buys) -> Tuple[List[Dict], List[str]]` where `holdings` is `[{symbol, market_value, tags, sector}]` and `other_sleeve_sector_notional` is `{sector_name: notional}` (Sleeve B's ETF exposure by sector). Rules, applied to buys in order (sells ALWAYS pass):
  1. halted sleeve (`allow_buys=False`) drops all buys;
  2. per-theme aggregate ≤ `MAX_THEME_PCT_OF_SLEEVE * sleeve_equity` — a buy is capped by its MOST constrained theme (overlapping names count against every tag);
  3. cross-sleeve sector ≤ `MAX_SECTOR_PCT_OF_ACCOUNT * account_equity` (holding sector exposure + Sleeve B's for that sector + this buy);
  4. cash including sell proceeds, $1 min notional — same semantics as `enforce_guardrails`.
  Every adjustment appends a human-readable note (they land in the journal).

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_funnel_guardrails.py
"""Aggregate caps: overlapping themes double-count; sector cap spans sleeves."""
from execution.constants import MAX_SECTOR_PCT_OF_ACCOUNT, MAX_THEME_PCT_OF_SLEEVE
from execution.engine.guardrails import enforce_funnel_guardrails

SLEEVE, ACCOUNT = 70_000.0, 100_000.0


def _order(sym, notional, themes=(), sector=None):
    return {"symbol": sym, "side": "buy", "notional": notional,
            "tags": {"themes": list(themes)}, "sector": sector}


def _hold(sym, mv, themes=(), sector=None):
    return {"symbol": sym, "market_value": mv, "tags": {"themes": list(themes)},
            "sector": sector}


def test_theme_cap_counts_existing_exposure():
    cap = MAX_THEME_PCT_OF_SLEEVE * SLEEVE                      # 24,500
    holdings = [_hold("A", 20_000, themes=["photonics"])]
    orders = [_order("B", 8_000, themes=["photonics"])]
    adjusted, notes = enforce_funnel_guardrails(
        orders, SLEEVE, ACCOUNT, cash_available=50_000.0, holdings=holdings,
        other_sleeve_sector_notional={}, allow_buys=True,
    )
    assert adjusted[0]["notional"] == round(cap - 20_000, 2)    # capped to 4,500
    assert any("photonics" in n for n in notes)


def test_overlapping_name_counts_against_every_theme():
    holdings = [_hold("A", 20_000, themes=["photonics", "chips"])]
    orders = [_order("B", 8_000, themes=["chips"])]
    adjusted, _ = enforce_funnel_guardrails(
        orders, SLEEVE, ACCOUNT, 50_000.0, holdings, {}, True,
    )
    cap = MAX_THEME_PCT_OF_SLEEVE * SLEEVE
    assert adjusted[0]["notional"] == round(cap - 20_000, 2)


def test_sector_cap_spans_sleeves():
    cap = MAX_SECTOR_PCT_OF_ACCOUNT * ACCOUNT                   # 35,000
    holdings = [_hold("A", 10_000, sector="Technology")]
    orders = [_order("B", 10_000, sector="Technology")]
    adjusted, notes = enforce_funnel_guardrails(
        orders, SLEEVE, ACCOUNT, 50_000.0, holdings,
        other_sleeve_sector_notional={"Technology": 20_000.0}, allow_buys=True,
    )
    assert adjusted[0]["notional"] == round(cap - 30_000, 2)    # 5,000 left
    assert any("sector" in n.lower() for n in notes)


def test_halted_drops_buys_sells_pass():
    orders = [_order("B", 5_000), {"symbol": "A", "side": "sell",
                                   "est_notional": 3_000.0, "qty": 10}]
    adjusted, notes = enforce_funnel_guardrails(
        orders, SLEEVE, ACCOUNT, 50_000.0, [], {}, allow_buys=False,
    )
    assert [o["side"] for o in adjusted] == ["sell"]
    assert any("halted" in n for n in notes)


def test_cash_includes_sell_proceeds_and_dust_dropped():
    orders = [{"symbol": "A", "side": "sell", "est_notional": 3_000.0, "qty": 10},
              _order("B", 3_500)]
    adjusted, _ = enforce_funnel_guardrails(
        orders, SLEEVE, ACCOUNT, cash_available=1_000.0, holdings=[],
        other_sleeve_sector_notional={}, allow_buys=True,
    )
    buy = [o for o in adjusted if o["side"] == "buy"][0]
    assert buy["notional"] == 3_500.0                            # 1k cash + 3k proceeds
    adjusted2, _ = enforce_funnel_guardrails(
        [_order("C", 3_500)], SLEEVE, ACCOUNT, cash_available=0.5, holdings=[],
        other_sleeve_sector_notional={}, allow_buys=True,
    )
    assert adjusted2 == []                                       # below $1 Alpaca minimum
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_funnel_guardrails.py -v`
Expected: FAIL with `ImportError: cannot import name 'enforce_funnel_guardrails'`

- [ ] **Step 3: Implement — append to `execution/engine/guardrails.py`**

```python
from collections import defaultdict

from execution.constants import MAX_THEME_PCT_OF_SLEEVE  # add to existing import line


def enforce_funnel_guardrails(
    orders: List[Dict[str, Any]], sleeve_equity: float, account_equity: float,
    cash_available: float, holdings: List[Dict[str, Any]],
    other_sleeve_sector_notional: Dict[str, float], allow_buys: bool = True,
) -> Tuple[List[Dict[str, Any]], List[str]]:
    """Sleeve A (funnel) guardrails. Sells always pass. Buys shrink through:
    theme overlap cap → cross-sleeve sector cap → cash (incl. sell proceeds)."""
    notes: List[str] = []
    adjusted: List[Dict[str, Any]] = []

    theme_used: Dict[str, float] = defaultdict(float)
    sector_used: Dict[str, float] = defaultdict(float)
    for h in holdings:
        for slug in (h.get("tags") or {}).get("themes", []):
            theme_used[slug] += h["market_value"]
        if h.get("sector"):
            sector_used[h["sector"]] += h["market_value"]
    for sector, notional in (other_sleeve_sector_notional or {}).items():
        sector_used[sector] += notional

    theme_cap = MAX_THEME_PCT_OF_SLEEVE * sleeve_equity
    sector_cap = MAX_SECTOR_PCT_OF_ACCOUNT * account_equity
    cash = cash_available + sum(
        o.get("est_notional", 0.0) for o in orders if o["side"] == "sell"
    )

    for order in orders:
        if order["side"] == "sell":
            adjusted.append(order)
            continue
        if not allow_buys:
            notes.append(f"{order['symbol']}: buy dropped — sleeve halted (circuit breaker)")
            continue
        notional = float(order["notional"])
        for slug in (order.get("tags") or {}).get("themes", []):
            room = theme_cap - theme_used[slug]
            if notional > room:
                notes.append(
                    f"{order['symbol']}: capped by theme '{slug}' aggregate "
                    f"({notional:.2f} -> {max(room, 0.0):.2f})"
                )
                notional = max(room, 0.0)
        sector = order.get("sector")
        if sector:
            room = sector_cap - sector_used[sector]
            if notional > room:
                notes.append(
                    f"{order['symbol']}: capped by cross-sleeve sector cap '{sector}' "
                    f"({notional:.2f} -> {max(room, 0.0):.2f})"
                )
                notional = max(room, 0.0)
        if notional > cash:
            notes.append(
                f"{order['symbol']}: buy capped by available cash "
                f"({notional:.2f} -> {cash:.2f})"
            )
            notional = cash
        if notional < _ALPACA_MIN_NOTIONAL:
            notes.append(f"{order['symbol']}: buy dropped — below minimum notional")
            continue
        cash -= notional
        for slug in (order.get("tags") or {}).get("themes", []):
            theme_used[slug] += notional
        if sector:
            sector_used[sector] += notional
        adjusted.append({**order, "notional": round(notional, 2)})
    return adjusted, notes
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_funnel_guardrails.py tests/test_execution_orders.py -v`
Expected: all PASS (existing guardrail tests included — `enforce_guardrails` untouched)

- [ ] **Step 5: Commit**

```bash
git add execution/engine/guardrails.py tests/test_funnel_guardrails.py
git commit -m "feat(autopilot): funnel guardrails — overlapping-theme + cross-sleeve sector caps"
```

---

### Task 10: `execution/funnel/research_budget.py` — DB-backed budgets + full-run handshake

**Files:**
- Create: `execution/funnel/research_budget.py`
- Test: `tests/test_funnel_budget.py`

**Interfaces:**
- Consumes: `api.services.weekly_signal_service.WeeklySignalService` (`find_fresh_result`, `upgrade_to_full`) and `extract_signals_from_result` from the same module; `api.services.analysis_service.run_stock_analysis`; `BATCH_SYSTEM_USER_ID` env (same operator id the batch uses). Quarters: `from inngest_app.functions.weekly_batch import _QUARTERS` if it is module-level; if it is defined inside the guarded registration closure, copy its exact expression here with a `# mirrors weekly_batch` comment (confirm by reading `inngest_app/functions/weekly_batch.py:20-45`).
- Produces:
  - `async full_runs_used(db, run_date) -> int` — count of `WeeklySignal` rows with `runDate == run_date`, `tier == "full"`, and `escalationReasons` containing `"sleeve_a_funnel"`. DB-derived so Inngest step retries can never double-spend (the tiered-batch $3.50 lesson).
  - `async ensure_signal_row(db, ticker, run_date, current_price, screen_score) -> None` — upsert a minimal `engine_light` row so `upgrade_to_full`'s update has a target (free-ride names may lack one).
  - `async commission_full_run(db, ticker, run_date, current_price, screen_score, analyze=None) -> Dict` — returns `{"status": "reused"|"upgraded"|"budget_exhausted"|"failed", "signals": Optional[Dict]}`. Order: fresh `StockResult` reuse (free, no budget slot) → budget check → paid `run_stock_analysis` (injectable via `analyze` for tests) → `upgrade_to_full(escalation_reasons=["sleeve_a_funnel"])`. `signals` is `extract_signals_from_result(result, ticker=ticker)` output — the cron feeds it back into `compute_conviction` (keys: `verdict`, `fairValue` → recompute `fair_value_gap_pct` against the screen price; `insiderScore/darkPoolScore/sentimentScore` map to their conviction inputs).
  - IMPORTANT: analyze (paid) and persist (free) run in SEPARATE Inngest steps at the cron layer (Task 12); this module only provides the pieces.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_funnel_budget.py
"""Budget counting is DB-derived; reuse is free; budget stops paid runs."""
import asyncio
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

from execution.funnel import research_budget as rb

RUN_DATE = datetime(2026, 7, 13, tzinfo=timezone.utc)


def _run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


def test_full_runs_used_counts_only_funnel_rows():
    db = MagicMock()
    rows = [MagicMock(escalationReasons=["sleeve_a_funnel"]),
            MagicMock(escalationReasons=["prior_buy"]),
            MagicMock(escalationReasons=None)]
    db.weeklysignal.find_many = AsyncMock(return_value=rows)
    assert _run(rb.full_runs_used(db, RUN_DATE)) == 1
    where = db.weeklysignal.find_many.call_args.kwargs["where"]
    assert where == {"runDate": RUN_DATE, "tier": "full"}


def test_commission_reuses_fresh_report_without_budget():
    db = MagicMock()
    svc = MagicMock()
    svc.find_fresh_result = AsyncMock(return_value={"rating": "BUY", "status": "completed"})
    with patch.object(rb, "_service", return_value=svc), \
         patch.object(rb, "extract_signals_from_result",
                      return_value={"verdict": "buy", "fairValue": 30.0}) as ex:
        out = _run(rb.commission_full_run(db, "NVDA", RUN_DATE, 25.0, 6.0))
    assert out["status"] == "reused" and out["signals"]["verdict"] == "buy"
    ex.assert_called_once()


def test_commission_respects_budget():
    db = MagicMock()
    svc = MagicMock()
    svc.find_fresh_result = AsyncMock(return_value=None)
    with patch.object(rb, "_service", return_value=svc), \
         patch.object(rb, "full_runs_used", new=AsyncMock(return_value=99)):
        out = _run(rb.commission_full_run(db, "AEHR", RUN_DATE, 20.0, 6.0))
    assert out == {"status": "budget_exhausted", "signals": None}


def test_commission_pays_upgrades_and_returns_signals():
    db = MagicMock()
    db.weeklysignal.find_unique = AsyncMock(return_value=None)
    db.weeklysignal.upsert = AsyncMock()
    svc = MagicMock()
    svc.find_fresh_result = AsyncMock(return_value=None)
    svc.upgrade_to_full = AsyncMock(return_value=True)
    analyze = AsyncMock(return_value={"rating": "HOLD", "status": "completed"})
    with patch.object(rb, "_service", return_value=svc), \
         patch.object(rb, "full_runs_used", new=AsyncMock(return_value=0)), \
         patch.object(rb, "extract_signals_from_result",
                      return_value={"verdict": "hold", "fairValue": 24.0}):
        out = _run(rb.commission_full_run(db, "AEHR", RUN_DATE, 20.0, 6.0, analyze=analyze))
    assert out["status"] == "upgraded" and out["signals"]["verdict"] == "hold"
    analyze.assert_awaited_once()
    kwargs = svc.upgrade_to_full.call_args.kwargs
    assert kwargs["escalation_reasons"] == ["sleeve_a_funnel"]


def test_commission_failed_analysis_is_failed_not_crash():
    db = MagicMock()
    db.weeklysignal.find_unique = AsyncMock(return_value=None)
    db.weeklysignal.upsert = AsyncMock()
    svc = MagicMock()
    svc.find_fresh_result = AsyncMock(return_value=None)
    analyze = AsyncMock(side_effect=RuntimeError("api down"))
    with patch.object(rb, "_service", return_value=svc), \
         patch.object(rb, "full_runs_used", new=AsyncMock(return_value=0)):
        out = _run(rb.commission_full_run(db, "AEHR", RUN_DATE, 20.0, 6.0, analyze=analyze))
    assert out == {"status": "failed", "signals": None}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_funnel_budget.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Implement**

```python
# execution/funnel/research_budget.py
"""Two-tier research budgets + the entry handshake: nothing enters the book
on light data. Budget counts are DB-derived (rows marked sleeve_a_funnel),
so Inngest step retries can never double-spend."""
import logging
import os
from datetime import datetime
from typing import Any, Callable, Dict, Optional

from api.services.weekly_signal_service import (
    WeeklySignalService, extract_signals_from_result,
)
from execution.constants import FULL_RUNS_PER_WEEK, FRESH_REPORT_DAYS

logger = logging.getLogger(__name__)

_FUNNEL_MARKER = "sleeve_a_funnel"


def _service(db) -> WeeklySignalService:
    return WeeklySignalService(db=db)


async def full_runs_used(db, run_date: datetime) -> int:
    rows = await db.weeklysignal.find_many(where={"runDate": run_date, "tier": "full"})
    return sum(1 for r in rows if _FUNNEL_MARKER in (r.escalationReasons or []))


async def ensure_signal_row(
    db, ticker: str, run_date: datetime, current_price: float, screen_score: float,
) -> None:
    from prisma import Json  # noqa: PLC0415

    existing = await db.weeklysignal.find_unique(
        where={"ticker_runDate": {"ticker": ticker, "runDate": run_date}}
    )
    if existing is None:
        await db.weeklysignal.upsert(
            where={"ticker_runDate": {"ticker": ticker, "runDate": run_date}},
            data={"create": {"ticker": ticker, "runDate": run_date,
                             "tier": "engine_light", "currentPrice": current_price,
                             "screenerScore": screen_score,
                             "escalationReasons": Json([_FUNNEL_MARKER])},
                  "update": {}},
        )


async def commission_full_run(
    db, ticker: str, run_date: datetime, current_price: float, screen_score: float,
    analyze: Optional[Callable[..., Any]] = None,
) -> Dict[str, Any]:
    svc = _service(db)
    try:
        fresh = await svc.find_fresh_result(ticker, max_age_days=FRESH_REPORT_DAYS)
        if fresh is not None:
            signals = extract_signals_from_result(fresh, ticker=ticker)
            if signals is not None:
                return {"status": "reused", "signals": signals}

        if await full_runs_used(db, run_date) >= FULL_RUNS_PER_WEEK:
            return {"status": "budget_exhausted", "signals": None}

        if analyze is None:
            from api.services.analysis_service import run_stock_analysis  # noqa: PLC0415
            # Quarters: reuse the batch's definition (see Interfaces note).
            from inngest_app.functions.weekly_batch import _QUARTERS  # noqa: PLC0415
            analyze = lambda t: run_stock_analysis(  # noqa: E731
                ticker=t, quarters=_QUARTERS, news_days_back=30,
                user_id=os.getenv("BATCH_SYSTEM_USER_ID"),
            )
        result = await analyze(ticker)
        signals = extract_signals_from_result(result, ticker=ticker)
        if signals is None:
            return {"status": "failed", "signals": None}
        await ensure_signal_row(db, ticker, run_date, current_price, screen_score)
        ok = await svc.upgrade_to_full(
            ticker=ticker, run_date=run_date, result=result,
            escalation_score=0.0, escalation_reasons=[_FUNNEL_MARKER],
        )
        return {"status": "upgraded" if ok else "failed",
                "signals": signals if ok else None}
    except Exception:  # noqa: BLE001 — a failed handshake defers the entry, never crashes
        logger.exception("commission_full_run failed for %s", ticker)
        return {"status": "failed", "signals": None}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_funnel_budget.py -v`
Expected: 5 PASS

- [ ] **Step 5: Commit**

```bash
git add execution/funnel/research_budget.py tests/test_funnel_budget.py
git commit -m "feat(autopilot): research budgets + full-run entry handshake (retry-safe, reuse-first)"
```

---

### Task 11: Journal types + step-split handshake helpers

**Files:**
- Modify: `execution/reporting.py`, `execution/funnel/research_budget.py`
- Test: `tests/test_funnel_budget.py` (extend), `tests/test_execution_alerts.py` (regression only)

**Interfaces:**
- Produces:
  - `REPORT_TYPES` gains: `"funnel_summary", "entry_order", "entry_filled", "entry_missed", "entry_deferred", "exit_stop", "exit_sell_verdict", "exit_outcompeted", "theme_review", "risk_trim", "light_run_failure"`.
  - In `research_budget.py`, the step-split pieces the cron needs so PAID analyze and free persist live in SEPARATE Inngest steps (the tiered-batch $3.50 lesson — a persist bug must never re-bill):
    - `async reuse_or_budget(db, ticker, run_date) -> Dict` — `{"action": "reuse", "signals": {...}} | {"action": "analyze"} | {"action": "skip", "reason": "budget_exhausted"}`.
    - `async run_paid_analysis(ticker) -> Dict` — the `run_stock_analysis` call exactly as in `commission_full_run`'s default path (quarters/user_id identical).
    - `async persist_full(db, ticker, run_date, result, current_price, screen_score) -> Dict` — `ensure_signal_row` + `upgrade_to_full(escalation_reasons=["sleeve_a_funnel"])` + `extract_signals_from_result`; returns `{"status": "upgraded"|"failed", "signals": ...}`.
    - Refactor `commission_full_run` to compose these three (its tests from Task 10 must stay green unmodified — that is the refactor's parity proof).

- [ ] **Step 1: Write the failing tests (append to `tests/test_funnel_budget.py`)**

```python
def test_reuse_or_budget_three_outcomes():
    db = MagicMock()
    svc = MagicMock()
    # reuse
    svc.find_fresh_result = AsyncMock(return_value={"rating": "BUY", "status": "completed"})
    with patch.object(rb, "_service", return_value=svc), \
         patch.object(rb, "extract_signals_from_result", return_value={"verdict": "buy"}):
        assert _run(rb.reuse_or_budget(db, "NVDA", RUN_DATE))["action"] == "reuse"
    # analyze
    svc.find_fresh_result = AsyncMock(return_value=None)
    with patch.object(rb, "_service", return_value=svc), \
         patch.object(rb, "full_runs_used", new=AsyncMock(return_value=0)):
        assert _run(rb.reuse_or_budget(db, "AEHR", RUN_DATE)) == {"action": "analyze"}
    # skip
    with patch.object(rb, "_service", return_value=svc), \
         patch.object(rb, "full_runs_used", new=AsyncMock(return_value=99)):
        out = _run(rb.reuse_or_budget(db, "AEHR", RUN_DATE))
        assert out == {"action": "skip", "reason": "budget_exhausted"}


def test_persist_full_marks_funnel_and_returns_signals():
    db = MagicMock()
    db.weeklysignal.find_unique = AsyncMock(return_value=None)
    db.weeklysignal.upsert = AsyncMock()
    svc = MagicMock()
    svc.upgrade_to_full = AsyncMock(return_value=True)
    with patch.object(rb, "_service", return_value=svc), \
         patch.object(rb, "extract_signals_from_result", return_value={"verdict": "hold"}):
        out = _run(rb.persist_full(db, "AEHR", RUN_DATE,
                                   {"status": "completed"}, 20.0, 6.0))
    assert out["status"] == "upgraded" and out["signals"]["verdict"] == "hold"
    assert svc.upgrade_to_full.call_args.kwargs["escalation_reasons"] == ["sleeve_a_funnel"]
```

And a reporting test (append to `tests/test_funnel_constants.py`):

```python
def test_funnel_report_types_registered():
    from execution.reporting import REPORT_TYPES
    for t in ("funnel_summary", "entry_order", "entry_filled", "entry_missed",
              "entry_deferred", "exit_stop", "exit_sell_verdict", "exit_outcompeted",
              "theme_review", "risk_trim", "light_run_failure"):
        assert t in REPORT_TYPES
```

- [ ] **Step 2: Run to verify failures**

Run: `python3 -m pytest tests/test_funnel_budget.py tests/test_funnel_constants.py -v`
Expected: new tests FAIL (`AttributeError: reuse_or_budget` / missing types)

- [ ] **Step 3: Implement**

In `execution/reporting.py`, replace the `REPORT_TYPES` frozenset with:

```python
REPORT_TYPES = frozenset({
    "theme_proposal", "membership_change", "theme_retired",
    "validation_failure", "engine_failure", "rebalance_summary",
    "breaker_event",
    # Phase 3C — Sleeve A funnel (shadow mode)
    "funnel_summary", "entry_order", "entry_filled", "entry_missed",
    "entry_deferred", "exit_stop", "exit_sell_verdict", "exit_outcompeted",
    "theme_review", "risk_trim", "light_run_failure",
})
```

In `execution/funnel/research_budget.py`, add the three functions and re-express `commission_full_run` through them:

```python
async def reuse_or_budget(db, ticker: str, run_date: datetime) -> Dict[str, Any]:
    svc = _service(db)
    fresh = await svc.find_fresh_result(ticker, max_age_days=FRESH_REPORT_DAYS)
    if fresh is not None:
        signals = extract_signals_from_result(fresh, ticker=ticker)
        if signals is not None:
            return {"action": "reuse", "signals": signals}
    if await full_runs_used(db, run_date) >= FULL_RUNS_PER_WEEK:
        return {"action": "skip", "reason": "budget_exhausted"}
    return {"action": "analyze"}


async def run_paid_analysis(ticker: str) -> Dict[str, Any]:
    from api.services.analysis_service import run_stock_analysis  # noqa: PLC0415
    from inngest_app.functions.weekly_batch import _QUARTERS  # noqa: PLC0415

    return await run_stock_analysis(
        ticker=ticker, quarters=_QUARTERS, news_days_back=30,
        user_id=os.getenv("BATCH_SYSTEM_USER_ID"),
    )


async def persist_full(
    db, ticker: str, run_date: datetime, result: Dict[str, Any],
    current_price: float, screen_score: float,
) -> Dict[str, Any]:
    signals = extract_signals_from_result(result, ticker=ticker)
    if signals is None:
        return {"status": "failed", "signals": None}
    await ensure_signal_row(db, ticker, run_date, current_price, screen_score)
    ok = await _service(db).upgrade_to_full(
        ticker=ticker, run_date=run_date, result=result,
        escalation_score=0.0, escalation_reasons=[_FUNNEL_MARKER],
    )
    return {"status": "upgraded" if ok else "failed", "signals": signals if ok else None}


async def commission_full_run(
    db, ticker: str, run_date: datetime, current_price: float, screen_score: float,
    analyze: Optional[Callable[..., Any]] = None,
) -> Dict[str, Any]:
    """All-in-one handshake for non-Inngest callers. The cron uses the three
    pieces above in SEPARATE steps so a persist retry can never re-bill."""
    try:
        gate = await reuse_or_budget(db, ticker, run_date)
        if gate["action"] == "reuse":
            return {"status": "reused", "signals": gate["signals"]}
        if gate["action"] == "skip":
            return {"status": "budget_exhausted", "signals": None}
        result = await (analyze or run_paid_analysis)(ticker)
        return await persist_full(db, ticker, run_date, result, current_price, screen_score)
    except Exception:  # noqa: BLE001
        logger.exception("commission_full_run failed for %s", ticker)
        return {"status": "failed", "signals": None}
```

The Task 10 tests define the exact contract; they must stay green WITHOUT edits — that is this refactor's parity proof. (`persist_full` returns `"upgraded"/"failed"`, matching what Task 10's tests assert.)

- [ ] **Step 4: Run to verify passes**

Run: `python3 -m pytest tests/test_funnel_budget.py tests/test_funnel_constants.py tests/test_execution_alerts.py -v`
Expected: all PASS

- [ ] **Step 5: Commit**

```bash
git add execution/reporting.py execution/funnel/research_budget.py tests/test_funnel_budget.py tests/test_funnel_constants.py
git commit -m "feat(autopilot): funnel journal types + step-split research handshake"
```

---

### Task 12: The `sleeve-a-funnel` Inngest cron

**Files:**
- Create: `inngest_app/functions/sleeve_a_funnel.py`
- Modify: `inngest_app/index.py` (register; 7 functions), `tests/test_inngest_registration.py` (count 6 → 7), `execution/sleeve_service.py` (`init_sleeve_state` gains `mode: str = "live"` passthrough)
- Test: `tests/test_sleeve_a_funnel_cron.py`

**Interfaces:**
- Consumes: everything above. Cron id `sleeve-a-funnel`, `inngest.TriggerCron(cron="0 16 * * 1")` (Mondays 16:00 UTC), `on_failure` journaling `engine_failure` (severity critical) — mirror `execution_daily.py`'s `_register_inngest_function` pattern exactly (guarded import, module exports `None` without SDK).
- Produces: the weekly shadow pass. Step layout (every step memoized by Inngest; paid analyze steps are per-symbol and isolated):

```
run-date            → Monday 00:00 UTC datetime (replay-safe, computed in-step)
load-outlook        → get_latest_outlook; age > OUTLOOK_MAX_AGE_DAYS ⇒ journal funnel skip, END
ensure-sleeve-a     → SleeveState A: init_sleeve_state(mode="shadow",
                      cash = SLEEVE_A_FRACTION × broker equity,
                      inceptionSpyClose = previous SPY close) on first run;
                      halted/frozen state only blocks buys, pass still runs
assemble-universe   → load_theme_members + research_feed watchlist +
                      current A positions + fetch_industry_holdings (to_thread)
screen              → fetch_ohlcv_batch(universe + SPY) (to_thread), apply_floors,
                      screen_row all names (quality=None), preliminary rank,
                      quality re-rank of top 40 via get_valuation_metrics +
                      HealthScorer().calculate_valuation_score, final rank,
                      select_light_slots (stale holdings first)
light-runs          → ONE step, per-name guards: light_run_one + persist_light_signal
                      for slot winners; failures journal light_run_failure and skip
conviction-table    → holdings + candidates scored with compute_conviction
                      (inputs from this run's light rows / latest full rows;
                      report_age_days from the source row's createdAt)
theme-review-*      → per flagged holding (all source themes retired):
                      review-check-{sym} / review-analyze-{sym} (paid) /
                      review-persist-{sym}; re-score with hunting_bonus=0.0;
                      sets theme_review_failed; journals theme_review
plan-decisions      → plan_decisions(...)
execute-sells       → shadow sells for exits+trims at last close
                      (client_order_id f"shadow-A-{sym}-{run_date:%Y%m%d}-sell"),
                      journal exit_*/risk_trim, update_sleeve_cash
entry-handshakes    → per entry_queue symbol, budget-aware:
                      handshake-check-{sym} (reuse_or_budget) /
                      handshake-analyze-{sym} (run_paid_analysis — PAID, own step) /
                      handshake-persist-{sym} (persist_full);
                      re-score conviction with full signals; SELL ⇒ veto journal;
                      budget skip ⇒ journal entry_deferred
place-entries       → size_entry + enforce_funnel_guardrails (sector from
                      TickerMeta, Sleeve B sector notional from its positions)
                      → submit_limit_buy per surviving order (deterministic
                      client_order_id f"shadow-A-{sym}-{run_date:%Y%m%d}"),
                      set position metadata after fills land (daily cron);
                      journal entry_order per order
funnel-summary      → ONE funnel_summary journal row: universe counts +
                      exclusions, screen top-20, light spend, conviction table,
                      every decision + guardrail note, budget usage
```

- The cron NEVER raises: each step body catches, journals `engine_failure`, and degrades per the spec table (§11). Buys blocked when SleeveState A is halted/frozen (pass `allow_buys=False` to guardrails).
- Sleeve A equity for sizing = `cashBalance + Σ(position qty × latest close)`.
- `init_sleeve_state` change: add `mode: str = "live"` parameter, stored on create only — read `execution/sleeve_service.py:17-29` and thread it through; existing callers unchanged (default preserves Sleeve B behavior).

**Sizing inputs in `place-entries`:** deployable = `REGIME_INVESTED_FRACTION[outlook.regime] × sleeve_equity − Σ current position market values − Σ already-queued entry notionals`; `size_entry` receives it as `deployable_remaining`, and `cash_available` is `SleeveState.cashBalance` plus planned sell proceeds. This is the SAME regime gate Sleeve B uses — no second regime system.

**Structure the cron for testability:** put the pass logic in plain module-level async helpers (`_load_and_gate_outlook(db, now)`, `_assemble(db, outlook)`, `_screen(universe, outlook)`, `_decide_and_execute(db, ctx_data)`) that the Inngest steps call one-to-one — tests below hit the helpers directly, matching how `tests/test_execution_daily.py` tests `build_sleeve_snapshot`.

**Test file `tests/test_sleeve_a_funnel_cron.py`** — all broker/network/LLM boundaries stubbed via `unittest.mock`:

```python
# tests/test_sleeve_a_funnel_cron.py
"""Funnel cron: gates, budget discipline, shadow orders, journal."""
import asyncio
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import inngest_app.functions.sleeve_a_funnel as saf

NOW = datetime(2026, 7, 13, 16, 0, tzinfo=timezone.utc)


def _run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


def test_module_imports_without_inngest_sdk():
    assert hasattr(saf, "sleeve_a_funnel")   # None without SDK is fine


def test_stale_outlook_skips_pass_and_journals():
    db = MagicMock()
    stale = MagicMock(runDate=NOW - timedelta(days=10), regime="neutral")
    with patch.object(saf, "get_latest_outlook", new=AsyncMock(return_value=stale)), \
         patch.object(saf, "write_report", new=AsyncMock()) as report:
        out = _run(saf._load_and_gate_outlook(db, now=NOW))
    assert out is None
    kwargs = report.call_args.kwargs if report.call_args.kwargs else {}
    args = report.call_args.args
    assert "engine_failure" in (list(args) + list(kwargs.values()))


def test_entry_requires_full_run_and_respects_budget():
    db = MagicMock()
    client = MagicMock()
    client.submit_limit_buy = AsyncMock()
    with patch.object(saf, "reuse_or_budget",
                      new=AsyncMock(return_value={"action": "skip",
                                                  "reason": "budget_exhausted"})), \
         patch.object(saf, "write_report", new=AsyncMock()) as report:
        placed = _run(saf._handshake_and_enter(
            db, client, entry_queue=["AEHR"],
            candidates_by_symbol={"AEHR": {"conviction": 80.0, "screen": {
                "price": 20.0, "sma20": 19.0, "atr": 1.0, "atr_pct": 0.05,
                "ext_atr": 0.5, "liquidity_adv_usd": 5e6,
                "tags": {"themes": ["photonics"]}, "screen_score": 6.0}}},
            run_date=NOW, sleeve_equity=70_000.0, deployable=49_000.0,
            cash_available=49_000.0, holdings=[], sector_by_symbol={},
            other_sleeve_sector_notional={}, allow_buys=True, step=None,
        ))
    assert placed == []
    client.submit_limit_buy.assert_not_called()
    types = [c.args[0] if c.args else c.kwargs.get("report_type")
             for c in report.call_args_list]
    assert "entry_deferred" in types


def test_full_pass_places_shadow_order_with_deterministic_id():
    db = MagicMock()
    client = MagicMock()
    client.submit_limit_buy = AsyncMock()
    signals = {"verdict": "hold", "fairValue": 26.0, "insiderScore": 7.0,
               "darkPoolScore": None, "sentimentScore": 6.0}
    with patch.object(saf, "reuse_or_budget",
                      new=AsyncMock(return_value={"action": "reuse", "signals": signals})), \
         patch.object(saf, "write_report", new=AsyncMock()):
        placed = _run(saf._handshake_and_enter(
            db, client, entry_queue=["AEHR"],
            candidates_by_symbol={"AEHR": {"conviction": 80.0, "screen": {
                "price": 20.0, "sma20": 19.0, "atr": 1.0, "atr_pct": 0.05,
                "ext_atr": 0.5, "liquidity_adv_usd": 5e6,
                "tags": {"themes": ["photonics"]}, "screen_score": 6.0}}},
            run_date=NOW, sleeve_equity=70_000.0, deployable=49_000.0,
            cash_available=49_000.0, holdings=[], sector_by_symbol={},
            other_sleeve_sector_notional={}, allow_buys=True, step=None,
        ))
    assert len(placed) == 1
    kwargs = client.submit_limit_buy.call_args.kwargs
    assert kwargs["client_order_id"] == "shadow-A-AEHR-20260713"
    assert kwargs["limit_price"] == 20.0          # not extended → limit at close


def test_full_run_sell_verdict_vetoes_entry():
    db = MagicMock()
    client = MagicMock()
    client.submit_limit_buy = AsyncMock()
    with patch.object(saf, "reuse_or_budget",
                      new=AsyncMock(return_value={"action": "reuse",
                                                  "signals": {"verdict": "sell"}})), \
         patch.object(saf, "write_report", new=AsyncMock()):
        placed = _run(saf._handshake_and_enter(
            db, client, entry_queue=["BAD"],
            candidates_by_symbol={"BAD": {"conviction": 80.0, "screen": {
                "price": 20.0, "sma20": 19.0, "atr": 1.0, "atr_pct": 0.05,
                "ext_atr": 0.5, "liquidity_adv_usd": 5e6, "tags": {"themes": []},
                "screen_score": 6.0}}},
            run_date=NOW, sleeve_equity=70_000.0, deployable=49_000.0,
            cash_available=49_000.0, holdings=[], sector_by_symbol={},
            other_sleeve_sector_notional={}, allow_buys=True, step=None,
        ))
    assert placed == []
    client.submit_limit_buy.assert_not_called()
```

This fixes `_handshake_and_enter`'s signature — implement exactly: `async def _handshake_and_enter(db, client, entry_queue, candidates_by_symbol, run_date, sleeve_equity, deployable, cash_available, holdings, sector_by_symbol, other_sleeve_sector_notional, allow_buys, step) -> List[Dict]` (returns placed-order dicts; `step=None` runs the analyze path inline — when running under Inngest, `step` wraps the paid call in its own memoized `handshake-analyze-{sym}` step; re-scores conviction with full signals; sizes via `size_entry`; filters via `enforce_funnel_guardrails`; submits via `client.submit_limit_buy(symbol=..., qty=round(notional/limit, 4), limit_price=..., expires_at=..., journal=..., client_order_id=f"shadow-A-{{sym}}-{{run_date:%Y%m%d}}")`).

Write the four tests first (failing), then implement the cron module against the step layout above, then registration:

In `inngest_app/index.py`: import `sleeve_a_funnel` alongside the others, add to `ACTIVE_FUNCTIONS`, and extend the module docstring with: `Owner decision (2026-07-09, Phase 3C): register sleeve_a_funnel (docs/superpowers/specs/2026-07-09-phase3c-sleeve-a-funnel-design.md).`
In `tests/test_inngest_registration.py`: expected count 6 → 7, add `"sleeve-a-funnel"` to the expected id set (read the test to match its exact assertion style).

- [ ] **Step 1: Write the four failing tests** (as specified above, fully stubbed)
- [ ] **Step 2: Run to verify failures** — `python3 -m pytest tests/test_sleeve_a_funnel_cron.py -v` → `ModuleNotFoundError`
- [ ] **Step 3: Implement `inngest_app/functions/sleeve_a_funnel.py`** per the step layout (mirror `execution_daily.py`'s registration/guard skeleton and `weekly_batch.py`'s per-symbol paid-step pattern)
- [ ] **Step 4: `init_sleeve_state` mode param + registration edits**
- [ ] **Step 5: Run to verify passes** — `python3 -m pytest tests/test_sleeve_a_funnel_cron.py tests/test_inngest_registration.py tests/test_execution_daily.py -v` → all PASS
- [ ] **Step 6: Commit**

```bash
git add inngest_app/functions/sleeve_a_funnel.py inngest_app/index.py execution/sleeve_service.py tests/test_sleeve_a_funnel_cron.py tests/test_inngest_registration.py
git commit -m "feat(autopilot): sleeve-a-funnel weekly cron — shadow pass end to end (Mon 16:00 UTC)"
```

---

### Task 13: Daily cron — shadow fills, trailing stops, Sleeve A snapshot + breaker

**Files:**
- Modify: `inngest_app/functions/execution_daily.py`
- Test: `tests/test_sleeve_a_daily.py`

**Interfaces:**
- Consumes: `ShadowBrokerClient` (Task 8), `compute_atr`/`fetch_ohlcv_batch` (Task 3), `write_report`, `update_sleeve_cash`, `store_snapshot`, existing breaker helpers in `execution/engine/circuit_breaker.py` (read it first; reuse for Sleeve A exactly as the daily cron does for B, including the transition-only alert fix from Task 15 of Phase 3B).
- Produces — new steps appended to `execution_daily` AFTER the existing Sleeve B steps, all no-ops when SleeveState A does not exist (funnel not yet live) and all failure-isolated:
  1. `sleeve-a-fills`: `get_open_orders()`; `fetch_ohlcv_batch(symbols, period="5d")` (to_thread); `settle_open_order(order, day_high, day_low, now)` per order using TODAY's bar; accumulate cash deltas → `update_sleeve_cash`; journal `entry_filled` per fill and `entry_missed` per expiry.
  2. `sleeve-a-stops` (pure rule, tested directly):
     - `new_high_water = max(highWaterClose or entry price, today_close)`
     - `stop = new_high_water − TRAILING_STOP_ATR_MULT × ATR(14)`
     - persist both on the position row
     - triggered when `today_low <= stop`; honest fill price: `min(stop, today_open)` if the day OPENED below the stop (gap-down — you cannot fill above the open), else `stop`
     - exit via `submit_shadow_sell(..., client_order_id=f"shadow-A-{sym}-{date:%Y%m%d}-stop")`, journal `exit_stop`, update cash
  3. `sleeve-a-snapshot`: equity = cash + Σ qty×close → `store_snapshot(sleeve="A", ...)` with the same SPY close the B snapshot uses
  4. `sleeve-a-breaker`: same −15pp-vs-SPY rule and transition-only `breaker_event` journaling as B; a trip halts Sleeve A (blocks buys; sells still pass by construction)
- Export the stop rule as module-level pure functions so tests hit them directly: `stop_levels(high_water, today_close, atr) -> Tuple[float, float]` (new high-water, stop) and `stop_fill_price(stop, today_open, today_low) -> Optional[float]` (None when not triggered).

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_sleeve_a_daily.py
"""Daily Sleeve A duties: honest fills, ATR trailing stops, snapshot math."""
from inngest_app.functions.execution_daily import stop_fill_price, stop_levels


def test_stop_ratchets_up_never_down():
    hw, stop = stop_levels(high_water=100.0, today_close=110.0, atr=4.0)
    assert (hw, stop) == (110.0, 100.0)            # 110 − 2.5×4
    hw2, stop2 = stop_levels(high_water=110.0, today_close=105.0, atr=4.0)
    assert (hw2, stop2) == (110.0, 100.0)          # close dipped: anchor holds


def test_stop_fill_honest_on_gap_down():
    assert stop_fill_price(stop=100.0, today_open=104.0, today_low=101.0) is None
    assert stop_fill_price(stop=100.0, today_open=104.0, today_low=99.0) == 100.0
    # gapped below the stop at the open — you cannot fill above the open
    assert stop_fill_price(stop=100.0, today_open=97.0, today_low=95.0) == 97.0


def test_daily_module_still_imports_without_sdk():
    import inngest_app.functions.execution_daily as mod
    assert hasattr(mod, "execution_daily")
```

Plus one integration test following `tests/test_execution_daily.py`'s existing style: SleeveState A absent → none of the new steps touch the DB (assert the shadow-order query is never made).

- [ ] **Step 2: Run to verify failures** — `python3 -m pytest tests/test_sleeve_a_daily.py -v` → `ImportError`
- [ ] **Step 3: Implement** — pure functions:

```python
def stop_levels(high_water: float, today_close: float, atr: float) -> Tuple[float, float]:
    hw = max(high_water, today_close)
    return hw, round(hw - TRAILING_STOP_ATR_MULT * atr, 2)


def stop_fill_price(stop: float, today_open: float, today_low: float) -> Optional[float]:
    if today_low > stop:
        return None
    return round(min(stop, today_open), 2)
```

then the four steps per the Interfaces block, each in its own `ctx.step.run` with the SleeveState-A-absent early return.

- [ ] **Step 4: Run to verify passes** — `python3 -m pytest tests/test_sleeve_a_daily.py tests/test_execution_daily.py -v` → all PASS
- [ ] **Step 5: Commit**

```bash
git add inngest_app/functions/execution_daily.py tests/test_sleeve_a_daily.py
git commit -m "feat(autopilot): daily shadow duties — honesty-rule fills, ATR trailing stops, Sleeve A snapshot + breaker"
```

---

### Task 14: Isolation regression — strategist exclusion + Sleeve B control group

**Files:**
- Create: `tests/test_phase3c_isolation.py`
- Test: itself

**Interfaces:**
- Consumes: `execution/strategist/prompts.py` (find the existing prompt-isolation test with `grep -rn "isolation\|strategist" tests/ | grep -i prompt` and extend alongside it, matching its approach).
- Produces: two standing guarantees.

- [ ] **Step 1: Write the tests (they should PASS immediately if Tasks 1–13 held the line — a failure here is a real leak)**

```python
# tests/test_phase3c_isolation.py
"""Phase 3C isolation: Sleeve B stays the control group; the strategist
never sees funnel data. These tests are permanent tripwires."""
import ast
import pathlib

_CONTROL_GROUP_FILES = [
    "execution/engine/sleeve_b.py",
    "execution/engine/orders.py",
    "inngest_app/functions/execution_weekly.py",
]


def test_sleeve_b_code_never_imports_funnel_modules():
    for rel in _CONTROL_GROUP_FILES:
        tree = ast.parse(pathlib.Path(rel).read_text())
        for node in ast.walk(tree):
            names = []
            if isinstance(node, ast.Import):
                names = [a.name for a in node.names]
            elif isinstance(node, ast.ImportFrom):
                names = [node.module or ""]
            for name in names:
                assert not name.startswith("execution.funnel"), (
                    f"{rel} imports {name} — Sleeve B is the control group"
                )
                assert "shadow_client" not in name, f"{rel} imports the shadow broker"


def test_strategist_prompt_never_mentions_funnel_keys():
    src = pathlib.Path("execution/strategist/prompts.py").read_text()
    for leak in ("conviction", "funnel", "entry_queue", "shadow", "engine_light"):
        assert leak not in src.lower(), (
            f"strategist prompt module references '{leak}' — Sleeve A signal leak"
        )
```

Note: if `test_strategist_prompt_never_mentions_funnel_keys` fails on a pre-existing legitimate use of a word (e.g. "conviction" already in the strategist prompt from Phase 1 — it does emit a conviction score), narrow the leak list to `("funnel", "entry_queue", "shadow", "engine_light", "sleeve_a")` and note why in the test docstring. Verify against the file before choosing.

- [ ] **Step 2: Run** — `python3 -m pytest tests/test_phase3c_isolation.py -v` → PASS (investigate ANY failure as a real leak before touching the test)
- [ ] **Step 3: Also extend the existing strategist payload-isolation test** (from Phase 3A/3B — locate it, add the funnel keys to its excluded-keys assertion so the *payload builder*, not just the prompt text, is covered)
- [ ] **Step 4: Commit**

```bash
git add tests/test_phase3c_isolation.py
git commit -m "test(autopilot): Phase 3C isolation tripwires — control group + strategist exclusion"
```

---

### Task 15: Full regression, docs, PR

**Files:**
- Modify: `docs/superpowers/specs/progress.md` (or the SDD ledger in use), memory file updates happen at session level

- [ ] **Step 1: Full suite**

Run: `python3 -m pytest tests/ -q 2>&1 | tail -20`
Expected: every Phase 3C test passes; pre-existing failure count on main (~76F/23E, unrelated legacy) NOT increased. Compare against `git stash`-free main baseline if in doubt: the delta must be zero.

- [ ] **Step 2: Diff review**

Run: `git diff main --stat`
Verify: NO diffs in `execution/engine/sleeve_b.py`, `execution/engine/orders.py`, `inngest_app/functions/execution_weekly.py`, `execution/indicators/` (except none), `api/` (except none — Task 10/11 only import from api, never modify).

- [ ] **Step 3: Push + PR**

```bash
git push -u origin autopilot-phase3c
gh pr create --title "Autopilot Phase 3C: Sleeve A funnel + small-cap guardrails (shadow mode)" --body "$(cat <<'EOF'
## Summary
- Weekly sleeve-a-funnel cron (Mon 16:00 UTC): dynamic universe → free screen →
  light runs (~$0.12, numbers only) → conviction ranking → full-run entry
  handshake → shadow limit orders. NO order reaches Alpaca (3D gate).
- Daily cron: honesty-rule shadow fills, ATR trailing stops, Sleeve A snapshot
  + circuit breaker.
- Spec: docs/superpowers/specs/2026-07-09-phase3c-sleeve-a-funnel-design.md

## Operator steps (in order)
1. BEFORE merge: `python3 -m prisma migrate deploy` against Neon prod
   (nullable columns only — safe for the running app).
2. Merge → Railway auto-deploy.
3. Inngest re-sync: verify 7 functions mounted.
4. Optional: one manual sleeve-a-funnel invoke (else first pass Monday 16:00 UTC).
5. Check /autopilot journal for funnel_summary + any engine_failure rows.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

---

## Go-Live Checklist (operator steps — after all tasks green)

1. `python3 -m prisma migrate deploy` on Neon prod **BEFORE merging** (regenerated client SELECTs new columns — same precondition as 3A/3B).
2. Merge PR → Railway deploys `main`.
3. Inngest app re-sync → expect **7** functions (was 6).
4. First funnel pass: Monday 16:00 UTC cron, or one manual invoke to smoke-test. Requires: a MarketOutlook younger than 8 days (Sunday cron), ≥1 active theme with constituents (live since 3B), linked broker row (live since Phase 2), `BATCH_SYSTEM_USER_ID` + `ANTHROPIC_API_KEY` set (both already on Railway).
5. Verify in journal: one `funnel_summary` (universe counts, top-20, decisions), `entry_order` rows for any entries, no `engine_failure`.
6. Following trading day 21:15 UTC: `entry_filled`/`entry_missed` rows + first Sleeve A `SleeveSnapshot`.
7. Budget sanity after first pass: `WeeklySignal` rows with `escalationReasons=["sleeve_a_funnel"]` — ≤ 20 `engine_light`, ≤ 2 `full`.

## Out of Scope (do not build here)

- Phase 3D: backtest/replay harness, the go-live gate, the ShadowBrokerClient→AlpacaPaperClient flip, Alpaca `client_order_id` idempotency.
- Phase 4: /autopilot dashboard funnel card (journal rows render generically until then).
- Tranched/partial entries, light-tier sentiment beyond one Haiku call, any email path (dead permanently), changes to the tiered batch or any user-facing research surface.

