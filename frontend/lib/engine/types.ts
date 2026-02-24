// ─── Dynamic Position Sizing Engine — Type Contracts ─────────────────────────
// All types are versioned alongside config/sizing-config.v1.json

export type Classification = 'CORE' | 'SATELLITE'
export type Sensitivity = 'LOW' | 'MODERATE' | 'HIGH'

export interface PositionSizingFlags {
  /** Hard cap active (smart money divergence detected) */
  signal_conflict_active?: boolean
  /** Force size at or below satellite cap regardless of classification */
  cap_at_satellite?: boolean
}

/** Input contract for the position sizing engine. All fields required unless noted. */
export interface PositionSizingInput {
  symbol: string
  /** CORE = 12% base; SATELLITE = 5% base */
  classification: Classification
  /** 0–100: higher = noisier signal regime */
  noise_score: number
  /** Derived from ModelSensitivityAttribution */
  overall_sensitivity: Sensitivity
  /** σ across all signals (from signal_spread); higher = more internal disagreement */
  signal_dispersion_sigma: number
  /** 0–1: probability of hitting stop loss during hold period */
  stop_probability: number
  /** Optional: market beta. Triggers M_beta = clamp(1/√β, 0.70, 1.10) */
  beta?: number
  /** Optional: 0–1 percentile of expected value distribution */
  ev_percentile?: number
  flags?: PositionSizingFlags
}

// ─── Output types ─────────────────────────────────────────────────────────────

export interface MultiplierDetail {
  /** Numeric multiplier applied (e.g., 0.70) */
  value: number
  /** Human-readable bucket label (e.g., "High Noise") */
  bucket_label: string
  /** One-line rationale string */
  reason: string
  /** Raw input value that triggered this bucket */
  input_value: string | number
}

export interface CapState {
  active: boolean
  reason: string
  /** The cap ceiling that was applied */
  cap_value?: number
}

export interface PositionSizingOutput {
  symbol: string
  base_weight: number
  multipliers: {
    noise: MultiplierDetail
    sensitivity: MultiplierDetail
    dispersion: MultiplierDetail
    stoprisk: MultiplierDetail
    beta?: MultiplierDetail
    ev_percentile?: MultiplierDetail
  }
  /** Product of all applied multipliers (before × base) */
  product_of_multipliers: number
  /** Final clamped weight as a decimal (e.g., 0.0236) */
  adjusted_weight: number
  /** Final weight as a percentage (e.g., 2.36) */
  adjusted_weight_pct: number
  cap_state: CapState
  notes: string[]
  /** Dollar exposure for common portfolio sizes: { "10000": 236, ... } */
  exposure_examples: Record<string, number>
  config_version: string
}

// ─── Config schema (mirrors sizing-config.v1.json) ────────────────────────────

export interface SizingRangeBucket {
  min: number
  max: number | null
  multiplier: number
  label: string
}

export interface SizingSensitivityEntry {
  multiplier: number
  label: string
}

export interface SizingConfig {
  version: string
  base_weights: {
    CORE: number
    SATELLITE: number
  }
  caps: {
    min_weight: number
    max_weight: number
    satellite_cap: number
  }
  noise_score_buckets: SizingRangeBucket[]
  sensitivity_map: Record<string, SizingSensitivityEntry>
  dispersion_sigma_buckets: SizingRangeBucket[]
  stop_probability_buckets: SizingRangeBucket[]
  optional_multipliers: {
    beta: {
      enabled: boolean
      formula?: string
      clamp_min: number
      clamp_max: number
    }
    ev_percentile: {
      enabled: boolean
      buckets: SizingRangeBucket[]
    }
  }
  exposure_example_sizes: number[]
}
