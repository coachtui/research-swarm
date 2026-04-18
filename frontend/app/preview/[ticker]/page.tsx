'use client'

import { useEffect, useState } from 'react'
import { useParams } from 'next/navigation'
import Link from 'next/link'
import { Lock, ArrowLeft } from 'lucide-react'
import { useUser } from '@clerk/nextjs'
import { useEntitlements } from '@/lib/hooks/useEntitlements'
import { apiClient } from '@/lib/api/client'
import { InlineDisclaimer } from '@/components/ui/InlineDisclaimer'
import { Button } from '@/components/ui/button'
import type { WeeklySignalPublic, WeeklySignalFull } from '@/types/weekly-signals'

function formatDate(dateStr: string): string {
  return new Date(dateStr).toLocaleDateString('en-US', {
    month: 'short', day: 'numeric', year: 'numeric'
  })
}

function formatPct(val: number | null, decimals = 1): string {
  if (val == null) return '—'
  const sign = val >= 0 ? '+' : ''
  return `${sign}${val.toFixed(decimals)}%`
}

function formatMarketCtx(label: string, val: number | null): string {
  if (val == null) return `${label} n/a`
  const sign = val >= 0 ? '+' : ''
  return `${label} ${sign}${val.toFixed(1)}%`
}

const VERDICT_STYLES: Record<string, { bg: string; text: string; border: string }> = {
  buy:   { bg: 'bg-accent/10',   text: 'text-accent',   border: 'border-accent/20' },
  hold:  { bg: 'bg-warning/10',  text: 'text-warning',  border: 'border-warning/20' },
  avoid: { bg: 'bg-error/10',    text: 'text-error',    border: 'border-error/20' },
}

function SignalCard({
  label,
  value,
  locked,
}: {
  label: string
  value: string
  locked: boolean
}) {
  return (
    <div className="bg-surface-1 border border-border rounded-lg p-4 text-center relative overflow-hidden">
      <div className="text-xs text-text-secondary mb-1">{label}</div>
      {locked ? (
        <>
          <div className="text-lg font-bold text-text-primary blur-sm select-none">{value}</div>
          <div className="absolute inset-0 flex items-center justify-center bg-surface-1/60">
            <span className="flex items-center gap-1 text-xs text-accent font-semibold">
              <Lock size={11} /> Starter+
            </span>
          </div>
        </>
      ) : (
        <div className="text-lg font-bold text-accent">{value}</div>
      )}
    </div>
  )
}

export default function WeeklyPreviewPage() {
  const params = useParams()
  const ticker = (params?.ticker as string ?? '').toUpperCase()
  const { isSignedIn } = useUser()
  const { data: ents } = useEntitlements()

  const [signal, setSignal] = useState<WeeklySignalPublic | null>(null)
  const [notFound, setNotFound] = useState(false)
  const [error, setError] = useState(false)

  const isStarterPlus = isSignedIn && ents && !ents.usage.is_free_tier
  const full = signal as WeeklySignalFull | null

  useEffect(() => {
    if (!ticker) return
    apiClient.getWeeklyPreview(ticker)
      .then(setSignal)
      .catch((e: any) => {
        if (e?.status === 404) setNotFound(true)
        else setError(true)
      })
  }, [ticker])

  if (notFound) {
    return (
      <div className="container mx-auto px-4 py-16 max-w-2xl text-center">
        <p className="text-xl font-semibold text-text-primary mb-2">No recent signal for {ticker}</p>
        <p className="text-text-secondary mb-6 text-sm">
          {ticker} wasn&apos;t in this week&apos;s batch. Run an on-demand analysis instead.
        </p>
        <Link href="/analyze">
          <Button>Analyze {ticker}</Button>
        </Link>
      </div>
    )
  }

  if (error) {
    return (
      <div className="container mx-auto px-4 py-16 text-center text-text-secondary">
        Unable to load signal. Try again later.
      </div>
    )
  }

  if (!signal) {
    return (
      <div className="container mx-auto px-4 py-16 text-center text-text-secondary">
        Loading...
      </div>
    )
  }

  const verdictStyle = VERDICT_STYLES[signal.verdict ?? ''] ?? VERDICT_STYLES.hold

  return (
    <div className="container mx-auto px-4 py-10 max-w-2xl">

      {/* Breadcrumb */}
      <Link
        href="/leaderboard"
        className="inline-flex items-center gap-1.5 text-sm text-text-secondary hover:text-text-primary
                   transition-colors mb-6"
      >
        <ArrowLeft size={14} />
        Back to Leaderboard
      </Link>

      {/* Header */}
      <div className="flex items-center gap-3 mb-2">
        <h1 className="text-4xl font-bold text-text-primary">{signal.ticker}</h1>
        {signal.verdict && (
          <span className={`text-sm font-bold px-3 py-1 rounded border uppercase
                           ${verdictStyle.bg} ${verdictStyle.text} ${verdictStyle.border}`}>
            {signal.verdict}
          </span>
        )}
      </div>
      <div className="text-xs text-text-subtle mb-6 flex gap-2 flex-wrap">
        <span>{formatDate(signal.run_date)}</span>
        {(signal.es_change_pct != null || signal.nq_change_pct != null) && (
          <>
            <span>·</span>
            <span>{formatMarketCtx('ES', signal.es_change_pct)}</span>
            <span>·</span>
            <span>{formatMarketCtx('NQ', signal.nq_change_pct)}</span>
          </>
        )}
      </div>

      {/* Synthesis quote */}
      {signal.synthesis_summary && (
        <blockquote
          className="text-text-primary text-base leading-relaxed mb-6 pl-4"
          style={{ borderLeft: '3px solid var(--accent)' }}
        >
          {signal.synthesis_summary}
        </blockquote>
      )}

      {/* Signal cards */}
      <div className="grid grid-cols-3 gap-3 mb-6">
        <SignalCard
          label="Fair value gap"
          value={formatPct(signal.fair_value_gap_pct)}
          locked={false}
        />
        <SignalCard
          label="EV probability"
          value={full?.ev_probability != null ? `${Math.round(full.ev_probability * 100)}%` : '—'}
          locked={!isStarterPlus}
        />
        <SignalCard
          label="Stop-loss risk"
          value={full?.stop_loss_probability != null ? `${Math.round(full.stop_loss_probability * 100)}%` : '—'}
          locked={!isStarterPlus}
        />
      </div>

      {/* Catalyst summary (locked) */}
      {!isStarterPlus && (
        <div className="relative mb-6 bg-surface-1 border border-border rounded-lg p-4 overflow-hidden">
          <div className="text-xs text-text-secondary mb-1 font-medium uppercase tracking-wider">
            Catalyst Summary
          </div>
          <p className="text-sm text-text-secondary blur-sm select-none line-clamp-2">
            {signal.synthesis_summary ?? 'Key catalysts and risk factors...'}
          </p>
          <div className="absolute inset-0 flex items-center justify-center bg-surface-1/60">
            <span className="flex items-center gap-1.5 text-sm text-accent font-semibold">
              <Lock size={13} /> Unlock full catalyst breakdown
            </span>
          </div>
        </div>
      )}

      {isStarterPlus && full?.catalyst_summary && (
        <div className="mb-6 bg-surface-1 border border-border rounded-lg p-4">
          <div className="text-xs text-text-secondary mb-1 font-medium uppercase tracking-wider">
            Catalyst Summary
          </div>
          <p className="text-sm text-text-primary">{full.catalyst_summary}</p>
        </div>
      )}

      {/* Upgrade CTA */}
      {!isStarterPlus && (
        <div className="bg-accent/5 border border-accent/20 rounded-lg p-5 text-center mb-6">
          <p className="text-text-primary font-semibold mb-1">
            Get the full thesis, position sizing, and 20+ signal breakdown
          </p>
          <p className="text-text-secondary text-sm mb-4">From $19.99/mo</p>
          <Link href={isSignedIn ? '/#pricing' : '/sign-up'}>
            <Button>
              {isSignedIn ? 'Upgrade to Starter \u2192' : 'Get started free \u2192'}
            </Button>
          </Link>
        </div>
      )}

      <InlineDisclaimer />
    </div>
  )
}
