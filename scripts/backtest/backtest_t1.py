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
    # ── Backtest parameters ───────────────────────────────────────────────────
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
    # ── Alpha engine ──────────────────────────────────────────────────────────
    ALPHA_MAX_WEIGHT,
    ALPHA_MIN_WEIGHT,
    ALPHA_W_CONF,
    ALPHA_W_DOWNSIDE,
    ALPHA_W_EV,
    ALPHA_W_MOM,
    ALPHA_W_QUAL,
    ALPHA_W_SKEW,
    BETA_HARD_CAP,
    GAMMA_DEFAULT,
    GRID_CONFIGS,
    N_ALPHA_NAMES,
    REGIME_CONTRACTION_GAMMA,
    REGIME_CONTRACTION_W_DOWNSIDE,
    REGIME_EXPANSION_GAMMA,
    REGIME_EXPANSION_W_MOM,
    VOL_HARD_CAP,
    VOL_LOOKBACK_DAYS,
    # ── Expected Return Engine ───────────────────────────────────────────────
    ER_ALPHA_W_CONF,
    ER_ALPHA_W_DOWNSIDE,
    ER_ALPHA_W_ER,
    ER_ALPHA_W_MOM,
    ER_ALPHA_W_QUAL,
    ER_ALPHA_W_SKEW,
    SQE_MAX_POSITION_CEILING_BOOST,
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

# ── Canonical gate columns (single source of truth) ───────────────────────────

GATE_COLS: List[str] = ["pass_ev", "pass_conf", "pass_risk", "pass_skew", "pass_downside"]


def normalize_bool_series(s: pd.Series) -> "pd.Series":
    """
    Coerce any gate-column dtype to strict Python bool.

    Handles:
      • bool          — passed through unchanged
      • int (0 / 1)   — 0 → False, non-zero → True
      • str           — case-insensitive "true" / "1" → True; anything else → False
      • NaN / None    — → False
    """
    if pd.api.types.is_bool_dtype(s):
        return s.fillna(False).astype(bool)

    def _coerce(v):
        if v is None:
            return False
        if isinstance(v, bool):          # bool before int — bool subclasses int
            return v
        if isinstance(v, float):
            return False if np.isnan(v) else bool(int(v))  # 1.0→True, 0.0→False
        if isinstance(v, (int, np.integer)):
            return bool(v)
        return str(v).strip().lower() in ("true", "1")

    return s.map(_coerce).astype(bool)


def _assert_gate_integrity(
    rows: List[dict],
    context: str,
    out_dir: Optional[Path] = None,
) -> None:
    """
    Hard-fail if any row's ``pass_all`` disagrees with the recomputed truth
    derived from the 5 canonical GATE_COLS.

    If ``out_dir`` is given, ``t1_qualify_mismatches.csv`` is written first
    (even when there are zero mismatches — an empty file proves a clean run).
    """
    mismatch_col_order = (
        ["month", "ticker", "pass_all_stored", "pass_all_truth",
         "scenario_valid", "t1_qualifies"] + GATE_COLS
    )

    if not rows:
        if out_dir is not None:
            pd.DataFrame(columns=mismatch_col_order).to_csv(
                out_dir / "t1_qualify_mismatches.csv", index=False
            )
            logger.info("  t1_qualify_mismatches.csv: 0 mismatch rows (clean)")
        return

    df = pd.DataFrame(rows)
    if "pass_all" not in df.columns:
        return

    for col in GATE_COLS:
        if col in df.columns:
            df[col] = normalize_bool_series(df[col])

    pass_all_truth  = df[GATE_COLS].all(axis=1)
    pass_all_stored = normalize_bool_series(df["pass_all"])
    mismatch_mask   = pass_all_stored != pass_all_truth

    # Always write the mismatches CSV (empty = clean proof)
    if out_dir is not None:
        mdf = df[mismatch_mask].copy()
        mdf["pass_all_stored"] = pass_all_stored[mismatch_mask].values
        mdf["pass_all_truth"]  = pass_all_truth[mismatch_mask].values
        out_cols = [c for c in mismatch_col_order if c in mdf.columns]
        mdf[out_cols].to_csv(out_dir / "t1_qualify_mismatches.csv", index=False)
        logger.info(
            "  t1_qualify_mismatches.csv: %d mismatch rows (0 = clean)",
            int(mismatch_mask.sum()),
        )

    if mismatch_mask.any():
        n = int(mismatch_mask.sum())
        sample_cols = ["month", "ticker", "pass_all"] + GATE_COLS
        sample = (
            df[mismatch_mask]
            .head(5)[[c for c in sample_cols if c in df.columns]]
            .to_string(index=False)
        )
        raise RuntimeError(
            f"[INTEGRITY FAILURE @ {context}] pass_all mismatches pass_all_truth "
            f"on {n} rows.\nSample:\n{sample}"
        )


# ── Audit CSV schema guarantee ────────────────────────────────────────────────

# Minimum columns required in every audit CSV row.
# Any deviation from this schema is a hard error — not a silent omission.
AUDIT_REQUIRED_COLS: List[str] = [
    "month", "ticker",
    "scenario_valid", "invalid_reason", "proxy_fallback",
    "pass_ev", "pass_conf", "pass_risk", "pass_skew", "pass_downside",
    "pass_all", "t1_qualifies",
    "ev_pct", "confidence", "risk", "skew", "downside_pct",
    "current_price",
]


def _assert_audit_schema(rows: List[dict], csv_name: str) -> None:
    """
    Hard-fail if any required column is missing from the audit rows.
    Called before writing t1_gate_audit_sample.csv and t1_gate_audit_full.csv.
    """
    if not rows:
        return
    present = set(rows[0].keys())
    missing = [c for c in AUDIT_REQUIRED_COLS if c not in present]
    if missing:
        raise RuntimeError(
            f"[SCHEMA FAILURE @ {csv_name}] Required columns missing: {missing}. "
            f"Present columns: {sorted(present)}"
        )


# ── T1 filter ─────────────────────────────────────────────────────────────────


def apply_t1_filter(signals: List[SignalRow]) -> List[SignalRow]:
    """
    Apply all T1 Accumulate criteria to a list of SignalRows.

    Qualification: scenario_valid=True AND all 5 gate thresholds met.
    rating_label and recommended_weight are NOT qualification criteria —
    they must not gate entry (see integrity spec item E).
    """
    qualified = []
    for s in signals:
        if not s.scenario_valid:
            continue
        if (
            s.expected_value >= T1_EV_THRESHOLD
            and s.confidence_score >= T1_CONFIDENCE_THRESHOLD
            and s.risk_level <= T1_RISK_MAX
            and s.asymmetry_ratio >= T1_SKEW_MIN
            and s.downside_severity <= T1_DOWNSIDE_MAX
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
        # Qualify on the 5 canonical gates only.
        # scenario_valid is already guaranteed by the valid_sigs pre-filter upstream.
        # rating_label and recommended_weight are NOT qualification criteria.
        if all(gates.values()):
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


# ── Alpha engine: continuous scoring + concentration allocation ───────────────


def get_spy_200dma(price_data: "PriceData", as_of: date) -> Optional[float]:
    """Return SPY 200-day simple moving average as of *as_of*, or None if insufficient history."""
    as_of_ts = pd.Timestamp(as_of)
    spy_hist = price_data.spy_daily[price_data.spy_daily.index <= as_of_ts].dropna()
    if len(spy_hist) < 200:
        return None
    return float(spy_hist.tail(200).mean())


def compute_6m_rel_strength(
    tickers: List[str],
    price_data: "PriceData",
    as_of: date,
) -> pd.Series:
    """
    6-month total return for each ticker minus SPY 6-month return.

    Returns a Series indexed by ticker.  NaN for tickers with < 2 price points
    in the 6-month window.
    """
    as_of_ts = pd.Timestamp(as_of)
    start_6m = as_of_ts - pd.DateOffset(months=6)

    # SPY reference return
    spy_window = price_data.spy_daily[
        (price_data.spy_daily.index >= start_6m)
        & (price_data.spy_daily.index <= as_of_ts)
    ].dropna()
    spy_ret = (
        float(spy_window.iloc[-1] / spy_window.iloc[0] - 1)
        if len(spy_window) >= 2
        else 0.0
    )

    result: Dict[str, float] = {}
    daily = price_data.daily
    for ticker in tickers:
        if ticker not in daily.columns:
            result[ticker] = float("nan")
            continue
        col = daily[ticker]
        hist = col[
            (col.index >= start_6m) & (col.index <= as_of_ts)
        ].dropna()
        if len(hist) < 2:
            result[ticker] = float("nan")
            continue
        result[ticker] = float(hist.iloc[-1] / hist.iloc[0] - 1) - spy_ret

    return pd.Series(result)


def _rank_normalize(series: pd.Series) -> pd.Series:
    """
    Rank-normalize *series* to (0, 1] scale: score_i = rank_i / N.

    Higher value in the original series → higher score.
    NaN values receive the median score (0.5) so they don't skew allocations.
    """
    n = int(series.notna().sum())
    if n == 0:
        return series.fillna(0.5)
    ranked = series.rank(method="average", na_option="keep")
    out = ranked / n
    return out.fillna(0.5)


def compute_alpha_scores(
    signals: List["SignalRow"],
    price_data: "PriceData",
    as_of: date,
    spy_200dma: Optional[float],
) -> pd.DataFrame:
    """
    Compute regime-aware composite alpha scores for all *signals*.

    Components (all rank-normalized to (0,1]):
      ev_score       — expected_value          (higher → better)
      skew_score     — asymmetry_ratio         (higher → better)
      conf_score     — confidence_score        (higher → better)
      mom_score      — 6M relative strength    (higher → better)
      qual_score     — moat_score              (higher → better)
      downside_score — downside_severity       (higher → more risky; subtracted)

    Composite:
      expansion  (SPY > 200DMA): gamma=1.8, mom_weight boosted to 0.20
      contraction (SPY ≤ 200DMA): gamma=1.2, downside_weight boosted to 0.20

    Returns a DataFrame indexed by ticker with one column per component
    plus ``alpha_score`` and ``regime``.
    """
    if not signals:
        return pd.DataFrame()

    tickers = [s.ticker for s in signals]

    ev_raw       = pd.Series({s.ticker: s.expected_value    for s in signals})
    skew_raw     = pd.Series({s.ticker: s.asymmetry_ratio   for s in signals})
    conf_raw     = pd.Series({s.ticker: s.confidence_score  for s in signals})
    qual_raw     = pd.Series({s.ticker: s.moat_score        for s in signals})
    downside_raw = pd.Series({s.ticker: s.downside_severity for s in signals})
    mom_raw      = compute_6m_rel_strength(tickers, price_data, as_of)

    ev_score       = _rank_normalize(ev_raw)
    skew_score     = _rank_normalize(skew_raw)
    conf_score     = _rank_normalize(conf_raw)
    qual_score     = _rank_normalize(qual_raw)
    downside_score = _rank_normalize(downside_raw)  # higher = more downside risk
    mom_score      = _rank_normalize(mom_raw.reindex(ev_raw.index))

    # Determine regime
    spy_current: Optional[float] = None
    try:
        spy_current = float(price_data.spy_daily.asof(pd.Timestamp(as_of)))
    except Exception:
        pass
    in_expansion = (
        spy_200dma is not None
        and spy_current is not None
        and spy_current > spy_200dma
    )

    w_mom      = REGIME_EXPANSION_W_MOM      if in_expansion else ALPHA_W_MOM
    w_downside = ALPHA_W_DOWNSIDE             if in_expansion else REGIME_CONTRACTION_W_DOWNSIDE

    alpha_score = (
        ALPHA_W_EV   * ev_score
        + ALPHA_W_SKEW * skew_score
        + ALPHA_W_CONF * conf_score
        + w_mom        * mom_score
        + ALPHA_W_QUAL * qual_score
        - w_downside   * downside_score
    )

    return pd.DataFrame({
        "ev_score":       ev_score,
        "skew_score":     skew_score,
        "conf_score":     conf_score,
        "mom_score":      mom_score,
        "qual_score":     qual_score,
        "downside_score": downside_score,
        "alpha_score":    alpha_score,
        "regime":         "expansion" if in_expansion else "contraction",
    })


def compute_alpha_scores_er(
    signals: List["SignalRow"],
    er_series: pd.Series,
    sqe_mask: pd.Series,
    price_data: "PriceData",
    as_of: date,
    spy_200dma: Optional[float],
) -> pd.DataFrame:
    """
    ER-integrated alpha scoring.

    Replaces ev_score with rank-normalized expected return as primary driver.
    SQE-eligible names get a quality boost.

    Components (all rank-normalized to (0,1]):
      er_score       — expected return (replaces ev_score)
      skew_score     — asymmetry_ratio
      conf_score     — confidence_score
      mom_score      — 6M relative strength
      qual_score     — moat_score (SQE-boosted for eligible names)
      downside_score — downside_severity (subtracted)

    Returns DataFrame with alpha_score, regime, sqe_eligible columns.
    """
    if not signals:
        return pd.DataFrame()

    tickers = [s.ticker for s in signals]

    # Rank-normalize all components
    er_score       = _rank_normalize(er_series.reindex(tickers))
    skew_raw       = pd.Series({s.ticker: s.asymmetry_ratio   for s in signals})
    conf_raw       = pd.Series({s.ticker: s.confidence_score  for s in signals})
    qual_raw       = pd.Series({s.ticker: s.moat_score        for s in signals})
    downside_raw   = pd.Series({s.ticker: s.downside_severity for s in signals})
    mom_raw        = compute_6m_rel_strength(tickers, price_data, as_of)

    skew_score     = _rank_normalize(skew_raw)
    conf_score     = _rank_normalize(conf_raw)
    qual_score     = _rank_normalize(qual_raw)
    downside_score = _rank_normalize(downside_raw)
    mom_score      = _rank_normalize(mom_raw.reindex(er_score.index))

    # SQE: boost quality score for eligible names by 25%
    sqe_reindexed = sqe_mask.reindex(qual_score.index, fill_value=False)
    adjusted_qual = qual_score.copy()
    adjusted_qual[sqe_reindexed] *= SQE_MAX_POSITION_CEILING_BOOST

    # Determine regime
    spy_current: Optional[float] = None
    try:
        spy_current = float(price_data.spy_daily.asof(pd.Timestamp(as_of)))
    except Exception:
        pass
    in_expansion = (
        spy_200dma is not None
        and spy_current is not None
        and spy_current > spy_200dma
    )

    w_mom      = REGIME_EXPANSION_W_MOM      if in_expansion else ER_ALPHA_W_MOM
    w_downside = ER_ALPHA_W_DOWNSIDE          if in_expansion else REGIME_CONTRACTION_W_DOWNSIDE

    alpha_score = (
        ER_ALPHA_W_ER    * er_score
        + ER_ALPHA_W_SKEW  * skew_score
        + ER_ALPHA_W_CONF  * conf_score
        + w_mom            * mom_score
        + ER_ALPHA_W_QUAL  * adjusted_qual
        - w_downside       * downside_score
    )

    return pd.DataFrame({
        "er_score":        er_score,
        "skew_score":      skew_score,
        "conf_score":      conf_score,
        "mom_score":       mom_score,
        "qual_score":      adjusted_qual,
        "downside_score":  downside_score,
        "alpha_score":     alpha_score,
        "regime":          "expansion" if in_expansion else "contraction",
        "sqe_eligible":    sqe_reindexed,
    })


def build_portfolio_alpha(
    alpha_df: pd.DataFrame,
    n_names: int,
    gamma: float,
    max_weight: float,
    min_weight: float,
) -> pd.Series:
    """
    Build concentration-weighted portfolio from alpha scores.

    Steps:
      1. Rank by alpha_score descending; select top *n_names*.
      2. Shift scores to be strictly positive.
      3. weight_i = score_i^gamma / Σ score_j^gamma
      4. Iteratively clip to [min_weight, max_weight] and renormalize.

    Returns an empty Series if fewer than MIN_NAMES names are available.
    """
    if alpha_df.empty:
        return pd.Series(dtype=float)

    top = alpha_df.nlargest(n_names, "alpha_score")
    if len(top) < MIN_NAMES:
        return pd.Series(dtype=float)

    scores = top["alpha_score"].copy()
    score_min = scores.min()
    if score_min <= 0:
        scores = scores - score_min + 1e-6  # shift so all values > 0

    powered = scores ** gamma
    weights = powered / powered.sum()

    # Cap/floor guardrails with iterative renormalization
    for _ in range(20):
        clipped = weights.clip(lower=min_weight, upper=max_weight)
        if (clipped == weights).all():
            break
        weights = clipped / clipped.sum()

    return weights


def _get_portfolio_beta(
    weights: pd.Series,
    signals_map: dict,
) -> float:
    """
    Weighted-average beta: Σ (w_i / Σw) × β_i.

    Uses normalized weights so partial allocations (risk-scaled) don't
    understate beta.  Returns 1.0 if no beta data is available.
    """
    total_w = float(weights.sum())
    if total_w < 1e-9:
        return 1.0
    beta = 0.0
    for ticker, w in weights.items():
        sig = signals_map.get(ticker)
        if sig is not None and sig.beta is not None:
            beta += (float(w) / total_w) * float(sig.beta)
    return beta


def _get_portfolio_trailing_vol(
    weights: pd.Series,
    price_data: "PriceData",
    as_of: date,
) -> float:
    """
    Conservative ex-ante vol estimate: Σ w_i × σ_i (assumes ρ = 1 upper bound).

    Uses VOL_LOOKBACK_DAYS trailing daily returns per ticker.
    Returns annualized volatility fraction (e.g. 0.18 for 18%).
    """
    as_of_ts = pd.Timestamp(as_of)
    daily_rets = price_data.daily_returns()
    weighted_vol = 0.0
    for ticker, w in weights.items():
        if ticker not in daily_rets.columns:
            continue
        hist = (
            daily_rets[ticker][daily_rets.index <= as_of_ts]
            .tail(VOL_LOOKBACK_DAYS)
            .dropna()
        )
        if len(hist) < 10:
            continue
        vol_i = float(hist.std()) * np.sqrt(TRADING_DAYS_PER_YEAR)
        weighted_vol += float(w) * vol_i
    return weighted_vol


def apply_risk_monitor(
    weights: pd.Series,
    signals_map: dict,
    price_data: "PriceData",
    as_of: date,
) -> pd.Series:
    """
    Proportionally scale all weights down if portfolio beta or ex-ante vol
    exceeds hard caps.  Relative ranking is preserved; cash holds excess.

    Constraints:
      portfolio beta ≤ BETA_HARD_CAP
      ex-ante portfolio vol ≤ VOL_HARD_CAP
    """
    if weights.empty:
        return weights

    port_beta = _get_portfolio_beta(weights, signals_map)
    port_vol  = _get_portfolio_trailing_vol(weights, price_data, as_of)

    scale = 1.0
    if port_beta > BETA_HARD_CAP:
        scale = min(scale, BETA_HARD_CAP / port_beta)
    if port_vol > VOL_HARD_CAP:
        scale = min(scale, VOL_HARD_CAP / port_vol)

    if scale < 1.0:
        logger.debug(
            "Risk monitor triggered: beta=%.2f vol=%.1f%% → scale=%.3f",
            port_beta, port_vol * 100, scale,
        )
        return weights * scale

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


def compute_extended_metrics(
    equity: pd.Series,
    benchmark: pd.Series,
    turnover_series: pd.Series,
    all_holdings: List[dict],
    all_portfolio_betas: List[float],
) -> dict:
    """
    Extends compute_metrics with alpha-engine-specific analytics.

    Additional fields:
      avg_portfolio_beta       — mean rebalance-date beta across full sample
      information_ratio        — annualised alpha / annualised tracking error
      rolling_3y_alpha_avg_pct — mean of the rolling 3Y excess-return series (%)
      top5_concentration_avg   — average top-5 names combined weight (%)
    """
    base = compute_metrics(equity, benchmark, turnover_series)

    # Average portfolio beta across all rebalance dates
    avg_beta = round(float(np.mean(all_portfolio_betas)), 3) if all_portfolio_betas else None

    # Information ratio
    rets = equity.pct_change().dropna()
    bret = benchmark.pct_change().dropna()
    shared = rets.index.intersection(bret.index)
    excess = rets.loc[shared] - bret.loc[shared]
    tracking_err = float(excess.std() * np.sqrt(TRADING_DAYS_PER_YEAR))
    alpha_ann     = float(excess.mean() * TRADING_DAYS_PER_YEAR)
    ir = round(alpha_ann / tracking_err, 3) if tracking_err > 1e-9 else 0.0

    # Rolling 3Y alpha: average of the rolling window series
    window = ROLLING_YEARS * TRADING_DAYS_PER_YEAR
    rolling_excess_ann = excess.rolling(window).mean() * TRADING_DAYS_PER_YEAR * 100
    valid_roll = rolling_excess_ann.dropna()
    rolling_3y_avg = round(float(valid_roll.mean()), 2) if not valid_roll.empty else 0.0

    # Top-5 average concentration across all rebalances
    top5_avg = 0.0
    if all_holdings:
        hdf = pd.DataFrame(all_holdings)
        hdf = hdf[hdf["ticker"] != "CASH"]
        if not hdf.empty:
            top5_by_date = hdf.groupby("date").apply(
                lambda g: g.nlargest(5, "weight_pct")["weight_pct"].sum()
            )
            top5_avg = round(float(top5_by_date.mean()), 1)

    base.update({
        "avg_portfolio_beta":        avg_beta,
        "information_ratio":         ir,
        "rolling_3y_alpha_avg_pct":  rolling_3y_avg,
        "top5_concentration_avg_pct": top5_avg,
    })
    return base


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


def format_alpha_summary(m: dict, n_names: int, gamma: float) -> str:
    """Performance summary for the alpha engine (replaces format_summary in run_backtest)."""
    beta_str = f"{m['avg_portfolio_beta']:.3f}" if m.get("avg_portfolio_beta") is not None else "N/A"
    lines = [
        "=" * 66,
        "  DVRG Alpha Engine — Historical Backtest Performance",
        "=" * 66,
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
        f"    Avg Portfolio β  : {beta_str:>7}",
        "",
        "  Risk-Adjusted",
        f"    Sharpe           : {m['sharpe']:>7.3f}",
        f"    Sortino          : {m['sortino']:>7.3f}",
        f"    Info Ratio       : {m.get('information_ratio', 0.0):>7.3f}",
        "",
        "  Alpha Quality",
        f"    Rolling 3Y Alpha : {m.get('rolling_3y_alpha_avg_pct', 0.0):>+7.2f}%  (avg)",
        f"    Top-5 Conc. Avg  : {m.get('top5_concentration_avg_pct', 0.0):>7.1f}%",
        "",
        "  Execution",
        f"    Hit Rate         : {m['hit_rate_pct']:>7.1f}%  (% daily excess > 0)",
        f"    Avg Monthly Turn : {m['avg_monthly_turnover_pct']:>7.2f}%",
        "=" * 66,
        "",
        "  Alpha Engine Parameters",
        f"    N names = {n_names}  |  γ = {gamma}  |  "
        f"Pos cap = {ALPHA_MAX_WEIGHT*100:.0f}%  |  "
        f"Floor = {ALPHA_MIN_WEIGHT*100:.1f}%  |  TXN = {TRANSACTION_COST_BPS:.0f} bps",
        f"    β cap = {BETA_HARD_CAP}  |  Vol cap = {VOL_HARD_CAP*100:.0f}%",
        "=" * 66,
        "",
        "  Success Criteria",
        f"    CAGR ≥ SPY+3%:  {'✓' if m['alpha_cagr'] >= 3.0 else '✗'}  "
        f"({m['alpha_cagr']:+.2f}%)",
        f"    Sharpe ≥ 0.9:   {'✓' if m['sharpe'] >= 0.9 else '✗'}  "
        f"({m['sharpe']:.3f})",
        f"    Pos alpha:      {'✓' if m['alpha_cagr'] > 0 else '✗'}",
        f"    Max DD < -50%:  {'✓' if m['max_drawdown'] > -50 else '✗'}  "
        f"({m['max_drawdown']:+.1f}%)",
        "=" * 66,
    ]
    return "\n".join(lines)


def _write_grid_comparison(results: List[dict], out_dir: Path) -> None:
    """Write grid parameter comparison table to grid_comparison.txt and stdout."""
    W = 95
    lines = [
        "=" * W,
        "  DVRG Alpha Engine — Parameter Grid Comparison",
        "=" * W,
        f"  {'Config':<7} {'γ':>5} {'N':>4}  "
        f"{'CAGR%':>7} {'Alpha%':>7} {'Sharpe':>7} {'MaxDD%':>8} "
        f"{'Roll3Y%':>8} {'IR':>7} {'β':>6}",
        "-" * W,
    ]
    for m in results:
        beta = m.get("avg_portfolio_beta") or 0.0
        lines.append(
            f"  {m.get('config', '?'):<7} "
            f"{m.get('gamma', 0)!s:>5} "
            f"{m.get('n_names', 0)!s:>4}  "
            f"{m.get('cagr', 0):>+7.2f} "
            f"{m.get('alpha_cagr', 0):>+7.2f} "
            f"{m.get('sharpe', 0):>7.3f} "
            f"{m.get('max_drawdown', 0):>+8.2f} "
            f"{m.get('rolling_3y_alpha_avg_pct', 0):>+8.2f} "
            f"{m.get('information_ratio', 0):>7.3f} "
            f"{beta:>6.3f}"
        )
    lines += [
        "=" * W,
        "",
        "  Success: CAGR ≥ SPY+3%  |  Sharpe ≥ 0.9  |  Alpha > 0  |  Max DD > -50%",
        "=" * W,
    ]
    text = "\n".join(lines)
    (out_dir / "grid_comparison.txt").write_text(text)
    print()
    print(text)
    logger.info("Grid comparison → %s/grid_comparison.txt", out_dir)


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
    monthly_sanity_rows: Optional[List[dict]] = None,
) -> str:
    """
    Produce a human-readable integrity report that summarises backtest quality.

    Terminology (post integrity fix 2026-03-01):
      pass_all     = all 5 gate thresholds met (EV / Conf / Risk / Skew / Downside)
      t1_qualifies = scenario_valid AND pass_all

    Sections
    ─────────
    1. Data coverage  — signals computed vs universe size per month
    2. Fallback rates — from fallback_tracker
    3. T1 qualifying  — monthly count of T1-qualifying names
    4. Cash %         — average uninvested allocation
    5. Turnover       — avg monthly one-way turnover
    6. Concentration  — top-5 average weight (last rebalance)
    7. Gate pass rates — individual gate rates + gate-only passes + t1_qualifies
    8. Scenario sanity — invalid reasons, base/price ratios, worst months
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
        lines += [
            "  7. T1 Gate Pass Rates  (avg across months, % of valid signals)",
            "     Individual gates:",
        ]
        for col, label in [
            ("pass_ev_rate_pct",       f"    EV ≥ {T1_EV_THRESHOLD*100:.0f}%"),
            ("pass_conf_rate_pct",     f"    Confidence ≥ {T1_CONFIDENCE_THRESHOLD:.0f}"),
            ("pass_risk_rate_pct",     f"    Risk ≤ {T1_RISK_MAX}"),
            ("pass_skew_rate_pct",     f"    Skew ≥ {T1_SKEW_MIN}"),
            ("pass_downside_rate_pct", f"    Downside ≤ {T1_DOWNSIDE_MAX*100:.0f}%"),
        ]:
            if col in gb_df.columns:
                lines.append(f"     {label:<34}: {gb_df[col].mean():.1f}%")

        # Gate-only pass rate from monthly_sanity_rows (all signals, incl. invalid)
        if monthly_sanity_rows:
            ms_df = pd.DataFrame(monthly_sanity_rows)
            if "n_pass_all" in ms_df.columns and "n_signals" in ms_df.columns:
                gate_only_rate = (
                    ms_df["n_pass_all"].sum() / max(ms_df["n_signals"].sum(), 1) * 100
                )
                lines.append("")
                lines.append(
                    f"     {'  Gate-only passes (pass_all, any scenario)':<34}: {gate_only_rate:.1f}%"
                )
            if "n_t1_qualifies" in ms_df.columns and "n_valid" in ms_df.columns:
                t1q_rate = (
                    ms_df["n_t1_qualifies"].sum() / max(ms_df["n_valid"].sum(), 1) * 100
                )
                lines.append(
                    f"     {'  T1 qualifies (scenario_valid ∧ pass_all)':<34}: {t1q_rate:.1f}%"
                )
        else:
            # Fallback: use gate_breakdown t1_qual_rate_pct
            if "t1_qual_rate_pct" in gb_df.columns:
                lines.append("")
                lines.append(
                    f"     {'  T1 qualifies (scenario_valid ∧ all gates)':<34}: {gb_df['t1_qual_rate_pct'].mean():.1f}%"
                )
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

    lines += [
        "=" * 68,
        "",
        "  Audit outputs:",
        "    t1_gate_audit_full.csv        — every signal, every month (no sampling)",
        "    t1_invalid_reasons_summary.csv — ranked invalid_reason counts",
        "    t1_sanity_metrics_by_month.csv — per-month skew/downside health",
        "=" * 68,
    ]
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
    # ── Alpha engine parameters ───────────────────────────────────────────────
    n_alpha_names: int = N_ALPHA_NAMES,
    gamma: float = GAMMA_DEFAULT,
    quiet: bool = False,  # suppress stdout for grid runs
) -> Optional[dict]:  # returns metrics dict

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
    all_portfolio_betas: List[float] = []   # per-rebalance beta for extended metrics
    rebalance_audit: List[dict] = []
    monthly_qualifying: List[dict] = []  # {month, t1_count, universe_size, cash_pct}

    # Gate breakdown accumulators (new)
    gate_breakdown_rows: List[dict] = []
    gate_audit_rows: List[dict] = []
    gate_audit_all_rows: List[dict] = []      # full universe audit (not sampled)
    monthly_sanity_rows: List[dict] = []      # per-month skew/downside distributions
    all_invalid_reasons: Dict[str, int] = {}
    valid_signal_ratios: List[float] = []  # base_target/current_price for valid signals

    prev_universe: set = set()

    # ── State machine + rotation (persistent across rebalance months) ────────
    from scripts.backtest.portfolio_state_machine import (
        PortfolioStateMachine,
        compute_breadth_signals,
        enforce_deployment_floor,
    )
    from scripts.backtest.rotation_engine import compute_sector_rotation, get_sector_multiplier

    state_machine = PortfolioStateMachine()

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

        _month_str = rb_date.strftime("%Y-%m")

        # T1 gate evaluation — kept for audit/diagnostic CSVs; NOT used for selection.
        qualified, gate_counts = _apply_t1_filter_breakdown(valid_sigs)

        # Integrity guard: verify each T1-gate-qualified signal actually passes all gates.
        for _qs in qualified:
            _qg = _eval_t1_gates(_qs)
            if not all(_qg.values()):
                raise RuntimeError(
                    f"[INTEGRITY FAILURE] Qualified signal {_qs.ticker} ({_month_str}) "
                    f"fails a T1 gate: {_qg}"
                )

        # ── Expected Return computation ──────────────────────────────────────
        from scripts.backtest.expected_return import compute_expected_returns
        from scripts.backtest.risk_budget import RiskBudgetAllocator

        er_series, sqe_mask, _er_details = compute_expected_returns(
            valid_sigs, price_data, rb_date,
        )

        # ── Alpha engine: ER-integrated scoring; select top N ────────────────
        spy_200dma_now = get_spy_200dma(price_data, rb_date)
        alpha_df = compute_alpha_scores_er(
            valid_sigs, er_series, sqe_mask,
            price_data, rb_date, spy_200dma_now,
        )

        # Select top N names by alpha score (pre-filter for risk budget)
        if not alpha_df.empty:
            top_tickers = list(
                alpha_df.nlargest(n_alpha_names, "alpha_score").index
            )
        else:
            top_tickers = []

        # Build signal map early — needed for risk monitor and holdings snapshot.
        sig_map = {s.ticker: s for s in valid_sigs}

        # ── State machine: update portfolio regime ─────────────────────────
        breadth = compute_breadth_signals(valid_sigs, price_data, rb_date)
        state_params = state_machine.update(breadth, rb_date)

        # ── Sector rotation: compute multipliers ─────────────────────────────
        rotation_df = compute_sector_rotation(valid_sigs, price_data, rb_date)

        # ── Risk Budget Allocator: covariance-based vol targeting ────────────
        new_weights = pd.Series(dtype=float)
        port_beta = 1.0

        if top_tickers:
            rb_allocator = RiskBudgetAllocator(
                vol_target=state_params.vol_target,
                vol_hard_cap=state_params.vol_hard_cap,
                min_weight=state_params.min_weight,
                max_weight=state_params.max_weight,
                sector_cap=state_params.sector_cap,
            )
            cov_matrix = rb_allocator.compute_covariance_matrix(
                top_tickers, price_data, rb_date,
            )
            indiv_vol = rb_allocator.compute_individual_vol(
                top_tickers, price_data, rb_date,
            )
            sectors = pd.Series(
                {s.ticker: s.sector for s in valid_sigs if s.ticker in top_tickers}
            )

            if not cov_matrix.empty:
                new_weights = rb_allocator.optimize_weights(
                    er_series.reindex(top_tickers),
                    cov_matrix,
                    indiv_vol,
                    sectors=sectors,
                    sqe_mask=sqe_mask.reindex(top_tickers) if not sqe_mask.empty else None,
                )
            else:
                # Fallback to alpha-weighted portfolio if covariance unavailable
                new_weights = build_portfolio_alpha(
                    alpha_df, n_alpha_names, gamma, ALPHA_MAX_WEIGHT, ALPHA_MIN_WEIGHT
                )

            # Apply sector rotation multipliers to position ceilings
            if not new_weights.empty and not rotation_df.empty:
                for ticker in new_weights.index:
                    sector = sectors.get(ticker, "Unknown")
                    sector_mult = get_sector_multiplier(rotation_df, sector)
                    max_for_ticker = state_params.max_weight * sector_mult * state_params.deployment_multiplier
                    new_weights[ticker] = min(float(new_weights[ticker]), max_for_ticker)

            # Deployment floor enforcement
            if not new_weights.empty:
                new_weights = enforce_deployment_floor(
                    new_weights, er_series, state_params,
                )

            if not new_weights.empty:
                port_beta = _get_portfolio_beta(new_weights, sig_map)
                all_portfolio_betas.append(port_beta)
                # Beta hard cap check (risk budget handles vol; beta is separate)
                if port_beta > BETA_HARD_CAP:
                    beta_scale = BETA_HARD_CAP / port_beta
                    new_weights = new_weights * beta_scale

        # ── Gate breakdown row ────────────────────────────────────────────────
        n_valid          = len(valid_sigs)
        n_invalid        = len(invalid_sigs)
        n_attempted      = signals_result.attempted_count
        n_t1_qualified   = len(qualified)           # T1-gate pass count (diagnostic only)
        n_alpha_selected = len(new_weights)         # alpha-engine selected count
        _sv              = max(n_valid, 1)
        _sa              = max(n_attempted, 1)
        _regime          = (
            alpha_df["regime"].iloc[0] if not alpha_df.empty else "unknown"
        )
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
            "t1_qualifiers_count":     n_t1_qualified,   # diagnostic
            "alpha_selected_count":    n_alpha_selected,  # active selection
            "portfolio_beta":          round(port_beta, 3),
            "regime":                  _regime,
            "success_rate_pct":        round(n_valid          / _sa * 100, 1),
            "invalid_rate_pct":        round(n_invalid        / _sa * 100, 1),
            "pass_ev_rate_pct":        round(gate_counts["pass_ev"]       / _sv * 100, 1),
            "pass_conf_rate_pct":      round(gate_counts["pass_conf"]     / _sv * 100, 1),
            "pass_risk_rate_pct":      round(gate_counts["pass_risk"]     / _sv * 100, 1),
            "pass_skew_rate_pct":      round(gate_counts["pass_skew"]     / _sv * 100, 1),
            "pass_downside_rate_pct":  round(gate_counts["pass_downside"] / _sv * 100, 1),
            "t1_qual_rate_pct":        round(n_t1_qualified   / _sv * 100, 1),
        })

        # ── Gate audit sample (deterministic RNG seed per month) ──────────────
        _rng = _random.Random(abs(hash(_month_str)) % (2 ** 31))
        _pool = all_sigs if len(all_sigs) <= audit_sample_size else _rng.sample(all_sigs, audit_sample_size)

        def _audit_row(s: "SignalRow", month: str) -> dict:
            g = _eval_t1_gates(s)
            # Canonical: pass_all = all 5 gates only (no rating_label / weight conditions)
            pass_all    = all(g.values())
            t1_qualifies = s.scenario_valid and pass_all
            return {
                "month":          month,
                "ticker":         s.ticker,
                "current_price":  round(s.current_price, 4),
                "ev_pct":         round(s.expected_value * 100, 2),
                "confidence":     round(s.confidence_score, 1),
                "risk":           s.risk_level,
                "skew":           round(s.asymmetry_ratio, 3),
                "downside_pct":   round(s.downside_severity * 100, 2),
                "pass_ev":        g["pass_ev"],
                "pass_conf":      g["pass_conf"],
                "pass_risk":      g["pass_risk"],
                "pass_skew":      g["pass_skew"],
                "pass_downside":  g["pass_downside"],
                "pass_all":       pass_all,
                "t1_qualifies":   t1_qualifies,
                "scenario_valid": s.scenario_valid,
                "invalid_reason": s.invalid_reason,
                "proxy_fallback": s.proxy_fallback,
                "missing_ebitda": s.missing_ebitda,
                "dcf_value_used": s.dcf_value_used,
                "pe_value_used":  s.pe_value_used,
                "ev_value_used":  s.ev_value_used,
            }

        for _s in _pool:
            gate_audit_rows.append(_audit_row(_s, _month_str))

        # ── Full audit — every signal this month (no sampling) ────────────────
        for _s in all_sigs:
            gate_audit_all_rows.append(_audit_row(_s, _month_str))

        # ── Per-month sanity metrics ───────────────────────────────────────────
        _all_skews     = [s.asymmetry_ratio for s in all_sigs if s.asymmetry_ratio is not None]
        _all_downs     = [s.downside_severity * 100 for s in all_sigs]
        _sanity_rows = [_audit_row(s, _month_str) for s in all_sigs]
        _n_pass_all      = sum(1 for r in _sanity_rows if r["pass_all"])
        _n_t1_qualifies  = sum(1 for r in _sanity_rows if r["t1_qualifies"])
        _n_neg_down      = sum(1 for s in all_sigs if s.downside_severity < 0)
        _n_huge_skew     = sum(1 for s in all_sigs if s.asymmetry_ratio > 20.0)
        _n_inv_skew      = sum(
            1 for s in all_sigs
            if not s.scenario_valid and "skew_unreasonable" in (s.invalid_reason or "")
        )
        monthly_sanity_rows.append({
            "month":               _month_str,
            "n_signals":           len(all_sigs),
            "n_valid":             n_valid,
            "n_invalid":           n_invalid,
            "n_pass_all":          _n_pass_all,
            "n_t1_qualifies":      _n_t1_qualifies,
            "n_skew_gt20":         _n_huge_skew,
            "n_invalid_skew":      _n_inv_skew,
            "n_neg_downside":      _n_neg_down,
            "median_skew":         round(float(np.median(_all_skews)), 3) if _all_skews else None,
            "p95_skew":            round(float(np.percentile(_all_skews, 95)), 3) if _all_skews else None,
            "median_downside_pct": round(float(np.median(_all_downs)), 2) if _all_downs else None,
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
            "[%s] universe=%d attempted=%d valid=%d invalid=%d "
            "alpha=%d(β=%.2f/%s) T1gate=%d pass(ev/conf/risk/skew/down)=%s",
            _month_str, len(universe),
            n_attempted, n_valid, n_invalid,
            n_alpha_selected, port_beta, _regime,
            n_t1_qualified, _gate_str,
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

        # Holdings snapshot  (sig_map built earlier, before risk monitor)
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
        return None

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
    metrics = compute_extended_metrics(
        portfolio_equity, benchmark_equity, turnover_series,
        all_holdings, all_portfolio_betas,
    )

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
        _assert_audit_schema(gate_audit_rows, "t1_gate_audit_sample.csv")
        pd.DataFrame(gate_audit_rows).to_csv(out_dir / "t1_gate_audit_sample.csv", index=False)
        logger.info("  t1_gate_audit_sample.csv: %d rows", len(gate_audit_rows))

    # t1_qualify_mismatches.csv + integrity assertion (hard-fail before writing full audit)
    # This assertion verifies pass_all == all(5 gates) for every row. After the fix it must
    # always be zero mismatches; a non-zero count indicates a regression.
    _assert_gate_integrity(gate_audit_all_rows, context="t1_gate_audit_full.csv", out_dir=out_dir)

    # t1_gate_audit_full.csv — complete signal universe (no sampling)
    if gate_audit_all_rows:
        _assert_audit_schema(gate_audit_all_rows, "t1_gate_audit_full.csv")
        pd.DataFrame(gate_audit_all_rows).to_csv(out_dir / "t1_gate_audit_full.csv", index=False)
        logger.info("  t1_gate_audit_full.csv: %d rows (all signals, all months)", len(gate_audit_all_rows))

    # t1_invalid_reasons_summary.csv — ranked count of every invalid_reason code
    if all_invalid_reasons:
        reasons_df = pd.DataFrame(
            sorted(all_invalid_reasons.items(), key=lambda x: -x[1]),
            columns=["invalid_reason", "count"],
        )
        total_invalid = reasons_df["count"].sum()
        reasons_df["pct_of_invalid"] = (reasons_df["count"] / max(total_invalid, 1) * 100).round(1)
        reasons_df.to_csv(out_dir / "t1_invalid_reasons_summary.csv", index=False)
        logger.info(
            "  t1_invalid_reasons_summary.csv: %d reason codes, %d total invalid",
            len(reasons_df), total_invalid,
        )

    # t1_sanity_metrics_by_month.csv — per-month skew/downside health summary
    if monthly_sanity_rows:
        pd.DataFrame(monthly_sanity_rows).to_csv(out_dir / "t1_sanity_metrics_by_month.csv", index=False)
        logger.info("  t1_sanity_metrics_by_month.csv: %d months", len(monthly_sanity_rows))

    # fallback_rate.csv + fallback check
    fallback_tracker.write_csv(out_dir / "fallback_rate.csv")
    fallback_summary = fallback_tracker.summary_line()
    logger.info("  Fallback rate: %s", fallback_summary)

    # performance_summary.txt
    summary_text = format_alpha_summary(metrics, n_names=n_alpha_names, gamma=gamma)
    (out_dir / "performance_summary.txt").write_text(summary_text)
    if not quiet:
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
        monthly_sanity_rows=monthly_sanity_rows,
    )
    (out_dir / "integrity_report.txt").write_text(integrity_text)
    if not quiet:
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
    return metrics


# ── Parameter grid ────────────────────────────────────────────────────────────


def run_parameter_grid(
    start: str,
    end: str,
    out_dir: Path,
    allow_survivorship_bias: bool = False,
    no_charts: bool = True,
    fail_on_fallback_rate: bool = False,
) -> List[dict]:
    """
    Run a full backtest for each configuration in GRID_CONFIGS and produce a
    side-by-side comparison table (grid_comparison.txt).

    Grid sets (defined in config.GRID_CONFIGS):
      A : gamma=1.3, N=15
      B : gamma=1.5, N=12  ← default
      C : gamma=2.0, N=10

    Comparison metrics: CAGR, Alpha, Sharpe, Max DD, Rolling 3Y alpha, IR, Beta.
    Data (prices + fundamentals) is re-loaded from cache for each run — no
    redundant downloads, but signal computation repeats per run.
    """
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    results: List[dict] = []
    for cfg in GRID_CONFIGS:
        cfg_name = cfg["name"]
        cfg_gamma = float(cfg["gamma"])
        cfg_n     = int(cfg["n"])
        cfg_out   = out_dir / f"grid_{cfg_name}"

        logger.info("=" * 60)
        logger.info(
            "Grid Set %s — gamma=%.1f  N=%d  → %s",
            cfg_name, cfg_gamma, cfg_n, cfg_out,
        )

        m = run_backtest(
            start=start,
            end=end,
            allow_survivorship_bias=allow_survivorship_bias,
            out_dir=cfg_out,
            no_charts=no_charts,
            fail_on_fallback_rate=fail_on_fallback_rate,
            n_alpha_names=cfg_n,
            gamma=cfg_gamma,
            quiet=True,
        )

        if m is not None:
            m["config"]  = cfg_name
            m["gamma"]   = cfg_gamma
            m["n_names"] = cfg_n
            results.append(m)
            logger.info(
                "  Grid %s: CAGR=%+.2f%%  Alpha=%+.2f%%  Sharpe=%.3f  MaxDD=%+.1f%%",
                cfg_name,
                m.get("cagr", 0),
                m.get("alpha_cagr", 0),
                m.get("sharpe", 0),
                m.get("max_drawdown", 0),
            )

    if results:
        _write_grid_comparison(results, out_dir)

    return results


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
    # ── Alpha engine CLI overrides ─────────────────────────────────────────────
    p.add_argument(
        "--gamma", type=float, default=None, metavar="FLOAT",
        help=f"Concentration exponent for power weighting (default: {GAMMA_DEFAULT})",
    )
    p.add_argument(
        "--n-names", type=int, default=None, metavar="N", dest="n_names",
        help=f"Top-N names selected each rebalance (default: {N_ALPHA_NAMES})",
    )
    _grid_desc = ", ".join(
        "gamma={} N={}".format(c["gamma"], c["n"]) for c in GRID_CONFIGS
    )
    p.add_argument(
        "--grid-test", action="store_true", default=False, dest="grid_test",
        help=(
            f"Run grid comparison across {len(GRID_CONFIGS)} parameter sets "
            f"({_grid_desc}) and write grid_comparison.txt"
        ),
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

    n_alpha = args.n_names if args.n_names is not None else N_ALPHA_NAMES
    gamma   = args.gamma   if args.gamma   is not None else GAMMA_DEFAULT

    try:
        if args.grid_test:
            run_parameter_grid(
                start=start,
                end=end,
                out_dir=Path(args.out_dir),
                allow_survivorship_bias=args.allow_survivorship_bias,
                no_charts=args.no_charts,
                fail_on_fallback_rate=args.fail_on_fallback_rate,
            )
        else:
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
                n_alpha_names=n_alpha,
                gamma=gamma,
            )
    except FallbackRateExceeded as exc:
        logger.error("FATAL: %s", exc)
        _sys.exit(1)


if __name__ == "__main__":
    main()
