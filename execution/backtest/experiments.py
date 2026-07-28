"""Entry-mechanics experiment race (Phase 3D follow-up spec). Variants are
harness flags plus patched constants — production code untouched. Base and
naive momentum re-run in-process so every race row shares one code path;
the combined config gets the full pre-committed gate, with the ±20% sweep
recentred on its active constants."""
from contextlib import ExitStack
from dataclasses import replace
from typing import Dict, List

from execution.backtest.metrics import compute_metrics, trade_stats
from execution.backtest.sensitivity import _row, patched
from execution.backtest.simulator import BacktestConfig, BacktestResult, run_backtest

ENTRIES = "execution.funnel.entries"
# Task 11 moved the challenger/outcompete logic (and its OUTCOMPETE_MARGIN
# constant) out of execution.funnel.decisions and into the backtest
# simulator's local, deprecated entry stand-in — this now patches the
# module that actually reads the constant at call time.
DECISIONS = "execution.backtest.simulator"

VARIANTS: List[dict] = [
    {"name": "requote", "cfg": {"requote_weekly": True},
     "patches": [(ENTRIES, "PATIENT_LIMIT_TTL_WEEKS", 1)]},
    {"name": "valve", "cfg": {"capitulation_valve": True}, "patches": []},
    {"name": "margin8", "cfg": {},
     "patches": [(DECISIONS, "OUTCOMPETE_MARGIN", 8.0)]},
    {"name": "combined",
     "cfg": {"requote_weekly": True, "capitulation_valve": True},
     "patches": [(ENTRIES, "PATIENT_LIMIT_TTL_WEEKS", 1),
                 (DECISIONS, "OUTCOMPETE_MARGIN", 8.0)]},
]

# sensitivity.SWEEP_SPECS recentred on the combined config: ±20% of the
# *active* values, so outcompete sweeps 6.4/9.6 around 8 (stop 2.5 and
# extension 1.5 are unchanged by the variants; their ±20% stays 2.0/3.0
# and 1.2/1.8).
COMBINED_SWEEP_SPECS: List[dict] = [
    {"name": "stop_mult", "module": "inngest_app.functions.execution_daily",
     "attr": "TRAILING_STOP_ATR_MULT", "values": [2.0, 3.0]},
    {"name": "extension_limit", "module": ENTRIES,
     "attr": "EXTENSION_ATR_LIMIT", "values": [1.2, 1.8]},
    {"name": "outcompete_margin", "module": DECISIONS,
     "attr": "OUTCOMPETE_MARGIN", "values": [6.4, 9.6]},
    {"name": "entry_band", "module": ENTRIES,
     "attr": ("ENTRY_WEIGHT_MIN", "ENTRY_WEIGHT_MAX"),
     "values": [(0.024, 0.096), (0.036, 0.144)]},
]


def run_variant(ohlcv, cfg: BacktestConfig, variant: dict,
                pit=None, static_universe=None) -> BacktestResult:
    vcfg = replace(cfg, **variant["cfg"])
    with ExitStack() as stack:
        for mod, attr, val in variant["patches"]:
            stack.enter_context(patched(mod, attr, val))
        return run_backtest(ohlcv, vcfg, pit=pit, static_universe=static_universe)


def fill_diagnostics(journal: List[dict]) -> Dict:
    """Missed-fill rate over *terminal* quote outcomes: a requote chain ends
    in either a fill (limit or valve) or one final missed_fill, so requote
    cancels are reported but excluded from the denominator."""
    fills = sum(1 for j in journal
                if j["side"] == "buy" and j["reason"] == "entry_fill")
    valve = sum(1 for j in journal
                if j["side"] == "buy" and j["reason"] == "capitulation_entry")
    missed = sum(1 for j in journal
                 if j["side"] == "cancel" and j["reason"] == "missed_fill")
    requotes = sum(1 for j in journal
                   if j["side"] == "cancel" and j["reason"] == "requote")
    terminal = fills + valve + missed
    return {"entry_fills": fills, "valve_entries": valve,
            "missed_fill_cancels": missed, "requote_cancels": requotes,
            "missed_fill_rate": round(missed / terminal, 4) if terminal else None}


def race_row(name: str, result: BacktestResult, naive_sharpe: float,
             starting_cash: float) -> dict:
    m = compute_metrics(result.equity)
    stats = trade_stats(result.journal, result.equity, starting_cash)
    return {"name": name, "cagr": m["cagr"], "max_drawdown": m["max_drawdown"],
            "sharpe": m["sharpe"], "mar": m["mar"],
            "sharpe_edge": m["sharpe"] - naive_sharpe,
            **fill_diagnostics(result.journal),
            "avg_exposure": stats["avg_exposure"],
            "yearly_returns": m["yearly_returns"]}


def run_combined_sweep(ohlcv, cfg: BacktestConfig, naive_sharpe: float,
                       pit=None, static_universe=None) -> List[dict]:
    combined = next(v for v in VARIANTS if v["name"] == "combined")
    ccfg = replace(cfg, **combined["cfg"])
    rows: List[dict] = []
    for spec in COMBINED_SWEEP_SPECS:
        for value in spec["values"]:
            with ExitStack() as stack:
                for mod, attr, val in combined["patches"]:
                    stack.enter_context(patched(mod, attr, val))
                stack.enter_context(patched(spec["module"], spec["attr"], value))
                result = run_backtest(ohlcv, ccfg, pit=pit,
                                      static_universe=static_universe)
            rows.append(_row(spec["name"], value, result.equity, naive_sharpe))
    with ExitStack() as stack:
        for mod, attr, val in combined["patches"]:
            stack.enter_context(patched(mod, attr, val))
        flat = run_backtest(ohlcv, replace(ccfg, flat_conviction=60.0),
                            pit=pit, static_universe=static_universe)
    rows.append(_row("flat_conviction_60", 60.0, flat.equity, naive_sharpe))
    return rows
