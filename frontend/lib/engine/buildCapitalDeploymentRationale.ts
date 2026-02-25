/**
 * Capital Deployment Rationale Builder
 *
 * Pure deterministic function — no randomness, no side-effects.
 * Produces a structured PM-style narrative explaining why the final
 * allocation is a specific size, derived entirely from model inputs.
 *
 * Intended to resolve the "BUY + High confidence + small allocation" UX confusion
 * by making the constraint chain explicit and legible.
 *
 * Noise-score interpretation (mirrors NOISE_BUCKETS in position sizing engine):
 *   0–20   Very Low Noise (1.20× multiplier — loosens)
 *   20–35  Low Noise      (1.00× multiplier — neutral)
 *   35–50  High Noise     (0.70× multiplier — tightens)
 *   50–70  Very High Noise(0.50× multiplier — tightens strongly)
 *   70+    Extreme Noise  (0.30× multiplier — tightens severely)
 */

import type {
  SignalBreakdown,
  ConvictionPosition,
  CapitalDeploymentRationale,
  CapitalDeploymentDriver,
} from '@/types/api'

// ─── Input contract ────────────────────────────────────────────────────────────

export interface RationaleInputs {
  /** Rating string from DecisionIntelligence (e.g. "BUY", "HOLD", "SELL") */
  rating: string
  signalBreakdown: SignalBreakdown | null | undefined
  convictionPosition: ConvictionPosition | null | undefined
  /** Computed by Noise-Adjusted Exposure Engine (computePositionSizing) */
  executionWeightPct: number
  /** Policy cap from Portfolio Construction Engine (ConvictionPosition.max_pct) */
  policyCap: number
  /** MIN(executionWeightPct, policyCap) */
  finalWeight: number
  bindingSource: 'EXECUTION' | 'POLICY' | 'EQUAL'
}

// ─── Helpers ──────────────────────────────────────────────────────────────────

function fmt(pct: number): string {
  return pct.toFixed(2) + '%'
}

type NormalisedRating = 'STRONG_BUY' | 'BUY' | 'HOLD' | 'WAIT' | 'SELL' | 'STRONG_SELL'

function normaliseRating(rating: string): NormalisedRating {
  const r = rating.toUpperCase().trim()
  if (r === 'STRONG BUY' || r === 'STRONG_BUY') return 'STRONG_BUY'
  if (r === 'STRONG SELL' || r === 'STRONG_SELL') return 'STRONG_SELL'
  if (r === 'BUY' || r === 'BUY NOW' || r === 'BUY_NOW') return 'BUY'
  if (r === 'SELL' || r === 'AVOID') return 'SELL'
  if (r === 'WAIT' || r === 'SCALE IN' || r === 'SCALE_IN') return 'WAIT'
  return 'HOLD'
}

function ratingLabel(nr: NormalisedRating): string {
  return nr.replace('_', ' ')
}

function isBullish(nr: NormalisedRating): boolean {
  return nr === 'BUY' || nr === 'STRONG_BUY'
}

function isBearish(nr: NormalisedRating): boolean {
  return nr === 'SELL' || nr === 'STRONG_SELL'
}

// ─── Main function ─────────────────────────────────────────────────────────────

export function buildCapitalDeploymentRationale(
  inputs: RationaleInputs
): CapitalDeploymentRationale {
  const {
    rating,
    signalBreakdown: sb,
    convictionPosition,
    executionWeightPct,
    policyCap,
    finalWeight,
    bindingSource,
  } = inputs

  const nr = normaliseRating(rating)
  const bullish = isBullish(nr)
  const bearish = isBearish(nr)

  const drivers: CapitalDeploymentDriver[] = []

  // ── Driver 1: Signal dispersion (σ across 7 signals) ──────────────────────
  const sigma = sb?.signal_spread
  if (sigma != null) {
    if (sigma >= 3.0) {
      drivers.push({
        label: 'Extreme signal dispersion',
        impact: 'tighten',
        evidence: `σ=${sigma.toFixed(2)} — scenario probability weights are highly uncertain`,
      })
    } else if (sigma >= 2.5) {
      drivers.push({
        label: 'Elevated signal dispersion',
        impact: 'tighten',
        evidence: `σ=${sigma.toFixed(2)} — confidence in directional scenario reduced`,
      })
    } else if (sigma < 1.5) {
      drivers.push({
        label: 'Tight signal dispersion',
        impact: 'loosen',
        evidence: `σ=${sigma.toFixed(2)} — signals are highly aligned across inputs`,
      })
    }
  }

  // ── Driver 2: Signal stability (1–10 scale) ───────────────────────────────
  const stability = sb?.signal_stability
  if (stability != null) {
    if (stability < 5.0) {
      drivers.push({
        label: 'Unstable signal regime',
        impact: 'tighten',
        evidence: `Stability ${stability.toFixed(1)}/10 — signals conflicting across time windows`,
      })
    } else if (stability < 6.0) {
      drivers.push({
        label: 'Mixed signal stability',
        impact: 'tighten',
        evidence: `Stability ${stability.toFixed(1)}/10 — cross-signal agreement is partial`,
      })
    } else if (stability >= 8.0) {
      drivers.push({
        label: 'High signal stability',
        impact: 'loosen',
        evidence: `Stability ${stability.toFixed(1)}/10 — signals consistent across time windows`,
      })
    }
  }

  // ── Driver 3: Noise environment ──────────────────────────────────────────
  // Noise score 35–50 = High Noise (0.70× multiplier)
  // Noise score 50–70 = Very High Noise (0.50× multiplier)
  // Noise score 70+   = Extreme Noise (0.30× multiplier)
  const noiseScore = sb?.noise_filter?.noise_score
  const noiseRegime = sb?.noise_filter?.noise_regime
  if (noiseScore != null) {
    if (noiseScore >= 70) {
      drivers.push({
        label: 'Extreme noise environment',
        impact: 'tighten',
        evidence: `Noise ${noiseScore}/100 (${noiseRegime ?? 'Noise Dominated'}) — signal extraction severely degraded`,
      })
    } else if (noiseScore >= 50) {
      drivers.push({
        label: 'Very high noise environment',
        impact: 'tighten',
        evidence: `Noise ${noiseScore}/100 (${noiseRegime ?? 'High Noise'}) — exposure compressed by signal regime`,
      })
    } else if (noiseScore >= 35) {
      drivers.push({
        label: 'High noise environment',
        impact: 'tighten',
        evidence: `Noise ${noiseScore}/100 (${noiseRegime ?? 'High Noise'}) — position engine applies 0.70× compression`,
      })
    } else if (noiseScore < 20) {
      drivers.push({
        label: 'Clean signal environment',
        impact: 'loosen',
        evidence: `Noise ${noiseScore}/100 (${noiseRegime ?? 'Clean'}) — signal regime supports fuller deployment`,
      })
    }
  }

  // ── Driver 4: Scenario rotation index ────────────────────────────────────
  const rotationIdx = sb?.scenario_weight_diagnostics?.scenario_rotation_index
  const driftLabel = sb?.scenario_weight_diagnostics?.drift_label
  if (rotationIdx != null) {
    if (rotationIdx >= 18) {
      drivers.push({
        label: 'Significant scenario rotation',
        impact: 'tighten',
        evidence: `Rotation idx ${rotationIdx.toFixed(0)} (${driftLabel ?? 'Significant Rotation'}) — probability distribution is actively shifting`,
      })
    } else if (rotationIdx >= 12) {
      drivers.push({
        label: 'Modest scenario rotation',
        impact: 'neutral',
        evidence: `Rotation idx ${rotationIdx.toFixed(0)} (${driftLabel ?? 'Modest Rotation'}) — minor probability drift detected`,
      })
    }
  }

  // ── Driver 5: Stop-loss probability ──────────────────────────────────────
  const stopProbPct = sb?.stop_probability?.effective_stop_probability_pct
  if (stopProbPct != null) {
    if (stopProbPct >= 30) {
      drivers.push({
        label: 'High stop-loss risk',
        impact: 'tighten',
        evidence: `StopProb ${stopProbPct.toFixed(0)}% — high probability of hitting stop during hold period`,
      })
    } else if (stopProbPct >= 20) {
      drivers.push({
        label: 'Elevated stop-loss risk',
        impact: 'tighten',
        evidence: `StopProb ${stopProbPct.toFixed(0)}% — meaningful downside tail present`,
      })
    } else if (stopProbPct < 12) {
      drivers.push({
        label: 'Low stop-loss risk',
        impact: 'loosen',
        evidence: `StopProb ${stopProbPct.toFixed(0)}% — stop discipline well-controlled`,
      })
    }
  }

  // ── Driver 6: Institutional posture ──────────────────────────────────────
  const instBias = sb?.liquidity_microstructure?.accumulation_distribution_bias
  if (instBias != null) {
    if (instBias === 'Distribution') {
      drivers.push({
        label: 'Institutional posture: Distribution',
        impact: 'tighten',
        evidence: 'Smart money reducing — constrains scaling despite directional signal',
      })
    } else if (instBias === 'Mild Distribution') {
      drivers.push({
        label: 'Institutional posture: Mild Distribution',
        impact: 'tighten',
        evidence: 'Smart money mildly reducing — modest headwind to position scaling',
      })
    } else if (instBias === 'Accumulation') {
      drivers.push({
        label: 'Institutional posture: Accumulation',
        impact: 'loosen',
        evidence: 'Smart money adding — supportive of deployment at current level',
      })
    } else if (instBias === 'Mild Accumulation') {
      drivers.push({
        label: 'Institutional posture: Mild Accumulation',
        impact: 'loosen',
        evidence: 'Smart money mildly adding — neutral-to-supportive for deployment',
      })
    }
  }

  // ── Driver 7: Cross-signal conflict (distribution posture vs bullish rating) ─
  if (
    bullish &&
    (instBias === 'Distribution' || instBias === 'Mild Distribution') &&
    sigma != null &&
    sigma >= 2.5
  ) {
    drivers.push({
      label: 'Cross-signal conflict: positioning vs trend',
      impact: 'tighten',
      evidence:
        'Institutional distribution posture conflicts with BUY rating — reduces size confidence',
    })
  }

  // ─── Binding ────────────────────────────────────────────────────────────────
  const binding =
    bindingSource === 'POLICY'
      ? {
          type: 'policy_cap' as const,
          explanation: `Portfolio construction cap (${fmt(policyCap)}) is more restrictive than the ${fmt(executionWeightPct)} execution weight. Allocation discipline enforces concentration limits regardless of thesis quality.`,
        }
      : {
          type: 'execution' as const,
          explanation: `Noise-adjusted execution weight (${fmt(executionWeightPct)}) is below the ${fmt(policyCap)} policy cap. Deployment is constrained by signal quality and regime conditions, not portfolio construction limits.`,
        }

  // ─── Dominant drivers for summary ───────────────────────────────────────────
  const tighteningDrivers = drivers.filter((d) => d.impact === 'tighten')
  const loosenDrivers = drivers.filter((d) => d.impact === 'loosen')

  // ─── Summary (rating-aware) ──────────────────────────────────────────────────
  let summary: string
  if (bullish && finalWeight <= 2.0) {
    const topConstraint = tighteningDrivers[0]?.label ?? 'signal instability'
    summary = `Thesis direction is intact (${ratingLabel(nr)}), but satellite sizing applies. ${topConstraint} constrains deployment — wait for signal convergence before scaling.`
  } else if (bullish && bindingSource === 'POLICY') {
    summary = `Thesis direction is intact (${ratingLabel(nr)}) with adequate signal confidence. Allocation is at the portfolio construction cap (${fmt(policyCap)}) — size reflects concentration discipline, not directional doubt.`
  } else if (bullish) {
    const topConstraint = tighteningDrivers[0]?.label ?? 'current signal conditions'
    summary = `Thesis direction is intact (${ratingLabel(nr)}). Position sizing reflects ${topConstraint.toLowerCase()} — directional conviction does not override risk-adjusted deployment rules.`
  } else if (nr === 'HOLD' || nr === 'WAIT') {
    const topConstraint = tighteningDrivers[0]?.label ?? 'mixed signals'
    summary = `No new capital deployment indicated (${ratingLabel(nr)}). ${topConstraint} limits incremental commitment. Monitor for a directional catalyst before adding exposure.`
  } else if (bearish) {
    summary = `Directional signal is bearish (${ratingLabel(nr)}). Allocation floor applies for any existing exposure only. No new deployment is supported by the model.`
  } else {
    summary = `Allocation of ${fmt(finalWeight)} reflects the output of the noise-adjusted position sizing engine, constrained by the ${binding.type === 'policy_cap' ? 'portfolio construction cap' : 'signal quality regime'}.`
  }

  // ─── Interpretation bullets ──────────────────────────────────────────────────
  const interpretation: string[] = []

  // Binding fact — always first
  if (bindingSource === 'EXECUTION') {
    interpretation.push(
      `Allocation is execution-bound — ${fmt(finalWeight)} (execution) < ${fmt(policyCap)} (policy cap).`
    )
  } else if (bindingSource === 'POLICY') {
    interpretation.push(
      `Policy cap binding — ${fmt(policyCap)} enforced; execution weight ${fmt(executionWeightPct)} exceeds the cap ceiling.`
    )
  } else {
    interpretation.push(
      `Execution weight and policy cap are equal at ${fmt(finalWeight)} — resolver at equilibrium.`
    )
  }

  // Thesis reconciliation
  if (bullish) {
    interpretation.push(
      `${ratingLabel(nr)} direction confirmed — size reduction is in deployment magnitude, not thesis invalidation.`
    )
  }

  // Top tightening drivers
  tighteningDrivers.slice(0, 3).forEach((d) => {
    interpretation.push(`${d.label} (${d.evidence}) → reduces exposure.`)
  })

  // Loosen note if no tightening drivers
  if (tighteningDrivers.length === 0 && loosenDrivers.length > 0) {
    interpretation.push(
      `${loosenDrivers[0].label} (${loosenDrivers[0].evidence}) → supports fuller deployment.`
    )
  }

  // Conviction level
  const convictionLevel = convictionPosition?.conviction_level
  if (convictionLevel) {
    interpretation.push(`Conviction: ${convictionLevel} — final allocation ceiling is ${fmt(finalWeight)}.`)
  }

  // Satellite sizing note
  if (bullish && finalWeight <= 2.0) {
    interpretation.push(
      `Satellite sizing (≤2%) is appropriate for current regime — await signal convergence to scale.`
    )
  }

  // ─── Next actions ────────────────────────────────────────────────────────────
  const next_actions: string[] = []

  if (bullish && bindingSource === 'EXECUTION') {
    if (noiseScore != null && noiseScore >= 35) {
      next_actions.push(
        `Monitor noise regime — score reduction below 35 removes the High Noise compression (currently ${noiseScore}/100).`
      )
    }
    if (sigma != null && sigma >= 2.5) {
      next_actions.push(
        `Watch σ convergence — signal dispersion below 2.2 enables re-evaluation (currently σ=${sigma.toFixed(2)}).`
      )
    }
    if (stopProbPct != null && stopProbPct >= 20) {
      next_actions.push(
        `Stop risk improvement (target <15%) would remove the ${stopProbPct.toFixed(0)}% stop-probability drag.`
      )
    }
    next_actions.push(
      `Thesis invalidation triggers: sustained fundamental deterioration or technical breakdown below key support.`
    )
  } else if (bullish && bindingSource === 'POLICY') {
    next_actions.push(
      `Allocation already at portfolio construction cap (${fmt(policyCap)}) — scale only if a conviction upgrade raises the ceiling.`
    )
    next_actions.push(
      `Monitor for signals that warrant a conviction upgrade from ${convictionLevel ?? 'current level'} to High.`
    )
  } else if (nr === 'HOLD' || nr === 'WAIT') {
    next_actions.push(
      `Wait for a directional catalyst — bullish confirmation (earnings beat, institutional accumulation, technical breakout) before adding exposure.`
    )
    next_actions.push(
      `Thesis break condition: two or more tightening signals failing to improve within the review window.`
    )
  } else if (bearish) {
    next_actions.push(
      `Reduce or exit existing exposure consistent with ${ratingLabel(nr)} signal — do not add.`
    )
    next_actions.push(
      `Re-evaluation criteria: rating upgrade to HOLD or better on improving fundamentals.`
    )
  } else {
    next_actions.push(`Review signal regime at next scheduled interval.`)
  }

  // ─── Disclaimers ─────────────────────────────────────────────────────────────
  const disclaimers =
    'Model output — not investment advice. Allocation is a sizing ceiling, not a directive to deploy full size at initiation.'

  return {
    summary,
    drivers,
    binding,
    interpretation,
    next_actions,
    disclaimers,
  }
}
