"""Failure alerts for the execution layer — journal-only (Phase 3B).

Email is dead: alerts land as EngineReport rows of type "engine_failure".
NEVER raises — a broken journal must not break the engine (the failure
posture is inaction + report, and inaction still happened; write_report
itself already swallows all errors).
"""
import logging
from typing import Dict

from execution.reporting import write_report

logger = logging.getLogger(__name__)


async def send_failure_alert(subject: str, body: str, source: str = "engine") -> Dict[str, str]:
    logger.warning("Autopilot alert: %s — %s", subject, body)
    report_id = await write_report(
        "engine_failure", "critical", source, subject, {"detail": body}
    )
    return {"status": "journaled" if report_id else "error"}
