"""Tests for execution/batch_run_service.py (db mocked)."""
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from execution.batch_run_service import (
    build_batch_run_record,
    get_batch_run,
    get_latest_batch_run,
    list_batch_runs,
    store_batch_run,
    summarize_batch_run,
)

RUN_DATE = datetime(2026, 7, 13, tzinfo=timezone.utc)


def test_build_record_completed_status():
    record = build_batch_run_record(
        RUN_DATE, "completed",
        universe_size=191, advanced_count=23, watchlist_extras=3,
        quant_stored=22, quant_failed=1,
        escalation_swarm=3, escalation_reuse=2, escalation_hold=17,
        swarm_cap=5, outcomes={"AAPL": "full"},
    )
    assert record["runDate"] == RUN_DATE
    assert record["status"] == "completed"
    assert record["abortReason"] is None
    assert record["universeSize"] == 191
    assert record["advancedCount"] == 23
    assert record["watchlistExtras"] == 3
    assert record["quantStored"] == 22
    assert record["quantFailed"] == 1
    assert record["escalationSwarm"] == 3
    assert record["escalationReuse"] == 2
    assert record["escalationHold"] == 17
    assert record["swarmCap"] == 5
    assert record["outcomes"] == {"AAPL": "full"}


def test_build_record_aborted_status_defaults_counts_to_none():
    record = build_batch_run_record(
        RUN_DATE, "aborted", abort_reason="empty_candidates",
        universe_size=0, advanced_count=0, watchlist_extras=0,
    )
    assert record["status"] == "aborted"
    assert record["abortReason"] == "empty_candidates"
    assert record["universeSize"] == 0
    assert record["advancedCount"] == 0
    assert record["quantStored"] is None
    assert record["escalationSwarm"] is None
    assert record["outcomes"] is None


def test_summarize_batch_run_counts_decisions_by_action():
    decisions = [
        {"ticker": "AAPL", "action": "swarm"},
        {"ticker": "MSFT", "action": "swarm"},
        {"ticker": "NVDA", "action": "reuse"},
        {"ticker": "TSLA", "action": "hold"},
        {"ticker": "AMD", "action": "hold"},
    ]
    quant = {"stored": 22, "failed": 1}
    outcomes = {"AAPL": "full", "MSFT": "step_failed", "NVDA": "reused"}

    counts = summarize_batch_run(
        universe_size=191, candidates=[{}] * 23, watchlist_extras=3,
        quant=quant, decisions=decisions, swarm_cap=5, outcomes=outcomes,
    )

    assert counts["universe_size"] == 191
    assert counts["advanced_count"] == 23
    assert counts["watchlist_extras"] == 3
    assert counts["quant_stored"] == 22
    assert counts["quant_failed"] == 1
    assert counts["escalation_swarm"] == 2
    assert counts["escalation_reuse"] == 1
    assert counts["escalation_hold"] == 2
    assert counts["swarm_cap"] == 5
    assert counts["outcomes"] == outcomes


def test_summarize_batch_run_zero_decisions():
    counts = summarize_batch_run(
        universe_size=191, candidates=[{}] * 5, watchlist_extras=0,
        quant={"stored": 5, "failed": 0}, decisions=[], swarm_cap=5, outcomes={},
    )
    assert counts["escalation_swarm"] == 0
    assert counts["escalation_reuse"] == 0
    assert counts["escalation_hold"] == 0
    assert counts["outcomes"] == {}


@pytest.mark.asyncio
async def test_store_batch_run_creates_row_and_wraps_outcomes_json():
    db = MagicMock()
    db.weeklybatchrun.create = AsyncMock(return_value="row")
    record = build_batch_run_record(
        RUN_DATE, "completed", universe_size=191, outcomes={"AAPL": "full"},
    )
    result = await store_batch_run(db, record)
    assert result == "row"
    data = db.weeklybatchrun.create.call_args.kwargs["data"]
    assert data["status"] == "completed"
    # prisma.Json is stubbed by conftest; assert it was wrapped (not the raw dict)
    assert data["outcomes"] is not record["outcomes"]


@pytest.mark.asyncio
async def test_store_batch_run_omits_none_outcomes():
    db = MagicMock()
    db.weeklybatchrun.create = AsyncMock(return_value="row")
    record = build_batch_run_record(RUN_DATE, "aborted", abort_reason="empty_candidates")
    await store_batch_run(db, record)
    data = db.weeklybatchrun.create.call_args.kwargs["data"]
    assert "outcomes" not in data


@pytest.mark.asyncio
async def test_get_latest_batch_run_orders_by_run_date_desc():
    db = MagicMock()
    db.weeklybatchrun.find_first = AsyncMock(return_value="latest")
    assert await get_latest_batch_run(db) == "latest"
    kwargs = db.weeklybatchrun.find_first.call_args.kwargs
    assert kwargs["order"] == {"runDate": "desc"}


@pytest.mark.asyncio
async def test_get_batch_run_filters_by_run_date():
    db = MagicMock()
    db.weeklybatchrun.find_first = AsyncMock(return_value="row")
    assert await get_batch_run(db, RUN_DATE) == "row"
    kwargs = db.weeklybatchrun.find_first.call_args.kwargs
    assert kwargs["where"] == {"runDate": RUN_DATE}


@pytest.mark.asyncio
async def test_list_batch_runs_orders_desc_and_clamps_limit():
    db = MagicMock()
    db.weeklybatchrun.find_many = AsyncMock(return_value=["a", "b"])
    result = await list_batch_runs(db, limit=999)
    assert result == ["a", "b"]
    kwargs = db.weeklybatchrun.find_many.call_args.kwargs
    assert kwargs["order"] == {"runDate": "desc"}
    assert kwargs["take"] == 52
