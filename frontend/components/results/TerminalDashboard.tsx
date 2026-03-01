'use client'

// DVRG Executive Compression — 3-Layer Decision Architecture.
//
// Layer 1 (EXECUTIVE PANEL): Edge (hero) · Risk (contextual) · Capital (action)
// Layer 2 (WHY THIS EDGE):   Collapsed — scenario construct + metrics
// Layer 3 (DIAGNOSTICS):     Collapsed — engine internals for advanced users
//
// Visual hierarchy: EDGE dominates (text-5xl). RISK is analytical, not alarm.
// Direction label moved out of header into secondary "Status" line below thesis.
// Red reserved for catastrophic risk only (downside >15% OR stopProb >35%).
// Presentation-layer refactor only. Zero logic changes.

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

// Deterministic thesis sentence — lookup matrix from edge + risk + position type.
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

// Capital Efficiency = PWE ÷ |bear downside| — risk-adjusted edge scalar.
function capitalEfficiency(evPct: number | null, bearRet: number | null): number | null {
  if (evPct === null || bearRet === null || Math.abs(bearRet) < 0.01) return null
  return evPct / Math.abs(bearRet)
}

// ── Color maps ─────────────────────────────────────────────────────────────────

function edgeTierStyle(tier: EdgeTier): { text: string; border: string; bg: string } {
  switch (tier) {
    case 'Dislocation':  return { text: 'text-primary',  border: 'border-t-primary/40',  bg: 'bg-primary/5'  }
    case 'Strong Edge':  return { text: 'text-success',  border: 'border-t-success/40',  bg: 'bg-success/5'  }
    case 'Moderate Edge':return { text: 'text-success',  border: 'border-t-success/25',  bg: 'bg-success/3'  }
    case 'Weak Edge':    return { text: 'text-warning',  border: 'border-t-warning/35',  bg: 'bg-warning/5'  }
    case 'Avoid':        return { text: 'text-error',    border: 'border-t-error/35',    bg: 'bg-error/5'    }
  }
}

// Risk: no bg unless catastrophic (High). Red reserved for >15% downside or >35% stop prob.
function riskTierStyle(tier: RiskTier): { text: string; border: string; bg: string } {
  switch (tier) {
    case 'Contained': return { text: 'text-text-secondary',  border: 'border-t-border/30',   bg: ''            }
    case 'Moderate':  return { text: 'text-warning/70',      border: 'border-t-warning/20',  bg: ''            }
    case 'Elevated':  return { text: 'text-warning',         border: 'border-t-warning/30',  bg: ''            }
    case 'High':      return { text: 'text-error',           border: 'border-t-error/35',    bg: 'bg-error/5'  }
  }
}

// Direction — text color only (used for status line, not a header badge).
function directionTextColor(label: DirectionLabel): string {
  switch (label) {
    case 'Conviction': return 'text-primary'
    case 'Overweight': return 'text-success'
    case 'Accumulate': return 'text-success/80'
    case 'Watch':      return 'text-warning'
    case 'Avoid':      return 'text-error'
  }
}

// Deterministic one-liner that explains WHY the direction label was assigned.
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

// ── Math helpers ───────────────────────────────────────────────────────────────

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
  children,
}: {
  label: string
  sublabel?: string
  badge?: string
  children: ReactNode
}) {
  const [open, setOpen] = useState(false)
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

  // ── Thesis compression ────────────────────────────────────────────────────

  const thesis = generateThesisCompression(edgeTier, riskTier, posType ?? 'Satellite', upsideSkewRatio)

  // ── Scenario rows ────────────────────────────────────────────────────────

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

      {/* ═══════════════════════════════════════════════════════════════════
          HEADER — Ticker + Confidence (direction label moved to status line)
          ═══════════════════════════════════════════════════════════════════ */}
      <div className="px-5 py-3 flex items-center justify-between border-b border-border/30">
        <span className="text-2xl font-bold font-mono text-text-primary leading-none tracking-tight">
          {ticker}
        </span>
        {rawConfidence !== null && (
          <span className={`text-[10px] font-semibold tabular-nums ${
            rawConfidence >= 65 ? 'text-text-tertiary/55' :
            rawConfidence >= 40 ? 'text-warning/60'       : 'text-error/60'
          }`}>
            {rawConfidence}% confidence
          </span>
        )}
      </div>

      {/* ═══════════════════════════════════════════════════════════════════
          LAYER 1 — EXECUTIVE DECISION PANEL
          EDGE (hero) · RISK PROFILE (analytical) · RECOMMENDED ALLOCATION
          Visual hierarchy: EDGE text-5xl > CAPITAL text-3xl > RISK text-xl
          ═══════════════════════════════════════════════════════════════════ */}
      <div className="flex flex-col sm:flex-row divide-y sm:divide-y-0 sm:divide-x divide-border/30">

        {/* ── EDGE — Primary, visual hero ─────────────────────────────── */}
        <div className={`flex-1 px-5 py-5 flex flex-col gap-1 border-t-2 ${edgeSty.border} ${edgeSty.bg}`}>
          <span className="text-[9px] uppercase tracking-[0.14em] font-semibold text-text-tertiary/50">
            Edge
          </span>
          <span className={`text-xl font-bold leading-none ${edgeSty.text}`}>
            {edgeTier}
          </span>
          <span className={`text-5xl font-bold font-mono leading-none ${edgeSty.text}`}>
            {fmt(effectiveEvPct)}
          </span>
          <div className="flex items-center gap-2 mt-1 flex-wrap">
            {upsideSkewRatio !== null && (
              <span className="text-[10px] text-text-tertiary/50 font-medium">
                Skew {upsideSkewRatio.toFixed(1)}×
              </span>
            )}
            {effScore !== null && upsideSkewRatio !== null && (
              <span className="text-text-tertiary/25 text-[10px]">·</span>
            )}
            {effScore !== null && (
              <span className={`text-[10px] font-medium ${efficiencyColor(effScore)} opacity-70`}>
                Eff {effScore.toFixed(2)} · {efficiencyLabel(effScore)}
              </span>
            )}
          </div>
        </div>

        {/* ── RISK PROFILE — Analytical, not alarm ────────────────────── */}
        {/* No background unless riskTier === High (catastrophic only)    */}
        <div className={`flex-1 px-5 py-5 flex flex-col gap-1.5 border-t-2 ${riskSty.border} ${riskSty.bg}`}>
          <span className="text-[9px] uppercase tracking-[0.14em] font-semibold text-text-tertiary/50">
            Risk Profile
          </span>
          <span className={`text-xl font-bold leading-none ${riskSty.text}`}>
            {riskTier}
          </span>
          <div className="flex flex-col gap-0.5 mt-0.5">
            {priceTargets && (
              <span className="text-[10px] text-text-tertiary/60">
                Base Case:{' '}
                <span className={`font-semibold font-mono ${signColor(baseRet)}`}>
                  {fmt(baseRet, true)}
                </span>
              </span>
            )}
            {bearPct > 0 && (
              <span className="text-[10px] text-text-tertiary/60">
                Bear Probability:{' '}
                <span className="font-semibold">{bearPct}%</span>
              </span>
            )}
            {stopProb !== null && (
              <span className="text-[10px] text-text-tertiary/55">
                Stop Prob:{' '}
                <span className={`font-semibold ${
                  stopProb > 30 ? 'text-error' : stopProb > 15 ? 'text-warning/80' : 'text-text-secondary'
                }`}>
                  {stopProb.toFixed(0)}%
                </span>
              </span>
            )}
          </div>
        </div>

        {/* ── RECOMMENDED ALLOCATION — Actionable ─────────────────────── */}
        <div className="flex-1 px-5 py-5 flex flex-col gap-1.5 border-t-2 border-t-primary/25 bg-primary/3">
          <span className="text-[9px] uppercase tracking-[0.14em] font-semibold text-text-tertiary/50">
            Recommended Allocation
          </span>
          {conviction ? (
            <>
              <span className="text-3xl font-bold font-mono leading-none text-primary">
                {conviction.recommended_pct.toFixed(1)}%
              </span>
              {posType && (
                <span className="text-[10px] text-text-tertiary/60">
                  Position Type · <span className="font-semibold text-text-secondary">{posType}</span>
                </span>
              )}
              {bindType && (
                <span className="text-[10px] text-text-tertiary/60">
                  Constraint · <span className={`font-semibold ${
                    bindType === 'Within Guardrails' ? 'text-success/70' :
                    bindType === 'Cap-Bound'         ? 'text-warning/70' : 'text-text-secondary'
                  }`}>
                    {bindType}
                  </span>
                </span>
              )}
              {conviction.dollar_per_100k != null && (
                <span className="text-[10px] text-text-tertiary/40 font-mono mt-0.5">
                  ${conviction.dollar_per_100k.toLocaleString()} per $100k
                </span>
              )}
            </>
          ) : (
            <span className="text-3xl font-bold font-mono leading-none text-text-tertiary/40">—</span>
          )}
        </div>
      </div>

      {/* ═══════════════════════════════════════════════════════════════════
          DECISION ANCHOR — Thesis + Status line
          Status line replaces the header badge for direction label.
          Explanation prevents label from feeling contradictory.
          ═══════════════════════════════════════════════════════════════════ */}
      <div className="border-t border-border/25 px-5 py-3.5 space-y-2">
        <p className="text-[11px] text-text-secondary leading-relaxed italic">
          {thesis}
        </p>
        <div className="flex items-center gap-1.5 flex-wrap">
          <span className="text-[8px] uppercase tracking-wider text-text-tertiary/35">Status</span>
          <span className={`text-[10px] font-bold uppercase tracking-wide ${dirColor}`}>
            {direction}
          </span>
          <span className="text-text-tertiary/25 text-[10px]">·</span>
          <span className="text-[10px] text-text-tertiary/50">
            {directionExplanation(direction)}
          </span>
        </div>
      </div>

      {/* Supporting reference row — muted, not competing */}
      {(currentPrice > 0 || fvMid || pwTarget > 0 || irr !== null) && (
        <div className="border-t border-border/20 px-5 py-2 flex items-center gap-4 flex-wrap">
          {currentPrice > 0 && (
            <div>
              <p className="text-[8px] uppercase tracking-wider text-text-tertiary/35">Price</p>
              <p className="text-xs font-semibold font-mono text-text-tertiary/55">
                ${currentPrice.toFixed(2)}
              </p>
            </div>
          )}
          {fvMid && (
            <>
              <div className="w-px h-4 bg-border/20" />
              <div>
                <p className="text-[8px] uppercase tracking-wider text-text-tertiary/35">Fair Value</p>
                <p className="text-xs font-semibold font-mono text-text-tertiary/55">
                  ${fvMid.toFixed(0)}
                  {impliedUpside !== null && (
                    <span className={`ml-1.5 ${signColor(impliedUpside)} opacity-65`}>
                      {fmt(impliedUpside, true)}
                    </span>
                  )}
                </p>
              </div>
            </>
          )}
          {pwTarget > 0 && (
            <>
              <div className="w-px h-4 bg-border/20" />
              <div>
                <p className="text-[8px] uppercase tracking-wider text-text-tertiary/35">PW Target</p>
                <p className={`text-xs font-semibold font-mono ${signColor(pwRet)} opacity-55`}>
                  ${pwTarget.toFixed(0)} · {fmt(pwRet, true)}
                  {stabilityMod < 1 && (
                    <span className="ml-1 text-warning/65">eff {fmt(pwRet * stabilityMod, true)}</span>
                  )}
                </p>
              </div>
            </>
          )}
          {irr !== null && (
            <>
              <div className="w-px h-4 bg-border/20" />
              <div>
                <p className="text-[8px] uppercase tracking-wider text-text-tertiary/35">Ann. IRR</p>
                <p className={`text-xs font-semibold font-mono ${signColor(irr)} opacity-55`}>
                  {fmt(irr)}
                </p>
              </div>
            </>
          )}
        </div>
      )}

      {/* ═══════════════════════════════════════════════════════════════════
          LAYER 2 — WHY THIS EDGE (collapsed)
          Scenario construct · Skew · Confidence · Stop Prob
          ═══════════════════════════════════════════════════════════════════ */}
      <Accordion
        label="Why This Edge"
        sublabel="· Scenario construct · Skew · Confidence"
      >
        {/* Scenario table */}
        {scenarioRows.length > 0 && (
          <div>
            <p className="text-[9px] uppercase tracking-wider text-text-tertiary/45 mb-2.5">
              Scenario Construct
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

        {/* Supporting metrics with micro-explanations */}
        <div className="grid grid-cols-2 gap-2">
          {upsideSkewRatio !== null && (
            <div className="rounded border border-border/25 px-3 py-2.5">
              <p className="text-[8px] uppercase tracking-wider text-text-tertiary/40 mb-0.5">Skew Ratio</p>
              <p className={`text-lg font-bold font-mono leading-none ${
                upsideSkewRatio >= 2 ? 'text-success' :
                upsideSkewRatio >= 1 ? 'text-warning' : 'text-error'
              }`}>
                {upsideSkewRatio.toFixed(1)}×
              </p>
              <p className="text-[9px] text-text-tertiary/50 mt-1 leading-snug">
                {upsideSkewRatio >= 1
                  ? `Upside outweighs downside by ${((upsideSkewRatio - 1) * 100).toFixed(0)}%`
                  : 'Downside outweighs upside'}
              </p>
            </div>
          )}

          {rawConfidence !== null && (
            <div className="rounded border border-border/25 px-3 py-2.5">
              <p className="text-[8px] uppercase tracking-wider text-text-tertiary/40 mb-0.5">Signal Confidence</p>
              <p className={`text-lg font-bold font-mono leading-none ${
                rawConfidence >= 65 ? 'text-success' :
                rawConfidence >= 40 ? 'text-warning' : 'text-error'
              }`}>
                {rawConfidence}%
              </p>
              <p className="text-[9px] text-text-tertiary/50 mt-1 leading-snug">
                Effective signal integrity
              </p>
            </div>
          )}

          {bearRet !== null && (
            <div className="rounded border border-border/25 px-3 py-2.5">
              <p className="text-[8px] uppercase tracking-wider text-text-tertiary/40 mb-0.5">Bear Downside</p>
              <p className="text-lg font-bold font-mono leading-none text-error">
                {fmt(bearRet, true)}
              </p>
              <p className="text-[9px] text-text-tertiary/50 mt-1 leading-snug">
                Worst-case scenario return
              </p>
            </div>
          )}

          {stopProb !== null && (
            <div className="rounded border border-border/25 px-3 py-2.5">
              <p className="text-[8px] uppercase tracking-wider text-text-tertiary/40 mb-0.5">Stop Probability</p>
              <p className={`text-lg font-bold font-mono leading-none ${
                stopProb > 30 ? 'text-error' : stopProb > 15 ? 'text-warning' : 'text-success'
              }`}>
                {stopProb.toFixed(0)}%
              </p>
              <p className="text-[9px] text-text-tertiary/50 mt-1 leading-snug">
                {signalBreakdown?.stop_probability?.stop_probability_label ?? 'Adverse exit probability'}
              </p>
            </div>
          )}
        </div>
      </Accordion>

      {/* ═══════════════════════════════════════════════════════════════════
          LAYER 3 — ADVANCED ALLOCATION DIAGNOSTICS (fully collapsible)
          Retail users should never feel required to open this.
          ═══════════════════════════════════════════════════════════════════ */}
      {(conviction || signalBreakdown?.noise_filter || signalBreakdown?.portfolio_action) && (
        <Accordion
          label="Advanced Allocation Diagnostics"
          badge="Engine"
        >
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

          {/* Sizing rationale */}
          {conviction?.rationale && (
            <div>
              <p className="text-[9px] font-semibold uppercase tracking-wider text-text-tertiary/45 mb-1.5">
                Sizing Rationale
              </p>
              <p className="text-xs text-text-secondary leading-relaxed">{conviction.rationale}</p>
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

          {/* Cap enforcement grid */}
          {conviction && (
            <div>
              <p className="text-[9px] font-semibold uppercase tracking-wider text-text-tertiary/45 mb-1.5">
                Allocation Guardrails
              </p>
              <div className="grid grid-cols-3 gap-1.5">
                {[
                  { label: 'Recommended', value: `${conviction.recommended_pct.toFixed(1)}%` },
                  { label: 'Exec-Constrained', value: `${execPct.toFixed(1)}%` },
                  { label: 'Policy Cap', value: `${conviction.max_pct.toFixed(1)}%` },
                ].map(({ label, value }) => (
                  <div key={label} className="rounded border border-border/25 px-2.5 py-2">
                    <p className="text-[8px] uppercase tracking-wider text-text-tertiary/35 mb-0.5">{label}</p>
                    <p className="text-sm font-bold font-mono text-text-secondary">{value}</p>
                  </div>
                ))}
              </div>
            </div>
          )}
        </Accordion>
      )}

    </div>
  )
}
