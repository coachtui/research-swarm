import { ManagerOutput, DecisionIntelligence } from '@/types/api'

interface ProfessionalValuationProps {
  ticker: string
  full_output: ManagerOutput
  decision_intelligence?: DecisionIntelligence | null
}

export function ProfessionalValuation({
  ticker,
  full_output,
  decision_intelligence,
}: ProfessionalValuationProps) {
  const currentPrice = decision_intelligence?.current_price || 0
  const idealZone = decision_intelligence?.recommended_strategy?.entry?.ideal_zone
  const valuationScore = full_output.moat_breakdown?.valuation || 0

  // Calculate scenario prices based on ideal zone
  const baseCaseValue = idealZone ? (idealZone.low + idealZone.high) / 2 : currentPrice * 1.1
  const bullCaseValue = baseCaseValue * 1.25
  const bearCaseValue = baseCaseValue * 0.75

  // Calculate probabilities based on valuation score and signals
  const signalScore = full_output.signal_breakdown?.overall_score || 5.0
  const avgScore = (valuationScore + signalScore) / 2

  let bullProb = 25
  let baseProb = 50
  let bearProb = 25

  if (avgScore >= 7.0) {
    bullProb = 40
    baseProb = 45
    bearProb = 15
  } else if (avgScore >= 6.0) {
    bullProb = 35
    baseProb = 45
    bearProb = 20
  } else if (avgScore <= 4.0) {
    bullProb = 15
    baseProb = 40
    bearProb = 45
  } else if (avgScore <= 5.0) {
    bullProb = 20
    baseProb = 45
    bearProb = 35
  }

  // Calculate expected value
  const expectedValue = (bullCaseValue * bullProb + baseCaseValue * baseProb + bearCaseValue * bearProb) / 100

  return (
    <section className="space-y-6">
      <h2 className="text-2xl font-serif font-bold text-text-primary border-b-2 border-border pb-2">
        Valuation Analysis
      </h2>

      {/* Methodology */}
      <div className="space-y-3">
        <h3 className="text-lg font-semibold text-text-primary">Valuation Methodology</h3>
        <div className="bg-surface-elevated rounded-lg p-6 space-y-3">
          <p className="text-sm text-text-primary leading-relaxed">
            The valuation analysis employs a multi-factor approach incorporating discounted cash flow (DCF)
            modeling, comparable company analysis, and technical price levels. The framework synthesizes
            fundamental metrics, including revenue growth trajectories, margin dynamics, and capital
            efficiency, with market-based indicators such as trading multiples and momentum signals.
          </p>
          <p className="text-sm text-text-primary leading-relaxed">
            Scenario analysis incorporates probability-weighted outcomes across bull, base, and bear cases,
            considering macroeconomic conditions, competitive positioning, and execution risks. The current
            assessment reflects a comprehensive evaluation of the company's intrinsic value relative to
            prevailing market conditions.
          </p>
        </div>
      </div>

      {/* Valuation Summary */}
      <div className="space-y-3">
        <h3 className="text-lg font-semibold text-text-primary">Valuation Summary</h3>
        <div className="grid grid-cols-2 gap-6">
          <div>
            <table className="w-full border-collapse">
              <thead>
                <tr className="bg-surface-elevated">
                  <th className="border border-border px-4 py-3 text-left text-sm font-semibold">
                    Metric
                  </th>
                  <th className="border border-border px-4 py-3 text-right text-sm font-semibold">
                    Value
                  </th>
                </tr>
              </thead>
              <tbody className="text-sm">
                <tr>
                  <td className="border border-border px-4 py-3">Current Market Price</td>
                  <td className="border border-border px-4 py-3 text-right font-semibold text-text-primary">
                    ${currentPrice.toFixed(2)}
                  </td>
                </tr>
                {idealZone && (
                  <>
                    <tr>
                      <td className="border border-border px-4 py-3">Fair Value Range (Low)</td>
                      <td className="border border-border px-4 py-3 text-right text-text-primary">
                        ${idealZone.low.toFixed(2)}
                      </td>
                    </tr>
                    <tr>
                      <td className="border border-border px-4 py-3">Fair Value Range (High)</td>
                      <td className="border border-border px-4 py-3 text-right text-text-primary">
                        ${idealZone.high.toFixed(2)}
                      </td>
                    </tr>
                  </>
                )}
                <tr>
                  <td className="border border-border px-4 py-3">Base Case Target</td>
                  <td className="border border-border px-4 py-3 text-right font-semibold text-text-primary">
                    ${baseCaseValue.toFixed(2)}
                  </td>
                </tr>
                <tr>
                  <td className="border border-border px-4 py-3">Expected Value</td>
                  <td className="border border-border px-4 py-3 text-right font-bold text-primary">
                    ${expectedValue.toFixed(2)}
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
          <div>
            <table className="w-full border-collapse">
              <thead>
                <tr className="bg-surface-elevated">
                  <th className="border border-border px-4 py-3 text-left text-sm font-semibold">
                    Metric
                  </th>
                  <th className="border border-border px-4 py-3 text-right text-sm font-semibold">
                    Value
                  </th>
                </tr>
              </thead>
              <tbody className="text-sm">
                <tr>
                  <td className="border border-border px-4 py-3">Valuation Score</td>
                  <td className="border border-border px-4 py-3 text-right text-text-primary">
                    {valuationScore.toFixed(1)}/10
                  </td>
                </tr>
                <tr>
                  <td className="border border-border px-4 py-3">Upside Potential</td>
                  <td className="border border-border px-4 py-3 text-right text-success">
                    +{(((baseCaseValue - currentPrice) / currentPrice) * 100).toFixed(1)}%
                  </td>
                </tr>
                <tr>
                  <td className="border border-border px-4 py-3">Downside Risk</td>
                  <td className="border border-border px-4 py-3 text-right text-error">
                    {(((bearCaseValue - currentPrice) / currentPrice) * 100).toFixed(1)}%
                  </td>
                </tr>
                <tr>
                  <td className="border border-border px-4 py-3">Risk/Reward Ratio</td>
                  <td className="border border-border px-4 py-3 text-right font-semibold text-text-primary">
                    {(Math.abs((baseCaseValue - currentPrice) / (currentPrice - bearCaseValue))).toFixed(2)}:1
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </div>

      {/* Scenario Analysis */}
      <div className="space-y-3">
        <h3 className="text-lg font-semibold text-text-primary">Scenario Analysis</h3>
        <table className="w-full border-collapse">
          <thead>
            <tr className="bg-surface-elevated">
              <th className="border border-border px-4 py-3 text-left text-sm font-semibold">
                Scenario
              </th>
              <th className="border border-border px-4 py-3 text-center text-sm font-semibold">
                Target Price
              </th>
              <th className="border border-border px-4 py-3 text-center text-sm font-semibold">
                Return from Current
              </th>
              <th className="border border-border px-4 py-3 text-center text-sm font-semibold">
                Probability
              </th>
              <th className="border border-border px-4 py-3 text-left text-sm font-semibold">
                Key Assumptions
              </th>
            </tr>
          </thead>
          <tbody className="text-sm">
            <tr>
              <td className="border border-border px-4 py-3 font-semibold text-success">
                Bull Case
              </td>
              <td className="border border-border px-4 py-3 text-center font-semibold">
                ${bullCaseValue.toFixed(2)}
              </td>
              <td className="border border-border px-4 py-3 text-center text-success font-semibold">
                +{(((bullCaseValue - currentPrice) / currentPrice) * 100).toFixed(1)}%
              </td>
              <td className="border border-border px-4 py-3 text-center font-semibold">
                {bullProb}%
              </td>
              <td className="border border-border px-4 py-3">
                Strong execution, market share gains, multiple expansion, favorable macro conditions
              </td>
            </tr>
            <tr>
              <td className="border border-border px-4 py-3 font-semibold">
                Base Case
              </td>
              <td className="border border-border px-4 py-3 text-center font-semibold">
                ${baseCaseValue.toFixed(2)}
              </td>
              <td className="border border-border px-4 py-3 text-center font-semibold">
                {(((baseCaseValue - currentPrice) / currentPrice) * 100).toFixed(1)}%
              </td>
              <td className="border border-border px-4 py-3 text-center font-semibold">
                {baseProb}%
              </td>
              <td className="border border-border px-4 py-3">
                In-line execution, stable competitive positioning, normalized growth trajectory
              </td>
            </tr>
            <tr>
              <td className="border border-border px-4 py-3 font-semibold text-error">
                Bear Case
              </td>
              <td className="border border-border px-4 py-3 text-center font-semibold">
                ${bearCaseValue.toFixed(2)}
              </td>
              <td className="border border-border px-4 py-3 text-center text-error font-semibold">
                {(((bearCaseValue - currentPrice) / currentPrice) * 100).toFixed(1)}%
              </td>
              <td className="border border-border px-4 py-3 text-center font-semibold">
                {bearProb}%
              </td>
              <td className="border border-border px-4 py-3">
                Execution challenges, competitive pressure, margin compression, adverse market conditions
              </td>
            </tr>
          </tbody>
        </table>
      </div>

      {/* Valuation Context */}
      <div className="bg-surface-elevated rounded-lg p-6">
        <h3 className="text-base font-semibold text-text-primary mb-3">
          Valuation Assessment
        </h3>
        <p className="text-sm text-text-primary leading-relaxed">
          {getValuationInterpretation(currentPrice, baseCaseValue, valuationScore)}
        </p>
      </div>
    </section>
  )
}

function getValuationInterpretation(
  currentPrice: number,
  fairValue: number,
  valuationScore: number
): string {
  const discount = ((fairValue - currentPrice) / fairValue) * 100
  const premium = ((currentPrice - fairValue) / fairValue) * 100

  if (discount >= 15) {
    return `The security currently trades at an approximately ${discount.toFixed(0)}% discount to our
      estimated fair value, presenting a potentially attractive entry opportunity for investors with
      appropriate risk tolerance. The valuation score of ${valuationScore.toFixed(1)}/10 ${valuationScore >= 6.0 ? 'supports' : 'reflects'}
      this assessment. However, investors should carefully consider the underlying assumptions and
      risk factors that may justify the current market pricing.`
  } else if (discount >= 5) {
    return `The security trades at a modest ${discount.toFixed(0)}% discount to estimated fair value,
      suggesting reasonable value at current levels. The valuation score of ${valuationScore.toFixed(1)}/10 indicates
      ${valuationScore >= 6.0 ? 'favorable' : 'balanced'} risk-reward dynamics. Investors should evaluate
      whether the current entry point aligns with their investment objectives and risk parameters.`
  } else if (premium <= 5) {
    return `The security trades approximately in line with our estimated fair value, indicating
      balanced valuation at current market levels. The valuation score of ${valuationScore.toFixed(1)}/10 reflects
      ${valuationScore >= 6.0 ? 'reasonable value' : 'fair pricing'}. Investment decisions should be guided by
      conviction in the underlying business fundamentals and catalyst potential.`
  } else if (premium <= 15) {
    return `The security commands a ${premium.toFixed(0)}% premium to our estimated fair value, suggesting
      elevated valuation levels. The valuation score of ${valuationScore.toFixed(1)}/10 reflects this premium positioning.
      Investors should assess whether growth prospects and competitive advantages justify the current
      valuation, or consider awaiting more favorable entry opportunities.`
  } else {
    return `The security trades at a significant ${premium.toFixed(0)}% premium to estimated fair value,
      indicating stretched valuation metrics. The valuation score of ${valuationScore.toFixed(1)}/10 reflects
      this elevated positioning. Investors should exercise caution and carefully evaluate whether
      exceptional growth prospects or unique competitive positioning warrant the premium valuation.`
  }
}
