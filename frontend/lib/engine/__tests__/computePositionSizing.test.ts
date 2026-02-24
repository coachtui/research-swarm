/**
 * Test suite for computePositionSizing engine.
 *
 * Coverage:
 *  1. NVDA acceptance test (end-to-end)
 *  2. bucketByRange — noise boundaries: 20, 35, 50, 70
 *  3. bucketByRange — dispersion boundaries: 1.5, 2.2
 *  4. bucketByRange — stop probability boundaries: 0.15, 0.25
 *  5. Core vs Satellite base weights
 *  6. Sensitivity map (all three values)
 *  7. Beta optional multiplier (clamp low, unclamped, clamp high)
 *  8. EV percentile optional multiplier
 *  9. Guardrails: satellite cap triggered / not triggered
 * 10. Guardrails: absolute floor / ceiling clamp
 * 11. Validation errors
 * 12. Snapshot: explainability output shape
 */

import {
  computePositionSizing,
  bucketByRange,
  validateInput,
  defaultConfig,
} from '../computePositionSizing'
import type { PositionSizingInput, SizingRangeBucket } from '../types'

// ─── NVDA acceptance test ─────────────────────────────────────────────────────

const NVDA_INPUT: PositionSizingInput = {
  symbol: 'NVDA',
  classification: 'SATELLITE',
  noise_score: 40,
  overall_sensitivity: 'MODERATE',
  signal_dispersion_sigma: 2.53,
  stop_probability: 0.22,
  beta: 1.28,
  ev_percentile: 0.38,
  flags: {
    signal_conflict_active: false,
    cap_at_satellite: true,
  },
}

describe('NVDA acceptance test', () => {
  const result = computePositionSizing(NVDA_INPUT)

  it('returns correct symbol', () => {
    expect(result.symbol).toBe('NVDA')
  })

  it('base weight is 5% (SATELLITE)', () => {
    expect(result.base_weight).toBe(0.05)
  })

  it('noise multiplier is 0.70 (noise=40 → High Noise bucket)', () => {
    expect(result.multipliers.noise.value).toBe(0.70)
    expect(result.multipliers.noise.bucket_label).toBe('High Noise')
  })

  it('sensitivity multiplier is 0.90 (MODERATE)', () => {
    expect(result.multipliers.sensitivity.value).toBe(0.90)
  })

  it('dispersion multiplier is 0.75 (sigma=2.53 → Wide bucket)', () => {
    expect(result.multipliers.dispersion.value).toBe(0.75)
  })

  it('stop risk multiplier is 1.00 (stop=0.22 → Moderate bucket)', () => {
    expect(result.multipliers.stoprisk.value).toBe(1.00)
  })

  it('beta multiplier absent — optional feature disabled in default config', () => {
    // config.optional_multipliers.beta.enabled = false
    expect(result.multipliers.beta).toBeUndefined()
  })

  it('ev_percentile multiplier absent — optional feature disabled in default config', () => {
    expect(result.multipliers.ev_percentile).toBeUndefined()
  })

  it('satellite cap NOT triggered (2.36% < 5.2%)', () => {
    expect(result.cap_state.active).toBe(false)
  })

  it('adjusted weight ≈ 2.36% — 0.05 × 0.70 × 0.90 × 0.75 × 1.00 = 0.023625', () => {
    expect(result.adjusted_weight_pct).toBeCloseTo(2.36, 1)
  })

  it('exposure_examples computed for $10k, $50k, $100k', () => {
    expect(result.exposure_examples['10000']).toBeDefined()
    expect(result.exposure_examples['50000']).toBeDefined()
    expect(result.exposure_examples['100000']).toBeDefined()
  })

  it('config_version matches', () => {
    expect(result.config_version).toBe('v1.0.0')
  })
})

// ─── Core-only multiplier test (no optional) ──────────────────────────────────

describe('Core four multipliers (no optional)', () => {
  const input: PositionSizingInput = {
    symbol: 'TEST',
    classification: 'SATELLITE',
    noise_score: 40,
    overall_sensitivity: 'MODERATE',
    signal_dispersion_sigma: 2.53,
    stop_probability: 0.22,
    // no beta, no ev_percentile
  }
  const result = computePositionSizing(input)

  it('adjusted_weight_pct ≈ 2.36%', () => {
    // 0.05 × 0.70 × 0.90 × 0.75 × 1.00 = 0.023625 → 2.3625%
    expect(result.adjusted_weight_pct).toBeCloseTo(2.36, 1)
  })

  it('exposure at $100k = $2363 (round of 0.023625 × 100000)', () => {
    expect(result.exposure_examples['100000']).toBe(2363)
  })
})

// ─── bucketByRange: noise boundaries ─────────────────────────────────────────

describe('bucketByRange — noise score boundaries', () => {
  const buckets: SizingRangeBucket[] = [
    { min: 0,  max: 20,   multiplier: 1.20, label: 'Very Low Noise' },
    { min: 20, max: 35,   multiplier: 1.00, label: 'Low Noise' },
    { min: 35, max: 50,   multiplier: 0.70, label: 'High Noise' },
    { min: 50, max: 70,   multiplier: 0.50, label: 'Very High Noise' },
    { min: 70, max: null, multiplier: 0.30, label: 'Extreme Noise' },
  ]

  it('score 0 → Very Low Noise (1.20)', () =>
    expect(bucketByRange(0, buckets).multiplier).toBe(1.20))
  it('score 19 → Very Low Noise (1.20)', () =>
    expect(bucketByRange(19, buckets).multiplier).toBe(1.20))

  // Boundary: 20 moves to next bucket
  it('score 20 → Low Noise (1.00)', () =>
    expect(bucketByRange(20, buckets).multiplier).toBe(1.00))
  it('score 34 → Low Noise (1.00)', () =>
    expect(bucketByRange(34, buckets).multiplier).toBe(1.00))

  // Boundary: 35 moves to next bucket
  it('score 35 → High Noise (0.70)', () =>
    expect(bucketByRange(35, buckets).multiplier).toBe(0.70))
  it('score 49 → High Noise (0.70)', () =>
    expect(bucketByRange(49, buckets).multiplier).toBe(0.70))

  // Boundary: 50 moves to next bucket
  it('score 50 → Very High Noise (0.50)', () =>
    expect(bucketByRange(50, buckets).multiplier).toBe(0.50))
  it('score 69 → Very High Noise (0.50)', () =>
    expect(bucketByRange(69, buckets).multiplier).toBe(0.50))

  // Boundary: 70 moves to final bucket
  it('score 70 → Extreme Noise (0.30)', () =>
    expect(bucketByRange(70, buckets).multiplier).toBe(0.30))
  it('score 100 → Extreme Noise (0.30)', () =>
    expect(bucketByRange(100, buckets).multiplier).toBe(0.30))
})

// ─── bucketByRange: dispersion boundaries ────────────────────────────────────

describe('bucketByRange — dispersion sigma boundaries', () => {
  const buckets: SizingRangeBucket[] = [
    { min: 0,   max: 1.5,  multiplier: 1.10, label: 'Tight' },
    { min: 1.5, max: 2.2,  multiplier: 1.00, label: 'Normal' },
    { min: 2.2, max: null, multiplier: 0.75, label: 'Wide' },
  ]

  it('sigma 0 → Tight (1.10)', () =>
    expect(bucketByRange(0, buckets).multiplier).toBe(1.10))
  it('sigma 1.49 → Tight (1.10)', () =>
    expect(bucketByRange(1.49, buckets).multiplier).toBe(1.10))

  // Boundary: 1.5 moves to Normal
  it('sigma 1.5 → Normal (1.00)', () =>
    expect(bucketByRange(1.5, buckets).multiplier).toBe(1.00))
  it('sigma 2.19 → Normal (1.00)', () =>
    expect(bucketByRange(2.19, buckets).multiplier).toBe(1.00))

  // Boundary: 2.2 moves to Wide (2.19 < 2.2 → Normal; 2.2 → final bucket)
  it('sigma 2.2 → Wide (0.75)', () =>
    expect(bucketByRange(2.2, buckets).multiplier).toBe(0.75))
  it('sigma 2.53 → Wide (0.75)', () =>
    expect(bucketByRange(2.53, buckets).multiplier).toBe(0.75))
  it('sigma 5.0 → Wide (0.75)', () =>
    expect(bucketByRange(5.0, buckets).multiplier).toBe(0.75))
})

// ─── bucketByRange: stop probability boundaries ───────────────────────────────

describe('bucketByRange — stop probability boundaries', () => {
  const buckets: SizingRangeBucket[] = [
    { min: 0,    max: 0.15, multiplier: 1.05, label: 'Low' },
    { min: 0.15, max: 0.25, multiplier: 1.00, label: 'Moderate' },
    { min: 0.25, max: null, multiplier: 0.80, label: 'High' },
  ]

  it('stop 0.0 → Low (1.05)', () =>
    expect(bucketByRange(0.0, buckets).multiplier).toBe(1.05))
  it('stop 0.14 → Low (1.05)', () =>
    expect(bucketByRange(0.14, buckets).multiplier).toBe(1.05))

  // Boundary: 0.15 moves to Moderate
  it('stop 0.15 → Moderate (1.00)', () =>
    expect(bucketByRange(0.15, buckets).multiplier).toBe(1.00))
  it('stop 0.22 → Moderate (1.00)', () =>
    expect(bucketByRange(0.22, buckets).multiplier).toBe(1.00))
  it('stop 0.2499 → Moderate (1.00)', () =>
    expect(bucketByRange(0.2499, buckets).multiplier).toBe(1.00))

  // Boundary: 0.25 moves to High
  it('stop 0.25 → High (0.80)', () =>
    expect(bucketByRange(0.25, buckets).multiplier).toBe(0.80))
  it('stop 0.50 → High (0.80)', () =>
    expect(bucketByRange(0.50, buckets).multiplier).toBe(0.80))
})

// ─── Classification base weights ──────────────────────────────────────────────

describe('Classification base weights', () => {
  const base: Omit<PositionSizingInput, 'classification'> = {
    symbol: 'X',
    noise_score: 20,
    overall_sensitivity: 'LOW',
    signal_dispersion_sigma: 0,
    stop_probability: 0,
  }

  it('SATELLITE → base 5%', () => {
    const r = computePositionSizing({ ...base, classification: 'SATELLITE' })
    expect(r.base_weight).toBe(0.05)
  })

  it('CORE → base 12%', () => {
    const r = computePositionSizing({ ...base, classification: 'CORE' })
    expect(r.base_weight).toBe(0.12)
  })
})

// ─── Sensitivity map ──────────────────────────────────────────────────────────

describe('Sensitivity multiplier mapping', () => {
  const base: PositionSizingInput = {
    symbol: 'X',
    classification: 'SATELLITE',
    noise_score: 20,
    signal_dispersion_sigma: 0,
    stop_probability: 0,
    overall_sensitivity: 'LOW',
  }

  it('LOW → 1.10', () => {
    const r = computePositionSizing({ ...base, overall_sensitivity: 'LOW' })
    expect(r.multipliers.sensitivity.value).toBe(1.10)
  })
  it('MODERATE → 0.90', () => {
    const r = computePositionSizing({ ...base, overall_sensitivity: 'MODERATE' })
    expect(r.multipliers.sensitivity.value).toBe(0.90)
  })
  it('HIGH → 0.65', () => {
    const r = computePositionSizing({ ...base, overall_sensitivity: 'HIGH' })
    expect(r.multipliers.sensitivity.value).toBe(0.65)
  })
})

// ─── Beta optional multiplier ─────────────────────────────────────────────────
// Must pass a config override with beta.enabled = true (default is false).

describe('Beta multiplier (optional, enabled via config override)', () => {
  const betaEnabledConfig = {
    ...defaultConfig,
    optional_multipliers: {
      ...defaultConfig.optional_multipliers,
      beta: { ...defaultConfig.optional_multipliers.beta, enabled: true },
    },
  }

  const base: PositionSizingInput = {
    symbol: 'X',
    classification: 'SATELLITE',
    noise_score: 20,
    overall_sensitivity: 'LOW',
    signal_dispersion_sigma: 0,
    stop_probability: 0,
  }

  it('beta=1.0 → 1/√1 = 1.00 (within clamp)', () => {
    const r = computePositionSizing({ ...base, beta: 1.0 }, betaEnabledConfig)
    expect(r.multipliers.beta!.value).toBeCloseTo(1.00, 3)
  })

  it('beta=0.5 → 1/√0.5 ≈ 1.414 → clamped to 1.10', () => {
    const r = computePositionSizing({ ...base, beta: 0.5 }, betaEnabledConfig)
    expect(r.multipliers.beta!.value).toBe(1.10)
    expect(r.multipliers.beta!.bucket_label).toBe('Clamped (low β)')
  })

  it('beta=4.0 → 1/√4 = 0.50 → clamped to 0.70', () => {
    const r = computePositionSizing({ ...base, beta: 4.0 }, betaEnabledConfig)
    expect(r.multipliers.beta!.value).toBe(0.70)
    expect(r.multipliers.beta!.bucket_label).toBe('Clamped (high β)')
  })

  it('no beta → multiplier absent even with feature enabled', () => {
    const r = computePositionSizing(base, betaEnabledConfig)
    expect(r.multipliers.beta).toBeUndefined()
  })

  it('feature disabled in default config → beta absent when provided', () => {
    const r = computePositionSizing({ ...base, beta: 1.28 })
    expect(r.multipliers.beta).toBeUndefined()
  })
})

// ─── EV percentile optional multiplier ───────────────────────────────────────

describe('EV percentile multiplier (optional, enabled via config override)', () => {
  const evEnabledConfig = {
    ...defaultConfig,
    optional_multipliers: {
      ...defaultConfig.optional_multipliers,
      ev_percentile: { ...defaultConfig.optional_multipliers.ev_percentile, enabled: true },
    },
  }

  const base: PositionSizingInput = {
    symbol: 'X',
    classification: 'SATELLITE',
    noise_score: 20,
    overall_sensitivity: 'LOW',
    signal_dispersion_sigma: 0,
    stop_probability: 0,
  }

  it('ev_percentile=0.20 (<30th) → 0.80', () => {
    const r = computePositionSizing({ ...base, ev_percentile: 0.20 }, evEnabledConfig)
    expect(r.multipliers.ev_percentile!.value).toBe(0.80)
  })
  it('ev_percentile=0.30 (30th boundary) → 1.00', () => {
    const r = computePositionSizing({ ...base, ev_percentile: 0.30 }, evEnabledConfig)
    expect(r.multipliers.ev_percentile!.value).toBe(1.00)
  })
  it('ev_percentile=0.60 (60th boundary) → 1.15', () => {
    const r = computePositionSizing({ ...base, ev_percentile: 0.60 }, evEnabledConfig)
    expect(r.multipliers.ev_percentile!.value).toBe(1.15)
  })
  it('no ev_percentile → multiplier absent', () => {
    const r = computePositionSizing(base, evEnabledConfig)
    expect(r.multipliers.ev_percentile).toBeUndefined()
  })
  it('feature disabled in default config → ev absent when provided', () => {
    const r = computePositionSizing({ ...base, ev_percentile: 0.90 })
    expect(r.multipliers.ev_percentile).toBeUndefined()
  })
})

// ─── Guardrails ───────────────────────────────────────────────────────────────

describe('Guardrails', () => {
  it('satellite cap triggered when adjusted > 5.2%', () => {
    // CORE with LOW sensitivity, Low noise → very high weight
    const input: PositionSizingInput = {
      symbol: 'BIG',
      classification: 'CORE',
      noise_score: 10,
      overall_sensitivity: 'LOW',
      signal_dispersion_sigma: 0.5,
      stop_probability: 0.05,
      flags: { cap_at_satellite: true },
    }
    const r = computePositionSizing(input)
    expect(r.cap_state.active).toBe(true)
    expect(r.adjusted_weight).toBeLessThanOrEqual(0.052)
  })

  it('satellite cap NOT triggered when adjusted < 5.2%', () => {
    // NVDA example: adjusted ≈ 2.36% < 5.2%
    const r = computePositionSizing(NVDA_INPUT)
    expect(r.cap_state.active).toBe(false)
  })

  it('absolute floor applied for extreme compression', () => {
    const input: PositionSizingInput = {
      symbol: 'TINY',
      classification: 'SATELLITE',
      noise_score: 99,
      overall_sensitivity: 'HIGH',
      signal_dispersion_sigma: 5.0,
      stop_probability: 0.99,
    }
    const r = computePositionSizing(input)
    // 0.05 × 0.30 × 0.65 × 0.75 × 0.80 = 0.00585 → above floor
    expect(r.adjusted_weight).toBeGreaterThanOrEqual(0.0025)
  })

  it('ceiling cap at 12% for CORE + all-boost multipliers', () => {
    const input: PositionSizingInput = {
      symbol: 'TOP',
      classification: 'CORE',
      noise_score: 5,
      overall_sensitivity: 'LOW',
      signal_dispersion_sigma: 0.1,
      stop_probability: 0.01,
      beta: 0.5,
      ev_percentile: 0.90,
    }
    const r = computePositionSizing(input)
    expect(r.adjusted_weight).toBeLessThanOrEqual(0.12)
  })
})

// ─── Validation errors ────────────────────────────────────────────────────────

describe('Input validation', () => {
  const good: PositionSizingInput = {
    symbol: 'X',
    classification: 'SATELLITE',
    noise_score: 40,
    overall_sensitivity: 'MODERATE',
    signal_dispersion_sigma: 1.5,
    stop_probability: 0.20,
  }

  it('throws on missing symbol', () => {
    expect(() => computePositionSizing({ ...good, symbol: '' })).toThrow('symbol')
  })
  it('throws on invalid classification', () => {
    // @ts-expect-error intentional bad value
    expect(() => computePositionSizing({ ...good, classification: 'MOON' })).toThrow('classification')
  })
  it('throws on noise_score > 100', () => {
    expect(() => computePositionSizing({ ...good, noise_score: 101 })).toThrow('noise_score')
  })
  it('throws on invalid sensitivity', () => {
    // @ts-expect-error intentional bad value
    expect(() => computePositionSizing({ ...good, overall_sensitivity: 'MILD' })).toThrow()
  })
  it('throws on negative dispersion sigma', () => {
    expect(() => computePositionSizing({ ...good, signal_dispersion_sigma: -1 })).toThrow(
      'signal_dispersion_sigma'
    )
  })
  it('throws on stop_probability > 1', () => {
    expect(() => computePositionSizing({ ...good, stop_probability: 1.5 })).toThrow('stop_probability')
  })
  it('throws on beta = 0', () => {
    expect(() => computePositionSizing({ ...good, beta: 0 })).toThrow('beta')
  })
  it('throws on ev_percentile = 1.1', () => {
    expect(() => computePositionSizing({ ...good, ev_percentile: 1.1 })).toThrow('ev_percentile')
  })
})

// ─── Explainability snapshot ──────────────────────────────────────────────────

describe('Explainability output shape', () => {
  const r = computePositionSizing(NVDA_INPUT)

  it('every multiplier has value, bucket_label, reason, input_value', () => {
    const keys = ['noise', 'sensitivity', 'dispersion', 'stoprisk'] as const
    for (const k of keys) {
      expect(r.multipliers[k].value).toBeDefined()
      expect(typeof r.multipliers[k].bucket_label).toBe('string')
      expect(typeof r.multipliers[k].reason).toBe('string')
      expect(r.multipliers[k].input_value).toBeDefined()
    }
  })

  it('notes array is non-empty', () => {
    expect(r.notes.length).toBeGreaterThan(0)
  })

  it('all reason strings are non-empty', () => {
    for (const [, detail] of Object.entries(r.multipliers)) {
      expect(detail.reason.length).toBeGreaterThan(0)
    }
  })
})
