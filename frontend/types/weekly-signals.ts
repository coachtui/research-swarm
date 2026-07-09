// WeeklySignal API response types

export interface WeeklySignalPublic {
  ticker: string
  verdict: 'buy' | 'hold' | 'avoid' | null
  fair_value_gap_pct: number | null
  synthesis_summary: string | null
  run_date: string
  current_price: number | null
  screener_score: number | null
  es_change_pct: number | null
  nq_change_pct: number | null
  dow_change_pct: number | null
  prior_verdict: 'buy' | 'hold' | 'avoid' | null
}

export interface WeeklySignalFull extends WeeklySignalPublic {
  fair_value: number | null
  ev_probability: number | null
  stop_loss_probability: number | null
  insider_score: number | null
  dark_pool_score: number | null
  sentiment_score: number | null
  catalyst_summary: string | null
  position_size_rec: string | null
  prior_ev_probability: number | null
}

export interface MarketContext {
  es_change_pct: number | null
  nq_change_pct: number | null
  dow_change_pct: number | null
}

export interface LeaderboardResponse {
  run_date: string | null
  market_context: MarketContext
  rows: WeeklySignalPublic[]
  total: number
  is_full_view?: boolean
}

export interface TrackRecordStats {
  analyzed: number
  buy: number
  hold: number
  avoid: number
}

export interface TrackRecordWeek {
  run_date: string
  stats: TrackRecordStats
  rows: WeeklySignalPublic[]
}

export interface TrackRecordResponse {
  weeks: TrackRecordWeek[]
  total_weeks: number
}
