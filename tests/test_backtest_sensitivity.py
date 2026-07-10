import importlib

import numpy as np
import pandas as pd

from execution.backtest.sensitivity import SWEEP_SPECS, patched, run_sweep
from execution.backtest.simulator import BacktestConfig


def test_patched_sets_and_restores():
    mod = importlib.import_module("execution.funnel.entries")
    original = mod.EXTENSION_ATR_LIMIT
    with patched("execution.funnel.entries", "EXTENSION_ATR_LIMIT", 9.9):
        assert mod.EXTENSION_ATR_LIMIT == 9.9
    assert mod.EXTENSION_ATR_LIMIT == original


def test_patched_handles_tuple_attrs():
    mod = importlib.import_module("execution.funnel.entries")
    orig = (mod.ENTRY_WEIGHT_MIN, mod.ENTRY_WEIGHT_MAX)
    with patched("execution.funnel.entries",
                 ("ENTRY_WEIGHT_MIN", "ENTRY_WEIGHT_MAX"), (0.05, 0.10)):
        assert (mod.ENTRY_WEIGHT_MIN, mod.ENTRY_WEIGHT_MAX) == (0.05, 0.10)
    assert (mod.ENTRY_WEIGHT_MIN, mod.ENTRY_WEIGHT_MAX) == orig


def test_sweep_specs_cover_the_gate_constants():
    names = {s["name"] for s in SWEEP_SPECS}
    assert names == {"stop_mult", "extension_limit", "outcompete_margin", "entry_band"}
    assert all(len(s["values"]) == 2 for s in SWEEP_SPECS)


def test_run_sweep_produces_a_row_per_run(monkeypatch):
    # stub run_backtest: constant equity curve → deterministic metrics
    import execution.backtest.sensitivity as sens

    idx = pd.bdate_range("2020-01-01", periods=300)
    fake = pd.Series(100_000 * 1.0005 ** np.arange(300), index=idx)

    class R:
        equity = fake
        journal = []
        weeks = 60
    monkeypatch.setattr(sens, "run_backtest", lambda ohlcv, cfg, **kw: R())

    rows = run_sweep({}, BacktestConfig(), naive_sharpe=0.5)
    # 4 specs × 2 values + flat_conviction_60 = 9 rows
    assert len(rows) == 9
    assert rows[-1]["name"] == "flat_conviction_60"
    assert all("sharpe_edge" in r for r in rows)
