import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { formatCurrency } from '@/lib/utils/formatting'
import type { EnhancedTradeSetup, TradeSetupSide, RecommendedStrategy, SignalBreakdown } from '@/types/api'

interface TradeSetupProps {
  setup: EnhancedTradeSetup
  ticker: string
  strategy?: RecommendedStrategy | null
  signalBreakdown?: SignalBreakdown | null
  rating?: string | null
}

const STOP_QUALITY_STYLES: Record<string, { badge: string; note: string }> = {
  ALIGNED: { badge: 'bg-success/15 text-success border-success/30', note: 'text-success' },
  WIDE: { badge: 'bg-warning/15 text-warning border-warning/30', note: 'text-warning' },
  ADJUSTED: { badge: 'bg-primary/15 text-primary border-primary/30', note: 'text-primary' },
}

// Issue 7: Precision normalization — use zone format for anchor prices (estimates),
// keep formatCurrency for precise target prices (objectives).
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
// Targets beyond ~12 months are labelled as scenario extensions.
function isExtendedTarget(label: string, index: number): boolean {
  const l = label.toLowerCase()
  if (l.includes('bull') || l.includes('stretch') || l.includes('extended') || l.includes('upside')) return true
  if (index >= 2) return true
  return false
}

// Classify target by analytical type for institutional-grade labeling.
function inferTargetType(label: string, index: number): string {
  const l = label.toLowerCase()
  if (l.includes('bull') || l.includes('stretch') || l.includes('extended') || l.includes('upside') || index >= 2)
    return 'Scenario'
  if (l.includes('near') || l.includes('t1') || l.includes('short') || index === 0)
    return 'Tactical Reversion'
  if (l.includes('base') || l.includes('t2') || l.includes('mid') || index === 1)
    return 'Momentum Continuation'
  return 'Thesis'
}

// Issue 6: R/R realism qualifier — high ratios are modeled projections,
// not realized outcome guarantees.
function getRRRealism(
  rr: number,
  hasHighDivergence: boolean
): { qualifier: string | null; footnote: string | null } {
  if (rr >= 6 && hasHighDivergence)
    return {
      qualifier: 'Theoretical',
      footnote: 'Modeled asymmetry — realized performance is regime-dependent. High divergence reduces path probability.',
    }
  if (rr >= 4)
    return {
      qualifier: 'Modeled',
      footnote: 'Modeled asymmetry. Execution variability and volatility may compress realized returns.',
    }
  return { qualifier: null, footnote: null }
}

// Issue 1: Conditional R/R qualifier — when signals conflict with the R/R implication,
// surface the conflict as a badge rather than silently showing the ratio.
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
      footnote: 'Asymmetric payoff modeled from current levels — bearish signal dominance reduces confidence that target prices are achievable within the holding period.',
    }
  if (rating === 'HOLD' && rr > 4)
    return {
      label: 'Thesis-Dependent',
      footnote: 'High theoretical R/R — payoff is contingent on divergence resolution in favor of the bull case. HOLD rating reflects current signal uncertainty.',
    }
  if (signalBreakdown.has_divergence && rr > 4)
    return {
      label: 'Divergence Unresolved',
      footnote: 'Divergence active — modeled asymmetry is regime-dependent. Monitor for signal resolution before sizing aggressively.',
    }
  return { label: null, footnote: null }
}

function SetupColumn({
  side,
  variant,
  signalBreakdown,
  rating,
  holdingPeriod,
}: {
  side: TradeSetupSide
  variant: 'conservative' | 'aggressive'
  signalBreakdown?: SignalBreakdown | null
  rating?: string | null
  holdingPeriod?: string | null
}) {
  const borderColor = variant === 'conservative' ? 'border-success/30' : 'border-warning/30'
  const headerBg = variant === 'conservative' ? 'bg-success/5' : 'bg-warning/5'

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

  // Req 1 + 6: Soften R/R badge under HOLD or signal conflict — prevents promotional read
  const isHoldRating = rating === 'HOLD'
  const showSoftRR = isHoldRating || conditionalLabel !== null
  const rrLabel = showSoftRR
    ? `Modeled Asymmetry (${side.risk_reward}:1)`
    : `${side.risk_reward}:1 R/R`
  const rrVariant = showSoftRR
    ? 'secondary' as const
    : (variant === 'conservative' ? 'success' as const : 'warning' as const)

  return (
    <div className={`rounded-lg border ${borderColor} overflow-hidden`}>
      {/* Header */}
      <div className={`px-4 py-3 ${headerBg}`}>
        <div className="flex items-center justify-between flex-wrap gap-1.5">
          {/* Req 2: Replace "Recommended" with "Model-Optimal" — eliminates execution tension */}
          <span className="text-sm font-semibold text-text-primary">
            {side.label.replace('Recommended', 'Model-Optimal')}
          </span>
          <div className="flex items-center gap-1.5 flex-wrap">
            <Badge variant={rrVariant} className={showSoftRR ? 'opacity-75 font-normal' : ''}>
              {rrLabel}
            </Badge>
            {displayQualifier && (
              <Badge variant="secondary" className="text-xs font-normal opacity-80">
                {displayQualifier}
              </Badge>
            )}
          </div>
        </div>
        {displayFootnote && (
          <p className="text-xs text-text-tertiary mt-1.5 leading-relaxed">{displayFootnote}</p>
        )}
      </div>

      {/* Body */}
      <div className="p-4 space-y-3">
        {/* Entry & Stop — use anchor format (estimates, not exact prices) */}
        <div className="grid grid-cols-2 gap-3">
          <div>
            <span className="text-xs text-text-tertiary block">Execution Anchor</span>
            <span className="text-sm font-semibold text-text-primary">
              {formatAnchor(side.entry)}
            </span>
            {/* Req 5: Clarify modeled vs actionable fill */}
            <span className="text-xs text-text-tertiary block mt-0.5">Modeled entry — scale in or wait for pullback</span>
          </div>
          <div>
            <span className="text-xs text-text-tertiary block">Stop Loss</span>
            <span className="text-sm font-semibold text-error">
              {formatAnchor(side.stop_loss)}
            </span>
          </div>
        </div>

        {/* Targets — kept precise as they are defined objectives, not estimates.
            Time horizons are inferred from label keywords for trade framing context. */}
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
            const horizon = inferTargetHorizon(t.label, i)
            const extended = isExtendedTarget(t.label, i)
            const targetType = inferTargetType(t.label, i)
            // Req 6: HOLD + extended targets get extra visual downgrade
            const dimExtra = rating === 'HOLD' && extended
            return (
              <div key={i} className={`flex items-center justify-between text-sm rounded px-2 py-1 ${extended ? 'bg-surface-elevated/60' : ''} ${dimExtra ? 'opacity-50' : ''}`}>
                <div className="flex items-center gap-2">
                  {/* Req 4: Full target classification label */}
                  <span className={extended ? 'text-text-tertiary' : 'text-text-secondary'}>
                    {t.label} – {targetType} Target
                  </span>
                  <span className={`text-xs px-1.5 py-0.5 rounded font-mono ${
                    extended
                      ? 'bg-surface-elevated text-text-tertiary'
                      : 'bg-primary/10 text-primary/70'
                  }`}>
                    {horizon}
                  </span>
                </div>
                <div className="flex items-center gap-2">
                  <span className={`font-medium ${extended ? 'text-success/60' : 'text-success'}`}>
                    {formatCurrency(t.price)}
                  </span>
                  <span className="text-xs text-text-tertiary">Sell {t.sell_pct}%</span>
                </div>
              </div>
            )
          })}
          {side.targets.some((t, i) => isExtendedTarget(t.label, i)) && (
            <p className="text-xs text-text-tertiary pt-1 leading-relaxed">
              Scenario targets (muted) extend beyond the primary holding window — applicable only if the bull case materializes.
            </p>
          )}
        </div>

        {/* Risk metrics */}
        <div className="border-t border-surface-elevated pt-3 grid grid-cols-2 gap-2 text-xs">
          <div>
            <span className="text-text-tertiary block">Max Loss / 100 sh</span>
            <span className="font-medium text-error">{formatCurrency(side.max_loss_per_100)}</span>
          </div>
          <div>
            <span className="text-text-tertiary block">Max Gain / 100 sh</span>
            <span className="font-medium text-success">{formatCurrency(side.max_gain_per_100)}</span>
          </div>
        </div>
      </div>
    </div>
  )
}

export function TradeSetup({ setup, ticker: _ticker, strategy, signalBreakdown, rating }: TradeSetupProps) {
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

  // Issue 2: Entry zone taxonomy — three distinct levels clarify the system
  const opportunityEnvelope = strategy?.entry?.ideal_zone
  const tacticalBand = entryZoneDisplay

  return (
    <Card>
      <CardHeader>
        <CardTitle>Entry / Exit Setup</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">

        {/* P0: Entry below bear case disclosure */}
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
                 'Entry Below Bear Case'}
              </span>
              {entryBelowBearPct !== undefined && entryBelowBearPct > 0 && (
                <span className="font-normal opacity-80">({entryBelowBearPct.toFixed(1)}% below bear)</span>
              )}
            </div>
            <p className="text-text-secondary">{belowBearJustification}</p>
          </div>
        )}

        {/* Issue 2: Entry zone taxonomy block — surfaces the three-level structure */}
        {(opportunityEnvelope || tacticalBand) && (
          <div className="p-3 rounded-md bg-surface-elevated border border-border text-xs space-y-2.5">
            <span className="font-semibold text-text-secondary block">Entry Zone Taxonomy</span>
            {opportunityEnvelope && (
              <div className="flex items-center justify-between">
                <div>
                  <span className="text-text-secondary font-medium">Opportunity Envelope</span>
                  <span className="block text-text-tertiary">Broad range where thesis is valid</span>
                </div>
                <span className="font-medium text-text-secondary font-mono">
                  ~${Math.round(opportunityEnvelope.low).toLocaleString()} – ~${Math.round(opportunityEnvelope.high).toLocaleString()}
                </span>
              </div>
            )}
            {tacticalBand && (
              <div className="flex items-center justify-between">
                <div>
                  <span className="text-text-secondary font-medium">Tactical Band</span>
                  <span className="block text-text-tertiary">Model-optimized entry zone</span>
                </div>
                <span className="font-medium text-text-secondary font-mono">{tacticalBand.label}</span>
              </div>
            )}
            <div className="flex items-center justify-between">
              <div>
                <span className="text-text-secondary font-medium">Execution Anchor</span>
                {/* Req 5: Clarify modeled vs actionable */}
                <span className="block text-text-tertiary">Modeled optimal entry, not guaranteed fill</span>
              </div>
              <span className="font-medium text-text-secondary font-mono">
                {formatAnchor(setup.conservative.entry)}
              </span>
            </div>
            {entryMethodology && (
              <p className="text-text-tertiary leading-relaxed pt-2 border-t border-border">{entryMethodology}</p>
            )}
            {/* Req 5: Static clarification — prevents actionable misread when anchor ≠ current price */}
            <p className="text-[11px] text-text-tertiary/60 leading-relaxed pt-1.5 border-t border-border/50 italic">
              Execution Anchor reflects modeled optimal entry. Current price may require scaling or pullback entry.
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

        {/* P0: Stop quality badge + alignment note */}
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

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <SetupColumn
            side={setup.conservative}
            variant="conservative"
            signalBreakdown={signalBreakdown}
            rating={rating}
            holdingPeriod={strategy?.exit?.holding_period}
          />
          <SetupColumn
            side={setup.aggressive}
            variant="aggressive"
            signalBreakdown={signalBreakdown}
            rating={rating}
            holdingPeriod={strategy?.exit?.holding_period}
          />
        </div>
      </CardContent>
    </Card>
  )
}
