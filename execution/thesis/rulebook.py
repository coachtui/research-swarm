"""The compounding method rulebook (spec §3).

Each quarter the study produces a digest; the revise call judges the CURRENT
rulebook against it and emits per-rule verdicts. This module does the
bookkeeping — version, confirmations, identity, staleness, cap — because
compounding state is too important to let an LLM increment it.

Method rules only. No issuers, cusips, weights, or values ever enter a
rulebook (guard-tested): the rulebook is what the buy-authority prompt reads.
"""
import logging
import re
from typing import Any, Dict, List, Optional

from execution.constants import RULEBOOK_MAX_RULES

logger = logging.getLogger(__name__)

SOURCE = "thirteenf_rulebook"

_SLUG_RE = re.compile(r"[^a-z0-9]+")
_VERDICTS = {"confirmed", "sharpened", "unchanged", "retired"}


def rule_id(text: str) -> str:
    """Stable slug for a rule, assigned ONCE at birth and then immutable — a
    `sharpened` rule keeps its original id so identity survives rewording."""
    return _SLUG_RE.sub("-", str(text).lower()).strip("-")[:60]


def _born(raw: Dict[str, Any], as_of: str) -> Dict[str, Any]:
    text = str(raw.get("rule") or "").strip()
    return {"id": rule_id(text), "rule": text,
            "rationale": str(raw.get("rationale") or "").strip(),
            "evidence_quarters": [as_of], "confirmations": 1,
            "first_seen": as_of, "last_reviewed": as_of, "status": "active"}


def _retire(rule: Dict[str, Any], because: str, as_of: str) -> Dict[str, Any]:
    return {"id": rule["id"], "rule": rule["rule"],
            "retired_because": because, "retired_at": as_of}


def _confirm(rule: Dict[str, Any], as_of: str) -> None:
    rule["confirmations"] = int(rule.get("confirmations") or 0) + 1
    rule["last_reviewed"] = as_of
    quarters = list(rule.get("evidence_quarters") or [])
    if as_of not in quarters:
        quarters.append(as_of)
    rule["evidence_quarters"] = quarters


def merge_rulebook(current: Optional[Dict[str, Any]], revision: Dict[str, Any],
                   as_of: str) -> Dict[str, Any]:
    """Next rulebook version from the current one plus this quarter's verdicts.

    A rule with NO verdict is treated as `unchanged`, never dropped — an LLM
    that forgets to mention a rule must not be able to delete it. `unchanged`
    deliberately does not bump `last_reviewed`, which is what keeps staleness
    visible to the next revise pass.
    """
    prior = current or {}
    rules = [dict(r) for r in (prior.get("rules") or [])]
    retired = [dict(r) for r in (prior.get("retired") or [])]
    by_id = {r["id"]: r for r in rules}

    verdicts = {str(v.get("id")): v
                for v in (revision.get("verdicts") or [])
                if isinstance(v, dict) and v.get("id")}

    kept: List[Dict[str, Any]] = []
    for rule in rules:
        v = verdicts.get(rule["id"]) or {}
        verdict = v.get("verdict") if v.get("verdict") in _VERDICTS else "unchanged"
        if verdict == "retired":
            retired.append(_retire(
                rule, str(v.get("retired_because") or "retired by revise"), as_of))
            continue
        if verdict == "sharpened":
            # A sharpened verdict with no replacement text is just a
            # confirmation — never blank the rule.
            text = str(v.get("rule") or "").strip()
            if text:
                rule["rule"] = text
            rationale = str(v.get("rationale") or "").strip()
            if rationale:
                rule["rationale"] = rationale
        if verdict in ("confirmed", "sharpened"):
            _confirm(rule, as_of)
        kept.append(rule)

    for raw in revision.get("new_rules") or []:
        if not isinstance(raw, dict):
            continue
        born = _born(raw, as_of)
        if not born["rule"] or born["id"] in by_id:
            continue                      # empty text, or already an active rule
        kept.append(born)
        by_id[born["id"]] = born

    # Cap: retire least-confirmed, then stalest, then by id for determinism.
    # Logged, never silently truncated (spec §3).
    if len(kept) > RULEBOOK_MAX_RULES:
        kept.sort(key=lambda r: (int(r.get("confirmations") or 0),
                                 str(r.get("last_reviewed") or ""), r["id"]))
        overflow = len(kept) - RULEBOOK_MAX_RULES
        for rule in kept[:overflow]:
            retired.append(_retire(
                rule, f"cap ({RULEBOOK_MAX_RULES}): displaced by "
                      f"better-evidenced rules", as_of))
        logger.warning("rulebook: cap retired %d rule(s): %s", overflow,
                       [r["id"] for r in kept[:overflow]])
        kept = kept[overflow:]

    return {"version": int(prior.get("version") or 0) + 1, "as_of": as_of,
            "rules": kept, "retired": retired,
            "calibration": revision.get("calibration") or {},
            "summary": str(revision.get("summary") or "").strip()}
