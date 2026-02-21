'use client'

import {
  AreaChart,
  Area,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from 'recharts'
import { Skeleton } from '@/components/ui/skeleton'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { TrendingUp, TrendingDown, DollarSign, BarChart2, Percent, Users } from 'lucide-react'
import { useAdminRevenue } from '@/lib/hooks/useAdmin'
import type { RevenueTimeSeries } from '@/types/api'

// ─── Shared theme constants ────────────────────────────────────────────────────
const COLORS = {
  revenue:  '#6366F1',   // indigo
  cost:     '#EF4444',   // red
  profit:   '#10B981',   // emerald
  analyses: '#F59E0B',   // amber
  grid:     '#252B3D',
  text:     '#9CA3AF',
  bg:       '#1A1F2E',
}

const MONTH_LABELS: Record<string, string> = {
  '01': 'Jan', '02': 'Feb', '03': 'Mar', '04': 'Apr',
  '05': 'May', '06': 'Jun', '07': 'Jul', '08': 'Aug',
  '09': 'Sep', '10': 'Oct', '11': 'Nov', '12': 'Dec',
}

function formatMonth(ym: string) {
  const [, m] = ym.split('-')
  return MONTH_LABELS[m] ?? ym
}

function formatDay(dateStr: string) {
  const d = new Date(dateStr + 'T00:00:00Z')
  return `${d.getUTCMonth() + 1}/${d.getUTCDate()}`
}

function fmt(n: number) {
  return n.toLocaleString('en-US', { style: 'currency', currency: 'USD', minimumFractionDigits: 2 })
}

// ─── Tooltip ──────────────────────────────────────────────────────────────────
function ChartTooltip({ active, payload, label, labelFormatter }: any) {
  if (!active || !payload?.length) return null
  return (
    <div className="rounded-lg border border-surface-elevated bg-surface px-3 py-2 text-xs shadow-lg">
      <p className="font-semibold text-text-primary mb-1">{labelFormatter ? labelFormatter(label) : label}</p>
      {payload.map((p: any) => (
        <div key={p.dataKey} className="flex items-center gap-2 leading-5">
          <span className="inline-block h-2 w-2 rounded-full" style={{ background: p.color }} />
          <span className="text-text-secondary">{p.name}:</span>
          <span className="font-medium text-text-primary">
            {p.dataKey === 'analyses'
              ? p.value.toLocaleString()
              : fmt(p.value)}
          </span>
        </div>
      ))}
    </div>
  )
}

// ─── KPI card ─────────────────────────────────────────────────────────────────
interface KpiCardProps {
  icon: React.ReactNode
  label: string
  value: string
  sub?: string
  positive?: boolean
}

function KpiCard({ icon, label, value, sub, positive }: KpiCardProps) {
  return (
    <Card>
      <CardContent className="pt-5">
        <div className="flex items-start justify-between">
          <div className="space-y-1">
            <p className="text-sm text-text-secondary">{label}</p>
            <p className="text-2xl font-bold text-text-primary">{value}</p>
            {sub && (
              <p className={`text-xs ${positive === undefined ? 'text-text-secondary' : positive ? 'text-success' : 'text-error'}`}>
                {sub}
              </p>
            )}
          </div>
          <div className="rounded-lg bg-surface-elevated p-2 text-text-secondary">
            {icon}
          </div>
        </div>
      </CardContent>
    </Card>
  )
}

// ─── Main component ────────────────────────────────────────────────────────────
export function AdminRevenueCharts() {
  const { data, isLoading } = useAdminRevenue()

  if (isLoading) {
    return (
      <div className="space-y-6">
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {[1, 2, 3, 4].map((i) => <Skeleton key={i} className="h-28" />)}
        </div>
        <Skeleton className="h-72" />
        <Skeleton className="h-72" />
      </div>
    )
  }

  if (!data) return null

  return <RevenueContent data={data} />
}

function RevenueContent({ data }: { data: RevenueTimeSeries }) {
  const {
    daily,
    monthly,
    estimated_mrr,
    current_month_cost,
    current_month_profit,
    profit_margin_pct,
    tier_breakdown,
  } = data

  // Derive monthly profit series for bar chart
  const monthlyWithProfit = monthly.map((m) => ({
    ...m,
    profit: Math.max(0, m.estimated_revenue - m.cost_usd),
    label: formatMonth(m.month),
  }))

  const dailyLabelled = daily.map((d) => ({ ...d, label: formatDay(d.date) }))

  const tierInfo = [
    { key: 'trader',   label: 'Trader',   color: '#6366F1' },
    { key: 'investor', label: 'Investor', color: '#8B5CF6' },
    { key: 'starter',  label: 'Starter',  color: '#A78BFA' },
  ]

  return (
    <div className="space-y-6">

      {/* ── KPI row ── */}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <KpiCard
          icon={<DollarSign className="h-5 w-5" />}
          label="Estimated MRR"
          value={fmt(estimated_mrr)}
          sub="Active subscribers × tier price"
        />
        <KpiCard
          icon={<BarChart2 className="h-5 w-5" />}
          label="AI Costs (this month)"
          value={fmt(current_month_cost)}
          sub="Sum of analysis costs"
        />
        <KpiCard
          icon={current_month_profit >= 0 ? <TrendingUp className="h-5 w-5" /> : <TrendingDown className="h-5 w-5" />}
          label="Gross Profit (this month)"
          value={fmt(current_month_profit)}
          sub="MRR − AI costs"
          positive={current_month_profit >= 0}
        />
        <KpiCard
          icon={<Percent className="h-5 w-5" />}
          label="Profit Margin"
          value={`${profit_margin_pct}%`}
          sub={estimated_mrr > 0 ? 'Gross margin on MRR' : 'No subscribers yet'}
          positive={profit_margin_pct >= 0}
        />
      </div>

      {/* ── Daily cost chart ── */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base font-semibold text-text-primary">
            Daily AI Costs — Last 30 Days
          </CardTitle>
        </CardHeader>
        <CardContent>
          <ResponsiveContainer width="100%" height={260}>
            <AreaChart data={dailyLabelled} margin={{ top: 4, right: 8, left: 0, bottom: 0 }}>
              <defs>
                <linearGradient id="costGrad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%"  stopColor={COLORS.cost} stopOpacity={0.3} />
                  <stop offset="95%" stopColor={COLORS.cost} stopOpacity={0} />
                </linearGradient>
                <linearGradient id="analysesGrad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%"  stopColor={COLORS.analyses} stopOpacity={0.3} />
                  <stop offset="95%" stopColor={COLORS.analyses} stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke={COLORS.grid} vertical={false} />
              <XAxis
                dataKey="label"
                tick={{ fontSize: 11, fill: COLORS.text }}
                axisLine={false}
                tickLine={false}
                interval={4}
              />
              <YAxis
                yAxisId="cost"
                tick={{ fontSize: 11, fill: COLORS.text }}
                axisLine={false}
                tickLine={false}
                tickFormatter={(v) => `$${v.toFixed(2)}`}
                width={54}
              />
              <YAxis
                yAxisId="analyses"
                orientation="right"
                tick={{ fontSize: 11, fill: COLORS.text }}
                axisLine={false}
                tickLine={false}
                allowDecimals={false}
                width={32}
              />
              <Tooltip
                content={<ChartTooltip labelFormatter={(l: string) => l} />}
                cursor={{ stroke: COLORS.grid, strokeWidth: 1 }}
              />
              <Legend
                wrapperStyle={{ fontSize: 12, color: COLORS.text, paddingTop: 8 }}
              />
              <Area
                yAxisId="cost"
                type="monotone"
                dataKey="cost_usd"
                name="AI Cost ($)"
                stroke={COLORS.cost}
                fill="url(#costGrad)"
                strokeWidth={2}
                dot={false}
                activeDot={{ r: 4, strokeWidth: 0 }}
              />
              <Area
                yAxisId="analyses"
                type="monotone"
                dataKey="analyses"
                name="Analyses"
                stroke={COLORS.analyses}
                fill="url(#analysesGrad)"
                strokeWidth={2}
                dot={false}
                activeDot={{ r: 4, strokeWidth: 0 }}
              />
            </AreaChart>
          </ResponsiveContainer>
        </CardContent>
      </Card>

      {/* ── Monthly revenue vs cost bar chart ── */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base font-semibold text-text-primary">
            Monthly Revenue vs AI Costs — Last 12 Months
          </CardTitle>
        </CardHeader>
        <CardContent>
          <ResponsiveContainer width="100%" height={260}>
            <BarChart data={monthlyWithProfit} margin={{ top: 4, right: 8, left: 0, bottom: 0 }} barGap={4}>
              <CartesianGrid strokeDasharray="3 3" stroke={COLORS.grid} vertical={false} />
              <XAxis
                dataKey="label"
                tick={{ fontSize: 11, fill: COLORS.text }}
                axisLine={false}
                tickLine={false}
              />
              <YAxis
                tick={{ fontSize: 11, fill: COLORS.text }}
                axisLine={false}
                tickLine={false}
                tickFormatter={(v) => `$${v}`}
                width={54}
              />
              <Tooltip
                content={<ChartTooltip labelFormatter={(l: string) => l} />}
                cursor={{ fill: COLORS.grid, opacity: 0.4 }}
              />
              <Legend wrapperStyle={{ fontSize: 12, color: COLORS.text, paddingTop: 8 }} />
              <Bar dataKey="estimated_revenue" name="Est. Revenue" fill={COLORS.revenue} radius={[4, 4, 0, 0]} maxBarSize={28} />
              <Bar dataKey="cost_usd"          name="AI Costs"    fill={COLORS.cost}    radius={[4, 4, 0, 0]} maxBarSize={28} />
              <Bar dataKey="profit"            name="Gross Profit" fill={COLORS.profit} radius={[4, 4, 0, 0]} maxBarSize={28} />
            </BarChart>
          </ResponsiveContainer>
        </CardContent>
      </Card>

      {/* ── Tier revenue breakdown ── */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base font-semibold text-text-primary flex items-center gap-2">
            <Users className="h-4 w-4" />
            Revenue by Subscription Tier
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="space-y-4">
            {tierInfo.map(({ key, label, color }) => {
              const tb = tier_breakdown[key] ?? { users: 0, monthly_revenue: 0 }
              const pct = estimated_mrr > 0
                ? Math.round((tb.monthly_revenue / estimated_mrr) * 100)
                : 0
              return (
                <div key={key} className="space-y-1">
                  <div className="flex items-center justify-between text-sm">
                    <span className="font-medium text-text-primary">{label}</span>
                    <span className="text-text-secondary">
                      {tb.users} {tb.users === 1 ? 'user' : 'users'} · {fmt(tb.monthly_revenue)}/mo
                    </span>
                  </div>
                  <div className="h-2 rounded-full bg-surface-elevated overflow-hidden">
                    <div
                      className="h-full rounded-full transition-all"
                      style={{ width: `${pct}%`, background: color }}
                    />
                  </div>
                  <p className="text-xs text-text-secondary text-right">{pct}% of MRR</p>
                </div>
              )
            })}
          </div>
        </CardContent>
      </Card>

    </div>
  )
}
