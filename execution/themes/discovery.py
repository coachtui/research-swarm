"""Monthly theme-discovery pass: gather -> reason (paid) -> validate -> apply.

Each function maps to ONE Inngest step (Task 10) so the paid LLM call is
memoized separately from apply — a retry after a failed apply must never
re-bill the reasoning call (tiered-batch lesson).
"""
import logging
import os
from typing import Any, Dict

from execution.constants import (
    THEME_REASONING_MODEL,
    THEME_WEB_SEARCH_MAX_USES,
)
from execution.reporting import write_report
from execution.research_feed import get_research_context
from execution.themes.lifecycle import apply_actions, plan_monthly_actions
from execution.themes.parser import parse_monthly_response
from execution.themes.prompts import build_monthly_prompt
from execution.themes.validation import validate_tickers

logger = logging.getLogger(__name__)

SOURCE = "theme_discovery_monthly"


def _anthropic_api_key() -> str:
    try:
        from research_swarm.config import settings  # noqa: PLC0415
        return settings.anthropic_api_key or os.getenv("ANTHROPIC_API_KEY", "")
    except ImportError:
        return os.getenv("ANTHROPIC_API_KEY", "")


def _call_llm(model: str, prompt: str, use_web_search: bool = False, max_uses: int = 8,
              max_tokens: int = 16384) -> str:
    """One native-SDK call. Server-side web_search when requested."""
    import anthropic  # noqa: PLC0415

    client = anthropic.Anthropic(api_key=_anthropic_api_key())
    kwargs: Dict[str, Any] = {
        "model": model,
        "max_tokens": max_tokens,
        "messages": [{"role": "user", "content": prompt}],
    }
    if use_web_search:
        kwargs["tools"] = [{"type": "web_search_20250305", "name": "web_search",
                            "max_uses": max_uses}]
    # Streamed accumulation: the SDK refuses non-streaming calls whose
    # max_tokens implies a >10-minute response (the 32k memo budget does).
    with client.messages.stream(**kwargs) as stream:
        response = stream.get_final_message()
    if getattr(response, "stop_reason", None) == "max_tokens":
        raise RuntimeError(
            "LLM response truncated at max_tokens — increase THEME reasoning budget")
    return "".join(
        block.text for block in response.content
        if getattr(block, "type", "") == "text"
    )


async def _current_theme_state(db, include_retired: bool = True) -> list:
    where = None if include_retired else {"status": "active"}
    rows = await db.themebasket.find_many(
        where=where, include={"constituents": True}, order={"createdAt": "asc"})
    return [{
        "slug": r.slug, "name": r.name, "status": r.status, "origin": r.origin,
        "thesis": r.thesis, "confidence": r.confidence,
        # Thesis stage (spec §3): the weekly memo must see the CURRENT stage to
        # move it. Other callers ignore the extra key.
        "stage": getattr(r, "stage", None),
        "constituents": [
            {"ticker": c.ticker, "exposure": c.exposure,
             "confidence": c.confidence, "status": c.status}
            for c in (r.constituents or [])
        ],
    } for r in rows]


async def gather_monthly_context(db) -> Dict[str, Any]:
    themes = await _current_theme_state(db)
    active = [{**t, "constituents": [c for c in t["constituents"] if c["status"] == "active"]}
              for t in themes if t["status"] == "active"]
    retired = [{"slug": t["slug"], "name": t["name"]} for t in themes if t["status"] == "retired"]

    latest_rankings = None
    try:
        from execution.outlook_service import get_latest_outlook  # noqa: PLC0415
        row = await get_latest_outlook(db)
        blob = getattr(row, "themeRankings", None) if row else None
        latest_rankings = blob.get("rankings") if isinstance(blob, dict) else None
    except Exception:
        logger.exception("gather_monthly_context: rankings unavailable")

    research = await get_research_context(db)
    return {"active_themes": active, "retired_themes": retired,
            "latest_rankings": latest_rankings, "research": research}


def reason_monthly(context: Dict[str, Any], llm_call=None) -> str:
    call = llm_call or _call_llm
    prompt = build_monthly_prompt(context)
    return call(THEME_REASONING_MODEL, prompt, use_web_search=True,
                max_uses=THEME_WEB_SEARCH_MAX_USES)


def parse_and_validate_monthly(raw: str, tradable=None) -> Dict[str, Any]:
    parsed = parse_monthly_response(raw)
    tickers = [c["ticker"] for p in parsed["themes"] for c in p["constituents"]]
    validation = validate_tickers(tickers, tradable=tradable) if tickers else {}
    return {"proposals": parsed["themes"], "validation": validation,
            "skipped": parsed["skipped"],
            "next_constraints": parsed["next_constraints"]}


async def _journal_next_constraints(db, hypotheses: list) -> None:
    """Journal each forward hypothesis as an informational theme_proposal
    report. Pure logging — never touches theme lifecycle/validation, and
    write_report itself never raises (it swallows and logs failures)."""
    for h in hypotheses:
        await write_report(
            "theme_proposal", "info", SOURCE,
            f"next-constraint hypothesis: {h['hypothesis'][:80]}", h, db=db)


async def apply_monthly(db, bundle: Dict[str, Any]) -> Dict[str, Any]:
    current = await _current_theme_state(db)
    plan = plan_monthly_actions(current, bundle["proposals"], bundle["validation"])
    summary = await apply_actions(db, plan["actions"], SOURCE)

    problems = bundle["skipped"] + plan["rejected"]
    rejected_tickers = sorted(t for t, v in bundle["validation"].items() if v is None)
    if problems or rejected_tickers:
        await write_report(
            "validation_failure", "warning", SOURCE,
            f"monthly pass: {len(problems)} skipped/rejected, "
            f"{len(rejected_tickers)} tickers failed validation",
            {"skipped": problems, "failed_tickers": rejected_tickers}, db=db)

    await _journal_next_constraints(db, bundle.get("next_constraints") or [])
    return {**summary, "rejected": len(problems), "failed_tickers": len(rejected_tickers)}
