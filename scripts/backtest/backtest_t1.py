#!/usr/bin/env python3
"""
DVRG T1 Accumulate — Historical Portfolio Backtest (10Y)
=========================================================

True point-in-time historical simulation.  No DB replay.  No LLM calls.
No look-ahead bias.  No survivorship bias (when PIT constituent CSV is provided).

Answers: "If DVRG ran monthly on the S&P 500 historically, would a
T1 Accumulate portfolio have beaten VOO/SPY?"

Usage
─────
    python scripts/backtest/backtest_t1.py

    # Date range override
    python scripts/backtest/backtest_t1.py --from 2018-01 --to 2023-12

    # Allow survivorship-biased fallback (Wikipedia current list)
    python scripts/backtest/backtest_t1.py --allow-survivorship-bias

    # Force re-download of all cached data
    python scripts/backtest/backtest_t1.py --force-refresh

Pipeline
────────
  Phase 1 — Data pre-warm
    • Determine full S&P 500 universe over the date range
    • Download and cache all daily prices (parallel batches)
    • Download and cache all fundamentals (parallel threads)

  Phase 2 — Monthly rebalance loop
    For each month-end rebalance date:
      • Get PIT S&P 500 universe
      • Compute deterministic signals for all universe members
      • Apply T1 filter → rank → select top MAX_NAMES
      • Build target weights (cap/floor/normalize)
      • Record holdings and trades

  Phase 3 — Daily return accumulation
    Between each pair of consecutive execution dates:
      • Compute daily portfolio return = Σ weight_i × daily_return_i
      • Deduct transaction costs on execution day (T+1)
      • Accumulate equity curve

  Phase 4 — Metrics + Outputs
    CAGR, vol, Sharpe, Sortino, max drawdown, hit rate, turnover
    equity_curve.csv, monthly_returns.csv, holdings_history.csv,
    trade_log.csv, performance_summary.txt,
    equity_curve.png, drawdown.png, rolling_3yr_alpha.png
"""

from __future__ import annotations

import argparse
import logging
import random as _random
import sys
from datetime import date
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from dotenv import load_dotenv
load_dotenv(PROJECT_ROOT / ".env")

from scripts.backtest.config import (
    BACKTEST_END,
    BACKTEST_START,
    BENCHMARK_FALLBACK,
    BENCHMARK_TICKER,
    BETA_WINDOW,
    CACHE_DIR,
    EXECUTION_LAG_DAYS,
    FUND_LAG_DAYS,
    FUNDAMENTALS_CACHE_DIR,
    FUNDAMENTALS_WORKERS,
    MAX_NAMES,
    MAX_WEIGHT,
    MIN_NAMES,
    MIN_WEIGHT,
    OUTPUT_DIR,
    PRICE_DOWNLOAD_BATCH_SIZE,
    PRICES_CACHE_DIR,
    REBALANCE_FREQ,
    ROLLING_YEARS,
    T1_CONFIDENCE_THRESHOLD,
    T1_DOWNSIDE_MAX,
    T1_EV_THRESHOLD,
    T1_RISK_MAX,
    T1_SKEW_MIN,
    TRANSACTION_COST_BPS,
)
from scripts.backtest.data.fundamentals import prewarm_fundamentals
from scripts.backtest.data.prices import (
    PriceData,
    get_price_as_of,
    get_total_return_series,
    next_business_day,
)
from scripts.backtest.data.sp500_constituents import (
    get_all_tickers_ever,
    get_constituents,
    set_survivorship_bias_ok,
)
from scripts.backtest.adapters.fallback_tracker import (
    FallbackRateExceeded,
    fallback_tracker,
)
from scripts.backtest.signal_snapshot import (
    SignalRow,
    UniverseSignalsResult,
    compute_universe_signals,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-7s  %(message)s",
    datefmt="%H:%M:%S",
)
# yfinance logs 404/401 HTTP errors at ERROR level for every delisted/acquired
# historical S&P 500 constituent — suppress these since we handle them gracefully.
logging.getLogger("yfinance").setLevel(logging.CRITICAL)
logger = logging.getLogger(__name__)

MONTHS_PER_YEAR = 12
TRADING_DAYS_PER_YEAR = 252


# ── T1 filter ─────────────────────────────────────────────────────────────────


def apply_t1_filter(signals: List[SignalRow]) -> List[SignalRow]:
    """Apply all T1 Accumulate criteria to a list of SignalRows."""
    qualified = []
    for s in signals:
        if (
            s.rating_label == "Accumulate"
            and s.expected_value >= T1_EV_THRESHOLD
            and s.confidence_score >= T1_CONFIDENCE_THRESHOLD
            and s.risk_level <= T1_RISK_MAX
            and s.asymmetry_ratio >= T1_SKEW_MIN
            and s.downside_severity <= T1_DOWNSIDE_MAX
            and s.recommended_weight > 0
        ):
            qualified.append(s)
    return qualified


def _eval_t1_gates(sig: SignalRow) -> dict:
    """Evaluate each T1 gate independently for one signal. Returns bool per gate."""
    return {
        "pass_ev":       sig.expected_value >= T1_EV_THRESHOLD,
        "pass_conf":     sig.confidence_score >= T1_CONFIDENCE_THRESHOLD,
        "pass_risk":     sig.risk_level <= T1_RISK_MAX,
        "pass_skew":     sig.asymmetry_ratio >= T1_SKEW_MIN,
        "pass_downside": sig.downside_severity <= T1_DOWNSIDE_MAX,
    }


def _apply_t1_filter_breakdown(
    signals: List[SignalRow],
) -> Tuple[List[SignalRow], dict]:
    """
    Apply T1 filter and return (qualified_list, per_gate_counts).

    Gate counts are independent — each count measures how many signals pass
    that gate regardless of whether they pass any other gate.
    """
    qualified = []
    gate_counts: dict = {
        "pass_ev": 0, "pass_conf": 0, "pass_risk": 0,
        "pass_skew": 0, "pass_downside": 0,
    }
    for s in signals:
        gates = _eval_t1_gates(s)
        for k, v in gates.items():
            if v:
                gate_counts[k] += 1
        if (
            s.rating_label == "Accumulate"
            and gates["pass_ev"]
            and gates["pass_conf"]
            and gates["pass_risk"]
            and gates["pass_skew"]
            and gates["pass_downside"]
            and s.recommended_weight > 0
        ):
            qualified.append(s)
    return qualified, gate_counts


# ── Portfolio construction ────────────────────────────────────────────────────


def build_portfolio(qualified: List[SignalRow]) -> pd.Series:
    """
    From T1-qualified signals build a normalized weight Series.

    Steps:
      1. If > MAX_NAMES, rank by expected_value × confidence_score, take top MAX_NAMES
      2. Start from recommended_weight
      3. Cap at MAX_WEIGHT, floor at MIN_WEIGHT
      4. Normalize to <= 1.0 (cash holds remainder)
    Returns empty Series if fewer than MIN_NAMES qualify.
    """
    if len(qualified) < MIN_NAMES:
        return pd.Series(dtype=float)

    df = pd.DataFrame([
        {
            "ticker": s.ticker,
            "recommended_weight": s.recommended_weight,
            "composite": s.expected_value * s.confidence_score,
        }
        for s in qualified
    ])
    df = df.nlargest(MAX_NAMES, "composite")

    weights = df.set_index("ticker")["recommended_weight"].copy()
    weights = weights.clip(lower=MIN_WEIGHT, upper=MAX_WEIGHT)

    total = weights.sum()
    if total > 1.0:
        # Over-allocated: cascade-normalize while respecting the cap.
        # Iteratively: normalize → re-cap → normalize until stable.
        for _ in range(10):
            weights = weights / weights.sum()
            capped = weights.clip(upper=MAX_WEIGHT)
            if (capped == weights).all():
                break
            weights = capped
    # If total <= 1.0: keep as-is; cash holds the remainder (ALLOW_CASH=True).

    return weights


# ── Trade log helpers ─────────────────────────────────────────────────────────


def compute_trades(
    old_weights: pd.Series,
    new_weights: pd.Series,
    rb_date: date,
    universe_changes: Optional[set] = None,
) -> List[dict]:
    """
    Produce a trade log by comparing old and new weight Series.

    reason codes:
      T1-ENTRY       : new position (0 → weight)
      T1-EXIT        : position closed (weight → 0) because no longer T1
      T1-REBALANCE   : size change within portfolio
      UNIVERSE-EXIT  : ticker left S&P 500 (forced close)
    """
    all_tickers = set(old_weights.index) | set(new_weights.index)
    trades = []
    for ticker in sorted(all_tickers):
        old_w = float(old_weights.get(ticker, 0.0))
        new_w = float(new_weights.get(ticker, 0.0))
        delta = new_w - old_w
        if abs(delta) < 1e-7:
            continue

        if new_w > 0 and old_w == 0:
            action, reason = "BUY", "T1-ENTRY"
        elif new_w == 0:
            reason = "UNIVERSE-EXIT" if (universe_changes and ticker in universe_changes) else "T1-EXIT"
            action = "SELL"
        else:
            action, reason = "RESIZE", "T1-REBALANCE"

        trades.append({
            "date": rb_date,
            "ticker": ticker,
            "action": action,
            "old_weight_pct": round(old_w * 100, 3),
            "new_weight_pct": round(new_w * 100, 3),
            "delta_pct": round(delta * 100, 3),
            "cost_bps": TRANSACTION_COST_BPS,
            "reason": reason,
        })
    return trades


def compute_turnover_cost(
    old_weights: pd.Series,
    new_weights: pd.Series,
) -> float:
    """
    One-way turnover cost as a fraction of portfolio value.
    cost = Σ |delta_weight| × (TXN_COST_BPS / 10_000)
    """
    all_tickers = set(old_weights.index) | set(new_weights.index)
    turnover = sum(
        abs(float(new_weights.get(t, 0.0)) - float(old_weights.get(t, 0.0)))
        for t in all_tickers
    )
    return turnover * (TRANSACTION_COST_BPS / 10_000)


# ── Return computation ────────────────────────────────────────────────────────


def compute_period_returns(
    weights: pd.Series,
    price_data: PriceData,
    exec_date: date,
    next_exec_date: date,
    cost_drag: float,
) -> Tuple[List[dict], float]:
    """
    Compute daily portfolio returns from exec_date to next_exec_date.
    Transaction costs are deducted on exec_date.

    Returns (daily_rows, period_return) where:
      daily_rows: list of {date, gross_ret, net_ret, n_holdings}
      period_return: compound net return over the full period
    """
    daily_rets = price_data.daily_returns()
    spy_rets = price_data.spy_returns()

    # Date range: exec_date through next_exec_date (exclusive)
    exec_ts = pd.Timestamp(exec_date)
    next_exec_ts = pd.Timestamp(next_exec_date)
    mask = (daily_rets.index >= exec_ts) & (daily_rets.index < next_exec_ts)
    period_dr = daily_rets.loc[mask]

    holding_tickers = [t for t in weights.index if t in period_dr.columns]

    compound = 1.0
    daily_rows = []

    for i, (dt, row) in enumerate(period_dr.iterrows()):
        gross_ret = float(
            sum(weights.get(t, 0.0) * row[t] for t in holding_tickers if pd.notna(row[t]))
        )
        # Apply transaction cost on the FIRST day only
        drag = cost_drag if i == 0 else 0.0
        net_ret = gross_ret - drag
        compound *= 1 + net_ret

        bench = float(spy_rets.get(dt, 0.0)) if dt in spy_rets.index else 0.0

        daily_rows.append({
            "date": dt.date(),
            "gross_ret": round(gross_ret, 8),
            "net_ret": round(net_ret, 8),
            "benchmark_ret": round(bench, 8),
            "n_holdings": len(holding_tickers),
            "in_cash": weights.empty,
        })

    period_return = compound - 1.0
    return daily_rows, period_return


# ── Performance metrics ───────────────────────────────────────────────────────


def compute_metrics(
    equity: pd.Series,
    benchmark: pd.Series,
    turnover_series: pd.Series,
) -> dict:
    """Compute annualised performance metrics from daily equity curves."""
    rets = equity.pct_change().dropna()
    bret = benchmark.pct_change().dropna()

    shared = rets.index.intersection(bret.index)
    rets = rets.loc[shared]
    bret = bret.loc[shared]

    n_days = len(rets)
    n_years = n_days / TRADING_DAYS_PER_YEAR

    cagr = (equity.iloc[-1] / equity.iloc[0]) ** (1 / max(n_years, 0.01)) - 1
    bench_cagr = (benchmark.iloc[-1] / benchmark.iloc[0]) ** (1 / max(n_years, 0.01)) - 1

    vol = rets.std() * np.sqrt(TRADING_DAYS_PER_YEAR)
    bench_vol = bret.std() * np.sqrt(TRADING_DAYS_PER_YEAR)

    sharpe = cagr / vol if vol > 0 else 0.0
    down_rets = rets[rets < 0]
    down_std = down_rets.std() * np.sqrt(TRADING_DAYS_PER_YEAR) if len(down_rets) > 1 else 1e-9
    sortino = cagr / down_std if down_std > 0 else 0.0

    rolling_max = equity.cummax()
    drawdown = (equity - rolling_max) / rolling_max
    max_dd = float(drawdown.min())

    excess_daily = rets.values - bret.values
    hit_rate = float(np.mean(excess_daily > 0)) * 100

    avg_turnover = float(turnover_series.mean()) if not turnover_series.empty else 0.0

    return {
        "start": str(equity.index[0].date()),
        "end": str(equity.index[-1].date()),
        "n_days": n_days,
        "n_years": round(n_years, 2),
        "cagr": round(cagr * 100, 2),
        "bench_cagr": round(bench_cagr * 100, 2),
        "alpha_cagr": round((cagr - bench_cagr) * 100, 2),
        "volatility": round(vol * 100, 2),
        "bench_vol": round(bench_vol * 100, 2),
        "sharpe": round(sharpe, 3),
        "sortino": round(sortino, 3),
        "max_drawdown": round(max_dd * 100, 2),
        "hit_rate_pct": round(hit_rate, 1),
        "avg_monthly_turnover_pct": round(avg_turnover * 100, 2),
        "total_return": round((equity.iloc[-1] - 1) * 100, 2),
        "bench_total_return": round((benchmark.iloc[-1] - 1) * 100, 2),
    }


# ── Chart generation ──────────────────────────────────────────────────────────


def save_charts(
    equity: pd.Series,
    benchmark: pd.Series,
    daily_rows: List[dict],
    out: Path,
) -> None:
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        import matplotlib.dates as mdates
    except ImportError:
        logger.warning("matplotlib not installed — charts skipped")
        return

    W, H = 13, 5

    # 1 — Equity curve (log scale option for 10Y)
    fig, ax = plt.subplots(figsize=(W, H))
    ax.plot(equity.index, equity.values, label="T1 Accumulate", lw=1.8, color="#2563EB")
    ax.plot(benchmark.index, benchmark.values, label=BENCHMARK_TICKER,
            lw=1.4, color="#9CA3AF", ls="--")
    ax.set_title("T1 Accumulate vs VOO — Daily Equity Curve", fontsize=13)
    ax.set_ylabel("Growth of $1")
    ax.legend()
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
    ax.grid(axis="y", alpha=0.3)
    fig.tight_layout()
    fig.savefig(out / "equity_curve.png", dpi=150)
    plt.close(fig)

    # 2 — Drawdown
    dd_port = (equity - equity.cummax()) / equity.cummax() * 100
    dd_bench = (benchmark - benchmark.cummax()) / benchmark.cummax() * 100

    fig, ax = plt.subplots(figsize=(W, H))
    ax.fill_between(dd_port.index, dd_port.values, 0, alpha=0.45, color="#EF4444",
                    label="T1 Accumulate")
    ax.fill_between(dd_bench.index, dd_bench.values, 0, alpha=0.25, color="#9CA3AF",
                    label=BENCHMARK_TICKER)
    ax.set_title("Drawdown (%)", fontsize=13)
    ax.set_ylabel("Drawdown %")
    ax.legend()
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
    ax.grid(axis="y", alpha=0.3)
    fig.tight_layout()
    fig.savefig(out / "drawdown.png", dpi=150)
    plt.close(fig)

    # 3 — Rolling 3-year excess (annualised)
    port_rets = equity.pct_change().dropna()
    bench_rets = benchmark.pct_change().dropna()
    shared = port_rets.index.intersection(bench_rets.index)
    excess = (port_rets.loc[shared] - bench_rets.loc[shared])
    window = ROLLING_YEARS * TRADING_DAYS_PER_YEAR
    rolling_excess_ann = excess.rolling(window).mean() * TRADING_DAYS_PER_YEAR * 100

    if not rolling_excess_ann.dropna().empty:
        fig, ax = plt.subplots(figsize=(W, H))
        ax.axhline(0, color="#6B7280", lw=0.8)
        pos = rolling_excess_ann.values >= 0
        neg = ~pos
        idx = rolling_excess_ann.index
        ax.fill_between(idx, rolling_excess_ann.values, 0,
                        where=pos, alpha=0.5, color="#22C55E", label="Outperform")
        ax.fill_between(idx, rolling_excess_ann.values, 0,
                        where=neg, alpha=0.5, color="#EF4444", label="Underperform")
        ax.set_title(f"Rolling {ROLLING_YEARS}-Year Annualised Excess Return vs VOO (%)",
                     fontsize=13)
        ax.set_ylabel("Annualised Excess %")
        ax.legend()
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
        ax.grid(axis="y", alpha=0.3)
        fig.tight_layout()
        fig.savefig(out / "rolling_3yr_alpha.png", dpi=150)
        plt.close(fig)


# ── Summary formatting ────────────────────────────────────────────────────────


def format_summary(m: dict) -> str:
    lines = [
        "=" * 62,
        "  DVRG T1 Accumulate — Historical Backtest Performance",
        "=" * 62,
        f"  Period            : {m['start']}  →  {m['end']}  ({m['n_years']:.1f} yr)",
        "",
        "  Returns",
        f"    CAGR             : {m['cagr']:>+7.2f}%   (bench: {m['bench_cagr']:+.2f}%)",
        f"    Alpha (ann.)     : {m['alpha_cagr']:>+7.2f}%",
        f"    Total Return     : {m['total_return']:>+7.2f}%   (bench: {m['bench_total_return']:+.2f}%)",
        "",
        "  Risk",
        f"    Volatility       : {m['volatility']:>7.2f}%   (bench: {m['bench_vol']:.2f}%)",
        f"    Max Drawdown     : {m['max_drawdown']:>+7.2f}%",
        "",
        "  Risk-Adjusted",
        f"    Sharpe           : {m['sharpe']:>7.3f}",
        f"    Sortino          : {m['sortino']:>7.3f}",
        "",
        "  Execution",
        f"    Hit Rate         : {m['hit_rate_pct']:>7.1f}%  (% daily excess > 0)",
        f"    Avg Monthly Turn : {m['avg_monthly_turnover_pct']:>7.2f}%",
        "=" * 62,
        "",
        "  T1 Thresholds (locked)",
        f"    EV ≥ {T1_EV_THRESHOLD*100:.0f}%  |  Confidence ≥ {T1_CONFIDENCE_THRESHOLD:.0f}  |  Risk ≤ {T1_RISK_MAX}  |"
        f"  Skew ≥ {T1_SKEW_MIN}  |  Downside ≤ {T1_DOWNSIDE_MAX*100:.0f}%",
        f"    Max names = {MAX_NAMES}  |  Pos cap = {MAX_WEIGHT*100:.0f}%  |  "
        f"Floor = {MIN_WEIGHT*100:.0f}%  |  TXN = {TRANSACTION_COST_BPS:.0f} bps",
        "=" * 62,
    ]
    return "\n".join(lines)


# ── Integrity report ──────────────────────────────────────────────────────────


def _format_integrity_report(
    metrics: dict,
    monthly_qualifying: List[dict],
    fallback_summary: str,
    all_turnovers: List[float],
    all_holdings: List[dict],
    gate_breakdown_rows: Optional[List[dict]] = None,
    all_invalid_reasons: Optional[dict] = None,
    valid_signal_ratios: Optional[List[float]] = None,
) -> str:
    """
    Produce a human-readable integrity report that summarises backtest quality.

    Sections
    ─────────
    1. Data coverage  — signals computed vs universe size per month
    2. Fallback rates — from fallback_tracker
    3. T1 qualifying  — monthly count of T1-qualifying names
    4. Cash %         — average uninvested allocation
    5. Turnover       — avg monthly one-way turnover
    6. Concentration  — top-5 average weight (last rebalance)
    """
    lines = [
        "=" * 68,
        "  DVRG T1 Accumulate — Backtest Integrity Report",
        f"  Period  : {metrics.get('start')} → {metrics.get('end')}",
        "=" * 68,
        "",
    ]

    # ── 1. Data coverage ──────────────────────────────────────────────────────
    if monthly_qualifying:
        mq_df = pd.DataFrame(monthly_qualifying)
        coverage_pct = (mq_df["signals_computed"] / mq_df["universe_size"] * 100).mean()
        lines += [
            "  1. Data Coverage",
            f"     Avg signals computed / universe : {coverage_pct:.1f}%",
            f"     Months with 0 T1 qualifiers    : "
            f"{(mq_df['t1_count'] == 0).sum()} / {len(mq_df)}",
            "",
        ]

    # ── 2. Fallback rates ─────────────────────────────────────────────────────
    lines += [
        "  2. Fallback Rate  (production engine → proxy)",
        f"     {fallback_summary}",
        "",
    ]

    # ── 3. Monthly qualifying counts ──────────────────────────────────────────
    if monthly_qualifying:
        mq_df = pd.DataFrame(monthly_qualifying)
        avg_t1 = mq_df["t1_count"].mean()
        min_t1 = mq_df["t1_count"].min()
        max_t1 = mq_df["t1_count"].max()
        lines += [
            "  3. T1 Qualifying Names",
            f"     Avg / Min / Max per month       : "
            f"{avg_t1:.1f} / {min_t1} / {max_t1}",
            "",
        ]

    # ── 4. Average cash % ─────────────────────────────────────────────────────
    if monthly_qualifying:
        avg_cash = mq_df["cash_pct"].mean()
        max_cash = mq_df["cash_pct"].max()
        lines += [
            "  4. Cash Allocation",
            f"     Average cash %                  : {avg_cash:.1f}%",
            f"     Maximum cash % (one month)      : {max_cash:.1f}%",
            "",
        ]

    # ── 5. Turnover ───────────────────────────────────────────────────────────
    if all_turnovers:
        avg_to = np.mean(all_turnovers) * 100
        max_to = np.max(all_turnovers) * 100
        lines += [
            "  5. Turnover",
            f"     Avg monthly one-way turnover    : {avg_to:.2f}%",
            f"     Peak monthly turnover           : {max_to:.2f}%",
            "",
        ]

    # ── 6. Concentration (last rebalance) ─────────────────────────────────────
    if all_holdings:
        hold_df = pd.DataFrame(all_holdings)
        last_date = hold_df["date"].max()
        last_hold = hold_df[hold_df["date"] == last_date].copy()
        last_hold = last_hold[last_hold["ticker"] != "CASH"].nlargest(5, "weight_pct")
        if not last_hold.empty:
            top5_sum = last_hold["weight_pct"].sum()
            top5_names = ", ".join(
                f"{r['ticker']}({r['weight_pct']:.1f}%)"
                for _, r in last_hold.iterrows()
            )
            lines += [
                "  6. Concentration  (last rebalance top-5)",
                f"     Top-5 combined weight          : {top5_sum:.1f}%",
                f"     Names                          : {top5_names}",
                "",
            ]

    # ── 7. Gate pass rates (avg across months) ────────────────────────────────
    if gate_breakdown_rows:
        gb_df = pd.DataFrame(gate_breakdown_rows)
        lines += ["  7. T1 Gate Pass Rates  (avg across months, % of valid signals)"]
        for col, label in [
            ("pass_ev_rate_pct",       f"  EV ≥ {T1_EV_THRESHOLD*100:.0f}%"),
            ("pass_conf_rate_pct",     f"  Confidence ≥ {T1_CONFIDENCE_THRESHOLD:.0f}"),
            ("pass_risk_rate_pct",     f"  Risk ≤ {T1_RISK_MAX}"),
            ("pass_skew_rate_pct",     f"  Skew ≥ {T1_SKEW_MIN}"),
            ("pass_downside_rate_pct", f"  Downside ≤ {T1_DOWNSIDE_MAX*100:.0f}%"),
            ("t1_qual_rate_pct",       "  ALL gates (T1 qualify)"),
        ]:
            if col in gb_df.columns:
                lines.append(f"     {label:<32}: {gb_df[col].mean():.1f}%")
        lines.append("")

    # ── 8. Scenario sanity analysis ───────────────────────────────────────────
    if gate_breakdown_rows or all_invalid_reasons or valid_signal_ratios:
        lines += ["  8. Scenario Sanity Analysis"]

        # 8a. Per-gate invalid reasons
        if all_invalid_reasons:
            total_invalid = sum(all_invalid_reasons.values())
            lines.append(f"     Total invalid scenarios           : {total_invalid}")
            lines.append("     Top invalid reasons:")
            for reason, cnt in sorted(all_invalid_reasons.items(), key=lambda x: -x[1])[:8]:
                lines.append(f"       {reason:<45}: {cnt}")
            lines.append("")

        # 8b. base_target / current_price ratio stats for valid signals
        if valid_signal_ratios:
            ratios = np.array(valid_signal_ratios)
            lines += [
                "     Base target / current price (valid signals):",
                f"       Min    : {ratios.min():.3f}",
                f"       Median : {np.median(ratios):.3f}",
                f"       Max    : {ratios.max():.3f}",
                "",
            ]

        # 8c. Worst 5 months by invalid rate
        if gate_breakdown_rows:
            gb_df = pd.DataFrame(gate_breakdown_rows)
            if "invalid_rate_pct" in gb_df.columns:
                worst5 = gb_df.nlargest(5, "invalid_rate_pct")[
                    ["month", "signals_invalid_count", "signals_attempted_count", "invalid_rate_pct"]
                ]
                lines.append("     Worst 5 months by invalid scenario rate:")
                for _, row in worst5.iterrows():
                    lines.append(
                        f"       {row['month']}  invalid={int(row['signals_invalid_count'])} "
                        f"/ attempted={int(row['signals_attempted_count'])}  "
                        f"({row['invalid_rate_pct']:.1f}%)"
                    )
                lines.append("")

    lines += ["=" * 68]
    return "\n".join(lines)


# ── Main backtest ─────────────────────────────────────────────────────────────


def run_backtest(
    start: str = BACKTEST_START,
    end: str = BACKTEST_END,
    allow_survivorship_bias: bool = False,
    force_refresh: bool = False,
    out_dir: Path = Path(OUTPUT_DIR),
    no_charts: bool = False,
    fail_on_fallback_rate: bool = True,
    fallback_rate_threshold: float = 0.05,
    audit_sample_size: int = 200,
    scenario_sanity_check: bool = True,
    sanity_min_ratio: float = 0.5,
    sanity_max_ratio: float = 2.0,
) -> None:

    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    # Reset fallback tracker for this run (safe for repeated in-process calls)
    fallback_tracker.reset()

    cache_dir = PROJECT_ROOT / CACHE_DIR
    prices_cache = PROJECT_ROOT / PRICES_CACHE_DIR
    fund_cache = PROJECT_ROOT / FUNDAMENTALS_CACHE_DIR

    if allow_survivorship_bias:
        set_survivorship_bias_ok(True)
        logger.warning("SURVIVORSHIP BIAS MODE ENABLED — results will be overstated")

    logger.info("=" * 62)
    logger.info("DVRG T1 Accumulate Historical Backtest — %s → %s", start, end)
    logger.info("=" * 62)

    # ── Phase 1: Determine full universe ─────────────────────────────────────
    logger.info("Phase 1/4: Building universe…")
    start_date = pd.Timestamp(start).date()
    end_date = pd.Timestamp(end).date()

    all_tickers = get_all_tickers_ever(start_date, end_date)
    benchmark = BENCHMARK_TICKER
    logger.info("  %d unique tickers in universe over date range", len(all_tickers))

    # ── Phase 2: Download prices ──────────────────────────────────────────────
    logger.info("Phase 2/4: Downloading prices…")
    # Start ~1yr before backtest for beta warmup
    price_start = (pd.Timestamp(start) - pd.DateOffset(years=1)).strftime("%Y-%m-%d")
    price_end = (pd.Timestamp(end) + pd.DateOffset(months=2)).strftime("%Y-%m-%d")

    price_data = get_total_return_series(
        tickers=all_tickers,
        start=price_start,
        end=price_end,
        cache_dir=prices_cache,
        batch_size=PRICE_DOWNLOAD_BATCH_SIZE,
        force_refresh=force_refresh,
        spy_ticker="SPY",
    )

    # Resolve benchmark ticker (VOO launched 2010; SPY as fallback)
    if benchmark not in price_data.daily.columns:
        logger.warning("%s not in price data — falling back to %s", benchmark, BENCHMARK_FALLBACK)
        benchmark = BENCHMARK_FALLBACK

    # ── Phase 3: Pre-warm fundamentals ───────────────────────────────────────
    logger.info("Phase 3/4: Pre-warming fundamentals cache…")
    prewarm_fundamentals(
        tickers=all_tickers,
        cache_dir=fund_cache,
        workers=FUNDAMENTALS_WORKERS,
        force_refresh=force_refresh,
    )

    # ── Phase 4: Monthly rebalance loop ──────────────────────────────────────
    logger.info("Phase 4/4: Running backtest loop…")

    rebalance_dates = pd.date_range(start=start, end=end, freq=REBALANCE_FREQ)
    logger.info("  %d month-end rebalance dates", len(rebalance_dates))

    # State
    current_weights: pd.Series = pd.Series(dtype=float)
    portfolio_value: float = 1.0
    benchmark_value: float = 1.0

    # Output accumulators
    all_daily: List[dict] = []
    all_holdings: List[dict] = []
    all_trades: List[dict] = []
    all_turnovers: List[float] = []
    rebalance_audit: List[dict] = []
    monthly_qualifying: List[dict] = []  # {month, t1_count, universe_size, cash_pct}

    # Gate breakdown accumulators (new)
    gate_breakdown_rows: List[dict] = []
    gate_audit_rows: List[dict] = []
    all_invalid_reasons: Dict[str, int] = {}
    valid_signal_ratios: List[float] = []  # base_target/current_price for valid signals

    prev_universe: set = set()

    for i, rb_ts in enumerate(rebalance_dates[:-1]):
        rb_date = rb_ts.date()
        next_rb_date = rebalance_dates[i + 1].date()

        # Execution dates (T+1)
        exec_date = next_business_day(rb_date, price_data)
        next_exec_date = next_business_day(next_rb_date, price_data)

        # PIT universe for this rebalance
        universe = get_constituents(rb_date)
        universe_set = set(universe)
        universe_exit = prev_universe - universe_set
        prev_universe = universe_set

        # Compute signals
        signals_result = compute_universe_signals(
            tickers=universe,
            as_of=rb_date,
            price_data=price_data,
            cache_dir=cache_dir,
            scenario_sanity_check=scenario_sanity_check,
            sanity_min_ratio=sanity_min_ratio,
            sanity_max_ratio=sanity_max_ratio,
        )
        all_sigs    = signals_result.all_signals
        valid_sigs   = [s for s in all_sigs if s.scenario_valid]
        invalid_sigs = [s for s in all_sigs if not s.scenario_valid]

        # Accumulate invalid reasons
        for _s in invalid_sigs:
            _r = _s.invalid_reason or "unknown"
            all_invalid_reasons[_r] = all_invalid_reasons.get(_r, 0) + 1

        # Track base/price ratios for valid signals (integrity report)
        for _s in valid_sigs:
            if _s.current_price > 0:
                valid_signal_ratios.append(_s.base_target / _s.current_price)

        qualified, gate_counts = _apply_t1_filter_breakdown(valid_sigs)
        new_weights = build_portfolio(qualified)

        # ── Gate breakdown row ────────────────────────────────────────────────
        n_valid     = len(valid_sigs)
        n_invalid   = len(invalid_sigs)
        n_attempted = signals_result.attempted_count
        n_qualified = len(qualified)
        _sv         = max(n_valid, 1)
        _sa         = max(n_attempted, 1)
        gate_breakdown_rows.append({
            "month":                   rb_date.strftime("%Y-%m"),
            "universe_count":          len(universe),
            "signals_attempted_count": n_attempted,
            "signals_success_count":   n_valid,
            "signals_invalid_count":   n_invalid,
            "pass_ev_count":           gate_counts["pass_ev"],
            "pass_conf_count":         gate_counts["pass_conf"],
            "pass_risk_count":         gate_counts["pass_risk"],
            "pass_skew_count":         gate_counts["pass_skew"],
            "pass_downside_count":     gate_counts["pass_downside"],
            "t1_qualifiers_count":     n_qualified,
            "success_rate_pct":        round(n_valid   / _sa * 100, 1),
            "invalid_rate_pct":        round(n_invalid / _sa * 100, 1),
            "pass_ev_rate_pct":        round(gate_counts["pass_ev"]       / _sv * 100, 1),
            "pass_conf_rate_pct":      round(gate_counts["pass_conf"]     / _sv * 100, 1),
            "pass_risk_rate_pct":      round(gate_counts["pass_risk"]     / _sv * 100, 1),
            "pass_skew_rate_pct":      round(gate_counts["pass_skew"]     / _sv * 100, 1),
            "pass_downside_rate_pct":  round(gate_counts["pass_downside"] / _sv * 100, 1),
            "t1_qual_rate_pct":        round(n_qualified / _sv * 100, 1),
        })

        # ── Gate audit sample (deterministic RNG seed per month) ──────────────
        _month_str = rb_date.strftime("%Y-%m")
        _rng = _random.Random(abs(hash(_month_str)) % (2 ** 31))
        _pool = all_sigs if len(all_sigs) <= audit_sample_size else _rng.sample(all_sigs, audit_sample_size)
        for _s in _pool:
            _gates   = _eval_t1_gates(_s)
            _pass_all = (
                all(_gates.values())
                and _s.rating_label == "Accumulate"
                and _s.recommended_weight > 0
                and _s.scenario_valid
            )
            gate_audit_rows.append({
                "month":          _month_str,
                "ticker":         _s.ticker,
                "current_price":  round(_s.current_price, 4),
                "ev_pct":         round(_s.expected_value * 100, 2),
                "confidence":     round(_s.confidence_score, 1),
                "risk":           _s.risk_level,
                "skew":           round(_s.asymmetry_ratio, 3),
                "downside_pct":   round(_s.downside_severity * 100, 2),
                "pass_ev":        _gates["pass_ev"],
                "pass_conf":      _gates["pass_conf"],
                "pass_risk":      _gates["pass_risk"],
                "pass_skew":      _gates["pass_skew"],
                "pass_downside":  _gates["pass_downside"],
                "pass_all":       _pass_all,
                "invalid_reason": _s.invalid_reason,
                "proxy_fallback": _s.proxy_fallback,
                "missing_ebitda": _s.missing_ebitda,
                "dcf_value_used": _s.dcf_value_used,
                "pe_value_used":  _s.pe_value_used,
                "ev_value_used":  _s.ev_value_used,
            })

        # ── Monthly qualifying snapshot ───────────────────────────────────────
        invested_pct = float(new_weights.sum()) if not new_weights.empty else 0.0
        monthly_qualifying.append({
            "month":            rb_date.strftime("%Y-%m"),
            "signal_date":      rb_date.isoformat(),
            "t1_count":         len(new_weights),
            "universe_size":    len(universe),
            "signals_computed": n_valid,
            "cash_pct":         round((1.0 - invested_pct) * 100, 2),
            "invested_pct":     round(invested_pct * 100, 2),
        })

        # ── Compact per-month diagnostic log ─────────────────────────────────
        _gate_str = (
            f"{gate_counts['pass_ev']}/{gate_counts['pass_conf']}/"
            f"{gate_counts['pass_risk']}/{gate_counts['pass_skew']}/"
            f"{gate_counts['pass_downside']}"
        )
        logger.info(
            "[%s] universe=%d attempted=%d success=%d invalid=%d T1=%d "
            "pass(ev/conf/risk/skew/down)=%s",
            _month_str, len(universe),
            n_attempted, n_valid, n_invalid, n_qualified, _gate_str,
        )

        # ── Rebalance audit row ───────────────────────────────────────────────
        bench_price_on_exec = get_price_as_of(benchmark, exec_date, price_data)
        prev_tickers = set(current_weights.index)
        new_tickers = set(new_weights.index)
        for ticker_w, wt in new_weights.items():
            ticker_price = get_price_as_of(ticker_w, exec_date, price_data)
            rebalance_audit.append({
                "signal_date": rb_date.isoformat(),
                "execution_date": exec_date.isoformat(),
                "ticker": ticker_w,
                "price_used": round(ticker_price, 4) if ticker_price else None,
                "benchmark_price": round(bench_price_on_exec, 4) if bench_price_on_exec else None,
                "weight_pct": round(wt * 100, 3),
                "is_new": "Y" if ticker_w not in prev_tickers else "N",
                "is_exit": "N",
                "t1_count": len(new_weights),
                "universe_size": len(universe),
            })
        # Record exits (positions closed this rebalance)
        for ticker_w in prev_tickers - new_tickers:
            ticker_price = get_price_as_of(ticker_w, exec_date, price_data)
            rebalance_audit.append({
                "signal_date": rb_date.isoformat(),
                "execution_date": exec_date.isoformat(),
                "ticker": ticker_w,
                "price_used": round(ticker_price, 4) if ticker_price else None,
                "benchmark_price": round(bench_price_on_exec, 4) if bench_price_on_exec else None,
                "weight_pct": 0.0,
                "is_new": "N",
                "is_exit": "Y",
                "t1_count": len(new_weights),
                "universe_size": len(universe),
            })

        # Turnover and costs
        turnover_cost = compute_turnover_cost(current_weights, new_weights)
        all_turnovers.append(turnover_cost)

        # Trade log
        trades = compute_trades(current_weights, new_weights, exec_date, universe_exit)
        all_trades.extend(trades)

        # Holdings snapshot
        sig_map = {s.ticker: s for s in signals}
        for ticker, w in new_weights.items():
            sig = sig_map.get(ticker)
            all_holdings.append({
                "date": rb_date,
                "ticker": ticker,
                "weight_pct": round(w * 100, 2),
                "expected_value_pct": round(sig.expected_value * 100, 2) if sig else None,
                "confidence_score": round(sig.confidence_score, 1) if sig else None,
                "moat_score": round(sig.moat_score, 2) if sig else None,
                "asymmetry_ratio": round(sig.asymmetry_ratio, 3) if sig else None,
                "t1_count": len(new_weights),
                "universe_size": len(universe),
            })
        if new_weights.empty:
            all_holdings.append({
                "date": rb_date,
                "ticker": "CASH",
                "weight_pct": 100.0,
                "expected_value_pct": None,
                "confidence_score": None,
                "moat_score": None,
                "asymmetry_ratio": None,
                "t1_count": 0,
                "universe_size": len(universe),
            })

        # Daily returns for this period
        daily_rows, period_return = compute_period_returns(
            weights=new_weights,
            price_data=price_data,
            exec_date=exec_date,
            next_exec_date=next_exec_date,
            cost_drag=turnover_cost,
        )

        portfolio_value *= 1 + period_return
        all_daily.extend(daily_rows)
        current_weights = new_weights

        # Annual summary line (keeps context on portfolio NAV every 12 months)
        if (i + 1) % 12 == 0:
            logger.info(
                "  Year summary  month=%d/%d  holdings=%d  portfolio=%.4f",
                i + 1, len(rebalance_dates) - 1,
                len(new_weights), portfolio_value,
            )

    # ── Build equity curves ───────────────────────────────────────────────────
    if not all_daily:
        logger.error("No daily returns computed — check price data coverage")
        return

    daily_df = pd.DataFrame(all_daily)
    daily_df["date"] = pd.to_datetime(daily_df["date"])
    daily_df = daily_df.sort_values("date").reset_index(drop=True)

    # Portfolio equity curve (compound from daily net returns)
    portfolio_equity = (1 + daily_df["net_ret"]).cumprod()
    portfolio_equity.index = daily_df["date"]

    # Benchmark equity curve (SPY daily returns)
    benchmark_equity = (1 + daily_df["benchmark_ret"]).cumprod()
    benchmark_equity.index = daily_df["date"]

    # Drawdown
    dd = (portfolio_equity - portfolio_equity.cummax()) / portfolio_equity.cummax() * 100

    # ── Metrics ───────────────────────────────────────────────────────────────
    turnover_series = pd.Series(all_turnovers)
    metrics = compute_metrics(portfolio_equity, benchmark_equity, turnover_series)

    # ── Write outputs ─────────────────────────────────────────────────────────
    logger.info("Writing outputs → %s", out_dir)

    # equity_curve.csv (daily)
    pd.DataFrame({
        "date": daily_df["date"].dt.date,
        "portfolio_value": portfolio_equity.values,
        "benchmark_value": benchmark_equity.values,
        "portfolio_dd_pct": dd.values,
        "n_holdings": daily_df["n_holdings"].values,
        "in_cash": daily_df["in_cash"].values,
    }).to_csv(out_dir / "equity_curve.csv", index=False)

    # monthly_returns.csv
    monthly_df = daily_df.copy()
    monthly_df["month"] = pd.to_datetime(monthly_df["date"]).dt.to_period("M")
    monthly_agg = monthly_df.groupby("month").agg(
        portfolio_gross=("gross_ret", lambda x: (1 + x).prod() - 1),
        portfolio_net=("net_ret", lambda x: (1 + x).prod() - 1),
        benchmark=("benchmark_ret", lambda x: (1 + x).prod() - 1),
    ).reset_index()
    monthly_agg["excess_bps"] = (
        monthly_agg["portfolio_net"] - monthly_agg["benchmark"]
    ) * 10_000
    monthly_agg.to_csv(out_dir / "monthly_returns.csv", index=False)

    # holdings_history.csv
    pd.DataFrame(all_holdings).to_csv(out_dir / "holdings_history.csv", index=False)

    # trade_log.csv
    pd.DataFrame(all_trades).to_csv(out_dir / "trade_log.csv", index=False)

    # rebalance_audit.csv
    if rebalance_audit:
        pd.DataFrame(rebalance_audit).to_csv(out_dir / "rebalance_audit.csv", index=False)
        logger.info("  rebalance_audit.csv: %d rows", len(rebalance_audit))

    # t1_gate_breakdown.csv
    if gate_breakdown_rows:
        pd.DataFrame(gate_breakdown_rows).to_csv(out_dir / "t1_gate_breakdown.csv", index=False)
        logger.info("  t1_gate_breakdown.csv: %d rows", len(gate_breakdown_rows))

    # t1_gate_audit_sample.csv
    if gate_audit_rows:
        pd.DataFrame(gate_audit_rows).to_csv(out_dir / "t1_gate_audit_sample.csv", index=False)
        logger.info("  t1_gate_audit_sample.csv: %d rows", len(gate_audit_rows))

    # fallback_rate.csv + fallback check
    fallback_tracker.write_csv(out_dir / "fallback_rate.csv")
    fallback_summary = fallback_tracker.summary_line()
    logger.info("  Fallback rate: %s", fallback_summary)

    # performance_summary.txt
    summary_text = format_summary(metrics)
    (out_dir / "performance_summary.txt").write_text(summary_text)
    print()
    print(summary_text)

    # integrity_report.txt
    integrity_text = _format_integrity_report(
        metrics=metrics,
        monthly_qualifying=monthly_qualifying,
        fallback_summary=fallback_summary,
        all_turnovers=all_turnovers,
        all_holdings=all_holdings,
        gate_breakdown_rows=gate_breakdown_rows,
        all_invalid_reasons=all_invalid_reasons,
        valid_signal_ratios=valid_signal_ratios,
    )
    (out_dir / "integrity_report.txt").write_text(integrity_text)
    print(integrity_text)

    # Charts
    if not no_charts:
        save_charts(portfolio_equity, benchmark_equity, all_daily, out_dir)

    # ── Fallback rate gate ────────────────────────────────────────────────────
    if fail_on_fallback_rate:
        try:
            fallback_tracker.check_fallback_rate(threshold=fallback_rate_threshold)
        except FallbackRateExceeded as exc:
            logger.error("BACKTEST INTEGRITY FAILED: %s", exc)
            raise

    logger.info("Done.  All outputs in: %s", out_dir)


# ── CLI ───────────────────────────────────────────────────────────────────────


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="DVRG T1 Accumulate Historical Portfolio Backtest (10Y)",
        formatter_class=argparse.RawTextHelpFormatter,
    )
    p.add_argument("--from", dest="from_date", metavar="YYYY-MM",
                   default=None, help=f"Start month (default: {BACKTEST_START[:7]})")
    p.add_argument("--to", dest="to_date", metavar="YYYY-MM",
                   default=None, help=f"End month (default: {BACKTEST_END[:7]})")
    p.add_argument("--allow-survivorship-bias", action="store_true", default=False,
                   help="Use Wikipedia current list (biased) when no PIT CSV is found")
    p.add_argument("--force-refresh", action="store_true", default=False,
                   help="Re-download all cached price and fundamental data")
    p.add_argument("--out-dir", dest="out_dir", metavar="PATH",
                   default=str(PROJECT_ROOT / OUTPUT_DIR),
                   help=f"Output directory (default: {OUTPUT_DIR})")
    p.add_argument("--no-charts", action="store_true", default=False,
                   help="Skip chart generation (faster)")
    p.add_argument("--benchmark", default=BENCHMARK_TICKER,
                   help=f"Benchmark ticker (default: {BENCHMARK_TICKER})")
    p.add_argument(
        "--fail-on-fallback-rate", action="store_true", default=False,
        dest="fail_on_fallback_rate",
        help="Exit non-zero if production-engine fallback rate exceeds 5%",
    )
    p.add_argument(
        "--fallback-rate-threshold", type=float, default=0.05,
        dest="fallback_rate_threshold",
        metavar="RATE",
        help="Fallback rate threshold for --fail-on-fallback-rate (default: 0.05)",
    )
    # ── Scenario sanity CLI flags ──────────────────────────────────────────────
    p.add_argument(
        "--audit-sample-size", type=int, default=200,
        dest="audit_sample_size",
        metavar="N",
        help="Max tickers per month written to t1_gate_audit_sample.csv (default: 200)",
    )
    p.add_argument(
        "--no-scenario-sanity", action="store_true", default=False,
        dest="no_scenario_sanity",
        help="Disable scenario sanity checks (enabled by default)",
    )
    p.add_argument(
        "--scenario-sanity-min-ratio", type=float, default=0.5,
        dest="sanity_min_ratio",
        metavar="RATIO",
        help="Min base_target/price ratio; below this → invalid (default: 0.5)",
    )
    p.add_argument(
        "--scenario-sanity-max-ratio", type=float, default=2.0,
        dest="sanity_max_ratio",
        metavar="RATIO",
        help="Max base_target/price ratio; above this → invalid (default: 2.0)",
    )
    return p.parse_args()


def main() -> None:
    import sys as _sys

    args = parse_args()

    start = args.from_date + "-01" if args.from_date else BACKTEST_START
    end = args.to_date + "-28" if args.to_date else BACKTEST_END  # conservative month end

    # Normalise to month-end
    start = pd.Timestamp(start).to_period("M").start_time.strftime("%Y-%m-%d")
    end = (pd.Timestamp(end).to_period("M") + 0).end_time.strftime("%Y-%m-%d")

    try:
        run_backtest(
            start=start,
            end=end,
            allow_survivorship_bias=args.allow_survivorship_bias,
            force_refresh=args.force_refresh,
            out_dir=Path(args.out_dir),
            no_charts=args.no_charts,
            fail_on_fallback_rate=args.fail_on_fallback_rate,
            fallback_rate_threshold=args.fallback_rate_threshold,
            audit_sample_size=args.audit_sample_size,
            scenario_sanity_check=not args.no_scenario_sanity,
            sanity_min_ratio=args.sanity_min_ratio,
            sanity_max_ratio=args.sanity_max_ratio,
        )
    except FallbackRateExceeded as exc:
        logger.error("FATAL: %s", exc)
        _sys.exit(1)


if __name__ == "__main__":
    main()
