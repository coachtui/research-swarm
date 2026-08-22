"""Failure alerts for the execution layer — journal-only (Phase 3B).

Email is dead: alerts land as EngineReport rows of type "engine_failure".
NEVER raises — a broken journal must not break the engine (the failure
posture is inaction + report, and inaction still happened; write_report
itself already swallows all errors).
"""
import logging
from typing import Any, Dict, Optional

from execution.reporting import write_report

logger = logging.getLogger(__name__)


async def send_failure_alert(
    subject: str,
    body: str,
    source: str = "engine",
    detail: Optional[Dict[str, Any]] = None,
) -> Dict[str, str]:
    """Raise an alert: an engine_failure row at "critical" severity.

    `detail` carries machine-readable context alongside the human sentence, so
    a caller does not have to choose between alerting (this) and journaling a
    structured body (write_report) and end up writing two rows for one event.
    """
    logger.warning("Autopilot alert: %s — %s", subject, body)
    report_body: Dict[str, Any] = {"detail": body}
    if detail:
        report_body.update(detail)
    report_id = await write_report(
        "engine_failure", "critical", source, subject, report_body
    )
    return {"status": "journaled" if report_id else "error"}
