"""Prompt + strict parser for the quarterly 13F study (spec §5).

The study's deliverable is METHOD RULES — how the fund reasons — never a
buy list. Parsing is loud (thesis-parser posture): a drifted top-level
shape raises StudyParseError, the cron journals engine_failure, and no
digest lands. Individual malformed items skip with reasons.
"""
import json
import logging
from typing import Any, Dict, List, Optional

from execution.themes.parser import ThemeParseError, _extract_json

logger = logging.getLogger(__name__)


class StudyParseError(Exception):
    """Study response unusable — no JSON or the top-level schema drifted."""


def _moves_block(moves: List[Dict[str, Any]]) -> str:
    return json.dumps(moves, indent=1)


def build_study_prompt(packet: Dict[str, Any]) -> str:
    return f"""You are the research historian of a long-horizon systematic fund.
Below is the quarter-over-quarter diff of {packet["fund"]}'s 13F filings —
as-of {packet["as_of"]} (filed {packet["filed"]}), diffed against
{packet["prior"]}. Filing history available: {packet["quarters_available"]}.

THIS IS A CURRICULUM, NOT A SIGNAL. By filing day these positions are
roughly seven weeks stale — acting on them is already late, and we never copy
trades. The filing is an answer key for a test the market already
gave: your job is to reconstruct the REASONING that produced each move,
then compress it into method rules we can apply to live decisions.

Each material move below carries its reconstructed window: the quarter the
position first appears, per-quarter share counts, and the implied
quarter-end price (value/shares — a quarter-end mark, bracketing where
they acted, not their exact fill). A put and a long in the same issuer are
separate rows — read paired moves in the same cusip together (a put
appearing while the long exits is one decision, not two). Fund book value:
{packet["book_value"]:,.0f} USD.

## Material moves (new / exited / resized ≥20% / top holdings)
{_moves_block(packet["material_moves"])}

For EACH move, use web search to answer: what was publicly knowable DURING
that window — before the hype — that justified it? Search the window's
period specifically (contracts signed, lead times, capex announcements,
pricing data, hiring, permits), not today's coverage of the name. Then
generalize: what repeatable METHOD does the set of moves reveal? Examples
of the register we want: "they treated compute as priced when hyperscaler
capex became a consensus headline"; "when grid interconnect lead times
blow out, they buy the deliver-now power name before the first big
contract prints."

Respond with ONLY a JSON object, no other text:
{{
  "method_rules": [{{
    "rule": "<one transferable decision rule, stated so we can apply it>",
    "evidence": "<what in the filings + that-period record supports it>",
    "moves_cited": ["<issuer + direction>"]
  }}],
  "moves": [{{
    "issuer": "<issuer name>",
    "direction": "<new long | new put | exited | increased | decreased>",
    "window": "<when they likely acted>",
    "what_was_knowable": "<the public record during the window, with sources>"
  }}],
  "summary": "<3-5 sentences: the quarter's thesis in their voice>"
}}"""


def _rule(raw: Any, skipped: List[str]) -> Optional[Dict[str, Any]]:
    if not isinstance(raw, dict):
        skipped.append("method_rule: not an object")
        return None
    rule = str(raw.get("rule") or "").strip()
    if not rule:
        skipped.append("method_rule: empty rule text")
        return None
    cited = raw.get("moves_cited")
    return {"rule": rule, "evidence": str(raw.get("evidence") or "").strip(),
            "moves_cited": [str(m) for m in cited] if isinstance(cited, list) else []}


def _move(raw: Any, skipped: List[str]) -> Optional[Dict[str, str]]:
    if not isinstance(raw, dict):
        skipped.append("move: not an object")
        return None
    issuer = str(raw.get("issuer") or "").strip()
    if not issuer:
        skipped.append("move: missing issuer")
        return None
    return {"issuer": issuer,
            "direction": str(raw.get("direction") or "").strip(),
            "window": str(raw.get("window") or "").strip(),
            "what_was_knowable": str(raw.get("what_was_knowable") or "").strip()}


def parse_study_response(raw: str) -> Dict[str, Any]:
    try:
        obj = _extract_json(raw)
    except ThemeParseError as exc:
        raise StudyParseError(str(exc)) from exc
    rules_raw, moves_raw = obj.get("method_rules"), obj.get("moves")
    summary = str(obj.get("summary") or "").strip()
    if not isinstance(rules_raw, list) or not isinstance(moves_raw, list):
        raise StudyParseError("schema drifted: method_rules/moves not lists")
    if not summary:
        raise StudyParseError("schema drifted: empty summary")
    skipped: List[str] = []
    rules = [r for r in (_rule(x, skipped) for x in rules_raw) if r]
    moves = [m for m in (_move(x, skipped) for x in moves_raw) if m]
    if not rules:
        raise StudyParseError("no usable method rules — digest refused")
    return {"method_rules": rules, "moves": moves, "summary": summary,
            "skipped": skipped}
