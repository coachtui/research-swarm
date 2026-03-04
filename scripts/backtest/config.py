"""
T1 Accumulate — hardcoded thresholds for DVRG internal portfolio backtest.

LOCKED before running.  Do not modify after backtest is initiated.
"""

# ── T1 Accumulate Criteria ────────────────────────────────────────────────────
#
#  T1 qualification = scenario_valid AND all 5 gate thresholds below.
#
#  NOT eligibility gates (allocation / presentation only):
#    rating_label  — diagnostic field; moat≥7.0 earns "Accumulate" label but
#                    does NOT gate T1 entry (fix: integrity spec 2026-03-01).
#    recommended_weight — starting allocation hint; may be 0.0 for moat<6.0;
#                         portfolio builder floors it at MIN_WEIGHT anyway.
#    moat_score   — used to set risk_level and recommended_weight; not a gate.
#
_ACCUMULATE_RATINGS: set[str] = {"STRONG BUY", "BUY"}   # DVRG label → "Accumulate"

#  expected_value >= T1_EV_THRESHOLD
#      Expected return = (probability-weighted price target - current_price) / current_price
#      0.15 = 15% minimum expected return to qualify.
T1_EV_THRESHOLD: float = 0.15

#  confidence_score >= T1_CONFIDENCE_THRESHOLD
#      Blended valuation confidence score 0–100.  55 = "Moderate" floor.
T1_CONFIDENCE_THRESHOLD: float = 55.0

#  risk_level <= T1_RISK_MAX
#      Encoded: Low=1, Medium=2, High=3.  Max = Medium.
T1_RISK_MAX: int = 2
RISK_LEVEL_ENCODE: dict[str, int] = {"Low": 1, "Medium": 2, "High": 3}

#  asymmetry_ratio >= T1_SKEW_MIN
#      asymmetry_ratio = (bull_target - current_price) / (current_price - bear_target)
#      1.3 = upside must be at least 1.3× the downside.
T1_SKEW_MIN: float = 1.3

#  downside_severity <= T1_DOWNSIDE_MAX
#      downside_severity = (current_price - bear_target) / current_price
#      NOTE: filter uses <=, not >=.  Bear-case loss must not exceed 30%.
#      T1_DOWNSIDE_MAX is a ceiling, not a floor.
T1_DOWNSIDE_MAX: float = 0.30

# ── Portfolio Construction ────────────────────────────────────────────────────
MAX_NAMES: int = 25          # if > 25 qualify, rank by EV × confidence; take top 25
MAX_WEIGHT: float = 0.08     # 8% position cap
MIN_WEIGHT: float = 0.01     # 1% position floor
MIN_NAMES: int = 3           # fewer than this → remainder goes to cash

# ── Transaction Costs ─────────────────────────────────────────────────────────
TRANSACTION_COST_BPS: float = 10.0   # 10 bps per side (open or close)

# ── Benchmark ─────────────────────────────────────────────────────────────────
BENCHMARK_TICKER: str = "VOO"

# ── Rolling Performance Window ────────────────────────────────────────────────
ROLLING_YEARS: int = 3        # rolling window for relative-performance chart

# ── Output directory (relative to project root) ───────────────────────────────
OUTPUT_DIR: str = "scripts/backtest/output"

# ── Historical Backtest Parameters ────────────────────────────────────────────
BACKTEST_START: str = "2016-01-01"
BACKTEST_END: str = "2025-12-31"

# Rebalance schedule: "ME" = month-end (pandas offset alias)
REBALANCE_FREQ: str = "ME"

# Execution lag: trades execute at T+1 close after rebalance signal date
EXECUTION_LAG_DAYS: int = 1

# Fundamental data look-ahead protection
# Quarter-end date + FUND_LAG_DAYS must be <= as_of_date before data is usable.
FUND_LAG_DAYS: int = 60

# ── Cache directories (relative to project root) ──────────────────────────────
CACHE_DIR: str = "scripts/backtest/data/cache"
PRICES_CACHE_DIR: str = "scripts/backtest/data/cache/prices"
FUNDAMENTALS_CACHE_DIR: str = "scripts/backtest/data/cache/fundamentals"

# ── Data providers ────────────────────────────────────────────────────────────
# S&P 500 point-in-time constituents CSV (relative to project root).
# Must exist unless --allow-survivorship-bias flag is passed.
# Download with: python -m scripts.backtest.data.sp500_constituents --download
SP500_CONSTITUENTS_CSV: str = "data/sp500_historical_constituents.csv"

# Tickers per yfinance batch download
PRICE_DOWNLOAD_BATCH_SIZE: int = 50

# Market index for beta computation
MARKET_INDEX_TICKER: str = "SPY"

# Rolling beta window (trading days)
BETA_WINDOW: int = 252

# Benchmark with fallback if insufficient VOO history (VOO launched 2010)
BENCHMARK_FALLBACK: str = "SPY"

# Number of parallel workers for fundamentals pre-warm
# 3 workers avoids Yahoo Finance 401/crumb expiry from too many concurrent requests
FUNDAMENTALS_WORKERS: int = 3

# Cache format: "parquet" (preferred, requires pyarrow) or "pickle" (fallback)
# Auto-detected at runtime.
CACHE_FORMAT: str = "auto"

# ── Alpha Engine (Continuous Scoring) ─────────────────────────────────────────
#
#  Replaces binary T1 gate filter with rank-normalized composite alpha score
#  and concentration-weighted capital allocation.
#
#  Selection: top N_ALPHA_NAMES by alpha_score each rebalance.
#  Weighting: w_i = score_i^gamma / Σ score_j^gamma, then cap/floor.

#  Top-N names selected each rebalance (no minimum score threshold).
N_ALPHA_NAMES: int = 12

#  Concentration exponent.  Higher γ → more capital to top-ranked names.
GAMMA_DEFAULT: float = 1.5

#  Position size guardrails (alpha engine only; replaces old 1%/8% bounds).
ALPHA_MAX_WEIGHT: float = 0.20   # 20% max per position
ALPHA_MIN_WEIGHT: float = 0.005  # 0.5% min per position

# ── Portfolio Risk Monitor ─────────────────────────────────────────────────────
BETA_HARD_CAP: float = 1.5      # scale all weights down if Σ w_i β_i > cap
VOL_HARD_CAP: float = 0.25      # scale all weights down if ex-ante vol > cap
VOL_LOOKBACK_DAYS: int = 63     # trailing window (≈ 3 months) for individual vol

# ── Alpha Score Component Weights (base regime) ────────────────────────────────
#  All components are rank-normalized to [0, 1] before weighting.
#  Composite = Σ positive_terms − downside_penalty.
ALPHA_W_EV: float = 0.35        # expected-value percentile
ALPHA_W_SKEW: float = 0.20      # asymmetry-ratio percentile
ALPHA_W_CONF: float = 0.15      # confidence-score percentile
ALPHA_W_MOM: float = 0.15       # 6-month relative-strength percentile
ALPHA_W_QUAL: float = 0.10      # moat-score (quality) percentile
ALPHA_W_DOWNSIDE: float = 0.15  # downside-severity percentile (subtracted)

# ── Regime Overlay ─────────────────────────────────────────────────────────────
#  SPY price vs SPY 200-day MA determines regime.

#  Expansion  (SPY > 200DMA): pro-cyclical — boost momentum, higher γ.
REGIME_EXPANSION_GAMMA: float = 1.8
REGIME_EXPANSION_W_MOM: float = 0.20   # replaces ALPHA_W_MOM in expansion

#  Contraction (SPY ≤ 200DMA): defensive — increase downside penalty, lower γ.
REGIME_CONTRACTION_GAMMA: float = 1.2
REGIME_CONTRACTION_W_DOWNSIDE: float = 0.20  # replaces ALPHA_W_DOWNSIDE in contraction

# ── Expected Return Engine ────────────────────────────────────────────────────
#
#  Decomposes expected return into four structural components.
#  Replaces binary T1 EV gate with continuous gradient allocation.
#
#  ER = w_growth * ForwardEPSGrowth
#     + w_multiple * MultipleExpansionPotential
#     + w_capital * CapitalReturnYield
#     - w_macro * MacroRiskDiscount

ER_W_GROWTH: float = 0.35       # forward EPS growth contribution weight
ER_W_MULTIPLE: float = 0.30     # valuation discount gradient weight
ER_W_CAPITAL: float = 0.15      # shareholder yield proxy weight
ER_W_MACRO: float = 0.20        # beta-adjusted macro risk discount weight

# ── Structural Quality Elasticity (SQE) ──────────────────────────────────────
#
#  When quality >= 85th pctile AND eps_revision_positive AND rotation_favorable:
#    → Reduce valuation penalty by 50%
#    → Increase max position ceiling by 25%
#  This prevents suppression of high-quality growth names (NVDA test case).

SQE_QUALITY_PERCENTILE: float = 0.85        # 85th percentile threshold
SQE_VALUATION_PENALTY_REDUCTION: float = 0.50  # 50% boost to multiple expansion
SQE_MAX_POSITION_CEILING_BOOST: float = 1.25   # 25% increase to max position

# ── ER-Integrated Alpha Score Weights ─────────────────────────────────────────
#  Same structure as ALPHA_W_* but with ER replacing EV as primary driver.

ER_ALPHA_W_ER: float = 0.40          # expected return (replaces ALPHA_W_EV=0.35)
ER_ALPHA_W_SKEW: float = 0.15        # asymmetry ratio (was 0.20)
ER_ALPHA_W_CONF: float = 0.15        # confidence score (unchanged)
ER_ALPHA_W_MOM: float = 0.15         # 6M relative strength (unchanged)
ER_ALPHA_W_QUAL: float = 0.10        # moat score / quality (unchanged)
ER_ALPHA_W_DOWNSIDE: float = 0.15    # downside severity (unchanged)

# ── Parameter Grid Test Sets ───────────────────────────────────────────────────
#  Compared on: CAGR, Alpha, Sharpe, Max DD, Rolling 3Y excess return.
GRID_CONFIGS: list = [
    {"name": "A", "gamma": 1.3, "n": 15},
    {"name": "B", "gamma": 1.5, "n": 12},   # default config
    {"name": "C", "gamma": 2.0, "n": 10},
]
