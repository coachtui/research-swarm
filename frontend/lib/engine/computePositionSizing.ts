/**
 * Dynamic Position Sizing Engine — Noise-Adjusted Exposure
 *
 * Pure deterministic function: no randomness, no side-effects.
 * All threshold mappings are driven by config/sizing-config.v1.json.
 *
 * AdjustedWeight = BaseWeight × M_noise × M_sensitivity × M_dispersion × M_stoprisk
 *                × (M_beta?) × (M_ev_percentile?)
 *
 * Acceptance test (NVDA):
 *   noise=40, sensitivity=MODERATE, sigma=2.53, stop=0.22
 *   → 0.05 × 0.70 × 0.90 × 0.75 × 1.00 = 2.36%
 */

import type {
  SizingConfig,
  SizingRangeBucket,
  PositionSizingInput,
  PositionSizingOutput,
  MultiplierDetail,
  CapState,
} from './types'

// Import the versioned config as a module (resolveJsonModule: true in tsconfig)
import rawConfig from '../../../config/sizing-config.v1.json'

export const defaultConfig: SizingConfig = rawConfig as SizingConfig

// ─── Core bucket utility ──────────────────────────────────────────────────────

/**
 * Select a range bucket for a given value.
 *
 * Boundary convention: [min, max) — lower inclusive, upper exclusive.
 * The final bucket (max === null) matches everything ≥ min.
 *
 * Examples:
 *   noise 20  → [20, 35)  bucket (not [0, 20) — 20 is excluded from first)
 *   noise 70  → [70, ∞)   bucket (last)
 *   sigma 2.2 → [2.2, ∞)  bucket (last; 2.2 < 2.2 is false in prior bucket)
 */
export function bucketByRange(
  value: number,
  buckets: SizingRangeBucket[]
): { multiplier: number; label: string } {
  for (const bucket of buckets) {
    const hi = bucket.max
    if (hi === null) {
      // Final bucket: [min, ∞)
      return { multiplier: bucket.multiplier, label: bucket.label }
    }
    if (value >= bucket.min && value < hi) {
      return { multiplier: bucket.multiplier, label: bucket.label }
    }
  }
  // Fallback (should never reach here with valid config)
  const last = buckets[buckets.length - 1]
  return { multiplier: last.multiplier, label: last.label }
}

// ─── Input validation ─────────────────────────────────────────────────────────

export function validateInput(input: PositionSizingInput): void {
  const errors: string[] = []

  if (!input.symbol || typeof input.symbol !== 'string') {
    errors.push('symbol must be a non-empty string')
  }
  if (!['CORE', 'SATELLITE'].includes(input.classification)) {
    errors.push(`classification must be CORE or SATELLITE, got: ${input.classification}`)
  }
  if (typeof input.noise_score !== 'number' || input.noise_score < 0 || input.noise_score > 100) {
    errors.push(`noise_score must be 0–100, got: ${input.noise_score}`)
  }
  if (!['LOW', 'MODERATE', 'HIGH'].includes(input.overall_sensitivity)) {
    errors.push(`overall_sensitivity must be LOW/MODERATE/HIGH, got: ${input.overall_sensitivity}`)
  }
  if (typeof input.signal_dispersion_sigma !== 'number' || input.signal_dispersion_sigma < 0) {
    errors.push(`signal_dispersion_sigma must be ≥ 0, got: ${input.signal_dispersion_sigma}`)
  }
  if (
    typeof input.stop_probability !== 'number' ||
    input.stop_probability < 0 ||
    input.stop_probability > 1
  ) {
    errors.push(`stop_probability must be 0–1, got: ${input.stop_probability}`)
  }
  if (input.beta !== undefined && (typeof input.beta !== 'number' || input.beta <= 0)) {
    errors.push(`beta must be > 0, got: ${input.beta}`)
  }
  if (
    input.ev_percentile !== undefined &&
    (typeof input.ev_percentile !== 'number' ||
      input.ev_percentile < 0 ||
      input.ev_percentile > 1)
  ) {
    errors.push(`ev_percentile must be 0–1, got: ${input.ev_percentile}`)
  }

  if (errors.length > 0) {
    throw new Error(`PositionSizing validation failed:\n• ${errors.join('\n• ')}`)
  }
}

// ─── Main engine ──────────────────────────────────────────────────────────────

export function computePositionSizing(
  input: PositionSizingInput,
  config: SizingConfig = defaultConfig
): PositionSizingOutput {
  validateInput(input)

  const {
    symbol,
    classification,
    noise_score,
    overall_sensitivity,
    signal_dispersion_sigma,
    stop_probability,
    beta,
    ev_percentile,
    flags = {},
  } = input

  // ── Base weight ────────────────────────────────────────────────────────────
  const baseWeight = config.base_weights[classification]

  // ── Noise multiplier ───────────────────────────────────────────────────────
  const noiseBucket = bucketByRange(noise_score, config.noise_score_buckets)
  const noiseMultiplier: MultiplierDetail = {
    value: noiseBucket.multiplier,
    bucket_label: noiseBucket.label,
    reason: `Noise score ${noise_score} → ${noiseBucket.label} bucket`,
    input_value: noise_score,
  }

  // ── Sensitivity multiplier ─────────────────────────────────────────────────
  const sensitivityKey = overall_sensitivity.toUpperCase()
  const sensitivityEntry = config.sensitivity_map[sensitivityKey]
  if (!sensitivityEntry) {
    throw new Error(`Unknown sensitivity value: ${overall_sensitivity}`)
  }
  const sensitivityMultiplier: MultiplierDetail = {
    value: sensitivityEntry.multiplier,
    bucket_label: sensitivityEntry.label,
    reason: `Overall sensitivity ${overall_sensitivity} → ${sensitivityEntry.label}`,
    input_value: overall_sensitivity,
  }

  // ── Dispersion multiplier ──────────────────────────────────────────────────
  const dispBucket = bucketByRange(signal_dispersion_sigma, config.dispersion_sigma_buckets)
  const dispersionMultiplier: MultiplierDetail = {
    value: dispBucket.multiplier,
    bucket_label: dispBucket.label,
    reason: `Dispersion σ ${signal_dispersion_sigma.toFixed(2)} → ${dispBucket.label}`,
    input_value: signal_dispersion_sigma,
  }

  // ── Stop risk multiplier ───────────────────────────────────────────────────
  const stopBucket = bucketByRange(stop_probability, config.stop_probability_buckets)
  const stopMultiplier: MultiplierDetail = {
    value: stopBucket.multiplier,
    bucket_label: stopBucket.label,
    reason: `Stop probability ${(stop_probability * 100).toFixed(0)}% → ${stopBucket.label}`,
    input_value: stop_probability,
  }

  // ── Optional: beta multiplier ──────────────────────────────────────────────
  let betaMultiplier: MultiplierDetail | undefined
  if (beta !== undefined && config.optional_multipliers.beta.enabled) {
    const rawM = 1 / Math.sqrt(beta)
    const { clamp_min, clamp_max } = config.optional_multipliers.beta
    const clamped = Math.max(clamp_min, Math.min(clamp_max, rawM))
    const wasClampedLow = clamped === clamp_min && rawM < clamp_min
    const wasClampedHigh = clamped === clamp_max && rawM > clamp_max
    betaMultiplier = {
      value: clamped,
      bucket_label: wasClampedLow
        ? 'Clamped (high β)'
        : wasClampedHigh
          ? 'Clamped (low β)'
          : 'Beta-normalized',
      reason: `β ${beta.toFixed(2)}: 1/√${beta.toFixed(2)} = ${rawM.toFixed(3)} → clamped [${clamp_min}, ${clamp_max}] → ${clamped.toFixed(3)}`,
      input_value: beta,
    }
  }

  // ── Optional: EV percentile multiplier ────────────────────────────────────
  let evMultiplier: MultiplierDetail | undefined
  if (ev_percentile !== undefined && config.optional_multipliers.ev_percentile.enabled) {
    const evBucket = bucketByRange(ev_percentile, config.optional_multipliers.ev_percentile.buckets)
    evMultiplier = {
      value: evBucket.multiplier,
      bucket_label: evBucket.label,
      reason: `EV percentile ${(ev_percentile * 100).toFixed(0)}th → ${evBucket.label}`,
      input_value: ev_percentile,
    }
  }

  // ── Product ────────────────────────────────────────────────────────────────
  const totalProduct =
    noiseBucket.multiplier *
    sensitivityEntry.multiplier *
    dispBucket.multiplier *
    stopBucket.multiplier *
    (betaMultiplier?.value ?? 1) *
    (evMultiplier?.value ?? 1)

  let adjustedWeight = baseWeight * totalProduct

  // ── Guardrails ────────────────────────────────────────────────────────────
  const notes: string[] = []
  let capState: CapState = { active: false, reason: '' }

  // Hard cap: signal conflict or explicit satellite cap flag
  if (flags.signal_conflict_active || flags.cap_at_satellite) {
    const satCap = config.caps.satellite_cap
    if (adjustedWeight > satCap) {
      adjustedWeight = satCap
      capState = {
        active: true,
        reason: flags.signal_conflict_active
          ? `Signal conflict active — capped at satellite max (${(satCap * 100).toFixed(1)}%)`
          : `cap_at_satellite flag — capped at ${(satCap * 100).toFixed(1)}%`,
        cap_value: satCap,
      }
      notes.push(`⚠ Position capped at ${(satCap * 100).toFixed(1)}% (satellite guardrail)`)
    } else {
      notes.push(
        `Satellite cap ${(satCap * 100).toFixed(1)}% not triggered — ` +
          `${(adjustedWeight * 100).toFixed(2)}% is within guardrail`
      )
    }
  }

  // Absolute clamp: [min_weight, max_weight]
  const { min_weight, max_weight } = config.caps
  const preClamp = adjustedWeight
  adjustedWeight = Math.max(min_weight, Math.min(max_weight, adjustedWeight))
  if (!capState.active && adjustedWeight !== preClamp) {
    if (adjustedWeight === min_weight) {
      notes.push(`Floor applied — minimum position weight ${(min_weight * 100).toFixed(2)}%`)
    } else {
      capState = {
        active: true,
        reason: `Hard ceiling ${(max_weight * 100).toFixed(0)}% reached`,
        cap_value: max_weight,
      }
      notes.push(`Ceiling applied — maximum weight ${(max_weight * 100).toFixed(0)}% enforced`)
    }
  }

  // Informational notes
  if (noise_score >= 50) notes.push('High Noise Environment — compress size')
  if (overall_sensitivity === 'HIGH') notes.push('High sensitivity — aggressive size reduction applied')
  notes.push(
    classification === 'SATELLITE'
      ? `Satellite mandate — base weight ${(baseWeight * 100).toFixed(0)}%`
      : `Core mandate — base weight ${(baseWeight * 100).toFixed(0)}%`
  )

  // ── Dollar exposure examples ───────────────────────────────────────────────
  const exposureExamples: Record<string, number> = {}
  for (const size of config.exposure_example_sizes) {
    exposureExamples[String(size)] = Math.round(size * adjustedWeight)
  }

  // ── Assemble output ────────────────────────────────────────────────────────
  return {
    symbol,
    base_weight: baseWeight,
    multipliers: {
      noise: noiseMultiplier,
      sensitivity: sensitivityMultiplier,
      dispersion: dispersionMultiplier,
      stoprisk: stopMultiplier,
      ...(betaMultiplier ? { beta: betaMultiplier } : {}),
      ...(evMultiplier ? { ev_percentile: evMultiplier } : {}),
    },
    product_of_multipliers: Math.round(totalProduct * 100000) / 100000,
    adjusted_weight: Math.round(adjustedWeight * 1000000) / 1000000,
    adjusted_weight_pct: Math.round(adjustedWeight * 10000) / 100,
    cap_state: capState,
    notes,
    exposure_examples: exposureExamples,
    config_version: config.version,
  }
}
