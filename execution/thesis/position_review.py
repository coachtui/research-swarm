"""Reviewing a winner whose thesis has reached crowded.

The stage ladder exists to catch positions BEFORE the crowd. A position
arriving at crowded is the thesis WORKING — so this asks whether there is still
room, and trims here are small and incremental rather than an exit.

Four questions, and they are the owner's, not a formula's:

  * does this still have room to run?
  * what has it done in the past under similar circumstances?
  * what are the consensus price targets, and what is ours?
  * what was the plan when we entered?

The last one is why position plans had to land first. Without the entry plan
the review re-decides from scratch every week, which is how you talk yourself
out of a winner. Reconciling against what we said at entry is the difference
between a considered change of mind and drift.

Failure posture is inverted from the entry disqualifier. There, an unusable
answer lets the entry through, because the memo is the buy authority. Here an
unusable answer changes NOTHING — the safe default for a position that is
working is to leave it alone.
"""
import json
import logging
import re
from typing import Any, Dict, Optional

from execution.constants import (
    DISQUALIFIER_MODEL, THESIS_WEB_SEARCH_MAX_USES,
)

logger = logging.getLogger(__name__)

REVIEW_STAGES = ("crowded", "priced")
# Trims into crowded are incremental. A review that wants most of the position
# gone is making an EXIT decision wearing a trim's clothes, and an exit belongs
# to the memo with a written thesis argument, not to a per-position review.
MAX_CROWDED_TRIM = 0.33
REVIEW_SEARCH_MAX_USES = 4
_POSTURES = ("let_run", "trim_into_strength", "scale_out", "close")
_NEEDS_FRACTION = ("trim_into_strength", "scale_out")

_NOOP = {"posture": "let_run", "fraction": None, "why": "", "reconsider_if": "",
         "room_to_run": "", "checked": False}


def should_review(position: Dict[str, Any], stage: Optional[str]) -> bool:
    """Only a WINNER whose thesis has arrived. A loser in crowded is a thesis
    question for the memo, not a profit-taking one."""
    if stage not in REVIEW_STAGES:
        return False
    try:
        return float(position.get("unrealized_plpc") or 0.0) > 0.0
    except (TypeError, ValueError):
        return False


def build_review_prompt(position: Dict[str, Any], plan: Dict[str, Any],
                        stage: Optional[str]) -> str:
    entry = (plan or {}).get("exit_plan") or {}
    ladder = ", ".join(
        f"${r['price']:g} ({r['size_pct']:g}%)" for r in (plan or {}).get("ladder") or []
    ) or "not recorded"
    return f"""A position you own has reached the {stage} stage. That is the thesis
WORKING — we buy before the crowd, and the crowd has arrived. The question is
not whether to keep owning it; it is whether there is still room.

## The position
- {position.get('symbol')}: {position.get('qty')} shares at an average of
  ${position.get('avg_price')}, now ${position.get('current_price')}
  ({float(position.get('unrealized_plpc') or 0) * 100:+.1f}%)
- Distance above the 200-week MA: {position.get('dist_200wma')}
  (1.0 means +100%)

## What we said entering the position
- Ladder: {ladder}
- Full size target: {(plan or {}).get('target_weight')} of sleeve equity
- What would break the thesis: {(plan or {}).get('thesis_break')}
- Exit posture we chose then: {entry.get('posture')} — {entry.get('why')}
- We said we would reconsider if: {entry.get('reconsider_if')}

## Answer these, in order, searching where you need current information
1. Does this still have room to run? Is the constraint we bought still
   binding, or has it resolved?
2. What has this name done in the PAST under similar circumstances — after a
   move of this size, at this distance from trend, at this point in a cycle?
3. What are the consensus price targets now, and what is OUR price target?
   The gap between them is what we were paid for. Has it closed?
4. What was our plan entering, and does today's evidence actually change it?
   A changed mind needs a reason. Drift does not count.

## Rules
- Trims here are SMALL and incremental, at most {MAX_CROWDED_TRIM:.0%} of the
  position. Letting a winner run is a legitimate and common answer.
- "let_run" must be ARGUED, not defaulted to. So must a trim.
- Reaching crowded is not a sell signal by itself. Consensus catching up to a
  thesis that keeps compounding is different from a thesis that is finished.
- If you trim, say what would bring you back.

Respond with ONLY a JSON object, no other text:
{{"posture": "let_run" | "trim_into_strength" | "scale_out" | "close",
  "fraction": <required for trim_into_strength / scale_out>,
  "room_to_run": "<one sentence>",
  "why": "<why THIS posture, citing what you found>",
  "reconsider_if": "<what would change it — after a trim, what brings you back>"}}"""


def _extract(raw: str) -> Optional[Dict[str, Any]]:
    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", raw or "", re.DOTALL)
    candidate = fenced.group(1) if fenced else None
    if candidate is None:
        start, end = (raw or "").find("{"), (raw or "").rfind("}")
        if start == -1 or end <= start:
            return None
        candidate = raw[start:end + 1]
    try:
        obj = json.loads(candidate)
    except json.JSONDecodeError:
        return None
    return obj if isinstance(obj, dict) else None


async def review_position(
    position: Dict[str, Any], plan: Dict[str, Any], stage: Optional[str],
    llm_call=None, timeout_s: float = 120.0,
) -> Dict[str, Any]:
    """Ask the four questions. Never raises; an unusable answer changes nothing."""
    import asyncio  # noqa: PLC0415

    from execution.themes.discovery import _call_llm  # noqa: PLC0415

    call = llm_call or _call_llm
    prompt = build_review_prompt(position, plan, stage)

    def _run() -> str:
        return call(DISQUALIFIER_MODEL, prompt, use_web_search=True,
                    max_uses=REVIEW_SEARCH_MAX_USES)

    try:
        raw = await asyncio.wait_for(asyncio.to_thread(_run), timeout=timeout_s)
    except Exception:  # noqa: BLE001
        logger.exception("position review failed for %s", position.get("symbol"))
        return dict(_NOOP)

    obj = _extract(raw)
    if obj is None or obj.get("posture") not in _POSTURES:
        logger.warning("position review unusable for %s", position.get("symbol"))
        return dict(_NOOP)

    posture = obj["posture"]
    fraction: Optional[float] = None
    if posture in _NEEDS_FRACTION:
        try:
            fraction = float(obj["fraction"])
        except (KeyError, TypeError, ValueError):
            return dict(_NOOP)          # a trim we cannot size is not a trim
        if fraction <= 0:
            return dict(_NOOP)
        # Clamp, never obey: an oversized "trim" is an exit decision, and exits
        # belong to the memo with a thesis argument behind them.
        fraction = min(fraction, MAX_CROWDED_TRIM)

    return {"posture": posture, "fraction": fraction,
            "why": str(obj.get("why") or "").strip(),
            "reconsider_if": str(obj.get("reconsider_if") or "").strip(),
            "room_to_run": str(obj.get("room_to_run") or "").strip(),
            "checked": True}
