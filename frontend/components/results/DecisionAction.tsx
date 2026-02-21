'use client'

import { useState } from 'react'
import { Card, CardContent } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { AlertTriangle, CheckCircle } from 'lucide-react'
import type { DecisionFramework, RecommendedStrategy, SignalBreakdown, FundTechDivergence, EnhancedTradeSetup } from '@/types/api'

interface DecisionActionProps {
  framework: DecisionFramework
  ticker: string
  rating: string | null
  riskLevel: string | null
  currentPrice?: number | null
  strategy?: RecommendedStrategy | null
  signalBreakdown?: SignalBreakdown | null
  fundTechDivergence?: FundTechDivergence | null
  convictionLevel?: string | null
  enhancedTradeSetup?: EnhancedTradeSetup | null
}

type Tab = 'new' | 'holders'

function actionToBadgeVariant(action: string): 'success' | 'warning' | 'error' | 'default' {
  switch (action) {
    case 'BUY NOW':
    case 'ADD':
      return 'success'
    case 'SCALE IN':
    case 'HOLD':
      return 'warning'
    case 'WAIT':
    case 'REDUCE':
    case 'AVOID':
      return 'error'
    default:
      return 'default'
  }
}

function ratingToBadgeVariant(rating: string): 'success' | 'warning' | 'error' | 'default' {
  if (rating.includes('STRONG BUY') || rating === 'BUY') return 'success'
  if (rating === 'HOLD') return 'warning'
  return 'error'
}

function formatZone(low: number | undefined, high: number | undefined): string | null {
  if (!low && !high) return null
  if (low && high) return `$${Math.round(low).toLocaleString()} – $${Math.round(high).toLocaleString()}`
  if (low) return `~$${Math.round(low).toLocaleString()}`
  if (high) return `~$${Math.round(high).toLocaleString()}`
  return null
}

// Issue 3: Proximity detection — when current price is close to the avoid threshold,
// surface a contextual warning instead of letting the tiles appear contradictory.
type ProximityStatus = 'CRITICAL' | 'ELEVATED' | null

function getAvoidProximity(currentPrice: number | null | undefined, avoidAbovePrice: number | null | undefined): ProximityStatus {
  if (!currentPrice || !avoidAbovePrice || avoidAbovePrice <= currentPrice) return null
  const buffer = (avoidAbovePrice - currentPrice) / currentPrice
  if (buffer < 0.03) return 'CRITICAL'
  if (buffer < 0.07) return 'ELEVATED'
  return null
}

export function DecisionAction({
  framework,
  rating,
  riskLevel,
  currentPrice,
  strategy,
  signalBreakdown,
  fundTechDivergence,
  convictionLevel,
  enhancedTradeSetup,
}: DecisionActionProps) {
  const [tab, setTab] = useState<Tab>('new')
  const { current_holders, new_buyers, one_liner } = framework

  // Build price zones from strategy
  // Issue 2: Rename "Entry Zone" → "Opportunity Envelope" at the decision-stack level.
  // The broad ideal_zone is the opportunity envelope, not a specific execution price.
  const opportunityEnvelope = strategy?.entry?.ideal_zone
    ? formatZone(strategy.entry.ideal_zone.low, strategy.entry.ideal_zone.high)
    : strategy?.entry?.entry_zone_display?.label ?? null

  // Fix 3: Stop zone derivation — resolved after dislocation detection below.
  // Placeholder until isStructuralDislocation is computed.
  const rawStopZone = strategy?.exit?.stop_zone?.label
    ?? (strategy?.exit?.stop_loss ? `~$${Math.round(strategy.exit.stop_loss).toLocaleString()}` : null)

  const targetZone = strategy?.exit?.target_2?.price
    ? formatZone(strategy.exit.target_1?.price, strategy.exit.target_2?.price)
    : strategy?.exit?.target_1?.price ? `~$${Math.round(strategy.exit.target_1.price).toLocaleString()}` : null

  // Avoid threshold: 5% above the top of the opportunity envelope
  const avoidAbovePrice = strategy?.entry?.ideal_zone?.high
    ? strategy.entry.ideal_zone.high * 1.05
    : null
  const avoidAbove = avoidAbovePrice
    ? `$${Math.round(avoidAbovePrice).toLocaleString()}+`
    : null

  // Issue 3: Proximity status
  const proximityStatus = getAvoidProximity(currentPrice, avoidAbovePrice)

  // Structural dislocation detection — when current price significantly exceeds the model's
  // avoid threshold, the opportunity envelope represents a long-term intrinsic anchor,
  // not a near-term actionable zone. Two-tier check prevents label flip on minor overruns.
  const isStructuralDislocation = Boolean(
    currentPrice && avoidAbovePrice && currentPrice > avoidAbovePrice * 1.25
  )
  const dislocationPct = (isStructuralDislocation && currentPrice && strategy?.entry?.ideal_zone?.high)
    ? Math.round(((currentPrice - strategy.entry.ideal_zone.high) / strategy.entry.ideal_zone.high) * 100)
    : null

  // Fix 3: When structural dislocation is active, the primary actionable setup is the aggressive
  // (market-regime) setup. Pull stop zone from aggressive.stop_loss with a clear label so the user
  // knows which entry it references. The structural setup's stop ($52–54) is irrelevant at current prices.
  const stopZone = (() => {
    if (isStructuralDislocation && enhancedTradeSetup?.aggressive?.stop_loss) {
      return `~$${Math.round(enhancedTradeSetup.aggressive.stop_loss).toLocaleString()}`
    }
    return rawStopZone
  })()
  const stopZoneSetupLabel = isStructuralDislocation && enhancedTradeSetup?.aggressive?.stop_loss
    ? 'Market-regime setup'
    : isStructuralDislocation
    ? 'Structural setup'
    : null

  // Signal status strip
  const hasDivergence = signalBreakdown?.has_divergence
  const divergenceSeverity = fundTechDivergence?.severity || (hasDivergence ? 'MODERATE' : null)

  // Req 3: Separate directional bias from signal agreement
  const directionalBias = (() => {
    const d = (signalBreakdown?.direction_consensus ?? '').toLowerCase()
    if (d.includes('bull')) return 'Bullish'
    if (d.includes('bear')) return 'Bearish'
    return 'Neutral'
  })()

  const agreementLabel = (() => {
    if (!hasDivergence) return 'Aligned'
    return divergenceSeverity === 'HIGH' ? 'High Conflict' : 'Moderate Conflict'
  })()

  return (
    <Card
      className="border-primary/30"
      style={{
        background: 'var(--surface-1)',
        boxShadow: '0 0 0 1px rgba(0 217 181 / 0.08), 0 4px 28px rgba(0 0 0 / 0.45)',
      }}
    >
      <CardContent className="pt-6 space-y-5">

        {/* Decision Hero */}
        <div className="space-y-3">
          <div className="flex items-center gap-2 flex-wrap">
            {rating && (
              <Badge
                variant={ratingToBadgeVariant(rating)}
                className="px-3.5 py-1 font-semibold tracking-wide"
                style={{ fontSize: 'var(--text-lg)' }}
              >
                {rating}
              </Badge>
            )}
            {riskLevel && (
              <Badge variant="secondary">{riskLevel} Risk</Badge>
            )}
            {convictionLevel && (
              <Badge variant="secondary">Conviction: {convictionLevel}</Badge>
            )}
          </div>
          <p className="text-base font-semibold text-text-primary leading-relaxed">{one_liner}</p>
        </div>

        {/* Signal Status Strip — inline, links to signals section below */}
        {signalBreakdown && (
          <div className={`flex items-center gap-2 px-3 py-2 rounded-md text-xs ${
            hasDivergence
              ? divergenceSeverity === 'HIGH'
                ? 'bg-error/5 border border-error/20 text-error'
                : 'bg-warning/5 border border-warning/20 text-warning'
              : 'bg-success/5 border border-success/20 text-success'
          }`}>
            {/* Req 3: Unified strip — Directional Bias + Signal Agreement as separate concepts */}
            {hasDivergence ? (
              <>
                <AlertTriangle className="h-3.5 w-3.5 flex-shrink-0" />
                <span className="font-medium">Directional Bias: {directionalBias}</span>
                <span className="text-text-secondary mx-1">·</span>
                <span className="text-text-secondary">Signal Agreement: {agreementLabel}</span>
                <span className="ml-auto whitespace-nowrap text-text-tertiary pl-2">See signals ↓</span>
              </>
            ) : (
              <>
                <CheckCircle className="h-3.5 w-3.5 flex-shrink-0" />
                <span className="font-medium">Directional Bias: {directionalBias}</span>
                <span className="text-text-secondary mx-1">·</span>
                <span className="text-text-secondary">Signal Agreement: {agreementLabel}</span>
                <span className="ml-auto whitespace-nowrap text-text-tertiary pl-2">See signals ↓</span>
              </>
            )}
          </div>
        )}

        {/* Issue 3: Proximity warning — shown when price is approaching avoid threshold */}
        {proximityStatus && (
          <div className={`flex items-center gap-2 px-3 py-2 rounded-md text-xs ${
            proximityStatus === 'CRITICAL'
              ? 'bg-error/8 border border-error/25 text-error'
              : 'bg-warning/8 border border-warning/25 text-warning'
          }`}>
            <AlertTriangle className="h-3.5 w-3.5 flex-shrink-0" />
            <span className="font-medium">
              {proximityStatus === 'CRITICAL'
                ? 'Price approaching Avoid Zone'
                : 'Limited buffer before Avoid Threshold'}
            </span>
            <span className="text-text-secondary mx-1">·</span>
            <span className="text-text-secondary">
              {proximityStatus === 'CRITICAL'
                ? 'Execution sensitivity elevated — verify current price before entering'
                : 'Consider limit orders to avoid chasing above threshold'}
            </span>
          </div>
        )}

        {/* Key Price Zones Grid
            Dislocation-aware: when current price significantly exceeds the avoid threshold,
            zones are reframed as structural (long-term intrinsic) anchors rather than
            near-term actionable levels. Prevents contradictory signal perception. */}
        {(opportunityEnvelope || stopZone || targetZone || avoidAbove) && (
          <div>
            <div className="flex items-center justify-between mb-2">
              <p className="text-xs font-medium text-text-tertiary uppercase tracking-wide">Key Price Zones</p>
              {isStructuralDislocation && (
                <span className="text-[10px] text-text-tertiary italic">
                  Structural framework · Timeframe-dependent
                </span>
              )}
            </div>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
              {opportunityEnvelope && (
                <div className="rounded-md bg-surface-elevated border border-border p-3 text-center">
                  <p className="text-xs text-text-tertiary mb-1">
                    {isStructuralDislocation ? 'Structural Value Zone' : 'Opportunity Envelope'}
                    <span
                      className="ml-1 text-text-tertiary cursor-help"
                      title={isStructuralDislocation
                        ? 'Long-term intrinsic value anchor derived from model bear-to-base scenario range. Represents the theoretical mean reversion zone (12–24 mo horizon), not a near-term actionable entry.'
                        : 'Broad price range where the investment thesis is favorably priced. The model-optimized Tactical Band and Execution Anchor are in the Trade Setup section below.'}
                    >
                      ⓘ
                    </span>
                  </p>
                  <p className="text-sm font-semibold text-success">{opportunityEnvelope}</p>
                  {isStructuralDislocation && (
                    <p className="text-[10px] text-text-tertiary mt-0.5 leading-tight">Long-term anchor</p>
                  )}
                </div>
              )}

              {/* Avoid Above tile: suppress when structurally dislocated (already breached).
                  Replace with Structural Premium to show the magnitude of dislocation. */}
              {isStructuralDislocation && dislocationPct !== null ? (
                <div className="rounded-md bg-surface-elevated border border-warning/30 p-3 text-center">
                  <p className="text-xs text-text-tertiary mb-1">Structural Premium</p>
                  <p className="text-sm font-semibold text-warning">+{dislocationPct}%</p>
                  <p className="text-[10px] text-text-tertiary mt-0.5 leading-tight">Above value zone</p>
                </div>
              ) : avoidAbove ? (
                <div className={`rounded-md bg-surface-elevated p-3 text-center border ${
                  proximityStatus === 'CRITICAL'
                    ? 'border-error/50 ring-1 ring-error/20'
                    : proximityStatus === 'ELEVATED'
                    ? 'border-warning/40'
                    : 'border-border'
                }`}>
                  <p className="text-xs text-text-tertiary mb-1">Avoid Above</p>
                  <p className={`text-sm font-semibold ${
                    proximityStatus ? 'text-error' : 'text-error'
                  }`}>{avoidAbove}</p>
                  {proximityStatus === 'CRITICAL' && (
                    <p className="text-xs text-error/70 mt-1">Near threshold</p>
                  )}
                </div>
              ) : null}

              {stopZone && (
                <div className="rounded-md bg-surface-elevated border border-border p-3 text-center">
                  <p className="text-xs text-text-tertiary mb-1">Stop Zone</p>
                  <p className="text-sm font-semibold text-error">{stopZone}</p>
                  {/* Fix 3: Label clarifies which setup the stop references */}
                  {stopZoneSetupLabel && (
                    <p className="text-[10px] text-text-tertiary mt-0.5 leading-tight">{stopZoneSetupLabel}</p>
                  )}
                </div>
              )}
              {targetZone && (
                <div className="rounded-md bg-surface-elevated border border-border p-3 text-center">
                  <p className="text-xs text-text-tertiary mb-1">
                    Target Band
                    <span
                      className="ml-1 text-text-tertiary cursor-help"
                      title="Base-case to bull-case price target range. T1 (50% exit) = intrinsic value midpoint. T2 (50% exit) = upside scenario. Both derived from the model's valuation output."
                    >
                      ⓘ
                    </span>
                  </p>
                  <p className="text-sm font-semibold text-primary">{targetZone}</p>
                  {strategy?.exit?.target_1?.rationale && (
                    <p className="text-xs text-text-tertiary mt-1 leading-relaxed">
                      T1 {strategy.exit.target_1.percent}% · T2 {strategy.exit.target_2?.percent}%
                    </p>
                  )}
                </div>
              )}
            </div>

            {/* Structural dislocation context note — explains the zone / price gap */}
            {isStructuralDislocation && dislocationPct !== null && (
              <p className="text-xs text-text-tertiary leading-relaxed mt-2.5 pl-1 border-l-2 border-warning/30">
                <span className="font-medium text-text-secondary">Structural vs. Tactical Context:</span> Current price (+{dislocationPct}% above structural value zone) reflects market pricing outside the model's intrinsic framework.
                {' '}Zones above represent the <span className="italic">long-term mean reversion basis</span> — not near-term actionable levels.
                {' '}Interpret against the applicable thesis horizon before using as entry signals.
              </p>
            )}
          </div>
        )}

        {/* Tabbed Guidance */}
        <div>
          <div className="flex border-b border-border mb-4">
            <button
              onClick={() => setTab('new')}
              className={`px-4 py-2 text-sm font-medium transition-colors border-b-2 -mb-px ${
                tab === 'new'
                  ? 'border-primary text-text-primary'
                  : 'border-transparent text-text-tertiary hover:text-text-secondary'
              }`}
            >
              New Buyers
              <Badge variant={actionToBadgeVariant(new_buyers.action)} className="ml-2 text-xs">
                {new_buyers.action}
              </Badge>
            </button>
            <button
              onClick={() => setTab('holders')}
              className={`px-4 py-2 text-sm font-medium transition-colors border-b-2 -mb-px ${
                tab === 'holders'
                  ? 'border-primary text-text-primary'
                  : 'border-transparent text-text-tertiary hover:text-text-secondary'
              }`}
            >
              Current Holders
              <Badge variant={actionToBadgeVariant(current_holders.action)} className="ml-2 text-xs">
                {current_holders.action}
              </Badge>
            </button>
          </div>

          {tab === 'new' && (
            <div className="space-y-3">
              {new_buyers.urgency && new_buyers.urgency !== 'N/A' && (
                <div className="space-y-1">
                  <div className="flex items-center justify-between text-xs">
                    <span className="text-text-tertiary">Entry Urgency</span>
                    <span className={`font-medium ${
                      proximityStatus === 'CRITICAL' && new_buyers.action === 'BUY NOW'
                        ? 'text-warning'
                        : 'text-text-primary'
                    }`}>
                      {/* Issue 3: Dampen urgency display when price is near avoid threshold */}
                      {proximityStatus === 'CRITICAL' && new_buyers.action === 'BUY NOW'
                        ? 'Elevated — Near Threshold'
                        : new_buyers.urgency}
                    </span>
                  </div>
                  <div className="relative h-1.5 bg-surface-elevated rounded-full overflow-hidden">
                    {/* Fix 5: Bar color maps to action + divergence — not urgency text alone.
                        A WAIT/Low urgency bar must never render green (visual contradiction).
                        RED FLAG divergence (high severity) shifts any bar to amber minimum.
                        new_buyers.action union: 'BUY NOW' | 'SCALE IN' | 'WAIT' | 'AVOID' */}
                    {(() => {
                      const urgencyLower = new_buyers.urgency.toLowerCase()
                      const urgencyHigh = urgencyLower.includes('high') || urgencyLower.includes('elevat')
                      const urgencyLow = urgencyLower.includes('low')
                      const action = new_buyers.action
                      const hasRedFlagDivergence = hasDivergence && divergenceSeverity === 'HIGH'
                      const isWaitAvoid = action === 'WAIT' || action === 'AVOID'
                      // HOLD rating maps to WAIT action for new buyers; catch it via rating prop
                      const isHoldRating = rating === 'HOLD' || rating === 'WAIT'
                      const isBuyAction = action === 'BUY NOW' || action === 'SCALE IN'

                      let barColor: string
                      let barWidth: string

                      if (proximityStatus === 'CRITICAL') {
                        barColor = 'bg-warning'
                        barWidth = 'w-[55%]'
                      } else if (isWaitAvoid || urgencyLow) {
                        // WAIT / AVOID / low urgency → grey (never green)
                        barColor = 'bg-text-tertiary/30'
                        barWidth = urgencyLow ? 'w-[15%]' : 'w-[25%]'
                      } else if (isHoldRating && !isBuyAction) {
                        // HOLD rating without explicit buy action → amber
                        barColor = 'bg-warning'
                        barWidth = 'w-[40%]'
                      } else if (isBuyAction && !hasRedFlagDivergence) {
                        // BUY NOW / SCALE IN with no red-flag divergence → green
                        barColor = 'bg-success'
                        barWidth = urgencyHigh ? 'w-[85%]' : 'w-[55%]'
                      } else if (isBuyAction && hasRedFlagDivergence) {
                        // BUY NOW but RED FLAG divergence active → amber minimum
                        barColor = 'bg-warning'
                        barWidth = urgencyHigh ? 'w-[70%]' : 'w-[50%]'
                      } else if (hasRedFlagDivergence) {
                        // Any other action with red flag → amber minimum
                        barColor = 'bg-warning'
                        barWidth = 'w-[40%]'
                      } else {
                        // Fallback
                        barColor = urgencyHigh ? 'bg-success' : 'bg-warning'
                        barWidth = urgencyHigh ? 'w-[65%]' : 'w-[40%]'
                      }

                      return <div className={`absolute inset-y-0 left-0 rounded-full ${barColor} ${barWidth}`} />
                    })()}
                  </div>
                </div>
              )}
              <p className="text-sm text-text-secondary leading-relaxed">{new_buyers.detail}</p>
              {(new_buyers.detail.includes('limit') || new_buyers.detail.includes('alerts')) && (
                <div className="p-2.5 bg-surface-elevated rounded border border-primary/20">
                  <p className="text-xs text-text-tertiary leading-relaxed">
                    <span className="font-medium text-text-secondary">Tip: </span>
                    {new_buyers.detail.includes('resistance') || new_buyers.detail.includes('breaks above')
                      ? 'A buy-stop limit above current price activates when price breaks resistance — confirming momentum before you enter.'
                      : 'A buy limit below current price fills only on a pullback, improving your entry cost vs. a market order.'}
                  </p>
                </div>
              )}
              {new_buyers.caveat && (
                <p className="text-xs text-warning italic">{new_buyers.caveat}</p>
              )}
            </div>
          )}

          {tab === 'holders' && (
            <div className="space-y-3">
              <p className="text-sm text-text-secondary leading-relaxed">{current_holders.detail}</p>
              {current_holders.conditions.length > 0 && (
                <ul className="space-y-1.5">
                  {current_holders.conditions.map((c, i) => (
                    <li key={i} className="text-xs text-text-tertiary flex items-start gap-1.5">
                      <span className="mt-1 w-1 h-1 rounded-full bg-text-tertiary flex-shrink-0" />
                      {c}
                    </li>
                  ))}
                </ul>
              )}
            </div>
          )}
        </div>
      </CardContent>
    </Card>
  )
}
