"""
Weekly market outlook — Autopilot Phase 1.

Cron: Sunday 20:00 UTC (before the Monday 03:00 UTC weekly batch), so the
outlook exists before any research/trading downstream ever wants it.

Pipeline: fetch market history -> indicators (sector strength, breadth,
regime) -> LLM strategist (with mechanical fallback) -> store MarketOutlook
-> email the owner.

Failure posture: OutlookDataError or any step failure results in NO outlook row for the week — never a partial/guessed outlook. Failures surface via Inngest's failure dashboard/notifications; an app-level failure-alert email is deferred to Phase 2.
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


# ── Pure helpers (unit-tested) ───────────────────────────────────────────────

def build_outlook_email_html(record: Dict[str, Any]) -> str:
    """Render the weekly outlook email from an outlook record dict."""
    regime = record["regime"].replace("_", " ").upper()
    run_date = record["runDate"].strftime("%B %d, %Y")

    override_line = ""
    if record["strategistOverride"]:
        override_line = (
            f"<p style='color:#b8860b'>Strategist override: mechanical call was "
            f"<b>{record['regimeMechanical']}</b>.</p>"
        )
    status_line = ""
    if record["strategistStatus"] != "ok":
        status_line = (
            "<p style='color:#c0392b'>Strategist status: fallback — "
            "mechanical regime used, no narrative this week.</p>"
        )

    conviction = record.get("conviction")
    conviction_str = f"{round(conviction * 100)}%" if conviction is not None else "n/a"

    rows = "".join(
        f"<tr><td>{r['rank_1m']}</td><td>{r['sector']} ({r['etf']})</td>"
        f"<td>{r['rank_change']:+d}</td><td>{r['score']:+.4f}</td></tr>"
        for r in record["sectorRankings"]
    )
    rotations = "".join(
        f"<li>{f['sector']} ({f['etf']}): rotation {f['direction'].replace('_', ' ')} "
        f"({f['rank_change']:+d} ranks)</li>"
        for f in record["rotationFlags"]
    ) or "<li>None detected</li>"

    breadth = record["breadth"]

    return f"""
<!DOCTYPE html>
<html>
<body style="font-family:sans-serif;max-width:640px;margin:0 auto;padding:24px;color:#333">
  <h2 style="color:#00D9B5;margin-top:0">DVRG Market Outlook — {run_date}</h2>
  <h3>Regime: {regime} <span style="color:#999;font-weight:normal">(conviction {conviction_str})</span></h3>
  {override_line}
  {status_line}
  <h4>Sector rankings (1m rank, best first)</h4>
  <table border="1" cellpadding="6" style="border-collapse:collapse;font-size:13px">
    <tr><th>Rank</th><th>Sector</th><th>Rank Δ (3m→1m)</th><th>Score</th></tr>
    {rows}
  </table>
  <h4>Rotation flags</h4>
  <ul>{rotations}</ul>
  <h4>Breadth</h4>
  <p>{breadth.get("pct_above_200dma")}% of sector ETFs above 200dma;
     RSP/SPY 3-month trend {breadth.get("equal_weight_trend_3m")}%.</p>
  <h4>Strategist reasoning</h4>
  <p>{record.get("reasoning") or "n/a"}</p>
  <hr style="border:none;border-top:1px solid #eee;margin:24px 0">
  <p style="font-size:12px;color:#999">Autopilot Phase 1 — outlook only, no trading. Do not reply.</p>
</body>
</html>
"""


def compute_extended_signals(closes_extra) -> "tuple[Dict[str, Any], list]":
    """Phase 3A industry + size/style passes.

    Each pass degrades independently to None. Returns (out, failures) where
    failures is a list of (subject, detail) for the async caller to journal —
    this helper stays sync/pure so it remains unit-testable.
    """
    from execution.indicators.industry_strength import rank_industries  # noqa: PLC0415
    from execution.indicators.size_style import compute_size_style  # noqa: PLC0415

    out: Dict[str, Any] = {"industry": None, "size_style": None}
    failures: list = []
    try:
        out["industry"] = rank_industries(closes_extra)
    except Exception as exc:
        logger.exception("Outlook industry pass failed")
        failures.append(("Outlook industry pass failed", f"{type(exc).__name__}: {exc}"))
    try:
        out["size_style"] = compute_size_style(closes_extra)
    except Exception as exc:
        logger.exception("Outlook size/style pass failed")
        failures.append(("Outlook size/style pass failed", f"{type(exc).__name__}: {exc}"))
    return out, failures


async def compute_theme_rankings_payload(db) -> "Optional[Dict[str, Any]]":
    """Fetch active themes and rank their synthetic baskets (Phase 3B).

    Returns None in the pre-first-discovery state (no themes with active
    constituents). Raises on real failures — the caller owns degrade+alert.
    """
    from execution.constants import BENCHMARK  # noqa: PLC0415
    from execution.indicators.theme_strength import rank_themes  # noqa: PLC0415
    from execution.market_data import (  # noqa: PLC0415
        fetch_closes_batch, fetch_history_for,
    )

    rows = await db.themebasket.find_many(
        where={"status": "active"}, include={"constituents": True})
    themes = [{
        "slug": r.slug, "name": r.name, "confidence": r.confidence,
        "tickers": [c.ticker for c in (r.constituents or [])
                    if c.status == "active"],
    } for r in rows]
    themes = [t for t in themes if t["tickers"]]
    if not themes:
        return None  # pre-first-discovery state: seeds have no constituents
    all_tickers = sorted({t for th in themes for t in th["tickers"]})
    closes = fetch_closes_batch(all_tickers)
    spy = fetch_history_for([BENCHMARK]).get(BENCHMARK)
    if spy is None:
        raise RuntimeError("SPY history unavailable for theme pass")
    return rank_themes(themes, closes, spy)


# ── Inngest function ─────────────────────────────────────────────────────────
# Guarded registration so pure helpers are unit-testable without the inngest
# runtime (same pattern as send_teaser_digest.py).

def _register_inngest_function():
    import inngest as inngest_sdk  # noqa: PLC0415 — pip SDK (module-level Trigger* classes)

    from inngest_app.client import inngest_client  # noqa: PLC0415

    @inngest_client.create_function(
        fn_id="weekly-market-outlook",
        trigger=inngest_sdk.TriggerCron(cron="0 20 * * 0"),  # Sunday 20:00 UTC
        name="Weekly Market Outlook",
        retries=1,
    )
    async def weekly_market_outlook(ctx: "inngest_sdk.Context") -> Dict[str, Any]:
        step = ctx.step  # steps live on ctx in the current SDK

        run_date = datetime.now(timezone.utc)

        # Step 1: indicators (JSON-serializable payload only crosses steps)
        async def compute_indicators() -> Dict[str, Any]:
            from execution.alerts import send_failure_alert  # noqa: PLC0415
            from execution.constants import (  # noqa: PLC0415
                BENCHMARK, INDUSTRY_ETFS, SIZE_STYLE_ETFS, VIX,
            )
            from execution.indicators.breadth import compute_breadth  # noqa: PLC0415
            from execution.indicators.regime import classify_regime  # noqa: PLC0415
            from execution.indicators.sector_strength import (  # noqa: PLC0415
                compute_relative_strength, detect_rotations, rank_sectors,
            )
            from execution.market_data import (  # noqa: PLC0415
                fetch_history_for, fetch_market_history,
            )

            closes = fetch_market_history()  # raises OutlookDataError -> step fails -> alert
            rankings = rank_sectors(compute_relative_strength(closes))
            rotations = detect_rotations(rankings)
            breadth = compute_breadth(closes)
            regime = classify_regime(
                closes[BENCHMARK], closes.get(VIX), breadth["pct_above_200dma"]
            )

            # Phase 3A: extended passes — downstream of the sector pipeline,
            # degrade to None + alert, never block the outlook.
            try:
                closes_extra = fetch_history_for(list(INDUSTRY_ETFS) + list(SIZE_STYLE_ETFS))
                if BENCHMARK in closes:
                    closes_extra[BENCHMARK] = closes[BENCHMARK]
            except Exception:
                logger.exception("Extended-signal fetch failed")
                closes_extra = {}
            extended, ext_failures = compute_extended_signals(closes_extra)
            for subject, detail in ext_failures:
                await send_failure_alert(subject, detail, source="weekly_market_outlook")

            return {
                "rankings": rankings,
                "rotations": rotations,
                "breadth": breadth,
                "regime_mechanical": regime["regime"],
                "regime_inputs": regime["inputs"],
                "industry": extended["industry"],
                "size_style": extended["size_style"],
            }

        indicators = await step.run("compute-indicators", compute_indicators)

        # Step 2: strategist (has its own internal fallback — never raises)
        async def strategist_step() -> Dict[str, Any]:
            from execution.strategist.agent import (  # noqa: PLC0415
                fetch_macro_headlines, run_strategist,
            )
            # Control-group contract: the strategist must never see the
            # Sleeve-A-only extended signals (its override feeds the shared regime).
            payload = {k: v for k, v in indicators.items()
                       if k not in ("industry", "size_style", "themes")}
            payload["macro_headlines"] = fetch_macro_headlines()
            return run_strategist(payload)

        strategist = await step.run("run-strategist", strategist_step)

        # Step 2.5: theme rankings (Phase 3B — Sleeve-A-only; degrades to None)
        # Deliberately runs AFTER the strategist step — structurally impossible
        # for the LLM to see theme data. All imports live inside the try so
        # even an ImportError degrades instead of killing the outlook.
        async def compute_theme_rankings() -> "Optional[Dict[str, Any]]":
            try:
                from api.lib.db import get_db  # noqa: PLC0415
                return await compute_theme_rankings_payload(await get_db())
            except Exception as exc:
                logger.exception("Outlook theme pass failed")
                try:
                    from execution.alerts import send_failure_alert  # noqa: PLC0415
                    await send_failure_alert(
                        "Outlook theme pass failed", f"{type(exc).__name__}: {exc}",
                        source="weekly_market_outlook")
                except Exception:
                    # Journaling is best-effort — never let the alert path
                    # break the degrade-to-None contract.
                    logger.exception("Failed to journal theme-pass alert")
                return None

        themes_result = await step.run("compute-theme-rankings", compute_theme_rankings)

        # Step 3: store
        async def store() -> Dict[str, Any]:
            from api.lib.db import get_db  # noqa: PLC0415
            from execution.outlook_service import (  # noqa: PLC0415
                build_outlook_record, store_outlook,
            )
            record = build_outlook_record(
                run_date, {**indicators, "themes": themes_result}, strategist)
            row = await store_outlook(await get_db(), record)
            logger.info("MarketOutlook stored: %s regime=%s", row.id, record["regime"])
            return {"id": row.id, **{k: v for k, v in record.items() if k != "runDate"},
                    "runDate": run_date.isoformat()}

        stored = await step.run("store-outlook", store)

        # Step 4: email the owner
        async def send_email() -> Dict[str, Any]:
            owner_email = os.getenv("OWNER_EMAIL", "")
            if not owner_email:
                logger.warning("OWNER_EMAIL not set — skipping outlook email")
                return {"status": "skipped"}
            import resend  # noqa: PLC0415 — only needed when email is actually enabled
            record = dict(stored)
            record["runDate"] = datetime.fromisoformat(record["runDate"])
            resend.api_key = os.getenv("RESEND_API_KEY", "")
            resend.Emails.send({
                "from": "DVRG Autopilot <digest@dvrg.co>",
                "to": [owner_email],
                "subject": f"Market Outlook — {record['regime'].replace('_', ' ')} — "
                           f"{record['runDate'].strftime('%b %d, %Y')}",
                "html": build_outlook_email_html(record),
            })
            return {"status": "sent"}

        email_result = await step.run("send-outlook-email", send_email)
        return {"outlook_id": stored["id"], "regime": stored["regime"],
                "email": email_result["status"]}

    return weekly_market_outlook


try:
    weekly_market_outlook = _register_inngest_function()
except Exception:
    weekly_market_outlook = None  # type: ignore[assignment]
