# Phase 3A Signal Expansion Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an industry-ETF overlay (~19 ETFs) and size/style (IWM/MDY) regime inputs to the weekly market outlook, stored as two new nullable JSON columns on `MarketOutlook`, surfaced in the admin outlook panel — with zero behavior change to anything Sleeve B consumes.

**Architecture:** The Sunday `weekly_market_outlook` cron gains two computation passes downstream of the existing sector pass. The ranking math in `execution/indicators/sector_strength.py` is parameterized (ETF map + label key, defaults preserve sector behavior byte-identically). New pure modules `industry_strength.py` and `size_style.py` consume it. Each new pass degrades to `null` + failure alert; the sector outlook never blocks on them.

**Tech Stack:** Python (pure functions + pytest), Prisma (Python client; hand-written SQL migrations), Inngest Python SDK, FastAPI, Next.js/TypeScript frontend.

**Spec:** `docs/superpowers/specs/2026-07-09-phase3a-signal-expansion-design.md`

## Global Constraints

- **Control-group isolation:** `execution/indicators/regime.py`, `breadth.py`, `execution/strategist/`, and every `MarketOutlook` field Sleeve B reads must be untouched. Sector call sites must produce byte-identical output (regression-tested in Task 2).
- **Migrations:** hand-write SQL under `db/migrations/<timestamp>_<name>/migration.sql`; NEVER run `prisma migrate dev` (broken shadow-DB baseline in this repo). Production applies via `prisma migrate deploy` — an operator step, not part of implementation.
- **Python typing:** use `typing.Dict/List/Optional` (no `X | None` unions — parts of this environment run pre-3.10).
- **Inngest functions:** deferred imports inside functions with `# noqa: PLC0415`, JSON-serializable payloads only across steps (established pattern in `inngest_app/functions/weekly_outlook.py`).
- **Tests:** run with `python -m pytest` from repo root. `tests/test_autopilot_routes.py` stubs the `prisma` module before importing `api.*` — keep that pattern.
- **Email paths stay dormant:** do not touch `build_outlook_email_html` or add any email content.
- Rounding: all RS/score floats rounded to 4 decimals, matching the sector layer.

---

### Task 1: Constants — industry ETF list, size/style ETFs, thresholds

**Files:**
- Modify: `execution/constants.py` (after the `WINDOWS` line, before the Sleeve B section)
- Test: `tests/test_execution_sector_strength.py` (extend)

**Interfaces:**
- Produces: `INDUSTRY_ETFS: Dict[str, str]` (19 entries, etf → industry label), `SIZE_STYLE_ETFS: Dict[str, str]` (`{"IWM": "small_cap", "MDY": "mid_cap"}`), `SCORE_WEIGHTS = {"1m": 0.5, "3m": 0.3, "6m": 0.2}`, `INDUSTRY_ROTATION_MIN_RANK_GAIN = 5`, `MIN_INDUSTRIES_REQUIRED = 15`, `SIZE_STYLE_RS_THRESHOLD = 0.01`. All later tasks import these.

- [ ] **Step 1: Write the failing test**

Append to `tests/test_execution_sector_strength.py`:

```python
def test_industry_and_size_style_constants_shape():
    from execution.constants import (
        INDUSTRY_ETFS,
        INDUSTRY_ROTATION_MIN_RANK_GAIN,
        MIN_INDUSTRIES_REQUIRED,
        SCORE_WEIGHTS,
        SIZE_STYLE_ETFS,
        SIZE_STYLE_RS_THRESHOLD,
    )

    assert len(INDUSTRY_ETFS) == 19
    assert INDUSTRY_ETFS["XBI"] == "Biotech"
    assert INDUSTRY_ETFS["SMH"] == "Semiconductors"
    assert not set(INDUSTRY_ETFS) & set(SECTOR_ETFS)  # no overlap with sectors
    assert SIZE_STYLE_ETFS == {"IWM": "small_cap", "MDY": "mid_cap"}
    assert SCORE_WEIGHTS == {"1m": 0.5, "3m": 0.3, "6m": 0.2}
    assert INDUSTRY_ROTATION_MIN_RANK_GAIN == 5
    assert MIN_INDUSTRIES_REQUIRED == 15
    assert SIZE_STYLE_RS_THRESHOLD == 0.01
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_execution_sector_strength.py::test_industry_and_size_style_constants_shape -v`
Expected: FAIL with `ImportError: cannot import name 'INDUSTRY_ETFS'`

- [ ] **Step 3: Write the implementation**

In `execution/constants.py`, insert after the `WINDOWS = {"1m": 21, "3m": 63, "6m": 126}` line:

```python
# Composite score weights favor recent momentum (early rotation) over long trend.
SCORE_WEIGHTS = {"1m": 0.5, "3m": 0.3, "6m": 0.2}

# ── Phase 3A: industry ETF overlay + size/style regime inputs ───────────────
# Signal instruments only — never traded. Consumed by Sleeve A / theme
# discovery only; Sleeve B reads none of this (control-group contract).
INDUSTRY_ETFS = {
    "XBI": "Biotech",
    "SMH": "Semiconductors",
    "IGV": "Software",
    "FDN": "Internet",
    "CIBR": "Cybersecurity",
    "KRE": "Regional Banks",
    "XHB": "Homebuilders",
    "ITB": "Home Construction",
    "XRT": "Retail",
    "XOP": "Oil & Gas E&P",
    "OIH": "Oil Services",
    "XME": "Metals & Mining",
    "URA": "Uranium / Nuclear",
    "SRVR": "Data Center REITs",
    "PAVE": "Infrastructure",
    "ITA": "Aerospace & Defense",
    "UFO": "Space",
    "JETS": "Airlines",
    "IHI": "Medical Devices",
}

SIZE_STYLE_ETFS = {"IWM": "small_cap", "MDY": "mid_cap"}

# Rotation threshold scaled for 19 ranks (sectors use 3 for 11 ranks).
INDUSTRY_ROTATION_MIN_RANK_GAIN = 5
# Industry pass fails (null + alert) below this many rankable industries.
MIN_INDUSTRIES_REQUIRED = 15
# IWM composite RS vs SPY beyond ±this ⇒ small/large caps leading.
SIZE_STYLE_RS_THRESHOLD = 0.01
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_execution_sector_strength.py -v`
Expected: all PASS (existing tests must still pass)

- [ ] **Step 5: Commit**

```bash
git add execution/constants.py tests/test_execution_sector_strength.py
git commit -m "feat(autopilot): Phase 3A constants — industry ETFs, size/style, thresholds"
```

---

### Task 2: Parameterize sector_strength ranking math (byte-identical for sectors)

**Files:**
- Modify: `execution/indicators/sector_strength.py`
- Test: `tests/test_execution_sector_strength.py` (extend)

**Interfaces:**
- Consumes: `SCORE_WEIGHTS` from Task 1.
- Produces (exact signatures later tasks rely on):
  - `compute_relative_strength(closes: Dict[str, pd.Series], etf_map: Optional[Dict[str, str]] = None) -> Dict[str, Dict[str, float]]` — `etf_map=None` means `SECTOR_ETFS`.
  - `rank_sectors(rel_strength, etf_map: Optional[Dict[str, str]] = None, label_key: str = "sector") -> List[Dict[str, Any]]` — element dicts carry `label_key` (e.g. `"industry"`) instead of hardcoded `"sector"`.
  - `detect_rotations(rankings, min_rank_gain: int = 3, label_key: str = "sector") -> List[Dict[str, Any]]` — flag dicts carry `label_key`.
- All existing call sites (`inngest_app/functions/weekly_outlook.py`, `execution/engine/sleeve_b.py` if it calls these, tests) pass no new args and get identical output.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_execution_sector_strength.py`:

```python
def test_parameterized_output_is_identical_to_default_for_sectors():
    """Control-group contract: explicit SECTOR_ETFS args == default args, exactly."""
    closes = {
        "SPY": _series(0.0004),
        "XLE": _series(0.0010),
        "XLK": _series(0.0006),
        "XLU": _series(0.0001),
    }
    rs_default = compute_relative_strength(closes)
    rs_explicit = compute_relative_strength(closes, etf_map=SECTOR_ETFS)
    assert rs_default == rs_explicit

    rankings_default = rank_sectors(rs_default)
    rankings_explicit = rank_sectors(rs_explicit, etf_map=SECTOR_ETFS, label_key="sector")
    assert rankings_default == rankings_explicit

    flags_default = detect_rotations(rankings_default)
    flags_explicit = detect_rotations(rankings_explicit, min_rank_gain=3, label_key="sector")
    assert flags_default == flags_explicit


def test_custom_etf_map_and_label_key():
    etf_map = {"XBI": "Biotech", "SMH": "Semiconductors"}
    closes = {"SPY": _series(0.0004), "XBI": _series(0.0010), "SMH": _series(0.0001)}
    rs = compute_relative_strength(closes, etf_map=etf_map)
    assert set(rs) == {"XBI", "SMH"}
    rankings = rank_sectors(rs, etf_map=etf_map, label_key="industry")
    assert rankings[0]["etf"] == "XBI"
    assert rankings[0]["industry"] == "Biotech"
    assert "sector" not in rankings[0]
    flags = detect_rotations(
        [{"etf": "XBI", "industry": "Biotech", "rank_change": 6}],
        min_rank_gain=5,
        label_key="industry",
    )
    assert flags == [{"etf": "XBI", "industry": "Biotech",
                      "direction": "into", "rank_change": 6}]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_execution_sector_strength.py -v`
Expected: the two new tests FAIL with `TypeError: ... unexpected keyword argument 'etf_map'`

- [ ] **Step 3: Write the implementation**

Replace the body of `execution/indicators/sector_strength.py` below the docstring with (docstring stays; note `_SCORE_WEIGHTS` is replaced by the shared constant):

```python
from typing import Any, Dict, List, Optional

import pandas as pd

from execution.constants import BENCHMARK, SCORE_WEIGHTS, SECTOR_ETFS, WINDOWS


def _window_return(closes: pd.Series, days: int) -> float:
    return float(closes.iloc[-1] / closes.iloc[-(days + 1)] - 1.0)


def compute_relative_strength(
    closes: Dict[str, pd.Series],
    etf_map: Optional[Dict[str, str]] = None,
) -> Dict[str, Dict[str, float]]:
    """Excess return vs SPY per window, for every ETF in etf_map with enough history.

    etf_map defaults to SECTOR_ETFS. Raises KeyError if SPY is missing.
    ETFs with < max(WINDOWS)+1 days are omitted.
    """
    if etf_map is None:
        etf_map = SECTOR_ETFS
    spy = closes[BENCHMARK]
    min_len = max(WINDOWS.values()) + 1
    out: Dict[str, Dict[str, float]] = {}
    for etf in etf_map:
        series = closes.get(etf)
        if series is None or len(series) < min_len or len(spy) < min_len:
            continue
        out[etf] = {
            label: _window_return(series, days) - _window_return(spy, days)
            for label, days in WINDOWS.items()
        }
    return out


def rank_sectors(
    rel_strength: Dict[str, Dict[str, float]],
    etf_map: Optional[Dict[str, str]] = None,
    label_key: str = "sector",
) -> List[Dict[str, Any]]:
    """Rank ETFs per window and compute a composite score (best first).

    etf_map defaults to SECTOR_ETFS; label_key names the human-label field
    ("sector" for the GICS layer, "industry" for the Phase 3A overlay).
    """
    if etf_map is None:
        etf_map = SECTOR_ETFS
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
            label_key: etf_map[etf],
            "rs_1m": round(rs["1m"], 4),
            "rs_3m": round(rs["3m"], 4),
            "rs_6m": round(rs["6m"], 4),
            "rank_1m": ranks[etf]["1m"],
            "rank_3m": ranks[etf]["3m"],
            "rank_6m": ranks[etf]["6m"],
            "rank_change": ranks[etf]["3m"] - ranks[etf]["1m"],
            "score": round(sum(SCORE_WEIGHTS[w] * rs[w] for w in WINDOWS), 4),
        })
    rankings.sort(key=lambda r: r["score"], reverse=True)
    return rankings


def detect_rotations(
    rankings: List[Dict[str, Any]],
    min_rank_gain: int = 3,
    label_key: str = "sector",
) -> List[Dict[str, Any]]:
    """Flag ETFs whose 1m rank improved/deteriorated ≥ min_rank_gain vs 3m."""
    flags = []
    for r in rankings:
        if r["rank_change"] >= min_rank_gain:
            flags.append({"etf": r["etf"], label_key: r[label_key],
                          "direction": "into", "rank_change": r["rank_change"]})
        elif r["rank_change"] <= -min_rank_gain:
            flags.append({"etf": r["etf"], label_key: r[label_key],
                          "direction": "out_of", "rank_change": r["rank_change"]})
    return flags
```

- [ ] **Step 4: Run the full sector-strength + outlook tests to verify parity**

Run: `python -m pytest tests/test_execution_sector_strength.py tests/test_execution_outlook_service.py tests/test_weekly_outlook_email.py -v`
Expected: all PASS

- [ ] **Step 5: Commit**

```bash
git add execution/indicators/sector_strength.py tests/test_execution_sector_strength.py
git commit -m "refactor(autopilot): parameterize RS/rank math over etf_map + label_key (sector output byte-identical)"
```

---

### Task 3: Industry overlay pure module — `rank_industries`

**Files:**
- Create: `execution/indicators/industry_strength.py`
- Test: `tests/test_execution_industry_strength.py` (new)

**Interfaces:**
- Consumes: Task 1 constants; Task 2 parameterized functions.
- Produces: `rank_industries(closes: Dict[str, pd.Series]) -> Dict[str, Any]` returning `{"rankings": List[dict], "rotations": List[dict], "missing": List[str]}` (rankings elements use `"industry"` label key); raises `InsufficientIndustryData` when fewer than `MIN_INDUSTRIES_REQUIRED` industries are rankable, `KeyError` when SPY missing. Task 7 wraps it; Task 6 stores its return value verbatim as `industryRankings`.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_execution_industry_strength.py`:

```python
"""Tests for execution/indicators/industry_strength.py (pure functions)."""
import numpy as np
import pandas as pd
import pytest

from execution.constants import INDUSTRY_ETFS
from execution.indicators.industry_strength import (
    InsufficientIndustryData,
    rank_industries,
)


def _series(daily_return: float, days: int = 260, start: float = 100.0) -> pd.Series:
    return pd.Series(start * (1 + daily_return) ** np.arange(days))


def _closes_for(tickers, spy_return: float = 0.0004):
    """SPY plus a distinct constant-return series per ticker."""
    closes = {"SPY": _series(spy_return)}
    for i, t in enumerate(tickers):
        closes[t] = _series(0.0001 * (i + 1))
    return closes


def test_ranks_all_industries_with_industry_label():
    closes = _closes_for(list(INDUSTRY_ETFS))
    result = rank_industries(closes)
    assert set(result) == {"rankings", "rotations", "missing"}
    assert len(result["rankings"]) == 19
    assert result["missing"] == []
    top = result["rankings"][0]
    assert top["industry"] == INDUSTRY_ETFS[top["etf"]]
    assert "sector" not in top
    # constant-return series ⇒ no rank divergence ⇒ no rotation flags
    assert result["rotations"] == []


def test_missing_tickers_listed_but_still_ranks():
    present = list(INDUSTRY_ETFS)[:16]  # 16 >= MIN_INDUSTRIES_REQUIRED
    closes = _closes_for(present)
    result = rank_industries(closes)
    assert len(result["rankings"]) == 16
    assert result["missing"] == sorted(set(INDUSTRY_ETFS) - set(present))


def test_too_few_industries_raises():
    present = list(INDUSTRY_ETFS)[:14]  # 14 < 15
    closes = _closes_for(present)
    with pytest.raises(InsufficientIndustryData):
        rank_industries(closes)


def test_missing_spy_raises_keyerror():
    closes = {t: _series(0.001) for t in INDUSTRY_ETFS}
    with pytest.raises(KeyError):
        rank_industries(closes)


def test_rotation_uses_industry_threshold():
    """A surge industry must move ≥5 ranks to flag (sectors flag at 3)."""
    laggards = {t: _series(0.0006) for t in list(INDUSTRY_ETFS) if t != "XBI"}
    daily = np.array([-0.003] * 239 + [0.006] * 21)
    surge = pd.Series(100.0 * np.cumprod(1 + daily))
    closes = {"SPY": _series(0.0004), "XBI": surge, **laggards}
    result = rank_industries(closes)
    xbi = next(r for r in result["rankings"] if r["etf"] == "XBI")
    flagged = [f["etf"] for f in result["rotations"]]
    if xbi["rank_change"] >= 5:
        assert "XBI" in flagged
        flag = next(f for f in result["rotations"] if f["etf"] == "XBI")
        assert flag["direction"] == "into"
        assert flag["industry"] == "Biotech"
    else:
        assert "XBI" not in flagged
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_execution_industry_strength.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'execution.indicators.industry_strength'`

- [ ] **Step 3: Write the implementation**

Create `execution/indicators/industry_strength.py`:

```python
"""Industry ETF overlay — Phase 3A.

Same RS/rank/rotation math as the sector layer, over INDUSTRY_ETFS, with
an "industry" label key and a rotation threshold scaled for 19 ranks.
Pure functions; the weekly-outlook cron handles degradation (null + alert).
"""
from typing import Any, Dict

import pandas as pd

from execution.constants import (
    INDUSTRY_ETFS,
    INDUSTRY_ROTATION_MIN_RANK_GAIN,
    MIN_INDUSTRIES_REQUIRED,
)
from execution.indicators.sector_strength import (
    compute_relative_strength,
    detect_rotations,
    rank_sectors,
)


class InsufficientIndustryData(Exception):
    """Too few industry ETFs rankable to trust the overlay this week."""


def rank_industries(closes: Dict[str, pd.Series]) -> Dict[str, Any]:
    """Rank INDUSTRY_ETFS vs SPY.

    Returns {"rankings", "rotations", "missing"}; rankings elements carry
    "industry" instead of "sector". Raises KeyError if SPY is absent and
    InsufficientIndustryData below MIN_INDUSTRIES_REQUIRED rankable ETFs.
    """
    rel = compute_relative_strength(closes, etf_map=INDUSTRY_ETFS)
    rankings = rank_sectors(rel, etf_map=INDUSTRY_ETFS, label_key="industry")
    if len(rankings) < MIN_INDUSTRIES_REQUIRED:
        raise InsufficientIndustryData(
            f"only {len(rankings)}/{len(INDUSTRY_ETFS)} industries rankable "
            f"(minimum {MIN_INDUSTRIES_REQUIRED})"
        )
    rotations = detect_rotations(
        rankings,
        min_rank_gain=INDUSTRY_ROTATION_MIN_RANK_GAIN,
        label_key="industry",
    )
    missing = sorted(set(INDUSTRY_ETFS) - {r["etf"] for r in rankings})
    return {"rankings": rankings, "rotations": rotations, "missing": missing}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_execution_industry_strength.py -v`
Expected: all PASS

- [ ] **Step 5: Commit**

```bash
git add execution/indicators/industry_strength.py tests/test_execution_industry_strength.py
git commit -m "feat(autopilot): industry ETF overlay ranking (Phase 3A)"
```

---

### Task 4: Size/style pure module — `compute_size_style`

**Files:**
- Create: `execution/indicators/size_style.py`
- Test: `tests/test_execution_size_style.py` (new)

**Interfaces:**
- Consumes: Task 1 constants; `_window_return` from `sector_strength` (same package).
- Produces: `compute_size_style(closes: Dict[str, pd.Series]) -> Dict[str, Any]` returning
  `{"iwm": {"label": "small_cap", "rs_1m", "rs_3m", "rs_6m", "composite"}, "mdy": {...}, "tag": "small_caps_leading"|"large_caps_leading"|"mixed"}`.
  Raises `KeyError` (SPY missing) or `ValueError` (IWM/MDY missing or short history). Also produces `tag_for_composite(composite: float) -> str` (boundary-testable tag rule). Task 7 wraps `compute_size_style`; Task 6 stores its return value verbatim as `sizeStyle`.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_execution_size_style.py`:

```python
"""Tests for execution/indicators/size_style.py (pure functions)."""
import numpy as np
import pandas as pd
import pytest

from execution.indicators.size_style import compute_size_style


def _series(daily_return: float, days: int = 260, start: float = 100.0) -> pd.Series:
    return pd.Series(start * (1 + daily_return) ** np.arange(days))


def test_small_caps_leading_when_iwm_outperforms():
    closes = {"SPY": _series(0.0002), "IWM": _series(0.0010), "MDY": _series(0.0005)}
    result = compute_size_style(closes)
    assert result["tag"] == "small_caps_leading"
    assert result["iwm"]["label"] == "small_cap"
    assert result["iwm"]["composite"] > 0.01
    assert result["mdy"]["label"] == "mid_cap"
    assert set(result["iwm"]) == {"label", "rs_1m", "rs_3m", "rs_6m", "composite"}


def test_large_caps_leading_when_iwm_lags():
    closes = {"SPY": _series(0.0010), "IWM": _series(0.0001), "MDY": _series(0.0005)}
    result = compute_size_style(closes)
    assert result["tag"] == "large_caps_leading"
    assert result["iwm"]["composite"] < -0.01


def test_mixed_when_iwm_tracks_spy():
    closes = {"SPY": _series(0.0004), "IWM": _series(0.0004), "MDY": _series(0.0004)}
    result = compute_size_style(closes)
    assert result["tag"] == "mixed"
    assert result["iwm"]["composite"] == 0.0


def test_tag_boundaries_are_strict():
    from execution.indicators.size_style import tag_for_composite

    assert tag_for_composite(0.0101) == "small_caps_leading"
    assert tag_for_composite(0.01) == "mixed"       # exactly at threshold ⇒ mixed
    assert tag_for_composite(-0.01) == "mixed"
    assert tag_for_composite(-0.0101) == "large_caps_leading"


def test_missing_spy_raises_keyerror():
    with pytest.raises(KeyError):
        compute_size_style({"IWM": _series(0.001), "MDY": _series(0.001)})


def test_missing_or_short_leg_raises_valueerror():
    with pytest.raises(ValueError):
        compute_size_style({"SPY": _series(0.0004), "MDY": _series(0.0005)})
    with pytest.raises(ValueError):
        compute_size_style({
            "SPY": _series(0.0004),
            "IWM": _series(0.001, days=30),
            "MDY": _series(0.0005),
        })
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_execution_size_style.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'execution.indicators.size_style'`

- [ ] **Step 3: Write the implementation**

Create `execution/indicators/size_style.py`:

```python
"""Size/style regime inputs — Phase 3A.

IWM (small) and MDY (mid) windowed relative strength vs SPY, plus a simple
leadership tag from IWM's composite. Pure; the weekly-outlook cron handles
degradation (null + alert). Consumed by Sleeve A only — never the shared
regime (control-group contract).
"""
from typing import Any, Dict

import pandas as pd

from execution.constants import (
    BENCHMARK,
    SCORE_WEIGHTS,
    SIZE_STYLE_ETFS,
    SIZE_STYLE_RS_THRESHOLD,
    WINDOWS,
)
from execution.indicators.sector_strength import _window_return


def tag_for_composite(composite: float) -> str:
    """Leadership tag from IWM's composite RS vs SPY (strict thresholds)."""
    if composite > SIZE_STYLE_RS_THRESHOLD:
        return "small_caps_leading"
    if composite < -SIZE_STYLE_RS_THRESHOLD:
        return "large_caps_leading"
    return "mixed"


def compute_size_style(closes: Dict[str, pd.Series]) -> Dict[str, Any]:
    """Windowed RS vs SPY for IWM/MDY + leadership tag.

    Raises KeyError if SPY is missing, ValueError if either leg is missing
    or has fewer than max(WINDOWS)+1 days.
    """
    spy = closes[BENCHMARK]
    min_len = max(WINDOWS.values()) + 1
    if len(spy) < min_len:
        raise ValueError(f"{BENCHMARK} history too short for size/style")

    out: Dict[str, Any] = {}
    for etf, label in SIZE_STYLE_ETFS.items():
        series = closes.get(etf)
        if series is None or len(series) < min_len:
            raise ValueError(f"{etf} history unavailable or too short for size/style")
        rs = {
            w: _window_return(series, days) - _window_return(spy, days)
            for w, days in WINDOWS.items()
        }
        out[etf.lower()] = {
            "label": label,
            "rs_1m": round(rs["1m"], 4),
            "rs_3m": round(rs["3m"], 4),
            "rs_6m": round(rs["6m"], 4),
            "composite": round(sum(SCORE_WEIGHTS[w] * rs[w] for w in WINDOWS), 4),
        }

    out["tag"] = tag_for_composite(out["iwm"]["composite"])
    return out
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_execution_size_style.py -v`
Expected: all PASS

- [ ] **Step 5: Commit**

```bash
git add execution/indicators/size_style.py tests/test_execution_size_style.py
git commit -m "feat(autopilot): size/style regime inputs — IWM/MDY RS + leadership tag (Phase 3A)"
```

---

### Task 5: Generic best-effort fetch — `fetch_history_for`

**Files:**
- Modify: `execution/market_data.py`
- Test: `tests/test_execution_market_data.py` (extend)

**Interfaces:**
- Produces: `fetch_history_for(tickers: Iterable[str], period: str = "1y") -> Dict[str, pd.Series]` — best-effort, non-raising; missing tickers simply absent from the result. `fetch_market_history` refactored to call it internally with behavior unchanged (same validation, same exceptions).

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_execution_market_data.py`:

```python
def test_fetch_history_for_returns_only_available_tickers():
    from execution.market_data import fetch_history_for

    def fake(ticker, period="1y"):
        return None if ticker == "XBI" else _df()

    with patch("execution.market_data.MarketDataClient") as MockClient:
        MockClient.return_value.get_historical_data.side_effect = fake
        closes = fetch_history_for(["XBI", "SMH", "IWM"])

    assert set(closes) == {"SMH", "IWM"}
    assert isinstance(closes["SMH"], pd.Series)


def test_fetch_history_for_never_raises_on_all_missing():
    from execution.market_data import fetch_history_for

    with patch("execution.market_data.MarketDataClient") as MockClient:
        MockClient.return_value.get_historical_data.return_value = None
        assert fetch_history_for(["XBI", "SMH"]) == {}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_execution_market_data.py -v`
Expected: the two new tests FAIL with `ImportError: cannot import name 'fetch_history_for'`

- [ ] **Step 3: Write the implementation**

In `execution/market_data.py`, add `Iterable` to the typing import (`from typing import Dict, Iterable`), then replace `fetch_market_history` with the pair:

```python
def fetch_history_for(tickers: Iterable[str], period: str = "1y") -> Dict[str, pd.Series]:
    """Best-effort close-series fetch. Missing tickers are simply absent.

    Callers own their completeness policy (fetch_market_history raises on
    missing benchmarks; the Phase 3A passes degrade to null + alert).
    """
    client = MarketDataClient()
    closes: Dict[str, pd.Series] = {}
    for ticker in tickers:
        df = client.get_historical_data(ticker, period=period)
        if df is None or "Close" not in df or df["Close"].dropna().empty:
            logger.warning("No history for %s", ticker)
            continue
        closes[ticker] = df["Close"].dropna().reset_index(drop=True)
    return closes


def fetch_market_history(period: str = "1y") -> Dict[str, pd.Series]:
    closes = fetch_history_for(list(SECTOR_ETFS) + [BENCHMARK, EQUAL_WEIGHT, VIX], period)

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

Run: `python -m pytest tests/test_execution_market_data.py -v`
Expected: all PASS (including pre-existing tests — behavior of `fetch_market_history` unchanged)

- [ ] **Step 5: Commit**

```bash
git add execution/market_data.py tests/test_execution_market_data.py
git commit -m "refactor(autopilot): extract best-effort fetch_history_for from fetch_market_history"
```

---

### Task 6: Outlook record + storage — new nullable fields

**Files:**
- Modify: `execution/outlook_service.py`
- Test: `tests/test_execution_outlook_service.py` (extend)

**Interfaces:**
- Consumes: indicators dict may carry `"industry"` (Task 3 return shape or None) and `"size_style"` (Task 4 return shape or None); both keys optional (`.get()`).
- Produces: record keys `industryRankings` and `sizeStyle` (value or None). `store_outlook` Json-wraps any non-None JSON field. Task 7 passes the indicators; Task 9 reads the stored row.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_execution_outlook_service.py`:

```python
INDUSTRY = {
    "rankings": [{"etf": "XBI", "industry": "Biotech", "rs_1m": 0.05, "rs_3m": 0.02,
                  "rs_6m": 0.01, "rank_1m": 1, "rank_3m": 4, "rank_6m": 5,
                  "rank_change": 3, "score": 0.033}],
    "rotations": [],
    "missing": ["UFO"],
}
SIZE_STYLE = {
    "iwm": {"label": "small_cap", "rs_1m": 0.02, "rs_3m": 0.01, "rs_6m": 0.0,
            "composite": 0.013},
    "mdy": {"label": "mid_cap", "rs_1m": 0.01, "rs_3m": 0.0, "rs_6m": 0.0,
            "composite": 0.005},
    "tag": "small_caps_leading",
}


def test_build_record_includes_extended_signals_when_present():
    indicators = {**INDICATORS, "industry": INDUSTRY, "size_style": SIZE_STYLE}
    record = build_outlook_record(RUN_DATE, indicators, STRATEGIST_OK)
    assert record["industryRankings"] == INDUSTRY
    assert record["sizeStyle"] == SIZE_STYLE


def test_build_record_extended_signals_default_to_none():
    record = build_outlook_record(RUN_DATE, INDICATORS, STRATEGIST_OK)
    assert record["industryRankings"] is None
    assert record["sizeStyle"] is None


@pytest.mark.asyncio
async def test_store_outlook_wraps_extended_json_only_when_present():
    db = MagicMock()
    db.marketoutlook.create = AsyncMock(return_value="row")

    indicators = {**INDICATORS, "industry": INDUSTRY, "size_style": SIZE_STYLE}
    await store_outlook(db, build_outlook_record(RUN_DATE, indicators, STRATEGIST_OK))
    data = db.marketoutlook.create.call_args.kwargs["data"]
    # prisma.Json is stubbed by conftest; assert the fields were wrapped (not raw dicts)
    assert data["industryRankings"] is not INDUSTRY
    assert data["sizeStyle"] is not SIZE_STYLE

    db.marketoutlook.create.reset_mock()
    await store_outlook(db, build_outlook_record(RUN_DATE, INDICATORS, STRATEGIST_OK))
    data = db.marketoutlook.create.call_args.kwargs["data"]
    assert data["industryRankings"] is None
    assert data["sizeStyle"] is None
```

Note: if `prisma.Json` in this test environment wraps values transparently (identity), replace the two `is not` assertions with `assert data["industryRankings"] == INDUSTRY` style equality plus a `Json` call-count check via `unittest.mock.patch("prisma.Json")`. Look at how the existing `test_store_outlook_creates_row_with_json_fields` observes `Json` and match that pattern exactly.

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_execution_outlook_service.py -v`
Expected: new tests FAIL with `KeyError: 'industryRankings'`

- [ ] **Step 3: Write the implementation**

In `execution/outlook_service.py`:

In `build_outlook_record`, add to the returned dict (after `"breadth": indicators["breadth"],`):

```python
        "industryRankings": indicators.get("industry"),
        "sizeStyle": indicators.get("size_style"),
```

In `store_outlook`, replace the wrap loop with:

```python
    for field in ("sectorRankings", "rotationFlags", "breadth",
                  "industryRankings", "sizeStyle"):
        if data.get(field) is not None:
            data[field] = Json(data[field])
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_execution_outlook_service.py -v`
Expected: all PASS

- [ ] **Step 5: Commit**

```bash
git add execution/outlook_service.py tests/test_execution_outlook_service.py
git commit -m "feat(autopilot): outlook record carries industryRankings + sizeStyle (nullable)"
```

---

### Task 7: Cron wiring — extended passes with graceful degradation

**Files:**
- Modify: `inngest_app/functions/weekly_outlook.py`
- Test: `tests/test_weekly_outlook_extended.py` (new)

**Interfaces:**
- Consumes: `rank_industries` (Task 3), `compute_size_style` (Task 4), `fetch_history_for` (Task 5), `send_failure_alert(subject: str, body: str)` from `execution/alerts.py`.
- Produces: module-level helper `compute_extended_signals(closes_extra: Dict[str, pd.Series], alert: Callable[[str, str], Any]) -> Dict[str, Any]` returning `{"industry": dict-or-None, "size_style": dict-or-None}`; the `compute-indicators` step payload gains `"industry"` and `"size_style"` keys.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_weekly_outlook_extended.py`:

```python
"""Tests for compute_extended_signals in inngest_app/functions/weekly_outlook.py."""
import numpy as np
import pandas as pd

from execution.constants import INDUSTRY_ETFS
from inngest_app.functions.weekly_outlook import compute_extended_signals


def _series(daily_return: float, days: int = 260, start: float = 100.0) -> pd.Series:
    return pd.Series(start * (1 + daily_return) ** np.arange(days))


def _full_closes():
    closes = {"SPY": _series(0.0004), "IWM": _series(0.0008), "MDY": _series(0.0005)}
    for i, t in enumerate(INDUSTRY_ETFS):
        closes[t] = _series(0.0001 * (i + 1))
    return closes


class AlertSpy:
    def __init__(self):
        self.calls = []

    def __call__(self, subject, body):
        self.calls.append((subject, body))
        return {"status": "skipped"}


def test_both_passes_succeed():
    alert = AlertSpy()
    result = compute_extended_signals(_full_closes(), alert)
    assert result["industry"] is not None
    assert len(result["industry"]["rankings"]) == 19
    assert result["size_style"] is not None
    assert result["size_style"]["tag"] in {
        "small_caps_leading", "large_caps_leading", "mixed",
    }
    assert alert.calls == []


def test_industry_failure_degrades_but_size_style_survives():
    closes = _full_closes()
    for t in list(INDUSTRY_ETFS)[:6]:  # only 13 industries left < 15
        del closes[t]
    alert = AlertSpy()
    result = compute_extended_signals(closes, alert)
    assert result["industry"] is None
    assert result["size_style"] is not None
    assert len(alert.calls) == 1
    assert "industry" in alert.calls[0][0].lower()


def test_size_style_failure_degrades_but_industry_survives():
    closes = _full_closes()
    del closes["IWM"]
    alert = AlertSpy()
    result = compute_extended_signals(closes, alert)
    assert result["industry"] is not None
    assert result["size_style"] is None
    assert len(alert.calls) == 1
    assert "size/style" in alert.calls[0][0].lower()


def test_total_failure_degrades_both_and_never_raises():
    alert = AlertSpy()
    result = compute_extended_signals({}, alert)
    assert result == {"industry": None, "size_style": None}
    assert len(alert.calls) == 2
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_weekly_outlook_extended.py -v`
Expected: FAIL with `ImportError: cannot import name 'compute_extended_signals'`

- [ ] **Step 3: Write the implementation**

In `inngest_app/functions/weekly_outlook.py`:

(a) Add to the "Pure helpers (unit-tested)" section, after `build_outlook_email_html`:

```python
def compute_extended_signals(closes_extra, alert) -> Dict[str, Any]:
    """Phase 3A industry + size/style passes.

    Each pass degrades independently to None + failure alert. Never raises —
    the sector outlook (Sleeve B's critical path) must publish regardless.
    """
    from execution.indicators.industry_strength import rank_industries  # noqa: PLC0415
    from execution.indicators.size_style import compute_size_style  # noqa: PLC0415

    out: Dict[str, Any] = {"industry": None, "size_style": None}
    try:
        out["industry"] = rank_industries(closes_extra)
    except Exception as exc:
        logger.exception("Outlook industry pass failed")
        alert("Outlook industry pass failed", f"{type(exc).__name__}: {exc}")
    try:
        out["size_style"] = compute_size_style(closes_extra)
    except Exception as exc:
        logger.exception("Outlook size/style pass failed")
        alert("Outlook size/style pass failed", f"{type(exc).__name__}: {exc}")
    return out
```

(b) In the `compute_indicators` inner function of `weekly_market_outlook`, extend the deferred imports:

```python
            from execution.alerts import send_failure_alert  # noqa: PLC0415
            from execution.constants import (  # noqa: PLC0415
                BENCHMARK, INDUSTRY_ETFS, SIZE_STYLE_ETFS, VIX,
            )
            from execution.market_data import (  # noqa: PLC0415
                fetch_history_for, fetch_market_history,
            )
```

and, after the existing `regime = classify_regime(...)` call, before the `return`:

```python
            # Phase 3A: extended passes — downstream of the sector pipeline,
            # degrade to None + alert, never block the outlook.
            closes_extra = fetch_history_for(list(INDUSTRY_ETFS) + list(SIZE_STYLE_ETFS))
            if BENCHMARK in closes:
                closes_extra[BENCHMARK] = closes[BENCHMARK]
            extended = compute_extended_signals(closes_extra, send_failure_alert)
```

then extend the returned dict:

```python
            return {
                "rankings": rankings,
                "rotations": rotations,
                "breadth": breadth,
                "regime_mechanical": regime["regime"],
                "regime_inputs": regime["inputs"],
                "industry": extended["industry"],
                "size_style": extended["size_style"],
            }
```

(Keep the existing `from execution.constants import BENCHMARK, VIX` line merged into the new import — don't import twice.)

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_weekly_outlook_extended.py tests/test_weekly_outlook_email.py -v`
Expected: all PASS

- [ ] **Step 5: Commit**

```bash
git add inngest_app/functions/weekly_outlook.py tests/test_weekly_outlook_extended.py
git commit -m "feat(autopilot): weekly outlook computes industry + size/style passes with graceful degradation"
```

---

### Task 8: Prisma schema + migration (additive, nullable)

**Files:**
- Modify: `db/schema.prisma` (MarketOutlook model, after the `breadth` line)
- Create: `db/migrations/20260709000002_add_outlook_industry_size_style/migration.sql`

**Interfaces:**
- Produces: nullable `MarketOutlook.industryRankings` and `MarketOutlook.sizeStyle` JSONB columns. Task 9 reads them off Prisma rows.

- [ ] **Step 1: Update the schema**

In `db/schema.prisma`, inside `model MarketOutlook`, after the `breadth  Json` line add:

```prisma
  // Phase 3A — Sleeve A signal expansion (nullable: passes degrade independently)
  industryRankings   Json?    // {rankings: [{etf, industry, rs_*, rank_*, rank_change, score}], rotations: [...], missing: [...]}
  sizeStyle          Json?    // {iwm: {label, rs_*, composite}, mdy: {...}, tag}
```

- [ ] **Step 2: Write the migration**

Create `db/migrations/20260709000002_add_outlook_industry_size_style/migration.sql`:

```sql
-- Phase 3A: industry ETF overlay + size/style regime inputs.
-- Additive and nullable — historical rows and degraded weeks stay valid.
ALTER TABLE "MarketOutlook" ADD COLUMN "industryRankings" JSONB;
ALTER TABLE "MarketOutlook" ADD COLUMN "sizeStyle" JSONB;
```

- [ ] **Step 3: Validate the schema parses**

Run: `prisma validate --schema db/schema.prisma`
Expected: "The schema at db/schema.prisma is valid" (if the `prisma` CLI is unavailable in this environment, skip — the operator deployment step in Task 11 exercises it; do NOT run `prisma migrate dev`).

- [ ] **Step 4: Commit**

```bash
git add db/schema.prisma db/migrations/20260709000002_add_outlook_industry_size_style/migration.sql
git commit -m "feat(autopilot): MarketOutlook industryRankings + sizeStyle columns (nullable, additive)"
```

---

### Task 9: API — surface extended signals on /autopilot/outlook

**Files:**
- Modify: `api/routes/autopilot.py` (`MarketOutlookResponse`, `outlook_row_to_response`)
- Test: `tests/test_autopilot_routes.py` (extend)

**Interfaces:**
- Consumes: Prisma row attrs `industryRankings` (the Task 3 object or None) and `sizeStyle` (Task 4 object or None).
- Produces (frontend relies on these exact snake_case names): `MarketOutlookResponse.industry_rankings: Optional[List[dict]]`, `industry_rotations: Optional[List[dict]]`, `industry_missing: Optional[List[str]]`, `size_style: Optional[dict]` — the industry object is flattened; all four are `None` when the underlying column is null or absent.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_autopilot_routes.py` (inside `TestOutlookRowToResponse`):

```python
    def test_extended_fields_none_for_legacy_rows(self):
        """Rows created before Phase 3A have no industry/size-style attrs."""
        result = outlook_row_to_response(_make_row())
        assert result.industry_rankings is None
        assert result.industry_rotations is None
        assert result.industry_missing is None
        assert result.size_style is None

    def test_extended_fields_flattened_when_present(self):
        industry = {
            "rankings": [{"etf": "XBI", "industry": "Biotech", "score": 0.033}],
            "rotations": [{"etf": "XBI", "industry": "Biotech",
                           "direction": "into", "rank_change": 6}],
            "missing": ["UFO"],
        }
        size_style = {"iwm": {"label": "small_cap", "composite": 0.013},
                      "mdy": {"label": "mid_cap", "composite": 0.005},
                      "tag": "small_caps_leading"}
        row = _make_row(industryRankings=industry, sizeStyle=size_style)
        result = outlook_row_to_response(row)
        assert result.industry_rankings == industry["rankings"]
        assert result.industry_rotations == industry["rotations"]
        assert result.industry_missing == ["UFO"]
        assert result.size_style == size_style

    def test_extended_fields_none_when_columns_null(self):
        row = _make_row(industryRankings=None, sizeStyle=None)
        result = outlook_row_to_response(row)
        assert result.industry_rankings is None
        assert result.size_style is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_autopilot_routes.py -v`
Expected: new tests FAIL (`AttributeError` / missing field)

- [ ] **Step 3: Write the implementation**

In `api/routes/autopilot.py`, add to `MarketOutlookResponse` after `reasoning`:

```python
    # Phase 3A extended signals — None until the first post-3A outlook runs
    industry_rankings: Optional[List[dict]] = None
    industry_rotations: Optional[List[dict]] = None
    industry_missing: Optional[List[str]] = None
    size_style: Optional[dict] = None
```

In `outlook_row_to_response`, before the `return`, and add the fields to the constructor:

```python
    industry = getattr(row, "industryRankings", None)
    return MarketOutlookResponse(
        id=row.id,
        run_date=row.runDate,
        regime=row.regime,
        regime_mechanical=row.regimeMechanical,
        strategist_override=row.strategistOverride,
        strategist_status=row.strategistStatus,
        conviction=row.conviction,
        sector_rankings=row.sectorRankings,
        rotation_flags=row.rotationFlags,
        breadth=row.breadth,
        reasoning=row.reasoning,
        industry_rankings=industry["rankings"] if industry else None,
        industry_rotations=industry["rotations"] if industry else None,
        industry_missing=industry["missing"] if industry else None,
        size_style=getattr(row, "sizeStyle", None),
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_autopilot_routes.py -v`
Expected: all PASS

- [ ] **Step 5: Commit**

```bash
git add api/routes/autopilot.py tests/test_autopilot_routes.py
git commit -m "feat(autopilot): /autopilot/outlook surfaces industry + size/style signals"
```

---

### Task 10: Frontend — leading industries + size/style in the outlook panel

**Files:**
- Modify: `frontend/types/api.ts` (`MarketOutlookResponse` + new interfaces)
- Modify: `frontend/components/autopilot/MarketOutlookPanel.tsx`

**Interfaces:**
- Consumes: Task 9 response fields (`industry_rankings`, `industry_rotations`, `industry_missing`, `size_style`).
- Produces: a "Leading Industries" card (top 5 by score + rotation flags) and a size/style badge; both render only when data is present, so legacy/degraded outlooks show today's UI unchanged.

- [ ] **Step 1: Extend the types**

In `frontend/types/api.ts`, before `export interface MarketOutlookResponse`:

```ts
export interface IndustryRanking {
  etf: string
  industry: string
  rs_1m: number
  rs_3m: number
  rs_6m: number
  rank_1m: number
  rank_3m: number
  rank_6m: number
  rank_change: number
  score: number
}

export interface IndustryRotationFlag {
  etf: string
  industry: string
  direction: 'into' | 'out_of'
  rank_change: number
}

export interface SizeStyleLeg {
  label: string
  rs_1m: number
  rs_3m: number
  rs_6m: number
  composite: number
}

export interface SizeStyle {
  iwm: SizeStyleLeg
  mdy: SizeStyleLeg
  tag: 'small_caps_leading' | 'large_caps_leading' | 'mixed'
}
```

and add to `MarketOutlookResponse` after `reasoning`:

```ts
  industry_rankings: IndustryRanking[] | null
  industry_rotations: IndustryRotationFlag[] | null
  industry_missing: string[] | null
  size_style: SizeStyle | null
```

- [ ] **Step 2: Extend the panel**

In `frontend/components/autopilot/MarketOutlookPanel.tsx`:

(a) Extend the imports and destructuring:

```ts
import type {
  IndustryRotationFlag,
  MarketOutlookResponse,
  RotationFlag,
  SizeStyle,
} from '@/types/api'
```

In `MarketOutlookContent`, add to the destructuring of `outlook`:

```ts
    industry_rankings,
    industry_rotations,
    size_style,
```

(b) Add helpers next to `rotationLabel`:

```ts
function sizeStyleLabel(tag: SizeStyle['tag']): string {
  return tag
    .split('_')
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(' ')
}

function industryRotationLabel(flag: IndustryRotationFlag): string {
  return flag.direction === 'into'
    ? `Rotation into ${flag.industry} (${flag.etf})`
    : `Rotation out of ${flag.industry} (${flag.etf})`
}
```

(c) In the first card's badge row (the `div` with the regime `Badge` and conviction), add after the conviction block:

```tsx
            {size_style && (
              <Badge variant="secondary">{sizeStyleLabel(size_style.tag)}</Badge>
            )}
```

(d) Between the "Sector Rankings" card and the "Rotation & Breadth" card, insert:

```tsx
      {industry_rankings && industry_rankings.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle>Leading Industries</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            <ul className="space-y-1">
              {industry_rankings.slice(0, 5).map((row, i) => (
                <li key={row.etf} className="text-sm text-text-primary">
                  <span className="font-medium">{i + 1}.</span> {row.industry}{' '}
                  <span className="text-text-tertiary">({row.etf})</span>
                  <span
                    className={`ml-2 text-xs font-medium ${
                      row.rank_change > 0
                        ? 'text-success'
                        : row.rank_change < 0
                          ? 'text-error'
                          : 'text-text-secondary'
                    }`}
                  >
                    {row.rank_change > 0 ? `+${row.rank_change}` : row.rank_change}
                  </span>
                  <span className="ml-2 text-xs text-text-secondary">
                    {row.score.toFixed(4)}
                  </span>
                </li>
              ))}
            </ul>
            {industry_rotations && industry_rotations.length > 0 && (
              <ul className="space-y-1">
                {industry_rotations.map((flag) => (
                  <li
                    key={flag.etf}
                    className={`text-sm ${flag.direction === 'into' ? 'text-success' : 'text-error'}`}
                  >
                    {industryRotationLabel(flag)}
                  </li>
                ))}
              </ul>
            )}
          </CardContent>
        </Card>
      )}
```

- [ ] **Step 3: Typecheck the frontend**

Run: `cd frontend && npx tsc --noEmit`
Expected: no errors (if the project lacks a typecheck setup, run `npm run lint` instead; fix any new errors your change introduced, ignore pre-existing ones)

- [ ] **Step 4: Commit**

```bash
git add frontend/types/api.ts frontend/components/autopilot/MarketOutlookPanel.tsx
git commit -m "feat(autopilot): outlook panel shows leading industries + size/style tag"
```

---

### Task 11: Full verification + deployment checklist

**Files:**
- No new files. Verification + operator handoff.

- [ ] **Step 1: Run the entire test suite**

Run: `python -m pytest tests/ -q`
Expected: all tests pass, zero failures. If anything fails, fix before proceeding (do not skip).

- [ ] **Step 2: Verify the isolation contract with git**

Run: `git diff main --stat -- execution/indicators/regime.py execution/indicators/breadth.py execution/strategist/ execution/engine/`
Expected: empty output (none of the Sleeve-B-facing modules changed). If not empty, something violated the spec — stop and fix.

- [ ] **Step 3: Operator deployment checklist (do NOT execute — hand to the owner/deploy session)**

```text
1. Apply migration to Neon prod:  prisma migrate deploy  (uses db/migrations/20260709000002_...)
   — never `migrate dev`.
2. Push main → Railway "shimmering-liberation"/web auto-deploys
   (no new pip deps; requirements.txt untouched).
3. Re-sync Inngest app (same as Phase 2 go-live) so the updated
   weekly-market-outlook function body is registered.
4. Next Sunday 20:00 UTC run populates the first industryRankings/sizeStyle;
   verify via GET /api/autopilot/outlook (admin) or the admin dashboard panel.
   A failure alert (or null fields) on first run means a ticker/data issue —
   check Railway logs for "Outlook industry pass failed" / "size/style pass failed".
```

- [ ] **Step 4: Final commit (if any stragglers) and report**

```bash
git status --short   # should be clean
```

Report completion with test counts and the deployment checklist surfaced to the owner.
