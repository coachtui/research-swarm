"""Dry-run the weekly delta pass without applying it.

theme_delta_weekly's paid `reason` step is memoized inside Inngest, which makes
"what did the model actually say?" and "what would Saturday do?" awkward to
answer — the dashboard is the only reader, and run history ages out.

This reaches the SAME plan the cron would, then stops. It reuses
plan_delta_actions (a pure function) rather than reimplementing the thresholds,
so it cannot drift from the real decision logic. apply_actions is never called
and nothing is written.
"""
import logging
from typing import Any, Dict, Optional, Set

import execution.themes.delta as delta_mod
from execution.themes.discovery import _current_theme_state
from execution.themes.lifecycle import plan_delta_actions

logger = logging.getLogger(__name__)


async def probe_delta(
    db, llm_call=None, tradable: Optional[Set[str]] = None,
) -> Dict[str, Any]:
    """Gather -> reason (PAID) -> parse -> validate -> plan. Never applies.

    llm_call is injected for tests; production callers leave it None and pay for
    one real model call. Returns the raw model text alongside the plan, because
    reading the raw text is the point.
    """
    current = await _current_theme_state(db, include_retired=False)
    active = [
        {**t, "constituents": [c for c in t["constituents"] if c["status"] == "active"]}
        for t in current
    ]

    raw = delta_mod.reason_delta({"active_themes": active}, llm_call=llm_call)
    bundle = delta_mod.parse_and_validate_delta(raw, tradable=tradable)
    plan = plan_delta_actions(current, bundle["deltas"], bundle["validation"])

    return {
        "themes_seen": len(active),
        "raw": raw,
        "deltas": bundle["deltas"],
        "validation": bundle["validation"],
        "skipped": bundle["skipped"],
        "actions": plan["actions"],
        "rejected": plan["rejected"],
    }
