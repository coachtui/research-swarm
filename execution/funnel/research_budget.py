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
