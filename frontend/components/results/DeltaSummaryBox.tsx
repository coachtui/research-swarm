'use client'

import type { PreviousAnalysisDelta, EVAttributionDriver, StopProbDriftDecomposition } from '@/types/api'

interface DeltaSummaryBoxProps {
  delta: PreviousAnalysisDelta
  ticker: string
}

function ratingColor(rating: string): string {
  if (rating.includes('BUY')) return 'text-success'
  if (rating === 'HOLD') return 'text-warning'
  return 'text-error'
}

function thesisDirectionStyle(direction: string): { label: string; color: string; icon: string } {
  switch (direction) {
    case 'strengthened': return { label: 'Strengthened', color: 'text-success', icon: '↑' }
    case 'weakened':     return { label: 'Weakened',     color: 'text-warning', icon: '↓' }
    case 'reversed':     return { label: 'Reversed',     color: 'text-error',   icon: '⟳' }
    default:             return { label: 'Held',         color: 'text-text-secondary', icon: '→' }
  }
}

function priceDeltaColor(pct: number | null): string {
  if (pct === null) return 'text-text-secondary'
  if (pct > 3) return 'text-success'
  if (pct < -3) return 'text-error'
  return 'text-text-secondary'
}

function scoreDeltaColor(delta: number | null): string {
  if (delta === null) return 'text-text-secondary'
  if (delta > 0.3) return 'text-success'
  if (delta < -0.3) return 'text-error'
  return 'text-text-secondary'
}

/** Arrow + color for a metric where higher is WORSE (stop prob, noise, instability) */
function riskDeltaDisplay(prior: number | null | undefined, current: number | null | undefined, unit = '%') {
  if (prior == null || current == null) return { arrow: '–', color: 'text-text-tertiary', label: 'N/A' }
  const d = current - prior
  if (Math.abs(d) < 0.5) return { arrow: '→', color: 'text-text-secondary', label: `${d > 0 ? '+' : ''}${d.toFixed(1)}${unit}` }
  if (d > 0) return { arrow: '↑', color: 'text-error', label: `+${d.toFixed(1)}${unit}` }
  return { arrow: '↓', color: 'text-success', label: `${d.toFixed(1)}${unit}` }
}

/** Arrow + color for a metric where higher is BETTER (confidence) */
function qualityDeltaDisplay(prior: number | null | undefined, current: number | null | undefined, unit = '') {
  if (prior == null || current == null) return { arrow: '–', color: 'text-text-tertiary', label: 'N/A' }
  const d = current - prior
  if (Math.abs(d) < 0.5) return { arrow: '→', color: 'text-text-secondary', label: `${d > 0 ? '+' : ''}${d.toFixed(1)}${unit}` }
  if (d > 0) return { arrow: '↑', color: 'text-success', label: `+${d.toFixed(1)}${unit}` }
  return { arrow: '↓', color: 'text-warning', label: `${d.toFixed(1)}${unit}` }
}

function driftLevelColor(level: string | null | undefined): string {
  if (level === 'Significant') return 'text-error'
  if (level === 'Moderate') return 'text-warning'
  if (level === 'Modest') return 'text-amber-400'
  return 'text-success'
}

function driftLevelBg(level: string | null | undefined): string {
  if (level === 'Significant') return 'bg-error/10 border-error/30'
  if (level === 'Moderate') return 'bg-warning/10 border-warning/30'
  if (level === 'Modest') return 'bg-amber-400/10 border-amber-400/30'
  return 'bg-success/10 border-success/30'
}

function attributionDriverColor(dir: string): string {
  if (dir === 'bearish') return 'text-error'
  if (dir === 'bullish') return 'text-success'
  return 'text-text-secondary'
}

function componentDeltaColor(delta: number): string {
  if (delta > 1) return 'text-error'
  if (delta < -1) return 'text-success'
  return 'text-text-secondary'
}

// ── MODEL DRIFT SUMMARY sub-section ─────────────────────────────────────────

function ModelDriftSummary({ delta }: { delta: PreviousAnalysisDelta }) {
  const {
    prior_stop_probability_pct,
    current_stop_probability_pct,
    prior_confidence_pct,
    current_confidence_pct,
    prior_stability_score,
    current_stability_score,
    prior_stability_class,
    current_stability_class,
    prior_scenario_weights,
    current_scenario_weights,
    model_drift_level,
    scenario_rotation_label,
    ev_attribution,
    stop_prob_drift_decomposition,
  } = delta

  // Only render if we have at least some probabilistic data
  const hasProbData = prior_stop_probability_pct != null || prior_confidence_pct != null || prior_stability_score != null

  if (!hasProbData) return null

  const stopDelta   = riskDeltaDisplay(prior_stop_probability_pct, current_stop_probability_pct)
  const confDelta   = qualityDeltaDisplay(prior_confidence_pct, current_confidence_pct)
  // For instability score: lower is better, so treat like risk (higher = worse)
  const stabDelta   = riskDeltaDisplay(prior_stability_score, current_stability_score, '')

  const stabilityClassChanged = prior_stability_class && current_stability_class && prior_stability_class !== current_stability_class

  // Interpretive regime note
  let driftInterpretation = ''
  if (model_drift_level === 'Significant') {
    driftInterpretation = 'Substantial model state change detected. Treat current output as a materially different setup from the prior run.'
  } else if (model_drift_level === 'Moderate') {
    driftInterpretation = 'Meaningful model drift observed. Output reflects updated regime conditions — review key changes before acting.'
  } else if (model_drift_level === 'Modest') {
    driftInterpretation = 'Minor model evolution detected. Inputs shifted incrementally — core thesis unchanged but risk parameters updated.'
  } else {
    driftInterpretation = 'Model state is stable. Output variation within normal recalculation tolerance — thesis continuity maintained.'
  }

  return (
    <div className="space-y-3">
      {/* MODEL DRIFT SUMMARY header */}
      <div className="flex items-center justify-between gap-2 flex-wrap">
        <p className="text-[10px] font-bold text-text-secondary uppercase tracking-wide">Model Drift Summary</p>
        {model_drift_level && (
          <span className={`text-[10px] font-bold uppercase tracking-wide px-2 py-0.5 rounded border ${driftLevelBg(model_drift_level)} ${driftLevelColor(model_drift_level)}`}>
            {model_drift_level} Drift
          </span>
        )}
      </div>

      {/* 3-metric drift grid */}
      <div className="grid grid-cols-3 gap-2">
        <div className="rounded-md bg-surface/60 border border-border p-2">
          <p className="text-[9px] text-text-tertiary uppercase tracking-wide mb-1">Stop Probability</p>
          {prior_stop_probability_pct != null && current_stop_probability_pct != null ? (
            <>
              <p className="text-xs font-bold text-text-primary">
                {prior_stop_probability_pct.toFixed(0)}% → {current_stop_probability_pct.toFixed(0)}%
              </p>
              <p className={`text-[10px] font-semibold ${stopDelta.color}`}>
                {stopDelta.arrow} {stopDelta.label}
              </p>
            </>
          ) : <p className="text-xs text-text-tertiary">N/A</p>}
        </div>

        <div className="rounded-md bg-surface/60 border border-border p-2">
          <p className="text-[9px] text-text-tertiary uppercase tracking-wide mb-1">Model Confidence</p>
          {prior_confidence_pct != null && current_confidence_pct != null ? (
            <>
              <p className="text-xs font-bold text-text-primary">
                {prior_confidence_pct.toFixed(0)} → {current_confidence_pct.toFixed(0)}
              </p>
              <p className={`text-[10px] font-semibold ${confDelta.color}`}>
                {confDelta.arrow} {confDelta.label}
              </p>
            </>
          ) : <p className="text-xs text-text-tertiary">N/A</p>}
        </div>

        <div className="rounded-md bg-surface/60 border border-border p-2">
          <p className="text-[9px] text-text-tertiary uppercase tracking-wide mb-1">Instability Score</p>
          {prior_stability_score != null && current_stability_score != null ? (
            <>
              <p className="text-xs font-bold text-text-primary">
                {prior_stability_score.toFixed(1)} → {current_stability_score.toFixed(1)}
              </p>
              <p className={`text-[10px] font-semibold ${stabDelta.color}`}>
                {stabDelta.arrow} Δ{stabDelta.label}
              </p>
            </>
          ) : <p className="text-xs text-text-tertiary">N/A</p>}
        </div>
      </div>

      {/* Stability class transition */}
      {stabilityClassChanged && (
        <div className="rounded-md bg-warning/8 border border-warning/25 px-3 py-2">
          <p className="text-[10px] font-semibold text-warning">
            EV Stability Regime Shift: {prior_stability_class} → {current_stability_class}
          </p>
        </div>
      )}

      {/* Scenario weights delta */}
      {prior_scenario_weights && current_scenario_weights && (
        <div className="rounded-md bg-surface/40 border border-border p-2.5 space-y-1.5">
          <div className="flex items-center justify-between">
            <p className="text-[9px] font-bold text-text-tertiary uppercase tracking-wide">Scenario Weights</p>
            {scenario_rotation_label && (
              <span className={`text-[9px] font-bold uppercase tracking-wide ${
                scenario_rotation_label === 'SIGNIFICANT' ? 'text-warning' :
                scenario_rotation_label === 'MODERATE' ? 'text-amber-400' : 'text-success'
              }`}>
                {scenario_rotation_label} Rotation
              </span>
            )}
          </div>
          <div className="grid grid-cols-3 gap-1 text-center">
            {(['bear', 'base', 'bull'] as const).map(s => {
              const prior = prior_scenario_weights[s]
              const cur = current_scenario_weights[s]
              const d = (cur - prior) * 100
              const isRisk = s === 'bear'
              const color = Math.abs(d) < 1 ? 'text-text-secondary' : (isRisk ? (d > 0 ? 'text-error' : 'text-success') : (d > 0 ? 'text-success' : 'text-warning'))
              return (
                <div key={s}>
                  <p className="text-[9px] text-text-tertiary capitalize">{s}</p>
                  <p className="text-[10px] font-bold text-text-primary">{(prior * 100).toFixed(0)}% → {(cur * 100).toFixed(0)}%</p>
                  <p className={`text-[9px] font-semibold ${color}`}>{d > 0 ? '+' : ''}{d.toFixed(0)}%</p>
                </div>
              )
            })}
          </div>
        </div>
      )}

      {/* EV Change Attribution */}
      {ev_attribution && ev_attribution.length > 0 && (
        <div className="rounded-md border border-primary/15 bg-surface/40 p-2.5 space-y-1.5">
          <p className="text-[9px] font-bold text-primary uppercase tracking-wide">EV Change Drivers</p>
          <div className="space-y-1">
            {ev_attribution.map((attr: EVAttributionDriver, i: number) => (
              <div key={i} className="flex items-center justify-between gap-2">
                <span className="text-[10px] text-text-secondary">• {attr.driver}</span>
                <span className={`text-[10px] font-semibold font-mono shrink-0 ${attributionDriverColor(attr.direction)}`}>
                  {attr.delta != null ? (attr.delta > 0 ? `+${attr.delta}` : `${attr.delta}`) : attr.direction}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Stop Probability Drift Decomposition */}
      {stop_prob_drift_decomposition && (
        prior_stop_probability_pct != null && current_stop_probability_pct != null &&
        Math.abs(current_stop_probability_pct - prior_stop_probability_pct) >= 3
      ) && (
        <div className="rounded-md bg-surface/40 border border-border p-2.5 space-y-1.5">
          <p className="text-[9px] font-bold text-text-secondary uppercase tracking-wide">
            Stop Risk Change Decomposition
          </p>
          <div className="grid grid-cols-2 gap-x-4 gap-y-1">
            {[
              { label: 'BaseStopRisk', delta: stop_prob_drift_decomposition.base_delta },
              { label: 'VolatilityPressure', delta: stop_prob_drift_decomposition.volatility_pressure_delta },
              { label: 'TrendModifier', delta: stop_prob_drift_decomposition.trend_modifier_delta },
              { label: 'SupportModifier', delta: stop_prob_drift_decomposition.support_modifier_delta },
            ].map(c => (
              <div key={c.label} className="flex items-center justify-between gap-1">
                <span className="text-[9px] text-text-tertiary">{c.label}</span>
                <span className={`text-[9px] font-mono font-semibold ${componentDeltaColor(c.delta)}`}>
                  {c.delta > 0 ? '+' : ''}{c.delta.toFixed(1)}%
                </span>
              </div>
            ))}
          </div>
          {stop_prob_drift_decomposition.prior_stop_label && stop_prob_drift_decomposition.current_stop_label &&
            stop_prob_drift_decomposition.prior_stop_label !== stop_prob_drift_decomposition.current_stop_label && (
            <p className="text-[9px] text-text-tertiary pt-0.5 border-t border-border/30">
              {stop_prob_drift_decomposition.prior_stop_label} → {stop_prob_drift_decomposition.current_stop_label}
            </p>
          )}
        </div>
      )}

      {/* Interpretation */}
      <p className="text-[10px] text-text-tertiary leading-relaxed italic">{driftInterpretation}</p>
    </div>
  )
}

/**
 * DeltaSummaryBox — opens the report with a "Since Last Analysis" summary
 * when the same user has a prior analysis for the same ticker.
 *
 * Includes MODEL DRIFT SUMMARY (Sensitivity Attribution & Drift Diagnostics Engine):
 * - Run-to-run deltas for stop probability, model confidence, instability score
 * - Scenario weight rotation tracking
 * - EV change attribution by driver
 * - Stop probability drift decomposition (per-component deltas)
 */
export function DeltaSummaryBox({ delta, ticker }: DeltaSummaryBoxProps) {
  const {
    prior_recommendation,
    current_recommendation,
    prior_price,
    current_price,
    price_change_pct,
    prior_smart_money_score,
    current_smart_money_score,
    prior_moat_score,
    current_moat_score,
    thesis_direction,
    days_since_last,
    prior_analysis_date,
    // Sensitivity attribution fields (item 1: "What Changed?" diagnostic)
    prior_signal_stability,
    current_signal_stability,
    prior_signal_spread,
    current_signal_spread,
    prior_vol_trend,
    current_vol_trend,
    sensitivity_attribution,
  } = delta

  const direction = thesisDirectionStyle(thesis_direction)
  const ratingChanged = prior_recommendation !== current_recommendation
  const smDelta = (current_smart_money_score != null && prior_smart_money_score != null)
    ? current_smart_money_score - prior_smart_money_score : null
  const moatDelta = (current_moat_score != null && prior_moat_score != null)
    ? current_moat_score - prior_moat_score : null

  const priorDateFormatted = prior_analysis_date
    ? new Date(prior_analysis_date).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })
    : null

  return (
    <div className="rounded-lg border border-primary/25 bg-primary/5 p-4 space-y-3">
      {/* Header */}
      <div className="flex items-center justify-between gap-2 flex-wrap">
        <div className="flex items-center gap-2">
          <span className="text-xs font-bold text-primary uppercase tracking-wide">
            Since Last Analysis
          </span>
          {priorDateFormatted && (
            <span className="text-[10px] text-text-tertiary">
              {days_since_last}d ago · {priorDateFormatted}
            </span>
          )}
        </div>
        <div className={`text-xs font-bold ${direction.color}`}>
          {direction.icon} Thesis {direction.label}
        </div>
      </div>

      {/* Delta grid */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">

        {/* Recommendation */}
        <div className="rounded-md bg-surface/60 border border-border p-2.5">
          <p className="text-[10px] text-text-tertiary uppercase tracking-wide mb-1">Recommendation</p>
          <div className="flex items-center gap-1">
            <span className={`text-sm font-bold ${ratingColor(prior_recommendation)}`}>
              {prior_recommendation}
            </span>
            {ratingChanged && (
              <>
                <span className="text-text-tertiary text-xs">→</span>
                <span className={`text-sm font-bold ${ratingColor(current_recommendation)}`}>
                  {current_recommendation}
                </span>
              </>
            )}
            {!ratingChanged && (
              <span className="text-[10px] text-text-tertiary ml-1">(unchanged)</span>
            )}
          </div>
        </div>

        {/* Price */}
        <div className="rounded-md bg-surface/60 border border-border p-2.5">
          <p className="text-[10px] text-text-tertiary uppercase tracking-wide mb-1">Price Change</p>
          {prior_price != null && current_price != null ? (
            <div>
              <p className="text-sm font-bold text-text-primary">
                ${prior_price.toFixed(2)} → ${current_price.toFixed(2)}
              </p>
              {price_change_pct != null && (
                <p className={`text-[10px] font-medium ${priceDeltaColor(price_change_pct)}`}>
                  {price_change_pct > 0 ? '+' : ''}{price_change_pct.toFixed(1)}%
                </p>
              )}
            </div>
          ) : (
            <p className="text-sm text-text-tertiary">N/A</p>
          )}
        </div>

        {/* Smart Money Score */}
        <div className="rounded-md bg-surface/60 border border-border p-2.5">
          <p className="text-[10px] text-text-tertiary uppercase tracking-wide mb-1">Smart Money</p>
          {prior_smart_money_score != null && current_smart_money_score != null ? (
            <div>
              <p className="text-sm font-bold text-text-primary">
                {prior_smart_money_score} → {current_smart_money_score}
              </p>
              {smDelta != null && (
                <p className={`text-[10px] font-medium ${scoreDeltaColor(smDelta)}`}>
                  {smDelta > 0 ? '+' : ''}{smDelta.toFixed(1)} pts
                </p>
              )}
            </div>
          ) : (
            <p className="text-sm text-text-tertiary">N/A</p>
          )}
        </div>

        {/* Overall Score */}
        <div className="rounded-md bg-surface/60 border border-border p-2.5">
          <p className="text-[10px] text-text-tertiary uppercase tracking-wide mb-1">Overall Score</p>
          {prior_moat_score != null && current_moat_score != null ? (
            <div>
              <p className="text-sm font-bold text-text-primary">
                {prior_moat_score.toFixed(1)} → {current_moat_score.toFixed(1)}
              </p>
              {moatDelta != null && (
                <p className={`text-[10px] font-medium ${scoreDeltaColor(moatDelta)}`}>
                  {moatDelta > 0 ? '+' : ''}{moatDelta.toFixed(1)} pts
                </p>
              )}
            </div>
          ) : (
            <p className="text-sm text-text-tertiary">N/A</p>
          )}
        </div>
      </div>

      {/* Sensitivity Attribution — "What Changed?" diagnostic (item 1) */}
      {((sensitivity_attribution && sensitivity_attribution.length > 0) ||
        (prior_signal_stability != null && current_signal_stability != null) ||
        (prior_vol_trend && current_vol_trend && prior_vol_trend !== current_vol_trend)) && (
        <div className="rounded-md border border-primary/15 bg-surface/40 p-3 space-y-2">
          <p className="text-[10px] font-bold text-primary uppercase tracking-wide">What Changed?</p>

          {/* Key metric deltas */}
          <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
            {prior_signal_stability != null && current_signal_stability != null && (
              <div>
                <p className="text-[10px] text-text-tertiary">Signal Stability</p>
                <p className={`text-xs font-semibold ${
                  current_signal_stability > prior_signal_stability ? 'text-success' :
                  current_signal_stability < prior_signal_stability ? 'text-warning' : 'text-text-secondary'
                }`}>
                  {prior_signal_stability.toFixed(1)} → {current_signal_stability.toFixed(1)}/10
                </p>
              </div>
            )}
            {prior_signal_spread != null && current_signal_spread != null && (
              <div>
                <p className="text-[10px] text-text-tertiary">Signal Spread (σ)</p>
                <p className={`text-xs font-semibold ${
                  current_signal_spread > prior_signal_spread ? 'text-warning' :
                  current_signal_spread < prior_signal_spread ? 'text-success' : 'text-text-secondary'
                }`}>
                  {prior_signal_spread.toFixed(2)} → {current_signal_spread.toFixed(2)}
                </p>
              </div>
            )}
            {prior_vol_trend && current_vol_trend && (
              <div>
                <p className="text-[10px] text-text-tertiary">Vol Regime</p>
                <p className={`text-xs font-semibold ${
                  prior_vol_trend !== current_vol_trend ? 'text-warning' : 'text-text-secondary'
                }`}>
                  {prior_vol_trend} → {current_vol_trend}
                </p>
              </div>
            )}
          </div>

          {/* Attribution bullets */}
          {sensitivity_attribution && sensitivity_attribution.length > 0 && (
            <div className="space-y-0.5 pt-1 border-t border-border/30">
              {sensitivity_attribution.map((attr, i) => (
                <p key={i} className="text-[10px] text-text-tertiary">• {attr}</p>
              ))}
            </div>
          )}
        </div>
      )}

      {/* MODEL DRIFT SUMMARY — probabilistic engine run-to-run diagnostics */}
      <ModelDriftSummary delta={delta} />

      {/* Thesis direction note */}
      <p className="text-[10px] text-text-tertiary leading-relaxed">
        {thesis_direction === 'reversed' && (
          `The rating has reversed since your last ${ticker} analysis ${days_since_last} days ago — review Key Takeaways and upgrade/downgrade triggers for what changed.`
        )}
        {thesis_direction === 'weakened' && (
          `The thesis has weakened since your last ${ticker} analysis. Check Key Risks and downgrade triggers below for evolving concerns.`
        )}
        {thesis_direction === 'strengthened' && (
          `The thesis has strengthened since your last ${ticker} analysis. Review Investment Highlights for updated supporting evidence.`
        )}
        {thesis_direction === 'held' && (
          `The thesis is holding at the same rating since your last ${ticker} analysis ${days_since_last} days ago. Check for changes in signal composition or price target movement.`
        )}
      </p>
    </div>
  )
}
