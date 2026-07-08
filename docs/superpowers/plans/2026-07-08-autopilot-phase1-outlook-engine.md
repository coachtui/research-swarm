# Autopilot Phase 1: Market Outlook Engine — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build DVRG's first top-down market view: a weekly pipeline that computes sector-rotation/breadth/regime indicators from free market data, has an LLM "macro strategist" synthesize them into a structured outlook, stores it in a new `MarketOutlook` table, and emails the owner every Sunday.

**Architecture:** New isolated `execution/` package (spec: `docs/superpowers/specs/2026-07-08-execution-layer-design.md`). Pure indicator math (pandas) over closes fetched via the existing `MarketDataClient` (yfinance). A single Inngest cron function (Sunday 20:00 UTC — before the Monday 03:00 UTC weekly batch) orchestrates: fetch → indicators → strategist → store → email. All heavy logic is pure functions; the Inngest function is thin orchestration following the `send_teaser_digest.py` pattern (pure helpers at module top, guarded `_register_inngest_function()`).

**Tech Stack:** Python, pandas, yfinance (via `MarketDataClient`), langchain_anthropic `ChatAnthropic`, Prisma (python client, Neon Postgres), Inngest, Resend, pytest.

## Global Constraints

- `execution/` NEVER imports from `research_swarm.agents.**`. In Phase 1 it does not touch research data at all.
- Nothing in the research/user-facing flow imports `execution/`.
- Inngest functions follow the repo pattern: pure helpers at module top (unit-testable with no inngest/resend/prisma installed), runtime registration in `_register_inngest_function()` wrapped in `try/except` (see `inngest/functions/send_teaser_digest.py:121-198`).
- Values returned from `step.run` must be JSON-serializable — never pass `pd.Series`/`pd.DataFrame` between steps.
- LLM calls copy the conventions of `research_swarm/agents/manager/analyzer.py:59-65`: `ChatAnthropic(model="claude-sonnet-5", api_key=..., max_tokens=4096, thinking={"type": "disabled"})` — Sonnet 5 rejects non-default sampling params and must have thinking explicitly disabled; `max_tokens` must be set in the constructor.
- Prisma schema lives at `db/schema.prisma`; migrations via `python3 -m prisma migrate dev --schema=db/schema.prisma --name <name>`; regenerate client with `python3 -m prisma generate --schema=db/schema.prisma`.
- Tests live in `tests/` (pytest, `testpaths = ["tests"]`). Async tests use `@pytest.mark.asyncio` (conftest has a fallback runner if pytest-asyncio is absent).
- No new pip dependencies. pandas, yfinance, langchain_anthropic, requests, resend, prisma are all already in the project.
- Env vars used (all already exist in `.env.example` conventions): `ANTHROPIC_API_KEY`, `NEWS_API_KEY` (optional), `RESEND_API_KEY`, `OWNER_EMAIL`.
- Failure posture: degrade to inaction, never guess. Data missing → skip the week and email the owner; strategist failure → fall back to the mechanical regime, flagged `strategistStatus="fallback"`.

## Deliberate deviations from the spec (Phase 1 simplifications)

- **Weekly, not daily, indicator computation.** The spec's daily cadence exists to serve position snapshots and stops, which don't exist until Phase 2. All indicators here derive from price history on demand, so the Sunday run computes everything fresh; a daily cron adds nothing yet (YAGNI). The daily job arrives in Phase 2 alongside positions.
- **Breadth uses the 11 sector ETFs + RSP/SPY ratio, not the 191-stock universe, and omits new-highs/new-lows.** Fetching 191 histories weekly through yfinance rate limits is heavy; the ETF proxy is cheap and adequate for a regime input. Upgrade path noted in Task 4.
- **No app-level failure-alert email in Phase 1.** The spec's "email the owner on failure" posture becomes load-bearing only when positions exist (Phase 2); Phase 1 failures surface via Inngest's failure notifications and the absence of the Sunday outlook email.

## File Map

| Action | File | Responsibility |
|---|---|---|
| Modify | `db/schema.prisma` | Add `MarketOutlook` model |
| Create | `execution/__init__.py` | Package marker (empty) |
| Create | `execution/constants.py` | Sector ETF map, benchmark tickers, indicator windows |
| Create | `execution/indicators/__init__.py` | Package marker (empty) |
| Create | `execution/indicators/sector_strength.py` | Relative strength, sector ranking, rotation detection (pure) |
| Create | `execution/indicators/regime.py` | Mechanical regime classifier + one-notch override rule (pure) |
| Create | `execution/indicators/breadth.py` | Breadth metrics (pure) |
| Create | `execution/market_data.py` | Fetch closes for ETFs/SPY/RSP/VIX via MarketDataClient; `OutlookDataError` |
| Create | `execution/strategist/__init__.py` | Package marker (empty) |
| Create | `execution/strategist/prompts.py` | Strategist prompt builder (pure) |
| Create | `execution/strategist/parser.py` | Strategist JSON response parser (pure) |
| Create | `execution/strategist/agent.py` | LLM call + macro headlines fetch + fallback |
| Create | `execution/outlook_service.py` | Build/store/read `MarketOutlook` records |
| Create | `inngest/functions/weekly_outlook.py` | Sunday cron orchestration + owner email |
| Modify | `inngest/index.py` | Register the new function |
| Create | `tests/test_execution_sector_strength.py` | Unit tests |
| Create | `tests/test_execution_regime.py` | Unit tests |
| Create | `tests/test_execution_breadth.py` | Unit tests |
| Create | `tests/test_execution_market_data.py` | Unit tests (MarketDataClient mocked) |
| Create | `tests/test_execution_strategist.py` | Prompt/parser/agent tests (LLM mocked) |
| Create | `tests/test_execution_outlook_service.py` | Record building + store/read (db mocked) |
| Create | `tests/test_weekly_outlook_email.py` | Email HTML helper tests |

---

### Task 1: `MarketOutlook` Prisma model + migration

**Files:**
- Modify: `db/schema.prisma` (append after the last model)

**Interfaces:**
- Produces: table `MarketOutlook` with prisma client accessor `db.marketoutlook` used by Task 8 (`store_outlook`/`get_latest_outlook`).

- [ ] **Step 1: Add the model to `db/schema.prisma`**

Append at the end of the file:

```prisma
// ── Autopilot execution layer (docs/superpowers/specs/2026-07-08-execution-layer-design.md) ──
// Written/read ONLY by the execution/ package. The research flow never touches this.
model MarketOutlook {
  id                 String   @id @default(cuid())
  runDate            DateTime // Sunday the outlook was generated (UTC)

  // Regime
  regime             String   // final call: "risk_on" | "neutral" | "risk_off"
  regimeMechanical   String   // pure-indicator call before strategist override
  strategistOverride Boolean  @default(false)
  strategistStatus   String   @default("ok") // "ok" | "fallback"
  conviction         Float?   // strategist conviction 0.0–1.0

  // Indicators (JSON snapshots so the outlook is fully self-describing)
  sectorRankings     Json     // list of {etf, sector, rs_1m, rs_3m, rs_6m, rank_1m, rank_3m, rank_6m, rank_change, score}
  rotationFlags      Json     // list of {etf, sector, direction, rank_change}
  breadth            Json     // {pct_above_200dma, equal_weight_trend_3m}

  // Narrative
  reasoning          String?  // strategist's written reasoning

  createdAt          DateTime @default(now())

  @@index([runDate])
}
```

- [ ] **Step 2: Run the migration**

Run: `python3 -m prisma migrate dev --schema=db/schema.prisma --name add_market_outlook`
Expected: new folder `db/migrations/<timestamp>_add_market_outlook/migration.sql` containing `CREATE TABLE "MarketOutlook"`.

- [ ] **Step 3: Regenerate the client and verify**

Run: `python3 -m prisma generate --schema=db/schema.prisma && python3 -c "from prisma import Prisma; print('marketoutlook' in dir(Prisma()))"`
Expected: `True`

- [ ] **Step 4: Commit**

```bash
git add db/schema.prisma db/migrations
git commit -m "feat(autopilot): add MarketOutlook table"
```

---

### Task 2: Package skeleton + sector relative strength & ranking

**Files:**
- Create: `execution/__init__.py`, `execution/indicators/__init__.py` (both empty)
- Create: `execution/constants.py`
- Create: `execution/indicators/sector_strength.py`
- Test: `tests/test_execution_sector_strength.py`

**Interfaces:**
- Produces:
  - `execution.constants.SECTOR_ETFS: Dict[str, str]` (ticker → sector name, 11 entries), `BENCHMARK = "SPY"`, `EQUAL_WEIGHT = "RSP"`, `VIX = "^VIX"`, `WINDOWS = {"1m": 21, "3m": 63, "6m": 126}`
  - `compute_relative_strength(closes: Dict[str, pd.Series]) -> Dict[str, Dict[str, float]]` — per-ETF excess return vs SPY per window; ETFs with insufficient history are omitted.
  - `rank_sectors(rel_strength: Dict[str, Dict[str, float]]) -> List[Dict[str, Any]]` — sorted best-first by `score`; each dict has keys `etf, sector, rs_1m, rs_3m, rs_6m, rank_1m, rank_3m, rank_6m, rank_change, score`.
  - `detect_rotations(rankings: List[Dict[str, Any]], min_rank_gain: int = 3) -> List[Dict[str, Any]]` — each `{etf, sector, direction: "into"|"out_of", rank_change}`.

- [ ] **Step 1: Write the failing tests**

`tests/test_execution_sector_strength.py`:

```python
"""Tests for execution/indicators/sector_strength.py (pure functions)."""
import numpy as np
import pandas as pd
import pytest

from execution.constants import SECTOR_ETFS, WINDOWS
from execution.indicators.sector_strength import (
    compute_relative_strength,
    detect_rotations,
    rank_sectors,
)


def _series(daily_return: float, days: int = 260, start: float = 100.0) -> pd.Series:
    """Price series compounding at a constant daily return."""
    return pd.Series(start * (1 + daily_return) ** np.arange(days))


def test_constants_shape():
    assert len(SECTOR_ETFS) == 11
    assert "XLK" in SECTOR_ETFS and SECTOR_ETFS["XLK"] == "Technology"
    assert WINDOWS == {"1m": 21, "3m": 63, "6m": 126}


def test_relative_strength_positive_for_outperformer():
    closes = {"SPY": _series(0.0004), "XLE": _series(0.0010), "XLK": _series(0.0001)}
    rs = compute_relative_strength(closes)
    assert rs["XLE"]["1m"] > 0 and rs["XLE"]["3m"] > 0 and rs["XLE"]["6m"] > 0
    assert rs["XLK"]["1m"] < 0


def test_relative_strength_skips_short_history():
    closes = {"SPY": _series(0.0004), "XLE": _series(0.0010, days=30)}
    rs = compute_relative_strength(closes)
    assert "XLE" not in rs  # needs 126+1 days for the 6m window


def test_relative_strength_requires_spy():
    with pytest.raises(KeyError):
        compute_relative_strength({"XLE": _series(0.001)})


def test_rank_sectors_orders_by_score_and_ranks_all_windows():
    closes = {
        "SPY": _series(0.0004),
        "XLE": _series(0.0010),
        "XLK": _series(0.0006),
        "XLU": _series(0.0001),
    }
    rankings = rank_sectors(compute_relative_strength(closes))
    assert [r["etf"] for r in rankings] == ["XLE", "XLK", "XLU"]
    assert rankings[0]["rank_1m"] == 1 and rankings[-1]["rank_1m"] == 3
    assert rankings[0]["sector"] == "Energy"
    # constant-return series ⇒ same rank in every window ⇒ no rank change
    assert all(r["rank_change"] == 0 for r in rankings)


def test_rank_change_detects_improvement():
    """XLE declines for months then surges in the last month ⇒ 1m rank better than 3m rank.

    The decline must be steep enough that XLE's 3m/6m cumulative return still
    trails the laggards despite the recent surge — otherwise one strong month
    dominates every lookback window and no rank divergence appears.
    """
    laggards = {t: _series(0.0006) for t in ["XLK", "XLF", "XLV", "XLI"]}
    daily = np.array([-0.003] * 239 + [0.005] * 21)
    surge = pd.Series(100.0 * np.cumprod(1 + daily))
    closes = {"SPY": _series(0.0004), "XLE": surge, **laggards}
    rankings = rank_sectors(compute_relative_strength(closes))
    xle = next(r for r in rankings if r["etf"] == "XLE")
    assert xle["rank_1m"] < xle["rank_3m"]      # better (lower) rank recently
    assert xle["rank_change"] > 0                # positive = improving


def test_detect_rotations_flags_direction():
    rankings = [
        {"etf": "XLE", "sector": "Energy", "rank_change": 4},
        {"etf": "XLK", "sector": "Technology", "rank_change": -5},
        {"etf": "XLF", "sector": "Financials", "rank_change": 1},
    ]
    flags = detect_rotations(rankings, min_rank_gain=3)
    assert {f["etf"]: f["direction"] for f in flags} == {"XLE": "into", "XLK": "out_of"}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_execution_sector_strength.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'execution'`

- [ ] **Step 3: Implement**

Create empty `execution/__init__.py` and `execution/indicators/__init__.py`.

`execution/constants.py`:

```python
"""Shared constants for the Autopilot execution layer."""

# The 11 SPDR sector ETFs — the top-down lens on where money is rotating.
SECTOR_ETFS = {
    "XLK": "Technology",
    "XLE": "Energy",
    "XLF": "Financials",
    "XLV": "Health Care",
    "XLI": "Industrials",
    "XLY": "Consumer Discretionary",
    "XLP": "Consumer Staples",
    "XLU": "Utilities",
    "XLB": "Materials",
    "XLRE": "Real Estate",
    "XLC": "Communication Services",
}

BENCHMARK = "SPY"
EQUAL_WEIGHT = "RSP"   # equal-weight S&P — RSP/SPY trend is a breadth proxy
VIX = "^VIX"

# Trading-day lookback windows for momentum
WINDOWS = {"1m": 21, "3m": 63, "6m": 126}
```

`execution/indicators/sector_strength.py`:

```python
"""Sector relative strength, ranking, and rotation detection.

Pure functions over close-price series. Rank 1 = strongest sector.
`rank_change = rank_3m - rank_1m`: positive means the sector's rank improved
recently — the early-rotation signal.
"""
from typing import Any, Dict, List

import pandas as pd

from execution.constants import BENCHMARK, SECTOR_ETFS, WINDOWS

# Composite weights favor recent momentum (early rotation) over long trend.
_SCORE_WEIGHTS = {"1m": 0.5, "3m": 0.3, "6m": 0.2}


def _window_return(closes: pd.Series, days: int) -> float:
    return float(closes.iloc[-1] / closes.iloc[-(days + 1)] - 1.0)


def compute_relative_strength(closes: Dict[str, pd.Series]) -> Dict[str, Dict[str, float]]:
    """Excess return vs SPY per window, for every sector ETF with enough history.

    Raises KeyError if SPY is missing. ETFs with < max(WINDOWS)+1 days are omitted.
    """
    spy = closes[BENCHMARK]
    min_len = max(WINDOWS.values()) + 1
    out: Dict[str, Dict[str, float]] = {}
    for etf in SECTOR_ETFS:
        series = closes.get(etf)
        if series is None or len(series) < min_len or len(spy) < min_len:
            continue
        out[etf] = {
            label: _window_return(series, days) - _window_return(spy, days)
            for label, days in WINDOWS.items()
        }
    return out


def rank_sectors(rel_strength: Dict[str, Dict[str, float]]) -> List[Dict[str, Any]]:
    """Rank sectors per window and compute a composite score (best first)."""
    if not rel_strength:
        return []
    ranks: Dict[str, Dict[str, int]] = {etf: {} for etf in rel_strength}
    for label in WINDOWS:
        ordered = sorted(rel_strength, key=lambda e: rel_strength[e][label], reverse=True)
        for i, etf in enumerate(ordered):
            ranks[etf][label] = i + 1

    rankings = []
    for etf, rs in rel_strength.items():
        rankings.append({
            "etf": etf,
            "sector": SECTOR_ETFS[etf],
            "rs_1m": round(rs["1m"], 4),
            "rs_3m": round(rs["3m"], 4),
            "rs_6m": round(rs["6m"], 4),
            "rank_1m": ranks[etf]["1m"],
            "rank_3m": ranks[etf]["3m"],
            "rank_6m": ranks[etf]["6m"],
            "rank_change": ranks[etf]["3m"] - ranks[etf]["1m"],
            "score": round(sum(_SCORE_WEIGHTS[w] * rs[w] for w in WINDOWS), 4),
        })
    rankings.sort(key=lambda r: r["score"], reverse=True)
    return rankings


def detect_rotations(rankings: List[Dict[str, Any]], min_rank_gain: int = 3) -> List[Dict[str, Any]]:
    """Flag sectors whose 1m rank improved/deteriorated ≥ min_rank_gain vs 3m."""
    flags = []
    for r in rankings:
        if r["rank_change"] >= min_rank_gain:
            flags.append({"etf": r["etf"], "sector": r["sector"],
                          "direction": "into", "rank_change": r["rank_change"]})
        elif r["rank_change"] <= -min_rank_gain:
            flags.append({"etf": r["etf"], "sector": r["sector"],
                          "direction": "out_of", "rank_change": r["rank_change"]})
    return flags
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_execution_sector_strength.py -v`
Expected: all PASS

- [ ] **Step 5: Commit**

```bash
git add execution tests/test_execution_sector_strength.py
git commit -m "feat(autopilot): sector relative strength, ranking, rotation detection"
```

---

### Task 3: Regime classifier + one-notch override rule

**Files:**
- Create: `execution/indicators/regime.py`
- Test: `tests/test_execution_regime.py`

**Interfaces:**
- Consumes: nothing from earlier tasks (pure).
- Produces:
  - `REGIME_ORDER = ["risk_off", "neutral", "risk_on"]`
  - `classify_regime(spy_close: pd.Series, vix_close: Optional[pd.Series], pct_above_200dma: Optional[float]) -> Dict[str, Any]` — returns `{"regime": str, "points": int, "inputs": {"spy_above_200dma": bool, "vix_last": float|None, "pct_above_200dma": float|None}}`
  - `apply_strategist_override(mechanical: str, proposed: str) -> Tuple[str, bool]` — returns `(final_regime, was_overridden)`; moves at most one notch toward `proposed`.

- [ ] **Step 1: Write the failing tests**

`tests/test_execution_regime.py`:

```python
"""Tests for execution/indicators/regime.py (pure functions)."""
import numpy as np
import pandas as pd
import pytest

from execution.indicators.regime import (
    REGIME_ORDER,
    apply_strategist_override,
    classify_regime,
)


def _trend(daily: float, days: int = 260) -> pd.Series:
    return pd.Series(100.0 * (1 + daily) ** np.arange(days))


def test_risk_on_uptrend_low_vix_healthy_breadth():
    result = classify_regime(_trend(0.0008), pd.Series([15.0] * 260), pct_above_200dma=75.0)
    assert result["regime"] == "risk_on"
    assert result["points"] >= 2
    assert result["inputs"]["spy_above_200dma"] is True


def test_risk_off_downtrend_high_vix():
    result = classify_regime(_trend(-0.0008), pd.Series([33.0] * 260), pct_above_200dma=25.0)
    assert result["regime"] == "risk_off"


def test_neutral_mixed_signals():
    # Uptrend but elevated VIX and weak breadth → neutral
    result = classify_regime(_trend(0.0008), pd.Series([24.0] * 260), pct_above_200dma=50.0)
    assert result["regime"] == "neutral"


def test_missing_vix_and_breadth_contribute_zero_points():
    result = classify_regime(_trend(0.0008), None, None)
    assert result["points"] == 1  # only the SPY trend point
    assert result["regime"] == "neutral"
    assert result["inputs"]["vix_last"] is None


def test_override_one_notch_allowed():
    assert apply_strategist_override("neutral", "risk_on") == ("risk_on", True)
    assert apply_strategist_override("risk_on", "neutral") == ("neutral", True)


def test_override_two_notches_clamped_to_one():
    # Never risk_off → risk_on directly; clamp to neutral.
    assert apply_strategist_override("risk_off", "risk_on") == ("neutral", True)
    assert apply_strategist_override("risk_on", "risk_off") == ("neutral", True)


def test_override_same_regime_is_not_an_override():
    assert apply_strategist_override("neutral", "neutral") == ("neutral", False)


def test_override_invalid_proposal_is_ignored():
    assert apply_strategist_override("neutral", "bullish") == ("neutral", False)


def test_regime_order_constant():
    assert REGIME_ORDER == ["risk_off", "neutral", "risk_on"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_execution_regime.py -v`
Expected: FAIL with `ModuleNotFoundError` (no `execution.indicators.regime`)

- [ ] **Step 3: Implement**

`execution/indicators/regime.py`:

```python
"""Mechanical market-regime classifier and the strategist override rule.

Point system (deterministic, fully testable):
  SPY above its 200-day MA      +1   below  -1
  VIX < 20                      +1   VIX > 28  -1   (missing: 0)
  breadth >= 60% above 200dma   +1   <= 40%    -1   (missing: 0)

  points >= 2  -> risk_on
  points <= -1 -> risk_off
  otherwise    -> neutral

The LLM strategist may move the final regime AT MOST one notch from the
mechanical call, and never risk_off -> risk_on directly (spec guardrail).
"""
from typing import Any, Dict, Optional, Tuple

import pandas as pd

REGIME_ORDER = ["risk_off", "neutral", "risk_on"]


def classify_regime(
    spy_close: pd.Series,
    vix_close: Optional[pd.Series],
    pct_above_200dma: Optional[float],
) -> Dict[str, Any]:
    sma200 = spy_close.rolling(200, min_periods=60).mean().iloc[-1]
    spy_above = bool(spy_close.iloc[-1] > sma200)
    points = 1 if spy_above else -1

    vix_last: Optional[float] = None
    if vix_close is not None and len(vix_close) > 0:
        vix_last = float(vix_close.iloc[-1])
        if vix_last < 20:
            points += 1
        elif vix_last > 28:
            points -= 1

    if pct_above_200dma is not None:
        if pct_above_200dma >= 60:
            points += 1
        elif pct_above_200dma <= 40:
            points -= 1

    if points >= 2:
        regime = "risk_on"
    elif points <= -1:
        regime = "risk_off"
    else:
        regime = "neutral"

    return {
        "regime": regime,
        "points": points,
        "inputs": {
            "spy_above_200dma": spy_above,
            "vix_last": vix_last,
            "pct_above_200dma": pct_above_200dma,
        },
    }


def apply_strategist_override(mechanical: str, proposed: str) -> Tuple[str, bool]:
    """Move at most one notch from `mechanical` toward `proposed`."""
    if proposed not in REGIME_ORDER or proposed == mechanical:
        return mechanical, False
    m_idx = REGIME_ORDER.index(mechanical)
    p_idx = REGIME_ORDER.index(proposed)
    step = 1 if p_idx > m_idx else -1
    final = REGIME_ORDER[m_idx + step]
    return final, final != mechanical
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_execution_regime.py -v`
Expected: all PASS

- [ ] **Step 5: Commit**

```bash
git add execution/indicators/regime.py tests/test_execution_regime.py
git commit -m "feat(autopilot): mechanical regime classifier with one-notch strategist override"
```

---

### Task 4: Breadth indicators

**Files:**
- Create: `execution/indicators/breadth.py`
- Test: `tests/test_execution_breadth.py`

**Interfaces:**
- Consumes: `SECTOR_ETFS`, `BENCHMARK`, `EQUAL_WEIGHT` from `execution.constants`.
- Produces: `compute_breadth(closes: Dict[str, pd.Series]) -> Dict[str, Optional[float]]` with keys `pct_above_200dma` (percent of available sector ETFs above their 200dma, `None` if none available) and `equal_weight_trend_3m` (63-day % change of the RSP/SPY ratio, `None` if either missing). Universe-level breadth (191 stocks) is deliberately deferred — 11 ETFs + RSP/SPY is a cheap, adequate proxy for Phase 1.

- [ ] **Step 1: Write the failing tests**

`tests/test_execution_breadth.py`:

```python
"""Tests for execution/indicators/breadth.py (pure functions)."""
import numpy as np
import pandas as pd

from execution.indicators.breadth import compute_breadth


def _trend(daily: float, days: int = 260) -> pd.Series:
    return pd.Series(100.0 * (1 + daily) ** np.arange(days))


def test_pct_above_200dma_counts_only_uptrending_etfs():
    closes = {
        "SPY": _trend(0.0004), "RSP": _trend(0.0004),
        "XLK": _trend(0.0008), "XLE": _trend(0.0008),   # above
        "XLF": _trend(-0.0008), "XLU": _trend(-0.0008),  # below
    }
    result = compute_breadth(closes)
    assert result["pct_above_200dma"] == 50.0


def test_equal_weight_trend_positive_when_rsp_outperforms():
    closes = {"SPY": _trend(0.0002), "RSP": _trend(0.0008), "XLK": _trend(0.0004)}
    result = compute_breadth(closes)
    assert result["equal_weight_trend_3m"] > 0


def test_missing_inputs_return_none():
    result = compute_breadth({"XLK": _trend(0.0004)})
    assert result["equal_weight_trend_3m"] is None
    result_empty = compute_breadth({"SPY": _trend(0.0004), "RSP": _trend(0.0004)})
    assert result_empty["pct_above_200dma"] is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_execution_breadth.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Implement**

`execution/indicators/breadth.py`:

```python
"""Breadth proxies from sector ETFs and the RSP/SPY ratio.

Phase 1 uses the 11 sector ETFs (not the 191-stock universe) as the breadth
sample — cheap and adequate for a weekly regime input.
"""
from typing import Dict, Optional

import pandas as pd

from execution.constants import BENCHMARK, EQUAL_WEIGHT, SECTOR_ETFS


def compute_breadth(closes: Dict[str, pd.Series]) -> Dict[str, Optional[float]]:
    above = 0
    total = 0
    for etf in SECTOR_ETFS:
        series = closes.get(etf)
        if series is None or len(series) < 60:
            continue
        sma200 = series.rolling(200, min_periods=60).mean().iloc[-1]
        total += 1
        if series.iloc[-1] > sma200:
            above += 1
    pct_above = round(100.0 * above / total, 1) if total else None

    trend: Optional[float] = None
    spy, rsp = closes.get(BENCHMARK), closes.get(EQUAL_WEIGHT)
    if spy is not None and rsp is not None and len(spy) > 63 and len(rsp) > 63:
        n = min(len(spy), len(rsp))
        ratio = rsp.iloc[-n:].reset_index(drop=True) / spy.iloc[-n:].reset_index(drop=True)
        trend = round(float(ratio.iloc[-1] / ratio.iloc[-64] - 1.0) * 100, 2)

    return {"pct_above_200dma": pct_above, "equal_weight_trend_3m": trend}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_execution_breadth.py -v`
Expected: all PASS

- [ ] **Step 5: Commit**

```bash
git add execution/indicators/breadth.py tests/test_execution_breadth.py
git commit -m "feat(autopilot): breadth indicators (pct above 200dma, RSP/SPY trend)"
```

---

### Task 5: Market data fetch layer

**Files:**
- Create: `execution/market_data.py`
- Test: `tests/test_execution_market_data.py`

**Interfaces:**
- Consumes: `research_swarm.data.market_data_client.MarketDataClient.get_historical_data(ticker: str, period: str = "1y") -> Optional[pd.DataFrame]` (existing; returns OHLCV DataFrame with a `Close` column, already cached/rate-limited).
- Produces:
  - `class OutlookDataError(Exception)`
  - `fetch_market_history(period: str = "1y") -> Dict[str, pd.Series]` — close series keyed by ticker for the 11 sector ETFs + SPY + RSP + ^VIX. Raises `OutlookDataError` if SPY is missing or more than 3 sector ETFs are missing (degrade-to-inaction). Missing RSP/VIX are tolerated (downstream handles `None`).

- [ ] **Step 1: Write the failing tests**

`tests/test_execution_market_data.py`:

```python
"""Tests for execution/market_data.py with MarketDataClient mocked."""
from unittest.mock import patch

import numpy as np
import pandas as pd
import pytest

from execution.constants import SECTOR_ETFS
from execution.market_data import OutlookDataError, fetch_market_history


def _df(days: int = 260) -> pd.DataFrame:
    return pd.DataFrame({"Close": 100.0 * (1.0005) ** np.arange(days)})


def test_fetch_returns_close_series_for_all_tickers():
    with patch("execution.market_data.MarketDataClient") as MockClient:
        MockClient.return_value.get_historical_data.return_value = _df()
        closes = fetch_market_history()
    for ticker in list(SECTOR_ETFS) + ["SPY", "RSP", "^VIX"]:
        assert ticker in closes
        assert isinstance(closes[ticker], pd.Series)


def test_missing_spy_raises():
    def fake(ticker, period="1y"):
        return None if ticker == "SPY" else _df()
    with patch("execution.market_data.MarketDataClient") as MockClient:
        MockClient.return_value.get_historical_data.side_effect = fake
        with pytest.raises(OutlookDataError):
            fetch_market_history()


def test_too_many_missing_etfs_raises():
    missing = {"XLK", "XLE", "XLF", "XLV"}  # 4 > 3 allowed
    def fake(ticker, period="1y"):
        return None if ticker in missing else _df()
    with patch("execution.market_data.MarketDataClient") as MockClient:
        MockClient.return_value.get_historical_data.side_effect = fake
        with pytest.raises(OutlookDataError):
            fetch_market_history()


def test_missing_vix_and_rsp_tolerated():
    def fake(ticker, period="1y"):
        return None if ticker in {"^VIX", "RSP"} else _df()
    with patch("execution.market_data.MarketDataClient") as MockClient:
        MockClient.return_value.get_historical_data.side_effect = fake
        closes = fetch_market_history()
    assert "^VIX" not in closes and "RSP" not in closes
    assert "SPY" in closes
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_execution_market_data.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Implement**

`execution/market_data.py`:

```python
"""Market-data fetch layer for the outlook engine.

Wraps the existing MarketDataClient (yfinance, cached, rate-limited).
Failure posture: if the benchmark or too many sector ETFs are missing,
raise OutlookDataError so the weekly job skips the week instead of
producing an outlook from partial data.
"""
import logging
from typing import Dict

import pandas as pd

from research_swarm.data.market_data_client import MarketDataClient

from execution.constants import BENCHMARK, EQUAL_WEIGHT, SECTOR_ETFS, VIX

logger = logging.getLogger(__name__)

_MAX_MISSING_ETFS = 3


class OutlookDataError(Exception):
    """Market data too incomplete to produce a trustworthy outlook."""


def fetch_market_history(period: str = "1y") -> Dict[str, pd.Series]:
    client = MarketDataClient()
    tickers = list(SECTOR_ETFS) + [BENCHMARK, EQUAL_WEIGHT, VIX]

    closes: Dict[str, pd.Series] = {}
    for ticker in tickers:
        df = client.get_historical_data(ticker, period=period)
        if df is None or "Close" not in df or df["Close"].dropna().empty:
            logger.warning("No history for %s", ticker)
            continue
        closes[ticker] = df["Close"].dropna().reset_index(drop=True)

    if BENCHMARK not in closes:
        raise OutlookDataError("SPY history unavailable — cannot compute outlook")
    missing_etfs = [t for t in SECTOR_ETFS if t not in closes]
    if len(missing_etfs) > _MAX_MISSING_ETFS:
        raise OutlookDataError(
            f"{len(missing_etfs)} sector ETFs missing ({missing_etfs}) — refusing partial outlook"
        )
    return closes
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_execution_market_data.py -v`
Expected: all PASS

- [ ] **Step 5: Commit**

```bash
git add execution/market_data.py tests/test_execution_market_data.py
git commit -m "feat(autopilot): market data fetch layer with degrade-to-inaction guards"
```

---

### Task 6: Strategist prompt builder + response parser

**Files:**
- Create: `execution/strategist/__init__.py` (empty)
- Create: `execution/strategist/prompts.py`
- Create: `execution/strategist/parser.py`
- Test: `tests/test_execution_strategist.py` (prompt + parser tests; Task 7 appends agent tests to this file)

**Interfaces:**
- Consumes: rankings/rotations/breadth/regime shapes from Tasks 2–4.
- Produces:
  - `build_strategist_prompt(payload: Dict[str, Any]) -> str` where payload = `{"rankings": List[Dict], "rotations": List[Dict], "breadth": Dict, "regime_mechanical": str, "regime_inputs": Dict, "macro_headlines": List[str]}`
  - `class StrategistParseError(Exception)`
  - `parse_strategist_response(text: str) -> Dict[str, Any]` returning exactly `{"regime_proposal": str, "conviction": float, "sector_comments": Dict[str, str], "rotation_calls": List[str], "reasoning": str}`

- [ ] **Step 1: Write the failing tests**

`tests/test_execution_strategist.py`:

```python
"""Tests for the macro strategist: prompt builder, parser (Task 6), agent (Task 7)."""
import json

import pytest

from execution.strategist.parser import StrategistParseError, parse_strategist_response
from execution.strategist.prompts import build_strategist_prompt

PAYLOAD = {
    "rankings": [
        {"etf": "XLE", "sector": "Energy", "rs_1m": 0.03, "rs_3m": 0.05, "rs_6m": 0.04,
         "rank_1m": 1, "rank_3m": 2, "rank_6m": 3, "rank_change": 1, "score": 0.04},
        {"etf": "XLK", "sector": "Technology", "rs_1m": -0.02, "rs_3m": 0.01, "rs_6m": 0.03,
         "rank_1m": 8, "rank_3m": 3, "rank_6m": 1, "rank_change": -5, "score": -0.001},
    ],
    "rotations": [{"etf": "XLK", "sector": "Technology", "direction": "out_of", "rank_change": -5}],
    "breadth": {"pct_above_200dma": 54.5, "equal_weight_trend_3m": 1.2},
    "regime_mechanical": "neutral",
    "regime_inputs": {"spy_above_200dma": True, "vix_last": 23.0, "pct_above_200dma": 54.5},
    "macro_headlines": ["Fed holds rates steady"],
}


def test_prompt_contains_indicators_and_rules():
    prompt = build_strategist_prompt(PAYLOAD)
    assert "XLE" in prompt and "Energy" in prompt
    assert "out_of" in prompt or "out of" in prompt
    assert "neutral" in prompt              # mechanical regime stated
    assert "one notch" in prompt.lower()    # override rule stated
    assert "Fed holds rates steady" in prompt
    assert "JSON" in prompt


def test_prompt_handles_no_headlines():
    payload = {**PAYLOAD, "macro_headlines": []}
    prompt = build_strategist_prompt(payload)
    assert "no macro headlines available" in prompt.lower()


VALID_RESPONSE = json.dumps({
    "regime_proposal": "risk_on",
    "conviction": 0.7,
    "sector_comments": {"XLE": "Energy leadership broadening"},
    "rotation_calls": ["Money rotating out of mega-cap tech into energy"],
    "reasoning": "Breadth is stable and rate pressure is easing.",
})


def test_parse_valid_response():
    result = parse_strategist_response(VALID_RESPONSE)
    assert result["regime_proposal"] == "risk_on"
    assert result["conviction"] == 0.7
    assert result["sector_comments"]["XLE"].startswith("Energy")


def test_parse_extracts_json_from_surrounding_prose():
    text = "Here is my outlook:\n```json\n" + VALID_RESPONSE + "\n```\nHope this helps."
    assert parse_strategist_response(text)["regime_proposal"] == "risk_on"


def test_parse_clamps_conviction_and_defaults_optional_fields():
    text = json.dumps({"regime_proposal": "neutral", "conviction": 1.7, "reasoning": "x"})
    result = parse_strategist_response(text)
    assert result["conviction"] == 1.0
    assert result["sector_comments"] == {} and result["rotation_calls"] == []


def test_parse_rejects_bad_regime():
    with pytest.raises(StrategistParseError):
        parse_strategist_response(json.dumps({"regime_proposal": "bullish", "reasoning": "x"}))


def test_parse_rejects_non_json():
    with pytest.raises(StrategistParseError):
        parse_strategist_response("I think markets look good.")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_execution_strategist.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Implement**

Create empty `execution/strategist/__init__.py`.

`execution/strategist/prompts.py`:

```python
"""Prompt construction for the weekly macro strategist."""
from typing import Any, Dict

STRATEGIST_SYSTEM_ROLE = (
    "You are a disciplined macro strategist for a long-horizon systematic fund. "
    "You synthesize sector rotation, breadth, and volatility indicators into a "
    "weekly market outlook. You are conservative: you only disagree with the "
    "mechanical regime when the evidence is clear."
)


def _rankings_table(rankings) -> str:
    lines = ["etf | sector | rs_1m | rs_3m | rs_6m | rank_1m | rank_3m | rank_change | score"]
    for r in rankings:
        lines.append(
            f"{r['etf']} | {r['sector']} | {r['rs_1m']:+.4f} | {r['rs_3m']:+.4f} | "
            f"{r['rs_6m']:+.4f} | {r['rank_1m']} | {r['rank_3m']} | "
            f"{r['rank_change']:+d} | {r['score']:+.4f}"
        )
    return "\n".join(lines)


def build_strategist_prompt(payload: Dict[str, Any]) -> str:
    rotations = payload["rotations"]
    rotation_lines = "\n".join(
        f"- {f['sector']} ({f['etf']}): rotation {f['direction']} "
        f"(rank change {f['rank_change']:+d})"
        for f in rotations
    ) or "- none detected"

    headlines = payload.get("macro_headlines") or []
    headline_lines = "\n".join(f"- {h}" for h in headlines) or "- No macro headlines available."

    breadth = payload["breadth"]
    inputs = payload["regime_inputs"]

    return f"""{STRATEGIST_SYSTEM_ROLE}

## Sector relative strength vs SPY (rank 1 = strongest; positive rank_change = improving recently)
{_rankings_table(payload["rankings"])}

## Rotation flags (1-month rank vs 3-month rank moved >= 3 places)
{rotation_lines}

## Breadth
- Percent of sector ETFs above their 200-day MA: {breadth.get("pct_above_200dma")}
- Equal-weight vs cap-weight 3-month trend (RSP/SPY): {breadth.get("equal_weight_trend_3m")}%

## Mechanical regime call
- Regime: {payload["regime_mechanical"]}
- Inputs: SPY above 200dma = {inputs.get("spy_above_200dma")}, VIX = {inputs.get("vix_last")}, breadth = {inputs.get("pct_above_200dma")}%

## Macro headlines this week
{headline_lines}

## Your task
Write this week's market outlook. Rules:
1. You may propose a regime at most ONE NOTCH away from the mechanical call
   (risk_off <-> neutral <-> risk_on). Proposals further away will be clamped.
2. Focus on where money is rotating INTO early — rank_change is the early signal.
3. Be specific and falsifiable in your reasoning (cite the numbers above).

Respond with ONLY a JSON object, no other text:
{{
  "regime_proposal": "risk_on" | "neutral" | "risk_off",
  "conviction": <float 0.0-1.0>,
  "sector_comments": {{"<ETF>": "<one-sentence view>", ...}},
  "rotation_calls": ["<one sentence per rotation you believe is real>"],
  "reasoning": "<4-8 sentences citing the indicator values>"
}}"""
```

`execution/strategist/parser.py`:

```python
"""Parse and validate the strategist's JSON response."""
import json
from typing import Any, Dict

from execution.indicators.regime import REGIME_ORDER


class StrategistParseError(Exception):
    """Strategist output could not be parsed into a valid outlook."""


def parse_strategist_response(text: str) -> Dict[str, Any]:
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end <= start:
        raise StrategistParseError("no JSON object found in strategist response")
    try:
        raw = json.loads(text[start : end + 1])
    except json.JSONDecodeError as e:
        raise StrategistParseError(f"invalid JSON: {e}") from e

    regime = raw.get("regime_proposal")
    if regime not in REGIME_ORDER:
        raise StrategistParseError(f"invalid regime_proposal: {regime!r}")

    reasoning = raw.get("reasoning")
    if not isinstance(reasoning, str) or not reasoning.strip():
        raise StrategistParseError("missing reasoning")

    try:
        conviction = float(raw.get("conviction", 0.5))
    except (TypeError, ValueError):
        conviction = 0.5
    conviction = max(0.0, min(1.0, conviction))

    comments = raw.get("sector_comments")
    if not isinstance(comments, dict):
        comments = {}
    calls = raw.get("rotation_calls")
    if not isinstance(calls, list):
        calls = []

    return {
        "regime_proposal": regime,
        "conviction": conviction,
        "sector_comments": {str(k): str(v) for k, v in comments.items()},
        "rotation_calls": [str(c) for c in calls],
        "reasoning": reasoning.strip(),
    }
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_execution_strategist.py -v`
Expected: all PASS

- [ ] **Step 5: Commit**

```bash
git add execution/strategist tests/test_execution_strategist.py
git commit -m "feat(autopilot): strategist prompt builder and response parser"
```

---

### Task 7: Strategist agent (LLM call + headlines + fallback)

**Files:**
- Create: `execution/strategist/agent.py`
- Test: append to `tests/test_execution_strategist.py`

**Interfaces:**
- Consumes: `build_strategist_prompt`, `parse_strategist_response`, `StrategistParseError` (Task 6).
- Produces:
  - `fetch_macro_headlines(days_back: int = 7, limit: int = 10) -> List[str]` — NewsAPI `everything` query; returns `[]` on any failure (headlines are optional color, never load-bearing).
  - `run_strategist(payload: Dict[str, Any]) -> Dict[str, Any]` — returns the parsed dict from Task 6 **plus** `"status": "ok"`, or on ANY failure a fallback: `{"status": "fallback", "regime_proposal": payload["regime_mechanical"], "conviction": None, "sector_comments": {}, "rotation_calls": [], "reasoning": "Strategist unavailable (<reason>); mechanical regime used."}`

- [ ] **Step 1: Write the failing tests** (append to `tests/test_execution_strategist.py`)

```python
from unittest.mock import MagicMock, patch

from execution.strategist.agent import fetch_macro_headlines, run_strategist


def _llm_returning(content: str) -> MagicMock:
    llm = MagicMock()
    llm.invoke.return_value = MagicMock(content=content)
    return llm


def test_run_strategist_ok_path():
    with patch("execution.strategist.agent._build_llm", return_value=_llm_returning(VALID_RESPONSE)):
        result = run_strategist(PAYLOAD)
    assert result["status"] == "ok"
    assert result["regime_proposal"] == "risk_on"
    assert result["conviction"] == 0.7


def test_run_strategist_falls_back_on_unparseable_output():
    with patch("execution.strategist.agent._build_llm", return_value=_llm_returning("markets look fine")):
        result = run_strategist(PAYLOAD)
    assert result["status"] == "fallback"
    assert result["regime_proposal"] == PAYLOAD["regime_mechanical"]
    assert result["conviction"] is None


def test_run_strategist_falls_back_on_llm_exception():
    llm = MagicMock()
    llm.invoke.side_effect = RuntimeError("api down")
    with patch("execution.strategist.agent._build_llm", return_value=llm):
        result = run_strategist(PAYLOAD)
    assert result["status"] == "fallback"
    assert "api down" in result["reasoning"]


def test_fetch_macro_headlines_returns_empty_on_error():
    with patch("execution.strategist.agent.requests.get", side_effect=RuntimeError("net down")):
        assert fetch_macro_headlines() == []


def test_fetch_macro_headlines_parses_titles():
    fake = MagicMock()
    fake.json.return_value = {"articles": [{"title": "Fed cuts rates"}, {"title": "Oil rallies"}]}
    fake.raise_for_status.return_value = None
    with patch("execution.strategist.agent.requests.get", return_value=fake), \
         patch("execution.strategist.agent._news_api_key", return_value="k"):
        assert fetch_macro_headlines(limit=2) == ["Fed cuts rates", "Oil rallies"]


def test_fetch_macro_headlines_empty_without_api_key():
    with patch("execution.strategist.agent._news_api_key", return_value=""):
        assert fetch_macro_headlines() == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_execution_strategist.py -v`
Expected: new tests FAIL with `ModuleNotFoundError: No module named 'execution.strategist.agent'`; Task 6 tests still PASS.

- [ ] **Step 3: Implement**

`execution/strategist/agent.py`:

```python
"""Weekly macro strategist: LLM synthesis of the indicator payload.

Failure posture: any error (API, parsing, network) degrades to the mechanical
regime with status="fallback" — the outlook is always produced, never blocked
on the LLM.
"""
import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List

import requests

from execution.strategist.parser import StrategistParseError, parse_strategist_response
from execution.strategist.prompts import build_strategist_prompt

logger = logging.getLogger(__name__)


def _anthropic_api_key() -> str:
    try:
        from research_swarm.config import settings
        return settings.anthropic_api_key or os.getenv("ANTHROPIC_API_KEY", "")
    except ImportError:
        return os.getenv("ANTHROPIC_API_KEY", "")


def _news_api_key() -> str:
    try:
        from research_swarm.config import settings
        return settings.news_api_key or os.getenv("NEWS_API_KEY", "")
    except ImportError:
        return os.getenv("NEWS_API_KEY", "")


def _build_llm():
    """Sonnet 5 per repo conventions (see manager/analyzer.py): thinking must be
    explicitly disabled and max_tokens set in the constructor."""
    from langchain_anthropic import ChatAnthropic
    return ChatAnthropic(
        model="claude-sonnet-5",
        api_key=_anthropic_api_key(),
        max_tokens=4096,
        thinking={"type": "disabled"},
    )


def fetch_macro_headlines(days_back: int = 7, limit: int = 10) -> List[str]:
    """Top market headlines for strategist color. Returns [] on any failure."""
    api_key = _news_api_key()
    if not api_key:
        return []
    try:
        since = (datetime.now(timezone.utc) - timedelta(days=days_back)).strftime("%Y-%m-%d")
        resp = requests.get(
            "https://newsapi.org/v2/everything",
            params={
                "q": '"stock market" OR "federal reserve" OR "sector rotation"',
                "from": since,
                "language": "en",
                "sortBy": "relevancy",
                "pageSize": limit,
                "apiKey": api_key,
            },
            timeout=15,
        )
        resp.raise_for_status()
        articles = resp.json().get("articles", [])
        return [a["title"] for a in articles if a.get("title")][:limit]
    except Exception as e:
        logger.warning("Macro headlines unavailable: %s", e)
        return []


def _fallback(payload: Dict[str, Any], reason: str) -> Dict[str, Any]:
    return {
        "status": "fallback",
        "regime_proposal": payload["regime_mechanical"],
        "conviction": None,
        "sector_comments": {},
        "rotation_calls": [],
        "reasoning": f"Strategist unavailable ({reason}); mechanical regime used.",
    }


def run_strategist(payload: Dict[str, Any]) -> Dict[str, Any]:
    prompt = build_strategist_prompt(payload)
    try:
        response = _build_llm().invoke(prompt)
        parsed = parse_strategist_response(response.content)
        return {"status": "ok", **parsed}
    except StrategistParseError as e:
        logger.error("Strategist output unparseable: %s", e)
        return _fallback(payload, str(e))
    except Exception as e:
        logger.error("Strategist LLM call failed: %s", e)
        return _fallback(payload, str(e))
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_execution_strategist.py -v`
Expected: all PASS

- [ ] **Step 5: Commit**

```bash
git add execution/strategist/agent.py tests/test_execution_strategist.py
git commit -m "feat(autopilot): strategist agent with headline fetch and mechanical fallback"
```

---

### Task 8: Outlook service (build record, store, read latest)

**Files:**
- Create: `execution/outlook_service.py`
- Test: `tests/test_execution_outlook_service.py`

**Interfaces:**
- Consumes: `apply_strategist_override` (Task 3); strategist result shape (Task 7); `db.marketoutlook` accessor (Task 1).
- Produces:
  - `build_outlook_record(run_date: datetime, indicators: Dict[str, Any], strategist: Dict[str, Any]) -> Dict[str, Any]` — pure; applies the one-notch override; returns plain-dict create data with keys `runDate, regime, regimeMechanical, strategistOverride, strategistStatus, conviction, sectorRankings, rotationFlags, breadth, reasoning`. `indicators` shape: `{"rankings": List[Dict], "rotations": List[Dict], "breadth": Dict, "regime_mechanical": str, "regime_inputs": Dict}` (produced by the Task 9 compute step).
  - `async store_outlook(db, record: Dict[str, Any]) -> Any` — wraps JSON fields in `prisma.Json` and calls `db.marketoutlook.create`.
  - `async get_latest_outlook(db) -> Optional[Any]` — most recent row by `runDate`.

- [ ] **Step 1: Write the failing tests**

`tests/test_execution_outlook_service.py`:

```python
"""Tests for execution/outlook_service.py (db mocked)."""
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from execution.outlook_service import build_outlook_record, get_latest_outlook, store_outlook

RUN_DATE = datetime(2026, 7, 12, tzinfo=timezone.utc)

INDICATORS = {
    "rankings": [{"etf": "XLE", "sector": "Energy", "rs_1m": 0.03, "rs_3m": 0.02,
                  "rs_6m": 0.01, "rank_1m": 1, "rank_3m": 2, "rank_6m": 3,
                  "rank_change": 1, "score": 0.024}],
    "rotations": [],
    "breadth": {"pct_above_200dma": 63.6, "equal_weight_trend_3m": 0.8},
    "regime_mechanical": "neutral",
    "regime_inputs": {"spy_above_200dma": True, "vix_last": 21.0, "pct_above_200dma": 63.6},
}

STRATEGIST_OK = {"status": "ok", "regime_proposal": "risk_on", "conviction": 0.65,
                 "sector_comments": {"XLE": "leadership"}, "rotation_calls": [],
                 "reasoning": "Breadth improving."}


def test_build_record_applies_one_notch_override():
    record = build_outlook_record(RUN_DATE, INDICATORS, STRATEGIST_OK)
    assert record["regime"] == "risk_on"           # neutral -> risk_on = one notch, allowed
    assert record["regimeMechanical"] == "neutral"
    assert record["strategistOverride"] is True
    assert record["strategistStatus"] == "ok"
    assert record["conviction"] == 0.65
    assert record["sectorRankings"] == INDICATORS["rankings"]


def test_build_record_clamps_two_notch_proposal():
    indicators = {**INDICATORS, "regime_mechanical": "risk_off"}
    record = build_outlook_record(RUN_DATE, indicators, STRATEGIST_OK)  # proposes risk_on
    assert record["regime"] == "neutral"           # clamped to one notch
    assert record["strategistOverride"] is True


def test_build_record_fallback_keeps_mechanical_regime():
    fallback = {"status": "fallback", "regime_proposal": "neutral", "conviction": None,
                "sector_comments": {}, "rotation_calls": [],
                "reasoning": "Strategist unavailable (x); mechanical regime used."}
    record = build_outlook_record(RUN_DATE, INDICATORS, fallback)
    assert record["regime"] == "neutral"
    assert record["strategistOverride"] is False
    assert record["strategistStatus"] == "fallback"


@pytest.mark.asyncio
async def test_store_outlook_creates_row_with_json_fields():
    db = MagicMock()
    db.marketoutlook.create = AsyncMock(return_value="row")
    record = build_outlook_record(RUN_DATE, INDICATORS, STRATEGIST_OK)
    result = await store_outlook(db, record)
    assert result == "row"
    data = db.marketoutlook.create.call_args.kwargs["data"]
    assert data["regime"] == "risk_on"
    assert data["runDate"] == RUN_DATE


@pytest.mark.asyncio
async def test_get_latest_outlook_orders_by_run_date_desc():
    db = MagicMock()
    db.marketoutlook.find_first = AsyncMock(return_value="latest")
    assert await get_latest_outlook(db) == "latest"
    kwargs = db.marketoutlook.find_first.call_args.kwargs
    assert kwargs["order"] == {"runDate": "desc"}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_execution_outlook_service.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Implement**

`execution/outlook_service.py`:

```python
"""Build, store, and read MarketOutlook records.

build_outlook_record is pure (unit-testable, no prisma). store/get are the
only DB touchpoints and wrap JSON columns in prisma.Json at the edge.
"""
from datetime import datetime
from typing import Any, Dict, Optional

from execution.indicators.regime import apply_strategist_override


def build_outlook_record(
    run_date: datetime,
    indicators: Dict[str, Any],
    strategist: Dict[str, Any],
) -> Dict[str, Any]:
    mechanical = indicators["regime_mechanical"]
    final_regime, overridden = apply_strategist_override(
        mechanical, strategist["regime_proposal"]
    )
    return {
        "runDate": run_date,
        "regime": final_regime,
        "regimeMechanical": mechanical,
        "strategistOverride": overridden,
        "strategistStatus": strategist["status"],
        "conviction": strategist["conviction"],
        "sectorRankings": indicators["rankings"],
        "rotationFlags": indicators["rotations"],
        "breadth": indicators["breadth"],
        "reasoning": strategist["reasoning"],
    }


async def store_outlook(db, record: Dict[str, Any]) -> Any:
    from prisma import Json  # runtime-only dependency

    data = dict(record)
    for field in ("sectorRankings", "rotationFlags", "breadth"):
        data[field] = Json(data[field])
    return await db.marketoutlook.create(data=data)


async def get_latest_outlook(db) -> Optional[Any]:
    return await db.marketoutlook.find_first(order={"runDate": "desc"})
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_execution_outlook_service.py -v`
Expected: all PASS

- [ ] **Step 5: Commit**

```bash
git add execution/outlook_service.py tests/test_execution_outlook_service.py
git commit -m "feat(autopilot): outlook record builder and persistence service"
```

---

### Task 9: Weekly Inngest function + owner email + registration

**Files:**
- Create: `inngest/functions/weekly_outlook.py`
- Modify: `inngest/index.py`
- Test: `tests/test_weekly_outlook_email.py`

**Interfaces:**
- Consumes: `fetch_market_history`/`OutlookDataError` (Task 5), indicator functions (Tasks 2–4), `fetch_macro_headlines`/`run_strategist` (Task 7), `build_outlook_record`/`store_outlook` (Task 8), `get_db` from `api.lib.db`.
- Produces: Inngest function `weekly-market-outlook`, cron `0 20 * * 0` (Sunday 20:00 UTC — 7 hours before the Monday 03:00 weekly batch); pure helper `build_outlook_email_html(record: Dict[str, Any]) -> str`.

- [ ] **Step 1: Write the failing tests**

`tests/test_weekly_outlook_email.py`:

```python
"""Tests for the pure email helper in inngest/functions/weekly_outlook.py."""
from datetime import datetime, timezone

from inngest.functions.weekly_outlook import build_outlook_email_html

RECORD = {
    "runDate": datetime(2026, 7, 12, tzinfo=timezone.utc),
    "regime": "risk_on",
    "regimeMechanical": "neutral",
    "strategistOverride": True,
    "strategistStatus": "ok",
    "conviction": 0.65,
    "sectorRankings": [
        {"etf": "XLE", "sector": "Energy", "rank_1m": 1, "rank_3m": 2,
         "rank_change": 1, "score": 0.024, "rs_1m": 0.03, "rs_3m": 0.02,
         "rs_6m": 0.01, "rank_6m": 3},
    ],
    "rotationFlags": [{"etf": "XLK", "sector": "Technology",
                       "direction": "out_of", "rank_change": -5}],
    "breadth": {"pct_above_200dma": 63.6, "equal_weight_trend_3m": 0.8},
    "reasoning": "Breadth improving and energy leadership broadening.",
}


def test_email_contains_regime_and_top_sector():
    html = build_outlook_email_html(RECORD)
    assert "RISK ON" in html.upper().replace("_", " ")
    assert "Energy" in html and "XLE" in html
    assert "Breadth improving" in html


def test_email_shows_override_and_rotations():
    html = build_outlook_email_html(RECORD)
    assert "neutral" in html.lower()          # mechanical shown alongside final
    assert "Technology" in html               # rotation flag rendered


def test_email_handles_fallback_status():
    record = {**RECORD, "strategistStatus": "fallback", "conviction": None,
              "strategistOverride": False, "regime": "neutral"}
    html = build_outlook_email_html(record)
    assert "fallback" in html.lower()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_weekly_outlook_email.py -v`
Expected: FAIL with `ImportError` (module doesn't exist)

- [ ] **Step 3: Implement the Inngest function**

`inngest/functions/weekly_outlook.py`:

```python
"""
Weekly market outlook — Autopilot Phase 1.

Cron: Sunday 20:00 UTC (before the Monday 03:00 UTC weekly batch), so the
outlook exists before any research/trading downstream ever wants it.

Pipeline: fetch market history -> indicators (sector strength, breadth,
regime) -> LLM strategist (with mechanical fallback) -> store MarketOutlook
-> email the owner.

Failure posture: OutlookDataError or any step failure results in NO outlook
row for the week plus an alert email — never a partial/guessed outlook.
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict

logger = logging.getLogger(__name__)


# ── Pure helpers (unit-tested) ───────────────────────────────────────────────

def build_outlook_email_html(record: Dict[str, Any]) -> str:
    """Render the weekly outlook email from an outlook record dict."""
    regime = record["regime"].replace("_", " ").upper()
    run_date = record["runDate"].strftime("%B %d, %Y")

    override_line = ""
    if record["strategistOverride"]:
        override_line = (
            f"<p style='color:#b8860b'>Strategist override: mechanical call was "
            f"<b>{record['regimeMechanical']}</b>.</p>"
        )
    status_line = ""
    if record["strategistStatus"] != "ok":
        status_line = (
            "<p style='color:#c0392b'>Strategist status: fallback — "
            "mechanical regime used, no narrative this week.</p>"
        )

    conviction = record.get("conviction")
    conviction_str = f"{int(conviction * 100)}%" if conviction is not None else "n/a"

    rows = "".join(
        f"<tr><td>{r['rank_1m']}</td><td>{r['sector']} ({r['etf']})</td>"
        f"<td>{r['rank_change']:+d}</td><td>{r['score']:+.4f}</td></tr>"
        for r in record["sectorRankings"]
    )
    rotations = "".join(
        f"<li>{f['sector']} ({f['etf']}): rotation {f['direction'].replace('_', ' ')} "
        f"({f['rank_change']:+d} ranks)</li>"
        for f in record["rotationFlags"]
    ) or "<li>None detected</li>"

    breadth = record["breadth"]

    return f"""
<!DOCTYPE html>
<html>
<body style="font-family:sans-serif;max-width:640px;margin:0 auto;padding:24px;color:#333">
  <h2 style="color:#00D9B5;margin-top:0">DVRG Market Outlook — {run_date}</h2>
  <h3>Regime: {regime} <span style="color:#999;font-weight:normal">(conviction {conviction_str})</span></h3>
  {override_line}
  {status_line}
  <h4>Sector rankings (1m rank, best first)</h4>
  <table border="1" cellpadding="6" style="border-collapse:collapse;font-size:13px">
    <tr><th>Rank</th><th>Sector</th><th>Rank Δ (3m→1m)</th><th>Score</th></tr>
    {rows}
  </table>
  <h4>Rotation flags</h4>
  <ul>{rotations}</ul>
  <h4>Breadth</h4>
  <p>{breadth.get("pct_above_200dma")}% of sector ETFs above 200dma;
     RSP/SPY 3-month trend {breadth.get("equal_weight_trend_3m")}%.</p>
  <h4>Strategist reasoning</h4>
  <p>{record.get("reasoning") or "n/a"}</p>
  <hr style="border:none;border-top:1px solid #eee;margin:24px 0">
  <p style="font-size:12px;color:#999">Autopilot Phase 1 — outlook only, no trading. Do not reply.</p>
</body>
</html>
"""


# ── Inngest function ─────────────────────────────────────────────────────────
# Guarded registration so pure helpers are unit-testable without the inngest
# runtime (same pattern as send_teaser_digest.py).

def _register_inngest_function():
    from inngest.functions.analyze_stock import inngest  # noqa: PLC0415

    @inngest.create_function(
        fn_id="weekly-market-outlook",
        trigger=inngest.trigger.cron(cron="0 20 * * 0"),  # Sunday 20:00 UTC
        name="Weekly Market Outlook",
        retries=1,
    )
    async def weekly_market_outlook(ctx: Any, step: Any) -> Dict[str, Any]:
        import resend  # noqa: PLC0415

        run_date = datetime.now(timezone.utc)

        # Step 1: indicators (JSON-serializable payload only crosses steps)
        async def compute_indicators() -> Dict[str, Any]:
            from execution.constants import BENCHMARK, VIX  # noqa: PLC0415
            from execution.indicators.breadth import compute_breadth  # noqa: PLC0415
            from execution.indicators.regime import classify_regime  # noqa: PLC0415
            from execution.indicators.sector_strength import (  # noqa: PLC0415
                compute_relative_strength, detect_rotations, rank_sectors,
            )
            from execution.market_data import fetch_market_history  # noqa: PLC0415

            closes = fetch_market_history()  # raises OutlookDataError -> step fails -> alert
            rankings = rank_sectors(compute_relative_strength(closes))
            rotations = detect_rotations(rankings)
            breadth = compute_breadth(closes)
            regime = classify_regime(
                closes[BENCHMARK], closes.get(VIX), breadth["pct_above_200dma"]
            )
            return {
                "rankings": rankings,
                "rotations": rotations,
                "breadth": breadth,
                "regime_mechanical": regime["regime"],
                "regime_inputs": regime["inputs"],
            }

        indicators = await step.run("compute-indicators", compute_indicators)

        # Step 2: strategist (has its own internal fallback — never raises)
        async def strategist_step() -> Dict[str, Any]:
            from execution.strategist.agent import (  # noqa: PLC0415
                fetch_macro_headlines, run_strategist,
            )
            payload = {**indicators, "macro_headlines": fetch_macro_headlines()}
            return run_strategist(payload)

        strategist = await step.run("run-strategist", strategist_step)

        # Step 3: store
        async def store() -> Dict[str, Any]:
            from api.lib.db import get_db  # noqa: PLC0415
            from execution.outlook_service import (  # noqa: PLC0415
                build_outlook_record, store_outlook,
            )
            record = build_outlook_record(run_date, indicators, strategist)
            row = await store_outlook(await get_db(), record)
            logger.info("MarketOutlook stored: %s regime=%s", row.id, record["regime"])
            return {"id": row.id, **{k: v for k, v in record.items() if k != "runDate"},
                    "runDate": run_date.isoformat()}

        stored = await step.run("store-outlook", store)

        # Step 4: email the owner
        async def send_email() -> Dict[str, Any]:
            owner_email = os.getenv("OWNER_EMAIL", "")
            if not owner_email:
                logger.warning("OWNER_EMAIL not set — skipping outlook email")
                return {"status": "skipped"}
            record = dict(stored)
            record["runDate"] = datetime.fromisoformat(record["runDate"])
            resend.api_key = os.getenv("RESEND_API_KEY", "")
            resend.Emails.send({
                "from": "DVRG Autopilot <digest@dvrg.co>",
                "to": [owner_email],
                "subject": f"Market Outlook — {record['regime'].replace('_', ' ')} — "
                           f"{record['runDate'].strftime('%b %d, %Y')}",
                "html": build_outlook_email_html(record),
            })
            return {"status": "sent"}

        email_result = await step.run("send-outlook-email", send_email)
        return {"outlook_id": stored["id"], "regime": stored["regime"],
                "email": email_result["status"]}

    return weekly_market_outlook


try:
    weekly_market_outlook = _register_inngest_function()
except Exception:
    weekly_market_outlook = None  # type: ignore[assignment]
```

- [ ] **Step 4: Register in `inngest/index.py`**

Add the import after line 17 and extend the serve list:

```python
from inngest.functions.weekly_outlook import weekly_market_outlook
```

and change the `serve(...)` list to:

```python
    [analyze_stock, weekly_batch, send_teaser_digest, send_watchlist_alerts, weekly_market_outlook],
```

- [ ] **Step 5: Run the email tests and the full suite**

Run: `python3 -m pytest tests/test_weekly_outlook_email.py -v && python3 -m pytest tests/ -q`
Expected: email tests PASS; full suite has no new failures.

- [ ] **Step 6: Smoke-test the pipeline end-to-end locally (no Inngest, no email)**

Run:
```bash
python3 - <<'EOF'
from execution.constants import BENCHMARK, VIX
from execution.market_data import fetch_market_history
from execution.indicators.sector_strength import compute_relative_strength, rank_sectors, detect_rotations
from execution.indicators.breadth import compute_breadth
from execution.indicators.regime import classify_regime

closes = fetch_market_history()
rankings = rank_sectors(compute_relative_strength(closes))
breadth = compute_breadth(closes)
regime = classify_regime(closes[BENCHMARK], closes.get(VIX), breadth["pct_above_200dma"])
print("regime:", regime["regime"], regime["inputs"])
print("breadth:", breadth)
for r in rankings[:3]:
    print("top:", r["etf"], r["sector"], "rank_change", r["rank_change"], "score", r["score"])
print("rotations:", detect_rotations(rankings))
EOF
```
Expected: prints a real regime, breadth numbers, top-3 sectors, and rotation flags from live yfinance data (no exceptions).

- [ ] **Step 7: Commit**

```bash
git add inngest/functions/weekly_outlook.py inngest/index.py tests/test_weekly_outlook_email.py
git commit -m "feat(autopilot): weekly market outlook Inngest cron with owner email"
```

---

### Task 10: Admin API endpoint for the latest outlook

Added after Task 9 by owner decision: email delivery is dormant (Resend never configured); the outlook surfaces in-app instead, admin-only for now, tier gating to follow later ("flag flip").

**Files:**
- Create: `api/routes/autopilot.py`
- Modify: `api/index.py` (import + `app.include_router(autopilot.router, prefix="/api", tags=["Autopilot"])` beside the existing routers)
- Test: `tests/test_autopilot_routes.py`

**Interfaces:**
- Consumes: `get_latest_outlook(db)` (Task 8), `require_admin` from `api/dependencies.py`, `get_db` from `api/lib/db.py`.
- Produces: `GET /api/autopilot/outlook` (admin-gated). Response model `MarketOutlookResponse` (pydantic): `id: str, run_date: datetime, regime: str, regime_mechanical: str, strategist_override: bool, strategist_status: str, conviction: Optional[float], sector_rankings: List[dict], rotation_flags: List[dict], breadth: dict, reasoning: Optional[str]`. Returns 404 with detail "No outlook available yet" when the table is empty. A pure helper `outlook_row_to_response(row) -> MarketOutlookResponse` does the field mapping (camelCase prisma row → snake_case response) so serialization is unit-testable without FastAPI.
- Follow `api/routes/admin.py` conventions (APIRouter, pydantic response models, `Depends(require_admin)`, `get_db` usage as in that file).
- Tests: unit-test `outlook_row_to_response` with a fake row object; endpoint tests via FastAPI dependency overrides (override `require_admin` and `get_db`) covering 200-with-data and 404-empty. No real DB, no real auth.
- Commit: `feat(autopilot): admin API endpoint for latest market outlook`

### Task 11: Market Outlook tab on the admin page

**Files:**
- Create: `frontend/components/autopilot/MarketOutlookPanel.tsx`
- Modify: `frontend/lib/hooks/useAdmin.ts` (add `useMarketOutlook` query hook + `outlook` query key), `frontend/lib/api/client.ts` (add `getMarketOutlook()` method), `frontend/types/api.ts` (add `MarketOutlookResponse` type matching Task 10's response model), `frontend/app/admin/page.tsx` (add an "Outlook" tab rendering the panel)
- Verify: `npx tsc --noEmit` in `frontend/` passes.

**Interfaces:**
- Consumes: `GET /api/autopilot/outlook` (Task 10).
- Panel renders, using the existing semantic Tailwind tokens and Card/Tabs components already imported by `app/admin/page.tsx`:
  - Regime as a prominent badge (risk_on → success token, neutral → warning, risk_off → error), with mechanical regime + override note when `strategist_override` is true, and a "fallback" warning line when `strategist_status !== "ok"`.
  - Conviction as a percentage ("n/a" when null).
  - Sector rankings table: rank, sector (ETF), 1m/3m ranks, rank change (signed, colored by sign), score.
  - Rotation flags list ("rotation into/out of X") and breadth line (pct above 200dma, RSP/SPY 3m trend).
  - Strategist reasoning as a paragraph; `run_date` as "Week of <date>".
  - Empty state for 404: "No outlook yet — first one generates Sunday night."
- Loading/error handling mirrors the other admin tabs (react-query `isLoading` / `error`).
- Commit: `feat(autopilot): market outlook tab on admin dashboard`

## Verification checklist (after all tasks)

- [ ] `python3 -m pytest tests/ -q` — zero new failures.
- [ ] `grep -rn "research_swarm.agents" execution/` — no matches (isolation constraint holds).
- [ ] Smoke script (Task 9 Step 6) produces a sensible live outlook.
- [ ] After the next Sunday 20:00 UTC run: `MarketOutlook` row exists and the owner email arrived.
