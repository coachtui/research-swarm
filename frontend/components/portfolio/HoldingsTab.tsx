'use client'

import Link from 'next/link'
import { usePortfolioDetail } from '@/lib/hooks/usePortfolio'
import { formatWeight } from '@/lib/ownership-mapping'
import type { PortfolioPosition } from '@/types/api'

/**
 * HoldingsTab — grid of current positions with state machine visualization.
 */
export function HoldingsTab({ portfolioId }: { portfolioId: string }) {
  const { data: portfolio, isLoading } = usePortfolioDetail(portfolioId)

  if (isLoading) {
    return <div className="text-sm text-text-tertiary text-center py-8">Loading holdings...</div>
  }

  if (!portfolio || portfolio.positions.length === 0) {
    return (
      <div className="text-center py-12 space-y-3">
        <div className="text-3xl">📊</div>
        <p className="text-sm text-text-secondary">No positions yet.</p>
        <p className="text-xs text-text-tertiary">
          Add positions from the Portfolio tab to start tracking your holdings.
        </p>
      </div>
    )
  }

  const sorted = [...portfolio.positions].sort((a, b) => b.current_weight - a.current_weight)

  return (
    <div className="space-y-3">
      {/* Summary row */}
      <div className="flex items-center justify-between text-xs text-text-tertiary">
        <span>{portfolio.positions.length} position{portfolio.positions.length > 1 ? 's' : ''}</span>
        <span>Total weight: <span className="font-mono font-semibold text-text-primary">{formatWeight(portfolio.total_weight)}</span></span>
      </div>

      {/* Position grid */}
      <div className="grid gap-2">
        {sorted.map((pos) => (
          <PositionRow key={pos.ticker} position={pos} />
        ))}
      </div>
    </div>
  )
}

function PositionRow({ position }: { position: PortfolioPosition }) {
  const ownershipColor = {
    core_compounder: 'text-success',
    watch: 'text-warning',
    disqualified: 'text-error',
  }[position.ownership_status] || 'text-text-tertiary'

  const ownershipLabel = {
    core_compounder: 'Core',
    watch: 'Watch',
    disqualified: 'DQ',
  }[position.ownership_status] || position.ownership_status

  const thesisColor = {
    intact: 'text-success',
    monitoring: 'text-warning',
    broken: 'text-error',
  }[position.thesis_state] || 'text-text-tertiary'

  return (
    <div className="flex items-center justify-between rounded-lg border border-border/60 bg-surface/30 px-4 py-3">
      <div className="flex items-center gap-3 min-w-0">
        {/* Ticker + status badge */}
        <div className="flex items-center gap-2">
          <span className="text-sm font-bold font-mono text-text-primary">{position.ticker}</span>
          <span className={`text-[9px] font-semibold uppercase tracking-wide ${ownershipColor}`}>
            {ownershipLabel}
          </span>
        </div>

        {/* Weight */}
        <span className="text-xs font-mono font-semibold text-text-secondary">
          {formatWeight(position.current_weight)}
        </span>
      </div>

      <div className="flex items-center gap-3">
        {/* Tier state */}
        {position.tier_state !== 'none' && (
          <span className="text-[9px] font-mono bg-warning/10 text-warning px-1.5 py-0.5 rounded">
            {position.tier_state.toUpperCase()}
          </span>
        )}

        {/* Thesis state */}
        <span className={`text-[9px] font-semibold uppercase ${thesisColor}`}>
          {position.thesis_state}
        </span>

        {/* Compounder score */}
        {position.compounder_score !== null && (
          <span className="text-[10px] font-mono text-text-tertiary">
            CS: {(position.compounder_score * 100).toFixed(0)}
          </span>
        )}

        {/* Link to research */}
        {position.latest_run_id && (
          <Link
            href={`/results/${position.latest_run_id}`}
            className="text-[10px] text-primary hover:underline"
          >
            Research
          </Link>
        )}
      </div>
    </div>
  )
}
