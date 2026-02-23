'use client'

import { useEffect, useState } from 'react'
import { useAuth } from '@clerk/nextjs'
import Link from 'next/link'
import { useAnalysis } from '@/lib/hooks/useAnalysis'
import { apiClient } from '@/lib/api/client'
import { LoadingSpinner } from '@/components/shared/LoadingSpinner'
import { SignalDivergenceSection } from '@/components/results/SignalDivergenceSection'
import { DecisionAction } from '@/components/results/DecisionAction'
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
      <div className="max-w-6xl mx-auto space-y-8">

        {/* ── IDENTITY BAR ─────────────────────────────────────────── */}
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="relative w-12 h-12 rounded-lg bg-surface-elevated overflow-hidden flex-shrink-0 border border-border-subtle">
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
              <div className="flex items-center gap-2">
                <span className="text-xl font-bold text-text-primary">{result.ticker}</span>
                {decision_intelligence?.current_price && (
                  <span className="text-lg font-semibold text-text-primary">
                    ${decision_intelligence.current_price.toFixed(2)}
                  </span>
                )}
              </div>
              <p className="text-xs text-text-tertiary">
                Completed {formatDateTime(run.completed_at || run.created_at)}
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
            <AddToWatchlistButton
              ticker={result.ticker}
              companyName={full_output?.fundamentalist_output?.company_name}
              runId={run.id}
            />
          </div>
        </div>

        {/* ── LONGITUDINAL DELTA — Since Last Analysis ──────────────
            Shown when the same user has a prior completed analysis for
            this ticker. Opens the report with a thesis comparison summary.
            Trader-tier differentiator: transforms snapshots into a living
            thesis tracker. */}
        {full_output?.previous_analysis_delta && (
          <DeltaSummaryBox
            delta={full_output.previous_analysis_delta}
            ticker={result.ticker}
          />
        )}

        {/* ══════════════════════════════════════════════════════════
            LAYER 1 — DECISION STACK
            Decision Action contains: rating, one-liner, signal strip,
            key price zones, and tabbed New Buyers / Current Holders
        ══════════════════════════════════════════════════════════ */}
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

        {/* ── SMART MONEY DIVERGENCE ALERT ─────────────────────────
            Shown immediately after the main recommendation when the gap
            between informed capital and public signals exceeds 3.0 pts.
            This is DVRG's core differentiator — surfaces it prominently. */}
        {signal_breakdown && (
          <SmartMoneyAlert signalBreakdown={signal_breakdown} />
        )}

        {/* ── WATCH FOR: Condensed upgrade/downgrade triggers ───────
            Top-2 triggers per direction surfaced early so users see
            the key catalysts before scrolling the full analysis. */}
        {(upgrade_triggers || downgrade_triggers) && (
          <WatchForSummary
            upgradeTriggers={upgrade_triggers}
            downgradeTriggers={downgrade_triggers}
          />
        )}

        {/* ══════════════════════════════════════════════════════════
            LAYER 2 — EVIDENCE
            Score scoreboard → Signal matrix → Key Takeaways → Catalysts
        ══════════════════════════════════════════════════════════ */}

        {/* 2A: Score Scoreboard — moved up to immediately follow decision */}
        {moat_breakdown && moat_score !== null && (
          <ScoreBreakdownBars breakdown={moat_breakdown} overallScore={moat_score} />
        )}

        {/* 2B + 2C: Signal matrix with inline conflict block */}
        {signal_breakdown && (
          <SignalDivergenceSection
            breakdown={signal_breakdown}
            recentNews={[]}
            nextEarningsDate={undefined}
          />
        )}

        {/* 2C.5: Historical Analog — heuristic pattern framing */}
        {signal_breakdown && (
          <HistoricalAnalogPanel breakdown={signal_breakdown} />
        )}

        {/* 2D: Key Takeaways — Strengths vs Risks */}
        <KeyTakeaways strengths={strengths} concerns={concerns} />

        {/* 2E: Recent Developments — merged WhatsNew + WatchCalendar */}
        <RecentDevelopments
          recentItems={whatsNewItems}
          upcomingEvents={watchCalendarEvents}
        />

        {/* ══════════════════════════════════════════════════════════
            LAYER 3 — VALUATION
            Price targets (Bear / Base / Bull)
        ══════════════════════════════════════════════════════════ */}
        {decision_intelligence?.current_price && full_output?.price_targets && (
          <PriceTargetsCard
            priceTargets={full_output.price_targets}
            currentPrice={decision_intelligence.current_price}
            ticker={result.ticker}
          />
        )}

        {/* ══════════════════════════════════════════════════════════
            LAYER 3.5 — FAIR VALUE REGIME CHECK
            Reconciles internal model vs market consensus proxy.
            Auto-expands on large divergences (>25%). Collapsed otherwise.
        ══════════════════════════════════════════════════════════ */}
        {full_output?.fair_value_calibration && (
          <FairValueRegimeCheck
            calibration={full_output.fair_value_calibration}
            currentPrice={decision_intelligence?.current_price}
            financialHealthScore={moat_breakdown?.financial_health}
            idealEntryZone={decision_intelligence?.recommended_strategy?.entry?.ideal_zone}
          />
        )}

        {/* ══════════════════════════════════════════════════════════
            LAYER 4 — NARRATIVE
            Single Analyst Verdict block (thesis + what changes rating)
            VerdictSummary removed — no duplicate narrative
        ══════════════════════════════════════════════════════════ */}
        {full_output?.investment_thesis && (
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
        )}

        {/* ══════════════════════════════════════════════════════════
            LAYER 5 — EXECUTION (collapsed by default)
            Position Sizing tab + Entry/Exit Setup tab
        ══════════════════════════════════════════════════════════ */}
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
    </OnboardingPanel>
  )
}
