import { Skeleton } from '@/components/ui/skeleton'
import type { QuotaData } from '@/types/api'
import { BarChart3, ListChecks, Zap } from 'lucide-react'

interface DashboardHeaderProps {
  quota?: QuotaData
  isLoading: boolean
}

export function DashboardHeader({ quota, isLoading }: DashboardHeaderProps) {
  return (
    <header style={{ borderBottom: '1px solid var(--border)', background: 'var(--surface-1)' }}>
      <div className="container mx-auto px-4 py-6">
        <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-6">
          {/* Title */}
          <div>
            <p className="text-xs font-medium tracking-widest uppercase text-text-secondary mb-1">Overview</p>
            <h1 className="text-2xl font-bold text-text-primary tracking-tight">Dashboard</h1>
          </div>

          {/* Quota */}
          {isLoading ? (
            <div className="flex gap-3">
              <Skeleton className="h-20 w-44" />
              <Skeleton className="h-20 w-36" />
            </div>
          ) : quota ? (
            <div className="flex gap-3 flex-wrap">
              <AnalysesQuotaCard quota={quota} />
              <QuotaCard
                icon={<ListChecks className="h-4 w-4" />}
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
    <div
      className="min-w-[168px] rounded-card p-4"
      style={{ background: 'var(--surface-2)', border: '1px solid var(--border)' }}
    >
      <div className="flex items-center gap-2 mb-2">
        <BarChart3 className="h-4 w-4 text-text-secondary" />
        <p className="text-xs font-medium text-text-secondary">Analyses</p>
      </div>
      <div className="flex items-baseline gap-1.5">
        <span className="text-xl font-bold text-text-primary">{analyses_used}</span>
        <span className="text-xs text-text-secondary">/ {totalLimit}</span>
      </div>

      {/* Progress bar */}
      <div className="mt-2.5 h-1 w-full rounded-full overflow-hidden" style={{ background: 'var(--border-strong)' }}>
        <div
          className={`h-full transition-all ${isAtLimit ? 'bg-error' : isNearLimit ? 'bg-warning' : 'bg-primary'}`}
          style={{ width: `${Math.min(percentage, 100)}%` }}
        />
      </div>

      {boost_analyses_added > 0 && (
        <div className="flex items-center gap-1 mt-1.5">
          <Zap className="h-3 w-3 text-warning" />
          <p className="text-xs text-warning">+{boost_analyses_added} boost</p>
        </div>
      )}

      <p className={`text-xs mt-1 ${isAtLimit ? 'text-error' : isNearLimit ? 'text-warning' : 'text-text-subtle'}`}>
        {isAtLimit ? 'Limit reached' : `${analyses_remaining} remaining`}
      </p>

      {resetDate && (
        <p className="text-xs text-text-subtle mt-0.5">
          Resets {resetDate}{days_remaining != null && ` (${days_remaining}d)`}
        </p>
      )}
    </div>
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
    <div
      className="min-w-[140px] rounded-card p-4"
      style={{ background: 'var(--surface-2)', border: '1px solid var(--border)' }}
    >
      <div className="flex items-center gap-2 mb-2">
        <span className="text-text-secondary">{icon}</span>
        <p className="text-xs font-medium text-text-secondary">{label}</p>
      </div>
      <div className="flex items-baseline gap-1.5">
        <span className="text-xl font-bold text-text-primary">{used}</span>
        <span className="text-xs text-text-secondary">/ {limit}</span>
      </div>

      <div className="mt-2.5 h-1 w-full rounded-full overflow-hidden" style={{ background: 'var(--border-strong)' }}>
        <div
          className={`h-full transition-all ${isAtLimit ? 'bg-error' : isNearLimit ? 'bg-warning' : 'bg-primary'}`}
          style={{ width: `${Math.min(percentage, 100)}%` }}
        />
      </div>

      <p className={`text-xs mt-1 ${isAtLimit ? 'text-error' : isNearLimit ? 'text-warning' : 'text-text-subtle'}`}>
        {isAtLimit ? 'Limit reached' : `${remaining} remaining`}
      </p>
    </div>
  )
}
