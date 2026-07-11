"""EngineReport journal writer — the engine's only channel to the owner.

Never raises: a broken journal must never block the engine (the engine's
failure posture is inaction + report, and inaction still happened). Unknown
types/severities are logged and written as-is — the journal is append-only
and freeform enough to absorb drift.
"""
import logging
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

REPORT_TYPES = frozenset({
    "theme_proposal", "membership_change", "theme_retired",
    "validation_failure", "engine_failure", "rebalance_summary",
    "breaker_event",
    # Phase 3C — Sleeve A funnel (shadow mode)
    "funnel_summary", "entry_order", "entry_filled", "entry_missed",
    "entry_deferred", "exit_stop", "exit_sell_verdict", "exit_outcompeted",
    "theme_review", "risk_trim", "light_run_failure",
    # Thesis-hold redesign (2026-07-10) — review triggers + ADD/REDUCE outcomes
    "dca_add", "review_trigger", "thesis_reduce",
})
SEVERITIES = frozenset({"info", "warning", "critical"})


async def write_report(
    report_type: str,
    severity: str,
    source: str,
    title: str,
    body: Optional[Dict[str, Any]],
    db=None,
) -> Optional[str]:
    """Append one EngineReport row. Returns the row id, or None on failure."""
    try:
        if report_type not in REPORT_TYPES:
            logger.warning("EngineReport: unknown type %r (writing anyway)", report_type)
        if severity not in SEVERITIES:
            logger.warning("EngineReport: unknown severity %r (writing anyway)", severity)
        from prisma import Json  # noqa: PLC0415 — runtime-only dependency

        if db is None:
            from api.lib.db import get_db  # noqa: PLC0415
            db = await get_db()
        row = await db.enginereport.create(data={
            "type": report_type,
            "severity": severity,
            "source": source,
            "title": title,
            "body": Json(body or {}),
        })
        return row.id
    except Exception:
        logger.exception("EngineReport write failed: %s — %s", report_type, title)
        return None
