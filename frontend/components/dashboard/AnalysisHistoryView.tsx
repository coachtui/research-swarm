'use client'

import { Card, CardContent } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import { StockLogo } from '@/components/ui/stock-logo'
import { useAnalysisHistory } from '@/lib/hooks/useAnalysisHistory'
import { formatDateTime } from '@/lib/utils/formatting'
import { ExternalLink, TrendingUp, TrendingDown } from 'lucide-react'
import Link from 'next/link'
import { useState } from 'react'

export function AnalysisHistoryView() {
  const [page, setPage] = useState(0)
  const limit = 10
  const offset = page * limit

  const { data, isLoading } = useAnalysisHistory(limit, offset)

  if (isLoading) {
    return (
      <div className="space-y-4">
        {[1, 2, 3, 4, 5].map((i) => (
          <Skeleton key={i} className="h-24" />
        ))}
      </div>
    )
  }

  if (!data || data.runs.length === 0) {
    return (
      <Card>
        <CardContent className="py-12 text-center space-y-4">
          <TrendingUp className="h-12 w-12 text-text-tertiary mx-auto" />
          <div>
            <h3 className="text-lg font-semibold text-text-primary mb-2">
              No analysis history yet
            </h3>
            <p className="text-text-secondary mb-4">
              Your completed analyses will appear here.
            </p>
            <Link href="/analyze">
              <Button>Analyze Your First Stock</Button>
            </Link>
          </div>
        </CardContent>
      </Card>
    )
  }

  const totalPages = Math.ceil(data.total / limit)

  return (
    <div className="space-y-6">
      {/* Header with pagination */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-semibold text-text-primary">
            Analysis History
          </h2>
          <p className="text-sm text-text-secondary">
            {data.total} {data.total === 1 ? 'analysis' : 'analyses'} completed
          </p>
        </div>

        {totalPages > 1 && (
          <div className="flex items-center gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={() => setPage(Math.max(0, page - 1))}
              disabled={page === 0}
            >
              Previous
            </Button>
            <span className="text-sm text-text-secondary">
              Page {page + 1} of {totalPages}
            </span>
            <Button
              variant="outline"
              size="sm"
              onClick={() => setPage(Math.min(totalPages - 1, page + 1))}
              disabled={page >= totalPages - 1}
            >
              Next
            </Button>
          </div>
        )}
      </div>

      {/* Analysis list */}
      <div className="space-y-4">
        {data.runs.map((run) => (
          <Card key={run.id} className="hover:border-primary/50 transition-colors">
            <CardContent className="p-6">
              <div className="flex items-start justify-between">
                <div className="flex-1">
                  {/* Ticker and status */}
                  <div className="flex items-center gap-3 mb-2">
                    <StockLogo ticker={run.ticker} size="md" />
                    <h3 className="text-xl font-bold text-text-primary">
                      {run.ticker}
                    </h3>
                    <Badge
                      variant={
                        run.status === 'completed'
                          ? 'default'
                          : run.status === 'running'
                          ? 'secondary'
                          : run.status === 'failed'
                          ? 'destructive'
                          : 'outline'
                      }
                    >
                      {run.status}
                    </Badge>
                  </div>

                  {/* Metadata */}
                  <div className="flex items-center gap-4 text-sm text-text-secondary">
                    <span>{formatDateTime(run.created_at)}</span>
                    {run.completed_at && (
                      <>
                        <span>•</span>
                        <span>
                          Completed {formatDateTime(run.completed_at)}
                        </span>
                      </>
                    )}
                  </div>
                </div>

                {/* Action button */}
                {run.status === 'completed' && (
                  <Link href={`/results/${run.id}`}>
                    <Button variant="outline" size="sm">
                      <ExternalLink className="h-4 w-4 mr-2" />
                      View Report
                    </Button>
                  </Link>
                )}
              </div>
            </CardContent>
          </Card>
        ))}
      </div>
    </div>
  )
}
