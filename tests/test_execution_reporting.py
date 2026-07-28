"""EngineReport writer: never raises, always JSON-wraps body."""
import pytest

from execution.reporting import REPORT_TYPES, SEVERITIES, write_report


class _StubEngineReport:
    def __init__(self, fail=False):
        self.fail = fail
        self.created = []

    async def create(self, data):
        if self.fail:
            raise RuntimeError("db down")
        self.created.append(data)
        class Row: id = "rep_1"
        return Row()


class _StubDb:
    def __init__(self, fail=False):
        self.enginereport = _StubEngineReport(fail=fail)


@pytest.mark.asyncio
async def test_write_report_creates_row_and_returns_id():
    db = _StubDb()
    rid = await write_report("engine_failure", "critical", "unit-test",
                             "something broke", {"detail": "boom"}, db=db)
    assert rid == "rep_1"
    data = db.enginereport.created[0]
    assert data["type"] == "engine_failure"
    assert data["severity"] == "critical"
    assert data["source"] == "unit-test"
    assert data["title"] == "something broke"


@pytest.mark.asyncio
async def test_write_report_never_raises_on_db_failure():
    rid = await write_report("engine_failure", "critical", "unit-test",
                             "boom", {}, db=_StubDb(fail=True))
    assert rid is None


@pytest.mark.asyncio
async def test_write_report_tolerates_unknown_type_and_none_body():
    db = _StubDb()
    rid = await write_report("mystery_type", "loud", "unit-test", "t", None, db=db)
    assert rid == "rep_1"  # soft validation: log-and-write, never block


def test_report_type_vocabulary_matches_spec():
    assert REPORT_TYPES == frozenset({
        "theme_proposal", "membership_change", "theme_retired", "theme_pass_summary",
        "validation_failure", "engine_failure", "rebalance_summary",
        "breaker_event",
        # Phase 3C — Sleeve A funnel (shadow mode)
        "funnel_summary", "entry_order", "entry_filled", "entry_missed",
        "entry_deferred", "exit_stop", "exit_sell_verdict", "exit_outcompeted",
        "theme_review", "risk_trim", "light_run_failure",
        # Thesis-hold redesign (2026-07-10)
        "dca_add", "review_trigger", "thesis_reduce",
        # Thesis-first entry redesign (2026-07-27)
        "thesis_memo", "study_digest", "entry_rejected",
    })
    assert SEVERITIES == frozenset({"info", "warning", "critical"})
