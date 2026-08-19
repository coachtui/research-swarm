'use client'

import type { DeploymentDriver } from '@/types/api'

interface DeploymentDriversPanelProps {
  drivers?: DeploymentDriver[] | null
  finalAllocation?: number | null
  addIntensityModifier?: number | null
}

/**
 * DeploymentDriversPanel — waterfall breakdown of the STARTER tranche.
 *
 * Shows how Quality Base → EV Opportunity → Divergence Overlay → Risk Adjustment
 * combine to produce the first tranche to deploy.
 *
 * This is deliberately NOT the position target. The target is the Final Weight
 * Resolver's output; this is the opening deployment toward it, sized at 40% of
 * the position ceiling. Labelling it "Final Allocation" made the smallest
 * number on the page read like the conclusion.
 */
export function DeploymentDriversPanel({
  drivers,
  finalAllocation,
  addIntensityModifier,
}: DeploymentDriversPanelProps) {
  if (!drivers || drivers.length === 0) return null

  return (
    <div className="rounded-xl border border-border/60 bg-surface/30 overflow-hidden">
      <div className="px-5 py-4 space-y-3">
        <p className="text-[10px] font-semibold uppercase tracking-wider text-text-tertiary">
          Deployment Drivers Waterfall
        </p>

        <div className="space-y-1.5">
          {drivers.map((driver, i) => {
            const isNegative = driver.sign === '-'
            const color = isNegative ? 'text-error' : 'text-success'
            return (
              <div key={i} className="flex items-center justify-between py-1.5 px-2.5 rounded-lg bg-surface-elevated/30">
                <span className="text-sm text-text-secondary">{driver.label}</span>
                <div className="flex items-center gap-2">
                  <span className={`text-xs font-bold ${color}`}>
                    {/* delta is already in percentage points (e.g. 2.5 = 2.5%) */}
                    {driver.sign} {driver.delta.toFixed(1)}%
                  </span>
                </div>
              </div>
            )
          })}

          {/* Divider */}
          <div className="h-px bg-border/40 my-2" />

          {/* Starter tranche total */}
          {finalAllocation !== null && finalAllocation !== undefined && (
            <div className="py-2 px-2.5 rounded-lg bg-primary/10 border border-primary/20">
              <div className="flex items-center justify-between">
                <span className="font-semibold text-text-primary">Starter Tranche</span>
                <span className="font-mono font-bold text-primary text-base tabular-nums">
                  {finalAllocation.toFixed(1)}%
                </span>
              </div>
              <p className="text-[10px] text-text-tertiary mt-1 leading-relaxed">
                Opening deployment, not the position target — see Final Position Weight
                for the size this builds toward.
              </p>
            </div>
          )}

          {/* Add intensity modifier */}
          {addIntensityModifier !== null && addIntensityModifier !== undefined && addIntensityModifier !== 1.0 && (
            <div className="flex items-center justify-between py-1.5 px-2.5 rounded-lg bg-surface-elevated/30 border border-border/40">
              <span className="text-sm text-text-secondary">Add Intensity Modifier</span>
              <span className="font-mono font-bold text-text-primary">{addIntensityModifier.toFixed(2)}×</span>
            </div>
          )}
        </div>

        {/* Explanatory note */}
        <p className="text-[10px] text-text-tertiary italic border-t border-border/40 pt-3 leading-relaxed">
          Deployment drivers show how initial allocation is adjusted by divergence phase, EV opportunity, and risk factors — respecting all quality gates, drawdown tiers, and position caps.
        </p>
      </div>
    </div>
  )
}
