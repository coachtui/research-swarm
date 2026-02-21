// All values are received as props — no calculations exist in this component.
// Changes: conviction-anchored allocation range bar, contextual sizing labels,
// and institutional framing for the three key parameters. No data altered.

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
  // Visual allocation bar: recommended fills the primary portion, remaining to max is lighter.
  // Uses max_pct as the 100% anchor so the bar is always self-contained.
  const recFraction = position.max_pct > 0
    ? Math.min((position.recommended_pct / position.max_pct) * 100, 100)
    : 0

  return (
    <Card>
      <CardContent className="pt-6">
        <div className="flex flex-col md:flex-row md:items-start justify-between gap-4">

          {/* Left: Conviction label + justification */}
          <div className="space-y-1 flex-1 min-w-0">
            <div className="flex items-center gap-2">
              <span className="text-xs font-semibold text-text-tertiary uppercase tracking-wider">
                Conviction Level
              </span>
              <Badge variant={convictionVariant(position.conviction_level)}>
                {position.conviction_level}
              </Badge>
            </div>
            <p className="text-xs text-text-tertiary max-w-md leading-relaxed">
              {position.conviction_justification}
            </p>

            {/* Conviction-anchored allocation range bar */}
            <div className="mt-3 max-w-xs">
              <div className="flex items-center justify-between text-[10px] text-text-tertiary mb-1">
                <span className="uppercase tracking-wider font-medium">Allocation Range</span>
                <span className="font-mono">{position.recommended_pct}% rec · {position.max_pct}% ceil</span>
              </div>
              <div className="h-2 bg-surface-elevated rounded-full overflow-hidden flex">
                {/* Recommended portion — primary fill */}
                <div
                  className="h-full bg-primary rounded-l-full transition-all"
                  style={{ width: `${recFraction}%` }}
                />
                {/* Remaining capacity to max — lighter fill */}
                <div
                  className="h-full bg-primary/20 transition-all"
                  style={{ width: `${100 - recFraction}%` }}
                />
              </div>
              <div className="flex items-center justify-between text-[10px] mt-0.5">
                <span className="text-primary font-medium">
                  {position.recommended_pct}% base conviction
                </span>
                <span className="text-text-tertiary/60">
                  {position.max_pct}% risk ceiling
                </span>
              </div>
            </div>
          </div>

          {/* Right: The three sizing parameters with institutional labels */}
          <div className="flex items-start gap-5 shrink-0">
            <div className="text-center">
              <span className="text-[10px] text-text-tertiary/70 block uppercase tracking-wider mb-1">
                Base Allocation
              </span>
              <span className="text-lg font-bold text-text-primary">
                {position.recommended_pct}%
              </span>
              <span className="text-[10px] text-text-tertiary block mt-0.5">recommended</span>
            </div>
            <div className="text-center">
              <span className="text-[10px] text-text-tertiary/70 block uppercase tracking-wider mb-1">
                Risk Ceiling
              </span>
              <span className="text-lg font-bold text-text-secondary">
                {position.max_pct}%
              </span>
              <span className="text-[10px] text-text-tertiary block mt-0.5">full-conviction max</span>
            </div>
            <div className="text-center">
              <span className="text-[10px] text-text-tertiary/70 block uppercase tracking-wider mb-1">
                Per $100K
              </span>
              <span className="text-lg font-bold text-primary">
                {formatCurrency(position.dollar_per_100k, 0)}
              </span>
              <span className="text-[10px] text-text-tertiary block mt-0.5">exposure basis</span>
            </div>
          </div>
        </div>
      </CardContent>
    </Card>
  )
}
