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
  /** The headline 0-10 score */
  quality_score: number
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
  meta: RunMeta
  previous?: PreviousAnalysisDelta | null
}
