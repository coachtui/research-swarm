'use client'

import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Skeleton } from '@/components/ui/skeleton'
import { useWeek } from '@/lib/hooks/useAdmin'
import { PositionCard } from './PositionCard'
import { DecisionsSection } from './DecisionsSection'
import { NoBuyBanner } from './NoBuyBanner'
import type { WeekResponse } from '@/types/api'

/**
 * One page for the whole week: what we own, what we're bidding for, what we
 * decided against — each with the memo's own words attached.
 *
 * Positions come from the BROKER, not EnginePosition: the engine's book is a
 * mirror that syncs once a day, so showing the mirror can disagree with what is
 * actually held.
 */

const STAGE_TONE: Record<string, string> = {
  pre_consensus: 'bg-teal-100 text-teal-900 dark:bg-teal-950 dark:text-teal-200',
  catching_on: 'bg-green-100 text-green-900 dark:bg-green-950 dark:text-green-200',
  crowded: 'bg-amber-100 text-amber-900 dark:bg-amber-950 dark:text-amber-200',
  priced: 'bg-red-100 text-red-900 dark:bg-red-950 dark:text-red-200',
}

const money = (n: number | null | undefined) =>
  n == null ? '—' : n.toLocaleString('en-US', { style: 'currency', currency: 'USD', maximumFractionDigits: 0 })

function Stat({ label, value, tone }: { label: string; value: string; tone?: string }) {
  return (
    <div className="flex-1 min-w-[7rem] border-r last:border-r-0 px-4 py-3">
      <div className={`font-mono text-xl font-semibold tabular-nums ${tone ?? ''}`}>{value}</div>
      <div className="text-[0.7rem] uppercase tracking-wider text-muted-foreground">{label}</div>
    </div>
  )
}

export function WeekPanel() {
  const { data, isLoading, error } = useWeek()

  if (isLoading) return <Skeleton className="h-96 w-full" />
  if (error || !data) {
    return (
      <Card>
        <CardContent className="py-8 text-sm text-muted-foreground">
          Could not load this week. The memo may not have run yet.
        </CardContent>
      </Card>
    )
  }

  const w: WeekResponse = data
  const totalPl = w.positions.reduce((s, p) => s + p.unrealized_pl, 0)
  const sleeveA = w.positions.filter((p) => p.sleeve === 'A')
  const orphans = sleeveA.filter((p) => p.themes.length === 0)

  return (
    <div className="flex flex-col gap-6">
      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="flex flex-wrap items-baseline gap-3">
            <span>Week of {w.week}</span>
            {w.regime && <Badge variant="secondary">regime {w.regime}</Badge>}
            {!w.broker_ok && (
              <Badge variant="warning">broker unreachable — positions may be stale</Badge>
            )}
          </CardTitle>
          {w.market_view && (
            <p className="text-sm text-muted-foreground max-w-[80ch]">{w.market_view}</p>
          )}
        </CardHeader>
        <CardContent className="p-0">
          <div className="flex flex-wrap border-t">
            <Stat label="equity" value={money(w.equity)} />
            <Stat label="cash" value={money(w.cash)} />
            <Stat
              label="open P&L"
              value={`${totalPl >= 0 ? '+' : ''}${totalPl.toFixed(0)}`}
              tone={totalPl >= 0 ? 'text-emerald-600' : 'text-red-600'}
            />
            <Stat label="positions" value={String(w.positions.length)} />
            <Stat label="orders working" value={String(w.open_orders.length)} />
            {orphans.length > 0 && (
              <Stat label="without a thesis" value={String(orphans.length)} tone="text-amber-600" />
            )}
          </div>
        </CardContent>
      </Card>

      <NoBuyBanner week={w} />

      {w.macro_reasoning && (
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-xs uppercase tracking-wider text-muted-foreground">
              Macro read — the why behind the regime
            </CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-sm text-muted-foreground max-w-[75ch] whitespace-pre-line">
              {w.macro_reasoning}
            </p>
          </CardContent>
        </Card>
      )}

      {w.theses.length > 0 && (
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-xs uppercase tracking-wider text-muted-foreground">
              Theses — new buys are legal only in pre-consensus and catching on
            </CardTitle>
          </CardHeader>
          <CardContent className="flex flex-col gap-3">
            {w.theses.map((t) => (
              <div key={t.slug}>
                <div className="flex items-baseline gap-2">
                  <span className="font-mono text-sm font-semibold">{t.slug}</span>
                  <span
                    className={`text-[0.62rem] uppercase tracking-wider px-1.5 py-0.5 rounded ${
                      STAGE_TONE[t.stage ?? ''] ?? 'bg-muted'
                    }`}
                  >
                    {(t.stage ?? 'unstaged').replace('_', ' ')}
                  </span>
                </div>
                {t.stage_rationale && (
                  <p className="mt-1 text-sm text-muted-foreground max-w-[72ch]">{t.stage_rationale}</p>
                )}
              </div>
            ))}
          </CardContent>
        </Card>
      )}

      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-xs uppercase tracking-wider text-muted-foreground">
            Positions — as the broker holds them
          </CardTitle>
        </CardHeader>
        <CardContent>
          {w.positions.map((p) => <PositionCard key={p.symbol} p={p} />)}
        </CardContent>
      </Card>

      {w.open_orders.length > 0 && (
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-xs uppercase tracking-wider text-muted-foreground">
              Working orders — the price we are bidding
            </CardTitle>
          </CardHeader>
          <CardContent>
            {w.open_orders.map((o) => (
              <div key={o.symbol + o.submitted} className="border-b last:border-b-0 py-2 flex flex-wrap gap-x-4 items-baseline">
                <span className="font-mono font-semibold">{o.symbol}</span>
                <span className="text-sm text-muted-foreground">{o.side}</span>
                <span className="font-mono text-sm tabular-nums">
                  {o.qty} sh @ {money(o.limit_price)}
                </span>
                <span className="ml-auto text-xs text-muted-foreground">
                  {o.status.toLowerCase()} · placed {o.submitted}
                </span>
              </div>
            ))}
          </CardContent>
        </Card>
      )}

      <DecisionsSection actions={w.actions} />
    </div>
  )
}
