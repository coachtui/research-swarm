import { Card, CardContent } from '@/components/ui/card'
import type { InvestmentThesisStructured, SignalBreakdown, TriggerItem, FairValueCalibration } from '@/types/api'
import { MarketRegimeOverlay } from './MarketRegimeOverlay'

interface AnalystVerdictProps {
  thesis: InvestmentThesisStructured | string
  upgradeTriggers?: TriggerItem[] | null
  downgradeTriggers?: TriggerItem[] | null
  signalBreakdown?: SignalBreakdown | null
  valuationScore?: number | null
  calibration?: FairValueCalibration | null
  currentPrice?: number
  financialHealthScore?: number
}

function detectStructuralPremium(
  calibration: FairValueCalibration | null | undefined,
  currentPrice: number | undefined,
  financialHealthScore: number | undefined
): boolean {
  if (!calibration || !currentPrice || financialHealthScore == null) return false
  const fv = calibration.internal_fair_value
  if (!fv || fv <= 0) return false
  return (currentPrice - fv) / fv > 0.5 && calibration.regime === 'Growth' && financialHealthScore > 7.0
}

/** Heuristic confidence score (0–100) derived from existing backend signal fields. */
function computeModelConfidence(breakdown: SignalBreakdown): number {
  const strength = (breakdown.signal_strength ?? 5) / 10           // 0–1
  const stability = (breakdown.signal_stability ?? 5) / 10         // 0–1
  const integrity = (breakdown.data_integrity_pct ?? 50) / 100     // 0–1
  const spread = breakdown.signal_spread ?? 5
  const inverseDivergence = Math.max(0, 10 - spread) / 10          // 0–1; high spread = low confidence

  const raw =
    strength * 30 +
    stability * 30 +
    integrity * 20 +
    inverseDivergence * 20

  return Math.round(Math.min(100, Math.max(0, raw)))
}

function ConfidencePill({ pct }: { pct: number }) {
  const color =
    pct >= 70
      ? 'text-success bg-success/10 border-success/20'
      : pct >= 50
      ? 'text-yellow-400 bg-yellow-500/10 border-yellow-500/20'
      : 'text-warning bg-warning/10 border-warning/20'

  return (
    <span
      className={`inline-flex items-center gap-1.5 text-xs font-medium px-2.5 py-1 rounded border ${color}`}
      title="Heuristic score derived from signal strength, stability, data completeness, and divergence magnitude. Not backtested."
    >
      Model Confidence: {pct}%
    </span>
  )
}

export function AnalystVerdict({ thesis, upgradeTriggers, downgradeTriggers, signalBreakdown, valuationScore, calibration, currentPrice, financialHealthScore }: AnalystVerdictProps) {
  const hasStructuredThesis = typeof thesis !== 'string'
  const hasTriggers = (upgradeTriggers?.length ?? 0) > 0 || (downgradeTriggers?.length ?? 0) > 0
  const confidence = signalBreakdown ? computeModelConfidence(signalBreakdown) : null
  const isStructuralPremium = detectStructuralPremium(calibration, currentPrice, financialHealthScore)
  const showValuationReframe = isStructuralPremium && valuationScore != null && valuationScore < 5.0

  return (
    <Card className="border border-border-subtle shadow-sm">
      <CardContent className="pt-6 space-y-6">

        {/* Market Regime Overlay — contextual framing only */}
        {signalBreakdown && (
          <MarketRegimeOverlay breakdown={signalBreakdown} />
        )}

        {/* Header row: title + model confidence */}
        <div className="flex items-center justify-between gap-4 flex-wrap">
          <h2 className="text-2xl font-bold text-text-primary tracking-tight">Analyst Verdict</h2>
          {confidence !== null && <ConfidencePill pct={confidence} />}
        </div>

        {hasStructuredThesis ? (
          <div className="space-y-6">
            {/* Company Overview */}
            <div>
              <h3 className="text-xs font-semibold text-text-tertiary uppercase tracking-widest mb-2">
                Company Overview
              </h3>
              <p className="text-text-secondary text-sm leading-relaxed">
                {(thesis as InvestmentThesisStructured).company_overview}
              </p>
            </div>

            {/* Recommendation summary — highlighted */}
            <div className="bg-surface-elevated rounded-lg p-4 border-l-4 border-primary">
              <p className="text-text-primary font-medium text-sm leading-relaxed">
                {(thesis as InvestmentThesisStructured).recommendation_summary}
              </p>
            </div>

            {/* Investment Highlights */}
            <div>
              <h3 className="text-xs font-semibold text-text-tertiary uppercase tracking-widest mb-2.5">
                Investment Highlights
              </h3>
              <ul className="space-y-2.5">
                {(thesis as InvestmentThesisStructured).investment_highlights.map((item, idx) => (
                  <li key={idx} className="flex items-start gap-2.5 text-sm text-text-secondary">
                    <span className="text-success mt-1 flex-shrink-0 font-bold">·</span>
                    <span className="leading-relaxed">{item}</span>
                  </li>
                ))}
              </ul>
            </div>

            {/* Valuation & Signal Analysis */}
            <div>
              <h3 className="text-xs font-semibold text-text-tertiary uppercase tracking-widest mb-2">
                Valuation &amp; Signal Analysis
              </h3>
              <p className="text-text-secondary text-sm leading-relaxed">
                {(thesis as InvestmentThesisStructured).valuation_signal_analysis}
              </p>
              {/* Fix 6: Reframe low valuation score for Structural Premium Regime stocks */}
              {showValuationReframe && (
                <div className="mt-3 rounded-md p-3 bg-primary/5 border border-primary/15 text-xs text-text-tertiary leading-relaxed">
                  <span className="font-medium text-text-secondary">Valuation Context: </span>
                  A valuation score of {valuationScore!.toFixed(1)} reflects a stock priced for continued
                  exceptional execution — not a signal that the stock should trade lower imminently.
                  The margin of safety is narrow and the cost of disappointment is elevated, but this
                  is characteristic of high-quality businesses operating in a sustained growth regime.
                  The structural anchor, not the valuation score, defines the mean-reversion risk.
                </div>
              )}
            </div>

            {/* Key Risks */}
            <div>
              <h3 className="text-xs font-semibold text-text-tertiary uppercase tracking-widest mb-2.5">
                Key Risks
              </h3>
              <ul className="space-y-2.5">
                {(thesis as InvestmentThesisStructured).key_risks.map((item, idx) => (
                  <li key={idx} className="flex items-start gap-2.5 text-sm text-text-secondary">
                    <span className="text-error mt-1 flex-shrink-0 font-bold">·</span>
                    <span className="leading-relaxed">{item}</span>
                  </li>
                ))}
              </ul>
            </div>

            {/* Entry Strategy & Investor Fit */}
            <div>
              <h3 className="text-xs font-semibold text-text-tertiary uppercase tracking-widest mb-2">
                Entry Strategy &amp; Investor Fit
              </h3>
              <p className="text-text-secondary text-sm leading-relaxed">
                {(thesis as InvestmentThesisStructured).entry_strategy}
              </p>
            </div>
          </div>
        ) : (
          <p className="text-text-secondary text-sm leading-relaxed whitespace-pre-wrap">
            {thesis as string}
          </p>
        )}

        {/* What changes the rating */}
        {hasTriggers && (
          <div className="border-t border-border pt-6 space-y-4">
            <h3 className="text-xs font-semibold text-text-tertiary uppercase tracking-widest">
              What Changes This Rating
            </h3>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {upgradeTriggers && upgradeTriggers.length > 0 && (
                <div className="rounded-lg border border-success/25 bg-success/5 p-4">
                  <p className="text-xs font-semibold text-success mb-3 flex items-center gap-1.5">
                    <span>↗</span> Upgrade to BUY if...
                  </p>
                  <ul className="space-y-2">
                    {upgradeTriggers.slice(0, 5).map((t, i) => (
                      <li key={i} className="text-xs text-text-secondary leading-relaxed">
                        <span className="font-medium text-text-primary">{t.metric}:</span>{' '}
                        {t.threshold}
                      </li>
                    ))}
                  </ul>
                </div>
              )}
              {downgradeTriggers && downgradeTriggers.length > 0 && (
                <div className="rounded-lg border border-error/25 bg-error/5 p-4">
                  <p className="text-xs font-semibold text-error mb-3 flex items-center gap-1.5">
                    <span>↘</span> Downgrade to SELL if...
                  </p>
                  <ul className="space-y-2">
                    {downgradeTriggers.slice(0, 5).map((t, i) => (
                      <li key={i} className="text-xs text-text-secondary leading-relaxed">
                        <span className="font-medium text-text-primary">{t.metric}:</span>{' '}
                        {t.threshold}
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  )
}
