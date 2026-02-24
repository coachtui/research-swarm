'use client'

import { useEffect, useState } from 'react'
import { useAuth } from '@clerk/nextjs'
import Link from 'next/link'
import { useAnalysis } from '@/lib/hooks/useAnalysis'
import { apiClient } from '@/lib/api/client'
import { LoadingSpinner } from '@/components/shared/LoadingSpinner'
import { SignalDivergenceSection } from '@/components/results/SignalDivergenceSection'
import { DecisionAction } from '@/components/results/DecisionAction'
import { DecisionSummaryCard } from '@/components/results/DecisionSummaryCard'
import { PriceTargetsCard } from '@/components/results/PriceTargetsCard'
import { KeyTakeaways } from '@/components/results/KeyTakeaways'
import { ScoreBreakdownBars } from '@/components/results/ScoreBreakdownBars'
import { RecentDevelopments } from '@/components/results/RecentDevelopments'
import { ExecutionLayer } from '@/components/results/ExecutionLayer'
import { AnalystVerdict } from '@/components/results/AnalystVerdict'
import { FairValueRegimeCheck } from '@/components/results/FairValueRegimeCheck'
import { HistoricalAnalogPanel } from '@/components/results/HistoricalAnalogPanel'
import { Card, CardContent } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { formatDateTime } from '@/lib/utils/formatting'
import { simplifyKeyInsights } from '@/lib/analysis/simplifyKeyInsights'
import { extractWhatsNew } from '@/lib/analysis/extractWhatsNew'
import { extractWatchCalendar } from '@/lib/analysis/extractWatchCalendar'
import { AddToWatchlistButton } from '@/components/dashboard/AddToWatchlistButton'
import { OnboardingPanel } from '@/components/knowledge/OnboardingPanel'
import { SmartMoneyAlert } from '@/components/results/SmartMoneyAlert'
import { WatchForSummary } from '@/components/results/WatchForSummary'
import { DeltaSummaryBox } from '@/components/results/DeltaSummaryBox'

interface ResultsPageProps {
  params: { run_id: string }
}

/**
 * Section divider — creates clear visual separation between analytical layers.
 * Variant "primary" for actionable panels, "muted" for long-term/structural panels.
 */
function SectionDivider({
  label,
  sublabel,
  variant = 'primary',
}: {
  label: string
  sublabel?: string
  variant?: 'primary' | 'muted' | 'neutral'
}) {
  const borderColor =
    variant === 'primary' ? 'border-l-primary' :
    variant === 'muted'   ? 'border-l-border' :
    'border-l-border-subtle'

  const labelColor =
    variant === 'primary' ? 'text-text-secondary' :
    variant === 'muted'   ? 'text-text-tertiary' :
    'text-text-tertiary'

  const lineColor =
    variant === 'muted' ? 'border-border/40' : 'border-border/70'

  return (
    <div className={`flex items-center gap-3 border-l-[3px] ${borderColor} pl-3`}>
      <div className="flex-1">
        <div className="flex items-center gap-3">
          <span className={`text-[11px] font-bold uppercase tracking-[0.14em] ${labelColor}`}>
            {label}
          </span>
          {sublabel && (
            <span className="text-[10px] text-text-tertiary italic">{sublabel}</span>
          )}
          <div className={`flex-1 border-t ${lineColor}`} />
        </div>
      </div>
    </div>
  )
}

export default function ResultsPage({ params }: ResultsPageProps) {
  const { run_id } = params
  const { getToken } = useAuth()
  const [tokenReady, setTokenReady] = useState(false)

  useEffect(() => {
    apiClient.setTokenGetter(getToken)
    setTokenReady(true)
  }, [getToken])

  if (!tokenReady) {
    return (
      <div className="min-h-screen bg-background flex items-center justify-center">
        <LoadingSpinner />
      </div>
    )
  }

  return <ResultsContent runId={run_id} />
}

function ResultsContent({ runId }: { runId: string }) {
  const { data: run, isLoading, error } = useAnalysis(runId)
  const [isReadingMode, setReadingMode] = useState(false)

  useEffect(() => {
    const handleKey = (e: KeyboardEvent) => {
      if (e.target instanceof HTMLInputElement || e.target instanceof HTMLTextAreaElement) return
      if (e.key === 'r' || e.key === 'R') setReadingMode(prev => !prev)
    }
    document.addEventListener('keydown', handleKey)
    return () => document.removeEventListener('keydown', handleKey)
  }, [])

  if (error) {
    return (
      <div className="container mx-auto px-4 py-12">
        <Card className="max-w-2xl mx-auto">
          <CardContent className="pt-6">
            <div className="text-center space-y-4">
              <div className="text-4xl">⚠️</div>
              <h2 className="text-xl font-semibold text-text-primary">Analysis Failed</h2>
              <p className="text-text-secondary">
                {error instanceof Error ? error.message : 'An error occurred while fetching your analysis.'}
              </p>
              <div className="pt-4">
                <Link href="/analyze"><Button>Try Another Analysis</Button></Link>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>
    )
  }

  if (isLoading || !run) {
    return (
      <div className="container mx-auto px-4 py-12">
        <Card className="max-w-3xl mx-auto">
          <CardContent className="pt-6">
            <LoadingSpinner estimatedMinutes={4} currentStep="Analyzing your stock..." />
          </CardContent>
        </Card>
      </div>
    )
  }

  if (run.status === 'queued' || run.status === 'running') {
    return (
      <div className="container mx-auto px-4 py-12">
        <Card className="max-w-3xl mx-auto">
          <CardContent className="pt-6">
            <LoadingSpinner
              estimatedMinutes={4}
              startTime={run.created_at}
              currentStep={run.status === 'queued' ? 'Analysis queued...' : 'Analyzing your stock...'}
            />
          </CardContent>
        </Card>
      </div>
    )
  }

  if (run.status === 'failed') {
    const result = run.results?.[0]
    return (
      <div className="container mx-auto px-4 py-12">
        <Card className="max-w-2xl mx-auto">
          <CardContent className="pt-6">
            <div className="text-center space-y-4">
              <div className="text-4xl">❌</div>
              <h2 className="text-xl font-semibold text-text-primary">Analysis Failed</h2>
              <p className="text-text-secondary">
                {result?.error_message || 'The analysis could not be completed.'}
              </p>
              <p className="text-sm text-text-tertiary">
                Don't worry! We've automatically issued a full refund.
              </p>
              <div className="pt-4">
                <Link href="/analyze"><Button>Try Another Analysis</Button></Link>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>
    )
  }

  const result = run.results?.[0]
  if (!result || !result.full_output) {
    return (
      <div className="container mx-auto px-4 py-12">
        <Card className="max-w-2xl mx-auto">
          <CardContent className="pt-6">
            <div className="text-center space-y-4">
              <h2 className="text-xl font-semibold text-text-primary">No Results Available</h2>
              <p className="text-text-secondary">The analysis completed but results are not available.</p>
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

  const { strengths, concerns } = simplifyKeyInsights(key_insights || [], risk_factors || [])
  const whatsNewItems = extractWhatsNew(full_output)
  const watchCalendarEvents = extractWatchCalendar(full_output)

  return (
    <OnboardingPanel>
    <div className="container mx-auto px-4 py-8">
      <div className="max-w-6xl mx-auto space-y-6">

        {/* ══ IDENTITY BAR ══════════════════════════════════════════════ */}
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="relative w-10 h-10 rounded-lg bg-surface-elevated overflow-hidden flex-shrink-0 border border-border-subtle">
              <img
                src={`https://assets.parqet.com/logos/symbol/${result.ticker}`}
                alt={`${result.ticker} logo`}
                className="w-full h-full object-contain p-1.5"
                onError={(e) => {
                  const target = e.target as HTMLImageElement
                  target.style.display = 'none'
                  const fallback = target.nextElementSibling as HTMLDivElement
                  if (fallback) fallback.style.display = 'flex'
                }}
              />
              <div className="absolute inset-0 items-center justify-center bg-surface-elevated text-text-secondary text-xl font-bold hidden">
                {result.ticker[0]}
              </div>
            </div>
            <div>
              <div className="flex items-center gap-2.5">
                <span className="text-lg font-bold text-text-primary">{result.ticker}</span>
                {decision_intelligence?.current_price && (
                  <span className="text-base font-semibold text-text-primary">
                    ${decision_intelligence.current_price.toFixed(2)}
                  </span>
                )}
              </div>
              <p className="text-[11px] text-text-tertiary">
                {formatDateTime(run.completed_at || run.created_at)}
              </p>
            </div>
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
            <button
              onClick={() => setReadingMode(r => !r)}
              className={`text-[10px] font-mono border rounded px-1.5 py-0.5 transition-colors ${
                isReadingMode
                  ? 'bg-primary/10 text-primary border-primary/30'
                  : 'text-text-tertiary border-border hover:text-text-secondary hover:border-border-subtle'
              }`}
              title="Toggle Reading Mode (R)"
            >
              {isReadingMode ? 'EXIT' : '[R]'}
            </button>
            <AddToWatchlistButton
              ticker={result.ticker}
              companyName={full_output?.fundamentalist_output?.company_name}
              runId={run.id}
            />
          </div>
        </div>

        {/* ══ LONGITUDINAL DELTA ════════════════════════════════════════ */}
        <div className={`transition-opacity duration-200${isReadingMode ? ' opacity-30 pointer-events-none' : ''}`}>
          {full_output?.previous_analysis_delta && (
            <DeltaSummaryBox
              delta={full_output.previous_analysis_delta}
              ticker={result.ticker}
            />
          )}
        </div>

        {/* ══ DECISION SUMMARY CARD (Above-the-Fold) ════════════════════
            PM-first: rating + 1-sentence thesis + primary catalyst/risk.
            No valuation anchors or asymmetry math visible here.           */}
        {decision_intelligence && (
          <DecisionSummaryCard
            rating={decision_intelligence.rating}
            riskLevel={decision_intelligence.risk_level}
            convictionLevel={decision_intelligence.conviction_position?.conviction_level ?? null}
            thesis={full_output?.investment_thesis ?? null}
            upgradeTriggers={upgrade_triggers}
            downgradeTriggers={downgrade_triggers}
          />
        )}

        {/* ══════════════════════════════════════════════════════════════
            PANEL A — TACTICAL FRAMEWORK (0–3 Months)
            Execution-oriented: price context, signals, setup guidance.
            Everything in this panel is actionable on a short horizon.
        ══════════════════════════════════════════════════════════════ */}
        <div className="space-y-6 pt-2">
          <SectionDivider label="Tactical Framework" sublabel="0–3 Month Horizon" variant="primary" />

          {/* Decision Action: rating + key zones + tabbed guidance */}
          {decision_intelligence?.decision_framework && (
            <DecisionAction
              framework={decision_intelligence.decision_framework}
              ticker={result.ticker}
              rating={decision_intelligence.rating}
              riskLevel={decision_intelligence.risk_level}
              currentPrice={decision_intelligence.current_price}
              strategy={decision_intelligence.recommended_strategy}
              signalBreakdown={signal_breakdown}
              fundTechDivergence={decision_intelligence.fund_tech_divergence}
              convictionLevel={decision_intelligence.conviction_position?.conviction_level}
              enhancedTradeSetup={decision_intelligence.enhanced_trade_setup}
            />
          )}

          {/* Supporting analysis — dimmed in Reading Mode */}
          <div className={`space-y-6 transition-opacity duration-200${isReadingMode ? ' opacity-30 pointer-events-none' : ''}`}>

            {/* Smart Money Divergence — core differentiator, shown when gap > 3pts */}
            {signal_breakdown && (
              <SmartMoneyAlert signalBreakdown={signal_breakdown} />
            )}

            {/* Watch For: top-2 upgrade/downgrade catalysts surfaced early */}
            {(upgrade_triggers || downgrade_triggers) && (
              <WatchForSummary
                upgradeTriggers={upgrade_triggers}
                downgradeTriggers={downgrade_triggers}
              />
            )}

            {/* Score Scoreboard — 5-factor breakdown */}
            {moat_breakdown && moat_score !== null && (
              <ScoreBreakdownBars breakdown={moat_breakdown} overallScore={moat_score} />
            )}

            {/* Signal Matrix — 7-signal alignment + conflict detection */}
            {signal_breakdown && (
              <SignalDivergenceSection
                breakdown={signal_breakdown}
                recentNews={[]}
                nextEarningsDate={undefined}
              />
            )}

            {/* Historical Pattern Framing */}
            {signal_breakdown && (
              <HistoricalAnalogPanel breakdown={signal_breakdown} />
            )}

            {/* Strengths vs. Concerns */}
            <KeyTakeaways strengths={strengths} concerns={concerns} />

            {/* Recent Developments + Upcoming Catalysts */}
            <RecentDevelopments
              recentItems={whatsNewItems}
              upcomingEvents={watchCalendarEvents}
            />
          </div>
        </div>

        {/* ══════════════════════════════════════════════════════════════
            PANEL B — LONG-TERM STRUCTURAL FRAMEWORK (12–36 Months)
            Valuation anchors, mean reversion references, scenario targets.
            Visually de-emphasized — NOT near-term actionable levels.
        ══════════════════════════════════════════════════════════════ */}
        <div className={`space-y-5 pt-2 transition-opacity duration-200 ${isReadingMode ? 'opacity-30 pointer-events-none' : 'opacity-[0.93]'}`}>
          <SectionDivider
            label="Long-Term Structural Framework"
            sublabel="12–36 Month Reference — Non-Actionable Near-Term"
            variant="muted"
          />

          {/* Scenario Value Construct: Bear / Base / Bull targets */}
          {decision_intelligence?.current_price && full_output?.price_targets && (
            <PriceTargetsCard
              priceTargets={full_output.price_targets}
              currentPrice={decision_intelligence.current_price}
              ticker={result.ticker}
            />
          )}

          {/* Fair Value Regime Check — model vs. consensus reconciliation */}
          {full_output?.fair_value_calibration && (
            <FairValueRegimeCheck
              calibration={full_output.fair_value_calibration}
              currentPrice={decision_intelligence?.current_price}
              financialHealthScore={moat_breakdown?.financial_health}
              idealEntryZone={decision_intelligence?.recommended_strategy?.entry?.ideal_zone}
            />
          )}
        </div>

        {/* ══════════════════════════════════════════════════════════════
            ANALYST VERDICT
            BLUF at top (always visible) + expandable full narrative.
            Investment thesis + what changes this rating.
        ══════════════════════════════════════════════════════════════ */}
        {full_output?.investment_thesis && (
          <div className="space-y-5 pt-2">
            <SectionDivider label="Analyst Verdict" variant="neutral" />
            <AnalystVerdict
              thesis={full_output.investment_thesis}
              upgradeTriggers={upgrade_triggers}
              downgradeTriggers={downgrade_triggers}
              signalBreakdown={signal_breakdown}
              valuationScore={moat_breakdown?.valuation}
              calibration={full_output.fair_value_calibration}
              currentPrice={decision_intelligence?.current_price}
              financialHealthScore={moat_breakdown?.financial_health}
            />
          </div>
        )}

        {/* ══════════════════════════════════════════════════════════════
            EXECUTION (collapsed by default)
            PM View (simplified allocation) / Trader View (full math)
        ══════════════════════════════════════════════════════════════ */}
        <div className={`space-y-6 transition-opacity duration-200${isReadingMode ? ' opacity-30 pointer-events-none' : ''}`}>
          {decision_intelligence && moat_breakdown && (
            <ExecutionLayer
              ticker={result.ticker}
              rating={decision_intelligence.rating || 'HOLD'}
              moatScore={moat_score || 5.0}
              financialHealthScore={moat_breakdown.financial_health}
              sector="Technology"
              currentPrice={decision_intelligence.current_price || 0}
              convictionPosition={decision_intelligence.conviction_position}
              enhancedTradeSetup={decision_intelligence.enhanced_trade_setup}
              strategy={decision_intelligence.recommended_strategy}
              signalBreakdown={signal_breakdown}
              calibration={full_output.fair_value_calibration}
            />
          )}

          {/* CTA */}
          <div className="flex justify-center pt-2">
            <Link href="/analyze">
              <Button variant="outline" size="lg">Analyze Another Stock</Button>
            </Link>
          </div>

          {/* Disclaimer */}
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
    </div>

    {/* Reading Mode indicator — fixed bottom pill, visible only when active */}
    {isReadingMode && (
      <div className="fixed bottom-5 left-1/2 -translate-x-1/2 z-50 flex items-center gap-2.5 px-4 py-2 bg-gray-900 border border-border rounded-full text-xs shadow-xl select-none">
        <span className="w-1.5 h-1.5 rounded-full bg-primary flex-shrink-0" />
        <span className="font-medium text-text-primary">Reading Mode</span>
        <span className="text-text-tertiary">· Press R or click EXIT to return</span>
      </div>
    )}
    </OnboardingPanel>
  )
}
