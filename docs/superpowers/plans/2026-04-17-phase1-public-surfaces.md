# Phase 1 — Public Surfaces Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the leaderboard, track record, preview page, and teaser digest that transform the weekly batch pipeline into a public discovery and conversion engine.

**Architecture:** Event-driven — `weekly_batch` fires a `batch/completed` Inngest event after storing signals; `send-teaser-digest` listens and emails 7 ready-to-copy social posts. Three new FastAPI routes serve `WeeklySignal` data with tier-aware field shaping. Three new Next.js public pages consume those routes.

**Tech Stack:** FastAPI + Pydantic v2, Prisma Python (async), Inngest Python SDK, Resend email, Next.js 14 App Router, TypeScript, Clerk auth (optional on public routes).

---

## File Map

| Action | File | Responsibility |
|--------|------|----------------|
| Create | `api/models/weekly_signals.py` | Pydantic response models (public + full tiers) |
| Create | `api/routes/weekly_signals.py` | 3 FastAPI endpoints: leaderboard, track-record, preview |
| Modify | `api/index.py` | Register new router |
| Modify | `inngest/functions/weekly_batch.py` | Add `batch/completed` event emission as final step |
| Create | `inngest/functions/send_teaser_digest.py` | Inngest function triggered by `batch/completed` |
| Modify | `inngest/index.py` | Register `send_teaser_digest` |
| Create | `tests/test_weekly_signals_route.py` | Unit tests for all 3 routes |
| Create | `tests/test_send_teaser_digest.py` | Unit tests for teaser digest logic |
| Create | `frontend/types/weekly-signals.ts` | TypeScript types for WeeklySignal API responses |
| Modify | `frontend/lib/api/client.ts` | Add `getLeaderboard()`, `getTrackRecord()`, `getWeeklyPreview()` |
| Create | `frontend/app/leaderboard/page.tsx` | Public leaderboard page |
| Create | `frontend/app/track-record/page.tsx` | Public track record page |
| Create | `frontend/app/preview/[ticker]/page.tsx` | Dynamic gated preview page |
| Delete | `frontend/app/preview/nvda/page.tsx` | Replaced by dynamic route |
| Modify | `frontend/components/layout/Header.tsx` | Add Leaderboard to both nav arrays |

---

## Task 1: Pydantic Response Models

**Files:**
- Create: `api/models/weekly_signals.py`

- [ ] **Step 1: Create the models file**

Create `api/models/weekly_signals.py`:

```python
"""Pydantic response models for WeeklySignal API endpoints."""
from __future__ import annotations

from datetime import datetime
from typing import Dict, List, Optional

from pydantic import BaseModel, ConfigDict


class WeeklySignalPublic(BaseModel):
    """Fields returned to all users — no auth required."""

    model_config = ConfigDict(from_attributes=True)

    ticker: str
    verdict: Optional[str] = None
    fair_value_gap_pct: Optional[float] = None
    synthesis_summary: Optional[str] = None
    run_date: datetime
    current_price: Optional[float] = None
    screener_score: Optional[float] = None
    es_change_pct: Optional[float] = None
    nq_change_pct: Optional[float] = None
    dow_change_pct: Optional[float] = None
    prior_verdict: Optional[str] = None  # needed for Verdict Upgrade lens


class WeeklySignalFull(WeeklySignalPublic):
    """All fields — returned only to Starter+ users."""

    fair_value: Optional[float] = None
    ev_probability: Optional[float] = None
    stop_loss_probability: Optional[float] = None
    insider_score: Optional[float] = None
    dark_pool_score: Optional[float] = None
    sentiment_score: Optional[float] = None
    catalyst_summary: Optional[str] = None
    position_size_rec: Optional[str] = None
    prior_ev_probability: Optional[float] = None


class MarketContextOut(BaseModel):
    es_change_pct: Optional[float]
    nq_change_pct: Optional[float]
    dow_change_pct: Optional[float]


class LeaderboardResponse(BaseModel):
    run_date: Optional[datetime]
    market_context: MarketContextOut
    rows: List[WeeklySignalPublic]  # WeeklySignalFull is a subtype — valid here
    total: int


class TrackRecordStats(BaseModel):
    analyzed: int
    buy: int
    hold: int
    avoid: int


class TrackRecordWeek(BaseModel):
    run_date: datetime
    stats: TrackRecordStats
    rows: List[WeeklySignalPublic]


class TrackRecordResponse(BaseModel):
    weeks: List[TrackRecordWeek]
    total_weeks: int
```

- [ ] **Step 2: Verify import works**

```bash
cd /Users/tui/research-swarm
python -c "from api.models.weekly_signals import WeeklySignalPublic, WeeklySignalFull, LeaderboardResponse, TrackRecordResponse; print('OK')"
```

Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add api/models/weekly_signals.py
git commit -m "feat: add Pydantic response models for WeeklySignal API"
```

---

## Task 2: FastAPI Routes — Write Tests First

**Files:**
- Create: `tests/test_weekly_signals_route.py`

These tests exercise the route *functions* directly, bypassing HTTP, by calling helper functions that contain the business logic extracted in Task 3.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_weekly_signals_route.py`:

```python
"""Unit tests for weekly signals route business logic."""
import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

from api.models.weekly_signals import WeeklySignalPublic, WeeklySignalFull


# ── Shared fixtures ──────────────────────────────────────────────────────────

RUN_DATE = datetime(2026, 4, 13, tzinfo=timezone.utc)


def _make_signal(ticker: str, verdict: str = "buy", screener_score: float = 5.0) -> MagicMock:
    """Build a mock Prisma WeeklySignal object."""
    s = MagicMock()
    s.ticker = ticker
    s.verdict = verdict
    s.fairValueGapPct = 15.5
    s.synthesisSummary = f"{ticker} thesis"
    s.runDate = RUN_DATE
    s.currentPrice = 100.0
    s.screenerScore = screener_score
    s.esChangePct = 1.2
    s.nqChangePct = 2.3
    s.dowChangePct = 0.8
    s.priorVerdict = "hold"
    s.fairValue = 115.5
    s.evProbability = 0.72
    s.stopLossProbability = 0.12
    s.insiderScore = 7.0
    s.darkPoolScore = 5.5
    s.sentimentScore = 6.0
    s.catalystSummary = "Strong earnings"
    s.positionSizeRec = "2.5% initial"
    s.priorEvProbability = 0.60
    return s


# ── Import helpers under test (written in Task 3) ────────────────────────────

from api.routes.weekly_signals import (
    _shape_public,
    _shape_full,
    _is_starter_plus,
    _compute_track_record_stats,
)


class TestShapePublic:
    def test_maps_camel_to_snake(self):
        signal = _make_signal("AAPL")
        result = _shape_public(signal)
        assert isinstance(result, WeeklySignalPublic)
        assert result.ticker == "AAPL"
        assert result.fair_value_gap_pct == 15.5
        assert result.synthesis_summary == "AAPL thesis"

    def test_does_not_include_ev_probability(self):
        signal = _make_signal("AAPL")
        result = _shape_public(signal)
        assert not hasattr(result, "ev_probability") or result.__class__ is WeeklySignalPublic


class TestShapeFull:
    def test_includes_ev_probability(self):
        signal = _make_signal("NVDA")
        result = _shape_full(signal)
        assert isinstance(result, WeeklySignalFull)
        assert result.ev_probability == 0.72
        assert result.stop_loss_probability == 0.12
        assert result.insider_score == 7.0

    def test_includes_catalyst_summary(self):
        signal = _make_signal("NVDA")
        result = _shape_full(signal)
        assert result.catalyst_summary == "Strong earnings"


class TestIsStarterPlus:
    def test_none_user_is_not_starter_plus(self):
        assert _is_starter_plus(None) is False

    def test_free_tier_is_not_starter_plus(self):
        user = MagicMock()
        user.tier = "free"
        assert _is_starter_plus(user) is False

    def test_starter_is_starter_plus(self):
        user = MagicMock()
        user.tier = "starter"
        assert _is_starter_plus(user) is True

    def test_investor_is_starter_plus(self):
        user = MagicMock()
        user.tier = "investor"
        assert _is_starter_plus(user) is True

    def test_trader_is_starter_plus(self):
        user = MagicMock()
        user.tier = "trader"
        assert _is_starter_plus(user) is True

    def test_admin_is_starter_plus(self):
        user = MagicMock()
        user.tier = "free"
        user.is_admin = True
        assert _is_starter_plus(user) is True


class TestComputeTrackRecordStats:
    def test_counts_verdicts(self):
        signals = [
            _make_signal("A", verdict="buy"),
            _make_signal("B", verdict="buy"),
            _make_signal("C", verdict="hold"),
            _make_signal("D", verdict="avoid"),
            _make_signal("E", verdict="buy"),
        ]
        stats = _compute_track_record_stats(signals)
        assert stats.analyzed == 5
        assert stats.buy == 3
        assert stats.hold == 1
        assert stats.avoid == 1

    def test_handles_empty(self):
        stats = _compute_track_record_stats([])
        assert stats.analyzed == 0
        assert stats.buy == 0
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
cd /Users/tui/research-swarm
python -m pytest tests/test_weekly_signals_route.py -v 2>&1 | head -20
```

Expected: `ModuleNotFoundError: cannot import name '_shape_public' from 'api.routes.weekly_signals'`

---

## Task 3: FastAPI Routes — Implementation

**Files:**
- Create: `api/routes/weekly_signals.py`

- [ ] **Step 1: Create the route file**

Create `api/routes/weekly_signals.py`:

```python
"""
Public endpoints for WeeklySignal data — leaderboard, track record, and preview.

Auth is optional on all endpoints:
  - Unauthenticated / free tier: limited rows, public fields only
  - Starter+ / admin: full rows, all signal fields
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, List, Optional

from fastapi import APIRouter, HTTPException

from api.dependencies import get_optional_user
from api.lib.db import get_db
from api.models.auth import User
from api.models.weekly_signals import (
    LeaderboardResponse,
    MarketContextOut,
    TrackRecordResponse,
    TrackRecordStats,
    TrackRecordWeek,
    WeeklySignalFull,
    WeeklySignalPublic,
)
from fastapi import Depends

router = APIRouter()
logger = logging.getLogger(__name__)

_STARTER_PLUS_TIERS = {"starter", "investor", "trader"}


# ── Pure helpers (tested directly) ──────────────────────────────────────────

def _is_starter_plus(user: Optional[User]) -> bool:
    """Return True if user has Starter or higher tier, or is admin."""
    if user is None:
        return False
    if getattr(user, "is_admin", False):
        return True
    return getattr(user, "tier", "") in _STARTER_PLUS_TIERS


def _shape_public(signal: Any) -> WeeklySignalPublic:
    """Map a Prisma WeeklySignal object to the public (restricted) response model."""
    return WeeklySignalPublic(
        ticker=signal.ticker,
        verdict=signal.verdict,
        fair_value_gap_pct=signal.fairValueGapPct,
        synthesis_summary=signal.synthesisSummary,
        run_date=signal.runDate,
        current_price=signal.currentPrice,
        screener_score=signal.screenerScore,
        es_change_pct=signal.esChangePct,
        nq_change_pct=signal.nqChangePct,
        dow_change_pct=signal.dowChangePct,
        prior_verdict=signal.priorVerdict,
    )


def _shape_full(signal: Any) -> WeeklySignalFull:
    """Map a Prisma WeeklySignal object to the full (Starter+) response model."""
    return WeeklySignalFull(
        ticker=signal.ticker,
        verdict=signal.verdict,
        fair_value_gap_pct=signal.fairValueGapPct,
        synthesis_summary=signal.synthesisSummary,
        run_date=signal.runDate,
        current_price=signal.currentPrice,
        screener_score=signal.screenerScore,
        es_change_pct=signal.esChangePct,
        nq_change_pct=signal.nqChangePct,
        dow_change_pct=signal.dowChangePct,
        prior_verdict=signal.priorVerdict,
        fair_value=signal.fairValue,
        ev_probability=signal.evProbability,
        stop_loss_probability=signal.stopLossProbability,
        insider_score=signal.insiderScore,
        dark_pool_score=signal.darkPoolScore,
        sentiment_score=signal.sentimentScore,
        catalyst_summary=signal.catalystSummary,
        position_size_rec=signal.positionSizeRec,
        prior_ev_probability=signal.priorEvProbability,
    )


def _compute_track_record_stats(signals: List[Any]) -> TrackRecordStats:
    """Count Buy / Hold / Avoid verdicts in a list of signals."""
    counts = {"buy": 0, "hold": 0, "avoid": 0}
    for s in signals:
        verdict = (s.verdict or "").lower()
        if verdict in counts:
            counts[verdict] += 1
    return TrackRecordStats(
        analyzed=len(signals),
        buy=counts["buy"],
        hold=counts["hold"],
        avoid=counts["avoid"],
    )


# ── Endpoints ────────────────────────────────────────────────────────────────

@router.get("/weekly-signals/leaderboard", response_model=LeaderboardResponse)
async def get_leaderboard(
    limit: int = 25,
    user: Optional[User] = Depends(get_optional_user),
):
    """
    Return this week's ranked picks.

    Unauthenticated / free users: top 3 rows, public fields.
    Starter+ / admin: up to 25 rows, full signal fields.
    """
    db = await get_db()

    # Find the most recent run_date
    latest = await db.weeklysignal.find_first(order={"runDate": "desc"})
    if not latest:
        return LeaderboardResponse(
            run_date=None,
            market_context=MarketContextOut(
                es_change_pct=None, nq_change_pct=None, dow_change_pct=None
            ),
            rows=[],
            total=0,
        )

    run_date = latest.runDate
    is_full = _is_starter_plus(user)
    row_limit = min(limit, 25) if is_full else 3

    signals = await db.weeklysignal.find_many(
        where={"runDate": run_date},
        order={"screenerScore": "desc"},
        take=row_limit,
    )

    rows = [_shape_full(s) if is_full else _shape_public(s) for s in signals]

    return LeaderboardResponse(
        run_date=run_date,
        market_context=MarketContextOut(
            es_change_pct=latest.esChangePct,
            nq_change_pct=latest.nqChangePct,
            dow_change_pct=latest.dowChangePct,
        ),
        rows=rows,
        total=len(rows),
    )


@router.get("/weekly-signals/track-record", response_model=TrackRecordResponse)
async def get_track_record(limit: int = 100):
    """
    Return all historical weekly verdicts grouped by run_date, newest first.
    Fully public — no auth required.
    """
    db = await get_db()

    signals = await db.weeklysignal.find_many(
        order={"runDate": "desc"},
        take=limit,
    )

    # Group by run_date
    weeks_map: dict[datetime, list] = {}
    for s in signals:
        rd = s.runDate
        weeks_map.setdefault(rd, []).append(s)

    weeks = [
        TrackRecordWeek(
            run_date=rd,
            stats=_compute_track_record_stats(sigs),
            rows=[_shape_public(s) for s in sigs],
        )
        for rd, sigs in sorted(weeks_map.items(), reverse=True)
    ]

    return TrackRecordResponse(weeks=weeks, total_weeks=len(weeks))


@router.get("/weekly-signals/preview/{ticker}", response_model=WeeklySignalPublic)
async def get_weekly_preview(
    ticker: str,
    user: Optional[User] = Depends(get_optional_user),
):
    """
    Return the most recent WeeklySignal for a ticker.

    Unauthenticated / free users: public fields only.
    Starter+ / admin: full signal fields.
    """
    db = await get_db()

    signal = await db.weeklysignal.find_first(
        where={"ticker": ticker.upper()},
        order={"runDate": "desc"},
    )

    if not signal:
        raise HTTPException(status_code=404, detail=f"No weekly signal found for {ticker.upper()}")

    if _is_starter_plus(user):
        return _shape_full(signal)
    return _shape_public(signal)
```

- [ ] **Step 2: Run the tests from Task 2 — they should now pass**

```bash
cd /Users/tui/research-swarm
python -m pytest tests/test_weekly_signals_route.py -v
```

Expected: all tests pass.

- [ ] **Step 3: Commit**

```bash
git add api/routes/weekly_signals.py tests/test_weekly_signals_route.py
git commit -m "feat: add WeeklySignal API routes — leaderboard, track-record, preview"
```

---

## Task 4: Register New Router

**Files:**
- Modify: `api/index.py`

- [ ] **Step 1: Add the import**

In `api/index.py`, find the line:
```python
from api.routes import portfolio as portfolio_route
```

Add immediately after it:
```python
from api.routes import weekly_signals as weekly_signals_route
```

- [ ] **Step 2: Register the router**

Find the last `app.include_router` call (currently the webhook router) and add after it:

```python
app.include_router(weekly_signals_route.router, prefix="/api", tags=["Weekly Signals"])
```

- [ ] **Step 3: Verify server starts**

```bash
cd /Users/tui/research-swarm
python -c "from api.index import app; print('OK', len(app.routes), 'routes')"
```

Expected: `OK` with a route count (no import errors).

- [ ] **Step 4: Commit**

```bash
git add api/index.py
git commit -m "feat: register weekly-signals router in FastAPI app"
```

---

## Task 5: Emit `batch/completed` Event from `weekly_batch`

**Files:**
- Modify: `inngest/functions/weekly_batch.py`

- [ ] **Step 1: Add the event emission step**

In `inngest/functions/weekly_batch.py`, replace the final `return` block:

```python
    # Current ending (replace this):
    return {
        "status": "completed",
        "run_date": run_date.isoformat(),
        "candidates": candidates,
        **summary,
    }
```

With:

```python
    # ── Final step: fire batch/completed event for downstream functions ──────
    async def fire_batch_event() -> None:
        await step.send_event("batch-completed-event", {
            "name": "batch/completed",
            "data": {
                "run_date": run_date.isoformat(),
                "ticker_count": summary.get("stored", 0),
            },
        })

    await step.run("fire-batch-completed", fire_batch_event)

    return {
        "status": "completed",
        "run_date": run_date.isoformat(),
        "candidates": candidates,
        **summary,
    }
```

- [ ] **Step 2: Verify no syntax errors**

```bash
cd /Users/tui/research-swarm
python -c "from inngest.functions.weekly_batch import weekly_batch; print('OK')"
```

Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add inngest/functions/weekly_batch.py
git commit -m "feat: emit batch/completed event from weekly_batch for downstream functions"
```

---

## Task 6: Teaser Digest — Write Tests First

**Files:**
- Create: `tests/test_send_teaser_digest.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_send_teaser_digest.py`:

```python
"""Unit tests for teaser digest helper functions."""
import pytest
from datetime import datetime, timezone
from unittest.mock import MagicMock

from inngest.functions.send_teaser_digest import (
    format_teaser_blurb,
    pick_top_signals,
)


RUN_DATE = datetime(2026, 4, 13, tzinfo=timezone.utc)


def _make_signal(
    ticker: str,
    verdict: str = "buy",
    screener_score: float = 5.0,
    fair_value_gap_pct: float = 15.0,
    ev_probability: float = 0.70,
    es_change_pct: float = 1.2,
    nq_change_pct: float = 2.3,
    synthesis_summary: str = "Strong thesis here.",
    catalyst_summary: str = "Earnings beat",
) -> MagicMock:
    s = MagicMock()
    s.ticker = ticker
    s.verdict = verdict
    s.screenerScore = screener_score
    s.fairValueGapPct = fair_value_gap_pct
    s.evProbability = ev_probability
    s.esChangePct = es_change_pct
    s.nqChangePct = nq_change_pct
    s.synthesisSummary = synthesis_summary
    s.catalystSummary = catalyst_summary
    s.runDate = RUN_DATE
    return s


class TestFormatTeaserBlurb:
    def test_includes_ticker_and_verdict(self):
        signal = _make_signal("NVDA")
        blurb = format_teaser_blurb(signal, base_url="https://dvrg.co")
        assert "NVDA" in blurb
        assert "Buy" in blurb

    def test_includes_fair_value_gap(self):
        signal = _make_signal("NVDA", fair_value_gap_pct=18.2)
        blurb = format_teaser_blurb(signal, base_url="https://dvrg.co")
        assert "18.2%" in blurb

    def test_includes_ev_probability_as_percent(self):
        signal = _make_signal("NVDA", ev_probability=0.72)
        blurb = format_teaser_blurb(signal, base_url="https://dvrg.co")
        assert "72%" in blurb

    def test_includes_market_context(self):
        signal = _make_signal("NVDA", es_change_pct=0.1, nq_change_pct=2.3)
        blurb = format_teaser_blurb(signal, base_url="https://dvrg.co")
        assert "ES" in blurb
        assert "NQ" in blurb

    def test_includes_preview_link(self):
        signal = _make_signal("NVDA")
        blurb = format_teaser_blurb(signal, base_url="https://dvrg.co")
        assert "https://dvrg.co/preview/nvda" in blurb

    def test_capitalises_verdict(self):
        signal = _make_signal("AAPL", verdict="hold")
        blurb = format_teaser_blurb(signal, base_url="https://dvrg.co")
        assert "Hold" in blurb

    def test_handles_missing_ev_probability(self):
        signal = _make_signal("AAPL")
        signal.evProbability = None
        blurb = format_teaser_blurb(signal, base_url="https://dvrg.co")
        assert "AAPL" in blurb  # Should not crash


class TestPickTopSignals:
    def test_prefers_buy_verdicts(self):
        signals = [
            _make_signal("HOLD1", verdict="hold", screener_score=10.0),
            _make_signal("BUY1", verdict="buy", screener_score=8.0),
            _make_signal("BUY2", verdict="buy", screener_score=7.0),
        ]
        result = pick_top_signals(signals, n=2)
        tickers = [s.ticker for s in result]
        assert "BUY1" in tickers
        assert "BUY2" in tickers
        assert "HOLD1" not in tickers

    def test_falls_back_to_all_verdicts_when_too_few_buys(self):
        signals = [
            _make_signal("BUY1", verdict="buy", screener_score=10.0),
            _make_signal("HOLD1", verdict="hold", screener_score=9.0),
            _make_signal("HOLD2", verdict="hold", screener_score=8.0),
        ]
        result = pick_top_signals(signals, n=3)
        assert len(result) == 3

    def test_returns_at_most_n(self):
        signals = [_make_signal(f"T{i}", verdict="buy", screener_score=float(i)) for i in range(20)]
        result = pick_top_signals(signals, n=7)
        assert len(result) == 7

    def test_sorts_by_screener_score_desc(self):
        signals = [
            _make_signal("LOW", verdict="buy", screener_score=1.0),
            _make_signal("HIGH", verdict="buy", screener_score=10.0),
        ]
        result = pick_top_signals(signals, n=2)
        assert result[0].ticker == "HIGH"

    def test_handles_empty_list(self):
        result = pick_top_signals([], n=7)
        assert result == []
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
cd /Users/tui/research-swarm
python -m pytest tests/test_send_teaser_digest.py -v 2>&1 | head -20
```

Expected: `ModuleNotFoundError: No module named 'inngest.functions.send_teaser_digest'`

---

## Task 7: Teaser Digest — Implementation

**Files:**
- Create: `inngest/functions/send_teaser_digest.py`

- [ ] **Step 1: Create the function file**

Create `inngest/functions/send_teaser_digest.py`:

```python
"""
Teaser digest — sends 7 ready-to-post social blurbs to the owner after each batch.

Triggered by the "batch/completed" event fired from weekly_batch.
"""
from __future__ import annotations

import logging
import os
from datetime import datetime
from typing import Any, Dict, List, Optional

import resend

from inngest.functions.analyze_stock import inngest
from api.lib.db import get_db

logger = logging.getLogger(__name__)

_BASE_URL = os.getenv("FRONTEND_URL", "https://dvrg.co")
_OWNER_EMAIL = os.getenv("OWNER_EMAIL", "")


# ── Pure helpers (unit-tested) ───────────────────────────────────────────────

def format_teaser_blurb(signal: Any, base_url: str) -> str:
    """Format a single WeeklySignal into a ready-to-copy social media post."""
    ticker = signal.ticker
    verdict = (signal.verdict or "hold").capitalize()
    gap = signal.fairValueGapPct
    ev = signal.evProbability
    es = signal.esChangePct
    nq = signal.nqChangePct
    summary = signal.synthesisSummary or ""

    # Fair value line
    if gap is not None and gap > 0:
        value_line = f"{gap:.1f}% below fair value"
    elif gap is not None:
        value_line = f"{abs(gap):.1f}% above fair value"
    else:
        value_line = "fair value gap unavailable"

    # EV probability line
    ev_line = f"EV probability {int(ev * 100)}%" if ev is not None else ""

    # Market context line
    def _fmt_pct(label: str, val: Optional[float]) -> str:
        if val is None:
            return f"{label} n/a"
        sign = "+" if val >= 0 else ""
        return f"{label} {sign}{val:.1f}%"

    market_line = f"{_fmt_pct('ES', es)}, {_fmt_pct('NQ', nq)} this week."

    # Preview link
    preview_link = f"{base_url}/preview/{ticker.lower()}"

    parts = [f"{ticker} — {verdict}. {value_line}."]
    if summary:
        # Use first sentence of synthesis only to keep posts short
        first_sentence = summary.split(".")[0].strip()
        if first_sentence:
            parts[0] = f"{ticker} — {verdict}. {value_line} as {first_sentence.lower()}."
    if ev_line:
        parts.append(ev_line + ".")
    parts.append(market_line)
    parts.append(f"Full thesis → {preview_link}")

    return " ".join(parts)


def pick_top_signals(signals: List[Any], n: int) -> List[Any]:
    """
    Return the top n signals for the teaser digest.

    Prefers Buy verdicts. Falls back to all verdicts (sorted by screenerScore)
    if fewer than n Buy signals are available.
    """
    if not signals:
        return []

    buys = sorted(
        [s for s in signals if (s.verdict or "").lower() == "buy"],
        key=lambda s: (s.screenerScore or 0),
        reverse=True,
    )

    if len(buys) >= n:
        return buys[:n]

    # Not enough buys — top-up from all signals sorted by score
    all_sorted = sorted(signals, key=lambda s: (s.screenerScore or 0), reverse=True)
    seen = {s.ticker for s in buys}
    extras = [s for s in all_sorted if s.ticker not in seen]
    return (buys + extras)[: n]


def _build_email_html(blurbs: List[str], run_date: str, ticker_count: int) -> str:
    """Build the HTML body for the teaser digest email."""
    blurb_html = "".join(
        f"<div style='margin-bottom:24px;padding:16px;background:#f9f9f9;"
        f"border-left:4px solid #00D9B5;border-radius:4px;'>"
        f"<pre style='white-space:pre-wrap;font-family:monospace;font-size:13px;"
        f"margin:0;'>{blurb}</pre></div>"
        for blurb in blurbs
    )
    return f"""
<!DOCTYPE html>
<html>
<body style="font-family:sans-serif;max-width:640px;margin:0 auto;padding:24px;color:#333">
  <h2 style="color:#00D9B5;margin-top:0">DVRG Weekly Teasers</h2>
  <p style="color:#666">Week of {run_date} &mdash; {ticker_count} stocks analyzed</p>
  <p>Copy and paste each blurb to X, Substack, or LinkedIn:</p>
  {blurb_html}
  <hr style="border:none;border-top:1px solid #eee;margin:24px 0">
  <p style="font-size:12px;color:#999">
    Auto-generated by DVRG weekly batch. Do not reply to this email.
  </p>
</body>
</html>
"""


# ── Inngest function ─────────────────────────────────────────────────────────

@inngest.create_function(
    fn_id="send-teaser-digest",
    trigger=inngest.trigger.event(event="batch/completed"),
    name="Send Weekly Teaser Digest",
    retries=2,
)
async def send_teaser_digest(ctx: Any, step: Any) -> Dict[str, Any]:
    """
    Triggered by the batch/completed event.
    Picks 7 top signals, formats social blurbs, emails them to OWNER_EMAIL.
    """
    data: Dict[str, Any] = ctx.event.data
    run_date_str: str = data["run_date"]
    ticker_count: int = data.get("ticker_count", 0)

    async def fetch_and_email() -> Dict[str, Any]:
        if not _OWNER_EMAIL:
            logger.warning("OWNER_EMAIL not set — skipping teaser digest")
            return {"status": "skipped", "reason": "OWNER_EMAIL not configured"}

        db = await get_db()
        run_date = datetime.fromisoformat(run_date_str)

        signals = await db.weeklysignal.find_many(
            where={"runDate": run_date},
            order={"screenerScore": "desc"},
        )

        if not signals:
            logger.warning("No signals found for run_date=%s", run_date_str)
            return {"status": "skipped", "reason": "no_signals"}

        top = pick_top_signals(signals, n=7)
        blurbs = [format_teaser_blurb(s, base_url=_BASE_URL) for s in top]

        subject = f"DVRG Weekly Teasers — Week of {run_date_str[:10]} · {ticker_count} stocks analyzed"
        html = _build_email_html(blurbs, run_date_str[:10], ticker_count)

        resend.api_key = os.getenv("RESEND_API_KEY", "")
        if not resend.api_key:
            logger.warning("RESEND_API_KEY not set — skipping email send")
            return {"status": "skipped", "reason": "RESEND_API_KEY not configured"}

        resend.Emails.send({
            "from": "DVRG <noreply@dvrg.co>",
            "to": [_OWNER_EMAIL],
            "subject": subject,
            "html": html,
        })

        logger.info("Teaser digest sent: %d blurbs to %s", len(blurbs), _OWNER_EMAIL)
        return {"status": "sent", "blurb_count": len(blurbs)}

    return await step.run("fetch-and-email", fetch_and_email)
```

- [ ] **Step 2: Run the Task 6 tests — they should now pass**

```bash
cd /Users/tui/research-swarm
python -m pytest tests/test_send_teaser_digest.py -v
```

Expected: all tests pass.

- [ ] **Step 3: Commit**

```bash
git add inngest/functions/send_teaser_digest.py tests/test_send_teaser_digest.py
git commit -m "feat: add send-teaser-digest Inngest function with email blurb formatting"
```

---

## Task 8: Register Teaser Digest Function

**Files:**
- Modify: `inngest/index.py`

- [ ] **Step 1: Add the import**

In `inngest/index.py`, find:
```python
from inngest.functions.weekly_batch import weekly_batch
```

Add immediately after:
```python
from inngest.functions.send_teaser_digest import send_teaser_digest
```

- [ ] **Step 2: Register the function**

Find the `serve()` call:
```python
serve(
    app,
    inngest,
    [analyze_stock, weekly_batch],
    signing_key=os.getenv("INNGEST_SIGNING_KEY")
)
```

Update to:
```python
serve(
    app,
    inngest,
    [analyze_stock, weekly_batch, send_teaser_digest],
    signing_key=os.getenv("INNGEST_SIGNING_KEY")
)
```

- [ ] **Step 3: Verify no import errors**

```bash
cd /Users/tui/research-swarm
python -c "from inngest.index import app; print('OK')"
```

Expected: `OK`

- [ ] **Step 4: Commit**

```bash
git add inngest/index.py
git commit -m "feat: register send-teaser-digest Inngest function"
```

---

## Task 9: TypeScript Types + API Client Methods

**Files:**
- Create: `frontend/types/weekly-signals.ts`
- Modify: `frontend/lib/api/client.ts`

- [ ] **Step 1: Create the TypeScript types**

Create `frontend/types/weekly-signals.ts`:

```typescript
// WeeklySignal API response types

export interface WeeklySignalPublic {
  ticker: string
  verdict: 'buy' | 'hold' | 'avoid' | null
  fair_value_gap_pct: number | null
  synthesis_summary: string | null
  run_date: string
  current_price: number | null
  screener_score: number | null
  es_change_pct: number | null
  nq_change_pct: number | null
  dow_change_pct: number | null
  prior_verdict: 'buy' | 'hold' | 'avoid' | null
}

export interface WeeklySignalFull extends WeeklySignalPublic {
  fair_value: number | null
  ev_probability: number | null
  stop_loss_probability: number | null
  insider_score: number | null
  dark_pool_score: number | null
  sentiment_score: number | null
  catalyst_summary: string | null
  position_size_rec: string | null
  prior_ev_probability: number | null
}

export interface MarketContext {
  es_change_pct: number | null
  nq_change_pct: number | null
  dow_change_pct: number | null
}

export interface LeaderboardResponse {
  run_date: string | null
  market_context: MarketContext
  rows: WeeklySignalPublic[]  // may be WeeklySignalFull at runtime for paid users
  total: number
}

export interface TrackRecordStats {
  analyzed: number
  buy: number
  hold: number
  avoid: number
}

export interface TrackRecordWeek {
  run_date: string
  stats: TrackRecordStats
  rows: WeeklySignalPublic[]
}

export interface TrackRecordResponse {
  weeks: TrackRecordWeek[]
  total_weeks: number
}
```

- [ ] **Step 2: Add the three API client methods**

In `frontend/lib/api/client.ts`, find the last `async` method in the `ApiClient` class (around the `getOpportunityDistribution` method) and add after it:

```typescript
  async getLeaderboard(limit = 25): Promise<LeaderboardResponse> {
    return this.request<LeaderboardResponse>(
      `/api/weekly-signals/leaderboard?limit=${limit}`
    )
  }

  async getTrackRecord(limit = 100): Promise<TrackRecordResponse> {
    return this.request<TrackRecordResponse>(
      `/api/weekly-signals/track-record?limit=${limit}`
    )
  }

  async getWeeklyPreview(ticker: string): Promise<WeeklySignalPublic> {
    return this.request<WeeklySignalPublic>(
      `/api/weekly-signals/preview/${encodeURIComponent(ticker.toUpperCase())}`
    )
  }
```

- [ ] **Step 3: Add the import to `client.ts`**

At the top of `frontend/lib/api/client.ts`, add to the existing import block:

```typescript
import type {
  LeaderboardResponse,
  TrackRecordResponse,
  WeeklySignalPublic,
} from '@/types/weekly-signals'
```

- [ ] **Step 4: Verify TypeScript compiles**

```bash
cd /Users/tui/research-swarm/frontend
npx tsc --noEmit 2>&1 | head -20
```

Expected: no errors related to the new types.

- [ ] **Step 5: Commit**

```bash
git add frontend/types/weekly-signals.ts frontend/lib/api/client.ts
git commit -m "feat: add WeeklySignal TypeScript types and API client methods"
```

---

## Task 10: Leaderboard Page

**Files:**
- Create: `frontend/app/leaderboard/page.tsx`

- [ ] **Step 1: Create the page**

Create `frontend/app/leaderboard/page.tsx`:

```tsx
'use client'

import { useEffect, useState } from 'react'
import { useUser } from '@clerk/nextjs'
import Link from 'next/link'
import { ChevronDown } from 'lucide-react'
import { apiClient } from '@/lib/api/client'
import { InlineDisclaimer } from '@/components/ui/InlineDisclaimer'
import type { LeaderboardResponse, WeeklySignalPublic, WeeklySignalFull } from '@/types/weekly-signals'

type Lens = 'fair_value_gap' | 'ev_probability' | 'stop_loss' | 'insider' | 'verdict_upgrade'

const LENSES: { value: Lens; label: string }[] = [
  { value: 'fair_value_gap', label: 'Largest Fair Value Gap' },
  { value: 'ev_probability', label: 'Highest EV Probability' },
  { value: 'stop_loss', label: 'Lowest Stop-Loss Risk' },
  { value: 'insider', label: 'Strongest Insider Activity' },
  { value: 'verdict_upgrade', label: 'Biggest Verdict Upgrade' },
]

const VERDICT_UPGRADE_SCORE: Record<string, Record<string, number>> = {
  avoid: { buy: 3, hold: 1 },
  hold: { buy: 2 },
}

function verdictUpgradeScore(current: string | null, prior: string | null): number {
  if (!current || !prior) return 0
  return VERDICT_UPGRADE_SCORE[prior]?.[current] ?? 0
}

function getLensValue(row: WeeklySignalPublic, lens: Lens): number {
  const full = row as WeeklySignalFull
  switch (lens) {
    case 'fair_value_gap': return row.fair_value_gap_pct ?? -Infinity
    case 'ev_probability': return full.ev_probability ?? -Infinity
    case 'stop_loss': return -(full.stop_loss_probability ?? Infinity)
    case 'insider': return full.insider_score ?? -Infinity
    case 'verdict_upgrade': return verdictUpgradeScore(row.verdict, row.prior_verdict)
  }
}

function formatLensValue(row: WeeklySignalPublic, lens: Lens): string {
  const full = row as WeeklySignalFull
  switch (lens) {
    case 'fair_value_gap':
      return row.fair_value_gap_pct != null ? `+${row.fair_value_gap_pct.toFixed(1)}%` : '—'
    case 'ev_probability':
      return full.ev_probability != null ? `${Math.round(full.ev_probability * 100)}%` : '—'
    case 'stop_loss':
      return full.stop_loss_probability != null ? `${Math.round(full.stop_loss_probability * 100)}%` : '—'
    case 'insider':
      return full.insider_score != null ? full.insider_score.toFixed(1) : '—'
    case 'verdict_upgrade': {
      const score = verdictUpgradeScore(row.verdict, row.prior_verdict)
      if (score === 3) return 'Avoid → Buy'
      if (score === 2) return 'Hold → Buy'
      if (score === 1) return 'Avoid → Hold'
      return '—'
    }
  }
}

const VERDICT_STYLES: Record<string, string> = {
  buy: 'bg-accent/10 text-accent border-accent/20',
  hold: 'bg-warning/10 text-warning border-warning/20',
  avoid: 'bg-error/10 text-error border-error/20',
}

function VerdictBadge({ verdict }: { verdict: string | null }) {
  if (!verdict) return null
  return (
    <span className={`text-xs font-semibold px-2 py-0.5 rounded border uppercase ${VERDICT_STYLES[verdict] ?? ''}`}>
      {verdict}
    </span>
  )
}

function formatMarketCtx(label: string, val: number | null): string {
  if (val == null) return `${label} n/a`
  const sign = val >= 0 ? '+' : ''
  return `${label} ${sign}${val.toFixed(1)}%`
}

function formatRunDate(dateStr: string | null): string {
  if (!dateStr) return ''
  const d = new Date(dateStr)
  return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })
}

export default function LeaderboardPage() {
  const { isSignedIn } = useUser()
  const [data, setData] = useState<LeaderboardResponse | null>(null)
  const [lens, setLens] = useState<Lens>('fair_value_gap')
  const [error, setError] = useState(false)

  useEffect(() => {
    apiClient.getLeaderboard(25)
      .then(setData)
      .catch(() => setError(true))
  }, [])

  if (error) {
    return (
      <div className="container mx-auto px-4 py-16 text-center text-text-secondary">
        Unable to load leaderboard. Try again later.
      </div>
    )
  }

  if (!data) {
    return (
      <div className="container mx-auto px-4 py-16 text-center text-text-secondary">
        Loading...
      </div>
    )
  }

  const { rows, run_date, market_context, total } = data
  const mc = market_context

  const sorted = [...rows].sort((a, b) => getLensValue(b, lens) - getLensValue(a, lens))
  const isFullData = total > 3

  return (
    <div className="container mx-auto px-4 py-10 max-w-3xl">

      {/* Header */}
      <div className="mb-6">
        <h1 className="text-3xl font-bold text-text-primary mb-1">This Week's Top Picks</h1>
        <div className="flex flex-wrap gap-3 items-center text-sm text-text-secondary">
          {run_date && (
            <span className="bg-surface-elevated px-2.5 py-1 rounded text-xs font-medium">
              Week of {formatRunDate(run_date)}
            </span>
          )}
          <span>{formatMarketCtx('ES', mc.es_change_pct)}</span>
          <span>·</span>
          <span>{formatMarketCtx('NQ', mc.nq_change_pct)}</span>
          <span>·</span>
          <span>{formatMarketCtx('DOW', mc.dow_change_pct)}</span>
        </div>
      </div>

      {/* Empty state */}
      {rows.length === 0 && (
        <div className="text-center py-20 text-text-secondary">
          <p className="text-lg font-medium mb-2">No signals yet</p>
          <p className="text-sm">The first weekly batch hasn't run. Check back Monday.</p>
        </div>
      )}

      {rows.length > 0 && (
        <>
          {/* Lens selector — only for full-data users */}
          {isFullData && (
            <div className="mb-4 flex items-center gap-2">
              <span className="text-xs text-text-secondary uppercase tracking-wider">Ranked by</span>
              <div className="relative">
                <select
                  value={lens}
                  onChange={e => setLens(e.target.value as Lens)}
                  className="appearance-none bg-surface-elevated border border-border rounded px-3 py-1.5 pr-7
                             text-sm text-text-primary focus:outline-none focus:ring-1 focus:ring-accent"
                >
                  {LENSES.map(l => (
                    <option key={l.value} value={l.value}>{l.label}</option>
                  ))}
                </select>
                <ChevronDown size={14} className="absolute right-2 top-1/2 -translate-y-1/2 text-text-secondary pointer-events-none" />
              </div>
            </div>
          )}

          {/* Ranked rows */}
          <div className="flex flex-col gap-2">
            {sorted.map((row, idx) => (
              <Link
                key={row.ticker}
                href={`/preview/${row.ticker.toLowerCase()}`}
                className="flex items-center gap-3 bg-surface-1 hover:bg-surface-elevated border border-border
                           rounded-lg px-4 py-3 transition-colors duration-150 group"
              >
                <span className="text-xs text-text-subtle w-5 shrink-0">{idx + 1}</span>
                <span className="text-sm font-bold text-text-primary w-12 shrink-0">{row.ticker}</span>
                <VerdictBadge verdict={row.verdict} />
                <span className="flex-1 text-xs text-text-secondary line-clamp-1 hidden sm:block">
                  {row.synthesis_summary ?? ''}
                </span>
                <span className="text-sm font-semibold text-accent shrink-0 ml-auto">
                  {formatLensValue(row, lens)}
                </span>
              </Link>
            ))}

            {/* Upgrade nudge between row 3 and 4 for unauthenticated/free */}
            {!isFullData && (
              <div className="flex items-center justify-center gap-2 bg-accent/5 border border-accent/20
                              rounded-lg px-4 py-3 text-sm">
                <span className="text-text-secondary">
                  {isSignedIn ? 'Upgrade to Starter to see all 25 picks' : 'Sign in to see all 25 picks'}
                </span>
                <Link
                  href={isSignedIn ? '/#pricing' : '/sign-in'}
                  className="text-accent font-semibold hover:underline"
                >
                  {isSignedIn ? 'Upgrade →' : 'Sign in →'}
                </Link>
              </div>
            )}
          </div>
        </>
      )}

      <div className="mt-10">
        <InlineDisclaimer />
      </div>
    </div>
  )
}
```

- [ ] **Step 2: Verify the page compiles**

```bash
cd /Users/tui/research-swarm/frontend
npx tsc --noEmit 2>&1 | grep leaderboard
```

Expected: no errors.

- [ ] **Step 3: Commit**

```bash
git add frontend/app/leaderboard/page.tsx
git commit -m "feat: add public leaderboard page with lens sorting and tier-aware blur"
```

---

## Task 11: Track Record Page

**Files:**
- Create: `frontend/app/track-record/page.tsx`

- [ ] **Step 1: Create the page**

Create `frontend/app/track-record/page.tsx`:

```tsx
'use client'

import { useEffect, useState } from 'react'
import { ChevronDown } from 'lucide-react'
import Link from 'next/link'
import { apiClient } from '@/lib/api/client'
import { InlineDisclaimer } from '@/components/ui/InlineDisclaimer'
import type { TrackRecordResponse, TrackRecordWeek } from '@/types/weekly-signals'

function formatRunDate(dateStr: string): string {
  const d = new Date(dateStr)
  return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })
}

function formatPrice(price: number | null): string {
  if (price == null) return '—'
  return `$${price.toFixed(2)}`
}

const VERDICT_STYLES: Record<string, string> = {
  buy: 'bg-accent/10 text-accent border-accent/20',
  hold: 'bg-warning/10 text-warning border-warning/20',
  avoid: 'bg-error/10 text-error border-error/20',
}

function VerdictBadge({ verdict }: { verdict: string | null }) {
  if (!verdict) return null
  return (
    <span className={`text-xs font-semibold px-2 py-0.5 rounded border uppercase ${VERDICT_STYLES[verdict] ?? ''}`}>
      {verdict}
    </span>
  )
}

function WeekSection({ week }: { week: TrackRecordWeek }) {
  const [open, setOpen] = useState(true)
  const { stats } = week

  return (
    <div className="border border-border rounded-lg overflow-hidden">
      <button
        onClick={() => setOpen(o => !o)}
        className="w-full flex items-center gap-3 px-4 py-3 bg-surface-1 hover:bg-surface-elevated
                   transition-colors duration-150 text-left"
      >
        <ChevronDown
          size={16}
          className={`text-text-secondary shrink-0 transition-transform duration-200 ${open ? '' : '-rotate-90'}`}
        />
        <span className="text-sm font-semibold text-text-primary">
          Week of {formatRunDate(week.run_date)}
        </span>
        <span className="text-xs text-text-secondary ml-2">
          {stats.analyzed} analyzed
        </span>
        <div className="flex gap-2 ml-auto text-xs">
          <span className="text-accent font-medium">{stats.buy} Buy</span>
          <span className="text-warning font-medium">{stats.hold} Hold</span>
          <span className="text-error font-medium">{stats.avoid} Avoid</span>
        </div>
      </button>

      {open && (
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-t border-border bg-surface-elevated/50">
                <th className="text-left px-4 py-2 text-xs text-text-secondary font-medium">Ticker</th>
                <th className="text-left px-4 py-2 text-xs text-text-secondary font-medium">Verdict</th>
                <th className="text-left px-4 py-2 text-xs text-text-secondary font-medium">Price at verdict</th>
                <th className="text-left px-4 py-2 text-xs text-text-secondary font-medium hidden md:table-cell">Thesis</th>
              </tr>
            </thead>
            <tbody>
              {week.rows.map(row => (
                <tr key={row.ticker} className="border-t border-border hover:bg-surface-elevated/30 transition-colors">
                  <td className="px-4 py-2.5">
                    <Link
                      href={`/preview/${row.ticker.toLowerCase()}`}
                      className="font-bold text-text-primary hover:text-accent transition-colors"
                    >
                      {row.ticker}
                    </Link>
                  </td>
                  <td className="px-4 py-2.5">
                    <VerdictBadge verdict={row.verdict} />
                  </td>
                  <td className="px-4 py-2.5 text-text-secondary font-mono text-xs">
                    {formatPrice(row.current_price)}
                  </td>
                  <td className="px-4 py-2.5 text-text-secondary text-xs hidden md:table-cell max-w-xs">
                    <span className="line-clamp-2">{row.synthesis_summary ?? '—'}</span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}

export default function TrackRecordPage() {
  const [data, setData] = useState<TrackRecordResponse | null>(null)
  const [error, setError] = useState(false)

  useEffect(() => {
    apiClient.getTrackRecord(100)
      .then(setData)
      .catch(() => setError(true))
  }, [])

  if (error) {
    return (
      <div className="container mx-auto px-4 py-16 text-center text-text-secondary">
        Unable to load track record. Try again later.
      </div>
    )
  }

  return (
    <div className="container mx-auto px-4 py-10 max-w-3xl">
      <div className="mb-8">
        <h1 className="text-3xl font-bold text-text-primary mb-2">Signal Track Record</h1>
        <p className="text-sm text-text-secondary">
          Every Buy / Hold / Avoid verdict the engine has made, timestamped at the price of verdict.{' '}
          <span className="text-text-subtle">Performance tracking coming soon.</span>
        </p>
      </div>

      {!data && (
        <div className="text-center py-20 text-text-secondary">Loading...</div>
      )}

      {data && data.weeks.length === 0 && (
        <div className="text-center py-20 text-text-secondary">
          <p className="text-lg font-medium mb-2">Track record is building</p>
          <p className="text-sm">Check back after the first weekly batch runs on Monday.</p>
        </div>
      )}

      {data && data.weeks.length > 0 && (
        <>
          <p className="text-xs text-text-subtle mb-6">
            {data.total_weeks} week{data.total_weeks !== 1 ? 's' : ''} tracked
          </p>
          <div className="flex flex-col gap-4">
            {data.weeks.map(week => (
              <WeekSection key={week.run_date} week={week} />
            ))}
          </div>
        </>
      )}

      <div className="mt-10">
        <InlineDisclaimer />
      </div>
    </div>
  )
}
```

- [ ] **Step 2: Verify TypeScript compiles**

```bash
cd /Users/tui/research-swarm/frontend
npx tsc --noEmit 2>&1 | grep track-record
```

Expected: no errors.

- [ ] **Step 3: Commit**

```bash
git add frontend/app/track-record/page.tsx
git commit -m "feat: add public track record page grouped by week"
```

---

## Task 12: Preview Dynamic Route

**Files:**
- Create: `frontend/app/preview/[ticker]/page.tsx`
- Delete: `frontend/app/preview/nvda/page.tsx`

- [ ] **Step 1: Create the dynamic page**

Create `frontend/app/preview/[ticker]/page.tsx`:

```tsx
'use client'

import { useEffect, useState } from 'react'
import { useParams } from 'next/navigation'
import Link from 'next/link'
import { Lock, ArrowLeft } from 'lucide-react'
import { useUser } from '@clerk/nextjs'
import { useEntitlements } from '@/lib/hooks/useEntitlements'
import { apiClient } from '@/lib/api/client'
import { InlineDisclaimer } from '@/components/ui/InlineDisclaimer'
import { Button } from '@/components/ui/button'
import type { WeeklySignalPublic, WeeklySignalFull } from '@/types/weekly-signals'

function formatDate(dateStr: string): string {
  return new Date(dateStr).toLocaleDateString('en-US', {
    month: 'short', day: 'numeric', year: 'numeric'
  })
}

function formatPct(val: number | null, decimals = 1): string {
  if (val == null) return '—'
  const sign = val >= 0 ? '+' : ''
  return `${sign}${val.toFixed(decimals)}%`
}

function formatMarketCtx(label: string, val: number | null): string {
  if (val == null) return `${label} n/a`
  const sign = val >= 0 ? '+' : ''
  return `${label} ${sign}${val.toFixed(1)}%`
}

const VERDICT_STYLES: Record<string, { bg: string; text: string; border: string }> = {
  buy:   { bg: 'bg-accent/10',   text: 'text-accent',   border: 'border-accent/20' },
  hold:  { bg: 'bg-warning/10',  text: 'text-warning',  border: 'border-warning/20' },
  avoid: { bg: 'bg-error/10',    text: 'text-error',    border: 'border-error/20' },
}

function SignalCard({
  label,
  value,
  locked,
}: {
  label: string
  value: string
  locked: boolean
}) {
  return (
    <div className="bg-surface-1 border border-border rounded-lg p-4 text-center relative overflow-hidden">
      <div className="text-xs text-text-secondary mb-1">{label}</div>
      {locked ? (
        <>
          <div className="text-lg font-bold text-text-primary blur-sm select-none">{value}</div>
          <div className="absolute inset-0 flex items-center justify-center bg-surface-1/60">
            <span className="flex items-center gap-1 text-xs text-accent font-semibold">
              <Lock size={11} /> Starter+
            </span>
          </div>
        </>
      ) : (
        <div className="text-lg font-bold text-accent">{value}</div>
      )}
    </div>
  )
}

export default function WeeklyPreviewPage() {
  const params = useParams()
  const ticker = (params?.ticker as string ?? '').toUpperCase()
  const { isSignedIn } = useUser()
  const { data: ents } = useEntitlements()

  const [signal, setSignal] = useState<WeeklySignalPublic | null>(null)
  const [notFound, setNotFound] = useState(false)
  const [error, setError] = useState(false)

  const isStarterPlus = isSignedIn && ents && !ents.usage.is_free_tier
  const full = signal as WeeklySignalFull | null

  useEffect(() => {
    if (!ticker) return
    apiClient.getWeeklyPreview(ticker)
      .then(setSignal)
      .catch((e: any) => {
        if (e?.status === 404) setNotFound(true)
        else setError(true)
      })
  }, [ticker])

  if (notFound) {
    return (
      <div className="container mx-auto px-4 py-16 max-w-2xl text-center">
        <p className="text-xl font-semibold text-text-primary mb-2">No recent signal for {ticker}</p>
        <p className="text-text-secondary mb-6 text-sm">
          {ticker} wasn't in this week's batch. Run an on-demand analysis instead.
        </p>
        <Link href="/analyze">
          <Button>Analyze {ticker}</Button>
        </Link>
      </div>
    )
  }

  if (error) {
    return (
      <div className="container mx-auto px-4 py-16 text-center text-text-secondary">
        Unable to load signal. Try again later.
      </div>
    )
  }

  if (!signal) {
    return (
      <div className="container mx-auto px-4 py-16 text-center text-text-secondary">
        Loading...
      </div>
    )
  }

  const verdictStyle = VERDICT_STYLES[signal.verdict ?? ''] ?? VERDICT_STYLES.hold

  return (
    <div className="container mx-auto px-4 py-10 max-w-2xl">

      {/* Breadcrumb */}
      <Link
        href="/leaderboard"
        className="inline-flex items-center gap-1.5 text-sm text-text-secondary hover:text-text-primary
                   transition-colors mb-6"
      >
        <ArrowLeft size={14} />
        Back to Leaderboard
      </Link>

      {/* Header */}
      <div className="flex items-center gap-3 mb-2">
        <h1 className="text-4xl font-bold text-text-primary">{signal.ticker}</h1>
        {signal.verdict && (
          <span className={`text-sm font-bold px-3 py-1 rounded border uppercase
                           ${verdictStyle.bg} ${verdictStyle.text} ${verdictStyle.border}`}>
            {signal.verdict}
          </span>
        )}
      </div>
      <div className="text-xs text-text-subtle mb-6 flex gap-2 flex-wrap">
        <span>{formatDate(signal.run_date)}</span>
        {(signal.es_change_pct != null || signal.nq_change_pct != null) && (
          <>
            <span>·</span>
            <span>{formatMarketCtx('ES', signal.es_change_pct)}</span>
            <span>·</span>
            <span>{formatMarketCtx('NQ', signal.nq_change_pct)}</span>
          </>
        )}
      </div>

      {/* Synthesis quote */}
      {signal.synthesis_summary && (
        <blockquote
          className="text-text-primary text-base leading-relaxed mb-6 pl-4"
          style={{ borderLeft: '3px solid var(--accent)' }}
        >
          {signal.synthesis_summary}
        </blockquote>
      )}

      {/* Signal cards */}
      <div className="grid grid-cols-3 gap-3 mb-6">
        <SignalCard
          label="Fair value gap"
          value={formatPct(signal.fair_value_gap_pct)}
          locked={false}
        />
        <SignalCard
          label="EV probability"
          value={full?.ev_probability != null ? `${Math.round(full.ev_probability * 100)}%` : '—'}
          locked={!isStarterPlus}
        />
        <SignalCard
          label="Stop-loss risk"
          value={full?.stop_loss_probability != null ? `${Math.round(full.stop_loss_probability * 100)}%` : '—'}
          locked={!isStarterPlus}
        />
      </div>

      {/* Catalyst summary (locked) */}
      {!isStarterPlus && (
        <div className="relative mb-6 bg-surface-1 border border-border rounded-lg p-4 overflow-hidden">
          <div className="text-xs text-text-secondary mb-1 font-medium uppercase tracking-wider">
            Catalyst Summary
          </div>
          <p className="text-sm text-text-secondary blur-sm select-none line-clamp-2">
            {signal.synthesis_summary ?? 'Key catalysts and risk factors...'}
          </p>
          <div className="absolute inset-0 flex items-center justify-center bg-surface-1/60">
            <span className="flex items-center gap-1.5 text-sm text-accent font-semibold">
              <Lock size={13} /> Unlock full catalyst breakdown
            </span>
          </div>
        </div>
      )}

      {isStarterPlus && full?.catalyst_summary && (
        <div className="mb-6 bg-surface-1 border border-border rounded-lg p-4">
          <div className="text-xs text-text-secondary mb-1 font-medium uppercase tracking-wider">
            Catalyst Summary
          </div>
          <p className="text-sm text-text-primary">{full.catalyst_summary}</p>
        </div>
      )}

      {/* Upgrade CTA */}
      {!isStarterPlus && (
        <div className="bg-accent/5 border border-accent/20 rounded-lg p-5 text-center mb-6">
          <p className="text-text-primary font-semibold mb-1">
            Get the full thesis, position sizing, and 20+ signal breakdown
          </p>
          <p className="text-text-secondary text-sm mb-4">From $19.99/mo</p>
          <Link href={isSignedIn ? '/#pricing' : '/sign-up'}>
            <Button>
              {isSignedIn ? 'Upgrade to Starter →' : 'Get started free →'}
            </Button>
          </Link>
        </div>
      )}

      <InlineDisclaimer />
    </div>
  )
}
```

- [ ] **Step 2: Delete the hardcoded NVDA preview page**

```bash
rm /Users/tui/research-swarm/frontend/app/preview/nvda/page.tsx
rmdir /Users/tui/research-swarm/frontend/app/preview/nvda
```

- [ ] **Step 3: Verify TypeScript compiles**

```bash
cd /Users/tui/research-swarm/frontend
npx tsc --noEmit 2>&1 | grep preview
```

Expected: no errors.

- [ ] **Step 4: Commit**

```bash
git add frontend/app/preview/
git commit -m "feat: add dynamic /preview/[ticker] page, replace hardcoded NVDA preview"
```

---

## Task 13: Add Leaderboard to Navigation

**Files:**
- Modify: `frontend/components/layout/Header.tsx`

- [ ] **Step 1: Add Leaderboard to both nav arrays**

In `frontend/components/layout/Header.tsx`, find:

```typescript
const PUBLIC_NAV_LINKS = [
  { href: '/#how-it-works', label: 'How It Works' },
  { href: '/#pricing',      label: 'Pricing'      },
  { href: '/#faq',          label: 'FAQ'           },
]

const AUTH_NAV_LINKS = [
  { href: '/dashboard',     label: 'Dashboard'    },
  ...PUBLIC_NAV_LINKS,
]
```

Replace with:

```typescript
const PUBLIC_NAV_LINKS = [
  { href: '/leaderboard',   label: 'Leaderboard'  },
  { href: '/#how-it-works', label: 'How It Works' },
  { href: '/#pricing',      label: 'Pricing'      },
  { href: '/#faq',          label: 'FAQ'           },
]

const AUTH_NAV_LINKS = [
  { href: '/dashboard',     label: 'Dashboard'    },
  { href: '/leaderboard',   label: 'Leaderboard'  },
  ...PUBLIC_NAV_LINKS.slice(1), // avoid duplicating Leaderboard
]
```

- [ ] **Step 2: Verify TypeScript compiles**

```bash
cd /Users/tui/research-swarm/frontend
npx tsc --noEmit 2>&1 | grep Header
```

Expected: no errors.

- [ ] **Step 3: Commit**

```bash
git add frontend/components/layout/Header.tsx
git commit -m "feat: add Leaderboard link to site navigation"
```

---

## Verification

After all tasks are complete:

- [ ] **Run full backend test suite**

```bash
cd /Users/tui/research-swarm
python -m pytest tests/test_weekly_signals_route.py tests/test_send_teaser_digest.py -v
```

Expected: all tests pass.

- [ ] **Start dev server and verify all three pages load**

```bash
cd /Users/tui/research-swarm/frontend
npm run dev
```

Visit:
- http://localhost:3000/leaderboard — should show ranked list (or empty state)
- http://localhost:3000/track-record — should show grouped weeks (or empty state)
- http://localhost:3000/preview/nvda — should load via dynamic route (not 404)
- http://localhost:3000/preview/aapl — should show "no signal" state

- [ ] **Check Leaderboard appears in nav on both desktop and mobile**

- [ ] **Final commit**

```bash
git add .
git commit -m "feat: Phase 1 complete — leaderboard, track record, preview, teaser digest"
```
