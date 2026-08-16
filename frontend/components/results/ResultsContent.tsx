'use client'

import { useEffect, useState } from 'react'
import Link from 'next/link'
import { ChevronDown, ChevronUp } from 'lucide-react'
import { useAnalysis } from '@/lib/hooks/useAnalysis'
import { useCurrentUser } from '@/lib/hooks/useCurrentUser'
import { useEntitlements } from '@/lib/hooks/useEntitlements'
import { LoadingSpinner } from '@/components/shared/LoadingSpinner'
import { OwnershipStatusHeader } from '@/components/results/OwnershipStatusHeader'
import { usePortfolioPosition } from '@/lib/hooks/usePortfolio'
import { GrowthQualityClassification } from '@/components/results/GrowthQualityClassification'
import { PMSnapshotCard } from '@/components/results/PMSnapshotCard'
import { VerdictHeader } from '@/components/results/VerdictHeader'
import { DivergenceIntelligencePanel } from '@/components/results/DivergenceIntelligencePanel'
import { DeploymentDriversPanel } from '@/components/results/DeploymentDriversPanel'
import { ScoreBreakdownBars } from '@/components/results/ScoreBreakdownBars'
import { ThesisDriversPanel } from '@/components/results/ThesisDriversPanel'
import { InvestmentThesisPanel } from '@/components/results/InvestmentThesisPanel'
import { StrategicCatalystsPanel } from '@/components/results/StrategicCatalystsPanel'
import { DislocationStatePanel } from '@/components/results/DislocationStatePanel'
import { FairValueRegimeCheck } from '@/components/results/FairValueRegimeCheck'
import { PriceTargetsCard } from '@/components/results/PriceTargetsCard'
import { PortfolioRolePanel } from '@/components/results/PortfolioRolePanel'
import { CompressedRiskPanel } from '@/components/results/CompressedRiskPanel'
import { WatchForSummary } from '@/components/results/WatchForSummary'
import { ProbabilisticEngineDashboard } from '@/components/results/ProbabilisticEngineDashboard'
import { ExecutionLayer } from '@/components/results/ExecutionLayer'
import { ReportCommandBar } from '@/components/results/ReportCommandBar'
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

  // Must be called unconditionally before any early returns (Rules of Hooks)
  const _tickerForHook = run?.results?.[0]?.ticker ?? ''
  const { position: portfolioPosition } = usePortfolioPosition(_tickerForHook)

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

  // Extract dislocation data from quant output
  const quant = full_output?.quant_output || {}
  const ti = quant?.technical_indicators || {}
  const ma = ti?.moving_averages || {}
  const high52Week = ti?.high_52_week || ma?.high_252d || null
  const ma200d = ma?.sma_200 || ti?.sma_200 || null
  const currentPrice = decision_intelligence?.current_price || ma?.current_price || null

  // Extract thesis break conditions from tranche plan
  const tranchePlan = decision_intelligence?.tranche_plan
  const thesisBreakConditions = tranchePlan?.thesis_break_conditions || null

  // Extract initiation status (used only for no-portfolio fallback in header)
  const initiationDecision = decision_intelligence?.initiation_decision
  const initiationStatus = initiationDecision?.status || null

  // Sector from fundamentalist
  const sector = full_output?.fundamentalist_output?.sector || null

  // Extract divergence overlay and fundamentalist output for Growth Quality & Divergence sections
  const divergenceOverlay = decision_intelligence?.divergence_overlay || null
  const fundamentalistOutput = full_output?.fundamentalist_output || null
  const qualityScore = full_output?.price_targets?.valuation_metadata?.quality_score || null
  const dvrgMode = divergenceOverlay?.dvrg_mode || null

  return (
    <OnboardingPanel>

      {/* ══ STICKY COMMAND BAR ══════════════════════════════════════════════ */}
      <ReportCommandBar
        ticker={result.ticker}
        price={currentPrice}
        timestamp={run.completed_at || run.created_at}
        runId={run.id}
        companyName={full_output?.fundamentalist_output?.company_name}
        isReadingMode={isReadingMode}
        onToggleReadingMode={() => setReadingMode(r => !r)}
        dvrgMode={dvrgMode}
      />

      <div className="container mx-auto px-4 pt-4 pb-8">
        <div className="max-w-6xl mx-auto space-y-3">

            {/* ══════════════════════════════════════════════════════════════════
              VERDICT — The headline call.
              Reconciled rating · one-line summary · key insights · synthesis.
              ══════════════════════════════════════════════════════════════════ */}
          <VerdictHeader
            rating={full_output?.rating || decision_intelligence?.rating}
            moatScore={moat_score}
            summary={full_output?.investment_thesis?.recommendation_summary}
            keyInsights={full_output?.key_insights}
            synthesisNarrative={full_output?.synthesis_narrative}
          />

            {/* ══════════════════════════════════════════════════════════════════
              PM SNAPSHOT — Persistent top-of-report block
              Answers 7 key questions in under 15 seconds.
              Capital Alignment Matrix · Synthesis · Capital Environment
              ══════════════════════════════════════════════════════════════════ */}
          <PMSnapshotCard
            moatScore={moat_score}
            priceTargets={full_output?.price_targets ?? null}
            currentPrice={currentPrice}
            divergenceOverlay={divergenceOverlay}
            fairValueCalibration={full_output?.fair_value_calibration ?? null}
            initiationStatus={initiationStatus}
            signalBreakdown={signal_breakdown}
          />

          {/* ══════════════════════════════════════════════════════════════════
              HEADER — OWNERSHIP STATUS
              Always visible. Ownership status · Thesis state · Action now ·
              Portfolio context.
              ══════════════════════════════════════════════════════════════════ */}
          <OwnershipStatusHeader
            ticker={result.ticker}
            initiationStatus={initiationStatus}
            currentPrice={currentPrice}
            high52Week={high52Week}
          />

          {/* ══════════════════════════════════════════════════════════════════
              SECTION I — CONSERVATIVE VALUATION LENS  (moved up — Risk/Reward first)
              Intrinsic anchor · Scenario risk/reward · EV
              Valuation informs trim sensitivity and risk assessment.
              It does NOT block adds.
              ══════════════════════════════════════════════════════════════════ */}
          {(full_output?.fair_value_calibration || full_output?.price_targets) && (
            <CollapsibleSection
              title="Valuation & Risk / Reward"
              sublabel="Downside · Upside · Intrinsic anchor · Scenarios · EV — does NOT block adds"
            >
              <div className="space-y-4">
                {/* Disclaimer — valuation is risk framing, never an entry gate */}
                <div className="flex items-start gap-2 rounded-lg border border-border/40 bg-surface-elevated/30 px-3 py-2 text-[10px] text-text-tertiary">
                  <span className="font-semibold uppercase tracking-wider">Note:</span>
                  <span>
                    Conservative valuation is used as risk framing and trim sensitivity only.
                    It does <span className="font-semibold text-text-secondary">not</span> block initiations or tier adds —
                    those are governed by CompounderScore, drawdown state, and portfolio slot.
                  </span>
                </div>

                {full_output?.fair_value_calibration && (
                  <FairValueRegimeCheck
                    calibration={full_output.fair_value_calibration}
                    currentPrice={currentPrice}
                    financialHealthScore={moat_breakdown?.financial_health}
                    idealEntryZone={decision_intelligence?.recommended_strategy?.entry?.ideal_zone}
                  />
                )}
                {currentPrice && full_output?.price_targets && (
                  <PriceTargetsCard
                    priceTargets={full_output.price_targets}
                    currentPrice={currentPrice}
                    ticker={result.ticker}
                    signalBreakdown={signal_breakdown}
                  />
                )}

                {/* Deployment drivers waterfall — if divergence overlay exists */}
                {divergenceOverlay && (
                  <DeploymentDriversPanel
                    drivers={divergenceOverlay.deployment_drivers}
                    finalAllocation={divergenceOverlay.final_allocation}
                    addIntensityModifier={divergenceOverlay.add_intensity_modifier}
                  />
                )}
              </div>
            </CollapsibleSection>
          )}

          {/* ══════════════════════════════════════════════════════════════════
              SECTION II — DIVERGENCE INTELLIGENCE  (Divergence & Allocation)
              Timing score · Phase · Sub-metrics · Allocation adjustment
              ══════════════════════════════════════════════════════════════════ */}
          {divergenceOverlay && (
            <DivergenceIntelligencePanel overlay={divergenceOverlay} />
          )}

          {/* ══════════════════════════════════════════════════════════════════
              SECTION III — COMPANY CLASSIFICATION
              Durable Growth / Durable Quality / Emerging Compounder
              ══════════════════════════════════════════════════════════════════ */}
          {(moat_breakdown || fundamentalistOutput) && (
            <GrowthQualityClassification
              moatBreakdown={moat_breakdown}
              fundamentalistOutput={fundamentalistOutput}
              qualityScore={qualityScore}
              moatScore={moat_score}
            />
          )}

          {/* ══════════════════════════════════════════════════════════════════
              SECTION IV — INVESTMENT THESIS  (collapsed by default)
              Company overview · Highlights · Key risks · Entry context
              ══════════════════════════════════════════════════════════════════ */}
          {full_output?.investment_thesis && (
            <CollapsibleSection
              title="Investment Thesis"
              sublabel="Company overview · Highlights · Key risks · Entry context"
            >
              <InvestmentThesisPanel thesis={full_output.investment_thesis} />
            </CollapsibleSection>
          )}

          {/* ══════════════════════════════════════════════════════════════════
              SECTION IV.b — CATALYSTS & GROWTH VECTORS  (collapsed by default)
              Upcoming dated events · Forward-looking strategic catalysts
              ══════════════════════════════════════════════════════════════════ */}
          {((full_output?.strategic_catalysts?.length ?? 0) > 0 ||
            (full_output?.news_hound_output?.upcoming_catalysts?.catalysts?.length ?? 0) > 0) && (
            <CollapsibleSection
              title="Catalysts & Growth Vectors"
              sublabel="Upcoming events · Forward-looking strategic catalysts"
              badge={
                (full_output?.strategic_catalysts?.length ?? 0) > 0
                  ? `${full_output.strategic_catalysts!.length} identified`
                  : undefined
              }
            >
              <StrategicCatalystsPanel
                catalysts={full_output?.strategic_catalysts}
                upcoming={full_output?.news_hound_output?.upcoming_catalysts}
              />
            </CollapsibleSection>
          )}

          {/* ══════════════════════════════════════════════════════════════════
              SECTION V — STRUCTURAL DURABILITY  (collapsed)
              Moat · Earnings durability · Financial health · Quality score
              ══════════════════════════════════════════════════════════════════ */}
          {moat_breakdown && moat_score !== null && (
            <CollapsibleSection
              title="Structural Durability"
              sublabel="Moat · Earnings durability · Financial health · Quality score"
            >
              <TierGate feature="structural_quality_full" userTier={userTier} isAdmin={isAdmin}>
                <ScoreBreakdownBars breakdown={moat_breakdown} overallScore={moat_score} />
              </TierGate>
            </CollapsibleSection>
          )}

          {/* ══════════════════════════════════════════════════════════════════
              SECTION VI — STRUCTURAL THESIS  (collapsed)
              Structural drivers · Break conditions (threshold-based)
              ══════════════════════════════════════════════════════════════════ */}
          {(upgrade_triggers || downgrade_triggers || thesisBreakConditions) && (
            <CollapsibleSection
              title="Structural Thesis"
              sublabel="Structural drivers · Break conditions"
            >
              <ThesisDriversPanel
                upgradeTriggers={upgrade_triggers}
                downgradeTriggers={downgrade_triggers}
                thesisBreakConditions={thesisBreakConditions}
              />
            </CollapsibleSection>
          )}

          {/* ══════════════════════════════════════════════════════════════════
              SECTION VII — DISLOCATION STATE
              52-week high · Drawdown % · Tier bands · Capacity remaining
              ══════════════════════════════════════════════════════════════════ */}
          {(high52Week || currentPrice) && (
            <CollapsibleSection
              title="Dislocation State"
              sublabel="252d rolling high · Drawdown % · Tier bands (+2/+4/+6/+8)"
            >
              <DislocationStatePanel
                currentPrice={currentPrice}
                high52Week={high52Week}
                ma200d={ma200d}
                position={portfolioPosition}
              />
            </CollapsibleSection>
          )}

          {/* ══════════════════════════════════════════════════════════════════
              SECTION V — PORTFOLIO ROLE
              Weight · Top 3 exposure · Sector · Role tag
              ══════════════════════════════════════════════════════════════════ */}
          <CollapsibleSection
            title="Portfolio Role"
            sublabel="Weight · Exposure · Sector · Role tag"
          >
            <PortfolioRolePanel ticker={result.ticker} sector={sector} />
          </CollapsibleSection>

          {/* ══════════════════════════════════════════════════════════════════
              SECTION VI — MONITORING DASHBOARD
              Key risks · Thesis flags · Probabilistic diagnostics
              ══════════════════════════════════════════════════════════════════ */}
          {((risk_factors?.length ?? 0) > 0 ||
            (downgrade_triggers?.length ?? 0) > 0 ||
            !!signal_breakdown) && (
            <CollapsibleSection
              title="Monitoring Dashboard"
              sublabel="Key risks · Thesis flags · Probabilistic diagnostics · Next catalyst"
            >
              <div className="space-y-4">
                {/* Compressed risk bullets */}
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
                sector={sector || 'Unknown'}
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
