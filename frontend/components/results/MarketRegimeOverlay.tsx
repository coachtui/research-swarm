'use client'

import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip'
import { Info } from 'lucide-react'
import type { SignalBreakdown } from '@/types/api'

type RegimeColor = 'success' | 'neutral' | 'error' | 'warning' | 'cyan'

interface RegimeItem {
  label: string
  value: string
  color: RegimeColor
  tooltip: string
}

function deriveRiskEnvironment(breakdown: SignalBreakdown): RegimeItem {
  const score = breakdown.overall_score ?? 5
  if (score >= 6.5) {
    return {
      label: 'Risk Environment',
      value: 'Risk-On',
      color: 'success',
      tooltip:
        'Broad signal consensus points to favorable conditions for risk assets. Bullish signals dominate the matrix, indicating market participants are positioned for upside.',
    }
  }
  if (score <= 4.0) {
    return {
      label: 'Risk Environment',
      value: 'Risk-Off',
      color: 'error',
      tooltip:
        'Signal consensus indicates defensive positioning is warranted. Bearish readings across multiple signals suggest elevated caution. Risk assets may face headwinds.',
    }
  }
  return {
    label: 'Risk Environment',
    value: 'Neutral',
    color: 'neutral',
    tooltip:
      'Signal matrix is balanced without a clear directional conviction. Neither risk-on nor risk-off conditions dominate. Await a cleaner signal before establishing directional positioning.',
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
      tooltip:
        'Institutional and dark pool activity indicate net accumulation. Large capital flows suggest expanding liquidity — institutions are adding exposure, which historically supports price.',
    }
  }
  if (avg <= 4.2) {
    return {
      label: 'Liquidity State',
      value: 'Contraction',
      color: 'warning',
      tooltip:
        'Institutional selling pressure and reduced dark pool activity point to liquidity contraction. Smart money appears to be reducing exposure, which can create supply overhang.',
    }
  }
  return {
    label: 'Liquidity State',
    value: 'Neutral',
    color: 'neutral',
    tooltip:
      'Institutional and dark pool activity show no strong directional bias. Liquidity conditions are balanced — neither aggressive accumulation nor distribution is detected.',
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
      tooltip:
        'High signal dispersion indicates elevated uncertainty. Wide spread between bullish and bearish signals historically corresponds to periods of elevated realized volatility and larger intraday price swings.',
    }
  }
  if (spread >= 2.0 || spreadLabel === 'Moderate') {
    return {
      label: 'Volatility State',
      value: 'Elevated',
      color: 'warning',
      tooltip:
        'Moderate signal divergence is present. Uncertainty is above baseline — expect more variable price action until signals converge. Not a stress condition, but noteworthy.',
    }
  }
  return {
    label: 'Volatility State',
    value: 'Low',
    color: 'success',
    tooltip:
      'Signal convergence suggests low volatility conditions. When signals broadly agree, realized volatility tends to be lower and trending conditions are more reliable.',
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
        <p className="text-xs leading-relaxed">{item.tooltip}</p>
      </TooltipContent>
    </Tooltip>
  )
}

interface MarketRegimeOverlayProps {
  breakdown: SignalBreakdown
}

export function MarketRegimeOverlay({ breakdown }: MarketRegimeOverlayProps) {
  const risk = deriveRiskEnvironment(breakdown)
  const liquidity = deriveLiquidityState(breakdown)
  const volatility = deriveVolatilityState(breakdown)

  return (
    <div className="flex items-center justify-between gap-4 py-3 px-4 rounded-md bg-surface-elevated/60 border border-border-subtle">
      <span className="text-xs font-medium text-text-tertiary uppercase tracking-wide shrink-0">
        Market Regime
      </span>
      <div className="flex items-center gap-6 flex-wrap justify-end">
        <RegimeBadge item={risk} />
        <RegimeBadge item={liquidity} />
        <RegimeBadge item={volatility} />
      </div>
    </div>
  )
}
