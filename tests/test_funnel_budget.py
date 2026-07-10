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
