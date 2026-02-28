'use client'

import React, { useMemo } from 'react'
import type { OpportunityDistributionResponse, PercentileCutlines } from '@/types/api'
import { useOpportunityDistribution } from '@/lib/hooks/useOpportunityDistribution'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { BarChart2, AlertCircle, AlertTriangle } from 'lucide-react'
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ReferenceLine,
  ResponsiveContainer,
  Cell,
} from 'recharts'

// ── Colour palette ──────────────────────────────────────────────────────────

const C = {
  edge:      '#818CF8',  // violet — raw upside edge
  stop:      '#F87171',  // red    — stop probability
  riskAdj:   '#34D399',  // emerald — risk-adjusted edge
  p50:       '#94A3B8',  // slate
  p60:       '#F59E0B',  // amber  — gating threshold
  p75:       '#F97316',  // orange
  p90:       '#EF4444',  // red
  gridLine:  '#1E293B',
  axisText:  '#6B7280',
}

// ── Histogram binning ───────────────────────────────────────────────────────

interface Bin { label: string; count: number; midpoint: number }

function buildBins(values: (number | null)[], numBins = 20): Bin[] {
  const valid = values.filter((v): v is number => v !== null && isFinite(v))
  if (valid.length === 0) return []
  const min = Math.min(...valid)
  const max = Math.max(...valid)
  if (min === max) {
    return [{ label: min.toFixed(1), count: valid.length, midpoint: min }]
  }
  const step = (max - min) / numBins
  const bins: Bin[] = Array.from({ length: numBins }, (_, i) => ({
    label: (min + (i + 0.5) * step).toFixed(1),
    count: 0,
    midpoint: min + (i + 0.5) * step,
  }))
  for (const v of valid) {
    const idx = Math.min(Math.floor((v - min) / step), numBins - 1)
    bins[idx].count++
  }
  return bins
}

// ── Custom histogram tooltip ────────────────────────────────────────────────

function HistTooltip({ active, payload, label, unit }: any) {
  if (!active || !payload?.length) return null
  return (
    <div className="rounded-lg border border-surface-elevated bg-surface px-3 py-2 text-xs shadow-lg">
      <p className="text-text-secondary mb-0.5">
        Around <span className="font-mono text-text-primary font-semibold">{label}{unit}</span>
      </p>
      <p className="font-mono text-text-primary">
        {payload[0].value} ticker{payload[0].value !== 1 ? 's' : ''}
      </p>
    </div>
  )
}

// ── Percentile legend ───────────────────────────────────────────────────────

function PctLegend({ cutlines, unit }: { cutlines: PercentileCutlines; unit: string }) {
  const items = [
    { label: 'p50', value: cutlines.p50, color: C.p50 },
    { label: 'p60', value: cutlines.p60, color: C.p60 },
    { label: 'p75', value: cutlines.p75, color: C.p75 },
    { label: 'p90', value: cutlines.p90, color: C.p90 },
  ]
  return (
    <div className="flex flex-wrap gap-x-4 gap-y-1 mt-1.5">
      {items.map(({ label, value, color }) => (
        <span key={label} className="flex items-center gap-1.5 text-xs text-text-secondary font-mono">
          <span
            className="inline-block h-2.5 w-0.5 rounded-full"
            style={{ backgroundColor: color }}
          />
          {label} = {value !== null ? `${value.toFixed(1)}${unit}` : '—'}
        </span>
      ))}
    </div>
  )
}

// ── Single histogram chart ──────────────────────────────────────────────────

function DistributionChart({
  title,
  values,
  cutlines,
  barColor,
  unit,
}: {
  title: string
  values: (number | null)[]
  cutlines: PercentileCutlines
  barColor: string
  unit: string
}) {
  const bins = useMemo(() => buildBins(values), [values])
  const maxCount = Math.max(...bins.map(b => b.count), 1)

  return (
    <div>
      <p className="text-xs font-medium text-text-primary mb-1">{title}</p>
      <PctLegend cutlines={cutlines} unit={unit} />
      <div className="mt-3">
        <ResponsiveContainer width="100%" height={160}>
          <BarChart data={bins} margin={{ top: 4, right: 4, left: -20, bottom: 0 }}>
            <CartesianGrid vertical={false} stroke={C.gridLine} strokeOpacity={0.6} />
            <XAxis
              dataKey="label"
              tick={{ fontSize: 10, fill: C.axisText }}
              tickLine={false}
              axisLine={false}
              interval="preserveStartEnd"
              tickFormatter={v => `${parseFloat(v).toFixed(0)}${unit}`}
            />
            <YAxis
              allowDecimals={false}
              tick={{ fontSize: 10, fill: C.axisText }}
              tickLine={false}
              axisLine={false}
              domain={[0, maxCount]}
            />
            <Tooltip content={<HistTooltip unit={unit} />} cursor={{ fill: 'rgba(255,255,255,0.04)' }} />

            {/* Percentile reference lines */}
            {cutlines.p50 !== null && (
              <ReferenceLine
                x={cutlines.p50.toFixed(1)}
                stroke={C.p50}
                strokeWidth={1.5}
                strokeDasharray="4 3"
                label={{ value: 'p50', position: 'insideTopLeft', fontSize: 9, fill: C.p50 }}
              />
            )}
            {cutlines.p60 !== null && (
              <ReferenceLine
                x={cutlines.p60.toFixed(1)}
                stroke={C.p60}
                strokeWidth={2}
                strokeDasharray="5 3"
                label={{ value: 'p60', position: 'insideTopLeft', fontSize: 9, fill: C.p60 }}
              />
            )}
            {cutlines.p75 !== null && (
              <ReferenceLine
                x={cutlines.p75.toFixed(1)}
                stroke={C.p75}
                strokeWidth={1.5}
                strokeDasharray="4 3"
                label={{ value: 'p75', position: 'insideTopRight', fontSize: 9, fill: C.p75 }}
              />
            )}
            {cutlines.p90 !== null && (
              <ReferenceLine
                x={cutlines.p90.toFixed(1)}
                stroke={C.p90}
                strokeWidth={1.5}
                strokeDasharray="4 3"
                label={{ value: 'p90', position: 'insideTopRight', fontSize: 9, fill: C.p90 }}
              />
            )}

            <Bar dataKey="count" radius={[2, 2, 0, 0]} maxBarSize={40}>
              {bins.map((_, i) => (
                <Cell key={i} fill={barColor} fillOpacity={0.75} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  )
}

// ── Summary stats box ───────────────────────────────────────────────────────

function SummaryBox({ data }: { data: OpportunityDistributionResponse }) {
  const s = data.summary
  const fmt = (v: number | null, suffix = '%') =>
    v !== null ? `${v.toFixed(1)}${suffix}` : '—'

  return (
    <div className="rounded-lg border border-surface-elevated bg-surface p-4 space-y-3">
      <p className="text-xs font-semibold text-text-secondary uppercase tracking-wide">
        Snapshot Stats
      </p>
      <div className="grid grid-cols-2 gap-x-6 gap-y-2 text-xs">
        <div className="flex justify-between gap-2">
          <span className="text-text-secondary">N Evaluated</span>
          <span className="font-mono text-text-primary">{s.n_evaluated}</span>
        </div>
        <div className="flex justify-between gap-2">
          <span className="text-text-secondary">N Valid Ranked</span>
          <span className="font-mono text-text-primary">{s.n_valid_ranked}</span>
        </div>
        <div className="flex justify-between gap-2">
          <span className="text-text-secondary">Min RA Edge</span>
          <span className="font-mono text-text-primary">{fmt(s.min_risk_adj_edge)}</span>
        </div>
        <div className="flex justify-between gap-2">
          <span className="text-text-secondary">Max RA Edge</span>
          <span className="font-mono text-text-primary">{fmt(s.max_risk_adj_edge)}</span>
        </div>
        <div className="flex justify-between gap-2">
          <span className="text-text-secondary">Mean RA Edge</span>
          <span className="font-mono text-text-primary">{fmt(s.mean_risk_adj_edge)}</span>
        </div>
        <div className="flex justify-between gap-2">
          <span className="text-text-secondary">Median RA Edge</span>
          <span className="font-mono text-text-primary">{fmt(s.median_risk_adj_edge)}</span>
        </div>
        <div className="flex justify-between gap-2">
          <span className="text-text-secondary">% Positive Edge</span>
          <span className="font-mono text-text-primary">{fmt(s.pct_positive_edge)}</span>
        </div>
        <div className="flex justify-between gap-2">
          <span className="text-text-secondary">% Positive RA</span>
          <span className="font-mono text-text-primary">{fmt(s.pct_positive_risk_adj)}</span>
        </div>
      </div>
    </div>
  )
}

// ── Tier table ───────────────────────────────────────────────────────────────

function TierTable({ data }: { data: OpportunityDistributionResponse }) {
  const rows = data.tier_tickers
  if (rows.length === 0) {
    return (
      <p className="text-xs text-text-secondary text-center py-3">
        No Tier 1 or Tier 2 tickers in current snapshot.
      </p>
    )
  }

  const fmt = (v: number | null, dec = 1, suffix = '%') =>
    v !== null ? `${v.toFixed(dec)}${suffix}` : '—'

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-xs">
        <thead>
          <tr className="border-b border-surface-elevated text-text-secondary uppercase tracking-wide">
            <th className="text-left py-2 pr-3 font-medium">Ticker</th>
            <th className="text-center py-2 px-2 font-medium">Tier</th>
            <th className="text-right py-2 px-2 font-medium">Edge</th>
            <th className="text-right py-2 px-2 font-medium">Stop</th>
            <th className="text-right py-2 px-2 font-medium">RA Edge</th>
            <th className="text-right py-2 pl-2 font-medium">Percentile</th>
          </tr>
        </thead>
        <tbody>
          {rows.map(row => {
            const isT1 = row.tier === 1
            return (
              <tr
                key={row.ticker}
                className={`border-b border-surface-elevated/30 ${
                  isT1 ? 'bg-emerald-500/5' : ''
                }`}
              >
                <td className="py-2 pr-3 font-mono font-semibold text-text-primary">
                  {row.ticker}
                </td>
                <td className="text-center py-2 px-2">
                  <span
                    className={`inline-flex items-center rounded-full border px-2 py-0.5 text-xs font-semibold ${
                      isT1
                        ? 'bg-emerald-500/15 text-emerald-300 border-emerald-500/30'
                        : 'bg-violet-500/15 text-violet-300 border-violet-500/30'
                    }`}
                  >
                    T{row.tier}
                  </span>
                </td>
                <td className={`text-right py-2 px-2 font-mono ${
                  row.edge_pct !== null && row.edge_pct > 0 ? 'text-emerald-400' : 'text-red-400'
                }`}>
                  {fmt(row.edge_pct)}
                </td>
                <td className={`text-right py-2 px-2 font-mono ${
                  row.stop_prob_pct <= 25 ? 'text-text-secondary' : 'text-amber-400'
                }`}>
                  {fmt(row.stop_prob_pct)}
                </td>
                <td className={`text-right py-2 px-2 font-mono ${
                  row.risk_adj_edge_pct !== null && row.risk_adj_edge_pct > 0
                    ? 'text-emerald-400'
                    : 'text-red-400'
                }`}>
                  {fmt(row.risk_adj_edge_pct)}
                </td>
                <td className="text-right py-2 pl-2 font-mono text-text-primary">
                  {fmt(row.risk_adj_edge_percentile, 1, 'th')}
                </td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}

// ── Warning chips ────────────────────────────────────────────────────────────

function WarningChips({ warnings }: { warnings: OpportunityDistributionResponse['warnings'] }) {
  if (warnings.length === 0) return null
  return (
    <div className="flex flex-wrap gap-2">
      {warnings.map(w => (
        <div
          key={w.code}
          className="flex items-center gap-1.5 rounded-full border border-amber-500/30 bg-amber-500/10 px-3 py-1 text-xs text-amber-300"
        >
          <AlertTriangle className="h-3 w-3 shrink-0" />
          {w.message}
        </div>
      ))}
    </div>
  )
}

// ── Main panel ───────────────────────────────────────────────────────────────

export function OpportunityDistributionPanel() {
  const { data, isLoading, error, run } = useOpportunityDistribution()

  return (
    <Card className="mt-6 border-dashed border-violet-500/20 bg-violet-500/5">
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between gap-3">
          <div className="flex items-center gap-2">
            <BarChart2 className="h-4 w-4 text-violet-400 shrink-0" />
            <CardTitle className="text-base text-text-primary">
              Opportunity Distribution (Current Snapshot)
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
            {isLoading ? 'Loading…' : data ? 'Refresh' : 'Load Distribution'}
          </Button>
        </div>
        <p className="text-xs text-text-secondary mt-1.5 leading-relaxed">
          Raw edge and risk-adjusted score distributions across the evaluated universe.
          Percentile cutlines show where the 60th-percentile gate (p60) and other thresholds sit.
          Tier 1 = allocation-eligible; Tier 2 = confirms structurally, fails one eligibility rule.
        </p>
      </CardHeader>

      <CardContent className="space-y-6">
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
            <span className="text-violet-300 font-medium">Load Distribution</span>{' '}
            to visualise the current snapshot&apos;s opportunity set.
          </p>
        )}

        {/* Skeleton */}
        {isLoading && (
          <div className="space-y-6 animate-pulse">
            <div className="h-4 w-40 rounded bg-surface-elevated" />
            <div className="h-44 rounded bg-surface-elevated" />
            <div className="h-44 rounded bg-surface-elevated" />
            <div className="h-44 rounded bg-surface-elevated" />
          </div>
        )}

        {/* Results */}
        {data && !isLoading && (
          <>
            {/* Warning chips */}
            <WarningChips warnings={data.warnings} />

            {/* Stats + histograms layout */}
            <div className="grid grid-cols-1 xl:grid-cols-[1fr_220px] gap-6">
              {/* Left: 3 histograms */}
              <div className="space-y-8">
                <DistributionChart
                  title="Raw Upside Edge Distribution  (edge_pct = (EV / price − 1) × 100)"
                  values={data.edge_pct}
                  cutlines={data.edge_pct_cutlines}
                  barColor={C.edge}
                  unit="%"
                />
                <DistributionChart
                  title="Stop Probability Distribution  (0 – 100, lower is better)"
                  values={data.stop_prob_pct}
                  cutlines={data.stop_prob_cutlines}
                  barColor={C.stop}
                  unit="%"
                />
                <DistributionChart
                  title="Risk-Adjusted Edge Distribution  (edge × (1 − stop/100))  ← percentile-ranked for gating"
                  values={data.risk_adj_edge_pct}
                  cutlines={data.risk_adj_edge_cutlines}
                  barColor={C.riskAdj}
                  unit="%"
                />
              </div>

              {/* Right: summary stats */}
              <div>
                <SummaryBox data={data} />
              </div>
            </div>

            {/* Tier table */}
            <div>
              <p className="text-xs text-text-secondary uppercase tracking-wide mb-2">
                Tier 1 + Tier 2 Tickers (confirmed universe)
              </p>
              <TierTable data={data} />
            </div>

            <p className="text-xs text-zinc-600 text-right">
              Snapshot {data.snapshot_id.slice(0, 8)}… ·{' '}
              {new Date(data.generated_at).toLocaleTimeString()} · no writes
            </p>
          </>
        )}
      </CardContent>
    </Card>
  )
}
