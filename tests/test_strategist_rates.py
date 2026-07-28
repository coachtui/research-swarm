"""Deterministic rate/curve inputs for the macro strategist.

The strategist could see the SYMPTOM (money rotating into Energy and Utilities,
tech falling #1 -> #10) but never the CAUSE, because it had no rate data at
all — only sector ranks, breadth, VIX and ten cached headlines. It inferred an
inflation-hedge rotation from rank changes and happened to be right.

These numbers are computed, not asked for: a model handed the implied path
cannot invent one. Every field degrades to None rather than raising — the
outlook must be produced even when market data is down.
"""
from unittest.mock import patch

import pandas as pd
import pytest

from execution.strategist import rates


def _series(values):
    return pd.DataFrame({"Close": values})


def test_implied_fed_funds_is_100_minus_price():
    with patch.object(rates, "_history", return_value=_series([96.0] * 5 + [96.295])):
        out = rates.rate_context()
    assert out["implied_fed_funds"] == pytest.approx(3.705, abs=1e-3)


def test_weekly_change_is_reported_in_basis_points():
    # price falls 0.07 => implied rate RISES 7bp: expectations firmed.
    with patch.object(rates, "_history", return_value=_series([96.365] * 5 + [96.295])):
        out = rates.rate_context()
    assert out["implied_fed_funds_1w_bp"] == pytest.approx(7.0, abs=0.5)


def test_curve_levels_are_carried_through():
    def fake(sym, period="1mo"):
        return {"ZQ=F": _series([96.295] * 6),
                "^IRX": _series([3.79] * 6),
                "^FVX": _series([4.38] * 6),
                "^TNX": _series([4.63] * 6)}[sym]

    with patch.object(rates, "_history", side_effect=fake):
        out = rates.rate_context()
    assert out["curve"]["3m"] == pytest.approx(3.79)
    assert out["curve"]["10y"] == pytest.approx(4.63)


def test_missing_data_degrades_to_none_and_never_raises():
    with patch.object(rates, "_history", return_value=None):
        out = rates.rate_context()
    assert out["implied_fed_funds"] is None
    assert out["curve"]["10y"] is None


def test_market_data_outage_never_raises():
    with patch.object(rates, "_history", side_effect=RuntimeError("yfinance down")):
        out = rates.rate_context()
    assert out["implied_fed_funds"] is None


def test_output_is_strict_json_serializable():
    # It crosses an Inngest step boundary inside weekly_outlook.
    import json
    with patch.object(rates, "_history", return_value=_series([96.295] * 6)):
        json.dumps(rates.rate_context(), allow_nan=False)


def test_single_bar_history_yields_level_but_no_change():
    with patch.object(rates, "_history", return_value=_series([96.295])):
        out = rates.rate_context()
    assert out["implied_fed_funds"] == pytest.approx(3.705, abs=1e-3)
    assert out["implied_fed_funds_1w_bp"] is None
