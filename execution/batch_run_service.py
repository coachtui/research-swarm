"""Build, store, and read WeeklyBatchRun funnel-summary records.

build_batch_run_record and summarize_batch_run are pure (unit-testable, no
prisma). store/get/list are the only DB touchpoints and wrap the outcomes
Json column at the edge — same split as execution/outlook_service.py.
"""
from datetime import datetime
from typing import Any, Dict, List, Optional


def build_batch_run_record(
    run_date: datetime,
    status: str,
    *,
    abort_reason: Optional[str] = None,
    universe_size: Optional[int] = None,
    advanced_count: Optional[int] = None,
    watchlist_extras: Optional[int] = None,
    quant_stored: Optional[int] = None,
    quant_failed: Optional[int] = None,
    escalation_swarm: Optional[int] = None,
    escalation_reuse: Optional[int] = None,
    escalation_hold: Optional[int] = None,
    swarm_cap: Optional[int] = None,
    outcomes: Optional[Dict[str, str]] = None,
) -> Dict[str, Any]:
    return {
        "runDate": run_date,
        "status": status,
        "abortReason": abort_reason,
        "universeSize": universe_size,
        "advancedCount": advanced_count,
        "watchlistExtras": watchlist_extras,
        "quantStored": quant_stored,
        "quantFailed": quant_failed,
        "escalationSwarm": escalation_swarm,
        "escalationReuse": escalation_reuse,
        "escalationHold": escalation_hold,
        "swarmCap": swarm_cap,
        "outcomes": outcomes,
    }


def summarize_batch_run(
    *,
    universe_size: int,
    candidates: List[Dict[str, Any]],
    watchlist_extras: int,
    quant: Dict[str, Any],
    decisions: List[Dict[str, Any]],
    swarm_cap: int,
    outcomes: Dict[str, str],
) -> Dict[str, Any]:
    """Reduce weekly_batch's in-memory funnel state to build_batch_run_record kwargs."""
    return {
        "universe_size": universe_size,
        "advanced_count": len(candidates),
        "watchlist_extras": watchlist_extras,
        "quant_stored": quant["stored"],
        "quant_failed": quant["failed"],
        "escalation_swarm": sum(1 for d in decisions if d["action"] == "swarm"),
        "escalation_reuse": sum(1 for d in decisions if d["action"] == "reuse"),
        "escalation_hold": sum(1 for d in decisions if d["action"] == "hold"),
        "swarm_cap": swarm_cap,
        "outcomes": outcomes,
    }


async def store_batch_run(db, record: Dict[str, Any]) -> Any:
    from prisma import Json  # runtime-only dependency

    data = dict(record)
    if data.get("outcomes") is None:
        data.pop("outcomes", None)
    else:
        data["outcomes"] = Json(data["outcomes"])
    return await db.weeklybatchrun.create(data=data)


async def get_latest_batch_run(db) -> Optional[Any]:
    return await db.weeklybatchrun.find_first(order={"runDate": "desc"})


async def get_batch_run(db, run_date: datetime) -> Optional[Any]:
    return await db.weeklybatchrun.find_first(where={"runDate": run_date})


async def list_batch_runs(db, limit: int = 12) -> List[Any]:
    return await db.weeklybatchrun.find_many(
        order={"runDate": "desc"}, take=max(1, min(limit, 52))
    )
