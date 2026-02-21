import { Card, CardContent } from '@/components/ui/card'
import { Skeleton } from '@/components/ui/skeleton'
import type { QuotaData } from '@/types/api'
import { BarChart3, ListChecks, Zap } from 'lucide-react'

interface DashboardHeaderProps {
  quota?: QuotaData
  isLoading: boolean
}

export function DashboardHeader({ quota, isLoading }: DashboardHeaderProps) {
  return (
    <header className="border-b border-surface-elevated bg-surface">
      <div className="container mx-auto px-4 py-6">
        <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-6">
          {/* Title */}
          <div>
            <h1 className="text-3xl font-bold text-text-primary">Dashboard</h1>
            <p className="text-sm text-text-secondary mt-1">
              Track your watchlist and analysis history
            </p>
          </div>

          {/* Quota Cards */}
          {isLoading ? (
            <div className="flex gap-4">
              <Skeleton className="h-28 w-48" />
              <Skeleton className="h-28 w-40" />
            </div>
          ) : quota ? (
            <div className="flex gap-4 flex-wrap">
              <AnalysesQuotaCard quota={quota} />
              <QuotaCard
                icon={<ListChecks className="h-5 w-5" />}
                label="Watchlist"
                used={quota.watchlist_count}
                limit={quota.watchlist_limit}
                remaining={quota.watchlist_remaining}
              />
            </div>
          ) : null}
        </div>
      </div>
    </header>
  )
}

interface AnalysesQuotaCardProps {
  quota: QuotaData
}

function AnalysesQuotaCard({ quota }: AnalysesQuotaCardProps) {
  const { analyses_used, analyses_limit, boost_analyses_added, analyses_remaining, days_remaining, billing_period_end } = quota
  const totalLimit = analyses_limit + (boost_analyses_added ?? 0)
  const percentage = totalLimit > 0 ? (analyses_used / totalLimit) * 100 : 0
  const isNearLimit = percentage >= 80
  const isAtLimit = analyses_remaining === 0

  const resetDate = billing_period_end
    ? new Date(billing_period_end).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })
    : null

  return (
    <Card className="min-w-[180px]">
      <CardContent className="p-4">
        <div className="flex items-center gap-2 mb-2">
          <div className="text-text-secondary"><BarChart3 className="h-5 w-5" /></div>
          <p className="text-sm font-medium text-text-secondary">Analyses</p>
        </div>

        <div className="flex items-baseline gap-2">
          <span className="text-2xl font-bold text-text-primary">{analyses_used}</span>
          <span className="text-sm text-text-secondary">/ {totalLimit}</span>
        </div>

        {/* Progress bar */}
        <div className="mt-2 h-1.5 w-full rounded-full bg-surface-elevated overflow-hidden">
          <div
            className={`h-full transition-all ${
              isAtLimit ? 'bg-error' : isNearLimit ? 'bg-warning' : 'bg-primary'
            }`}
            style={{ width: `${Math.min(percentage, 100)}%` }}
          />
        </div>

        {/* Boost indicator */}
        {boost_analyses_added > 0 && (
          <div className="flex items-center gap-1 mt-1.5">
            <Zap className="h-3 w-3 text-warning" />
            <p className="text-xs text-warning">+{boost_analyses_added} boost</p>
          </div>
        )}

        {/* Status line */}
        {isAtLimit ? (
          <p className="text-xs text-error mt-1">Limit reached</p>
        ) : isNearLimit ? (
          <p className="text-xs text-warning mt-1">{analyses_remaining} remaining</p>
        ) : (
          <p className="text-xs text-text-tertiary mt-1">{analyses_remaining} remaining</p>
        )}

        {/* Reset info */}
        {resetDate && (
          <p className="text-xs text-text-tertiary mt-0.5">
            Resets {resetDate}
            {days_remaining != null && ` (${days_remaining}d)`}
          </p>
        )}
      </CardContent>
    </Card>
  )
}

interface QuotaCardProps {
  icon: React.ReactNode
  label: string
  used: number
  limit: number
  remaining: number
}

function QuotaCard({ icon, label, used, limit, remaining }: QuotaCardProps) {
  const percentage = limit > 0 ? (used / limit) * 100 : 0
  const isNearLimit = percentage >= 80
  const isAtLimit = remaining === 0

  return (
    <Card className="min-w-[160px]">
      <CardContent className="p-4">
        <div className="flex items-center gap-2 mb-2">
          <div className="text-text-secondary">{icon}</div>
          <p className="text-sm font-medium text-text-secondary">{label}</p>
        </div>

        <div className="flex items-baseline gap-2">
          <span className="text-2xl font-bold text-text-primary">{used}</span>
          <span className="text-sm text-text-secondary">/ {limit}</span>
        </div>

        {/* Progress bar */}
        <div className="mt-2 h-1.5 w-full rounded-full bg-surface-elevated overflow-hidden">
          <div
            className={`h-full transition-all ${
              isAtLimit ? 'bg-error' : isNearLimit ? 'bg-warning' : 'bg-primary'
            }`}
            style={{ width: `${Math.min(percentage, 100)}%` }}
          />
        </div>

        {/* Status text */}
        {isAtLimit ? (
          <p className="text-xs text-error mt-1">Limit reached</p>
        ) : isNearLimit ? (
          <p className="text-xs text-warning mt-1">{remaining} remaining</p>
        ) : (
          <p className="text-xs text-text-tertiary mt-1">{remaining} remaining</p>
        )}
      </CardContent>
    </Card>
  )
}
