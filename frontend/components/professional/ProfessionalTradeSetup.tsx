import { DecisionIntelligence } from '@/types/api'

interface ProfessionalTradeSetupProps {
  ticker: string
  decision_intelligence?: DecisionIntelligence | null
}

export function ProfessionalTradeSetup({
  ticker,
  decision_intelligence,
}: ProfessionalTradeSetupProps) {
  if (!decision_intelligence) {
    return null
  }

  const {
    rating,
    risk_level,
    current_price,
    recommended_strategy,
    decision_framework,
    conviction_position,
  } = decision_intelligence

  return (
    <section className="space-y-6">
      <h2 className="text-2xl font-serif font-bold text-text-primary border-b-2 border-border pb-2">
        Investment Recommendation
      </h2>

      {/* Investment Rating */}
      <div className="grid grid-cols-2 gap-6">
        <div className="bg-surface-elevated rounded-lg p-6">
          <h3 className="text-base font-semibold text-text-primary mb-4">
            Investment Rating & Risk Classification
          </h3>
          <table className="w-full text-sm">
            <tbody>
              <tr className="border-b border-border">
                <td className="py-3 font-medium text-text-secondary">Rating</td>
                <td className="py-3 text-right font-bold text-lg text-text-primary">{rating || 'N/A'}</td>
              </tr>
              <tr className="border-b border-border">
                <td className="py-3 font-medium text-text-secondary">Risk Level</td>
                <td className="py-3 text-right font-semibold text-text-primary">{risk_level || 'N/A'}</td>
              </tr>
              <tr className="border-b border-border">
                <td className="py-3 font-medium text-text-secondary">Current Price</td>
                <td className="py-3 text-right font-semibold text-text-primary">
                  ${current_price?.toFixed(2) || 'N/A'}
                </td>
              </tr>
              {conviction_position && (
                <tr>
                  <td className="py-3 font-medium text-text-secondary">Conviction Level</td>
                  <td className="py-3 text-right font-semibold text-text-primary">
                    {conviction_position.conviction_level}
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>

        {decision_framework && (
          <div className="bg-surface-elevated rounded-lg p-6">
            <h3 className="text-base font-semibold text-text-primary mb-4">
              Investor-Specific Guidance
            </h3>
            <div className="space-y-4 text-sm">
              <div>
                <p className="font-semibold text-text-secondary mb-1">Current Holders</p>
                <p className="text-text-primary font-semibold">{decision_framework.current_holders.action}</p>
                <p className="text-text-secondary mt-1">{decision_framework.current_holders.detail}</p>
              </div>
              <div>
                <p className="font-semibold text-text-secondary mb-1">Prospective Investors</p>
                <p className="text-text-primary font-semibold">{decision_framework.new_buyers.action}</p>
                <p className="text-text-secondary mt-1">{decision_framework.new_buyers.detail}</p>
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Entry and Exit Strategy */}
      {recommended_strategy && (
        <div className="space-y-3">
          <h3 className="text-lg font-semibold text-text-primary">Entry & Exit Strategy</h3>
          <div className="grid grid-cols-2 gap-6">
            {/* Entry Strategy */}
            <div className="bg-surface-elevated rounded-lg p-6">
              <h4 className="text-base font-semibold text-text-primary mb-4">Entry Parameters</h4>
              <table className="w-full text-sm">
                <tbody>
                  {recommended_strategy.entry.ideal_zone &&
                   typeof recommended_strategy.entry.ideal_zone.low === 'number' &&
                   typeof recommended_strategy.entry.ideal_zone.high === 'number' && (
                    <tr className="border-b border-border">
                      <td className="py-3 font-medium text-text-secondary">Ideal Entry Zone</td>
                      <td className="py-3 text-right font-semibold text-text-primary">
                        ${recommended_strategy.entry.ideal_zone.low.toFixed(2)} - $
                        {recommended_strategy.entry.ideal_zone.high.toFixed(2)}
                      </td>
                    </tr>
                  )}
                  {typeof recommended_strategy.entry.discount_to_target_pct === 'number' && (
                    <tr className="border-b border-border">
                      <td className="py-3 font-medium text-text-secondary">Discount to Target</td>
                      <td className="py-3 text-right text-text-primary">
                        {recommended_strategy.entry.discount_to_target_pct.toFixed(1)}%
                      </td>
                    </tr>
                  )}
                  <tr>
                    <td className="py-3 font-medium text-text-secondary">Entry Approach</td>
                    <td className="py-3 text-right text-text-primary">
                      {decision_framework?.new_buyers.action === 'BUY NOW'
                        ? 'Immediate Entry'
                        : decision_framework?.new_buyers.action === 'SCALE IN'
                        ? 'Scaled Entry'
                        : 'Opportunistic Entry'}
                    </td>
                  </tr>
                </tbody>
              </table>
              <div className="mt-4 p-4 bg-background/50 rounded">
                <p className="text-xs font-semibold text-text-secondary mb-2">ENTRY GUIDANCE</p>
                <p className="text-sm text-text-primary leading-relaxed">
                  Consider initiating positions within the recommended entry zone, employing
                  dollar-cost averaging techniques to manage execution risk and optimize entry timing.
                </p>
              </div>
            </div>

            {/* Exit Strategy */}
            <div className="bg-surface-elevated rounded-lg p-6">
              <h4 className="text-base font-semibold text-text-primary mb-4">Exit Parameters</h4>
              <table className="w-full text-sm">
                <tbody>
                  {typeof recommended_strategy.exit.stop_loss === 'number' && (
                    <tr className="border-b border-border">
                      <td className="py-3 font-medium text-text-secondary">Stop Loss Level</td>
                      <td className="py-3 text-right font-semibold text-error">
                        ${recommended_strategy.exit.stop_loss.toFixed(2)}
                      </td>
                    </tr>
                  )}
                  {typeof recommended_strategy.exit.target_1 === 'number' && (
                    <tr className="border-b border-border">
                      <td className="py-3 font-medium text-text-secondary">Primary Target</td>
                      <td className="py-3 text-right font-semibold text-success">
                        ${recommended_strategy.exit.target_1.toFixed(2)}
                      </td>
                    </tr>
                  )}
                  {typeof recommended_strategy.exit.target_2 === 'number' && (
                    <tr className="border-b border-border">
                      <td className="py-3 font-medium text-text-secondary">Extended Target</td>
                      <td className="py-3 text-right font-semibold text-success">
                        ${recommended_strategy.exit.target_2.toFixed(2)}
                      </td>
                    </tr>
                  )}
                  {recommended_strategy.exit.holding_period && (
                    <tr>
                      <td className="py-3 font-medium text-text-secondary">Holding Period</td>
                      <td className="py-3 text-right">{recommended_strategy.exit.holding_period}</td>
                    </tr>
                  )}
                </tbody>
              </table>
              <div className="mt-4 p-4 bg-background/50 rounded">
                <p className="text-xs font-semibold text-text-secondary mb-2">EXIT DISCIPLINE</p>
                <p className="text-sm text-text-primary leading-relaxed">
                  Maintain disciplined stop-loss protocols. Consider scaling out at target levels
                  while allowing core positions to run in favorable conditions.
                </p>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Return Expectations */}
      {recommended_strategy && (
        <div className="space-y-3">
          <h3 className="text-lg font-semibold text-text-primary">Return Expectations</h3>
          <div className="grid grid-cols-2 gap-6">
            <div className="bg-surface-elevated rounded-lg p-6">
              <table className="w-full text-sm">
                <tbody>
                  {typeof recommended_strategy.exit.expected_return_total === 'number' && (
                    <tr className="border-b border-border">
                      <td className="py-3 font-medium text-text-secondary">
                        Expected Total Return
                      </td>
                      <td className="py-3 text-right text-lg font-bold text-success">
                        +{recommended_strategy.exit.expected_return_total.toFixed(1)}%
                      </td>
                    </tr>
                  )}
                  {typeof recommended_strategy.exit.expected_return_annualized === 'number' && (
                    <tr>
                      <td className="py-3 font-medium text-text-secondary">
                        Annualized Return Projection
                      </td>
                      <td className="py-3 text-right font-semibold">
                        {recommended_strategy.exit.expected_return_annualized.toFixed(1)}%
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
            <div className="bg-surface-elevated rounded-lg p-6 flex items-center">
              <p className="text-xs text-text-secondary leading-relaxed">
                <strong>Note:</strong> Return projections represent base-case scenarios and do not
                constitute guarantees. Actual returns may vary materially based on market conditions,
                execution timing, and unforeseen developments. Past performance is not indicative of
                future results.
              </p>
            </div>
          </div>
        </div>
      )}

      {/* Implementation Considerations */}
      <div className="bg-surface-elevated border-l-4 border-l-primary rounded-lg p-6">
        <h3 className="text-base font-semibold text-text-primary mb-3">
          Implementation Considerations
        </h3>
        <div className="grid grid-cols-2 gap-6 text-sm">
          <div>
            <p className="font-semibold text-text-secondary mb-2">Execution Best Practices</p>
            <ul className="space-y-1 text-text-primary">
              <li>• Employ limit orders to optimize entry pricing</li>
              <li>• Monitor liquidity conditions during execution</li>
              <li>• Consider market hours and volatility patterns</li>
              <li>• Scale entry over multiple time periods if warranted</li>
            </ul>
          </div>
          <div>
            <p className="font-semibold text-text-secondary mb-2">Risk Management Protocols</p>
            <ul className="space-y-1 text-text-primary">
              <li>• Adhere strictly to position size guidelines</li>
              <li>• Implement stop-loss discipline consistently</li>
              <li>• Monitor key risk indicators and catalysts</li>
              <li>• Maintain appropriate portfolio diversification</li>
            </ul>
          </div>
        </div>
      </div>
    </section>
  )
}
