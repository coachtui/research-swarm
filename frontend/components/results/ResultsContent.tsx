'use client'

import { useEffect, useState } from 'react'
import Link from 'next/link'
import { ChevronDown, ChevronUp } from 'lucide-react'
import { useAnalysis } from '@/lib/hooks/useAnalysis'
import { useCurrentUser } from '@/lib/hooks/useCurrentUser'
import { useEntitlements } from '@/lib/hooks/useEntitlements'
import { LoadingSpinner } from '@/components/shared/LoadingSpinner'
import { CapitalDeploymentSummary } from '@/components/results/CapitalDeploymentSummary'
import { TrancheDeploymentPath } from '@/components/results/TrancheDeploymentPath'
import { ScoreBreakdownBars } from '@/components/results/ScoreBreakdownBars'
import { FairValueRegimeCheck } from '@/components/results/FairValueRegimeCheck'
import { PriceTargetsCard } from '@/components/results/PriceTargetsCard'
import { CompressedRiskPanel } from '@/components/results/CompressedRiskPanel'
import { WatchForSummary } from '@/components/results/WatchForSummary'
import { ProbabilisticEngineDashboard } from '@/components/results/ProbabilisticEngineDashboard'
import { HistoricalAnalogPanel } from '@/components/results/HistoricalAnalogPanel'
import { SmartMoneyAlert } from '@/components/results/SmartMoneyAlert'
import { AnalystVerdict } from '@/components/results/AnalystVerdict'
import { InstitutionalRiskDashboard } from '@/components/results/InstitutionalRiskDashboard'
import { ExecutionLayer } from '@/components/results/ExecutionLayer'
import { ReportCommandBar } from '@/components/results/ReportCommandBar'
import { DeltaSummaryBox } from '@/components/results/DeltaSummaryBox'
import { TierGate } from '@/components/common/TierGate'
import { Card, CardContent } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { OnboardingPanel } from '@/components/knowledge/OnboardingPanel'
import type { RunResponse } from '@/types/api'

// ── Collapsible section wrapper ────────────────────────────────────────────────

function CollapsibleSection({
  title,
  sublabel,
  defaultOpen = false,
  badge,
  children,
}: {
  title: string
  sublabel?: string
  defaultOpen?: boolean
  badge?: string
  children: React.ReactNode
}) {
  const [open, setOpen] = useState(defaultOpen)
  return (
    <div className="rounded-xl border border-border/60 bg-surface/30 overflow-hidden">
      <button
        onClick={() => setOpen(o => !o)}
        className="w-full flex items-center justify-between px-5 py-3.5 text-left hover:bg-surface-elevated/30 transition-colors"
      >
        <div>
          <p className="text-sm font-semibold text-text-primary">{title}</p>
          {sublabel && (
            <p className="text-[10px] text-text-tertiary mt-0.5">{sublabel}</p>
          )}
        </div>
        <div className="flex items-center gap-2">
          {badge && (
            <span className="text-[10px] font-semibold uppercase tracking-wide text-text-tertiary border border-border rounded px-1.5 py-0.5">
              {badge}
            </span>
          )}
          {open
            ? <ChevronUp className="h-4 w-4 text-text-tertiary flex-shrink-0" />
            : <ChevronDown className="h-4 w-4 text-text-tertiary flex-shrink-0" />}
        </div>
      </button>
      {open && (
        <div className="border-t border-border/40 px-4 pb-4 pt-3 space-y-4">
          {children}
        </div>
      )}
    </div>
  )
}

// ── Tactical signal score card (Section 6) ────────────────────────────────────

function SignalCard({
  label,
  score,
  interpretation,
  hasData,
}: {
  label: string
  score: number
  interpretation: string
  hasData?: boolean
}) {
  const na = hasData === false
  const color = na
    ? 'text-text-tertiary'
    : score >= 7 ? 'text-success' : score >= 4 ? 'text-warning' : 'text-error'
  const barColor = score >= 7 ? 'bg-success' : score >= 4 ? 'bg-warning' : 'bg-error'

  return (
    <div className="rounded-lg border border-border/60 bg-surface-elevated p-3.5 space-y-2">
      <div className="flex items-center justify-between">
        <p className="text-[10px] font-semibold uppercase tracking-wider text-text-tertiary">{label}</p>
        <span className={`text-sm font-bold font-mono tabular-nums ${color}`}>
          {na ? 'N/A' : score.toFixed(1)}
        </span>
      </div>
      {!na && (
        <div className="h-1.5 bg-surface rounded-full overflow-hidden">
          <div
            className={`h-full rounded-full ${barColor}`}
            style={{ width: `${Math.min((score / 10) * 100, 100)}%` }}
          />
        </div>
      )}
      {interpretation && (
        <p className="text-[11px] text-text-tertiary leading-snug line-clamp-2">{interpretation}</p>
      )}
    </div>
  )
}

// ── Main component ────────────────────────────────────────────────────────────

export function ResultsContent({
  runId,
  previewData,
  isPreview = false,
}: {
  runId?: string
  previewData?: RunResponse
  isPreview?: boolean
}) {
  const { data: fetchedRun, isLoading, error } = useAnalysis(previewData ? null : (runId ?? null))
  const run = previewData ?? fetchedRun
  const { data: currentUser } = useCurrentUser()
  const { data: entitlements } = useEntitlements()
  const [isReadingMode, setReadingMode] = useState(false)

  const userTier = isPreview ? 'investor' : (currentUser?.tier ?? null)
  const isAdmin  = isPreview ? false : (currentUser?.is_admin ?? false)

  // Granular capability flags derived from server-side entitlements
  const canSeeSignalMetrics     = isAdmin || (entitlements?.features['feature.report.signal_metrics'] ?? false)
  const canSeeEngineDiagnostics = isAdmin || (entitlements?.features['feature.report.engine_diagnostics'] ?? false)

  useEffect(() => {
    const handleKey = (e: KeyboardEvent) => {
      if (e.target instanceof HTMLInputElement || e.target instanceof HTMLTextAreaElement) return
      if (e.key === 'r' || e.key === 'R') setReadingMode(prev => !prev)
    }
    document.addEventListener('keydown', handleKey)
    return () => document.removeEventListener('keydown', handleKey)
  }, [])

  // ── Error / loading states ──────────────────────────────────────────────────

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
                Don&apos;t worry! We&apos;ve automatically issued a full refund.
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

  // ── Data extraction ─────────────────────────────────────────────────────────

  const { moat_score, full_output } = result
  const {
    moat_breakdown,
    risk_factors,
    signal_breakdown,
    upgrade_triggers,
    downgrade_triggers,
    decision_intelligence,
  } = full_output

  return (
    <OnboardingPanel>

      {/* ══ STICKY COMMAND BAR ══════════════════════════════════════════════ */}
      <ReportCommandBar
        ticker={result.ticker}
        price={decision_intelligence?.current_price ?? null}
        timestamp={run.completed_at || run.created_at}
        runId={run.id}
        companyName={full_output?.fundamentalist_output?.company_name}
        isReadingMode={isReadingMode}
        onToggleReadingMode={() => setReadingMode(r => !r)}
      />

      <div className="container mx-auto px-4 pt-4 pb-8">
        <div className="max-w-6xl mx-auto space-y-3">

          {/* ── Longitudinal delta ────────────────────────────────────────── */}
          {full_output?.previous_analysis_delta && (
            <DeltaSummaryBox
              delta={full_output.previous_analysis_delta}
              ticker={result.ticker}
            />
          )}

          {/* ══════════════════════════════════════════════════════════════════
              SECTION 1 — CAPITAL DEPLOYMENT SUMMARY
              Always expanded. Answers: initiate? at what price? at what size?
              what breaks the thesis?
              ══════════════════════════════════════════════════════════════════ */}
          {decision_intelligence?.conviction_position && (
            <CapitalDeploymentSummary
              rating={decision_intelligence.rating}
              conviction={decision_intelligence.conviction_position}
              strategy={decision_intelligence.recommended_strategy}
              upgradeTriggers={upgrade_triggers}
              downgradeTriggers={downgrade_triggers}
              ticker={result.ticker}
            />
          )}

          {/* ══════════════════════════════════════════════════════════════════
              TRANCHE DEPLOYMENT PATH (Investor+)
              3-stage capital deployment timing framework — display only.
              Blurred upgrade preview shown for Starter tier.
              ══════════════════════════════════════════════════════════════════ */}
          {decision_intelligence?.tranche_plan && (
            <TierGate feature="capital_deployment_path" userTier={userTier} isAdmin={isAdmin}>
              <TrancheDeploymentPath tranchePlan={decision_intelligence.tranche_plan} />
            </TierGate>
          )}

          {/* ══════════════════════════════════════════════════════════════════
              SECTION 2 — STRUCTURAL QUALITY
              Moat · Earnings durability · Financial health · Quality score
              ══════════════════════════════════════════════════════════════════ */}
          {moat_breakdown && moat_score !== null && (
            <CollapsibleSection
              title="Structural Quality"
              sublabel="Moat · Earnings durability · Financial health · Quality score"
            >
              <TierGate feature="structural_quality_full" userTier={userTier} isAdmin={isAdmin}>
                <ScoreBreakdownBars breakdown={moat_breakdown} overallScore={moat_score} />
              </TierGate>
            </CollapsibleSection>
          )}

          {/* ══════════════════════════════════════════════════════════════════
              SECTION 3 — MISPRICING ENGINE
              Intrinsic anchor · Divergence · Valuation regime · Consensus gap
              ══════════════════════════════════════════════════════════════════ */}
          {full_output?.fair_value_calibration && (
            <CollapsibleSection
              title="Mispricing Engine"
              sublabel="Intrinsic anchor · Divergence · Valuation regime · Consensus gap"
            >
              <FairValueRegimeCheck
                calibration={full_output.fair_value_calibration}
                currentPrice={decision_intelligence?.current_price}
                financialHealthScore={moat_breakdown?.financial_health}
                idealEntryZone={decision_intelligence?.recommended_strategy?.entry?.ideal_zone}
              />
            </CollapsibleSection>
          )}

          {/* ══════════════════════════════════════════════════════════════════
              SECTION 4 — SCENARIO & EV
              Bear · Base · Bull · Probability-weighted expected value
              ══════════════════════════════════════════════════════════════════ */}
          {decision_intelligence?.current_price && full_output?.price_targets && (
            <CollapsibleSection
              title="Scenario & EV"
              sublabel="Bear · Base · Bull · Probability-weighted expected value · Downside %"
            >
              <PriceTargetsCard
                priceTargets={full_output.price_targets}
                currentPrice={decision_intelligence.current_price}
                ticker={result.ticker}
                signalBreakdown={signal_breakdown}
              />
            </CollapsibleSection>
          )}

          {/* ══════════════════════════════════════════════════════════════════
              SECTION 5 — RISK FACTORS
              Key risks · Thesis invalidation · Stop probability
              No valuation content.
              ══════════════════════════════════════════════════════════════════ */}
          {((risk_factors?.length ?? 0) > 0 ||
            (downgrade_triggers?.length ?? 0) > 0 ||
            !!signal_breakdown) && (
            <CollapsibleSection
              title="Risk Factors"
              sublabel="Key risks · Thesis invalidation · Stop probability"
            >
              <div className="space-y-4">
                {/* Compressed risk bullets + kill-thesis conditions */}
                {((risk_factors?.length ?? 0) > 0 || (downgrade_triggers?.length ?? 0) > 0) && (
                  <CompressedRiskPanel
                    riskFactors={risk_factors || []}
                    downgradeTriggers={downgrade_triggers}
                  />
                )}

                {/* Full trigger watchlist */}
                {(upgrade_triggers || downgrade_triggers) && (
                  <WatchForSummary
                    upgradeTriggers={upgrade_triggers}
                    downgradeTriggers={downgrade_triggers}
                  />
                )}

                {/* Probabilistic diagnostics (Investor+) */}
                {canSeeSignalMetrics && signal_breakdown && (
                  <ProbabilisticEngineDashboard
                    breakdown={signal_breakdown}
                    delta={full_output?.previous_analysis_delta ?? null}
                    userTier={userTier}
                    isAdmin={isAdmin}
                  />
                )}

                {/* Historical analogs (Trader) */}
                {canSeeEngineDiagnostics && signal_breakdown && (
                  <TierGate feature="historical_patterns" userTier={userTier} isAdmin={isAdmin}>
                    <HistoricalAnalogPanel breakdown={signal_breakdown} />
                  </TierGate>
                )}
              </div>
            </CollapsibleSection>
          )}

          {/* ══════════════════════════════════════════════════════════════════
              SECTION 6 — TACTICAL OVERLAYS
              Analyst · Sentiment · Insider · Dark pool
              ══════════════════════════════════════════════════════════════════ */}
          {signal_breakdown && (
            <CollapsibleSection
              title="Tactical Overlays"
              sublabel="Analyst · Sentiment · Insider · Dark pool"
            >
              <div className="space-y-4">
                {/* 2×2 signal score grid */}
                <div className="grid grid-cols-2 gap-3">
                  <SignalCard
                    label="Analyst"
                    score={signal_breakdown.analyst_score}
                    interpretation={signal_breakdown.analyst_interpretation}
                    hasData={signal_breakdown.analyst_has_data}
                  />
                  <SignalCard
                    label="Sentiment"
                    score={signal_breakdown.news_score}
                    interpretation={signal_breakdown.news_interpretation}
                    hasData={signal_breakdown.news_has_data}
                  />
                  <SignalCard
                    label="Insider"
                    score={signal_breakdown.insider_score}
                    interpretation={signal_breakdown.insider_interpretation}
                    hasData={signal_breakdown.insider_has_data}
                  />
                  <SignalCard
                    label="Dark Pool"
                    score={signal_breakdown.dark_pool_score}
                    interpretation={signal_breakdown.dark_pool_interpretation}
                    hasData={signal_breakdown.dark_pool_has_data}
                  />
                </div>

                {/* Smart money alert */}
                <SmartMoneyAlert signalBreakdown={signal_breakdown} />

                {/* Analyst verdict (Investor+) */}
                {canSeeSignalMetrics && full_output?.investment_thesis && (
                  <TierGate feature="analyst_verdict" userTier={userTier} isAdmin={isAdmin}>
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
                  </TierGate>
                )}

                {/* Institutional risk (Trader) */}
                {canSeeEngineDiagnostics && (
                  <TierGate feature="institutional_risk" userTier={userTier} isAdmin={isAdmin}>
                    <InstitutionalRiskDashboard breakdown={signal_breakdown} />
                  </TierGate>
                )}
              </div>
            </CollapsibleSection>
          )}

          {/* ══════════════════════════════════════════════════════════════════
              EXECUTION LAYER (Trader — always at bottom when entitled)
              ══════════════════════════════════════════════════════════════════ */}
          <TierGate feature="execution_layer" userTier={userTier} isAdmin={isAdmin}>
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
          </TierGate>

          {/* ── Footer ──────────────────────────────────────────────────────── */}
          <div className="flex justify-center pt-2">
            <Link href="/analyze">
              <Button variant="outline" size="lg">Analyze Another Stock</Button>
            </Link>
          </div>

          <Card className="bg-surface-elevated/50">
            <CardContent className="pt-6">
              <p className="text-xs text-text-tertiary text-center">
                <strong>Disclaimer:</strong> This analysis is for informational purposes only and
                should not be considered financial advice. Past performance is not indicative of
                future results. Consult a qualified financial advisor before making investment decisions.
              </p>
            </CardContent>
          </Card>

        </div>
      </div>

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
