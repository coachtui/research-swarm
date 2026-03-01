"""
T1 Accumulate — hardcoded thresholds for DVRG internal portfolio backtest.

LOCKED before running.  Do not modify after backtest is initiated.
"""

# ── T1 Accumulate Criteria ────────────────────────────────────────────────────
#
#  rating_label == "Accumulate"
#      Maps to DVRG ratings BUY / STRONG BUY.  Any other rating fails T1.
#
T1_RATING_LABELS: set[str] = {"Accumulate"}
_ACCUMULATE_RATINGS: set[str] = {"STRONG BUY", "BUY"}   # internal DVRG → T1 label

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

#  recommended_weight > 0
#      conviction_position.recommended_pct / 100.  Must be non-zero.
#      (Derived from moat_score when decision_intelligence not yet enriched.)

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
