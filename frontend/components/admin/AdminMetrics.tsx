import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card'
import { Skeleton } from '@/components/ui/skeleton'
import type { PlatformMetrics } from '@/types/api'
import { Users, BarChart3, Star, TrendingUp } from 'lucide-react'

interface AdminMetricsProps {
  metrics?: PlatformMetrics
  isLoading: boolean
}

export function AdminMetrics({ metrics, isLoading }: AdminMetricsProps) {
  if (isLoading) {
    return (
      <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-4">
        {[1, 2, 3, 4].map((i) => (
          <Skeleton key={i} className="h-32" />
        ))}
      </div>
    )
  }

  if (!metrics) {
    return (
      <div className="text-center py-12">
        <p className="text-text-secondary">Failed to load metrics</p>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {/* Top metrics grid */}
      <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-4">
        <MetricCard
          icon={<Users className="h-5 w-5" />}
          title="Total Users"
          value={metrics.users.total}
          subtitle={`Free: ${metrics.users.free} • Pro: ${metrics.users.pro} • Premium: ${metrics.users.premium}`}
        />

        <MetricCard
          icon={<BarChart3 className="h-5 w-5" />}
          title="Total Analyses"
          value={metrics.analyses.total}
          subtitle={`${metrics.analyses.today} today`}
        />

        <MetricCard
          icon={<Star className="h-5 w-5" />}
          title="Watchlist Adoption"
          value={`${(metrics.watchlist_adoption_rate * 100).toFixed(0)}%`}
          subtitle="Users with watchlists"
        />

        <MetricCard
          icon={<TrendingUp className="h-5 w-5" />}
          title="Avg. Analyses/User"
          value={(metrics.analyses.total / metrics.users.total).toFixed(1)}
          subtitle="All-time average"
        />
      </div>

      {/* User distribution chart */}
      <Card>
        <CardHeader>
          <CardTitle>User Distribution by Tier</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="space-y-4">
            {/* Free tier disabled - only showing test users if any exist */}
            {metrics.users.free > 0 && (
              <TierBar
                label="Free (Legacy)"
                count={metrics.users.free}
                total={metrics.users.total}
                color="bg-text-secondary"
              />
            )}
            <TierBar
              label="Pro"
              count={metrics.users.pro}
              total={metrics.users.total}
              color="bg-primary"
            />
            <TierBar
              label="Premium"
              count={metrics.users.premium}
              total={metrics.users.total}
              color="bg-success"
            />
          </div>
        </CardContent>
      </Card>
    </div>
  )
}

interface MetricCardProps {
  icon: React.ReactNode
  title: string
  value: string | number
  subtitle: string
}

function MetricCard({ icon, title, value, subtitle }: MetricCardProps) {
  return (
    <Card>
      <CardContent className="p-6">
        <div className="flex items-center gap-2 mb-2">
          <div className="text-text-secondary">{icon}</div>
          <p className="text-sm font-medium text-text-secondary">{title}</p>
        </div>

        <p className="text-3xl font-bold text-text-primary mb-1">{value}</p>
        <p className="text-xs text-text-tertiary">{subtitle}</p>
      </CardContent>
    </Card>
  )
}

interface TierBarProps {
  label: string
  count: number
  total: number
  color: string
}

function TierBar({ label, count, total, color }: TierBarProps) {
  const percentage = (count / total) * 100

  return (
    <div>
      <div className="flex justify-between text-sm mb-2">
        <span className="text-text-secondary">{label}</span>
        <span className="text-text-primary font-medium">
          {count} ({percentage.toFixed(0)}%)
        </span>
      </div>
      <div className="h-2 rounded-full bg-surface-elevated overflow-hidden">
        <div
          className={`h-full ${color} transition-all`}
          style={{ width: `${percentage}%` }}
        />
      </div>
    </div>
  )
}
