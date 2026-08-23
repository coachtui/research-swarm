'use client'

import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Legend,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import { ArrowUpRight, FileText } from 'lucide-react'
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Skeleton } from '@/components/ui/skeleton'
import { useQuarterlies } from '@/lib/hooks/useAdmin'
import type { QuarterlyReview } from '@/types/api'

// Sleeve A / Sleeve B / benchmark. Validated for colour-vision separation and
// deliberately the same three colours the written quarterly reports use, so a
// reader moving between this tab and a report does not have to relearn them.
const COLORS = {
  A: '#3987E5',
  B: '#D95926',
  SPY: '#8A93A1',
  grid: '#252B3D',
  text: '#9CA3AF',
}

const SLEEVE_LABEL: Record<string, string> = {
  A: 'Sleeve A · thesis-hold stocks',
  B: 'Sleeve B · mechanical ETF rotation',
}

function pct(v: number | null | undefined): string {
  if (v == null) return '—'
  return `${v > 0 ? '+' : ''}${v.toFixed(2)}%`
}

function toneFor(v: number | null | undefined): string {
  if (v == null) return 'text-text-secondary'
  if (v > 0) return 'text-accent'
  if (v < 0) return 'text-error'
  return 'text-text-primary'
}

/** One row per quarter, one numeric key per series — a grouped bar chart. */
function toChartRows(quarters: QuarterlyReview[]) {
  return quarters.map((q) => {
    const row: Record<string, string | number | null> = {
      quarter: q.complete ? q.quarter : `${q.quarter} *`,
      SPY: q.benchmark_return_pct,
    }
    for (const s of q.sleeves) row[s.sleeve] = s.return_pct
    return row
  })
}

function ChartTooltip({ active, payload, label }: any) {
  if (!active || !payload?.length) return null
  return (
    <div className="rounded border border-hairline bg-surface-elevated px-3 py-2 text-xs shadow-lg">
      <div className="mb-1 font-semibold text-text-primary">{label}</div>
      {payload.map((p: any) => (
        <div key={p.dataKey} className="flex items-center justify-between gap-4">
          <span className="flex items-center gap-1.5 text-text-secondary">
            <span
              className="inline-block h-2 w-2 rounded-sm"
              style={{ backgroundColor: p.fill }}
            />
            {p.dataKey === 'SPY' ? 'SPY' : `Sleeve ${p.dataKey}`}
          </span>
          <span className="font-mono tabular-nums text-text-primary">
            {pct(p.value)}
          </span>
        </div>
      ))}
    </div>
  )
}

function QuarterRow({ q }: { q: QuarterlyReview }) {
  const sleeves = [...q.sleeves].sort((a, b) => a.sleeve.localeCompare(b.sleeve))
  return (
    <div className="border-b border-hairline py-4 last:border-b-0">
      <div className="flex flex-wrap items-center gap-2">
        <span className="text-sm font-semibold text-text-primary">{q.quarter}</span>
        {!q.complete && <Badge variant="secondary">in progress</Badge>}
        <span className="text-xs text-text-secondary">
          {q.period_start} → {q.period_end} · {q.trading_days} trading days
        </span>

        {q.report_url ? (
          <a
            href={q.report_url}
            target="_blank"
            rel="noopener noreferrer"
            className="ml-auto inline-flex items-center gap-1 rounded border border-hairline px-2.5 py-1
                       text-xs font-medium text-text-primary transition-colors
                       hover:border-accent hover:text-accent
                       focus-visible:outline focus-visible:outline-2 focus-visible:outline-accent"
          >
            <FileText size={13} />
            {q.report_title || 'Open report'}
            <ArrowUpRight size={13} />
          </a>
        ) : (
          <span className="ml-auto text-xs text-text-secondary">No write-up yet</span>
        )}
      </div>

      <div className="mt-3 grid gap-2 sm:grid-cols-3">
        {sleeves.map((s) => (
          <div key={s.sleeve} className="rounded border border-hairline p-2.5">
            <div className="flex items-center gap-1.5 text-xs text-text-secondary">
              <span
                className="inline-block h-2 w-2 rounded-sm"
                style={{ backgroundColor: COLORS[s.sleeve as 'A' | 'B'] ?? COLORS.SPY }}
              />
              {SLEEVE_LABEL[s.sleeve] ?? `Sleeve ${s.sleeve}`}
            </div>
            <div className={`mt-1 font-mono text-lg tabular-nums ${toneFor(s.return_pct)}`}>
              {pct(s.return_pct)}
            </div>
            <div className="text-xs text-text-secondary">
              {pct(s.excess_pct)} vs SPY · {s.snapshots} snapshots
            </div>
          </div>
        ))}
        <div className="rounded border border-hairline p-2.5">
          <div className="flex items-center gap-1.5 text-xs text-text-secondary">
            <span
              className="inline-block h-2 w-2 rounded-sm"
              style={{ backgroundColor: COLORS.SPY }}
            />
            SPY benchmark
          </div>
          <div className={`mt-1 font-mono text-lg tabular-nums ${toneFor(q.benchmark_return_pct)}`}>
            {pct(q.benchmark_return_pct)}
          </div>
          <div className="text-xs text-text-secondary">
            {q.benchmark_start.toFixed(2)} → {q.benchmark_end.toFixed(2)}
          </div>
        </div>
      </div>
    </div>
  )
}

export function QuarterliesPanel() {
  const { data, isLoading, error } = useQuarterlies()

  const quarters = data ?? []
  const rows = toChartRows(quarters)
  const sleeveKeys = Array.from(
    new Set(quarters.flatMap((q) => q.sleeves.map((s) => s.sleeve))),
  ).sort()
  const anyIncomplete = quarters.some((q) => !q.complete)

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader>
          <CardTitle>Quarter over quarter</CardTitle>
        </CardHeader>
        <CardContent>
          {isLoading && <Skeleton className="h-64 w-full" />}

          {error && (
            <p className="py-8 text-center text-sm text-error">
              Could not load quarterly performance. Reload to try again.
            </p>
          )}

          {!isLoading && !error && quarters.length === 0 && (
            <p className="py-8 text-center text-sm text-text-secondary">
              No sleeve snapshots yet — the first quarter appears once the daily
              cron has recorded one.
            </p>
          )}

          {!isLoading && !error && quarters.length > 0 && (
            <>
              <ResponsiveContainer width="100%" height={280}>
                <BarChart data={rows} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke={COLORS.grid} vertical={false} />
                  <XAxis
                    dataKey="quarter"
                    stroke={COLORS.text}
                    tick={{ fontSize: 12 }}
                    tickLine={false}
                  />
                  <YAxis
                    stroke={COLORS.text}
                    tick={{ fontSize: 12 }}
                    tickLine={false}
                    axisLine={false}
                    tickFormatter={(v: number) => `${v}%`}
                  />
                  <ReferenceLine y={0} stroke={COLORS.text} strokeWidth={1} />
                  <Tooltip content={<ChartTooltip />} cursor={{ fillOpacity: 0.06 }} />
                  <Legend
                    wrapperStyle={{ fontSize: 12 }}
                    formatter={(v) => (v === 'SPY' ? 'SPY' : `Sleeve ${v}`)}
                  />
                  {sleeveKeys.map((k) => (
                    <Bar
                      key={k}
                      dataKey={k}
                      fill={COLORS[k as 'A' | 'B'] ?? COLORS.SPY}
                      radius={[3, 3, 0, 0]}
                      maxBarSize={44}
                    />
                  ))}
                  <Bar dataKey="SPY" fill={COLORS.SPY} radius={[3, 3, 0, 0]} maxBarSize={44}>
                    {rows.map((_, i) => (
                      <Cell key={i} fillOpacity={0.75} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
              <p className="mt-3 text-xs text-text-secondary">
                Each bar is that quarter&rsquo;s own return, not a running total, so a
                quarter never inherits the one before it.
                {anyIncomplete && ' Quarters marked * are still in progress.'}
              </p>
            </>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>All quarterlies</CardTitle>
        </CardHeader>
        <CardContent>
          {isLoading && (
            <div className="space-y-3">
              <Skeleton className="h-20 w-full" />
              <Skeleton className="h-20 w-full" />
            </div>
          )}
          {!isLoading && !error && quarters.length === 0 && (
            <p className="py-6 text-center text-sm text-text-secondary">
              Nothing to list yet.
            </p>
          )}
          {!isLoading &&
            !error &&
            [...quarters]
              .reverse()
              .map((q) => <QuarterRow key={q.quarter} q={q} />)}
        </CardContent>
      </Card>
    </div>
  )
}
