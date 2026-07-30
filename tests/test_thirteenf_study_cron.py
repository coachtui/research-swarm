# tests/test_thirteenf_study_cron.py
"""Quarterly 13F study cron: never raises, paid step memoized, per-fund
isolation (spec §5, §7)."""
import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch

import inngest_app.functions.thirteenf_study_quarterly as tsq

FUNDS = [{"name": "Situational Awareness LP", "ciks": ["0002045724"]}]
GOOD_RAW = json.dumps({
    "method_rules": [{"rule": "r", "evidence": "e", "moves_cited": []}],
    "moves": [], "summary": "s"})
HISTORY = [
    {"period": "2026-03-31", "filed": "2026-05-14", "holdings": [
        {"issuer": "BLOOM", "cusip": "093712107", "class": "COM",
         "value": 100.0, "shares": 10.0, "share_type": "SH", "put_call": None}]},
    {"period": "2025-12-31", "filed": "2026-02-12", "holdings": []},
]


def _run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


class _MemoStep:
    """Inngest replay model: step.run memoizes by id across executions."""
    def __init__(self):
        self.memo = {}
        self.executed = []

    async def run(self, step_id, fn):
        if step_id not in self.memo:
            self.executed.append(step_id)
            self.memo[step_id] = await fn()
        return self.memo[step_id]


def test_module_imports_without_inngest_sdk():
    assert hasattr(tsq, "thirteenf_study_quarterly")   # None without SDK is fine


def test_happy_path_studies_and_persists():
    db = MagicMock()
    with patch.object(tsq, "fetch_13f_history", return_value=HISTORY), \
         patch.object(tsq, "reason_study", return_value=GOOD_RAW), \
         patch.object(tsq, "persist_digest", new=AsyncMock()) as persist, \
         patch.object(tsq, "write_report", new=AsyncMock()):
        out = _run(tsq._study_pipeline(db, FUNDS, "2026-08-21", step=None))
    assert out["funds"] == [{"fund": "Situational Awareness LP", "rules": 1}]
    assert out["failures"] == []
    persist.assert_awaited_once()
    assert persist.call_args.args[1] == "2026-08-21"


def test_replay_bills_the_paid_step_once():
    """Run the pipeline twice over the same memo store (the Inngest replay
    model). The paid fetch+study step and the persist step each execute
    once; the digest is identical because parse is pure."""
    db = MagicMock()
    step = _MemoStep()
    paid = MagicMock(return_value=GOOD_RAW)
    with patch.object(tsq, "fetch_13f_history", return_value=HISTORY), \
         patch.object(tsq, "reason_study", paid), \
         patch.object(tsq, "persist_digest", new=AsyncMock()) as persist, \
         patch.object(tsq, "write_report", new=AsyncMock()):
        _run(tsq._study_pipeline(db, FUNDS, "2026-08-21", step=step))
        _run(tsq._study_pipeline(db, FUNDS, "2026-08-21", step=step))  # replay
    assert paid.call_count == 1
    assert persist.await_count == 1
    assert len(step.executed) == 2          # study-… and study-persist-…


def test_parse_failure_journals_engine_failure_and_skips_persist():
    db = MagicMock()
    with patch.object(tsq, "fetch_13f_history", return_value=HISTORY), \
         patch.object(tsq, "reason_study", return_value="not json"), \
         patch.object(tsq, "persist_digest", new=AsyncMock()) as persist, \
         patch.object(tsq, "write_report", new=AsyncMock()) as report:
        out = _run(tsq._study_pipeline(db, FUNDS, "2026-08-21", step=None))
    assert out["failures"] == ["Situational Awareness LP"]
    persist.assert_not_awaited()
    assert any(c.args[0] == "engine_failure" for c in report.call_args_list)


def test_fund_failure_isolates_the_other_fund():
    funds = [{"name": "BOOM FUND", "ciks": ["1"]},
             {"name": "Situational Awareness LP", "ciks": ["0002045724"]}]

    def _fetch(ciks, limit=8):
        if ciks == ["1"]:
            raise RuntimeError("EDGAR down")
        return HISTORY

    db = MagicMock()
    with patch.object(tsq, "fetch_13f_history", side_effect=_fetch), \
         patch.object(tsq, "reason_study", return_value=GOOD_RAW), \
         patch.object(tsq, "persist_digest", new=AsyncMock()), \
         patch.object(tsq, "write_report", new=AsyncMock()) as report:
        out = _run(tsq._study_pipeline(db, funds, "2026-08-21", step=None))
    assert out["failures"] == ["BOOM FUND"]
    assert out["funds"] == [{"fund": "Situational Awareness LP", "rules": 1}]
    assert any(c.args[0] == "engine_failure" for c in report.call_args_list)


def test_fewer_than_two_filings_is_a_journaled_noop():
    db = MagicMock()
    with patch.object(tsq, "fetch_13f_history", return_value=HISTORY[:1]), \
         patch.object(tsq, "reason_study") as paid, \
         patch.object(tsq, "persist_digest", new=AsyncMock()) as persist, \
         patch.object(tsq, "write_report", new=AsyncMock()) as report:
        out = _run(tsq._study_pipeline(db, FUNDS, "2026-08-21", step=None))
    paid.assert_not_called()                # nothing to diff → no paid call
    persist.assert_not_awaited()
    assert out["failures"] == ["Situational Awareness LP"]
    assert any(c.args[0] == "engine_failure" for c in report.call_args_list)
