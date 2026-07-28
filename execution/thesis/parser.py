"""Strict parsing of the weekly thesis memo (spec §3.2, §7).

Posture: LOUDER than the theme parsers. The memo is the only buy authority,
so a response whose top-level shape drifted is a no-op week, not a quiet
zero — MemoParseError propagates to the cron which journals engine_failure
and places nothing. Individual malformed items skip with reasons.
"""
import logging
from typing import Any, Dict, List, Optional

from execution.constants import THESIS_ROLES, THESIS_STAGES
from execution.themes.parser import ThemeParseError, _extract_json, _TICKER_RE

logger = logging.getLogger(__name__)

_ACTIONS = {"enter", "add", "review", "hold"}
_ENTRY_ACTIONS = {"enter", "add"}
_STYLES = {"at_market", "on_pullback"}
_VERDICTS = {"confirming", "unclear", "disconfirmed", "graduate_to_theme"}


class MemoParseError(Exception):
    """Memo unusable — no JSON, or the top-level schema drifted."""


def _action(raw: Any, slug: str, skipped: List[str]) -> Optional[Dict[str, Any]]:
    if not isinstance(raw, dict):
        skipped.append(f"{slug}: action is not an object")
        return None
    action = raw.get("action")
    ticker = str(raw.get("ticker") or "").strip().upper()
    if action not in _ACTIONS:
        skipped.append(f"{slug}: unknown action {action!r}")
        return None
    if not _TICKER_RE.match(ticker):
        skipped.append(f"{slug}: bad ticker {raw.get('ticker')!r}")
        return None
    out = {"action": action, "ticker": ticker}
    if action in _ENTRY_ACTIONS:
        role, style = raw.get("role"), raw.get("entry_style")
        why_now = str(raw.get("why_now") or "").strip()
        why_expr = str(raw.get("why_this_expression") or "").strip()
        try:
            conviction = float(raw.get("conviction"))
        except (TypeError, ValueError):
            conviction = -1.0
        if role not in THESIS_ROLES:
            skipped.append(f"{slug}/{ticker}: bad role {role!r}")
            return None
        if style not in _STYLES:
            skipped.append(f"{slug}/{ticker}: bad entry_style {style!r}")
            return None
        if not why_now or not why_expr:
            skipped.append(f"{slug}/{ticker}: missing why_now/why_this_expression")
            return None
        if not 0.0 <= conviction <= 1.0:
            skipped.append(f"{slug}/{ticker}: conviction out of range")
            return None
        out.update({"role": role, "entry_style": style, "why_now": why_now,
                    "why_this_expression": why_expr, "conviction": conviction})
    return out


def _passed_on(raw: Any, slug: str, skipped: List[str]) -> List[Dict[str, str]]:
    """Candidates the memo saw and DECLINED — never an action, purely the record.

    Advisory: a malformed block degrades to empty and never sinks the thesis
    it hangs off. Both fields are required, because a ticker with no reason is
    exactly the silence this field exists to remove.
    """
    if not isinstance(raw, list):
        if raw is not None:
            skipped.append(f"{slug}: passed_on is not a list")
        return []
    out: List[Dict[str, str]] = []
    for p in raw:
        if not isinstance(p, dict):
            skipped.append(f"{slug}: passed_on entry not an object")
            continue
        ticker = str(p.get("ticker") or "").strip().upper()
        reason = str(p.get("reason") or "").strip()
        if not ticker:
            skipped.append(f"{slug}: passed_on entry without ticker")
            continue
        if not reason:
            skipped.append(f"{slug}: passed_on {ticker} without a reason")
            continue
        out.append({"ticker": ticker, "reason": reason})
    return out


def parse_memo_response(raw: str) -> Dict[str, Any]:
    try:
        obj = _extract_json(raw)
    except ThemeParseError as exc:
        raise MemoParseError(str(exc)) from exc
    theses_raw = obj.get("theses")
    if not isinstance(theses_raw, list):
        raise MemoParseError(
            f'"theses" missing or not a list — top-level keys {sorted(map(str, obj))}')

    skipped: List[str] = []
    theses: List[Dict[str, Any]] = []
    for t in theses_raw:
        if not isinstance(t, dict) or not t.get("slug"):
            skipped.append("thesis item without slug")
            continue
        slug = str(t["slug"]).strip()
        stage = t.get("stage")
        if stage not in THESIS_STAGES:
            skipped.append(f"{slug}: bad stage {stage!r}")
            continue
        actions = [a for a_raw in (t.get("actions") or [])
                   if (a := _action(a_raw, slug, skipped)) is not None]
        theses.append({
            "slug": slug, "stage": stage,
            "stage_rationale": str(t.get("stage_rationale") or ""),
            "evidence_this_week": [str(e) for e in (t.get("evidence_this_week") or [])],
            "actions": actions,
            "passed_on": _passed_on(t.get("passed_on"), slug, skipped),
        })

    updates: List[Dict[str, Any]] = []
    for h in (obj.get("hypothesis_updates") or []):
        if not isinstance(h, dict) or not h.get("hypothesis"):
            skipped.append("hypothesis update without hypothesis text")
            continue
        if h.get("verdict") not in _VERDICTS:
            skipped.append(f"hypothesis {str(h['hypothesis'])[:40]!r}: bad verdict")
            continue
        updates.append({
            "hypothesis": str(h["hypothesis"]).strip(),
            "indicator_observations": [str(o) for o in (h.get("indicator_observations") or [])],
            "verdict": h["verdict"],
        })

    return {"theses": theses, "hypothesis_updates": updates,
            "market_view": str(obj.get("market_view") or ""), "skipped": skipped}
