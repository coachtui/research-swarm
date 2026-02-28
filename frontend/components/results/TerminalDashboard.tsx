'use client'

// Terminal-grade unified above-fold dashboard.
// Replaces CapitalSignalPanel + AsymmetryPanel + CapitalDeploymentPanel.
//
// ROW 1 — Signal Bar:  Rating · Ticker · Conviction  |  EV (dominant)  |  Price · FV · Implied
// ROW 2 — Asymmetry:   BASE · BULL · BEAR → PW Target strip
// ROW 3 — Deployment:  Rec Allocation (dominant %) + 4-cell secondary grid
//
// No new model logic — all values are derived from existing output fields.

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
  conviction: ConvictionPosition
  fairValueCalibration?: FairValueCalibration | null
  priceTargets?: PriceTargets | null
  signalBreakdown?: SignalBreakdown | null
  expectedReturnAnnualized?: number | null
}

// ── Helpers ────────────────────────────────────────────────────────────────────

function ratingColors(rating: string | null) {
  if (!rating) return { bg: 'bg-surface-elevated', border: 'border-border', text: 'text-text-secondary' }
  const r = rating.toUpperCase()
  if (['STRONG BUY', 'BUY', 'ACCUMULATE', 'BULLISH'].some(k => r.includes(k)))
    return { bg: 'bg-success/10', border: 'border-success/40', text: 'text-success' }
  if (['AVOID', 'SELL', 'REDUCE', 'BEARISH'].some(k => r.includes(k)))
    return { bg: 'bg-error/10', border: 'border-error/40', text: 'text-error' }
  return { bg: 'bg-warning/10', border: 'border-warning/40', text: 'text-warning' }
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

function SmallMetric({
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
      <span className="text-[9px] uppercase tracking-[0.13em] font-semibold text-text-tertiary/70">{label}</span>
      <span className={`text-base font-bold font-mono leading-none ${valueClass}`}>{value}</span>
      {sub && <span className="text-[9px] text-text-tertiary/50 font-mono">{sub}</span>}
    </div>
  )
}

function SecondaryBlotterCell({
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
      <span className="text-[9px] uppercase tracking-[0.13em] font-semibold text-text-tertiary/70">{label}</span>
      <span className={`text-2xl font-bold font-mono leading-none ${valueClass}`}>{value}</span>
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
  const { bg: rBg, border: rBorder, text: rText } = ratingColors(rating)
  const tier = convictionTier(conviction.conviction_level, conviction.recommended_pct, effectiveEvPct)
  const tierColor =
    tier === 'Strategic' ? 'text-primary' :
    tier === 'High' ? 'text-success' :
    tier === 'Moderate' ? 'text-warning' :
    'text-text-tertiary'

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
      topBorder: 'border-t-blue-500',
      labelColor: 'text-blue-400',
      assumptions: priceTargets.base_assumptions,
    },
    {
      label: 'BULL',
      weight: bullPct,
      target: priceTargets.bull_target,
      ret: bullRet,
      retColor: 'text-success',
      topBorder: 'border-t-success',
      labelColor: 'text-success',
      assumptions: priceTargets.bull_assumptions,
    },
    {
      label: 'BEAR',
      weight: bearPct,
      target: priceTargets.bear_target,
      ret: bearRet,
      retColor: 'text-error',
      topBorder: 'border-t-error',
      labelColor: 'text-error',
      assumptions: priceTargets.bear_assumptions,
    },
  ] : []

  // ── Row 3 calculations ─────────────────────────────────────────────────────
  const execPct = executionConstrainedPct(conviction, signalBreakdown)
  const posType = positionTypeLabel(conviction.conviction_level)
  const bindingType =
    execPct < conviction.recommended_pct * 0.95
      ? (execPct >= conviction.max_pct * 0.95 ? 'Cap-Bound' : 'Execution-Bound')
      : 'Within Guardrails'
  const noiseDefer = signalBreakdown?.noise_filter?.defer_sizing
  const noiseRegime = signalBreakdown?.noise_filter?.noise_regime
  const scalingLabel = signalBreakdown?.portfolio_action?.conviction_scaling_label ?? null

  const irr = expectedReturnAnnualized ?? null

  return (
    <div className="rounded-xl border border-border/70 bg-surface-elevated/60 overflow-hidden">

      {/* ═══════════════════════════════════════════════════════════════════
          ROW 1 — SIGNAL BAR
          Left: Rating · Ticker · Conviction Tier
          Center: EV (dominant) · PW Return · Confidence
          Right: Price · FV Mid · Implied ↑/↓
          ═══════════════════════════════════════════════════════════════════ */}
      <div className="grid grid-cols-1 sm:grid-cols-3 divide-y sm:divide-y-0 sm:divide-x divide-border/40 border-b border-border/50">

        {/* Left */}
        <div className="px-5 py-4 flex flex-col justify-center gap-2">
          <div className={`self-start px-3 py-1.5 rounded-lg border ${rBg} ${rBorder}`}>
            <span className={`text-xs font-bold tracking-widest uppercase ${rText}`}>
              {bias || rating || '—'}
            </span>
          </div>
          <div>
            <span className="text-base font-bold text-text-primary">{ticker}</span>
          </div>
          <div className={`self-start text-[10px] font-semibold px-1.5 py-0.5 rounded border ${tierColor} border-current/30`}>
            {tier} Conviction
          </div>
        </div>

        {/* Center — EV dominant */}
        <div className="px-5 py-4 flex flex-col justify-center gap-3 bg-surface/20">
          <div>
            <p className="text-[9px] uppercase tracking-[0.15em] font-semibold text-text-tertiary/70 mb-1">
              Expected Value
            </p>
            <p className={`text-5xl font-bold font-mono leading-none ${signColor(effectiveEvPct)}`}>
              {fmt(effectiveEvPct)}
            </p>
          </div>
          <div className="flex items-center gap-5">
            <SmallMetric
              label="PW Return"
              value={fmt(effectiveEvPct)}
              valueClass={signColor(effectiveEvPct)}
              sub="prob-weighted"
            />
            <div className="w-px h-6 bg-border/40" />
            <SmallMetric
              label="Confidence"
              value={rawConfidence !== null ? `${rawConfidence}` : '—'}
              valueClass={
                rawConfidence === null ? 'text-text-secondary' :
                rawConfidence >= 65 ? 'text-success' :
                rawConfidence >= 40 ? 'text-warning' : 'text-error'
              }
              sub={signalBreakdown?.confidence_integrity?.ev_confidence_level ?? '0–100'}
            />
            {irr !== null && (
              <>
                <div className="w-px h-6 bg-border/40" />
                <SmallMetric
                  label="Ann. IRR"
                  value={fmt(irr)}
                  valueClass={signColor(irr)}
                  sub="annualised"
                />
              </>
            )}
          </div>
        </div>

        {/* Right */}
        <div className="px-5 py-4 flex flex-col justify-center gap-3">
          <div>
            <p className="text-[9px] uppercase tracking-[0.13em] font-semibold text-text-tertiary/70 mb-1">
              Current Price
            </p>
            <p className="text-2xl font-bold font-mono text-text-primary leading-none">
              ${currentPrice.toFixed(2)}
            </p>
          </div>
          <div className="flex items-center gap-5">
            <SmallMetric
              label="FV Mid"
              value={fvMid ? `$${fvMid.toFixed(0)}` : '—'}
              valueClass="text-text-primary"
              sub={fairValueCalibration?.display_label ?? 'blended'}
            />
            {impliedUpside !== null && (
              <>
                <div className="w-px h-6 bg-border/40" />
                <SmallMetric
                  label="Implied ↑/↓"
                  value={
                    <span className="flex items-center gap-1">
                      {impliedUpside > 0
                        ? <TrendingUp className="h-3 w-3 flex-shrink-0" />
                        : <TrendingDown className="h-3 w-3 flex-shrink-0" />}
                      {fmt(impliedUpside)}
                    </span>
                  }
                  valueClass={signColor(impliedUpside)}
                  sub="vs FV mid"
                />
              </>
            )}
          </div>
        </div>
      </div>

      {/* ═══════════════════════════════════════════════════════════════════
          ROW 2 — ASYMMETRY SNAPSHOT
          3 scenario columns + PW Target strip below.
          Rendered only when price targets are available.
          ═══════════════════════════════════════════════════════════════════ */}
      {priceTargets && (
        <div className="border-b border-border/50">

          {/* 3-column scenario grid */}
          <div className="grid grid-cols-3 divide-x divide-border/40">
            {scenarioRows.map(row => (
              <div
                key={row.label}
                className={`px-5 py-4 border-t-4 ${row.topBorder}`}
              >
                <p className={`text-[9px] font-bold uppercase tracking-[0.14em] mb-1.5 ${row.labelColor}`}>
                  {row.label} CASE
                </p>
                <p className="text-3xl font-bold font-mono text-text-primary leading-none">
                  ${row.target.toFixed(0)}
                </p>
                <p className="text-sm font-semibold font-mono text-text-secondary mt-1">
                  {row.weight}%
                </p>
                <p className={`text-sm font-bold font-mono mt-0.5 ${row.retColor}`}>
                  {fmt(row.ret, true)}
                </p>
              </div>
            ))}
          </div>

          {/* PW Target — centered below */}
          <div className="flex flex-col sm:flex-row items-center justify-center gap-3 px-5 py-3 bg-surface/20">
            <div className="text-center">
              <p className="text-[9px] uppercase tracking-[0.13em] font-semibold text-text-tertiary/70">
                Probability-Weighted Target
              </p>
              <div className="flex items-baseline justify-center gap-2 mt-0.5">
                <span className="text-2xl font-bold font-mono text-text-primary">
                  ${pwTarget.toFixed(0)}
                </span>
                <span className={`text-base font-bold font-mono ${signColor(pwRet)}`}>
                  {fmt(pwRet, true)}
                </span>
                {stabilityMod < 1 && (
                  <span className="text-[10px] text-warning font-mono">
                    eff {fmt(pwRet * stabilityMod, true)}
                  </span>
                )}
              </div>
            </div>
            <div className="hidden sm:block w-px h-8 bg-border/30" />
            <div className="text-center">
              <p className="text-[9px] uppercase tracking-[0.13em] font-semibold text-text-tertiary/70">
                Downside Severity
              </p>
              <p className="text-2xl font-bold font-mono text-error mt-0.5">
                {downsideSeverity !== null ? fmt(downsideSeverity, true) : '—'}
              </p>
            </div>
            <div className="hidden sm:block w-px h-8 bg-border/30" />
            <div className="text-center">
              <p className="text-[9px] uppercase tracking-[0.13em] font-semibold text-text-tertiary/70">
                Upside Skew
              </p>
              <p className={`text-2xl font-bold font-mono mt-0.5 ${
                upsideSkewRatio === null ? 'text-text-secondary' :
                upsideSkewRatio >= 2 ? 'text-success' :
                upsideSkewRatio >= 1 ? 'text-warning' : 'text-error'
              }`}>
                {upsideSkewRatio !== null ? `${upsideSkewRatio.toFixed(1)}×` : '—'}
              </p>
            </div>
          </div>

          {/* Scenario assumptions toggle */}
          <div className="border-t border-border/30">
            <button
              onClick={() => setShowAssumptions(o => !o)}
              className="w-full flex items-center justify-between px-5 py-2 text-left hover:bg-surface-elevated/20 transition-colors"
            >
              <span className="text-[10px] text-text-tertiary/50 uppercase tracking-wider font-medium">
                Scenario Assumptions
              </span>
              {showAssumptions
                ? <ChevronUp className="h-3 w-3 text-text-tertiary/40" />
                : <ChevronDown className="h-3 w-3 text-text-tertiary/40" />}
            </button>
            {showAssumptions && (
              <div className="px-5 pb-4 pt-1 border-t border-border/20 space-y-3">
                {scenarioRows.map(row => (
                  <div key={row.label} className={`border-l-2 pl-3 ${
                    row.label === 'BASE' ? 'border-l-blue-500/60' :
                    row.label === 'BULL' ? 'border-l-success/60' : 'border-l-error/60'
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
          ROW 3 — CAPITAL DEPLOYMENT BLOTTER
          Left: Recommended Allocation % (dominant)
          Right: 2×2 secondary metric grid
          ═══════════════════════════════════════════════════════════════════ */}
      <div>
        {/* Header strip */}
        <div className="px-5 py-2.5 border-b border-border/30 flex items-center justify-between">
          <p className="text-[9px] uppercase tracking-[0.14em] font-semibold text-text-tertiary/60">
            Capital Deployment · {posType} Position
          </p>
          <span className={`text-[9px] font-semibold px-1.5 py-0.5 rounded border uppercase tracking-wider ${
            bindingType === 'Within Guardrails'
              ? 'text-success border-success/30 bg-success/5'
              : bindingType === 'Cap-Bound'
              ? 'text-warning border-warning/30 bg-warning/5'
              : 'text-text-tertiary border-border/40'
          }`}>
            {bindingType}
          </span>
        </div>

        {/* Allocation layout */}
        <div className="flex divide-x divide-border/40">

          {/* Dominant: Recommended % */}
          <div className="flex-[2] px-6 py-5 bg-primary/5 flex flex-col justify-center">
            <p className="text-[9px] uppercase tracking-[0.15em] font-semibold text-text-tertiary/60 mb-1.5">
              Recommended Allocation
            </p>
            <p className="text-6xl font-bold font-mono text-primary leading-none">
              {conviction.recommended_pct.toFixed(1)}%
            </p>
            {conviction.dollar_per_100k !== undefined && conviction.dollar_per_100k !== null && (
              <p className="text-[10px] text-text-tertiary/60 mt-2 font-mono">
                ${conviction.dollar_per_100k.toLocaleString()} per $100k portfolio
              </p>
            )}
          </div>

          {/* Secondary 2×2 grid */}
          <div className="flex-[3] grid grid-cols-2 divide-x divide-y divide-border/30">
            <SecondaryBlotterCell
              label="Max Risk"
              value={`${conviction.max_pct.toFixed(1)}%`}
            />
            <SecondaryBlotterCell
              label="Exec-Constrained"
              value={`${execPct.toFixed(1)}%`}
              valueClass="text-text-primary"
            />
            <SecondaryBlotterCell
              label="Asymmetry Ratio"
              value={
                upsideSkewRatio !== null
                  ? `${upsideSkewRatio.toFixed(1)}×`
                  : '—'
              }
              valueClass={
                upsideSkewRatio === null ? 'text-text-secondary' :
                upsideSkewRatio >= 2 ? 'text-success' :
                upsideSkewRatio >= 1 ? 'text-warning' : 'text-error'
              }
            />
            <SecondaryBlotterCell
              label="Downside Severity"
              value={downsideSeverity !== null ? fmt(downsideSeverity, true) : '—'}
              valueClass="text-error"
            />
          </div>
        </div>

        {/* Noise regime warning */}
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

        {/* Deployment Logic toggle */}
        <div className="border-t border-border/30">
          <button
            onClick={() => setShowDeploymentLogic(o => !o)}
            className="w-full flex items-center justify-between px-5 py-2 text-left hover:bg-surface-elevated/20 transition-colors"
          >
            <span className="text-[10px] text-text-tertiary/50 uppercase tracking-wider font-medium">
              Deployment Logic
            </span>
            {showDeploymentLogic
              ? <ChevronUp className="h-3 w-3 text-text-tertiary/40" />
              : <ChevronDown className="h-3 w-3 text-text-tertiary/40" />}
          </button>
          {showDeploymentLogic && (
            <div className="px-5 pb-5 pt-2 border-t border-border/20 space-y-4">
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
              {signalBreakdown?.portfolio_action && (
                <div className="space-y-2">
                  <p className="text-[9px] font-semibold uppercase tracking-wider text-text-tertiary/60">
                    Portfolio Action Context
                  </p>
                  <div className="grid grid-cols-2 gap-1.5">
                    {([
                      ['Allocation Bias', signalBreakdown.portfolio_action.allocation_bias],
                      ['Conviction Scale', scalingLabel ?? `${signalBreakdown.portfolio_action.conviction_scaling_multiplier?.toFixed(2)}×`],
                      ['Risk Budget Impact', signalBreakdown.portfolio_action.risk_budget_impact],
                      ['Mandate Fit', signalBreakdown.portfolio_action.mandate_fit],
                    ] as [string, string | undefined | null][]).map(([k, v]) => v && (
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
    </div>
  )
}
