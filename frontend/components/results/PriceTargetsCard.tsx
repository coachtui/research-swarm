'use client'

// All calculations are IDENTICAL to the original — only visual presentation is refined.
// Changes: institutional header, layered tier labels, probability micro-context strips,
// visual probability allocation bar, probability construction framework, effective EV table,
// and distribution shape profile. No scenario numbers or weights were altered.

import { useState } from 'react'
import type { SignalBreakdown } from '@/types/api'

interface PriceTargetsCardProps {
  priceTargets: {
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
    /** DVRG divergence-weighted target provenance (present on new runs) */
    persistence_probability?: number | null
    reversion_anchor?: number | null
    persistence_anchor?: number | null
    basis_note?: string | null
  }
  currentPrice: number
  ticker: string
  signalBreakdown?: SignalBreakdown
  /** Server-computed probability-weighted EV from the persisted AnalysisReport */
  probabilityWeightedEv?: number | null
}

export function PriceTargetsCard({ priceTargets, currentPrice, signalBreakdown, probabilityWeightedEv }: PriceTargetsCardProps) {
  const [showProbFramework, setShowProbFramework] = useState(false)

  const baseUpside = ((priceTargets.base_target - currentPrice) / currentPrice) * 100
  const bullUpside = ((priceTargets.bull_target - currentPrice) / currentPrice) * 100
  const bearDownside = ((priceTargets.bear_target - currentPrice) / currentPrice) * 100

  // Probability-weighted expected value — Phase D: prefer the server-computed
  // value from the persisted AnalysisReport (single source); local math only
  // as a fallback for pre-Phase-C runs.
  const bearW = priceTargets.bear_probability ?? 0.25
  const baseW = priceTargets.base_probability ?? 0.50
  const bullW = priceTargets.bull_probability ?? 0.25
  const probWeightedEV =
    probabilityWeightedEv ??
    (priceTargets.bear_target * bearW +
      priceTargets.base_target * baseW +
      priceTargets.bull_target * bullW)
  const evVsCurrent = ((probWeightedEV - currentPrice) / currentPrice) * 100

  // Effective EV: stability modifier dampens EV magnitude (instability reduces outcome magnitude, not just confidence)
  const stabilityModifier = signalBreakdown?.data_integrity_confidence_factor ?? 1.0
  const rawEvPct = evVsCurrent
  const effectiveEvPct = rawEvPct * stabilityModifier
  const effectiveEV = currentPrice * (1 + effectiveEvPct / 100)

  // Distribution shape profile — derived from scenario geometry
  const bullDistance = priceTargets.bull_target - priceTargets.base_target
  const bearDistance = priceTargets.base_target - priceTargets.bear_target
  const asymmetryRatio = bearDistance > 0 ? bullDistance / bearDistance : 1.0

  // Probability-weighted moments (3rd moment skewness approximation)
  const varianceProxy =
    bearW * Math.pow(priceTargets.bear_target - probWeightedEV, 2) +
    baseW * Math.pow(priceTargets.base_target - probWeightedEV, 2) +
    bullW * Math.pow(priceTargets.bull_target - probWeightedEV, 2)
  const stdDev = Math.sqrt(varianceProxy)
  const skewnessProxy = stdDev > 0
    ? (bearW * Math.pow(priceTargets.bear_target - probWeightedEV, 3) +
       baseW * Math.pow(priceTargets.base_target - probWeightedEV, 3) +
       bullW * Math.pow(priceTargets.bull_target - probWeightedEV, 3)) / Math.pow(stdDev, 3)
    : 0

  const scenarioSpreadPct = priceTargets.base_target > 0
    ? ((priceTargets.bull_target - priceTargets.bear_target) / priceTargets.base_target) * 100
    : 0

  let leftTailLabel: string
  let rightTailLabel: string
  let distributionShapeLabel: string
  let distributionShapeColor: string

  if (skewnessProxy < -0.25) {
    leftTailLabel = 'Thick — elevated downside event risk'
    rightTailLabel = 'Thin — limited re-rating convexity'
    distributionShapeLabel = 'Negatively skewed / concentrated downside'
    distributionShapeColor = 'text-error'
  } else if (skewnessProxy > 0.25) {
    leftTailLabel = 'Thin — limited downside tail risk'
    rightTailLabel = 'Thick — asymmetric upside convexity'
    distributionShapeLabel = 'Positively skewed / convex upside'
    distributionShapeColor = 'text-success'
  } else {
    leftTailLabel = 'Moderate — balanced downside risk'
    rightTailLabel = 'Moderate — balanced upside potential'
    distributionShapeLabel = 'Approximately symmetric distribution'
    distributionShapeColor = 'text-text-secondary'
  }

  const kurtosisNote =
    scenarioSpreadPct > 60
      ? 'High kurtosis — wide tail events are material'
      : scenarioSpreadPct > 30
        ? 'Moderate kurtosis — meaningful tail outcomes'
        : 'Low kurtosis — tight scenario band, limited tail risk'

  const bearPct  = Math.round(bearW * 100)
  const basePct  = Math.round(baseW * 100)
  const bullPct  = Math.round(bullW * 100)

  return (
    <div className="bg-card border rounded-lg p-6">

      {/* Institutional header — no emoji, structural framing */}
      <div className="flex items-start justify-between mb-2">
        <div>
          <h2 className="text-base font-semibold text-text-primary tracking-tight">
            Scenario Value Construct
          </h2>
          <p className="text-xs text-text-tertiary mt-0.5">
            {priceTargets.methodology} · 12-Month Calibration Window
          </p>
        </div>
        <span className="text-[10px] font-mono text-text-tertiary/60 border border-border rounded px-1.5 py-0.5 mt-0.5 shrink-0">
          Structural Layer
        </span>
      </div>

      <p className="text-xs text-text-tertiary mb-4 leading-relaxed border-l-2 border-border pl-2.5">
        Probabilistic outcome paths calibrated to signal divergence — not Structural Valuation Reference forecasts.
        <span className="block text-text-tertiary/60 italic mt-0.5">
          Scenario weights: heuristic-derived · regime-conditioned reliability
        </span>
      </p>

      {/* DVRG target basis — how the base target bridges intrinsic value and market expectation */}
      {priceTargets.basis_note && (
        <p className="text-xs text-text-tertiary mb-4 leading-relaxed border-l-2 border-accent/40 pl-2.5">
          {priceTargets.basis_note}
        </p>
      )}

      {/* Probability allocation strip — purely visual, reflects existing weight values */}
      <div className="mb-5">
        <div className="text-[10px] text-text-tertiary mb-1.5 uppercase tracking-wider font-medium">
          Probability Allocation
        </div>
        <div className="flex h-1.5 rounded-full overflow-hidden gap-px">
          <div
            className="bg-error/70 rounded-l-full transition-all"
            style={{ width: `${bearPct}%` }}
          />
          <div
            className="bg-blue-500/70 transition-all"
            style={{ width: `${basePct}%` }}
          />
          <div
            className="bg-success/70 rounded-r-full transition-all"
            style={{ width: `${bullPct}%` }}
          />
        </div>
        <div className="flex justify-between text-[10px] text-text-tertiary mt-1">
          <span>{bearPct}% Risk</span>
          <span>{basePct}% Continuation</span>
          <span>{bullPct}% Re-rating</span>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-4">

        {/* ── Tier 1: Capital Preservation Threshold ── */}
        <div className="border-l-4 border-red-500 bg-surface-elevated p-4 rounded">
          <div className="text-[10px] text-error/70 mb-0.5 uppercase tracking-wider font-medium">
            Risk Scenario
          </div>
          <div className="text-xs text-text-secondary mb-2 font-medium leading-tight">
            Capital Preservation Threshold
          </div>
          <div className="text-2xl font-bold text-red-500 font-mono">
            ${priceTargets.bear_target.toFixed(2)}
          </div>
          <div className="text-sm text-red-500">
            {bearDownside.toFixed(1)}% downside
          </div>
          {/* Per-scenario probability micro-context */}
          <div className="mt-2.5 flex items-center gap-1.5">
            <div className="h-1 bg-error/20 rounded-full flex-1">
              <div
                className="h-full bg-error/60 rounded-full transition-all"
                style={{ width: `${bearPct}%` }}
              />
            </div>
            <span className="text-[10px] text-text-tertiary font-mono w-7 text-right shrink-0">
              {bearPct}%
            </span>
          </div>
          <p className="text-[10px] text-text-tertiary/60 italic mt-0.5">
            heuristic weight · regime-conditioned
          </p>
          <p className="text-xs text-text-tertiary mt-2.5 pt-2 border-t border-border/50 leading-relaxed">
            {priceTargets.bear_assumptions}
          </p>
        </div>

        {/* ── Tier 2: Regime-Adjusted Structural Value ── */}
        <div className="border-l-4 border-blue-500 bg-surface-elevated p-4 rounded">
          <div className="text-[10px] text-blue-400/70 mb-0.5 uppercase tracking-wider font-medium">
            Continuation Scenario
          </div>
          <div className="text-xs text-text-secondary mb-2 font-medium leading-tight">
            Regime-Adjusted Structural Value
          </div>
          <div className="text-2xl font-bold text-blue-500 font-mono">
            ${priceTargets.base_target.toFixed(2)}
          </div>
          <div className="text-sm text-blue-500">
            {baseUpside > 0 ? '+' : ''}{baseUpside.toFixed(1)}% potential
          </div>
          <div className="mt-2.5 flex items-center gap-1.5">
            <div className="h-1 bg-blue-500/20 rounded-full flex-1">
              <div
                className="h-full bg-blue-500/60 rounded-full transition-all"
                style={{ width: `${basePct}%` }}
              />
            </div>
            <span className="text-[10px] text-text-tertiary font-mono w-7 text-right shrink-0">
              {basePct}%
            </span>
          </div>
          <p className="text-[10px] text-text-tertiary/60 italic mt-0.5">
            heuristic weight · regime-conditioned
          </p>
          <p className="text-xs text-text-tertiary mt-2.5 pt-2 border-t border-border/50 leading-relaxed">
            {priceTargets.base_assumptions}
          </p>
        </div>

        {/* ── Tier 3: Growth-Sustained Structural Range ── */}
        <div className="border-l-4 border-green-500 bg-surface-elevated p-4 rounded">
          <div className="text-[10px] text-success/70 mb-0.5 uppercase tracking-wider font-medium">
            Re-rating Scenario
          </div>
          <div className="text-xs text-text-secondary mb-2 font-medium leading-tight">
            Growth-Sustained Structural Range
          </div>
          <div className="text-2xl font-bold text-green-500 font-mono">
            ${priceTargets.bull_target.toFixed(2)}
          </div>
          <div className="text-sm text-green-500">
            +{bullUpside.toFixed(1)}% upside
          </div>
          <div className="mt-2.5 flex items-center gap-1.5">
            <div className="h-1 bg-success/20 rounded-full flex-1">
              <div
                className="h-full bg-success/60 rounded-full transition-all"
                style={{ width: `${bullPct}%` }}
              />
            </div>
            <span className="text-[10px] text-text-tertiary font-mono w-7 text-right shrink-0">
              {bullPct}%
            </span>
          </div>
          <p className="text-[10px] text-text-tertiary/60 italic mt-0.5">
            heuristic weight · regime-conditioned
          </p>
          <p className="text-xs text-text-tertiary mt-2.5 pt-2 border-t border-border/50 leading-relaxed">
            {priceTargets.bull_assumptions}
          </p>
        </div>
      </div>

      {/* ── Risk / Reward Summary — downside first, institutional tone ── */}
      <div className="mt-4 rounded-lg border border-border/60 bg-surface-elevated/30 overflow-hidden">
        <div className="px-3 py-1.5 border-b border-border/40 flex items-center justify-between">
          <span className="text-[10px] font-semibold uppercase tracking-wider text-text-tertiary">
            Risk / Reward Summary
          </span>
          <span className="text-[9px] text-text-tertiary/40 italic">Downside assessed first</span>
        </div>
        <div className="divide-y divide-border/30">
          {/* Downside — first, prominent */}
          <div className="flex items-center justify-between px-3 py-2">
            <span className="text-xs text-text-secondary">Downside to Bear</span>
            <span className="font-mono font-bold text-sm text-error">
              {bearDownside.toFixed(1)}%
            </span>
          </div>
          {/* Upside — second */}
          <div className="flex items-center justify-between px-3 py-2">
            <span className="text-xs text-text-secondary">Upside to Bull</span>
            <span className={`font-mono font-bold text-sm ${bullUpside >= 0 ? 'text-success' : 'text-error'}`}>
              +{bullUpside.toFixed(1)}%
            </span>
          </div>
          {/* Asymmetry */}
          <div className="flex items-center justify-between px-3 py-2">
            <span className="text-xs text-text-secondary">Asymmetry Ratio</span>
            <span className={`font-mono font-bold text-sm ${asymmetryRatio >= 1.5 ? 'text-success' : asymmetryRatio >= 1.0 ? 'text-text-secondary' : 'text-warning'}`}>
              {asymmetryRatio.toFixed(1)}:1
              <span className="text-[10px] font-normal text-text-tertiary ml-1">(bull:bear)</span>
            </span>
          </div>
          {/* Probability-Weighted EV — last */}
          <div className="flex items-center justify-between px-3 py-2 bg-surface-elevated/40">
            <span className="text-xs font-medium text-text-secondary">Prob-Weighted EV</span>
            <span className={`font-mono font-bold text-sm ${evVsCurrent >= 5 ? 'text-success' : evVsCurrent >= 0 ? 'text-text-secondary' : 'text-error'}`}>
              {evVsCurrent > 0 ? '+' : ''}{evVsCurrent.toFixed(1)}%
            </span>
          </div>
        </div>
      </div>

      {/* ── EV Summary + Effective EV Table ── */}
      <div className="mt-4 pt-4 border-t border-border space-y-3">

        {/* Raw EV row */}
        <div className="flex items-center justify-between flex-wrap gap-2 text-xs mb-0.5">
          <div className="flex items-center gap-2">
            <span className="text-text-tertiary">Scenario-Weighted Expected Value</span>
            <span className="font-semibold text-text-primary font-mono">
              ${probWeightedEV.toFixed(2)}
            </span>
            <span className={`font-medium ${evVsCurrent >= 0 ? 'text-success' : 'text-error'}`}>
              {evVsCurrent > 0 ? '+' : ''}{evVsCurrent.toFixed(1)}% vs current
            </span>
          </div>
          <span className="text-[10px] font-mono text-text-tertiary/60">
            {bearPct}/{basePct}/{bullPct} risk·cont·rerating
          </span>
        </div>

        {/* Effective EV table — shows stability impact on EV magnitude */}
        {signalBreakdown && (
          <div className="rounded-md border border-border/50 bg-surface-elevated overflow-hidden">
            <div className="px-3 py-1.5 border-b border-border/40 flex items-center justify-between">
              <span className="text-[10px] font-semibold uppercase tracking-wider text-text-tertiary">
                EV → Stability Interaction
              </span>
              <span className="text-[9px] text-text-tertiary/50 italic">
                Instability reduces EV magnitude, not only confidence
              </span>
            </div>
            <div className="divide-y divide-border/30">
              <div className="flex items-center justify-between px-3 py-1.5 text-xs">
                <span className="text-text-tertiary">Raw EV</span>
                <span className="font-mono text-text-primary">
                  {rawEvPct > 0 ? '+' : ''}{rawEvPct.toFixed(2)}%
                </span>
              </div>
              <div className="flex items-center justify-between px-3 py-1.5 text-xs">
                <span className="text-text-tertiary">
                  Stability Modifier
                  <span className="ml-1 text-text-tertiary/50 text-[10px]">
                    ({signalBreakdown.valid_signal_count ?? '—'}/{((signalBreakdown.valid_signal_count ?? 0) + (signalBreakdown.missing_signal_count ?? 0))} signals confirmed)
                  </span>
                </span>
                <span className={`font-mono font-semibold ${stabilityModifier >= 0.9 ? 'text-success' : stabilityModifier >= 0.75 ? 'text-warning' : 'text-error'}`}>
                  {stabilityModifier.toFixed(2)}×
                </span>
              </div>
              <div className="flex items-center justify-between px-3 py-2 text-xs bg-surface-elevated/60">
                <span className="font-medium text-text-secondary">
                  Effective EV
                  <span className="ml-1 text-text-tertiary font-normal text-[10px]">(raw × modifier)</span>
                </span>
                <div className="flex items-center gap-2">
                  <span className="font-mono font-semibold text-text-primary">
                    ${effectiveEV.toFixed(2)}
                  </span>
                  <span className={`font-mono font-semibold text-sm ${effectiveEvPct >= 0 ? 'text-success' : 'text-error'}`}>
                    {effectiveEvPct > 0 ? '+' : ''}{effectiveEvPct.toFixed(2)}%
                  </span>
                </div>
              </div>
            </div>
          </div>
        )}

        <div className="text-[10px] text-text-tertiary">
          Current:{' '}
          <span className="font-mono">${currentPrice.toFixed(2)}</span>
          {' · '}
          Scenario range:{' '}
          <span className="font-mono">
            ${priceTargets.bear_target.toFixed(2)} – ${priceTargets.bull_target.toFixed(2)}
          </span>
          {' · '}
          <span className="italic text-text-tertiary/50">
            Heuristic weights · regime-conditioned reliability
          </span>
        </div>
      </div>

      {/* ── Distribution Shape Profile ── */}
      <div className="mt-4 pt-3 border-t border-border/40">
        <div className="text-[10px] text-text-tertiary mb-2 uppercase tracking-wider font-medium">
          Outcome Distribution Profile
        </div>
        <div className="grid grid-cols-3 gap-2 text-xs mb-2">
          <div className="bg-surface-elevated rounded p-2 border border-border/40">
            <div className="text-[9px] uppercase tracking-wider text-text-tertiary/70 mb-0.5 font-medium">
              Left Tail
            </div>
            <div className="text-text-secondary leading-tight text-[11px]">{leftTailLabel}</div>
          </div>
          <div className="bg-surface-elevated rounded p-2 border border-border/40">
            <div className="text-[9px] uppercase tracking-wider text-text-tertiary/70 mb-0.5 font-medium">
              Right Tail
            </div>
            <div className="text-text-secondary leading-tight text-[11px]">{rightTailLabel}</div>
          </div>
          <div className="bg-surface-elevated rounded p-2 border border-border/40">
            <div className="text-[9px] uppercase tracking-wider text-text-tertiary/70 mb-0.5 font-medium">
              Kurtosis
            </div>
            <div className="text-text-secondary leading-tight text-[11px]">{kurtosisNote}</div>
          </div>
        </div>
        <div className="flex items-center gap-2 text-xs">
          <span className="text-text-tertiary">Distribution Shape:</span>
          <span className={`font-medium ${distributionShapeColor}`}>
            {distributionShapeLabel}
          </span>
          <span className="text-[10px] text-text-tertiary/50 font-mono">
            (skew={skewnessProxy.toFixed(2)}, spread={scenarioSpreadPct.toFixed(0)}%)
          </span>
        </div>
        <p className="text-[10px] text-text-tertiary/50 italic mt-1">
          Derived from 3-scenario probability geometry · asymmetry ratio {asymmetryRatio.toFixed(2)}:1 (bull:bear distance)
        </p>
      </div>

      {/* ── Probability Construction Framework (expandable) ── */}
      {signalBreakdown?.probability_construction_framework && (
        <div className="mt-3 pt-3 border-t border-border/40">
          <button
            onClick={() => setShowProbFramework(!showProbFramework)}
            className="text-xs text-primary hover:text-primary-light transition-colors"
          >
            {showProbFramework ? 'Hide Probability Framework ↑' : 'Probability Construction Framework →'}
          </button>

          {showProbFramework && (
            <div className="mt-3 space-y-2">
              <div className="flex items-baseline justify-between">
                <span className="text-[10px] font-semibold uppercase tracking-wider text-text-tertiary">
                  Probability Derivation Logic
                </span>
                <span className="text-[9px] text-text-tertiary/50 italic">
                  Structural — not opinion-based
                </span>
              </div>

              <div className="space-y-1.5">
                {signalBreakdown.probability_construction_framework.factors.map((factor, i) => (
                  <div key={i} className="rounded border border-border/40 bg-surface-elevated px-3 py-2">
                    <div className="flex items-center justify-between mb-0.5">
                      <span className="text-xs font-medium text-text-secondary">
                        {factor.name}
                      </span>
                      <span className={`text-[10px] font-semibold px-1.5 py-0 rounded ${
                        factor.impact_level === 'High' ? 'text-error bg-error/10 border border-error/20' :
                        factor.impact_level === 'Moderate' ? 'text-warning bg-warning/10 border border-warning/20' :
                        factor.impact_level === 'None' ? 'text-success bg-success/10 border border-success/20' :
                        'text-text-tertiary border border-border/50'
                      }`}>
                        {factor.impact_level} Impact
                      </span>
                    </div>
                    <div className="text-[10px] text-text-tertiary mb-0.5">{factor.description}</div>
                    <div className="flex items-baseline gap-2">
                      <span className="font-mono text-[11px] text-text-primary">{factor.current_value}</span>
                    </div>
                    <p className="text-[10px] text-text-tertiary/70 italic mt-0.5">{factor.effect}</p>
                  </div>
                ))}
              </div>

              <p className="text-[10px] text-text-tertiary/60 leading-relaxed border-l-2 border-border pl-2 mt-2">
                {signalBreakdown.probability_construction_framework.derivation_note}
              </p>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
