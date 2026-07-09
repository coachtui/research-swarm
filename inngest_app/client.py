"""
Guarded Inngest client construction.

Every function module imports the client from here (never constructs its own
top-level `Inngest(...)` — that pattern used to live in analyze_stock.py and
broke importability whenever the pip `inngest` SDK wasn't installed).

If the pip SDK is unavailable, `inngest_client` is `None` and any module that
needs it MUST guard its own function registration behind a try/except (see
send_teaser_digest.py for the reference pattern) so importing this package
never raises just because the SDK is missing.
"""
from __future__ import annotations

import logging
import os
from typing import Any, Optional

logger = logging.getLogger(__name__)

inngest_client: Optional[Any] = None

try:
    from inngest import Inngest  # noqa: PLC0415 -- pip SDK; only importable now
    # that this package is `inngest_app` and no longer shadows it on sys.path.

    inngest_client = Inngest(
        app_id="research-swarm",
        signing_key=os.getenv("INNGEST_SIGNING_KEY"),
        event_key=os.getenv("INNGEST_EVENT_KEY"),
    )
except Exception:
    logger.warning(
        "inngest pip package not available — Inngest client disabled "
        "(functions will not register)"
    )
    inngest_client = None
