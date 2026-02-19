'use client'

import { useState } from 'react'
import { Card, CardContent } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { AlertTriangle, CheckCircle } from 'lucide-react'
import type { DecisionFramework, RecommendedStrategy, SignalBreakdown, FundTechDivergence } from '@/types/api'

interface DecisionActionProps {
  framework: DecisionFramework
  ticker: string
  rating: string | null
  riskLevel: string | null
  strategy?: RecommendedStrategy | null
  signalBreakdown?: SignalBreakdown | null
  fundTechDivergence?: FundTechDivergence | null
  convictionLevel?: string | null
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

export function DecisionAction({
  framework,
  rating,
  riskLevel,
  strategy,
  signalBreakdown,
  fundTechDivergence,
  convictionLevel,
}: DecisionActionProps) {
  const [tab, setTab] = useState<Tab>('new')
  const { current_holders, new_buyers, one_liner } = framework

  // Build price zones from strategy
  const entryZone = strategy?.entry?.ideal_zone
    ? formatZone(strategy.entry.ideal_zone.low, strategy.entry.ideal_zone.high)
    : strategy?.entry?.entry_zone_display?.label ?? null

  const stopZone = strategy?.exit?.stop_zone?.label
    ?? (strategy?.exit?.stop_loss ? `~$${Math.round(strategy.exit.stop_loss).toLocaleString()}` : null)

  const targetZone = strategy?.exit?.target_2?.price
    ? formatZone(strategy.exit.target_1?.price, strategy.exit.target_2?.price)
    : strategy?.exit?.target_1?.price ? `~$${Math.round(strategy.exit.target_1.price).toLocaleString()}` : null

  const avoidAbove = strategy?.entry?.ideal_zone?.high
    ? `$${Math.round(strategy.entry.ideal_zone.high * 1.05).toLocaleString()}+`
    : null

  // Signal status strip
  const hasDivergence = signalBreakdown?.has_divergence
  const divergenceSeverity = fundTechDivergence?.severity || (hasDivergence ? 'MODERATE' : null)

  return (
    <Card className="border-primary/30 bg-surface">
      <CardContent className="pt-6 space-y-5">

        {/* Decision Hero */}
        <div className="space-y-3">
          <div className="flex items-center gap-2 flex-wrap">
            {rating && (
              <Badge variant={ratingToBadgeVariant(rating)} className="text-base px-3 py-0.5">
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
            {hasDivergence ? (
              <>
                <AlertTriangle className="h-3.5 w-3.5 flex-shrink-0" />
                <span className="font-medium">Signal Conflict</span>
                <span className="text-text-secondary mx-1">·</span>
                <span className="text-text-secondary truncate">
                  {signalBreakdown.divergence_explanation?.split('.')[0]}
                </span>
                <span className="ml-auto whitespace-nowrap text-text-tertiary pl-2">See signals ↓</span>
              </>
            ) : (
              <>
                <CheckCircle className="h-3.5 w-3.5 flex-shrink-0" />
                <span className="font-medium">Signals Aligned</span>
                <span className="text-text-secondary mx-1">·</span>
                <span className="text-text-secondary">{signalBreakdown.alignment_status}</span>
                <span className="ml-auto whitespace-nowrap text-text-tertiary pl-2">See signals ↓</span>
              </>
            )}
          </div>
        )}

        {/* Key Price Zones Grid */}
        {(entryZone || stopZone || targetZone || avoidAbove) && (
          <div>
            <p className="text-xs font-medium text-text-tertiary uppercase tracking-wide mb-2">Key Price Zones</p>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
              {entryZone && (
                <div className="rounded-md bg-surface-elevated border border-border p-3 text-center">
                  <p className="text-xs text-text-tertiary mb-1">Entry Zone</p>
                  <p className="text-sm font-semibold text-success">{entryZone}</p>
                </div>
              )}
              {avoidAbove && (
                <div className="rounded-md bg-surface-elevated border border-border p-3 text-center">
                  <p className="text-xs text-text-tertiary mb-1">Avoid Above</p>
                  <p className="text-sm font-semibold text-error">{avoidAbove}</p>
                </div>
              )}
              {stopZone && (
                <div className="rounded-md bg-surface-elevated border border-border p-3 text-center">
                  <p className="text-xs text-text-tertiary mb-1">Stop Zone</p>
                  <p className="text-sm font-semibold text-error">{stopZone}</p>
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
                    <span className="font-medium text-text-primary">{new_buyers.urgency}</span>
                  </div>
                  <div className="relative h-1.5 bg-surface-elevated rounded-full overflow-hidden">
                    <div
                      className={`absolute inset-y-0 left-0 rounded-full ${
                        new_buyers.urgency.toLowerCase().includes('high')
                          ? 'bg-error w-[85%]'
                          : new_buyers.urgency.toLowerCase().includes('medium')
                          ? 'bg-warning w-[55%]'
                          : 'bg-success w-[25%]'
                      }`}
                    />
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
