'use client'

import { useEffect, useState } from 'react'
import Link from 'next/link'
import { ChevronDown, ChevronUp } from 'lucide-react'
import { useAnalysis } from '@/lib/hooks/useAnalysis'
import { useCurrentUser } from '@/lib/hooks/useCurrentUser'
import { useEntitlements } from '@/lib/hooks/useEntitlements'
import { LoadingSpinner } from '@/components/shared/LoadingSpinner'
import { SignalDivergenceSection } from '@/components/results/SignalDivergenceSection'
import { DecisionHeader } from '@/components/results/DecisionHeader'
import { CapitalAllocationDiscipline } from '@/components/results/CapitalAllocationDiscipline'
import { PriceTargetsCard } from '@/components/results/PriceTargetsCard'
import { KeyTakeaways } from '@/components/results/KeyTakeaways'
import { ScoreBreakdownBars } from '@/components/results/ScoreBreakdownBars'
import { RecentDevelopments } from '@/components/results/RecentDevelopments'
import { ExecutionLayer } from '@/components/results/ExecutionLayer'
import { AnalystVerdict } from '@/components/results/AnalystVerdict'
import { FairValueRegimeCheck } from '@/components/results/FairValueRegimeCheck'
import { HistoricalAnalogPanel } from '@/components/results/HistoricalAnalogPanel'
import { InstitutionalRiskDashboard } from '@/components/results/InstitutionalRiskDashboard'
import { ProbabilisticEngineDashboard } from '@/components/results/ProbabilisticEngineDashboard'
import { CompressedRiskPanel } from '@/components/results/CompressedRiskPanel'
import { TerminalDashboard } from '@/components/results/TerminalDashboard'
import { ModeToggle, type ReportMode } from '@/components/results/ModeToggle'
import { TierGate } from '@/components/common/TierGate'
import { Card, CardContent } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { formatDateTime } from '@/lib/utils/formatting'
import {
  deriveStructuralBias,
  deriveTacticalStance,
  structuralBiasBadgeVariant,
} from '@/lib/utils/decisionDimensions'
import { derivePositionType } from '@/lib/narratives/sizingNarrative'
import { simplifyKeyInsights } from '@/lib/analysis/simplifyKeyInsights'
import { extractWhatsNew } from '@/lib/analysis/extractWhatsNew'
import { extractWatchCalendar } from '@/lib/analysis/extractWatchCalendar'
import { AddToWatchlistButton } from '@/components/dashboard/AddToWatchlistButton'
import { OnboardingPanel } from '@/components/knowledge/OnboardingPanel'
import { SmartMoneyAlert } from '@/components/results/SmartMoneyAlert'
import { WatchForSummary } from '@/components/results/WatchForSummary'
import { DeltaSummaryBox } from '@/components/results/DeltaSummaryBox'
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
  const [reportMode, setReportMode] = useState<ReportMode>('investor')

  const userTier = isPreview ? 'investor' : (currentUser?.tier ?? null)
  const isAdmin = isPreview ? false : (currentUser?.is_admin ?? false)

  const canSeeCapitalDiscipline = isAdmin || (entitlements?.features['feature.report.signal_metrics'] ?? false)
  const canSeeAdvancedDiagnostics = isAdmin || (entitlements?.features['feature.report.engine_diagnostics'] ?? false)

  // Mode-aware section visibility
  // Investor: Terminal + Capital Discipline + Risk Profile only
  // Advisor: all sections
  // Allocator: Terminal + Capital Discipline (expanded) + Risk Profile
  const showModelInputs = reportMode === 'advisor'
  const showThesisDrivers = reportMode === 'advisor'
  const showAnalystThesis = reportMode === 'advisor'
  const capitalDisciplineOpen = reportMode === 'allocator'
  const riskProfileOpen = reportMode === 'investor'

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

  const hasDivergence = signal_breakdown?.has_divergence ?? false
  const divergenceSeverity = decision_intelligence?.fund_tech_divergence?.severity ?? null
  const structuralBias = deriveStructuralBias(decision_intelligence?.rating)
  const tacticalStance = deriveTacticalStance(
    decision_intelligence?.decision_framework?.new_buyers?.action ?? null,
    decision_intelligence?.rating,
    hasDivergence,
    (divergenceSeverity ?? null) as 'HIGH' | 'MODERATE' | null,
    false,
  )
  const positionType = decision_intelligence?.conviction_position
    ? derivePositionType(structuralBias, decision_intelligence.conviction_position.conviction_level)
    : 'Satellite'

  const hasRiskContent =
    (risk_factors?.length ?? 0) > 0 ||
    (downgrade_triggers?.length ?? 0) > 0 ||
    !!signal_breakdown

  return (
    <OnboardingPanel>
    <div className="container mx-auto px-4 py-8">
      <div className="max-w-6xl mx-auto space-y-4">

        {/* ══ IDENTITY BAR ══════════════════════════════════════════════ */}
        <div className="flex items-center justify-between gap-3 flex-wrap">
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
          <div className="flex items-center gap-2 flex-wrap">
            {decision_intelligence?.rating && (() => {
              const bias = deriveStructuralBias(decision_intelligence.rating)
              return (
                <Badge variant={structuralBiasBadgeVariant(bias)}>
                  {bias}
                </Badge>
              )
            })()}
            <ModeToggle mode={reportMode} onChange={setReportMode} />
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
        {full_output?.previous_analysis_delta && (
          <div className={`transition-opacity duration-200${isReadingMode ? ' opacity-30 pointer-events-none' : ''}`}>
            <DeltaSummaryBox
              delta={full_output.previous_analysis_delta}
              ticker={result.ticker}
            />
          </div>
        )}

        {/* ══════════════════════════════════════════════════════════════
            TERMINAL DASHBOARD — Unified top section (Rows 1–3)
            Always visible. Replaces CapitalSignalPanel + AsymmetryPanel
            + CapitalDeploymentPanel.
            ══════════════════════════════════════════════════════════════ */}
        {decision_intelligence?.conviction_position && (
          <TerminalDashboard
            rating={decision_intelligence.rating}
            ticker={result.ticker}
            currentPrice={decision_intelligence.current_price ?? 0}
            conviction={decision_intelligence.conviction_position}
            fairValueCalibration={full_output.fair_value_calibration}
            priceTargets={full_output.price_targets ?? null}
            signalBreakdown={signal_breakdown}
            expectedReturnAnnualized={
              decision_intelligence.recommended_strategy?.exit?.expected_return_annualized ?? undefined
            }
          />
        )}

        {/* ══════════════════════════════════════════════════════════════
            CAPITAL ALLOCATION DISCIPLINE (Investor+)
            Investor: collapsed. Allocator: expanded by default.
            ══════════════════════════════════════════════════════════════ */}
        {canSeeCapitalDiscipline && decision_intelligence?.conviction_position && (
          <CapitalAllocationDiscipline
            key={`discipline-${reportMode}`}
            conviction={decision_intelligence.conviction_position}
            signalBreakdown={signal_breakdown}
            ticker={result.ticker}
            rating={decision_intelligence.rating}
            structuralBias={structuralBias}
            tacticalStance={tacticalStance}
            positionType={positionType}
            defaultOpen={capitalDisciplineOpen}
          />
        )}

        {/* ══════════════════════════════════════════════════════════════
            RISK PROFILE (always visible)
            Merges: Risk Assessment + Probabilistic Diagnostics + Historical
            Investor: open by default. Advisor/Allocator: collapsed.
            ══════════════════════════════════════════════════════════════ */}
        {hasRiskContent && (
          <div className={`transition-opacity duration-200${isReadingMode ? ' opacity-30 pointer-events-none' : ''}`}>
            <CollapsibleSection
              key={`risk-${reportMode}`}
              title="Risk Profile"
              sublabel="Risk drivers · Stop probability · Probabilistic diagnostics"
              defaultOpen={riskProfileOpen}
            >
              <div className="space-y-4">
                {/* Risk drivers + downgrade triggers */}
                {((risk_factors?.length ?? 0) > 0 || (downgrade_triggers?.length ?? 0) > 0) && (
                  <CompressedRiskPanel
                    riskFactors={risk_factors || []}
                    downgradeTriggers={downgrade_triggers}
                  />
                )}

                {/* Probabilistic Diagnostics */}
                {signal_breakdown && (
                  <ProbabilisticEngineDashboard
                    breakdown={signal_breakdown}
                    delta={full_output?.previous_analysis_delta ?? null}
                    userTier={userTier}
                    isAdmin={isAdmin}
                  />
                )}

                {/* Historical Analogs (Trader) */}
                {canSeeAdvancedDiagnostics && (
                  <TierGate feature="historical_patterns" userTier={userTier} isAdmin={isAdmin}>
                    {signal_breakdown && (
                      <HistoricalAnalogPanel breakdown={signal_breakdown} />
                    )}
                  </TierGate>
                )}
              </div>
            </CollapsibleSection>
          </div>
        )}

        {/* ══════════════════════════════════════════════════════════════
            MODEL INPUTS (Advisor mode only)
            Merges: Valuation Components + Decision Framework
            ══════════════════════════════════════════════════════════════ */}
        {showModelInputs && (full_output?.fair_value_calibration || full_output?.price_targets || decision_intelligence?.decision_framework) && (
          <CollapsibleSection
            key={`inputs-${reportMode}`}
            title="Model Inputs"
            sublabel="FV regime · Scenario construct · Entry zones · Exit targets"
            defaultOpen={true}
          >
            {full_output?.fair_value_calibration && (
              <FairValueRegimeCheck
                calibration={full_output.fair_value_calibration}
                currentPrice={decision_intelligence?.current_price}
                financialHealthScore={moat_breakdown?.financial_health}
                idealEntryZone={decision_intelligence?.recommended_strategy?.entry?.ideal_zone}
              />
            )}
            {decision_intelligence?.current_price && full_output?.price_targets && (
              <PriceTargetsCard
                priceTargets={full_output.price_targets}
                currentPrice={decision_intelligence.current_price}
                ticker={result.ticker}
                signalBreakdown={signal_breakdown}
              />
            )}
            {decision_intelligence?.decision_framework && decision_intelligence?.conviction_position && (
              <DecisionHeader
                framework={decision_intelligence.decision_framework}
                ticker={result.ticker}
                rating={decision_intelligence.rating}
                riskLevel={decision_intelligence.risk_level}
                currentPrice={decision_intelligence.current_price}
                strategy={decision_intelligence.recommended_strategy}
                signalBreakdown={signal_breakdown}
                fundTechDivergence={decision_intelligence.fund_tech_divergence}
                convictionLevel={decision_intelligence.conviction_position.conviction_level}
                enhancedTradeSetup={decision_intelligence.enhanced_trade_setup}
                conviction={decision_intelligence.conviction_position}
              />
            )}
          </CollapsibleSection>
        )}

        {/* ══════════════════════════════════════════════════════════════
            THESIS DRIVERS (Advisor mode only)
            Merges: Signal Analysis + Intelligence Context
            ══════════════════════════════════════════════════════════════ */}
        {showThesisDrivers && (
          <div className={`transition-opacity duration-200${isReadingMode ? ' opacity-30 pointer-events-none' : ''}`}>
            <CollapsibleSection
              key={`thesis-${reportMode}`}
              title="Thesis Drivers"
              sublabel="Smart money · Score breakdown · Key takeaways · Catalysts"
              defaultOpen={false}
            >
              <div className="space-y-4">
                {signal_breakdown && (
                  <SmartMoneyAlert signalBreakdown={signal_breakdown} />
                )}
                {(upgrade_triggers || downgrade_triggers) && (
                  <WatchForSummary
                    upgradeTriggers={upgrade_triggers}
                    downgradeTriggers={downgrade_triggers}
                  />
                )}
                {moat_breakdown && moat_score !== null && (
                  <ScoreBreakdownBars breakdown={moat_breakdown} overallScore={moat_score} />
                )}
                {signal_breakdown && (
                  <SignalDivergenceSection
                    breakdown={signal_breakdown}
                    recentNews={[]}
                    nextEarningsDate={undefined}
                  />
                )}
                <TierGate feature="institutional_risk" userTier={userTier} isAdmin={isAdmin}>
                  {signal_breakdown && (
                    <InstitutionalRiskDashboard breakdown={signal_breakdown} />
                  )}
                </TierGate>
                {(strengths.length > 0 || concerns.length > 0 || whatsNewItems.length > 0) && (
                  <>
                    <KeyTakeaways strengths={strengths} concerns={concerns} />
                    <RecentDevelopments
                      recentItems={whatsNewItems}
                      upcomingEvents={watchCalendarEvents}
                    />
                  </>
                )}
              </div>
            </CollapsibleSection>
          </div>
        )}

        {/* ══════════════════════════════════════════════════════════════
            ANALYST THESIS (Advisor mode only)
            ══════════════════════════════════════════════════════════════ */}
        {showAnalystThesis && (
          <CollapsibleSection
            key={`analyst-${reportMode}`}
            title="Analyst Thesis"
            sublabel="Investment thesis · Valuation context · Entry strategy"
            defaultOpen={false}
          >
            <TierGate feature="analyst_verdict" userTier={userTier} isAdmin={isAdmin}>
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
            </TierGate>
          </CollapsibleSection>
        )}

        {/* ══════════════════════════════════════════════════════════════
            EXECUTION LAYER (Trader — always at bottom when entitled)
            ══════════════════════════════════════════════════════════════ */}
        <div className={`space-y-6 transition-opacity duration-200${isReadingMode ? ' opacity-30 pointer-events-none' : ''}`}>
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
