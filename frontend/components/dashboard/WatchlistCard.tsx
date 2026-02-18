import { Card, CardHeader, CardContent } from '@/components/ui/card'
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
      onSettled: () => {
        setIsRefreshing(false)
      },
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
    <Card className="hover:border-primary/50 transition-colors">
      <CardHeader className="pb-3">
        <div className="flex items-start justify-between">
          <div className="flex items-center gap-3">
            <StockLogo ticker={item.ticker} companyName={item.company_name} size="md" />
            <div>
              <h3 className="text-lg font-bold text-text-primary">{item.ticker}</h3>
              {item.company_name && (
                <p className="text-sm text-text-secondary mt-0.5">
                  {item.company_name}
                </p>
              )}
            </div>
          </div>

          {hasScore && (
            <Badge variant={getRatingVariant(item.latest_moat_score!)}>
              {getRatingLabel(item.latest_moat_score!)}
            </Badge>
          )}
        </div>
      </CardHeader>

      <CardContent className="space-y-4">
        {/* Score display */}
        {hasScore ? (
          <div>
            <div className="flex items-baseline gap-2">
              <span className="text-3xl font-bold text-text-primary">
                {item.latest_moat_score!.toFixed(1)}
              </span>
              <span className="text-sm text-text-secondary">/10</span>

              {scoreChange !== 0 && (
                <div className="flex items-center gap-1 ml-2">
                  {scoreChange > 0 ? (
                    <TrendingUp className="h-4 w-4 text-success" />
                  ) : scoreChange < 0 ? (
                    <TrendingDown className="h-4 w-4 text-error" />
                  ) : (
                    <Minus className="h-4 w-4 text-text-tertiary" />
                  )}
                  <span className={`text-sm font-medium ${
                    scoreChange > 0 ? 'text-success' : scoreChange < 0 ? 'text-error' : 'text-text-tertiary'
                  }`}>
                    {Math.abs(scoreChange).toFixed(1)}
                  </span>
                </div>
              )}
            </div>

            {/* Last updated */}
            {item.days_since_update !== null && (
              <p className="text-xs text-text-tertiary mt-1">
                Updated {item.days_since_update === 0 ? 'today' : `${item.days_since_update} day${item.days_since_update === 1 ? '' : 's'} ago`}
              </p>
            )}
          </div>
        ) : (
          <div className="text-center py-4">
            <p className="text-sm text-text-secondary">No analysis yet</p>
          </div>
        )}

        {/* User notes */}
        {item.notes && (
          <p className="text-sm text-text-secondary border-l-2 border-primary pl-3 py-1">
            {item.notes}
          </p>
        )}

        {/* Actions */}
        <div className="flex flex-wrap gap-2">
          <Button
            size="sm"
            variant="outline"
            onClick={handleRefresh}
            disabled={!item.can_refresh || isRefreshing}
            className="flex-1"
          >
            <RefreshCw className={`h-4 w-4 mr-2 ${isRefreshing ? 'animate-spin' : ''}`} />
            {isRefreshing ? 'Refreshing...' : 'Refresh'}
          </Button>

          {item.latest_analysis_run_id && (
            <Link href={`/results/${item.latest_analysis_run_id}`} className="flex-1">
              <Button size="sm" variant="secondary" className="w-full">
                <ExternalLink className="h-4 w-4 mr-2" />
                View Report
              </Button>
            </Link>
          )}

          <Button
            size="sm"
            variant="ghost"
            onClick={handleRemove}
            className="text-text-tertiary hover:text-error"
          >
            <Trash2 className="h-4 w-4" />
          </Button>
        </div>
      </CardContent>
    </Card>
  )
}

// Helper functions for rating badges
function getRatingVariant(score: number): 'default' | 'secondary' | 'destructive' | 'outline' {
  if (score >= 7.5) return 'default' // Strong Buy
  if (score >= 6.0) return 'secondary' // Buy
  if (score >= 4.0) return 'outline' // Hold
  return 'destructive' // Sell
}

function getRatingLabel(score: number): string {
  if (score >= 7.5) return 'Strong Buy'
  if (score >= 6.0) return 'Buy'
  if (score >= 4.0) return 'Hold'
  return 'Sell'
}
