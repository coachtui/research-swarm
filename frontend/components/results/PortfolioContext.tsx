import { useState } from 'react'
import { Card, CardContent } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Briefcase, AlertTriangle } from 'lucide-react'
import type { ConvictionPosition, SignalBreakdown } from '@/types/api'

interface PortfolioContextProps {
  ticker: string
  rating: string
  moatScore: number
  financialHealthScore?: number
  sector?: string
  currentPrice: number
  convictionPosition?: ConvictionPosition | null
  signalBreakdown?: SignalBreakdown | null
}

type RiskProfile = 'conservative' | 'moderate' | 'aggressive'

export function PortfolioContext({
  ticker,
  rating,
  moatScore,
  financialHealthScore = 5.0,
  sector = 'Technology',
  currentPrice,
  convictionPosition,
  signalBreakdown,
}: PortfolioContextProps) {
  const [riskProfile, setRiskProfile] = useState<RiskProfile>('moderate')

  // Calculate suggested allocation based on rating, quality, and risk profile
  const getSuggestedAllocation = (profile: RiskProfile) => {
    let baseAllocation: { min: number; max: number; type: string }

    // If we have backend conviction data, use that as the base
    if (convictionPosition) {
      const convictionLevel = convictionPosition.conviction_level.toLowerCase()

      // Determine position type from conviction level
      let positionType = 'Satellite Position'
      if (convictionLevel.includes('high') || convictionPosition.recommended_pct >= 5) {
        positionType = 'Core Holding'
      } else if (convictionLevel.includes('low') || convictionPosition.recommended_pct <= 2) {
        positionType = 'Speculative / Avoid'
      }

      // Use backend's recommended_pct as the base max, derive min
      const backendMax = convictionPosition.recommended_pct
      const backendMin = Math.max(0.5, backendMax * 0.5) // Min is roughly 50% of max

      baseAllocation = {
        min: backendMin,
        max: backendMax,
        type: positionType,
      }
    } else {
      // Fallback: Calculate from quality/rating if no backend data
      if (moatScore >= 8.0 && rating.includes('BUY')) {
        baseAllocation = { min: 3, max: 5, type: 'Core Holding' }
      } else if (moatScore >= 7.0 && rating.includes('BUY')) {
        baseAllocation = { min: 2, max: 4, type: 'Core Holding' }
      } else if (moatScore >= 6.0 || rating === 'HOLD') {
        baseAllocation = { min: 1, max: 2, type: 'Satellite Position' }
      } else {
        baseAllocation = { min: 0, max: 1, type: 'Speculative / Avoid' }
      }
    }

    // Adjust for risk profile
    const multipliers = {
      conservative: 0.7,  // 70% of base allocation (less aggressive than before)
      moderate: 1.0,      // 100% of base allocation
      aggressive: 1.3,    // 130% of base allocation (less aggressive than before)
    }

    const multiplier = multipliers[profile]
    const absoluteMax = convictionPosition?.max_pct || 10 // Use backend's risk-adjusted cap if available

    return {
      min: Math.max(0, Math.round(baseAllocation.min * multiplier * 10) / 10),
      max: Math.min(absoluteMax, Math.round(baseAllocation.max * multiplier * 10) / 10),
      type: baseAllocation.type,
    }
  }

  const allocation = getSuggestedAllocation(riskProfile)
  const portfolioExamples = [
    { size: 10000, position: (10000 * allocation.max) / 100 },
    { size: 50000, position: (50000 * allocation.max) / 100 },
    { size: 100000, position: (100000 * allocation.max) / 100 },
  ]

  // Risk warnings based on quality
  const qualityLevel = financialHealthScore >= 8.0 ? 'high' : financialHealthScore >= 6.0 ? 'medium' : 'low'

  // Fix 6: Signal-conflict override for position sizing language.
  // Trigger conditions (all three must be true):
  //   1. Smart Money composite (avg of institutional + insider + dark_pool) < 3.5
  //   2. Smart Money vs Public divergence magnitude > 4.0 pts
  //      (public composite = avg of news + earnings + analyst + tech_divergence)
  //   3. Rating is HOLD or WAIT
  const institutionalScore = signalBreakdown?.institutional_score ?? null
  const insiderScore = signalBreakdown?.insider_score ?? null
  const darkPoolScore = signalBreakdown?.dark_pool_score ?? null
  const ratingIsHoldOrWait = rating === 'HOLD' || rating === 'WAIT'

  const smartMoneyScoresAvailable =
    institutionalScore != null && insiderScore != null && darkPoolScore != null
  const smartMoneyComposite = smartMoneyScoresAvailable
    ? (institutionalScore! + insiderScore! + darkPoolScore!) / 3
    : null

  const newsScore = signalBreakdown?.news_score ?? null
  const earningsScore = signalBreakdown?.earnings_score ?? null
  const analystScore = signalBreakdown?.analyst_score ?? null
  const techScore = signalBreakdown?.tech_divergence_score ?? null
  const publicScoresAvailable =
    newsScore != null && earningsScore != null && analystScore != null && techScore != null
  const publicComposite = publicScoresAvailable
    ? (newsScore! + earningsScore! + analystScore! + techScore!) / 4
    : null

  const divergenceMagnitude =
    smartMoneyComposite != null && publicComposite != null
      ? Math.abs(smartMoneyComposite - publicComposite)
      : null

  const hasSignalConflict = Boolean(
    smartMoneyComposite != null && smartMoneyComposite < 3.5 &&
    divergenceMagnitude != null && divergenceMagnitude > 4.0 &&
    ratingIsHoldOrWait
  )

  return (
    <Card className="border-primary/20 bg-gradient-to-br from-primary/5 to-primary/10">
      <CardContent className="pt-6 space-y-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Briefcase className="h-5 w-5 text-primary" />
            <div>
              <h3 className="text-lg font-semibold text-text-primary">Portfolio Construction</h3>
              <p className="text-[10px] text-text-tertiary leading-none mt-0.5">
                Multi-factor allocation engine
              </p>
            </div>
            <Badge variant="secondary">{ticker}</Badge>
          </div>

          {/* Risk Profile Selector */}
          <div className="flex items-center gap-1 bg-surface rounded-lg p-1 border border-border">
            {(['conservative', 'moderate', 'aggressive'] as const).map((profile) => (
              <button
                key={profile}
                onClick={() => setRiskProfile(profile)}
                className={`px-3 py-1 text-xs font-medium rounded transition-all ${
                  riskProfile === profile
                    ? 'bg-primary text-white shadow-sm'
                    : 'text-text-tertiary hover:text-text-primary'
                }`}
              >
                {profile.charAt(0).toUpperCase() + profile.slice(1)}
              </button>
            ))}
          </div>
        </div>

        {/* Risk Profile Description */}
        <div className="bg-surface/50 rounded-lg p-3 border border-border">
          <p className="text-xs text-text-secondary">
            <span className="font-medium text-text-primary">
              {riskProfile === 'conservative' && 'Conservative: '}
              {riskProfile === 'moderate' && 'Moderate: '}
              {riskProfile === 'aggressive' && 'Aggressive: '}
            </span>
            {riskProfile === 'conservative' &&
              'Lower position sizes with tighter risk controls - prioritizes capital preservation'}
            {riskProfile === 'moderate' &&
              'Balanced position sizing based on company quality and market signals - standard approach'}
            {riskProfile === 'aggressive' &&
              'Larger positions for high-conviction ideas - accepts higher volatility for greater upside potential'}
          </p>
        </div>

        {/* Sizing Determinants — surfaces the factor inputs driving the allocation range.
            All values are already computed above; this is purely a visual disclosure. */}
        <div className="rounded-lg border border-border/60 bg-surface/30 p-3">
          <p className="text-[10px] uppercase tracking-wider text-text-tertiary mb-2 font-semibold">
            Sizing Determinants
          </p>
          <div className="grid grid-cols-2 md:grid-cols-3 gap-x-4 gap-y-2">
            <div>
              <span className="text-[10px] text-text-tertiary block">Conviction</span>
              <span className="text-xs font-medium text-text-primary">
                {convictionPosition?.conviction_level ??
                  (moatScore >= 7.5 ? 'High' : moatScore >= 5.5 ? 'Medium' : 'Low')}
              </span>
            </div>
            <div>
              <span className="text-[10px] text-text-tertiary block">Financial Quality</span>
              <span
                className={`text-xs font-medium ${
                  qualityLevel === 'high'
                    ? 'text-success'
                    : qualityLevel === 'medium'
                      ? 'text-warning'
                      : 'text-error'
                }`}
              >
                {financialHealthScore.toFixed(1)}/10 ·{' '}
                {qualityLevel.charAt(0).toUpperCase() + qualityLevel.slice(1)}
              </span>
            </div>
            <div>
              <span className="text-[10px] text-text-tertiary block">Signal Conflict</span>
              <span
                className={`text-xs font-medium ${hasSignalConflict ? 'text-warning' : 'text-success'}`}
              >
                {hasSignalConflict ? 'Active — Cap at Satellite' : 'None Detected'}
              </span>
            </div>
            {smartMoneyComposite != null && (
              <div>
                <span className="text-[10px] text-text-tertiary block">Smart Money Flow</span>
                <span
                  className={`text-xs font-medium ${
                    smartMoneyComposite >= 6
                      ? 'text-success'
                      : smartMoneyComposite >= 4
                        ? 'text-warning'
                        : 'text-error'
                  }`}
                >
                  {smartMoneyComposite.toFixed(1)}/10 composite
                </span>
              </div>
            )}
            <div>
              <span className="text-[10px] text-text-tertiary block">Risk Multiplier</span>
              <span className="text-xs font-medium text-text-primary">
                {riskProfile === 'conservative' ? '0.7×' : riskProfile === 'aggressive' ? '1.3×' : '1.0×'}{' '}
                <span className="text-text-tertiary font-normal">({riskProfile})</span>
              </span>
            </div>
            {convictionPosition?.max_pct && (
              <div>
                <span className="text-[10px] text-text-tertiary block">Risk-Adjusted Cap</span>
                <span className="text-xs font-medium text-text-primary">
                  {convictionPosition.max_pct}% max
                </span>
              </div>
            )}
          </div>
        </div>

        {/* Position Sizing Guidance */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div className="space-y-2">
            <p className="text-sm font-medium text-text-secondary">Conviction-Adjusted Range</p>
            <div className="bg-surface rounded-lg p-3 border border-border">
              <div className="flex items-baseline gap-2 mb-1">
                <span className="text-2xl font-bold text-primary">
                  {allocation.min}–{allocation.max}%
                </span>
                <span className="text-xs text-text-tertiary">of portfolio</span>
              </div>
              <p className="text-xs text-text-secondary">{allocation.type}</p>
            </div>

            {/* Quality context */}
            <div className="text-xs space-y-1">
              <div className="flex items-center justify-between">
                <span className="text-text-tertiary">Quality Rating:</span>
                <span className="font-medium text-text-primary">
                  {financialHealthScore.toFixed(1)}/10 Financial Health
                </span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-text-tertiary">Position Type:</span>
                <span className="font-medium text-text-primary">{allocation.type}</span>
              </div>
            </div>
          </div>

          <div className="space-y-2">
            <p className="text-sm font-medium text-text-secondary">Dollar Exposure Calculator</p>
            <div className="bg-surface rounded-lg p-3 border border-border space-y-1.5">
              {portfolioExamples.map((example, i) => (
                <div key={i} className="flex items-center justify-between text-xs">
                  <span className="text-text-tertiary">
                    ${(example.size / 1000).toFixed(0)}K portfolio:
                  </span>
                  <span className="font-medium text-text-primary">
                    ${example.position.toLocaleString()} ({allocation.max}%)
                  </span>
                </div>
              ))}
            </div>
            <p className="text-xs text-text-tertiary italic">
              Based on {allocation.max}% max allocation ({currentPrice > 0 ? Math.floor((portfolioExamples[1].position / currentPrice)) : '~'} shares at ${currentPrice.toFixed(2)})
            </p>
          </div>
        </div>

        {/* Risk Considerations */}
        <div className="bg-surface/50 rounded-lg p-4 border border-border">
          <div className="flex items-start gap-2">
            <AlertTriangle className="h-4 w-4 text-warning mt-0.5 flex-shrink-0" />
            <div className="flex-1 space-y-2">
              <p className="text-xs font-medium text-text-primary">Risk Considerations</p>
              <ul className="space-y-1 text-xs text-text-secondary">
                {/* Fix 6: When smart money divergence conflicts with fundamental quality, override
                    the quality-only copy with a combined assessment that reflects signal reality. */}
                {hasSignalConflict ? (
                  <li className="flex gap-2">
                    <span className="text-warning">⚠</span>
                    <span>
                      Fundamental quality supports long-term thesis, but active smart money distribution
                      signals (Institutional: {institutionalScore!.toFixed(1)}, Insider: {insiderScore!.toFixed(1)}, Dark
                      Pool: {darkPoolScore!.toFixed(1)}) indicate large holders are reducing exposure. Size as
                      satellite position until institutional flows stabilize — do not treat as core holding
                      at current signal levels.
                    </span>
                  </li>
                ) : qualityLevel === 'high' ? (
                  <li className="flex gap-2">
                    <span className="text-success">✓</span>
                    <span>High-quality company suitable as core holding with disciplined sizing</span>
                  </li>
                ) : qualityLevel === 'medium' ? (
                  <li className="flex gap-2">
                    <span className="text-warning">⚠</span>
                    <span>Moderate quality - consider as satellite position, not core holding</span>
                  </li>
                ) : (
                  <li className="flex gap-2">
                    <span className="text-error">⚠</span>
                    <span>Lower quality - limit position size and consider speculative allocation only</span>
                  </li>
                )}
                <li className="flex gap-2">
                  <span className="text-primary">•</span>
                  <span>
                    Check sector concentration: If you own other {sector} stocks, reduce allocation to avoid over-concentration
                  </span>
                </li>
                <li className="flex gap-2">
                  <span className="text-primary">•</span>
                  <span>
                    Timing matters: {rating === 'HOLD' || rating === 'SELL'
                      ? 'Current signals suggest waiting for better entry or holding existing position'
                      : 'Current signals support initiation or addition to position'}
                  </span>
                </li>
              </ul>
            </div>
          </div>
        </div>

        {/* Bottom line */}
        <p className="text-xs text-text-tertiary italic">
          Allocation range is conviction-weighted and signal-gated — sized by company quality, flow alignment, and active conflict state. Position sizing discipline is as structurally important as stock selection.
        </p>
      </CardContent>
    </Card>
  )
}
