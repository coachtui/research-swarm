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
    // Scenario targets (backward-compatible)
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

  // Decision Intelligence (computed on-the-fly by API)
  decision_intelligence?: DecisionIntelligence
}

// --- Signal Breakdown Types ---

export interface SignalBreakdown {
  overall_score: number
  // Original 5 signals
  news_score: number
  earnings_score: number
  analyst_score: number
  institutional_score: number
  insider_score: number
  // NEW: 2 additional signals (7-signal system)
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
  // Divergence analysis
  alignment_status: string
  has_divergence: boolean
  divergence_explanation: string
  divergence_recommendation: string
  direction_consensus: string
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
}

export interface TradeTarget {
  price: number
  sell_pct: number
  label: string
}

export interface TradeSetupSide {
  label: string
  entry: number
  stop_loss: number
  targets: TradeTarget[]
  max_loss_per_100: number
  max_gain_per_100: number
  risk_reward: number
}

export interface EnhancedTradeSetup {
  conservative: TradeSetupSide
  aggressive: TradeSetupSide
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
  }
  exit: {
    stop_loss: number
    target_1: number
    target_2: number
    holding_period: string
    expected_return_total: number
    expected_return_annualized: number
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
  analyses_remaining: number
  watchlist_count: number
  watchlist_limit: number
  watchlist_remaining: number
  period_start: string
  period_end: string
  tier: string
}

// --- Admin Types ---

export interface PlatformMetrics {
  users: {
    total: number
    free: number
    pro: number
    premium: number
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

export interface UserInfo {
  id: string
  email: string
  full_name: string | null
  tier: string
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
