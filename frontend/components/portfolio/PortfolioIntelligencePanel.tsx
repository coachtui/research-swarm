'use client'

import { usePortfolioIntelligence } from '@/lib/hooks/usePortfolioIntelligence'
import { useEntitlements } from '@/lib/hooks/useEntitlements'
import { canAccessFeature } from '@/lib/entitlements'
import { TierGate } from '@/components/common/TierGate'
import type {
  PortfolioIntelligence,
  PortfolioEdgeScore,
  AlignmentMatrixRow,
  ConcentrationDiagnostics,
  RegimeVulnerability,
  MisalignmentFlag,
} from '@/types/api'

// ── Helpers ──────────────────────────────────────────────────────────────────

function statusColor(status: string): string {
  const map: Record<string, string> = {
    Strong: 'text-success',
    Confirmed: 'text-success',
    Attractive: 'text-success',
    Tailwind: 'text-success',
    Low: 'text-success',
    Mixed: 'text-warning',
    Neutral: 'text-warning',
    Fair: 'text-warning',
    Moderate: 'text-warning',
    Weak: 'text-error',
    Extended: 'text-error',
    Headwind: 'text-error',
    Elevated: 'text-error',
  }
  return map[status] ?? 'text-text-secondary'
}

function statusDot(status: string): string {
  const map: Record<string, string> = {
    Strong: 'bg-success',
    Confirmed: 'bg-success',
    Attractive: 'bg-success',
    Tailwind: 'bg-success',
    Low: 'bg-success',
    Mixed: 'bg-warning',
    Neutral: 'bg-warning',
    Fair: 'bg-warning',
    Moderate: 'bg-warning',
    Weak: 'bg-error',
    Extended: 'bg-error',
    Headwind: 'bg-error',
    Elevated: 'bg-error',
  }
  return map[status] ?? 'bg-text-tertiary'
}

function edgeLabelColor(label: string): string {
  if (label === 'High Conviction Alignment') return 'text-success'
  if (label === 'Constructive') return 'text-primary'
  if (label === 'Neutral') return 'text-warning'
  return 'text-error'
}

function edgeBarColor(score: number): string {
  if (score >= 8) return 'bg-success'
  if (score >= 6) return 'bg-primary'
  if (score >= 4) return 'bg-warning'
  return 'bg-error'
}

// ── PM Memo Card ─────────────────────────────────────────────────────────────

function PMMemoCard({ memo }: { memo: string }) {
  return (
    <div className="rounded-lg border border-border bg-surface p-4 space-y-2">
      <div className="flex items-center gap-2">
        <span className="text-xs font-medium text-text-tertiary uppercase tracking-wider">
          Portfolio Intelligence Summary
        </span>
      </div>
      <p className="text-sm text-text-primary leading-relaxed">{memo}</p>
    </div>
  )
}

// ── Alignment Matrix Card ─────────────────────────────────────────────────────

function AlignmentMatrixCard({ rows }: { rows: AlignmentMatrixRow[] }) {
  return (
    <div className="rounded-lg border border-border bg-surface overflow-hidden">
      <div className="px-4 py-3 border-b border-border">
        <span className="text-xs font-medium text-text-tertiary uppercase tracking-wider">
          Capital Alignment Matrix
        </span>
      </div>
      <div className="divide-y divide-border">
        {rows.map((row) => (
          <div key={row.dimension} className="flex items-center justify-between px-4 py-3">
            <div className="flex items-center gap-2 min-w-0">
              <div className={`w-1.5 h-1.5 rounded-full flex-shrink-0 ${statusDot(row.status)}`} />
              <span className="text-sm text-text-secondary truncate">{row.dimension}</span>
            </div>
            <div className="flex items-center gap-3 flex-shrink-0">
              <span className="text-xs text-text-tertiary">{row.metric_label}</span>
              <span className={`text-sm font-medium ${statusColor(row.status)}`}>
                {row.status}
              </span>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}

// ── Edge Score Gauge ──────────────────────────────────────────────────────────

function EdgeScoreGauge({ edge }: { edge: PortfolioEdgeScore }) {
  const pct = (edge.total / 10) * 100
  const barColor = edgeBarColor(edge.total)
  const labelColor = edgeLabelColor(edge.label)

  const components = [
    { label: 'Structural Quality', value: edge.structural_component, weight: '25%' },
    { label: 'Valuation Attractiveness', value: edge.valuation_component, weight: '25%' },
    { label: 'Dislocation Alignment', value: edge.divergence_component, weight: '20%' },
    { label: 'Regime Positioning', value: edge.regime_component, weight: '15%' },
    { label: 'Concentration (inverse)', value: edge.concentration_score, weight: '15%' },
  ]

  return (
    <div className="rounded-lg border border-border bg-surface p-4 space-y-4">
      {/* Header row */}
      <div className="flex items-center justify-between">
        <span className="text-xs font-medium text-text-tertiary uppercase tracking-wider">
          Portfolio Edge Score
        </span>
        <div className="flex items-center gap-2">
          <span className={`text-xs font-medium ${labelColor}`}>{edge.label}</span>
          <span className="text-2xl font-bold font-mono text-text-primary">
            {edge.total.toFixed(1)}
          </span>
          <span className="text-xs text-text-tertiary">/10</span>
        </div>
      </div>

      {/* Overall bar */}
      <div className="h-2 rounded-full bg-surface-elevated overflow-hidden">
        <div
          className={`h-full rounded-full transition-all duration-500 ${barColor}`}
          style={{ width: `${pct}%` }}
        />
      </div>

      {/* Scale legend — abbreviated on mobile, full on sm+ */}
      <div className="flex justify-between text-[10px] text-text-tertiary">
        <span>Defensive</span>
        <span className="hidden sm:inline">4 Neutral</span>
        <span className="hidden sm:inline">6 Constructive</span>
        <span>High Conv.</span>
      </div>

      {/* Component bars */}
      <div className="space-y-2 pt-1">
        {components.map((c) => (
          <div key={c.label} className="space-y-1">
            <div className="flex items-center justify-between text-xs">
              <span className="text-text-tertiary">{c.label}</span>
              <div className="flex items-center gap-2">
                <span className="text-text-quaternary">{c.weight}</span>
                <span className="font-mono text-text-secondary w-8 text-right">
                  {c.value.toFixed(1)}
                </span>
              </div>
            </div>
            <div className="h-1 rounded-full bg-surface-elevated overflow-hidden">
              <div
                className={`h-full rounded-full ${edgeBarColor(c.value)}`}
                style={{ width: `${(c.value / 10) * 100}%` }}
              />
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}

// ── Concentration Diagnostics ─────────────────────────────────────────────────

function ConcentrationDiagnosticsCard({
  concentration,
  showThematic,
}: {
  concentration: ConcentrationDiagnostics
  showThematic: boolean
}) {
  const sectorEntries = Object.entries(concentration.sector_breakdown).slice(0, 6)
  const thematicEntries = showThematic
    ? Object.entries(concentration.thematic_clusters).slice(0, 6)
    : []

  return (
    <div className="rounded-lg border border-border bg-surface p-4 space-y-4">
      <div className="flex items-center justify-between">
        <span className="text-xs font-medium text-text-tertiary uppercase tracking-wider">
          Concentration Diagnostics
        </span>
        <span className={`text-xs font-medium px-2 py-0.5 rounded-full border ${
          concentration.concentration_label === 'Low'
            ? 'border-success/30 text-success bg-success/5'
            : concentration.concentration_label === 'Moderate'
            ? 'border-warning/30 text-warning bg-warning/5'
            : 'border-error/30 text-error bg-error/5'
        }`}>
          {concentration.concentration_label}
        </span>
      </div>

      {/* Top 3 */}
      <div className="space-y-1.5">
        <span className="text-[10px] font-medium text-text-quaternary uppercase tracking-wider">
          Top Holdings
        </span>
        <div className="space-y-1">
          {concentration.top_3_tickers.map((item, i) => (
            <div key={item.ticker} className="flex items-center gap-2">
              <span className="text-[10px] w-4 text-text-tertiary">{i + 1}.</span>
              <span className="text-sm font-mono font-medium text-text-primary flex-1">
                {item.ticker}
              </span>
              <div className="flex-1 h-1.5 rounded-full bg-surface-elevated overflow-hidden max-w-24">
                <div
                  className="h-full rounded-full bg-primary/60"
                  style={{ width: `${Math.min(item.weight * 2, 100)}%` }}
                />
              </div>
              <span className="text-xs font-mono text-text-secondary w-10 text-right">
                {item.weight.toFixed(1)}%
              </span>
            </div>
          ))}
        </div>
        <p className="text-[10px] text-text-tertiary">
          Top 3 combined: {concentration.top_3_weight_pct.toFixed(1)}%
        </p>
      </div>

      {/* Sector breakdown */}
      <div className="space-y-1.5">
        <span className="text-[10px] font-medium text-text-quaternary uppercase tracking-wider">
          Sector Exposure
        </span>
        <div className="space-y-1">
          {sectorEntries.map(([sector, pct]) => (
            <div key={sector} className="flex items-center gap-2">
              <span className="text-xs text-text-secondary flex-1 truncate">{sector}</span>
              <div className="flex-1 h-1.5 rounded-full bg-surface-elevated overflow-hidden max-w-32">
                <div
                  className="h-full rounded-full bg-accent/70"
                  style={{ width: `${Math.min(pct * 1.5, 100)}%` }}
                />
              </div>
              <span className="text-xs font-mono text-text-secondary w-10 text-right">
                {pct.toFixed(1)}%
              </span>
            </div>
          ))}
        </div>
      </div>

      {/* Thematic clusters (Trader) */}
      {showThematic && thematicEntries.length > 0 && (
        <div className="space-y-1.5">
          <span className="text-[10px] font-medium text-text-quaternary uppercase tracking-wider">
            Thematic Clusters
          </span>
          <div className="flex flex-wrap gap-1.5">
            {thematicEntries.map(([theme, pct]) => (
              <span
                key={theme}
                className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-surface-elevated border border-border text-xs text-text-secondary"
              >
                {theme}
                <span className="font-mono text-text-tertiary">{pct.toFixed(0)}%</span>
              </span>
            ))}
          </div>
        </div>
      )}

      {/* Largest downside impact */}
      {concentration.largest_downside_ticker && (
        <div className="pt-1 border-t border-border/50">
          <p className="text-xs text-text-tertiary">
            Largest single-name downside impact:{' '}
            <span className="font-mono font-medium text-text-secondary">
              {concentration.largest_downside_ticker}
            </span>
            {' '}at{' '}
            <span className="font-mono text-error">
              {concentration.largest_downside_impact_pct.toFixed(1)}%
            </span>{' '}
            portfolio impact
          </p>
        </div>
      )}

      {/* HHI */}
      <p className="text-[10px] text-text-quaternary">
        Herfindahl-Hirschman Index: {concentration.hhi.toFixed(0)} (
        {concentration.hhi < 1500 ? 'diversified' : concentration.hhi < 2500 ? 'moderate' : 'concentrated'})
      </p>
    </div>
  )
}

// ── Regime Vulnerability ──────────────────────────────────────────────────────

function RegimeVulnerabilityCard({ regime }: { regime: RegimeVulnerability }) {
  const drawdown = regime.projected_portfolio_drawdown
  const drawdownColor = drawdown < -20 ? 'text-error' : drawdown < -10 ? 'text-warning' : 'text-text-secondary'
  const regimeColor = regime.regime_label === 'Expansion' ? 'text-success'
    : regime.regime_label === 'Neutral' ? 'text-warning'
    : 'text-error'

  return (
    <div className="rounded-lg border border-border bg-surface p-4 space-y-4">
      <div className="flex items-center justify-between">
        <span className="text-xs font-medium text-text-tertiary uppercase tracking-wider">
          Regime Vulnerability
        </span>
        <span className={`text-xs font-medium ${regimeColor}`}>
          {regime.regime_label}
        </span>
      </div>

      {/* Bear / Bull summary */}
      <div className="grid grid-cols-2 gap-3">
        <div className="rounded-md border border-border/50 bg-surface-elevated p-3 text-center space-y-0.5">
          <div className="text-[10px] text-text-tertiary uppercase tracking-wider">Bear Drawdown</div>
          <div className={`text-xl font-bold font-mono ${drawdownColor}`}>
            {drawdown.toFixed(1)}%
          </div>
          <div className="text-[10px] text-text-quaternary">weighted portfolio impact</div>
        </div>
        <div className="rounded-md border border-border/50 bg-surface-elevated p-3 text-center space-y-0.5">
          <div className="text-[10px] text-text-tertiary uppercase tracking-wider">Bull Upside</div>
          <div className="text-xl font-bold font-mono text-success">
            +{regime.weighted_bull_return.toFixed(1)}%
          </div>
          <div className="text-[10px] text-text-quaternary">weighted portfolio upside</div>
        </div>
      </div>

      {/* Most vulnerable */}
      {regime.most_vulnerable.length > 0 && (
        <div className="space-y-1.5">
          <span className="text-[10px] font-medium text-text-quaternary uppercase tracking-wider">
            Highest Downside Sensitivity
          </span>
          <div className="space-y-1">
            {regime.most_vulnerable.map((item) => (
              <div key={item.ticker} className="flex flex-col sm:flex-row sm:items-center sm:justify-between text-xs gap-0.5 sm:gap-0">
                <span className="font-mono font-medium text-text-primary">{item.ticker}</span>
                <div className="flex items-center gap-2 sm:gap-3 text-text-tertiary flex-wrap">
                  <span>{item.weight_pct.toFixed(1)}% wt</span>
                  <span className="text-error">{item.bear_return_pct.toFixed(1)}% bear</span>
                  <span className="font-mono text-text-secondary">
                    {item.impact_pct.toFixed(1)}% impact
                  </span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Compression risk note */}
      {regime.expansion_compression_risk > 0 && (
        <p className="text-xs text-text-tertiary border-t border-border/50 pt-2">
          Expansion valuation compression risk: {regime.expansion_compression_risk.toFixed(1)}% avg gap on overvalued positions
        </p>
      )}
    </div>
  )
}

// ── Misalignment Flags ────────────────────────────────────────────────────────

function MisalignmentFlagsCard({ flags }: { flags: MisalignmentFlag[] }) {
  if (flags.length === 0) {
    return (
      <div className="rounded-lg border border-border bg-surface p-4">
        <div className="flex items-center gap-2 mb-2">
          <span className="text-xs font-medium text-text-tertiary uppercase tracking-wider">
            Misalignment Detection
          </span>
        </div>
        <p className="text-sm text-success">No misalignment flags detected.</p>
      </div>
    )
  }

  return (
    <div className="rounded-lg border border-border bg-surface p-4 space-y-3">
      <span className="text-xs font-medium text-text-tertiary uppercase tracking-wider">
        Misalignment Detection
      </span>
      <div className="space-y-2">
        {flags.map((flag) => (
          <div
            key={flag.code}
            className={`rounded-md border p-3 space-y-1.5 ${
              flag.severity === 'critical'
                ? 'border-error/30 bg-error/5'
                : 'border-warning/30 bg-warning/5'
            }`}
          >
            <div className="flex items-center gap-2">
              <span
                className={`text-[10px] font-bold uppercase tracking-wider px-1.5 py-0.5 rounded ${
                  flag.severity === 'critical'
                    ? 'text-error bg-error/10'
                    : 'text-warning bg-warning/10'
                }`}
              >
                {flag.severity}
              </span>
              <span className="text-[10px] font-mono text-text-tertiary">{flag.code}</span>
            </div>
            <p className="text-xs text-text-secondary leading-relaxed">{flag.message}</p>
            {flag.affected_tickers.length > 0 && (
              <div className="flex flex-wrap gap-1">
                {flag.affected_tickers.slice(0, 6).map((t) => (
                  <span
                    key={t}
                    className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-surface-elevated border border-border text-text-tertiary"
                  >
                    {t}
                  </span>
                ))}
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  )
}

// ── Loading / Empty States ────────────────────────────────────────────────────

function LoadingState() {
  return (
    <div className="space-y-3">
      {[1, 2, 3].map((i) => (
        <div key={i} className="rounded-lg border border-border bg-surface p-4 h-24 animate-pulse" />
      ))}
    </div>
  )
}

function EmptyState() {
  return (
    <div className="text-center py-12 space-y-2">
      <p className="text-sm text-text-secondary">No positions with analysis data yet.</p>
      <p className="text-xs text-text-tertiary">
        Run analyses on your holdings to unlock portfolio intelligence scoring.
      </p>
    </div>
  )
}

// ── Coverage Banner ───────────────────────────────────────────────────────────

function CoverageBanner({
  positionsWithData,
  positionCount,
}: {
  positionsWithData: number
  positionCount: number
}) {
  if (positionsWithData === positionCount || positionCount === 0) return null

  return (
    <div className="rounded-md border border-warning/30 bg-warning/5 px-3 py-2">
      <p className="text-xs text-warning">
        {positionsWithData}/{positionCount} positions have current analysis data.{' '}
        Scores reflect available coverage only.
      </p>
    </div>
  )
}

// ── Main Panel ────────────────────────────────────────────────────────────────

interface PortfolioIntelligencePanelProps {
  portfolioId: string
  userTier: string | null
  isAdmin?: boolean
}

export function PortfolioIntelligencePanel({
  portfolioId,
  userTier,
  isAdmin = false,
}: PortfolioIntelligencePanelProps) {
  const { data, isLoading, error } = usePortfolioIntelligence(portfolioId)
  const { data: entitlements } = useEntitlements()

  const canSeeFull = isAdmin || canAccessFeature('portfolio_intelligence_full', userTier)
  const canSeeStress = isAdmin || canAccessFeature('portfolio_intelligence_stress', userTier)

  if (isLoading) return <LoadingState />

  if (error) {
    return (
      <div className="rounded-lg border border-border bg-surface p-6 text-center">
        <p className="text-sm text-text-secondary">Unable to compute portfolio intelligence.</p>
        <p className="text-xs text-text-tertiary mt-1">
          Ensure your positions have completed analyses.
        </p>
      </div>
    )
  }

  if (!data || data.position_count === 0) return <EmptyState />

  return (
    <div className="space-y-3">
      {/* Coverage warning */}
      <CoverageBanner
        positionsWithData={data.positions_with_data}
        positionCount={data.position_count}
      />

      {/* PM Memo — always visible */}
      <PMMemoCard memo={data.pm_memo} />

      {/* Alignment Matrix — all tiers (Starter sees 3 rows, Investor+ sees 5) */}
      <AlignmentMatrixCard rows={data.alignment_matrix} />

      {/* Portfolio Edge Score — Investor+ */}
      {canSeeFull ? (
        data.edge_score && <EdgeScoreGauge edge={data.edge_score} />
      ) : (
        <TierGate feature="portfolio_intelligence_full" userTier={userTier} isAdmin={isAdmin}>
          <div />
        </TierGate>
      )}

      {/* Concentration Diagnostics — Investor+ */}
      {canSeeFull ? (
        data.concentration && (
          <ConcentrationDiagnosticsCard
            concentration={data.concentration}
            showThematic={canSeeStress}
          />
        )
      ) : (
        <TierGate feature="portfolio_intelligence_full" userTier={userTier} isAdmin={isAdmin}>
          <div />
        </TierGate>
      )}

      {/* Regime Vulnerability — Investor+ */}
      {canSeeFull ? (
        data.regime_vulnerability && (
          <RegimeVulnerabilityCard regime={data.regime_vulnerability} />
        )
      ) : null}

      {/* Misalignment Flags — Investor+ (Trader sees all 5) */}
      {canSeeFull ? (
        <MisalignmentFlagsCard flags={data.misalignment_flags} />
      ) : (
        <TierGate feature="portfolio_intelligence_full" userTier={userTier} isAdmin={isAdmin}>
          <div />
        </TierGate>
      )}
    </div>
  )
}
