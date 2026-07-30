"""Prompt + strict parser for the quarterly rulebook revision (spec §5).

Posture: loud on top-level drift. A drifted revision must never be able to
blank the accumulated rulebook — RevisionParseError propagates to the cron,
which journals engine_failure, keeps the digest, and leaves the PRIOR rulebook
authoritative (spec §7).
"""
import json
import logging
from typing import Any, Dict, List, Optional

from execution.constants import RULEBOOK_MAX_RULES
from execution.themes.parser import ThemeParseError, _extract_json

logger = logging.getLogger(__name__)

_VERDICTS = {"confirmed", "sharpened", "unchanged", "retired"}


class RevisionParseError(Exception):
    """Revision unusable — no JSON, or the top-level schema drifted."""


def _rulebook_block(current: Optional[Dict[str, Any]]) -> str:
    if not current or not (current.get("rules") or []):
        return ("No rulebook yet — this is the first revision. Every rule you\n"
                "return in `new_rules` starts the book; `verdicts` should be empty.")
    view = {"version": current.get("version"), "as_of": current.get("as_of"),
            "summary": current.get("summary"),
            "calibration": current.get("calibration") or {},
            "rules": [{"id": r.get("id"), "rule": r.get("rule"),
                       "rationale": r.get("rationale"),
                       "confirmations": r.get("confirmations"),
                       "first_seen": r.get("first_seen"),
                       "last_reviewed": r.get("last_reviewed"),
                       "evidence_quarters": r.get("evidence_quarters")}
                      for r in current.get("rules") or []],
            "previously_retired": [r.get("id")
                                   for r in current.get("retired") or []]}
    return json.dumps(view, indent=1)


def build_revise_prompt(current: Optional[Dict[str, Any]],
                        digest: Dict[str, Any], fund_name: str,
                        as_of: str) -> str:
    return f"""You maintain the method rulebook of a long-horizon systematic fund.

The rulebook is how our engine reasons about entries — it is a curriculum of
transferable METHOD learned by studying {fund_name}'s filings quarter after
quarter. It never contains tickers to copy: by filing day those positions are
about seven weeks stale, and we do not copy trades. Your job is to revise the
rulebook in light of one new quarter of evidence, {as_of}.

## The current rulebook
{_rulebook_block(current)}

## This quarter's study digest ({as_of})
{json.dumps(digest, indent=1)}

Rule the quarter on EACH existing rule by id:

- `confirmed` — this quarter's evidence independently supports it again.
- `sharpened` — it holds, but you can state it more precisely. Supply the
  replacement text in `rule`. The id stays the same.
- `unchanged` — this quarter did not test it. Say so rather than inventing
  support; a rule carried on narrative alone is weaker than one a later
  quarter independently confirmed, and `last_reviewed` is how we see that.
- `retired` — contradicted, or revealed as noise specific to one quarter.
  Give `retired_because`.

**Retiring is a first-class outcome. A rulebook that only grows is a rulebook
nobody edited.** Maximum {RULEBOOK_MAX_RULES} active rules; if your additions
would exceed that, retire the weakest explicitly rather than leaving us to
drop them.

Then set `calibration` from the digest's earliness findings: how many quarters
ahead of the mainstream story this fund actually was, and which classes of
indicator gave them the lead. That is the compounding measurement — not how
extended a name was, but how early they were and on what evidence.

Respond with ONLY a JSON object, no other text:
{{
  "verdicts": [{{
    "id": "<existing rule id>",
    "verdict": "confirmed" | "sharpened" | "unchanged" | "retired",
    "why": "<one sentence tied to this quarter's evidence>",
    "rule": "<replacement text — sharpened only>",
    "rationale": "<replacement rationale — sharpened only>",
    "retired_because": "<retired only>"
  }}],
  "new_rules": [{{
    "rule": "<one transferable decision rule>",
    "rationale": "<what in this quarter's record supports it>"
  }}],
  "calibration": {{
    "typical_lead_quarters": 0.0,
    "lead_indicator_classes": ["<indicator class>"],
    "notes": "<how early they were, measured>"
  }},
  "summary": "<3-6 sentences: how this fund reasons, current best synthesis>"
}}"""


def _verdict(raw: Any, skipped: List[str]) -> Optional[Dict[str, Any]]:
    if not isinstance(raw, dict):
        skipped.append("verdict: not an object")
        return None
    rid = str(raw.get("id") or "").strip()
    verdict = raw.get("verdict")
    if not rid:
        skipped.append("verdict: missing id")
        return None
    if verdict not in _VERDICTS:
        skipped.append(f"verdict {rid}: unknown verdict {verdict!r}")
        return None
    out: Dict[str, Any] = {"id": rid, "verdict": verdict,
                           "why": str(raw.get("why") or "").strip()}
    for key in ("rule", "rationale", "retired_because"):
        value = str(raw.get(key) or "").strip()
        if value:
            out[key] = value
    return out


def _new_rule(raw: Any, skipped: List[str]) -> Optional[Dict[str, str]]:
    if not isinstance(raw, dict):
        skipped.append("new_rule: not an object")
        return None
    text = str(raw.get("rule") or "").strip()
    if not text:
        skipped.append("new_rule: empty rule text")
        return None
    return {"rule": text, "rationale": str(raw.get("rationale") or "").strip()}


def parse_revision_response(raw: str) -> Dict[str, Any]:
    try:
        obj = _extract_json(raw)
    except ThemeParseError as exc:
        raise RevisionParseError(str(exc)) from exc
    verdicts_raw, new_raw = obj.get("verdicts"), obj.get("new_rules")
    summary = str(obj.get("summary") or "").strip()
    if not isinstance(verdicts_raw, list) or not isinstance(new_raw, list):
        raise RevisionParseError("schema drifted: verdicts/new_rules not lists")
    if not summary:
        raise RevisionParseError("schema drifted: empty summary")
    skipped: List[str] = []
    verdicts = [v for v in (_verdict(x, skipped) for x in verdicts_raw) if v]
    new_rules = [r for r in (_new_rule(x, skipped) for x in new_raw) if r]
    calibration = obj.get("calibration")
    # An all-unchanged quarter is legitimate: empty verdicts + no new rules is
    # NOT drift. The merge carries the book forward untouched.
    return {"verdicts": verdicts, "new_rules": new_rules,
            "calibration": calibration if isinstance(calibration, dict) else {},
            "summary": summary, "skipped": skipped}
