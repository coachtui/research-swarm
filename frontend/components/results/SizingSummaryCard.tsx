'use client'

/**
 * SizingSummaryCard — Position sizing summary visible to all tiers.
 *
 * Visual hierarchy:
 *   PRIMARY   → Exposure Ceiling / Deployable Allocation (conviction-adjusted)
 *   SECONDARY → Sizing Framework: Baseline Model Weight, Policy Cap, Multiplier (Investor+)
 *   TERTIARY  → Interpretation block + rationale + conviction justification (Trader)
 *
 * Cognitive intent:
 *   SELL mode  → Constraint Envelope framing (existing positions only)
 *   Other      → Deployable Allocation framing (deployment guidance)
 *
 * Tier rendering:
 *   Starter    → Primary metric + status tag + interpretation + rationale
 *   Investor+  → + Sizing Framework panel (baseline, policy cap, multiplier, $/100k)
 *   Trader     → + full conviction justification via FeatureGate
 */

import { Info, TrendingUp } from 'lucide-react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip'
import { FeatureGate } from '@/components/common/FeatureGate'
import { useEntitlements } from '@/lib/hooks/useEntitlements'
import { isDeploymentGated } from '@/lib/utils/decisionDimensions'
import type { TacticalStance } from '@/lib/utils/decisionDimensions'
import type { ConvictionPosition } from '@/types/api'

interface SizingSummaryCardProps {
  conviction: ConvictionPosition
  isAdmin?: boolean
  /** Tactical Stance derived from the decision framework — gates the allocation label. */
  tacticalStance?: TacticalStance | null
  /** Analyst rating — triggers SELL-mode constraint framing when SELL / STRONG SELL. */
  rating?: string | null
}

// ── Sell Mode Detection ─────────────────────────────────────────────────────
/** True when the analyst verdict is a SELL-family rating. */
function isSell(rating: string | null | undefined): boolean {
  if (!rating) return false
  const r = rating.toUpperCase()
  return r === 'SELL' || r === 'STRONG SELL'
}

// ── A) Decision Sentence ────────────────────────────────────────────────────
/** One-line action directive derived from Tactical Stance. */
function getDecisionSentence(stance: TacticalStance): string {
  switch (stance) {
    case 'Favorable':
      return 'Action: Conditions support deployment — initiate or add exposure at current levels.'
    case 'Opportunistic':
      return 'Action: Signals support selective entry — size conservatively and scale on confirmation.'
    case 'Deferred':
      return 'Action: Hold exposure; do not add until entry conditions improve.'
    case 'Constrained':
      return 'Action: Hold exposure; do not add until stance flips to Favorable.'
    case 'Defensive':
      return 'Action: Reduce or stand aside — prioritize capital preservation over expansion.'
  }
}

// ── B) Stance Flip Triggers ─────────────────────────────────────────────────
/** Chips describing what would shift the current stance. Empty for Favorable. */
function getStanceFlipTriggers(stance: TacticalStance): string[] {
  switch (stance) {
    case 'Favorable':     return []
    case 'Opportunistic': return ['Confirm entry signal', 'Flow turns accumulating']
    case 'Deferred':      return ['Valuation regime normalizes', 'Flow turns accumulating']
    case 'Constrained':   return ['Dispersion improves', 'Flow turns neutral/accumulating', 'Valuation regime normalizes']
    case 'Defensive':     return ['Dispersion improves', 'Valuation regime normalizes', 'Flow turns neutral']
  }
}

// ── C) Semantic Guardrail ───────────────────────────────────────────────────
const AGGRESSIVE_ENTRY_RE = /\b(buy now|add now|enter now)\b/gi

/**
 * Strips aggressive entry language from rationale unless the stance
 * explicitly supports immediate deployment (Favorable or Opportunistic).
 */
function sanitizeRationale(text: string, stance: TacticalStance | null | undefined): string {
  if (stance === 'Favorable' || stance === 'Opportunistic' || stance == null) return text
  return text.replace(AGGRESSIVE_ENTRY_RE, 'maintain current exposure')
}

function convictionBadgeVariant(level: string): 'success' | 'warning' | 'error' | 'default' | 'secondary' {
  // Conviction = signal quality classification, not a directional risk state.
  // Color encodes execution environment, not thesis direction.
  if (level === 'HIGH') return 'default'       // Teal/primary — clean signal environment, informational
  if (level === 'MODERATE') return 'secondary' // Neutral slate — adaptive, not constrained
  if (level === 'LOW') return 'warning'        // Amber — constrained execution, not alarm
  return 'secondary'
}

/** Map conviction level to execution multiplier (mirrors backend strategy_calculator). */
function getExecutionMultiplier(level: string): number {
  const map: Record<string, number> = {
    High: 1.0, Medium: 0.7, Low: 0.4,
    HIGH: 1.0, MODERATE: 0.7, LOW: 0.4,
  }
  return map[level] ?? 0.7
}

/** Map execution multiplier to allocation stability label. */
function getSizingConfidence(multiplier: number): string {
  if (multiplier >= 1.0) return 'Stable'
  if (multiplier >= 0.7) return 'Adaptive'
  return 'Constrained'
}

export function SizingSummaryCard({ conviction, isAdmin = false, tacticalStance, rating }: SizingSummaryCardProps) {
  const { data: entitlements } = useEntitlements()
  const canSeeSignalMetrics = isAdmin || (entitlements?.features['feature.report.signal_metrics'] ?? false)

  const sellMode = isSell(rating)

  const multiplier = getExecutionMultiplier(conviction.conviction_level)
  const isExecutionBound = multiplier < 1.0

  // Deployment gate: use Tactical Stance when available, fall back to execution multiplier
  const deploymentGated = tacticalStance != null ? isDeploymentGated(tacticalStance) : isExecutionBound

  // ── Terminology selection: SELL mode uses constraint framing throughout ──
  const primaryMetricLabel = sellMode
    ? 'Exposure Ceiling (Policy Bound)'
    : deploymentGated
    ? 'Deployable Allocation (Gated)'
    : 'Deployable Allocation (Active)'

  // Back-calculate the pre-multiplier baseline for display (no math change, display only)
  const baselineModelWeight =
    multiplier > 0
      ? Math.round((conviction.recommended_pct / multiplier) * 10) / 10
      : conviction.recommended_pct

  // A + B: derived from tactical stance when available
  const decisionSentence = tacticalStance != null ? getDecisionSentence(tacticalStance) : null
  const flipTriggers = tacticalStance != null ? getStanceFlipTriggers(tacticalStance) : []

  return (
    <Card className="border border-border">
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between gap-2">
          <div className="flex items-center gap-2">
            <TrendingUp className="w-4 h-4 text-primary" />
            <CardTitle className="text-base font-semibold text-text-primary">
              {sellMode ? 'Exposure Constraint Framework' : 'Position Sizing'}
            </CardTitle>
            {/* Engine relationship disclosure — always present, subtle */}
            <Tooltip>
              <TooltipTrigger asChild>
                <Info className="w-3.5 h-3.5 text-text-tertiary opacity-40 cursor-default" />
              </TooltipTrigger>
              <TooltipContent className="max-w-xs" side="bottom">
                <p className="text-xs font-medium leading-snug">
                  Directional Verdict governs capital deployment.
                </p>
                <p className="text-xs leading-relaxed mt-1 opacity-75">
                  Exposure engines govern sizing constraints. These outputs operate on separate dimensions — the allocation model computes permissible exposure envelopes independent of the directional verdict.
                </p>
              </TooltipContent>
            </Tooltip>
          </div>
          <div className="flex items-center gap-1.5">
            <span className="text-[10px] font-medium text-text-tertiary">Risk Regime</span>
            <Badge variant={convictionBadgeVariant(conviction.conviction_level)}>
              {conviction.conviction_level}
            </Badge>
          </div>
        </div>
      </CardHeader>

      <CardContent className="space-y-4">

        {/* ── SELL MODE: Exposure Interpretation Block ──────────────────
            Injected above ALL allocation components when verdict is SELL.
            Eliminates perceived contradiction between rating and numbers. */}
        {sellMode && (
          <div className="rounded-md border border-border/60 bg-surface-elevated px-3.5 py-3">
            <p className="text-[10px] font-bold text-text-tertiary uppercase tracking-wider mb-2">
              Exposure Interpretation
            </p>
            <div className="space-y-1">
              <div className="flex items-center justify-between text-xs">
                <span className="text-text-tertiary">New Capital Deployment</span>
                <span className="font-semibold text-text-secondary">Not Supported</span>
              </div>
              <div className="flex items-start justify-between gap-3 text-xs">
                <span className="text-text-tertiary">Exposure Guidance Applies To</span>
                <span className="font-medium text-text-secondary text-right">Existing Positions Only</span>
              </div>
            </div>
            <p className="text-[10px] text-text-tertiary mt-2.5 pt-2 border-t border-border/40 leading-snug">
              Allocation outputs represent constraint boundaries, not entry signals.
            </p>
          </div>
        )}

        {/* ── PRIMARY METRIC ────────────────────────────────────────────── */}
        <div>
          <p className="text-[10px] font-semibold text-text-tertiary uppercase tracking-wider mb-2">
            {primaryMetricLabel}
          </p>
          {/* Number: reduced emphasis in SELL mode (secondary/muted vs bold/primary) */}
          <div className="flex items-baseline gap-1">
            <span
              className={`tabular-nums leading-none ${
                sellMode
                  ? 'text-3xl font-semibold text-text-secondary'
                  : 'text-4xl font-bold text-primary'
              }`}
            >
              {conviction.recommended_pct}
            </span>
            <span
              className={`font-semibold ${
                sellMode ? 'text-lg text-text-tertiary' : 'text-xl text-primary/60'
              }`}
            >
              %
            </span>
          </div>
          {/* Status tag: neutral constraint language in SELL mode */}
          <div className="flex items-center gap-2 mt-2">
            <span className="text-xs text-text-tertiary">
              {sellMode ? 'Maximum Permitted Exposure' : 'Active Position Size'}
            </span>
            <span
              className={`text-[10px] font-medium px-1.5 py-0.5 rounded-sm ${
                sellMode
                  ? 'bg-surface-elevated text-text-tertiary border border-border/60'
                  : isExecutionBound
                  ? 'bg-amber-500/10 text-amber-600 dark:text-amber-400'
                  : 'bg-emerald-500/10 text-emerald-600 dark:text-emerald-400'
              }`}
            >
              {sellMode ? '· Constraint-Bound' : isExecutionBound ? '· Execution-Constrained' : '· Within Guardrails'}
            </span>
          </div>
          {/* Hard constraint note — added under the number in SELL mode */}
          {sellMode && (
            <p className="text-[10px] text-text-tertiary mt-1.5 leading-tight italic">
              This represents a hard portfolio constraint, not a directional recommendation.
            </p>
          )}
          {!sellMode && deploymentGated && (
            <p className="text-[10px] text-text-tertiary mt-1.5 leading-tight italic">
              Allocation reflects execution constraints, not thesis impairment.
            </p>
          )}
          <p className="text-[10px] text-text-tertiary mt-1 leading-tight">
            Sizing Confidence: {getSizingConfidence(multiplier)}
          </p>
        </div>

        {/* ── A) DECISION SENTENCE ──────────────────────────────────────── */}
        {decisionSentence && (
          <p className="text-[11px] font-medium text-text-primary leading-snug border-l-2 border-primary/40 pl-2.5">
            {decisionSentence}
          </p>
        )}

        {/* ── SECONDARY: SIZING FRAMEWORK (Investor+) ───────────────────── */}
        {canSeeSignalMetrics && (
          <div className={`rounded-md border border-border/60 p-3 ${sellMode ? 'bg-surface-elevated/60 opacity-80' : 'bg-background/40'}`}>
            <p className="text-[10px] font-semibold text-text-tertiary uppercase tracking-wider mb-3">
              Sizing Diagnostics
            </p>
            <div className="grid grid-cols-3 gap-x-4 gap-y-2.5">
              {/* Model Baseline — renamed to Theoretical Risk-Neutral Weight in SELL mode */}
              <div>
                <p className="text-[10px] text-text-tertiary leading-tight mb-0.5">
                  {sellMode ? 'Theoretical Risk-Neutral Weight' : 'Model Baseline'}
                </p>
                <p className="text-xs font-normal text-text-tertiary tabular-nums">
                  {baselineModelWeight}{' '}%
                </p>
              </div>
              {/* Policy Constraint — renamed to Exposure Ceiling in SELL mode */}
              <div>
                <p className="text-[10px] text-text-tertiary leading-tight mb-0.5">
                  {sellMode ? 'Exposure Ceiling' : 'Policy Constraint'}
                </p>
                <p className="text-xs font-normal text-text-secondary tabular-nums">
                  {conviction.max_pct}{' '}%
                </p>
              </div>
              {/* Execution Multiplier — diagnostic, no numeric dominance */}
              <div>
                <p className="text-[10px] text-text-tertiary leading-tight mb-0.5">
                  Execution Multiplier
                </p>
                <p className="text-xs font-normal text-text-secondary tabular-nums">
                  {multiplier.toFixed(3)}&times;
                </p>
              </div>
            </div>
            <div className="mt-2.5 pt-2 border-t border-border/40">
              <p className="text-[10px] text-text-tertiary tabular-nums">
                {sellMode
                  ? `${conviction.dollar_per_100k.toLocaleString()} max exposure per $100K (constraint reference)`
                  : `$${conviction.dollar_per_100k.toLocaleString()} per $100K deployed capital`
                }
              </p>
            </div>
          </div>
        )}

        {/* ── INTERPRETATION BLOCK ─────────────────────────────────────── */}
        <p className="text-[11px] text-text-tertiary leading-relaxed border-l-2 border-border/50 pl-2.5 italic">
          {sellMode
            ? 'Exposure model operates independently of the directional verdict. Values reflect the maximum permissible exposure envelope under portfolio risk constraints — not a deployment signal.'
            : 'Allocation calibrated to prevailing signal reliability and execution environment. Thesis conditions unchanged; deployment governed by portfolio risk parameters.'
          }
        </p>

        {/* ── B) STANCE FLIP TRIGGERS ──────────────────────────────────── */}
        {flipTriggers.length > 0 && (
          <div>
            <p className="text-[10px] font-semibold text-text-tertiary uppercase tracking-wider mb-1.5">
              Flip Triggers
            </p>
            <div className="flex flex-wrap gap-1.5">
              {flipTriggers.map(trigger => (
                <span
                  key={trigger}
                  className="text-[10px] font-medium px-2 py-0.5 rounded-full border border-border/60 text-text-tertiary"
                >
                  {trigger}
                </span>
              ))}
            </div>
          </div>
        )}

        {/* ── PLAIN-LANGUAGE RATIONALE (C: semantic guardrail applied) ─── */}
        <p className="text-sm text-text-secondary leading-relaxed">
          {sanitizeRationale(conviction.rationale, tacticalStance)}
        </p>

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
