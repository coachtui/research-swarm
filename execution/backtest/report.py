"""Gate verdict (the three pre-committed criteria from the 3D spec) and
the markdown/JSON report. The criteria are code, not prose — they cannot
be reinterpreted after results are seen."""
import json
from pathlib import Path
from typing import Dict, List

DISCLAIMER = (
    "> **Survivorship bias:** the large-cap set uses point-in-time S&P 500 "
    "membership, clean only to the extent yfinance still serves delisted "
    "tickers (coverage reported in the run metadata); the mid/small set is "
    "today's IJH/IJR membership held fixed backwards, so dead companies are "
    "absent and absolute returns are inflated. Every baseline shares the "
    "same universe — only relative conclusions are meaningful. The mcap "
    "floor is not applied historically (no point-in-time share counts); ADV "
    "is the liquidity proxy. Guardrails (theme/sector caps) are omitted — "
    "inert without historical tags. Conviction is a mechanical stand-in — "
    "screen_score × 10, no LLM inputs — the one deliberate substitution "
    "from the live funnel (flat-60 variant in the sweep)."
)


def gate_verdict(base: dict, naive: dict, yearly_outperf: Dict[str, float],
                 sweep_edges: List[float]) -> dict:
    drawdown_ok = abs(base["max_drawdown"]) <= 0.8 * abs(naive["max_drawdown"])
    risk_adjusted_ok = (base["sharpe"] >= naive["sharpe"]
                        and base["mar"] >= naive["mar"])
    total = sum(yearly_outperf.values())
    robust_ok = (total > 0
                 and max(yearly_outperf.values()) <= 0.5 * total
                 and all(e > 0 for e in sweep_edges))
    return {"drawdown_ok": drawdown_ok, "risk_adjusted_ok": risk_adjusted_ok,
            "robust_ok": robust_ok,
            "passed": drawdown_ok and risk_adjusted_ok and robust_ok}


def _metrics_row(name: str, m: dict) -> str:
    return (f"| {name} | {m['cagr']:+.2%} | {m['max_drawdown']:.2%} "
            f"| {m['sharpe']:.2f} | {m['mar']:.2f} |")


def render_report(run_meta: dict, base: dict, baselines: Dict[str, dict],
                  yearly_outperf: Dict[str, float], sweep_rows: List[dict],
                  verdict: dict) -> str:
    lines = ["# Sleeve A Tier 2 Backtest — Gate Report", ""]
    lines += [f"- **{k}:** {v}" for k, v in run_meta.items()]
    lines += ["", DISCLAIMER, "", "## GATE VERDICT", ""]
    labels = {
        "drawdown_ok": "1. Max drawdown ≤ 0.8 × naive momentum's",
        "risk_adjusted_ok": "2. Sharpe and MAR ≥ naive momentum's",
        "robust_ok": "3. No year > 50% of edge; all perturbations keep a positive Sharpe edge",
    }
    for key, label in labels.items():
        if key == "robust_ok" and not sweep_rows:
            lines.append(f"- N/A — {label} (sweep not run)")
        else:
            lines.append(f"- {'PASS' if verdict[key] else 'FAIL'} — {label}")
    if sweep_rows:
        lines += ["", f"**Overall: {'PASS' if verdict['passed'] else 'FAIL'}**", ""]
    else:
        lines += ["", "**Overall: INCOMPLETE — run sweep for the full gate**", ""]

    lines += ["## Performance", "", "| run | CAGR | maxDD | Sharpe | MAR |",
              "|---|---|---|---|---|", _metrics_row("**funnel (base)**", base)]
    lines += [_metrics_row(name, m) for name, m in baselines.items()]

    lines += ["", "## Yearly returns (funnel base)", "",
              "| year | return |", "|---|---|"]
    lines += [f"| {y} | {r:+.2%} |" for y, r in sorted(
        base["yearly_returns"].items())]

    lines += ["", "## Yearly log outperformance vs naive momentum", "",
              "| year | edge |", "|---|---|"]
    lines += [f"| {y} | {v:+.4f} |" for y, v in sorted(yearly_outperf.items())]

    if sweep_rows:
        lines += ["", "## Sensitivity sweep", "",
                  "| constant | value | CAGR | maxDD | Sharpe | Sharpe edge vs naive |",
                  "|---|---|---|---|---|---|"]
        lines += [(f"| {r['name']} | {r['value']} | {r['cagr']:+.2%} "
                   f"| {r['max_drawdown']:.2%} | {r['sharpe']:.2f} "
                   f"| {r['sharpe_edge']:+.2f} |") for r in sweep_rows]
    return "\n".join(lines) + "\n"


SCOPE_LOCK = ("> **Scope lock:** backtest-only. No production funnel or "
              "live-engine change follows from this report regardless of "
              "the verdict; promotion is a separate owner decision.")


def render_experiments_report(run_meta: dict, race_rows: List[dict],
                              gate_md: str) -> str:
    lines = ["# Sleeve A Tier 2 Backtest — Entry-Mechanics Experiments", ""]
    lines += [f"- **{k}:** {v}" for k, v in run_meta.items()]
    lines += ["", SCOPE_LOCK, "", DISCLAIMER, "", "## Race", "",
              "| variant | CAGR | maxDD | Sharpe | MAR | edge vs naive "
              "| fills | valve | missed | requotes | missed rate | exposure |",
              "|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for r in race_rows:
        rate = (f"{r['missed_fill_rate']:.1%}"
                if r["missed_fill_rate"] is not None else "n/a")
        lines.append(
            f"| {r['name']} | {r['cagr']:+.2%} | {r['max_drawdown']:.2%} "
            f"| {r['sharpe']:.2f} | {r['mar']:.2f} | {r['sharpe_edge']:+.2f} "
            f"| {r['entry_fills']} | {r['valve_entries']} "
            f"| {r['missed_fill_cancels']} | {r['requote_cancels']} "
            f"| {rate} | {r['avg_exposure']} |")
    lines += ["", "## Combined-config gate "
              "(pre-committed criteria, sweep recentred on the combined constants)",
              "", gate_md]
    return "\n".join(lines) + "\n"


def write_report(out_dir: Path, markdown: str, payload: dict) -> Path:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "report.md").write_text(markdown)
    (out_dir / "metrics.json").write_text(json.dumps(payload, indent=2, default=str))
    return out_dir
