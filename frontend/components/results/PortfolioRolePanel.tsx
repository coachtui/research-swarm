'use client'

import { usePortfolioPosition } from '@/lib/hooks/usePortfolio'
import { formatWeight } from '@/lib/ownership-mapping'

/**
 * PortfolioRolePanel — Section V: Portfolio Role.
 *
 * Displays: weight, exposure contribution, sector, role tag.
 * Only meaningful when the user has a portfolio with this ticker.
 * Shows a "not held" state otherwise.
 */
export function PortfolioRolePanel({
  ticker,
  sector,
}: {
  ticker: string
  sector?: string | null
}) {
  const { portfolio, position } = usePortfolioPosition(ticker)

  if (!portfolio) {
    return (
      <div className="text-center py-6">
        <p className="text-sm text-text-tertiary">
          Create a portfolio to see how this position fits your holdings.
        </p>
      </div>
    )
  }

  if (!position) {
    return (
      <div className="text-center py-6">
        <p className="text-sm text-text-tertiary">
          {ticker} is not in your portfolio. Add it via the Holdings tab to see portfolio context.
        </p>
      </div>
    )
  }

  // Compute top-3 exposure
  const positions = portfolio.positions || []
  const sorted = [...positions].sort((a, b) => b.current_weight - a.current_weight)
  const top3 = sorted.slice(0, 3)
  const isInTop3 = top3.some(p => p.ticker === ticker)

  // Sector tickers
  const sectorPositions = sector
    ? positions.filter(p => true) // Would need sector data on positions — simplified
    : []

  // Role tag derivation
  const roleTag = deriveRoleTag(position, portfolio.total_weight)

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        <RoleTile
          label="Portfolio Weight"
          value={formatWeight(position.current_weight)}
        />
        <RoleTile
          label="Top 3 Exposure"
          value={top3.map(p => `${p.ticker} ${formatWeight(p.current_weight)}`).join(', ')}
          small
        />
        <RoleTile
          label="Sector"
          value={sector || 'Unknown'}
        />
        <RoleTile
          label="Role"
          value={roleTag}
        />
      </div>

      {/* Position ranking */}
      <div className="flex items-center gap-2 text-[11px]">
        <span className="text-text-tertiary">Rank:</span>
        <span className="font-mono font-semibold text-text-primary">
          #{sorted.findIndex(p => p.ticker === ticker) + 1} of {positions.length}
        </span>
        {isInTop3 && (
          <span className="text-[9px] font-semibold uppercase text-primary bg-primary/10 px-1.5 py-0.5 rounded">
            Top 3
          </span>
        )}
        <span className="text-text-tertiary">|</span>
        <span className="text-text-tertiary">Quarters held:</span>
        <span className="font-mono font-semibold text-text-primary">
          {position.quarters_held}
        </span>
      </div>
    </div>
  )
}

function RoleTile({ label, value, small }: { label: string; value: string; small?: boolean }) {
  return (
    <div className="rounded-lg border border-border/40 bg-surface-elevated/50 px-3 py-2.5">
      <p className="text-[10px] font-semibold uppercase tracking-wider text-text-tertiary">{label}</p>
      <p className={`font-semibold text-text-primary mt-0.5 ${small ? 'text-[10px]' : 'text-sm'}`}>
        {value}
      </p>
    </div>
  )
}

function deriveRoleTag(
  position: { current_weight: number; compounder_score: number | null; quarters_held: number },
  totalWeight: number,
): string {
  const weight = position.current_weight
  const score = position.compounder_score ?? 0.5
  const quarters = position.quarters_held

  if (weight >= 0.10 && score >= 0.7 && quarters >= 4) return 'Core Engine'
  if (weight >= 0.06 && score >= 0.5) return 'Growth Engine'
  if (weight >= 0.04 && quarters >= 8) return 'Stabilizer'
  if (quarters < 4) return 'New Position'
  return 'Satellite'
}
