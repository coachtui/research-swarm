"""App-level failure alerts for the execution layer (deferred from Phase 1).

Same dormant-email posture as the outlook email: sends only when both
RESEND_API_KEY and OWNER_EMAIL are set; otherwise logs and reports
"skipped". NEVER raises — a broken alert channel must not break the engine
(the engine's failure posture is inaction + alert, and inaction still
happened).
"""
import html
import logging
import os
from typing import Dict

logger = logging.getLogger(__name__)


def send_failure_alert(subject: str, body: str) -> Dict[str, str]:
    owner_email = os.getenv("OWNER_EMAIL", "")
    api_key = os.getenv("RESEND_API_KEY", "")
    if not owner_email or not api_key:
        logger.warning("Autopilot alert skipped (email unconfigured): %s — %s", subject, body)
        return {"status": "skipped"}
    try:
        import resend  # lazy — only needed when email is actually enabled

        resend.api_key = api_key
        resend.Emails.send({
            "from": "DVRG Autopilot <digest@dvrg.co>",
            "to": [owner_email],
            "subject": f"[Autopilot alert] {subject}",
            "html": f"<pre style='font-family:monospace'>{html.escape(body)}</pre>",
        })
        return {"status": "sent"}
    except Exception:
        logger.exception("Autopilot alert failed to send: %s", subject)
        return {"status": "error"}
