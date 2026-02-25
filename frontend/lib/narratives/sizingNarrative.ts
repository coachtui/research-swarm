/**
 * Sizing Narrative Generator
 *
 * Derives institutional-language narrative from model outputs.
 * Zero new calculations — presentation-layer interpretation only.
 *
 * DVRG Capital Allocation Discipline language throughout:
 * Execution-bound | Cap-bound | Structural Bias | Tactical Stance | Deployment Status
 */

import type { StructuralBias, TacticalStance } from '@/lib/utils/decisionDimensions'

// ── Input / Output types ─────────────────────────────────────────────────────

export interface SizingNarrativeInputs {
  structural_bias: StructuralBias
  tactical_stance: TacticalStance
  deployment_status: 'Active' | 'Deferred' | 'Restricted'
  final_weight_pct: number
  execution_weight_pct: number   // conviction.recommended_pct (post-multiplier, pre-cap)
  policy_cap_pct: number         // conviction.max_pct
  dispersion_sigma: number | null  // signal_spread (σ across signals)
  noise_score: number | null       // noise_filter.noise_score (0–100)
  stop_probability_pct: number | null  // stop_probability.effective_stop_probability_pct
  institutional_posture: 'accumulation' | 'distribution' | 'neutral' | null
  conviction_level: string  // HIGH | MODERATE | LOW (or High | Moderate | Low)
}

export interface SizingNarrativeOutput {
  summary: string             // max 2 sentences
  drivers: string[]           // max 3 constraint bullets
  posture_shift_triggers: string[]  // max 3 bullets describing what lifts posture
}

// ── Severity thresholds (from spec) ─────────────────────────────────────────

const DISPERSION_THRESHOLD = 2.5
const NOISE_THRESHOLD = 35
const STOP_PROB_THRESHOLD = 20
const CAP_PROXIMITY = 0.95   // within 95% of cap = cap-bound

// ── Constraint detection ─────────────────────────────────────────────────────

type ConstraintBound = 'execution' | 'cap' | 'risk' | 'none'

/** Detects the primary sizing constraint from allocation math. Pure interpretation. */
function detectConstraintBound(inputs: SizingNarrativeInputs): ConstraintBound {
  const { final_weight_pct, policy_cap_pct, conviction_level } = inputs
  const lvl = conviction_level.toUpperCase()
  const multiplier = lvl === 'HIGH' ? 1.0 : lvl === 'MODERATE' ? 0.7 : 0.4

  // Cap-bound: final weight is at or near policy cap
  if (final_weight_pct >= policy_cap_pct * CAP_PROXIMITY) return 'cap'

  // Execution-bound: execution multiplier is constraining, cap is not the limit
  if (multiplier < 1.0 && final_weight_pct < policy_cap_pct * CAP_PROXIMITY) return 'execution'

  // Risk-bound: stop probability is the primary constraint
  if ((inputs.stop_probability_pct ?? 0) >= STOP_PROB_THRESHOLD) return 'risk'

  return 'none'
}

// ── Driver bullets ───────────────────────────────────────────────────────────

function buildDrivers(inputs: SizingNarrativeInputs): string[] {
  const drivers: string[] = []
  const bound = detectConstraintBound(inputs)

  if (bound === 'execution') {
    const lvl = inputs.conviction_level.toUpperCase()
    drivers.push(
      lvl === 'LOW'
        ? 'Low conviction environment — execution multiplier reduces deployable allocation to 0.4× of baseline'
        : 'Moderate conviction environment — execution multiplier applied (0.7×), below full deployment threshold'
    )
  }

  if (bound === 'cap') {
    drivers.push(
      `Policy cap reached — allocation ceiling limits deployment at ${inputs.policy_cap_pct}% of portfolio`
    )
  }

  if ((inputs.dispersion_sigma ?? 0) >= DISPERSION_THRESHOLD) {
    drivers.push(
      `Signal dispersion elevated (σ ${inputs.dispersion_sigma?.toFixed(1)}) — regime uncertainty constraining position sizing`
    )
  }

  if ((inputs.noise_score ?? 0) >= NOISE_THRESHOLD) {
    drivers.push(
      `Noise regime active (score ${inputs.noise_score}) — signal-to-noise ratio degraded, sizing conserved`
    )
  }

  if ((inputs.stop_probability_pct ?? 0) >= STOP_PROB_THRESHOLD) {
    drivers.push(
      `Adverse exit probability elevated (${inputs.stop_probability_pct?.toFixed(0)}%) — position sized to risk envelope constraints`
    )
  }

  if (inputs.institutional_posture === 'distribution') {
    drivers.push(
      'Institutional flow in distribution phase — conviction weight reduced pending re-accumulation signal'
    )
  }

  return drivers.slice(0, 3)
}

// ── Posture-shift triggers ───────────────────────────────────────────────────

function buildPostureShiftTriggers(inputs: SizingNarrativeInputs): string[] {
  const { tactical_stance, dispersion_sigma, noise_score, stop_probability_pct } = inputs

  if (tactical_stance === 'Favorable') {
    return ['Current conditions support deployment — re-evaluate on material signal or regime change']
  }

  if (tactical_stance === 'Defensive') {
    return [
      'Regime transition from defensive to neutral or constructive posture',
      'Structural bias inflection — fundamental conditions stabilize',
      'Signal dispersion compresses below divergence threshold',
    ]
  }

  const triggers: string[] = []

  if ((dispersion_sigma ?? 0) >= DISPERSION_THRESHOLD) {
    triggers.push(
      `Dispersion convergence below σ ${DISPERSION_THRESHOLD} — signal alignment restores deployment confidence`
    )
  }

  if ((noise_score ?? 0) >= NOISE_THRESHOLD) {
    triggers.push(
      `Noise compression below ${NOISE_THRESHOLD} — regime transition to clean signal environment unlocks full sizing`
    )
  }

  if ((stop_probability_pct ?? 0) >= STOP_PROB_THRESHOLD) {
    triggers.push(
      `Stop probability reducing below ${STOP_PROB_THRESHOLD}% — risk envelope widens, allocation can be reinstated`
    )
  }

  if (inputs.institutional_posture === 'distribution') {
    triggers.push('Institutional flow shift from distribution to accumulation phase')
  }

  if (triggers.length < 2 && tactical_stance === 'Deferred') {
    triggers.push('Valuation regime normalization — price approaches structural entry zone')
  }

  if (triggers.length < 2 && tactical_stance === 'Opportunistic') {
    triggers.push('Entry signal confirmation — confirm flow turns accumulating before full sizing')
  }

  return triggers.slice(0, 3)
}

// ── Main export ──────────────────────────────────────────────────────────────

/**
 * Generates an institutional-language sizing narrative from model outputs.
 * Pure function — no network calls, no state, no side effects.
 */
export function generateSizingNarrative(inputs: SizingNarrativeInputs): SizingNarrativeOutput {
  const { structural_bias, tactical_stance, deployment_status, policy_cap_pct } = inputs
  const bound = detectConstraintBound(inputs)

  // Sentence 1: structural + tactical classification
  const sentence1 = `Structural bias remains ${structural_bias} with ${tactical_stance.toLowerCase()} tactical conditions.`

  // Sentence 2: deployment status + primary constraint
  const deploymentPhrase =
    deployment_status === 'Active'
      ? 'Deployment is Active'
      : deployment_status === 'Restricted'
      ? 'Deployment is Restricted — risk regime governs capital posture'
      : 'Deployment is Deferred — entry conditions unfavorable'

  const envFactors: string[] = []
  if ((inputs.dispersion_sigma ?? 0) >= DISPERSION_THRESHOLD) envFactors.push('elevated dispersion')
  if ((inputs.noise_score ?? 0) >= NOISE_THRESHOLD) envFactors.push('regime noise')
  const envSuffix = envFactors.length > 0 ? ` due to ${envFactors.join(' and ')}` : ''

  let constraintPhrase = ''
  if (bound === 'execution') {
    constraintPhrase = ', but sizing is execution-bound due to reduced signal reliability'
  } else if (bound === 'cap') {
    constraintPhrase = `, sizing held at policy cap (${policy_cap_pct}%)`
  } else if (bound === 'risk') {
    constraintPhrase = ', but sizing is risk-bound due to elevated stop probability'
  }

  const sentence2 = `${deploymentPhrase}${constraintPhrase}${envSuffix}.`

  return {
    summary: `${sentence1} ${sentence2}`,
    drivers: buildDrivers(inputs),
    posture_shift_triggers: buildPostureShiftTriggers(inputs),
  }
}

// ── Derived label helpers ────────────────────────────────────────────────────

/** Derives deployment status from Tactical Stance. */
export function deriveDeploymentStatus(stance: TacticalStance): 'Active' | 'Deferred' | 'Restricted' {
  if (stance === 'Favorable' || stance === 'Opportunistic') return 'Active'
  if (stance === 'Defensive') return 'Restricted'
  return 'Deferred'
}

/** Derives position type (Satellite vs Core) from structural bias and conviction. */
export function derivePositionType(bias: StructuralBias, convictionLevel: string): 'Core' | 'Satellite' {
  const lvl = convictionLevel.toUpperCase()
  if (bias === 'Bullish' && lvl === 'HIGH') return 'Core'
  return 'Satellite'
}

/** Derives human-readable constraint tag from allocation math. */
export function deriveConstraintTag(
  finalWeightPct: number,
  policyCapPct: number,
  convictionLevel: string,
): 'Execution-bound' | 'Cap-bound' | 'Within Guardrails' {
  const lvl = convictionLevel.toUpperCase()
  const multiplier = lvl === 'HIGH' ? 1.0 : lvl === 'MODERATE' ? 0.7 : 0.4
  if (finalWeightPct >= policyCapPct * CAP_PROXIMITY) return 'Cap-bound'
  if (multiplier < 1.0 && finalWeightPct < policyCapPct * CAP_PROXIMITY) return 'Execution-bound'
  return 'Within Guardrails'
}

/** Derives institutional posture label from institutional score (0–10). */
export function deriveInstitutionalPosture(
  institutionalScore: number | null | undefined,
): 'accumulation' | 'distribution' | 'neutral' | null {
  if (institutionalScore == null) return null
  if (institutionalScore >= 7) return 'accumulation'
  if (institutionalScore <= 3) return 'distribution'
  return 'neutral'
}
