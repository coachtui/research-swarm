import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import { StockLogo } from '@/components/ui/stock-logo'
import { useAdminAnalyses } from '@/lib/hooks/useAdmin'
import { formatDateTime } from '@/lib/utils/formatting'
import { ExternalLink } from 'lucide-react'
import { useState } from 'react'
import { useRouter } from 'next/navigation'

export function AdminAnalysisTable() {
  const router = useRouter()
  const [ticker, setTicker] = useState<string>('')
  const { data, isLoading } = useAdminAnalyses(50, ticker || undefined)

  if (isLoading) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Recent Analyses</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="space-y-4">
            {[1, 2, 3, 4, 5].map((i) => (
              <Skeleton key={i} className="h-16" />
            ))}
          </div>
        </CardContent>
      </Card>
    )
  }

  if (!data) {
    return (
      <Card>
        <CardContent className="py-12 text-center">
          <p className="text-text-secondary">Failed to load analyses</p>
        </CardContent>
      </Card>
    )
  }

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
          <CardTitle>Recent Analyses ({data.total})</CardTitle>
          <div className="flex items-center gap-2">
            <input
              type="text"
              placeholder="Filter by ticker..."
              value={ticker}
              onChange={(e) => setTicker(e.target.value.toUpperCase())}
              className="px-3 py-1.5 rounded-md border border-surface-elevated bg-surface text-sm text-text-primary focus:outline-none focus:ring-2 focus:ring-primary w-40"
            />
          </div>
        </div>
      </CardHeader>
      <CardContent>
        <div className="space-y-4">
          {data.analyses.map((analysis) => (
            <div
              key={analysis.run_id}
              className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 p-4 rounded-lg border border-surface-elevated hover:border-primary/50 transition-colors"
            >
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-3 mb-1 flex-wrap">
                  <StockLogo ticker={analysis.ticker} size="md" />
                  <p className="font-bold text-lg text-text-primary">
                    {analysis.ticker}
                  </p>
                  {analysis.moat_score !== null && (
                    <Badge variant={
                      analysis.moat_score >= 7.5 ? 'success' :
                      analysis.moat_score >= 6.0 ? 'secondary' :
                      analysis.moat_score >= 4.0 ? 'warning' : 'error'
                    }>
                      {analysis.moat_score.toFixed(1)}/10
                    </Badge>
                  )}
                  <Badge variant="secondary">{analysis.status}</Badge>
                </div>

                <p className="text-sm text-text-secondary mb-1">
                  By: {analysis.user_email}
                </p>

                <p className="text-xs text-text-tertiary">
                  {formatDateTime(analysis.created_at)} •
                  Cost: ${analysis.cost_usd.toFixed(2)}
                </p>
              </div>

              <div className="flex items-center gap-2 self-end sm:self-auto shrink-0">
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => router.push(`/results/${analysis.run_id}`)}
                  className="cursor-pointer"
                >
                  <ExternalLink className="h-4 w-4 mr-2" />
                  View Report
                </Button>
              </div>
            </div>
          ))}

          {data.analyses.length === 0 && (
            <p className="text-center py-8 text-text-secondary">
              No analyses found{ticker && ` for ${ticker}`}
            </p>
          )}
        </div>
      </CardContent>
    </Card>
  )
}
