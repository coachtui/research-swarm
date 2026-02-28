'use client'

import React from 'react'
import type { EligibilityRollingSimResponse, WeeklySimPoint } from '@/types/api'
import { useEligibilityRollingSim } from '@/lib/hooks/useEligibilityRollingSim'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { TrendingUp, AlertCircle, CalendarRange } from 'lucide-react'
import {
  ComposedChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from 'recharts'

// ── Colour palette ──────────────────────────────────────────────────────────────
const COLORS = {
  tier1:    '#10B981',  // emerald
  tier2:    '#818CF8',  // violet
  di:       '#F59E0B',  // amber
  grid:     '#252B3D',
  text:     '#9CA3AF',
}

// ── X-axis label formatter: "Mar 3" ────────────────────────────────────────────
function formatWeek(dateStr: string) {
  const d = new Date(dateStr + 'T00:00:00Z')
  return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', timeZone: 'UTC' })
}

// ── Custom tooltip ──────────────────────────────────────────────────────────────
function ChartTooltip({ active, payload, label }: any) {
  if (!active || !payload?.length) return null
  const week = new Date(label + 'T00:00:00Z').toLocaleDateString('en-US', {
    month: 'short', day: 'numeric', year: 'numeric', timeZone: 'UTC',
  })
  return (
    <div className="rounded-lg border border-surface-elevated bg-surface px-3 py-2 text-xs shadow-lg min-w-[170px]">
      <p className="font-semibold text-text-primary mb-1.5">Week of {week}</p>
      {payload.map((p: any) => (
        <div key={p.dataKey} className="flex items-center justify-between gap-3 leading-5">
          <span className="flex items-center gap-1.5 text-text-secondary">
            <span className="inline-block h-2 w-2 rounded-full" style={{ background: p.color }} />
            {p.name}
          </span>
          <span className="font-mono font-medium text-text-primary">
            {p.dataKey === 'deployability_index' ? `${p.value.toFixed(1)}` : p.value}
          </span>
        </div>
      ))}
    </div>
  )
}

// ── Summary stat tile ───────────────────────────────────────────────────────────
function StatTile({
  label,
  value,
  sub,
  highlight,
}: {
  label: string
  value: string
  sub?: string
  highlight?: 'good' | 'warn' | 'neutral'
}) {
  const color =
    highlight === 'good'
      ? 'text-emerald-400'
      : highlight === 'warn'
      ? 'text-amber-400'
      : 'text-text-primary'
  return (
    <div className="rounded-lg border border-surface-elevated bg-surface p-3 text-center">
      <p className="text-xs text-text-secondary mb-1">{label}</p>
      <p className={`text-xl font-bold font-mono ${color}`}>{value}</p>
      {sub && <p className="text-xs text-zinc-500 mt-0.5">{sub}</p>}
    </div>
  )
}

// ── Rolling chart ───────────────────────────────────────────────────────────────
function RollingChart({ weeks }: { weeks: WeeklySimPoint[] }) {
  // Show every ~4th week label on x-axis to avoid crowding
  const tickInterval = Math.max(1, Math.floor(weeks.length / 13))

  const maxCount = Math.max(
    ...weeks.map(w => Math.max(w.tier1_count, w.tier2_count)),
    1,
  )

  return (
    <ResponsiveContainer width="100%" height={260}>
      <ComposedChart data={weeks} margin={{ top: 4, right: 40, left: 0, bottom: 0 }}>
        <CartesianGrid strokeDasharray="3 3" stroke={COLORS.grid} />
        <XAxis
          dataKey="week"
          tickFormatter={formatWeek}
          interval={tickInterval}
          tick={{ fill: COLORS.text, fontSize: 11 }}
          axisLine={{ stroke: COLORS.grid }}
          tickLine={false}
        />
        {/* Left Y: tier counts */}
        <YAxis
          yAxisId="left"
          domain={[0, maxCount + 1]}
          allowDecimals={false}
          tick={{ fill: COLORS.text, fontSize: 11 }}
          axisLine={false}
          tickLine={false}
          width={24}
        />
        {/* Right Y: deployability index 0-100 */}
        <YAxis
          yAxisId="right"
          orientation="right"
          domain={[0, 100]}
          tick={{ fill: COLORS.text, fontSize: 11 }}
          axisLine={false}
          tickLine={false}
          width={32}
          tickFormatter={(v) => `${v}`}
        />
        <Tooltip content={<ChartTooltip />} />
        <Legend
          wrapperStyle={{ fontSize: 12, color: COLORS.text, paddingTop: 8 }}
          formatter={(value) => (
            <span style={{ color: COLORS.text }}>{value}</span>
          )}
        />
        <Line
          yAxisId="left"
          type="monotone"
          dataKey="tier1_count"
          name="Tier 1 (strict)"
          stroke={COLORS.tier1}
          strokeWidth={2}
          dot={false}
          activeDot={{ r: 4 }}
        />
        <Line
          yAxisId="left"
          type="monotone"
          dataKey="tier2_count"
          name="Tier 2 (moderate)"
          stroke={COLORS.tier2}
          strokeWidth={2}
          dot={false}
          activeDot={{ r: 4 }}
          strokeDasharray="4 2"
        />
        <Line
          yAxisId="right"
          type="monotone"
          dataKey="deployability_index"
          name="Deployability Index"
          stroke={COLORS.di}
          strokeWidth={1.5}
          dot={false}
          activeDot={{ r: 3 }}
          strokeDasharray="2 3"
          opacity={0.75}
        />
      </ComposedChart>
    </ResponsiveContainer>
  )
}

// ── Main component ──────────────────────────────────────────────────────────────

export function EligibilityRollingSimPanel() {
  const { data, isLoading, error, run } = useEligibilityRollingSim()

  return (
    <Card className="mt-6 border-dashed border-violet-500/20 bg-violet-500/5">
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between gap-3">
          <div className="flex items-center gap-2">
            <CalendarRange className="h-4 w-4 text-violet-400 shrink-0" />
            <CardTitle className="text-base text-text-primary">
              Rolling 12-Month Eligibility Simulation
            </CardTitle>
            <span className="rounded-full bg-violet-500/15 border border-violet-500/30 px-2 py-0.5 text-xs text-violet-300 font-medium">
              Admin Only
            </span>
          </div>
          <Button
            variant="outline"
            size="sm"
            onClick={run}
            disabled={isLoading}
            className="text-xs border-violet-500/30 text-violet-300 hover:bg-violet-500/10"
          >
            {isLoading ? 'Simulating…' : data ? 'Re-run' : 'Run Simulation'}
          </Button>
        </div>
        <p className="text-xs text-text-secondary mt-1.5 leading-relaxed">
          Replays eligibility tiers weekly across the trailing 52-week window using historical
          report snapshots — no recalculation, no new analyses. Values reflect EV, stop probability,
          and delta as recorded at the time of each original report.
        </p>
        {data && (
          <div className="flex gap-3 mt-2 text-xs text-zinc-500">
            <span className="flex items-center gap-1">
              <span className="inline-block h-2 w-2 rounded-full" style={{ background: COLORS.tier1 }} />
              {data.tier1_label}
            </span>
            <span className="flex items-center gap-1 mt-0.5">
              <span className="inline-block h-2 w-2 rounded-full" style={{ background: COLORS.tier2 }} />
              {data.tier2_label}
            </span>
          </div>
        )}
      </CardHeader>

      <CardContent className="space-y-5">
        {/* Error */}
        {error && !isLoading && (
          <div className="flex items-center gap-2 rounded-lg border border-red-500/30 bg-red-500/10 p-3 text-sm text-red-300">
            <AlertCircle className="h-4 w-4 shrink-0" />
            {error.message}
          </div>
        )}

        {/* Empty prompt */}
        {!data && !isLoading && !error && (
          <p className="text-sm text-text-secondary text-center py-4">
            Click{' '}
            <span className="text-violet-300 font-medium">Run Simulation</span>{' '}
            to replay eligibility tiers across the trailing 12-month history.
          </p>
        )}

        {/* Loading skeleton */}
        {isLoading && (
          <div className="space-y-3 animate-pulse">
            <div className="grid grid-cols-4 gap-3">
              {[...Array(4)].map((_, i) => (
                <div key={i} className="h-16 rounded bg-surface-elevated" />
              ))}
            </div>
            <div className="h-64 rounded bg-surface-elevated" />
          </div>
        )}

        {/* Results */}
        {data && !isLoading && (
          <>
            {/* Summary stats */}
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
              <StatTile
                label="Weeks Tier 1 ≥ 1"
                value={`${data.summary_stats.pct_weeks_tier1_gte1.toFixed(1)}%`}
                sub={`of ${data.summary_stats.weeks_with_data} data weeks`}
                highlight={data.summary_stats.pct_weeks_tier1_gte1 >= 50 ? 'good' : 'warn'}
              />
              <StatTile
                label="Weeks Tier 1 = 0"
                value={`${data.summary_stats.pct_weeks_tier1_zero.toFixed(1)}%`}
                sub="no eligible tickers"
                highlight={data.summary_stats.pct_weeks_tier1_zero > 70 ? 'warn' : 'neutral'}
              />
              <StatTile
                label="Median Tier 1"
                value={data.summary_stats.median_tier1.toFixed(1)}
                sub="eligible / week"
              />
              <StatTile
                label="Median Tier 2"
                value={data.summary_stats.median_tier2.toFixed(1)}
                sub="moderate eligible / week"
              />
            </div>

            {/* Chart */}
            {data.weeks.length > 0 && (
              <div>
                <p className="text-xs text-text-secondary uppercase tracking-wide mb-3">
                  Weekly Tier Counts &amp; Deployability Index
                </p>
                <RollingChart weeks={data.weeks} />
              </div>
            )}

            {/* No data note */}
            {data.summary_stats.weeks_with_data === 0 && (
              <p className="text-sm text-text-secondary text-center py-2">
                No historical report data found in the 12-month window. Run some analyses first.
              </p>
            )}

            <p className="text-xs text-zinc-600 text-right">
              Simulated {data.summary_stats.total_weeks} weeks
              {data.data_start && data.data_end && (
                <> · data {formatWeek(data.data_start)} – {formatWeek(data.data_end)}</>
              )}
               · no writes · generated {new Date(data.generated_at).toLocaleTimeString()}
            </p>
          </>
        )}
      </CardContent>
    </Card>
  )
}
