import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { formatCurrency } from '@/lib/utils/formatting'
import type { EnhancedTradeSetup, TradeSetupSide } from '@/types/api'

interface TradeSetupProps {
  setup: EnhancedTradeSetup
  ticker: string
}

function SetupColumn({ side, variant }: { side: TradeSetupSide; variant: 'conservative' | 'aggressive' }) {
  const borderColor = variant === 'conservative' ? 'border-success/30' : 'border-warning/30'
  const headerBg = variant === 'conservative' ? 'bg-success/5' : 'bg-warning/5'

  return (
    <div className={`rounded-lg border ${borderColor} overflow-hidden`}>
      {/* Header */}
      <div className={`px-4 py-3 ${headerBg}`}>
        <div className="flex items-center justify-between">
          <span className="text-sm font-semibold text-text-primary">{side.label}</span>
          <Badge variant={variant === 'conservative' ? 'success' : 'warning'}>
            {side.risk_reward}:1 R/R
          </Badge>
        </div>
      </div>

      {/* Body */}
      <div className="p-4 space-y-3">
        {/* Entry & Stop */}
        <div className="grid grid-cols-2 gap-3">
          <div>
            <span className="text-xs text-text-tertiary block">Entry</span>
            <span className="text-sm font-semibold text-text-primary">
              {formatCurrency(side.entry)}
            </span>
          </div>
          <div>
            <span className="text-xs text-text-tertiary block">Stop Loss</span>
            <span className="text-sm font-semibold text-error">
              {formatCurrency(side.stop_loss)}
            </span>
          </div>
        </div>

        {/* Targets */}
        <div className="space-y-2">
          <span className="text-xs text-text-tertiary block">Profit Targets</span>
          {side.targets.map((t, i) => (
            <div key={i} className="flex items-center justify-between text-sm">
              <span className="text-text-secondary">{t.label}</span>
              <div className="flex items-center gap-2">
                <span className="font-medium text-success">{formatCurrency(t.price)}</span>
                <span className="text-xs text-text-tertiary">Sell {t.sell_pct}%</span>
              </div>
            </div>
          ))}
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

export function TradeSetup({ setup, ticker }: TradeSetupProps) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Trade Setup Options</CardTitle>
      </CardHeader>
      <CardContent>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <SetupColumn side={setup.conservative} variant="conservative" />
          <SetupColumn side={setup.aggressive} variant="aggressive" />
        </div>
      </CardContent>
    </Card>
  )
}
