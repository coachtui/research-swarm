'use client'

import { useState } from 'react'
import Link from 'next/link'
import { Pencil, Trash2, Check, X, Plus, ChevronDown } from 'lucide-react'
import {
  usePortfolioDetail,
  useAddPosition,
  useUpdatePosition,
  useRemovePosition,
} from '@/lib/hooks/usePortfolio'
import { formatWeight } from '@/lib/ownership-mapping'
import type { PortfolioPosition } from '@/types/api'

/**
 * HoldingsTab — grid of current positions with inline add, edit, and delete.
 */
export function HoldingsTab({ portfolioId }: { portfolioId: string }) {
  const { data: portfolio, isLoading } = usePortfolioDetail(portfolioId)
  const [addingPosition, setAddingPosition] = useState(false)

  if (isLoading) {
    return <div className="text-sm text-text-tertiary text-center py-8">Loading holdings...</div>
  }

  const hasPositions = portfolio && portfolio.positions.length > 0
  const sorted = hasPositions
    ? [...portfolio.positions].sort((a, b) => b.current_weight - a.current_weight)
    : []

  return (
    <div className="space-y-3">
      {/* Summary row */}
      <div className="flex items-center justify-between text-xs text-text-tertiary">
        <span>
          {portfolio ? `${portfolio.positions.length} position${portfolio.positions.length !== 1 ? 's' : ''}` : 'No portfolio'}
        </span>
        <div className="flex items-center gap-3">
          {portfolio && (
            <span>
              Total weight:{' '}
              <span className="font-mono font-semibold text-text-primary">
                {formatWeight(portfolio.total_weight)}
              </span>
            </span>
          )}
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

      {/* Position grid */}
      {hasPositions ? (
        <div className="grid gap-2">
          {sorted.map((pos) => (
            <PositionRow key={pos.ticker} portfolioId={portfolioId} position={pos} />
          ))}
        </div>
      ) : (
        !addingPosition && (
          <div className="text-center py-8 text-sm text-text-tertiary">
            No positions yet — click Add Position above to get started.
          </div>
        )
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
  const [weight, setWeight] = useState('5')
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
    const w = parseFloat(weight)
    if (isNaN(w) || w <= 0 || w > 100) {
      setError('Weight must be between 0.1 and 100%')
      return
    }
    const cb = costBasis ? parseFloat(costBasis) : undefined
    if (costBasis && isNaN(cb!)) {
      setError('Cost basis must be a valid number')
      return
    }
    const sh = shares ? parseFloat(shares) : undefined
    if (shares && isNaN(sh!)) {
      setError('Shares must be a valid number')
      return
    }

    try {
      await addPosition.mutateAsync({ portfolioId, ticker: t, weight: w / 100, costBasis: cb, shares: sh })
      setTicker('')
      setWeight('5')
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
          <label className="text-[10px] font-semibold uppercase tracking-wider text-text-tertiary">Weight %</label>
          <input
            type="number"
            value={weight}
            onChange={e => setWeight(e.target.value)}
            min={0}
            max={100}
            step={0.5}
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

  const handleSave = async () => {
    const w = parseFloat(weight)
    if (isNaN(w) || w < 0 || w > 100) {
      setError('Weight must be between 0 and 100%')
      return
    }
    const data: { weight?: number; cost_basis?: number; shares?: number } = { weight: w / 100 }
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

      {/* Remove error (only shown outside edit mode) */}
      {!editing && error && (
        <div className="border-t border-border/40 px-4 py-2 bg-surface/60">
          <p className="text-xs text-error">{error}</p>
        </div>
      )}
    </div>
  )
}
