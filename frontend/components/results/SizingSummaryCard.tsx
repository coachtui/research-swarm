'use client'

/**
 * SizingSummaryCard — Position sizing summary visible to all tiers.
 *
 * Visual hierarchy:
 *   PRIMARY   → Deployable Allocation (conviction-adjusted, actionable size)
 *   SECONDARY → Sizing Framework: Baseline Model Weight, Policy Cap, Multiplier (Investor+)
 *   TERTIARY  → Interpretation block + rationale + conviction justification (Trader)
 *
 * Cognitive intent: Deployable Allocation = decision anchor.
 * All other values = constraint diagnostics.
 *
 * Tier rendering:
 *   Starter    → Deployable Allocation + status tag + interpretation + rationale
 *   Investor+  → + Sizing Framework panel (baseline, policy cap, multiplier, $/100k)
 *   Trader     → + full conviction justification via FeatureGate
 */

import { TrendingUp } from 'lucide-react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { FeatureGate } from '@/components/common/FeatureGate'
import { useEntitlements } from '@/lib/hooks/useEntitlements'
import type { ConvictionPosition } from '@/types/api'

interface SizingSummaryCardProps {
  conviction: ConvictionPosition
  isAdmin?: boolean
}

function convictionBadgeVariant(level: string): 'success' | 'warning' | 'error' | 'default' {
  if (level === 'HIGH') return 'success'
  if (level === 'MODERATE') return 'warning'
  if (level === 'LOW') return 'error'
  return 'default'
}

/** Map conviction level to execution multiplier (mirrors backend strategy_calculator). */
function getExecutionMultiplier(level: string): number {
  const map: Record<string, number> = {
    High: 1.0, Medium: 0.7, Low: 0.4,
    HIGH: 1.0, MODERATE: 0.7, LOW: 0.4,
  }
  return map[level] ?? 0.7
}

export function SizingSummaryCard({ conviction, isAdmin = false }: SizingSummaryCardProps) {
  const { data: entitlements } = useEntitlements()
  const canSeeSignalMetrics = isAdmin || (entitlements?.features['feature.report.signal_metrics'] ?? false)

  const multiplier = getExecutionMultiplier(conviction.conviction_level)
  const isExecutionBound = multiplier < 1.0

  // Back-calculate the pre-multiplier baseline for display (no math change, display only)
  const baselineModelWeight =
    multiplier > 0
      ? Math.round((conviction.recommended_pct / multiplier) * 10) / 10
      : conviction.recommended_pct

  return (
    <Card className="border border-border">
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between gap-2">
          <div className="flex items-center gap-2">
            <TrendingUp className="w-4 h-4 text-primary" />
            <CardTitle className="text-base font-semibold text-text-primary">
              Position Sizing
            </CardTitle>
          </div>
          <Badge variant={convictionBadgeVariant(conviction.conviction_level)}>
            {conviction.conviction_level}
          </Badge>
        </div>
      </CardHeader>

      <CardContent className="space-y-4">

        {/* ── PRIMARY DECISION VARIABLE ────────────────────────────────── */}
        <div>
          <p className="text-[10px] font-semibold text-text-tertiary uppercase tracking-wider mb-2">
            Deployable Allocation
          </p>
          <div className="flex items-baseline gap-1">
            <span className="text-4xl font-bold text-primary tabular-nums leading-none">
              {conviction.recommended_pct}
            </span>
            <span className="text-xl font-semibold text-primary/60">%</span>
          </div>
          <div className="flex items-center gap-2 mt-2">
            <span className="text-xs text-text-tertiary">Final Position Size</span>
            <span
              className={`text-[10px] font-medium px-1.5 py-0.5 rounded-sm ${
                isExecutionBound
                  ? 'bg-amber-500/10 text-amber-600 dark:text-amber-400'
                  : 'bg-emerald-500/10 text-emerald-600 dark:text-emerald-400'
              }`}
            >
              {isExecutionBound ? '· Execution-Bound' : '· Within Guardrails'}
            </span>
          </div>
        </div>

        {/* ── SECONDARY: SIZING FRAMEWORK (Investor+) ───────────────────── */}
        {canSeeSignalMetrics && (
          <div className="rounded-md border border-border/60 bg-background/40 p-3">
            <p className="text-[10px] font-semibold text-text-tertiary uppercase tracking-wider mb-3">
              Sizing Framework
            </p>
            <div className="grid grid-cols-3 gap-x-4 gap-y-2.5">
              {/* Baseline Model Weight — lowest salience */}
              <div>
                <p className="text-[10px] text-text-tertiary leading-tight mb-0.5">
                  Baseline Model Weight
                </p>
                <p className="text-xs font-normal text-text-tertiary tabular-nums">
                  {baselineModelWeight}%
                </p>
              </div>
              {/* Policy Cap — neutral, slightly above baseline */}
              <div>
                <p className="text-[10px] text-text-tertiary leading-tight mb-0.5">
                  Policy Cap
                </p>
                <p className="text-xs font-normal text-text-secondary tabular-nums">
                  {conviction.max_pct}%
                </p>
              </div>
              {/* Noise-Adjusted Multiplier — diagnostic, no numeric dominance */}
              <div>
                <p className="text-[10px] text-text-tertiary leading-tight mb-0.5">
                  Noise-Adjusted Multiplier
                </p>
                <p className="text-xs font-normal text-text-secondary tabular-nums">
                  {multiplier.toFixed(3)}&times;
                </p>
              </div>
            </div>
            <div className="mt-2.5 pt-2 border-t border-border/40">
              <p className="text-[10px] text-text-tertiary tabular-nums">
                ${conviction.dollar_per_100k.toLocaleString()} per $100K deployed capital
              </p>
            </div>
          </div>
        )}

        {/* ── INTERPRETATION BLOCK ─────────────────────────────────────── */}
        <p className="text-[11px] text-text-tertiary leading-relaxed border-l-2 border-border/50 pl-2.5 italic">
          Final position size reflects execution constraints rather than thesis deterioration.
          Baseline sizing adjusted due to signal dispersion, noise regime, or portfolio risk filters.
        </p>

        {/* ── PLAIN-LANGUAGE RATIONALE ─────────────────────────────────── */}
        <p className="text-sm text-text-secondary leading-relaxed">{conviction.rationale}</p>

        {/* ── TRADER: FULL CONVICTION JUSTIFICATION ────────────────────── */}
        <FeatureGate
          flag="feature.report.multiplier_stack"
          fallback={
            <p className="text-[11px] text-text-tertiary border-t border-border/40 pt-3">
              Full sizing justification and multiplier breakdown available on Trader plan.
            </p>
          }
        >
          {conviction.conviction_justification && (
            <div className="border-t border-border/40 pt-3">
              <p className="text-[10px] font-semibold text-text-tertiary uppercase tracking-wider mb-1.5">
                Conviction Justification
              </p>
              <p className="text-xs text-text-secondary leading-relaxed">
                {conviction.conviction_justification}
              </p>
            </div>
          )}
        </FeatureGate>

      </CardContent>
    </Card>
  )
}
