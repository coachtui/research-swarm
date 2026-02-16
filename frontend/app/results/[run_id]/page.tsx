'use client'

import Link from 'next/link'
import { useAnalysis } from '@/lib/hooks/useAnalysis'
import { LoadingSpinner } from '@/components/shared/LoadingSpinner'
import { SignalDivergenceHero } from '@/components/results/SignalDivergenceHero'
import { SignalDivergenceSection } from '@/components/results/SignalDivergenceSection'
import { DecisionAction } from '@/components/results/DecisionAction'
import { KeyTakeaways } from '@/components/results/KeyTakeaways'
import { ScoreBreakdownBars } from '@/components/results/ScoreBreakdownBars'
import { TradeSetup } from '@/components/results/TradeSetup'
import { BottomLine } from '@/components/results/BottomLine'
import { VerdictSummary } from '@/components/results/VerdictSummary'
import { RatingTriggers } from '@/components/results/RatingTriggers'
import { WhatsNew } from '@/components/results/WhatsNew'
import { WatchCalendar } from '@/components/results/WatchCalendar'
import { QuickActions } from '@/components/results/QuickActions'
import { ProfessionalAnalysisSection } from '@/components/results/ProfessionalAnalysisSection'
import { PortfolioContext } from '@/components/results/PortfolioContext'
import { Card, CardContent } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { formatDateTime } from '@/lib/utils/formatting'
import { generateVerdictSummary } from '@/lib/analysis/generateVerdictSummary'
import { simplifyKeyInsights } from '@/lib/analysis/simplifyKeyInsights'
import { generateRatingTriggers } from '@/lib/analysis/generateRatingTriggers'
import { extractWhatsNew } from '@/lib/analysis/extractWhatsNew'
import { extractWatchCalendar } from '@/lib/analysis/extractWatchCalendar'
import { extractQuickActionsData } from '@/lib/analysis/extractQuickActionsData'

interface ResultsPageProps {
  params: { run_id: string }
}

export default function ResultsPage({ params }: ResultsPageProps) {
  const { run_id } = params
  const { data: run, isLoading, error } = useAnalysis(run_id)

  // Error state
  if (error) {
    return (
      <div className="container mx-auto px-4 py-12">
        <Card className="max-w-2xl mx-auto">
          <CardContent className="pt-6">
            <div className="text-center space-y-4">
              <div className="text-4xl">⚠️</div>
              <h2 className="text-xl font-semibold text-text-primary">
                Analysis Failed
              </h2>
              <p className="text-text-secondary">
                {error instanceof Error ? error.message : 'An error occurred while fetching your analysis.'}
              </p>
              <div className="pt-4">
                <Link href="/analyze">
                  <Button>Try Another Analysis</Button>
                </Link>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>
    )
  }

  // Loading state
  if (isLoading || !run) {
    return (
      <div className="container mx-auto px-4 py-12">
        <Card className="max-w-3xl mx-auto">
          <CardContent className="pt-6">
            <LoadingSpinner
              estimatedMinutes={4}
              currentStep="Analyzing your stock..."
            />
          </CardContent>
        </Card>
      </div>
    )
  }

  // Processing state
  if (run.status === 'queued' || run.status === 'running') {
    return (
      <div className="container mx-auto px-4 py-12">
        <Card className="max-w-3xl mx-auto">
          <CardContent className="pt-6">
            <LoadingSpinner
              estimatedMinutes={4}
              startTime={run.created_at}
              currentStep={
                run.status === 'queued'
                  ? 'Analysis queued...'
                  : 'Analyzing your stock...'
              }
            />
          </CardContent>
        </Card>
      </div>
    )
  }

  // Failed state
  if (run.status === 'failed') {
    const result = run.results?.[0]
    return (
      <div className="container mx-auto px-4 py-12">
        <Card className="max-w-2xl mx-auto">
          <CardContent className="pt-6">
            <div className="text-center space-y-4">
              <div className="text-4xl">❌</div>
              <h2 className="text-xl font-semibold text-text-primary">
                Analysis Failed
              </h2>
              <p className="text-text-secondary">
                {result?.error_message || 'The analysis could not be completed.'}
              </p>
              <p className="text-sm text-text-tertiary">
                Don't worry! We've automatically issued a full refund.
              </p>
              <div className="pt-4">
                <Link href="/analyze">
                  <Button>Try Another Analysis</Button>
                </Link>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>
    )
  }

  // Completed state - show results
  const result = run.results?.[0]

  if (!result || !result.full_output) {
    return (
      <div className="container mx-auto px-4 py-12">
        <Card className="max-w-2xl mx-auto">
          <CardContent className="pt-6">
            <div className="text-center space-y-4">
              <h2 className="text-xl font-semibold text-text-primary">
                No Results Available
              </h2>
              <p className="text-text-secondary">
                The analysis completed but results are not available.
              </p>
            </div>
          </CardContent>
        </Card>
      </div>
    )
  }

  const { moat_score, full_output } = result
  const {
    moat_breakdown,
    key_insights,
    risk_factors,
    signal_breakdown,
    upgrade_triggers,
    downgrade_triggers,
    decision_intelligence,
  } = full_output

  // Generate enhanced data using transformation functions
  const verdictData = generateVerdictSummary(full_output, decision_intelligence, moat_score)
  const { strengths, concerns } = simplifyKeyInsights(key_insights || [], risk_factors || [])
  const ratingTriggersData = generateRatingTriggers(full_output, decision_intelligence)

  // Extract data for new components
  const whatsNewItems = extractWhatsNew(full_output)
  const watchCalendarEvents = extractWatchCalendar(full_output)
  const quickActionsData = extractQuickActionsData(full_output, result.ticker)

  return (
    <div className="container mx-auto px-4 py-8">
      <div className="max-w-6xl mx-auto space-y-6">

        {/* 1. Header */}
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold text-text-primary">
              {result.ticker} Analysis
            </h1>
            <p className="text-sm text-text-secondary">
              Completed {formatDateTime(run.completed_at || run.created_at)}
            </p>
          </div>
          <div className="flex items-center gap-2">
            {decision_intelligence?.rating && (
              <Badge variant={
                decision_intelligence.rating.includes('BUY') ? 'success' :
                decision_intelligence.rating === 'HOLD' ? 'warning' : 'error'
              }>
                {decision_intelligence.rating}
              </Badge>
            )}
            {decision_intelligence?.risk_level && (
              <Badge variant="secondary">{decision_intelligence.risk_level} Risk</Badge>
            )}
          </div>
        </div>

        {/* 2. Signal Divergence Hero (always shown if signal data exists) */}
        {signal_breakdown && (
          <SignalDivergenceHero
            signalBreakdown={signal_breakdown}
            fundTechDivergence={decision_intelligence?.fund_tech_divergence}
          />
        )}

        {/* 3. Decision Action (one-liner + holder/buyer guidance) */}
        {decision_intelligence?.decision_framework && (
          <DecisionAction
            framework={decision_intelligence.decision_framework}
            ticker={result.ticker}
            rating={decision_intelligence.rating}
            riskLevel={decision_intelligence.risk_level}
          />
        )}

        {/* 4. The Verdict - WHY not WHAT (30-second investment thesis) */}
        <VerdictSummary {...verdictData} />

        {/* 4.6. What's New This Week */}
        <WhatsNew items={whatsNewItems} />

        {/* 5. Key Takeaways (strengths vs concerns) */}
        <KeyTakeaways
          strengths={strengths}
          concerns={concerns}
        />

        {/* 6. Signal Divergence Section (PRIORITY - THE DIFFERENTIATOR) */}
        {signal_breakdown && (
          <SignalDivergenceSection
            breakdown={signal_breakdown}
            recentNews={[
              // TODO: Extract from full_output.news_hound_output or decision_intelligence
              // For now, using placeholder structure
            ]}
            nextEarningsDate={undefined} // TODO: Extract from full_output
          />
        )}

        {/* 6.5. What to Watch Calendar */}
        <WatchCalendar events={watchCalendarEvents} />

        {/* 7. Score Breakdown Bars with context */}
        {moat_breakdown && moat_score !== null && (
          <ScoreBreakdownBars breakdown={moat_breakdown} overallScore={moat_score} />
        )}

        {/* 7.5 Portfolio Context - Position Sizing Guidance */}
        {decision_intelligence && moat_breakdown && (
          <PortfolioContext
            ticker={result.ticker}
            rating={decision_intelligence.rating || 'HOLD'}
            moatScore={moat_score || 5.0}
            financialHealthScore={moat_breakdown.financial_health}
            sector="Technology" // TODO: Extract from full_output
            currentPrice={decision_intelligence.current_price || 0}
          />
        )}

        {/* 8. Trade Setup (conservative vs aggressive) */}
        {decision_intelligence?.enhanced_trade_setup && (
          <TradeSetup
            setup={decision_intelligence.enhanced_trade_setup}
            ticker={result.ticker}
          />
        )}

        {/* 8.5. Quick Actions Checklist */}
        <QuickActions
          ticker={quickActionsData.ticker}
          current_price={quickActionsData.current_price}
          rating={quickActionsData.rating}
          key_levels={quickActionsData.key_levels}
          next_catalyst={quickActionsData.next_catalyst}
          conviction_position={decision_intelligence?.conviction_position}
        />

        {/* 10. Bottom Line */}
        <BottomLine
          upgradeTriggers={upgrade_triggers}
          downgradeTriggers={downgrade_triggers}
        />

        {/* 10.5. Enhanced Rating Triggers */}
        <RatingTriggers {...ratingTriggersData} />

        {/* 11. Professional Analysis Section */}
        <ProfessionalAnalysisSection
          ticker={result.ticker}
          run_id={run_id}
          onDownloadPDF={async () => {
            try {
              const response = await fetch(`/api/proxy/runs/${run_id}/report/pdf`)
              if (!response.ok) {
                const error = await response.json().catch(() => ({ error: 'PDF generation failed' }))
                throw new Error(error.detail || error.error || 'Failed to generate PDF')
              }
              const blob = await response.blob()
              const url = window.URL.createObjectURL(blob)
              const a = document.createElement('a')
              a.href = url
              a.download = `report_${result.ticker}_${run_id.slice(0, 8)}.pdf`
              document.body.appendChild(a)
              a.click()
              document.body.removeChild(a)
              window.URL.revokeObjectURL(url)
            } catch (error) {
              alert(error instanceof Error ? error.message : 'Failed to download PDF. Please try again.')
            }
          }}
        />

        {/* 12. Analyze Another Stock */}
        <div className="flex justify-center">
          <Link href="/analyze">
            <Button variant="outline" size="lg">Analyze Another Stock</Button>
          </Link>
        </div>

        {/* 12. Disclaimer */}
        <Card className="bg-surface-elevated/50">
          <CardContent className="pt-6">
            <p className="text-xs text-text-tertiary text-center">
              <strong>Disclaimer:</strong> This analysis is for informational purposes only and
              should not be considered financial advice. Past performance is not indicative of
              future results. Please consult with a qualified financial advisor before making
              investment decisions.
            </p>
          </CardContent>
        </Card>
      </div>
    </div>
  )
}
