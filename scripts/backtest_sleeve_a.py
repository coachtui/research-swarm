"""Phase 3D Tier 2 backtest CLI. Local only — never Railway, never cron.

  python3 scripts/backtest_sleeve_a.py fetch   # universe CSVs + OHLCV cache
  python3 scripts/backtest_sleeve_a.py run     # base run + baselines + report
  python3 scripts/backtest_sleeve_a.py sweep   # + sensitivity suite + gate
"""
import argparse
import logging
import sys
import urllib.request
from datetime import datetime
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from execution.backtest.baselines import (          # noqa: E402
    equal_weight_universe, naive_momentum, spy_buy_hold,
)
from execution.backtest.data import (               # noqa: E402
    MARKET_SYMBOLS, fetch_ohlcv, load_ohlcv,
)
from execution.backtest.metrics import (            # noqa: E402
    compute_metrics, trade_stats, yearly_log_outperformance,
)
from execution.backtest.report import (             # noqa: E402
    gate_verdict, render_report, write_report,
)
from execution.backtest.sensitivity import run_sweep     # noqa: E402
from execution.backtest.simulator import BacktestConfig, run_backtest  # noqa: E402
from execution.backtest.universe import (                # noqa: E402
    load_pit_membership, load_universe,
)
from scripts.backtest.data.sp500_constituents import (   # noqa: E402
    download_constituents_csv,
)

DATA_DIR = REPO / "data" / "backtest"
OHLCV_DIR = DATA_DIR / "ohlcv"
UNIVERSE_DIR = DATA_DIR / "universe"
PIT_CSV = DATA_DIR / "sp500_constituents.csv"
REPORTS_DIR = REPO / "reports" / "backtests"

# Mid/small breadth = current S&P 400/600 membership (what IJH/IJR track).
# Wikipedia's component lists are stable HTML tables; iShares' holdings
# CSVs sit behind JS-injected ajax URLs that return HTML to plain fetches.
WIKI_INDEXES = {
    "SP400": "https://en.wikipedia.org/wiki/List_of_S%26P_400_companies",
    "SP600": "https://en.wikipedia.org/wiki/List_of_S%26P_600_companies",
}

# Not in WIKI_INDEXES: this must not download unconditionally. It's only a
# fallback for large-cap coverage when the PIT constituents CSV is absent —
# when PIT is present, current S&P 500 members must come only from it, or
# the PIT tier's cleanliness claim is polluted.
SP500 = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"


def _download_index_holdings(name: str, url: str, dest: Path) -> None:
    """Write the index's current members as a minimal iShares-format CSV
    (Ticker / Asset Class columns) so universe.parse_ishares_csv reads it."""
    import io

    import pandas as pd

    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    html = urllib.request.urlopen(req, timeout=60).read().decode("utf-8", "replace")
    table = next(t for t in pd.read_html(io.StringIO(html))
                 if "Symbol" in [str(c) for c in t.columns])
    lines = ["Ticker,Name,Asset Class"]
    lines += [f"{str(sym).strip()},{name} member,Equity"
              for sym in table["Symbol"] if str(sym).strip()]
    dest.write_text("\n".join(lines) + "\n")


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Sleeve A Tier 2 backtest")
    sub = p.add_subparsers(dest="command", required=True)
    for name in ("fetch", "run", "sweep"):
        s = sub.add_parser(name)
        s.add_argument("--start", default="2015-01-01")
        s.add_argument("--end", default="2026-06-30")
        s.add_argument("--cash", type=float, default=100_000.0)
    return p


def cmd_fetch(ns) -> None:
    UNIVERSE_DIR.mkdir(parents=True, exist_ok=True)
    if not PIT_CSV.exists():
        try:
            download_constituents_csv(PIT_CSV)
        except Exception as exc:  # noqa: BLE001
            print(f"PIT constituents download raised: {exc}")
        if PIT_CSV.exists():
            print("downloaded PIT S&P 500 constituents")
        else:
            print(f"FAILED to obtain PIT constituents.\n"
                  f"  Run `python3 -m scripts.backtest.data.sp500_constituents "
                  f"--download` or save the canonical CSV as {PIT_CSV}.\n"
                  f"  Proceeding survivorship-biased (current members only).")
    sp500_dest = UNIVERSE_DIR / "SP500_holdings.csv"
    if not PIT_CSV.exists():
        # No PIT source at all — fall back to current S&P 500 membership so
        # large-cap coverage isn't dropped entirely.
        if not sp500_dest.exists():
            try:
                _download_index_holdings("SP500", SP500, sp500_dest)
                print(f"downloaded SP500 member list ({sp500_dest.name})")
            except Exception as exc:  # noqa: BLE001
                print(f"FAILED to download SP500 ({exc}).\n"
                      f"  Save a CSV with Ticker/Asset Class columns as {sp500_dest}")
    elif sp500_dest.exists():
        # PIT is present — a leftover Wikipedia SP500 list from an earlier
        # degraded fetch would pollute the PIT tier's cleanliness claim.
        sp500_dest.unlink()
        print(f"removed stale {sp500_dest.name} — PIT constituents present, "
              f"S&P 500 membership comes from PIT only")
    for name, url in WIKI_INDEXES.items():
        dest = UNIVERSE_DIR / f"{name}_holdings.csv"
        if dest.exists():
            continue
        try:
            _download_index_holdings(name, url, dest)
            print(f"downloaded {name} member list ({dest.name})")
        except Exception as exc:  # noqa: BLE001
            print(f"FAILED to download {name} ({exc}).\n"
                  f"  Save a CSV with Ticker/Asset Class columns as {dest}")
    universe = set(load_universe(UNIVERSE_DIR))
    if PIT_CSV.exists():
        universe |= set(load_pit_membership(PIT_CSV)["ticker"])
    if not universe:
        sys.exit("no universe sources — fetch aborted")
    print(f"universe: {len(universe)} symbols; fetching OHLCV "
          f"(first run takes a while)…")
    fetch_ohlcv(list(MARKET_SYMBOLS) + sorted(universe), OHLCV_DIR)
    print(f"cache: {len(list(OHLCV_DIR.glob('*.parquet')))} parquet files")


def _load_all(ns):
    ohlcv = load_ohlcv(OHLCV_DIR)
    if "SPY" not in ohlcv:
        sys.exit("no cached data — run `fetch` first")
    cfg = BacktestConfig(start=ns.start, end=ns.end, starting_cash=ns.cash)
    pit = load_pit_membership(PIT_CSV) if PIT_CSV.exists() else None
    static = load_universe(UNIVERSE_DIR)
    if pit is None:
        print("WARNING: no PIT constituents CSV — survivorship-biased run")
    return ohlcv, cfg, pit, static


def cmd_run(ns, with_sweep: bool) -> None:
    ohlcv, cfg, pit, static = _load_all(ns)
    pit_coverage = None
    if pit is not None:
        pit_syms = set(pit["ticker"])
        if pit_syms:
            pit_coverage = round(
                100.0 * len(pit_syms & set(ohlcv)) / len(pit_syms), 1)
    print(f"universe: {len(ohlcv)} symbols with data; running base backtest…")
    base_res = run_backtest(ohlcv, cfg, pit=pit, static_universe=static)
    base = compute_metrics(base_res.equity)
    print("base done; baselines…")
    naive_eq = naive_momentum(ohlcv, cfg, pit=pit, static_universe=static)
    baselines = {
        "naive_momentum": compute_metrics(naive_eq),
        "equal_weight": compute_metrics(
            equal_weight_universe(ohlcv, cfg, pit=pit, static_universe=static)),
        "spy": compute_metrics(spy_buy_hold(ohlcv, cfg)),
    }
    yearly = yearly_log_outperformance(base_res.equity, naive_eq)
    sweep_rows = []
    if with_sweep:
        print("sensitivity sweep (9 full runs)…")
        sweep_rows = run_sweep(ohlcv, cfg, baselines["naive_momentum"]["sharpe"],
                               pit=pit, static_universe=static)
    edges = [r["sharpe_edge"] for r in sweep_rows if r["name"] != "flat_conviction_60"]
    verdict = gate_verdict(base, baselines["naive_momentum"], yearly, edges)
    stats = trade_stats(base_res.journal, base_res.equity, cfg.starting_cash)
    meta = {"window": f"{cfg.start} → {cfg.end}", "starting_cash": cfg.starting_cash,
            "symbols": len(ohlcv), "weeks": base_res.weeks,
            "trades": len(base_res.journal),
            "pit_coverage_pct": pit_coverage if pit_coverage is not None
            else "n/a — survivorship-biased run",
            "sweep": "yes" if with_sweep else "no (run `sweep` for the full gate)",
            **stats}
    md = render_report(meta, base, baselines, yearly, sweep_rows, verdict)
    out = write_report(REPORTS_DIR / datetime.now().strftime("%Y%m%d-%H%M%S"),
                       md, {"meta": meta, "base": base, "baselines": baselines,
                            "yearly_log_outperformance": yearly,
                            "sweep": sweep_rows, "verdict": verdict,
                            "trade_stats": stats})
    import pandas as pd
    pd.DataFrame(base_res.journal).to_csv(out / "trades.csv", index=False)
    print(md)
    print(f"written: {out}/report.md (+ trades.csv, {len(base_res.journal)} rows)")


def main() -> None:
    logging.basicConfig(level=logging.WARNING)
    ns = build_parser().parse_args()
    if ns.command == "fetch":
        cmd_fetch(ns)
    else:
        cmd_run(ns, with_sweep=(ns.command == "sweep"))


if __name__ == "__main__":
    main()
