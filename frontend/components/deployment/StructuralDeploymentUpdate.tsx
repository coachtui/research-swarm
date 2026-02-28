'use client'

import React from 'react'
import ReactDOM from 'react-dom'
import type { DeploymentUpdateResponse, MarketDeployabilitySnapshot, DeployableTickerItem, SectorBreadthRow, SectorLeadershipEntry, RotationSignalLeader, RotationMomentumLeader, EligibilityDiagnostics, NearMissTicker } from '@/types/api'
import { useDeploymentUpdate } from '@/lib/hooks/useDeploymentUpdate'
import { useAdminDeploymentUpdate } from '@/lib/hooks/useAdminDeploymentUpdate'
import { useEntitlements } from '@/lib/hooks/useEntitlements'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Skeleton } from '@/components/ui/skeleton'
import { Lock, TrendingUp, TrendingDown, Minus, ShieldCheck, ShieldOff, Activity, ChevronDown, X } from 'lucide-react'
import Link from 'next/link'
import { EligibilityStressTestPanel } from '@/components/deployment/EligibilityStressTestPanel'
import { EligibilityRollingSimPanel } from '@/components/deployment/EligibilityRollingSimPanel'
import { OpportunityDistributionPanel } from '@/components/deployment/OpportunityDistributionPanel'
import { ThresholdCalibrationPanel } from '@/components/deployment/ThresholdCalibrationPanel'
import {
  BarChart, Bar, XAxis, YAxis, Tooltip as RechartsTooltip,
  Cell, ResponsiveContainer, CartesianGrid,
  ScatterChart, Scatter, ZAxis,
} from 'recharts'

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
  diag,
}: {
  snapshot: MarketDeployabilitySnapshot
  index: number
  regime: RegimeType
  gateOpen: boolean
  diag: EligibilityDiagnostics
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

      {/* Pipeline funnel — evaluated → confirmed → eligible */}
      <PipelineFunnel diag={diag} />

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
                <Th align="right">Upside Rank</Th>
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
                  <Td align="right">
                    {t.vol_adj_ev_percentile != null ? `${t.vol_adj_ev_percentile.toFixed(0)}th` : '—'}
                  </Td>
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

// Abbreviate long sector names so X-axis labels don't overlap.
const SECTOR_ABBREV: Record<string, string> = {
  'Communication Services': 'Comm. Svcs',
  'Consumer Defensive':     'Cons. Def.',
  'Consumer Cyclical':      'Cons. Cyc.',
  'Financial Services':     'Financials',
  'Basic Materials':        'Materials',
}
function abbreviateSector(s: string): string {
  return SECTOR_ABBREV[s] ?? s
}

/** Rich tooltip content rendered inside the bar chart. */
function SectorBreadthChartTooltip({
  active,
  payload,
}: {
  active?: boolean
  payload?: Array<{ payload: SectorBreadthRow }>
}) {
  if (!active || !payload?.length) return null
  const r = payload[0].payload

  const edgeColor = r.avg_edge_pct > 0 ? '#34d399' : r.avg_edge_pct < 0 ? '#f87171' : '#f8fafc'
  const stopColor = r.median_stop_pct > 40 ? '#fbbf24' : '#f8fafc'

  return (
    <div style={{
      background: '#0B0F19',
      border: '1px solid rgba(255,255,255,0.10)',
      borderRadius: 10,
      padding: '10px 13px',
      boxShadow: '0 12px 30px rgba(0,0,0,0.40)',
      fontSize: 12,
      lineHeight: 1.45,
      minWidth: 210,
      pointerEvents: 'none',
    }}>
      <div style={{ fontWeight: 700, color: '#f8fafc', marginBottom: 7, fontSize: 13 }}>
        {r.sector}
      </div>
      <div style={{ display: 'grid', gridTemplateColumns: '1fr auto', columnGap: 14, rowGap: 3 }}>
        <span style={{ color: '#9ca3af' }}>% Confirmed</span>
        <span style={{ color: '#f8fafc', fontWeight: 600, textAlign: 'right' }}>{r.pct_confirmed.toFixed(1)}%</span>

        <span style={{ color: '#9ca3af' }}>Structural Rank</span>
        <span style={{ color: '#f8fafc', fontWeight: 600, textAlign: 'right' }}>{r.structural_score.toFixed(3)}</span>

        <span style={{ color: '#9ca3af' }}>Opp. Score</span>
        <span style={{ color: '#f8fafc', fontWeight: 600, textAlign: 'right' }}>{r.opportunity_score.toFixed(3)}</span>

        <span style={{ color: '#9ca3af' }}>Avg Risk-Adj Edge</span>
        <span style={{ color: edgeColor, fontWeight: 600, textAlign: 'right' }}>
          {r.avg_edge_pct > 0 ? '+' : ''}{r.avg_edge_pct.toFixed(1)}%
        </span>

        <span style={{ color: '#9ca3af' }}>Median Stop</span>
        <span style={{ color: stopColor, fontWeight: 600, textAlign: 'right' }}>{r.median_stop_pct.toFixed(1)}%</span>

        {r.tier2 > 0 && (
          <>
            <span style={{ color: '#9ca3af' }}>Tier 2</span>
            <span style={{ color: '#fbbf24', fontWeight: 600, textAlign: 'right' }}>{r.tier2}</span>
          </>
        )}
      </div>
    </div>
  )
}

/** Bar chart — % confirmed by sector with hover highlight + portal tooltip. */
function SectorBreadthChart({ rows }: { rows: SectorBreadthRow[] }) {
  const [activeIndex, setActiveIndex] = React.useState<number | null>(null)
  const [hoveredRow, setHoveredRow] = React.useState<SectorBreadthRow | null>(null)
  const mousePos = useGlobalMousePos()
  if (rows.length === 0) return null
  const sorted = [...rows].sort((a, b) => b.pct_confirmed - a.pct_confirmed)

  return (
    <div style={{ height: 200, overflow: 'visible' }}>
      <ResponsiveContainer width="100%" height="100%">
        <BarChart
          data={sorted}
          margin={{ top: 4, right: 4, bottom: 52, left: 0 }}
          barSize={18}
          onMouseMove={(state) => {
            const idx = (state as { activeTooltipIndex?: number }).activeTooltipIndex
            setActiveIndex(idx ?? null)
            // eslint-disable-next-line @typescript-eslint/no-explicit-any
            const p = (state as any).activePayload
            setHoveredRow(p?.[0]?.payload ?? null)
          }}
          onMouseLeave={() => { setActiveIndex(null); setHoveredRow(null) }}
        >
          <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.04)" vertical={false} />
          <XAxis
            dataKey="sector"
            tick={{ fontSize: 9, fill: '#9ca3af' }}
            angle={-28}
            textAnchor="end"
            interval={0}
            tickFormatter={abbreviateSector}
          />
          <YAxis
            domain={[0, 100]}
            tick={{ fontSize: 9, fill: '#9ca3af' }}
            unit="%"
            width={32}
          />
          {/* Disable built-in tooltip — we use portal instead */}
          <RechartsTooltip content={() => null} cursor={{ fill: 'rgba(255,255,255,0.03)' }} />
          <Bar dataKey="pct_confirmed" radius={[2, 2, 0, 0]}>
            {sorted.map((r, idx) => {
              const baseColor = r.pct_confirmed > 60 ? '#2dd4bf' : r.pct_confirmed < 20 ? '#52525b' : '#6b7280'
              const dimmed = activeIndex !== null && activeIndex !== idx
              return (
                <Cell
                  key={r.sector}
                  fill={baseColor}
                  opacity={dimmed ? 0.3 : 1}
                />
              )
            })}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
      {/* Portal tooltip — renders to document.body, never clipped */}
      {hoveredRow && typeof document !== 'undefined' && ReactDOM.createPortal(
        <div style={{ position: 'fixed', left: mousePos.x + 14, top: mousePos.y - 12, zIndex: 9999, pointerEvents: 'none' }}>
          <SectorBreadthChartTooltip active payload={[{ payload: hoveredRow }]} />
        </div>,
        document.body,
      )}
    </div>
  )
}

// ── Delta helpers ──────────────────────────────────────────────────────────────

/** Render a Δ score (0–1 scale → displayed as %) with arrow and color. */
function DeltaScore({ v }: { v: number | null }) {
  if (v === null || v === undefined) return <span className="text-zinc-600">—</span>
  const pct = v * 100
  if (Math.abs(pct) < 0.05) return <span className="text-zinc-500 font-mono">—</span>
  const up = v > 0
  return (
    <span className={`font-mono text-xs ${up ? 'text-teal-400' : 'text-red-400/80'}`}>
      {up ? '↑' : '↓'} {up ? '+' : ''}{pct.toFixed(1)}%
    </span>
  )
}

/** Render a Δ tier2 count with arrow and color. */
function DeltaCount({ v }: { v: number | null }) {
  if (v === null || v === undefined) return <span className="text-zinc-600">—</span>
  if (v === 0) return <span className="text-zinc-500 font-mono">—</span>
  return (
    <span className={`font-mono text-xs ${v > 0 ? 'text-teal-400' : 'text-red-400/80'}`}>
      {v > 0 ? '↑ +' : '↓ '}{v}
    </span>
  )
}

// ── Global mouse position (for portal tooltips) ────────────────────────────

function useGlobalMousePos() {
  const [pos, setPos] = React.useState({ x: 0, y: 0 })
  React.useEffect(() => {
    const handler = (e: MouseEvent) => setPos({ x: e.clientX, y: e.clientY })
    document.addEventListener('mousemove', handler, { passive: true })
    return () => document.removeEventListener('mousemove', handler)
  }, [])
  return pos
}

/** Dark-theme tooltip shell — shared by bar + scatter charts. */
function TooltipShell({ children }: { children: React.ReactNode }) {
  return (
    <div style={{
      background: '#0B0F19',
      border: '1px solid rgba(255,255,255,0.10)',
      borderRadius: 10,
      padding: '10px 13px',
      boxShadow: '0 16px 40px rgba(0,0,0,0.60)',
      fontSize: 12,
      lineHeight: 1.45,
      minWidth: 210,
      pointerEvents: 'none',
      color: '#F8FAFC',
    }}>
      {children}
    </div>
  )
}

/** Derive structural trend from Δ when available; fall back to legacy field. */
function derivedStructuralTrend(r: SectorBreadthRow): 'rising' | 'stable' | 'falling' {
  if (r.delta_structural !== null && r.delta_structural !== undefined) {
    if (r.delta_structural >= 0.01) return 'rising'
    if (r.delta_structural <= -0.01) return 'falling'
    return 'stable'
  }
  return r.trend
}

/** Derive opportunity trend from Δ when available; fall back to legacy field. */
function derivedOppTrend(r: SectorBreadthRow): 'rising' | 'stable' | 'falling' {
  if (r.delta_opp !== null && r.delta_opp !== undefined) {
    if (r.delta_opp >= 0.01) return 'rising'
    if (r.delta_opp <= -0.01) return 'falling'
    return 'stable'
  }
  return r.opportunity_trend
}

// ── Sector Leadership Block ────────────────────────────────────────────────────

/** Compact rotation leaderboard — top 3 sectors by composite rotation score. */
function SectorLeadershipBlock({
  entries,
  coverageLabel,
  hasDelta,
}: {
  entries: SectorLeadershipEntry[]
  coverageLabel?: string
  hasDelta: boolean
}) {
  if (entries.length === 0) return null

  return (
    <div className="rounded-lg border border-surface-elevated bg-surface p-3 space-y-2">
      <div className="flex items-center justify-between">
        <h4 className="text-xs font-semibold text-text-primary uppercase tracking-wider">
          Sector Leadership — Deployable Rotation
        </h4>
        {coverageLabel && (
          <span className="text-xs text-text-secondary opacity-70">{coverageLabel}</span>
        )}
      </div>
      <table className="w-full text-xs">
        <thead>
          <tr className="border-b border-surface-elevated/50">
            <Th>Rank</Th>
            <Th>Sector</Th>
            <Th align="right">Rot. Score</Th>
            <Th align="right">Opp.</Th>
            <Th align="right">Structural</Th>
            {hasDelta && <Th align="right">Δ Opp</Th>}
            {hasDelta && <Th align="right">Δ Struct</Th>}
            {hasDelta && <Th align="right">Δ T2</Th>}
          </tr>
        </thead>
        <tbody>
          {entries.map((e) => (
            <tr key={e.sector} className="border-b border-surface-elevated/30 hover:bg-surface-elevated/20 transition-colors">
              <td className="py-1.5 pr-3 font-mono text-text-secondary w-6">{e.rank}.</td>
              <td className="py-1.5 pr-4 font-medium text-text-primary">{e.sector}</td>
              <Td align="right">
                <span className="font-mono font-semibold text-teal-400">
                  {e.rotation_score.toFixed(3)}
                </span>
              </Td>
              <Td align="right">
                <span className="font-mono text-text-secondary">
                  {(e.opportunity_score ?? 0).toFixed(3)}
                </span>
              </Td>
              <Td align="right">
                <span className="font-mono text-text-secondary">
                  {(e.structural_score ?? 0).toFixed(3)}
                </span>
              </Td>
              {hasDelta && <Td align="right"><DeltaScore v={e.delta_opp ?? null} /></Td>}
              {hasDelta && <Td align="right"><DeltaScore v={e.delta_structural ?? null} /></Td>}
              {hasDelta && <Td align="right"><DeltaCount v={e.delta_tier2 ?? null} /></Td>}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

// ── Rotation Signal Panel ──────────────────────────────────────────────────────

/** Mini panel: sectors with the most meaningful ΔOpp − ΔStructural divergence. */
function RotationSignalPanel({ leaders }: { leaders: RotationSignalLeader[] }) {
  if (leaders.length === 0) return null

  const early    = leaders.filter((l) => l.direction === 'early_rotation')
  const extended = leaders.filter((l) => l.direction === 'overextended')

  function SignalRow({ l }: { l: RotationSignalLeader }) {
    const sig = l.rotation_signal
    const up  = sig > 0
    return (
      <tr className="border-b border-surface-elevated/30 hover:bg-surface-elevated/20 transition-colors">
        <td className="py-1.5 pr-4 font-medium text-text-primary text-xs">{l.sector}</td>
        <Td align="right"><DeltaScore v={l.delta_opp} /></Td>
        <Td align="right"><DeltaScore v={l.delta_structural} /></Td>
        <Td align="right">
          <span className={`font-mono font-semibold text-xs ${up ? 'text-teal-400' : 'text-red-400/80'}`}>
            {up ? '+' : ''}{(sig * 100).toFixed(1)}%
          </span>
        </Td>
      </tr>
    )
  }

  return (
    <div className="rounded-lg border border-surface-elevated bg-surface p-3 space-y-3">
      <div className="flex items-center justify-between">
        <h4 className="text-xs font-semibold text-text-primary uppercase tracking-wider">
          Rotation Signal — Sector Rotation in Motion
        </h4>
        <span className="text-xs text-text-secondary opacity-60">ΔOpp − ΔStructural</span>
      </div>

      {early.length > 0 && (
        <div className="space-y-1">
          <p className="text-xs text-teal-400/70 font-medium">Early Rotation ↑</p>
          <table className="w-full text-xs">
            <thead>
              <tr className="border-b border-surface-elevated/50">
                <Th>Sector</Th>
                <Th align="right">Δ Opp</Th>
                <Th align="right">Δ Structural</Th>
                <Th align="right">Signal</Th>
              </tr>
            </thead>
            <tbody>{early.map((l) => <SignalRow key={l.sector} l={l} />)}</tbody>
          </table>
        </div>
      )}

      {extended.length > 0 && (
        <div className="space-y-1">
          <p className="text-xs text-red-400/60 font-medium">Overextended ↓</p>
          <table className="w-full text-xs">
            <thead>
              <tr className="border-b border-surface-elevated/50">
                <Th>Sector</Th>
                <Th align="right">Δ Opp</Th>
                <Th align="right">Δ Structural</Th>
                <Th align="right">Signal</Th>
              </tr>
            </thead>
            <tbody>{extended.map((l) => <SignalRow key={l.sector} l={l} />)}</tbody>
          </table>
        </div>
      )}

      <p className="text-xs text-text-secondary/40 leading-relaxed">
        Positive signal = opportunity improving faster than structural confirmation (early rotation).
        Negative = confirmation rising while opportunity deteriorates (overextended).
      </p>
    </div>
  )
}

// ── Flow State helpers ─────────────────────────────────────────────────────────

const FLOW_COLORS: Record<string, string> = {
  Inflow:  '#2dd4bf',
  Outflow: '#f87171',
  Neutral: '#6b7280',
}

function FlowBadge({ state }: { state: string }) {
  const styles: Record<string, string> = {
    Inflow:  'bg-teal-500/15 text-teal-400 border-teal-500/30',
    Outflow: 'bg-red-500/15 text-red-400 border-red-500/30',
    Neutral: 'bg-zinc-500/15 text-zinc-400 border-zinc-500/30',
  }
  const arrow = state === 'Inflow' ? '↑' : state === 'Outflow' ? '↓' : '—'
  return (
    <span className={`inline-flex items-center gap-0.5 rounded border px-1.5 py-0.5 text-xs font-semibold ${styles[state] ?? styles.Neutral}`}>
      {arrow} {state}
    </span>
  )
}

// ── Flow Summary Strip ─────────────────────────────────────────────────────────

/** Compact horizontal strip showing Inflow leaders + Outflow laggards by RM. */
function FlowSummaryStrip({ leaders }: { leaders: RotationMomentumLeader[] }) {
  if (leaders.length === 0) return null

  const inflow  = leaders.filter((l) => l.flow_state === 'Inflow')
  const outflow = leaders.filter((l) => l.flow_state === 'Outflow')

  function Chip({ l }: { l: RotationMomentumLeader }) {
    const rm  = l.rotation_momentum
    const pos = rm >= 0
    return (
      <div className="flex items-center gap-1.5 rounded-full border border-surface-elevated bg-surface px-3 py-1.5">
        <span className="text-xs font-medium text-text-primary truncate max-w-[90px]" title={l.sector}>
          {abbreviateSector(l.sector)}
        </span>
        <span className={`font-mono text-xs font-semibold ${pos ? 'text-teal-400' : 'text-red-400'}`}>
          {pos ? '+' : ''}{(rm * 100).toFixed(1)}%
        </span>
        <FlowBadge state={l.flow_state} />
      </div>
    )
  }

  return (
    <div className="rounded-lg border border-surface-elevated bg-surface/50 p-3 space-y-2.5">
      <div className="flex items-center justify-between">
        <h4 className="text-xs font-semibold text-text-primary uppercase tracking-wider">
          Sector Rotation Flow
        </h4>
        <span className="text-xs text-text-secondary opacity-50">RM = EWMA × confidence</span>
      </div>
      <div className="flex flex-wrap gap-x-6 gap-y-2">
        {inflow.length > 0 && (
          <div className="space-y-1.5">
            <p className="text-xs text-teal-400/70 font-medium uppercase tracking-wide">Rotation Leaders</p>
            <div className="flex flex-wrap gap-2">
              {inflow.map((l) => <Chip key={l.sector} l={l} />)}
            </div>
          </div>
        )}
        {outflow.length > 0 && (
          <div className="space-y-1.5">
            <p className="text-xs text-red-400/60 font-medium uppercase tracking-wide">Rotation Laggards</p>
            <div className="flex flex-wrap gap-2">
              {outflow.map((l) => <Chip key={l.sector} l={l} />)}
            </div>
          </div>
        )}
        {inflow.length === 0 && outflow.length === 0 && (
          <p className="text-xs text-text-secondary/60">
            All sectors in neutral momentum — no strong rotation signal detected.
          </p>
        )}
      </div>
    </div>
  )
}

// ── Rotation Momentum Table ────────────────────────────────────────────────────

/** Core rotation momentum table sorted by RM descending. */
function RotationMomentumTable({
  rows,
  hasMomentum,
}: {
  rows: SectorBreadthRow[]
  hasMomentum: boolean
}) {
  if (!hasMomentum) return null

  const eligible = rows
    .filter((r) => r.rotation_momentum !== null && r.rotation_momentum !== undefined)
    .sort((a, b) => (b.rotation_momentum ?? 0) - (a.rotation_momentum ?? 0))

  if (eligible.length === 0) return null

  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between">
        <h4 className="text-xs font-semibold text-text-primary uppercase tracking-wider">
          Rotation Momentum
        </h4>
        <span
          className="text-xs text-text-secondary/50 cursor-help"
          title="Rotation Momentum = Smoothed (ΔOpp − ΔStructural) × confidence factor. Confidence = min(1, √(n/10)) — prevents small sectors from dominating."
        >
          RM = EWMA(ΔOpp − ΔStruct) × C ⓘ
        </span>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full text-xs">
          <thead>
            <tr className="border-b border-surface-elevated">
              <Th>Sector</Th>
              <Th>Flow</Th>
              <Th align="right">RM</Th>
              <Th align="right">ΔOpp</Th>
              <Th align="right">ΔStruct</Th>
              <Th align="right">n</Th>
              <Th align="right">ΔTier2</Th>
            </tr>
          </thead>
          <tbody>
            {eligible.map((r) => {
              const rm  = r.rotation_momentum ?? 0
              const rmPos = rm > 0
              return (
                <tr key={r.sector} className="border-b border-surface-elevated/40 hover:bg-surface-elevated/20 transition-colors">
                  <td className="py-2 pr-3 font-medium text-text-primary truncate max-w-[120px]" title={r.sector}>
                    {r.sector}
                  </td>
                  <td className="py-2 pr-3">
                    <FlowBadge state={r.flow_state ?? 'Neutral'} />
                  </td>
                  <Td align="right">
                    <span className={`font-mono font-semibold ${rmPos ? 'text-teal-400' : rm < 0 ? 'text-red-400/80' : 'text-zinc-500'}`}>
                      {rmPos ? '+' : ''}{(rm * 100).toFixed(1)}%
                    </span>
                  </Td>
                  <Td align="right"><DeltaScore v={r.ewma_delta_opp ?? null} /></Td>
                  <Td align="right"><DeltaScore v={r.ewma_delta_structural ?? null} /></Td>
                  <Td align="right">
                    <span className="font-mono text-text-secondary">{r.total}</span>
                  </Td>
                  <Td align="right"><DeltaCount v={r.delta_tier2 ?? null} /></Td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
      <p className="text-xs text-text-secondary/40">
        C = min(1, √(n/10)) — sectors with &lt;10 tickers are confidence-discounted.
      </p>
    </div>
  )
}

// ── Flow Map Scatter ────────────────────────────────────────────────────────────

/** Scatter tooltip (portal-based). */
function ScatterTooltipContent({
  r,
  hasMomentum,
}: {
  r: SectorBreadthRow & { total: number }
  hasMomentum: boolean
}) {
  const edgeColor = r.avg_edge_pct > 0 ? '#34d399' : r.avg_edge_pct < 0 ? '#f87171' : '#f8fafc'
  const stopColor = r.median_stop_pct > 40 ? '#fbbf24' : '#f8fafc'
  const rm = r.rotation_momentum
  return (
    <TooltipShell>
      <div style={{ fontWeight: 700, color: '#f8fafc', marginBottom: 7, fontSize: 13 }}>
        {r.sector}
      </div>
      <div style={{ display: 'grid', gridTemplateColumns: '1fr auto', columnGap: 14, rowGap: 3 }}>
        <span style={{ color: '#9ca3af' }}>Structural</span>
        <span style={{ color: '#f8fafc', fontWeight: 600, textAlign: 'right' }}>{(r.structural_score * 100).toFixed(1)}%</span>

        <span style={{ color: '#9ca3af' }}>Opportunity</span>
        <span style={{ color: '#f8fafc', fontWeight: 600, textAlign: 'right' }}>{(r.opportunity_score * 100).toFixed(1)}%</span>

        {r.delta_opp !== null && r.delta_opp !== undefined && (
          <>
            <span style={{ color: '#9ca3af' }}>ΔOpp</span>
            <span style={{ color: r.delta_opp > 0 ? '#2dd4bf' : '#f87171', fontWeight: 600, textAlign: 'right' }}>
              {r.delta_opp > 0 ? '+' : ''}{(r.delta_opp * 100).toFixed(1)}%
            </span>
          </>
        )}
        {r.delta_structural !== null && r.delta_structural !== undefined && (
          <>
            <span style={{ color: '#9ca3af' }}>ΔStruct</span>
            <span style={{ color: r.delta_structural > 0 ? '#2dd4bf' : '#f87171', fontWeight: 600, textAlign: 'right' }}>
              {r.delta_structural > 0 ? '+' : ''}{(r.delta_structural * 100).toFixed(1)}%
            </span>
          </>
        )}
        {hasMomentum && rm !== null && rm !== undefined && (
          <>
            <span style={{ color: '#9ca3af' }}>RM</span>
            <span style={{ color: rm > 0 ? '#2dd4bf' : rm < 0 ? '#f87171' : '#6b7280', fontWeight: 600, textAlign: 'right' }}>
              {rm > 0 ? '+' : ''}{(rm * 100).toFixed(1)}%
            </span>
          </>
        )}
        {r.tier2 > 0 && (
          <>
            <span style={{ color: '#9ca3af' }}>Tier 2</span>
            <span style={{ color: '#fbbf24', fontWeight: 600, textAlign: 'right' }}>{r.tier2}</span>
          </>
        )}
        <span style={{ color: '#9ca3af' }}>Avg Edge</span>
        <span style={{ color: edgeColor, fontWeight: 600, textAlign: 'right' }}>
          {r.avg_edge_pct > 0 ? '+' : ''}{r.avg_edge_pct.toFixed(1)}%
        </span>

        <span style={{ color: '#9ca3af' }}>Median Stop</span>
        <span style={{ color: stopColor, fontWeight: 600, textAlign: 'right' }}>{r.median_stop_pct.toFixed(1)}%</span>
      </div>
    </TooltipShell>
  )
}

/** 2D scatter — structural vs opportunity score, sized by n, colored by flow state. */
function FlowMapScatter({
  rows,
  hasMomentum,
}: {
  rows: SectorBreadthRow[]
  hasMomentum: boolean
}) {
  const [hoveredSector, setHoveredSector] = React.useState<SectorBreadthRow | null>(null)
  const mousePos = useGlobalMousePos()

  if (rows.length === 0) return null

  const scatterData = rows.map((r) => ({
    x: r.structural_score,
    y: r.opportunity_score,
    z: Math.max(60, r.total * 30),
    sector: r.sector,
    _row: r,
  }))

  // Split into groups for per-color rendering
  const groups: Record<string, typeof scatterData> = { Inflow: [], Outflow: [], Neutral: [] }
  for (const d of scatterData) {
    const fs = hasMomentum ? (d._row.flow_state ?? 'Neutral') : 'Neutral'
    groups[fs]?.push(d)
  }

  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between">
        <h4 className="text-xs font-semibold text-text-primary uppercase tracking-wider">
          Flow Map — Structural vs Opportunity
        </h4>
        <div className="flex items-center gap-3 text-xs text-text-secondary/60">
          <span><span style={{ color: FLOW_COLORS.Inflow }}>●</span> Inflow</span>
          <span><span style={{ color: FLOW_COLORS.Neutral }}>●</span> Neutral</span>
          <span><span style={{ color: FLOW_COLORS.Outflow }}>●</span> Outflow</span>
        </div>
      </div>
      <div style={{ height: 220, position: 'relative' }}>
        <ResponsiveContainer width="100%" height="100%">
          <ScatterChart margin={{ top: 8, right: 16, bottom: 24, left: 0 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.04)" />
            <XAxis
              type="number" dataKey="x" domain={[0, 1]} name="Structural"
              tick={{ fontSize: 9, fill: '#9ca3af' }}
              label={{ value: 'Structural', position: 'insideBottom', offset: -12, fontSize: 9, fill: '#6b7280' }}
            />
            <YAxis
              type="number" dataKey="y" domain={[0, 1]} name="Opportunity"
              tick={{ fontSize: 9, fill: '#9ca3af' }}
              width={32}
              label={{ value: 'Opp', angle: -90, position: 'insideLeft', offset: 12, fontSize: 9, fill: '#6b7280' }}
            />
            <ZAxis type="number" dataKey="z" range={[40, 350]} />
            <RechartsTooltip content={() => null} />
            {(Object.entries(groups) as [string, typeof scatterData][]).map(([fs, pts]) => (
              pts.length > 0 && (
                <Scatter
                  key={fs}
                  data={pts}
                  fill={FLOW_COLORS[fs] ?? FLOW_COLORS.Neutral}
                  fillOpacity={fs === 'Neutral' ? 0.5 : 0.8}
                  onMouseEnter={(data) => setHoveredSector((data as typeof pts[0])._row)}
                  onMouseLeave={() => setHoveredSector(null)}
                />
              )
            ))}
          </ScatterChart>
        </ResponsiveContainer>
        {/* Portal tooltip */}
        {hoveredSector && typeof document !== 'undefined' && ReactDOM.createPortal(
          <div style={{ position: 'fixed', left: mousePos.x + 14, top: mousePos.y - 12, zIndex: 9999, pointerEvents: 'none' }}>
            <ScatterTooltipContent r={hoveredSector} hasMomentum={hasMomentum} />
          </div>,
          document.body,
        )}
      </div>
    </div>
  )
}

/** Section 1 of sector panel — structural confirmation breadth. */
function SectorStructuralTable({ rows }: { rows: SectorBreadthRow[] }) {
  return (
    <div className="space-y-2">
      <h4 className="text-xs font-semibold text-text-secondary uppercase tracking-wider">
        Sector Structural Breadth
      </h4>
      <div className="overflow-x-auto">
        <table className="w-full text-xs">
          <thead>
            <tr className="border-b border-surface-elevated">
              <Th>Sector</Th>
              <Th align="right">Confirmed</Th>
              <Th align="right">Total</Th>
              <Th align="right">% Confirmed</Th>
              <Th align="right">ΔStruct</Th>
              <Th>Structural Trend</Th>
            </tr>
          </thead>
          <tbody>
            {[...rows].sort((a, b) => b.structural_score - a.structural_score).map((r) => {
              const highConf = r.pct_confirmed > 60
              const lowConf  = r.pct_confirmed < 20
              return (
                <tr
                  key={r.sector}
                  className="border-b border-surface-elevated/50 transition-colors hover:bg-surface-elevated/20"
                >
                  <td className="py-2 pr-4 text-text-primary font-medium">{r.sector}</td>
                  <Td align="right">{r.confirmed}</Td>
                  <Td align="right">{r.total}</Td>
                  <Td align="right">
                    <span className={
                      highConf ? 'text-teal-400' :
                      lowConf  ? 'text-zinc-500' :
                      'text-text-secondary'
                    }>
                      {r.pct_confirmed.toFixed(1)}%
                    </span>
                  </Td>
                  <Td align="right">
                    <DeltaScore v={r.delta_structural ?? null} />
                  </Td>
                  <td className="py-2 pr-4 text-text-secondary">
                    {(() => { const t = derivedStructuralTrend(r); return (<><TrendIcon trend={t} /><span className="ml-1">{t === 'rising' ? 'expanding' : t === 'falling' ? 'contracting' : 'stable'}</span></>) })()}
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
    </div>
  )
}

/** Section 2 of sector panel — opportunity quality (edge + risk-adj dispersion). */
function SectorOpportunityTable({ rows }: { rows: SectorBreadthRow[] }) {
  return (
    <div className="space-y-2">
      <h4 className="text-xs font-semibold text-text-secondary uppercase tracking-wider">
        Sector Opportunity Quality
      </h4>
      <div className="overflow-x-auto">
        <table className="w-full text-xs">
          <thead>
            <tr className="border-b border-surface-elevated">
              <Th>Sector</Th>
              <Th align="right">Avg Risk-Adj Edge</Th>
              <Th align="right">% Positive Edge</Th>
              <Th align="right">Median Stop</Th>
              <Th align="right">Tier 2</Th>
              <Th align="right">ΔOpp</Th>
              <Th>Opp. Trend</Th>
            </tr>
          </thead>
          <tbody>
            {[...rows].sort((a, b) => b.opportunity_score - a.opportunity_score).map((r) => (
              <tr
                key={r.sector}
                className="border-b border-surface-elevated/50 transition-colors hover:bg-surface-elevated/20"
              >
                <td className="py-2 pr-4 text-text-primary font-medium">{r.sector}</td>
                <Td align="right">
                  <span className={
                    r.avg_edge_pct > 0 ? 'text-emerald-400' :
                    r.avg_edge_pct < 0 ? 'text-red-400/70'  :
                    'text-text-secondary'
                  }>
                    {r.avg_edge_pct > 0 ? '+' : ''}{r.avg_edge_pct.toFixed(1)}%
                  </span>
                </Td>
                <Td align="right">
                  <span className="text-text-secondary">
                    {(r.positive_edge_ratio * 100).toFixed(0)}%
                  </span>
                </Td>
                <Td align="right">
                  <span className={
                    r.median_stop_pct > 40 ? 'text-amber-400' :
                    r.median_stop_pct < 25 ? 'text-emerald-400/80' :
                    'text-text-secondary'
                  }>
                    {r.median_stop_pct.toFixed(1)}%
                  </span>
                </Td>
                <Td align="right">
                  <span className={r.tier2 > 0 ? 'text-amber-400' : 'text-text-secondary'}>
                    {r.tier2}
                  </span>
                </Td>
                <Td align="right">
                  <DeltaScore v={r.delta_opp ?? null} />
                </Td>
                <td className="py-2 pr-4 text-text-secondary">
                  {(() => { const t = derivedOppTrend(r); return (<><TrendIcon trend={t} /><span className="ml-1">{t === 'rising' ? 'expanding' : t === 'falling' ? 'contracting' : 'stable'}</span></>) })()}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}

function SectorBreadthTable({
  rows,
  leadership,
  rotationSignalLeaders,
  rotationMomentumLeaders,
  hasSectorHistory,
  hasRotationMomentum,
  coverageLabel,
  adminMode,
}: {
  rows: SectorBreadthRow[]
  leadership: SectorLeadershipEntry[]
  rotationSignalLeaders: RotationSignalLeader[]
  rotationMomentumLeaders: RotationMomentumLeader[]
  hasSectorHistory: boolean
  hasRotationMomentum: boolean
  coverageLabel?: string
  adminMode?: boolean
}) {
  return (
    <div className="space-y-6">
      <h3 className="text-sm font-semibold text-text-primary uppercase tracking-wider">
        Sector Flow
      </h3>

      {rows.length === 0 ? (
        <p className="text-xs text-text-secondary">No sector data available.</p>
      ) : (
        <>
          {/* Rotation Flow Summary Strip — Inflow/Outflow chips */}
          {hasRotationMomentum && (
            <FlowSummaryStrip leaders={rotationMomentumLeaders} />
          )}

          {/* Composite rotation leaderboard (top 3) */}
          <SectorLeadershipBlock
            entries={leadership}
            coverageLabel={coverageLabel}
            hasDelta={hasSectorHistory}
          />

          {/* Structural breadth bar chart */}
          <SectorBreadthChart rows={rows} />

          {/* Two-Layer Sector Panel — structural + opportunity side by side */}
          <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
            <SectorStructuralTable rows={rows} />
            <SectorOpportunityTable rows={rows} />
          </div>

          {/* Rotation Signal Panel (raw delta) — when prior snapshot exists */}
          {hasSectorHistory && rotationSignalLeaders.length > 0 && (
            <RotationSignalPanel leaders={rotationSignalLeaders} />
          )}

          {/* Rotation Momentum Table (EWMA-smoothed) */}
          <RotationMomentumTable rows={rows} hasMomentum={hasRotationMomentum} />

          {/* Flow Map Scatter — structural vs opportunity, sized + colored by flow */}
          <FlowMapScatter rows={rows} hasMomentum={hasRotationMomentum} />

          {/* Admin diagnostic footer */}
          {adminMode && (
            <p className="text-xs text-text-secondary/50 text-right">
              Rotation score weights: 60% opportunity / 40% structural.
            </p>
          )}
        </>
      )}
    </div>
  )
}

// ── Section 4: Capital Deployment Guidance ────────────────────────────────────

function RegimeExposureGuidance({
  regime,
  ceiling,
  tier_counts,
}: {
  regime: RegimeType
  ceiling: number
  tier_counts: Record<number, number>
}) {
  const regimeColor =
    regime === 'Risk-Off'    ? 'text-zinc-400' :
    regime === 'Transitional'? 'text-amber-400' :
    'text-teal-400'

  const borderColor =
    regime === 'Risk-Off'    ? 'border-zinc-600/40' :
    regime === 'Transitional'? 'border-amber-600/40' :
    'border-teal-600/40'

  const t1 = tier_counts[1] ?? 0
  const t2 = tier_counts[2] ?? 0
  const t3 = tier_counts[3] ?? 0

  const tierDisplay = (
    <div className="space-y-1">
      <div className="flex items-center gap-3 font-mono text-sm">
        <span className={`font-semibold ${t1 > 0 ? 'text-emerald-400' : 'text-zinc-500'}`}>
          T1: {t1}
        </span>
        <span className="text-zinc-600">·</span>
        <span className={`font-semibold ${t2 > 0 ? 'text-amber-400' : 'text-zinc-500'}`}>
          T2: {t2}
        </span>
        <span className="text-zinc-600">·</span>
        <span className={`font-semibold ${t3 > 0 ? 'text-zinc-400' : 'text-zinc-600'}`}>
          T3: {t3}
        </span>
      </div>
      <p className="text-xs text-text-secondary">eligible / near-miss / watch</p>
    </div>
  )

  const regimeNote =
    regime === 'Risk-Off'
      ? 'Preserve capital until structural conditions improve.'
      : regime === 'Transitional'
      ? 'Deploy selectively in highest-conviction names only.'
      : 'Active deployment permitted according to upside rank and stability.'

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
            <p className="text-xs text-text-secondary mb-1">Allocation Tiers</p>
            {tierDisplay}
          </div>
        </div>

        <div className="border-t border-surface-elevated pt-3">
          <p className="text-xs text-text-secondary leading-relaxed">
            {regime === 'Risk-Off'
              ? `Risk-Off regime: structural conditions do not support broad capital deployment. Maximum portfolio exposure capped at ${ceiling}%. Preserve capital until structural confirmation rates improve.`
              : regime === 'Transitional'
              ? `Transitional regime: conditions are mixed. Deploy selectively in highest-conviction names only. Maximum portfolio exposure capped at ${ceiling}%.`
              : `Risk-On regime: structural conditions support active capital deployment. Maximum portfolio exposure extended to ${ceiling}%. Deploy according to upside rank and stability.`
            }
          </p>
        </div>
      </div>
    </div>
  )
}

// ── Pipeline Funnel ────────────────────────────────────────────────────────────
// Requirement A: explicit evaluated → structural confirmed → allocation eligible counts

function PipelineFunnel({ diag }: { diag: EligibilityDiagnostics }) {
  const steps = [
    {
      label: 'Evaluated Universe',
      count: diag.evaluated_count,
      color: 'text-text-primary',
    },
    {
      label: 'Structural Confirmed',
      count: diag.confirmed_count,
      color: 'text-teal-400',
    },
    {
      label: 'Allocation Eligible',
      count: diag.eligible_count,
      color: diag.eligible_count > 0 ? 'text-emerald-400' : 'text-zinc-500',
    },
  ]

  return (
    <div className="rounded-lg border border-surface-elevated bg-surface/50 px-4 py-3">
      <p className="text-xs font-semibold text-text-secondary uppercase tracking-wide mb-2.5">
        Eligibility Pipeline
      </p>
      <div className="flex flex-wrap items-center gap-x-3 gap-y-2">
        {steps.map((step, i) => (
          <React.Fragment key={step.label}>
            {i > 0 && <span className="text-zinc-600 text-sm select-none">›</span>}
            <div className="flex items-baseline gap-1.5">
              <span className={`text-base font-mono font-bold ${step.color}`}>{step.count}</span>
              <span className="text-xs text-text-secondary">{step.label}</span>
            </div>
          </React.Fragment>
        ))}
      </div>
    </div>
  )
}

// ── Eligibility Rule List ──────────────────────────────────────────────────────
// Requirement B: human-readable rule list with exact thresholds

const ELIGIBILITY_RULES = [
  { label: 'Structural Gate', requirement: 'Confirmation score ≥ 4 of 5 moat components' },
  { label: 'Conviction Delta', requirement: 'Allocation delta > 0% vs prior 30-day run' },
  { label: 'Upside Rank', requirement: 'Risk-Adj Upside ≥ 60th percentile (universe-wide)' },
  { label: 'Stop Probability', requirement: '≤ 25.0%' },
  { label: 'Regime Stability', requirement: 'Not Noise-Dominated or High-Noise' },
] as const

function EligibilityRuleList() {
  return (
    <div className="space-y-2">
      <h4 className="text-xs font-semibold text-text-secondary uppercase tracking-wide">
        Allocation Eligibility Requires (all must pass)
      </h4>
      <div className="rounded-lg border border-surface-elevated bg-surface divide-y divide-surface-elevated/70">
        {ELIGIBILITY_RULES.map((rule) => (
          <div key={rule.label} className="flex items-start gap-3 px-3 py-2">
            <span className="text-teal-400 text-xs mt-0.5 shrink-0">✓</span>
            <div>
              <span className="text-xs font-medium text-text-primary">{rule.label}:</span>
              {' '}
              <span className="text-xs text-text-secondary">{rule.requirement}</span>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}

// ── Failure Reason Breakdown ───────────────────────────────────────────────────
// Requirement C: why structurally confirmed tickers are not allocation-eligible

function FailureReasonBreakdown({ diag }: { diag: EligibilityDiagnostics }) {
  if (diag.confirmed_count === 0 || diag.failure_reasons.length === 0) return null

  return (
    <div className="space-y-2">
      <h4 className="text-xs font-semibold text-text-secondary uppercase tracking-wide">
        Why Not Eligible? — out of {diag.confirmed_count} structurally confirmed
      </h4>
      <div className="space-y-1.5">
        {diag.failure_reasons.map((reason) => {
          const barPct = diag.confirmed_count > 0
            ? Math.round((reason.count / diag.confirmed_count) * 100)
            : 0
          return (
            <div key={reason.rule} className="rounded-md border border-surface-elevated bg-surface px-3 py-2.5">
              <div className="flex items-center justify-between mb-1.5">
                <div>
                  <span className="text-xs font-medium text-text-primary">{reason.label}</span>
                  <span className="text-xs text-text-secondary ml-1.5">({reason.threshold_desc})</span>
                </div>
                <span className="text-sm font-mono font-bold text-amber-400 ml-3 shrink-0">
                  {reason.count}
                </span>
              </div>
              {/* Progress bar */}
              <div className="h-1 rounded-full bg-surface-elevated overflow-hidden">
                <div
                  className="h-full rounded-full bg-amber-500/50 transition-all duration-500"
                  style={{ width: `${barPct}%` }}
                />
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}

// ── Near Miss Table ────────────────────────────────────────────────────────────
// Requirement D: top 10 tickers closest to eligibility with gap details

const RULE_LABELS: Record<string, string> = {
  vol_adj_ev_percentile:  'Upside Rank',
  stop_probability:       'Stop Prob',
  allocation_delta_positive: 'Delta',
  regime_stable:          'Regime',
}

function formatGap(rule: string, metrics: Record<string, number>): string {
  switch (rule) {
    case 'vol_adj_ev_percentile': {
      const actual = metrics['vol_adj_ev_percentile']
      return actual != null ? `${actual.toFixed(0)}th vs ≥60th` : '—'
    }
    case 'stop_probability': {
      const actual = metrics['stop_probability']
      return actual !== undefined ? `${actual.toFixed(1)}% vs ≤25.0%` : '—'
    }
    case 'allocation_delta_positive': {
      const actual = metrics['allocation_delta_30d']
      if (actual === undefined) return 'No prior data'
      return actual <= 0 ? `${actual.toFixed(2)}% (needs > 0%)` : '—'
    }
    case 'regime_stable':
      return 'Noise-Dominated'
    default:
      return '—'
  }
}

function TierBadge({ tier }: { tier: number }) {
  if (tier === 2) {
    return (
      <span className="inline-flex items-center rounded px-1.5 py-0.5 text-xs font-semibold font-mono bg-amber-500/15 text-amber-400 border border-amber-500/30">
        T2
      </span>
    )
  }
  if (tier === 3) {
    return (
      <span className="inline-flex items-center rounded px-1.5 py-0.5 text-xs font-semibold font-mono bg-zinc-500/15 text-zinc-400 border border-zinc-500/30">
        T3
      </span>
    )
  }
  return (
    <span className="inline-flex items-center rounded px-1.5 py-0.5 text-xs font-semibold font-mono bg-zinc-800/50 text-zinc-600 border border-zinc-700/30">
      T{tier}
    </span>
  )
}

function NearMissTable({ diag }: { diag: EligibilityDiagnostics }) {
  if (diag.near_misses.length === 0) return null

  return (
    <div className="space-y-2">
      <h4 className="text-xs font-semibold text-text-secondary uppercase tracking-wide">
        Top Near Misses — Tier 2 First
      </h4>
      <div className="overflow-x-auto">
        <table className="w-full text-xs">
          <thead>
            <tr className="border-b border-surface-elevated">
              <Th>Tier</Th>
              <Th>Ticker</Th>
              <Th>Failing Rule(s)</Th>
              <Th>Metric vs Threshold</Th>
              <Th>Suggested Focus</Th>
            </tr>
          </thead>
          <tbody>
            {diag.near_misses.map((nm) => {
              const primaryRule = nm.failing_rules[0]
              const extraCount  = nm.failing_rules.length - 1
              return (
                <tr
                  key={nm.ticker}
                  className="border-b border-surface-elevated/50 hover:bg-surface-elevated/30 transition-colors"
                >
                  <td className="py-2 pr-3 whitespace-nowrap">
                    <TierBadge tier={nm.tier} />
                  </td>
                  <td className="py-2 pr-4 font-mono font-semibold text-text-primary">{nm.ticker}</td>
                  <td className="py-2 pr-4 text-text-secondary whitespace-nowrap">
                    {RULE_LABELS[primaryRule] ?? primaryRule}
                    {extraCount > 0 && (
                      <span className="ml-1 text-zinc-500">+{extraCount}</span>
                    )}
                  </td>
                  <td className="py-2 pr-4 text-text-secondary font-mono whitespace-nowrap">
                    {formatGap(primaryRule, nm.metric_values)}
                  </td>
                  <td className="py-2 pr-4 text-text-secondary italic whitespace-nowrap">
                    {nm.suggested_action}
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
    </div>
  )
}

// ── Eligibility Diagnostics Section ───────────────────────────────────────────
// Combines rule list + failure breakdown + near misses into one collated section.

const ELIGIBILITY_CONTEXT_NOTE =
  'Structural confirmation indicates market regime support. ' +
  'Allocation eligibility requires favorable risk-adjusted upside rank + stability at current prices. ' +
  'A Risk-On regime can still produce zero eligible targets when valuations are extended.'

function EligibilityDiagnosticsSection({ diag }: { diag: EligibilityDiagnostics }) {
  const hasGap = diag.confirmed_count > 0 && diag.eligible_count < diag.confirmed_count

  return (
    <div className="space-y-5">
      <h3 className="text-sm font-semibold text-text-primary uppercase tracking-wider">
        Eligibility Diagnostics
      </h3>

      {/* Context note */}
      <div className="rounded-md border border-zinc-700/40 bg-zinc-900/30 px-4 py-3">
        <p className="text-xs text-text-secondary leading-relaxed italic">
          {ELIGIBILITY_CONTEXT_NOTE}
        </p>
      </div>

      {/* B: Rule list */}
      <EligibilityRuleList />

      {/* C: Failure reason breakdown — only when there are confirmed-but-not-eligible names */}
      {hasGap && <FailureReasonBreakdown diag={diag} />}

      {/* D: Near miss table */}
      {diag.near_misses.length > 0 && <NearMissTable diag={diag} />}
    </div>
  )
}

// ── Layout primitives ──────────────────────────────────────────────────────────

/** SSR-safe localStorage-backed state. */
function useLocalStorage<T>(key: string, defaultVal: T): [T, (v: T) => void] {
  const [val, setVal] = React.useState<T>(() => {
    if (typeof window === 'undefined') return defaultVal
    try {
      const s = localStorage.getItem(key)
      return s !== null ? (JSON.parse(s) as T) : defaultVal
    } catch { return defaultVal }
  })
  const set = React.useCallback((v: T) => {
    setVal(v)
    try { localStorage.setItem(key, JSON.stringify(v)) } catch { /* ignore */ }
  }, [key])
  return [val, set]
}

/** Collapsible section with chevron toggle + optional badge. */
function AccordionSection({
  title, badge, isOpen, onToggle, children,
}: {
  title: string
  badge?: React.ReactNode
  isOpen: boolean
  onToggle: () => void
  children: React.ReactNode
}) {
  return (
    <div>
      <button
        onClick={onToggle}
        className="w-full flex items-center justify-between px-6 py-4 hover:bg-surface-elevated/20 transition-colors text-left"
      >
        <div className="flex items-center gap-3 min-w-0">
          <span className="text-sm font-semibold text-text-primary uppercase tracking-wider truncate">
            {title}
          </span>
          {badge}
        </div>
        <ChevronDown
          className={`h-4 w-4 text-text-secondary transition-transform duration-200 shrink-0 ml-2 ${
            isOpen ? 'rotate-180' : ''
          }`}
        />
      </button>
      {isOpen && (
        <div className="px-6 pb-6 space-y-6">
          {children}
        </div>
      )}
    </div>
  )
}

/** Horizontal tab navigation strip. */
function TabBar({
  tabs, activeTab, onChange,
}: {
  tabs: { id: string; label: string }[]
  activeTab: string
  onChange: (id: string) => void
}) {
  return (
    <div className="flex border-b border-surface-elevated overflow-x-auto -mx-0.5">
      {tabs.map((tab) => (
        <button
          key={tab.id}
          onClick={() => onChange(tab.id)}
          className={`px-4 py-2.5 text-xs font-medium whitespace-nowrap transition-colors border-b-2 ${
            activeTab === tab.id
              ? 'border-teal-500 text-teal-400'
              : 'border-transparent text-text-secondary hover:text-text-primary'
          }`}
        >
          {tab.label}
        </button>
      ))}
    </div>
  )
}

/** Compact sticky strip visible while scrolling. */
function StickyCapitalHeader({
  gate, index, regime, diag, cacheLabel, ttlLabel, adminMode, onDrawerOpen,
}: {
  gate: boolean
  index: number
  regime: RegimeType
  diag: EligibilityDiagnostics
  cacheLabel: string
  ttlLabel: string | null
  adminMode: boolean
  onDrawerOpen: () => void
}) {
  const t1 = diag.tier_counts[1] ?? 0
  const t2 = diag.tier_counts[2] ?? 0
  const t3 = diag.tier_counts[3] ?? 0
  const regimeColor =
    regime === 'Risk-Off'     ? 'text-zinc-400' :
    regime === 'Transitional' ? 'text-amber-400' : 'text-teal-400'

  return (
    <div className="sticky top-0 z-20 bg-background/95 backdrop-blur-sm border-b border-surface-elevated px-4 sm:px-6 py-2">
      <div className="flex items-center justify-between gap-3 flex-wrap">
        {/* Gate + Index + Regime */}
        <div className="flex items-center gap-2.5 shrink-0">
          {gate
            ? <ShieldCheck className="h-3.5 w-3.5 text-teal-400" />
            : <ShieldOff   className="h-3.5 w-3.5 text-zinc-500" />
          }
          <span className={`text-xs font-bold ${gate ? 'text-teal-400' : 'text-zinc-500'}`}>
            {gate ? 'OPEN' : 'CLOSED'}
          </span>
          <span className="text-zinc-700 select-none">·</span>
          <span className="font-mono text-sm font-bold text-text-primary">{index}</span>
          <span className="text-xs text-text-secondary hidden sm:inline">MDI</span>
          <span className="text-zinc-700 select-none">·</span>
          <span className={`text-xs font-semibold ${regimeColor}`}>{regime}</span>
        </div>

        {/* Pipeline + tiers */}
        <div className="flex items-center gap-1.5 text-xs font-mono shrink-0">
          <span className="text-text-secondary">{diag.evaluated_count}</span>
          <span className="text-zinc-600">›</span>
          <span className="text-teal-400">{diag.confirmed_count}</span>
          <span className="text-zinc-700">·</span>
          <span className={t1 > 0 ? 'text-emerald-400' : 'text-zinc-600'}>T1:{t1}</span>
          <span className={t2 > 0 ? 'text-amber-400'  : 'text-zinc-600'}>T2:{t2}</span>
          <span className={t3 > 0 ? 'text-zinc-400'   : 'text-zinc-700'}>T3:{t3}</span>
        </div>

        {/* Timer + drawer */}
        <div className="flex items-center gap-2.5 ml-auto">
          <span className="text-xs text-text-secondary opacity-60 hidden sm:inline">{cacheLabel}</span>
          {ttlLabel && <span className="text-xs text-text-secondary opacity-40 hidden md:inline">{ttlLabel}</span>}
          {adminMode && (
            <button
              onClick={onDrawerOpen}
              className="text-xs text-zinc-500 hover:text-zinc-300 border border-zinc-700/60 rounded px-2 py-1 transition-colors"
            >
              Debug ▸
            </button>
          )}
        </div>
      </div>
    </div>
  )
}

/** Section B: T1 table + T2 near-miss (expanded) + T3 watchlist (collapsed). */
function TierNearMissRows({ items }: { items: NearMissTicker[] }) {
  if (items.length === 0) return null
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-xs">
        <thead>
          <tr className="border-b border-surface-elevated">
            <Th>Tier</Th>
            <Th>Ticker</Th>
            <Th>Failing Rule</Th>
            <Th>Metric vs Threshold</Th>
            <Th>Suggested Focus</Th>
          </tr>
        </thead>
        <tbody>
          {items.map((nm) => {
            const primaryRule = nm.failing_rules[0]
            const extraCount  = nm.failing_rules.length - 1
            return (
              <tr key={nm.ticker} className="border-b border-surface-elevated/50 hover:bg-surface-elevated/30 transition-colors">
                <td className="py-2 pr-3 whitespace-nowrap"><TierBadge tier={nm.tier} /></td>
                <td className="py-2 pr-4 font-mono font-semibold text-text-primary">{nm.ticker}</td>
                <td className="py-2 pr-4 text-text-secondary whitespace-nowrap">
                  {RULE_LABELS[primaryRule] ?? primaryRule}
                  {extraCount > 0 && <span className="ml-1 text-zinc-500">+{extraCount}</span>}
                </td>
                <td className="py-2 pr-4 text-text-secondary font-mono whitespace-nowrap">
                  {formatGap(primaryRule, nm.metric_values)}
                </td>
                <td className="py-2 pr-4 text-text-secondary italic whitespace-nowrap">
                  {nm.suggested_action}
                </td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}

function TieredNamesSection({
  tickers, nearMisses, noDeployableMessage,
}: {
  tickers: DeployableTickerItem[]
  nearMisses: NearMissTicker[]
  noDeployableMessage: string | null
}) {
  const [t2Open, setT2Open] = React.useState(true)
  const [t3Open, setT3Open] = React.useState(false)
  const t2Items = nearMisses.filter((nm) => nm.tier === 2)
  const t3Items = nearMisses.filter((nm) => nm.tier === 3)

  return (
    <div className="space-y-5">
      {/* T1 */}
      <div className="space-y-2">
        <p className="text-xs font-semibold text-text-secondary uppercase tracking-wide">
          Tier 1 — Confirmed Deployable
          <span className={`ml-2 font-mono font-bold ${tickers.length > 0 ? 'text-emerald-400' : 'text-zinc-600'}`}>
            {tickers.length}
          </span>
        </p>
        <DeployableTickersGrid tickers={tickers} noDeployableMessage={noDeployableMessage} />
      </div>

      {/* T2 */}
      {t2Items.length > 0 && (
        <div className="space-y-2">
          <button
            onClick={() => setT2Open(!t2Open)}
            className="flex items-center gap-2 text-xs text-text-secondary hover:text-text-primary transition-colors"
          >
            <ChevronDown className={`h-3.5 w-3.5 transition-transform ${t2Open ? 'rotate-180' : ''}`} />
            <span className="font-semibold uppercase tracking-wide">Tier 2 — Near Miss</span>
            <span className="font-mono font-bold text-amber-400">{t2Items.length}</span>
            <span className="opacity-50">(1 rule away)</span>
          </button>
          {t2Open && <TierNearMissRows items={t2Items} />}
        </div>
      )}

      {/* T3 */}
      {t3Items.length > 0 && (
        <div className="space-y-2">
          <button
            onClick={() => setT3Open(!t3Open)}
            className="flex items-center gap-2 text-xs text-text-secondary hover:text-text-primary transition-colors"
          >
            <ChevronDown className={`h-3.5 w-3.5 transition-transform ${t3Open ? 'rotate-180' : ''}`} />
            <span className="font-semibold uppercase tracking-wide">Tier 3 — Watchlist</span>
            <span className="font-mono font-bold text-zinc-400">{t3Items.length}</span>
            <span className="opacity-50">(2 rules away)</span>
          </button>
          {t3Open && <TierNearMissRows items={t3Items} />}
        </div>
      )}
    </div>
  )
}

/** Section C: tabbed diagnostics. Lazy-renders tabs until first open. */
function DiagnosticsTabContent({
  diag, sectorRows, sectorLeadership, rotationSignalLeaders,
  rotationMomentumLeaders, hasSectorHistory, hasRotationMomentum,
  coverageLabel, adminMode, activeTab, onTabChange,
}: {
  diag: EligibilityDiagnostics
  sectorRows: SectorBreadthRow[]
  sectorLeadership: SectorLeadershipEntry[]
  rotationSignalLeaders: RotationSignalLeader[]
  rotationMomentumLeaders: RotationMomentumLeader[]
  hasSectorHistory: boolean
  hasRotationMomentum: boolean
  coverageLabel?: string
  adminMode: boolean
  activeTab: string
  onTabChange: (id: string) => void
}) {
  // Track which tabs have ever been opened so we keep their state alive
  const [mounted, setMounted] = React.useState<Record<string, boolean>>({
    [activeTab]: true,
  })
  React.useEffect(() => {
    setMounted((prev) => ({ ...prev, [activeTab]: true }))
  }, [activeTab])

  const baseTabs = [
    { id: 'why-not',      label: 'Why Not Eligible' },
    { id: 'sector-flow',  label: 'Sector Flow' },
  ]
  const adminTabs = adminMode ? [
    { id: 'stress-test',   label: 'Stress Test' },
    { id: 'distributions', label: 'Distributions' },
    { id: 'calibration',   label: 'Calibration' },
  ] : []
  const tabs = [...baseTabs, ...adminTabs]
  // Migrate old 'sector-breadth' saved tab ID to 'sector-flow'
  const safeActive = tabs.find((t) => t.id === activeTab)
    ? activeTab
    : activeTab === 'sector-breadth' ? 'sector-flow' : 'why-not'

  return (
    <div className="space-y-4">
      <TabBar tabs={tabs} activeTab={safeActive} onChange={onTabChange} />

      {/* Why Not Eligible */}
      <div className={safeActive === 'why-not' ? '' : 'hidden'}>
        {mounted['why-not'] && (
          <div className="space-y-5 pt-1">
            <div className="rounded-md border border-zinc-700/40 bg-zinc-900/30 px-4 py-3">
              <p className="text-xs text-text-secondary leading-relaxed italic">
                {ELIGIBILITY_CONTEXT_NOTE}
              </p>
            </div>
            <EligibilityRuleList />
            {diag.confirmed_count > 0 && diag.eligible_count < diag.confirmed_count && (
              <FailureReasonBreakdown diag={diag} />
            )}
          </div>
        )}
      </div>

      {/* Sector Flow */}
      <div className={safeActive === 'sector-flow' ? '' : 'hidden'}>
        {(mounted['sector-flow'] || mounted['sector-breadth']) && (
          <div className="pt-1">
            <SectorBreadthTable
              rows={sectorRows}
              leadership={sectorLeadership}
              rotationSignalLeaders={rotationSignalLeaders}
              rotationMomentumLeaders={rotationMomentumLeaders}
              hasSectorHistory={hasSectorHistory}
              hasRotationMomentum={hasRotationMomentum}
              coverageLabel={coverageLabel}
              adminMode={adminMode}
            />
          </div>
        )}
      </div>

      {/* Stress Test (admin, lazy) */}
      {adminMode && (
        <div className={safeActive === 'stress-test' ? '' : 'hidden'}>
          {mounted['stress-test'] && (
            <div className="space-y-6 pt-1">
              <EligibilityStressTestPanel />
              <EligibilityRollingSimPanel />
            </div>
          )}
        </div>
      )}

      {/* Distributions (admin, lazy) */}
      {adminMode && (
        <div className={safeActive === 'distributions' ? '' : 'hidden'}>
          {mounted['distributions'] && (
            <div className="pt-1">
              <OpportunityDistributionPanel />
            </div>
          )}
        </div>
      )}

      {/* Calibration (admin, lazy) */}
      {adminMode && (
        <div className={safeActive === 'calibration' ? '' : 'hidden'}>
          {mounted['calibration'] && (
            <div className="pt-1">
              <ThresholdCalibrationPanel />
            </div>
          )}
        </div>
      )}
    </div>
  )
}

/** Admin-only slide-over with snapshot metadata + pipeline integrity. */
function DiagnosticsDrawer({
  isOpen, onClose, data, deployIndex, regime,
}: {
  isOpen: boolean
  onClose: () => void
  data: DeploymentUpdateResponse
  deployIndex: number
  regime: RegimeType
}) {
  if (!isOpen) return null
  const regimeCls =
    regime === 'Risk-On'      ? 'text-teal-400' :
    regime === 'Transitional' ? 'text-amber-400' : 'text-zinc-400'

  return (
    <>
      <div className="fixed inset-0 z-30 bg-black/40" onClick={onClose} />
      <div className="fixed right-0 top-0 h-full w-72 z-40 bg-[#0d1117] border-l border-surface-elevated overflow-y-auto shadow-2xl">
        <div className="flex items-center justify-between px-4 py-3 border-b border-surface-elevated">
          <h3 className="text-xs font-semibold text-text-primary uppercase tracking-wider">Snapshot Debug</h3>
          <button onClick={onClose} className="text-text-secondary hover:text-text-primary transition-colors">
            <X className="h-4 w-4" />
          </button>
        </div>
        <div className="p-4 space-y-5 text-xs">
          <section className="space-y-2">
            <h4 className="font-semibold text-text-secondary uppercase tracking-wide">Snapshot Metadata</h4>
            <dl className="space-y-1.5">
              {([
                ['Snapshot ID', data.snapshot_id.slice(0, 13) + '…'],
                ['Model',       data.model_version],
                ['Ruleset',     data.ruleset_version],
                ['Cache Age',   `${data.cache_age_hours.toFixed(1)}h`],
              ] as [string, string][]).map(([lbl, val]) => (
                <div key={lbl} className="flex justify-between gap-4">
                  <dt className="text-text-secondary">{lbl}</dt>
                  <dd className="font-mono text-text-primary">{val}</dd>
                </div>
              ))}
            </dl>
          </section>
          <section className="space-y-2">
            <h4 className="font-semibold text-text-secondary uppercase tracking-wide">Pipeline Integrity</h4>
            <dl className="space-y-1.5">
              <div className="flex justify-between"><dt className="text-text-secondary">Universe</dt><dd className="font-mono text-text-primary">{data.universe_size}</dd></div>
              <div className="flex justify-between"><dt className="text-text-secondary">Confirmed</dt><dd className="font-mono text-teal-400">{data.confirmed_count}</dd></div>
              <div className="flex justify-between"><dt className="text-text-secondary">Eligible</dt><dd className="font-mono text-emerald-400">{data.eligible_count}</dd></div>
              <div className="flex justify-between"><dt className="text-text-secondary">MDI</dt><dd className="font-mono text-text-primary">{deployIndex}</dd></div>
              <div className="flex justify-between"><dt className="text-text-secondary">Regime</dt><dd className={`font-mono ${regimeCls}`}>{regime}</dd></div>
            </dl>
          </section>
          <section className="space-y-2">
            <h4 className="font-semibold text-text-secondary uppercase tracking-wide">Data Coverage</h4>
            <p className="text-text-secondary">{data.sector_coverage_label}</p>
          </section>
        </div>
      </div>
    </>
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

export function StructuralDeploymentUpdate({ adminMode = false }: { adminMode?: boolean }) {
  const { data: entitlements } = useEntitlements()
  const hasAccess = adminMode || (entitlements?.features['feature.deployment.structural_update'] ?? false)

  const userResult  = useDeploymentUpdate(!adminMode && hasAccess)
  const adminResult = useAdminDeploymentUpdate(adminMode)
  const { data, isLoading, error } = adminMode ? adminResult : userResult

  // ── Persistent accordion + tab state ─────────────────────────────────────────
  const [overviewOpen, setOverviewOpen] = useLocalStorage('deploy_overview', true)
  const [namesOpen,    setNamesOpen]    = useLocalStorage('deploy_names',    true)
  const [diagOpen,     setDiagOpen]     = useLocalStorage('deploy_diag',     false)
  const [diagTab,      setDiagTab]      = useLocalStorage('deploy_diag_tab', 'why-not')
  const [drawerOpen,   setDrawerOpen]   = React.useState(false)

  if (!adminMode && entitlements && !hasAccess) return <LockedCard />
  if ((!adminMode && !entitlements) || isLoading)  return <LoadingSkeleton />

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

  // ── Derived values ────────────────────────────────────────────────────────────
  const avgBreadthPct   = getAvgBreadthPct(data.sector_breadth)
  const deployIndex     = getDeployabilityIndex(data.snapshot, avgBreadthPct)
  const regime          = getRegime(deployIndex)
  const exposureCeiling = getRegimeExposureCeiling(regime)
  const gateOpen        = data.snapshot.pct_universe_confirmed > 0

  const cacheLabel = data.cache_age_hours < 0.1
    ? 'Generated just now'
    : `Generated ${data.cache_age_hours.toFixed(1)}h ago`

  const ttlLabel = (() => {
    try {
      const expires    = new Date(data.ttl_expires_at)
      const hoursUntil = (expires.getTime() - Date.now()) / 3_600_000
      return hoursUntil > 0 ? `Refreshes in ${hoursUntil.toFixed(1)}h` : 'Refresh pending'
    } catch { return null }
  })()

  const tc = data.eligibility_diagnostics.tier_counts
  const t1 = tc[1] ?? 0
  const t2 = tc[2] ?? 0
  const t3 = tc[3] ?? 0

  return (
    <div className="relative">
      {/* ── Sticky summary strip ─────────────────────────────────────────────── */}
      <StickyCapitalHeader
        gate={gateOpen}
        index={deployIndex}
        regime={regime}
        diag={data.eligibility_diagnostics}
        cacheLabel={cacheLabel}
        ttlLabel={ttlLabel}
        adminMode={adminMode}
        onDrawerOpen={() => setDrawerOpen(true)}
      />

      {/* ── Main card with 3 accordion sections ──────────────────────────────── */}
      <Card className="bg-surface border-surface-elevated rounded-t-none border-t-0">
        <CardHeader className="pb-2 pt-4">
          <CardTitle className="text-base font-semibold text-text-primary">
            Capital Control Panel
            {adminMode && (
              <span className="ml-2 text-xs font-normal text-text-secondary border border-surface-elevated rounded px-1.5 py-0.5">
                Platform-Wide
              </span>
            )}
          </CardTitle>
          <p className="text-xs text-text-secondary">
            {adminMode ? 'All users · Structural Deployment Update' : 'Structural Deployment Update'}
          </p>
        </CardHeader>

        <CardContent className="p-0 divide-y divide-surface-elevated">

          {/* ── Section A: Overview ─────────────────────────────────────────── */}
          <AccordionSection
            title="Overview"
            badge={<PostureBadge posture={data.snapshot.capital_posture} />}
            isOpen={overviewOpen}
            onToggle={() => setOverviewOpen(!overviewOpen)}
          >
            <CapitalRegimeStatus
              snapshot={data.snapshot}
              index={deployIndex}
              regime={regime}
              gateOpen={gateOpen}
              diag={data.eligibility_diagnostics}
            />
            {/* Sector Rotation Flow Summary Strip */}
            {(data.has_rotation_momentum ?? false) && (data.rotation_momentum_leaders?.length ?? 0) > 0 && (
              <div className="border-t border-surface-elevated/60 pt-5">
                <FlowSummaryStrip leaders={data.rotation_momentum_leaders ?? []} />
              </div>
            )}
            <div className="border-t border-surface-elevated/60 pt-5">
              <RegimeExposureGuidance
                regime={regime}
                ceiling={exposureCeiling}
                tier_counts={data.eligibility_diagnostics.tier_counts}
              />
            </div>
            <div className="border-t border-surface-elevated/60 pt-5">
              <AllocationEngineStatus gateOpen={gateOpen} />
            </div>
          </AccordionSection>

          {/* ── Section B: Eligible Names ────────────────────────────────────── */}
          <AccordionSection
            title="Eligible Names"
            badge={
              <div className="flex items-center gap-2 font-mono text-xs">
                <span className={t1 > 0 ? 'text-emerald-400' : 'text-zinc-600'}>T1:{t1}</span>
                <span className={t2 > 0 ? 'text-amber-400'  : 'text-zinc-600'}>T2:{t2}</span>
                <span className={t3 > 0 ? 'text-zinc-400'   : 'text-zinc-700'}>T3:{t3}</span>
              </div>
            }
            isOpen={namesOpen}
            onToggle={() => setNamesOpen(!namesOpen)}
          >
            <TieredNamesSection
              tickers={data.deployable_tickers}
              nearMisses={data.eligibility_diagnostics.near_misses}
              noDeployableMessage={data.no_deployable_message}
            />
          </AccordionSection>

          {/* ── Section C: Diagnostics ───────────────────────────────────────── */}
          <AccordionSection
            title="Diagnostics"
            isOpen={diagOpen}
            onToggle={() => setDiagOpen(!diagOpen)}
          >
            {diagOpen && (
              <DiagnosticsTabContent
                diag={data.eligibility_diagnostics}
                sectorRows={data.sector_breadth}
                sectorLeadership={data.sector_leadership ?? []}
                rotationSignalLeaders={data.rotation_signal_leaders ?? []}
                rotationMomentumLeaders={data.rotation_momentum_leaders ?? []}
                hasSectorHistory={data.has_sector_history ?? false}
                hasRotationMomentum={data.has_rotation_momentum ?? false}
                coverageLabel={data.sector_coverage_label}
                adminMode={adminMode}
                activeTab={diagTab}
                onTabChange={setDiagTab}
              />
            )}
          </AccordionSection>

        </CardContent>
      </Card>

      {/* ── Admin debug drawer ────────────────────────────────────────────────── */}
      {adminMode && (
        <DiagnosticsDrawer
          isOpen={drawerOpen}
          onClose={() => setDrawerOpen(false)}
          data={data}
          deployIndex={deployIndex}
          regime={regime}
        />
      )}
    </div>
  )
}
