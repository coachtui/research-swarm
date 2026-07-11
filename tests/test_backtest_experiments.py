# tests/test_backtest_experiments.py
"""Race-driver logic on stubs — no full simulations here."""
import importlib

import numpy as np
import pandas as pd

import execution.backtest.experiments as exp
from execution.backtest.simulator import BacktestConfig


def _fake_result(journal=()):
    idx = pd.bdate_range("2020-01-01", periods=300)
    rows = list(journal)   # class bodies can't see enclosing function args

    class R:
        equity = pd.Series(100_000 * 1.0005 ** np.arange(300), index=idx)
        journal = rows
        weeks = 60
    return R()


def test_variants_cover_the_owner_approved_matrix():
    names = [v["name"] for v in exp.VARIANTS]
    assert names == ["requote", "valve", "margin8", "combined"]
    combined = exp.VARIANTS[-1]
    assert combined["cfg"] == {"requote_weekly": True, "capitulation_valve": True}
    assert (exp.ENTRIES, "PATIENT_LIMIT_TTL_WEEKS", 1) in combined["patches"]
    assert (exp.DECISIONS, "OUTCOMPETE_MARGIN", 8.0) in combined["patches"]


def test_combined_sweep_recentred_on_margin_8():
    spec = next(s for s in exp.COMBINED_SWEEP_SPECS
                if s["name"] == "outcompete_margin")
    assert spec["values"] == [6.4, 9.6]          # ±20% of 8, not of 10
    assert {s["name"] for s in exp.COMBINED_SWEEP_SPECS} == {
        "stop_mult", "extension_limit", "outcompete_margin", "entry_band"}


def test_run_variant_applies_flags_and_patches(monkeypatch):
    seen = {}

    def spy_run(ohlcv, cfg, **kw):
        entries = importlib.import_module(exp.ENTRIES)
        decisions = importlib.import_module(exp.DECISIONS)
        seen.update(requote=cfg.requote_weekly, valve=cfg.capitulation_valve,
                    ttl=entries.PATIENT_LIMIT_TTL_WEEKS,
                    margin=decisions.OUTCOMPETE_MARGIN)
        return _fake_result()
    monkeypatch.setattr(exp, "run_backtest", spy_run)

    combined = next(v for v in exp.VARIANTS if v["name"] == "combined")
    exp.run_variant({}, BacktestConfig(), combined)
    assert seen == {"requote": True, "valve": True, "ttl": 1, "margin": 8.0}
    # and everything restored afterwards
    assert importlib.import_module(exp.ENTRIES).PATIENT_LIMIT_TTL_WEEKS == 2
    assert importlib.import_module(exp.DECISIONS).OUTCOMPETE_MARGIN == 10.0


def test_run_combined_sweep_keeps_flags_on_and_yields_nine_rows(monkeypatch):
    calls = []

    def spy_run(ohlcv, cfg, **kw):
        decisions = importlib.import_module(exp.DECISIONS)
        calls.append((cfg.requote_weekly, cfg.capitulation_valve,
                      cfg.flat_conviction, decisions.OUTCOMPETE_MARGIN))
        return _fake_result()
    monkeypatch.setattr(exp, "run_backtest", spy_run)

    rows = exp.run_combined_sweep({}, BacktestConfig(), naive_sharpe=0.5)
    assert len(rows) == 9                       # 4 specs × 2 + flat-60
    assert rows[-1]["name"] == "flat_conviction_60"
    assert all(c[0] and c[1] for c in calls)    # every run carries both flags
    assert calls[-1][2] == 60.0                 # flat-60 run
    margins = {c[3] for c in calls}
    assert margins == {6.4, 9.6, 8.0}           # 8 except when itself swept


def _journal():
    d = pd.Timestamp("2020-02-03").date()
    return ([{"date": d, "side": "buy", "symbol": "A", "qty": 1, "price": 10.0,
              "reason": "entry_fill"}] * 3
            + [{"date": d, "side": "buy", "symbol": "B", "qty": 1, "price": 10.0,
                "reason": "capitulation_entry"}]
            + [{"date": d, "side": "cancel", "symbol": "C", "qty": 1, "price": 10.0,
                "reason": "missed_fill"}] * 2
            + [{"date": d, "side": "cancel", "symbol": "D", "qty": 1, "price": 10.0,
                "reason": "requote"}] * 5
            + [{"date": d, "side": "sell", "symbol": "A", "qty": 1, "price": 11.0,
                "reason": "trailing_stop"}])


def test_fill_diagnostics_counts_terminal_outcomes():
    d = exp.fill_diagnostics(_journal())
    assert d == {"entry_fills": 3, "valve_entries": 1, "missed_fill_cancels": 2,
                 "requote_cancels": 5, "missed_fill_rate": round(2 / 6, 4)}


def test_race_row_shape():
    r = exp.race_row("combined", _fake_result(_journal()), naive_sharpe=0.5,
                     starting_cash=100_000.0)
    for key in ("name", "cagr", "max_drawdown", "sharpe", "mar", "sharpe_edge",
                "entry_fills", "valve_entries", "missed_fill_cancels",
                "requote_cancels", "missed_fill_rate", "avg_exposure",
                "yearly_returns"):
        assert key in r
    assert r["name"] == "combined"
    assert r["sharpe_edge"] == r["sharpe"] - 0.5
