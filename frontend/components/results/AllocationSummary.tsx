'use client'

import { Target } from 'lucide-react'
import type { ConvictionPosition, SignalBreakdown } from '@/types/api'
import { computePositionSizing, defaultConfig } from '@/lib/engine/computePositionSizing'
import type { PositionSizingInput } from '@/lib/engine/types'

/**
 * AllocationSummary — the whole sizing funnel in one sentence.
 *
 * The report derives four different percentages, each answering a different
 * question:
 *
 *   Risk-Adjusted Cap        the most this may EVER be      (risk level x rating)
 *   Noise-Adjusted Exposure  what conditions support NOW    (noise/dispersion/stop)
 *   Final Position Weight    MIN of the two — the target
 *   Starter Tranche          what to deploy TODAY           (40% of the ceiling)
 *
 * Presented as peers they read as four competing recommendations. Stated as a
 * chain — target, ceiling, opening size — every panel below becomes the
 * derivation of one sentence rather than a rival answer to it.
 */
export function AllocationSummary({
  ticker,
  signalBreakdown,
  convictionPosition,
  starterTranchePct,
}: {
  ticker: string
  signalBreakdown?: SignalBreakdown | null
  convictionPosition?: ConvictionPosition | null
  starterTranchePct?: number | null
}) {
  const cap = convictionPosition?.max_pct ?? null

  // Same derivation the Final Weight Resolver runs, so the headline and the
  // panel below it can never disagree.
  let executionWeight: number | null = null
  const noiseScore = signalBreakdown?.noise_filter?.noise_score
  const sigma = signalBreakdown?.signal_spread
  const stopProbPct = signalBreakdown?.stop_probability?.effective_stop_probability_pct

  if (noiseScore != null && sigma != null && stopProbPct != null) {
    const recPct = convictionPosition?.recommended_pct ?? 0
    const sensitivity = (
      signalBreakdown?.model_sensitivity_attribution?.overall_sensitivity ?? ''
    ).toUpperCase()
    const beta = signalBreakdown?.factor_diagnostics?.beta_estimate
    const hasDivergence = signalBreakdown?.has_divergence ?? false

    const input: PositionSizingInput = {
      symbol: ticker,
      classification: recPct >= 5 ? 'CORE' : 'SATELLITE',
      noise_score: noiseScore,
      overall_sensitivity:
        sensitivity === 'HIGH' ? 'HIGH' : sensitivity === 'LOW' ? 'LOW' : 'MODERATE',
      signal_dispersion_sigma: sigma,
      stop_probability: stopProbPct / 100,
      ...(beta != null && beta > 0 ? { beta } : {}),
      flags: { signal_conflict_active: hasDivergence, cap_at_satellite: hasDivergence },
    }
    try {
      executionWeight = computePositionSizing(input, defaultConfig).adjusted_weight_pct
    } catch {
      executionWeight = null
    }
  }

  if (cap == null && executionWeight == null) return null

  const target =
    cap != null && executionWeight != null
      ? Math.min(cap, executionWeight)
      : (cap ?? executionWeight)
  if (target == null) return null

  const capBinding = cap != null && executionWeight != null && cap < executionWeight
  const pct = (v: number) => `${v.toFixed(1)}%`

  return (
    <div className="rounded-lg border border-primary/30 bg-primary/5 px-4 py-3">
      <div className="flex items-start gap-2.5">
        <Target className="h-4 w-4 text-primary mt-0.5 shrink-0" />
        <div className="min-w-0">
          <p className="text-sm text-text-primary leading-relaxed">
            Target{' '}
            <span className="font-semibold font-mono tabular-nums">{pct(target)}</span> of
            portfolio
            {cap != null && (
              <>
                {' '}
                <span className="text-text-secondary">
                  (ceiling {pct(cap)})
                </span>
              </>
            )}
            {starterTranchePct != null && (
              <>
                ; deploy{' '}
                <span className="font-semibold font-mono tabular-nums">
                  {pct(starterTranchePct)}
                </span>{' '}
                now
              </>
            )}
            .
          </p>
          <p className="text-[10px] text-text-tertiary mt-1 leading-relaxed">
            {capBinding
              ? 'Concentration policy is the binding constraint — conditions would support a larger position.'
              : executionWeight != null && cap != null
                ? 'Current signal conditions are the binding constraint — policy would allow a larger position.'
                : 'Sized from the available constraint; the panels below show the derivation.'}
          </p>
        </div>
      </div>
    </div>
  )
}
