import { useWatchlist } from '@/lib/hooks/useWatchlist'
import { WatchlistCard } from './WatchlistCard'
import { Skeleton } from '@/components/ui/skeleton'
import { Button } from '@/components/ui/button'
import { Plus } from 'lucide-react'
import Link from 'next/link'

export function WatchlistView() {
  const { data: watchlist, isLoading, error } = useWatchlist()

  if (isLoading) {
    return (
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
        {[1, 2, 3].map((i) => (
          <Skeleton key={i} className="h-64" />
        ))}
      </div>
    )
  }

  if (error) {
    return (
      <div className="rounded-lg border border-surface-elevated bg-surface p-8 text-center">
        <p className="text-error">Failed to load watchlist</p>
        <p className="text-sm text-text-secondary mt-2">
          {(error as any).message || 'An error occurred'}
        </p>
      </div>
    )
  }

  if (!watchlist?.items.length) {
    return <WatchlistEmpty />
  }

  return (
    <div className="space-y-6">
      {/* Action buttons */}
      <div className="flex gap-2">
        <Link href="/analyze">
          <Button variant="outline" size="sm">
            <Plus className="h-4 w-4 mr-2" />
            Add Stock
          </Button>
        </Link>
      </div>

      {/* Watchlist grid */}
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
        {watchlist.items.map((item) => (
          <WatchlistCard key={item.id} item={item} />
        ))}
      </div>

      {/* Stats */}
      <div className="text-sm text-text-secondary text-center pt-4">
        Tracking {watchlist.total} {watchlist.total === 1 ? 'stock' : 'stocks'}
      </div>
    </div>
  )
}

function WatchlistEmpty() {
  return (
    <div className="rounded-lg border border-surface-elevated bg-surface p-12 text-center">
      <div className="mx-auto max-w-sm">
        <h3 className="text-lg font-semibold text-text-primary mb-2">
          Your watchlist is empty
        </h3>
        <p className="text-text-secondary mb-6">
          Add stocks to your watchlist to track score changes and get alerts when analysis updates.
        </p>
        <Link href="/analyze">
          <Button>
            <Plus className="h-4 w-4 mr-2" />
            Analyze Your First Stock
          </Button>
        </Link>
      </div>
    </div>
  )
}
