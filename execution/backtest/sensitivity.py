"""Constant-perturbation sweep. Production modules are patched in place
(each consuming module imported the constant by name) and always restored —
the same pattern the unit-test suite uses. Production code is untouched."""
import importlib
from contextlib import contextmanager
from dataclasses import replace
from typing import Dict, List, Union

from execution.backtest.metrics import compute_metrics
from execution.backtest.simulator import BacktestConfig, run_backtest

SWEEP_SPECS: List[dict] = [
    {"name": "stop_mult", "module": "inngest_app.functions.execution_daily",
     "attr": "TRAILING_STOP_ATR_MULT", "values": [2.0, 3.0]},
    {"name": "extension_limit", "module": "execution.funnel.entries",
     "attr": "EXTENSION_ATR_LIMIT", "values": [1.2, 1.8]},
    {"name": "outcompete_margin", "module": "execution.funnel.decisions",
     "attr": "OUTCOMPETE_MARGIN", "values": [8.0, 12.0]},
    {"name": "entry_band", "module": "execution.funnel.entries",
     "attr": ("ENTRY_WEIGHT_MIN", "ENTRY_WEIGHT_MAX"),
     "values": [(0.024, 0.096), (0.036, 0.144)]},
]


@contextmanager
def patched(module_path: str, attr: Union[str, tuple], value):
    mod = importlib.import_module(module_path)
    attrs = attr if isinstance(attr, tuple) else (attr,)
    values = value if isinstance(attr, tuple) else (value,)
    originals = [getattr(mod, a) for a in attrs]
    try:
        for a, v in zip(attrs, values):
            setattr(mod, a, v)
        yield
    finally:
        for a, v in zip(attrs, originals):
            setattr(mod, a, v)


def _row(name: str, value, equity, naive_sharpe: float) -> Dict:
    m = compute_metrics(equity)
    return {"name": name, "value": value, "cagr": m["cagr"],
            "max_drawdown": m["max_drawdown"], "sharpe": m["sharpe"],
            "sharpe_edge": m["sharpe"] - naive_sharpe}


def run_sweep(ohlcv, cfg: BacktestConfig, naive_sharpe: float,
              pit=None, static_universe=None) -> List[dict]:
    rows: List[dict] = []
    for spec in SWEEP_SPECS:
        for value in spec["values"]:
            with patched(spec["module"], spec["attr"], value):
                result = run_backtest(ohlcv, cfg, pit=pit,
                                      static_universe=static_universe)
            rows.append(_row(spec["name"], value, result.equity, naive_sharpe))
    flat = run_backtest(ohlcv, replace(cfg, flat_conviction=60.0),
                        pit=pit, static_universe=static_universe)
    rows.append(_row("flat_conviction_60", 60.0, flat.equity, naive_sharpe))
    return rows
