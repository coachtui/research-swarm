'use client'

import { useState } from 'react'
import { Check, X } from 'lucide-react'
import { useCashBalance } from '@/lib/hooks/usePortfolio'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'

interface CashCardProps {
  portfolioId: string
  cashBalance: number
  cashPct: number
}

/**
 * CashCard — small utility card showing cash balance and % of portfolio.
 * Displays default state with Update button, or inline editor when updating.
 */
export function CashCard({ portfolioId, cashBalance, cashPct }: CashCardProps) {
  const [isEditing, setIsEditing] = useState(false)
  const [inputValue, setInputValue] = useState(cashBalance.toString())
  const mutation = useCashBalance()

  const handleUpdate = () => {
    const newAmount = parseFloat(inputValue)
    if (!isNaN(newAmount) && newAmount >= 0) {
      mutation.mutate({ portfolioId, amount: newAmount }, {
        onSuccess: () => {
          setIsEditing(false)
        },
      })
    }
  }

  const handleCancel = () => {
    setInputValue(cashBalance.toString())
    setIsEditing(false)
  }

  const formattedCash = cashBalance.toLocaleString('en-US', {
    style: 'currency',
    currency: 'USD',
    maximumFractionDigits: 0,
  })

  const formattedPct = (cashPct * 100).toFixed(1) + '%'

  if (isEditing) {
    return (
      <div className="rounded-card bg-surface p-4 border border-hairline shadow-theme-sm">
        <div className="flex flex-col gap-3">
          <label className="text-sm text-text-secondary">Cash Balance</label>
          <Input
            type="number"
            min="0"
            step="0.01"
            value={inputValue}
            onChange={(e) => setInputValue(e.target.value)}
            placeholder="Enter amount"
          />
          <div className="flex gap-2">
            <Button
              variant="primary"
              size="sm"
              onClick={handleUpdate}
              disabled={mutation.isPending}
            >
              {mutation.isPending ? (
                <>
                  <span className="inline-block w-3 h-3 rounded-full border-2 border-white/30 border-t-white animate-spin mr-1" />
                  Saving...
                </>
              ) : (
                <>
                  <Check size={16} />
                  Save
                </>
              )}
            </Button>
            <Button
              variant="ghost"
              size="sm"
              onClick={handleCancel}
              disabled={mutation.isPending}
            >
              <X size={16} />
              Cancel
            </Button>
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="rounded-card bg-surface p-4 border border-hairline shadow-theme-sm">
      <div className="flex items-center justify-between">
        <div className="flex flex-col gap-1">
          <p className="text-sm text-text-tertiary">Cash</p>
          <p className="text-lg font-semibold text-text-primary">{formattedCash}</p>
          <p className="text-xs text-text-secondary">{formattedPct} of portfolio</p>
        </div>
        <Button
          variant="outline"
          size="sm"
          onClick={() => setIsEditing(true)}
        >
          Update
        </Button>
      </div>
    </div>
  )
}
