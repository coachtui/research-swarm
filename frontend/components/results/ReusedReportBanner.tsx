'use client'

import { useState } from 'react'
import { useRouter } from 'next/navigation'
import { RefreshCw, Clock } from 'lucide-react'
import { apiClient } from '@/lib/api/client'

interface ReusedReportBannerProps {
  ticker: string
  asOf: string
}

/**
 * Shown when the analyze endpoint served a prior still-relevant report
 * instead of running a fresh analysis. Explains why, and offers a
 * force-fresh re-run (which does consume a credit).
 */
export function ReusedReportBanner({ ticker, asOf }: ReusedReportBannerProps) {
  const router = useRouter()
  const [rerunning, setRerunning] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const runFresh = async () => {
    setRerunning(true)
    setError(null)
    try {
      const response = await apiClient.analyzeStock({ ticker, force_fresh: true })
      router.push(`/results/${response.run_id}`)
    } catch (e: any) {
      setError(e?.message || 'Could not start a fresh analysis.')
      setRerunning(false)
    }
  }

  return (
    <div className="rounded-xl border border-border/60 bg-surface/30 px-5 py-3.5 mb-4 flex flex-wrap items-center justify-between gap-3">
      <div className="flex items-start gap-2.5">
        <Clock className="h-4 w-4 text-text-tertiary flex-shrink-0 mt-0.5" />
        <div>
          <p className="text-sm font-semibold text-text-primary">
            Showing your {asOf} report — still current
          </p>
          <p className="text-[11px] text-text-tertiary mt-0.5">
            No earnings, no material SEC filings, and price within ±10% since this
            analysis, so no credit was used. Market data may have moved since.
          </p>
          {error && <p className="text-[11px] text-red-400 mt-1">{error}</p>}
        </div>
      </div>
      <button
        onClick={runFresh}
        disabled={rerunning}
        className="flex items-center gap-1.5 text-xs font-semibold border border-border rounded-lg px-3 py-1.5 hover:bg-surface-elevated/30 transition-colors disabled:opacity-50"
      >
        <RefreshCw className={`h-3.5 w-3.5 ${rerunning ? 'animate-spin' : ''}`} />
        {rerunning ? 'Starting fresh run…' : 'Run fresh analysis'}
      </button>
    </div>
  )
}
