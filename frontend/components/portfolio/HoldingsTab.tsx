'use client'

import { useState } from 'react'
import Link from 'next/link'
import { Pencil, Trash2, Check, X, Plus, ChevronDown, RefreshCw } from 'lucide-react'
import {
  usePortfolioDetail,
  useAddPosition,
  useUpdatePosition,
  useRemovePosition,
  usePortfolioActions,
  useRefreshPrices,
} from '@/lib/hooks/usePortfolio'
import { CashCard } from '@/components/portfolio/CashCard'
import { ActionPlanCard } from '@/components/portfolio/ActionPlanCard'
import type { PortfolioPosition, EngineAction } from '@/types/api'

/**
 * isPriceStale — returns true if lastPriceAt is more than 7 days old.
 */
function isPriceStale(lastPriceAt: string | null): boolean {
  if (!lastPriceAt) return false
  return Date.now() - new Date(lastPriceAt).getTime() > 7 * 24 * 60 * 60 * 1000
}

/**
 * HoldingsTab — grid of current positions with inline add, edit, and delete.
 */
export function HoldingsTab({ portfolioId }: { portfolioId: string }) {
  const { data: portfolio, isLoading } = usePortfolioDetail(portfolioId)
  const { data: feed } = usePortfolioActions(portfolioId)
  const refreshPrices = useRefreshPrices()
  const [addingPosition, setAddingPosition] = useState(false)

  if (isLoading) {
    return <div className="text-sm text-text-tertiary text-center py-8">Loading holdings...</div>
  }

  const hasPositions = portfolio && portfolio.positions.length > 0
  const sorted = hasPositions
    ? [...portfolio.positions].sort((a, b) => (b.allocation_pct ?? -1) - (a.allocation_pct ?? -1))
    : []

  const activePositions = sorted.filter(p => p.ownership_status !== 'watch')
  const watchPositions = sorted.filter(p => p.ownership_status === 'watch')

  return (
    <div className="space-y-3">
      {/* Summary row */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-1.5 text-xs text-text-tertiary">
        <span>
          {portfolio ? `${portfolio.positions.length} position${portfolio.positions.length !== 1 ? 's' : ''}` : 'No portfolio'}
          {portfolio && portfolio.total_value !== undefined && portfolio.total_value !== null && (
            <span className="ml-2">
              · <span className="font-mono font-semibold text-text-primary">
                ${portfolio.total_value.toLocaleString()}
              </span>
            </span>
          )}
        </span>
        <div className="flex items-center gap-2 self-start sm:self-auto">
          <button
            onClick={() => refreshPrices.mutate(portfolioId)}
            disabled={refreshPrices.isPending}
            className="flex items-center gap-1 text-text-tertiary hover:text-text-primary transition-colors disabled:opacity-50"
            title="Refresh prices"
          >
            <RefreshCw className={`h-3 w-3 ${refreshPrices.isPending ? 'animate-spin' : ''}`} />
            {refreshPrices.isPending ? 'Refreshing...' : 'Refresh Prices'}
          </button>
          <button
            onClick={() => setAddingPosition(v => !v)}
            className="flex items-center gap-1 text-primary hover:text-primary/80 transition-colors font-semibold"
          >
            <Plus className="h-3 w-3" />
            Add Position
            <ChevronDown className={`h-3 w-3 transition-transform ${addingPosition ? 'rotate-180' : ''}`} />
          </button>
        </div>
      </div>

      {/* Add Position form */}
      {addingPosition && (
        <AddPositionForm
          portfolioId={portfolioId}
          existingTickers={sorted.map(p => p.ticker)}
          onDone={() => setAddingPosition(false)}
        />
      )}

      {/* Cash card */}
      {portfolio && (
        <CashCard
          portfolioId={portfolioId}
          cashBalance={portfolio.cash_balance}
          cashPct={portfolio.cash_pct}
        />
      )}

      {/* Active holdings */}
      {activePositions.length > 0 && (
        <div className="grid gap-2">
          {activePositions.map((pos) => {
            const posActions = (feed?.actions ?? []).filter(a => a.ticker === pos.ticker)
            return <PositionRow key={pos.ticker} portfolioId={portfolioId} position={pos} actions={posActions} />
          })}
        </div>
      )}

      {/* Watchlist section */}
      {watchPositions.length > 0 && (
        <div className="space-y-2">
          <div className="text-xs font-semibold uppercase tracking-wider text-text-tertiary pt-2">Watchlist</div>
          <div className="grid gap-2">
            {watchPositions.map((pos) => {
              const posActions = (feed?.actions ?? []).filter(a => a.ticker === pos.ticker)
              return <PositionRow key={pos.ticker} portfolioId={portfolioId} position={pos} actions={posActions} />
            })}
          </div>
        </div>
      )}

      {/* Empty state */}
      {!hasPositions && !addingPosition && (
        <div className="text-center py-8 text-sm text-text-tertiary">
          No positions yet — click Add Position above to get started.
        </div>
      )}
    </div>
  )
}

// ── Add Position Form ─────────────────────────────────────────────────────────

function AddPositionForm({
  portfolioId,
  existingTickers,
  onDone,
}: {
  portfolioId: string
  existingTickers: string[]
  onDone: () => void
}) {
  const [ticker, setTicker] = useState('')
  const [costBasis, setCostBasis] = useState('')
  const [shares, setShares] = useState('')
  const [error, setError] = useState<string | null>(null)

  const addPosition = useAddPosition()

  const handleAdd = async () => {
    const t = ticker.trim().toUpperCase()
    if (!t) {
      setError('Ticker is required')
      return
    }
    if (existingTickers.includes(t)) {
      setError(`${t} is already in your portfolio`)
      return
    }
    const sh = parseFloat(shares)
    if (!shares || isNaN(sh) || sh < 0) {
      setError('Shares is required and must be a valid non-negative number')
      return
    }
    const cb = costBasis ? parseFloat(costBasis) : undefined
    if (costBasis && isNaN(cb!)) {
      setError('Cost basis must be a valid number')
      return
    }
    try {
      await addPosition.mutateAsync({ portfolioId, ticker: t, shares: sh, costBasis: cb })
      setTicker('')
      setCostBasis('')
      setShares('')
      setError(null)
      onDone()
    } catch (err: unknown) {
      setError((err as { message?: string }).message ?? 'Failed to add position')
    }
  }

  return (
    <div className="rounded-lg border border-primary/30 bg-surface/60 px-4 py-3 space-y-3">
      <div className="flex flex-wrap items-end gap-3">
        <div className="flex-1 min-w-[100px]">
          <label className="text-[10px] font-semibold uppercase tracking-wider text-text-tertiary">Ticker</label>
          <input
            type="text"
            value={ticker}
            onChange={e => setTicker(e.target.value.toUpperCase())}
            onKeyDown={e => e.key === 'Enter' && handleAdd()}
            placeholder="AAPL"
            autoFocus
            className="w-full mt-1 px-3 py-1.5 text-sm bg-surface border border-border rounded-lg text-text-primary placeholder:text-text-tertiary font-mono focus:outline-none focus:ring-1 focus:ring-primary"
          />
        </div>
        <div className="w-24">
          <label className="text-[10px] font-semibold uppercase tracking-wider text-text-tertiary">Shares</label>
          <input
            type="text"
            value={shares}
            onChange={e => setShares(e.target.value)}
            placeholder="Required"
            className="w-full mt-1 px-3 py-1.5 text-sm bg-surface border border-border rounded-lg text-text-primary placeholder:text-text-tertiary font-mono focus:outline-none focus:ring-1 focus:ring-primary"
          />
        </div>
        <div className="w-28">
          <label className="text-[10px] font-semibold uppercase tracking-wider text-text-tertiary">Cost / Share</label>
          <input
            type="text"
            value={costBasis}
            onChange={e => setCostBasis(e.target.value)}
            placeholder="Optional"
            className="w-full mt-1 px-3 py-1.5 text-sm bg-surface border border-border rounded-lg text-text-primary placeholder:text-text-tertiary font-mono focus:outline-none focus:ring-1 focus:ring-primary"
          />
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={handleAdd}
            disabled={addPosition.isPending}
            className="flex items-center gap-1 h-[34px] px-3 text-xs font-semibold rounded-lg bg-primary text-white hover:bg-primary/90 disabled:opacity-50 transition-colors"
          >
            <Check className="h-3.5 w-3.5" />
            {addPosition.isPending ? 'Adding...' : 'Add'}
          </button>
          <button
            onClick={onDone}
            className="h-[34px] px-2 text-text-tertiary hover:text-text-primary transition-colors"
          >
            <X className="h-3.5 w-3.5" />
          </button>
        </div>
      </div>
      {error && <p className="text-xs text-error">{error}</p>}
    </div>
  )
}

// ── Position Row ──────────────────────────────────────────────────────────────

function PositionRow({
  portfolioId,
  position,
  actions,
}: {
  portfolioId: string
  position: PortfolioPosition
  actions: EngineAction[]
}) {
  const [editing, setEditing] = useState(false)
  const [confirmingDelete, setConfirmingDelete] = useState(false)
  const [targetWeight, setTargetWeight] = useState('')
  const [costBasis, setCostBasis] = useState('')
  const [shares, setShares] = useState('')
  const [error, setError] = useState<string | null>(null)

  const updatePosition = useUpdatePosition()
  const removePosition = useRemovePosition()

  const handleEditOpen = () => {
    setTargetWeight((position.target_weight * 100).toFixed(1))
    setCostBasis(position.cost_basis?.toString() ?? '')
    setShares(position.shares?.toString() ?? '')
    setError(null)
    setConfirmingDelete(false)
    setEditing(true)
  }

  const handleEditCancel = () => {
    setEditing(false)
    setError(null)
  }

  const handleSave = async () => {
    const data: { target_weight?: number; cost_basis?: number; shares?: number } = {}
    if (targetWeight !== '') {
      const tw = parseFloat(targetWeight)
      if (!isNaN(tw)) data.target_weight = tw / 100
    }
    if (costBasis !== '') {
      const parsed = parseFloat(costBasis)
      if (!isNaN(parsed)) data.cost_basis = parsed
    }
    if (shares !== '') {
      const parsed = parseFloat(shares)
      if (!isNaN(parsed)) data.shares = parsed
    }

    try {
      await updatePosition.mutateAsync({ portfolioId, ticker: position.ticker, data })
      setEditing(false)
      setError(null)
    } catch (err: unknown) {
      setError((err as { message?: string }).message ?? 'Failed to save')
    }
  }

  const handleRemove = async () => {
    try {
      await removePosition.mutateAsync({ portfolioId, ticker: position.ticker })
    } catch (err: unknown) {
      setConfirmingDelete(false)
      setError((err as { message?: string }).message ?? 'Failed to remove')
    }
  }

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

  // Allocation vs target delta
  const allocationPct = position.allocation_pct !== null ? position.allocation_pct * 100 : null
  const targetPct = position.target_weight * 100
  const deltaPct = allocationPct !== null ? allocationPct - targetPct : null
  const deltaColor = deltaPct === null ? '' : deltaPct > 0 ? 'text-error' : 'text-success'
  const deltaText = deltaPct !== null
    ? `${deltaPct >= 0 ? '+' : ''}${deltaPct.toFixed(1)}%`
    : null

  const stale = isPriceStale(position.last_price_at)

  return (
    <div className="rounded-lg border border-border/60 bg-surface/30 overflow-hidden">
      {/* Main row */}
      <div className="flex items-center justify-between px-4 py-3">
        <div className="flex items-center gap-3 min-w-0">
          <div className="flex items-center gap-2">
            <span className="text-sm font-bold font-mono text-text-primary">{position.ticker}</span>
            <span className={`text-[9px] font-semibold uppercase tracking-wide ${ownershipColor}`}>
              {ownershipLabel}
            </span>
          </div>

          {/* Allocation % */}
          <span className="text-xs font-mono font-semibold text-text-secondary">
            {position.allocation_pct !== null ? `${(position.allocation_pct * 100).toFixed(1)}%` : '—'}
          </span>

          {/* Market value */}
          <span className="hidden sm:inline text-xs font-mono text-text-tertiary">
            {position.market_value !== null
              ? position.market_value.toLocaleString('en-US', { style: 'currency', currency: 'USD', maximumFractionDigits: 0 })
              : '—'}
          </span>

          {/* Stale price badge */}
          {stale && (
            <span className="text-[9px] font-semibold px-1 py-0.5 rounded bg-warning/10 text-warning">Stale</span>
          )}
        </div>

        <div className="flex items-center gap-2 sm:gap-3">
          {/* Target % and delta */}
          <span className="hidden sm:inline text-[10px] font-mono text-text-tertiary">
            tgt {targetPct.toFixed(1)}%
          </span>
          {deltaText && (
            <span className={`text-[10px] font-mono font-semibold ${deltaColor}`}>{deltaText}</span>
          )}

          {position.tier_state !== 'none' && (
            <span className="hidden sm:inline-flex text-[9px] font-mono bg-warning/10 text-warning px-1.5 py-0.5 rounded">
              {position.tier_state.toUpperCase()}
            </span>
          )}

          <span className={`text-[9px] font-semibold uppercase ${thesisColor}`}>
            {position.thesis_state}
          </span>

          {position.compounder_score !== null && (
            <span className="hidden sm:inline text-[10px] font-mono text-text-tertiary">
              CS: {(position.compounder_score * 100).toFixed(0)}
            </span>
          )}

          {position.latest_run_id && !editing && !confirmingDelete && (
            <Link
              href={`/results/${position.latest_run_id}`}
              className="text-[10px] text-primary hover:underline"
            >
              Research
            </Link>
          )}

          {/* Delete confirmation prompt */}
          {confirmingDelete && !editing && (
            <div className="flex items-center gap-2">
              <span className="text-[10px] text-error font-semibold">Remove?</span>
              <button
                onClick={handleRemove}
                disabled={removePosition.isPending}
                className="text-[10px] font-semibold text-error hover:text-error/80 disabled:opacity-50"
              >
                {removePosition.isPending ? '...' : 'Yes'}
              </button>
              <button
                onClick={() => setConfirmingDelete(false)}
                className="text-[10px] font-semibold text-text-tertiary hover:text-text-secondary"
              >
                No
              </button>
            </div>
          )}

          {/* Edit toggle */}
          <button
            onClick={editing ? handleEditCancel : handleEditOpen}
            className="text-text-tertiary hover:text-text-primary transition-colors"
            title={editing ? 'Cancel edit' : 'Edit position'}
          >
            {editing ? <X className="h-3.5 w-3.5" /> : <Pencil className="h-3.5 w-3.5" />}
          </button>

          {/* Delete toggle */}
          {!editing && (
            <button
              onClick={() => setConfirmingDelete(v => !v)}
              className={`transition-colors ${confirmingDelete ? 'text-error' : 'text-text-tertiary hover:text-error'}`}
              title="Remove position"
            >
              <Trash2 className="h-3.5 w-3.5" />
            </button>
          )}
        </div>
      </div>

      {/* Inline edit form */}
      {editing && (
        <div className="border-t border-border/40 px-4 py-3 bg-surface/60 space-y-3">
          <div className="flex flex-wrap items-end gap-3">
            <div className="w-24">
              <label className="text-[10px] font-semibold uppercase tracking-wider text-text-tertiary">Target %</label>
              <input
                type="number"
                value={targetWeight}
                onChange={e => setTargetWeight(e.target.value)}
                min={0}
                max={100}
                step={0.5}
                autoFocus
                className="w-full mt-1 px-3 py-1.5 text-sm bg-surface border border-border rounded-lg text-text-primary font-mono focus:outline-none focus:ring-1 focus:ring-primary"
              />
            </div>
            <div className="w-28">
              <label className="text-[10px] font-semibold uppercase tracking-wider text-text-tertiary">Cost Basis</label>
              <input
                type="text"
                value={costBasis}
                onChange={e => setCostBasis(e.target.value)}
                placeholder="Optional"
                className="w-full mt-1 px-3 py-1.5 text-sm bg-surface border border-border rounded-lg text-text-primary placeholder:text-text-tertiary font-mono focus:outline-none focus:ring-1 focus:ring-primary"
              />
            </div>
            <div className="w-24">
              <label className="text-[10px] font-semibold uppercase tracking-wider text-text-tertiary">Shares</label>
              <input
                type="text"
                value={shares}
                onChange={e => setShares(e.target.value)}
                placeholder="Optional"
                className="w-full mt-1 px-3 py-1.5 text-sm bg-surface border border-border rounded-lg text-text-primary placeholder:text-text-tertiary font-mono focus:outline-none focus:ring-1 focus:ring-primary"
              />
            </div>
            <button
              onClick={handleSave}
              disabled={updatePosition.isPending}
              className="flex items-center gap-1 h-[34px] px-3 text-xs font-semibold rounded-lg bg-primary text-white hover:bg-primary/90 disabled:opacity-50 transition-colors"
            >
              <Check className="h-3.5 w-3.5" />
              {updatePosition.isPending ? 'Saving...' : 'Save'}
            </button>
          </div>
          {error && <p className="text-xs text-error">{error}</p>}
        </div>
      )}

      {/* Remove error (only shown outside edit mode) */}
      {!editing && error && (
        <div className="border-t border-border/40 px-4 py-2 bg-surface/60">
          <p className="text-xs text-error">{error}</p>
        </div>
      )}

      {/* Action plan card */}
      {actions.length > 0 && (
        <ActionPlanCard ticker={position.ticker} actions={actions} />
      )}
    </div>
  )
}
