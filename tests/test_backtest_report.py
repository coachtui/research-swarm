import json

from execution.backtest.report import gate_verdict, render_report, write_report

BASE = {"cagr": 0.12, "max_drawdown": -0.20, "sharpe": 0.9, "mar": 0.6,
        "yearly_returns": {"2020": 0.1}}
NAIVE = {"cagr": 0.14, "max_drawdown": -0.30, "sharpe": 0.8, "mar": 0.47,
         "yearly_returns": {"2020": 0.2}}


def test_gate_passes_when_all_criteria_met():
    v = gate_verdict(BASE, NAIVE, {"2020": 0.04, "2021": 0.05, "2022": 0.03},
                     sweep_edges=[0.05, 0.02, 0.01])
    assert v == {"drawdown_ok": True, "risk_adjusted_ok": True,
                 "robust_ok": True, "passed": True}


def test_gate_fails_on_drawdown():
    base = dict(BASE, max_drawdown=-0.29)          # not ≤ 0.8 × 0.30
    assert not gate_verdict(base, NAIVE, {"2020": 0.1, "2021": 0.1},
                            sweep_edges=[0.1])["drawdown_ok"]


def test_gate_fails_on_risk_adjusted():
    base = dict(BASE, sharpe=0.7)
    assert not gate_verdict(base, NAIVE, {"2020": 0.1, "2021": 0.1},
                            sweep_edges=[0.1])["risk_adjusted_ok"]


def test_gate_fails_when_one_year_dominates_or_edge_flips():
    v = gate_verdict(BASE, NAIVE, {"2020": 0.09, "2021": 0.01},
                     sweep_edges=[0.05])
    assert not v["robust_ok"]                       # 2020 is 90% of the edge
    v = gate_verdict(BASE, NAIVE, {"2020": 0.05, "2021": 0.05},
                     sweep_edges=[0.05, -0.01])
    assert not v["robust_ok"]                       # a perturbation flips sign
    v = gate_verdict(BASE, NAIVE, {"2020": -0.05, "2021": 0.01},
                     sweep_edges=[0.05])
    assert not v["robust_ok"]                       # negative total edge


def test_render_and_write_report(tmp_path):
    yearly = {"2020": 0.04, "2021": 0.05, "2022": 0.03}   # no year > 50% of total
    verdict = gate_verdict(BASE, NAIVE, yearly, sweep_edges=[0.05])
    md = render_report(
        {"window": "2015-01-01 → 2026-06-30", "universe_size": 1400},
        BASE, {"naive_momentum": NAIVE, "equal_weight": NAIVE, "spy": NAIVE},
        yearly,
        [{"name": "stop_mult", "value": 2.0, "cagr": 0.1,
          "max_drawdown": -0.22, "sharpe": 0.85, "sharpe_edge": 0.05}],
        verdict)
    assert "GATE" in md and "survivorship" in md.lower()
    assert "stand-in" in md.lower()
    out = write_report(tmp_path / "run1", md, {"base": BASE, "verdict": verdict})
    assert (out / "report.md").read_text().startswith("#")
    assert json.loads((out / "metrics.json").read_text())["verdict"]["passed"]


def test_render_report_with_no_sweep_is_incomplete_not_pass():
    yearly = {"2020": 0.04, "2021": 0.05, "2022": 0.03}
    verdict = gate_verdict(BASE, NAIVE, yearly, sweep_edges=[])
    md = render_report(
        {"window": "2015-01-01 → 2026-06-30", "universe_size": 1400},
        BASE, {"naive_momentum": NAIVE, "equal_weight": NAIVE, "spy": NAIVE},
        yearly, [], verdict)
    assert "INCOMPLETE" in md
    assert "Overall: PASS" not in md
    assert "N/A" in md and "sweep not run" in md


def test_render_experiments_report_race_table_and_embedded_gate():
    from execution.backtest.report import render_experiments_report
    row = {"name": "combined", "cagr": 0.13, "max_drawdown": -0.16,
           "sharpe": 1.05, "mar": 0.8, "sharpe_edge": 0.28,
           "entry_fills": 900, "valve_entries": 40, "missed_fill_cancels": 200,
           "requote_cancels": 800, "missed_fill_rate": 0.1754,
           "avg_exposure": 0.51, "yearly_returns": {"2020": 0.2}}
    md = render_experiments_report({"window": "w"}, [row], "GATE-SECTION")
    assert "Entry-Mechanics Experiments" in md
    assert "| combined | +13.00% | -16.00% | 1.05 | 0.80 | +0.28 " in md
    assert "| 900 | 40 | 200 | 800 | 17.5% | 0.51 |" in md
    assert md.rstrip().endswith("GATE-SECTION")
    assert "backtest-only" in md.lower()
