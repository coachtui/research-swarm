import { Card, CardContent } from '@/components/ui/card'
import { Skeleton } from '@/components/ui/skeleton'
import type { QuotaData } from '@/types/api'
import { BarChart3, ListChecks } from 'lucide-react'

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
              <Skeleton className="h-24 w-40" />
              <Skeleton className="h-24 w-40" />
            </div>
          ) : quota ? (
            <div className="flex gap-4">
              <QuotaCard
                icon={<BarChart3 className="h-5 w-5" />}
                label="Analyses"
                used={quota.analyses_used}
                limit={quota.analyses_limit}
                remaining={quota.analyses_remaining}
                tier={quota.tier}
              />
              <QuotaCard
                icon={<ListChecks className="h-5 w-5" />}
                label="Watchlist"
                used={quota.watchlist_count}
                limit={quota.watchlist_limit}
                remaining={quota.watchlist_remaining}
                tier={quota.tier}
              />
            </div>
          ) : null}
        </div>
      </div>
    </header>
  )
}

interface QuotaCardProps {
  icon: React.ReactNode
  label: string
  used: number
  limit: number
  remaining: number
  tier: string
}

function QuotaCard({ icon, label, used, limit, remaining, tier }: QuotaCardProps) {
  const percentage = (used / limit) * 100
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
          <span className="text-2xl font-bold text-text-primary">
            {used}
          </span>
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
          <p className="text-xs text-error mt-1">
            Limit reached
          </p>
        ) : isNearLimit ? (
          <p className="text-xs text-warning mt-1">
            {remaining} remaining
          </p>
        ) : (
          <p className="text-xs text-text-tertiary mt-1">
            {remaining} remaining
          </p>
        )}
      </CardContent>
    </Card>
  )
}
