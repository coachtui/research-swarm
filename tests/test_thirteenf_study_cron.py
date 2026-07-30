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
         patch.object(tsq, "load_rulebook", new=AsyncMock(return_value=None)), \
         patch.object(tsq, "reason_revision", return_value=GOOD_REVISION), \
         patch.object(tsq, "persist_rulebook", new=AsyncMock()), \
         patch.object(tsq, "write_report", new=AsyncMock()):
        out = _run(tsq._study_pipeline(db, FUNDS, "2026-08-21", step=None))
    assert out["funds"] == [{"fund": "Situational Awareness LP", "rules": 1,
                             "rulebook_version": 1}]
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
         patch.object(tsq, "load_rulebook", new=AsyncMock(return_value=None)), \
         patch.object(tsq, "reason_revision", return_value=GOOD_REVISION), \
         patch.object(tsq, "persist_rulebook", new=AsyncMock()), \
         patch.object(tsq, "write_report", new=AsyncMock()):
        _run(tsq._study_pipeline(db, FUNDS, "2026-08-21", step=step))
        _run(tsq._study_pipeline(db, FUNDS, "2026-08-21", step=step))  # replay
    assert paid.call_count == 1
    assert persist.await_count == 1
    assert len(step.executed) == 4    # study-…, study-persist-…, revise-…, revise-persist-…


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
         patch.object(tsq, "load_rulebook", new=AsyncMock(return_value=None)), \
         patch.object(tsq, "reason_revision", return_value=GOOD_REVISION), \
         patch.object(tsq, "persist_rulebook", new=AsyncMock()), \
         patch.object(tsq, "write_report", new=AsyncMock()) as report:
        out = _run(tsq._study_pipeline(db, funds, "2026-08-21", step=None))
    assert out["failures"] == ["BOOM FUND"]
    assert out["funds"] == [{"fund": "Situational Awareness LP", "rules": 1,
                             "rulebook_version": 1}]
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


# ── revise step (Phase B2) ───────────────────────────────────────────────────

GOOD_REVISION = json.dumps({
    "verdicts": [], "new_rules": [{"rule": "a learned rule", "rationale": "r"}],
    "calibration": {"typical_lead_quarters": 2.0}, "summary": "synthesis"})


def _patch_study(paid_study=GOOD_RAW):
    """Study half always succeeds; tests vary the revise half."""
    return [patch.object(tsq, "fetch_13f_history", return_value=HISTORY),
            patch.object(tsq, "reason_study", return_value=paid_study),
            patch.object(tsq, "persist_digest", new=AsyncMock())]


def test_revise_merges_and_persists_a_new_rulebook_version():
    db = MagicMock()
    ctx = _patch_study()
    with ctx[0], ctx[1], ctx[2], \
         patch.object(tsq, "load_rulebook", new=AsyncMock(return_value=None)), \
         patch.object(tsq, "reason_revision", return_value=GOOD_REVISION), \
         patch.object(tsq, "persist_rulebook", new=AsyncMock()) as persist_rb, \
         patch.object(tsq, "write_report", new=AsyncMock()):
        out = _run(tsq._study_pipeline(db, FUNDS, "2026-08-21", step=None))
    assert out["funds"][0]["rulebook_version"] == 1
    book = persist_rb.call_args.args[3]
    assert [r["rule"] for r in book["rules"]] == ["a learned rule"]


def test_revise_builds_on_the_existing_rulebook():
    db = MagicMock()
    prior = {"version": 4, "as_of": "2026-03-31", "retired": [],
             "calibration": {}, "summary": "old",
             "rules": [{"id": "keep-me", "rule": "keep me", "rationale": "r",
                        "confirmations": 2, "first_seen": "2025-06-30",
                        "last_reviewed": "2026-03-31",
                        "evidence_quarters": ["2026-03-31"], "status": "active"}]}
    ctx = _patch_study()
    with ctx[0], ctx[1], ctx[2], \
         patch.object(tsq, "load_rulebook", new=AsyncMock(return_value=prior)), \
         patch.object(tsq, "reason_revision", return_value=GOOD_REVISION), \
         patch.object(tsq, "persist_rulebook", new=AsyncMock()) as persist_rb, \
         patch.object(tsq, "write_report", new=AsyncMock()):
        _run(tsq._study_pipeline(db, FUNDS, "2026-08-21", step=None))
    book = persist_rb.call_args.args[3]
    assert book["version"] == 5
    assert sorted(r["id"] for r in book["rules"]) == ["a-learned-rule", "keep-me"]


def test_drifted_revise_KEEPS_the_prior_rulebook_and_still_persists_the_digest():
    """The compounding invariant: a bad revise must never cost us the book."""
    db = MagicMock()
    ctx = _patch_study()
    with ctx[0], ctx[1], ctx[2] as persist_digest, \
         patch.object(tsq, "load_rulebook", new=AsyncMock(return_value=None)), \
         patch.object(tsq, "reason_revision", return_value="not json"), \
         patch.object(tsq, "persist_rulebook", new=AsyncMock()) as persist_rb, \
         patch.object(tsq, "write_report", new=AsyncMock()) as report:
        out = _run(tsq._study_pipeline(db, FUNDS, "2026-08-21", step=None))
    persist_digest.assert_awaited_once()          # study was paid for — keep it
    persist_rb.assert_not_awaited()               # no new version written
    assert out["funds"][0]["rulebook_version"] is None
    assert any(c.args[0] == "engine_failure" for c in report.call_args_list)


def test_replay_bills_study_and_revise_exactly_once_each():
    db = MagicMock()
    step = _MemoStep()
    paid_study = MagicMock(return_value=GOOD_RAW)
    paid_revise = MagicMock(return_value=GOOD_REVISION)
    with patch.object(tsq, "fetch_13f_history", return_value=HISTORY), \
         patch.object(tsq, "reason_study", paid_study), \
         patch.object(tsq, "reason_revision", paid_revise), \
         patch.object(tsq, "load_rulebook", new=AsyncMock(return_value=None)), \
         patch.object(tsq, "persist_digest", new=AsyncMock()), \
         patch.object(tsq, "persist_rulebook", new=AsyncMock()) as persist_rb, \
         patch.object(tsq, "write_report", new=AsyncMock()):
        _run(tsq._study_pipeline(db, FUNDS, "2026-08-21", step=step))
        _run(tsq._study_pipeline(db, FUNDS, "2026-08-21", step=step))   # replay
    assert paid_study.call_count == 1 and paid_revise.call_count == 1
    assert persist_rb.await_count == 1
    assert len(step.executed) == 4      # study, persist, revise, revise-persist


# ── trusted-fund retirement (SALP forced liquidation, 2026-07-30) ────────────
# A fund past its retire_after date must not be studied: a margin-driven
# unwind is not method, and the November run must not read SALP's zeroed
# Q3 book as a curriculum quarter even if nobody edits constants by then.

RETIRED = [{"name": "Situational Awareness LP", "ciks": ["0002045724"],
            "retire_after": "2026-09-01"}]


def test_fund_past_retire_after_is_skipped_without_a_paid_call():
    db = MagicMock()
    with patch.object(tsq, "fetch_13f_history") as fetch, \
         patch.object(tsq, "reason_study") as paid, \
         patch.object(tsq, "persist_digest", new=AsyncMock()) as persist, \
         patch.object(tsq, "write_report", new=AsyncMock()) as report:
        out = _run(tsq._study_pipeline(db, RETIRED, "2026-11-21", step=None))
    fetch.assert_not_called()
    paid.assert_not_called()
    persist.assert_not_awaited()
    assert out["funds"] == [] and out["failures"] == []
    assert out["retired"] == ["Situational Awareness LP"]
    # journaled as deliberate retirement, NOT engine_failure — a November
    # operator must see "retired", not debug a silent empty run
    types = [c.args[0] for c in report.call_args_list]
    assert "engine_failure" not in types
    assert any("retired" in (c.args[3] or "").lower()
               for c in report.call_args_list)


def test_fund_before_retire_after_is_still_studied():
    """The Aug 21 run studies Q2 — the last clean quarter — because the run
    date precedes retire_after."""
    db = MagicMock()
    with patch.object(tsq, "fetch_13f_history", return_value=HISTORY), \
         patch.object(tsq, "reason_study", return_value=GOOD_RAW) as paid, \
         patch.object(tsq, "load_rulebook", new=AsyncMock(return_value=None)), \
         patch.object(tsq, "reason_revision", return_value=GOOD_REVISION), \
         patch.object(tsq, "persist_rulebook", new=AsyncMock()), \
         patch.object(tsq, "persist_digest", new=AsyncMock()), \
         patch.object(tsq, "write_report", new=AsyncMock()):
        out = _run(tsq._study_pipeline(db, RETIRED, "2026-08-21", step=None))
    paid.assert_called_once()
    assert out["funds"][0]["fund"] == "Situational Awareness LP"
    assert out["retired"] == []


def test_fund_without_retire_after_is_unaffected():
    db = MagicMock()
    with patch.object(tsq, "fetch_13f_history", return_value=HISTORY), \
         patch.object(tsq, "reason_study", return_value=GOOD_RAW), \
         patch.object(tsq, "load_rulebook", new=AsyncMock(return_value=None)), \
         patch.object(tsq, "reason_revision", return_value=GOOD_REVISION), \
         patch.object(tsq, "persist_rulebook", new=AsyncMock()), \
         patch.object(tsq, "persist_digest", new=AsyncMock()), \
         patch.object(tsq, "write_report", new=AsyncMock()):
        out = _run(tsq._study_pipeline(db, FUNDS, "2026-11-21", step=None))
    assert out["funds"] and out["retired"] == []
