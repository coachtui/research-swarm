"""
Inngest function registry.

Exposes the shared `inngest_client` and `ACTIVE_FUNCTIONS`, the list of
functions the FastAPI app (api/index.py) mounts at /api/inngest via
`inngest.fast_api.serve`. There is no standalone HTTP handler here anymore —
the old Flask app was never served by any process.

Owner decision (2026-07-08): register weekly_market_outlook and the tiered
weekly_batch (docs/superpowers/specs/2026-07-08-tiered-batch-design.md). The
remaining dormant functions below stay unregistered until they consume
tiered batch data (see docs/superpowers/plans/2026-04-19-weekly-batch-alerts.md).

Owner decision (2026-07-09): also register the two Autopilot Phase 2
execution crons, execution_daily and execution_weekly
(docs/superpowers/plans/2026-07-08-autopilot-phase2-broker-sleeve-b.md).
Both use the same guarded-registration pattern (None when the pip SDK is
absent), so they are safe to add to the roster in every environment.

Owner decision (2026-07-09, Phase 3B): register theme_discovery_monthly and
theme_delta_weekly
(docs/superpowers/specs/2026-07-09-phase3b-theme-baskets-design.md).

Owner decision (2026-07-09, Phase 3C): register sleeve_a_funnel
(docs/superpowers/specs/2026-07-09-phase3c-sleeve-a-funnel-design.md).

Hosting decision (2026-07-08 review): Vercel installs the inngest SDK
transitively (requirements-vercel.txt -> requirements.txt), so the SDK being
importable does NOT mean this host should serve cron. The handler only
mounts where INNGEST_SIGNING_KEY is set — i.e. the cron host (Railway).
See should_mount_inngest() and the gate in api/index.py.
"""
from __future__ import annotations

from typing import Any, List, Optional

from inngest_app.client import inngest_client
from inngest_app.functions.weekly_batch import weekly_batch
from inngest_app.functions.weekly_outlook import weekly_market_outlook
from inngest_app.functions.execution_daily import execution_daily
from inngest_app.functions.execution_weekly import execution_weekly
from inngest_app.functions.theme_discovery_monthly import theme_discovery_monthly
from inngest_app.functions.theme_delta_weekly import theme_delta_weekly
from inngest_app.functions.sleeve_a_funnel import sleeve_a_funnel
from inngest_app.functions.thirteenf_study_quarterly import thirteenf_study_quarterly

# Dormant roster — intentionally NOT registered (need real batch data first):
# from inngest_app.functions.send_teaser_digest import send_teaser_digest
# from inngest_app.functions.send_watchlist_alerts import send_watchlist_alerts
# from inngest_app.functions.analyze_stock import analyze_stock

# Each function is None when the inngest pip SDK is absent (guarded
# registration in each module), so filter Nones to keep this list safe to
# pass to serve() in any environment.
ACTIVE_FUNCTIONS = [
    fn
    for fn in [weekly_market_outlook, weekly_batch, execution_daily, execution_weekly,
               theme_discovery_monthly, theme_delta_weekly, sleeve_a_funnel,
               thirteenf_study_quarterly]
    if fn is not None
]


def should_mount_inngest(
    signing_key: Optional[str],
    client: Optional[Any],
    functions: Optional[List[Any]],
) -> bool:
    """Decide whether api/index.py should mount the Inngest handler.

    Mount only when ALL hold:
    - INNGEST_SIGNING_KEY is set (opt-in per host — Railway yes, Vercel no,
      even though Vercel installs the SDK transitively via
      requirements-vercel.txt -> requirements.txt)
    - the pip SDK client was constructed (not None)
    - at least one function is registered
    """
    return bool(signing_key) and client is not None and bool(functions)
