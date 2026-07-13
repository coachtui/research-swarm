import { useMemo, useState } from 'react'
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Skeleton } from '@/components/ui/skeleton'
import { useWeeklyBatchRuns, useWeeklyBatchRunDetail } from '@/lib/hooks/useAdmin'
import { formatDate } from '@/lib/utils/formatting'
import type {
  WeeklyBatchRunDetail,
  WeeklyBatchRunSummary,
  WeeklySignalRow,
} from '@/types/api'

type SortDir = 'asc' | 'desc'

const SIGNAL_SORT_DEFAULTS: Partial<Record<keyof WeeklySignalRow, SortDir>> = {
  ticker: 'asc',
  tier: 'asc',
  verdict: 'asc',
  screener_score: 'desc',
  escalation_score: 'desc',
}

function SortIndicator({ active, dir }: { active: boolean; dir: SortDir }) {
  if (!active) return null
  return <span className="ml-1">{dir === 'asc' ? '▲' : '▼'}</span>
}

const TIER_BADGE_VARIANT: Record<string, 'success' | 'warning' | 'secondary'> = {
  full: 'success',
  quant: 'secondary',
  engine_light: 'warning',
}

function FunnelStat({ label, value, sub }: { label: string; value: number | null; sub?: string }) {
  return (
    <div className="flex flex-col">
      <span className="text-text-tertiary text-xs uppercase tracking-wide">{label}</span>
      <span className="text-text-primary font-medium">{value ?? 'n/a'}</span>
      {sub && <span className="text-text-tertiary text-xs">{sub}</span>}
    </div>
  )
}

function FunnelArrow() {
  return <span className="text-text-tertiary">→</span>
}

function SortableHeader({
  field, label, sort, onSort, align,
}: {
  field: keyof WeeklySignalRow
  label: string
  sort: { field: keyof WeeklySignalRow; dir: SortDir }
  onSort: (field: keyof WeeklySignalRow) => void
  align: 'left' | 'right'
}) {
  return (
    <th className={`${align === 'right' ? 'text-right' : 'text-left'} py-2 px-2 font-medium`}>
      <button
        type="button"
        onClick={() => onSort(field)}
        className={`flex items-center hover:text-text-primary ${align === 'right' ? 'justify-end w-full' : ''}`}
      >
        {label}
        <SortIndicator active={sort.field === field} dir={sort.dir} />
      </button>
    </th>
  )
}

export function WeeklyBatchPanel() {
  const { data: runs } = useWeeklyBatchRuns()
  const [selectedRunDate, setSelectedRunDate] = useState<string | undefined>(undefined)
  const { data, isLoading, error } = useWeeklyBatchRunDetail(selectedRunDate)

  if (isLoading) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Monday Batch</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="space-y-4">
            {[1, 2, 3].map((i) => (
              <Skeleton key={i} className="h-16" />
            ))}
          </div>
        </CardContent>
      </Card>
    )
  }

  if (error && (error as any).status === 404) {
    return (
      <Card>
        <CardContent className="py-12 text-center">
          <p className="text-text-secondary">
            No batch run yet — first one generates Monday morning.
          </p>
        </CardContent>
      </Card>
    )
  }

  if (error || !data) {
    return (
      <Card>
        <CardContent className="py-12 text-center">
          <p className="text-text-secondary">Failed to load batch run</p>
        </CardContent>
      </Card>
    )
  }

  return (
    <WeeklyBatchContent
      run={data}
      history={runs ?? []}
      selectedRunDate={selectedRunDate}
      onSelectRunDate={setSelectedRunDate}
    />
  )
}

function WeeklyBatchContent({
  run,
  history,
  selectedRunDate,
  onSelectRunDate,
}: {
  run: WeeklyBatchRunDetail
  history: WeeklyBatchRunSummary[]
  selectedRunDate: string | undefined
  onSelectRunDate: (runDate: string | undefined) => void
}) {
  const [signalSort, setSignalSort] = useState<{ field: keyof WeeklySignalRow; dir: SortDir }>({
    field: 'escalation_score',
    dir: 'desc',
  })

  function toggleSignalSort(field: keyof WeeklySignalRow) {
    setSignalSort((prev) =>
      prev.field === field
        ? { field, dir: prev.dir === 'asc' ? 'desc' : 'asc' }
        : { field, dir: SIGNAL_SORT_DEFAULTS[field] ?? 'asc' }
    )
  }

  const sortedSignals = useMemo(() => {
    const rows = [...run.signals]
    const { field, dir } = signalSort
    rows.sort((a, b) => {
      const av = a[field]
      const bv = b[field]
      if (av === null && bv === null) return 0
      if (av === null) return 1
      if (bv === null) return -1
      if (typeof av === 'string' && typeof bv === 'string') {
        return dir === 'asc' ? av.localeCompare(bv) : bv.localeCompare(av)
      }
      return dir === 'asc' ? (av as number) - (bv as number) : (bv as number) - (av as number)
    })
    return rows
  }, [run.signals, signalSort])

  const totalEscalated =
    run.escalation_swarm !== null && run.escalation_reuse !== null && run.escalation_hold !== null
      ? run.escalation_swarm + run.escalation_reuse + run.escalation_hold
      : null

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader>
          <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2">
            <CardTitle>Monday Batch</CardTitle>
            <div className="flex items-center gap-2">
              <span className="text-sm text-text-secondary">Week of {formatDate(run.run_date)}</span>
              {history.length > 1 && (
                <select
                  className="text-sm bg-surface border border-surface-elevated rounded px-2 py-1"
                  value={selectedRunDate ?? history[0]?.run_date ?? ''}
                  onChange={(e) => {
                    const val = e.target.value
                    onSelectRunDate(val === history[0]?.run_date ? undefined : val)
                  }}
                >
                  {history.map((h) => (
                    <option key={h.id} value={h.run_date}>
                      {formatDate(h.run_date)} ({h.status})
                    </option>
                  ))}
                </select>
              )}
            </div>
          </div>
        </CardHeader>
        <CardContent className="space-y-4">
          {run.status === 'aborted' ? (
            <div className="flex items-center gap-2 text-sm text-error">
              <Badge variant="error">Aborted</Badge>
              <span>{run.abort_reason ?? 'unknown reason'}</span>
            </div>
          ) : (
            <div className="flex flex-wrap items-center gap-4 text-sm">
              <FunnelStat label="Screened" value={run.universe_size} />
              <FunnelArrow />
              <FunnelStat
                label="Advanced"
                value={run.advanced_count}
                sub={run.watchlist_extras ? `${run.watchlist_extras} watchlist` : undefined}
              />
              <FunnelArrow />
              <FunnelStat
                label="Quant stored"
                value={run.quant_stored}
                sub={run.quant_failed ? `${run.quant_failed} failed` : undefined}
              />
              <FunnelArrow />
              <FunnelStat
                label="Escalated"
                value={totalEscalated}
                sub={`${run.escalation_swarm ?? 0} swarm / ${run.escalation_reuse ?? 0} reuse / ${run.escalation_hold ?? 0} hold`}
              />
              <FunnelArrow />
              <FunnelStat
                label="Swarm used"
                value={run.escalation_swarm}
                sub={run.swarm_cap !== null ? `of ${run.swarm_cap} cap` : undefined}
              />
            </div>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Escalated Tickers</CardTitle>
        </CardHeader>
        <CardContent>
          {run.signals.length === 0 ? (
            <p className="text-sm text-text-secondary">No escalated tickers this run.</p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-xs">
                <thead>
                  <tr className="border-b border-surface-elevated text-text-secondary uppercase tracking-wide">
                    <SortableHeader field="ticker" label="Ticker" sort={signalSort} onSort={toggleSignalSort} align="left" />
                    <SortableHeader field="tier" label="Tier" sort={signalSort} onSort={toggleSignalSort} align="left" />
                    <SortableHeader field="verdict" label="Verdict" sort={signalSort} onSort={toggleSignalSort} align="left" />
                    <SortableHeader field="screener_score" label="Screener" sort={signalSort} onSort={toggleSignalSort} align="right" />
                    <SortableHeader field="escalation_score" label="Escalation" sort={signalSort} onSort={toggleSignalSort} align="right" />
                    <th className="text-left py-2 pl-2 font-medium">Reasons</th>
                  </tr>
                </thead>
                <tbody>
                  {sortedSignals.map((row) => (
                    <tr key={row.ticker} className="border-b border-surface-elevated/30">
                      <td className="py-2 pr-3 text-text-primary font-medium">{row.ticker}</td>
                      <td className="py-2 px-2">
                        <Badge variant={TIER_BADGE_VARIANT[row.tier] ?? 'secondary'}>{row.tier}</Badge>
                      </td>
                      <td className="py-2 px-2 text-text-secondary">{row.verdict ?? 'n/a'}</td>
                      <td className="text-right py-2 px-2 text-text-secondary">
                        {row.screener_score !== null ? row.screener_score.toFixed(2) : 'n/a'}
                      </td>
                      <td className="text-right py-2 px-2 text-text-secondary">
                        {row.escalation_score !== null ? row.escalation_score.toFixed(2) : 'n/a'}
                      </td>
                      <td className="py-2 pl-2 text-text-tertiary">
                        {row.escalation_reasons?.join(', ') ?? '—'}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  )
}
