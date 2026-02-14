import { ManagerOutput } from '@/types/api'

interface ProfessionalRiskFactorsProps {
  full_output: ManagerOutput
}

interface RiskCategory {
  category: string
  severity: 'HIGH' | 'MODERATE' | 'LOW'
  factors: string[]
  mitigation: string
}

export function ProfessionalRiskFactors({ full_output }: ProfessionalRiskFactorsProps) {
  const riskFactors = full_output.risk_factors || []

  // Categorize risks into 6 major categories
  const categorizedRisks = categorizeRisks(riskFactors)

  return (
    <section className="space-y-6">
      <h2 className="text-2xl font-serif font-bold text-text-primary border-b-2 border-border pb-2">
        Risk Factor Analysis
      </h2>

      {/* Risk Framework */}
      <div className="bg-surface-elevated rounded-lg p-6">
        <h3 className="text-base font-semibold text-text-primary mb-3">
          Risk Assessment Framework
        </h3>
        <p className="text-sm text-text-primary leading-relaxed">
          The risk analysis employs a comprehensive framework evaluating potential adverse factors
          across operational, financial, competitive, regulatory, market, and macroeconomic dimensions.
          Each risk category is assessed for severity and probability, with consideration given to
          management's ability to mitigate or control identified risks. This multi-dimensional approach
          provides investors with a holistic view of the investment risk profile.
        </p>
      </div>

      {/* Risk Summary Matrix */}
      <div className="space-y-3">
        <h3 className="text-lg font-semibold text-text-primary">Risk Category Overview</h3>
        <table className="w-full border-collapse text-sm">
          <thead>
            <tr className="bg-surface-elevated">
              <th className="border border-border px-4 py-3 text-left font-semibold">
                Risk Category
              </th>
              <th className="border border-border px-4 py-3 text-center font-semibold">
                Severity
              </th>
              <th className="border border-border px-4 py-3 text-center font-semibold">
                Key Factors
              </th>
              <th className="border border-border px-4 py-3 text-left font-semibold">
                Primary Concerns
              </th>
            </tr>
          </thead>
          <tbody>
            {categorizedRisks.map((risk, idx) => (
              <tr key={idx}>
                <td className="border border-border px-4 py-3 font-semibold">
                  {risk.category}
                </td>
                <td className="border border-border px-4 py-3 text-center">
                  <span
                    className={`inline-block px-3 py-1 rounded text-xs font-semibold ${
                      risk.severity === 'HIGH'
                        ? 'bg-error/20 text-error'
                        : risk.severity === 'MODERATE'
                        ? 'bg-warning/20 text-warning'
                        : 'bg-success/20 text-success'
                    }`}
                  >
                    {risk.severity}
                  </span>
                </td>
                <td className="border border-border px-4 py-3 text-center">
                  {risk.factors.length}
                </td>
                <td className="border border-border px-4 py-3">
                  {risk.factors[0] || 'No specific concerns identified'}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Detailed Risk Analysis */}
      <div className="space-y-6">
        <h3 className="text-lg font-semibold text-text-primary">Detailed Risk Assessment</h3>
        {categorizedRisks.map((risk, idx) => (
          <div
            key={idx}
            className="border-l-4 rounded-lg p-6 bg-surface-elevated"
            style={{
              borderLeftColor:
                risk.severity === 'HIGH'
                  ? 'rgb(239, 68, 68)'
                  : risk.severity === 'MODERATE'
                  ? 'rgb(245, 158, 11)'
                  : 'rgb(34, 197, 94)',
            }}
          >
            <div className="flex items-start justify-between mb-4">
              <h4 className="text-base font-semibold text-text-primary">{risk.category}</h4>
              <span
                className={`px-3 py-1 rounded text-xs font-semibold ${
                  risk.severity === 'HIGH'
                    ? 'bg-error/20 text-error'
                    : risk.severity === 'MODERATE'
                    ? 'bg-warning/20 text-warning'
                    : 'bg-success/20 text-success'
                }`}
              >
                {risk.severity} RISK
              </span>
            </div>

            <div className="space-y-4">
              <div>
                <p className="text-xs font-semibold text-text-secondary uppercase tracking-wide mb-2">
                  Identified Risk Factors
                </p>
                <ul className="space-y-2">
                  {risk.factors.map((factor, factorIdx) => (
                    <li key={factorIdx} className="flex items-start gap-2 text-sm text-text-primary">
                      <span className="text-text-tertiary mt-1">•</span>
                      <span>{factor}</span>
                    </li>
                  ))}
                </ul>
              </div>

              <div className="bg-background/50 rounded-lg p-4">
                <p className="text-xs font-semibold text-text-secondary uppercase tracking-wide mb-2">
                  Mitigation Considerations
                </p>
                <p className="text-sm text-text-primary leading-relaxed">{risk.mitigation}</p>
              </div>
            </div>
          </div>
        ))}
      </div>

      {/* Overall Risk Assessment */}
      <div className="bg-surface-elevated border-2 border-border rounded-lg p-6">
        <h3 className="text-base font-semibold text-text-primary mb-3">
          Overall Risk Profile
        </h3>
        <p className="text-sm text-text-primary leading-relaxed">
          {getOverallRiskAssessment(categorizedRisks)}
        </p>
      </div>
    </section>
  )
}

function categorizeRisks(riskFactors: string[]): RiskCategory[] {
  const categories: RiskCategory[] = [
    {
      category: 'Operational Risk',
      severity: 'LOW',
      factors: [],
      mitigation:
        'Management should focus on operational efficiency improvements, supply chain resilience, and execution consistency to mitigate operational risks.',
    },
    {
      category: 'Financial Risk',
      severity: 'LOW',
      factors: [],
      mitigation:
        'Maintain prudent capital allocation, monitor leverage ratios, and ensure adequate liquidity buffers to address potential financial stress scenarios.',
    },
    {
      category: 'Competitive Risk',
      severity: 'LOW',
      factors: [],
      mitigation:
        'Continue investing in innovation, brand differentiation, and customer retention to sustain competitive positioning in dynamic market environments.',
    },
    {
      category: 'Regulatory & Legal Risk',
      severity: 'LOW',
      factors: [],
      mitigation:
        'Proactive compliance programs, regulatory engagement, and legal risk management frameworks can help mitigate exposure to regulatory changes.',
    },
    {
      category: 'Market Risk',
      severity: 'LOW',
      factors: [],
      mitigation:
        'Diversification strategies, hedging mechanisms, and adaptive market strategies can help manage exposure to market volatility and cyclical dynamics.',
    },
    {
      category: 'Macroeconomic Risk',
      severity: 'LOW',
      factors: [],
      mitigation:
        'Scenario planning, geographic diversification, and flexible cost structures provide resilience against macroeconomic headwinds and policy changes.',
    },
  ]

  // Categorize each risk factor
  riskFactors.forEach((risk) => {
    const lowerRisk = risk.toLowerCase()

    if (
      lowerRisk.includes('execution') ||
      lowerRisk.includes('operational') ||
      lowerRisk.includes('supply chain') ||
      lowerRisk.includes('production')
    ) {
      categories[0].factors.push(risk)
    } else if (
      lowerRisk.includes('debt') ||
      lowerRisk.includes('cash flow') ||
      lowerRisk.includes('liquidity') ||
      lowerRisk.includes('financial health')
    ) {
      categories[1].factors.push(risk)
    } else if (
      lowerRisk.includes('competition') ||
      lowerRisk.includes('market share') ||
      lowerRisk.includes('pricing power') ||
      lowerRisk.includes('competitive')
    ) {
      categories[2].factors.push(risk)
    } else if (
      lowerRisk.includes('regulatory') ||
      lowerRisk.includes('compliance') ||
      lowerRisk.includes('legal') ||
      lowerRisk.includes('litigation')
    ) {
      categories[3].factors.push(risk)
    } else if (
      lowerRisk.includes('valuation') ||
      lowerRisk.includes('volatility') ||
      lowerRisk.includes('market conditions') ||
      lowerRisk.includes('technical')
    ) {
      categories[4].factors.push(risk)
    } else {
      categories[5].factors.push(risk)
    }
  })

  // Adjust severity based on number of factors and keyword analysis
  categories.forEach((category) => {
    if (category.factors.length === 0) {
      category.factors.push('No material risks identified in this category')
    } else if (category.factors.length >= 3) {
      category.severity = 'HIGH'
    } else if (category.factors.length >= 2) {
      category.severity = 'MODERATE'
    } else {
      // 1 factor: check for high-impact keywords to determine severity
      const hasHighImpactKeywords = category.factors.some((factor) => {
        const lower = factor.toLowerCase()
        return (
          lower.includes('significant') ||
          lower.includes('substantial') ||
          lower.includes('major') ||
          lower.includes('critical') ||
          lower.includes('severe') ||
          lower.includes('material')
        )
      })
      category.severity = hasHighImpactKeywords ? 'MODERATE' : 'LOW'
    }
  })

  return categories
}

function getOverallRiskAssessment(categories: RiskCategory[]): string {
  const highCount = categories.filter((c) => c.severity === 'HIGH').length
  const moderateCount = categories.filter((c) => c.severity === 'MODERATE').length

  if (highCount >= 3) {
    return `The investment presents an elevated risk profile with ${highCount} high-severity risk categories
      identified. Investors should carefully evaluate their risk tolerance and consider position sizing
      accordingly. Enhanced due diligence and ongoing monitoring of key risk indicators are essential.
      The investment may be suitable primarily for risk-tolerant investors with appropriate portfolio
      diversification.`
  } else if (highCount >= 1 || moderateCount >= 4) {
    return `The investment exhibits a moderate-to-elevated risk profile with ${highCount} high and ${moderateCount}
      moderate-severity risk categories. While certain risks are manageable through operational excellence
      and strategic execution, investors should maintain awareness of potential adverse developments.
      Appropriate position sizing and risk management protocols are recommended for investors considering
      this opportunity.`
  } else if (moderateCount >= 2) {
    return `The investment demonstrates a balanced risk profile with ${moderateCount} moderate-severity risk
      categories identified. The risks appear manageable through prudent operational execution and
      strategic oversight. The risk-return profile may be appropriate for investors with moderate risk
      tolerance and medium-term investment horizons. Ongoing monitoring of key risk factors remains advisable.`
  } else {
    return `The investment presents a relatively favorable risk profile with limited high-severity concerns
      identified. The identified risks appear manageable and consistent with normal business operations
      in the industry. The risk-return characteristics may be suitable for a broad range of investors,
      though continued monitoring of evolving risk factors remains prudent investment practice.`
  }
}
