'use client'

import { useEffect, useState } from 'react'
import { ChevronDown } from 'lucide-react'
import Link from 'next/link'
import { apiClient } from '@/lib/api/client'
import { InlineDisclaimer } from '@/components/ui/InlineDisclaimer'
import type { TrackRecordResponse, TrackRecordWeek } from '@/types/weekly-signals'

function formatRunDate(dateStr: string): string {
  const d = new Date(dateStr)
  return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })
}

function formatPrice(price: number | null): string {
  if (price == null) return '—'
  return `$${price.toFixed(2)}`
}

const VERDICT_STYLES: Record<string, string> = {
  buy: 'bg-accent/10 text-accent border-accent/20',
  hold: 'bg-warning/10 text-warning border-warning/20',
  avoid: 'bg-error/10 text-error border-error/20',
}

function VerdictBadge({ verdict }: { verdict: string | null }) {
  if (!verdict) return null
  return (
    <span className={`text-xs font-semibold px-2 py-0.5 rounded border uppercase ${VERDICT_STYLES[verdict] ?? ''}`}>
      {verdict}
    </span>
  )
}

function WeekSection({ week }: { week: TrackRecordWeek }) {
  const [open, setOpen] = useState(true)
  const { stats } = week

  return (
    <div className="border border-border rounded-lg overflow-hidden">
      <button
        onClick={() => setOpen(o => !o)}
        className="w-full flex items-center gap-3 px-4 py-3 bg-surface-1 hover:bg-surface-elevated
                   transition-colors duration-150 text-left"
      >
        <ChevronDown
          size={16}
          className={`text-text-secondary shrink-0 transition-transform duration-200 ${open ? '' : '-rotate-90'}`}
        />
        <span className="text-sm font-semibold text-text-primary">
          Week of {formatRunDate(week.run_date)}
        </span>
        <span className="text-xs text-text-secondary ml-2">
          {stats.analyzed} analyzed
        </span>
        <div className="flex gap-2 ml-auto text-xs">
          <span className="text-accent font-medium">{stats.buy} Buy</span>
          <span className="text-warning font-medium">{stats.hold} Hold</span>
          <span className="text-error font-medium">{stats.avoid} Avoid</span>
        </div>
      </button>

      {open && (
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-t border-border bg-surface-elevated/50">
                <th className="text-left px-4 py-2 text-xs text-text-secondary font-medium">Ticker</th>
                <th className="text-left px-4 py-2 text-xs text-text-secondary font-medium">Verdict</th>
                <th className="text-left px-4 py-2 text-xs text-text-secondary font-medium">Price at verdict</th>
                <th className="text-left px-4 py-2 text-xs text-text-secondary font-medium hidden md:table-cell">Thesis</th>
              </tr>
            </thead>
            <tbody>
              {week.rows.map(row => (
                <tr key={row.ticker} className="border-t border-border hover:bg-surface-elevated/30 transition-colors">
                  <td className="px-4 py-2.5">
                    <Link
                      href={`/preview/${row.ticker.toLowerCase()}`}
                      className="font-bold text-text-primary hover:text-accent transition-colors"
                    >
                      {row.ticker}
                    </Link>
                  </td>
                  <td className="px-4 py-2.5">
                    <VerdictBadge verdict={row.verdict} />
                  </td>
                  <td className="px-4 py-2.5 text-text-secondary font-mono text-xs">
                    {formatPrice(row.current_price)}
                  </td>
                  <td className="px-4 py-2.5 text-text-secondary text-xs hidden md:table-cell max-w-xs">
                    <span className="line-clamp-2">{row.synthesis_summary ?? '—'}</span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}

export default function TrackRecordPage() {
  const [data, setData] = useState<TrackRecordResponse | null>(null)
  const [error, setError] = useState(false)

  useEffect(() => {
    apiClient.getTrackRecord(100)
      .then(setData)
      .catch(() => setError(true))
  }, [])

  if (error) {
    return (
      <div className="container mx-auto px-4 py-16 text-center text-text-secondary">
        Unable to load track record. Try again later.
      </div>
    )
  }

  return (
    <div className="container mx-auto px-4 py-10 max-w-3xl">
      <div className="mb-8">
        <h1 className="text-3xl font-bold text-text-primary mb-2">Signal Track Record</h1>
        <p className="text-sm text-text-secondary">
          Every Buy / Hold / Avoid verdict the engine has made, timestamped at the price of verdict.{' '}
          <span className="text-text-subtle">Performance tracking coming soon.</span>
        </p>
      </div>

      {!data && (
        <div className="text-center py-20 text-text-secondary">Loading...</div>
      )}

      {data && data.weeks.length === 0 && (
        <div className="text-center py-20 text-text-secondary">
          <p className="text-lg font-medium mb-2">Track record is building</p>
          <p className="text-sm">Check back after the first weekly batch runs on Monday.</p>
        </div>
      )}

      {data && data.weeks.length > 0 && (
        <>
          <p className="text-xs text-text-subtle mb-6">
            {data.total_weeks} week{data.total_weeks !== 1 ? 's' : ''} tracked
          </p>
          <div className="flex flex-col gap-4">
            {data.weeks.map(week => (
              <WeekSection key={week.run_date} week={week} />
            ))}
          </div>
        </>
      )}

      <div className="mt-10">
        <InlineDisclaimer />
      </div>
    </div>
  )
}
