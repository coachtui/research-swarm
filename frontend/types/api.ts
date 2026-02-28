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

// --- Institutional Risk System Types ---

export interface FactorDiagnostics {
  beta_estimate: number
  beta_label: 'High' | 'Above-Market' | 'Market-Rate' | 'Below-Market'
  growth_factor_loading: number
  growth_factor_label: string
  momentum_factor_loading: number
  momentum_factor_label: string
  quality_factor_proxy: number
  quality_factor_label: string
  vol_sensitivity: 'High' | 'Moderate' | 'Low'
  vol_sensitivity_note: string
  crowding_proxy: 'Elevated' | 'Moderate' | 'Low' | 'Unknown'
  crowding_proxy_note: string
  correlation_sensitivity: 'High' | 'Moderate' | 'Low'
  portfolio_interaction: 'Concentrating' | 'Neutral' | 'Diversifying'
  portfolio_interaction_note: string
  regime_sensitivity_flags: string[]
  estimation_note: string
}

export interface VolatilityRegimeDynamics {
  vol_trend: 'Expanding' | 'Contracting' | 'Stable'
  vol_trend_note: string
  event_vol_condition: boolean
  event_vol_note: string | null
  implied_realized_spread: 'Elevated' | 'Normal' | 'Compressed'
  implied_realized_note: string
  compression_probability: 'High' | 'Moderate' | 'Low'
  compression_note: string
  ev_reliability_impact: string
  stop_probability_modifier: string
  regime_label: string
}

export interface LiquidityMicrostructure {
  volume_participation: 'Above-ADV' | 'Normal' | 'Sub-ADV'
  volume_participation_note: string
  volume_state: 'Expansion' | 'Stable' | 'Contraction' | 'Suspect'
  volume_state_note: string
  thin_volume_risk: 'High' | 'Moderate' | 'Low'
  thin_volume_note: string
  block_flow_proxy: 'Active' | 'Normal' | 'Limited' | 'Unavailable'
  block_flow_note: string
  spread_impact_proxy: 'Tight' | 'Normal' | 'Wide'
  spread_impact_note: string
  accumulation_distribution_bias: 'Accumulation' | 'Mild Accumulation' | 'Neutral' | 'Mild Distribution' | 'Distribution'
  bias_note: string
  stability_modifier_effect: string
  ev_confidence_effect: string
}

export interface ModelSensitivityAttribution {
  overall_sensitivity: 'High' | 'Moderate' | 'Low'
  dominant_driver: string
  dominant_driver_rationale: string
  sensitivity_drivers: Array<{
    factor: string
    sensitivity: 'High' | 'Moderate' | 'Low'
    elasticity_note: string
    rank: number
  }>
  confidence_degradation_rationale: string
  model_failure_risk: string
}

export interface PortfolioAction {
  allocation_bias: 'Add' | 'Hold' | 'Reduce' | 'Avoid'
  allocation_bias_note: string
  conviction_scaling_multiplier: number
  conviction_scaling_label: 'Full Conviction' | 'Standard Conviction' | 'Reduced Conviction' | 'Low Conviction' | 'Minimal Conviction'
  conviction_scaling_rationale: string
  conviction_multiplier_drivers: string[]
  risk_budget_impact: 'High' | 'Moderate' | 'Low'
  risk_budget_note: string
  mandate_fit: 'Core Holding' | 'Satellite Position' | 'Tactical Trade' | 'Watchlist Only'
  mandate_fit_rationale: string
  sizing_guidance: string
  regime_break_condition: string
}

// --- Probabilistic Engine Interpretability Types ---

export interface EVStabilityClass {
  stability_class: 'Structurally Stable' | 'Moderately Sensitive' | 'Highly Sensitive' | 'Noise Dominated'
  sensitivity_driver: 'Signal Instability' | 'Market Movement Impact' | 'Mixed' | 'None'
  driver_note: string
  ev_sensitivity_band_pct: number
  instability_score: number
  signal_driver_score: number
  market_driver_score: number
  stability_rationale: string
}

export interface ConfidenceIntegrity {
  ev_confidence_level: 'HIGH' | 'MODERATE' | 'LOW' | 'VERY LOW'
  ev_confidence_label: string
  confidence_note: string
  probability_dispersion_label: 'Tight' | 'Moderate' | 'Wide'
  confidence_degradation_drivers: string[]
  effective_confidence_pct: number
  base_confidence_pct: number
  total_degradation_pts: number
  separation_note: string
}

export interface ScenarioWeightDiagnostics {
  model_bear_prob: number
  model_base_prob: number
  model_bull_prob: number
  effective_bear_prob: number
  effective_base_prob: number
  effective_bull_prob: number
  scenario_rotation_index: number
  probability_compression_ratio: number
  tail_state: 'Expanded' | 'Neutral' | 'Compressed'
  tail_note: string
  drift_label: 'Stable Distribution' | 'Modest Rotation' | 'Significant Rotation'
  weight_shift_rationale: string
  active_rotation_factors: string[]
}

export interface StopProbabilityDecomposition {
  effective_stop_probability_pct: number
  stop_probability_label: 'Low' | 'Elevated' | 'High' | 'Critical'
  base_stop_risk_pct: number
  volatility_pressure_pct: number
  trend_modifier_pct: number
  support_modifier_pct: number
  volatility_pressure_drivers: string[]
  decomposition_narrative: string
  regime_note: string
}

export interface NoiseFilter {
  noise_regime: 'Clean' | 'Moderate Noise' | 'High Noise' | 'Noise Dominated'
  noise_score: number
  noise_flag: boolean
  defer_sizing: boolean
  noise_drivers: string[]
  regime_warning: string | null
  action_guidance: string
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
  // Institutional Risk System modules
  factor_diagnostics?: FactorDiagnostics
  volatility_regime_dynamics?: VolatilityRegimeDynamics
  liquidity_microstructure?: LiquidityMicrostructure
  model_sensitivity_attribution?: ModelSensitivityAttribution
  portfolio_action?: PortfolioAction
  // Probabilistic Engine Interpretability modules
  ev_stability?: EVStabilityClass
  confidence_integrity?: ConfidenceIntegrity
  scenario_weight_diagnostics?: ScenarioWeightDiagnostics
  stop_probability?: StopProbabilityDecomposition
  noise_filter?: NoiseFilter
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

// --- Capital Deployment Rationale Types ---

export interface CapitalDeploymentDriver {
  label: string
  impact: 'tighten' | 'loosen' | 'neutral'
  evidence: string
}

export interface CapitalDeploymentBinding {
  type: 'execution' | 'policy_cap'
  explanation: string
}

export interface CapitalDeploymentRationale {
  summary: string
  drivers: CapitalDeploymentDriver[]
  binding: CapitalDeploymentBinding
  interpretation: string[]
  next_actions: string[]
  disclaimers: string
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
  /** Pre-computed capital deployment rationale — available for PDF export */
  capital_deployment_rationale?: CapitalDeploymentRationale | null
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

/** Sensitivity attribution driver (EV change decomposition) */
export interface EVAttributionDriver {
  driver: string
  delta: number | null
  direction: 'bearish' | 'bullish' | 'neutral'
}

/** Stop probability drift decomposition — per-component deltas */
export interface StopProbDriftDecomposition {
  base_delta: number
  volatility_pressure_delta: number
  trend_modifier_delta: number
  support_modifier_delta: number
  prior_stop_label?: string | null
  current_stop_label?: string | null
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
  // Sensitivity attribution (item 1: "What Changed?" diagnostic)
  prior_overall_score?: number | null
  current_overall_score?: number | null
  prior_signal_stability?: number | null
  current_signal_stability?: number | null
  prior_signal_spread?: number | null
  current_signal_spread?: number | null
  prior_vol_trend?: string | null
  current_vol_trend?: string | null
  sensitivity_attribution?: string[]
  // Probabilistic module drift (Sensitivity Attribution & Drift Diagnostics Engine)
  prior_stop_probability_pct?: number | null
  current_stop_probability_pct?: number | null
  prior_confidence_pct?: number | null
  current_confidence_pct?: number | null
  prior_stability_score?: number | null
  current_stability_score?: number | null
  prior_noise_score?: number | null
  current_noise_score?: number | null
  prior_stability_class?: string | null
  current_stability_class?: string | null
  prior_scenario_weights?: { bear: number; base: number; bull: number } | null
  current_scenario_weights?: { bear: number; base: number; bull: number } | null
  model_drift_level?: 'Stable' | 'Modest' | 'Moderate' | 'Significant' | null
  scenario_rotation_label?: string | null
  ev_attribution?: EVAttributionDriver[] | null
  stop_prob_drift_decomposition?: StopProbDriftDecomposition | null
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
  tier: string
  is_free_tier: boolean
  analyses_used: number
  analyses_limit: number
  boost_analyses_added: number
  analyses_remaining: number
  watchlist_count: number
  watchlist_limit: number
  watchlist_remaining: number
  period_start: string | null
  period_end: string | null
  billing_period_end: string | null
  days_remaining: number | null
  boost_eligible: boolean
  at_warning_threshold: boolean
  /** Free-tier lifetime credits (null for paid tiers). */
  report_credits_total: number | null
  report_credits_used: number | null
  report_credits_remaining: number | null
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

// ─── Dynamic Position Sizing Engine types ─────────────────────────────────────
// Mirrors frontend/lib/engine/types.ts — used for API request/response shapes.

export interface PositionSizingFlags {
  signal_conflict_active?: boolean
  cap_at_satellite?: boolean
}

export interface PositionSizingRequest {
  symbol: string
  classification: 'CORE' | 'SATELLITE'
  /** 0–100 */
  noise_score: number
  overall_sensitivity: 'LOW' | 'MODERATE' | 'HIGH'
  signal_dispersion_sigma: number
  /** 0–1 */
  stop_probability: number
  beta?: number
  ev_percentile?: number
  flags?: PositionSizingFlags
  custom_exposure_sizes?: number[]
}

export interface PositionSizingMultiplierDetail {
  value: number
  bucket_label: string
  reason: string
  input_value: string | number
}

export interface PositionSizingCapState {
  active: boolean
  reason: string
  cap_value?: number
}

export interface PositionSizingResponse {
  symbol: string
  base_weight: number
  multipliers: {
    noise: PositionSizingMultiplierDetail
    sensitivity: PositionSizingMultiplierDetail
    dispersion: PositionSizingMultiplierDetail
    stoprisk: PositionSizingMultiplierDetail
    beta?: PositionSizingMultiplierDetail
    ev_percentile?: PositionSizingMultiplierDetail
  }
  product_of_multipliers: number
  adjusted_weight: number
  adjusted_weight_pct: number
  cap_state: PositionSizingCapState
  notes: string[]
  /** Dollar exposure keyed by portfolio size string: { "10000": 236 } */
  exposure_examples: Record<string, number>
  config_version: string
}

// --- Entitlements ---

/**
 * Server-resolved feature flags and quota limits for the current user.
 * Returned by GET /api/entitlements — derives tier, admin override, and
 * Stripe inactive-status downgrade server-side so the client never has to
 * replicate that logic.
 */
export interface EntitlementsResponse {
  /** Effective tier after admin override and Stripe status check. */
  tier: 'free' | 'starter' | 'investor' | 'trader'
  /** False when the Stripe subscription is in an inactive/delinquent status. */
  active: boolean
  /**
   * Map of feature flag → granted (boolean).
   * All known flags are always present; unknown flags default to false on use.
   */
  features: Record<string, boolean>
  limits: {
    analyses_per_month: number
    concurrent_analyses: number
    watchlist_max: number
    /** True for the free tier (credit-based instead of monthly rolling). */
    is_credit_based: boolean
    /** Total lifetime credits available (free tier only). */
    free_credits_total: number
  }
  /** Live usage counters — always fresh (no extra client-side DB hit). */
  usage: {
    analyses_used: number
    analyses_remaining: number
    analyses_limit: number
    /** Free-tier lifetime credits total (null for paid tiers). */
    report_credits_total: number | null
    /** Free-tier credits consumed so far (null for paid tiers). */
    report_credits_used: number | null
    /** Free-tier credits remaining (null for paid tiers). */
    report_credits_remaining: number | null
    /** True only for the free tier. */
    is_free_tier: boolean
    /** True when a paid-tier user has used ≥80% of their monthly analyses. */
    at_warning_threshold: boolean
  }
}

// ── Structural Deployment Update (Investor+) ──────────────────────────────────

export interface DeployableTickerItem {
  ticker: string
  sector: string
  allocation_current: number
  /** null when no prior run exists to compare against */
  allocation_delta_30d: number | null
  /** 0–5: count of moat breakdown components above confirmation threshold */
  confirmation_score: number
  /** 0–100 mid-rank percentile within tracked universe; null when universe < 5 (ranking disabled) */
  vol_adj_ev_percentile: number | null
  /** 0–100 effective stop probability */
  stop_probability: number
  /** Percentage of same-sector tickers that are structurally confirmed */
  sector_breadth_pct: number
}

export interface SectorBreadthRow {
  sector: string
  confirmed: number
  total: number
  pct_confirmed: number
  trend: 'rising' | 'stable' | 'falling'
}

export interface MarketDeployabilitySnapshot {
  universe_size: number
  /** Percentage of universe with confirmation_score >= 4 */
  pct_universe_confirmed: number
  avg_allocation_delta: number | null
  avg_stop_probability: number
  /** "rising" = worsening, "falling" = improving, "stable" = unchanged */
  avg_stop_probability_trend: 'rising' | 'stable' | 'falling'
  /** Percentage of universe with stable regime */
  regime_stable_pct: number
  capital_posture: 'Low' | 'Moderate' | 'Expanding'
  /** Suggested max portfolio exposure % based on posture */
  exposure_ceiling: number
}

export interface EligibilityFailureItem {
  /** Machine name matching NearMissTicker.failing_rules entries */
  rule: string
  /** Human-readable rule name */
  label: string
  /** How many structurally confirmed tickers fail this rule */
  count: number
  /** Threshold description, e.g. "≥ 60th percentile" */
  threshold_desc: string
}

export interface NearMissTicker {
  ticker: string
  /** Rules this ticker fails (subset of the 4 allocation eligibility rules) */
  failing_rules: string[]
  /** Actual metric values; keys match failing_rules semantics */
  metric_values: Record<string, number>
  /** Required threshold values; same keys as metric_values */
  threshold_values: Record<string, number>
  /** Explanatory focus label, e.g. "Stop risk elevated" */
  suggested_action: string
  /** 2 = fails exactly 1 rule, 3 = fails exactly 2 rules, 0 = fails 3+ */
  tier: number
}

export interface EligibilityDiagnostics {
  /** Total tickers in tracked universe */
  evaluated_count: number
  /** Tickers with confirmation_score >= 4 */
  confirmed_count: number
  /** Tickers passing ALL 5 allocation eligibility criteria */
  eligible_count: number
  /** Failure reasons ranked by count descending */
  failure_reasons: EligibilityFailureItem[]
  /** Top 10 near-miss tickers sorted by fewest failing rules then smallest gap */
  near_misses: NearMissTicker[]
  /** Tier counts across all confirmed tickers: {1: eligible, 2: fails 1 rule, 3: fails 2 rules} */
  tier_counts: Record<number, number>
}

export interface DeploymentUpdateResponse {
  snapshot_id: string
  generated_at: string
  ttl_expires_at: string
  cache_age_hours: number
  model_version: string
  ruleset_version: string
  universe_size: number
  /** Tickers with confirmation_score >= 4 (structural gate) */
  confirmed_count: number
  /** Count of tickers passing all 5 inclusion criteria */
  eligible_count: number
  snapshot: MarketDeployabilitySnapshot
  deployable_tickers: DeployableTickerItem[]
  sector_breadth: SectorBreadthRow[]
  /** Set when deployable_tickers is empty */
  no_deployable_message: string | null
  eligibility_diagnostics: EligibilityDiagnostics
}

// ── Eligibility Stress-Test Simulation ────────────────────────────────────────

export interface StressBaselineResult {
  eligible: number
  /** % of structurally confirmed tickers that pass all rules */
  pass_rate_structural: number
}

export interface StressScenarioResult {
  name: string
  eligible: number
  pass_rate_structural: number
  change_vs_baseline: number
}

export interface AvgDistanceToThreshold {
  /** Avg allocationDelta30d for tickers failing delta rule (negative = below 0) */
  delta: number | null
  /** Avg (vol_adj_ev_percentile - 60) for tickers below 60th pct (negative = below) */
  ev_percentile: number | null
  /** Avg (stopProbability - 25) for tickers above 25% stop (positive = elevated) */
  stop: number | null
}

export interface EligibilityStressTestResponse {
  evaluated_universe: number
  structural_confirmed: number
  baseline: StressBaselineResult
  scenarios: StressScenarioResult[]
  /** Which single rule eliminates the most confirmed tickers */
  dominant_binding_constraint: string
  avg_distance_to_threshold: AvgDistanceToThreshold
  generated_at: string
}

// ── Rolling simulation types ──────────────────────────────────────────────────

export interface WeeklySimPoint {
  /** ISO date "YYYY-MM-DD" — Monday of the ISO week */
  week: string
  deployability_index: number   // 0–100
  structural_confirmed: number
  tier1_count: number           // strict: all 5 eligibility rules
  tier2_count: number           // moderate: Scenario-D relaxation
  universe_size: number
}

export interface RollingSimSummaryStats {
  /** % of data-weeks where tier1_count >= 1 */
  pct_weeks_tier1_gte1: number
  /** % of data-weeks where tier1_count == 0 */
  pct_weeks_tier1_zero: number
  median_tier1: number
  median_tier2: number
  total_weeks: number
  weeks_with_data: number
}

export interface EligibilityRollingSimResponse {
  weeks: WeeklySimPoint[]
  summary_stats: RollingSimSummaryStats
  tier1_label: string
  tier2_label: string
  generated_at: string
  data_start: string | null
  data_end: string | null
}

// ── Opportunity Distribution ───────────────────────────────────────────────────

export interface PercentileCutlines {
  p50: number | null
  p60: number | null
  p75: number | null
  p90: number | null
}

export interface DistributionTicker {
  ticker: string
  /** 1 = eligible, 2 = fails 1 rule */
  tier: number
  edge_pct: number | null
  stop_prob_pct: number
  risk_adj_edge_pct: number | null
  risk_adj_edge_percentile: number | null
}

export interface DistributionSummaryStats {
  n_evaluated: number
  n_valid_ranked: number
  min_risk_adj_edge: number | null
  max_risk_adj_edge: number | null
  mean_risk_adj_edge: number | null
  median_risk_adj_edge: number | null
  pct_positive_edge: number
  pct_positive_risk_adj: number
}

export interface DataIntegrityWarning {
  code: string
  message: string
}

export interface OpportunityDistributionResponse {
  snapshot_id: string
  generated_at: string
  /** Index-aligned arrays — one entry per universe ticker */
  tickers: string[]
  edge_pct: (number | null)[]
  stop_prob_pct: number[]
  risk_adj_edge_pct: (number | null)[]
  risk_adj_edge_percentile: (number | null)[]
  edge_pct_cutlines: PercentileCutlines
  stop_prob_cutlines: PercentileCutlines
  risk_adj_edge_cutlines: PercentileCutlines
  /** Tier 1 (eligible) + Tier 2 (near-miss) confirmed tickers */
  tier_tickers: DistributionTicker[]
  summary: DistributionSummaryStats
  warnings: DataIntegrityWarning[]
}

// ── Threshold Calibration ──────────────────────────────────────────────────────

export interface ThresholdImpliedValues {
  percentile_gate: number
  /** P-th percentile of the risk-adjusted edge distribution */
  risk_adj_edge_pct: number | null
  /** P-th percentile of the raw edge distribution */
  edge_pct: number | null
  /** P-th percentile of the stop-probability distribution */
  stop_prob: number | null
}

export interface CalibrationSensitivityRow {
  percentile_gate: number
  /** True when this row matches the live production EV gate (60.0) */
  is_current: boolean
  tier1_eligible: number
  tier2_eligible: number
}

export interface TargetHitRateRow {
  label: string
  tier: number
  min_count: number
  max_count: number
  /** Percentile gate that yields a count in [min_count, max_count]; null = unachievable */
  suggested_gate: number | null
}

export interface CalibrationNote {
  id: string
  text: string
  saved_at: string
}

export interface ThresholdCalibrationResponse {
  snapshot_id: string
  generated_at: string
  universe_size: number
  confirmed_count: number
  implied_values: ThresholdImpliedValues
  sensitivity_table: CalibrationSensitivityRow[]
  target_hit_rates: TargetHitRateRow[]
}

export interface CalibrationNoteListResponse {
  notes: CalibrationNote[]
}
