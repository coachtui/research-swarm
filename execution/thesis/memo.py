"""Weekly thesis memo: gather → reason (paid) → persist (spec §3).

reason_memo is the PAID call — the cron runs it in its own memoized step.
gather/persist are cheap and deterministic given their inputs.
"""
import logging
import re
from typing import Any, Dict, List, Optional

from execution.constants import (
    THESIS_MEMO_MAX_TOKENS, THESIS_MEMO_MODEL, THESIS_WEB_SEARCH_MAX_USES,
)
from execution.reporting import write_report
from execution.themes.discovery import _call_llm, _current_theme_state
from execution.thesis.ledger import append_evidence, load_ledger_context
from execution.thesis.prompts import build_weekly_memo_prompt

logger = logging.getLogger(__name__)

SOURCE = "thesis_memo_weekly"
_KEY_RE = re.compile(r"[^a-z0-9]+")


def hypothesis_key(text: str) -> str:
    """Stable slug key for a hypothesis sentence (first 60 chars)."""
    return _KEY_RE.sub("-", text.lower()).strip("-")[:60]


def _rankings(blob: Any) -> Optional[List[Any]]:
    """Rankings blobs come in BOTH shapes: the raw MarketOutlook column
    ({"rankings": [...], "rotations": [...]}) and the already-unwrapped LIST
    the funnel cron's _outlook_context hands downstream consumers. Accept
    either — calling .get() on the unwrapped list raised AttributeError, which
    the cron caught as a failed gather, i.e. a permanent no-op week."""
    if isinstance(blob, dict):
        return blob.get("rankings")
    return blob or None


async def gather_memo_packet(
    db, outlook: Dict[str, Any], book: List[Dict[str, Any]],
    candidates: Dict[str, Dict[str, Any]],
) -> Dict[str, Any]:
    themes = await _current_theme_state(db, include_retired=False)
    active = [{**t, "constituents": [c for c in t["constituents"]
                                     if c["status"] == "active"]}
              for t in themes]
    ledger = await load_ledger_context(db, [t["slug"] for t in active])
    for t in active:
        t["ledger"] = ledger["by_theme"].get(t["slug"], [])
        t.setdefault("stage", None)  # _current_theme_state projects it
    crowd = {
        "theme_rankings": _rankings(outlook.get("themeRankings")),
        "sector_rankings": _rankings(outlook.get("sectorRankings")),
        "industry_rankings": _rankings(outlook.get("industryRankings")),
    }
    return {"theses": active, "hypotheses": ledger["hypotheses"],
            "study_digest": ledger["study_digest"], "book": book,
            "candidates": candidates, "crowdedness": crowd,
            "regime": outlook.get("regime")}


def reason_memo(packet: Dict[str, Any], llm_call=None) -> str:
    call = llm_call or _call_llm
    return call(THESIS_MEMO_MODEL, build_weekly_memo_prompt(packet),
                use_web_search=True, max_uses=THESIS_WEB_SEARCH_MAX_USES,
                max_tokens=THESIS_MEMO_MAX_TOKENS)


async def persist_memo(db, week: str, raw: str, memo: Dict[str, Any]) -> None:
    """Journal the memo verbatim + append ledger rows. write_report and
    append_evidence both swallow their own failures."""
    await write_report(
        "thesis_memo", "info", SOURCE,
        f"weekly memo: {len(memo['theses'])} theses, "
        f"{sum(len(t['actions']) for t in memo['theses'])} actions, "
        f"{len(memo['skipped'])} skipped",
        {"raw": raw, "market_view": memo["market_view"],
         "skipped": memo["skipped"]}, db=db)
    for t in memo["theses"]:
        await append_evidence(
            db, "weekly_memo",
            {"evidence_this_week": t["evidence_this_week"],
             "stage_rationale": t["stage_rationale"], "actions": t["actions"],
             # Candidates seen and declined. Purely a record — nothing reads it
             # back into a decision; it exists so "made the screen, never
             # bought" stops being the one case with no recorded reason.
             "passed_on": t.get("passed_on") or []},
            theme_slug=t["slug"], week=week, stage=t["stage"])
    for h in memo["hypothesis_updates"]:
        await append_evidence(
            db, "hypothesis", h, hypothesis_key=hypothesis_key(h["hypothesis"]),
            week=week)
