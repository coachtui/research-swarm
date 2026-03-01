'use client'

// Terminal-grade unified above-fold dashboard.
// Strict hierarchy: EV (largest) → Allocation (second) → PW Target (third).
// Flat UI — no heavy fills, whitespace + subtle dividers only.
//
// ROW 1 — Signal strip:  Rating · Conviction  |  EV (dominant)  |  Price · FV · Implied
// ROW 2 — Scenario band: minimalist strip with thin color accents + PW Target
// ROW 3 — Deployment:    Allocation % (second-tier dominant) + 4-cell secondary grid
//
// No new model logic — all values derived from existing output fields.

import { useState } from 'react'
import { ChevronDown, ChevronUp, TrendingUp, TrendingDown } from 'lucide-react'
import type { ConvictionPosition, SignalBreakdown, FairValueCalibration } from '@/types/api'
import { deriveStructuralBias } from '@/lib/utils/decisionDimensions'

// ── Types ──────────────────────────────────────────────────────────────────────

interface PriceTargets {
  bear_target: number
  bear_probability: number
  bear_assumptions: string
  base_target: number
  base_probability: number
  base_assumptions: string
  bull_target: number
  bull_probability: number
  bull_assumptions: string
  methodology?: string
}

interface TerminalDashboardProps {
  rating: string | null
  ticker: string
  currentPrice: number
  conviction: ConvictionPosition | null
  fairValueCalibration?: FairValueCalibration | null
  priceTargets?: PriceTargets | null
  signalBreakdown?: SignalBreakdown | null
  expectedReturnAnnualized?: number | null
}

// ── Helpers ────────────────────────────────────────────────────────────────────

function ratingTextColor(rating: string | null): string {
  if (!rating) return 'text-text-secondary'
  const r = rating.toUpperCase()
  if (['STRONG BUY', 'BUY', 'ACCUMULATE', 'BULLISH'].some(k => r.includes(k)))
    return 'text-success'
  if (['AVOID', 'SELL', 'REDUCE', 'BEARISH'].some(k => r.includes(k)))
    return 'text-error'
  return 'text-warning'
}

function signColor(v: number | null) {
  if (v === null) return 'text-text-secondary'
  return v > 0 ? 'text-success' : v < 0 ? 'text-error' : 'text-text-secondary'
}

function fmt(v: number | null, sign = true, decimals = 1): string {
  if (v === null || isNaN(v)) return '—'
  return `${sign && v > 0 ? '+' : ''}${v.toFixed(decimals)}%`
}

function convictionTier(
  convictionLevel: string | undefined,
  recommendedPct: number | undefined,
  evPct: number | null,
): string {
  const level = (convictionLevel ?? '').toLowerCase()
  const pct = recommendedPct ?? 0
  const ev = evPct ?? 0
  if (level === 'high' && pct >= 5 && ev >= 15) return 'Strategic'
  if (level === 'high') return 'High'
  if (level === 'medium' || level === 'moderate') return 'Moderate'
  return 'Low'
}

function convictionTierColor(tier: string): string {
  if (tier === 'Strategic') return 'text-primary'
  if (tier === 'High') return 'text-success'
  if (tier === 'Moderate') return 'text-warning'
  return 'text-text-tertiary'
}

// Asymmetric return profile descriptor — skewRatio = bull% / |bear%|
function asymmetryProfile(skewRatio: number | null): string {
  if (skewRatio === null) return ''
  if (skewRatio >= 3.0) return 'Strong Positive Skew'
  if (skewRatio >= 1.8) return 'Moderate Positive Skew'
  if (skewRatio >= 1.1) return 'Weak Positive Skew'
  if (skewRatio >= 0.9) return 'Symmetric Distribution'
  if (skewRatio >= 0.5) return 'Slight Negative Skew'
  return 'Negative Skew'
}

function positionTypeLabel(convictionLevel: string): string {
  const l = convictionLevel.toLowerCase()
  if (l === 'high') return 'Core'
  if (l === 'medium' || l === 'moderate') return 'Satellite'
  return 'Tactical'
}

function executionConstrainedPct(
  conviction: ConvictionPosition | null,
  signalBreakdown?: SignalBreakdown | null,
): number {
  if (!conviction) return 0
  const scalingMult = signalBreakdown?.portfolio_action?.conviction_scaling_multiplier
  if (scalingMult !== undefined && scalingMult !== null) {
    return Math.min(conviction.recommended_pct * scalingMult, conviction.max_pct)
  }
  const lvl = (conviction.conviction_level ?? '').toLowerCase()
  const mult = lvl === 'high' ? 1.0 : lvl === 'medium' ? 0.75 : 0.5
  const noiseDeferral = signalBreakdown?.noise_filter?.defer_sizing ? 0.75 : 1.0
  return Math.min(conviction.recommended_pct * mult * noiseDeferral, conviction.max_pct)
}

function pct(target: number, current: number): number {
  return ((target - current) / current) * 100
}

// ── Sub-components ─────────────────────────────────────────────────────────────

function MetricCell({
  label,
  value,
  valueClass = 'text-text-primary',
  sub,
}: {
  label: string
  value: React.ReactNode
  valueClass?: string
  sub?: string
}) {
  return (
    <div className="flex flex-col gap-0.5">
      <span className="text-[9px] uppercase tracking-[0.13em] font-semibold text-text-tertiary/60">{label}</span>
      <span className={`text-sm font-bold font-mono leading-none ${valueClass}`}>{value}</span>
      {sub && <span className="text-[9px] text-text-tertiary/40 font-mono">{sub}</span>}
    </div>
  )
}

function SecondaryCell({
  label,
  value,
  valueClass = 'text-text-primary',
}: {
  label: string
  value: React.ReactNode
  valueClass?: string
}) {
  return (
    <div className="px-4 py-3 flex flex-col gap-0.5">
      <span className="text-[9px] uppercase tracking-[0.13em] font-semibold text-text-tertiary/60">{label}</span>
      <span className={`text-lg font-bold font-mono leading-none ${valueClass}`}>{value}</span>
    </div>
  )
}

// ── Main ───────────────────────────────────────────────────────────────────────

export function TerminalDashboard({
  rating,
  ticker,
  currentPrice,
  conviction,
  fairValueCalibration,
  priceTargets,
  signalBreakdown,
  expectedReturnAnnualized,
}: TerminalDashboardProps) {
  const [showAssumptions, setShowAssumptions] = useState(false)
  const [showDeploymentLogic, setShowDeploymentLogic] = useState(false)

  // ── Row 1 calculations ─────────────────────────────────────────────────────
  let evPct: number | null = null
  if (priceTargets && currentPrice > 0) {
    const bearW = priceTargets.bear_probability ?? 0.25
    const baseW = priceTargets.base_probability ?? 0.50
    const bullW = priceTargets.bull_probability ?? 0.25
    const pw =
      priceTargets.bear_target * bearW +
      priceTargets.base_target * baseW +
      priceTargets.bull_target * bullW
    evPct = ((pw - currentPrice) / currentPrice) * 100
  }

  const stabilityMod = signalBreakdown?.data_integrity_confidence_factor ?? 1.0
  const effectiveEvPct = evPct !== null ? evPct * stabilityMod : null

  const rawConfidence =
    signalBreakdown?.confidence_integrity?.effective_confidence_pct ??
    ((signalBreakdown?.signal_strength ?? null) !== null
      ? Math.round((signalBreakdown!.signal_strength!) * 100)
      : null)

  const fvMid = fairValueCalibration?.internal_fair_value ?? null
  const impliedUpside =
    fvMid && currentPrice > 0 ? ((fvMid - currentPrice) / currentPrice) * 100 : null

  const bias = deriveStructuralBias(rating)
  const ratingColor = ratingTextColor(rating)
  const tier = conviction
    ? convictionTier(conviction.conviction_level, conviction.recommended_pct, effectiveEvPct)
    : null
  const tierColor = tier ? convictionTierColor(tier) : 'text-text-tertiary'
  const irr = expectedReturnAnnualized ?? null

  // ── Row 2 calculations ─────────────────────────────────────────────────────
  let bearRet = 0, baseRet = 0, bullRet = 0, pwTarget = 0, pwRet = 0
  let downsideSeverity: number | null = null
  let upsideSkewRatio: number | null = null
  let bearPct = 0, basePct = 0, bullPct = 0

  if (priceTargets && currentPrice > 0) {
    bearPct = Math.round((priceTargets.bear_probability ?? 0.25) * 100)
    basePct = Math.round((priceTargets.base_probability ?? 0.50) * 100)
    bullPct = Math.round((priceTargets.bull_probability ?? 0.25) * 100)
    bearRet = pct(priceTargets.bear_target, currentPrice)
    baseRet = pct(priceTargets.base_target, currentPrice)
    bullRet = pct(priceTargets.bull_target, currentPrice)
    pwTarget =
      priceTargets.bear_target * (priceTargets.bear_probability ?? 0.25) +
      priceTargets.base_target * (priceTargets.base_probability ?? 0.50) +
      priceTargets.bull_target * (priceTargets.bull_probability ?? 0.25)
    pwRet = pct(pwTarget, currentPrice)
    downsideSeverity = bearRet
    upsideSkewRatio = Math.abs(bearRet) > 0.01 ? bullRet / Math.abs(bearRet) : null
  }

  const scenarioRows = priceTargets ? [
    {
      label: 'BASE',
      weight: basePct,
      target: priceTargets.base_target,
      ret: baseRet,
      retColor: baseRet >= 0 ? 'text-success' : 'text-error',
      accentBorder: 'border-t-2 border-t-blue-500/70',
      labelColor: 'text-blue-400',
      assumptions: priceTargets.base_assumptions,
    },
    {
      label: 'BULL',
      weight: bullPct,
      target: priceTargets.bull_target,
      ret: bullRet,
      retColor: 'text-success',
      accentBorder: 'border-t-2 border-t-emerald-500/70',
      labelColor: 'text-emerald-400',
      assumptions: priceTargets.bull_assumptions,
    },
    {
      label: 'BEAR',
      weight: bearPct,
      target: priceTargets.bear_target,
      ret: bearRet,
      retColor: 'text-error',
      accentBorder: 'border-t-2 border-t-red-500/70',
      labelColor: 'text-red-400',
      assumptions: priceTargets.bear_assumptions,
    },
  ] : []

  // ── Row 3 calculations ─────────────────────────────────────────────────────
  const execPct = executionConstrainedPct(conviction, signalBreakdown)
  const posType = conviction ? positionTypeLabel(conviction.conviction_level) : null
  const bindingType = conviction
    ? (execPct < conviction.recommended_pct * 0.95
        ? (execPct >= conviction.max_pct * 0.95 ? 'Cap-Bound' : 'Execution-Bound')
        : 'Within Guardrails')
    : null
  const noiseDefer = signalBreakdown?.noise_filter?.defer_sizing
  const noiseRegime = signalBreakdown?.noise_filter?.noise_regime
  const scalingLabel = signalBreakdown?.portfolio_action?.conviction_scaling_label ?? null

  return (
    <div className="rounded-xl border border-border/40 overflow-hidden">

      {/* ═══════════════════════════════════════════════════════════════════
          ROW 1 — SIGNAL STRIP
          Non-symmetric flex layout:
            Left  (fixed ~180px): Ticker dominant → Rating → Conviction
            Center (flex-1, widest): "Probability-Weighted Edge" label →
                   EV text-5xl → Asymmetry descriptor → muted supporting metrics
            Right  (fixed ~200px): Price → FV · Implied muted
          ═══════════════════════════════════════════════════════════════════ */}
      <div className="flex flex-col sm:flex-row divide-y sm:divide-y-0 sm:divide-x divide-border/30">

        {/* Left — ticker anchors the page; rating + conviction below */}
        <div className="sm:w-44 flex-shrink-0 px-5 py-5 flex flex-col justify-center gap-1.5">
          <span className="text-3xl font-bold font-mono text-text-primary leading-none tracking-tight">
            {ticker}
          </span>
          <span className={`text-[11px] font-bold tracking-widest uppercase mt-1 ${ratingColor}`}>
            {bias || rating || '—'}
          </span>
          {tier && (
            <span className={`text-[10px] font-semibold ${tierColor}`}>
              {tier} Conviction
            </span>
          )}
        </div>

        {/* Center — EV is the alpha signal; asymmetry narrates the edge */}
        <div className="flex-1 px-6 py-5 flex flex-col justify-center gap-2.5">
          <div>
            <p className="text-[9px] uppercase tracking-[0.15em] font-semibold text-text-tertiary/50 mb-1">
              Probability-Weighted Edge
            </p>
            <p className={`text-5xl font-bold font-mono leading-none ${signColor(effectiveEvPct)}`}>
              {fmt(effectiveEvPct)}
            </p>
            {upsideSkewRatio !== null && (
              <p className="text-[10px] text-text-tertiary/50 font-medium mt-1.5 tracking-wide">
                Asymmetric Profile: {asymmetryProfile(upsideSkewRatio)}
              </p>
            )}
          </div>
          {/* Supporting metrics — muted, secondary */}
          <div className="flex items-center gap-4 flex-wrap">
            {rawConfidence !== null && (
              <MetricCell
                label="Confidence"
                value={`${rawConfidence}`}
                valueClass={
                  rawConfidence >= 65 ? 'text-success/80' :
                  rawConfidence >= 40 ? 'text-warning/80' : 'text-error/80'
                }
                sub="signal integrity"
              />
            )}
            {irr !== null && rawConfidence !== null && (
              <div className="w-px h-5 bg-border/25" />
            )}
            {irr !== null && (
              <MetricCell
                label="Ann. IRR"
                value={fmt(irr)}
                valueClass={`${signColor(irr)} opacity-70`}
                sub="annualised"
              />
            )}
          </div>
        </div>

        {/* Right — price reference; FV + implied muted */}
        <div className="sm:w-52 flex-shrink-0 px-5 py-5 flex flex-col justify-center gap-2.5">
          <div>
            <p className="text-[9px] uppercase tracking-[0.13em] font-semibold text-text-tertiary/50 mb-1">
              Current Price
            </p>
            <p className="text-2xl font-bold font-mono text-text-primary leading-none">
              ${currentPrice.toFixed(2)}
            </p>
          </div>
          <div className="flex items-center gap-4 flex-wrap">
            <MetricCell
              label="Fair Value"
              value={fvMid ? `$${fvMid.toFixed(0)}` : '—'}
              valueClass="text-text-secondary"
              sub={fairValueCalibration?.display_label ?? 'blended'}
            />
            {impliedUpside !== null && (
              <>
                <div className="w-px h-5 bg-border/25" />
                <MetricCell
                  label="Implied ↑/↓"
                  value={
                    <span className="flex items-center gap-1">
                      {impliedUpside > 0
                        ? <TrendingUp className="h-3 w-3 flex-shrink-0" />
                        : <TrendingDown className="h-3 w-3 flex-shrink-0" />}
                      {fmt(impliedUpside)}
                    </span>
                  }
                  valueClass={`${signColor(impliedUpside)} opacity-80`}
                  sub="vs FV mid"
                />
              </>
            )}
          </div>
        </div>
      </div>

      {/* ═══════════════════════════════════════════════════════════════════
          ROW 2 — SCENARIO STRIP
          Minimalist horizontal band. Thin color accents. Compact pricing.
          PW Target = third-tier dominant below the strip.
          ═══════════════════════════════════════════════════════════════════ */}
      {priceTargets && (
        <div className="border-t border-border/30">

          {/* 3-scenario compact row */}
          <div className="grid grid-cols-3 divide-x divide-border/25">
            {scenarioRows.map(row => (
              <div
                key={row.label}
                className={`px-5 py-3.5 ${row.accentBorder}`}
              >
                <p className={`text-[9px] font-bold uppercase tracking-[0.14em] mb-1.5 ${row.labelColor}`}>
                  {row.label} · {row.weight}%
                </p>
                <div className="flex items-baseline gap-2">
                  <span className="text-xl font-bold font-mono text-text-primary leading-none">
                    ${row.target.toFixed(0)}
                  </span>
                  <span className={`text-sm font-semibold font-mono ${row.retColor}`}>
                    {fmt(row.ret, true)}
                  </span>
                </div>
              </div>
            ))}
          </div>

          {/* PW Target row — third in hierarchy */}
          <div className="border-t border-border/25 px-5 py-3 flex items-center gap-6 flex-wrap">
            <div>
              <p className="text-[9px] uppercase tracking-[0.13em] font-semibold text-text-tertiary/60">
                PW Target
              </p>
              <div className="flex items-baseline gap-2 mt-0.5">
                <span className="text-2xl font-bold font-mono text-text-primary">
                  ${pwTarget.toFixed(0)}
                </span>
                <span className={`text-sm font-bold font-mono ${signColor(pwRet)}`}>
                  {fmt(pwRet, true)}
                </span>
                {stabilityMod < 1 && (
                  <span className="text-[10px] text-warning font-mono">
                    eff {fmt(pwRet * stabilityMod, true)}
                  </span>
                )}
              </div>
            </div>
            <div className="w-px h-7 bg-border/25" />
            <div>
              <p className="text-[9px] uppercase tracking-[0.13em] font-semibold text-text-tertiary/60">
                Downside
              </p>
              <p className="text-sm font-bold font-mono text-error mt-0.5">
                {downsideSeverity !== null ? fmt(downsideSeverity, true) : '—'}
              </p>
            </div>
            <div className="w-px h-7 bg-border/25" />
            <div>
              <p className="text-[9px] uppercase tracking-[0.13em] font-semibold text-text-tertiary/60">
                Skew
              </p>
              <p className={`text-sm font-bold font-mono mt-0.5 ${
                upsideSkewRatio === null ? 'text-text-secondary' :
                upsideSkewRatio >= 2 ? 'text-success' :
                upsideSkewRatio >= 1 ? 'text-warning' : 'text-error'
              }`}>
                {upsideSkewRatio !== null ? `${upsideSkewRatio.toFixed(1)}×` : '—'}
              </p>
            </div>
          </div>

          {/* Scenario assumptions toggle */}
          <div className="border-t border-border/20">
            <button
              onClick={() => setShowAssumptions(o => !o)}
              className="w-full flex items-center justify-between px-5 py-2 text-left hover:bg-surface-elevated/15 transition-colors"
            >
              <span className="text-[10px] text-text-tertiary/40 uppercase tracking-wider font-medium">
                Scenario Assumptions
              </span>
              {showAssumptions
                ? <ChevronUp className="h-3 w-3 text-text-tertiary/30" />
                : <ChevronDown className="h-3 w-3 text-text-tertiary/30" />}
            </button>
            {showAssumptions && (
              <div className="px-5 pb-4 pt-1 border-t border-border/15 space-y-3">
                {scenarioRows.map(row => (
                  <div key={row.label} className={`border-l-2 pl-3 ${
                    row.label === 'BASE' ? 'border-l-blue-500/50' :
                    row.label === 'BULL' ? 'border-l-emerald-500/50' : 'border-l-red-500/50'
                  }`}>
                    <p className={`text-[9px] font-bold uppercase tracking-wider mb-1 ${row.labelColor}`}>
                      {row.label} · {row.weight}%
                    </p>
                    <p className="text-[11px] text-text-tertiary leading-relaxed">
                      {row.assumptions}
                    </p>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      )}

      {/* ═══════════════════════════════════════════════════════════════════
          ROW 3 — CAPITAL DEPLOYMENT (only when conviction data is available)
          Allocation % = second-tier dominant (text-4xl, EV is text-5xl).
          Right: 2×2 secondary grid (text-lg, supporting only).
          No fill backgrounds.
          ═══════════════════════════════════════════════════════════════════ */}
      {conviction && <div className="border-t border-border/30">
        {/* Header strip */}
        <div className="px-5 py-2 border-b border-border/25 flex items-center justify-between">
          <p className="text-[9px] uppercase tracking-[0.14em] font-semibold text-text-tertiary/50">
            Capital Deployment · {posType} Position
          </p>
          <span className={`text-[9px] font-semibold px-1.5 py-0.5 rounded border uppercase tracking-wider ${
            bindingType === 'Within Guardrails'
              ? 'text-success border-success/25 bg-success/5'
              : bindingType === 'Cap-Bound'
              ? 'text-warning border-warning/25 bg-warning/5'
              : 'text-text-tertiary/60 border-border/30'
          }`}>
            {bindingType}
          </span>
        </div>

        {/* Allocation layout */}
        <div className="flex divide-x divide-border/30">

          {/* Dominant: Recommended % */}
          <div className="flex-[2] px-6 py-5 flex flex-col justify-center">
            <p className="text-[9px] uppercase tracking-[0.15em] font-semibold text-text-tertiary/50 mb-1.5">
              Recommended Allocation
            </p>
            <p className="text-4xl font-bold font-mono text-primary leading-none">
              {conviction.recommended_pct.toFixed(1)}%
            </p>
            {conviction.dollar_per_100k !== undefined && conviction.dollar_per_100k !== null && (
              <p className="text-[10px] text-text-tertiary/50 mt-2 font-mono">
                ${conviction.dollar_per_100k.toLocaleString()} per $100k
              </p>
            )}
          </div>

          {/* Secondary 2×2 */}
          <div className="flex-[3] grid grid-cols-2 divide-x divide-y divide-border/25">
            <SecondaryCell label="Max Risk" value={`${conviction.max_pct.toFixed(1)}%`} />
            <SecondaryCell
              label="Exec-Constrained"
              value={`${execPct.toFixed(1)}%`}
            />
            <SecondaryCell
              label="Asymmetry Ratio"
              value={upsideSkewRatio !== null ? `${upsideSkewRatio.toFixed(1)}×` : '—'}
              valueClass={
                upsideSkewRatio === null ? 'text-text-secondary' :
                upsideSkewRatio >= 2 ? 'text-success' :
                upsideSkewRatio >= 1 ? 'text-warning' : 'text-error'
              }
            />
            <SecondaryCell
              label="Downside Severity"
              value={downsideSeverity !== null ? fmt(downsideSeverity, true) : '—'}
              valueClass="text-error"
            />
          </div>
        </div>

        {/* Noise regime warning */}
        {noiseDefer && noiseRegime && (
          <div className="px-5 py-2 border-t border-warning/15 flex items-center gap-2">
            <span className="text-[10px] font-semibold text-warning uppercase tracking-wider">
              Noise Regime: {noiseRegime}
            </span>
            <span className="text-[10px] text-text-tertiary/50">
              — defer full sizing; scale gradually
            </span>
          </div>
        )}

        {/* Deployment Logic toggle */}
        <div className="border-t border-border/20">
          <button
            onClick={() => setShowDeploymentLogic(o => !o)}
            className="w-full flex items-center justify-between px-5 py-2 text-left hover:bg-surface-elevated/15 transition-colors"
          >
            <span className="text-[10px] text-text-tertiary/40 uppercase tracking-wider font-medium">
              Deployment Logic
            </span>
            {showDeploymentLogic
              ? <ChevronUp className="h-3 w-3 text-text-tertiary/30" />
              : <ChevronDown className="h-3 w-3 text-text-tertiary/30" />}
          </button>
          {showDeploymentLogic && (
            <div className="px-5 pb-5 pt-2 border-t border-border/15 space-y-4">
              {conviction.rationale && (
                <div>
                  <p className="text-[9px] font-semibold uppercase tracking-wider text-text-tertiary/50 mb-1.5">
                    Sizing Rationale
                  </p>
                  <p className="text-xs text-text-secondary leading-relaxed">
                    {conviction.rationale}
                  </p>
                </div>
              )}
              {conviction.conviction_justification && (
                <div>
                  <p className="text-[9px] font-semibold uppercase tracking-wider text-text-tertiary/50 mb-1.5">
                    Conviction Basis
                  </p>
                  <p className="text-xs text-text-secondary leading-relaxed">
                    {conviction.conviction_justification}
                  </p>
                </div>
              )}
              {signalBreakdown?.portfolio_action && (
                <div className="space-y-2">
                  <p className="text-[9px] font-semibold uppercase tracking-wider text-text-tertiary/50">
                    Portfolio Action Context
                  </p>
                  <div className="grid grid-cols-2 gap-1.5">
                    {([
                      ['Allocation Bias', signalBreakdown.portfolio_action.allocation_bias],
                      ['Conviction Scale', scalingLabel ?? `${signalBreakdown.portfolio_action.conviction_scaling_multiplier?.toFixed(2)}×`],
                      ['Risk Budget Impact', signalBreakdown.portfolio_action.risk_budget_impact],
                      ['Mandate Fit', signalBreakdown.portfolio_action.mandate_fit],
                    ] as [string, string | undefined | null][]).map(([k, v]) => v && (
                      <div key={k} className="rounded border border-border/30 px-2.5 py-1.5">
                        <p className="text-[8px] uppercase tracking-wider text-text-tertiary/40 mb-0.5">{k}</p>
                        <p className="text-[11px] text-text-secondary">{v}</p>
                      </div>
                    ))}
                  </div>
                  {signalBreakdown.portfolio_action.sizing_guidance && (
                    <p className="text-[11px] text-text-tertiary/60 italic border-l-2 border-border/30 pl-2.5 leading-relaxed">
                      {signalBreakdown.portfolio_action.sizing_guidance}
                    </p>
                  )}
                </div>
              )}
              {signalBreakdown?.noise_filter && (
                <div>
                  <p className="text-[9px] font-semibold uppercase tracking-wider text-text-tertiary/50 mb-1">
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
      </div>}
    </div>
  )
}
