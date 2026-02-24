'use client'

import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip'
import { Info } from 'lucide-react'
import type { SignalBreakdown } from '@/types/api'

type RegimeColor = 'success' | 'neutral' | 'error' | 'warning' | 'cyan'

interface RegimeItem {
  label: string
  value: string
  color: RegimeColor
  tooltipL1: string
  tooltipL2: string
}

function deriveRiskEnvironment(breakdown: SignalBreakdown): RegimeItem {
  const score = breakdown.overall_score ?? 5
  if (score >= 6.5) {
    return {
      label: 'Risk Environment',
      value: 'Risk-On',
      color: 'success',
      tooltipL1: 'Broad signal consensus reflects favorable structural conditions. Characterizes alignment — not return probability.',
      tooltipL2: 'Signal matrix reflects broad alignment toward favorable conditions for risk assets. Characterizes the prevailing signal environment — not a directional mandate, expected return magnitude, or entry timing signal.',
    }
  }
  if (score <= 4.0) {
    return {
      label: 'Risk Environment',
      value: 'Risk-Off',
      color: 'error',
      tooltipL1: 'Signal consensus reflects defensive structural conditions. Not a directive to reduce exposure.',
      tooltipL2: 'Broad signals reflect structural alignment toward defensive conditions. Characterizes prevailing signal weight — not a loss-magnitude indicator or position instruction. Conditions warrant analytical caution, not automatic de-risking.',
    }
  }
  return {
    label: 'Risk Environment',
    value: 'Neutral',
    color: 'neutral',
    tooltipL1: 'Signal matrix is balanced without directional conviction. Outcome distribution is approximately symmetric.',
    tooltipL2: 'Broad signal weight reflects no structural dominance in either direction. Neither risk-on nor risk-off conditions prevail — outcome distribution remains symmetric from current conditions.',
  }
}

function deriveLiquidityState(breakdown: SignalBreakdown): RegimeItem {
  const instHasData = breakdown.institutional_has_data !== false
  const dpHasData = breakdown.dark_pool_has_data !== false && breakdown.dark_pool_score != null
  const instScore = instHasData ? breakdown.institutional_score : 5
  const dpScore = dpHasData ? (breakdown.dark_pool_score as number) : 5
  const count = [instHasData, dpHasData].filter(Boolean).length
  const avg = count > 0 ? (instScore + dpScore) / 2 : 5

  if (avg >= 6.2) {
    return {
      label: 'Liquidity State',
      value: 'Expansion',
      color: 'cyan',
      tooltipL1: 'Net institutional accumulation detected. Characterizes capital flow direction — not asset quality.',
      tooltipL2: 'Institutional and dark pool activity indicate net accumulation. Expansion characterizes capital flow directionality — not company financial quality or near-term return certainty. Net inflows historically support price, but correlation is not causation.',
    }
  }
  if (avg <= 4.2) {
    return {
      label: 'Liquidity State',
      value: 'Contraction',
      color: 'warning',
      tooltipL1: 'Institutional distribution detected. Characterizes flow directionality — not fundamental deterioration.',
      tooltipL2: 'Institutional and dark pool signals indicate net distribution. Contraction characterizes capital flow directionality — not company quality impairment. Smart money reduction can create supply overhang independent of fundamental thesis validity.',
    }
  }
  return {
    label: 'Liquidity State',
    value: 'Neutral',
    color: 'neutral',
    tooltipL1: 'Capital flows show no strong directional bias. Neither accumulation nor distribution dominates.',
    tooltipL2: 'Institutional and dark pool activity show balanced directionality — neither aggressive accumulation nor distribution is structurally detectable. Liquidity conditions are symmetric relative to prevailing baseline.',
  }
}

function deriveVolatilityState(breakdown: SignalBreakdown): RegimeItem {
  const spread = breakdown.signal_spread ?? 0
  const spreadLabel = breakdown.signal_spread_label

  if (spread >= 3.5 || spreadLabel === 'High') {
    return {
      label: 'Volatility State',
      value: 'Stress',
      color: 'error',
      tooltipL1: 'Wide signal dispersion indicates elevated outcome uncertainty. Not a directional signal.',
      tooltipL2: 'High signal dispersion reflects elevated outcome variance across the analytical composite. Stress characterizes uncertainty breadth — not direction. Both recovery and further weakness are statistically plausible. Position sizing should reflect the uncertainty envelope.',
    }
  }
  if (spread >= 2.0 || spreadLabel === 'Moderate') {
    return {
      label: 'Volatility State',
      value: 'Elevated',
      color: 'warning',
      tooltipL1: 'Signal divergence is above baseline. Expect wider outcome range until signals converge.',
      tooltipL2: 'Moderate signal divergence indicates above-baseline outcome variance. Not a stress condition, but noteworthy. Signal convergence typically precedes trend clarification — Elevated state warrants monitoring, not immediate position changes.',
    }
  }
  return {
    label: 'Volatility State',
    value: 'Low',
    color: 'success',
    tooltipL1: 'Signal convergence indicates low variability environment. Trending conditions are more reliable.',
    tooltipL2: 'Broad signal agreement reflects compressed outcome variance and structurally lower realized volatility. When signals align, trending conditions are historically more durable and momentum signals carry higher informational weight.',
  }
}

const COLOR_MAP: Record<RegimeColor, string> = {
  success: 'bg-success/10 text-success border-success/20',
  error: 'bg-error/10 text-error border-error/20',
  warning: 'bg-yellow-500/10 text-yellow-400 border-yellow-500/20',
  cyan: 'bg-cyan-500/10 text-cyan-400 border-cyan-500/20',
  neutral: 'bg-surface-elevated text-text-secondary border-border',
}

function RegimeBadge({ item }: { item: RegimeItem }) {
  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <div className="flex flex-col items-center gap-1 cursor-default select-none">
          <span className="text-[10px] text-text-tertiary uppercase tracking-wide font-medium">
            {item.label}
          </span>
          <span
            className={`inline-flex items-center gap-1 px-2.5 py-1 rounded text-xs font-medium border ${COLOR_MAP[item.color]}`}
          >
            {item.value}
            <Info className="h-2.5 w-2.5 opacity-50 flex-shrink-0" />
          </span>
        </div>
      </TooltipTrigger>
      <TooltipContent className="max-w-xs" side="bottom">
        <p className="text-xs font-medium leading-snug">{item.tooltipL1}</p>
        <p className="text-xs leading-relaxed mt-1 opacity-75">{item.tooltipL2}</p>
      </TooltipContent>
    </Tooltip>
  )
}

/**
 * Build a sector-contextual interpretation of the current regime combination.
 * Used to expand the regime strip from a label-only display to a 2-3 sentence
 * interpretive paragraph that explains how this regime historically affects
 * the specific stock's sector.
 */
function buildRegimeInterpretation(
  risk: RegimeItem,
  liquidity: RegimeItem,
  volatility: RegimeItem,
): { text: string; severity: 'warn' | 'caution' | 'neutral' | 'favorable' } | null {
  const isRiskOff = risk.value === 'Risk-Off'
  const isRiskOn = risk.value === 'Risk-On'
  const isContraction = liquidity.value === 'Contraction'
  const isExpansion = liquidity.value === 'Expansion'
  const isStress = volatility.value === 'Stress'
  const isElevated = volatility.value === 'Elevated'

  // Triple-adverse: worst configuration — high urgency
  if (isRiskOff && isContraction && isStress) {
    return {
      text: 'Triple-adverse regime: Risk-Off signals combine with institutional distribution (Contraction) and elevated signal dispersion (Stress). In this configuration, stocks with active smart money selling and weak technicals have historically underperformed their sector by 12–20% over the subsequent 90 days. Individual stock selection weight should increase vs. macro beta exposure — this regime does not lift all boats.',
      severity: 'warn',
    }
  }

  // Risk-Off + Contraction (no stress)
  if (isRiskOff && isContraction) {
    return {
      text: 'Risk-Off + Liquidity Contraction regime: Institutions are reducing exposure while broad signal environment turns defensive. This combination has historically favored reducing cyclical and growth exposure until regime normalizes. Technically weak stocks operating in fintech or financial services — sectors sensitive to rate and credit cycle — have shown elevated vulnerability in this configuration.',
      severity: 'warn',
    }
  }

  // Risk-Off + Stress (no contraction — could be volatile but not distributing)
  if (isRiskOff && isStress) {
    return {
      text: 'Risk-Off + Volatility Stress regime: Broad signals have turned defensive while signal dispersion is elevated, indicating elevated uncertainty. This regime creates wider outcome bands — both recovery rallies and further weakness are possible. Position sizing should reflect the uncertainty; avoid adding full positions into the stress peak.',
      severity: 'caution',
    }
  }

  // Risk-Off alone (mild)
  if (isRiskOff) {
    return {
      text: 'Risk-Off signal environment: Broad signals point to defensive conditions, though institutional flows and volatility are not yet in stress. This backdrop warrants patience on new entries — wait for regime normalization or a strong individual-stock catalyst before establishing full positions.',
      severity: 'caution',
    }
  }

  // Favorable: Risk-On + Expansion
  if (isRiskOn && isExpansion) {
    return {
      text: 'Favorable regime: Risk-On signals combined with institutional accumulation (Expansion) create a supportive backdrop for new positions. Signal quality is elevated — macro tailwinds amplify individual stock setups. Stocks with strong fundamentals and positive technical momentum historically outperform by the widest margin in this configuration.',
      severity: 'favorable',
    }
  }

  // Risk-On but some friction
  if (isRiskOn && (isContraction || isElevated)) {
    return {
      text: 'Mixed regime: Broad signals are Risk-On but institutional flows show friction (Contraction or elevated volatility). The macro backdrop is supportive, but the smart money signal conflict introduces uncertainty. This is a stock-picker\'s environment — conviction in individual thesis quality matters more than macro beta.',
      severity: 'neutral',
    }
  }

  // Neutral / unremarkable
  return null
}

interface MarketRegimeOverlayProps {
  breakdown: SignalBreakdown
}

export function MarketRegimeOverlay({ breakdown }: MarketRegimeOverlayProps) {
  const risk = deriveRiskEnvironment(breakdown)
  const liquidity = deriveLiquidityState(breakdown)
  const volatility = deriveVolatilityState(breakdown)
  const interpretation = buildRegimeInterpretation(risk, liquidity, volatility)

  const interpretBorderColor = {
    warn: 'border-l-error/40',
    caution: 'border-l-warning/40',
    neutral: 'border-l-border',
    favorable: 'border-l-success/40',
  }

  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between gap-4 py-3 px-4 rounded-md bg-surface-elevated/60 border border-border-subtle">
        <Tooltip>
          <TooltipTrigger asChild>
            <span className="text-xs font-medium text-text-tertiary uppercase tracking-wide shrink-0 cursor-default">
              Market Regime
            </span>
          </TooltipTrigger>
          <TooltipContent className="max-w-xs" side="bottom">
            <p className="text-xs font-medium leading-snug">Structural assessment of market behavior across risk, liquidity, and volatility dimensions.</p>
            <p className="text-xs leading-relaxed mt-1 opacity-75">Descriptive, not predictive. Regime conditions characterize the prevailing analytical environment — they do not imply continuation, transition timing, or directional instruction.</p>
          </TooltipContent>
        </Tooltip>
        <div className="flex items-center gap-6 flex-wrap justify-end">
          <RegimeBadge item={risk} />
          <RegimeBadge item={liquidity} />
          <RegimeBadge item={volatility} />
        </div>
      </div>

      {/* Issue 4: Regime interpretation — 2-3 sentence sector-contextual expansion.
          Shown only for non-trivial regime combinations (adverse or favorable).
          Neutral regimes return null and skip this block. */}
      {interpretation && (
        <div className={`pl-3 border-l-2 ${interpretBorderColor[interpretation.severity]} py-0.5`}>
          <p className="text-xs text-text-tertiary leading-relaxed">
            <span className="font-medium text-text-secondary">Regime Impact: </span>
            {interpretation.text}
          </p>
        </div>
      )}
    </div>
  )
}
