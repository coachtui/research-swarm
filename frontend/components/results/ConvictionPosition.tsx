import { Card, CardContent } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { formatCurrency } from '@/lib/utils/formatting'
import type { ConvictionPosition as ConvictionPositionType } from '@/types/api'

interface ConvictionPositionProps {
  position: ConvictionPositionType
}

function convictionVariant(level: string): 'success' | 'warning' | 'error' {
  if (level === 'High') return 'success'
  if (level === 'Medium') return 'warning'
  return 'error'
}

export function ConvictionPosition({ position }: ConvictionPositionProps) {
  return (
    <Card>
      <CardContent className="pt-6">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          {/* Left: Conviction label */}
          <div className="space-y-1">
            <div className="flex items-center gap-2">
              <span className="text-sm font-medium text-text-secondary">Conviction Level</span>
              <Badge variant={convictionVariant(position.conviction_level)}>
                {position.conviction_level}
              </Badge>
            </div>
            <p className="text-xs text-text-tertiary max-w-md">
              {position.conviction_justification}
            </p>
          </div>

          {/* Right: Position sizing */}
          <div className="flex items-center gap-6">
            <div className="text-center">
              <span className="text-xs text-text-tertiary block">Recommended</span>
              <span className="text-lg font-bold text-text-primary">
                {position.recommended_pct}%
              </span>
            </div>
            <div className="text-center">
              <span className="text-xs text-text-tertiary block">Max</span>
              <span className="text-lg font-bold text-text-secondary">
                {position.max_pct}%
              </span>
            </div>
            <div className="text-center">
              <span className="text-xs text-text-tertiary block">Per $100K</span>
              <span className="text-lg font-bold text-primary">
                {formatCurrency(position.dollar_per_100k, 0)}
              </span>
            </div>
          </div>
        </div>
      </CardContent>
    </Card>
  )
}
