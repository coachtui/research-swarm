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

from fastapi import APIRouter, Depends, HTTPException

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
