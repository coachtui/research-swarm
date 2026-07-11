"""Strict parsing of theme-discovery LLM output.

Posture (manager-schema-drift lesson): unknown fields are ignored; any item
missing a required field or failing shape checks is SKIPPED and listed in
"skipped" with a reason — never a crash, never a silent guess. Only a
response with no extractable JSON at all raises ThemeParseError.
"""
import json
import logging
import re
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

VALID_ACTIONS = {"add", "keep", "retire"}
_SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9-]{1,40}$")
_TICKER_RE = re.compile(r"^[A-Z][A-Z0-9.\-]{0,9}$")


class ThemeParseError(Exception):
    """No JSON object could be extracted from the response."""


def _extract_json(text: str) -> Dict[str, Any]:
    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    candidate = fenced.group(1) if fenced else None
    if candidate is None:
        start, end = text.find("{"), text.rfind("}")
        if start == -1 or end <= start:
            raise ThemeParseError("no JSON object in response")
        candidate = text[start:end + 1]
    try:
        obj = json.loads(candidate)
    except json.JSONDecodeError as exc:
        raise ThemeParseError(f"unparseable JSON: {exc}") from exc
    if not isinstance(obj, dict):
        raise ThemeParseError("top-level JSON is not an object")
    return obj


def _clamped_confidence(value: Any) -> Optional[float]:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return max(0.0, min(1.0, float(value)))


def _parse_constituent(raw: Any, skipped: List[str], context: str) -> Optional[Dict[str, Any]]:
    if not isinstance(raw, dict):
        skipped.append(f"{context}: constituent not an object")
        return None
    ticker = str(raw.get("ticker", "")).strip().upper()
    exposure = raw.get("exposure")
    confidence = _clamped_confidence(raw.get("confidence"))
    if not _TICKER_RE.match(ticker):
        skipped.append(f"{context}: invalid ticker {raw.get('ticker')!r}")
        return None
    if not isinstance(exposure, str) or not exposure.strip():
        skipped.append(f"{context}/{ticker}: missing exposure")
        return None
    if confidence is None:
        skipped.append(f"{context}/{ticker}: invalid confidence")
        return None
    return {"ticker": ticker, "exposure": exposure.strip(), "confidence": confidence}


def parse_monthly_response(text: str) -> Dict[str, Any]:
    obj = _extract_json(text)
    themes: List[Dict[str, Any]] = []
    skipped: List[str] = []
    for raw in obj.get("themes") or []:
        if not isinstance(raw, dict):
            skipped.append("theme entry not an object")
            continue
        slug = str(raw.get("slug", "")).strip()
        action = str(raw.get("action", "")).strip().lower()
        name = raw.get("name")
        thesis = raw.get("thesis")
        confidence = _clamped_confidence(raw.get("confidence"))
        if not _SLUG_RE.match(slug):
            skipped.append(f"invalid slug {raw.get('slug')!r}")
            continue
        if action not in VALID_ACTIONS:
            skipped.append(f"{slug}: invalid action {raw.get('action')!r}")
            continue
        if not isinstance(name, str) or not name.strip() or not isinstance(thesis, str) or not thesis.strip():
            skipped.append(f"{slug}: missing name/thesis")
            continue
        if confidence is None:
            skipped.append(f"{slug}: invalid confidence")
            continue
        constituents = []
        for c in raw.get("constituents") or []:
            parsed = _parse_constituent(c, skipped, slug)
            if parsed is not None:
                constituents.append(parsed)
        metadata = raw.get("metadata") if isinstance(raw.get("metadata"), dict) else {}
        themes.append({
            "slug": slug, "name": name.strip(), "action": action,
            "thesis": thesis.strip(), "confidence": confidence,
            "metadata": metadata, "constituents": constituents,
        })
    next_constraints = [
        h for h in (obj.get("next_constraints") or [])
        if isinstance(h, dict) and h.get("hypothesis")
    ]
    return {"themes": themes, "skipped": skipped, "next_constraints": next_constraints}


def parse_delta_response(text: str) -> Dict[str, Any]:
    obj = _extract_json(text)
    themes: List[Dict[str, Any]] = []
    skipped: List[str] = []
    for raw in obj.get("themes") or []:
        if not isinstance(raw, dict):
            skipped.append("delta entry not an object")
            continue
        slug = str(raw.get("slug", "")).strip()
        if not _SLUG_RE.match(slug):
            skipped.append(f"invalid slug {raw.get('slug')!r}")
            continue
        adds = []
        for c in raw.get("add") or []:
            parsed = _parse_constituent(c, skipped, slug)
            if parsed is not None:
                adds.append(parsed)
        removes = []
        for c in raw.get("remove") or []:
            if not isinstance(c, dict):
                skipped.append(f"{slug}: remove entry not an object")
                continue
            ticker = str(c.get("ticker", "")).strip().upper()
            confidence = _clamped_confidence(c.get("confidence"))
            if not _TICKER_RE.match(ticker) or confidence is None:
                skipped.append(f"{slug}: invalid remove {c.get('ticker')!r}")
                continue
            removes.append({"ticker": ticker,
                            "reason": str(c.get("reason", "")).strip(),
                            "confidence": confidence})
        themes.append({"slug": slug, "add": adds, "remove": removes})
    return {"themes": themes, "skipped": skipped}
