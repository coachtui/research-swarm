import { Card, CardContent } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import type { DecisionFramework } from '@/types/api'

interface DecisionActionProps {
  framework: DecisionFramework
  ticker: string
  rating: string | null
  riskLevel: string | null
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
      return 'error'
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

export function DecisionAction({ framework, ticker, rating, riskLevel }: DecisionActionProps) {
  const { current_holders, new_buyers, one_liner } = framework

  return (
    <Card className="border-primary/30 bg-surface">
      <CardContent className="pt-6 space-y-5">
        {/* One-liner header */}
        <div className="flex flex-col gap-3">
          <div className="flex items-center gap-2 flex-wrap">
            <h2 className="text-lg font-bold text-text-primary">ACTION</h2>
            {rating && (
              <Badge variant={ratingToBadgeVariant(rating)}>{rating}</Badge>
            )}
            {riskLevel && (
              <Badge variant="secondary">{riskLevel} Risk</Badge>
            )}
          </div>
          <p className="text-base font-semibold text-text-primary leading-relaxed">{one_liner}</p>
        </div>

        {/* Two-column guidance */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {/* Current Holders */}
          <div className="rounded-lg border border-surface-elevated p-4 space-y-3">
            <div className="flex items-center gap-2">
              <span className="text-sm font-medium text-text-secondary">Current Holders</span>
              <Badge variant={actionToBadgeVariant(current_holders.action)}>
                {current_holders.action}
              </Badge>
            </div>
            <p className="text-sm text-text-secondary leading-relaxed">
              {current_holders.detail}
            </p>
            {current_holders.conditions.length > 0 && (
              <ul className="space-y-1">
                {current_holders.conditions.map((c, i) => (
                  <li key={i} className="text-xs text-text-tertiary flex items-start gap-1.5">
                    <span className="mt-1 w-1 h-1 rounded-full bg-text-tertiary flex-shrink-0" />
                    {c}
                  </li>
                ))}
              </ul>
            )}
          </div>

          {/* New Buyers */}
          <div className="rounded-lg border border-surface-elevated p-4 space-y-3">
            <div className="flex items-center gap-2">
              <span className="text-sm font-medium text-text-secondary">New Buyers</span>
              <Badge variant={actionToBadgeVariant(new_buyers.action)}>
                {new_buyers.action}
              </Badge>
            </div>

            {/* Urgency Heat Map */}
            {new_buyers.urgency && new_buyers.urgency !== 'N/A' && (
              <div className="space-y-1.5">
                <div className="flex items-center justify-between text-xs">
                  <span className="text-text-tertiary">Entry Urgency</span>
                  <span className="font-medium text-text-primary">{new_buyers.urgency}</span>
                </div>
                <div className="relative h-2 bg-surface-elevated rounded-full overflow-hidden">
                  <div
                    className={`absolute inset-y-0 left-0 rounded-full transition-all ${
                      new_buyers.urgency.toLowerCase().includes('high')
                        ? 'bg-error w-[85%]'
                        : new_buyers.urgency.toLowerCase().includes('medium')
                        ? 'bg-warning w-[55%]'
                        : 'bg-success w-[25%]'
                    }`}
                  />
                </div>
                <p className="text-xs text-text-tertiary">
                  {new_buyers.urgency.toLowerCase().includes('high')
                    ? 'Act quickly - favorable entry window may close soon'
                    : new_buyers.urgency.toLowerCase().includes('medium')
                    ? 'Moderate urgency - consider scaling in over time'
                    : 'Low urgency - plenty of time to wait for ideal entry'}
                </p>
              </div>
            )}

            <p className="text-sm text-text-secondary leading-relaxed">
              {new_buyers.detail}
            </p>

            {/* Educational info for limit orders */}
            {(new_buyers.detail.includes('limit') || new_buyers.detail.includes('alerts')) && (
              <div className="mt-2 p-2 bg-surface-elevated rounded border border-primary/20">
                <p className="text-xs text-text-tertiary leading-relaxed">
                  <span className="font-medium text-text-secondary">💡 Trading Tip:</span> A <span className="font-medium">market order</span> executes immediately at the current price.
                  {new_buyers.detail.includes('resistance') || new_buyers.detail.includes('momentum') || new_buyers.detail.includes('breaks above') ? (
                    <> A <span className="font-medium">buy limit above</span> current price triggers when the stock breaks through resistance, confirming bullish momentum (called a "breakout entry").</>
                  ) : (
                    <> A <span className="font-medium">buy limit below</span> current price executes only if the stock dips to your target, helping you get a better entry on pullbacks.</>
                  )}
                </p>
              </div>
            )}

            {new_buyers.caveat && (
              <p className="text-xs text-warning italic">
                {new_buyers.caveat}
              </p>
            )}
          </div>
        </div>
      </CardContent>
    </Card>
  )
}
