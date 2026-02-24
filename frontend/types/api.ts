// API Request/Response Types for DVRG Backend

export interface AnalyzeRequest {
  ticker: string
  quarters?: string[]
  news_days_back?: number
}

export interface AnalyzeResponse {
  job_id: string
  run_id: string
  ticker: string
  status: 'queued' | 'running' | 'completed' | 'failed'
  estimated_time_minutes: number
  created_at: string
  result?: StockResult
}

export interface InvestmentThesisStructured {
  company_overview: string
  recommendation_summary: string
  investment_highlights: string[]
  valuation_signal_analysis: string
  key_risks: string[]
  entry_strategy: string
}

export interface StockResult {
  ticker: string
  status: 'pending' | 'running' | 'completed' | 'failed'
  moat_score: number | null
  financial_health_score: number | null
  business_model_moat_score: number | null
  sentiment_score: number | null
  technical_score: number | null
  supply_chain_score: number | null
  watchlist_candidate: boolean
  investment_thesis: InvestmentThesisStructured | null
  full_output: ManagerOutput | null
  tokens_used: number
  cost_usd: number
  processing_time_seconds: number
  error_message: string | null
  created_at: string
  updated_at: string
}

export interface ManagerOutput {
  ticker: string
  analysis_date: string
  analysis_period: string
  quarters: string[]
  news_days_back: number

  // Agent outputs
  fundamentalist_output: any
  news_hound_output: any
  quant_output: any

  // Synthesis
  synthesis_narrative: string
  key_insights: string[]
  risk_factors: string[]
  investment_thesis: InvestmentThesisStructured
  strategic_catalysts?: Array<{
    title: string
    description: string
    category: string
    potential_impact: 'HIGH' | 'MEDIUM' | 'LOW'
    timeframe: string
  }>

  // Moat breakdown (v2.0 formula)
  moat_breakdown: {
    earnings_momentum: number     // 25%
    financial_health: number       // 25%
    valuation: number              // 20%
    technical_strength: number     // 15%
    sentiment_catalysts: number    // 15%
  }

  // VGM scores
  vgm_scores?: {
    value_score: number
    growth_score: number
    momentum_score: number
  }

  // Signal breakdown (divergence analysis)
  signal_breakdown?: SignalBreakdown

  // Investment recommendations (newly exposed)
  price_targets?: {
    // Intrinsic Value Range
    fair_value_low: number
    fair_value_mid: number
    fair_value_high: number
    fair_value_zone_label: string
    // Confidence
    confidence_score: number  // 0–100
    confidence: 'High' | 'Moderate' | 'Low'
    uncertainty_drivers: string[]
    // Price vs. zone
    premium_vs_mid?: number   // (price − mid) / mid
    deviation_vs_price?: number  // (price − mid) / price
    price_vs_zone: string
    // Scenario targets (validated chain: bear < base < bull)
    bull_target: number
    bull_probability: number
    bull_assumptions: string
    base_target: number
    base_probability: number
    base_assumptions: string
    bear_target: number
    bear_probability: number
    bear_assumptions: string
    methodology: string
    // P2: Cross-method dispersion (valuation model agreement)
    valuation_dispersion_pct?: number
    valuation_dispersion_label?: 'Low' | 'Moderate' | 'High'
    method_values?: { pe?: number; ev_ebitda?: number; dcf?: number }
    // P2: Probability-weighted expected value
    probability_weighted_ev?: number
    // P2: Premium justification
    premium_justification?: {
      classification: 'JUSTIFIED_PREMIUM' | 'EXECUTION_DEPENDENT_PREMIUM' | 'SPECULATIVE_PREMIUM' | 'NO_PREMIUM'
      label: string
      rationale: string
      premium_pct_vs_sector: number
      implied_peg: number | null
    }
    // P0: Chain validation (auto-correction notes)
    chain_validation_notes?: string[]
  }
  structured_risks?: Array<{
    risk: string
    severity: 'HIGH' | 'MEDIUM' | 'LOW'
    likelihood: 'High' | 'Medium' | 'Low'
    impact: string
    mitigation: string
  }>
  recommendation?: 'BUY' | 'HOLD' | 'AVOID'
  rating?: string
  rating_score?: number
  risk_level?: string

  // Conviction & triggers
  conviction_statement?: ConvictionStatement
  upgrade_triggers?: TriggerItem[]
  downgrade_triggers?: TriggerItem[]

  // Cost tracking
  cost_by_agent: {
    fundamentalist: number
    news_hound: number
    quant: number
    manager: number
  }

  // Fair value calibration metadata
  fair_value_calibration?: FairValueCalibration
  report_qa_flags?: Array<Record<string, unknown>>

  // Decision Intelligence (computed on-the-fly by API)
  decision_intelligence?: DecisionIntelligence

  // Longitudinal delta tracking — populated when user has a prior analysis for this ticker
  previous_analysis_delta?: PreviousAnalysisDelta
}

export interface FairValueCalibration {
  // Regime
  regime: string                              // "Growth" | "Stable" | "Value/Turnaround"
  regime_rev_growth_pct: number               // Forward revenue growth used for classification (%)

  // Internal model — untouched, display reference only
  internal_fair_value: number                 // fair_value_mid from DVRG blended model
  internal_method_dispersion_pct: number | null  // spread across P/E, EV/EBITDA, DCF (%)

  // Analyst consensus target — forward market expectation proxy (structurally distinct from FV)
  consensus_target: number | null             // analyst mean price target
  num_analysts: number | null                 // number of analyst estimates

  // Divergence analysis
  divergence_ratio: number | null             // internal_fair_value / consensus_target
  divergence_pct: number | null               // signed % gap vs consensus target
  divergence_state: 'Consensus Validated ✓' | 'Model-Conservative Regime' | 'Model-Driven Upside Scenario' | 'No Consensus Data'

  // Anomaly guardrail — does NOT trigger recalibration, just flags data quality
  model_stability_warning: boolean
  stability_warning_reasons: string[]

  // Audit
  qa_flags: string[]
  display_label: string
}

// --- Signal Breakdown Types ---

export interface RsiExtremeFlag {
  rsi_value: number
  direction: 'oversold' | 'overbought'
  interpretation: string
  confidence_penalty: number
  label: string
}

export interface SignalBreakdown {
  overall_score: number
  // Signal scores
  news_score: number
  earnings_score: number
  analyst_score: number
  institutional_score: number
  insider_score: number
  dark_pool_score: number
  tech_divergence_score: number
  // Interpretations
  news_interpretation: string
  earnings_interpretation: string
  analyst_interpretation: string
  institutional_interpretation: string
  insider_interpretation: string
  dark_pool_interpretation: string
  tech_divergence_interpretation: string
  // Data availability flags
  news_has_data?: boolean
  earnings_has_data?: boolean
  analyst_has_data?: boolean
  institutional_has_data?: boolean
  insider_has_data?: boolean
  dark_pool_has_data?: boolean
  tech_divergence_has_data?: boolean
  // P0: Data integrity (scores computed from confirmed signals only)
  valid_signal_count?: number
  missing_signal_count?: number
  data_integrity_pct?: number
  data_integrity_label?: 'Complete' | 'Partial' | 'Incomplete'
  data_integrity_confidence_factor?: number
  // P3: Model confidence dimensions
  signal_strength?: number
  signal_strength_label?: 'Strong' | 'Moderate' | 'Weak'
  signal_stability?: number
  signal_stability_label?: 'Stable' | 'Mixed' | 'Unstable'
  // P1: RSI extreme flag
  rsi_extreme_flag?: RsiExtremeFlag | null
  // P0: Divergence metric labeling — three distinct constructs
  signal_spread?: number           // σ across all 7 signals — drives headline has_divergence
  signal_spread_label?: 'Low' | 'Moderate' | 'High'
  component_gap?: number           // Fundamentalist valuation score vs quant technical score gap
  component_gap_label?: 'Low' | 'Moderate' | 'High' | 'None'
  // P0: Volume data quality
  volume_data_quality?: 'NORMAL' | 'SUSPECT' | 'ELEVATED'
  volume_data_flag?: string | null
  // P1: Confidence reduction audit trail
  confidence_reduction_log?: Array<{
    trigger: string
    penalty_pct: number
    resulting_factor: number
    detail: string
  }>
  // P2: Insider anomaly note
  insider_anomaly_note?: string | null
  // ADR / foreign listing flag — drives differentiated N/A display for insider + dark pool
  is_adr?: boolean
  // Divergence analysis
  alignment_status: string
  has_divergence: boolean
  divergence_explanation: string
  divergence_recommendation: string
  direction_consensus: string
  // Probability Construction Framework — structural derivation of scenario weights
  probability_construction_framework?: {
    factors: Array<{
      name: string
      description: string
      current_value: string
      effect: string
      impact_level: 'High' | 'Moderate' | 'Low' | 'None'
    }>
    derivation_note: string
  }
  // Factor Exposure — portfolio-level risk context
  factor_exposure?: {
    beta_contribution: string        // High / Above-Market / Market-Rate / Below-Market / Unknown
    beta_note: string
    factor_tilt: string              // "Growth, Momentum (Growth/Momentum)" etc
    crowding_risk: string            // Elevated / Moderate / Low / Unknown
    crowding_note: string
    diversification_benefit: string  // Low / Low–Moderate / Moderate / Moderate–High
    diversification_note: string
    estimation_note: string
  }
}

export interface ConvictionStatement {
  conviction_level: string
  bottom_line: string
  best_suited_for: {
    investor_type: string
    risk_tolerance: string
    time_horizon: string
  }
}

export interface TriggerItem {
  metric: string
  threshold: string
  action: string
}

// --- Decision Intelligence Types ---

export interface DecisionIntelligence {
  decision_framework: DecisionFramework | null
  enhanced_trade_setup: EnhancedTradeSetup | null
  fund_tech_divergence: FundTechDivergence | null
  conviction_position: ConvictionPosition | null
  rating: string | null
  risk_level: string | null
  current_price: number
  recommended_strategy: RecommendedStrategy | null
  /** QA flags: constraint violations and clamping events logged during calculation */
  report_qa_flags?: string[]
}

export interface DecisionFramework {
  current_holders: {
    action: 'HOLD' | 'ADD' | 'REDUCE'
    detail: string
    conditions: string[]
  }
  new_buyers: {
    action: 'BUY NOW' | 'SCALE IN' | 'WAIT' | 'AVOID'
    urgency: string
    detail: string
    caveat: string | null
  }
  one_liner: string
  /** Structured per-reader-type guidance lines: New positions · Current holders · Traders */
  action_subtext?: string[]
  regime_caveat?: string | null
}

/** Previous analysis comparison for longitudinal delta tracking */
export interface PreviousAnalysisDelta {
  prior_run_id: string
  prior_analysis_date: string
  prior_recommendation: string
  current_recommendation: string
  prior_price: number | null
  current_price: number | null
  price_change_pct: number | null
  prior_smart_money_score: number | null
  current_smart_money_score: number | null
  prior_moat_score: number | null
  current_moat_score: number | null
  thesis_direction: 'strengthened' | 'weakened' | 'held' | 'reversed'
  days_since_last: number
}

export interface TradeTarget {
  price: number
  sell_pct: number
  label: string
  /** True when target price < current price in a long position (illogical profit target) */
  suppressed?: boolean
  /** Reason for suppression — shown in place of the target price */
  suppression_reason?: string | null
}

export interface TradeSetupSide {
  label: string
  entry: number
  stop_loss: number
  targets: TradeTarget[]
  max_loss_per_100: number
  max_gain_per_100: number
  risk_reward: number
  /** C2: Set when entry/stop are too close to form a valid risk buffer (< 5% gap) */
  setup_unavailable?: string | null
  /** MOMENTUM mode: the structural fair value anchor price (conservative entry) */
  structural_anchor_price?: number | null
  /** MOMENTUM mode: R/R ratio calculated from current price (may be negative when targets < price) */
  asymmetry_from_current_price?: number | null
}

export interface EnhancedTradeSetup {
  conservative: TradeSetupSide
  aggressive: TradeSetupSide
  /** Regime classification: STANDARD | MOMENTUM | DISTRESSED */
  regime_mode?: 'STANDARD' | 'MOMENTUM' | 'DISTRESSED' | null
  /** Raw intrinsic fair value used for regime detection (pre-sanity-gate) */
  intrinsic_fair_value?: number | null
  /** Warning message shown prominently when in MOMENTUM regime */
  momentum_regime_warning?: string | null
}

export interface FundTechDivergence {
  has_divergence: boolean
  divergence_type: string
  severity: 'HIGH' | 'MODERATE'
  gap: number
  fundamental_signal: string
  technical_signal: string
  interpretation: string
  recommendation: string
  resolution_bias: string
}

export interface ConvictionPosition {
  conviction_level: string
  conviction_score: string
  recommended_pct: number
  max_pct: number
  dollar_per_100k: number
  rationale: string
  conviction_justification: string
}

export interface RecommendedStrategy {
  entry: {
    ideal_zone: { low: number; high: number }
    discount_to_target_pct: number
    // P1: Provenance
    entry_methodology?: string
    // P2: Zone display
    entry_zone_display?: { low: number; high: number; label: string }
    // P0: Entry / Bear case relationship
    entry_below_bear?: boolean
    entry_below_bear_pct?: number
    below_bear_classification?: 'ABOVE_BEAR' | 'TAIL_RISK_DISCOUNT' | 'DISTRESSED_ENTRY' | 'CLAMPED'
    below_bear_justification?: string | null
    // Only present when CLAMPED — the raw model value before re-anchoring
    original_ideal_low?: number | null
  }
  exit: {
    stop_loss: number
    target_1: { price: number; percent: number; rationale: string }
    target_2: { price: number; percent: number; rationale: string }
    holding_period: string
    expected_return_total: number
    expected_return_annualized: number
    // P0: Stop/bear alignment
    stop_quality?: 'ALIGNED' | 'WIDE' | 'ADJUSTED'
    stop_alignment_note?: string
    // P1: Stop provenance
    stop_methodology?: string
    // P2: Stop zone
    stop_zone?: { low: number; high: number; label: string }
  }
  position_sizing: {
    recommended_pct: number
    max_pct: number
    rationale: string
  }
}

export interface RunListResponse {
  total: number
  limit: number
  offset: number
  runs: RunSummary[]
}

export interface RunSummary {
  id: string
  ticker: string
  status: 'queued' | 'running' | 'completed' | 'failed' | 'cancelled'
  created_at: string
  completed_at: string | null
  total_cost_usd: number
  stock_count: number
}

export interface RunResponse {
  id: string
  status: 'queued' | 'running' | 'completed' | 'failed' | 'cancelled'
  tickers: string[]
  total_cost_usd: number
  created_at: string
  completed_at: string | null
  results: StockResult[]
}

// --- Watchlist Types ---

export interface WatchlistItem {
  id: string
  ticker: string
  company_name: string | null
  added_at: string
  last_checked_at: string | null
  initial_moat_score: number | null
  latest_moat_score: number | null
  score_change: number | null
  latest_analysis_date: string | null
  notes: string | null
  days_since_update: number | null
  can_refresh: boolean
  initial_analysis_run_id: string | null
  latest_analysis_run_id: string | null
}

export interface WatchlistResponse {
  items: WatchlistItem[]
  total: number
}

export interface AddToWatchlistRequest {
  ticker: string
  company_name?: string
  notes?: string
  analysis_run_id?: string
}

export interface UpdateNotesRequest {
  notes: string
}

export interface RefreshWatchlistResponse {
  success: boolean
  new_score: number | null
  old_score: number | null
  score_change: number | null
  run_id: string | null
}

export interface WatchlistStatsResponse {
  watchlist_count: number
  watchlist_limit: number
  avg_score: number | null
  divergence_count: number
  needs_refresh_count: number
}

// --- Quota Types ---

export interface QuotaData {
  analyses_used: number
  analyses_limit: number
  boost_analyses_added: number
  analyses_remaining: number
  watchlist_count: number
  watchlist_limit: number
  watchlist_remaining: number
  period_start: string
  period_end: string
  billing_period_end: string
  days_remaining: number
  boost_eligible: boolean
  tier: string
}

// --- Admin Types ---

export interface PlatformMetrics {
  users: {
    total: number
    free: number       // legacy — may be 0
    starter: number
    investor: number
    trader: number
  }
  analyses: {
    total: number
    today: number
  }
  watchlist_adoption_rate: number
}

export interface UserWithUsage {
  id: string
  email: string
  full_name: string | null
  tier: string
  is_active: boolean
  is_admin: boolean
  created_at: string
  watchlist_count: number
  analyses_used: number
  analyses_limit: number
}

export interface UsersListResponse {
  users: UserWithUsage[]
  total: number
  limit: number
  offset: number
}

export interface AnalysisRecord {
  run_id: string
  user_email: string
  ticker: string
  status: string
  moat_score: number | null
  created_at: string
  cost_usd: number
}

export interface AnalysesListResponse {
  analyses: AnalysisRecord[]
  total: number
}

export interface UpdateTierRequest {
  new_tier: string
}

export interface CostSummary {
  today: number
  week: number
  month: number
  year: number
  all_time: number
  analyses_today: number
  analyses_week: number
  analyses_month: number
  analyses_year: number
  analyses_all_time: number
}

export interface DailyCostPoint {
  date: string           // YYYY-MM-DD
  cost_usd: number
  analyses: number
}

export interface MonthlyCostPoint {
  month: string          // YYYY-MM
  cost_usd: number
  analyses: number
  estimated_revenue: number
}

export interface RevenueTimeSeries {
  daily: DailyCostPoint[]
  monthly: MonthlyCostPoint[]
  estimated_mrr: number
  current_month_cost: number
  current_month_profit: number
  profit_margin_pct: number
  tier_breakdown: Record<string, { users: number; monthly_revenue: number }>
}

export interface UserInfo {
  id: string
  email: string
  full_name: string | null
  tier: string
  stripe_subscription_status: string | null
  is_active: boolean
  is_admin: boolean
}

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string
  ) {
    super(message)
    this.name = 'ApiError'
  }
}
