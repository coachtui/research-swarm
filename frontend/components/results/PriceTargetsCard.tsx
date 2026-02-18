'use client'

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

export function PriceTargetsCard({ priceTargets, currentPrice, ticker }: PriceTargetsCardProps) {
  const baseUpside = ((priceTargets.base_target - currentPrice) / currentPrice) * 100
  const bullUpside = ((priceTargets.bull_target - currentPrice) / currentPrice) * 100
  const bearDownside = ((priceTargets.bear_target - currentPrice) / currentPrice) * 100

  return (
    <div className="bg-card border rounded-lg p-6">
      <h2 className="text-xl font-semibold mb-4 flex items-center gap-2">
        🎯 12-Month Price Targets
        <span className="text-sm font-normal text-muted-foreground">
          ({priceTargets.methodology})
        </span>
      </h2>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-4">
        {/* Bear Case */}
        <div className="border-l-4 border-red-500 bg-surface-elevated p-4 rounded">
          <div className="text-sm text-text-secondary mb-1">
            Bear Case ({(priceTargets.bear_probability * 100).toFixed(0)}%)
          </div>
          <div className="text-2xl font-bold text-red-500">
            ${priceTargets.bear_target.toFixed(2)}
          </div>
          <div className="text-sm text-red-500">
            {bearDownside.toFixed(1)}% downside
          </div>
          <p className="text-xs text-text-tertiary mt-2">
            {priceTargets.bear_assumptions}
          </p>
        </div>

        {/* Base Case */}
        <div className="border-l-4 border-blue-500 bg-surface-elevated p-4 rounded">
          <div className="text-sm text-text-secondary mb-1">
            Base Case ({(priceTargets.base_probability * 100).toFixed(0)}%)
          </div>
          <div className="text-2xl font-bold text-blue-500">
            ${priceTargets.base_target.toFixed(2)}
          </div>
          <div className="text-sm text-blue-500">
            {baseUpside > 0 ? '+' : ''}{baseUpside.toFixed(1)}% potential
          </div>
          <p className="text-xs text-text-tertiary mt-2">
            {priceTargets.base_assumptions}
          </p>
        </div>

        {/* Bull Case */}
        <div className="border-l-4 border-green-500 bg-surface-elevated p-4 rounded">
          <div className="text-sm text-text-secondary mb-1">
            Bull Case ({(priceTargets.bull_probability * 100).toFixed(0)}%)
          </div>
          <div className="text-2xl font-bold text-green-500">
            ${priceTargets.bull_target.toFixed(2)}
          </div>
          <div className="text-sm text-green-500">
            +{bullUpside.toFixed(1)}% upside
          </div>
          <p className="text-xs text-text-tertiary mt-2">
            {priceTargets.bull_assumptions}
          </p>
        </div>
      </div>

      <div className="text-sm text-muted-foreground text-center">
        Current Price: ${currentPrice.toFixed(2)} | Target Range: ${priceTargets.bear_target.toFixed(2)} - ${priceTargets.bull_target.toFixed(2)}
      </div>
    </div>
  )
}
