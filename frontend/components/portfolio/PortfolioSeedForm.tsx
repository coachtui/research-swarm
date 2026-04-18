'use client'

import { useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { apiClient } from '@/lib/api/client'
import { Button } from '@/components/ui/button'
import { Plus, X } from 'lucide-react'

/**
 * PortfolioSeedForm — manual entry form for seeding portfolio positions.
 *
 * Creates portfolio on first position add. Allocation is computed automatically
 * from shares × current price — no weight entry required.
 */
export function PortfolioSeedForm() {
  const queryClient = useQueryClient()
  const [positions, setPositions] = useState<Array<{
    ticker: string
    shares: number
    costBasis: string
  }>>([])
  const [currentTicker, setCurrentTicker] = useState('')
  const [currentShares, setCurrentShares] = useState('')
  const [currentCostBasis, setCurrentCostBasis] = useState('')
  const [error, setError] = useState<string | null>(null)

  const createPortfolio = useMutation({
    mutationFn: async () => {
      const portfolio = await apiClient.createPortfolio('Core', 'compounder')
      for (const pos of positions) {
        await apiClient.addPosition(
          portfolio.id,
          pos.ticker,
          pos.shares,
          pos.costBasis ? parseFloat(pos.costBasis) : undefined,
        )
      }
      return portfolio
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['portfolios'] })
      setPositions([])
    },
    onError: (err: Error) => {
      setError(err.message)
    },
  })

  const addPosition = () => {
    const ticker = currentTicker.trim().toUpperCase()
    if (!ticker) return
    if (positions.some(p => p.ticker === ticker)) {
      setError(`${ticker} already added`)
      return
    }
    const shares = parseFloat(currentShares)
    if (!currentShares || isNaN(shares) || shares <= 0) {
      setError('Shares is required and must be greater than 0')
      return
    }
    setPositions(prev => [...prev, { ticker, shares, costBasis: currentCostBasis }])
    setCurrentTicker('')
    setCurrentShares('')
    setCurrentCostBasis('')
    setError(null)
  }

  const removePosition = (ticker: string) => {
    setPositions(prev => prev.filter(p => p.ticker !== ticker))
  }

  return (
    <div className="space-y-6">
      <div className="text-center space-y-2">
        <h3 className="text-lg font-semibold text-text-primary">Build Your Portfolio</h3>
        <p className="text-sm text-text-secondary">
          Add your current holdings. Allocation is computed automatically from your shares and current price.
        </p>
      </div>

      {/* ── Entry form ──────────────────────────────────────────────── */}
      <div className="flex flex-wrap items-end gap-3">
        <div className="flex-1 min-w-[120px]">
          <label className="text-[10px] font-semibold uppercase tracking-wider text-text-tertiary">Ticker</label>
          <input
            type="text"
            value={currentTicker}
            onChange={e => setCurrentTicker(e.target.value.toUpperCase())}
            onKeyDown={e => e.key === 'Enter' && addPosition()}
            placeholder="AAPL"
            className="w-full mt-1 px-3 py-2 text-sm bg-surface border border-border rounded-lg text-text-primary placeholder:text-text-tertiary focus:outline-none focus:ring-1 focus:ring-primary"
          />
        </div>
        <div className="w-24">
          <label className="text-[10px] font-semibold uppercase tracking-wider text-text-tertiary">Shares</label>
          <input
            type="number"
            value={currentShares}
            onChange={e => setCurrentShares(e.target.value)}
            min={0}
            step={1}
            placeholder="Required"
            className="w-full mt-1 px-3 py-2 text-sm bg-surface border border-border rounded-lg text-text-primary font-mono focus:outline-none focus:ring-1 focus:ring-primary"
          />
        </div>
        <div className="w-28">
          <label className="text-[10px] font-semibold uppercase tracking-wider text-text-tertiary">Cost / Share</label>
          <input
            type="text"
            value={currentCostBasis}
            onChange={e => setCurrentCostBasis(e.target.value)}
            placeholder="Optional"
            className="w-full mt-1 px-3 py-2 text-sm bg-surface border border-border rounded-lg text-text-primary placeholder:text-text-tertiary font-mono focus:outline-none focus:ring-1 focus:ring-primary"
          />
        </div>
        <Button onClick={addPosition} size="sm" className="h-9">
          <Plus className="h-3.5 w-3.5 mr-1" /> Add
        </Button>
      </div>

      {error && (
        <p className="text-xs text-error">{error}</p>
      )}

      {/* ── Position list ───────────────────────────────────────────── */}
      {positions.length > 0 && (
        <div className="space-y-2">
          {positions.map((pos) => (
            <div key={pos.ticker} className="flex items-center justify-between rounded-lg border border-border/60 bg-surface/30 px-4 py-2.5">
              <div className="flex items-center gap-3">
                <span className="text-sm font-bold font-mono text-text-primary">{pos.ticker}</span>
                <span className="text-xs font-mono text-text-secondary">{pos.shares} shares</span>
                {pos.costBasis && (
                  <span className="text-[10px] text-text-tertiary">@ ${pos.costBasis}</span>
                )}
              </div>
              <button onClick={() => removePosition(pos.ticker)} className="text-text-tertiary hover:text-error transition-colors">
                <X className="h-3.5 w-3.5" />
              </button>
            </div>
          ))}

          <div className="flex items-center justify-between pt-2">
            <span className="text-xs text-text-tertiary">
              {positions.length} position{positions.length > 1 ? 's' : ''} — allocation computed after creation
            </span>
            <Button
              onClick={() => createPortfolio.mutate()}
              disabled={positions.length === 0 || createPortfolio.isPending}
            >
              {createPortfolio.isPending ? 'Creating...' : 'Create Portfolio'}
            </Button>
          </div>
        </div>
      )}
    </div>
  )
}
