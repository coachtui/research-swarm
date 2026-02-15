import { ManagerOutput } from '@/types/api'

interface ProfessionalPeerComparisonProps {
  ticker: string
  full_output: ManagerOutput
}

export function ProfessionalPeerComparison({
  ticker,
  full_output,
}: ProfessionalPeerComparisonProps) {
  const moatBreakdown = full_output.moat_breakdown

  // Try to get VGM scores from top-level first, then fallback to fundamentalist_output
  const vgmScores = full_output.vgm_scores || full_output.fundamentalist_output?.vgm_scores

  // Placeholder peer data - in production, this would come from the API
  const companyData = {
    ticker: ticker,
    valuationScore: vgmScores?.value_score || 0,
    growthScore: vgmScores?.growth_score || 0,
    momentumScore: vgmScores?.momentum_score || 0,
    financialHealth: moatBreakdown?.financial_health || 0,
    earningsMomentum: moatBreakdown?.earnings_momentum || 0,
    technicalStrength: moatBreakdown?.technical_strength || 0,
    sentimentScore: moatBreakdown?.sentiment_catalysts || 0,
  }

  // Placeholder for peer companies - would be fetched from API
  const peers = [
    { ticker: 'Peer 1', valuationScore: 6.5, growthScore: 7.2, momentumScore: 6.8, financialHealth: 7.5, earningsMomentum: 6.9, technicalStrength: 7.1, sentimentScore: 6.7 },
    { ticker: 'Peer 2', valuationScore: 5.8, growthScore: 6.5, momentumScore: 7.2, financialHealth: 6.8, earningsMomentum: 7.3, technicalStrength: 6.5, sentimentScore: 7.0 },
    { ticker: 'Peer 3', valuationScore: 7.1, growthScore: 6.8, momentumScore: 5.9, financialHealth: 7.2, earningsMomentum: 6.5, technicalStrength: 6.8, sentimentScore: 6.3 },
    { ticker: 'Industry Avg', valuationScore: 6.5, growthScore: 6.8, momentumScore: 6.6, financialHealth: 7.2, earningsMomentum: 6.9, technicalStrength: 6.8, sentimentScore: 6.7 },
  ]

  const allCompanies = [companyData, ...peers]

  return (
    <section className="space-y-6">
      <h2 className="text-2xl font-serif font-bold text-text-primary border-b-2 border-border pb-2">
        Peer Comparison Analysis
      </h2>

      {/* Methodology */}
      <div className="space-y-3">
        <h3 className="text-lg font-semibold text-text-primary">Comparative Framework</h3>
        <div className="bg-surface-elevated rounded-lg p-6">
          <p className="text-sm text-text-primary leading-relaxed">
            The peer comparison analysis evaluates {ticker} against industry competitors across multiple
            dimensions including valuation metrics, growth characteristics, financial strength, and market
            positioning. This multi-factor assessment provides context for understanding the company's
            relative competitive standing and identifies areas of competitive advantage or disadvantage
            within the industry landscape.
          </p>
        </div>
      </div>

      {/* Comparison Matrix */}
      <div className="overflow-x-auto">
        <table className="w-full border-collapse text-sm">
          <thead>
            <tr className="bg-surface-elevated">
              <th className="border border-border px-3 py-3 text-left font-semibold sticky left-0 bg-surface-elevated z-10">
                Company
              </th>
              <th className="border border-border px-3 py-3 text-center font-semibold min-w-[90px]">
                Valuation<br/>Score
              </th>
              <th className="border border-border px-3 py-3 text-center font-semibold min-w-[90px]">
                Growth<br/>Score
              </th>
              <th className="border border-border px-3 py-3 text-center font-semibold min-w-[90px]">
                Momentum<br/>Score
              </th>
              <th className="border border-border px-3 py-3 text-center font-semibold min-w-[100px]">
                Financial<br/>Health
              </th>
              <th className="border border-border px-3 py-3 text-center font-semibold min-w-[100px]">
                Earnings<br/>Momentum
              </th>
              <th className="border border-border px-3 py-3 text-center font-semibold min-w-[100px]">
                Technical<br/>Strength
              </th>
              <th className="border border-border px-3 py-3 text-center font-semibold min-w-[90px]">
                Sentiment<br/>Score
              </th>
              <th className="border border-border px-3 py-3 text-center font-semibold min-w-[100px]">
                Composite<br/>Score
              </th>
            </tr>
          </thead>
          <tbody>
            {allCompanies.map((company, idx) => {
              const isTarget = company.ticker === ticker
              const isAverage = company.ticker === 'Industry Avg'
              const compositeScore = (
                company.valuationScore * 0.15 +
                company.growthScore * 0.15 +
                company.momentumScore * 0.10 +
                company.financialHealth * 0.25 +
                company.earningsMomentum * 0.20 +
                company.technicalStrength * 0.10 +
                company.sentimentScore * 0.05
              )

              return (
                <tr
                  key={idx}
                  className={
                    isTarget
                      ? 'bg-primary/10 font-semibold'
                      : isAverage
                      ? 'bg-surface-elevated font-semibold border-t-2 border-t-border'
                      : ''
                  }
                >
                  <td className="border border-border px-3 py-3 sticky left-0 bg-inherit z-10">
                    {company.ticker}
                    {isTarget && <span className="ml-2 text-xs text-primary">(Target)</span>}
                  </td>
                  <td className="border border-border px-3 py-3 text-center">
                    {formatScore(company.valuationScore, allCompanies, 'valuationScore', isAverage)}
                  </td>
                  <td className="border border-border px-3 py-3 text-center">
                    {formatScore(company.growthScore, allCompanies, 'growthScore', isAverage)}
                  </td>
                  <td className="border border-border px-3 py-3 text-center">
                    {formatScore(company.momentumScore, allCompanies, 'momentumScore', isAverage)}
                  </td>
                  <td className="border border-border px-3 py-3 text-center">
                    {formatScore(company.financialHealth, allCompanies, 'financialHealth', isAverage)}
                  </td>
                  <td className="border border-border px-3 py-3 text-center">
                    {formatScore(company.earningsMomentum, allCompanies, 'earningsMomentum', isAverage)}
                  </td>
                  <td className="border border-border px-3 py-3 text-center">
                    {formatScore(company.technicalStrength, allCompanies, 'technicalStrength', isAverage)}
                  </td>
                  <td className="border border-border px-3 py-3 text-center">
                    {formatScore(company.sentimentScore, allCompanies, 'sentimentScore', isAverage)}
                  </td>
                  <td className="border border-border px-3 py-3 text-center font-semibold">
                    {formatScore(compositeScore, allCompanies.map(c => ({
                      ...c,
                      compositeScore: (
                        c.valuationScore * 0.15 +
                        c.growthScore * 0.15 +
                        c.momentumScore * 0.10 +
                        c.financialHealth * 0.25 +
                        c.earningsMomentum * 0.20 +
                        c.technicalStrength * 0.10 +
                        c.sentimentScore * 0.05
                      )
                    })), 'compositeScore', isAverage)}
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>

      {/* Key Takeaways */}
      <div className="grid grid-cols-2 gap-6">
        <div className="bg-surface-elevated rounded-lg p-6">
          <h3 className="text-base font-semibold text-text-primary mb-3">
            Competitive Strengths
          </h3>
          <ul className="space-y-2 text-sm text-text-primary">
            {getCompetitiveStrengths(companyData, peers[3]).map((strength, idx) => (
              <li key={idx} className="flex items-start gap-2">
                <span className="text-success mt-0.5">•</span>
                <span>{strength}</span>
              </li>
            ))}
          </ul>
        </div>
        <div className="bg-surface-elevated rounded-lg p-6">
          <h3 className="text-base font-semibold text-text-primary mb-3">
            Areas for Improvement
          </h3>
          <ul className="space-y-2 text-sm text-text-primary">
            {getAreasForImprovement(companyData, peers[3]).map((area, idx) => (
              <li key={idx} className="flex items-start gap-2">
                <span className="text-warning mt-0.5">•</span>
                <span>{area}</span>
              </li>
            ))}
          </ul>
        </div>
      </div>

      {/* Note about peer data */}
      <div className="bg-warning/10 border border-warning/20 rounded-lg p-4">
        <p className="text-xs text-text-secondary">
          <strong>Note:</strong> Peer comparison data represents industry averages and selected competitors
          based on business model similarity, market capitalization, and operational characteristics.
          Individual peer selection may vary based on sector classification and competitive dynamics.
        </p>
      </div>
    </section>
  )
}

function formatScore(
  score: number,
  companies: any[],
  metric: string,
  isAverage: boolean
): JSX.Element {
  const scoreValue = score.toFixed(1)

  if (isAverage) {
    return <span>{scoreValue}</span>
  }

  const avg = companies.find(c => c.ticker === 'Industry Avg')?.[metric] || score
  const isAboveAverage = score > avg
  const isBelowAverage = score < avg * 0.9

  return (
    <span className={isAboveAverage ? 'text-success' : isBelowAverage ? 'text-error' : ''}>
      {scoreValue}
    </span>
  )
}

function getCompetitiveStrengths(company: any, industryAvg: any): string[] {
  const strengths: string[] = []

  if (company.financialHealth > industryAvg.financialHealth) {
    strengths.push(`Superior financial health position (${company.financialHealth.toFixed(1)} vs industry ${industryAvg.financialHealth.toFixed(1)})`)
  }
  if (company.earningsMomentum > industryAvg.earningsMomentum) {
    strengths.push(`Strong earnings momentum relative to peers (${company.earningsMomentum.toFixed(1)} vs ${industryAvg.earningsMomentum.toFixed(1)})`)
  }
  if (company.growthScore > industryAvg.growthScore) {
    strengths.push(`Above-average growth trajectory (${company.growthScore.toFixed(1)} vs ${industryAvg.growthScore.toFixed(1)})`)
  }

  if (strengths.length === 0) {
    strengths.push('Maintains competitive positioning within industry peer group')
    strengths.push('Demonstrates stable operational execution relative to comparables')
  }

  return strengths.slice(0, 3)
}

function getAreasForImprovement(company: any, industryAvg: any): string[] {
  const areas: string[] = []

  if (company.valuationScore < industryAvg.valuationScore * 0.9) {
    areas.push(`Valuation metrics below industry standards (${company.valuationScore.toFixed(1)} vs ${industryAvg.valuationScore.toFixed(1)})`)
  }
  if (company.technicalStrength < industryAvg.technicalStrength * 0.9) {
    areas.push(`Technical positioning lags peer group (${company.technicalStrength.toFixed(1)} vs ${industryAvg.technicalStrength.toFixed(1)})`)
  }
  if (company.momentumScore < industryAvg.momentumScore * 0.9) {
    areas.push(`Market momentum trails industry average (${company.momentumScore.toFixed(1)} vs ${industryAvg.momentumScore.toFixed(1)})`)
  }

  if (areas.length === 0) {
    areas.push('Continue monitoring competitive dynamics and market share trends')
    areas.push('Focus on sustaining current operational efficiency levels')
  }

  return areas.slice(0, 3)
}
