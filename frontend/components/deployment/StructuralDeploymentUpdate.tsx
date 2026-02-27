'use client'

import React from 'react'
import type { DeploymentUpdateResponse, MarketDeployabilitySnapshot, DeployableTickerItem, SectorBreadthRow } from '@/types/api'
import { useDeploymentUpdate } from '@/lib/hooks/useDeploymentUpdate'
import { useEntitlements } from '@/lib/hooks/useEntitlements'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Skeleton } from '@/components/ui/skeleton'
import { canAccessFeature } from '@/lib/entitlements'
import { Lock, TrendingUp, TrendingDown, Minus } from 'lucide-react'
import Link from 'next/link'

// ── Posture badge colours ──────────────────────────────────────────────────────

function PostureBadge({ posture }: { posture: string }) {
  const variants: Record<string, string> = {
    Expanding: 'bg-emerald-500/15 text-emerald-400 border-emerald-500/30',
    Moderate:  'bg-yellow-500/15  text-yellow-400  border-yellow-500/30',
    Low:       'bg-zinc-500/15    text-zinc-400    border-zinc-500/30',
  }
  return (
    <span className={`inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-medium ${variants[posture] ?? variants.Low}`}>
      {posture}
    </span>
  )
}

// ── Trend icon ─────────────────────────────────────────────────────────────────

function TrendIcon({ trend }: { trend: 'rising' | 'stable' | 'falling' }) {
  if (trend === 'rising')  return <TrendingUp  className="h-3.5 w-3.5 text-emerald-400 inline-block mr-1" />
  if (trend === 'falling') return <TrendingDown className="h-3.5 w-3.5 text-red-400    inline-block mr-1" />
  return <Minus className="h-3.5 w-3.5 text-zinc-400 inline-block mr-1" />
}

// ── Section 1: Market Deployability Snapshot ──────────────────────────────────

function DeployabilitySnapshot({ snapshot }: { snapshot: MarketDeployabilitySnapshot }) {
  const deltaStr = snapshot.avg_allocation_delta != null
    ? (snapshot.avg_allocation_delta >= 0 ? `+${snapshot.avg_allocation_delta.toFixed(2)}%` : `${snapshot.avg_allocation_delta.toFixed(2)}%`)
    : '—'

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-3">
        <h3 className="text-sm font-semibold text-text-primary uppercase tracking-wider">
          Market Deployability Snapshot
        </h3>
        <PostureBadge posture={snapshot.capital_posture} />
      </div>

      {/* 4-metric grid */}
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <MetricTile
          label="Universe Confirmed"
          value={`${snapshot.pct_universe_confirmed.toFixed(1)}%`}
          sub={`${snapshot.universe_size} tickers tracked`}
        />
        <MetricTile
          label="Avg Alloc Delta"
          value={deltaStr}
          sub="vs. prior run"
        />
        <MetricTile
          label="Avg Stop Prob"
          value={
            <span className="inline-flex items-center gap-1">
              {snapshot.avg_stop_probability.toFixed(1)}%
              <TrendIcon trend={snapshot.avg_stop_probability_trend} />
            </span>
          }
          sub="across universe"
        />
        <MetricTile
          label="Regime Stable"
          value={`${snapshot.regime_stable_pct.toFixed(1)}%`}
          sub="not noise-dominated"
        />
      </div>

      {/* Compact posture summary */}
      <p className="text-xs text-text-secondary leading-relaxed max-w-prose">
        {buildPostureSummary(snapshot)}
      </p>
    </div>
  )
}

function MetricTile({ label, value, sub }: { label: string; value: React.ReactNode; sub: string }) {
  return (
    <div className="rounded-lg border border-surface-elevated bg-surface p-3">
      <p className="text-xs text-text-secondary mb-1">{label}</p>
      <div className="text-base font-mono font-semibold text-text-primary">{value}</div>
      <p className="text-xs text-text-secondary mt-0.5">{sub}</p>
    </div>
  )
}

/** Deterministic posture summary — no LLM. ≤150 words. */
function buildPostureSummary(s: MarketDeployabilitySnapshot): string {
  const pct = s.pct_universe_confirmed.toFixed(1)
  const stop = s.avg_stop_probability.toFixed(1)
  const stable = s.regime_stable_pct.toFixed(1)
  const posture = s.capital_posture

  if (posture === 'Expanding') {
    return `${pct}% of the tracked universe meets structural confirmation criteria. ` +
      `Average stop probability is ${stop}% with ${stable}% of names operating in stable regimes. ` +
      `Capital deployment conditions are structurally expanding. ` +
      `Confirmed names appear below.`
  }
  if (posture === 'Moderate') {
    return `${pct}% of the tracked universe meets structural confirmation criteria. ` +
      `Average stop probability is ${stop}%. Regime conditions are mixed — ` +
      `${stable}% of the universe is operating in a stable noise environment. ` +
      `Capital deployment posture is moderate.`
  }
  return `${pct}% of the tracked universe meets structural confirmation criteria. ` +
    `Average stop probability is ${stop}%. Only ${stable}% of names are in stable regimes. ` +
    `Capital deployment posture remains low. No structural deployment is indicated at this time.`
}

// ── Section 2: Confirmed Deployable Names ─────────────────────────────────────

function DeployableTickersGrid({ tickers, noDeployableMessage }: {
  tickers: DeployableTickerItem[]
  noDeployableMessage: string | null
}) {
  return (
    <div className="space-y-3">
      <h3 className="text-sm font-semibold text-text-primary uppercase tracking-wider">
        Confirmed Deployable Names
      </h3>

      {tickers.length === 0 ? (
        <div className="rounded-lg border border-surface-elevated bg-surface px-4 py-6 text-center">
          <p className="text-sm text-text-secondary">
            {noDeployableMessage ?? 'No capital structurally deployable this cycle.'}
          </p>
        </div>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-xs">
            <thead>
              <tr className="border-b border-surface-elevated">
                <Th>Ticker</Th>
                <Th>Sector</Th>
                <Th align="right">Alloc Current</Th>
                <Th align="right">Alloc Delta</Th>
                <Th align="right">Conf. Score</Th>
                <Th align="right">Vol-Adj EV %ile</Th>
                <Th align="right">Stop Prob</Th>
                <Th align="right">Sector Breadth</Th>
              </tr>
            </thead>
            <tbody>
              {tickers.map((t) => (
                <tr key={t.ticker} className="border-b border-surface-elevated/50 hover:bg-surface-elevated/30 transition-colors">
                  <td className="py-2 pr-4 font-mono font-semibold text-text-primary">{t.ticker}</td>
                  <td className="py-2 pr-4 text-text-secondary">{t.sector}</td>
                  <Td align="right">{t.allocation_current.toFixed(2)}%</Td>
                  <Td align="right" className={
                    t.allocation_delta_30d != null && t.allocation_delta_30d > 0
                      ? 'text-emerald-400' : 'text-text-secondary'
                  }>
                    {t.allocation_delta_30d != null
                      ? (t.allocation_delta_30d >= 0 ? `+${t.allocation_delta_30d.toFixed(2)}` : t.allocation_delta_30d.toFixed(2))
                      : '—'}
                  </Td>
                  <Td align="right">{t.confirmation_score}/5</Td>
                  <Td align="right">{t.vol_adj_ev_percentile.toFixed(0)}th</Td>
                  <Td align="right">{t.stop_probability.toFixed(1)}%</Td>
                  <Td align="right">{t.sector_breadth_pct.toFixed(0)}%</Td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}

function Th({ children, align = 'left' }: { children: React.ReactNode; align?: 'left' | 'right' }) {
  return (
    <th className={`py-2 pr-4 text-text-secondary font-medium text-${align} whitespace-nowrap`}>
      {children}
    </th>
  )
}

function Td({ children, align = 'left', className = '' }: {
  children: React.ReactNode
  align?: 'left' | 'right'
  className?: string
}) {
  return (
    <td className={`py-2 pr-4 text-text-secondary text-${align} ${className}`}>
      {children}
    </td>
  )
}

// ── Section 3: Sector Breadth Overview ────────────────────────────────────────

function SectorBreadthTable({ rows }: { rows: SectorBreadthRow[] }) {
  return (
    <div className="space-y-3">
      <h3 className="text-sm font-semibold text-text-primary uppercase tracking-wider">
        Sector Breadth Overview
      </h3>

      {rows.length === 0 ? (
        <p className="text-xs text-text-secondary">No sector data available.</p>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-xs">
            <thead>
              <tr className="border-b border-surface-elevated">
                <Th>Sector</Th>
                <Th align="right">Confirmed</Th>
                <Th align="right">Total Tracked</Th>
                <Th align="right">% Confirmed</Th>
                <Th>Trend</Th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => (
                <tr key={r.sector} className="border-b border-surface-elevated/50 hover:bg-surface-elevated/30 transition-colors">
                  <td className="py-2 pr-4 text-text-secondary">{r.sector}</td>
                  <Td align="right">{r.confirmed}</Td>
                  <Td align="right">{r.total}</Td>
                  <Td align="right">{r.pct_confirmed.toFixed(1)}%</Td>
                  <td className="py-2 pr-4 text-text-secondary">
                    <TrendIcon trend={r.trend} />
                    {r.trend}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}

// ── Section 4: Capital Deployment Guidance ────────────────────────────────────

function getGuidanceDescription(
  posture: string,
  ceiling: number,
  deployabilityRatioPct: number,
): string {
  if (posture === 'Expanding') {
    return `Structural conditions support active capital deployment. ${deployabilityRatioPct.toFixed(1)}% of the tracked universe passes all inclusion criteria. Suggested maximum portfolio exposure is ${ceiling.toFixed(0)}%.`
  }
  if (posture === 'Moderate') {
    return `Structural conditions are mixed. ${deployabilityRatioPct.toFixed(1)}% of the tracked universe is structurally confirmed. Suggested maximum portfolio exposure is ${ceiling.toFixed(0)}%. Deploy selectively in highest-conviction names only.`
  }
  return `Structural conditions do not support broad capital deployment. ${deployabilityRatioPct.toFixed(1)}% of the tracked universe meets confirmation criteria. Suggested maximum portfolio exposure is ${ceiling.toFixed(0)}%. Preserve capital until structural conditions improve.`
}

function CapitalDeploymentGuidance({ data }: { data: DeploymentUpdateResponse }) {
  const { snapshot, eligible_count, universe_size } = data
  const deployabilityRatioPct = universe_size > 0 ? (eligible_count / universe_size * 100) : 0
  const description = getGuidanceDescription(snapshot.capital_posture, snapshot.exposure_ceiling, deployabilityRatioPct)

  return (
    <div className="space-y-3">
      <h3 className="text-sm font-semibold text-text-primary uppercase tracking-wider">
        Capital Deployment Guidance
      </h3>

      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
        <MetricTile
          label="Capital Posture"
          value={<PostureBadge posture={snapshot.capital_posture} />}
          sub={`${snapshot.pct_universe_confirmed.toFixed(1)}% universe confirmed`}
        />
        <MetricTile
          label="Exposure Ceiling"
          value={`${snapshot.exposure_ceiling.toFixed(0)}%`}
          sub="suggested max portfolio exposure"
        />
        <MetricTile
          label="Deployability Ratio"
          value={`${eligible_count} / ${universe_size}`}
          sub={`${deployabilityRatioPct.toFixed(1)}% pass structural gate`}
        />
      </div>

      <p className="text-xs text-text-secondary leading-relaxed max-w-prose">
        {description}
      </p>
    </div>
  )
}

// ── Upgrade card for locked tiers ─────────────────────────────────────────────

function LockedCard() {
  return (
    <div className="rounded-lg border border-surface-elevated bg-surface p-8 text-center space-y-3">
      <div className="flex justify-center">
        <Lock className="h-8 w-8 text-text-secondary" />
      </div>
      <h3 className="text-sm font-semibold text-text-primary">Structural Deployment Update</h3>
      <p className="text-xs text-text-secondary max-w-sm mx-auto">
        Monthly capital deployability report — structurally confirmed names only.
        Available on Investor tier and above.
      </p>
      <ul className="text-xs text-text-secondary space-y-1 text-left max-w-xs mx-auto">
        <li className="flex gap-2"><span className="text-text-secondary">–</span>Market deployability snapshot with capital posture classification</li>
        <li className="flex gap-2"><span className="text-text-secondary">–</span>Confirmed deployable tickers filtered by 5-criterion structural gate</li>
        <li className="flex gap-2"><span className="text-text-secondary">–</span>Sector breadth overview with trend direction</li>
      </ul>
      <Link href="/billing" className="inline-flex items-center gap-1 rounded-md bg-indigo-600 hover:bg-indigo-500 px-3 py-1.5 text-xs font-medium text-white transition-colors">
        Upgrade to Investor
      </Link>
    </div>
  )
}

// ── Loading skeleton ───────────────────────────────────────────────────────────

function LoadingSkeleton() {
  return (
    <div className="space-y-6">
      <Skeleton className="h-6 w-48" />
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        {[1, 2, 3, 4].map((i) => <Skeleton key={i} className="h-20" />)}
      </div>
      <Skeleton className="h-40" />
      <Skeleton className="h-32" />
    </div>
  )
}

// ── Main component ─────────────────────────────────────────────────────────────

export function StructuralDeploymentUpdate() {
  const { data: entitlements } = useEntitlements()
  const hasAccess = entitlements?.features['feature.deployment.structural_update'] ?? false
  const { data, isLoading, error } = useDeploymentUpdate(hasAccess)

  // Show locked card for non-entitled users once entitlements are resolved
  if (entitlements && !hasAccess) {
    return <LockedCard />
  }

  if (!entitlements || isLoading) {
    return <LoadingSkeleton />
  }

  if (error) {
    return (
      <div className="rounded-lg border border-surface-elevated bg-surface p-6 text-center">
        <p className="text-sm text-error">Failed to load deployment update.</p>
        <p className="text-xs text-text-secondary mt-1">
          {(error as Error).message || 'An unexpected error occurred.'}
        </p>
      </div>
    )
  }

  if (!data) return <LoadingSkeleton />

  const cacheLabel = data.cache_age_hours < 0.1
    ? 'Generated just now'
    : `Generated ${data.cache_age_hours.toFixed(1)}h ago`

  const ttlLabel = (() => {
    try {
      const expires = new Date(data.ttl_expires_at)
      const hoursUntil = (expires.getTime() - Date.now()) / 3_600_000
      return hoursUntil > 0 ? `Refreshes in ${hoursUntil.toFixed(1)}h` : 'Refresh pending'
    } catch {
      return null
    }
  })()

  return (
    <Card className="bg-surface border-surface-elevated">
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between flex-wrap gap-2">
          <CardTitle className="text-sm font-semibold text-text-primary">
            Structural Deployment Update
          </CardTitle>
          <div className="flex items-center gap-3">
            <span className="text-xs text-text-secondary">{cacheLabel}</span>
            {ttlLabel && (
              <span className="text-xs text-text-secondary opacity-60">{ttlLabel}</span>
            )}
          </div>
        </div>
      </CardHeader>

      <CardContent className="space-y-8">
        {/* Section 1 — Market Deployability Snapshot */}
        <DeployabilitySnapshot snapshot={data.snapshot} />

        <div className="border-t border-surface-elevated" />

        {/* Section 2 — Confirmed Deployable Names */}
        <DeployableTickersGrid
          tickers={data.deployable_tickers}
          noDeployableMessage={data.no_deployable_message}
        />

        <div className="border-t border-surface-elevated" />

        {/* Section 3 — Sector Breadth Overview */}
        <SectorBreadthTable rows={data.sector_breadth} />

        <div className="border-t border-surface-elevated" />

        {/* Section 4 — Capital Deployment Guidance */}
        <CapitalDeploymentGuidance data={data} />
      </CardContent>
    </Card>
  )
}
