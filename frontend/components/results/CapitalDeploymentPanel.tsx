'use client'

// Phase 3 — Capital Deployment Panel
// Portfolio blotter aesthetic. Large numeric dominance. Minimal explanation.
// Deployment Logic behind collapsible toggle.
// No new model logic — all values from conviction_position + signal_breakdown.

import { useState } from 'react'
import { ChevronDown, ChevronUp } from 'lucide-react'
import type { ConvictionPosition, SignalBreakdown } from '@/types/api'

interface CapitalDeploymentPanelProps {
  conviction: ConvictionPosition
  signalBreakdown?: SignalBreakdown | null
  ticker: string
  rating?: string | null
}

function positionTypeLabel(convictionLevel: string): string {
  const l = convictionLevel.toLowerCase()
  if (l === 'high') return 'Core'
  if (l === 'medium' || l === 'moderate') return 'Satellite'
  return 'Tactical'
}

function executionConstrainedPct(
  conviction: ConvictionPosition,
  signalBreakdown?: SignalBreakdown | null,
): number {
  // Use portfolio_action scaling multiplier if available (Trader tier)
  const scalingMult = signalBreakdown?.portfolio_action?.conviction_scaling_multiplier
  if (scalingMult !== undefined && scalingMult !== null) {
    return Math.min(conviction.recommended_pct * scalingMult, conviction.max_pct)
  }
  // Fall back to conviction_level-derived multiplier
  const lvl = (conviction.conviction_level ?? '').toLowerCase()
  const mult = lvl === 'high' ? 1.0 : lvl === 'medium' ? 0.75 : 0.5
  // Apply noise reduction if noise filter defers sizing
  const noiseDeferral = signalBreakdown?.noise_filter?.defer_sizing ? 0.75 : 1.0
  return Math.min(conviction.recommended_pct * mult * noiseDeferral, conviction.max_pct)
}

function AllocationBlock({
  label,
  value,
  sub,
  highlight = false,
}: {
  label: string
  value: string
  sub?: string
  highlight?: boolean
}) {
  return (
    <div className={`flex flex-col gap-1 px-5 py-4 ${highlight ? 'bg-primary/5 border-r border-l border-primary/20' : ''}`}>
      <span className="text-[9px] uppercase tracking-[0.13em] font-semibold text-text-tertiary">
        {label}
      </span>
      <span className={`text-4xl font-bold font-mono leading-none ${highlight ? 'text-primary' : 'text-text-primary'}`}>
        {value}
      </span>
      {sub && (
        <span className="text-[10px] text-text-tertiary/60">{sub}</span>
      )}
    </div>
  )
}

export function CapitalDeploymentPanel({
  conviction,
  signalBreakdown,
  ticker: _ticker,
  rating: _rating,
}: CapitalDeploymentPanelProps) {
  const [showLogic, setShowLogic] = useState(false)

  const execPct = executionConstrainedPct(conviction, signalBreakdown)
  const posType = positionTypeLabel(conviction.conviction_level)

  // Constraint classification
  const bindingType =
    execPct < conviction.recommended_pct * 0.95
      ? (execPct >= conviction.max_pct * 0.95 ? 'Cap-Bound' : 'Execution-Bound')
      : 'Within Guardrails'

  // Scaling label from portfolio_action if available
  const scalingLabel = signalBreakdown?.portfolio_action?.conviction_scaling_label ?? null
  const allocationBias = signalBreakdown?.portfolio_action?.allocation_bias ?? null

  // Noise warning
  const noiseDefer = signalBreakdown?.noise_filter?.defer_sizing
  const noiseRegime = signalBreakdown?.noise_filter?.noise_regime

  return (
    <div className="rounded-xl border border-border/70 bg-card overflow-hidden">

      {/* Header */}
      <div className="px-5 pt-4 pb-3 border-b border-border/40 flex items-start justify-between">
        <div>
          <h2 className="text-sm font-semibold text-text-primary tracking-tight uppercase">
            Capital Deployment
          </h2>
          <p className="text-[10px] text-text-tertiary/60 mt-0.5 uppercase tracking-wider">
            {posType} Position
            {allocationBias && ` · ${allocationBias}`}
            {noiseDefer && ' · Noise caution active'}
          </p>
        </div>
        <div className="flex items-center gap-1.5 mt-0.5">
          <span className={`text-[9px] font-medium px-1.5 py-0.5 rounded border uppercase tracking-wider ${
            bindingType === 'Within Guardrails'
              ? 'text-success border-success/30 bg-success/5'
              : bindingType === 'Cap-Bound'
              ? 'text-warning border-warning/30 bg-warning/5'
              : 'text-text-tertiary border-border/40'
          }`}>
            {bindingType}
          </span>
        </div>
      </div>

      {/* Allocation trio — large numerics */}
      <div className="grid grid-cols-3 divide-x divide-border/40">
        <AllocationBlock
          label="Recommended"
          value={`${conviction.recommended_pct.toFixed(1)}%`}
          sub={`$${conviction.dollar_per_100k?.toLocaleString() ?? '—'} per $100k`}
          highlight
        />
        <AllocationBlock
          label="Max Risk"
          value={`${conviction.max_pct.toFixed(1)}%`}
          sub="Policy ceiling"
        />
        <AllocationBlock
          label="Execution-Constrained"
          value={`${execPct.toFixed(1)}%`}
          sub={scalingLabel ?? (noiseDefer ? 'Noise-adjusted' : 'Final weight')}
        />
      </div>

      {/* Noise regime warning bar */}
      {noiseDefer && noiseRegime && (
        <div className="px-5 py-2 bg-warning/5 border-t border-warning/20 flex items-center gap-2">
          <span className="text-[10px] font-semibold text-warning uppercase tracking-wider">
            Noise Regime: {noiseRegime}
          </span>
          <span className="text-[10px] text-text-tertiary/60">
            — defer full sizing; scale gradually
          </span>
        </div>
      )}

      {/* Deployment logic toggle */}
      <div className="border-t border-border/30">
        <button
          onClick={() => setShowLogic(o => !o)}
          className="w-full flex items-center justify-between px-5 py-2.5 text-left hover:bg-surface-elevated/20 transition-colors"
        >
          <span className="text-[11px] text-text-tertiary/60 uppercase tracking-wider font-medium">
            Deployment Logic
          </span>
          {showLogic
            ? <ChevronUp className="h-3 w-3 text-text-tertiary/50" />
            : <ChevronDown className="h-3 w-3 text-text-tertiary/50" />}
        </button>

        {showLogic && (
          <div className="px-5 pb-5 pt-2 border-t border-border/20 space-y-4">

            {/* Rationale */}
            {conviction.rationale && (
              <div>
                <p className="text-[9px] font-semibold uppercase tracking-wider text-text-tertiary/60 mb-1.5">
                  Sizing Rationale
                </p>
                <p className="text-xs text-text-secondary leading-relaxed">
                  {conviction.rationale}
                </p>
              </div>
            )}

            {/* Justification (Trader) */}
            {conviction.conviction_justification && (
              <div>
                <p className="text-[9px] font-semibold uppercase tracking-wider text-text-tertiary/60 mb-1.5">
                  Conviction Basis
                </p>
                <p className="text-xs text-text-secondary leading-relaxed">
                  {conviction.conviction_justification}
                </p>
              </div>
            )}

            {/* Portfolio action details if available */}
            {signalBreakdown?.portfolio_action && (
              <div className="space-y-2">
                <p className="text-[9px] font-semibold uppercase tracking-wider text-text-tertiary/60">
                  Portfolio Action Context
                </p>
                <div className="grid grid-cols-2 gap-1.5">
                  {[
                    ['Allocation Bias', signalBreakdown.portfolio_action.allocation_bias],
                    ['Conviction Scale', `${signalBreakdown.portfolio_action.conviction_scaling_multiplier.toFixed(2)}× — ${signalBreakdown.portfolio_action.conviction_scaling_label}`],
                    ['Risk Budget Impact', signalBreakdown.portfolio_action.risk_budget_impact],
                    ['Mandate Fit', signalBreakdown.portfolio_action.mandate_fit],
                  ].map(([k, v]) => (
                    <div key={k} className="rounded border border-border/40 px-2.5 py-1.5">
                      <p className="text-[8px] uppercase tracking-wider text-text-tertiary/50 mb-0.5">{k}</p>
                      <p className="text-[11px] text-text-secondary">{v}</p>
                    </div>
                  ))}
                </div>
                {signalBreakdown.portfolio_action.sizing_guidance && (
                  <p className="text-[11px] text-text-tertiary/70 italic border-l-2 border-border pl-2.5 leading-relaxed">
                    {signalBreakdown.portfolio_action.sizing_guidance}
                  </p>
                )}
              </div>
            )}

            {/* Noise detail */}
            {signalBreakdown?.noise_filter && (
              <div>
                <p className="text-[9px] font-semibold uppercase tracking-wider text-text-tertiary/60 mb-1">
                  Noise Filter
                </p>
                <p className="text-[11px] text-text-secondary">
                  {signalBreakdown.noise_filter.action_guidance}
                </p>
              </div>
            )}

          </div>
        )}
      </div>
    </div>
  )
}
