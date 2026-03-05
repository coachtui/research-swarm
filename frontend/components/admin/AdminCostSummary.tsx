import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card'
import { Skeleton } from '@/components/ui/skeleton'
import type { CostSummary } from '@/types/api'
import { DollarSign, TrendingUp, Calendar, Clock } from 'lucide-react'

interface AdminCostSummaryProps {
  costs?: CostSummary
  isLoading: boolean
}

export function AdminCostSummary({ costs, isLoading }: AdminCostSummaryProps) {
  if (isLoading) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Cost Tracking</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-4">
            {[1, 2, 3, 4].map((i) => (
              <Skeleton key={i} className="h-24" />
            ))}
          </div>
        </CardContent>
      </Card>
    )
  }

  if (!costs) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Cost Tracking</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-text-secondary">Failed to load cost data</p>
        </CardContent>
      </Card>
    )
  }

  const formatCost = (amount: number) => {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: 'USD',
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    }).format(amount)
  }

  const costPerAnalysis = (total: number, count: number) => {
    if (count === 0) return '$0.00'
    return formatCost(total / count)
  }

  return (
    <Card>
      <CardHeader>
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-1">
          <CardTitle>Cost Tracking</CardTitle>
          <div className="text-sm text-text-secondary">
            Running tallies for all analyses
          </div>
        </div>
      </CardHeader>
      <CardContent>
        <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-4">
          {/* Today */}
          <CostPeriodCard
            icon={<Clock className="h-5 w-5" />}
            period="Today"
            cost={costs.today}
            analysisCount={costs.analyses_today}
            avgCost={costPerAnalysis(costs.today, costs.analyses_today)}
            color="text-primary"
          />

          {/* Week */}
          <CostPeriodCard
            icon={<Calendar className="h-5 w-5" />}
            period="This Week"
            cost={costs.week}
            analysisCount={costs.analyses_week}
            avgCost={costPerAnalysis(costs.week, costs.analyses_week)}
            color="text-info"
          />

          {/* Month */}
          <CostPeriodCard
            icon={<TrendingUp className="h-5 w-5" />}
            period="This Month"
            cost={costs.month}
            analysisCount={costs.analyses_month}
            avgCost={costPerAnalysis(costs.month, costs.analyses_month)}
            color="text-success"
          />

          {/* Year */}
          <CostPeriodCard
            icon={<DollarSign className="h-5 w-5" />}
            period="This Year"
            cost={costs.year}
            analysisCount={costs.analyses_year}
            avgCost={costPerAnalysis(costs.year, costs.analyses_year)}
            color="text-warning"
          />
        </div>

        {/* All-time summary */}
        <div className="mt-6 pt-6 border-t border-surface-elevated">
          <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
            <div>
              <p className="text-sm font-medium text-text-secondary mb-1">
                All-Time Total
              </p>
              <p className="text-2xl font-bold text-text-primary tabular-nums">
                {formatCost(costs.all_time)}
              </p>
            </div>
            <div className="sm:text-right">
              <p className="text-sm font-medium text-text-secondary mb-1">
                Average per Analysis
              </p>
              <p className="text-2xl font-bold text-text-primary tabular-nums">
                {costPerAnalysis(costs.all_time, costs.analyses_all_time)}
              </p>
            </div>
          </div>
        </div>
      </CardContent>
    </Card>
  )
}

interface CostPeriodCardProps {
  icon: React.ReactNode
  period: string
  cost: number
  analysisCount: number
  avgCost: string
  color: string
}

function CostPeriodCard({
  icon,
  period,
  cost,
  analysisCount,
  avgCost,
  color,
}: CostPeriodCardProps) {
  const formatCost = (amount: number) => {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: 'USD',
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    }).format(amount)
  }

  return (
    <div className="p-4 rounded-lg border border-surface-elevated bg-surface hover:bg-surface-elevated transition-colors">
      <div className="flex items-center gap-2 mb-3">
        <div className={color}>{icon}</div>
        <p className="text-sm font-medium text-text-secondary">{period}</p>
      </div>

      <div className="space-y-2">
        <div>
          <p className="text-2xl font-bold text-text-primary">
            {formatCost(cost)}
          </p>
          <p className="text-xs text-text-tertiary">
            {analysisCount} {analysisCount === 1 ? 'analysis' : 'analyses'}
          </p>
        </div>

        <div className="pt-2 border-t border-surface-elevated">
          <p className="text-xs text-text-secondary">Avg per analysis</p>
          <p className="text-sm font-semibold text-text-primary">{avgCost}</p>
        </div>
      </div>
    </div>
  )
}
