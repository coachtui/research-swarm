'use client'

import React from 'react'
import type { EligibilityStressTestResponse, StressScenarioResult } from '@/types/api'
import { useEligibilityStressTest } from '@/lib/hooks/useEligibilityStressTest'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { FlaskConical, AlertCircle, TrendingUp, Minus, TrendingDown } from 'lucide-react'

// ── Constraint badge ───────────────────────────────────────────────────────────

function ConstraintBadge({ label }: { label: string }) {
  const colorMap: Record<string, string> = {
    'Delta':             'bg-violet-500/15 text-violet-300 border-violet-500/30',
    'EV Percentile':     'bg-amber-500/15  text-amber-300  border-amber-500/30',
    'Stop Probability':  'bg-red-500/15    text-red-300    border-red-500/30',
    'Regime Stability':  'bg-zinc-500/15   text-zinc-300   border-zinc-500/30',
  }
  const cls = colorMap[label] ?? 'bg-zinc-500/15 text-zinc-300 border-zinc-500/30'
  return (
    <span className={`inline-flex items-center rounded-full border px-3 py-1 text-xs font-semibold ${cls}`}>
      {label}
    </span>
  )
}

// ── Change badge ───────────────────────────────────────────────────────────────

function ChangeBadge({ delta, isTop }: { delta: number; isTop: boolean }) {
  if (delta === 0) {
    return (
      <span className="flex items-center gap-1 text-xs text-zinc-400 font-mono">
        <Minus className="h-3 w-3" /> 0
      </span>
    )
  }
  if (delta > 0) {
    const cls = isTop
      ? 'text-emerald-300 font-bold'
      : 'text-emerald-400'
    return (
      <span className={`flex items-center gap-1 text-xs font-mono ${cls}`}>
        <TrendingUp className="h-3 w-3" />+{delta}
      </span>
    )
  }
  return (
    <span className="flex items-center gap-1 text-xs text-red-400 font-mono">
      <TrendingDown className="h-3 w-3" />{delta}
    </span>
  )
}

// ── Shortfall tile ─────────────────────────────────────────────────────────────

function ShortfallTile({
  label,
  value,
  unit,
  positive_is_bad,
}: {
  label: string
  value: number | null
  unit: string
  positive_is_bad: boolean
}) {
  if (value === null) {
    return (
      <div className="rounded-lg border border-surface-elevated bg-surface p-3">
        <p className="text-xs text-text-secondary mb-1">{label}</p>
        <p className="text-sm font-mono text-zinc-500">—</p>
        <p className="text-xs text-text-secondary mt-0.5">No failing tickers</p>
      </div>
    )
  }
  const isGood = positive_is_bad ? value <= 0 : value >= 0
  const color = isGood ? 'text-zinc-400' : 'text-amber-400'
  const sign = value > 0 ? '+' : ''
  return (
    <div className="rounded-lg border border-surface-elevated bg-surface p-3">
      <p className="text-xs text-text-secondary mb-1">{label}</p>
      <p className={`text-base font-mono font-semibold ${color}`}>
        {sign}{value.toFixed(1)}{unit}
      </p>
      <p className="text-xs text-text-secondary mt-0.5">avg shortfall (failing tickers)</p>
    </div>
  )
}

// ── Scenario table ─────────────────────────────────────────────────────────────

function ScenarioTable({
  baseline,
  scenarios,
}: {
  baseline: { eligible: number; pass_rate_structural: number }
  scenarios: StressScenarioResult[]
}) {
  const maxChange = Math.max(...scenarios.map(s => s.change_vs_baseline))
  const topIdx = scenarios.findIndex(s => s.change_vs_baseline === maxChange && maxChange > 0)

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-surface-elevated text-text-secondary text-xs uppercase tracking-wide">
            <th className="text-left py-2 pr-4 font-medium">Scenario</th>
            <th className="text-right py-2 px-3 font-medium">Eligible</th>
            <th className="text-right py-2 px-3 font-medium">% Structural</th>
            <th className="text-right py-2 pl-3 font-medium">Δ vs Baseline</th>
          </tr>
        </thead>
        <tbody>
          {/* Baseline row */}
          <tr className="border-b border-surface-elevated/50 bg-surface/40">
            <td className="py-2.5 pr-4 text-text-secondary font-medium">
              Baseline (Production)
            </td>
            <td className="text-right py-2.5 px-3 font-mono text-text-primary font-semibold">
              {baseline.eligible}
            </td>
            <td className="text-right py-2.5 px-3 font-mono text-text-secondary">
              {baseline.pass_rate_structural.toFixed(1)}%
            </td>
            <td className="text-right py-2.5 pl-3 text-zinc-500 text-xs">—</td>
          </tr>

          {/* Scenario rows */}
          {scenarios.map((s, i) => {
            const isTop = i === topIdx
            return (
              <tr
                key={s.name}
                className={`border-b border-surface-elevated/30 transition-colors ${
                  isTop
                    ? 'bg-emerald-500/5 border-emerald-500/20'
                    : 'hover:bg-surface/50'
                }`}
              >
                <td className="py-2.5 pr-4 text-text-primary">
                  <span className={isTop ? 'font-semibold' : ''}>{s.name}</span>
                  {isTop && (
                    <span className="ml-2 text-xs text-emerald-400 font-medium">
                      highest elasticity
                    </span>
                  )}
                </td>
                <td className="text-right py-2.5 px-3 font-mono text-text-primary">
                  {s.eligible}
                </td>
                <td className="text-right py-2.5 px-3 font-mono text-text-secondary">
                  {s.pass_rate_structural.toFixed(1)}%
                </td>
                <td className="text-right py-2.5 pl-3">
                  <ChangeBadge delta={s.change_vs_baseline} isTop={isTop} />
                </td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}

// ── Main component ─────────────────────────────────────────────────────────────

export function EligibilityStressTestPanel() {
  const { data, isLoading, error, run } = useEligibilityStressTest()

  return (
    <Card className="mt-6 border-dashed border-amber-500/20 bg-amber-500/5">
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between gap-3">
          <div className="flex items-center gap-2">
            <FlaskConical className="h-4 w-4 text-amber-400 shrink-0" />
            <CardTitle className="text-base text-text-primary">
              Eligibility Stress-Test Simulation
            </CardTitle>
            <span className="rounded-full bg-amber-500/15 border border-amber-500/30 px-2 py-0.5 text-xs text-amber-300 font-medium">
              Admin Only
            </span>
          </div>
          <Button
            variant="outline"
            size="sm"
            onClick={run}
            disabled={isLoading}
            className="text-xs border-amber-500/30 text-amber-300 hover:bg-amber-500/10"
          >
            {isLoading ? 'Running…' : data ? 'Re-run' : 'Run Simulation'}
          </Button>
        </div>
        <p className="text-xs text-text-secondary mt-1.5 leading-relaxed">
          Read-only threshold elasticity test. Identifies which eligibility rule is the
          dominant binding constraint and how eligible count changes under relaxed thresholds.
          No production logic is modified.
        </p>
      </CardHeader>

      <CardContent className="space-y-5">
        {/* Error state */}
        {error && !isLoading && (
          <div className="flex items-center gap-2 rounded-lg border border-red-500/30 bg-red-500/10 p-3 text-sm text-red-300">
            <AlertCircle className="h-4 w-4 shrink-0" />
            {error.message}
          </div>
        )}

        {/* Empty prompt */}
        {!data && !isLoading && !error && (
          <p className="text-sm text-text-secondary text-center py-4">
            Click <span className="text-amber-300 font-medium">Run Simulation</span> to evaluate
            threshold elasticity against the current admin snapshot.
          </p>
        )}

        {/* Loading state */}
        {isLoading && (
          <div className="space-y-3 animate-pulse">
            <div className="h-5 w-48 rounded bg-surface-elevated" />
            <div className="h-32 rounded bg-surface-elevated" />
            <div className="h-48 rounded bg-surface-elevated" />
          </div>
        )}

        {/* Results */}
        {data && !isLoading && (
          <>
            {/* Universe summary */}
            <div className="grid grid-cols-3 gap-3 text-center">
              <div className="rounded-lg border border-surface-elevated bg-surface p-3">
                <p className="text-xs text-text-secondary mb-1">Evaluated Universe</p>
                <p className="text-xl font-bold font-mono text-text-primary">
                  {data.evaluated_universe}
                </p>
              </div>
              <div className="rounded-lg border border-surface-elevated bg-surface p-3">
                <p className="text-xs text-text-secondary mb-1">Structurally Confirmed</p>
                <p className="text-xl font-bold font-mono text-text-primary">
                  {data.structural_confirmed}
                </p>
              </div>
              <div className="rounded-lg border border-surface-elevated bg-surface p-3">
                <p className="text-xs text-text-secondary mb-1">Baseline Eligible</p>
                <p className="text-xl font-bold font-mono text-text-primary">
                  {data.baseline.eligible}
                </p>
                <p className="text-xs text-text-secondary">
                  {data.baseline.pass_rate_structural.toFixed(1)}% of confirmed
                </p>
              </div>
            </div>

            {/* Dominant constraint */}
            <div className="flex items-center gap-3 rounded-lg border border-surface-elevated bg-surface p-3">
              <span className="text-xs text-text-secondary shrink-0">
                Dominant Binding Constraint
              </span>
              <ConstraintBadge label={data.dominant_binding_constraint} />
            </div>

            {/* Avg shortfall diagnostics */}
            <div>
              <p className="text-xs text-text-secondary uppercase tracking-wide mb-2">
                Avg Distance to Threshold (Failing Tickers)
              </p>
              <div className="grid grid-cols-3 gap-3">
                <ShortfallTile
                  label="Conviction Delta"
                  value={data.avg_distance_to_threshold.delta}
                  unit="%"
                  positive_is_bad={false}
                />
                <ShortfallTile
                  label="EV Percentile Gap"
                  value={data.avg_distance_to_threshold.ev_percentile}
                  unit=" pct"
                  positive_is_bad={false}
                />
                <ShortfallTile
                  label="Stop Excess"
                  value={data.avg_distance_to_threshold.stop}
                  unit="%"
                  positive_is_bad={true}
                />
              </div>
            </div>

            {/* Scenario comparison table */}
            <div>
              <p className="text-xs text-text-secondary uppercase tracking-wide mb-2">
                Scenario Comparison
              </p>
              <ScenarioTable baseline={data.baseline} scenarios={data.scenarios} />
            </div>

            <p className="text-xs text-zinc-600 text-right">
              Simulated at {new Date(data.generated_at).toLocaleTimeString()} ·
              snapshot bucket data · no writes
            </p>
          </>
        )}
      </CardContent>
    </Card>
  )
}
