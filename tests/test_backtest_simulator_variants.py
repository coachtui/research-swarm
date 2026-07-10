# tests/test_backtest_simulator_variants.py
"""Entry-mechanics variants (requote / capitulation valve). Synthetic
fixture: one permanently *extended* uptrend whose patient limit never
fills — the exact pathology the 41% missed-fill finding points at."""
import numpy as np
import pandas as pd
import pytest

from execution.backtest.fills import LimitOrder
from execution.backtest.simulator import (
    BacktestConfig, run_backtest, valve_armed, _record_miss,
)


def test_config_flags_default_off():
    cfg = BacktestConfig()
    assert cfg.requote_weekly is False
    assert cfg.capitulation_valve is False


def test_valve_armed_rules():
    assert not valve_armed(None, 60.0)                              # never missed
    assert not valve_armed({"count": 1, "conviction": 60.0}, 60.0)  # one miss only
    assert not valve_armed({"count": 2, "conviction": 61.0}, 60.0)  # conviction dropped
    assert valve_armed({"count": 2, "conviction": 60.0}, 60.0)      # not lower: equal ok
    assert valve_armed({"count": 3, "conviction": 55.0}, 60.0)      # higher ok


def test_record_miss_counts_and_tracks_conviction():
    missed = {}
    order = LimitOrder("XY", 10, 50.0, 1.0,
                       pd.Timestamp("2020-01-06").date(),
                       pd.Timestamp("2020-01-13").date(), conviction=70.0)
    _record_miss(missed, order)
    _record_miss(missed, order)
    assert missed["XY"] == {"count": 2, "conviction": 70.0}
