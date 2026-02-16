import { ManagerOutput, DecisionIntelligence } from '@/types/api'
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/components/ui/tooltip'
import { HelpCircle } from 'lucide-react'

interface ProfessionalExecutiveSummaryProps {
  ticker: string
  full_output: ManagerOutput
  decision_intelligence?: DecisionIntelligence | null
  moat_score: number | null
}

export function ProfessionalExecutiveSummary({
  ticker,
  full_output,
  decision_intelligence,
  moat_score,
}: ProfessionalExecutiveSummaryProps) {
  const rating = decision_intelligence?.rating || 'N/A'
  const riskLevel = decision_intelligence?.risk_level || 'N/A'
  const currentPrice = decision_intelligence?.current_price || 0

  // Extract key metrics
  const moatBreakdown = full_output.moat_breakdown
  // Try to get VGM scores from top-level first, then fallback to fundamentalist_output
  const vgmScores = full_output.vgm_scores || full_output.fundamentalist_output?.vgm_scores
  const signalBreakdown = full_output.signal_breakdown

  return (
    <section className="space-y-6">
      <h2 className="text-2xl font-serif font-bold text-text-primary border-b-2 border-border pb-2">
        Executive Summary
      </h2>

      {/* Investment Overview */}
      <div className="space-y-4">
        <h3 className="text-lg font-semibold text-text-primary">Investment Overview</h3>
        <div className="grid grid-cols-2 gap-6">
          <div>
            <table className="w-full">
              <tbody className="text-sm">
                <tr className="border-b">
                  <td className="py-2 font-medium text-text-secondary">Ticker Symbol</td>
                  <td className="py-2 text-right font-semibold text-text-primary">{ticker}</td>
                </tr>
                <tr className="border-b">
                  <td className="py-2 font-medium text-text-secondary">Current Price</td>
                  <td className="py-2 text-right font-semibold text-text-primary">
                    ${currentPrice.toFixed(2)}
                  </td>
                </tr>
                <tr className="border-b">
                  <td className="py-2 font-medium text-text-secondary">Investment Rating</td>
                  <td className="py-2 text-right font-semibold text-text-primary">{rating}</td>
                </tr>
                <tr className="border-b">
                  <td className="py-2 font-medium text-text-secondary">Risk Classification</td>
                  <td className="py-2 text-right font-semibold text-text-primary">{riskLevel}</td>
                </tr>
              </tbody>
            </table>
          </div>
          <div>
            <table className="w-full">
              <tbody className="text-sm">
                {moat_score !== null && (
                  <tr className="border-b">
                    <td className="py-2 font-medium text-text-secondary">Overall Moat Score</td>
                    <td className="py-2 text-right font-semibold text-text-primary">
                      {moat_score.toFixed(1)}/10
                    </td>
                  </tr>
                )}
                {vgmScores && (
                  <>
                    <tr className="border-b">
                      <td className="py-2 font-medium text-text-secondary">Value Score</td>
                      <td className="py-2 text-right font-semibold text-text-primary">{vgmScores.value_score.toFixed(1)}/10</td>
                    </tr>
                    <tr className="border-b">
                      <td className="py-2 font-medium text-text-secondary">Growth Score</td>
                      <td className="py-2 text-right font-semibold text-text-primary">{vgmScores.growth_score.toFixed(1)}/10</td>
                    </tr>
                    <tr className="border-b">
                      <td className="py-2 font-medium text-text-secondary">Momentum Score</td>
                      <td className="py-2 text-right font-semibold text-text-primary">{vgmScores.momentum_score.toFixed(1)}/10</td>
                    </tr>
                  </>
                )}
              </tbody>
            </table>
          </div>
        </div>
      </div>

      {/* Investment Thesis */}
      <div className="space-y-3">
        <h3 className="text-lg font-semibold text-text-primary">Investment Thesis</h3>
        <div className="bg-surface-elevated rounded-lg p-6">
          <p className="text-text-primary leading-relaxed whitespace-pre-wrap">
            {full_output.investment_thesis || 'Investment thesis not available.'}
          </p>
        </div>
      </div>

      {/* Moat Component Analysis */}
      {moatBreakdown && (
        <div className="space-y-3">
          <h3 className="text-lg font-semibold text-text-primary">Competitive Moat Analysis</h3>
          <TooltipProvider>
            <table className="w-full border-collapse">
              <thead>
                <tr className="bg-surface-elevated">
                  <th className="border border-border px-4 py-3 text-left text-sm font-semibold">
                    Component
                  </th>
                  <th className="border border-border px-4 py-3 text-center text-sm font-semibold">
                    Score
                  </th>
                  <th className="border border-border px-4 py-3 text-center text-sm font-semibold">
                    Assessment
                  </th>
                </tr>
              </thead>
              <tbody className="text-sm">
                <tr>
                  <td className="border border-border px-4 py-3">
                    <div className="flex items-center gap-1.5">
                      <span>Earnings Momentum</span>
                      <Tooltip>
                        <TooltipTrigger asChild>
                          <button className="text-text-tertiary hover:text-text-secondary transition-colors">
                            <HelpCircle className="h-3.5 w-3.5" />
                          </button>
                        </TooltipTrigger>
                        <TooltipContent className="max-w-xs">
                          <p className="text-xs leading-relaxed">
                            Tracks whether the company is beating earnings expectations and raising guidance. Higher scores indicate consistent earnings beats and positive revisions.
                          </p>
                        </TooltipContent>
                      </Tooltip>
                    </div>
                  </td>
                  <td className="border border-border px-4 py-3 text-center font-semibold text-text-primary">
                    {moatBreakdown.earnings_momentum.toFixed(1)}
                  </td>
                  <td className="border border-border px-4 py-3 text-center text-text-primary">
                    {getAssessment(moatBreakdown.earnings_momentum)}
                  </td>
                </tr>
                <tr>
                  <td className="border border-border px-4 py-3">
                    <div className="flex items-center gap-1.5">
                      <span className="text-text-primary">Financial Health</span>
                      <Tooltip>
                        <TooltipTrigger asChild>
                          <button className="text-text-tertiary hover:text-text-primary transition-colors">
                            <HelpCircle className="h-3.5 w-3.5" />
                          </button>
                        </TooltipTrigger>
                        <TooltipContent className="max-w-xs">
                          <p className="text-xs leading-relaxed">
                            Measures balance sheet strength, profitability, and cash flow stability. Strong companies have low debt, high margins, and growing free cash flow.
                          </p>
                        </TooltipContent>
                      </Tooltip>
                    </div>
                  </td>
                  <td className="border border-border px-4 py-3 text-center font-semibold text-text-primary">
                    {moatBreakdown.financial_health.toFixed(1)}
                  </td>
                  <td className="border border-border px-4 py-3 text-center text-text-primary">
                    {getAssessment(moatBreakdown.financial_health)}
                  </td>
                </tr>
                <tr>
                  <td className="border border-border px-4 py-3">
                    <div className="flex items-center gap-1.5">
                      <span className="text-text-primary">Valuation</span>
                      <Tooltip>
                        <TooltipTrigger asChild>
                          <button className="text-text-tertiary hover:text-text-primary transition-colors">
                            <HelpCircle className="h-3.5 w-3.5" />
                          </button>
                        </TooltipTrigger>
                        <TooltipContent className="max-w-xs">
                          <p className="text-xs leading-relaxed">
                            Compares current price to intrinsic value using P/E, PEG, DCF, and peer multiples. Lower scores mean expensive relative to fundamentals.
                          </p>
                        </TooltipContent>
                      </Tooltip>
                    </div>
                  </td>
                  <td className="border border-border px-4 py-3 text-center font-semibold text-text-primary">
                    {moatBreakdown.valuation.toFixed(1)}
                  </td>
                  <td className="border border-border px-4 py-3 text-center text-text-primary">
                    {getAssessment(moatBreakdown.valuation)}
                  </td>
                </tr>
                <tr>
                  <td className="border border-border px-4 py-3">
                    <div className="flex items-center gap-1.5">
                      <span className="text-text-primary">Technical Strength</span>
                      <Tooltip>
                        <TooltipTrigger asChild>
                          <button className="text-text-tertiary hover:text-text-primary transition-colors">
                            <HelpCircle className="h-3.5 w-3.5" />
                          </button>
                        </TooltipTrigger>
                        <TooltipContent className="max-w-xs">
                          <p className="text-xs leading-relaxed">
                            Analyzes price trends, volume patterns, and momentum indicators (RSI, MACD). Strong technicals suggest institutional accumulation.
                          </p>
                        </TooltipContent>
                      </Tooltip>
                    </div>
                  </td>
                  <td className="border border-border px-4 py-3 text-center font-semibold text-text-primary">
                    {moatBreakdown.technical_strength.toFixed(1)}
                  </td>
                  <td className="border border-border px-4 py-3 text-center text-text-primary">
                    {getAssessment(moatBreakdown.technical_strength)}
                  </td>
                </tr>
                <tr>
                  <td className="border border-border px-4 py-3">
                    <div className="flex items-center gap-1.5">
                      <span className="text-text-primary">Sentiment & Catalysts</span>
                      <Tooltip>
                        <TooltipTrigger asChild>
                          <button className="text-text-tertiary hover:text-text-primary transition-colors">
                            <HelpCircle className="h-3.5 w-3.5" />
                          </button>
                        </TooltipTrigger>
                        <TooltipContent className="max-w-xs">
                          <p className="text-xs leading-relaxed">
                            Evaluates market sentiment, news flow, and upcoming catalysts (earnings, product launches, regulatory). Positive sentiment can drive near-term moves.
                          </p>
                        </TooltipContent>
                      </Tooltip>
                    </div>
                  </td>
                  <td className="border border-border px-4 py-3 text-center font-semibold text-text-primary">
                    {moatBreakdown.sentiment_catalysts.toFixed(1)}
                  </td>
                  <td className="border border-border px-4 py-3 text-center text-text-primary">
                    {getAssessment(moatBreakdown.sentiment_catalysts)}
                  </td>
                </tr>
              </tbody>
            </table>
          </TooltipProvider>
        </div>
      )}

      {/* Market Signal Analysis */}
      {signalBreakdown && (
        <div className="space-y-3">
          <h3 className="text-lg font-semibold text-text-primary">Market Signal Assessment</h3>
          <div className="grid grid-cols-2 gap-4">
            <div className="bg-surface-elevated rounded-lg p-4">
              <table className="w-full text-sm">
                <tbody>
                  <tr className="border-b border-border">
                    <td className="py-2 font-medium text-text-secondary">Overall Signal</td>
                    <td className="py-2 text-right font-semibold text-text-primary">
                      {signalBreakdown.overall_score.toFixed(1)}/10
                    </td>
                  </tr>
                  <tr className="border-b border-border">
                    <td className="py-2 font-medium text-text-secondary">Analyst Consensus</td>
                    <td className="py-2 text-right text-text-primary">{signalBreakdown.analyst_score.toFixed(1)}/10</td>
                  </tr>
                  <tr className="border-b border-border">
                    <td className="py-2 font-medium text-text-secondary">Institutional Activity</td>
                    <td className="py-2 text-right text-text-primary">{signalBreakdown.institutional_score.toFixed(1)}/10</td>
                  </tr>
                  <tr>
                    <td className="py-2 font-medium text-text-secondary">Insider Activity</td>
                    <td className="py-2 text-right text-text-primary">{signalBreakdown.insider_score.toFixed(1)}/10</td>
                  </tr>
                </tbody>
              </table>
            </div>
            <div className="bg-surface-elevated rounded-lg p-4">
              <table className="w-full text-sm">
                <tbody>
                  <tr className="border-b border-border">
                    <td className="py-2 font-medium text-text-secondary">News Sentiment</td>
                    <td className="py-2 text-right text-text-primary">{signalBreakdown.news_score.toFixed(1)}/10</td>
                  </tr>
                  <tr className="border-b border-border">
                    <td className="py-2 font-medium text-text-secondary">Earnings Revisions</td>
                    <td className="py-2 text-right text-text-primary">{signalBreakdown.earnings_score.toFixed(1)}/10</td>
                  </tr>
                  <tr className="border-b border-border">
                    <td className="py-2 font-medium text-text-secondary">Direction Consensus</td>
                    <td className="py-2 text-right font-semibold text-text-primary">{signalBreakdown.direction_consensus}</td>
                  </tr>
                  <tr>
                    <td className="py-2 font-medium text-text-secondary">Divergence Status</td>
                    <td className="py-2 text-right text-text-primary">
                      {signalBreakdown.has_divergence ? 'Present' : 'Aligned'}
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>
          {signalBreakdown.has_divergence && signalBreakdown.divergence_explanation && (
            <div className="bg-warning/10 border border-warning/20 rounded-lg p-4">
              <p className="text-sm font-medium text-warning mb-2">Signal Divergence Detected</p>
              <p className="text-sm text-text-primary leading-relaxed">
                {signalBreakdown.divergence_explanation}
              </p>
            </div>
          )}
        </div>
      )}

      {/* Bottom Line */}
      {full_output.conviction_statement && (
        <div className="bg-primary/10 border-l-4 border-l-primary rounded-lg p-6">
          <h3 className="text-lg font-semibold text-text-primary mb-3">Investment Conviction</h3>
          <p className="text-text-primary font-medium mb-4">
            {full_output.conviction_statement.bottom_line}
          </p>
          <div className="grid grid-cols-3 gap-4 text-sm">
            <div>
              <p className="font-medium text-text-secondary mb-1">Investor Profile</p>
              <p className="text-text-primary">
                {full_output.conviction_statement.best_suited_for.investor_type}
              </p>
            </div>
            <div>
              <p className="font-medium text-text-secondary mb-1">Risk Tolerance</p>
              <p className="text-text-primary">
                {full_output.conviction_statement.best_suited_for.risk_tolerance}
              </p>
            </div>
            <div>
              <p className="font-medium text-text-secondary mb-1">Time Horizon</p>
              <p className="text-text-primary">
                {full_output.conviction_statement.best_suited_for.time_horizon}
              </p>
            </div>
          </div>
        </div>
      )}
    </section>
  )
}

function getAssessment(score: number): string {
  if (score >= 8.0) return 'Excellent'
  if (score >= 7.0) return 'Strong'
  if (score >= 6.0) return 'Above Average'
  if (score >= 5.0) return 'Average'
  if (score >= 4.0) return 'Below Average'
  return 'Weak'
}
