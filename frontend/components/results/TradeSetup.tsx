import { useState } from 'react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { formatCurrency } from '@/lib/utils/formatting'
import { computeOutcomeDistribution } from '@/lib/utils/probability-engine'
import type { OutcomeDistribution } from '@/lib/utils/probability-engine'
import type { EnhancedTradeSetup, TradeSetupSide, RecommendedStrategy, SignalBreakdown, FairValueCalibration } from '@/types/api'

// Expandable disclosure for the CLAMPED entry case.
// Shows both the original model output and the re-anchored value so users can
// make an informed judgment rather than only seeing the post-heuristic result.
function ClampedEntryDisclosure({
  classification,
  justification,
  belowBearPct,
  originalIdealLow,
}: {
  classification?: string
  justification: string
  belowBearPct?: number
  originalIdealLow?: number | null
}) {
  const [expanded, setExpanded] = useState(false)
  const isClamped = classification === 'CLAMPED'
  const isDistressed = classification === 'DISTRESSED_ENTRY'
  const colorClass = isDistressed || isClamped
    ? 'bg-error/10 border-error/30 text-error'
    : 'bg-warning/10 border-warning/30 text-warning'

  const title = isDistressed ? 'Distressed Entry Zone'
    : isClamped ? 'Entry Re-anchored (Risk Heuristic)'
    : 'Entry Below Risk Scenario Floor'

  return (
    <div className={`p-3 rounded-md border text-xs leading-relaxed ${colorClass}`}>
      <div className="flex items-center justify-between gap-2 mb-1">
        <div className="flex items-center gap-2">
          <span className="font-bold">{title}</span>
          {belowBearPct !== undefined && belowBearPct > 0 && (
            <span className="font-normal opacity-80">({belowBearPct.toFixed(1)}% below Risk Scenario)</span>
          )}
        </div>
        {isClamped && (
          <button
            onClick={() => setExpanded(v => !v)}
            className="text-[10px] underline underline-offset-2 opacity-70 hover:opacity-100 shrink-0"
          >
            {expanded ? 'Hide detail ▲' : 'Why? ▼'}
          </button>
        )}
      </div>

      <p className="text-text-secondary">{justification}</p>

      {isClamped && expanded && (
        <div className="mt-2.5 pt-2.5 border-t border-error/20 space-y-1.5">
          {originalIdealLow != null && (
            <p>
              <span className="font-semibold">Model output (unclamped):</span>{' '}
              <span className="font-mono">${originalIdealLow.toFixed(2)}</span>
              <span className="opacity-70"> — the raw calculation before re-anchoring.</span>
            </p>
          )}
          <p className="opacity-80">
            <span className="font-semibold">Why we re-anchor:</span>{' '}
            When the model calculates an entry significantly below its own bear-case estimate,
            we cap it at bear−5% as a conservative floor. This is a{' '}
            <span className="font-semibold">risk management heuristic, not a model prediction</span>{' '}
            — if you believe the model&rsquo;s original calculation is correct for your risk tolerance,
            you may use that value instead.
          </p>
          <p className="opacity-70 italic">
            Consider: if the model genuinely thinks ${originalIdealLow?.toFixed(2)} is the right
            entry, suppressing that signal may not serve your interests. Use professional judgment.
          </p>
        </div>
      )}
    </div>
  )
}

interface TradeSetupProps {
  setup: EnhancedTradeSetup
  ticker: string
  strategy?: RecommendedStrategy | null
  signalBreakdown?: SignalBreakdown | null
  rating?: string | null
  currentPrice?: number
  calibration?: FairValueCalibration | null
  financialHealthScore?: number
}

function detectStructuralPremium(
  calibration: FairValueCalibration | null | undefined,
  currentPrice: number | undefined,
  financialHealthScore: number | undefined
): boolean {
  if (!calibration || !currentPrice || financialHealthScore == null) return false
  const fv = calibration.internal_fair_value
  if (!fv || fv <= 0) return false
  return (currentPrice - fv) / fv > 0.5 && calibration.regime === 'Growth' && financialHealthScore > 7.0
}

const STOP_QUALITY_STYLES: Record<string, { badge: string; note: string }> = {
  ALIGNED: { badge: 'bg-success/15 text-success border-success/30', note: 'text-success' },
  WIDE: { badge: 'bg-warning/15 text-warning border-warning/30', note: 'text-warning' },
  ADJUSTED: { badge: 'bg-primary/15 text-primary border-primary/30', note: 'text-primary' },
}

// Precision normalization — use zone format for anchor prices (estimates),
// keep formatCurrency for precise target prices (defined objectives).
function formatAnchor(price: number): string {
  return `~$${Math.round(price).toLocaleString()}`
}

// ── Probability display utilities ─────────────────────────────────────────────

/**
 * Visual floor/ceiling clamp for ALL probability displays.
 * 0% → "<1%", 100% → ">99%". Pure presentation — no math change.
 * Accepts a fraction (0–1).
 */
function clampProb(fraction: number): string {
  const rounded = Math.round(fraction * 100)
  if (rounded <= 0) return '<1%'
  if (rounded >= 100) return '>99%'
  return `${rounded}%`
}

/**
 * Qualitative probability band for institutional cognition.
 * Returns the band label only — caller appends the numeric value.
 * Accepts a fraction (0–1).
 */
function probBand(fraction: number): string {
  const pct = fraction * 100
  if (pct < 1)  return 'Negligible'
  if (pct < 5)  return 'Very Low'
  if (pct < 15) return 'Low'
  if (pct < 35) return 'Moderate'
  if (pct < 60) return 'Balanced'
  return 'High'
}

// Derive approximate time horizon from the target label (backend-supplied).
// Returns a short string for display. This is interpretive only — no calculation.
function inferTargetHorizon(label: string, index: number): string {
  const l = label.toLowerCase()
  if (l.startsWith('t1') || l.includes('t1 —') || l.includes('tactical bounce') || l.includes('near') || l.includes('short')) return '1–3 mo'
  if (l.startsWith('t2') || l.includes('t2 —') || l.includes('trend repair') || l.includes('base') || l.includes('mid')) return '6–12 mo'
  if (l.startsWith('t3') || l.includes('t3 —') || l.includes('fundamental re-rating')) return '12–24 mo'
  if (l.startsWith('t4') || l.includes('t4 —') || l.includes('regime expansion') || l.includes('bull') || l.includes('stretch') || l.includes('extended') || l.includes('upside')) return '24–36 mo'
  // Fallback by position
  if (index === 0) return '1–3 mo'
  if (index === 1) return '6–12 mo'
  if (index === 2) return '12–24 mo'
  return '24–36 mo'
}

// Determine whether a target is within the primary holding period window.
// T4 (regime expansion) and legacy "bull"/"stretch" labels are extended.
// T3 (fundamental re-rating) is a primary target — NOT extended.
function isExtendedTarget(label: string, index: number): boolean {
  const l = label.toLowerCase()
  if (l.startsWith('t4') || l.includes('t4 —') || l.includes('regime expansion') || l.includes('bull') || l.includes('stretch') || l.includes('extended') || l.includes('upside')) return true
  if (index >= 3) return true  // T4+ (0-indexed) are extended
  return false
}

// Classify target by analytical type for institutional-grade labeling.
// Extended targets use regime framing rather than promotional outcome language.
function inferTargetType(label: string, index: number): string {
  const l = label.toLowerCase()
  if (l.startsWith('t4') || l.includes('t4 —') || l.includes('regime expansion') || l.includes('bull') || l.includes('stretch') || l.includes('extended') || l.includes('upside') || index >= 3)
    return 'Regime Expansion'
  if (l.startsWith('t3') || l.includes('t3 —') || l.includes('fundamental re-rating') || (l.includes('t3') && index === 2))
    return 'Fundamental Re-rating'
  if (l.startsWith('t2') || l.includes('t2 —') || l.includes('trend repair') || l.includes('base') || l.includes('mid') || index === 1)
    return 'Trend Repair'
  if (l.startsWith('t1') || l.includes('t1 —') || l.includes('tactical bounce') || l.includes('near') || l.includes('short') || index === 0)
    return 'Tactical Reversion'
  return 'Thesis'
}

// Normalize any legacy target label formats to the current scenario taxonomy.
// New labels (T1/T2/T3 with scenario names) pass through unchanged.
// No numerical values are altered — this is label normalization only.
function sanitizeTargetLabel(label: string): string {
  return label
    // Legacy formats → current scenario names
    .replace(/\(bull case\)/gi, '(Re-rating Scenario)')
    .replace(/\(stretch\)/gi, '(Regime Expansion Scenario)')
    .replace(/\(near.?term\)/gi, '(Continuation Scenario)')
    .replace(/\(base case\)/gi, '(Continuation Scenario)')
    // Current format (T1/T2/T3 — Scenario Name) passes through unchanged
}

// Qualitative conditionality tag per target — expectation management without
// introducing new probability models.
function inferTargetConditionality(
  label: string,
  index: number,
  rating: string | null | undefined,
  variant: 'conservative' | 'aggressive'
): string | null {
  const l = label.toLowerCase()
  // T3 (Regime Expansion) and legacy "bull"/"stretch" labels are conditional on regime / thesis validation
  if (l.includes('regime expansion') || l.includes('bull') || l.includes('stretch') || index >= 2) return 'Conditional Scenario'
  // Re-rating Scenario (T2 aggressive) requires multiple expansion beyond current consensus
  if ((l.includes('re-rating') || index === 1) && variant === 'aggressive') return 'Requires Multiple Expansion'
  // T1 under HOLD depends on divergence resolving in favor of the thesis
  if (index === 0 && rating === 'HOLD') return 'Dependent on Thesis Resolution'
  return null
}

// Target validity classification — ensures only actionable targets appear in "Profit Targets".
// Drives scenario-branch separation and the Structural References subsection.
type TargetValidity = 'VALID' | 'NOT_APPLICABLE' | 'REFERENCE_ONLY' | 'SUPPRESSED'

function classifyTargetValidity(
  target: { price: number; suppressed?: boolean },
  currentPrice: number | undefined,
  regimeMode: string | null | undefined,
  isDeepEntry: boolean,
): TargetValidity {
  if (target.suppressed) return 'SUPPRESSED'
  // Long setup: target at or below current price is not a profit target
  if (currentPrice && currentPrice > 0 && target.price <= currentPrice) return 'NOT_APPLICABLE'
  // Structural reversion targets in MOMENTUM regime are structural anchors, not actionable
  if (regimeMode === 'MOMENTUM' && isDeepEntry) return 'REFERENCE_ONLY'
  return 'VALID'
}

// H2: Weighted realized R/R using staged sell percentages.
// Formula: Σ(target_gain_per_share × sell_fraction) / risk_per_share
// Normalised by total sell fraction in case percentages don't add to 100.
function getWeightedRealizedRR(
  entry: number,
  stopLoss: number,
  targets: { price: number; sell_pct: number }[]
): number | null {
  const risk = entry - stopLoss
  if (risk <= 0 || targets.length === 0) return null
  const totalPct = targets.reduce((sum, t) => sum + t.sell_pct, 0)
  if (totalPct === 0) return null
  let weightedGain = 0
  for (const t of targets) {
    const gain = t.price - entry
    weightedGain += gain * (t.sell_pct / totalPct)
  }
  if (weightedGain <= 0) return null
  return Math.round((weightedGain / risk) * 10) / 10
}

// Time-normalized interpretation of the R/R ratio — purely informational.
// Annualizes the modeled ratio to prevent conflating long-horizon asymmetry
// with short-term trade expectancy. Not a new calculation engine.
function getAnnualizedRREq(rr: number, holdingPeriod: string | null | undefined): string | null {
  if (!holdingPeriod || rr <= 0) return null
  const rangeMatch = holdingPeriod.match(/(\d+)[–\-](\d+)\s*months?/i)
  if (rangeMatch) {
    const avgMonths = (parseInt(rangeMatch[1]) + parseInt(rangeMatch[2])) / 2
    const years = avgMonths / 12
    if (years <= 0) return null
    return `${(rr / years).toFixed(1)}:1`
  }
  const singleMatch = holdingPeriod.match(/(\d+)\s*months?/i)
  if (singleMatch) {
    const years = parseInt(singleMatch[1]) / 12
    if (years <= 0) return null
    return `${(rr / years).toFixed(1)}:1`
  }
  return null
}

// Adaptive copy when current price is within a tight band near the stop loss.
// Neutral / institutional tone — not alarmist.
function getProximityWarning(
  currentPrice: number | undefined,
  stopLoss: number,
  entry: number
): string | null {
  if (!currentPrice || currentPrice <= 0) return null
  if (currentPrice < stopLoss) return 'Current Price Below Stop — Risk Threshold Breached'
  const riskRange = entry - stopLoss
  if (riskRange <= 0) return null
  const proximity = (currentPrice - stopLoss) / riskRange
  if (proximity < 0.12) return 'Price Near Risk Boundary — Limited Margin for Error'
  if (proximity < 0.22) return 'Execution Sensitivity Elevated'
  return null
}

// R/R realism qualifier — high ratios are modeled projections, not realized outcome guarantees.
function getRRRealism(
  rr: number,
  hasHighDivergence: boolean
): { qualifier: string | null; footnote: string | null } {
  if (rr >= 6 && hasHighDivergence)
    return {
      qualifier: 'Theoretical',
      footnote: 'Modeled asymmetry — realized performance is regime-dependent. High signal divergence reduces path probability; monitor flow and momentum alignment before full sizing.',
    }
  if (rr >= 4)
    return {
      qualifier: 'Modeled',
      footnote: 'Modeled asymmetry reflects scenario-weighted price targets. Execution variability, volatility compression, and timing risk may reduce realized returns.',
    }
  return { qualifier: null, footnote: null }
}

// Conditional R/R qualifier — when signals conflict with the R/R implication,
// surfaces the structural vs. tactical distinction rather than a generic conflict flag.
function getRRConditionalQualifier(
  rr: number,
  signalBreakdown: SignalBreakdown | null | undefined,
  rating: string | null | undefined
): { label: string | null; footnote: string | null } {
  if (!signalBreakdown?.has_divergence || rr < 2.5) return { label: null, footnote: null }

  const scores = [
    signalBreakdown.news_score,
    signalBreakdown.earnings_score,
    signalBreakdown.analyst_score,
    signalBreakdown.institutional_score,
    signalBreakdown.insider_score,
  ]
  const bearishCount = scores.filter(s => s < 4).length
  const bullishCount = scores.filter(s => s > 6).length

  if (bearishCount > bullishCount && rr > 3)
    return {
      label: 'Low Signal Agreement',
      footnote: 'Flow and sentiment signals (tactical) conflict with the structural thesis — bearish signal dominance impairs near-term path probability. Modeled upside magnitude is intact; probability of achieving it within the holding window is reduced.',
    }
  if (rating === 'HOLD' && rr > 4)
    return {
      label: 'Thesis-Dependent',
      footnote: 'High modeled asymmetry — realized payoff is contingent on divergence resolution in favor of the structural thesis. HOLD reflects signal-level timing uncertainty, not fundamental impairment. Monitor for flow and momentum alignment before adding exposure.',
    }
  if (signalBreakdown.has_divergence && rr > 4)
    return {
      label: 'Divergence Unresolved',
      footnote: 'Signal conflict active — structural thesis is intact but tactical timing risk is elevated. Modeled asymmetry is regime-dependent; await valuation and flow convergence before full position sizing.',
    }
  return { label: null, footnote: null }
}

// Horizon-bound gain from primary window targets only (non-extended, within ~12-month horizon).
// Prevents the low-probability regime expansion ceiling from dominating payoff display.
// Formula: Σ (target_price - entry) × sell_fraction × 100 shares, primary targets only.
function computeHorizonBoundGain(
  entry: number,
  targets: { price: number; sell_pct: number; label: string }[]
): number | null {
  const primaryTargets = targets.filter((t, i) => !isExtendedTarget(t.label, i))
  if (primaryTargets.length === 0) return null
  let totalGain = 0
  for (const t of primaryTargets) {
    const gain = (t.price - entry) * (t.sell_pct / 100) * 100
    totalGain += gain
  }
  if (totalGain <= 0) return null
  return Math.round(totalGain * 100) / 100
}

// FIX 2 + FIX 4: Calculate estimated R/R at a different entry price, using the same
// proportional stop distance as the current setup.
function calcRRAtEntry(newEntry: number, currentEntry: number, currentStop: number, t2Price: number): number | null {
  if (currentEntry <= 0 || newEntry <= 0 || newEntry >= currentEntry) return null
  const stopPct = (currentEntry - currentStop) / currentEntry
  if (stopPct <= 0) return null
  const newStop = newEntry * (1 - stopPct)
  const risk = newEntry - newStop
  const gain = t2Price - newEntry
  if (risk <= 0 || gain <= 0) return null
  return Math.round((gain / risk) * 10) / 10
}

// ──────────────────────────────────────────────────────────────
// Module 1–4 + 6–9: Outcome Distribution Model
// Probability-weighted outcome table + EV engine + context layers.
// ──────────────────────────────────────────────────────────────

function OutcomeDistributionPanel({ dist, variant }: {
  dist: OutcomeDistribution
  variant: 'conservative' | 'aggressive'
}) {
  const [expanded, setExpanded] = useState(false)
  const evPositive = dist.ev >= 0
  const evColor = dist.ev > 1.5 ? 'text-success' : dist.ev > 0 ? 'text-warning' : 'text-error'

  // Stop progress bar — clipped to 80% width max for visual clarity
  const stopBarWidth = Math.min(80, Math.round(dist.stopTriggerProb * 100))

  // Payoff skew label
  const skewLabel =
    dist.payoffSkew >= 3.0 ? 'Favorable' :
    dist.payoffSkew >= 1.5 ? 'Moderate'  :
    dist.payoffSkew >= 0.8 ? 'Marginal'  : 'Unfavorable'
  const skewColor =
    dist.payoffSkew >= 3.0 ? 'text-success' :
    dist.payoffSkew >= 1.5 ? 'text-warning' : 'text-error'

  // Risk efficiency interpretation
  const effLabel =
    dist.riskEfficiency > 0.40  ? 'Efficient' :
    dist.riskEfficiency > 0.10  ? 'Marginal'  :
    dist.riskEfficiency > -0.10 ? 'Breakeven' : 'Inefficient'
  const effColor =
    dist.riskEfficiency > 0.40  ? 'text-success' :
    dist.riskEfficiency > 0.10  ? 'text-warning'  :
    dist.riskEfficiency > -0.10 ? 'text-text-tertiary' : 'text-error'

  // Module 7: Volatility state styling
  const volStateColor =
    dist.volatilityContext.state === 'Stress'     ? 'text-error' :
    dist.volatilityContext.state === 'Elevated'   ? 'text-warning' :
    dist.volatilityContext.state === 'Suppressed' ? 'text-text-tertiary' : 'text-success/80'

  // Module 9: Stability tier styling
  const stabilityColor =
    dist.probabilityStability.tier === 'Robust'          ? 'text-success/80' :
    dist.probabilityStability.tier === 'Stable'          ? 'text-success/60' :
    dist.probabilityStability.tier === 'Moderate'        ? 'text-warning' :
    dist.probabilityStability.tier === 'Fragile'         ? 'text-error/70' : 'text-error'

  // Module 6: Horizon efficiency styling
  const horizonEffColor =
    dist.horizonContext.horizonEfficiencyFlag === 'Efficient'  ? 'text-success/70' :
    dist.horizonContext.horizonEfficiencyFlag === 'Acceptable' ? 'text-warning' :
    dist.horizonContext.horizonEfficiencyFlag === 'Extended'   ? 'text-text-tertiary' : 'text-error/60'

  // Short T-label extraction for table rows
  function shortLabel(label: string, i: number): string {
    const m = label.match(/^[Tt](\d+)/)
    return m ? `T${m[1]}` : `T${i + 1}`
  }

  return (
    <div className="border-t border-surface-elevated pt-3 mt-1 space-y-3">
      {/* Section header */}
      <div className="flex items-center justify-between">
        <span className="text-[10px] font-semibold uppercase tracking-wider text-text-tertiary/70">
          Outcome Distribution Model
        </span>
        <button
          onClick={() => setExpanded(v => !v)}
          className="text-[10px] text-text-tertiary/60 hover:text-text-tertiary underline underline-offset-2"
        >
          {expanded ? 'Collapse ▲' : 'Expand ▼'}
        </button>
      </div>

      {/* EV summary — always visible (primary metrics) */}
      <div className={`rounded-md px-3 py-2 border ${
        variant === 'conservative'
          ? 'bg-success/5 border-success/15'
          : 'bg-warning/5 border-warning/15'
      }`}>
        <div className="grid grid-cols-4 gap-2 text-xs">
          <div>
            <span className="text-text-tertiary block text-[10px]">Expected Value</span>
            <span className={`font-semibold ${evColor}`}>
              {evPositive ? '+' : ''}{dist.ev.toFixed(2)}%
            </span>
          </div>
          <div>
            <span className="text-text-tertiary block text-[10px]">Payoff Skew</span>
            <span className={`font-semibold ${skewColor}`}>{dist.payoffSkew.toFixed(1)}× <span className="font-normal text-[10px]">{skewLabel}</span></span>
          </div>
          <div>
            <span className="text-text-tertiary block text-[10px]">Risk Efficiency</span>
            <span className={`font-semibold ${effColor}`}>{dist.riskEfficiency.toFixed(2)} <span className="font-normal text-[10px]">{effLabel}</span></span>
          </div>
          <div>
            <span className="text-text-tertiary block text-[10px]">Stop Prob.</span>
            <span className={`font-semibold ${dist.stopTailRiskFlag ? 'text-error' : 'text-text-secondary'}`}>
              {clampProb(dist.stopTriggerProb)}
            </span>
          </div>
        </div>

        {/* Module 6 / 7 / 9: Context layer — always visible, provides reliability framing */}
        <div className="grid grid-cols-4 gap-2 text-xs mt-2 pt-2 border-t border-border/20">
          <div>
            <span className="text-text-tertiary/60 block text-[9px] uppercase tracking-wide">Horizon</span>
            <span className="text-[10px] font-medium text-text-secondary">
              {dist.horizonContext.primaryHorizon}
            </span>
          </div>
          <div>
            <span className="text-text-tertiary/60 block text-[9px] uppercase tracking-wide">Vol Regime</span>
            <span className={`text-[10px] font-medium ${volStateColor}`}>
              {dist.volatilityContext.state}
            </span>
          </div>
          <div>
            <span className="text-text-tertiary/60 block text-[9px] uppercase tracking-wide">Stability</span>
            <span className={`text-[10px] font-medium ${stabilityColor}`}>
              {dist.probabilityStability.tier}
            </span>
          </div>
          <div>
            <span className="text-text-tertiary/60 block text-[9px] uppercase tracking-wide">EV Pctile (Calib.)</span>
            <span className="text-[10px] font-medium text-text-secondary">
              {dist.universePercentiles.evPercentile}th
            </span>
          </div>
        </div>
      </div>

      {/* Expanded: full probability table + context layers */}
      {expanded && (
        <div className="space-y-3">

          {/* Module 6: EV Horizon Anchoring */}
          <div className="rounded-md border border-border/40 bg-surface/30 px-3 py-2.5 space-y-1.5">
            <p className="text-[10px] font-semibold uppercase tracking-wider text-text-tertiary/70">
              EV Horizon Context
            </p>
            <div className="grid grid-cols-3 gap-3 text-xs">
              <div>
                <span className="text-[10px] text-text-tertiary block">Time-Bound EV</span>
                <span className={`font-semibold ${evColor}`}>
                  {evPositive ? '+' : ''}{dist.ev.toFixed(2)}%{" "}
                  <span className="font-normal text-[10px] text-text-tertiary">
                    ({dist.horizonContext.primaryHorizon})
                  </span>
                </span>
              </div>
              <div>
                <span className="text-[10px] text-text-tertiary block">Annualized Equiv.</span>
                <span className={`font-semibold ${dist.horizonContext.annualizedExpectation > 0 ? evColor : 'text-error'}`}>
                  {dist.horizonContext.annualizedExpectation > 0 ? '+' : ''}{dist.horizonContext.annualizedExpectation.toFixed(1)}%<span className="font-normal text-text-tertiary"> /yr</span>
                </span>
              </div>
              <div>
                <span className="text-[10px] text-text-tertiary block">Horizon Efficiency</span>
                <span className={`font-semibold text-[10px] ${horizonEffColor}`}>
                  {dist.horizonContext.horizonEfficiencyFlag}
                </span>
              </div>
            </div>
            <p className="text-[9px] text-text-tertiary/50 italic leading-relaxed">
              Annualized expectation is a heuristic normalization — not a realized return forecast.
              Horizon derived from target count and regime state.
            </p>
          </div>

          {/* Probability × Return × EV table */}
          <div className="rounded-md border border-border/50 overflow-hidden">
            <div className="grid grid-cols-4 gap-0 px-2 py-1 bg-surface-elevated/50">
              <span className="text-[10px] font-semibold text-text-tertiary uppercase tracking-wide">Scenario</span>
              <span className="text-[10px] font-semibold text-text-tertiary uppercase tracking-wide text-right">Prob.</span>
              <span className="text-[10px] font-semibold text-text-tertiary uppercase tracking-wide text-right">Return</span>
              <span className="text-[10px] font-semibold text-text-tertiary uppercase tracking-wide text-right">EV Contrib.</span>
            </div>
            {/* Stop row */}
            <div className="grid grid-cols-4 gap-0 px-2 py-1.5 border-t border-border/30 bg-error/3">
              <span className="text-xs font-medium text-error/80">Stop</span>
              <span className="text-xs text-right text-text-secondary">{clampProb(dist.stop.prob)}</span>
              <span className="text-xs text-right text-error font-mono">{dist.stop.returnPct.toFixed(1)}%</span>
              <span className="text-xs text-right text-error/70 font-mono">{dist.stop.evContrib.toFixed(2)}%</span>
            </div>
            {/* Target rows */}
            {dist.targets.map((t, i) => (
              <div key={i} className="grid grid-cols-4 gap-0 px-2 py-1.5 border-t border-border/20">
                <span className="text-xs text-text-secondary">{shortLabel(t.label, i)}</span>
                <span className="text-xs text-right text-text-secondary">{clampProb(t.prob)}</span>
                <span className="text-xs text-right text-success/80 font-mono">+{t.returnPct.toFixed(1)}%</span>
                <span className="text-xs text-right text-success/60 font-mono">+{t.evContrib.toFixed(2)}%</span>
              </div>
            ))}
          </div>

          {/* EV decomposition */}
          <div className="grid grid-cols-3 gap-2 text-xs">
            <div className="bg-surface-elevated/40 rounded px-2 py-1.5">
              <span className="text-[10px] text-text-tertiary block">Expected Gain</span>
              <span className="font-semibold text-success">+{dist.expectedGain.toFixed(2)}%</span>
            </div>
            <div className="bg-surface-elevated/40 rounded px-2 py-1.5">
              <span className="text-[10px] text-text-tertiary block">Expected Loss</span>
              <span className="font-semibold text-error">−{dist.expectedLoss.toFixed(2)}%</span>
            </div>
            <div className="bg-surface-elevated/40 rounded px-2 py-1.5">
              <span className="text-[10px] text-text-tertiary block">Expected Vol.</span>
              <span className="font-semibold text-text-secondary">±{dist.expectedVolatility.toFixed(1)}%</span>
            </div>
          </div>

          {/* Module 9 + 6: Probability Reliability & EV Confidence */}
          <div className="rounded-md border border-border/40 p-2.5 space-y-2">
            <div className="flex items-center justify-between">
              <span className="text-[10px] font-semibold uppercase tracking-wider text-text-tertiary/70">
                Probability Reliability
              </span>
              <div className="flex items-center gap-1.5">
                {dist.probabilityStability.modelSensitivityFlag && (
                  <span className="text-[10px] font-semibold text-error bg-error/10 px-1.5 py-0.5 rounded">
                    Model Sensitivity Elevated
                  </span>
                )}
                {dist.probabilityStability.stabilityModifierActive && !dist.probabilityStability.modelSensitivityFlag && (
                  <span className="text-[10px] font-semibold text-warning bg-warning/10 px-1.5 py-0.5 rounded">
                    Stability Modifier Active
                  </span>
                )}
              </div>
            </div>
            <div className="grid grid-cols-2 gap-x-4 gap-y-1.5 text-xs">
              <div>
                <span className="text-[10px] text-text-tertiary block">Probability Stability</span>
                <span className={`font-semibold ${stabilityColor}`}>
                  {dist.probabilityStability.tier}
                  <span className="font-normal text-text-tertiary text-[10px]">
                    {" "}({dist.probabilityStability.score}/100)
                  </span>
                </span>
              </div>
              <div>
                <span className="text-[10px] text-text-tertiary block">EV Confidence</span>
                <span className={`font-semibold ${stabilityColor}`}>
                  {dist.probabilityStability.evConfidenceLevel}
                </span>
              </div>
              <div>
                <span className="text-[10px] text-text-tertiary block">Stability-Adjusted EV</span>
                <span className={`font-semibold ${dist.probabilityStability.stabilityAdjustedEV > 0 ? 'text-success/70' : 'text-error'}`}>
                  {dist.probabilityStability.stabilityAdjustedEV > 0 ? '+' : ''}{dist.probabilityStability.stabilityAdjustedEV.toFixed(2)}%
                </span>
              </div>
              <div>
                <span className="text-[10px] text-text-tertiary block">EV Uncertainty Band</span>
                <span className="font-medium text-text-secondary text-[10px] font-mono">
                  [{dist.probabilityStability.evBandLow > 0 ? '+' : ''}{dist.probabilityStability.evBandLow.toFixed(1)}%, {dist.probabilityStability.evBandHigh > 0 ? '+' : ''}{dist.probabilityStability.evBandHigh.toFixed(1)}%]
                </span>
              </div>
            </div>
          </div>

          {/* Module 7 + 3: Stop risk detail with vol context */}
          <div className="rounded-md border border-border/40 p-2.5 space-y-2">
            <div className="flex items-center justify-between">
              <span className="text-[10px] font-semibold uppercase tracking-wider text-text-tertiary/70">
                Stop Trigger Model
              </span>
              {dist.stopTailRiskFlag && (
                <span className="text-[10px] font-semibold text-error bg-error/10 px-1.5 py-0.5 rounded">
                  Tail Risk Elevated
                </span>
              )}
            </div>
            <div>
              <div className="flex items-center justify-between mb-1">
                <span className="text-xs text-text-tertiary">Stop Trigger Probability</span>
                <span className={`text-xs font-semibold ${dist.stopTailRiskFlag ? 'text-error' : 'text-text-secondary'}`}>
                  {probBand(dist.stopTriggerProb)} ({clampProb(dist.stopTriggerProb)})
                </span>
              </div>
              {/* Minimal probability bar — institutional, not gamified */}
              <div className="h-1 bg-surface-elevated rounded-full overflow-hidden">
                <div
                  className={`h-full rounded-full transition-all ${dist.stopTailRiskFlag ? 'bg-error/50' : 'bg-border/60'}`}
                  style={{ width: `${stopBarWidth}%` }}
                />
              </div>
              <div className="flex justify-between text-[9px] text-text-tertiary/40 mt-0.5">
                <span>0%</span>
                <span>Typical range: 15–35%</span>
                <span>80%+</span>
              </div>
            </div>
            {/* Module 7: Volatility regime context */}
            <div className="grid grid-cols-3 gap-2 text-xs pt-1 border-t border-border/30">
              <div>
                <span className="text-[10px] text-text-tertiary block">Volatility State</span>
                <span className={`font-medium ${volStateColor}`}>
                  {dist.volatilityContext.state}
                </span>
              </div>
              <div>
                <span className="text-[10px] text-text-tertiary block">Vol Percentile</span>
                <span className="font-medium text-text-secondary">
                  {dist.volatilityContext.percentile}th
                </span>
              </div>
              <div>
                <span className="text-[10px] text-text-tertiary block">Regime Modifier</span>
                <span className={`font-medium ${dist.volatilityContext.regimeModifierActive ? 'text-warning' : 'text-text-tertiary'}`}>
                  {dist.volatilityContext.regimeModifierActive ? 'Active' : 'Inactive'}
                </span>
              </div>
            </div>
            <div className="text-[10px] text-text-tertiary leading-relaxed">
              <span className="text-text-secondary">Expected Drawdown Path: </span>
              {dist.expectedDrawdownPath}
            </div>
          </div>

          {/* Module 8: Cross-Universe Benchmarking */}
          <div className="rounded-md border border-border/40 bg-surface/30 px-3 py-2.5 space-y-1.5">
            <p className="text-[10px] font-semibold uppercase tracking-wider text-text-tertiary/70">
              Universe Context
            </p>
            <div className="grid grid-cols-4 gap-2 text-xs">
              <div>
                <span className="text-[10px] text-text-tertiary block">EV Rank (Calibrated)</span>
                <span className="font-medium text-text-secondary">
                  {dist.universePercentiles.evPercentile}th pctile
                </span>
              </div>
              <div>
                <span className="text-[10px] text-text-tertiary block">Risk Eff. Rank</span>
                <span className="font-medium text-text-secondary">
                  {dist.universePercentiles.riskEfficiencyPercentile}th pctile
                </span>
              </div>
              <div>
                <span className="text-[10px] text-text-tertiary block">Stop Risk Rank</span>
                <span className="font-medium text-text-secondary">
                  {dist.universePercentiles.stopRiskPercentile}th pctile
                </span>
              </div>
              <div>
                <span className="text-[10px] text-text-tertiary block">Skew Rank</span>
                <span className="font-medium text-text-secondary">
                  {dist.universePercentiles.payoffSkewPercentile}th pctile
                </span>
              </div>
            </div>
            <p className="text-[9px] text-text-tertiary/50 italic leading-relaxed">
              Ranked vs. calibrated reference distribution — not a live cross-sectional universe.
              EV Rank calibrated on typical EV range: −5% to +15%.
              Higher = more favorable relative to typical institutional setup parameters.
              Stop Risk rank: higher = lower relative stop risk.
            </p>
          </div>

          {/* Module 4: Risk efficiency detail */}
          <div className="text-[10px] text-text-tertiary/70 leading-relaxed italic border-t border-border/30 pt-2">
            <span className="font-medium text-text-tertiary not-italic">Volatility-Adjusted Expectation: </span>
            EV of {dist.ev > 0 ? '+' : ''}{dist.ev.toFixed(2)}% / expected vol of ±{dist.expectedVolatility.toFixed(1)}%
            {" "}= <span className={`font-semibold not-italic ${effColor}`}>{dist.riskEfficiency.toFixed(2)} return per unit of risk</span>.
            {" "}Typical institutional threshold: ≥0.30.
          </div>
        </div>
      )}
    </div>
  )
}


// ──────────────────────────────────────────────────────────────────────────────
// Module 7: Model Transparency Panel
// Expandable institutional-grade explanation of all probability derivation logic.
// ──────────────────────────────────────────────────────────────────────────────

function ModelTransparencyPanel() {
  const [open, setOpen] = useState(false)
  return (
    <div className="border border-border/40 rounded-md overflow-hidden">
      <button
        onClick={() => setOpen(v => !v)}
        className="w-full px-3 py-2 flex items-center justify-between text-left bg-surface-elevated/30 hover:bg-surface-elevated/50 transition-colors"
      >
        <span className="text-[11px] font-semibold text-text-tertiary uppercase tracking-wider">
          Model Construction Logic
        </span>
        <span className="text-[10px] text-text-tertiary/60">{open ? '▲ Collapse' : '▼ Expand'}</span>
      </button>
      {open && (
        <div className="px-4 py-3 space-y-3 text-[11px] text-text-tertiary leading-relaxed bg-surface/20">
          <div>
            <p className="font-semibold text-text-secondary mb-1">Probability Derivation</p>
            <p>
              Each outcome probability is derived from{' '}
              <span className="font-medium text-text-secondary">P_i = BaseProbability × DistanceFactor × TrendFactor × ConflictFactor</span>.
              DistanceFactor uses exponential decay (e^−d/2ATR) where ATR is proxied as the stop distance.
              All raw scores are normalized to sum to 1.0. Base probabilities: Stop 22%, T1 38%, T2 26%,
              T3 10%, T4 4% — adjusted by regime and signal state before normalization.
            </p>
          </div>
          <div>
            <p className="font-semibold text-text-secondary mb-1">EV Computation</p>
            <p>
              EV = Σ(P_i × R_i) where R_i is the return of each scenario as a percentage of entry price.
              Expected Gain aggregates positive contributions; Expected Loss is the absolute value of
              the stop contribution. Payoff Skew = Expected Gain / Expected Loss.
            </p>
          </div>
          <div>
            <p className="font-semibold text-text-secondary mb-1">Stop Probability Framework</p>
            <p>
              P(StopHit) = BaseStopRisk × VolatilityPressure × TrendModifier × SupportModifier.
              Base: 20%. VolatilityPressure normalized to 1.0 (stop ≈ 1 ATR by construction).
              TrendModifier: MOMENTUM 0.75×, DISTRESSED 1.38×, STANDARD 1.0×.
              SupportModifier: active signal divergence adds 1.25×. Output is capped at 82%.
            </p>
          </div>
          <div>
            <p className="font-semibold text-text-secondary mb-1">Risk Efficiency (EV / Vol)</p>
            <p>
              Expected Volatility = √(E[R²] − E[R]²) — standard deviation of the probability-weighted
              return distribution. Risk Efficiency = EV / ExpectedVolatility. A ratio ≥0.30 indicates
              positive expected return per unit of outcome dispersion. This is not Sharpe ratio — it
              does not use historical price data.
            </p>
          </div>
          <div>
            <p className="font-semibold text-text-secondary mb-1">Regime Overrides</p>
            <p>
              MOMENTUM regime: stop probability reduced 28%, target probabilities lifted 8%.
              DISTRESSED regime: stop probability lifted 42%, target probabilities compressed 26%.
              High signal divergence (has_divergence=true): stop lifted 22–38%, targets compressed 13%.
              These are heuristic multipliers — not calibrated from price history.
            </p>
          </div>
          <div>
            <p className="font-semibold text-text-secondary mb-1">Factor Approximations</p>
            <p>
              Beta estimates use sector proxies (Technology 1.30, Healthcare 0.82, etc.).
              Stock volatility is approximated as stop distance × 4 (annualization heuristic).
              Volatility contribution = position weight × stock volatility. No covariance matrix is used.
              These are order-of-magnitude estimates for portfolio context, not precision factor models.
            </p>
          </div>
          <p className="text-[10px] text-text-tertiary/50 italic border-t border-border/30 pt-2">
            All probability estimates are model-derived heuristics. No historical calibration or
            backtesting has been performed. Results should be treated as analytical framing aids,
            not realized probability forecasts.
          </p>
        </div>
      )}
    </div>
  )
}

function SetupColumn({
  side,
  variant,
  signalBreakdown,
  rating,
  holdingPeriod,
  currentPrice,
  isDeepEntry,
  structuralFairValue,
  opportunityEnvelopeLow,
  regimeMode,
  momentumRegimeWarning,
}: {
  side: TradeSetupSide
  variant: 'conservative' | 'aggressive'
  signalBreakdown?: SignalBreakdown | null
  rating?: string | null
  holdingPeriod?: string | null
  currentPrice?: number
  isDeepEntry?: boolean
  structuralFairValue?: number | null
  opportunityEnvelopeLow?: number | null
  regimeMode?: 'STANDARD' | 'MOMENTUM' | 'DISTRESSED' | null
  momentumRegimeWarning?: string | null
}) {
  const isMomentumRegime = regimeMode === 'MOMENTUM'

  // Fix 2: Deep entry (structural reversion) uses visually subordinate styling — muted border and lighter treatment
  // In MOMENTUM regime, both cards get the momentum warning treatment instead
  const borderColor = isMomentumRegime
    ? 'border-amber-500/40'
    : isDeepEntry
      ? 'border-border'
      : variant === 'conservative' ? 'border-success/30' : 'border-warning/30'
  const headerBg = isMomentumRegime
    ? 'bg-amber-500/5'
    : isDeepEntry
      ? 'bg-surface-elevated/40'
      : variant === 'conservative' ? 'bg-success/5' : 'bg-warning/5'

  const hasHighDivergence = signalBreakdown?.has_divergence === true

  // Module 1–4: Probability inputs — derive bearish signal count for conflict factor
  const bearishSignalCount = signalBreakdown
    ? [
        signalBreakdown.news_score,
        signalBreakdown.earnings_score,
        signalBreakdown.analyst_score,
        signalBreakdown.institutional_score,
        signalBreakdown.insider_score,
      ].filter((s): s is number => s != null && s < 4).length
    : 0

  const outcomeDistribution = computeOutcomeDistribution({
    entry: side.entry,
    stopLoss: side.stop_loss,
    targets: side.targets,
    regimeMode,
    hasDivergence: hasHighDivergence,
    bearishSignalCount,
    signalSpread: signalBreakdown?.signal_spread ?? 1.5,  // Module 9: stability input
  })

  // Conditional qualifier takes precedence over pure realism qualifier
  const { label: conditionalLabel, footnote: conditionalFootnote } = getRRConditionalQualifier(
    side.risk_reward,
    signalBreakdown,
    rating
  )
  const { qualifier: realismQualifier, footnote: realismFootnote } = getRRRealism(
    side.risk_reward,
    hasHighDivergence
  )

  const displayQualifier = conditionalLabel ?? realismQualifier
  const displayFootnote = conditionalFootnote ?? realismFootnote

  // Soften R/R badge under HOLD or signal conflict — prevents promotional read
  const isHoldRating = rating === 'HOLD'
  const showSoftRR = isHoldRating || conditionalLabel !== null
  const rrVariant = showSoftRR
    ? 'secondary' as const
    : (variant === 'conservative' ? 'success' as const : 'warning' as const)

  // Informational time-normalized R/R — prevents conflating long-horizon ratio with short-term expectancy
  const annualizedRR = getAnnualizedRREq(side.risk_reward, holdingPeriod)

  // H2: Weighted realized R/R using staged sell percentages (30/40/30 or 33/34/33)
  const weightedRR = getWeightedRealizedRR(side.entry, side.stop_loss, side.targets)

  // Proximity warning based on current price relative to stop loss
  const proximityWarning = getProximityWarning(currentPrice, side.stop_loss, side.entry)

  // Horizon-bound gain: realistic 12-month outcome from primary window targets only.
  // Extended / regime expansion targets are excluded and demoted to "tail outcome" framing.
  const horizonBoundGain = computeHorizonBoundGain(side.entry, side.targets)

  // FIX 2 + FIX 4: Compressed asymmetry callout — shown when rr < 2.5 for BUY/STRONG BUY.
  // Quantifies the improvement in risk/reward at the preferred entry zone, giving users a
  // concrete mathematical reason to wait rather than a qualitative recommendation.
  const isCompressedAsymmetry =
    !isDeepEntry &&
    side.risk_reward < 2.5 &&
    (rating === 'BUY' || rating === 'STRONG BUY')

  const t2Price = side.targets[1]?.price ?? null
  const rrAtIdeal =
    isCompressedAsymmetry && opportunityEnvelopeLow != null && t2Price != null
      ? calcRRAtEntry(opportunityEnvelopeLow, side.entry, side.stop_loss, t2Price)
      : null

  // FIX 4: Momentum regime asymmetry — for conservative card, expose structural anchor R/R separately.
  // The high R/R on the conservative card is FROM the structural anchor entry (e.g., $59), not from
  // the current price ($248). Display both so users understand the distinction.
  const showMomentumAsymmetry = isMomentumRegime && variant === 'conservative'
  const rrFromCurrent = side.asymmetry_from_current_price ?? null
  const structuralAnchorPrice = side.structural_anchor_price ?? null

  // Pre-classify each target before rendering to drive scenario branching + exclusion logic
  const targetValidities: TargetValidity[] = side.targets.map(t =>
    classifyTargetValidity(t, currentPrice, regimeMode, isDeepEntry ?? false)
  )

  // Sort targets by T-number in label (T1 < T2 < T3 < T4) for display — preserves correct
  // sequence regardless of the price order the backend emits them in. All logic functions
  // (inferTargetHorizon, isExtendedTarget, etc.) continue to use originalIndex so
  // label-matching and index-fallback behaviour is preserved exactly.
  function extractTargetNumber(label: string, fallbackIndex: number): number {
    const match = label.match(/^[Tt](\d+)/)
    return match ? parseInt(match[1]) : fallbackIndex + 1
  }
  const sortedTargetData = side.targets
    .map((t, i) => ({ t, validity: targetValidities[i], originalIndex: i }))
    .sort((a, b) =>
      extractTargetNumber(a.t.label, a.originalIndex) - extractTargetNumber(b.t.label, b.originalIndex)
    )

  // ── Entry Architecture — Institutional Multi-Anchor Framework ────────────────
  // ATR proxy: stop distance approximates 1 ATR (by construction in the backend).
  const atrProxy = Math.abs(side.entry - side.stop_loss)

  // Tactical Entry Zone: volatility-responsive execution band around the modeled entry.
  // Derived purely from existing ATR proxy — no new math.
  const tacticalLow = side.entry - atrProxy * 0.45
  const tacticalHigh = side.entry + atrProxy * 0.2
  const tacticalZoneDisplay = `${formatAnchor(tacticalLow)} – ${formatAnchor(tacticalHigh)}`

  // Liquidity Support Region: opportunity envelope floor as the volume-weighted acceptance zone.
  // Only shown when it sits meaningfully below the structural entry (≥3% discount).
  const liquidityAnchorPrice =
    opportunityEnvelopeLow != null && opportunityEnvelopeLow < side.entry * 0.97
      ? opportunityEnvelopeLow
      : null

  // C2: Setup unavailable state — show instead of normal setup when risk buffer is insufficient
  const setupUnavailable = side.setup_unavailable

  if (setupUnavailable) {
    return (
      <div className={`rounded-lg border ${borderColor} overflow-hidden`}>
        <div className={`px-4 py-3 ${headerBg}`}>
          <span className="text-sm font-semibold text-text-primary">
            {side.label.replace('Recommended', 'Model-Optimal')}
          </span>
        </div>
        <div className="p-4">
          <div className="rounded-md bg-warning/10 border border-warning/30 p-3 text-xs text-warning leading-relaxed">
            <span className="font-semibold block mb-1">Setup Unavailable — Insufficient Risk Buffer</span>
            <span className="text-text-secondary">{setupUnavailable}</span>
          </div>
        </div>
      </div>
    )
  }

  // Fix 5: all primary targets above structural FV → targets are in market regime, not anchored to FV
  const allTargetsAboveStructuralFV =
    structuralFairValue != null &&
    structuralFairValue > 0 &&
    side.targets.length > 0 &&
    side.targets.every(t => t.price > structuralFairValue)

  // Detect when T3 (fundamental anchor) < T2 (analyst consensus) — valid in MOMENTUM regime
  // where sell-side consensus overshoots the model's intrinsic estimate.
  const t2Entry = sortedTargetData.find(({ t }) => extractTargetNumber(t.label, 0) === 2)
  const t3Entry = sortedTargetData.find(({ t }) => extractTargetNumber(t.label, 0) === 3)
  const hasConsensusAboveFundamental =
    t2Entry != null &&
    t3Entry != null &&
    t3Entry.t.price < t2Entry.t.price &&
    t2Entry.validity === 'VALID' &&
    t3Entry.validity === 'VALID'

  return (
    <div className={`rounded-lg border ${borderColor} overflow-hidden`}>
      {/* FIX 1: Momentum Regime banner — shown on BOTH cards when price > 150% of fair value */}
      {isMomentumRegime && momentumRegimeWarning && (
        <div className="px-4 pt-3 pb-0">
          <div className="rounded-md bg-amber-500/10 border border-amber-500/30 p-2.5 text-xs leading-relaxed">
            <span className="font-semibold text-amber-400 block mb-0.5">
              {momentumRegimeWarning}
            </span>
          </div>
        </div>
      )}
      {/* Fix 4: Deep Value Entry warning — shown when entry is far below current market price (STANDARD mode only) */}
      {isDeepEntry && !isMomentumRegime && (
        <div className="px-4 pt-3 pb-0">
          <div className="rounded-md bg-warning/8 border border-warning/25 p-2.5 text-xs leading-relaxed">
            <span className="font-semibold text-warning block mb-0.5">
              Deep Value Entry — Structural Reversion Scenario
            </span>
            <span className="text-text-tertiary">
              This setup anchors to the structural value zone ({formatAnchor(side.entry)}), which is{' '}
              {currentPrice ? Math.round(((currentPrice - side.entry) / currentPrice) * 100) : '—'}%
              below current market price. Not actionable at current levels — only becomes relevant
              during a significant market dislocation. See the aggressive setup for the
              regime-anchored position.
            </span>
          </div>
        </div>
      )}
      {/* FIX 2 + FIX 4: Compressed asymmetry callout */}
      {isCompressedAsymmetry && (
        <div className="px-4 pt-3 pb-0">
          <div className="rounded-md bg-amber-500/8 border border-amber-500/25 p-2.5 text-xs leading-relaxed">
            <span className="font-semibold text-amber-400 block mb-1">
              ⚠ Compressed Asymmetry ({side.risk_reward}:1) — Staged Entry Preferred
            </span>
            <span className="text-text-tertiary">
              Entry near the Structural Valuation Reference compresses near-term asymmetry. Asymmetry improves
              significantly at preferred entry zones:
            </span>
            {rrAtIdeal != null && opportunityEnvelopeLow != null && (
              <div className="mt-1.5 space-y-0.5">
                <div className="flex items-center justify-between">
                  <span className="text-text-tertiary">
                    Entry at ~${Math.round(opportunityEnvelopeLow).toLocaleString()} (preferred zone)
                  </span>
                  <span className="font-semibold text-text-secondary ml-2">
                    est. {rrAtIdeal}:1
                  </span>
                </div>
                <p className="text-text-tertiary/70 italic mt-1">
                  Staged entry toward support improves the T2 risk-reward from {side.risk_reward}:1
                  to ~{rrAtIdeal}:1 — a meaningful improvement in probability-weighted outcome for
                  the same underlying thesis.
                </p>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Header */}
      <div className={`px-4 py-3 ${headerBg} ${isDeepEntry || isCompressedAsymmetry ? 'mt-2' : ''}`}>
        {/* Row 1: Label + R/R badge on same line */}
        <div className="flex items-start justify-between gap-2">
          <div className="min-w-0">
            <span className={`text-sm font-semibold leading-tight ${isDeepEntry ? 'text-text-tertiary' : 'text-text-primary'}`}>
              {isDeepEntry
                ? 'Structural Reversion — Conditional Setup'
                : side.label.replace('Recommended', 'Model-Optimal')
              }
            </span>
            {/* Fix 2: Subtitle clarifying non-primary nature of structural reversion card */}
            {isDeepEntry && (
              <p className="text-[10px] text-text-tertiary/70 leading-tight mt-0.5">
                Only actionable during significant market dislocation. Not a primary recommendation at current prices.
              </p>
            )}
          </div>
          <Badge
            variant={rrVariant}
            className={`shrink-0 text-xs ${showSoftRR ? 'opacity-75 font-normal' : ''}`}
          >
            Modeled Asymmetry ({side.risk_reward}:1)
          </Badge>
        </div>

        {/* Row 2: Qualifier badge + time-normalized R/R + weighted R/R */}
        {(displayQualifier || annualizedRR || weightedRR) && (
          <div className="flex items-center gap-2 mt-1.5 flex-wrap">
            {displayQualifier && (
              <Badge variant="secondary" className="text-xs font-normal opacity-80">
                {displayQualifier}
              </Badge>
            )}
            {annualizedRR && (
              <span className="text-[10px] text-text-tertiary/70 italic">
                Horizon-Normalized: {annualizedRR} ann. equiv.
              </span>
            )}
            {weightedRR !== null && (
              <span className="text-[10px] text-text-tertiary/70 italic">
                · Weighted Realized: {weightedRR}:1
              </span>
            )}
          </div>
        )}

        {/* FIX 4: Dual asymmetry display for conservative card in MOMENTUM regime.
            The modeled R/R is from the structural anchor (e.g., $59), NOT from current price.
            Show both so users understand the distinction. */}
        {showMomentumAsymmetry && structuralAnchorPrice != null && (
          <div className="mt-2 pt-2 border-t border-amber-500/20 text-[10px] text-text-tertiary leading-relaxed space-y-1">
            <div className="flex items-center justify-between">
              <span>Asymmetry from structural anchor ({formatAnchor(structuralAnchorPrice)})</span>
              <span className="font-semibold text-text-secondary ml-2">{side.risk_reward}:1 — Valuation-dependent setup</span>
            </div>
            <div className="flex items-center justify-between">
              <span>Asymmetry from current price</span>
              <span className={`font-semibold ml-2 ${rrFromCurrent != null && rrFromCurrent > 0 ? 'text-text-secondary' : 'text-error/70'}`}>
                {rrFromCurrent != null && rrFromCurrent > 0
                  ? `${rrFromCurrent}:1`
                  : 'N/A — targets below current price'
                }
              </span>
            </div>
          </div>
        )}

        {/* Footnote */}
        {displayFootnote && (
          <p className="text-xs text-text-tertiary mt-1.5 leading-relaxed">{displayFootnote}</p>
        )}
      </div>

      {/* Body */}
      <div className="p-4 space-y-3">
        {/* Entry Architecture — Institutional Multi-Anchor Framework */}
        <div className="space-y-2">

          {/* 1️⃣ Tactical Entry Zone — PRIMARY (highest visual weight, execution-aware) */}
          <div className="rounded-md bg-primary/5 border border-primary/20 px-3 py-2">
            <span className="text-[10px] font-semibold text-primary/70 uppercase tracking-wide block">
              Tactical Entry Zone
            </span>
            <span className="text-sm font-bold text-text-primary">{tacticalZoneDisplay}</span>
            <span className="text-[10px] text-text-tertiary block mt-0.5">
              Volatility-responsive execution range · Short-horizon
            </span>
          </div>

          {/* 2️⃣ Liquidity Support Region — SECONDARY (flow anchor, shown when meaningfully below entry) */}
          {liquidityAnchorPrice && (
            <div className="rounded-md bg-surface-elevated border border-border px-3 py-2">
              <span className="text-[10px] text-text-tertiary/70 uppercase tracking-wide block">
                Liquidity Support Region
              </span>
              <span className="text-sm font-semibold text-text-secondary">
                {formatAnchor(liquidityAnchorPrice)}
              </span>
              <span className="text-[10px] text-text-tertiary/60 block mt-0.5">
                Volume-weighted acceptance zone
              </span>
            </div>
          )}

          {/* 3️⃣ Structural Entry + Risk Control — TERTIARY (contextual / subdued) */}
          <div className="grid grid-cols-2 gap-3 pt-0.5">
            <div>
              <span className="text-[10px] text-text-tertiary/60 block">
                Structural Entry (Mean Reversion Basis)
              </span>
              <span className="text-sm text-text-tertiary">{formatAnchor(side.entry)}</span>
              <span className="text-[10px] text-text-tertiary/50 block mt-0.5">
                Valuation-dependent setup · Long-horizon
              </span>
            </div>
            <div>
              <span className="text-xs text-text-tertiary block">Risk Control Zone</span>
              <span className="text-sm font-semibold text-error">
                {formatAnchor(side.stop_loss)}
              </span>
              {proximityWarning && (
                <span className="text-[10px] text-warning block mt-0.5 leading-tight">
                  {proximityWarning}
                </span>
              )}
            </div>
          </div>

        </div>

        {/* Target Validation + Scenario-Branched Rendering
            VALID primary (T1/T2/T3) → Profit Targets.
            VALID extended (T4) → Expansion Scenario block with separator.
            NOT_APPLICABLE (price ≤ current price) → silently excluded.
            REFERENCE_ONLY (structural targets in MOMENTUM regime) → Structural References.
            SUPPRESSED (backend-flagged) → existing suppression UI. */}
        <div className="space-y-2">
          <div className="flex items-center justify-between">
            <span className="text-xs text-text-tertiary">Profit Targets</span>
            {holdingPeriod && (
              <span className="text-xs text-text-tertiary">
                Holding period: <span className="font-medium text-text-secondary">{holdingPeriod}</span>
              </span>
            )}
          </div>

          {/* Primary scenario: T1 / T2 / T3 — non-extended, actionable targets */}
          {sortedTargetData.every(({ validity }) =>
            validity === 'NOT_APPLICABLE' || validity === 'REFERENCE_ONLY'
          ) && (
            <p className="text-xs text-text-tertiary italic py-1">No actionable targets above current price.</p>
          )}

          {sortedTargetData.map(({ t, validity, originalIndex: i }) => {
            // Exclude non-actionable — silently skip
            if (validity === 'NOT_APPLICABLE') return null
            // Reference-only rendered below
            if (validity === 'REFERENCE_ONLY') return null
            // Extended targets rendered in Expansion Scenario block below
            if (isExtendedTarget(t.label, i)) return null

            const horizon = isDeepEntry
              ? (i === 0 ? '12–24 mo' : '24–36 mo')
              : inferTargetHorizon(t.label, i)
            const targetType = inferTargetType(t.label, i)
            const conditionality = inferTargetConditionality(t.label, i, rating, variant)
            const sanitizedLabel = sanitizeTargetLabel(t.label)

            if (validity === 'SUPPRESSED') {
              return (
                <div key={i} className="rounded px-2 py-1.5 text-xs bg-surface-elevated/40 border border-border/40">
                  <div className="flex items-center gap-1.5 mb-0.5">
                    <span className="text-text-tertiary">{sanitizedLabel}</span>
                    <span className="bg-surface-elevated text-text-tertiary/70 text-[10px] px-1.5 py-0.5 rounded font-semibold">Inactive in Current Regime</span>
                  </div>
                  <p className="text-text-tertiary/60 leading-relaxed">
                    {t.suppression_reason ?? 'Target inactive in current market regime.'}
                  </p>
                </div>
              )
            }

            return (
              <div key={i} className="rounded px-2 py-1.5 text-sm">
                <div className="flex flex-wrap items-center justify-between gap-x-2 gap-y-1">
                  <div className="flex items-center gap-1.5 min-w-0">
                    <span className="text-text-secondary">{sanitizedLabel}</span>
                    <span className="text-xs px-1.5 py-0.5 rounded font-mono shrink-0 bg-primary/10 text-primary/70">{horizon}</span>
                  </div>
                  <div className="flex items-center gap-1.5 shrink-0">
                    <span className="font-medium text-success">{formatCurrency(t.price)}</span>
                    {t.sell_pct > 0
                      ? <span className="text-xs text-text-tertiary">Sell {t.sell_pct}%</span>
                      : <span className="text-xs text-text-tertiary/50 italic">Extended</span>
                    }
                  </div>
                </div>
                <div className="flex items-center gap-1.5 mt-0.5">
                  <span className="text-[11px] text-text-tertiary">{targetType} Target</span>
                  {conditionality && (
                    <span className="text-[10px] text-text-tertiary/60 italic">— {conditionality}</span>
                  )}
                </div>
              </div>
            )
          })}

          {/* Consensus-above-fundamental note — shown when T2 (analyst consensus) > T3 (intrinsic anchor).
              Valid in MOMENTUM regime: near-term sell-side optimism exceeds the model's fundamental estimate. */}
          {hasConsensusAboveFundamental && t2Entry && t3Entry && (
            <div className="rounded-md bg-primary/5 border border-primary/15 px-3 py-2 text-[10px] text-text-tertiary leading-relaxed">
              <span className="font-medium text-text-secondary block mb-1">T3 below T2 — Consensus Overshoots Fundamental Anchor</span>
              <span>
                <span className="font-medium text-text-secondary">T2 ({formatCurrency(t2Entry.t.price)})</span>
                {' '}reflects the near-term sell-side consensus — where analysts expect the stock to trade in 6–12 months, driven by momentum and sentiment.
              </span>
              <span className="block mt-1">
                <span className="font-medium text-text-secondary">T3 ({formatCurrency(t3Entry.t.price)})</span>
                {' '}is the model&rsquo;s base-case fundamental re-rating anchor for the 12–24 month horizon, derived from intrinsic valuation. It sits below T2 because the model assesses the consensus as pricing in more optimism than fundamentals currently support — not a predicted price drop, but a signal that the stock may overshoot consensus before normalizing toward fundamental value.
              </span>
            </div>
          )}

          {/* Expansion Scenario — T4 / Regime Expansion, visually separated from primary */}
          {sortedTargetData.some(({ t, validity, originalIndex: i }) => validity === 'VALID' && isExtendedTarget(t.label, i)) && (
            <>
              <div className="flex items-center gap-2 pt-1">
                <span className="text-[10px] font-semibold text-text-tertiary/60 uppercase tracking-wide">Expansion Scenario</span>
                <div className="flex-1 h-px bg-border/40" />
              </div>
              {sortedTargetData.map(({ t, validity, originalIndex: i }) => {
                if (validity !== 'VALID' || !isExtendedTarget(t.label, i)) return null
                const horizon = inferTargetHorizon(t.label, i)
                const targetType = inferTargetType(t.label, i)
                const conditionality = inferTargetConditionality(t.label, i, rating, variant)
                const sanitizedLabel = sanitizeTargetLabel(t.label)
                const dimExtra = rating === 'HOLD'
                return (
                  <div key={i} className={`rounded px-2 py-1.5 text-sm bg-surface-elevated/60 ${dimExtra ? 'opacity-50' : ''}`}>
                    <div className="flex flex-wrap items-center justify-between gap-x-2 gap-y-1">
                      <div className="flex items-center gap-1.5 min-w-0">
                        <span className="text-text-tertiary">{sanitizedLabel}</span>
                        <span className="text-xs px-1.5 py-0.5 rounded font-mono shrink-0 bg-surface-elevated text-text-tertiary">{horizon}</span>
                      </div>
                      <div className="flex items-center gap-1.5 shrink-0">
                        <span className="font-medium text-success/60">{formatCurrency(t.price)}</span>
                        {t.sell_pct > 0
                          ? <span className="text-xs text-text-tertiary">Sell {t.sell_pct}%</span>
                          : <span className="text-xs text-text-tertiary/50 italic">Extended</span>
                        }
                      </div>
                    </div>
                    <div className="flex items-center gap-1.5 mt-0.5">
                      <span className="text-[11px] text-text-tertiary">{targetType} Target</span>
                      {conditionality && (
                        <span className="text-[10px] text-text-tertiary/60 italic">— {conditionality}</span>
                      )}
                    </div>
                  </div>
                )
              })}
              <p className="text-[10px] text-text-tertiary/60 leading-relaxed italic">
                Expansion Scenario targets extend beyond the primary holding window — conditional on thesis validation and sustained macro regime.
              </p>
            </>
          )}

          {/* Structural References — MOMENTUM regime only; not actionable at current price */}
          {sortedTargetData.some(({ validity }) => validity === 'REFERENCE_ONLY') && (
            <div className="pt-2 border-t border-border/40">
              <p className="text-[10px] font-semibold text-text-tertiary/60 uppercase tracking-wide mb-1.5">Structural References</p>
              {sortedTargetData.map(({ t, validity, originalIndex }) => {
                if (validity !== 'REFERENCE_ONLY') return null
                const sanitizedLabel = sanitizeTargetLabel(t.label)
                return (
                  <div key={originalIndex} className="rounded px-2 py-1.5 text-xs bg-surface-elevated/30 opacity-70">
                    <div className="flex items-center justify-between">
                      <span className="text-text-tertiary">{sanitizedLabel}</span>
                      <span className="font-medium text-text-tertiary/70 font-mono">{formatCurrency(t.price)}</span>
                    </div>
                    <p className="text-[10px] text-text-tertiary/50 mt-0.5 italic">
                      Mean-reversion reference — not actionable in current momentum regime
                    </p>
                  </div>
                )
              })}
            </div>
          )}

          {/* Context footnotes */}
          {isDeepEntry && (
            <p className="text-[11px] text-text-tertiary/80 pt-1.5 leading-relaxed border-t border-border/50 italic">
              Targets calculated from structural entry — not comparable to market-regime setup targets.
            </p>
          )}
          {allTargetsAboveStructuralFV && !isDeepEntry && (
            <p className="text-[10px] text-text-tertiary/70 pt-1 italic leading-relaxed">
              Targets reflect current market pricing path — not anchored to the Structural Valuation Reference.
            </p>
          )}
        </div>

        {/* Outcome distribution bounds — primary window gain is the headline figure.
            Regime expansion ceiling is demoted to tail outcome framing to prevent
            lottery-like perception of low-probability extended scenarios. */}
        <div className="border-t border-surface-elevated pt-3">
          <span className="text-[10px] text-text-tertiary/60 block mb-1.5 italic">
            Outcome distribution bounds — 100 shares at anchor price.
          </span>
          <div className="grid grid-cols-2 gap-2 text-xs">
            <div>
              <span className="text-text-tertiary block">Stop-Out Exposure / 100 sh</span>
              <span className="font-medium text-error">{formatCurrency(side.max_loss_per_100)}</span>
              <span className="text-[10px] text-text-tertiary/60 block">If Stop Triggered</span>
            </div>
            <div>
              {horizonBoundGain !== null && horizonBoundGain > 0 ? (
                <>
                  <span className="text-text-tertiary block">Horizon-Bound Gain / 100 sh</span>
                  <span className="font-medium text-success">{formatCurrency(horizonBoundGain)}</span>
                  <span className="text-[10px] text-text-tertiary/60 block">Primary Holding Window</span>
                  <span className="text-[10px] text-text-tertiary/40 block mt-1 italic">
                    Tail ceiling: {formatCurrency(side.max_gain_per_100)} — extended scenario, low probability
                  </span>
                </>
              ) : (
                <>
                  <span className="text-text-tertiary block">Upside Capture / 100 sh</span>
                  <span className="font-medium text-success">{formatCurrency(side.max_gain_per_100)}</span>
                  <span className="text-[10px] text-text-tertiary/60 block">Regime Expansion Ceiling</span>
                </>
              )}
            </div>
          </div>

          {/* Payoff vs probability clarifier — surfaces when signal conflict is active.
              Asymmetry magnitude is intact; path probability is reduced by divergence. */}
          {hasHighDivergence && side.risk_reward >= 3 && (
            <div className="mt-2 pt-2 border-t border-surface-elevated/50 text-[10px] text-text-tertiary leading-relaxed">
              <span className="font-medium text-text-secondary">Payoff Skew vs. Probability: </span>
              Structural asymmetry ({side.risk_reward}:1) reflects scenario payoff magnitude — not probability of achievement.
              Active signal conflict compresses near-term path probability; asymmetry is thesis-dependent, not probability-dominant.
            </div>
          )}
        </div>

        {/* Module 1–4: Probability-weighted outcome distribution + EV engine */}
        {outcomeDistribution && (
          <OutcomeDistributionPanel
            dist={outcomeDistribution}
            variant={variant}
          />
        )}
      </div>
    </div>
  )
}

export function TradeSetup({ setup, ticker: _ticker, strategy, signalBreakdown, rating, currentPrice, calibration, financialHealthScore }: TradeSetupProps) {
  const stopQuality = strategy?.exit?.stop_quality
  const stopAlignmentNote = strategy?.exit?.stop_alignment_note
  const stopZone = strategy?.exit?.stop_zone
  const stopMethodology = strategy?.exit?.stop_methodology
  const entryBelowBear = strategy?.entry?.entry_below_bear
  const entryBelowBearPct = strategy?.entry?.entry_below_bear_pct
  const belowBearClassification = strategy?.entry?.below_bear_classification
  const belowBearJustification = strategy?.entry?.below_bear_justification
  const originalIdealLow = strategy?.entry?.original_ideal_low

  const stopStyle = stopQuality ? STOP_QUALITY_STYLES[stopQuality] : undefined

  // Opportunity envelope — used for deep-entry detection below
  const opportunityEnvelope = strategy?.entry?.ideal_zone


  // Structural Premium Regime detection (Fix 2, 4, 5)
  const isStructuralPremium = detectStructuralPremium(calibration, currentPrice, financialHealthScore)
  const structuralFV = calibration?.internal_fair_value ?? null
  // Fix 4: conservative entry anchored to structural zone far below current price
  const isDeepConservativeEntry =
    isStructuralPremium &&
    currentPrice != null &&
    currentPrice > 0 &&
    setup.conservative.entry < currentPrice * 0.65

  return (
    <Card>
      <CardHeader>
        <CardTitle>Entry / Exit Setup</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">

        {/* Entry below bear case disclosure */}
        {entryBelowBear && belowBearJustification && (
          <ClampedEntryDisclosure
            classification={belowBearClassification}
            justification={belowBearJustification}
            belowBearPct={entryBelowBearPct}
            originalIdealLow={originalIdealLow}
          />
        )}

        {/* Issue 9: Entry Zone Taxonomy panel removed — information is surfaced in
            DecisionAction's Key Price Zones grid, which is always visible in the Tactical
            Framework section. Removing duplication reduces cognitive noise and improves
            vertical flow to the Conservative / Aggressive setup columns below. */}

        {/* Stop quality badge + alignment note */}
        {stopQuality && (
          <div className={`p-3 rounded-md border text-xs ${stopStyle?.badge ?? 'bg-surface-elevated border-border'}`}>
            <div className="flex items-center gap-2 mb-1">
              <span className="font-semibold">Stop Quality:</span>
              <span className={`font-bold ${stopStyle?.note ?? 'text-text-primary'}`}>
                {stopQuality}
              </span>
              {stopZone && (
                <span className="text-text-tertiary font-normal">
                  Zone: {stopZone.label}
                </span>
              )}
            </div>
            {stopAlignmentNote && (
              <p className="leading-relaxed text-text-secondary">{stopAlignmentNote}</p>
            )}
            {stopMethodology && (
              <p className="mt-1 text-text-tertiary leading-relaxed">{stopMethodology}</p>
            )}
          </div>
        )}

        {/* Fix 2: Structural Premium Regime context callout beneath the key price zones block */}
        {isStructuralPremium && (
          <p className="text-[11px] text-text-tertiary/70 leading-relaxed italic px-0.5">
            Structural Value Zone represents long-term mean-reversion basis. Current price reflects
            market-assigned growth premium. Tactical targets and stops operate within the current
            market pricing regime, not the structural zone.
          </p>
        )}

        {/* Regime Mode Banner — frames the anchor framework for both setup cards */}
        {setup.regime_mode && (
          <div className={`flex items-center gap-2 px-3 py-2 rounded-md text-xs border ${
            setup.regime_mode === 'MOMENTUM'
              ? 'bg-amber-500/8 border-amber-500/25 text-amber-400'
              : setup.regime_mode === 'DISTRESSED'
              ? 'bg-error/8 border-error/25 text-error'
              : 'bg-primary/8 border-primary/25 text-primary'
          }`}>
            <span className="font-semibold">
              {setup.regime_mode === 'MOMENTUM'
                ? 'Momentum Regime'
                : setup.regime_mode === 'DISTRESSED'
                ? 'Distressed Setup'
                : 'Structural Regime'}
            </span>
            <span className="opacity-50 mx-0.5">—</span>
            <span className="opacity-75">
              {setup.regime_mode === 'MOMENTUM'
                ? 'Targets anchored to current market price'
                : setup.regime_mode === 'DISTRESSED'
                ? 'Entry anchored at distressed support levels'
                : 'Targets anchored to intrinsic / structural entry'}
            </span>
          </div>
        )}

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <SetupColumn
            side={setup.conservative}
            variant="conservative"
            signalBreakdown={signalBreakdown}
            rating={rating}
            holdingPeriod={strategy?.exit?.holding_period}
            currentPrice={currentPrice}
            isDeepEntry={isDeepConservativeEntry}
            structuralFairValue={structuralFV}
            opportunityEnvelopeLow={opportunityEnvelope ? Math.min(opportunityEnvelope.low, opportunityEnvelope.high) : null}
            regimeMode={setup.regime_mode}
            momentumRegimeWarning={setup.momentum_regime_warning}
          />
          <SetupColumn
            side={setup.aggressive}
            variant="aggressive"
            signalBreakdown={signalBreakdown}
            rating={rating}
            holdingPeriod={strategy?.exit?.holding_period}
            currentPrice={currentPrice}
            structuralFairValue={structuralFV}
            opportunityEnvelopeLow={opportunityEnvelope ? Math.min(opportunityEnvelope.low, opportunityEnvelope.high) : null}
            regimeMode={setup.regime_mode}
            momentumRegimeWarning={setup.momentum_regime_warning}
          />
        </div>

        {/* Module 7: Model Construction Logic — expandable transparency panel */}
        <ModelTransparencyPanel />
      </CardContent>
    </Card>
  )
}
