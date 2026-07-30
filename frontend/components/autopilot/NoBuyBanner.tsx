'use client'

import { Card, CardContent } from '@/components/ui/card'
import type { WeekResponse } from '@/types/api'

/** A week with zero buys is a DECISION, not an empty page. Rendered only when
 * the memo ran (market_view exists) and placed no entries. */
export function NoBuyBanner({ week }: { week: WeekResponse }) {
  const boughtSomething =
    week.open_orders.some((o) => o.side === 'buy') ||
    week.actions.some((a) => a.outcome === 'not_placed') ||
    week.positions.some((p) => p.why_now != null)
  if (boughtSomething || !week.market_view) return null
  return (
    <Card className="border-amber-300/60 dark:border-amber-800/60">
      <CardContent className="py-4">
        <div className="text-[0.65rem] uppercase tracking-wider font-semibold text-amber-700 dark:text-amber-400">
          Nothing at attractive prices this week
        </div>
        <p className="mt-1.5 text-sm text-muted-foreground max-w-[80ch]">{week.market_view}</p>
      </CardContent>
    </Card>
  )
}
