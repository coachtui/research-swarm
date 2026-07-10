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


async def reuse_or_budget(db, ticker: str, run_date: datetime) -> Dict[str, Any]:
    """Handshake gate: reuse fresh result, analyze, or skip on budget exhaustion."""
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
    """Run the paid stock analysis with standard parameters."""
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
    """Persist the analysis result to the signal row and upgrade to full tier."""
    signals = extract_signals_from_result(result, ticker=ticker)
    if signals is None:
        return {"status": "failed", "signals": None}
    await ensure_signal_row(db, ticker, run_date, current_price, screen_score)
    ok = await _service(db).upgrade_to_full(
        ticker=ticker, run_date=run_date, result=result,
        escalation_score=0.0, escalation_reasons=[_FUNNEL_MARKER],
    )
    return {"status": "upgraded" if ok else "failed",
            "signals": signals if ok else None}


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
