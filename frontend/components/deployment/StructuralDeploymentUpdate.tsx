'use client'

import React from 'react'
import type { DeploymentUpdateResponse, MarketDeployabilitySnapshot, DeployableTickerItem, SectorBreadthRow } from '@/types/api'
import { useDeploymentUpdate } from '@/lib/hooks/useDeploymentUpdate'
import { useEntitlements } from '@/lib/hooks/useEntitlements'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Skeleton } from '@/components/ui/skeleton'
import { Lock, TrendingUp, TrendingDown, Minus, ShieldCheck, ShieldOff, Activity } from 'lucide-react'
import Link from 'next/link'

// ── Derived regime types ───────────────────────────────────────────────────────

type RegimeType = 'Risk-Off' | 'Transitional' | 'Risk-On'

function getDeployabilityIndex(
  snapshot: MarketDeployabilitySnapshot,
  avgBreadthPct: number,
): number {
  return Math.round(
    (snapshot.pct_universe_confirmed * 0.35) +
    (snapshot.regime_stable_pct * 0.30) +
    ((100 - snapshot.avg_stop_probability) * 0.20) +
    (avgBreadthPct * 0.15),
  )
}

function getRegime(index: number): RegimeType {
  if (index < 15) return 'Risk-Off'
  if (index < 35) return 'Transitional'
  return 'Risk-On'
}

function getRegimeExposureCeiling(regime: RegimeType): number {
  if (regime === 'Risk-Off') return 30
  if (regime === 'Transitional') return 60
  return 90
}

function getAvgBreadthPct(rows: SectorBreadthRow[]): number {
  if (rows.length === 0) return 0
  return rows.reduce((sum, r) => sum + r.pct_confirmed, 0) / rows.length
}

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

// ── Metric tile ────────────────────────────────────────────────────────────────

function MetricTile({ label, value, sub }: { label: string; value: React.ReactNode; sub: string }) {
  return (
    <div className="rounded-lg border border-surface-elevated bg-surface p-3">
      <p className="text-xs text-text-secondary mb-1">{label}</p>
      <div className="text-base font-mono font-semibold text-text-primary">{value}</div>
      <p className="text-xs text-text-secondary mt-0.5">{sub}</p>
    </div>
  )
}

// ── Structural Gate ────────────────────────────────────────────────────────────

function StructuralGate({ isOpen }: { isOpen: boolean }) {
  return (
    <div className={`flex items-center gap-2.5 ${isOpen ? 'text-teal-400' : 'text-zinc-400'}`}>
      {isOpen
        ? <ShieldCheck className="h-6 w-6 shrink-0" />
        : <ShieldOff   className="h-6 w-6 shrink-0" />
      }
      <span className="text-xl font-bold tracking-wide leading-none">
        Structural Gate: {isOpen ? 'OPEN' : 'CLOSED'}
      </span>
      <span className="text-lg leading-none">{isOpen ? '🟢' : '🔒'}</span>
    </div>
  )
}

// ── Market Deployability Index ─────────────────────────────────────────────────

function DeployabilityIndexDisplay({ index, regime }: { index: number; regime: RegimeType }) {
  const regimeColor =
    regime === 'Risk-Off'    ? 'text-zinc-400' :
    regime === 'Transitional'? 'text-amber-400' :
    'text-teal-400'

  return (
    <div className="space-y-0.5">
      <div className="flex items-baseline gap-1.5">
        <span className="text-4xl font-bold font-mono text-text-primary">{index}</span>
        <span className="text-sm text-text-secondary">/ 100</span>
      </div>
      <p className="text-xs text-text-secondary font-medium uppercase tracking-wide">
        Market Deployability Index
      </p>
      <p className={`text-sm font-semibold ${regimeColor}`}>
        Risk Regime: {regime}
      </p>
    </div>
  )
}

// ── Regime Spectrum Meter ──────────────────────────────────────────────────────

function RegimeSpectrumMeter({ index, regime }: { index: number; regime: RegimeType }) {
  const clamped = Math.min(100, Math.max(0, index))
  const barColor =
    regime === 'Risk-Off'    ? '#71717a' :
    regime === 'Transitional'? '#f59e0b' :
    '#00D9B5'

  return (
    <div className="space-y-1.5">
      <div className="flex justify-between text-xs">
        <span className="text-zinc-400">Risk-Off</span>
        <span className="text-amber-400/70">Transitional</span>
        <span className="text-teal-400/70">Risk-On</span>
      </div>

      {/* Track */}
      <div className="relative h-3 rounded-full bg-surface-elevated overflow-hidden">
        {/* Zone tinting */}
        <div className="absolute inset-0 flex">
          <div style={{ width: '15%' }} className="bg-zinc-600/30 rounded-l-full" />
          <div style={{ width: '20%' }} className="bg-amber-600/20" />
          <div style={{ width: '65%' }} className="bg-teal-600/10 rounded-r-full" />
        </div>
        {/* Zone separators */}
        <div className="absolute inset-y-0 w-px bg-white/10" style={{ left: '15%' }} />
        <div className="absolute inset-y-0 w-px bg-white/10" style={{ left: '35%' }} />
        {/* Active fill */}
        <div
          className="absolute left-0 top-0 h-full rounded-full transition-all duration-700"
          style={{ width: `${clamped}%`, backgroundColor: barColor, opacity: 0.85 }}
        />
      </div>

      {/* Index pointer label */}
      <div className="relative h-4">
        <div
          className="absolute -translate-x-1/2 text-xs font-mono font-semibold transition-all duration-700"
          style={{ left: `${clamped}%`, color: barColor }}
        >
          {index}
        </div>
      </div>
    </div>
  )
}

// ── Activation Threshold Banner ────────────────────────────────────────────────

function ActivationThreshold() {
  return (
    <div className="rounded-md border border-zinc-700/50 bg-zinc-900/40 px-4 py-3 space-y-0.5">
      <p className="text-xs font-semibold text-text-secondary uppercase tracking-wide">
        Deployment Engine Activation Threshold
      </p>
      <p className="text-xs text-text-secondary">
        Activates when Deployability Index ≥ 25
      </p>
    </div>
  )
}

// ── Allocation Engine Status ───────────────────────────────────────────────────

function AllocationEngineStatus({ gateOpen }: { gateOpen: boolean }) {
  return (
    <div className="space-y-3">
      <h3 className="text-sm font-semibold text-text-primary uppercase tracking-wider flex items-center gap-2">
        <Activity className="h-4 w-4" />
        Allocation Engine Status
      </h3>
      <div className={`rounded-lg border px-4 py-4 ${
        gateOpen
          ? 'border-teal-500/30 bg-teal-500/5'
          : 'border-zinc-700/50 bg-surface'
      }`}>
        <div className="flex items-center gap-2 mb-2">
          <span className={`inline-block h-2 w-2 rounded-full ${gateOpen ? 'bg-teal-400' : 'bg-zinc-500'}`} />
          <span className={`text-sm font-semibold ${gateOpen ? 'text-teal-400' : 'text-zinc-400'}`}>
            Allocation Engine: {gateOpen ? 'Active' : 'Standby Mode'}
          </span>
        </div>
        <p className="text-xs text-text-secondary leading-relaxed">
          {gateOpen
            ? 'Deploy capital according to ticker-level EV and stability scoring.'
            : 'No per-position capital deployment permitted.'}
        </p>
      </div>
    </div>
  )
}

// ── Section 1: Capital Regime Status ──────────────────────────────────────────

function CapitalRegimeStatus({
  snapshot,
  index,
  regime,
  gateOpen,
}: {
  snapshot: MarketDeployabilitySnapshot
  index: number
  regime: RegimeType
  gateOpen: boolean
}) {
  const deltaStr = snapshot.avg_allocation_delta != null
    ? (snapshot.avg_allocation_delta >= 0
        ? `+${snapshot.avg_allocation_delta.toFixed(2)}%`
        : `${snapshot.avg_allocation_delta.toFixed(2)}%`)
    : '—'

  const universeConfirmedDisplay =
    snapshot.pct_universe_confirmed === 0
      ? 'None Detected'
      : `${snapshot.pct_universe_confirmed.toFixed(1)}%`

  return (
    <div className="space-y-5">
      {/* Primary signals row */}
      <div className="flex flex-col gap-5 sm:flex-row sm:items-start sm:justify-between">
        {/* Gate — dominant */}
        <div className="space-y-2">
          <StructuralGate isOpen={gateOpen} />
          {!gateOpen && (
            <p className="text-xs text-text-secondary pl-8">
              Universe Confirmation: None Detected
            </p>
          )}
        </div>

        {/* Index + regime — dominant */}
        <DeployabilityIndexDisplay index={index} regime={regime} />
      </div>

      {/* Regime spectrum meter */}
      <RegimeSpectrumMeter index={index} regime={regime} />

      {/* Context metrics (secondary) */}
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <MetricTile
          label="Universe Confirmed"
          value={
            <span className={snapshot.pct_universe_confirmed === 0 ? 'text-zinc-500 text-sm' : ''}>
              {universeConfirmedDisplay}
            </span>
          }
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

      {/* Posture summary text */}
      <p className="text-xs text-text-secondary leading-relaxed max-w-prose">
        {buildPostureSummary(snapshot)}
      </p>

      {/* Activation threshold — always visible */}
      <ActivationThreshold />
    </div>
  )
}

/** Deterministic posture summary — no LLM. ≤150 words. */
function buildPostureSummary(s: MarketDeployabilitySnapshot): string {
  const pct    = s.pct_universe_confirmed.toFixed(1)
  const stop   = s.avg_stop_probability.toFixed(1)
  const stable = s.regime_stable_pct.toFixed(1)

  if (s.capital_posture === 'Expanding') {
    return `${pct}% of the tracked universe meets structural confirmation criteria. ` +
      `Average stop probability is ${stop}% with ${stable}% of names operating in stable regimes. ` +
      `Capital deployment conditions are structurally expanding. ` +
      `Confirmed names appear below.`
  }
  if (s.capital_posture === 'Moderate') {
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

function RegimeExposureGuidance({
  regime,
  ceiling,
  eligible_count,
  universe_size,
}: {
  regime: RegimeType
  ceiling: number
  eligible_count: number
  universe_size: number
}) {
  const regimeColor =
    regime === 'Risk-Off'    ? 'text-zinc-400' :
    regime === 'Transitional'? 'text-amber-400' :
    'text-teal-400'

  const borderColor =
    regime === 'Risk-Off'    ? 'border-zinc-600/40' :
    regime === 'Transitional'? 'border-amber-600/40' :
    'border-teal-600/40'

  const ratioDisplay = universe_size === 0
    ? <p className="text-xs text-text-secondary italic">No eligible tickers in tracked universe.</p>
    : (
      <div className="space-y-0.5">
        <p className="font-mono font-semibold text-text-primary text-base">
          {eligible_count} Confirmed
        </p>
        <p className="text-xs text-text-secondary">
          {universe_size} Evaluated
        </p>
      </div>
    )

  const regimeNote =
    regime === 'Risk-Off'
      ? 'Preserve capital until structural conditions improve.'
      : regime === 'Transitional'
      ? 'Deploy selectively in highest-conviction names only.'
      : 'Active deployment permitted according to EV and stability ranking.'

  return (
    <div className="space-y-3">
      <h3 className="text-sm font-semibold text-text-primary uppercase tracking-wider">
        Capital Deployment Guidance
      </h3>

      <div className={`rounded-lg border ${borderColor} bg-surface p-4 space-y-4`}>
        <div className="grid grid-cols-2 gap-4 sm:grid-cols-3">
          {/* Regime exposure ceiling — primary in this section */}
          <div>
            <p className="text-xs text-text-secondary mb-1">Regime-Based Exposure Limit</p>
            <p className={`text-2xl font-bold font-mono ${regimeColor}`}>{ceiling}%</p>
            <p className="text-xs text-text-secondary">max portfolio exposure</p>
          </div>

          <div>
            <p className="text-xs text-text-secondary mb-1">Active Regime</p>
            <p className={`text-sm font-semibold ${regimeColor}`}>{regime}</p>
            <p className="text-xs text-text-secondary mt-0.5">{regimeNote}</p>
          </div>

          <div>
            <p className="text-xs text-text-secondary mb-1">Deployability Ratio</p>
            {ratioDisplay}
          </div>
        </div>

        <div className="border-t border-surface-elevated pt-3">
          <p className="text-xs text-text-secondary leading-relaxed">
            {regime === 'Risk-Off'
              ? `Risk-Off regime: structural conditions do not support broad capital deployment. Maximum portfolio exposure capped at ${ceiling}%. Preserve capital until structural confirmation rates improve.`
              : regime === 'Transitional'
              ? `Transitional regime: conditions are mixed. Deploy selectively in highest-conviction names only. Maximum portfolio exposure capped at ${ceiling}%.`
              : `Risk-On regime: structural conditions support active capital deployment. Maximum portfolio exposure extended to ${ceiling}%. Deploy according to tier EV and stability ranking.`
            }
          </p>
        </div>
      </div>
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
      <h3 className="text-sm font-semibold text-text-primary">Capital Control Panel</h3>
      <p className="text-xs text-text-secondary max-w-sm mx-auto">
        Institutional-grade capital regime monitoring — structurally confirmed names,
        deployability index, and regime-based exposure guidance.
        Available on Investor tier and above.
      </p>
      <ul className="text-xs text-text-secondary space-y-1 text-left max-w-xs mx-auto">
        <li className="flex gap-2"><span className="text-text-secondary">–</span>Structural gate state with Market Deployability Index</li>
        <li className="flex gap-2"><span className="text-text-secondary">–</span>Confirmed deployable tickers filtered by 5-criterion structural gate</li>
        <li className="flex gap-2"><span className="text-text-secondary">–</span>Regime-based exposure ceiling and allocation engine status</li>
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
      <Skeleton className="h-8 w-64" />
      <Skeleton className="h-16 w-40" />
      <Skeleton className="h-10 w-full" />
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

  // ── Compute derived presentation values ──────────────────────────────────────
  const avgBreadthPct  = getAvgBreadthPct(data.sector_breadth)
  const deployIndex    = getDeployabilityIndex(data.snapshot, avgBreadthPct)
  const regime         = getRegime(deployIndex)
  const exposureCeiling = getRegimeExposureCeiling(regime)
  const gateOpen       = data.snapshot.pct_universe_confirmed > 0

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
          <div>
            <CardTitle className="text-base font-semibold text-text-primary">
              Capital Control Panel
            </CardTitle>
            <p className="text-xs text-text-secondary mt-0.5">Structural Deployment Update</p>
          </div>
          <div className="flex items-center gap-3">
            <span className="text-xs text-text-secondary">{cacheLabel}</span>
            {ttlLabel && (
              <span className="text-xs text-text-secondary opacity-60">{ttlLabel}</span>
            )}
          </div>
        </div>
      </CardHeader>

      <CardContent className="space-y-8">
        {/* Section 1 — Capital Regime Status (Gate + Index + Meter + Metrics) */}
        <CapitalRegimeStatus
          snapshot={data.snapshot}
          index={deployIndex}
          regime={regime}
          gateOpen={gateOpen}
        />

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

        {/* Section 4 — Capital Deployment Guidance (regime-based) */}
        <RegimeExposureGuidance
          regime={regime}
          ceiling={exposureCeiling}
          eligible_count={data.eligible_count}
          universe_size={data.universe_size}
        />

        <div className="border-t border-surface-elevated" />

        {/* Section 5 — Allocation Engine Status */}
        <AllocationEngineStatus gateOpen={gateOpen} />
      </CardContent>
    </Card>
  )
}
