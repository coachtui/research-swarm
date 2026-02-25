'use client'

/**
 * DecisionHeader — Layer 1 SNAPSHOT (always visible)
 *
 * Visual architecture:
 *   1. Dual-dimension classification: Structural Bias + Tactical Stance
 *   2. Deployment Status banner + Portfolio Bias
 *   3. Primary Allocation Display (ONE dominant %)
 *      – Position Type tag (Satellite / Core)
 *      – Constraint tag (Execution-bound / Cap-bound / Within Guardrails)
 *   4. Sizing narrative: why constrained + posture shift triggers
 *   5. Key Price Zones (3 simplified cards) + toggle for full view
 *   6. Entry & Holder Guidance accordion (collapsed by default)
 *
 * CRITICAL: Zero retail language. DVRG institutional vocabulary throughout.
 * CRITICAL: Zero new backend calculations — presentation-layer only.
 */

import { useState } from 'react'
import { ChevronDown, ChevronUp, AlertTriangle, CheckCircle } from 'lucide-react'
import { Card, CardContent } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import {
  deriveStructuralBias,
  deriveTacticalStance,
  derivePortfolioBias,
  deploymentGateCopy,
  isDeploymentGated,
  structuralBiasColor,
  tacticalStanceColor,
} from '@/lib/utils/decisionDimensions'
import {
  generateSizingNarrative,
  deriveDeploymentStatus,
  derivePositionType,
  deriveConstraintTag,
  deriveInstitutionalPosture,
} from '@/lib/narratives/sizingNarrative'
import type { DecisionFramework, RecommendedStrategy, SignalBreakdown, FundTechDivergence, EnhancedTradeSetup, ConvictionPosition } from '@/types/api'

// ── Props ─────────────────────────────────────────────────────────────────────

interface DecisionHeaderProps {
  framework: DecisionFramework
  ticker: string
  rating: string | null
  riskLevel: string | null
  currentPrice?: number | null
  strategy?: RecommendedStrategy | null
  signalBreakdown?: SignalBreakdown | null
  fundTechDivergence?: FundTechDivergence | null
  convictionLevel?: string | null
  enhancedTradeSetup?: EnhancedTradeSetup | null
  conviction: ConvictionPosition
}

// ── Helpers ───────────────────────────────────────────────────────────────────

function formatZone(low: number | undefined, high: number | undefined): string | null {
  if (!low && !high) return null
  if (low && high) return `$${Math.round(low).toLocaleString()} – $${Math.round(high).toLocaleString()}`
  if (low) return `~$${Math.round(low).toLocaleString()}`
  if (high) return `~$${Math.round(high).toLocaleString()}`
  return null
}

/** Map institutional action to DVRG vocabulary tab badge. */
function buyerBadgeLabel(action: string, rating: string | null, spreadLabel?: string | null): string {
  const r = (rating ?? 'HOLD').toUpperCase()
  if (r === 'STRONG SELL' || r === 'SELL') return action === 'AVOID' ? 'Exit' : 'Reduce'
  if (r === 'HOLD') {
    return spreadLabel === 'High' ? 'Monitor' : 'Selective'
  }
  switch (action.toUpperCase()) {
    case 'BUY NOW':   return 'Deploy Now'
    case 'SCALE IN':  return spreadLabel === 'High' ? 'Stage Entry' : 'Stage Entry'
    case 'WAIT':      return 'Monitor'
    case 'AVOID':     return 'Restricted'
    case 'ADD':       return 'Accumulate'
    default:          return action
  }
}

function holderBadgeLabel(action: string): string {
  switch (action.toUpperCase()) {
    case 'HOLD':   return 'Maintain'
    case 'ADD':    return 'Accumulate'
    case 'REDUCE': return 'Reduce'
    default:       return action
  }
}

function actionBadgeVariant(action: string): 'success' | 'warning' | 'error' | 'default' {
  switch (action.toUpperCase()) {
    case 'BUY NOW':
    case 'ADD':
      return 'success'
    case 'SCALE IN':
    case 'HOLD':
    case 'WAIT':
    case 'AVOID':
      return 'warning'
    case 'REDUCE':
      return 'error'
    default:
      return 'default'
  }
}

function isSell(rating: string | null | undefined): boolean {
  if (!rating) return false
  const r = rating.toUpperCase()
  return r === 'SELL' || r === 'STRONG SELL'
}

// ── Structural dislocation ────────────────────────────────────────────────────

function getStructuralPremiumTier(pct: number): string {
  if (pct > 100) return 'EXTREME'
  if (pct > 50) return 'HIGH'
  return 'ELEVATED'
}

// ── Component ─────────────────────────────────────────────────────────────────

export function DecisionHeader({
  framework,
  ticker,
  rating,
  riskLevel,
  currentPrice,
  strategy,
  signalBreakdown,
  fundTechDivergence,
  convictionLevel,
  enhancedTradeSetup,
  conviction,
}: DecisionHeaderProps) {
  const [guidanceOpen, setGuidanceOpen] = useState(false)
  const [zonesExpanded, setZonesExpanded] = useState(false)
  const [guidanceTab, setGuidanceTab] = useState<'new' | 'holders'>('new')

  const { current_holders, new_buyers, one_liner } = framework

  // ── Dimension derivation ─────────────────────────────────────────────────
  const hasDivergence = signalBreakdown?.has_divergence
  const divergenceSeverity = fundTechDivergence?.severity || (hasDivergence ? 'MODERATE' : null)

  // Price zone computation
  const entryZone = strategy?.entry?.ideal_zone
    ? formatZone(strategy.entry.ideal_zone.low, strategy.entry.ideal_zone.high)
    : strategy?.entry?.entry_zone_display?.label ?? null

  const avoidAbovePrice = strategy?.entry?.ideal_zone?.high
    ? strategy.entry.ideal_zone.high * 1.05
    : null
  const avoidAbove = avoidAbovePrice ? `$${Math.round(avoidAbovePrice).toLocaleString()}+` : null

  const isStructuralDislocation = Boolean(
    currentPrice && avoidAbovePrice && currentPrice > avoidAbovePrice * 1.25
  )
  const dislocationPct = (isStructuralDislocation && currentPrice && strategy?.entry?.ideal_zone?.high)
    ? Math.round(((currentPrice - strategy.entry.ideal_zone.high) / strategy.entry.ideal_zone.high) * 100)
    : null

  const stopZone = (() => {
    if (isStructuralDislocation && enhancedTradeSetup?.aggressive?.stop_loss) {
      return `~$${Math.round(enhancedTradeSetup.aggressive.stop_loss).toLocaleString()}`
    }
    return strategy?.exit?.stop_zone?.label
      ?? (strategy?.exit?.stop_loss ? `~$${Math.round(strategy.exit.stop_loss).toLocaleString()}` : null)
  })()

  const targetZone = strategy?.exit?.target_2?.price
    ? formatZone(strategy.exit.target_1?.price, strategy.exit.target_2?.price)
    : strategy?.exit?.target_1?.price ? `~$${Math.round(strategy.exit.target_1.price).toLocaleString()}` : null

  // Dual dimension
  const bias = deriveStructuralBias(rating)
  const stance = deriveTacticalStance(
    new_buyers.action,
    rating,
    hasDivergence ?? false,
    divergenceSeverity as 'HIGH' | 'MODERATE' | null | undefined,
    isStructuralDislocation,
  )
  const portfolioBias = derivePortfolioBias(rating)
  const gateCopy = deploymentGateCopy(stance)
  const gated = isDeploymentGated(stance)
  const biasColors = structuralBiasColor(bias)
  const stanceColors = tacticalStanceColor(stance)
  const deploymentStatus = deriveDeploymentStatus(stance)

  // Gate banner color
  const gateBannerColor = gated
    ? stance === 'Defensive'
      ? 'bg-error/8 border-error/25 text-error'
      : 'bg-warning/8 border-warning/25 text-warning'
    : 'bg-success/8 border-success/25 text-success'

  // Allocation derivation
  const sellMode = isSell(rating)
  const convLvl = conviction.conviction_level
  const positionType = derivePositionType(bias, convLvl)
  const constraintTag = deriveConstraintTag(conviction.recommended_pct, conviction.max_pct, convLvl)
  const institutionalPosture = deriveInstitutionalPosture(signalBreakdown?.institutional_score)

  // Sizing narrative
  const narrative = generateSizingNarrative({
    structural_bias: bias,
    tactical_stance: stance,
    deployment_status: deploymentStatus,
    final_weight_pct: conviction.recommended_pct,
    execution_weight_pct: conviction.recommended_pct,
    policy_cap_pct: conviction.max_pct,
    dispersion_sigma: signalBreakdown?.signal_spread ?? null,
    noise_score: signalBreakdown?.noise_filter?.noise_score ?? null,
    stop_probability_pct: signalBreakdown?.stop_probability?.effective_stop_probability_pct ?? null,
    institutional_posture: institutionalPosture,
    conviction_level: convLvl,
  })

  // Directional bias for signal strip
  const directionalBias = (() => {
    const d = (signalBreakdown?.direction_consensus ?? '').toLowerCase()
    if (d.includes('bull')) return 'Bullish'
    if (d.includes('bear')) return 'Bearish'
    return 'Neutral'
  })()
  const agreementLabel = hasDivergence
    ? divergenceSeverity === 'HIGH' ? 'Signal Dispersion — High' : 'Signal Dispersion Detected'
    : 'Aligned'

  const constraintTagColors = {
    'Execution-bound': 'bg-amber-500/10 text-amber-600 dark:text-amber-400 border-amber-500/20',
    'Cap-bound': 'bg-primary/10 text-primary border-primary/25',
    'Within Guardrails': 'bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border-emerald-500/20',
  }[constraintTag]

  const positionTypeColors = positionType === 'Core'
    ? 'bg-primary/10 text-primary border-primary/25'
    : 'bg-surface-elevated text-text-tertiary border-border/60'

  return (
    <Card
      className="ambient-verdict"
      style={{ background: 'var(--surface-1)', borderColor: 'rgba(0, 217, 181, 0.22)' }}
    >
      <CardContent className="pt-6 space-y-5">

        {/* ── TIER 1: Dual-Dimension Classification ───────────────────────── */}
        <div className="grid grid-cols-2 gap-2.5">
          <div className={`rounded-lg border-2 ${biasColors.border} ${biasColors.bg} px-3.5 py-3`}>
            <p className="text-[9px] uppercase tracking-[0.18em] text-text-tertiary font-bold mb-1">
              Structural Bias
            </p>
            <p className={`text-xl font-bold ${biasColors.text}`}>{bias}</p>
            <p className="text-[9px] text-text-tertiary mt-0.5">Business quality · Long-term EV direction</p>
          </div>
          <div className={`rounded-lg border ${stanceColors.border} bg-surface-elevated px-3.5 py-3`}>
            <p className="text-[9px] uppercase tracking-[0.18em] text-text-tertiary font-bold mb-1">
              Tactical Stance
            </p>
            <p className={`text-xl font-bold ${stanceColors.text}`}>{stance}</p>
            <p className="text-[9px] text-text-tertiary mt-0.5">Entry conditions · Capital deployment</p>
          </div>
        </div>

        {/* ── TIER 2: Deployment Status + Portfolio Bias ───────────────────── */}
        <div className={`rounded-lg border px-4 py-3 ${gateBannerColor}`}>
          <div className="flex items-center justify-between gap-3">
            <div>
              <p className="text-sm font-bold tracking-wide">{gateCopy.title}</p>
              <p className="text-[11px] opacity-80 leading-snug mt-0.5">{gateCopy.subtitle}</p>
            </div>
            <div className="text-right shrink-0">
              <p className="text-[9px] uppercase tracking-wider opacity-60 font-semibold mb-0.5">
                Portfolio Bias
              </p>
              <p className="text-sm font-bold">{portfolioBias}</p>
              {riskLevel && (
                <p className="text-[9px] opacity-45 mt-0.5">{riskLevel} Risk</p>
              )}
            </div>
          </div>
        </div>

        {/* Signal strip */}
        {signalBreakdown && (
          <div className={`flex items-center gap-2 px-3 py-2 rounded-md text-xs ${
            hasDivergence
              ? divergenceSeverity === 'HIGH'
                ? 'bg-error/5 border border-error/20 text-error'
                : 'bg-warning/5 border border-warning/20 text-warning'
              : 'bg-success/5 border border-success/20 text-success'
          }`}>
            {hasDivergence
              ? <AlertTriangle className="h-3.5 w-3.5 flex-shrink-0" />
              : <CheckCircle className="h-3.5 w-3.5 flex-shrink-0" />
            }
            <span className="font-medium">Directional Bias: {directionalBias}</span>
            <span className="text-text-secondary mx-1">·</span>
            <span className="text-text-secondary">Signal Agreement: {agreementLabel}</span>
          </div>
        )}

        {/* ── TIER 3: Primary Allocation Display ──────────────────────────── */}
        <div className="rounded-xl border border-border/60 bg-surface-elevated/50 px-5 py-4 text-center space-y-2">
          <p className="text-[10px] font-bold uppercase tracking-[0.18em] text-text-tertiary">
            {sellMode ? 'Exposure Ceiling (Policy Bound)' : 'Recommended Allocation'}
          </p>

          <div className="flex items-baseline justify-center gap-1">
            <span className={`tabular-nums leading-none ${
              sellMode
                ? 'text-4xl font-semibold text-text-secondary'
                : 'text-5xl font-bold text-primary'
            }`}>
              {conviction.recommended_pct}
            </span>
            <span className={`font-semibold ${
              sellMode ? 'text-xl text-text-tertiary' : 'text-2xl text-primary/60'
            }`}>
              %
            </span>
          </div>

          {/* Tags: Position Type + Constraint */}
          <div className="flex items-center justify-center gap-2 flex-wrap">
            <span className={`text-[10px] font-semibold px-2.5 py-0.5 rounded-full border ${positionTypeColors}`}>
              {positionType} Position
            </span>
            <span className={`text-[10px] font-semibold px-2.5 py-0.5 rounded-full border ${constraintTagColors}`}>
              {constraintTag}
            </span>
          </div>

          {sellMode && (
            <p className="text-[10px] text-text-tertiary italic">
              Hard portfolio constraint — not a deployment signal.
            </p>
          )}
        </div>

        {/* ── TIER 4: Sizing Narrative ─────────────────────────────────────── */}
        <div className="space-y-3">
          {/* Summary sentence — max 2 sentences */}
          <p className="text-sm text-text-secondary leading-relaxed">
            {narrative.summary}
          </p>

          {/* Why sizing is constrained (max 3 bullets) */}
          {narrative.drivers.length > 0 && (
            <div className="space-y-1.5">
              <p className="text-[10px] font-bold uppercase tracking-[0.14em] text-text-tertiary">
                Sizing Constraints
              </p>
              <ul className="space-y-1">
                {narrative.drivers.map((driver, i) => (
                  <li key={i} className="flex items-start gap-2">
                    <span className="mt-1.5 w-1 h-1 rounded-full bg-text-tertiary/50 flex-shrink-0" />
                    <span className="text-xs text-text-tertiary leading-relaxed">{driver}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}

          {/* What shifts posture? (max 3 bullets) */}
          {narrative.posture_shift_triggers.length > 0 && (
            <div className="space-y-1.5">
              <p className="text-[10px] font-bold uppercase tracking-[0.14em] text-text-tertiary">
                What shifts posture?
              </p>
              <ul className="space-y-1">
                {narrative.posture_shift_triggers.map((trigger, i) => (
                  <li key={i} className="flex items-start gap-2">
                    <span className="mt-1.5 w-1 h-1 rounded-full bg-primary/40 flex-shrink-0" />
                    <span className="text-xs text-text-tertiary leading-relaxed">{trigger}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}

          {/* Model one-liner (lower salience) */}
          {one_liner && (
            <p className="text-xs text-text-tertiary leading-relaxed italic border-l-2 border-border/40 pl-2.5">
              {one_liner}
            </p>
          )}
        </div>

        {/* ── TIER 5: Key Price Zones (3 simplified cards) ────────────────── */}
        {(entryZone || stopZone || targetZone) && (
          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <p className="text-[10px] font-bold uppercase tracking-[0.14em] text-text-tertiary">
                Key Price Zones
              </p>
              {isStructuralDislocation && (
                <span className="text-[10px] text-text-tertiary italic">
                  Structural framework · Timeframe-dependent
                </span>
              )}
            </div>

            {/* Default: 3 simplified cards */}
            <div className="grid grid-cols-3 gap-2">
              {entryZone && (
                <div className="rounded-md bg-surface-elevated border border-border p-3 text-center">
                  <p className="text-[10px] text-text-tertiary mb-0.5">
                    {isStructuralDislocation ? 'Valuation Baseline' : 'Entry Zone'}
                  </p>
                  {isStructuralDislocation && (
                    <p className="text-[8px] text-text-tertiary/60 mb-0.5 italic">(Non-Tactical)</p>
                  )}
                  <p className={`text-sm ${
                    isStructuralDislocation
                      ? 'font-medium text-text-tertiary'
                      : 'font-semibold text-primary'
                  }`}>
                    {entryZone}
                  </p>
                </div>
              )}
              {stopZone && (
                <div className="rounded-md bg-surface-elevated border border-border p-3 text-center">
                  <p className="text-[10px] text-text-tertiary mb-0.5">Risk Control Zone</p>
                  <p className="text-sm font-semibold text-error">{stopZone}</p>
                </div>
              )}
              {targetZone && (
                <div className="rounded-md bg-surface-elevated border border-border p-3 text-center">
                  <p className="text-[10px] text-text-tertiary mb-0.5">Target Band</p>
                  <p className="text-sm font-semibold text-primary">{targetZone}</p>
                  {strategy?.exit?.target_1 && strategy?.exit?.target_2 && (
                    <p className="text-[9px] text-text-tertiary/60 mt-0.5">
                      T1 {strategy.exit.target_1.percent}% · T2 {strategy.exit.target_2.percent}%
                    </p>
                  )}
                </div>
              )}
            </div>

            {/* Structural dislocation context */}
            {isStructuralDislocation && dislocationPct !== null && (
              <p className="text-xs text-text-tertiary leading-relaxed pl-1 border-l-2 border-warning/30">
                <span className="font-medium text-text-secondary">Structural vs. Tactical:</span>{' '}
                Current price (+{dislocationPct}% above structural value zone) reflects market pricing outside the model&apos;s intrinsic framework. Zones represent the long-term mean reversion basis — not near-term actionable levels.
              </p>
            )}

            {/* Toggle: View full valuation framework */}
            <button
              onClick={() => setZonesExpanded(o => !o)}
              className="flex items-center gap-1.5 text-[10px] text-text-tertiary hover:text-text-secondary transition-colors"
            >
              {zonesExpanded
                ? <ChevronUp className="h-3 w-3" />
                : <ChevronDown className="h-3 w-3" />
              }
              {zonesExpanded ? 'Hide full valuation framework' : 'View full valuation framework'}
            </button>

            {/* Expanded: additional zone tiles */}
            {zonesExpanded && (
              <div className="grid grid-cols-2 md:grid-cols-4 gap-2 pt-1">
                {/* Avoid Above / Structural Premium */}
                {isStructuralDislocation && dislocationPct !== null ? (
                  <div
                    className="rounded-md bg-surface-elevated border border-warning/30 p-3 text-center"
                    title={`+${dislocationPct}% above structural valuation baseline.`}
                  >
                    <p className="text-[10px] text-text-tertiary mb-0.5">Structural Premium</p>
                    <p className="text-sm font-semibold text-warning">{getStructuralPremiumTier(dislocationPct)}</p>
                    <p className="text-[9px] text-text-tertiary/70 mt-0.5">Outside structural band</p>
                  </div>
                ) : avoidAbove ? (
                  <div className="rounded-md bg-surface-elevated border border-border p-3 text-center">
                    <p className="text-[10px] text-text-tertiary mb-0.5">Avoid Above</p>
                    <p className="text-sm font-semibold text-error">{avoidAbove}</p>
                  </div>
                ) : null}
                {/* Re-show entry zone in full view for reference */}
                {entryZone && (
                  <div className="rounded-md bg-surface-elevated border border-border/60 p-3 text-center opacity-70">
                    <p className="text-[10px] text-text-tertiary mb-0.5">
                      {isStructuralDislocation ? 'Valuation Baseline' : 'Entry Zone'}
                    </p>
                    <p className="text-xs font-medium text-text-secondary">{entryZone}</p>
                    <p className="text-[9px] text-text-tertiary/60 mt-0.5">
                      {isStructuralDislocation ? 'Long-term reference' : 'Structural valuation range'}
                    </p>
                  </div>
                )}
                {/* Conviction Reference */}
                <div className="rounded-md bg-surface-elevated border border-border/60 p-3 text-center opacity-70">
                  <p className="text-[10px] text-text-tertiary mb-0.5">Policy Cap</p>
                  <p className="text-xs font-medium text-text-secondary">{conviction.max_pct}%</p>
                  <p className="text-[9px] text-text-tertiary/60 mt-0.5">Portfolio ceiling</p>
                </div>
              </div>
            )}
          </div>
        )}

        {/* ── TIER 6: Entry & Holder Guidance accordion ───────────────────── */}
        <div className="rounded-md border border-border/60 bg-surface-elevated/40 overflow-hidden">
          <button
            onClick={() => setGuidanceOpen(o => !o)}
            className="w-full flex items-center justify-between px-4 py-2.5 text-left hover:bg-surface-elevated/60 transition-colors"
          >
            <span className="text-xs font-medium text-text-secondary">
              Entry &amp; Holder Guidance
            </span>
            {guidanceOpen
              ? <ChevronUp className="h-3.5 w-3.5 text-text-tertiary flex-shrink-0" />
              : <ChevronDown className="h-3.5 w-3.5 text-text-tertiary flex-shrink-0" />
            }
          </button>

          {guidanceOpen && (
            <div className="border-t border-border/40">
              {/* Tabs */}
              <div className="flex border-b border-border/40">
                <button
                  onClick={() => setGuidanceTab('new')}
                  className={`px-4 py-2 text-xs font-medium transition-colors border-b-2 -mb-px ${
                    guidanceTab === 'new'
                      ? 'border-primary text-text-primary'
                      : 'border-transparent text-text-tertiary hover:text-text-secondary'
                  }`}
                >
                  New Buyers
                  <Badge
                    variant={actionBadgeVariant(new_buyers.action)}
                    className="ml-2 text-[10px]"
                  >
                    {buyerBadgeLabel(new_buyers.action, rating, signalBreakdown?.signal_spread_label)}
                  </Badge>
                </button>
                <button
                  onClick={() => setGuidanceTab('holders')}
                  className={`px-4 py-2 text-xs font-medium transition-colors border-b-2 -mb-px ${
                    guidanceTab === 'holders'
                      ? 'border-primary text-text-primary'
                      : 'border-transparent text-text-tertiary hover:text-text-secondary'
                  }`}
                >
                  Current Holders
                  <Badge
                    variant={actionBadgeVariant(current_holders.action)}
                    className="ml-2 text-[10px]"
                  >
                    {holderBadgeLabel(current_holders.action)}
                  </Badge>
                </button>
              </div>

              {/* Tab content */}
              <div className="px-4 py-3 space-y-2">
                {guidanceTab === 'new' && (
                  <>
                    <p className="text-sm text-text-secondary leading-relaxed">{new_buyers.detail}</p>
                    {new_buyers.caveat && (
                      <p className="text-xs text-warning italic">{new_buyers.caveat}</p>
                    )}
                    {framework.action_subtext && framework.action_subtext.length > 0 && (
                      <div className="flex flex-wrap gap-x-4 gap-y-0.5 pt-1">
                        {framework.action_subtext.map((line, i) => (
                          <p key={i} className="text-xs text-text-tertiary leading-relaxed">{line}</p>
                        ))}
                      </div>
                    )}
                  </>
                )}
                {guidanceTab === 'holders' && (
                  <>
                    <p className="text-sm text-text-secondary leading-relaxed">{current_holders.detail}</p>
                    {current_holders.conditions.length > 0 && (
                      <ul className="space-y-1.5 pt-1">
                        {current_holders.conditions.map((c, i) => (
                          <li key={i} className="text-xs text-text-tertiary flex items-start gap-1.5">
                            <span className="mt-1 w-1 h-1 rounded-full bg-text-tertiary flex-shrink-0" />
                            {c}
                          </li>
                        ))}
                      </ul>
                    )}
                  </>
                )}
              </div>
            </div>
          )}
        </div>

        {/* Meta badges */}
        <div className="flex items-center gap-2 flex-wrap">
          {convictionLevel && (
            <Badge variant="secondary">Conviction: {convictionLevel}</Badge>
          )}
          {ticker && (
            <span className="text-[10px] font-mono text-text-tertiary">{ticker}</span>
          )}
        </div>

      </CardContent>
    </Card>
  )
}
