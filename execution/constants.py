"""Shared constants for the Autopilot execution layer."""

# The 11 SPDR sector ETFs — the top-down lens on where money is rotating.
SECTOR_ETFS = {
    "XLK": "Technology",
    "XLE": "Energy",
    "XLF": "Financials",
    "XLV": "Health Care",
    "XLI": "Industrials",
    "XLY": "Consumer Discretionary",
    "XLP": "Consumer Staples",
    "XLU": "Utilities",
    "XLB": "Materials",
    "XLRE": "Real Estate",
    "XLC": "Communication Services",
}

BENCHMARK = "SPY"
EQUAL_WEIGHT = "RSP"   # equal-weight S&P — RSP/SPY trend is a breadth proxy
VIX = "^VIX"

# Trading-day lookback windows for momentum
WINDOWS = {"1m": 21, "3m": 63, "6m": 126}

# ── Sleeve B (mechanical ETF rotation — Phase 2) ────────────────────────────
SLEEVE_B = "B"
SLEEVE_B_FRACTION = 0.30           # share of total account equity Sleeve B manages
SLEEVE_B_TOP_N = 3                 # ETFs held in risk_on / neutral
SLEEVE_B_BASE_WEIGHTS = (0.5, 0.3, 0.2)  # rank-proportional base weights
HYSTERESIS_RANKS = 2               # challenger must out-rank an incumbent by >= this
REGIME_INVESTED_FRACTION = {"risk_on": 1.0, "neutral": 0.7, "risk_off": 0.4}
DEFENSIVE_ETFS = ("XLP", "XLU", "XLV")  # risk_off holds only the best of these
MIN_TRADE_NOTIONAL = 50.0          # ignore dust rebalances below this
MAX_SECTOR_PCT_OF_ACCOUNT = 0.35   # hard guardrail: one sector across both sleeves
CIRCUIT_BREAKER_VS_SPY = -0.15     # sleeve return minus SPY return since inception
POSITION_QTY_TOLERANCE = 0.01      # relative qty tolerance for reconciliation
OUTLOOK_MAX_AGE_DAYS = 8           # rebalance refuses an outlook older than this
