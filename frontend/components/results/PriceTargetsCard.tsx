'use client'

// All calculations are IDENTICAL to the original — only visual presentation is refined.
// Changes: institutional header, layered tier labels, probability micro-context strips,
// visual probability allocation bar. No numbers or weights were altered.

interface PriceTargetsCardProps {
  priceTargets: {
    bull_target: number
    bull_probability: number
    bull_assumptions: string
    base_target: number
    base_probability: number
    base_assumptions: string
    bear_target: number
    bear_probability: number
    bear_assumptions: string
    methodology: string
  }
  currentPrice: number
  ticker: string
}

export function PriceTargetsCard({ priceTargets, currentPrice }: PriceTargetsCardProps) {
  const baseUpside = ((priceTargets.base_target - currentPrice) / currentPrice) * 100
  const bullUpside = ((priceTargets.bull_target - currentPrice) / currentPrice) * 100
  const bearDownside = ((priceTargets.bear_target - currentPrice) / currentPrice) * 100

  // Probability-weighted expected value across all three scenario paths — unchanged
  const bearW = priceTargets.bear_probability ?? 0.25
  const baseW = priceTargets.base_probability ?? 0.50
  const bullW = priceTargets.bull_probability ?? 0.25
  const probWeightedEV =
    priceTargets.bear_target * bearW +
    priceTargets.base_target * baseW +
    priceTargets.bull_target * bullW
  const evVsCurrent = ((probWeightedEV - currentPrice) / currentPrice) * 100

  const bearPct  = Math.round(bearW * 100)
  const basePct  = Math.round(baseW * 100)
  const bullPct  = Math.round(bullW * 100)

  return (
    <div className="bg-card border rounded-lg p-6">

      {/* Institutional header — no emoji, structural framing */}
      <div className="flex items-start justify-between mb-2">
        <div>
          <h2 className="text-base font-semibold text-text-primary tracking-tight">
            Scenario Value Construct
          </h2>
          <p className="text-xs text-text-tertiary mt-0.5">
            {priceTargets.methodology} · 12-Month Calibration Window
          </p>
        </div>
        <span className="text-[10px] font-mono text-text-tertiary/60 border border-border rounded px-1.5 py-0.5 mt-0.5 shrink-0">
          Structural Layer
        </span>
      </div>

      <p className="text-xs text-text-tertiary mb-4 leading-relaxed border-l-2 border-border pl-2.5">
        Probabilistic outcome paths calibrated to signal divergence — not direct fair value forecasts.
        <span className="block text-text-tertiary/60 italic mt-0.5">
          Scenario weights: heuristic-derived · regime-conditioned reliability
        </span>
      </p>

      {/* Probability allocation strip — purely visual, reflects existing weight values */}
      <div className="mb-5">
        <div className="text-[10px] text-text-tertiary mb-1.5 uppercase tracking-wider font-medium">
          Probability Allocation
        </div>
        <div className="flex h-1.5 rounded-full overflow-hidden gap-px">
          <div
            className="bg-error/70 rounded-l-full transition-all"
            style={{ width: `${bearPct}%` }}
          />
          <div
            className="bg-blue-500/70 transition-all"
            style={{ width: `${basePct}%` }}
          />
          <div
            className="bg-success/70 rounded-r-full transition-all"
            style={{ width: `${bullPct}%` }}
          />
        </div>
        <div className="flex justify-between text-[10px] text-text-tertiary mt-1">
          <span>{bearPct}% Risk</span>
          <span>{basePct}% Continuation</span>
          <span>{bullPct}% Re-rating</span>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-4">

        {/* ── Tier 1: Capital Preservation Threshold ── */}
        <div className="border-l-4 border-red-500 bg-surface-elevated p-4 rounded">
          <div className="text-[10px] text-error/70 mb-0.5 uppercase tracking-wider font-medium">
            Risk Scenario
          </div>
          <div className="text-xs text-text-secondary mb-2 font-medium leading-tight">
            Capital Preservation Threshold
          </div>
          <div className="text-2xl font-bold text-red-500 font-mono">
            ${priceTargets.bear_target.toFixed(2)}
          </div>
          <div className="text-sm text-red-500">
            {bearDownside.toFixed(1)}% downside
          </div>
          {/* Per-scenario probability micro-context */}
          <div className="mt-2.5 flex items-center gap-1.5">
            <div className="h-1 bg-error/20 rounded-full flex-1">
              <div
                className="h-full bg-error/60 rounded-full transition-all"
                style={{ width: `${bearPct}%` }}
              />
            </div>
            <span className="text-[10px] text-text-tertiary font-mono w-7 text-right shrink-0">
              {bearPct}%
            </span>
          </div>
          <p className="text-[10px] text-text-tertiary/60 italic mt-0.5">
            heuristic weight · regime-conditioned
          </p>
          <p className="text-xs text-text-tertiary mt-2.5 pt-2 border-t border-border/50 leading-relaxed">
            {priceTargets.bear_assumptions}
          </p>
        </div>

        {/* ── Tier 2: Regime-Adjusted Structural Value ── */}
        <div className="border-l-4 border-blue-500 bg-surface-elevated p-4 rounded">
          <div className="text-[10px] text-blue-400/70 mb-0.5 uppercase tracking-wider font-medium">
            Continuation Scenario
          </div>
          <div className="text-xs text-text-secondary mb-2 font-medium leading-tight">
            Regime-Adjusted Structural Value
          </div>
          <div className="text-2xl font-bold text-blue-500 font-mono">
            ${priceTargets.base_target.toFixed(2)}
          </div>
          <div className="text-sm text-blue-500">
            {baseUpside > 0 ? '+' : ''}{baseUpside.toFixed(1)}% potential
          </div>
          <div className="mt-2.5 flex items-center gap-1.5">
            <div className="h-1 bg-blue-500/20 rounded-full flex-1">
              <div
                className="h-full bg-blue-500/60 rounded-full transition-all"
                style={{ width: `${basePct}%` }}
              />
            </div>
            <span className="text-[10px] text-text-tertiary font-mono w-7 text-right shrink-0">
              {basePct}%
            </span>
          </div>
          <p className="text-[10px] text-text-tertiary/60 italic mt-0.5">
            heuristic weight · regime-conditioned
          </p>
          <p className="text-xs text-text-tertiary mt-2.5 pt-2 border-t border-border/50 leading-relaxed">
            {priceTargets.base_assumptions}
          </p>
        </div>

        {/* ── Tier 3: Growth-Sustained Structural Range ── */}
        <div className="border-l-4 border-green-500 bg-surface-elevated p-4 rounded">
          <div className="text-[10px] text-success/70 mb-0.5 uppercase tracking-wider font-medium">
            Re-rating Scenario
          </div>
          <div className="text-xs text-text-secondary mb-2 font-medium leading-tight">
            Growth-Sustained Structural Range
          </div>
          <div className="text-2xl font-bold text-green-500 font-mono">
            ${priceTargets.bull_target.toFixed(2)}
          </div>
          <div className="text-sm text-green-500">
            +{bullUpside.toFixed(1)}% upside
          </div>
          <div className="mt-2.5 flex items-center gap-1.5">
            <div className="h-1 bg-success/20 rounded-full flex-1">
              <div
                className="h-full bg-success/60 rounded-full transition-all"
                style={{ width: `${bullPct}%` }}
              />
            </div>
            <span className="text-[10px] text-text-tertiary font-mono w-7 text-right shrink-0">
              {bullPct}%
            </span>
          </div>
          <p className="text-[10px] text-text-tertiary/60 italic mt-0.5">
            heuristic weight · regime-conditioned
          </p>
          <p className="text-xs text-text-tertiary mt-2.5 pt-2 border-t border-border/50 leading-relaxed">
            {priceTargets.bull_assumptions}
          </p>
        </div>
      </div>

      {/* Scenario-weighted EV summary — unchanged calculation */}
      <div className="mt-4 pt-4 border-t border-border">
        <div className="flex items-center justify-between flex-wrap gap-2 text-xs mb-1.5">
          <div className="flex items-center gap-2">
            <span className="text-text-tertiary">Scenario-Weighted Expected Value</span>
            <span className="font-semibold text-text-primary font-mono">
              ${probWeightedEV.toFixed(2)}
            </span>
            <span className={`font-medium ${evVsCurrent >= 0 ? 'text-success' : 'text-error'}`}>
              {evVsCurrent > 0 ? '+' : ''}{evVsCurrent.toFixed(1)}% vs current
            </span>
          </div>
          <span className="text-[10px] font-mono text-text-tertiary/60">
            {bearPct}/{basePct}/{bullPct} risk·cont·rerating
          </span>
        </div>
        <div className="text-[10px] text-text-tertiary">
          Current:{' '}
          <span className="font-mono">${currentPrice.toFixed(2)}</span>
          {' · '}
          Scenario range:{' '}
          <span className="font-mono">
            ${priceTargets.bear_target.toFixed(2)} – ${priceTargets.bull_target.toFixed(2)}
          </span>
          {' · '}
          <span className="italic text-text-tertiary/50">
            Heuristic weights · regime-conditioned reliability
          </span>
        </div>
      </div>
    </div>
  )
}
