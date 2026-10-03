"""Rotation flags are states, not events — these date them."""
from types import SimpleNamespace
from datetime import datetime, timezone

from execution.indicators.rotation_tenure import (
    annotate_rotations, history_from_outlook_rows, rotation_tenure,
)


def _row(slug, rc):
    return {"slug": slug, "etf": slug, "rank_change": rc}


def test_tenure_counts_consecutive_weeks_newest_first():
    # ai-neocloud-miners: flagged 09-27, 09-20, 09-13, 09-06; not on 08-30.
    history = [
        ("2026-09-27", [_row("neo", 5), _row("photonics", -4)]),
        ("2026-09-20", [_row("neo", 6), _row("photonics", -1)]),
        ("2026-09-13", [_row("neo", 5)]),
        ("2026-09-06", [_row("neo", 5)]),
        ("2026-08-30", [_row("neo", 0)]),
        ("2026-08-23", [_row("neo", 7)]),      # an older streak does not count
    ]
    t = rotation_tenure(history, "slug", 5)
    assert t == {"neo": {"direction": "into", "since": "2026-09-06", "weeks": 4}}


def test_tenure_direction_flip_ends_the_streak_and_out_of_is_dated_too():
    history = [
        ("2026-09-27", [_row("x", -5)]),
        ("2026-09-20", [_row("x", -6)]),
        ("2026-09-13", [_row("x", 5)]),      # was rotating IN — streak breaks
    ]
    assert rotation_tenure(history, "slug", 5) == {
        "x": {"direction": "out_of", "since": "2026-09-20", "weeks": 2}}


def test_tenure_missing_key_in_older_row_ends_streak():
    history = [("2026-09-27", [_row("new", 5)]), ("2026-09-20", [_row("other", 5)])]
    assert rotation_tenure(history, "slug", 5)["new"] == {
        "direction": "into", "since": "2026-09-27", "weeks": 1}


def test_tenure_empty_and_unflagged():
    assert rotation_tenure([], "slug", 5) == {}
    assert rotation_tenure([("2026-09-27", [_row("a", 2), {"slug": None}])], "slug", 5) == {}
    assert rotation_tenure([("2026-09-27", [{"slug": "b", "rank_change": "n/a"}])], "slug", 5) == {}


def test_annotate_rotations_adds_since_without_mutating():
    flags = [{"etf": "neo", "theme": "Neo", "direction": "into", "rank_change": 5},
             {"etf": "gone", "theme": "Gone", "direction": "out_of", "rank_change": -5}]
    out = annotate_rotations(flags, {"neo": {"direction": "into", "since": "2026-09-06", "weeks": 4}})
    assert out[0]["since"] == "2026-09-06" and out[0]["weeks"] == 4
    assert out[1]["since"] is None and out[1]["weeks"] is None
    assert "since" not in flags[0]
    assert annotate_rotations(None, {}) is None


def test_history_from_outlook_rows_reduces_prisma_rows():
    rows = [
        SimpleNamespace(runDate=datetime(2026, 9, 27, 20, tzinfo=timezone.utc),
                        themeRankings={"rankings": [_row("neo", 5)], "rotations": []}),
        SimpleNamespace(runDate=datetime(2026, 9, 20, 20, tzinfo=timezone.utc),
                        themeRankings=None),
    ]
    h = history_from_outlook_rows(rows, "themeRankings")
    assert h == [("2026-09-27", [_row("neo", 5)]), ("2026-09-20", [])]
    # the None blob ends any streak
    assert rotation_tenure(h, "slug", 5)["neo"]["weeks"] == 1
