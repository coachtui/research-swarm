'use client'

import { useState } from 'react'
import { ChevronDown, ChevronUp } from 'lucide-react'
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

/** Returns score-appropriate valuation context text and visual variant. */
function getValuationContext(score: number): { text: string; variant: 'warning' | 'default' | 'success' } {
  if (score < 3.0) {
    return {
      text: `Valuation score of ${score.toFixed(1)} signals extreme premium pricing. The market is embedding near-zero execution risk and sustained above-consensus growth into the current multiple. Any deceleration in revenue growth, margin compression, or guidance reduction could trigger rapid multiple compression — this is the highest-risk valuation configuration.`,
      variant: 'warning',
    }
  }
  if (score < 5.0) {
    return {
      text: `Valuation score of ${score.toFixed(1)} reflects a stock priced for continued strong execution — not a signal that the stock should trade lower imminently. The margin of safety is narrow and the cost of disappointment is elevated. The structural anchor, not the valuation score, defines mean-reversion risk.`,
      variant: 'default',
    }
  }
  if (score < 7.0) {
    return {
      text: `Valuation score of ${score.toFixed(1)} reflects approximate fair value pricing. Risk/reward is roughly symmetric from current levels — upside requires fundamental outperformance while downside is limited by valuation support.`,
      variant: 'default',
    }
  }
  return {
    text: `Valuation score of ${score.toFixed(1)} signals a meaningful discount to intrinsic value. The margin of safety is intact — downside is bounded by fundamental floor while upside reflects re-rating potential as the discount closes.`,
    variant: 'success',
  }
}

/** Heuristic confidence score (0–100) derived from existing backend signal fields. */
function computeModelConfidence(breakdown: SignalBreakdown): number {
  const strength = (breakdown.signal_strength ?? 5) / 10
  const stability = (breakdown.signal_stability ?? 5) / 10
  const integrity = (breakdown.data_integrity_pct ?? 50) / 100
  const spread = breakdown.signal_spread ?? 5
  const inverseDivergence = Math.max(0, 10 - spread) / 10

  const raw =
    strength * 30 +
    stability * 30 +
    integrity * 20 +
    inverseDivergence * 20

  return Math.round(Math.min(100, Math.max(0, raw)))
}

const CONFIDENCE_TYPICAL_LOW = 55
const CONFIDENCE_TYPICAL_HIGH = 85

function ConfidencePill({ pct }: { pct: number }) {
  const label =
    pct >= 72 ? 'Moderate–High' :
    pct >= 58 ? 'Moderate' :
    pct >= 45 ? 'Low–Moderate' :
    'Low'

  const color =
    pct >= 70
      ? 'text-success bg-success/10 border-success/20'
      : pct >= 50
      ? 'text-yellow-400 bg-yellow-500/10 border-yellow-500/20'
      : 'text-warning bg-warning/10 border-warning/20'

  const barColor =
    pct >= 70 ? 'bg-success' :
    pct >= 50 ? 'bg-yellow-400' :
    'bg-warning'

  const markerPos = Math.min(100, Math.max(0,
    ((pct - CONFIDENCE_TYPICAL_LOW) / (CONFIDENCE_TYPICAL_HIGH - CONFIDENCE_TYPICAL_LOW)) * 100
  ))

  return (
    <div
      className={`inline-flex flex-col gap-1 text-xs font-medium px-2.5 py-1.5 rounded border ${color}`}
      title="Heuristic score derived from signal strength, stability, data completeness, and divergence magnitude. Typical operational range: 55–85%. Not backtested."
    >
      <div className="flex items-center gap-1.5">
        <span>Model Confidence: {pct}%</span>
        <span className="text-[10px] opacity-70">({label})</span>
      </div>
      <div className="flex items-center gap-1.5">
        <span className="text-[9px] opacity-50 shrink-0">55</span>
        <div className="relative flex-1 h-1 bg-current/10 rounded-full overflow-hidden">
          <div
            className={`absolute h-full w-1 ${barColor} rounded-full`}
            style={{ left: `calc(${markerPos}% - 2px)` }}
          />
        </div>
        <span className="text-[9px] opacity-50 shrink-0">85</span>
      </div>
    </div>
  )
}

export function AnalystVerdict({
  thesis,
  upgradeTriggers,
  downgradeTriggers,
  signalBreakdown,
  valuationScore,
  calibration,
  currentPrice,
  financialHealthScore,
}: AnalystVerdictProps) {
  const [showFull, setShowFull] = useState(false)

  const hasStructuredThesis = typeof thesis !== 'string'
  const hasTriggers = (upgradeTriggers?.length ?? 0) > 0 || (downgradeTriggers?.length ?? 0) > 0
  const confidence = signalBreakdown ? computeModelConfidence(signalBreakdown) : null
  const valuationContext = valuationScore != null ? getValuationContext(valuationScore) : null

  // BLUF: recommendation_summary as the always-visible lead paragraph.
  // For unstructured thesis, use the first 2 sentences.
  const blufText = (() => {
    if (!thesis) return null
    if (hasStructuredThesis) {
      return (thesis as InvestmentThesisStructured).recommendation_summary ?? null
    }
    const sentences = (thesis as string).split(/\.\s+/)
    return sentences.slice(0, 2).join('. ') + (sentences.length > 1 ? '.' : '')
  })()

  return (
    <Card className="border border-border-subtle shadow-sm">
      <CardContent className="pt-6 space-y-5">

        {/* Market Regime Overlay — context framing */}
        {signalBreakdown && (
          <MarketRegimeOverlay breakdown={signalBreakdown} />
        )}

        {/* Header row: title + model confidence */}
        <div className="flex items-center justify-between gap-4 flex-wrap">
          <h2 className="text-2xl font-bold text-text-primary tracking-tight">Analyst Verdict</h2>
          {confidence !== null && <ConfidencePill pct={confidence} />}
        </div>

        {/* ── BLUF — Bottom Line Up Front ──────────────────────────────
            Always visible. Summarizes: what to do, why, what matters most.
            Structured per sell-side memo convention (JP Morgan / GS style). */}
        {blufText && (
          <div className="border-l-[3px] border-primary pl-4 py-0.5 space-y-0.5">
            <p className="text-[10px] uppercase tracking-widest font-bold text-primary">BLUF</p>
            <p className="text-[15px] font-semibold text-text-primary leading-relaxed">{blufText}</p>
          </div>
        )}

        {/* ── Expand/collapse toggle ────────────────────────────────── */}
        {hasStructuredThesis && (
          <button
            onClick={() => setShowFull(!showFull)}
            className="flex items-center gap-1.5 text-xs text-text-tertiary hover:text-text-secondary transition-colors group"
          >
            {showFull
              ? <><ChevronUp className="h-3.5 w-3.5" /> Collapse analysis</>
              : <><ChevronDown className="h-3.5 w-3.5" /> Full analysis — highlights, valuation context, risks, entry strategy</>
            }
          </button>
        )}

        {/* ── Full structured narrative (collapsible) ──────────────── */}
        {hasStructuredThesis && showFull && (
          <div className="space-y-8 pt-1 border-t border-border/50">

            {/* Company Overview */}
            <div>
              <h3 className="label mb-2">Company Overview</h3>
              <p className="text-text-secondary leading-relaxed" style={{ fontSize: 'var(--text-base)' }}>
                {(thesis as InvestmentThesisStructured).company_overview}
              </p>
            </div>

            {/* Investment Highlights */}
            <div>
              <h3 className="label mb-2.5">Investment Highlights</h3>
              <ul className="space-y-2.5">
                {(thesis as InvestmentThesisStructured).investment_highlights.map((item, idx) => (
                  <li key={idx} className="flex items-start gap-2.5 text-text-secondary" style={{ fontSize: 'var(--text-base)' }}>
                    <span className="text-success mt-1 flex-shrink-0 font-bold">·</span>
                    <span className="leading-relaxed">{item}</span>
                  </li>
                ))}
              </ul>
            </div>

            {/* Valuation & Signal Analysis */}
            <div>
              <h3 className="label mb-2">Valuation &amp; Signal Analysis</h3>
              <p className="text-text-secondary leading-relaxed" style={{ fontSize: 'var(--text-base)' }}>
                {(thesis as InvestmentThesisStructured).valuation_signal_analysis}
              </p>
              {valuationContext && (
                <div className={`mt-3 rounded-md p-3 text-xs text-text-tertiary leading-relaxed border ${
                  valuationContext.variant === 'warning'
                    ? 'bg-error/5 border-error/20'
                    : valuationContext.variant === 'success'
                    ? 'bg-success/5 border-success/20'
                    : 'bg-primary/5 border-primary/15'
                }`}>
                  <span className="font-medium text-text-secondary">Valuation Context: </span>
                  {valuationContext.text}
                </div>
              )}
            </div>

            {/* Key Risks */}
            <div className="pt-2" style={{ borderTop: '1px solid var(--border)' }}>
              <h3 className="label mb-2.5">Key Risks</h3>
              <ul className="space-y-2.5">
                {(thesis as InvestmentThesisStructured).key_risks.map((item, idx) => (
                  <li key={idx} className="flex items-start gap-2.5 text-text-secondary" style={{ fontSize: 'var(--text-base)' }}>
                    <span className="text-error mt-1 flex-shrink-0 font-bold">·</span>
                    <span className="leading-relaxed">{item}</span>
                  </li>
                ))}
              </ul>
            </div>

            {/* Entry Strategy & Investor Fit */}
            <div>
              <h3 className="label mb-2">Entry Strategy &amp; Investor Fit</h3>
              <p className="text-text-secondary leading-relaxed" style={{ fontSize: 'var(--text-base)' }}>
                {(thesis as InvestmentThesisStructured).entry_strategy}
              </p>
            </div>
          </div>
        )}

        {/* Unstructured thesis fallback — show full text always */}
        {!hasStructuredThesis && (
          <p className="text-text-secondary leading-relaxed whitespace-pre-wrap" style={{ fontSize: 'var(--text-base)' }}>
            {thesis as string}
          </p>
        )}

        {/* What changes the rating */}
        {hasTriggers && (
          <div className="border-t border-border pt-5 space-y-4">
            <h3 className="label">What Changes This Rating</h3>
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
