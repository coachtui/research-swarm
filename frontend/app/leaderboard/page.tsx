'use client'

import { useEffect, useState } from 'react'
import { useUser } from '@clerk/nextjs'
import Link from 'next/link'
import { ChevronDown } from 'lucide-react'
import { apiClient } from '@/lib/api/client'
import { InlineDisclaimer } from '@/components/ui/InlineDisclaimer'
import type { LeaderboardResponse, WeeklySignalPublic, WeeklySignalFull } from '@/types/weekly-signals'

type Lens = 'fair_value_gap' | 'ev_probability' | 'stop_loss' | 'insider' | 'verdict_upgrade'

const LENSES: { value: Lens; label: string }[] = [
  { value: 'fair_value_gap', label: 'Largest Fair Value Gap' },
  { value: 'ev_probability', label: 'Highest EV Probability' },
  { value: 'stop_loss', label: 'Lowest Stop-Loss Risk' },
  { value: 'insider', label: 'Strongest Insider Activity' },
  { value: 'verdict_upgrade', label: 'Biggest Verdict Upgrade' },
]

const VERDICT_UPGRADE_SCORE: Record<string, Record<string, number>> = {
  avoid: { buy: 3, hold: 1 },
  hold: { buy: 2 },
}

function verdictUpgradeScore(current: string | null, prior: string | null): number {
  if (!current || !prior) return 0
  return VERDICT_UPGRADE_SCORE[prior]?.[current] ?? 0
}

function getLensValue(row: WeeklySignalPublic, lens: Lens): number {
  const full = row as WeeklySignalFull
  switch (lens) {
    case 'fair_value_gap': return row.fair_value_gap_pct ?? -Infinity
    case 'ev_probability': return full.ev_probability ?? -Infinity
    case 'stop_loss': return -(full.stop_loss_probability ?? Infinity)
    case 'insider': return full.insider_score ?? -Infinity
    case 'verdict_upgrade': return verdictUpgradeScore(row.verdict, row.prior_verdict)
  }
}

function formatLensValue(row: WeeklySignalPublic, lens: Lens): string {
  const full = row as WeeklySignalFull
  switch (lens) {
    case 'fair_value_gap':
      return row.fair_value_gap_pct != null ? `+${row.fair_value_gap_pct.toFixed(1)}%` : '—'
    case 'ev_probability':
      return full.ev_probability != null ? `${Math.round(full.ev_probability * 100)}%` : '—'
    case 'stop_loss':
      return full.stop_loss_probability != null ? `${Math.round(full.stop_loss_probability * 100)}%` : '—'
    case 'insider':
      return full.insider_score != null ? full.insider_score.toFixed(1) : '—'
    case 'verdict_upgrade': {
      const score = verdictUpgradeScore(row.verdict, row.prior_verdict)
      if (score === 3) return 'Avoid → Buy'
      if (score === 2) return 'Hold → Buy'
      if (score === 1) return 'Avoid → Hold'
      return '—'
    }
  }
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

function formatMarketCtx(label: string, val: number | null): string {
  if (val == null) return `${label} n/a`
  const sign = val >= 0 ? '+' : ''
  return `${label} ${sign}${val.toFixed(1)}%`
}

function formatRunDate(dateStr: string | null): string {
  if (!dateStr) return ''
  const d = new Date(dateStr)
  return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })
}

export default function LeaderboardPage() {
  const { isSignedIn } = useUser()
  const [data, setData] = useState<LeaderboardResponse | null>(null)
  const [lens, setLens] = useState<Lens>('fair_value_gap')
  const [error, setError] = useState(false)

  useEffect(() => {
    apiClient.getLeaderboard(25)
      .then(setData)
      .catch(() => setError(true))
  }, [])

  if (error) {
    return (
      <div className="container mx-auto px-4 py-16 text-center text-text-secondary">
        Unable to load leaderboard. Try again later.
      </div>
    )
  }

  if (!data) {
    return (
      <div className="container mx-auto px-4 py-16 text-center text-text-secondary">
        Loading...
      </div>
    )
  }

  const { rows, run_date, market_context, total } = data
  const mc = market_context

  const sorted = [...rows].sort((a, b) => getLensValue(b, lens) - getLensValue(a, lens))
  const isFullData = total > 3

  return (
    <div className="container mx-auto px-4 py-10 max-w-3xl">

      {/* Header */}
      <div className="mb-6">
        <h1 className="text-3xl font-bold text-text-primary mb-1">This Week's Top Picks</h1>
        <div className="flex flex-wrap gap-3 items-center text-sm text-text-secondary">
          {run_date && (
            <span className="bg-surface-elevated px-2.5 py-1 rounded text-xs font-medium">
              Week of {formatRunDate(run_date)}
            </span>
          )}
          <span>{formatMarketCtx('ES', mc.es_change_pct)}</span>
          <span>·</span>
          <span>{formatMarketCtx('NQ', mc.nq_change_pct)}</span>
          <span>·</span>
          <span>{formatMarketCtx('DOW', mc.dow_change_pct)}</span>
        </div>
      </div>

      {/* Empty state */}
      {rows.length === 0 && (
        <div className="text-center py-20 text-text-secondary">
          <p className="text-lg font-medium mb-2">No signals yet</p>
          <p className="text-sm">The first weekly batch hasn't run. Check back Monday.</p>
        </div>
      )}

      {rows.length > 0 && (
        <>
          {/* Lens selector — only for full-data users */}
          {isFullData && (
            <div className="mb-4 flex items-center gap-2">
              <span className="text-xs text-text-secondary uppercase tracking-wider">Ranked by</span>
              <div className="relative">
                <select
                  value={lens}
                  onChange={e => setLens(e.target.value as Lens)}
                  className="appearance-none bg-surface-elevated border border-border rounded px-3 py-1.5 pr-7
                             text-sm text-text-primary focus:outline-none focus:ring-1 focus:ring-accent"
                >
                  {LENSES.map(l => (
                    <option key={l.value} value={l.value}>{l.label}</option>
                  ))}
                </select>
                <ChevronDown size={14} className="absolute right-2 top-1/2 -translate-y-1/2 text-text-secondary pointer-events-none" />
              </div>
            </div>
          )}

          {/* Ranked rows */}
          <div className="flex flex-col gap-2">
            {sorted.map((row, idx) => (
              <Link
                key={row.ticker}
                href={`/preview/${row.ticker.toLowerCase()}`}
                className="flex items-center gap-3 bg-surface-1 hover:bg-surface-elevated border border-border
                           rounded-lg px-4 py-3 transition-colors duration-150 group"
              >
                <span className="text-xs text-text-subtle w-5 shrink-0">{idx + 1}</span>
                <span className="text-sm font-bold text-text-primary w-12 shrink-0">{row.ticker}</span>
                <VerdictBadge verdict={row.verdict} />
                <span className="flex-1 text-xs text-text-secondary line-clamp-1 hidden sm:block">
                  {row.synthesis_summary ?? ''}
                </span>
                <span className="text-sm font-semibold text-accent shrink-0 ml-auto">
                  {formatLensValue(row, lens)}
                </span>
              </Link>
            ))}

            {/* Upgrade nudge between row 3 and 4 for unauthenticated/free */}
            {!isFullData && (
              <div className="flex items-center justify-center gap-2 bg-accent/5 border border-accent/20
                              rounded-lg px-4 py-3 text-sm">
                <span className="text-text-secondary">
                  {isSignedIn ? 'Upgrade to Starter to see all 25 picks' : 'Sign in to see all 25 picks'}
                </span>
                <Link
                  href={isSignedIn ? '/#pricing' : '/sign-in'}
                  className="text-accent font-semibold hover:underline"
                >
                  {isSignedIn ? 'Upgrade →' : 'Sign in →'}
                </Link>
              </div>
            )}
          </div>
        </>
      )}

      <div className="mt-10">
        <InlineDisclaimer />
      </div>
    </div>
  )
}
