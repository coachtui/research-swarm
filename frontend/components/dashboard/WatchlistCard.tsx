import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { StockLogo } from '@/components/ui/stock-logo'
import { useRemoveFromWatchlist, useRefreshWatchlistItem } from '@/lib/hooks/useWatchlist'
import type { WatchlistItem } from '@/types/api'
import { TrendingUp, TrendingDown, Minus, RefreshCw, ExternalLink, Trash2 } from 'lucide-react'
import Link from 'next/link'
import { useState } from 'react'

interface WatchlistCardProps {
  item: WatchlistItem
}

export function WatchlistCard({ item }: WatchlistCardProps) {
  const [isRefreshing, setIsRefreshing] = useState(false)
  const { mutate: removeFromWatchlist } = useRemoveFromWatchlist()
  const { mutate: refreshItem } = useRefreshWatchlistItem()

  const handleRefresh = async () => {
    setIsRefreshing(true)
    refreshItem(item.ticker, {
      onSettled: () => setIsRefreshing(false),
    })
  }

  const handleRemove = () => {
    if (confirm(`Remove ${item.ticker} from watchlist?`)) {
      removeFromWatchlist(item.ticker)
    }
  }

  const scoreChange = item.score_change || 0
  const hasScore = item.latest_moat_score !== null

  return (
    <div
      className="rounded-card bg-surface p-5 flex flex-col gap-4 transition-colors duration-150"
      style={{ border: '1px solid var(--border)' }}
    >
      {/* Header row */}
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-center gap-3 min-w-0">
          <StockLogo ticker={item.ticker} companyName={item.company_name} size="md" />
          <div className="min-w-0">
            <h3 className="text-base font-bold text-text-primary leading-none">{item.ticker}</h3>
            {item.company_name && (
              <p className="text-xs text-text-secondary mt-1 truncate">{item.company_name}</p>
            )}
          </div>
        </div>
        {hasScore && (
          <Badge variant={getRatingVariant(item.latest_moat_score!)}>
            {getRatingLabel(item.latest_moat_score!)}
          </Badge>
        )}
      </div>

      {/* Score */}
      {hasScore ? (
        <div style={{ borderTop: '1px solid var(--border)', paddingTop: '1rem' }}>
          <div className="flex items-baseline gap-2">
            <span className="text-3xl font-bold text-text-primary font-mono">
              {item.latest_moat_score!.toFixed(1)}
            </span>
            <span className="text-xs text-text-secondary">/10</span>
            {scoreChange !== 0 && (
              <div className="flex items-center gap-1 ml-1">
                {scoreChange > 0
                  ? <TrendingUp className="h-3.5 w-3.5 text-success" />
                  : <TrendingDown className="h-3.5 w-3.5 text-error" />}
                <span className={`text-xs font-medium ${scoreChange > 0 ? 'text-success' : 'text-error'}`}>
                  {Math.abs(scoreChange).toFixed(1)}
                </span>
              </div>
            )}
          </div>
          {item.days_since_update !== null && (
            <p className="text-xs text-text-subtle mt-1">
              Updated {item.days_since_update === 0 ? 'today' : `${item.days_since_update}d ago`}
            </p>
          )}
        </div>
      ) : (
        <p className="text-xs text-text-secondary italic">No analysis yet</p>
      )}

      {/* Notes */}
      {item.notes && (
        <p
          className="text-xs text-text-secondary py-2 pl-3"
          style={{ borderLeft: '2px solid var(--accent-border)' }}
        >
          {item.notes}
        </p>
      )}

      {/* Actions */}
      <div className="flex gap-2 flex-wrap" style={{ borderTop: '1px solid var(--border)', paddingTop: '0.75rem' }}>
        <Button
          size="sm"
          variant="ghost"
          onClick={handleRefresh}
          disabled={!item.can_refresh || isRefreshing}
          className="flex-1"
        >
          <RefreshCw className={`h-3.5 w-3.5 mr-1.5 ${isRefreshing ? 'animate-spin' : ''}`} />
          {isRefreshing ? 'Refreshing…' : 'Refresh'}
        </Button>

        {item.latest_analysis_run_id && (
          <Link href={`/results/${item.latest_analysis_run_id}`} className="flex-1">
            <Button size="sm" variant="secondary" className="w-full">
              <ExternalLink className="h-3.5 w-3.5 mr-1.5" />
              View Report
            </Button>
          </Link>
        )}

        <Button
          size="sm"
          variant="ghost"
          onClick={handleRemove}
          className="text-text-subtle hover:text-error"
        >
          <Trash2 className="h-3.5 w-3.5" />
        </Button>
      </div>
    </div>
  )
}

function getRatingVariant(score: number): 'default' | 'secondary' | 'success' | 'warning' | 'error' {
  if (score >= 7.5) return 'success'
  if (score >= 6.0) return 'default'
  if (score >= 4.0) return 'warning'
  return 'error'
}

function getRatingLabel(score: number): string {
  if (score >= 7.5) return 'Strong Buy'
  if (score >= 6.0) return 'Buy'
  if (score >= 4.0) return 'Hold'
  return 'Sell'
}
