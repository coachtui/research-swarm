// GENERATED FILE — DO NOT EDIT.
//
// Source of truth: research_swarm/contracts/report.py (AnalysisReport).
// Regenerate with:  python scripts/generate_report_types.py
// CI fails if this file is out of date with the Python contract.


export interface Catalyst {
  description: string
  /** ISO date or textual window, e.g. '2026-Q4' */
  expected_date?: string | null
  direction?: Direction
}

/** The single authoritative 'what to do'. Every consumer reads this; */
export interface Decision {
  rating: Rating
  /** One line: score, thresholds, and any overrides applied (e.g. 'quality 7.4 → BUY; technical 3.8 gated to HOLD') */
  rating_basis: string
  risk_level: RiskLevel
  /** High / Medium / Low, rule-derived */
  conviction: string
  is_watchlist_candidate: boolean
  entry_zone_low?: number | null
  entry_zone_high?: number | null
  stop_loss?: number | null
  /** Percentage points (2.5 means 2.5% of portfolio) */
  starter_allocation_pct?: number | null
  max_allocation_pct?: number | null
  tranche_plan?: TrancheStage[]
  upgrade_triggers?: string[]
  downgrade_triggers?: string[]
  thesis_break_conditions?: string[]
}

export type Direction = "bullish" | "neutral" | "bearish"

/** Cross-signal divergence read (e.g. news bearish vs institutions buying). */
export interface Divergence {
  detected?: boolean
  /** e.g. 'sentiment-vs-flows', 'fundamentals-vs-price' */
  kind?: string | null
  score?: number | null
  summary?: string | null
}

/** Market state plus the themes that apply to this company. */
export interface MacroContext {
  /** risk-on | risk-off | mixed */
  regime?: string | null
  regime_rationale?: string | null
  backdrop?: string | null
  themes?: MacroTheme[]
  /** How many themes were screened before exposure filtering */
  themes_considered?: number
  /** S&P 500 1-month return % */
  market_return_1m?: number | null
  /** S&P 500 3-month return % */
  market_return_3m?: number | null
  vix_level?: number | null
  /** 10Y minus 3M, in pp */
  yield_curve_slope?: number | null
  sector_leaders?: string[]
  sector_laggards?: string[]
  as_of?: string | null
}

/** A live macro/geopolitical theme with a concrete channel to this company. */
export interface MacroTheme {
  name: string
  summary?: string | null
  /** escalating | stable | de-escalating */
  status: string
  /** headwind | tailwind | mixed */
  direction: string
  /** Generic mechanism by which it reaches company results */
  transmission: string
  /** The concrete link to this company (mechanical screen) */
  why_relevant: string
  /** high | moderate — mechanical screen strength */
  relevance: string
  /** high | medium | low */
  confidence: string
  evidence?: string | null
  /** How this theme specifically reaches THIS company */
  company_impact?: string | null
  /** high | moderate | low — analyst judgment of earnings impact */
  materiality?: string | null
  /** Whether the effect is in reported results or still prospective */
  already_visible?: string | null
}

/** What changed since this user's last analysis of the same ticker. */
export interface PreviousAnalysisDelta {
  prior_analysis_id: string
  prior_date: string
  days_since: number
  /** e.g. 'HOLD → BUY'; None if unchanged */
  rating_change?: string | null
  quality_score_change?: number | null
  price_change_pct?: number | null
  new_risks?: string[]
  resolved_risks?: string[]
  summary?: string | null
}

export interface PriceTargets {
  current_price: number
  fair_value_low?: number | null
  fair_value_mid?: number | null
  fair_value_high?: number | null
  bull?: TargetCase | null
  base?: TargetCase | null
  bear?: TargetCase | null
  /** Computed here once; the UI must not recompute it */
  probability_weighted_ev?: number | null
  /** DCF / multiples / comparables / heuristic */
  methodology: string
  confidence_score: number
  /** True when targets were derived from a scoring heuristic rather than a valuation model. The UI must label these differently. */
  is_heuristic?: boolean
  /** Probability the premium/consensus regime persists over 12 months */
  persistence_probability?: number | null
  /** Intrinsic fair value midpoint (multiple-reversion anchor) */
  reversion_anchor?: number | null
  /** Analyst consensus mean target (premium-persistence anchor) */
  persistence_anchor?: number | null
  /** One-line explanation of how the base target was derived */
  basis_note?: string | null
}

export interface QAFlag {
  /** Stable machine code, e.g. 'targets_heuristic', 'news_missing' */
  code: string
  message: string
}

export type Rating = "STRONG BUY" | "BUY" | "HOLD" | "SELL" | "STRONG SELL"

export interface Risk {
  description: string
  severity: RiskLevel
  likelihood: RiskLevel
  mitigation?: string | null
}

export type RiskLevel = "low" | "medium" | "high"

export interface RunMeta {
  analysis_id: string
  schema_version?: number
  created_at: string
  /** stage → model id, e.g. {'synthesis': 'claude-sonnet-5'} */
  models_used?: Record<string, string>
  /** Total tokens (agents track a single sum today) */
  tokens_total?: number
  tokens_input?: number
  tokens_output?: number
  tokens_cache_read?: number
  cost_usd?: number
  duration_seconds?: number
  /** From TickerSnapshot.completeness_pct() */
  data_completeness_pct?: number
  qa_flags?: QAFlag[]
}

/** One weighted component of the quality score. Weights are recorded so */
export interface ScoreComponent {
  name: string
  score: number
  weight: number
  /** One line: what drove this score */
  basis?: string | null
}

export interface Scores {
  /** Business quality only — durability and execution. Price is NOT in it. */
  quality_score: number
  /** The second rating axis: how attractive the price is (higher = cheaper). Kept separate from quality so 'excellent business, rich price' is distinguishable from 'average business, fair price' — a blended score cannot express the difference. */
  valuation_score?: number | null
  /** high | mid | low — the quality axis of the rating matrix */
  quality_tier?: string | null
  /** attractive | fair | expensive — the valuation axis */
  valuation_tier?: string | null
  /** Weighted components; weights sum to 1.0 */
  components: ScoreComponent[]
  /** Tracked separately; gates the rating but is not in quality_score */
  technical_score?: number | null
  /** Analysis confidence, data-driven */
  confidence: number
}

/** One of the positioning/momentum signals (sentiment, revisions, */
export interface Signal {
  name: string
  direction: Direction
  score?: number | null
  /** One factual line, e.g. '4 buys / 1 sale, net +$2.1M' */
  evidence?: string | null
  has_data?: boolean
}

export interface TargetCase {
  target: number
  probability: number
  assumptions: string
}

export interface Thesis {
  /** One sentence: the call and the core reason */
  headline: string
  /** The full synthesis narrative */
  narrative: string
  /** 3-6 bullets */
  key_insights?: string[]
  bull_case: string
  bear_case: string
  /** Concrete falsifiers for the thesis */
  what_would_change_our_mind?: string[]
}

export interface TrancheStage {
  stage: number
  /** Percentage points of portfolio */
  allocation_pct: number
  trigger: string
}

/** The complete result of one ticker analysis. Persisted verbatim; */
export interface AnalysisReport {
  ticker: string
  company_name?: string | null
  sector?: string | null
  industry?: string | null
  as_of: string
  scores: Scores
  signals?: Signal[]
  divergence?: Divergence | null
  targets?: PriceTargets | null
  thesis: Thesis
  risks?: Risk[]
  catalysts?: Catalyst[]
  decision: Decision
  macro?: MacroContext | null
  meta: RunMeta
  previous?: PreviousAnalysisDelta | null
}
