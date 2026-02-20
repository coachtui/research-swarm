import type { SignalBreakdown } from '@/types/api'

interface AnalogProfile {
  scenario: string
  resolution: string
  probability: string
  volatility: string
}

function deriveAnalog(breakdown: SignalBreakdown): AnalogProfile {
  const hasDivergence = breakdown.has_divergence
  const spread = breakdown.signal_spread ?? 0
  const overall = breakdown.overall_score ?? 5

  if (!hasDivergence && overall >= 6.5) {
    return {
      scenario: 'Broad Bullish Alignment',
      resolution: '2–6 weeks typical',
      probability: '~65% historical upside follow-through',
      volatility: 'Low-to-moderate — trending conditions more reliable when signals broadly agree',
    }
  }
  if (!hasDivergence && overall <= 4.0) {
    return {
      scenario: 'Broad Bearish Alignment',
      resolution: '2–6 weeks typical',
      probability: '~62% historical downside continuation',
      volatility: 'Elevated drawdown risk; defensive positioning historically advantaged',
    }
  }
  if (hasDivergence && spread >= 3.5) {
    return {
      scenario: 'High Signal Conflict',
      resolution: '1–4 weeks typical',
      probability: '~55% resolve toward fundamental signal',
      volatility: 'Elevated realized volatility expected during resolution window',
    }
  }
  if (hasDivergence) {
    return {
      scenario: 'Moderate Signal Divergence',
      resolution: '2–8 weeks typical',
      probability: '~57% resolve toward fundamental signal',
      volatility: 'Above-average intraday swings; wider spreads possible near resolution',
    }
  }
  return {
    scenario: 'Balanced / Mixed Signals',
    resolution: '3–10 weeks typical',
    probability: 'Outcome distribution near 50/50 — catalyst-dependent',
    volatility: 'Moderate — expect directional clarity once a signal breaks the tie',
  }
}

interface HistoricalAnalogPanelProps {
  breakdown: SignalBreakdown
}

export function HistoricalAnalogPanel({ breakdown }: HistoricalAnalogPanelProps) {
  const analog = deriveAnalog(breakdown)

  return (
    <div className="border border-border rounded-lg p-4 bg-surface">
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-sm font-semibold text-text-primary">Historical Analog Behavior</h3>
        <span className="text-[10px] text-text-tertiary bg-surface-elevated px-2 py-0.5 rounded border border-border uppercase tracking-wide">
          Heuristic · Not backtested
        </span>
      </div>

      <p className="text-xs font-medium text-text-secondary mb-3 pb-3 border-b border-border-subtle">
        Current pattern matches: <span className="text-text-primary">{analog.scenario}</span>
      </p>

      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <div>
          <p className="text-[10px] text-text-tertiary uppercase tracking-wide mb-1">
            Typical Resolution
          </p>
          <p className="text-sm font-semibold text-text-primary">{analog.resolution}</p>
        </div>
        <div>
          <p className="text-[10px] text-text-tertiary uppercase tracking-wide mb-1">
            Probability Bias
          </p>
          <p className="text-sm font-semibold text-text-primary">{analog.probability}</p>
        </div>
        <div>
          <p className="text-[10px] text-text-tertiary uppercase tracking-wide mb-1">
            Volatility Profile
          </p>
          <p className="text-xs text-text-secondary leading-snug">{analog.volatility}</p>
        </div>
      </div>
    </div>
  )
}
