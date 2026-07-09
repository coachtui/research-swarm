"""Equal-weight synthetic basket index + RS ranking + sparkline history."""
import numpy as np
import pandas as pd
import pytest

from execution.indicators.theme_strength import build_theme_index, rank_themes

N = 200  # > 126+1 everywhere


def _series(daily_return, days=N, start=100.0):
    return pd.Series(start * (1 + daily_return) ** np.arange(days))


def _theme(slug, tickers):
    return {"slug": slug, "name": slug.title(), "confidence": 0.8, "tickers": list(tickers)}


def test_index_is_equal_weight_of_normalized_series():
    closes = {"A": _series(0.002, start=10.0), "B": _series(0.002, start=1000.0)}
    index, eligible = build_theme_index(closes)
    assert eligible == ["A", "B"]
    # both legs identical in return space -> index equals either normalized leg
    expected = _series(0.002, start=1.0)
    assert np.allclose(index.values, expected.values / expected.values[0])


def test_short_history_constituent_excluded():
    closes = {"A": _series(0.002), "B": _series(0.002, days=30)}
    _, eligible = build_theme_index(closes)
    assert eligible == ["A"]


def test_rank_themes_orders_by_relative_strength():
    spy = _series(0.001)
    closes = {f"H{i}": _series(0.003) for i in range(5)}
    closes.update({f"L{i}": _series(-0.001) for i in range(5)})
    themes = [_theme("hot", [f"H{i}" for i in range(5)]),
              _theme("cold", [f"L{i}" for i in range(5)])]
    out = rank_themes(themes, closes, spy)
    assert [r["slug"] for r in out["rankings"]] == ["hot", "cold"]
    top = out["rankings"][0]
    assert top["theme"] == "Hot" and top["confidence"] == 0.8
    assert top["constituent_count"] == 5
    assert out["missing"] == []


def test_theme_below_min_constituents_goes_missing():
    spy = _series(0.001)
    closes = {"A": _series(0.002), "B": _series(0.002)}
    out = rank_themes([_theme("thin", ["A", "B", "GONE1", "GONE2", "GONE3"])], closes, spy)
    assert out["rankings"] == []
    assert out["missing"][0]["slug"] == "thin"
    assert "2" in out["missing"][0]["reason"]


def test_history_has_12_weekly_points_with_ranks():
    spy = _series(0.001)
    closes = {f"H{i}": _series(0.003) for i in range(5)}
    closes.update({f"L{i}": _series(-0.001) for i in range(5)})
    themes = [_theme("hot", [f"H{i}" for i in range(5)]),
              _theme("cold", [f"L{i}" for i in range(5)])]
    out = rank_themes(themes, closes, spy)
    hot = out["history"]["hot"]
    assert len(hot) == 12
    assert hot[-1]["weeks_ago"] == 0
    assert all(p["rank"] == 1 for p in hot)  # hot dominates every week


def test_missing_ticker_series_tolerated():
    spy = _series(0.001)
    closes = {f"H{i}": _series(0.003) for i in range(5)}
    themes = [_theme("hot", [f"H{i}" for i in range(5)] + ["ABSENT"])]
    out = rank_themes(themes, closes, spy)
    assert out["rankings"][0]["constituent_count"] == 5
