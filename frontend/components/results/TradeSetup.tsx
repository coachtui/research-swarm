import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { formatCurrency } from '@/lib/utils/formatting'
import type { EnhancedTradeSetup, TradeSetupSide, RecommendedStrategy, SignalBreakdown, FairValueCalibration } from '@/types/api'

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

// Derive approximate time horizon from the target label (backend-supplied).
// Returns a short string for display. This is interpretive only — no calculation.
function inferTargetHorizon(label: string, index: number): string {
  const l = label.toLowerCase()
  if (l.includes('near') || l.includes('short') || l.includes('t1')) return '1–3 mo'
  if (l.includes('base') || l.includes('t2') || l.includes('mid')) return '6–12 mo'
  if (l.includes('bull') || l.includes('t3') || l.includes('stretch') || l.includes('extended') || l.includes('upside')) return '12–24 mo'
  // Fallback by position
  if (index === 0) return '1–3 mo'
  if (index === 1) return '6–12 mo'
  return '12–24 mo'
}

// Determine whether a target is within the primary holding period window.
// Targets beyond ~12 months are labelled as regime expansion scenarios.
function isExtendedTarget(label: string, index: number): boolean {
  const l = label.toLowerCase()
  if (l.includes('bull') || l.includes('stretch') || l.includes('extended') || l.includes('upside')) return true
  if (index >= 2) return true
  return false
}

// Classify target by analytical type for institutional-grade labeling.
// Extended targets use regime framing rather than promotional outcome language.
function inferTargetType(label: string, index: number): string {
  const l = label.toLowerCase()
  if (l.includes('bull') || l.includes('stretch') || l.includes('extended') || l.includes('upside') || index >= 2)
    return 'Regime Expansion'
  if (l.includes('near') || l.includes('t1') || l.includes('short') || index === 0)
    return 'Tactical Reversion'
  if (l.includes('base') || l.includes('t2') || l.includes('mid') || index === 1)
    return 'Momentum Continuation'
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

function SetupColumn({
  side,
  variant,
  signalBreakdown,
  rating,
  holdingPeriod,
  currentPrice,
  isDeepEntry,
  structuralFairValue,
}: {
  side: TradeSetupSide
  variant: 'conservative' | 'aggressive'
  signalBreakdown?: SignalBreakdown | null
  rating?: string | null
  holdingPeriod?: string | null
  currentPrice?: number
  isDeepEntry?: boolean
  structuralFairValue?: number | null
}) {
  // Fix 2: Deep entry (structural reversion) uses visually subordinate styling — muted border and lighter treatment
  const borderColor = isDeepEntry
    ? 'border-border'
    : variant === 'conservative' ? 'border-success/30' : 'border-warning/30'
  const headerBg = isDeepEntry
    ? 'bg-surface-elevated/40'
    : variant === 'conservative' ? 'bg-success/5' : 'bg-warning/5'

  const hasHighDivergence = signalBreakdown?.has_divergence === true

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

  return (
    <div className={`rounded-lg border ${borderColor} overflow-hidden`}>
      {/* Fix 4: Deep Value Entry warning — shown when entry is far below current market price */}
      {isDeepEntry && (
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
      {/* Header */}
      <div className={`px-4 py-3 ${headerBg} ${isDeepEntry ? 'mt-2' : ''}`}>
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

        {/* Footnote */}
        {displayFootnote && (
          <p className="text-xs text-text-tertiary mt-1.5 leading-relaxed">{displayFootnote}</p>
        )}
      </div>

      {/* Body */}
      <div className="p-4 space-y-3">
        {/* Entry & Stop */}
        <div className="grid grid-cols-2 gap-3">
          <div>
            <span className="text-xs text-text-tertiary block">Execution Anchor</span>
            <span className="text-sm font-semibold text-text-primary">
              {formatAnchor(side.entry)}
            </span>
            <span className="text-xs text-text-tertiary block mt-0.5">
              Modeled entry — scale in or await pullback
            </span>
          </div>
          <div>
            <span className="text-xs text-text-tertiary block">Stop Loss</span>
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

        {/* Targets — precise prices are defined objectives, not estimates.
            Two-line layout prevents label truncation at normal breakpoints. */}
        <div className="space-y-2">
          <div className="flex items-center justify-between">
            <span className="text-xs text-text-tertiary">Profit Targets</span>
            {holdingPeriod && (
              <span className="text-xs text-text-tertiary">
                Holding period: <span className="font-medium text-text-secondary">{holdingPeriod}</span>
              </span>
            )}
          </div>
          {side.targets.map((t, i) => {
            // Fix 1: Deep entry (structural reversion) targets are anchored to long-term recovery —
            // minimum horizon is 12–24 mo regardless of label. Prevents short-horizon framing on
            // targets that are measured from a structural entry far below current market price.
            const horizon = isDeepEntry
              ? (i === 0 ? '12–24 mo' : '24–36 mo')
              : inferTargetHorizon(t.label, i)
            const extended = isExtendedTarget(t.label, i)
            const targetType = inferTargetType(t.label, i)
            const conditionality = inferTargetConditionality(t.label, i, rating, variant)
            const sanitizedLabel = sanitizeTargetLabel(t.label)
            const dimExtra = rating === 'HOLD' && extended
            return (
              <div
                key={i}
                className={`rounded px-2 py-1.5 text-sm ${extended ? 'bg-surface-elevated/60' : ''} ${dimExtra ? 'opacity-50' : ''}`}
              >
                {/* Label row — wraps on narrow screens to keep full label visible */}
                <div className="flex flex-wrap items-center justify-between gap-x-2 gap-y-1">
                  <div className="flex items-center gap-1.5 min-w-0">
                    <span className={`${extended ? 'text-text-tertiary' : 'text-text-secondary'}`}>
                      {sanitizedLabel}
                    </span>
                    <span className={`text-xs px-1.5 py-0.5 rounded font-mono shrink-0 ${
                      extended
                        ? 'bg-surface-elevated text-text-tertiary'
                        : 'bg-primary/10 text-primary/70'
                    }`}>
                      {horizon}
                    </span>
                  </div>
                  <div className="flex items-center gap-1.5 shrink-0">
                    <span className={`font-medium ${extended ? 'text-success/60' : 'text-success'}`}>
                      {formatCurrency(t.price)}
                    </span>
                    <span className="text-xs text-text-tertiary">Sell {t.sell_pct}%</span>
                  </div>
                </div>
                {/* Type + conditionality subrow */}
                <div className="flex items-center gap-1.5 mt-0.5">
                  <span className="text-[11px] text-text-tertiary">
                    {targetType} Target
                  </span>
                  {conditionality && (
                    <span className="text-[10px] text-text-tertiary/60 italic">
                      — {conditionality}
                    </span>
                  )}
                </div>
              </div>
            )
          })}
          {side.targets.some((t, i) => isExtendedTarget(t.label, i)) && !isDeepEntry && (
            <p className="text-xs text-text-tertiary pt-1 leading-relaxed">
              Regime Expansion targets (muted) extend beyond the primary holding window — conditional on thesis validation and favorable macro regime.
            </p>
          )}
          {/* Fix 1: Structural entry disclaimer — targets anchored to entry, not market regime */}
          {isDeepEntry && (
            <p className="text-[11px] text-text-tertiary/80 pt-1.5 leading-relaxed border-t border-border/50 italic">
              Targets calculated from structural entry — not comparable to market-regime setup targets.
            </p>
          )}
          {/* Coherence label when targets operate in market pricing regime, not structural FV zone */}
          {allTargetsAboveStructuralFV && !isDeepEntry && (
            <p className="text-[10px] text-text-tertiary/70 pt-1 italic leading-relaxed">
              Targets reflect current market pricing path — not anchored to structural fair value.
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
      </div>
    </div>
  )
}

export function TradeSetup({ setup, ticker: _ticker, strategy, signalBreakdown, rating, currentPrice, calibration, financialHealthScore }: TradeSetupProps) {
  const stopQuality = strategy?.exit?.stop_quality
  const stopAlignmentNote = strategy?.exit?.stop_alignment_note
  const stopZone = strategy?.exit?.stop_zone
  const stopMethodology = strategy?.exit?.stop_methodology
  const entryMethodology = strategy?.entry?.entry_methodology
  const entryZoneDisplay = strategy?.entry?.entry_zone_display
  const entryBelowBear = strategy?.entry?.entry_below_bear
  const entryBelowBearPct = strategy?.entry?.entry_below_bear_pct
  const belowBearClassification = strategy?.entry?.below_bear_classification
  const belowBearJustification = strategy?.entry?.below_bear_justification

  const stopStyle = stopQuality ? STOP_QUALITY_STYLES[stopQuality] : undefined

  // Entry zone taxonomy — three distinct levels clarify the system
  const opportunityEnvelope = strategy?.entry?.ideal_zone
  const tacticalBand = entryZoneDisplay

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
          <div className={`p-3 rounded-md border text-xs leading-relaxed ${
            belowBearClassification === 'DISTRESSED_ENTRY' || belowBearClassification === 'CLAMPED'
              ? 'bg-error/10 border-error/30 text-error'
              : 'bg-warning/10 border-warning/30 text-warning'
          }`}>
            <div className="flex items-center gap-2 mb-1">
              <span className="font-bold">
                {belowBearClassification === 'DISTRESSED_ENTRY' ? 'Distressed Entry Zone' :
                 belowBearClassification === 'CLAMPED' ? 'Entry Clamped' :
                 'Entry Below Risk Scenario Floor'}
              </span>
              {entryBelowBearPct !== undefined && entryBelowBearPct > 0 && (
                <span className="font-normal opacity-80">({entryBelowBearPct.toFixed(1)}% below Risk Scenario)</span>
              )}
            </div>
            <p className="text-text-secondary">{belowBearJustification}</p>
          </div>
        )}

        {/* Entry zone taxonomy block — three-level structure with structural/tactical framing.
            Structural Value Zone: long-term intrinsic anchor (model bear-to-base range).
            Tactical Anchor: regime-contextual execution price. When large dislocation exists,
            labels clarify the timeframe distinction rather than implying conflicting signals. */}
        {(opportunityEnvelope || tacticalBand) && (
          <div className="p-3 rounded-md bg-surface-elevated border border-border text-xs space-y-2.5">
            <span className="font-semibold text-text-secondary block">Entry Zone Taxonomy</span>
            {opportunityEnvelope && (() => {
              // C3: Always render low-to-high regardless of backend ordering
              const envLow = Math.min(opportunityEnvelope.low, opportunityEnvelope.high)
              const envHigh = Math.max(opportunityEnvelope.low, opportunityEnvelope.high)
              // Structural dislocation: current price significantly above the opportunity envelope
              const isDislocated = currentPrice !== undefined && currentPrice > 0 && currentPrice > envHigh * 1.25
              // Deep discount: current price below the opportunity envelope floor
              const priceDeepDiscount = currentPrice !== undefined && currentPrice > 0 && currentPrice < envLow
              return (
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <span className="text-text-secondary font-medium">
                      {isDislocated ? 'Structural Value Zone' : 'Opportunity Envelope'}
                    </span>
                    <span className="block text-text-tertiary">
                      {isDislocated
                        ? 'Long-term intrinsic anchor — mean reversion basis (12–24 mo)'
                        : 'Broad range where structural thesis remains valid'
                      }
                    </span>
                    {priceDeepDiscount && (
                      <span className="block text-xs text-success mt-0.5">
                        Execution Discount Zone fully active — verify thesis remains intact
                      </span>
                    )}
                  </div>
                  <span className="font-medium text-text-secondary font-mono shrink-0">
                    ~${Math.round(envLow).toLocaleString()} – ~${Math.round(envHigh).toLocaleString()}
                  </span>
                </div>
              )
            })()}
            {tacticalBand && (
              <div className="flex items-center justify-between">
                <div>
                  <span className="text-text-secondary font-medium">Tactical Band</span>
                  <span className="block text-text-tertiary">Model-optimized entry zone</span>
                </div>
                <span className="font-medium text-text-secondary font-mono">{tacticalBand.label}</span>
              </div>
            )}
            {(() => {
              const envHigh = opportunityEnvelope
                ? Math.max(opportunityEnvelope.low, opportunityEnvelope.high)
                : null
              const isDislocated = currentPrice !== undefined && currentPrice > 0 && envHigh !== null && currentPrice > envHigh * 1.25
              return (
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <span className="text-text-secondary font-medium">
                      {isDislocated ? 'Structural Anchor' : 'Execution Anchor'}
                    </span>
                    <span className="block text-text-tertiary">
                      {isDislocated
                        ? 'Regime-compressed entry — actionable if price reverts to structural zone'
                        : 'Modeled optimal entry — not a guaranteed fill'
                      }
                    </span>
                  </div>
                  <span className="font-medium text-text-secondary font-mono shrink-0">
                    {formatAnchor(setup.conservative.entry)}
                  </span>
                </div>
              )
            })()}
            {entryMethodology && (
              <p className="text-text-tertiary leading-relaxed pt-2 border-t border-border">{entryMethodology}</p>
            )}
            <p className="text-[11px] text-text-tertiary/60 leading-relaxed pt-1.5 border-t border-border/50 italic">
              Structural anchor reflects the model's long-term intrinsic basis. Current regime may require
              pullback or time for price compression before the zone becomes tactically actionable.
            </p>
          </div>
        )}

        {/* Fallback: entry methodology only when no zone data is present */}
        {!opportunityEnvelope && !tacticalBand && entryMethodology && (
          <div className="p-3 rounded-md bg-surface-elevated border border-border text-xs text-text-tertiary leading-relaxed">
            <span className="font-semibold text-text-secondary block mb-1">Entry Methodology</span>
            {entryMethodology}
          </div>
        )}

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
          />
          <SetupColumn
            side={setup.aggressive}
            variant="aggressive"
            signalBreakdown={signalBreakdown}
            rating={rating}
            holdingPeriod={strategy?.exit?.holding_period}
            currentPrice={currentPrice}
            structuralFairValue={structuralFV}
          />
        </div>
      </CardContent>
    </Card>
  )
}
