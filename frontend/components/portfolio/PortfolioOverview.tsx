'use client'

import { useEffect, useRef } from 'react'
import { usePortfolio, useTriggerEngine } from '@/lib/hooks/usePortfolio'
import { formatWeight } from '@/lib/ownership-mapping'
import { Button } from '@/components/ui/button'
import { RefreshCw, CheckCircle, AlertCircle } from 'lucide-react'
import { canAccessFeature } from '@/lib/entitlements'

type EngineResult = {
  success: boolean
  actions_created: number
  cycle_type: string
  trigger_cycle: string
  diagnostics?: { message?: string }
}

/**
 * PortfolioOverview — summary of the user's primary portfolio.
 *
 * Shows: total positions, weight allocated, sector breakdown,
 * top exposures, and engine trigger button (Investor+).
 */
export function PortfolioOverview({
  portfolioId,
  userTier,
}: {
  portfolioId: string
  userTier: string | null
}) {
  const { data } = usePortfolio()
  const triggerEngine = useTriggerEngine()
  const dismissTimer = useRef<ReturnType<typeof setTimeout> | null>(null)

  // Auto-dismiss the result banner after 12s
  useEffect(() => {
    if (triggerEngine.isSuccess || triggerEngine.isError) {
      dismissTimer.current = setTimeout(() => triggerEngine.reset(), 12000)
    }
    return () => {
      if (dismissTimer.current) clearTimeout(dismissTimer.current)
    }
  }, [triggerEngine.isSuccess, triggerEngine.isError])

  const portfolio = data?.portfolios?.find(p => p.id === portfolioId)
  if (!portfolio) return null

  const engineResult = triggerEngine.data as EngineResult | undefined

  const sorted = [...portfolio.positions].sort((a, b) => b.current_weight - a.current_weight)
  const top3 = sorted.slice(0, 3)

  // Ownership status counts
  const coreCount = portfolio.positions.filter(p => p.ownership_status === 'core_compounder').length
  const watchCount = portfolio.positions.filter(p => p.ownership_status === 'watch').length
  const dqCount = portfolio.positions.filter(p => p.ownership_status === 'disqualified').length

  // Thesis state counts
  const intactCount = portfolio.positions.filter(p => p.thesis_state === 'intact').length
  const monitoringCount = portfolio.positions.filter(p => p.thesis_state === 'monitoring').length
  const brokenCount = portfolio.positions.filter(p => p.thesis_state === 'broken').length

  const canTrigger = canAccessFeature('portfolio_actions', userTier)

  return (
    <div className="space-y-6">
      {/* ── Header ───────────────────────────────────────────────────── */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2">
        <div className="min-w-0">
          <h3 className="text-lg font-semibold text-text-primary truncate">{portfolio.name}</h3>
          <p className="text-xs text-text-tertiary">
            {portfolio.mandate} mandate · {portfolio.position_count} positions
          </p>
        </div>
        {canTrigger && (
          <Button
            size="sm"
            variant="outline"
            onClick={() => triggerEngine.mutate({ portfolioId })}
            disabled={triggerEngine.isPending}
            className="h-8 text-xs self-start sm:self-auto shrink-0"
          >
            <RefreshCw className={`h-3.5 w-3.5 mr-1.5 ${triggerEngine.isPending ? 'animate-spin' : ''}`} />
            {triggerEngine.isPending ? 'Running...' : 'Run Engine'}
          </Button>
        )}
      </div>

      {/* ── Engine result banner ─────────────────────────────────────── */}
      {triggerEngine.isSuccess && engineResult && (
        <div className="flex items-start gap-2.5 rounded-lg border border-success/30 bg-success/5 px-4 py-3">
          <CheckCircle className="h-4 w-4 text-success mt-0.5 shrink-0" />
          <div className="text-xs text-text-secondary">
            <span className="font-semibold text-success">Engine run complete.</span>{' '}
            {engineResult.actions_created > 0 ? (
              <>
                <span className="font-semibold text-text-primary">{engineResult.actions_created}</span>{' '}
                new action{engineResult.actions_created !== 1 ? 's' : ''} generated
                — check the <span className="font-semibold text-text-primary">Actions</span> tab to review them.
              </>
            ) : (
              <>No new actions — positions are on track for the {engineResult.cycle_type} cycle.</>
            )}
          </div>
        </div>
      )}
      {triggerEngine.isError && (
        <div className="flex items-start gap-2.5 rounded-lg border border-error/30 bg-error/5 px-4 py-3">
          <AlertCircle className="h-4 w-4 text-error mt-0.5 shrink-0" />
          <p className="text-xs text-error">
            Engine run failed:{' '}
            {(triggerEngine.error as { message?: string })?.message ?? 'Unknown error'}
          </p>
        </div>
      )}

      {/* ── Summary tiles ────────────────────────────────────────────── */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        <SummaryTile label="Total Weight" value={formatWeight(portfolio.total_weight)} />
        <SummaryTile label="Positions" value={`${portfolio.position_count}`} />
        <SummaryTile
          label="Status"
          value={`${coreCount} Core · ${watchCount} Watch`}
          sublabel={dqCount > 0 ? `${dqCount} DQ` : undefined}
        />
        <SummaryTile
          label="Thesis"
          value={`${intactCount} Intact`}
          sublabel={monitoringCount > 0 || brokenCount > 0
            ? `${monitoringCount} Mon · ${brokenCount} Broken`
            : undefined}
        />
      </div>

      {/* ── Top exposures ────────────────────────────────────────────── */}
      {top3.length > 0 && (
        <div>
          <h4 className="text-[11px] font-semibold uppercase tracking-wider text-text-tertiary mb-2">
            Top Exposures
          </h4>
          <div className="space-y-1.5">
            {top3.map((pos, i) => (
              <div
                key={pos.ticker}
                className="flex items-center justify-between rounded-lg bg-surface-elevated/50 px-3 py-2"
              >
                <div className="flex items-center gap-2">
                  <span className="text-xs font-mono text-text-tertiary w-4">#{i + 1}</span>
                  <span className="text-sm font-bold font-mono text-text-primary">{pos.ticker}</span>
                </div>
                <div className="flex items-center gap-3">
                  <span className="text-xs font-mono font-semibold text-text-secondary">
                    {formatWeight(pos.current_weight)}
                  </span>
                  <div className="w-16 h-1.5 bg-surface rounded-full overflow-hidden">
                    <div
                      className="h-full bg-primary rounded-full"
                      style={{ width: `${Math.min((pos.current_weight / 0.25) * 100, 100)}%` }}
                    />
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

function SummaryTile({
  label,
  value,
  sublabel,
}: {
  label: string
  value: string
  sublabel?: string
}) {
  return (
    <div className="rounded-lg border border-border/40 bg-surface-elevated/50 px-3 py-2.5">
      <p className="text-[10px] font-semibold uppercase tracking-wider text-text-tertiary">{label}</p>
      <p className="text-sm font-bold text-text-primary mt-0.5">{value}</p>
      {sublabel && (
        <p className="text-[10px] text-text-tertiary mt-0.5">{sublabel}</p>
      )}
    </div>
  )
}
