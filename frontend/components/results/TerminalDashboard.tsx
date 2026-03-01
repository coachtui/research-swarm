'use client'

// DVRG Research-First Architecture — Institutional Equity Research Format.
//
// Reading order: Thesis → Valuation Work → Risk → Capital → Conclusion
// Allocation is the OUTCOME of research, not the headline.
//
// Section 1: Investment Thesis        (always visible, no metrics)
// Section 2: Valuation & Scenarios    (always visible)
// Section 3: Risk Framework           (always visible)
// Section 4: Capital Allocation       (always visible, subordinate)
// Section 5: Executive Conclusion     (always visible)
// Engine Diagnostics: collapsed accordion at bottom
//
// Presentation-layer refactor only. Zero calculation changes.

import { useState } from 'react'
import type { ReactNode } from 'react'
import { ChevronDown, ChevronUp } from 'lucide-react'
import type { ConvictionPosition, SignalBreakdown, FairValueCalibration } from '@/types/api'

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

// ── Tier types ─────────────────────────────────────────────────────────────────

type EdgeTier = 'Avoid' | 'Weak Edge' | 'Moderate Edge' | 'Strong Edge' | 'Dislocation'
type RiskTier = 'Contained' | 'Moderate' | 'Elevated' | 'High'
type DirectionLabel = 'Avoid' | 'Watch' | 'Accumulate' | 'Overweight' | 'Conviction'

// ── Tier classifiers (unchanged logic) ────────────────────────────────────────

function classifyEdge(evPct: number | null): EdgeTier {
  if (evPct === null) return 'Weak Edge'
  if (evPct < 0) return 'Avoid'
  if (evPct < 1) return 'Weak Edge'
  if (evPct < 3) return 'Moderate Edge'
  if (evPct < 6) return 'Strong Edge'
  return 'Dislocation'
}

function classifyRisk(bearRet: number | null, stopProb: number | null): RiskTier {
  const downside = bearRet ?? 0
  const stop = stopProb ?? 0
  if (downside < -15 || stop > 35) return 'High'
  if (downside < -8 || stop > 20) return 'Elevated'
  if (downside < -4 || stop > 10) return 'Moderate'
  return 'Contained'
}

function deriveDirectionLabel(edge: EdgeTier, risk: RiskTier): DirectionLabel {
  if (edge === 'Avoid') return 'Avoid'
  if (edge === 'Weak Edge' || risk === 'High') return 'Watch'
  if (risk === 'Elevated') return edge === 'Moderate Edge' ? 'Watch' : 'Accumulate'
  if (edge === 'Moderate Edge') return 'Accumulate'
  if (edge === 'Strong Edge') return 'Overweight'
  return 'Conviction'
}

// Deterministic thesis sentence — lookup matrix from edge + risk + position type (unchanged).
function generateThesisCompression(
  edge: EdgeTier,
  risk: RiskTier,
  positionType: string,
  skewRatio: number | null,
): string {
  const skewNote = skewRatio !== null && skewRatio >= 1.5 ? ' with favorable asymmetry' : ''
  if (edge === 'Avoid') {
    return risk === 'High'
      ? 'Negative expected value combined with high downside risk; avoid new exposure.'
      : 'Negative expected value — no statistical basis for new capital deployment.'
  }
  if (edge === 'Dislocation' && risk === 'Contained') {
    return 'Rare statistical dislocation with contained downside; elevated conviction warrants overweight consideration.'
  }
  if (edge === 'Dislocation') {
    return `Strong dislocation signal${skewNote}; risk profile requires active monitoring despite high edge.`
  }
  if (edge === 'Strong Edge' && risk === 'Contained') {
    return `Strong statistical edge with contained downside${skewNote}; favorable asymmetry supports ${positionType.toLowerCase()} allocation.`
  }
  if (edge === 'Strong Edge' && risk === 'Moderate') {
    return 'Strong edge offset by moderate risk; asymmetry justifies tactical overweight with active monitoring.'
  }
  if (edge === 'Strong Edge') {
    return 'Statistically strong setup; elevated structural volatility warrants scaled entry rather than full deployment.'
  }
  if (edge === 'Moderate Edge' && risk === 'Contained') {
    return `Moderate expected value with contained downside; appropriate as ${positionType.toLowerCase()} exposure.`
  }
  if (edge === 'Moderate Edge' && risk === 'Moderate') {
    return 'Moderate expected value with elevated structural volatility. Appropriate as small tactical exposure.'
  }
  if (edge === 'Moderate Edge') {
    return 'Moderate expected value; marginal edge relative to risk profile — defer full sizing pending regime confirmation.'
  }
  if (risk === 'High') {
    return 'Weak statistical edge with high downside risk; risk/reward does not justify new capital.'
  }
  return 'Weak statistical edge; monitor for setup improvement before deploying capital.'
}

// Deterministic variant view — what the market may be underweighting or mispricing.
function generateVariantView(
  edge: EdgeTier,
  evPct: number | null,
  fvMid: number | null,
  currentPrice: number,
): string | null {
  if (evPct === null) return null
  const fvNote =
    fvMid && currentPrice > 0
      ? ` Intrinsic value anchor of $${fvMid.toFixed(0)} implies ${evPct > 0 ? 'fundamental undervaluation' : 'overvaluation'} versus current price.`
      : ''
  if (edge === 'Avoid') {
    return 'Market consensus appears broadly aligned with fundamental deterioration. No identifiable mispricing creates actionable upside at current levels.'
  }
  if (edge === 'Dislocation') {
    return `Statistical analysis identifies significant divergence between market pricing and probability-weighted intrinsic value.${fvNote} The market may be overweighting near-term execution risk or underweighting a structural re-rating catalyst embedded in the base case.`
  }
  if (edge === 'Strong Edge') {
    const evStr = evPct > 0 ? `+${evPct.toFixed(1)}%` : `${evPct.toFixed(1)}%`
    return `Expected value of ${evStr} signals the market may be underweighting the base case probability or discounting near-term catalysts prematurely.${fvNote}`
  }
  if (edge === 'Moderate Edge') {
    return `Moderate expected value suggests partial pricing of fundamentals. The variant view is that execution on existing catalysts could close the remaining gap more rapidly than consensus assumes.${fvNote}`
  }
  return 'Limited statistical edge suggests market is broadly efficient in pricing this setup. Monitor for fundamental inflection that may reopen opportunity.'
}

// Deterministic invalidation conditions derived from scenario data.
function generateInvalidationConditions(
  bearTarget: number | null,
  stopProb: number | null,
  evPct: number | null,
  currentPrice: number,
): string[] {
  const conditions: string[] = []
  if (bearTarget && currentPrice > 0) {
    conditions.push(
      `Price erosion to $${bearTarget.toFixed(0)} or below signals bear case realization and materially destroys expected value`,
    )
  }
  if (stopProb !== null) {
    const threshold = stopProb > 20 ? Math.round(stopProb * 0.8) : 25
    conditions.push(
      `Stop probability rising above ${threshold}% would indicate deteriorating technical structure and adverse exit probability`,
    )
  }
  conditions.push(
    'Fundamental deterioration shifting base case inputs to bear scenario assumptions — negative earnings revision cycle or guidance withdrawal',
  )
  if (evPct !== null && evPct > 0) {
    conditions.push(
      'Macro regime shift compressing multiple expansion assumptions embedded in base and bull scenario pricing',
    )
  }
  return conditions
}

// Deterministic executive conclusion — 2–3 sentence synthesis of the full report.
function generateExecutiveConclusion(
  edge: EdgeTier,
  risk: RiskTier,
  direction: DirectionLabel,
  execPct: number,
  posType: string | null,
  stopProb: number | null,
): string {
  const quality =
    edge === 'Dislocation'   ? 'exceptional' :
    edge === 'Strong Edge'   ? 'high-quality' :
    edge === 'Moderate Edge' ? 'moderate' : 'weak'
  const riskDesc =
    risk === 'Contained' ? 'well-contained downside' :
    risk === 'Moderate'  ? 'manageable risk structure' :
    risk === 'Elevated'  ? 'elevated structural risk requiring active monitoring' :
    'high downside risk constraining deployment'
  const capitalLine =
    direction === 'Avoid' ? 'No new capital deployment warranted at current levels.' :
    direction === 'Watch' ? 'Monitor for setup improvement before committing capital.' :
    `${posType ?? 'Satellite'} allocation of ${execPct.toFixed(1)}% reflects policy-constrained deployment against this setup.`
  const monitorLine =
    stopProb !== null && stopProb > 20
      ? 'Elevated stop probability warrants active position monitoring.'
      : 'Monitor for fundamental inflection or technical confirmation supporting thesis reconfirmation.'
  return `Expected value quality is ${quality} against ${riskDesc}. ${capitalLine} ${monitorLine}`
}

// Capital Efficiency = PWE ÷ |bear downside| — risk-adjusted edge scalar (unchanged).
function capitalEfficiency(evPct: number | null, bearRet: number | null): number | null {
  if (evPct === null || bearRet === null || Math.abs(bearRet) < 0.01) return null
  return evPct / Math.abs(bearRet)
}

// ── Color maps (unchanged) ─────────────────────────────────────────────────────

function edgeTierStyle(tier: EdgeTier): { text: string; border: string; bg: string } {
  switch (tier) {
    case 'Dislocation':   return { text: 'text-primary',  border: 'border-t-primary/40',  bg: 'bg-primary/5'  }
    case 'Strong Edge':   return { text: 'text-success',  border: 'border-t-success/40',  bg: 'bg-success/5'  }
    case 'Moderate Edge': return { text: 'text-success',  border: 'border-t-success/25',  bg: 'bg-success/3'  }
    case 'Weak Edge':     return { text: 'text-warning',  border: 'border-t-warning/35',  bg: 'bg-warning/5'  }
    case 'Avoid':         return { text: 'text-error',    border: 'border-t-error/35',    bg: 'bg-error/5'    }
  }
}

// Risk: no bg unless catastrophic (High). Red reserved for >15% downside or >35% stop prob.
function riskTierStyle(tier: RiskTier): { text: string; border: string; bg: string } {
  switch (tier) {
    case 'Contained': return { text: 'text-text-secondary', border: 'border-t-border/30',  bg: ''           }
    case 'Moderate':  return { text: 'text-warning/70',     border: 'border-t-warning/20', bg: ''           }
    case 'Elevated':  return { text: 'text-warning',        border: 'border-t-warning/30', bg: ''           }
    case 'High':      return { text: 'text-error',          border: 'border-t-error/35',   bg: 'bg-error/5' }
  }
}

// Direction — text color only.
function directionTextColor(label: DirectionLabel): string {
  switch (label) {
    case 'Conviction': return 'text-primary'
    case 'Overweight': return 'text-success'
    case 'Accumulate': return 'text-success/80'
    case 'Watch':      return 'text-warning'
    case 'Avoid':      return 'text-error'
  }
}

// Deterministic one-liner explaining why the direction was assigned (unchanged).
function directionExplanation(label: DirectionLabel): string {
  switch (label) {
    case 'Conviction': return 'Rare dislocation event — elevated conviction'
    case 'Overweight': return 'Strong statistical edge confirmed — favorable asymmetry'
    case 'Accumulate': return 'Positive setup — conditions support gradual deployment'
    case 'Watch':      return 'Edge below overweight threshold — monitor for improvement'
    case 'Avoid':      return 'Negative expected value — no statistical basis for new capital'
  }
}

function efficiencyLabel(score: number): string {
  if (score >= 0.6) return 'Strong Risk-Adj Edge'
  if (score >= 0.35) return 'Moderate Risk-Adj Edge'
  if (score >= 0.15) return 'Weak Risk-Adj Edge'
  return 'Poor Risk-Adj Edge'
}

function efficiencyColor(score: number): string {
  if (score >= 0.6) return 'text-success'
  if (score >= 0.35) return 'text-warning'
  return 'text-error'
}

// ── Math helpers (unchanged) ───────────────────────────────────────────────────

function signColor(v: number | null) {
  if (v === null) return 'text-text-secondary'
  return v > 0 ? 'text-success' : v < 0 ? 'text-error' : 'text-text-secondary'
}

function fmt(v: number | null, sign = true, decimals = 1): string {
  if (v === null || isNaN(v)) return '—'
  return `${sign && v > 0 ? '+' : ''}${v.toFixed(decimals)}%`
}

function pct(target: number, current: number): number {
  return ((target - current) / current) * 100
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

function positionTypeLabel(convictionLevel: string): string {
  const l = convictionLevel.toLowerCase()
  if (l === 'high') return 'Core'
  if (l === 'medium' || l === 'moderate') return 'Satellite'
  return 'Tactical'
}

// ── Accordion wrapper ──────────────────────────────────────────────────────────

function Accordion({
  label,
  sublabel,
  badge,
  defaultOpen = false,
  children,
}: {
  label: string
  sublabel?: string
  badge?: string
  defaultOpen?: boolean
  children: ReactNode
}) {
  const [open, setOpen] = useState(defaultOpen)
  return (
    <div className="border-t border-border/30">
      <button
        onClick={() => setOpen(o => !o)}
        className="w-full flex items-center justify-between px-5 py-2.5 text-left hover:bg-surface-elevated/15 transition-colors"
      >
        <div className="flex items-center gap-2">
          <span className="text-[11px] font-semibold text-text-secondary uppercase tracking-wider">
            {label}
          </span>
          {badge && (
            <span className="text-[8px] text-text-tertiary/35 border border-border/25 rounded px-1.5 py-0.5 uppercase tracking-wider">
              {badge}
            </span>
          )}
          {sublabel && (
            <span className="text-[9px] text-text-tertiary/35 hidden sm:inline">{sublabel}</span>
          )}
        </div>
        {open
          ? <ChevronUp className="h-3.5 w-3.5 text-text-tertiary/35 flex-shrink-0" />
          : <ChevronDown className="h-3.5 w-3.5 text-text-tertiary/35 flex-shrink-0" />}
      </button>
      {open && (
        <div className="border-t border-border/20 px-5 py-4 space-y-4">
          {children}
        </div>
      )}
    </div>
  )
}

// ── Section label ──────────────────────────────────────────────────────────────

function SectionLabel({ children }: { children: ReactNode }) {
  return (
    <p className="text-[9px] uppercase tracking-[0.14em] font-semibold text-text-tertiary/45">
      {children}
    </p>
  )
}

// ── Main ───────────────────────────────────────────────────────────────────────

export function TerminalDashboard({
  ticker,
  currentPrice,
  conviction,
  fairValueCalibration,
  priceTargets,
  signalBreakdown,
  expectedReturnAnnualized,
}: TerminalDashboardProps) {

  // ── Calculations (unchanged logic) ───────────────────────────────────────

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

  let bearRet: number | null = null
  let baseRet = 0, bullRet = 0, pwTarget = 0, pwRet = 0
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
    upsideSkewRatio = Math.abs(bearRet) > 0.01 ? bullRet / Math.abs(bearRet) : null
  }

  const stopProb = signalBreakdown?.stop_probability?.effective_stop_probability_pct ?? null
  const irr = expectedReturnAnnualized ?? null

  // ── Tier classifications ──────────────────────────────────────────────────

  const edgeTier  = classifyEdge(effectiveEvPct)
  const riskTier  = classifyRisk(bearRet, stopProb)
  const direction = deriveDirectionLabel(edgeTier, riskTier)
  const edgeSty   = edgeTierStyle(edgeTier)
  const riskSty   = riskTierStyle(riskTier)
  const dirColor  = directionTextColor(direction)
  const effScore  = capitalEfficiency(effectiveEvPct, bearRet)

  // ── Capital instruction ───────────────────────────────────────────────────

  const execPct  = executionConstrainedPct(conviction, signalBreakdown)
  const posType  = conviction ? positionTypeLabel(conviction.conviction_level) : null
  const bindType = conviction
    ? execPct >= conviction.max_pct * 0.95
      ? 'Cap-Bound'
      : execPct < conviction.recommended_pct * 0.95
        ? 'Exec-Bound'
        : 'Within Guardrails'
    : null

  // ── Narrative generation ──────────────────────────────────────────────────

  const thesis = generateThesisCompression(edgeTier, riskTier, posType ?? 'Satellite', upsideSkewRatio)
  const variantView = generateVariantView(edgeTier, effectiveEvPct, fvMid, currentPrice)
  const invalidationConditions = generateInvalidationConditions(
    priceTargets?.bear_target ?? null,
    stopProb,
    effectiveEvPct,
    currentPrice,
  )
  const executiveConclusion = generateExecutiveConclusion(
    edgeTier, riskTier, direction, execPct, posType, stopProb,
  )

  // ── Scenario rows ─────────────────────────────────────────────────────────

  const scenarioRows = priceTargets ? [
    {
      label: 'BASE', weight: basePct,
      target: priceTargets.base_target, ret: baseRet,
      retColor: baseRet >= 0 ? 'text-success' : 'text-error',
      accent: 'border-l-blue-500/60', labelColor: 'text-blue-400',
      assumptions: priceTargets.base_assumptions,
    },
    {
      label: 'BULL', weight: bullPct,
      target: priceTargets.bull_target, ret: bullRet,
      retColor: 'text-success',
      accent: 'border-l-emerald-500/60', labelColor: 'text-emerald-400',
      assumptions: priceTargets.bull_assumptions,
    },
    {
      label: 'BEAR', weight: bearPct,
      target: priceTargets.bear_target, ret: bearRet,
      retColor: 'text-error',
      accent: 'border-l-red-500/60', labelColor: 'text-red-400',
      assumptions: priceTargets.bear_assumptions,
    },
  ] : []

  const noiseDefer   = signalBreakdown?.noise_filter?.defer_sizing
  const noiseRegime  = signalBreakdown?.noise_filter?.noise_regime
  const scalingLabel = signalBreakdown?.portfolio_action?.conviction_scaling_label ?? null

  return (
    <div className="rounded-xl border border-border/40 overflow-hidden">

      {/* ════════════════════════════════════════════════════════════════════
          HEADER — Ticker · Edge classification · Direction label
          Allocation is NOT shown here. It appears only in Section 4.
          ════════════════════════════════════════════════════════════════════ */}
      <div className={`px-5 py-3.5 flex items-center justify-between border-b border-border/30 border-t-2 ${edgeSty.border} ${edgeSty.bg}`}>
        <div className="flex items-center gap-2.5 flex-wrap">
          <span className="text-2xl font-bold font-mono text-text-primary leading-none tracking-tight">
            {ticker}
          </span>
          <span className={`text-[9px] font-bold uppercase tracking-wider px-1.5 py-0.5 rounded border border-current/20 ${edgeSty.text}`}>
            {edgeTier}
          </span>
          <span className="text-text-tertiary/25 text-[10px]">·</span>
          <span className={`text-[10px] font-bold uppercase tracking-wide ${dirColor}`}>
            {direction}
          </span>
        </div>
        {rawConfidence !== null && (
          <span className={`text-[10px] font-semibold tabular-nums ${
            rawConfidence >= 65 ? 'text-text-tertiary/55' :
            rawConfidence >= 40 ? 'text-warning/60'       : 'text-error/60'
          }`}>
            {rawConfidence}% confidence
          </span>
        )}
      </div>

      {/* ════════════════════════════════════════════════════════════════════
          SECTION 1 — INVESTMENT THESIS
          Narrative first. No metrics in this section.
          Core Thesis → Variant View → Invalidation Conditions
          ════════════════════════════════════════════════════════════════════ */}
      <div className="px-5 py-5 space-y-4 border-b border-border/25">

        {/* A. Core Thesis */}
        <div className="space-y-2">
          <SectionLabel>Core Thesis</SectionLabel>
          <p className="text-sm text-text-secondary leading-relaxed">
            {thesis}
          </p>
          <div className="flex items-center gap-2 flex-wrap">
            <span className="text-[9px] uppercase tracking-widest text-text-tertiary/55 font-medium">Status</span>
            <span className={`text-xs font-bold uppercase tracking-wider ${dirColor}`}>
              {direction}
            </span>
            <span className="text-text-tertiary/40 text-xs">·</span>
            <span className="text-xs text-text-secondary/75">
              {directionExplanation(direction)}
            </span>
          </div>
        </div>

        {/* B. Variant View */}
        {variantView && (
          <div className="space-y-1">
            <SectionLabel>Variant View</SectionLabel>
            <p className="text-[11px] text-text-tertiary/70 leading-relaxed">
              {variantView}
            </p>
          </div>
        )}

        {/* C. Invalidation Conditions */}
        <div className="space-y-1">
          <SectionLabel>Invalidation Conditions</SectionLabel>
          <ul className="space-y-1.5 mt-1">
            {invalidationConditions.map((condition, i) => (
              <li key={i} className="flex items-start gap-2">
                <span className="text-error/40 text-[10px] mt-0.5 flex-shrink-0">—</span>
                <span className="text-[10px] text-text-tertiary/60 leading-snug">{condition}</span>
              </li>
            ))}
          </ul>
        </div>
      </div>

      {/* ════════════════════════════════════════════════════════════════════
          SECTION 2 — VALUATION & SCENARIO FRAMEWORK
          Intrinsic anchor → Scenario table → PWE formula
          PWE % shown here, not in the header.
          ════════════════════════════════════════════════════════════════════ */}
      <div className="px-5 py-5 space-y-4 border-b border-border/25">

        {/* Section header with PWE right-aligned */}
        <div className="flex items-start justify-between gap-4">
          <SectionLabel>Valuation &amp; Scenario Framework</SectionLabel>
          {effectiveEvPct !== null && (
            <div className="text-right flex-shrink-0">
              <p className="text-[8px] uppercase tracking-wider text-text-tertiary/35 mb-0.5">
                Prob-Weighted Edge
              </p>
              <p className={`text-2xl font-bold font-mono leading-none ${edgeSty.text}`}>
                {fmt(effectiveEvPct)}
              </p>
            </div>
          )}
        </div>

        {/* Intrinsic Value Anchor */}
        {(currentPrice > 0 || fvMid || pwTarget > 0 || irr !== null) && (
          <div>
            <p className="text-[9px] uppercase tracking-wider text-text-tertiary/40 mb-2">
              Intrinsic Value Anchor
            </p>
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
              {currentPrice > 0 && (
                <div className="rounded border border-border/25 px-2.5 py-2">
                  <p className="text-[8px] uppercase tracking-wider text-text-tertiary/35 mb-0.5">Market Price</p>
                  <p className="text-sm font-bold font-mono text-text-secondary">
                    ${currentPrice.toFixed(2)}
                  </p>
                </div>
              )}
              {fvMid && (
                <div className="rounded border border-border/25 px-2.5 py-2">
                  <p className="text-[8px] uppercase tracking-wider text-text-tertiary/35 mb-0.5">Blended Fair Value</p>
                  <p className="text-sm font-bold font-mono text-text-secondary">
                    ${fvMid.toFixed(0)}
                    {impliedUpside !== null && (
                      <span className={`ml-1.5 text-xs font-normal ${signColor(impliedUpside)} opacity-70`}>
                        {fmt(impliedUpside, true)}
                      </span>
                    )}
                  </p>
                </div>
              )}
              {pwTarget > 0 && (
                <div className="rounded border border-border/25 px-2.5 py-2">
                  <p className="text-[8px] uppercase tracking-wider text-text-tertiary/35 mb-0.5">PW Target</p>
                  <p className={`text-sm font-bold font-mono ${signColor(pwRet)} opacity-80`}>
                    ${pwTarget.toFixed(0)}
                  </p>
                </div>
              )}
              {irr !== null && (
                <div className="rounded border border-border/25 px-2.5 py-2">
                  <p className="text-[8px] uppercase tracking-wider text-text-tertiary/35 mb-0.5">Ann. IRR</p>
                  <p className={`text-sm font-bold font-mono ${signColor(irr)} opacity-80`}>
                    {fmt(irr)}
                  </p>
                </div>
              )}
            </div>
          </div>
        )}

        {/* Scenario construction table */}
        {scenarioRows.length > 0 && (
          <div>
            <p className="text-[9px] uppercase tracking-wider text-text-tertiary/40 mb-2">
              Scenario Construction
            </p>
            <div className="space-y-2">
              {scenarioRows.map(row => (
                <div
                  key={row.label}
                  className={`pl-3 py-2.5 pr-3 rounded-lg border border-border/25 border-l-2 ${row.accent} bg-surface/20`}
                >
                  <div className="flex items-center justify-between mb-1">
                    <span className={`text-[9px] font-bold uppercase tracking-wider ${row.labelColor}`}>
                      {row.label} · {row.weight}%
                    </span>
                    <div className="flex items-baseline gap-2">
                      <span className="text-sm font-bold font-mono text-text-primary">
                        ${row.target.toFixed(0)}
                      </span>
                      <span className={`text-xs font-semibold font-mono ${row.retColor}`}>
                        {fmt(row.ret, true)}
                      </span>
                    </div>
                  </div>
                  <p className="text-[10px] text-text-tertiary/55 leading-relaxed">
                    {row.assumptions}
                  </p>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* PWE formula */}
        {effectiveEvPct !== null && (
          <div className="rounded border border-border/20 bg-surface/10 px-3.5 py-2.5">
            <p className="text-[8px] uppercase tracking-wider text-text-tertiary/35 mb-1.5">
              PWE = Σ (Probability × Return)
            </p>
            <div className="flex items-baseline gap-3 flex-wrap">
              <span className={`text-xl font-bold font-mono ${edgeSty.text}`}>
                {fmt(effectiveEvPct)}
              </span>
              {stabilityMod < 1 && (
                <span className="text-[9px] text-warning/60">
                  Stability-adjusted from {fmt(evPct)}
                </span>
              )}
              {effScore !== null && (
                <span className={`text-[9px] font-medium ${efficiencyColor(effScore)} opacity-70`}>
                  · Cap. Eff. {effScore.toFixed(2)} · {efficiencyLabel(effScore)}
                </span>
              )}
            </div>
          </div>
        )}
      </div>

      {/* ════════════════════════════════════════════════════════════════════
          SECTION 3 — RISK FRAMEWORK
          Downside analysis → Asymmetry → Model stability & confidence
          Red bg only if High (downside >15% OR stopProb >35%).
          ════════════════════════════════════════════════════════════════════ */}
      <div className={`px-5 py-5 space-y-4 border-b border-border/25${riskSty.bg ? ` ${riskSty.bg}` : ''}`}>

        {/* Section header with risk tier right-aligned */}
        <div className="flex items-center justify-between">
          <SectionLabel>Risk Framework</SectionLabel>
          <span className={`text-[10px] font-bold uppercase tracking-wider ${riskSty.text}`}>
            {riskTier}
          </span>
        </div>

        {/* A. Downside Case Analysis */}
        {priceTargets && (
          <div>
            <p className="text-[9px] uppercase tracking-wider text-text-tertiary/40 mb-2">
              Downside Case Analysis
            </p>
            <div className="grid grid-cols-3 gap-2">
              {bearRet !== null && (
                <div className="rounded border border-border/25 px-2.5 py-2">
                  <p className="text-[8px] uppercase tracking-wider text-text-tertiary/35 mb-0.5">Bear Downside</p>
                  <p className={`text-sm font-bold font-mono ${
                    riskTier === 'High' ? 'text-error' : 'text-text-secondary'
                  }`}>
                    {fmt(bearRet, true)}
                  </p>
                  <p className="text-[8px] text-text-tertiary/40 mt-0.5">
                    {riskTier === 'High' || riskTier === 'Elevated' ? 'Structural risk' : 'Cyclical risk'}
                  </p>
                </div>
              )}
              {bearPct > 0 && (
                <div className="rounded border border-border/25 px-2.5 py-2">
                  <p className="text-[8px] uppercase tracking-wider text-text-tertiary/35 mb-0.5">Bear Probability</p>
                  <p className="text-sm font-bold font-mono text-text-secondary">{bearPct}%</p>
                  <p className="text-[8px] text-text-tertiary/40 mt-0.5">Scenario weight</p>
                </div>
              )}
              {stopProb !== null && (
                <div className="rounded border border-border/25 px-2.5 py-2">
                  <p className="text-[8px] uppercase tracking-wider text-text-tertiary/35 mb-0.5">Stop Probability</p>
                  <p className={`text-sm font-bold font-mono ${
                    stopProb > 30 ? 'text-error' : stopProb > 15 ? 'text-warning' : 'text-text-secondary'
                  }`}>
                    {stopProb.toFixed(0)}%
                  </p>
                  <p className="text-[8px] text-text-tertiary/40 mt-0.5">Adverse exit prob.</p>
                </div>
              )}
            </div>
          </div>
        )}

        {/* B. Asymmetry Profile */}
        {upsideSkewRatio !== null && (
          <div>
            <p className="text-[9px] uppercase tracking-wider text-text-tertiary/40 mb-1.5">
              Asymmetry Profile
            </p>
            <div className="flex items-baseline gap-2.5">
              <span className={`text-2xl font-bold font-mono ${
                upsideSkewRatio >= 2 ? 'text-success' :
                upsideSkewRatio >= 1 ? 'text-warning' : 'text-error'
              }`}>
                {upsideSkewRatio.toFixed(1)}×
              </span>
              <span className="text-[10px] text-text-tertiary/55">skew ratio</span>
            </div>
            <p className="text-[10px] text-text-tertiary/60 mt-1 leading-snug">
              {upsideSkewRatio >= 1
                ? `Upside outweighs downside by ${((upsideSkewRatio - 1) * 100).toFixed(0)}%. Risk-adjusted entry favors deployment.`
                : 'Downside magnitude exceeds upside potential. Asymmetry does not favor new capital.'}
            </p>
          </div>
        )}

        {/* C. Model Stability & Confidence */}
        {(rawConfidence !== null || stabilityMod < 1) && (
          <div>
            <p className="text-[9px] uppercase tracking-wider text-text-tertiary/40 mb-1.5">
              Model Stability &amp; Confidence
            </p>
            <div className="space-y-1">
              {rawConfidence !== null && (
                <p className="text-[10px] text-text-tertiary/60">
                  Signal confidence:{' '}
                  <span className={`font-semibold ${
                    rawConfidence >= 65 ? 'text-success/70' :
                    rawConfidence >= 40 ? 'text-warning/70' : 'text-error/70'
                  }`}>
                    {rawConfidence}%
                  </span>
                  <span className="text-text-tertiary/40"> effective integrity</span>
                </p>
              )}
              {stabilityMod < 1 && (
                <p className="text-[10px] text-warning/60">
                  Stability modifier: {(stabilityMod * 100).toFixed(0)}% — model inputs show elevated sensitivity
                </p>
              )}
              {rawConfidence !== null && (
                <p className="text-[9px] text-text-tertiary/45 italic mt-0.5">
                  {rawConfidence >= 65
                    ? 'Valuation inputs exhibit stable convergence across signal sources.'
                    : rawConfidence >= 40
                    ? 'Moderate signal agreement — core setup intact but monitor for divergence.'
                    : 'Low signal confidence — elevated sensitivity to input assumptions. Size conservatively.'}
                </p>
              )}
            </div>
          </div>
        )}
      </div>

      {/* ════════════════════════════════════════════════════════════════════
          SECTION 4 — CAPITAL ALLOCATION FRAMEWORK
          Policy-derived → Execution adjustments → Final allocation.
          Allocation is the conclusion of the research, not the starting point.
          Only rendered when conviction data is available.
          ════════════════════════════════════════════════════════════════════ */}
      {conviction && (
        <div className="px-5 py-5 space-y-4 border-b border-border/25">
          <SectionLabel>Capital Allocation Framework</SectionLabel>

          {/* Policy-Based Allocation */}
          <div>
            <p className="text-[9px] uppercase tracking-wider text-text-tertiary/40 mb-1.5">
              Policy-Based Allocation
            </p>
            <p className="text-[10px] text-text-tertiary/60 leading-relaxed">
              Allocation derived from: expected value ({fmt(effectiveEvPct)}),
              downside severity ({bearRet !== null ? fmt(bearRet, true) : '—'}),
              and model confidence ({rawConfidence !== null ? `${rawConfidence}%` : '—'}).
              {noiseDefer && (
                <span className="text-warning/70">
                  {' '}Noise regime deferral applied — full sizing withheld pending regime confirmation.
                </span>
              )}
            </p>
            {conviction.rationale && (
              <p className="text-[10px] text-text-tertiary/55 italic mt-2 border-l-2 border-border/30 pl-2.5 leading-relaxed">
                {conviction.rationale}
              </p>
            )}
          </div>

          {/* Execution Adjustments */}
          <div>
            <p className="text-[9px] uppercase tracking-wider text-text-tertiary/40 mb-1.5">
              Execution Adjustments
            </p>
            <div className="grid grid-cols-3 gap-1.5 mb-2">
              {[
                { label: 'Recommended',     value: `${conviction.recommended_pct.toFixed(1)}%` },
                { label: 'Exec-Constrained', value: `${execPct.toFixed(1)}%` },
                { label: 'Policy Cap',       value: `${conviction.max_pct.toFixed(1)}%` },
              ].map(({ label, value }) => (
                <div key={label} className="rounded border border-border/25 px-2.5 py-2">
                  <p className="text-[8px] uppercase tracking-wider text-text-tertiary/35 mb-0.5">{label}</p>
                  <p className="text-sm font-bold font-mono text-text-secondary">{value}</p>
                </div>
              ))}
            </div>
            <p className="text-[9px] text-text-tertiary/40 leading-snug">
              Final Weight = MIN(Execution Weight, Policy Cap).{' '}
              Constraint driver:{' '}
              <span className={`font-semibold ${
                bindType === 'Within Guardrails' ? 'text-success/60' :
                bindType === 'Cap-Bound'         ? 'text-warning/60' : 'text-text-secondary/60'
              }`}>
                {bindType}
              </span>
            </p>
          </div>

          {/* Final Recommended Allocation — clean, restrained presentation */}
          <div className="rounded-lg border border-primary/20 bg-primary/3 px-4 py-3.5">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-[8px] uppercase tracking-[0.14em] font-semibold text-text-tertiary/45 mb-1">
                  Final Position Size
                </p>
                <p className="text-3xl font-bold font-mono text-primary leading-none">
                  {conviction.recommended_pct.toFixed(1)}%
                </p>
                {conviction.dollar_per_100k != null && (
                  <p className="text-[9px] text-text-tertiary/40 font-mono mt-1.5">
                    ${conviction.dollar_per_100k.toLocaleString()} per $100k
                  </p>
                )}
              </div>
              <div className="text-right space-y-2">
                {posType && (
                  <div>
                    <p className="text-[8px] uppercase tracking-wider text-text-tertiary/35">Classification</p>
                    <p className="text-[11px] font-semibold text-text-secondary">{posType}</p>
                  </div>
                )}
                {bindType && (
                  <div>
                    <p className="text-[8px] uppercase tracking-wider text-text-tertiary/35">Constraint Driver</p>
                    <p className={`text-[11px] font-semibold ${
                      bindType === 'Within Guardrails' ? 'text-success/70' :
                      bindType === 'Cap-Bound'         ? 'text-warning/70' : 'text-text-secondary'
                    }`}>
                      {bindType}
                    </p>
                  </div>
                )}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* ════════════════════════════════════════════════════════════════════
          SECTION 5 — EXECUTIVE CONCLUSION
          Concise synthesis: quality · risk posture · capital stance · triggers.
          3 sentences maximum. Closing memo.
          ════════════════════════════════════════════════════════════════════ */}
      <div className="px-5 py-4 border-b border-border/20">
        <SectionLabel>Executive Conclusion</SectionLabel>
        <p className="text-[11px] text-text-secondary leading-relaxed mt-1.5">
          {executiveConclusion}
        </p>
      </div>

      {/* ════════════════════════════════════════════════════════════════════
          ENGINE DIAGNOSTICS — Fully collapsible.
          Noise filter · Portfolio action context · Conviction basis.
          Advanced users only — not required for investment decisions.
          ════════════════════════════════════════════════════════════════════ */}
      {(conviction || signalBreakdown?.noise_filter || signalBreakdown?.portfolio_action) && (
        <Accordion label="Engine Diagnostics" badge="Advanced">

          {/* Noise regime */}
          {signalBreakdown?.noise_filter && (
            <div>
              <p className="text-[9px] font-semibold uppercase tracking-wider text-text-tertiary/45 mb-1.5">
                Noise Filter
              </p>
              <div className="flex items-center gap-2 mb-1.5 flex-wrap">
                <span className={`text-[10px] font-semibold uppercase tracking-wide ${
                  noiseDefer ? 'text-warning' : 'text-success/70'
                }`}>
                  {noiseRegime ?? '—'}
                </span>
                {noiseDefer && (
                  <span className="text-[9px] text-warning/60">· Defer full sizing</span>
                )}
              </div>
              <p className="text-[11px] text-text-secondary leading-relaxed">
                {signalBreakdown.noise_filter.action_guidance}
              </p>
            </div>
          )}

          {/* Portfolio action context */}
          {signalBreakdown?.portfolio_action && (
            <div className="space-y-2">
              <p className="text-[9px] font-semibold uppercase tracking-wider text-text-tertiary/45">
                Portfolio Action Context
              </p>
              <div className="grid grid-cols-2 gap-1.5">
                {([
                  ['Allocation Bias', signalBreakdown.portfolio_action.allocation_bias],
                  ['Conviction Scale', scalingLabel ?? `${signalBreakdown.portfolio_action.conviction_scaling_multiplier?.toFixed(2)}×`],
                  ['Risk Budget', signalBreakdown.portfolio_action.risk_budget_impact],
                  ['Mandate Fit', signalBreakdown.portfolio_action.mandate_fit],
                ] as [string, string | undefined | null][]).map(([k, v]) => v ? (
                  <div key={k} className="rounded border border-border/30 px-2.5 py-1.5">
                    <p className="text-[8px] uppercase tracking-wider text-text-tertiary/35 mb-0.5">{k}</p>
                    <p className="text-[11px] text-text-secondary">{v}</p>
                  </div>
                ) : null)}
              </div>
              {signalBreakdown.portfolio_action.sizing_guidance && (
                <p className="text-[11px] text-text-tertiary/55 italic border-l-2 border-border/30 pl-2.5 leading-relaxed">
                  {signalBreakdown.portfolio_action.sizing_guidance}
                </p>
              )}
            </div>
          )}

          {/* Conviction basis */}
          {conviction?.conviction_justification && (
            <div>
              <p className="text-[9px] font-semibold uppercase tracking-wider text-text-tertiary/45 mb-1.5">
                Conviction Basis
              </p>
              <p className="text-xs text-text-secondary leading-relaxed">
                {conviction.conviction_justification}
              </p>
            </div>
          )}
        </Accordion>
      )}

    </div>
  )
}
