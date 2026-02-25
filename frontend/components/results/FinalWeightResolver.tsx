'use client'

/**
 * Final Position Weight Resolver
 *
 * Aggregates two upstream allocation outputs and enforces the binding constraint:
 *
 *   Final Weight = MIN(Execution Weight, Policy Cap)
 *
 * Input sources:
 *   – Noise-Adjusted Exposure Engine  → Execution Weight (adjusted_weight_pct)
 *   – Portfolio Construction Engine   → Policy Cap       (ConvictionPosition.max_pct)
 *
 * Resolver logic is deterministic and symmetric: whichever source produces the
 * lower allocation becomes the binding constraint. No override, no blending.
 */

import { useMemo, useState } from 'react'
import { Scale, Shield, ChevronRight, Info, ChevronDown, ChevronUp, HelpCircle, AlertTriangle, TrendingUp, TrendingDown, Minus } from 'lucide-react'
import { cn } from '@/lib/utils/cn'
import { computePositionSizing, defaultConfig } from '@/lib/engine/computePositionSizing'
import { buildCapitalDeploymentRationale } from '@/lib/engine/buildCapitalDeploymentRationale'
import type { PositionSizingInput } from '@/lib/engine/types'
import type { SignalBreakdown, ConvictionPosition, CapitalDeploymentDriver } from '@/types/api'

// ─── Props ────────────────────────────────────────────────────────────────────

interface FinalWeightResolverProps {
  ticker: string
  rating?: string | null
  signalBreakdown?: SignalBreakdown | null
  convictionPosition?: ConvictionPosition | null
}

// ─── Helpers ──────────────────────────────────────────────────────────────────

function normaliseSensitivity(raw?: string): 'LOW' | 'MODERATE' | 'HIGH' {
  const v = (raw ?? '').toUpperCase()
  if (v === 'HIGH') return 'HIGH'
  if (v === 'LOW') return 'LOW'
  return 'MODERATE'
}

function fmt(pct: number): string {
  return pct.toFixed(2) + '%'
}

type BindingSource = 'EXECUTION' | 'POLICY' | 'EQUAL'

// ─── Sub-components ───────────────────────────────────────────────────────────

function SourcePill({ label, active }: { label: string; active: boolean }) {
  return (
    <span
      className={cn(
        'text-[9px] font-semibold uppercase tracking-wider px-2 py-0.5 rounded-full border',
        active
          ? 'bg-primary/10 text-primary border-primary/30'
          : 'bg-surface-elevated text-text-tertiary border-border/40'
      )}
    >
      {active ? 'BINDING' : 'WITHIN CAP'}
    </span>
  )
}

function InputSourceCard({
  label,
  sublabel,
  value,
  isBinding,
  note,
  dimmed,
}: {
  label: string
  sublabel: string
  value: number
  isBinding: boolean
  note: string
  dimmed: boolean
}) {
  return (
    <div
      className={cn(
        'flex-1 rounded-lg border px-3 py-3 space-y-1.5 transition-all',
        isBinding
          ? 'border-primary/40 bg-primary/5'
          : dimmed
            ? 'border-border/30 bg-surface/20 opacity-60'
            : 'border-border/50 bg-surface/30'
      )}
    >
      <div className="flex items-start justify-between gap-1">
        <div>
          <p className="text-[9px] uppercase tracking-wider text-text-tertiary font-semibold">{label}</p>
          <p className="text-[10px] text-text-tertiary/70 mt-0.5 leading-tight">{sublabel}</p>
        </div>
        <SourcePill label={isBinding ? 'BINDING' : 'WITHIN CAP'} active={isBinding} />
      </div>
      <div className="flex items-baseline gap-1">
        <span
          className={cn(
            'text-2xl font-bold tabular-nums font-mono',
            isBinding ? 'text-primary' : 'text-text-secondary'
          )}
        >
          {value.toFixed(2)}
        </span>
        <span className="text-sm text-text-tertiary font-medium">%</span>
      </div>
      <p className="text-[10px] text-text-tertiary/60 leading-tight">{note}</p>
    </div>
  )
}

// ─── Capital Deployment Rationale sub-components ──────────────────────────────

function ImpactIcon({ impact }: { impact: CapitalDeploymentDriver['impact'] }) {
  if (impact === 'tighten') return <TrendingDown className="h-3 w-3 text-warning/70 shrink-0" />
  if (impact === 'loosen') return <TrendingUp className="h-3 w-3 text-success/70 shrink-0" />
  return <Minus className="h-3 w-3 text-text-tertiary/50 shrink-0" />
}

function ImpactBadge({ impact }: { impact: CapitalDeploymentDriver['impact'] }) {
  return (
    <span
      className={cn(
        'text-[8px] font-semibold uppercase tracking-wider px-1.5 py-0.5 rounded border shrink-0',
        impact === 'tighten'
          ? 'text-warning border-warning/30 bg-warning/10'
          : impact === 'loosen'
            ? 'text-success border-success/30 bg-success/10'
            : 'text-text-tertiary border-border/30 bg-surface-elevated'
      )}
    >
      {impact === 'tighten' ? '↓ Tighten' : impact === 'loosen' ? '↑ Loosen' : '— Neutral'}
    </span>
  )
}

function BindingBadge({ type }: { type: 'execution' | 'policy_cap' }) {
  return (
    <span
      className={cn(
        'inline-flex items-center gap-1 text-[9px] font-semibold uppercase tracking-wider px-2 py-0.5 rounded-full border',
        type === 'execution'
          ? 'text-primary border-primary/30 bg-primary/10'
          : 'text-warning border-warning/30 bg-warning/10'
      )}
    >
      <Shield className="h-2.5 w-2.5" />
      {type === 'execution' ? 'Execution-bound' : 'Cap-bound'}
    </span>
  )
}

function ArbitrationRow({
  dimension,
  value,
  status,
  statusClass,
  valueClass = 'text-text-secondary',
}: {
  dimension: string
  value: string
  status?: string
  statusClass?: string
  valueClass?: string
}) {
  return (
    <div className="grid grid-cols-[1fr_auto_auto] items-center gap-3 py-1.5 border-b border-border/30 last:border-0">
      <span className="text-[11px] text-text-tertiary">{dimension}</span>
      <span className={cn('text-[11px] font-semibold tabular-nums font-mono text-right', valueClass)}>
        {value}
      </span>
      {status && (
        <span
          className={cn(
            'text-[9px] font-semibold uppercase tracking-wider px-1.5 py-0.5 rounded border min-w-[52px] text-center',
            statusClass
          )}
        >
          {status}
        </span>
      )}
      {!status && <span />}
    </div>
  )
}

// ─── Main component ───────────────────────────────────────────────────────────

export function FinalWeightResolver({
  ticker,
  rating,
  signalBreakdown,
  convictionPosition,
}: FinalWeightResolverProps) {

  // ── Derive execution weight from Noise-Adjusted Exposure Engine ─────────────
  const executionWeightPct = useMemo((): number | null => {
    const noiseScore = signalBreakdown?.noise_filter?.noise_score
    const sensitivity = signalBreakdown?.model_sensitivity_attribution?.overall_sensitivity
    const sigma = signalBreakdown?.signal_spread
    const stopProbPct = signalBreakdown?.stop_probability?.effective_stop_probability_pct

    if (noiseScore == null || sigma == null || stopProbPct == null) return null

    const recPct = convictionPosition?.recommended_pct ?? 0
    const classification = recPct >= 5 ? 'CORE' : 'SATELLITE'
    const beta = signalBreakdown?.factor_diagnostics?.beta_estimate
    const hasDivergence = signalBreakdown?.has_divergence ?? false

    const input: PositionSizingInput = {
      symbol: ticker,
      classification,
      noise_score: noiseScore,
      overall_sensitivity: normaliseSensitivity(sensitivity),
      signal_dispersion_sigma: sigma,
      stop_probability: stopProbPct / 100,
      ...(beta != null && beta > 0 ? { beta } : {}),
      flags: {
        signal_conflict_active: hasDivergence,
        cap_at_satellite: hasDivergence,
      },
    }

    try {
      return computePositionSizing(input, defaultConfig).adjusted_weight_pct
    } catch {
      return null
    }
  }, [ticker, signalBreakdown, convictionPosition])

  // ── Policy Cap from Portfolio Construction Engine ───────────────────────────
  const policyCap = convictionPosition?.max_pct ?? null

  // ── Resolver: Final Weight = MIN(Execution Weight, Policy Cap) ──────────────
  const resolver = useMemo(() => {
    if (executionWeightPct == null || policyCap == null) return null

    const finalWeight = Math.min(executionWeightPct, policyCap)

    const bindingSource: BindingSource =
      executionWeightPct < policyCap ? 'EXECUTION'
      : policyCap < executionWeightPct ? 'POLICY'
      : 'EQUAL'

    const headroom = policyCap - executionWeightPct  // positive = cap not enforced
    const capUtilisation = (finalWeight / policyCap) * 100

    return { finalWeight, bindingSource, headroom, capUtilisation }
  }, [executionWeightPct, policyCap])

  // ── Capital Deployment Rationale ───────────────────────────────────────────
  const rationale = useMemo(() => {
    if (!resolver || executionWeightPct == null || policyCap == null) return null
    return buildCapitalDeploymentRationale({
      rating: rating ?? 'HOLD',
      signalBreakdown,
      convictionPosition,
      executionWeightPct,
      policyCap,
      finalWeight: resolver.finalWeight,
      bindingSource: resolver.bindingSource,
    })
  }, [rating, signalBreakdown, convictionPosition, executionWeightPct, policyCap, resolver])

  const [rationaleOpen, setRationaleOpen] = useState(true)

  // ── Early return: insufficient data ────────────────────────────────────────
  if (!resolver || executionWeightPct == null || policyCap == null) {
    return (
      <div className="rounded-lg border border-border/60 bg-surface/30 p-4">
        <div className="flex items-center gap-2 text-text-tertiary">
          <Scale className="h-4 w-4 shrink-0" />
          <span className="text-xs">
            Weight resolver unavailable — requires both noise-adjusted exposure output and
            conviction position data.
          </span>
        </div>
      </div>
    )
  }

  const { finalWeight, bindingSource, headroom, capUtilisation } = resolver
  const capEnforced = bindingSource === 'POLICY'

  // ── Resolver state copy ─────────────────────────────────────────────────────
  const resolverStateLabel =
    bindingSource === 'EXECUTION'
      ? 'Execution Weight is binding — Policy Cap not reached'
      : bindingSource === 'POLICY'
        ? 'Policy Cap enforced — Execution Weight truncated'
        : 'Execution Weight equals Policy Cap — resolver at equilibrium'

  const resolverStateCopy =
    bindingSource === 'EXECUTION'
      ? `The Noise-Adjusted Exposure Engine produced an allocation (${fmt(executionWeightPct)}) below the Policy Cap (${fmt(policyCap)}). No cap enforcement is required. The execution weight stands as the final allocation.`
      : bindingSource === 'POLICY'
        ? `The Portfolio Construction Engine's Policy Cap (${fmt(policyCap)}) is more restrictive than the Noise-Adjusted Exposure output (${fmt(executionWeightPct)}). Allocation discipline requires enforcement of the lower bound. Final weight is capped at ${fmt(finalWeight)}.`
        : `Execution Weight and Policy Cap are equal at ${fmt(finalWeight)}. Resolver is at equilibrium.`

  return (
    <div className="rounded-lg border border-border bg-surface overflow-hidden">

      {/* ── Header ──────────────────────────────────────────────────────────── */}
      <div className="flex items-center justify-between px-4 py-3 bg-surface-elevated/50 border-b border-border/60">
        <div className="flex items-center gap-2">
          <Scale className="h-4 w-4 text-text-tertiary" />
          <span className="text-xs font-semibold text-text-primary uppercase tracking-wide">
            Final Position Weight Resolver
          </span>
        </div>
        <div className="flex items-center gap-2">
          {capEnforced && (
            <span className="flex items-center gap-1 text-[10px] font-medium text-warning bg-warning/10 px-2 py-0.5 rounded-full">
              <Shield className="h-3 w-3" />
              Cap Enforced
            </span>
          )}
          {!capEnforced && (
            <span className="flex items-center gap-1 text-[10px] font-medium text-success bg-success/10 px-2 py-0.5 rounded-full">
              <Shield className="h-3 w-3" />
              No Cap Applied
            </span>
          )}
          <span className="text-[10px] text-text-tertiary font-mono">{ticker}</span>
        </div>
      </div>

      <div className="p-4 space-y-4">

        {/* ── Input sources: two-column cards ──────────────────────────────── */}
        <div>
          <p className="text-[9px] uppercase tracking-wider text-text-tertiary/60 font-semibold mb-2">
            Input Sources
          </p>
          <div className="flex gap-2">
            <InputSourceCard
              label="Noise-Adjusted Exposure"
              sublabel="Execution Weight"
              value={executionWeightPct}
              isBinding={bindingSource === 'EXECUTION' || bindingSource === 'EQUAL'}
              note="Signal-regime-weighted allocation from the Dynamic Position Sizing Engine"
              dimmed={capEnforced}
            />
            <InputSourceCard
              label="Portfolio Construction"
              sublabel="Policy Cap"
              value={policyCap}
              isBinding={bindingSource === 'POLICY'}
              note="Risk-adjusted ceiling enforced by the conviction-based allocation framework"
              dimmed={!capEnforced && bindingSource !== 'EQUAL'}
            />
          </div>
        </div>

        {/* ── Resolver rule ─────────────────────────────────────────────────── */}
        <div className="rounded-lg border border-border/50 bg-surface-elevated/30 px-3 py-2.5">
          <p className="text-[9px] uppercase tracking-wider text-text-tertiary/60 font-semibold mb-1.5">
            Resolver Rule
          </p>
          <div className="font-mono text-xs text-text-secondary space-y-0.5">
            <div>
              <span className="text-text-tertiary">Final Weight</span>
              <span className="mx-2 text-text-tertiary/50">=</span>
              <span>MIN(Execution Weight, Policy Cap)</span>
            </div>
            <div className="pl-24 text-text-tertiary">
              <span className="mx-0 text-text-tertiary/50">=</span>
              <span className="ml-2">MIN(
                <span className={bindingSource === 'EXECUTION' ? 'text-primary font-bold' : ''}>
                  {fmt(executionWeightPct)}
                </span>
                ,{' '}
                <span className={bindingSource === 'POLICY' ? 'text-primary font-bold' : ''}>
                  {fmt(policyCap)}
                </span>
              )</span>
            </div>
            <div className="pl-24 flex items-center gap-2">
              <span className="text-text-tertiary/50">=</span>
              <span className="ml-2 text-text-primary font-bold text-sm">{fmt(finalWeight)}</span>
              <ChevronRight className="h-3.5 w-3.5 text-text-tertiary/40" />
              <span className="text-[10px] text-text-tertiary">
                {bindingSource === 'EXECUTION' ? 'Execution binding'
                : bindingSource === 'POLICY' ? 'Policy Cap binding'
                : 'Equilibrium'}
              </span>
            </div>
          </div>
        </div>

        {/* ── Capital Deployment Rationale ──────────────────────────────────── */}
        {rationale && (
          <div className="rounded-lg border border-border/50 bg-surface-elevated/20 overflow-hidden">

            {/* Collapsible header */}
            <button
              onClick={() => setRationaleOpen((o) => !o)}
              className="w-full flex items-center justify-between px-3 py-2 hover:bg-surface-elevated/30 transition-colors text-left"
            >
              <div className="flex items-center gap-1.5">
                <HelpCircle className="h-3.5 w-3.5 text-text-tertiary/60 shrink-0" />
                <span className="text-[10px] font-semibold text-text-tertiary uppercase tracking-wider">
                  Why is my allocation {fmt(resolver.finalWeight)}?
                </span>
                <BindingBadge type={rationale.binding.type} />
              </div>
              {rationaleOpen
                ? <ChevronUp className="h-3.5 w-3.5 text-text-tertiary/40 shrink-0" />
                : <ChevronDown className="h-3.5 w-3.5 text-text-tertiary/40 shrink-0" />
              }
            </button>

            {rationaleOpen && (
              <div className="px-3 pb-3 pt-0 space-y-3 border-t border-border/30">

                {/* Summary */}
                <p className="text-[11px] text-text-secondary leading-relaxed pt-2.5">
                  {rationale.summary}
                </p>

                {/* Drivers (if any) */}
                {rationale.drivers.length > 0 && (
                  <div className="space-y-1">
                    <p className="text-[9px] uppercase tracking-wider text-text-tertiary/50 font-semibold">
                      Sizing Drivers
                    </p>
                    <div className="space-y-1">
                      {rationale.drivers.map((d, i) => (
                        <div key={i} className="flex items-start gap-2 py-1 border-b border-border/20 last:border-0">
                          <ImpactIcon impact={d.impact} />
                          <div className="flex-1 min-w-0">
                            <div className="flex items-center gap-1.5 flex-wrap">
                              <span className="text-[10px] font-medium text-text-secondary">{d.label}</span>
                              <ImpactBadge impact={d.impact} />
                            </div>
                            <p className="text-[10px] text-text-tertiary/70 leading-tight mt-0.5">{d.evidence}</p>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* Interpretation bullets */}
                <div className="space-y-1">
                  <p className="text-[9px] uppercase tracking-wider text-text-tertiary/50 font-semibold">
                    Interpretation
                  </p>
                  <ul className="space-y-1">
                    {rationale.interpretation.map((line, i) => (
                      <li key={i} className="flex items-start gap-1.5">
                        <span className="text-text-tertiary/30 text-[10px] shrink-0 mt-0.5">•</span>
                        <span className="text-[10px] text-text-tertiary leading-relaxed">{line}</span>
                      </li>
                    ))}
                  </ul>
                </div>

                {/* Binding explanation */}
                <div className="rounded border border-border/40 bg-surface/30 px-2.5 py-2">
                  <div className="flex items-start gap-1.5">
                    <Info className="h-3 w-3 text-text-tertiary/40 shrink-0 mt-0.5" />
                    <p className="text-[10px] text-text-tertiary leading-relaxed">
                      {rationale.binding.explanation}
                    </p>
                  </div>
                </div>

                {/* Next actions */}
                {rationale.next_actions.length > 0 && (
                  <div className="space-y-1">
                    <p className="text-[9px] uppercase tracking-wider text-text-tertiary/50 font-semibold">
                      What would change this?
                    </p>
                    <ul className="space-y-0.5">
                      {rationale.next_actions.map((action, i) => (
                        <li key={i} className="flex items-start gap-1.5">
                          <span className="text-primary/40 text-[10px] shrink-0 mt-0.5">→</span>
                          <span className="text-[10px] text-text-tertiary/80 leading-relaxed">{action}</span>
                        </li>
                      ))}
                    </ul>
                  </div>
                )}

                {/* Disclaimer */}
                <p className="text-[9px] text-text-tertiary/30 italic">{rationale.disclaimers}</p>

              </div>
            )}
          </div>
        )}

        {/* ── Final Allowed Allocation — hero ───────────────────────────────── */}
        <div
          className={cn(
            'rounded-lg border p-5 text-center',
            capEnforced
              ? 'border-warning/30 bg-warning/5'
              : 'border-primary/20 bg-primary/5'
          )}
        >
          <p className="text-[9px] uppercase tracking-widest font-semibold mb-1.5"
             style={{ color: capEnforced ? 'var(--warning)' : undefined }}
             >
            <span className={capEnforced ? 'text-warning/70' : 'text-text-tertiary'}>
              Final Allowed Allocation
            </span>
          </p>
          <div className="flex items-baseline justify-center gap-1">
            <span
              className={cn(
                'text-5xl font-bold tabular-nums font-mono',
                capEnforced ? 'text-warning' : 'text-primary'
              )}
            >
              {finalWeight.toFixed(2)}
            </span>
            <span className={cn('text-2xl font-semibold', capEnforced ? 'text-warning/70' : 'text-primary/60')}>
              %
            </span>
          </div>
          <p className={cn('text-[11px] mt-2 font-medium', capEnforced ? 'text-warning/70' : 'text-success')}>
            {resolverStateLabel}
          </p>
        </div>

        {/* ── Sizing Arbitration table ──────────────────────────────────────── */}
        <div>
          <p className="text-[9px] uppercase tracking-wider text-text-tertiary/60 font-semibold mb-2">
            Sizing Arbitration
          </p>
          <div className="rounded-lg border border-border/50 bg-surface/30 px-3 py-1">

            {/* Column headers */}
            <div className="grid grid-cols-[1fr_auto_auto] gap-3 pb-1 mb-0.5 border-b border-border/30">
              <span className="text-[9px] uppercase tracking-wider text-text-tertiary/50 font-semibold">Dimension</span>
              <span className="text-[9px] uppercase tracking-wider text-text-tertiary/50 font-semibold text-right">Value</span>
              <span className="text-[9px] uppercase tracking-wider text-text-tertiary/50 font-semibold text-center min-w-[52px]">Status</span>
            </div>

            <ArbitrationRow
              dimension="Execution Weight"
              value={fmt(executionWeightPct)}
              status={bindingSource === 'EXECUTION' || bindingSource === 'EQUAL' ? 'BINDING' : 'ALLOWED'}
              statusClass={
                bindingSource === 'EXECUTION' || bindingSource === 'EQUAL'
                  ? 'text-primary border-primary/30 bg-primary/10'
                  : 'text-text-tertiary border-border/40 bg-surface-elevated'
              }
              valueClass={
                bindingSource === 'EXECUTION' ? 'text-primary' : 'text-text-secondary'
              }
            />

            <ArbitrationRow
              dimension="Policy Cap"
              value={fmt(policyCap)}
              status={bindingSource === 'POLICY' ? 'BINDING' : 'ALLOWED'}
              statusClass={
                bindingSource === 'POLICY'
                  ? 'text-warning border-warning/30 bg-warning/10'
                  : 'text-text-tertiary border-border/40 bg-surface-elevated'
              }
              valueClass={bindingSource === 'POLICY' ? 'text-warning' : 'text-text-secondary'}
            />

            <ArbitrationRow
              dimension="Final Resolved Weight"
              value={fmt(finalWeight)}
              status="ENFORCED"
              statusClass="text-success border-success/30 bg-success/10"
              valueClass="text-text-primary"
            />

            <ArbitrationRow
              dimension="Cap Headroom"
              value={
                headroom >= 0
                  ? `+${headroom.toFixed(2)}%`
                  : `${headroom.toFixed(2)}%`
              }
              valueClass={headroom >= 0 ? 'text-success/70' : 'text-warning/70'}
            />

            <ArbitrationRow
              dimension="Cap Utilisation"
              value={`${capUtilisation.toFixed(1)}%`}
              valueClass={
                capUtilisation >= 100 ? 'text-warning'
                : capUtilisation >= 80  ? 'text-warning/70'
                : 'text-text-tertiary'
              }
            />
          </div>
        </div>

        {/* ── Resolver explanation ──────────────────────────────────────────── */}
        <div className="rounded-lg border border-border/40 bg-surface-elevated/20 px-3 py-2.5">
          <div className="flex items-start gap-1.5">
            <Info className="h-3.5 w-3.5 text-text-tertiary/50 shrink-0 mt-0.5" />
            <p className="text-[11px] text-text-tertiary leading-relaxed">
              {resolverStateCopy}
            </p>
          </div>
        </div>

        {/* ── Methodology note ─────────────────────────────────────────────── */}
        <p className="text-[10px] text-text-tertiary/40 italic leading-relaxed">
          Resolver applies a strict MIN constraint — no interpolation, no blending.
          Allocation discipline is enforced by the lower of the two upstream outputs.
          Final weight is a sizing ceiling, not a directive to deploy full size at initiation.
        </p>

      </div>
    </div>
  )
}
