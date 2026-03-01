'use client'

import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import { StockLogo } from '@/components/ui/stock-logo'
import { useAnalysisHistory } from '@/lib/hooks/useAnalysisHistory'
import { formatDateTime } from '@/lib/utils/formatting'
import { ExternalLink, Search, TrendingUp, X } from 'lucide-react'
import Link from 'next/link'
import { useState } from 'react'

export function AnalysisHistoryView() {
  const [page, setPage] = useState(0)
  const [search, setSearch] = useState('')
  const hasSearch = search.trim().length > 0
  const limit = hasSearch ? 100 : 10
  const offset = hasSearch ? 0 : page * 10
  const { data, isLoading } = useAnalysisHistory(limit, offset)

  const filteredRuns = hasSearch
    ? (data?.runs ?? []).filter(r =>
        r.ticker.toUpperCase().includes(search.trim().toUpperCase())
      )
    : (data?.runs ?? [])

  const totalPages = data ? Math.ceil(data.total / 10) : 0

  if (isLoading) {
    return (
      <div className="space-y-5">
        <div className="relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-text-tertiary pointer-events-none" />
          <input
            type="text"
            placeholder="Search by ticker..."
            className="w-full pl-9 pr-4 py-2 text-sm bg-surface border border-border rounded-lg text-text-primary placeholder:text-text-tertiary focus:outline-none focus:ring-1 focus:ring-primary/40"
            disabled
          />
        </div>
        <div className="space-y-px" style={{ borderTop: '1px solid var(--border)' }}>
          {[1, 2, 3, 4, 5].map((i) => (
            <Skeleton key={i} className="h-16 rounded-none" />
          ))}
        </div>
      </div>
    )
  }

  if (!data || (data.runs.length === 0 && !hasSearch)) {
    return (
      <div
        className="rounded-card py-16 text-center space-y-4"
        style={{ background: 'var(--surface-1)', border: '1px solid var(--border)' }}
      >
        <TrendingUp className="h-10 w-10 text-text-subtle mx-auto" />
        <div>
          <h3 className="text-base font-semibold text-text-primary mb-1">No analysis history yet</h3>
          <p className="text-sm text-text-secondary mb-5">Your completed analyses will appear here.</p>
          <Link href="/dashboard">
            <Button>Analyze Your First Stock</Button>
          </Link>
        </div>
      </div>
    )
  }

  return (
    <div className="space-y-5">
      {/* Section header */}
      <div className="flex items-center justify-between gap-4">
        <div className="relative flex-1 max-w-xs">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-text-tertiary pointer-events-none" />
          <input
            type="text"
            value={search}
            onChange={e => {
              setSearch(e.target.value)
              setPage(0)
            }}
            placeholder="Search by ticker..."
            className="w-full pl-9 pr-8 py-2 text-sm bg-surface border border-border rounded-lg text-text-primary placeholder:text-text-tertiary focus:outline-none focus:ring-1 focus:ring-primary/40"
          />
          {hasSearch && (
            <button
              onClick={() => setSearch('')}
              className="absolute right-2.5 top-1/2 -translate-y-1/2 text-text-tertiary hover:text-text-secondary"
            >
              <X className="h-3.5 w-3.5" />
            </button>
          )}
        </div>

        <div className="flex items-center gap-3 flex-shrink-0">
          <p className="text-xs text-text-secondary hidden sm:block">
            {hasSearch
              ? `${filteredRuns.length} match${filteredRuns.length !== 1 ? 'es' : ''}`
              : `${data?.total ?? 0} ${(data?.total ?? 0) === 1 ? 'analysis' : 'analyses'}`}
          </p>

          {!hasSearch && totalPages > 1 && (
            <div className="flex items-center gap-2">
              <Button variant="ghost" size="sm" onClick={() => setPage(Math.max(0, page - 1))} disabled={page === 0}>
                Previous
              </Button>
              <span className="text-xs text-text-secondary">
                {page + 1} / {totalPages}
              </span>
              <Button variant="ghost" size="sm" onClick={() => setPage(Math.min(totalPages - 1, page + 1))} disabled={page >= totalPages - 1}>
                Next
              </Button>
            </div>
          )}
        </div>
      </div>

      {/* Table-style list */}
      {filteredRuns.length === 0 ? (
        <div className="rounded-card py-12 text-center" style={{ border: '1px solid var(--border)' }}>
          <p className="text-sm text-text-secondary">No reports found for &ldquo;{search.toUpperCase()}&rdquo;</p>
        </div>
      ) : (
      <div
        className="rounded-card overflow-hidden"
        style={{ border: '1px solid var(--border)' }}
      >
        {filteredRuns.map((run, idx) => (
          <div
            key={run.id}
            className="flex items-center gap-4 px-5 py-4 transition-colors duration-150 hover:bg-surface-elevated"
            style={idx > 0 ? { borderTop: '1px solid var(--border)' } : undefined}
          >
            <StockLogo ticker={run.ticker} size="md" />

            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2.5 mb-0.5">
                <span className="text-sm font-bold text-text-primary">{run.ticker}</span>
                <Badge
                  variant={
                    run.status === 'completed' ? 'success'
                    : run.status === 'running'   ? 'default'
                    : run.status === 'failed'    ? 'error'
                    : 'secondary'
                  }
                >
                  {run.status}
                </Badge>
              </div>
              <p className="text-xs text-text-secondary">
                {formatDateTime(run.created_at)}
                {run.completed_at && (
                  <span className="ml-2 text-text-subtle">· completed {formatDateTime(run.completed_at)}</span>
                )}
              </p>
            </div>

            {run.status === 'completed' && (
              <Link href={`/results/${run.id}`} className="shrink-0">
                <Button variant="ghost" size="sm">
                  <ExternalLink className="h-3.5 w-3.5 mr-1.5" />
                  View
                </Button>
              </Link>
            )}
          </div>
        ))}
      </div>
      )}
    </div>
  )
}
