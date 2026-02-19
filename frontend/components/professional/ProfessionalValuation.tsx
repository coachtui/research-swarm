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
  const valuationScore = full_output.moat_breakdown?.valuation || 0

  // Use validated price_targets from backend (bear < base < bull guaranteed)
  const pt = full_output.price_targets
  const baseCaseValue = pt?.base_target
    ?? (decision_intelligence?.recommended_strategy?.entry?.ideal_zone
      ? (decision_intelligence.recommended_strategy.entry.ideal_zone.low + decision_intelligence.recommended_strategy.entry.ideal_zone.high) / 2
      : currentPrice * 1.1)
  const bullCaseValue = pt?.bull_target ?? baseCaseValue * 1.25
  const bearCaseValue = pt?.bear_target ?? baseCaseValue * 0.75
  const fairValueLow = pt?.fair_value_low ?? baseCaseValue * 0.85
  const fairValueHigh = pt?.fair_value_high ?? baseCaseValue * 1.15

  const bullProb = Math.round((pt?.bull_probability ?? 0.25) * 100)
  const baseProb = Math.round((pt?.base_probability ?? 0.50) * 100)
  const bearProb = Math.round((pt?.bear_probability ?? 0.25) * 100)

  // Use probability-weighted EV from backend (uses validated scenario targets)
  const expectedValue = pt?.probability_weighted_ev
    ?? (bullCaseValue * bullProb + baseCaseValue * baseProb + bearCaseValue * bearProb) / 100

  const dispersionLabel = pt?.valuation_dispersion_label
  const dispersionPct = pt?.valuation_dispersion_pct
  const methodValues = pt?.method_values
  const premiumJustification = pt?.premium_justification
  const chainNotes = pt?.chain_validation_notes

  const dispersionColor =
    dispersionLabel === 'Low' ? 'text-success' :
    dispersionLabel === 'Moderate' ? 'text-warning' :
    dispersionLabel === 'High' ? 'text-error' : 'text-text-tertiary'

  const premiumColor =
    premiumJustification?.classification === 'JUSTIFIED_PREMIUM' ? 'text-success' :
    premiumJustification?.classification === 'EXECUTION_DEPENDENT_PREMIUM' ? 'text-warning' :
    premiumJustification?.classification === 'SPECULATIVE_PREMIUM' ? 'text-error' : 'text-text-tertiary'

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
            {pt?.methodology
              ? `${pt.methodology}. Fair value band: $${fairValueLow.toFixed(0)}–$${fairValueHigh.toFixed(0)} (${pt.confidence ?? 'Moderate'} confidence, ${pt.confidence_score ?? '—'}/100).`
              : 'The valuation analysis employs a multi-factor approach incorporating discounted cash flow (DCF) modeling, comparable company analysis, and technical price levels.'}
          </p>
          <p className="text-sm text-text-primary leading-relaxed">
            Scenario analysis uses probability-weighted outcomes across bull ({bullProb}%),
            base ({baseProb}%), and bear ({bearProb}%) cases. The base case anchors at fair value midpoint.
            Bear case is structurally below fair value. Bull case reflects upside tail scenario.
            Expected value = bear×{bearProb}% + base×{baseProb}% + bull×{bullProb}%.
          </p>
          {chainNotes && chainNotes.length > 0 && (
            <div className="mt-2 p-2.5 rounded-md bg-primary/5 border border-primary/20">
              <p className="text-xs font-semibold text-primary mb-1">Valuation Chain Notes</p>
              {chainNotes.map((note, i) => (
                <p key={i} className="text-xs text-text-secondary">• {note}</p>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* P2: Valuation Model Agreement (Dispersion Panel) */}
      {methodValues && Object.keys(methodValues).length >= 2 && (
        <div className="space-y-3">
          <h3 className="text-lg font-semibold text-text-primary">Valuation Model Agreement</h3>
          <div className="bg-surface-elevated rounded-lg p-5 space-y-3">
            <div className="grid grid-cols-3 gap-4 text-sm">
              {methodValues.pe !== undefined && (
                <div>
                  <span className="text-text-tertiary text-xs block">P/E Method</span>
                  <span className="font-semibold text-text-primary">${methodValues.pe.toFixed(0)}</span>
                </div>
              )}
              {methodValues.ev_ebitda !== undefined && (
                <div>
                  <span className="text-text-tertiary text-xs block">EV/EBITDA Method</span>
                  <span className="font-semibold text-text-primary">${methodValues.ev_ebitda.toFixed(0)}</span>
                </div>
              )}
              {methodValues.dcf !== undefined && (
                <div>
                  <span className="text-text-tertiary text-xs block">DCF Method</span>
                  <span className="font-semibold text-text-primary">${methodValues.dcf.toFixed(0)}</span>
                </div>
              )}
            </div>
            <div className="flex items-center gap-3 pt-2 border-t border-border text-sm">
              <span className="text-text-tertiary">Model Disagreement:</span>
              <span className={`font-semibold ${dispersionColor}`}>
                {dispersionLabel ?? '—'}
                {dispersionPct !== undefined && (
                  <span className="font-normal text-text-tertiary ml-1">
                    ({(dispersionPct * 100).toFixed(0)}% spread)
                  </span>
                )}
              </span>
              {dispersionLabel === 'High' && (
                <span className="text-xs text-error">
                  → Fair value band widened, confidence reduced
                </span>
              )}
            </div>
            {pt?.uncertainty_drivers && pt.uncertainty_drivers.length > 0 && (
              <div className="pt-2 border-t border-border">
                <p className="text-xs font-semibold text-text-secondary mb-1">Uncertainty Drivers</p>
                {pt.uncertainty_drivers.slice(0, 3).map((d, i) => (
                  <p key={i} className="text-xs text-text-tertiary">• {d}</p>
                ))}
              </div>
            )}
          </div>
        </div>
      )}

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
                <tr>
                  <td className="border border-border px-4 py-3">
                    Fair Value Band
                    <span className="block text-xs text-text-tertiary font-normal">
                      Normalized Intrinsic Value
                    </span>
                  </td>
                  <td className="border border-border px-4 py-3 text-right text-text-primary">
                    ${fairValueLow.toFixed(0)}–${fairValueHigh.toFixed(0)}
                  </td>
                </tr>
                <tr>
                  <td className="border border-border px-4 py-3">
                    Base Case Target
                    <span className="block text-xs text-text-tertiary font-normal">
                      Intrinsic Value Midpoint
                    </span>
                  </td>
                  <td className="border border-border px-4 py-3 text-right font-semibold text-text-primary">
                    ${baseCaseValue.toFixed(2)}
                  </td>
                </tr>
                <tr>
                  <td className="border border-border px-4 py-3">
                    Expected Value
                    <span className="block text-xs text-text-tertiary font-normal">
                      Probability-Weighted
                    </span>
                  </td>
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
                    {currentPrice !== bearCaseValue
                      ? (Math.abs((baseCaseValue - currentPrice) / (currentPrice - bearCaseValue))).toFixed(2)
                      : '—'}:1
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
              <td className="border border-border px-4 py-3 text-text-secondary">
                {pt?.bull_assumptions ?? 'Strong execution, market share gains, multiple expansion, favorable macro conditions'}
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
              <td className="border border-border px-4 py-3 text-text-secondary">
                {pt?.base_assumptions
                  ? pt.base_assumptions.split('.')[0] + '.'
                  : 'In-line execution, stable competitive positioning, normalized growth trajectory'}
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
              <td className="border border-border px-4 py-3 text-text-secondary">
                {pt?.bear_assumptions ?? 'Execution challenges, competitive pressure, margin compression, adverse market conditions'}
              </td>
            </tr>
          </tbody>
        </table>
      </div>

      {/* P2: Premium Justification */}
      {premiumJustification && premiumJustification.classification !== 'NO_PREMIUM' && (
        <div className="bg-surface-elevated rounded-lg p-5">
          <h3 className="text-base font-semibold text-text-primary mb-2">
            P/E Premium Analysis
          </h3>
          <div className="flex items-center gap-3 mb-2">
            <span className={`text-sm font-semibold ${premiumColor}`}>
              {premiumJustification.label}
            </span>
            {premiumJustification.implied_peg !== null && (
              <span className="text-xs text-text-tertiary">
                Implied PEG: {premiumJustification.implied_peg}x
              </span>
            )}
            <span className="text-xs text-text-tertiary">
              vs Sector: {premiumJustification.premium_pct_vs_sector >= 0 ? '+' : ''}{(premiumJustification.premium_pct_vs_sector * 100).toFixed(0)}%
            </span>
          </div>
          <p className="text-sm text-text-secondary leading-relaxed">
            {premiumJustification.rationale}
          </p>
        </div>
      )}

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
    return `The security currently trades at an approximately ${discount.toFixed(0)}% discount to our estimated fair value, presenting a potentially attractive entry opportunity. The valuation score of ${valuationScore.toFixed(1)}/10 ${valuationScore >= 6.0 ? 'supports' : 'reflects'} this assessment. Investors should consider underlying assumptions and risk factors that may justify current market pricing.`
  } else if (discount >= 5) {
    return `The security trades at a modest ${discount.toFixed(0)}% discount to estimated fair value, suggesting reasonable value at current levels. The valuation score of ${valuationScore.toFixed(1)}/10 indicates ${valuationScore >= 6.0 ? 'favorable' : 'balanced'} risk-reward dynamics.`
  } else if (premium <= 5) {
    return `The security trades approximately in line with our estimated fair value, indicating balanced valuation. The valuation score of ${valuationScore.toFixed(1)}/10 reflects ${valuationScore >= 6.0 ? 'reasonable value' : 'fair pricing'}. Decisions should be guided by conviction in business fundamentals and catalyst potential.`
  } else if (premium <= 15) {
    return `The security commands a ${premium.toFixed(0)}% premium to our estimated fair value. The valuation score of ${valuationScore.toFixed(1)}/10 reflects this positioning. Investors should assess whether growth prospects and competitive advantages justify the current valuation.`
  } else {
    return `The security trades at a significant ${premium.toFixed(0)}% premium to estimated fair value, indicating stretched valuation metrics. The valuation score of ${valuationScore.toFixed(1)}/10 reflects this elevated positioning. Investors should evaluate whether exceptional growth prospects warrant the premium.`
  }
}
