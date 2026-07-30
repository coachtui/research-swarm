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

# Composite score weights favor recent momentum (early rotation) over long trend.
SCORE_WEIGHTS = {"1m": 0.5, "3m": 0.3, "6m": 0.2}

# ── Phase 3A: industry ETF overlay + size/style regime inputs ───────────────
# Signal instruments only — never traded. Consumed by Sleeve A / theme
# discovery only; Sleeve B reads none of this (control-group contract).
INDUSTRY_ETFS = {
    "XBI": "Biotech",
    "SMH": "Semiconductors",
    "IGV": "Software",
    "FDN": "Internet",
    "CIBR": "Cybersecurity",
    "KRE": "Regional Banks",
    "XHB": "Homebuilders",
    "ITB": "Home Construction",
    "XRT": "Retail",
    "XOP": "Oil & Gas E&P",
    "OIH": "Oil Services",
    "XME": "Metals & Mining",
    "URA": "Uranium / Nuclear",
    "SRVR": "Data Center REITs",
    "PAVE": "Infrastructure",
    "ITA": "Aerospace & Defense",
    "UFO": "Space",
    "JETS": "Airlines",
    "IHI": "Medical Devices",
}

SIZE_STYLE_ETFS = {"IWM": "small_cap", "MDY": "mid_cap"}

# Rotation threshold scaled for 19 ranks (sectors use 3 for 11 ranks).
INDUSTRY_ROTATION_MIN_RANK_GAIN = 5
# Industry pass fails (null + alert) below this many rankable industries.
MIN_INDUSTRIES_REQUIRED = 15
# IWM composite RS vs SPY beyond ±this ⇒ small/large caps leading.
SIZE_STYLE_RS_THRESHOLD = 0.01

# ── Sleeve B (mechanical ETF rotation — Phase 2) ────────────────────────────
SLEEVE_B = "B"
SLEEVE_B_FRACTION = 0.30           # share of total account equity Sleeve B manages
SLEEVE_B_TOP_N = 3                 # ETFs held in risk_on / neutral
SLEEVE_B_BASE_WEIGHTS = (0.5, 0.3, 0.2)  # rank-proportional base weights
HYSTERESIS_RANKS = 2               # challenger must out-rank an incumbent by >= this
REGIME_INVESTED_FRACTION = {"risk_on": 1.0, "neutral": 0.7, "risk_off": 0.4}
# Sleeve A thesis-hold exposure floors (owner ruling 2026-07-10). Sleeve B
# (control) keeps REGIME_INVESTED_FRACTION above — never merge these.
SLEEVE_A_INVESTED_FRACTION = {"risk_on": 1.0, "neutral": 0.9, "risk_off": 0.75}
DEFENSIVE_ETFS = ("XLP", "XLU", "XLV")  # risk_off holds only the best of these
MIN_TRADE_NOTIONAL = 50.0          # ignore dust rebalances below this
MAX_SECTOR_PCT_OF_ACCOUNT = 0.35   # hard guardrail: one sector across both sleeves
CIRCUIT_BREAKER_VS_SPY = -0.15     # sleeve return minus SPY return since inception
POSITION_QTY_TOLERANCE = 0.01      # relative qty tolerance for reconciliation
OUTLOOK_MAX_AGE_DAYS = 8           # rebalance refuses an outlook older than this

# ── Phase 3B: LLM-discovered theme baskets (Sleeve A signal layer 3) ─────────
# Theme membership NEVER buys a stock — themes pick hunting grounds only.
MAX_ACTIVE_THEMES = 12
MIN_THEME_CONSTITUENTS = 5          # validated names required to activate/rank
MAX_THEME_CONSTITUENTS = 20         # bounds the Sunday batch download (≤240 tickers)
THEME_ADV_FLOOR_USD = 1_000_000.0   # avg daily dollar volume floor
THEME_MCAP_FLOOR_USD = 100_000_000.0
DELTA_AUTO_APPLY_CONFIDENCE = 0.7   # weekly delta below this journals but doesn't apply
THEME_ROTATION_MIN_RANK_GAIN = 5    # same scale as industries
THEME_HISTORY_WEEKS = 12            # sparkline series length (current membership)
THEME_REASONING_MODEL = "claude-sonnet-5"
THEME_DELTA_MODEL = "claude-haiku-4-5"
THEME_WEB_SEARCH_MAX_USES = 8
THEME_DELTA_WEB_SEARCH_MAX_USES = 4  # verification budget only, not research

# ── Phase 3C: Sleeve A funnel + small-cap guardrails (SHADOW MODE) ──────────
# Spec: docs/superpowers/specs/2026-07-09-phase3c-sleeve-a-funnel-design.md
# Sleeve A places NO real orders until the Phase 3D backtest gate flips it.
SLEEVE_A = "A"
SLEEVE_A_FRACTION = 0.70            # share of account equity Sleeve A manages
SLEEVE_A_TARGET_POSITIONS = 10      # intended book shape — NEVER a forcing rule
SLEEVE_A_MAX_POSITIONS = 15         # hard cap
ENTRY_WEIGHT_MIN = 0.03             # conviction band at entry (of sleeve equity)
ENTRY_WEIGHT_MAX = 0.12
RISK_TRIM_CEILING = 0.20            # only above this is a winner ever trimmed…
RISK_TRIM_TARGET = 0.12             # …back to here; journaled risk_trim, not a signal
RETIRED_THEME_EXIT_CONVICTION = 50.0  # review re-score (hunting_bonus=0) must clear this

LIGHT_RUNS_PER_WEEK = 20            # numbers-only runs (~$0.10–0.15 each)
FULL_RUNS_PER_WEEK = 10             # entry handshake budget (~$0.51 avg each)
HOLDING_STALE_WEEKS = 6             # holding report older than this claims a light slot
FRESH_REPORT_DAYS = 7               # reports younger than this ride free

EXTENSION_ATR_LIMIT = 1.5           # >this many ATRs above 20d SMA ⇒ "extended"
PATIENT_LIMIT_TTL_WEEKS = 2         # extended entries wait this long for a pullback
TRAILING_STOP_ATR_MULT = 2.5        # stop = high-water close − this × ATR
ADV_POSITION_CAP_PCT = 0.01         # position ≤ 1% of 20d dollar ADV
VOL_CEILING_SLEEVE_RISK = 0.0075    # 1-ATR day move costs ≤ 0.75% of sleeve
SMALL_CAP_HAIRCUT_BELOW = 1_000_000_000.0   # conviction haircut under $1B mcap
SMALL_CAP_HAIRCUT_MIN_MULT = 0.70   # haircut floor (at/below FUNNEL_MCAP_FLOOR)
OUTCOMPETE_MARGIN = 10.0            # challenger must beat weakest holding by this
MAX_THEME_PCT_OF_SLEEVE = 0.35      # aggregate cap per theme (overlaps double-count)
FUNNEL_MCAP_FLOOR = 150_000_000.0
FUNNEL_PRICE_FLOOR = 2.0
FUNNEL_INDUSTRY_TOP_N = 5           # industries whose ETF holdings enter the universe
FUNNEL_HOLDINGS_PER_ETF = 10
STALENESS_DECAY_PER_WEEK = 0.02     # conviction multiplier loss per week of report age
STALENESS_DECAY_FLOOR = 0.60
CONVICTION_BUY_BONUS = 5.0          # points (0–100 scale); SELL is a veto, not a score
LIGHT_SENTIMENT_MODEL = "claude-haiku-4-5"
LIGHT_SENTIMENT_MAX_HEADLINES = 25

# ── Thesis-hold review triggers (spec 2026-07-10-sleeve-a-thesis-hold-redesign) ─
DCA_RUNGS = (0.20, 0.30, 0.40)       # drawdown-from-high add/review levels
DCA_TRANCHE_FRACTION = 0.5           # ADD buys half a fresh entry's notional
EARNINGS_DIVERGENCE_DD = 0.15        # drawdown floor for the "MU signal"
EARNINGS_DIVERGENCE_MAX_DAYS = 14    # two weekly passes wide (Mon-cutoff leak)
CONCENTRATION_REVIEW_WEIGHT = 0.20   # weight that TRIGGERS a review (never sells)
TRIM_FALLBACK_TARGET = 0.15          # owner ruling 2026-07-11: 20% triggers, trim to 15%
RUNUP_REVIEW_GAIN = 0.25             # price gain threshold for review trigger
REDUCE_TRANCHE_FRACTION = 0.25       # REDUCE buys this fraction of a tranche

# Weights must each sum to 1.0 (tested).
CONVICTION_WEIGHTS = {
    "fair_value_gap": 0.30,
    "fundamental": 0.20,
    "flow": 0.20,
    "momentum": 0.20,
    "hunting_ground": 0.10,
}
SCREEN_WEIGHTS = {
    "momentum": 0.40,
    "trend": 0.20,
    "liquidity": 0.15,
    "quality": 0.15,
    "hunting_ground": 0.10,
}

# ── Thesis-first entry redesign (spec 2026-07-27-thesis-first-entry-redesign) ─
# The weekly memo is the ONLY buy authority. Stages gate entry legality;
# crowded/priced fire reviews (existing sell authority), never auto-sell.
THESIS_MEMO_MODEL = "claude-sonnet-5"
THESIS_WEB_SEARCH_MAX_USES = 15     # pointed at leading indicators, not news
# The memo reconciles + evidences 6+ theses with search citations — it does
# not fit the 16k budget sized for theme-discovery JSON (truncation guard
# fired on the 2026-07-28 first live pass).
THESIS_MEMO_MAX_TOKENS = 32768
# Entry veto (spec §4). Replaces reading one boolean out of a ~$0.51 swarm run
# whose fair value and size recommendation the engine never consumed. Two
# fields out, so far less to drift than a full manager blob.
DISQUALIFIER_MODEL = "claude-haiku-4-5"
DISQUALIFIER_WEB_SEARCH_MAX_USES = 3
# Weekly macro strategist. It was the only LLM here without search, while its
# whole job is "what is happening in the world" — it could describe the tape
# but never explain it.
STRATEGIST_MODEL = "claude-sonnet-5"
STRATEGIST_WEB_SEARCH_MAX_USES = 8
THESIS_STAGES = ("pre_consensus", "catching_on", "crowded", "priced")
ENTRY_LEGAL_STAGES = ("pre_consensus", "catching_on")
THESIS_ROLES = ("anchor", "pure_play", "catalyst")
# conviction 0..1 maps linearly inside the role's band (of sleeve equity);
# every ceiling in size_thesis_entry only shrinks.
ROLE_BANDS = {
    "anchor": (0.08, ENTRY_WEIGHT_MAX),
    "pure_play": (0.05, 0.09),
    "catalyst": (ENTRY_WEIGHT_MIN, 0.05),
}
THESIS_LEDGER_WEEKS = 8             # memo context window into its own past

# ── Quarterly 13F study pass (spec §5) — a CURRICULUM, never copy-trading ────
# Tickers seen in filings carry ZERO order authority (guard-tested in
# tests/test_thesis_study_guards.py).
TRUSTED_FUNDS_13F = [
    {"name": "Situational Awareness LP",
     # Both registrants file; history is merged and deduped by period.
     "ciks": ["0002045724", "0002038540"]},
]
STUDY_MODEL = "claude-sonnet-5"
STUDY_MAX_TOKENS = 32768
STUDY_WEB_SEARCH_MAX_USES = 15   # pointed at the entry WINDOW's news, not today's
STUDY_QUARTERS_BACK = 8          # filing history for first-appearance reconstruction
STUDY_MATERIAL_DELTA = 0.20      # |Δvalue|/prior ≥ 20% counts as a material resize
STUDY_TOP_WEIGHT_PCT = 3.0       # positions ≥ this % of book are studied regardless
SEC_EDGAR_USER_AGENT = "DVRG Autopilot tui@tuialailima.com"  # SEC fair-access rule

# ── Compounding method rulebook (Phase B2) ───────────────────────────────────
# The rulebook is the memo's prompt-facing curriculum. It carries METHOD ONLY —
# no issuers, cusips, weights, or values (guard-tested).
RULEBOOK_MAX_RULES = 25          # revise must retire to stay under; never truncate silently
RULEBOOK_MODEL = "claude-sonnet-5"
RULEBOOK_MAX_TOKENS = 32768      # revise emits verdicts + calibration, no web search
