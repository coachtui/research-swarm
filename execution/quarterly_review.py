"""Quarter-by-quarter sleeve performance, derived from SleeveSnapshot.

Nothing here is stored. Every number is recomputed from the snapshot series on
each request, so a correction to that series (the 2026-08-22 spyClose repair,
say) flows through immediately instead of leaving a stale aggregate behind.

The one thing that CANNOT be derived is the link to a quarter's written review;
that lives in an EngineReport row of type "quarterly_review" and is joined on
here by quarter label.
"""
from __future__ import annotations

from datetime import date
from typing import Any, Dict, Iterable, List, NamedTuple, Optional


class SnapshotPoint(NamedTuple):
    """One SleeveSnapshot row, reduced to what a quarterly rollup needs."""
    day: date
    sleeve: str
    equity: float
    spy_close: float


def quarter_key(day: date) -> str:
    """Calendar quarter label, sortable as a plain string."""
    return f"{day.year}-Q{(day.month - 1) // 3 + 1}"


def quarter_bounds(key: str) -> tuple:
    """(first day, last day) of the calendar quarter `key` names."""
    year, q = int(key[:4]), int(key[-1])
    first_month = 3 * (q - 1) + 1
    last_month = first_month + 2
    last_day = 31 if last_month in (3, 12) else 30
    return date(year, first_month, 1), date(year, last_month, last_day)


def _pct(start: float, end: float) -> Optional[float]:
    if start is None or end is None or start == 0:
        return None
    return (end / start - 1.0) * 100.0


def build_quarterly_reviews(
    snapshots: Iterable[SnapshotPoint],
    today: Optional[date] = None,
) -> List[Dict[str, Any]]:
    """One rollup per calendar quarter that has snapshots, oldest first.

    WINDOW: a quarter's window runs from the earliest to the latest snapshot
    date in that quarter, across all sleeves, and every sleeve plus the
    benchmark is measured over those same two dates. Sleeves are snapshotted by
    the same cron on the same days, so their windows differ only where one
    sleeve was skipped — at most a day at either edge. One shared window is
    what makes the sleeves and the benchmark comparable as bars in one chart,
    which is worth more than a day of edge precision; `period_start` and
    `period_end` are returned so the reader can audit it.

    RETURNS ARE WITHIN-QUARTER, not cumulative — the question this answers is
    "how did each sleeve do THIS quarter", so Q4 does not inherit Q3's result.
    """
    points = list(snapshots)
    if not points:
        return []

    by_quarter: Dict[str, List[SnapshotPoint]] = {}
    for p in points:
        by_quarter.setdefault(quarter_key(p.day), []).append(p)

    out: List[Dict[str, Any]] = []
    for key in sorted(by_quarter):
        rows = sorted(by_quarter[key], key=lambda p: p.day)
        start_day, end_day = rows[0].day, rows[-1].day

        # The benchmark is a property of the DAY, not of a sleeve — every row
        # for a given date carries the same spyClose.
        spy_start = next(p.spy_close for p in rows if p.day == start_day)
        spy_end = next(p.spy_close for p in rows if p.day == end_day)
        bench = _pct(spy_start, spy_end)

        sleeves: Dict[str, Dict[str, Any]] = {}
        for name in sorted({p.sleeve for p in rows}):
            own = [p for p in rows if p.sleeve == name]
            ret = _pct(own[0].equity, own[-1].equity)
            sleeves[name] = {
                "sleeve": name,
                "start_equity": round(own[0].equity, 2),
                "end_equity": round(own[-1].equity, 2),
                "return_pct": None if ret is None else round(ret, 2),
                "excess_pct": (
                    None if ret is None or bench is None else round(ret - bench, 2)
                ),
                "snapshots": len(own),
            }

        _, quarter_end = quarter_bounds(key)
        out.append({
            "quarter": key,
            "period_start": start_day.isoformat(),
            "period_end": end_day.isoformat(),
            "complete": (today or date.today()) > quarter_end,
            "trading_days": len({p.day for p in rows}),
            "benchmark_return_pct": None if bench is None else round(bench, 2),
            "benchmark_start": round(spy_start, 2),
            "benchmark_end": round(spy_end, 2),
            "sleeves": list(sleeves.values()),
            "report_url": None,   # filled in from the EngineReport journal
            "report_title": None,
        })
    return out


def attach_reports(
    quarters: List[Dict[str, Any]], reports: Iterable[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """Join written reviews onto their quarter.

    `reports` are EngineReport bodies, newest first; the first one seen for a
    quarter wins, so re-publishing a review is just a new row rather than an
    edit. A review naming a quarter with no snapshots is ignored rather than
    inventing a row — the snapshot series decides which quarters exist.
    """
    index = {q["quarter"]: q for q in quarters}
    for body in reports:
        key = (body or {}).get("quarter")
        target = index.get(key)
        if target is None or target["report_url"]:
            continue
        url = (body or {}).get("report_url")
        if not url:
            continue
        target["report_url"] = url
        target["report_title"] = (body or {}).get("report_title") or key
    return quarters
