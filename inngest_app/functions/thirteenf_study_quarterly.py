"""Quarterly 13F study pass (spec §5) — the curriculum cron.

Cron: 21st of Feb/May/Aug/Nov 12:00 UTC — one week after the 45-day 13F
deadline (Feb 14 / May 15 / Aug 14 / Nov 14), clear of the Monday funnel
and the 1st-of-month discovery pass.

Per trusted fund: fetch+study (PAID, memoized together — a transient EDGAR
blip on a post-pay replay must never discard a paid study) → parse (pure,
re-derived identically on every replay) → persist (own memoized step, so a
persist retry can never re-bill).

Never raises: a fund's failure journals engine_failure and the pass moves
to the next fund. FOUNDING PREMISE: this is a curriculum, never
copy-trading — tickers in filings get ZERO order authority, and this
module never imports the broker, sizing, or the planner (guard-tested in
tests/test_thesis_study_guards.py).
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from execution.reporting import write_report
from execution.thesis.ledger import load_rulebook
from execution.thesis.rulebook import (
    merge_rulebook, persist_rulebook, reason_revision,
)
from execution.thesis.rulebook_prompts import (
    RevisionParseError, parse_revision_response,
)
from execution.thesis.study import build_study_packet, persist_digest, reason_study
from execution.thesis.study_edgar import fetch_13f_history
from execution.thesis.study_prompts import StudyParseError, parse_study_response

logger = logging.getLogger(__name__)

SOURCE = "thirteenf_study_quarterly"


async def _run_step(step, step_id: str, fn):
    """Run fn as a memoized Inngest step, or inline when step is None (tests /
    non-Inngest callers). Only for closures that DON'T themselves call
    step.run — nested steps are a non-retriable SDK error."""
    if step is None:
        return await fn()
    return await step.run(step_id, fn)


async def _study_pipeline(db, funds: List[Dict[str, Any]], week: str,
                          step=None) -> Dict[str, Any]:
    """One study per trusted fund. NEVER raises."""
    import asyncio  # noqa: PLC0415

    summary: Dict[str, Any] = {"funds": [], "failures": [], "retired": []}

    # Retirement gate (SALP forced liquidation, 2026-07-30): a fund past its
    # retire_after date is skipped MECHANICALLY — a margin-driven unwind is
    # not method, and the post-liquidation filing must never be read as a
    # curriculum quarter, even if nobody edits constants before November.
    # Journaled as a deliberate skip, not engine_failure, so an empty run
    # reads as "retired", not as something to debug.
    active = []
    for fund in funds:
        retire_after = fund.get("retire_after")
        if retire_after and week >= retire_after:
            summary["retired"].append(fund["name"])
        else:
            active.append(fund)
    if summary["retired"]:
        await write_report(
            "study_digest", "info", SOURCE,
            f"13F study: retired fund(s) skipped this quarter: "
            f"{', '.join(summary['retired'])}",
            {"retired": summary["retired"], "week": week}, db=db)

    for fund in active:
        name, ciks = fund["name"], fund["ciks"]
        slug = ciks[0]
        try:
            async def _fetch_and_reason() -> Dict[str, Any]:
                # EDGAR fetch lives INSIDE the paid step (sleeve_a_funnel
                # lesson) — this closure calls no step.run of its own.
                history = await asyncio.to_thread(fetch_13f_history, ciks)
                packet = build_study_packet(name, history)
                if packet is None:
                    return {"packet": None, "raw": None}
                raw = await asyncio.to_thread(reason_study, packet)
                return {"packet": packet, "raw": raw}

            bundle = await _run_step(step, f"study-{slug}", _fetch_and_reason)
            if not bundle["raw"]:
                await write_report(
                    "engine_failure", "warning", SOURCE,
                    f"13F study: {name} skipped — fewer than two usable filings",
                    {"fund": name, "ciks": ciks}, db=db)
                summary["failures"].append(name)
                continue
            digest = parse_study_response(bundle["raw"])   # pure — same on replay

            async def _persist() -> bool:
                await persist_digest(db, week, name, digest, bundle["raw"],
                                     bundle["packet"])
                return True

            await _run_step(step, f"study-persist-{slug}", _persist)

            # ── revise the rulebook (PAID, own memoized step) ───────────────
            # A failure here must NOT cost us the accumulated rulebook: the
            # digest is already persisted, the prior version stays
            # authoritative, and we journal loudly (spec §7).
            rulebook_version = None
            try:
                current = await load_rulebook(db)

                async def _revise() -> str:
                    return await asyncio.to_thread(
                        reason_revision, current, digest, name,
                        bundle["packet"]["as_of"])

                raw_revision = await _run_step(step, f"revise-{slug}", _revise)
                revision = parse_revision_response(raw_revision)   # pure
                merged = merge_rulebook(current, revision,
                                        bundle["packet"]["as_of"])

                async def _persist_book() -> bool:
                    await persist_rulebook(db, week, name, merged, raw_revision)
                    return True

                await _run_step(step, f"revise-persist-{slug}", _persist_book)
                rulebook_version = merged["version"]
            except RevisionParseError as exc:
                await write_report(
                    "engine_failure", "critical", SOURCE,
                    f"13F rulebook: {name} revision unusable — prior rulebook "
                    f"stands, digest kept",
                    {"fund": name, "error": str(exc)}, db=db)
            except Exception as exc:  # noqa: BLE001 — never raises
                logger.exception("13F rulebook: %s revise failed", name)
                await write_report(
                    "engine_failure", "critical", SOURCE,
                    f"13F rulebook: {name} revise failed — prior rulebook "
                    f"stands — {exc}",
                    {"fund": name, "error": str(exc)}, db=db)

            summary["funds"].append({"fund": name,
                                     "rules": len(digest["method_rules"]),
                                     "rulebook_version": rulebook_version})
        except StudyParseError as exc:
            await write_report(
                "engine_failure", "critical", SOURCE,
                f"13F study: {name} digest unusable — no digest this quarter",
                {"fund": name, "error": str(exc)}, db=db)
            summary["failures"].append(name)
        except Exception as exc:  # noqa: BLE001 — cron never raises (spec §7)
            logger.exception("13F study: %s failed", name)
            await write_report(
                "engine_failure", "critical", SOURCE,
                f"13F study: {name} failed — {exc}",
                {"fund": name, "error": str(exc)}, db=db)
            summary["failures"].append(name)
    return summary


# ── Inngest function (guarded registration, execution_daily.py pattern) ────

def _register_inngest_function():
    import inngest as inngest_sdk  # noqa: PLC0415

    from inngest_app.client import inngest_client  # noqa: PLC0415

    async def _on_failure(ctx: "inngest_sdk.Context") -> None:
        from execution.alerts import send_failure_alert  # noqa: PLC0415

        await send_failure_alert(
            "13F study quarterly failed",
            f"thirteenf-study-quarterly failed after retries: {ctx.event.data}",
            source=SOURCE,
        )

    @inngest_client.create_function(
        fn_id="thirteenf-study-quarterly",
        # 21st of Feb/May/Aug/Nov: one week past the 45-day 13F deadline.
        trigger=inngest_sdk.TriggerCron(cron="0 12 21 2,5,8,11 *"),
        name="13F Study (quarterly curriculum pass)",
        retries=1,
        on_failure=_on_failure,
    )
    async def thirteenf_study_quarterly(ctx: "inngest_sdk.Context") -> Dict[str, Any]:
        from datetime import datetime, timezone  # noqa: PLC0415

        from api.lib.db import get_db  # noqa: PLC0415
        from execution.constants import TRUSTED_FUNDS_13F  # noqa: PLC0415

        db = await get_db()
        # Label only (ledger `week` column); a replay crossing midnight can
        # shift it by a day — cosmetic, the persist step is already memoized.
        week = datetime.now(timezone.utc).date().isoformat()
        summary = await _study_pipeline(db, TRUSTED_FUNDS_13F, week, step=ctx.step)
        logger.info("13F study quarterly: %s", summary)
        return summary

    return thirteenf_study_quarterly


try:
    thirteenf_study_quarterly = _register_inngest_function()
except Exception:
    thirteenf_study_quarterly = None  # type: ignore[assignment]
