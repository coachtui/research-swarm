"""How long a rotation flag has been on.

`detect_rotations` compares the 1-month rank with the 3-month rank, so
"rotating in" is a STATE that can hold for many weeks, not an event. The
outlook page showed the badge with no date, and the owner could not tell a
rotation that began this Sunday from one that had been on since early
September. These functions walk the stored MarketOutlook history and answer
"since when" for every key currently flagged.

Pure: takes already-loaded rows, returns plain dicts. No DB, no pandas.
"""
from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional, Tuple

HistoryRow = Tuple[str, List[Dict[str, Any]]]  # (run_date ISO, rankings list)


def _direction(rank_change: Any, min_gain: int) -> Optional[str]:
    try:
        rc = int(rank_change)
    except (TypeError, ValueError):
        return None
    if rc >= min_gain:
        return "into"
    if rc <= -min_gain:
        return "out_of"
    return None


def rotation_tenure(
    history: Iterable[HistoryRow], key: str, min_gain: int,
) -> Dict[str, Dict[str, Any]]:
    """{key_value: {"direction", "since", "weeks"}} for every key flagged in
    the NEWEST row of `history` (rows newest-first). `weeks` counts the
    consecutive newest rows in which the same direction held; `since` is the
    run date of the oldest of those rows. A key absent from an older row ends
    the streak (a theme that did not exist yet was not rotating)."""
    rows = list(history)
    if not rows:
        return {}
    latest_date, latest = rows[0]
    out: Dict[str, Dict[str, Any]] = {}
    for r in latest or []:
        k = r.get(key)
        d = _direction(r.get("rank_change"), min_gain)
        if k is None or d is None:
            continue
        since, weeks = latest_date, 1
        for older_date, older in rows[1:]:
            match = next((o for o in (older or []) if o.get(key) == k), None)
            if match is None or _direction(match.get("rank_change"), min_gain) != d:
                break
            since, weeks = older_date, weeks + 1
        out[k] = {"direction": d, "since": since, "weeks": weeks}
    return out


def annotate_rotations(
    rotations: Optional[List[Dict[str, Any]]], tenure: Dict[str, Dict[str, Any]],
    key: str = "etf",
) -> Optional[List[Dict[str, Any]]]:
    """Copy each rotation flag with `since` and `weeks` from `tenure` (None /
    1 when history is unavailable). Never mutates the stored row."""
    if rotations is None:
        return None
    out = []
    for flag in rotations:
        t = tenure.get(flag.get(key))
        out.append({**flag, "since": t["since"] if t else None,
                    "weeks": t["weeks"] if t else None})
    return out


def history_from_outlook_rows(rows: Iterable[Any], field: str) -> List[HistoryRow]:
    """Reduce Prisma MarketOutlook rows (newest-first) to (run_date, rankings)
    for `field` ("themeRankings" or "industryRankings"). Rows whose blob is
    missing or malformed contribute an empty list, which ends any streak."""
    out: List[HistoryRow] = []
    for row in rows:
        run = getattr(row, "runDate", None)
        day = run.date().isoformat() if hasattr(run, "date") else str(run)[:10]
        blob = getattr(row, field, None)
        rankings = blob.get("rankings") if isinstance(blob, dict) else None
        out.append((day, rankings if isinstance(rankings, list) else []))
    return out
