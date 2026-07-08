"""Parse and validate the strategist's JSON response."""
import json
from typing import Any, Dict

from execution.indicators.regime import REGIME_ORDER


class StrategistParseError(Exception):
    """Strategist output could not be parsed into a valid outlook."""


def parse_strategist_response(text: str) -> Dict[str, Any]:
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end <= start:
        raise StrategistParseError("no JSON object found in strategist response")
    try:
        raw = json.loads(text[start : end + 1])
    except json.JSONDecodeError as e:
        raise StrategistParseError(f"invalid JSON: {e}") from e

    regime = raw.get("regime_proposal")
    if regime not in REGIME_ORDER:
        raise StrategistParseError(f"invalid regime_proposal: {regime!r}")

    reasoning = raw.get("reasoning")
    if not isinstance(reasoning, str) or not reasoning.strip():
        raise StrategistParseError("missing reasoning")

    try:
        conviction = float(raw.get("conviction", 0.5))
    except (TypeError, ValueError):
        conviction = 0.5
    conviction = max(0.0, min(1.0, conviction))

    comments = raw.get("sector_comments")
    if not isinstance(comments, dict):
        comments = {}
    calls = raw.get("rotation_calls")
    if not isinstance(calls, list):
        calls = []

    return {
        "regime_proposal": regime,
        "conviction": conviction,
        "sector_comments": {str(k): str(v) for k, v in comments.items()},
        "rotation_calls": [str(c) for c in calls],
        "reasoning": reasoning.strip(),
    }
