"""Weekly constituent-delta pass — cheap model, no web search, adds/drops only."""
import logging
from typing import Any, Dict

from execution.constants import THEME_DELTA_MODEL, THEME_DELTA_WEB_SEARCH_MAX_USES
from execution.reporting import write_report
from execution.themes.discovery import _call_llm, _current_theme_state
from execution.themes.lifecycle import apply_actions, plan_delta_actions
from execution.themes.parser import parse_delta_response
from execution.themes.prompts import build_delta_prompt
from execution.themes.validation import validate_tickers

logger = logging.getLogger(__name__)

SOURCE = "theme_delta_weekly"


async def gather_delta_context(db) -> Dict[str, Any]:
    themes = await _current_theme_state(db, include_retired=False)
    active = [{**t, "constituents": [c for c in t["constituents"] if c["status"] == "active"]}
              for t in themes]
    return {"active_themes": active}


def reason_delta(context: Dict[str, Any], llm_call=None) -> str:
    """Web search is ON despite the cheap model: offline recall proposes symbols
    that stopped trading years ago (JDSU split in 2015, PSTH liquidated in 2022).
    max_uses is held below the monthly pass's — this is a verification budget,
    not a research budget."""
    call = llm_call or _call_llm
    return call(THEME_DELTA_MODEL, build_delta_prompt(context), use_web_search=True,
                max_uses=THEME_DELTA_WEB_SEARCH_MAX_USES)


def parse_and_validate_delta(raw: str, tradable=None) -> Dict[str, Any]:
    parsed = parse_delta_response(raw)
    tickers = [c["ticker"] for t in parsed["themes"] for c in t.get("add", [])]
    validation = validate_tickers(tickers, tradable=tradable) if tickers else {}
    return {"deltas": parsed["themes"], "validation": validation,
            "skipped": parsed["skipped"]}


async def apply_delta(db, bundle: Dict[str, Any]) -> Dict[str, Any]:
    current = await _current_theme_state(db, include_retired=False)
    deltas = bundle["deltas"]
    plan = plan_delta_actions(current, deltas, bundle["validation"])
    summary = await apply_actions(db, plan["actions"], SOURCE)
    problems = bundle["skipped"] + plan["rejected"]
    if problems:
        await write_report("validation_failure", "warning", SOURCE,
                           f"delta pass: {len(problems)} skipped/rejected",
                           {"skipped": problems}, db=db)

    diagnostics = {
        "themes_seen": len(current),
        "deltas_returned": len(deltas),
        "proposed_adds": sum(len(d.get("add", [])) for d in deltas),
        "proposed_removes": sum(len(d.get("remove", [])) for d in deltas),
    }
    result = {**summary, "rejected": len(problems), **diagnostics}
    await _journal_pass_summary(db, current, diagnostics, result)
    return result


async def _journal_pass_summary(db, current, diagnostics, result) -> None:
    """Journal one row per run, including — especially — a clean no-op.

    Every other write in this pass is per-action, so a week where the model
    proposes nothing leaves zero rows and the journal cannot distinguish it
    from a cron that never fired. Recording what was reasoned over alongside
    what came back also separates "model said no changes" from "model output
    never reached the planner"."""
    changed = result["applied"] or result["rejected"]
    title = (f"delta pass: {result['applied']} applied, {result['rejected']} rejected"
             if changed else "delta pass: no changes proposed")
    await write_report(
        "theme_pass_summary", "info", SOURCE, title,
        {"themes_reasoned_over": [t["slug"] for t in current], **diagnostics,
         "applied": result["applied"], "rejected": result["rejected"]},
        db=db)
