'use client'

/**
 * Capital Allocation Discipline — Layer 2 (Investor+, collapsed by default)
 *
 * Parent accordion containing four sub-sections:
 *   A) Position Sizing Context     — open by default inside container
 *   B) Regime Conditions           — collapsed
 *   C) Risk Controls               — collapsed
 *   D) Capital Resolver            — collapsed (wraps existing FinalWeightResolver)
 *
 * CRITICAL: Duplicate % values must NOT appear outside this section.
 * Execution weight, cap %, headroom %, and utilisation % live here only.
 */

import { useState } from 'react'
import { ChevronDown, ChevronUp, Scale, Shield, Activity, AlertTriangle } from 'lucide-react'
import { Card, CardContent } from '@/components/ui/card'
import { FinalWeightResolver } from '@/components/results/FinalWeightResolver'
import type { ConvictionPosition, SignalBreakdown } from '@/types/api'
import type { TacticalStance, StructuralBias } from '@/lib/utils/decisionDimensions'
import { deriveConstraintTag } from '@/lib/narratives/sizingNarrative'

// ── Props ─────────────────────────────────────────────────────────────────────

interface CapitalAllocationDisciplineProps {
  conviction: ConvictionPosition
  signalBreakdown?: SignalBreakdown | null
  ticker: string
  rating?: string | null
  structuralBias: StructuralBias
  tacticalStance: TacticalStance
  positionType: 'Core' | 'Satellite'
}

// ── Sub-accordion component ───────────────────────────────────────────────────

function SubAccordion({
  title,
  icon,
  children,
  defaultOpen = false,
}: {
  title: string
  icon?: React.ReactNode
  children: React.ReactNode
  defaultOpen?: boolean
}) {
  const [open, setOpen] = useState(defaultOpen)
  return (
    <div className="rounded-md border border-border/50 bg-surface-elevated/30 overflow-hidden">
      <button
        onClick={() => setOpen(o => !o)}
        className="w-full flex items-center justify-between px-4 py-2.5 text-left hover:bg-surface-elevated/50 transition-colors"
      >
        <div className="flex items-center gap-2">
          {icon && <span className="text-text-tertiary">{icon}</span>}
          <span className="text-xs font-semibold text-text-secondary uppercase tracking-wide">
            {title}
          </span>
        </div>
        {open
          ? <ChevronUp className="h-3.5 w-3.5 text-text-tertiary flex-shrink-0" />
          : <ChevronDown className="h-3.5 w-3.5 text-text-tertiary flex-shrink-0" />
        }
      </button>
      {open && (
        <div className="border-t border-border/40 px-4 pb-4 pt-3">
          {children}
        </div>
      )}
    </div>
  )
}

// ── Helpers ───────────────────────────────────────────────────────────────────

function getExecutionMultiplier(level: string): number {
  const map: Record<string, number> = {
    High: 1.0, Medium: 0.7, Low: 0.4,
    HIGH: 1.0, MODERATE: 0.7, LOW: 0.4,
  }
  return map[level] ?? 0.7
}

function getSizingConfidence(multiplier: number): string {
  if (multiplier >= 1.0) return 'Stable'
  if (multiplier >= 0.7) return 'Adaptive'
  return 'Constrained'
}

function DataRow({
  label,
  value,
  valueClass = 'text-text-secondary',
  note,
}: {
  label: string
  value: string
  valueClass?: string
  note?: string
}) {
  return (
    <div className="flex items-start justify-between gap-3 py-1.5 border-b border-border/30 last:border-0">
      <span className="text-[11px] text-text-tertiary leading-tight">{label}</span>
      <div className="text-right">
        <span className={`text-[11px] font-semibold tabular-nums ${valueClass}`}>{value}</span>
        {note && <p className="text-[9px] text-text-tertiary/60 mt-0.5">{note}</p>}
      </div>
    </div>
  )
}

// ── Main component ────────────────────────────────────────────────────────────

export function CapitalAllocationDiscipline({
  conviction,
  signalBreakdown,
  ticker,
  rating,
  structuralBias,
  tacticalStance,
  positionType,
}: CapitalAllocationDisciplineProps) {
  const [containerOpen, setContainerOpen] = useState(false)

  const multiplier = getExecutionMultiplier(conviction.conviction_level)
  const baselineModelWeight =
    multiplier > 0
      ? Math.round((conviction.recommended_pct / multiplier) * 10) / 10
      : conviction.recommended_pct
  const constraintTag = deriveConstraintTag(conviction.recommended_pct, conviction.max_pct, conviction.conviction_level)
  const sizingConfidence = getSizingConfidence(multiplier)

  // ── Regime Conditions from signal breakdown ──────────────────────────────
  const noiseFilter = signalBreakdown?.noise_filter
  const evStability = signalBreakdown?.ev_stability
  const confidenceInt = signalBreakdown?.confidence_integrity
  const scenarioWeights = signalBreakdown?.scenario_weight_diagnostics
  const stopProb = signalBreakdown?.stop_probability

  // ── Synthesis sentence ───────────────────────────────────────────────────
  const synthesisSentence = (() => {
    if (constraintTag === 'Execution-bound') {
      return `Deployment constrained by signal regime quality, not portfolio cap.`
    }
    if (constraintTag === 'Cap-bound') {
      return `Allocation at policy ceiling — cap discipline enforced by portfolio construction rules.`
    }
    return `Allocation within normal operating parameters — no binding constraint active.`
  })()

  return (
    <div className="rounded-xl border border-border/60 bg-surface/30 overflow-hidden">

      {/* ── Container header / toggle ──────────────────────────────────────── */}
      <button
        onClick={() => setContainerOpen(o => !o)}
        className="w-full flex items-center justify-between px-5 py-3.5 text-left hover:bg-surface-elevated/30 transition-colors"
      >
        <div className="flex items-center gap-2.5">
          <Scale className="h-4 w-4 text-text-tertiary" />
          <div>
            <p className="text-sm font-semibold text-text-primary">Capital Allocation Discipline</p>
            <p className="text-[10px] text-text-tertiary mt-0.5">
              Sizing context · Regime conditions · Risk controls · Arbitration table
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <span className="text-[10px] text-text-tertiary font-mono tabular-nums">
            {conviction.recommended_pct}% allocated
          </span>
          {containerOpen
            ? <ChevronUp className="h-4 w-4 text-text-tertiary flex-shrink-0" />
            : <ChevronDown className="h-4 w-4 text-text-tertiary flex-shrink-0" />
          }
        </div>
      </button>

      {containerOpen && (
        <div className="border-t border-border/40 px-4 pb-4 pt-3 space-y-2.5">

          {/* ── A) Position Sizing Context (open by default) ─────────────── */}
          <SubAccordion
            title="Position Sizing Context"
            icon={<Shield className="h-3.5 w-3.5" />}
            defaultOpen={true}
          >
            <div className="space-y-3">
              {/* Base posture row */}
              <div className="flex items-center justify-between">
                <span className="text-[10px] text-text-tertiary">Base Posture</span>
                <div className="flex items-center gap-1.5">
                  <span className="text-[10px] font-medium text-text-secondary">{positionType} Position</span>
                  <span className="text-[10px] text-text-tertiary/40">·</span>
                  <span className="text-[10px] text-text-secondary">{structuralBias} Bias</span>
                  <span className="text-[10px] text-text-tertiary/40">·</span>
                  <span className="text-[10px] text-text-secondary">{tacticalStance}</span>
                </div>
              </div>

              {/* Allocation band and final weight */}
              <div className="rounded-md bg-surface-elevated/50 border border-border/50 px-3 py-2.5 space-y-1">
                <DataRow
                  label="Model Baseline Weight"
                  value={`${baselineModelWeight}%`}
                  valueClass="text-text-tertiary"
                  note="pre-multiplier"
                />
                <DataRow
                  label="Execution Multiplier"
                  value={`${multiplier.toFixed(3)}×`}
                  valueClass="text-text-secondary"
                  note={`${conviction.conviction_level.toLowerCase()} conviction`}
                />
                <DataRow
                  label="Policy Cap"
                  value={`${conviction.max_pct}%`}
                  valueClass="text-text-secondary"
                  note="portfolio ceiling"
                />
                <DataRow
                  label="Final Allocation"
                  value={`${conviction.recommended_pct}%`}
                  valueClass="text-text-primary font-bold"
                />
              </div>

              {/* Constraint tag + sizing confidence */}
              <div className="flex items-center justify-between">
                <span className={`text-[10px] font-semibold px-2 py-0.5 rounded-full border ${
                  constraintTag === 'Execution-bound'
                    ? 'bg-amber-500/10 text-amber-600 dark:text-amber-400 border-amber-500/20'
                    : constraintTag === 'Cap-bound'
                    ? 'bg-primary/10 text-primary border-primary/25'
                    : 'bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border-emerald-500/20'
                }`}>
                  {constraintTag}
                </span>
                <span className="text-[10px] text-text-tertiary">
                  Sizing Confidence: {sizingConfidence}
                </span>
              </div>

              {/* Synthesis sentence */}
              <p className="text-[11px] text-text-tertiary italic border-l-2 border-border/50 pl-2.5 leading-snug">
                {synthesisSentence}
              </p>

              {/* Dollar reference */}
              {conviction.dollar_per_100k > 0 && (
                <p className="text-[10px] text-text-tertiary">
                  ${conviction.dollar_per_100k.toLocaleString()} per $100K portfolio
                </p>
              )}
            </div>
          </SubAccordion>

          {/* ── B) Regime Conditions (collapsed) ─────────────────────────── */}
          <SubAccordion
            title="Regime Conditions"
            icon={<Activity className="h-3.5 w-3.5" />}
            defaultOpen={false}
          >
            <div className="space-y-1">
              {noiseFilter ? (
                <>
                  <DataRow
                    label="Noise Score"
                    value={`${noiseFilter.noise_score}`}
                    valueClass={noiseFilter.noise_score >= 35 ? 'text-warning' : 'text-text-secondary'}
                  />
                  <DataRow
                    label="Noise Regime"
                    value={noiseFilter.noise_regime ?? '—'}
                    valueClass={
                      noiseFilter.noise_regime === 'Noise Dominated' ? 'text-error'
                      : noiseFilter.noise_regime !== 'Clean' ? 'text-warning'
                      : 'text-success'
                    }
                  />
                  {noiseFilter.defer_sizing && (
                    <p className="text-[10px] text-warning mt-1.5">
                      Regime flag: sizing deferral recommended by model.
                    </p>
                  )}
                </>
              ) : (
                <p className="text-[11px] text-text-tertiary">Noise regime data unavailable.</p>
              )}

              {signalBreakdown?.signal_spread != null && (
                <DataRow
                  label="Dispersion σ"
                  value={signalBreakdown.signal_spread.toFixed(2)}
                  valueClass={signalBreakdown.signal_spread >= 2.5 ? 'text-warning' : 'text-text-secondary'}
                  note={signalBreakdown.signal_spread_label}
                />
              )}

              {evStability && (
                <DataRow
                  label="EV Stability Class"
                  value={evStability.stability_class ?? '—'}
                  valueClass={
                    evStability.stability_class === 'Structurally Stable' ? 'text-success'
                    : evStability.stability_class === 'Noise Dominated' ? 'text-error'
                    : 'text-warning'
                  }
                />
              )}

              {scenarioWeights && (
                <DataRow
                  label="Scenario Rotation Index"
                  value={scenarioWeights.scenario_rotation_index?.toFixed(2) ?? '—'}
                  valueClass="text-text-secondary"
                  note="weight volatility across model runs"
                />
              )}

              {/* One-line regime summary */}
              {noiseFilter?.noise_regime && (
                <p className="text-[10px] text-text-tertiary italic mt-2 border-l-2 border-border/40 pl-2">
                  {noiseFilter.noise_regime === 'Clean'
                    ? 'Signal environment is clean — regime not constraining sizing.'
                    : `${noiseFilter.noise_regime} environment active — regime conditions reducing effective allocation.`
                  }
                </p>
              )}
            </div>
          </SubAccordion>

          {/* ── C) Risk Controls (collapsed) ─────────────────────────────── */}
          <SubAccordion
            title="Risk Controls"
            icon={<AlertTriangle className="h-3.5 w-3.5" />}
            defaultOpen={false}
          >
            <div className="space-y-1">
              {stopProb ? (
                <>
                  <DataRow
                    label="Stop Probability"
                    value={`${stopProb.effective_stop_probability_pct?.toFixed(1) ?? '—'}%`}
                    valueClass={
                      (stopProb.effective_stop_probability_pct ?? 0) >= 20 ? 'text-warning'
                      : (stopProb.effective_stop_probability_pct ?? 0) >= 30 ? 'text-error'
                      : 'text-text-secondary'
                    }
                    note="probability of hitting stop before target"
                  />
                  {stopProb.base_stop_risk_pct != null && (
                    <DataRow
                      label="Base Stop Risk"
                      value={`${stopProb.base_stop_risk_pct.toFixed(1)}%`}
                      valueClass="text-text-tertiary"
                    />
                  )}
                  {stopProb.volatility_pressure_pct != null && (
                    <DataRow
                      label="Volatility Pressure"
                      value={`${stopProb.volatility_pressure_pct >= 0 ? '+' : ''}${stopProb.volatility_pressure_pct.toFixed(1)}%`}
                      valueClass={stopProb.volatility_pressure_pct > 0 ? 'text-warning' : 'text-success'}
                    />
                  )}
                  {stopProb.trend_modifier_pct != null && (
                    <DataRow
                      label="Trend Modifier"
                      value={`${stopProb.trend_modifier_pct >= 0 ? '+' : ''}${stopProb.trend_modifier_pct.toFixed(1)}%`}
                      valueClass={stopProb.trend_modifier_pct > 0 ? 'text-warning' : 'text-success'}
                    />
                  )}
                </>
              ) : (
                <p className="text-[11px] text-text-tertiary">Stop probability data unavailable.</p>
              )}

              {confidenceInt && (
                <>
                  <DataRow
                    label="Model Confidence"
                    value={confidenceInt.ev_confidence_level ?? '—'}
                    valueClass={
                      confidenceInt.ev_confidence_level === 'HIGH' ? 'text-success'
                      : confidenceInt.ev_confidence_level === 'LOW' || confidenceInt.ev_confidence_level === 'VERY LOW' ? 'text-warning'
                      : 'text-text-secondary'
                    }
                  />
                  {confidenceInt.total_degradation_pts != null && confidenceInt.total_degradation_pts > 0 && (
                    <DataRow
                      label="Confidence Degradation"
                      value={`−${confidenceInt.total_degradation_pts} pts`}
                      valueClass="text-warning/80"
                      note="cumulative confidence reduction"
                    />
                  )}
                </>
              )}

              {/* Tail risk comment */}
              {scenarioWeights?.tail_state && (
                <p className="text-[10px] text-text-tertiary italic mt-2 border-l-2 border-border/40 pl-2">
                  Tail state: {scenarioWeights.tail_state} — scenario tails are{' '}
                  {scenarioWeights.tail_state === 'Expanded' ? 'widened (elevated tail risk)'
                    : scenarioWeights.tail_state === 'Compressed' ? 'compressed (reduced tail risk)'
                    : 'within normal range'
                  }.
                </p>
              )}
            </div>
          </SubAccordion>

          {/* ── D) Capital Resolver (collapsed) ──────────────────────────── */}
          <SubAccordion
            title="Capital Resolver"
            icon={<Scale className="h-3.5 w-3.5" />}
            defaultOpen={false}
          >
            <div className="space-y-2">
              <p className="text-[10px] text-text-tertiary">
                MIN(Execution Weight, Policy Cap) — arbitration table below.
              </p>
              <FinalWeightResolver
                ticker={ticker}
                rating={rating}
                signalBreakdown={signalBreakdown}
                convictionPosition={conviction}
              />
            </div>
          </SubAccordion>

        </div>
      )}
    </div>
  )
}
