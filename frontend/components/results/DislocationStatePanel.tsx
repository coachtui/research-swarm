'use client'

/**
 * DislocationStatePanel — Section III: Dislocation State.
 *
 * Visual drawdown module showing:
 *   - 52-week high and current drawdown %
 *   - Tier bands (-20/-30/-40/-50) with active tier highlight
 *   - Capacity remaining to add
 *
 * Data from signal_breakdown + compounder_owner drawdown calculations.
 */
export function DislocationStatePanel({
  currentPrice,
  high52Week,
  ma200d,
  position,
}: {
  currentPrice: number | null
  high52Week: number | null
  ma200d: number | null
  position?: {
    tier_state: string
    last_drawdown: number | null
    allocation_pct: number | null
  } | null
}) {
  const drawdownPct = currentPrice && high52Week && high52Week > 0
    ? ((currentPrice / high52Week) - 1) * 100
    : null

  const above200dma = currentPrice && ma200d && ma200d > 0
    ? ((currentPrice / ma200d) - 1) * 100
    : null

  const tiers = [
    { label: '-20%', threshold: -20, addPct: '+2%', key: 't1_20' },
    { label: '-30%', threshold: -30, addPct: '+4%', key: 't2_30' },
    { label: '-40%', threshold: -40, addPct: '+6%', key: 't3_40' },
    { label: '-50%', threshold: -50, addPct: '+8%', key: 't4_50' },
  ]

  const activeTier = position?.tier_state || 'none'
  const currentWeight = position?.allocation_pct ?? 0

  // Guard: if rolling high is missing, tier adds can't be computed
  const rollingHighMissing = !high52Week

  return (
    <div className="space-y-4">
      {/* ── Price Context ─────────────────────────────────────────────── */}
      <div className="grid grid-cols-3 gap-3">
        <PriceTile
          label="252d Rolling High"
          value={high52Week ? `$${high52Week.toFixed(2)}` : 'Data unavailable'}
          color={rollingHighMissing ? 'text-text-tertiary' : undefined}
        />
        <PriceTile
          label="Current Price"
          value={currentPrice ? `$${currentPrice.toFixed(2)}` : '—'}
        />
        <PriceTile
          label="Drawdown"
          value={drawdownPct !== null ? `${drawdownPct.toFixed(1)}%` : '—'}
          color={
            drawdownPct === null ? undefined :
            drawdownPct <= -30 ? 'text-error' :
            drawdownPct <= -20 ? 'text-warning' :
            'text-text-secondary'
          }
        />
      </div>

      {/* ── Tier Bands Visualization ──────────────────────────────────── */}
      <div>
        <h4 className="text-[11px] font-semibold uppercase tracking-wider text-text-tertiary mb-2">
          Drawdown Accumulation Tiers
        </h4>
        {rollingHighMissing && (
          <div className="text-[10px] text-text-tertiary bg-surface-elevated/50 border border-border/40 rounded-lg px-3 py-2 mb-2">
            252d rolling high unavailable — tier adds cannot be computed until price data loads.
          </div>
        )}
        <div className="space-y-1.5">
          {tiers.map((tier) => {
            const isTriggered = drawdownPct !== null && drawdownPct <= tier.threshold
            const isActive = activeTier === tier.key
            const tierApplied = position && isTriggered

            return (
              <div
                key={tier.key}
                className={`flex items-center justify-between rounded-lg px-3 py-2 ${
                  isActive
                    ? 'bg-primary/10 border border-primary/30'
                    : isTriggered
                    ? 'bg-warning/10 border border-warning/20'
                    : 'bg-surface-elevated/50 border border-transparent'
                }`}
              >
                <div className="flex items-center gap-3">
                  {/* Progress indicator */}
                  <div className={`w-2 h-2 rounded-full ${
                    isTriggered ? 'bg-warning' : 'bg-border'
                  }`} />
                  <span className="text-xs font-mono font-semibold text-text-primary">
                    {tier.label}
                  </span>
                  <span className="text-[10px] text-text-tertiary">
                    drawdown
                  </span>
                </div>
                <div className="flex items-center gap-3">
                  <span className={`text-xs font-mono font-bold ${
                    isTriggered ? 'text-success' : 'text-text-tertiary'
                  }`}>
                    {tier.addPct}
                  </span>
                  {tierApplied && (
                    <span className="text-[9px] font-semibold uppercase tracking-wide text-warning bg-warning/10 px-1.5 py-0.5 rounded">
                      Triggered
                    </span>
                  )}
                </div>
              </div>
            )
          })}
        </div>
      </div>

      {/* ── 200DMA Context ────────────────────────────────────────────── */}
      {above200dma !== null && (
        <div className="flex items-center gap-2 text-[11px]">
          <span className="text-text-tertiary">vs 200DMA:</span>
          <span className={`font-mono font-semibold ${
            above200dma >= 30 ? 'text-warning' :
            above200dma >= 0 ? 'text-success' :
            'text-error'
          }`}>
            {above200dma >= 0 ? '+' : ''}{above200dma.toFixed(1)}%
          </span>
          {above200dma >= 30 && (
            <span className="text-[9px] font-semibold uppercase text-warning bg-warning/10 px-1.5 py-0.5 rounded">
              Euphoria Zone
            </span>
          )}
        </div>
      )}

      {/* ── Capacity Remaining (if in portfolio) ──────────────────────── */}
      {position && (
        <div className="flex items-center gap-2 text-[11px]">
          <span className="text-text-tertiary">Current weight:</span>
          <span className="font-mono font-semibold text-text-primary">
            {(currentWeight * 100).toFixed(1)}%
          </span>
          <span className="text-text-tertiary">|</span>
          <span className="text-text-tertiary">Capacity to max (25%):</span>
          <span className="font-mono font-semibold text-text-secondary">
            {((0.25 - currentWeight) * 100).toFixed(1)}%
          </span>
        </div>
      )}
    </div>
  )
}

function PriceTile({
  label,
  value,
  color,
}: {
  label: string
  value: string
  color?: string
}) {
  return (
    <div className="rounded-lg border border-border/40 bg-surface-elevated/50 px-3 py-2">
      <p className="text-[10px] font-semibold uppercase tracking-wider text-text-tertiary">{label}</p>
      <p className={`text-sm font-bold font-mono tabular-nums mt-0.5 ${color || 'text-text-primary'}`}>
        {value}
      </p>
    </div>
  )
}
