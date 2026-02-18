'use client'

import { Button } from '@/components/ui/button'
import { useAddToWatchlist, useRemoveFromWatchlist, useWatchlist } from '@/lib/hooks/useWatchlist'
import { Star, StarOff, Loader2 } from 'lucide-react'
import { useState } from 'react'

interface AddToWatchlistButtonProps {
  ticker: string
  companyName?: string | null
  runId?: string | null
}

export function AddToWatchlistButton({ ticker, companyName, runId }: AddToWatchlistButtonProps) {
  const [isLoading, setIsLoading] = useState(false)

  // Check if already in watchlist
  const { data: watchlist } = useWatchlist()
  const isInWatchlist = watchlist?.items.some(item => item.ticker === ticker) || false

  const { mutate: addToWatchlist } = useAddToWatchlist()
  const { mutate: removeFromWatchlist } = useRemoveFromWatchlist()

  const handleToggle = () => {
    setIsLoading(true)

    if (isInWatchlist) {
      // Remove from watchlist
      removeFromWatchlist(ticker, {
        onSettled: () => setIsLoading(false)
      })
    } else {
      // Add to watchlist
      addToWatchlist({
        ticker,
        company_name: companyName || undefined,
        analysis_run_id: runId || undefined,
      }, {
        onSettled: () => setIsLoading(false)
      })
    }
  }

  return (
    <Button
      onClick={handleToggle}
      disabled={isLoading}
      variant={isInWatchlist ? 'secondary' : 'primary'}
      size="sm"
    >
      {isLoading ? (
        <Loader2 className="h-4 w-4 mr-2 animate-spin" />
      ) : isInWatchlist ? (
        <StarOff className="h-4 w-4 mr-2" />
      ) : (
        <Star className="h-4 w-4 mr-2" />
      )}
      {isInWatchlist ? 'Remove from Watchlist' : 'Add to Watchlist'}
    </Button>
  )
}
