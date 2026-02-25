'use client'

/**
 * SizingSummaryCard — Position sizing summary visible to all tiers.
 *
 * Tier rendering:
 *   Starter    → Allocation % + plain-language rationale
 *   Investor+  → + max %, dollar/100k, conviction level (3 numeric drivers)
 *   Trader     → + full conviction justification via FeatureGate
 *
 * The full dynamic sizing tool (ExecutionLayer) remains Trader-only.
 * This card surfaces the essential "what to do" for Starter/Investor users.
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

export function SizingSummaryCard({ conviction, isAdmin = false }: SizingSummaryCardProps) {
  const { data: entitlements } = useEntitlements()
  // Investor+: show numeric sizing drivers (max %, $/100k, conviction level)
  const canSeeSignalMetrics = isAdmin || (entitlements?.features['feature.report.signal_metrics'] ?? false)

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
        {/* Always visible: allocation % */}
        <div className="flex items-end gap-3">
          <div>
            <p className="text-3xl font-bold text-text-primary tabular-nums">
              {conviction.recommended_pct}
              <span className="text-lg font-semibold text-text-tertiary">%</span>
            </p>
            <p className="text-xs text-text-tertiary mt-0.5">Recommended allocation</p>
          </div>

          {/* Investor+: numeric drivers */}
          {canSeeSignalMetrics && (
            <div className="flex gap-4 pb-1 ml-4">
              <div className="text-center">
                <p className="text-sm font-semibold text-text-primary tabular-nums">
                  {conviction.max_pct}%
                </p>
                <p className="text-[10px] text-text-tertiary">Max %</p>
              </div>
              <div className="text-center">
                <p className="text-sm font-semibold text-text-primary tabular-nums">
                  ${conviction.dollar_per_100k.toLocaleString()}
                </p>
                <p className="text-[10px] text-text-tertiary">per $100k</p>
              </div>
            </div>
          )}
        </div>

        {/* Always visible: plain-language rationale */}
        <p className="text-sm text-text-secondary leading-relaxed">{conviction.rationale}</p>

        {/* Trader: full conviction justification */}
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
