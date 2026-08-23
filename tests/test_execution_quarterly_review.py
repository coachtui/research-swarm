"""Quarterly sleeve rollups — pure aggregation over SleeveSnapshot rows."""
from datetime import date

from execution.quarterly_review import (
    SnapshotPoint,
    attach_reports,
    build_quarterly_reviews,
    quarter_bounds,
    quarter_key,
)

TODAY = date(2026, 8, 23)


def _pt(day, sleeve, equity, spy):
    return SnapshotPoint(day=day, sleeve=sleeve, equity=equity, spy_close=spy)


def test_quarter_key_labels_each_calendar_quarter():
    assert quarter_key(date(2026, 1, 1)) == "2026-Q1"
    assert quarter_key(date(2026, 3, 31)) == "2026-Q1"
    assert quarter_key(date(2026, 7, 10)) == "2026-Q3"
    assert quarter_key(date(2026, 12, 31)) == "2026-Q4"


def test_quarter_keys_sort_chronologically_as_strings():
    keys = [quarter_key(date(y, m, 1)) for y, m in
            [(2027, 1), (2026, 7), (2026, 10), (2026, 4)]]
    assert sorted(keys) == ["2026-Q2", "2026-Q3", "2026-Q4", "2027-Q1"]


def test_quarter_bounds():
    assert quarter_bounds("2026-Q3") == (date(2026, 7, 1), date(2026, 9, 30))
    assert quarter_bounds("2026-Q4") == (date(2026, 10, 1), date(2026, 12, 31))
    assert quarter_bounds("2026-Q1") == (date(2026, 1, 1), date(2026, 3, 31))


def test_empty_input_is_no_quarters():
    assert build_quarterly_reviews([], today=TODAY) == []


def test_single_quarter_rollup():
    pts = [
        _pt(date(2026, 7, 10), "A", 70000.0, 700.0),
        _pt(date(2026, 7, 10), "B", 30000.0, 700.0),
        _pt(date(2026, 8, 21), "A", 69300.0, 707.0),   # -1.00%
        _pt(date(2026, 8, 21), "B", 30600.0, 707.0),   # +2.00%
    ]
    [q] = build_quarterly_reviews(pts, today=TODAY)

    assert q["quarter"] == "2026-Q3"
    assert q["period_start"] == "2026-07-10"
    assert q["period_end"] == "2026-08-21"
    assert q["trading_days"] == 2
    assert q["benchmark_return_pct"] == 1.0        # 700 -> 707
    a, b = q["sleeves"]
    assert a["sleeve"] == "A" and a["return_pct"] == -1.0 and a["excess_pct"] == -2.0
    assert b["sleeve"] == "B" and b["return_pct"] == 2.0 and b["excess_pct"] == 1.0


def test_returns_are_within_quarter_not_cumulative():
    """Q4 must measure Q4 only. A sleeve that doubled in Q3 and was flat in Q4
    reads as flat in Q4 — otherwise every later bar inherits the first one."""
    pts = [
        _pt(date(2026, 7, 1), "A", 100.0, 100.0),
        _pt(date(2026, 9, 30), "A", 200.0, 110.0),
        _pt(date(2026, 10, 1), "A", 200.0, 110.0),
        _pt(date(2026, 12, 31), "A", 200.0, 110.0),
    ]
    q3, q4 = build_quarterly_reviews(pts, today=date(2027, 1, 5))
    assert q3["quarter"] == "2026-Q3" and q3["sleeves"][0]["return_pct"] == 100.0
    assert q4["quarter"] == "2026-Q4" and q4["sleeves"][0]["return_pct"] == 0.0


def test_quarters_come_back_oldest_first():
    pts = [
        _pt(date(2027, 1, 5), "A", 100.0, 100.0),
        _pt(date(2026, 7, 1), "A", 100.0, 100.0),
        _pt(date(2026, 10, 1), "A", 100.0, 100.0),
    ]
    assert [q["quarter"] for q in build_quarterly_reviews(pts, today=date(2027, 2, 1))] \
        == ["2026-Q3", "2026-Q4", "2027-Q1"]


def test_complete_flag_tracks_the_calendar_not_the_data():
    pts = [_pt(date(2026, 7, 10), "A", 100.0, 100.0),
           _pt(date(2026, 8, 21), "A", 101.0, 100.0)]
    assert build_quarterly_reviews(pts, today=date(2026, 8, 23))[0]["complete"] is False
    assert build_quarterly_reviews(pts, today=date(2026, 10, 1))[0]["complete"] is True


def test_a_sleeve_missing_the_edge_day_uses_its_own_snapshots():
    """Sleeve A was skipped on the quarter's last day (the 2026-08-20 case).
    Its return is measured over ITS rows; the shared window still frames the
    quarter, and the row count makes the gap visible."""
    pts = [
        _pt(date(2026, 7, 10), "A", 100.0, 700.0),
        _pt(date(2026, 7, 10), "B", 100.0, 700.0),
        _pt(date(2026, 8, 20), "A", 110.0, 705.0),
        _pt(date(2026, 8, 20), "B", 105.0, 705.0),
        _pt(date(2026, 8, 21), "B", 106.0, 707.0),   # A has no row here
    ]
    [q] = build_quarterly_reviews(pts, today=TODAY)
    a = next(s for s in q["sleeves"] if s["sleeve"] == "A")
    b = next(s for s in q["sleeves"] if s["sleeve"] == "B")
    assert q["period_end"] == "2026-08-21"
    assert a["snapshots"] == 2 and a["end_equity"] == 110.0   # last row A actually has
    assert b["snapshots"] == 3 and b["end_equity"] == 106.0


def test_zero_start_equity_degrades_to_null_not_infinity():
    pts = [_pt(date(2026, 7, 1), "A", 0.0, 100.0),
           _pt(date(2026, 9, 1), "A", 50.0, 100.0)]
    [q] = build_quarterly_reviews(pts, today=TODAY)
    assert q["sleeves"][0]["return_pct"] is None
    assert q["sleeves"][0]["excess_pct"] is None


# ── attach_reports ──────────────────────────────────────────────────────────

def _quarters():
    return build_quarterly_reviews(
        [_pt(date(2026, 7, 10), "A", 100.0, 700.0),
         _pt(date(2026, 8, 21), "A", 101.0, 707.0)],
        today=TODAY,
    )


def test_attach_reports_links_a_review_to_its_quarter():
    out = attach_reports(_quarters(), [
        {"quarter": "2026-Q3", "report_url": "https://example/r", "report_title": "Q3 Review"},
    ])
    assert out[0]["report_url"] == "https://example/r"
    assert out[0]["report_title"] == "Q3 Review"


def test_attach_reports_keeps_the_newest_row_per_quarter():
    """Reports arrive newest first; re-publishing a review is a new row, so the
    first one seen must win rather than the last."""
    out = attach_reports(_quarters(), [
        {"quarter": "2026-Q3", "report_url": "https://example/new"},
        {"quarter": "2026-Q3", "report_url": "https://example/old"},
    ])
    assert out[0]["report_url"] == "https://example/new"


def test_attach_reports_ignores_unknown_quarters_and_junk():
    out = attach_reports(_quarters(), [
        {"quarter": "2099-Q1", "report_url": "https://example/nope"},
        {"quarter": "2026-Q3"},          # no url
        {},                               # no quarter
        None,                             # not a dict at all
    ])
    assert out[0]["report_url"] is None
    assert len(out) == 1


def test_attach_reports_titles_default_to_the_quarter_label():
    out = attach_reports(_quarters(), [
        {"quarter": "2026-Q3", "report_url": "https://example/r"},
    ])
    assert out[0]["report_title"] == "2026-Q3"
