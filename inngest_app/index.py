"""
Inngest function registry.

Exposes the shared `inngest_client` and `ACTIVE_FUNCTIONS`, the list of
functions the FastAPI app (api/index.py) mounts at /api/inngest via
`inngest.fast_api.serve`. There is no standalone HTTP handler here anymore —
the old Flask app was never served by any process.

Owner decision (2026-07-08): register ONLY weekly_market_outlook for now.
The dormant functions below stay unregistered until the tiered-batch
redesign lands (see docs/superpowers/plans/2026-04-19-weekly-batch-alerts.md
and the forthcoming tiered-batch plan).
"""
from __future__ import annotations

from inngest_app.client import inngest_client
from inngest_app.functions.weekly_outlook import weekly_market_outlook

# Dormant roster — intentionally NOT registered (tiered-batch redesign pending):
# from inngest_app.functions.weekly_batch import weekly_batch
# from inngest_app.functions.send_teaser_digest import send_teaser_digest
# from inngest_app.functions.send_watchlist_alerts import send_watchlist_alerts
# from inngest_app.functions.analyze_stock import analyze_stock

# Each function is None when the inngest pip SDK is absent (guarded
# registration in each module), so filter Nones to keep this list safe to
# pass to serve() in any environment.
ACTIVE_FUNCTIONS = [
    fn for fn in [weekly_market_outlook] if fn is not None
]
