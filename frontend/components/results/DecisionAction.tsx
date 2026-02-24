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

/** Classify structural dislocation magnitude into institutional tier labels. */
function getStructuralPremiumTier(pct: number): string {
  if (pct > 100) return 'EXTREME'
  if (pct > 50) return 'HIGH'
  return 'ELEVATED'
}

/** Replace retail/tactical phrasing with institutional analytical language.
 *  Presentation-only — no math or signal values are changed. */
function institutionalizeLang(text: string): string {
  return text
    .replace(/Wait for better entry/gi, 'Risk \/ Reward Unfavorable at Current Levels')
    .replace(/Wait for a pullback/gi, 'Entry Deferred — Valuation Regime Extended')
    .replace(/Wait for pullback/gi, 'Entry Deferred — Valuation Regime Extended')
    .replace(/Better entry levels expected/gi, 'Entry Deferred — Asymmetry Compressed')
    .replace(/Add on pullbacks/gi, 'Scale in on Price Weakness')
}

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

/**
 * Maps (rating, raw_action, signal_spread_label) to a concise, reader-friendly
 * tab badge label that never contradicts the headline recommendation.
 *
 * Raw action drives the detail text; this label drives the tab badge only.
 */
function buyerTabLabel(
  rating: string | null,
  action: string,
  spreadLabel: string | null | undefined,
): string {
  const r = rating ?? 'HOLD'
  const spread = spreadLabel ?? 'Low'

  if (r === 'STRONG SELL' || r === 'SELL') return action === 'AVOID' ? 'EXIT' : 'REDUCE'

  if (r === 'HOLD') {
    if (spread === 'High') return 'WATCH ONLY'
    return 'CAUTIOUS'
  }

  // BUY / STRONG BUY
  if (action === 'BUY NOW') return 'BUY NOW'
  if (action === 'SCALE IN') {
    if (spread === 'High') return 'START POSITION'
    return 'SCALE IN'
  }
  return action
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

  // Issue 5: Entry is deferred when structural dislocation is active and action is non-buy
  const entryIsDeferred = isStructuralDislocation &&
    (new_buyers.action === 'WAIT' || new_buyers.action === 'AVOID' || rating === 'HOLD')
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
    return divergenceSeverity === 'HIGH' ? 'Signal Dispersion — High' : 'Signal Dispersion Detected'
  })()

  return (
    <Card
      className="ambient-verdict"
      style={{ background: 'var(--surface-1)', borderColor: 'rgba(0, 217, 181, 0.22)' }}
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
          {/* Issue 4: Institutional language — presentation-only transform of tactical phrasing */}
          <p className="text-base font-semibold text-text-primary leading-relaxed">{institutionalizeLang(one_liner)}</p>
          {/* Structured per-reader-type subtext — replaces the pipe-delimited multi-audience line.
              When structurally dislocated, subtext lines reference the intrinsic baseline zone
              (e.g., $55–$65), not current tactical levels — frame accordingly to prevent misread. */}
          {framework.action_subtext && framework.action_subtext.length > 0 && (
            <div className={isStructuralDislocation ? 'opacity-60' : ''}>
              {isStructuralDislocation && (
                <p className="text-[10px] text-text-tertiary/70 italic mb-1">
                  Structural baseline context — zones below reference intrinsic valuation, not current tactical levels:
                </p>
              )}
              <div className="flex flex-wrap gap-x-4 gap-y-0.5">
                {framework.action_subtext.map((line: string, i: number) => (
                  <p key={i} className="text-xs text-text-tertiary leading-relaxed">{line}</p>
                ))}
              </div>
            </div>
          )}
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
                  {/* Issue 1: Renamed label + (Non-Tactical) qualifier for structural dislocation */}
                  <p className="text-xs text-text-tertiary mb-0.5">
                    {isStructuralDislocation ? 'Structural Valuation Baseline' : 'Opportunity Envelope'}
                    <span
                      className="ml-1 text-text-tertiary cursor-help"
                      title={isStructuralDislocation
                        ? 'Represents model-derived intrinsic baseline assuming long-cycle normalization. Not a near-term price expectation. Used for regime classification & asymmetry modeling only.'
                        : 'Broad price range where the investment thesis is favorably priced. The model-optimized Tactical Band and Execution Anchor are in the Trade Setup section below.'}
                    >
                      ⓘ
                    </span>
                  </p>
                  {isStructuralDislocation && (
                    <p className="text-[9px] text-text-tertiary/60 mb-0.5 italic">(Non-Tactical)</p>
                  )}
                  {/* Issue 2: Muted color + reduced weight for structural baseline — prevents anchor shock */}
                  <p className={`text-sm ${isStructuralDislocation ? 'font-medium text-text-tertiary' : 'font-semibold text-success'}`}>
                    {opportunityEnvelope}
                  </p>
                  {isStructuralDislocation && (
                    <p className="text-[9px] text-text-tertiary/60 mt-0.5 leading-tight">
                      Regime classification reference — not a price target
                    </p>
                  )}
                </div>
              )}

              {/* Avoid Above tile: suppress when structurally dislocated (already breached).
                  Replace with Structural Premium to show the magnitude of dislocation. */}
              {isStructuralDislocation && dislocationPct !== null ? (
                /* Issue 3: Classification-first framing — magnitude moved to tooltip to prevent anchor shock */
                <div
                  className="rounded-md bg-surface-elevated border border-warning/30 p-3 text-center cursor-help"
                  title={`+${dislocationPct}% above structural valuation baseline. Price trades materially outside the model's intrinsic valuation framework. Magnitude is informational — not a mean-reversion price target.`}
                >
                  <p className="text-xs text-text-tertiary mb-0.5">Structural Premium</p>
                  <p className="text-sm font-semibold text-warning">{getStructuralPremiumTier(dislocationPct)}</p>
                  <p className="text-[9px] text-text-tertiary/70 mt-0.5 leading-tight">
                    Outside structural valuation band
                  </p>
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
                  <p className="text-xs text-text-tertiary mb-1">Risk Control Zone</p>
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
                      title="Base-case to bull-case price target range. T1 (50% exit) = Structural Value Anchor midpoint. T2 (50% exit) = upside scenario. Both derived from the model's valuation output. Horizon-dependent — not near-term price expectations."
                    >
                      ⓘ
                    </span>
                  </p>
                  <p className="text-sm font-semibold text-primary">{targetZone}</p>
                  <p className="text-[9px] text-text-tertiary/60 mt-0.5 italic">Mean Reversion Envelope (Tactical Horizon)</p>
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

            {/* Issue 3: Opportunity Envelope clarification — reconciles envelope range with avoid threshold.
                The Opportunity Envelope shows the full model-derived value range where the thesis is
                favorably priced. The Avoid Above threshold marks where risk/reward deteriorates.
                Prefer entries in the lower portion of the envelope for maximum margin of safety.
                Entries near or above the Avoid threshold require price confirmation before acting. */}
            {opportunityEnvelope && avoidAbove && !isStructuralDislocation && (
              <p className="text-[10px] text-text-tertiary leading-relaxed mt-2 pl-1 border-l-2 border-border-subtle">
                <span className="font-medium text-text-secondary">Entry Zone Note:</span>{' '}
                The Opportunity Envelope marks the full Structural Valuation Reference range.
                Entries in the <span className="font-medium">lower portion offer maximum margin of safety</span>.
                Above the Avoid Above threshold, risk/reward deteriorates — wait for price confirmation (sustained close above {avoidAbove}) before initiating new positions at the upper end.
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
                {buyerTabLabel(rating, new_buyers.action, signalBreakdown?.signal_spread_label)}
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
                    {/* Issue 5: Entry deferral framing — regime-based language replaces pullback anchors */}
                    <span className="text-text-tertiary">
                      {entryIsDeferred ? 'Positioning Posture' : 'Entry Urgency'}
                    </span>
                    <span
                      className={`font-medium ${entryIsDeferred ? 'text-warning' : proximityStatus === 'CRITICAL' && new_buyers.action === 'BUY NOW' ? 'text-warning' : 'text-text-primary'}`}
                      title={entryIsDeferred
                        ? 'Model-derived structural baseline materially below current price; tactical entries require regime reset or signal alignment.'
                        : undefined}
                    >
                      {entryIsDeferred
                        ? 'Entry Deferred — Valuation Regime Extended'
                        : proximityStatus === 'CRITICAL' && new_buyers.action === 'BUY NOW'
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
