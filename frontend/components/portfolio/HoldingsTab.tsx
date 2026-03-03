'use client'

import { useState } from 'react'
import Link from 'next/link'
import { Pencil, Trash2, Check, X } from 'lucide-react'
import { usePortfolioDetail, useUpdatePosition, useRemovePosition } from '@/lib/hooks/usePortfolio'
import { formatWeight } from '@/lib/ownership-mapping'
import type { PortfolioPosition } from '@/types/api'

/**
 * HoldingsTab — grid of current positions with inline edit and delete.
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
          <PositionRow key={pos.ticker} portfolioId={portfolioId} position={pos} />
        ))}
      </div>
    </div>
  )
}

function PositionRow({ portfolioId, position }: { portfolioId: string; position: PortfolioPosition }) {
  const [editing, setEditing] = useState(false)
  const [confirmingDelete, setConfirmingDelete] = useState(false)
  const [weight, setWeight] = useState('')
  const [costBasis, setCostBasis] = useState('')
  const [shares, setShares] = useState('')
  const [error, setError] = useState<string | null>(null)

  const updatePosition = useUpdatePosition()
  const removePosition = useRemovePosition()

  const handleEditOpen = () => {
    setWeight((position.current_weight * 100).toFixed(1))
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

  const handleSave = () => {
    const w = parseFloat(weight)
    if (isNaN(w) || w < 0 || w > 100) {
      setError('Weight must be between 0 and 100%')
      return
    }
    const data: { weight?: number; cost_basis?: number; shares?: number } = {
      weight: w / 100,
    }
    if (costBasis !== '') data.cost_basis = parseFloat(costBasis) || undefined
    if (shares !== '') data.shares = parseFloat(shares) || undefined

    updatePosition.mutate(
      { portfolioId, ticker: position.ticker, data },
      {
        onSuccess: () => {
          setEditing(false)
          setError(null)
        },
        onError: (err: Error) => setError(err.message),
      }
    )
  }

  const handleRemove = () => {
    removePosition.mutate(
      { portfolioId, ticker: position.ticker },
      { onError: (err: Error) => setError(err.message) }
    )
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
          <span className="text-xs font-mono font-semibold text-text-secondary">
            {formatWeight(position.current_weight)}
          </span>
        </div>

        <div className="flex items-center gap-3">
          {position.tier_state !== 'none' && (
            <span className="text-[9px] font-mono bg-warning/10 text-warning px-1.5 py-0.5 rounded">
              {position.tier_state.toUpperCase()}
            </span>
          )}

          <span className={`text-[9px] font-semibold uppercase ${thesisColor}`}>
            {position.thesis_state}
          </span>

          {position.compounder_score !== null && (
            <span className="text-[10px] font-mono text-text-tertiary">
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

          {/* Delete confirmation inline prompt */}
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

          {/* Edit button */}
          <button
            onClick={editing ? handleEditCancel : handleEditOpen}
            className="text-text-tertiary hover:text-text-primary transition-colors"
            title={editing ? 'Cancel edit' : 'Edit position'}
          >
            {editing ? <X className="h-3.5 w-3.5" /> : <Pencil className="h-3.5 w-3.5" />}
          </button>

          {/* Delete button — only shown when not editing */}
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
              <label className="text-[10px] font-semibold uppercase tracking-wider text-text-tertiary">Weight %</label>
              <input
                type="number"
                value={weight}
                onChange={e => setWeight(e.target.value)}
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

      {/* Remove error */}
      {!editing && error && (
        <div className="border-t border-border/40 px-4 py-2 bg-surface/60">
          <p className="text-xs text-error">{error}</p>
        </div>
      )}
    </div>
  )
}
