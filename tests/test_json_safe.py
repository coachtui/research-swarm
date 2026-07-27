"""Non-finite floats must not reach an Inngest step boundary.

Python's json.dumps emits bare NaN/Infinity by default; Inngest's Go executor
rejects both ("invalid character 'N' looking for beginning of value"), failing
the run with no traceback and no partial writes. The step body has already
succeeded by then, so no try/except in our code can catch it.
"""
import json

import numpy as np

from execution.json_safe import json_safe


def test_replaces_nan_and_infinity_with_none():
    assert json_safe(float("nan")) is None
    assert json_safe(float("inf")) is None
    assert json_safe(float("-inf")) is None


def test_numpy_floats_are_covered():
    # numpy.float64 subclasses float, which is exactly why this slipped through.
    assert json_safe(np.float64("nan")) is None
    assert json_safe(np.float64(1.5)) == 1.5


def test_finite_values_and_other_types_pass_through():
    assert json_safe(1.5) == 1.5
    assert json_safe(0.0) == 0.0
    assert json_safe("NVDA") == "NVDA"
    assert json_safe(None) is None
    assert json_safe(True) is True
    assert json_safe(7) == 7


def test_recurses_into_nested_dicts_and_lists():
    out = json_safe({
        "candidates": [
            {"ticker": "AAPL", "weekly_price_change_pct": float("nan")},
            {"ticker": "MSFT", "weekly_price_change_pct": 2.5},
        ],
        "universe_size": 191,
    })
    assert out["candidates"][0]["weekly_price_change_pct"] is None
    assert out["candidates"][1]["weekly_price_change_pct"] == 2.5
    assert out["universe_size"] == 191


def test_output_survives_strict_json_encoding():
    # The property that actually matters: allow_nan=False is what Go enforces.
    payload = {"a": float("nan"), "b": [float("inf"), {"c": float("-inf")}]}
    json.dumps(json_safe(payload), allow_nan=False)
