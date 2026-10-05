'use client'

import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Skeleton } from '@/components/ui/skeleton'
import { useWeek } from '@/lib/hooks/useAdmin'
import { PositionCard } from './PositionCard'
import { DecisionsSection } from './DecisionsSection'
import { NoBuyBanner } from './NoBuyBanner'
import { ChangesSection } from './ChangesSection'
import { HypothesesSection } from './HypothesesSection'
import { ThemeRow, StageChip } from './ThemeRow'
import type { WeekPosition, WeekResponse, WeekTheme } from '@/types/api'

/**
 * The weekly decision view, read once a week in this order:
 *
 *   1. regime and leading constraints — the outlook's read, then every theme
 *      ranked, dated, and expandable to the names behind it
 *   2. what changed this week — new or removed names, themes, vetoes, failures
 *   3. what the engine decided — the memo's entries and what became of them
 *   4. the book — positions as the broker holds them, grouped by thesis
 *   5. open hypotheses — what the engine thinks binds next
 *
 * Every panel before this showed one stage's raw output. This page shows the
 * chain. Positions come from the BROKER, not EnginePosition: the engine's book
 * is a mirror that syncs once a day.
 */

const money = (n: number | null | undefined) =>
  n == null ? '—' : n.toLocaleString('en-US', { style: 'currency', currency: 'USD', maximumFractionDigits: 0 })

const REGIME_VARIANT: Record<string, 'success' | 'warning' | 'error' | 'secondary'> = {
  risk_on: 'success',
  neutral: 'warning',
  risk_off: 'error',
}

function Stat({ label, value, tone }: { label: string; value: string; tone?: string }) {
  return (
    <div className="flex-1 min-w-[7rem] border-r border-hairline last:border-r-0 px-4 py-3">
      <div className={`font-mono text-xl font-semibold tabular-nums ${tone ?? ''}`}>{value}</div>
      <div className="text-[0.7rem] uppercase tracking-wider text-text-secondary">{label}</div>
    </div>
  )
}

function SectionTitle({ children }: { children: React.ReactNode }) {
  return (
    <CardTitle className="text-xs uppercase tracking-wider text-text-secondary">{children}</CardTitle>
  )
}

/** Positions grouped by the thesis that sourced them; Sleeve B and untagged
 * names get their own groups so nothing is hidden. */
function groupPositions(positions: WeekPosition[], themes: WeekTheme[]) {
  const byTheme = new Map<string, WeekPosition[]>()
  const order = themes.map((t) => t.slug)
  const names = new Map(themes.map((t) => [t.slug, t.name]))
  const other: WeekPosition[] = []
  const sleeveB: WeekPosition[] = []
  for (const p of positions) {
    if (p.sleeve === 'B') { sleeveB.push(p); continue }
    const slug = p.themes[0]
    if (!slug) { other.push(p); continue }
    if (!byTheme.has(slug)) byTheme.set(slug, [])
    byTheme.get(slug)!.push(p)
  }
  const groups: { key: string; label: string; stage?: string | null; rows: WeekPosition[] }[] = []
  const seen = new Set<string>()
  for (const slug of order) {
    const rows = byTheme.get(slug)
    if (rows) {
      groups.push({ key: slug, label: names.get(slug) ?? slug, stage: themes.find((t) => t.slug === slug)?.stage, rows })
      seen.add(slug)
    }
  }
  for (const [slug, rows] of byTheme) {
    if (!seen.has(slug)) groups.push({ key: slug, label: slug, rows })
  }
  if (other.length) groups.push({ key: '_untagged', label: 'No thesis recorded', rows: other })
  if (sleeveB.length) groups.push({ key: '_sleeveB', label: 'Sleeve B — mechanical ETF rotation', rows: sleeveB })
  return groups
}

export function WeekPanel() {
  const { data, isLoading, error } = useWeek()

  if (isLoading) return <Skeleton className="h-96 w-full" />
  if (error || !data) {
    return (
      <Card>
        <CardContent className="py-8 text-sm text-text-secondary">
          Could not load this week. The memo may not have run yet.
        </CardContent>
      </Card>
    )
  }

  const w: WeekResponse = data
  const themes = w.themes_ranked ?? []
  const changes = w.changes ?? []
  const hypotheses = w.hypotheses ?? []
  const totalPl = w.positions.reduce((s, p) => s + p.unrealized_pl, 0)
  const sleeveA = w.positions.filter((p) => p.sleeve === 'A')
  const orphans = sleeveA.filter((p) => p.themes.length === 0)
  const invested = w.equity ? w.positions.reduce((s, p) => s + p.market_value, 0) / w.equity : null
  const vetoed = w.actions.filter((a) => a.outcome === 'vetoed').length
  const placed = w.actions.filter((a) => a.outcome === 'placed').length
  const groups = groupPositions(w.positions, themes)
  const leading = themes.filter((t) => t.flag === 'into')
  const fading = themes.filter((t) => t.flag === 'out_of')

  return (
    <div className="flex flex-col gap-6">
      {/* 1 ── Regime and leading constraints */}
      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="flex flex-wrap items-baseline gap-3">
            <span>Week of {w.week}</span>
            {w.regime && (
              <Badge variant={REGIME_VARIANT[w.regime] ?? 'secondary'}>
                {w.regime.replace('_', ' ')}
              </Badge>
            )}
            {!w.broker_ok && (
              <Badge variant="warning">broker unreachable — positions may be stale</Badge>
            )}
          </CardTitle>
          {w.market_view && (
            <p className="text-sm text-text-secondary max-w-[80ch]">{w.market_view}</p>
          )}
        </CardHeader>
        <CardContent className="p-0">
          <div className="flex flex-wrap border-t border-hairline">
            <Stat label="equity" value={money(w.equity)} />
            <Stat label="invested" value={invested == null ? '—' : `${(invested * 100).toFixed(0)}%`} />
            <Stat
              label="open P&L"
              value={`${totalPl >= 0 ? '+' : ''}${totalPl.toFixed(0)}`}
              tone={totalPl >= 0 ? 'text-success' : 'text-error'}
            />
            <Stat label="positions" value={String(w.positions.length)} />
            <Stat label="orders working" value={String(w.open_orders.length)} />
            <Stat label="placed this week" value={String(placed)} tone={placed > 0 ? 'text-success' : undefined} />
            <Stat label="vetoed this week" value={String(vetoed)} tone={vetoed > 0 ? 'text-error' : undefined} />
            {orphans.length > 0 && (
              <Stat label="without a thesis" value={String(orphans.length)} tone="text-warning" />
            )}
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader className="pb-2">
          <SectionTitle>
            Leading constraints — themes ranked by relative strength, dated from the first week the rotation held
          </SectionTitle>
          {(leading.length > 0 || fading.length > 0) && (
            <p className="text-sm text-text-secondary">
              {leading.length > 0 && (
                <>Rotating in: {leading.map((t) => t.name).join(', ')}. </>
              )}
              {fading.length > 0 && (
                <>Rotating out: {fading.map((t) => t.name).join(', ')}.</>
              )}
            </p>
          )}
        </CardHeader>
        <CardContent className="pt-0">
          {themes.length === 0 ? (
            <p className="text-sm italic text-text-secondary">No ranked themes yet. The Sunday outlook ranks them.</p>
          ) : (
            themes.map((t, i) => (
              <ThemeRow
                key={t.slug}
                rank={t.rank_1m == null ? null : i + 1}
                slug={t.slug}
                name={t.name}
                stage={t.stage}
                rankChange={t.rank_change}
                score={t.score}
                flag={t.flag}
                since={t.since}
                weeks={t.weeks}
                constituents={t.constituents}
                history={t.history}
              />
            ))
          )}
          {w.theses.some((t) => t.stage_rationale) && (
            <details className="mt-3">
              <summary className="text-xs uppercase tracking-wider text-text-secondary cursor-pointer">
                Stage calls from this week&apos;s memo
              </summary>
              <div className="mt-2 flex flex-col gap-2">
                {w.theses.filter((t) => t.stage_rationale).map((t) => (
                  <div key={t.slug} className="text-sm">
                    <span className="font-mono font-semibold mr-2">{t.slug}</span>
                    <StageChip stage={t.stage} />
                    <p className="mt-1 text-text-secondary max-w-[72ch]">{t.stage_rationale}</p>
                  </div>
                ))}
              </div>
            </details>
          )}
        </CardContent>
      </Card>

      {w.macro_reasoning && (
        <details className="group">
          <summary className="text-xs uppercase tracking-wider text-text-secondary cursor-pointer px-1">
            Macro read — the why behind the regime
          </summary>
          <Card className="mt-2">
            <CardContent className="py-4">
              <p className="text-sm text-text-secondary max-w-[75ch] whitespace-pre-line">{w.macro_reasoning}</p>
            </CardContent>
          </Card>
        </details>
      )}

      {/* 2 ── What changed */}
      <ChangesSection changes={changes} />

      {/* 3 ── What the engine decided */}
      <NoBuyBanner week={w} />
      <DecisionsSection actions={w.actions} />

      {w.open_orders.length > 0 && (
        <Card>
          <CardHeader className="pb-2">
            <SectionTitle>Working orders — the price we are bidding</SectionTitle>
          </CardHeader>
          <CardContent>
            {w.open_orders.map((o) => (
              <div key={o.symbol + o.submitted} className="border-b border-hairline last:border-b-0 py-2 flex flex-wrap gap-x-4 items-baseline">
                <span className="font-mono font-semibold">{o.symbol}</span>
                <span className="text-sm text-text-secondary">{o.side}</span>
                <span className="font-mono text-sm tabular-nums">
                  {o.qty} sh @ {money(o.limit_price)}
                </span>
                <span className="ml-auto text-xs text-text-secondary">
                  {o.status.toLowerCase()} · placed {o.submitted}
                </span>
              </div>
            ))}
          </CardContent>
        </Card>
      )}

      {/* 4 ── The book */}
      <Card>
        <CardHeader className="pb-2">
          <SectionTitle>The book — positions as the broker holds them, grouped by thesis</SectionTitle>
        </CardHeader>
        <CardContent className="flex flex-col gap-5">
          {groups.length === 0 && (
            <p className="text-sm italic text-text-secondary">No open positions.</p>
          )}
          {groups.map((g) => {
            const pl = g.rows.reduce((s, p) => s + p.unrealized_pl, 0)
            const mv = g.rows.reduce((s, p) => s + p.market_value, 0)
            return (
              <div key={g.key}>
                <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1 mb-1">
                  <span className="text-sm font-medium text-text-primary">{g.label}</span>
                  <StageChip stage={g.stage} />
                  <span className="text-xs text-text-tertiary">{g.rows.length} {g.rows.length === 1 ? 'name' : 'names'}</span>
                  <span className="ml-auto font-mono text-xs tabular-nums text-text-secondary">{money(mv)}</span>
                  <span className={`font-mono text-xs tabular-nums ${pl >= 0 ? 'text-success' : 'text-error'}`}>
                    {pl >= 0 ? '+' : ''}{pl.toFixed(0)}
                  </span>
                </div>
                <div className="border-t border-hairline">
                  {g.rows.map((p) => <PositionCard key={p.symbol} p={p} />)}
                </div>
              </div>
            )
          })}
        </CardContent>
      </Card>

      {/* 5 ── Open hypotheses */}
      <HypothesesSection hypotheses={hypotheses} />
    </div>
  )
}
