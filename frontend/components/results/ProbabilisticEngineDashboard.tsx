'use client'

/**
 * Probabilistic Engine Dashboard
 *
 * Upgrades the DVRG analytical framework from "heuristic calculator"
 * to "adaptive probabilistic system with sensitivity diagnostics."
 *
 * Five interpretability modules (items 2, 4, 5, 6, 7 from spec):
 *   2. EV Stability Classification System
 *   4. Confidence Integrity System (EV vs Confidence separation)
 *   5. Scenario Weight Stability Diagnostics
 *   6. Stop Probability Drift Decomposition
 *   7. Institutional Noise Filter
 *
 * Sensitivity Attribution & Drift Diagnostics Engine (items 1–7):
 *   1. Run-to-Run Delta Engine (Model Drift tab)
 *   2. Sensitivity Attribution (EV change driver decomposition)
 *   3. Probability Drift Decomposition (stop risk component deltas)
 *   4. Scenario Rotation Diagnostics (rotation index, compression, tail state)
 *   5. EV Stability Classification (Structurally Stable → Noise Dominated)
 *   6. Confidence Integrity Separation (Signal Confidence vs Model Stability)
 *   7. Drift Visualization Encoding (arrows, glow, animation, pulse)
 *
 * Design constraints:
 *   - Probabilistic framing throughout — no deterministic language
 *   - Institutional tone — outputs communicate What / How Stable / Why Changed
 *   - Minimal cognitive overload — progressive disclosure, summary strip always visible
 */

import { useState } from 'react'
import { AlertTriangle, Shield, Activity, TrendingDown, BarChart3, Info, GitCompare } from 'lucide-react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip'
import type {
  SignalBreakdown,
  EVStabilityClass,
  ConfidenceIntegrity,
  ScenarioWeightDiagnostics,
  StopProbabilityDecomposition,
  NoiseFilter,
  PreviousAnalysisDelta,
  EVAttributionDriver,
  StopProbDriftDecomposition,
} from '@/types/api'

interface ProbabilisticEngineDashboardProps {
  breakdown: SignalBreakdown
  /** Optional: prior analysis delta for run-to-run drift diagnostics */
  delta?: PreviousAnalysisDelta | null
}

type TabId = 'ev' | 'confidence' | 'scenarios' | 'stop' | 'noise' | 'drift'

// ── Color helpers ────────────────────────────────────────────────────────────

function stabilityColor(cls: string) {
  if (cls === 'Noise Dominated') return 'text-error'
  if (cls === 'Highly Sensitive') return 'text-warning'
  if (cls === 'Moderately Sensitive') return 'text-amber-400'
  return 'text-success'
}

function stabilityBadgeVariant(cls: string): 'error' | 'warning' | 'default' | 'success' {
  if (cls === 'Noise Dominated') return 'error'
  if (cls === 'Highly Sensitive') return 'warning'
  if (cls === 'Moderately Sensitive') return 'warning'
  return 'success'
}

function confidenceColor(level: string) {
  if (level === 'VERY LOW') return 'text-error'
  if (level === 'LOW') return 'text-warning'
  if (level === 'MODERATE') return 'text-amber-400'
  return 'text-success'
}

function confidenceBarColor(level: string) {
  if (level === 'VERY LOW') return 'bg-error'
  if (level === 'LOW') return 'bg-warning'
  if (level === 'MODERATE') return 'bg-amber-400'
  return 'bg-success'
}

function stopColor(label: string) {
  if (label === 'Critical') return 'text-error'
  if (label === 'High') return 'text-warning'
  if (label === 'Elevated') return 'text-amber-400'
  return 'text-success'
}

function stopBarColor(label: string) {
  if (label === 'Critical') return 'bg-error'
  if (label === 'High') return 'bg-warning'
  if (label === 'Elevated') return 'bg-amber-400'
  return 'bg-success'
}

function noiseColor(regime: string) {
  if (regime === 'Noise Dominated') return 'text-error'
  if (regime === 'High Noise') return 'text-warning'
  if (regime === 'Moderate Noise') return 'text-amber-400'
  return 'text-success'
}

function tailStateColor(state: string) {
  if (state === 'Expanded') return 'text-warning'
  if (state === 'Compressed') return 'text-success'
  return 'text-text-secondary'
}

function driverTypeColor(driver: string) {
  if (driver === 'Signal Instability') return 'text-warning'
  if (driver === 'Market Movement Impact') return 'text-primary'
  if (driver === 'Mixed') return 'text-amber-400'
  return 'text-text-tertiary'
}

// ── Card-level border color based on noise regime (visual drift encoding) ───

function noiseBorderClass(noise: NoiseFilter | undefined) {
  if (!noise) return ''
  if (noise.noise_regime === 'Noise Dominated') return 'border-error/40'
  if (noise.noise_regime === 'High Noise') return 'border-warning/40'
  if (noise.noise_regime === 'Moderate Noise') return 'border-amber-400/30'
  return ''
}

// ── Drift visual helpers ─────────────────────────────────────────────────────

function driftArrow(prior: number | null | undefined, current: number | null | undefined, higherIsWorse = true) {
  if (prior == null || current == null) return null
  const d = current - prior
  if (Math.abs(d) < 0.5) return <span className="text-text-tertiary text-[9px]">→</span>
  if (d > 0) return <span className={`text-[9px] font-bold ${higherIsWorse ? 'text-error' : 'text-success'}`}>↑</span>
  return <span className={`text-[9px] font-bold ${higherIsWorse ? 'text-success' : 'text-warning'}`}>↓</span>
}

function driftLevelColor(level: string | null | undefined): string {
  if (level === 'Significant') return 'text-error'
  if (level === 'Moderate') return 'text-warning'
  if (level === 'Modest') return 'text-amber-400'
  return 'text-success'
}

// ── Glow class: pulse when metric is degrading ───────────────────────────────

function degradingGlowClass(prior: number | null | undefined, current: number | null | undefined, higherIsWorse = true, threshold = 3): string {
  if (prior == null || current == null) return ''
  const d = current - prior
  const worsening = higherIsWorse ? d > threshold : d < -threshold
  return worsening ? 'ring-1 ring-error/40 shadow-error/20 shadow-sm animate-pulse' : ''
}

// ── Sub-components ───────────────────────────────────────────────────────────

function MetricRow({ label, value, className = '' }: { label: string; value: React.ReactNode; className?: string }) {
  return (
    <div className="flex items-start justify-between gap-3 text-sm py-1.5 border-b border-border/30 last:border-0">
      <span className="text-text-tertiary shrink-0">{label}</span>
      <span className={`text-right font-medium ${className}`}>{value}</span>
    </div>
  )
}

function SectionLabel({ children }: { children: React.ReactNode }) {
  return (
    <p className="text-xs font-semibold text-text-tertiary uppercase tracking-wider mb-2">{children}</p>
  )
}

// ── EV Stability Panel ───────────────────────────────────────────────────────

function EVStabilityPanel({ data, delta }: { data: EVStabilityClass; delta?: PreviousAnalysisDelta | null }) {
  const bandHalf = data.ev_sensitivity_band_pct
  const priorStab = delta?.prior_stability_score
  const curStab = delta?.current_stability_score
  const classChanged = delta?.prior_stability_class && delta?.current_stability_class &&
    delta.prior_stability_class !== delta.current_stability_class

  return (
    <div className="space-y-4">
      {/* Classification header */}
      <div className="flex items-center gap-3">
        <Badge variant={stabilityBadgeVariant(data.stability_class)} className="text-sm px-3 py-1">
          {data.stability_class}
        </Badge>
        <span className={`text-sm font-medium ${driverTypeColor(data.sensitivity_driver)}`}>
          Driver: {data.sensitivity_driver}
        </span>
        {/* Drift arrow for stability class */}
        {classChanged && (
          <span className="text-[10px] text-warning bg-warning/10 border border-warning/25 rounded px-1.5 py-0.5">
            {delta.prior_stability_class} → {delta.current_stability_class}
          </span>
        )}
      </div>

      {/* EV Flicker Band — visual drift encoding */}
      <div className="rounded-md bg-surface-elevated p-4 space-y-2">
        <SectionLabel>EV Sensitivity Band (Item 8: Flicker Encoding)</SectionLabel>
        <div className="flex items-center gap-2 text-xs text-text-tertiary">
          <span className="shrink-0">−{bandHalf.toFixed(1)}%</span>
          <div className="relative flex-1 h-3 rounded-full bg-border/40 overflow-hidden">
            {/* Center anchor */}
            <div className="absolute inset-y-0 left-1/2 w-0.5 -translate-x-1/2 bg-text-primary opacity-60" />
            {/* Sensitivity band overlay — width scales with instability */}
            <div
              className={`absolute inset-y-0 left-1/2 -translate-x-1/2 rounded-full opacity-40 ${
                data.stability_class === 'Noise Dominated' ? 'bg-error animate-pulse' :
                data.stability_class === 'Highly Sensitive' ? 'bg-warning' :
                data.stability_class === 'Moderately Sensitive' ? 'bg-amber-400' :
                'bg-success'
              }`}
              style={{ width: `${Math.min(100, bandHalf * 5)}%` }}
            />
          </div>
          <span className="shrink-0">+{bandHalf.toFixed(1)}%</span>
        </div>
        <p className="text-xs text-text-tertiary">
          EV estimates may vary by ±{bandHalf.toFixed(1)}% under current signal conditions.
        </p>
      </div>

      {/* Driver attribution */}
      <div className="rounded-md bg-surface-elevated p-4 space-y-2">
        <SectionLabel>Sensitivity Attribution</SectionLabel>
        <MetricRow
          label="Signal-side instability score"
          value={
            <span className="flex items-center gap-1">
              {data.signal_driver_score}/10
              {driftArrow(delta?.prior_stability_score, delta?.current_stability_score, true)}
            </span>
          }
          className={data.signal_driver_score >= 4 ? 'text-warning' : 'text-text-secondary'}
        />
        <MetricRow
          label="Market-side instability score"
          value={`${data.market_driver_score}/10`}
          className={data.market_driver_score >= 4 ? 'text-warning' : 'text-text-secondary'}
        />
        {priorStab != null && curStab != null && (
          <p className="text-[10px] text-text-tertiary pt-1 border-t border-border/30">
            Instability run-to-run: {priorStab.toFixed(1)} → {curStab.toFixed(1)}
            {' '}{curStab > priorStab ? '(degrading ↑)' : curStab < priorStab ? '(improving ↓)' : '(stable)'}
          </p>
        )}
        <p className="text-xs text-text-secondary pt-1 leading-relaxed">{data.driver_note}</p>
      </div>

      {/* Rationale */}
      <div className="rounded-md bg-surface-elevated p-4">
        <SectionLabel>Stability Rationale</SectionLabel>
        <p className="text-sm text-text-secondary leading-relaxed">{data.stability_rationale}</p>
      </div>
    </div>
  )
}

// ── Confidence Integrity Panel ───────────────────────────────────────────────

function ConfidenceIntegrityPanel({ data, delta }: { data: ConfidenceIntegrity; delta?: PreviousAnalysisDelta | null }) {
  const priorConf = delta?.prior_confidence_pct
  const curConf = delta?.current_confidence_pct
  const glowClass = degradingGlowClass(priorConf, curConf, false, 10)

  return (
    <div className="space-y-4">
      {/* EV vs Confidence separation — key visual */}
      <div className="grid grid-cols-2 gap-3">
        <div className="rounded-md bg-surface-elevated p-4 text-center">
          <p className="text-xs text-text-tertiary mb-1">EV Signal</p>
          <p className="text-lg font-bold text-text-primary">Intact</p>
          <p className="text-xs text-text-tertiary mt-1">Directional estimate retained</p>
        </div>
        <div className={`rounded-md bg-surface-elevated p-4 text-center ${glowClass}`}>
          <p className="text-xs text-text-tertiary mb-1">Confidence in EV</p>
          <p className={`text-lg font-bold ${confidenceColor(data.ev_confidence_level)}`}>
            {data.ev_confidence_level}
          </p>
          <div className="flex items-center justify-center gap-1">
            <p className="text-xs text-text-tertiary mt-1">{data.effective_confidence_pct.toFixed(0)}/100</p>
            {driftArrow(priorConf, curConf, false)}
          </div>
        </div>
      </div>

      {/* Confidence bar */}
      <div className="rounded-md bg-surface-elevated p-4 space-y-2">
        <div className="flex justify-between text-xs text-text-tertiary">
          <span>Effective Confidence</span>
          <span>{data.effective_confidence_pct.toFixed(0)}/100</span>
        </div>
        <div className="h-2 rounded-full bg-border/40 overflow-hidden">
          <div
            className={`h-full rounded-full transition-all ${confidenceBarColor(data.ev_confidence_level)}`}
            style={{ width: `${data.effective_confidence_pct}%` }}
          />
        </div>
        <p className="text-xs text-text-tertiary">
          Base: {data.base_confidence_pct.toFixed(0)}/100 → Degradation: −{data.total_degradation_pts.toFixed(0)}pts
          · Dispersion: {data.probability_dispersion_label}
        </p>
        {/* Run-to-run confidence drift */}
        {priorConf != null && curConf != null && (
          <p className="text-[10px] text-text-tertiary border-t border-border/30 pt-1">
            Prior run: {priorConf.toFixed(0)}/100 → Current: {curConf.toFixed(0)}/100
            {' '}({curConf - priorConf > 0 ? '+' : ''}{(curConf - priorConf).toFixed(0)} pts)
          </p>
        )}
      </div>

      {/* Confidence note */}
      <div className="rounded-md bg-surface-elevated p-4">
        <SectionLabel>Model Confidence Assessment</SectionLabel>
        <p className="text-sm text-text-secondary leading-relaxed">{data.confidence_note}</p>
      </div>

      {/* Degradation drivers */}
      {data.confidence_degradation_drivers.length > 0 && (
        <div className="rounded-md bg-surface-elevated p-4">
          <SectionLabel>Degradation Drivers</SectionLabel>
          <div className="space-y-1">
            {data.confidence_degradation_drivers.map((d, i) => (
              <p key={i} className="text-xs text-warning">• {d}</p>
            ))}
          </div>
        </div>
      )}

      {/* Separation note */}
      <div className="rounded-md bg-primary/5 border border-primary/15 p-3">
        <p className="text-xs text-text-secondary leading-relaxed italic">{data.separation_note}</p>
      </div>
    </div>
  )
}

// ── Scenario Weight Diagnostics Panel ────────────────────────────────────────

function ScenarioWeightsPanel({ data, delta }: { data: ScenarioWeightDiagnostics; delta?: PreviousAnalysisDelta | null }) {
  const scenarios = [
    { label: 'Bear (Risk)', model: data.model_bear_prob, effective: data.effective_bear_prob, color: 'bg-error', key: 'bear' as const },
    { label: 'Base (Continuation)', model: data.model_base_prob, effective: data.effective_base_prob, color: 'bg-primary', key: 'base' as const },
    { label: 'Bull (Re-rating)', model: data.model_bull_prob, effective: data.effective_bull_prob, color: 'bg-success', key: 'bull' as const },
  ]

  const priorWeights = delta?.prior_scenario_weights
  const curWeights = delta?.current_scenario_weights
  const rotationLabel = delta?.scenario_rotation_label

  return (
    <div className="space-y-4">
      {/* Summary row */}
      <div className="grid grid-cols-3 gap-2">
        <div className="rounded-md bg-surface-elevated p-3 text-center">
          <p className="text-xs text-text-tertiary mb-1">Rotation Index</p>
          <p className={`text-base font-bold ${data.scenario_rotation_index >= 15 ? 'text-warning' : data.scenario_rotation_index >= 5 ? 'text-amber-400' : 'text-success'}`}>
            {data.scenario_rotation_index.toFixed(1)}
          </p>
          <p className="text-xs text-text-tertiary mt-0.5">{data.drift_label}</p>
        </div>
        <div className="rounded-md bg-surface-elevated p-3 text-center">
          <p className="text-xs text-text-tertiary mb-1">Compression Ratio</p>
          <p className="text-base font-bold text-text-primary">{data.probability_compression_ratio.toFixed(2)}×</p>
          <p className="text-xs text-text-tertiary mt-0.5">Base / Tails</p>
        </div>
        <div className="rounded-md bg-surface-elevated p-3 text-center">
          <p className="text-xs text-text-tertiary mb-1">Tail State</p>
          <p className={`text-base font-bold ${tailStateColor(data.tail_state)}`}>{data.tail_state}</p>
          <p className="text-xs text-text-tertiary mt-0.5">vs Neutral</p>
        </div>
      </div>

      {/* Model vs Effective table */}
      <div className="rounded-md bg-surface-elevated p-4 space-y-3">
        <SectionLabel>Model vs Effective Probabilities</SectionLabel>
        {scenarios.map(s => {
          const priorPct = priorWeights ? priorWeights[s.key] * 100 : null
          const curPct = curWeights ? curWeights[s.key] * 100 : null
          return (
            <div key={s.label} className="space-y-1">
              <div className="flex justify-between text-xs">
                <span className="text-text-tertiary">{s.label}</span>
                <span className="text-text-secondary flex items-center gap-1">
                  Model {(s.model * 100).toFixed(0)}% → Effective {(s.effective * 100).toFixed(0)}%
                  {/* Run-to-run arrow */}
                  {priorPct != null && curPct != null && (
                    <span className="text-[9px] text-text-tertiary ml-1">
                      (prev: {priorPct.toFixed(0)}%{' '}
                      {driftArrow(priorPct, curPct, s.key === 'bear')})
                    </span>
                  )}
                </span>
              </div>
              <div className="relative h-2 rounded-full bg-border/30 overflow-hidden">
                {/* Model bar (ghost) */}
                <div
                  className="absolute inset-y-0 left-0 rounded-full opacity-20 bg-text-tertiary"
                  style={{ width: `${s.model * 100}%` }}
                />
                {/* Effective bar */}
                <div
                  className={`absolute inset-y-0 left-0 rounded-full ${s.color}`}
                  style={{ width: `${s.effective * 100}%` }}
                />
              </div>
            </div>
          )
        })}
      </div>

      {/* Scenario Rotation Diagnostics — cross-run */}
      {priorWeights && curWeights && (
        <div className="rounded-md bg-surface-elevated p-4 space-y-2">
          <div className="flex items-center justify-between">
            <SectionLabel>Scenario Rotation (Run-to-Run)</SectionLabel>
            {rotationLabel && (
              <span className={`text-[10px] font-bold uppercase tracking-wide ${
                rotationLabel === 'SIGNIFICANT' ? 'text-warning' :
                rotationLabel === 'MODERATE' ? 'text-amber-400' : 'text-success'
              }`}>
                {rotationLabel}
              </span>
            )}
          </div>
          <div className="grid grid-cols-3 gap-2 text-center">
            {(['bear', 'base', 'bull'] as const).map(s => {
              const prev = priorWeights[s] * 100
              const cur = curWeights[s] * 100
              const d = cur - prev
              const isRisk = s === 'bear'
              const color = Math.abs(d) < 1 ? 'text-text-secondary' :
                isRisk ? (d > 0 ? 'text-error' : 'text-success') :
                (d > 0 ? 'text-success' : 'text-warning')
              return (
                <div key={s} className="rounded bg-surface p-2">
                  <p className="text-[9px] text-text-tertiary capitalize mb-0.5">{s}</p>
                  <p className="text-[10px] font-bold text-text-primary">{prev.toFixed(0)}% → {cur.toFixed(0)}%</p>
                  <p className={`text-[9px] font-semibold ${color}`}>{d > 0 ? '+' : ''}{d.toFixed(0)}%</p>
                </div>
              )
            })}
          </div>
        </div>
      )}

      {/* Tail note */}
      <div className="rounded-md bg-surface-elevated p-4">
        <SectionLabel>Tail Condition</SectionLabel>
        <p className="text-sm text-text-secondary leading-relaxed">{data.tail_note}</p>
      </div>

      {/* Weight shift rationale */}
      {data.active_rotation_factors.length > 0 && (
        <div className="rounded-md bg-surface-elevated p-4">
          <SectionLabel>Weight Shift Rationale</SectionLabel>
          <p className="text-xs text-text-secondary leading-relaxed mb-2">{data.weight_shift_rationale}</p>
          <div className="space-y-1">
            {data.active_rotation_factors.slice(0, 4).map((f, i) => (
              <p key={i} className="text-xs text-text-tertiary">• {f}</p>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

// ── Stop Probability Decomposition Panel ─────────────────────────────────────

function StopProbabilityPanel({ data, delta }: { data: StopProbabilityDecomposition; delta?: PreviousAnalysisDelta | null }) {
  const components = [
    { label: 'Base Stop Risk', value: data.base_stop_risk_pct, note: 'Bear scenario prior (25%)' },
    { label: 'Volatility Pressure', value: data.volatility_pressure_pct, note: data.volatility_pressure_drivers.join(', ') || 'Stable regime' },
    { label: 'Trend Modifier', value: data.trend_modifier_pct, note: 'Technical momentum alignment' },
    { label: 'Support Modifier', value: data.support_modifier_pct, note: 'Aggregate signal score proxy' },
  ]

  const priorStop = delta?.prior_stop_probability_pct
  const curStop = delta?.current_stop_probability_pct
  const stopDecomp: StopProbDriftDecomposition | null | undefined = delta?.stop_prob_drift_decomposition
  const glowClass = degradingGlowClass(priorStop, curStop, true, 5)

  return (
    <div className="space-y-4">
      {/* Headline */}
      <div className={`flex items-center gap-3 rounded-md p-3 ${glowClass}`}>
        <div className="text-center">
          <p className="text-xs text-text-tertiary">Effective Stop Probability</p>
          <p className={`text-3xl font-bold ${stopColor(data.stop_probability_label)}`}>
            {data.effective_stop_probability_pct.toFixed(0)}%
          </p>
        </div>
        <div>
          <Badge
            variant={data.stop_probability_label === 'Critical' || data.stop_probability_label === 'High' ? 'error' : data.stop_probability_label === 'Elevated' ? 'warning' : 'success'}
          >
            {data.stop_probability_label}
          </Badge>
          {/* Run-to-run delta */}
          {priorStop != null && curStop != null && (
            <p className="text-[10px] text-text-tertiary mt-1">
              Prior: {priorStop.toFixed(0)}% {driftArrow(priorStop, curStop, true)} {curStop > priorStop ? `(+${(curStop - priorStop).toFixed(0)}%)` : `(${(curStop - priorStop).toFixed(0)}%)`}
            </p>
          )}
          <p className="text-xs text-text-tertiary mt-1">Bear scenario probability</p>
        </div>
      </div>

      {/* Progress bar */}
      <div className="h-2 rounded-full bg-border/40 overflow-hidden">
        <div
          className={`h-full rounded-full ${stopBarColor(data.stop_probability_label)}`}
          style={{ width: `${Math.min(100, data.effective_stop_probability_pct)}%` }}
        />
      </div>

      {/* Decomposition waterfall */}
      <div className="rounded-md bg-surface-elevated p-4 space-y-2">
        <SectionLabel>Decomposition</SectionLabel>
        {components.map((c, i) => {
          // Component-level delta
          const compDelta: number | null = stopDecomp ? [
            stopDecomp.base_delta,
            stopDecomp.volatility_pressure_delta,
            stopDecomp.trend_modifier_delta,
            stopDecomp.support_modifier_delta,
          ][i] : null

          return (
            <div key={i} className="flex items-start justify-between gap-3 text-xs py-1.5 border-b border-border/30 last:border-0">
              <div>
                <p className="text-text-secondary font-medium">{c.label}</p>
                {c.note && <p className="text-text-tertiary mt-0.5">{c.note}</p>}
              </div>
              <div className="text-right shrink-0">
                <span className={`font-mono font-semibold ${
                  c.value > 0 ? 'text-error' : c.value < 0 ? 'text-success' : 'text-text-tertiary'
                }`}>
                  {c.value > 0 ? '+' : ''}{c.value.toFixed(1)}%
                </span>
                {/* Run-to-run component delta */}
                {compDelta != null && Math.abs(compDelta) >= 0.5 && (
                  <p className={`text-[9px] font-mono mt-0.5 ${compDelta > 0 ? 'text-error' : 'text-success'}`}>
                    Δ{compDelta > 0 ? '+' : ''}{compDelta.toFixed(1)}%
                  </p>
                )}
              </div>
            </div>
          )
        })}
        {/* Narrative */}
        <p className="text-xs text-text-tertiary font-mono pt-1 border-t border-border/30">
          {data.decomposition_narrative}
        </p>
      </div>

      {/* Stop Drift Interpretation */}
      {stopDecomp && priorStop != null && curStop != null && Math.abs(curStop - priorStop) >= 3 && (
        <div className="rounded-md bg-surface-elevated p-4 space-y-2">
          <SectionLabel>Stop Risk Change Interpretation</SectionLabel>
          <div className="grid grid-cols-2 gap-x-4 gap-y-1">
            {[
              { label: 'VolatilityPressure', delta: stopDecomp.volatility_pressure_delta },
              { label: 'TrendModifier', delta: stopDecomp.trend_modifier_delta },
              { label: 'SupportModifier', delta: stopDecomp.support_modifier_delta },
            ].filter(c => Math.abs(c.delta) >= 0.5).map(c => (
              <div key={c.label} className="flex items-center gap-2">
                <span className={`text-[9px] ${c.delta > 0 ? 'text-error' : 'text-success'}`}>
                  {c.delta > 0 ? '↑' : '↓'}
                </span>
                <span className="text-[10px] text-text-secondary">{c.label}</span>
                <span className={`text-[10px] font-mono ml-auto ${c.delta > 0 ? 'text-error' : 'text-success'}`}>
                  {c.delta > 0 ? '+' : ''}{c.delta.toFixed(1)}%
                </span>
              </div>
            ))}
          </div>
          <p className="text-[10px] text-text-tertiary italic pt-1 border-t border-border/30">
            {stopDecomp.volatility_pressure_delta > 3
              ? 'Risk expansion driven primarily by regime instability rather than structural deterioration.'
              : stopDecomp.support_modifier_delta > 2 || stopDecomp.trend_modifier_delta > 2
              ? 'Stop risk increase reflects technical and support deterioration — monitor for structural breakdown.'
              : 'Stop probability shift is modest and within normal recalibration range.'}
          </p>
        </div>
      )}

      {/* Regime note */}
      <div className="rounded-md bg-surface-elevated p-4">
        <SectionLabel>Regime Context</SectionLabel>
        <p className="text-sm text-text-secondary leading-relaxed">{data.regime_note}</p>
      </div>
    </div>
  )
}

// ── Noise Filter Panel ───────────────────────────────────────────────────────

function NoiseFilterPanel({ data, delta }: { data: NoiseFilter; delta?: PreviousAnalysisDelta | null }) {
  const priorNoise = delta?.prior_noise_score
  const curNoise = delta?.current_noise_score

  return (
    <div className="space-y-4">
      {/* Headline */}
      <div className="flex items-center gap-3">
        <p className={`text-2xl font-bold ${noiseColor(data.noise_regime)}`}>{data.noise_regime}</p>
        <div className="text-right">
          <p className="text-xs text-text-tertiary">Noise Score</p>
          <div className="flex items-center gap-1">
            <p className={`text-lg font-bold ${noiseColor(data.noise_regime)}`}>{data.noise_score}/100</p>
            {driftArrow(priorNoise, curNoise, true)}
          </div>
        </div>
      </div>

      {/* Noise score bar */}
      <div className="h-2 rounded-full bg-border/40 overflow-hidden">
        <div
          className={`h-full rounded-full ${
            data.noise_regime === 'Noise Dominated' ? 'bg-error animate-pulse' :
            data.noise_regime === 'High Noise' ? 'bg-warning' :
            data.noise_regime === 'Moderate Noise' ? 'bg-amber-400' :
            'bg-success'
          }`}
          style={{ width: `${data.noise_score}%` }}
        />
      </div>

      {/* Run-to-run noise drift */}
      {priorNoise != null && curNoise != null && (
        <p className="text-[10px] text-text-tertiary">
          Prior noise score: {priorNoise.toFixed(0)}/100 → Current: {curNoise.toFixed(0)}/100
          {' '}({curNoise > priorNoise ? `+${(curNoise - priorNoise).toFixed(0)}` : `${(curNoise - priorNoise).toFixed(0)}`})
        </p>
      )}

      {/* Action guidance */}
      <div className="rounded-md bg-surface-elevated p-4">
        <SectionLabel>Action Guidance</SectionLabel>
        <p className={`text-sm font-semibold ${noiseColor(data.noise_regime)}`}>{data.action_guidance}</p>
        {data.defer_sizing && (
          <p className="text-xs text-error mt-1">⚠ Defer sizing decisions — confidence impaired</p>
        )}
      </div>

      {/* Noise drivers */}
      {data.noise_drivers.length > 0 && (
        <div className="rounded-md bg-surface-elevated p-4">
          <SectionLabel>Active Noise Drivers</SectionLabel>
          <div className="space-y-1">
            {data.noise_drivers.map((d, i) => (
              <p key={i} className="text-xs text-warning">• {d}</p>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

// ── Model Drift Panel (new: run-to-run delta diagnostics) ────────────────────

function ModelDriftPanel({ delta }: { delta: PreviousAnalysisDelta }) {
  const {
    prior_stop_probability_pct,
    current_stop_probability_pct,
    prior_confidence_pct,
    current_confidence_pct,
    prior_stability_score,
    current_stability_score,
    prior_noise_score,
    current_noise_score,
    prior_stability_class,
    current_stability_class,
    prior_scenario_weights,
    current_scenario_weights,
    model_drift_level,
    scenario_rotation_label,
    ev_attribution,
    stop_prob_drift_decomposition,
  } = delta

  const hasProbData = prior_stop_probability_pct != null || prior_confidence_pct != null

  if (!hasProbData) {
    return (
      <div className="rounded-md bg-surface-elevated p-6 text-center">
        <p className="text-sm text-text-tertiary">No prior probabilistic model state available for comparison.</p>
        <p className="text-xs text-text-tertiary mt-1">Run a second analysis on the same ticker to unlock drift diagnostics.</p>
      </div>
    )
  }

  // Interpretive drift narrative
  const driftInterpretation =
    model_drift_level === 'Significant'
      ? 'Substantial model state change detected. Treat current output as a materially different setup from the prior run.'
      : model_drift_level === 'Moderate'
      ? 'Meaningful model drift observed. Output reflects updated regime conditions — review key changes before acting.'
      : model_drift_level === 'Modest'
      ? 'Minor model evolution detected. Inputs shifted incrementally — core thesis unchanged but risk parameters updated.'
      : 'Model state is stable. Output variation within normal recalculation tolerance — thesis continuity maintained.'

  return (
    <div className="space-y-4">
      {/* Drift level badge */}
      {model_drift_level && (
        <div className="flex items-center gap-2">
          <span className="text-xs text-text-tertiary">Model Drift Level:</span>
          <span className={`text-sm font-bold ${driftLevelColor(model_drift_level)}`}>
            {model_drift_level}
          </span>
          {model_drift_level === 'Significant' && <span className="text-xs text-error animate-pulse">●</span>}
          {model_drift_level === 'Moderate' && <span className="text-xs text-warning">●</span>}
        </div>
      )}

      {/* Core metric drift grid */}
      <div className="rounded-md bg-surface-elevated p-4 space-y-2">
        <SectionLabel>Model State Δ (Run-to-Run)</SectionLabel>
        {[
          {
            label: 'Stop Probability',
            prior: prior_stop_probability_pct,
            cur: current_stop_probability_pct,
            unit: '%',
            higherIsWorse: true,
          },
          {
            label: 'Model Confidence',
            prior: prior_confidence_pct,
            cur: current_confidence_pct,
            unit: '/100',
            higherIsWorse: false,
          },
          {
            label: 'Instability Score',
            prior: prior_stability_score,
            cur: current_stability_score,
            unit: '',
            higherIsWorse: true,
          },
          {
            label: 'Noise Score',
            prior: prior_noise_score,
            cur: current_noise_score,
            unit: '/100',
            higherIsWorse: true,
          },
        ].map(m => {
          if (m.prior == null || m.cur == null) return null
          const d = m.cur - m.prior
          const color = Math.abs(d) < 0.5 ? 'text-text-secondary' :
            m.higherIsWorse
              ? (d > 0 ? 'text-error' : 'text-success')
              : (d > 0 ? 'text-success' : 'text-warning')
          return (
            <div key={m.label} className="flex items-center justify-between gap-3 text-xs py-1.5 border-b border-border/30 last:border-0">
              <span className="text-text-tertiary">{m.label}</span>
              <div className="flex items-center gap-2 text-right">
                <span className="text-text-secondary font-mono">
                  {m.prior.toFixed(1)}{m.unit} → {m.cur.toFixed(1)}{m.unit}
                </span>
                <span className={`font-mono font-bold ${color}`}>
                  {d > 0 ? '↑' : d < 0 ? '↓' : '→'} {d > 0 ? '+' : ''}{d.toFixed(1)}{m.unit}
                </span>
              </div>
            </div>
          )
        })}

        {/* EV Stability class transition */}
        {prior_stability_class && current_stability_class && (
          <div className="flex items-center justify-between gap-3 text-xs py-1.5 border-b border-border/30 last:border-0">
            <span className="text-text-tertiary">EV Stability Class</span>
            <span className={`font-medium ${prior_stability_class !== current_stability_class ? 'text-warning' : 'text-text-secondary'}`}>
              {prior_stability_class} → {current_stability_class}
            </span>
          </div>
        )}
      </div>

      {/* EV Change Attribution */}
      {ev_attribution && ev_attribution.length > 0 && (
        <div className="rounded-md bg-surface-elevated p-4 space-y-2">
          <SectionLabel>EV Change Attribution</SectionLabel>
          <p className="text-xs text-text-secondary mb-2">EV δ decomposed by primary driver:</p>
          <div className="space-y-1.5">
            {ev_attribution.map((attr: EVAttributionDriver, i: number) => (
              <div key={i} className="flex items-center justify-between gap-2 text-xs">
                <span className="text-text-secondary">• {attr.driver}</span>
                <span className={`font-mono font-semibold shrink-0 ${
                  attr.direction === 'bearish' ? 'text-error' :
                  attr.direction === 'bullish' ? 'text-success' : 'text-text-secondary'
                }`}>
                  {attr.delta != null
                    ? `${attr.delta > 0 ? '+' : ''}${attr.delta}`
                    : attr.direction === 'bearish' ? '↑ bearish' : attr.direction === 'bullish' ? '↓ bullish' : '~'}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Scenario rotation diagnostics */}
      {prior_scenario_weights && current_scenario_weights && (
        <div className="rounded-md bg-surface-elevated p-4 space-y-2">
          <div className="flex items-center justify-between mb-1">
            <SectionLabel>Scenario Rotation</SectionLabel>
            {scenario_rotation_label && (
              <span className={`text-[10px] font-bold uppercase ${
                scenario_rotation_label === 'SIGNIFICANT' ? 'text-warning' :
                scenario_rotation_label === 'MODERATE' ? 'text-amber-400' : 'text-success'
              }`}>
                {scenario_rotation_label}
              </span>
            )}
          </div>
          <div className="grid grid-cols-3 gap-2">
            {(['bear', 'base', 'bull'] as const).map(s => {
              const prev = prior_scenario_weights[s] * 100
              const cur = current_scenario_weights[s] * 100
              const d = cur - prev
              const isRisk = s === 'bear'
              const color = Math.abs(d) < 1 ? 'text-text-secondary' :
                isRisk ? (d > 0 ? 'text-error' : 'text-success') : (d > 0 ? 'text-success' : 'text-warning')
              return (
                <div key={s} className="rounded bg-surface p-2 text-center">
                  <p className="text-[9px] text-text-tertiary capitalize mb-0.5">{s}</p>
                  <p className="text-xs font-bold text-text-primary">{prev.toFixed(0)}%→{cur.toFixed(0)}%</p>
                  <p className={`text-[9px] font-semibold ${color}`}>{d > 0 ? '+' : ''}{d.toFixed(0)}%</p>
                </div>
              )
            })}
          </div>
        </div>
      )}

      {/* Stop probability drift decomposition */}
      {stop_prob_drift_decomposition && (
        prior_stop_probability_pct != null && current_stop_probability_pct != null &&
        Math.abs(current_stop_probability_pct - prior_stop_probability_pct) >= 3
      ) && (
        <div className="rounded-md bg-surface-elevated p-4 space-y-2">
          <SectionLabel>Stop Risk Change Decomposition</SectionLabel>
          <div className="space-y-1.5">
            {[
              { label: 'BaseStopRisk', delta: stop_prob_drift_decomposition!.base_delta },
              { label: 'VolatilityPressure', delta: stop_prob_drift_decomposition!.volatility_pressure_delta },
              { label: 'TrendModifier', delta: stop_prob_drift_decomposition!.trend_modifier_delta },
              { label: 'SupportModifier', delta: stop_prob_drift_decomposition!.support_modifier_delta },
            ].map(c => (
              <div key={c.label} className="flex items-center justify-between text-xs">
                <span className="text-text-secondary">• {c.label}</span>
                <span className={`font-mono font-semibold ${c.delta > 0 ? 'text-error' : c.delta < 0 ? 'text-success' : 'text-text-tertiary'}`}>
                  {c.delta > 0 ? '+' : ''}{c.delta.toFixed(1)}%
                </span>
              </div>
            ))}
          </div>
          {stop_prob_drift_decomposition!.prior_stop_label && stop_prob_drift_decomposition!.current_stop_label &&
            stop_prob_drift_decomposition!.prior_stop_label !== stop_prob_drift_decomposition!.current_stop_label && (
            <p className="text-[10px] text-text-tertiary pt-1 border-t border-border/30">
              Label: {stop_prob_drift_decomposition!.prior_stop_label} → {stop_prob_drift_decomposition!.current_stop_label}
            </p>
          )}
          {/* Interpretive note */}
          <p className="text-[10px] text-text-tertiary italic pt-1 border-t border-border/30">
            {stop_prob_drift_decomposition!.volatility_pressure_delta > 3
              ? 'Risk expansion driven by regime instability rather than structural deterioration.'
              : stop_prob_drift_decomposition!.support_modifier_delta > 2 || stop_prob_drift_decomposition!.trend_modifier_delta > 2
              ? 'Stop risk increase reflects technical and support deterioration — monitor for structural breakdown.'
              : 'Stop probability shift within normal recalibration range.'}
          </p>
        </div>
      )}

      {/* Interpretation */}
      <div className="rounded-md bg-primary/5 border border-primary/15 p-3">
        <p className="text-xs text-text-secondary leading-relaxed italic">{driftInterpretation}</p>
      </div>
    </div>
  )
}

// ── Main Component ───────────────────────────────────────────────────────────

export function ProbabilisticEngineDashboard({ breakdown, delta }: ProbabilisticEngineDashboardProps) {
  const [activeTab, setActiveTab] = useState<TabId>('ev')

  const evStability = breakdown.ev_stability
  const confidenceInt = breakdown.confidence_integrity
  const scenarioWeights = breakdown.scenario_weight_diagnostics
  const stopProb = breakdown.stop_probability
  const noiseFilter = breakdown.noise_filter

  // Has run-to-run drift data?
  const hasDriftData = delta != null && (
    delta.prior_stop_probability_pct != null ||
    delta.prior_confidence_pct != null ||
    delta.prior_stability_score != null
  )

  // Return null if no interpretability modules are present
  if (!evStability && !confidenceInt && !scenarioWeights && !stopProb && !noiseFilter) {
    return null
  }

  const allTabs: Array<{ id: TabId; label: string; icon: React.ReactNode; available: boolean }> = [
    { id: 'ev', label: 'EV Stability', icon: <Activity className="w-3.5 h-3.5" />, available: !!evStability },
    { id: 'confidence', label: 'Confidence', icon: <Shield className="w-3.5 h-3.5" />, available: !!confidenceInt },
    { id: 'scenarios', label: 'Scenario Weights', icon: <BarChart3 className="w-3.5 h-3.5" />, available: !!scenarioWeights },
    { id: 'stop', label: 'Stop Probability', icon: <TrendingDown className="w-3.5 h-3.5" />, available: !!stopProb },
    { id: 'noise', label: 'Noise Filter', icon: <AlertTriangle className="w-3.5 h-3.5" />, available: !!noiseFilter },
    { id: 'drift', label: 'Model Drift', icon: <GitCompare className="w-3.5 h-3.5" />, available: !!delta },
  ]
  const tabs = allTabs.filter(t => t.available)

  // Keep active tab valid if data isn't present
  const validTab = tabs.find(t => t.id === activeTab) ? activeTab : (tabs[0]?.id ?? 'ev')

  const borderClass = noiseBorderClass(noiseFilter)

  // Summary strip drift arrows
  const stopArrow = hasDriftData ? driftArrow(delta!.prior_stop_probability_pct, delta!.current_stop_probability_pct, true) : null
  const confArrow = hasDriftData ? driftArrow(delta!.prior_confidence_pct, delta!.current_confidence_pct, false) : null

  return (
    <div className="space-y-3">
      {/* Noise Regime Warning Banner (item 7 + item 8 visual drift) */}
      {noiseFilter?.noise_flag && noiseFilter.regime_warning && (
        <div className={`rounded-lg border px-4 py-3 flex items-start gap-3 ${
          noiseFilter.noise_regime === 'Noise Dominated'
            ? 'border-error/40 bg-error/8'
            : 'border-warning/40 bg-warning/8'
        }`}>
          <AlertTriangle className={`w-4 h-4 mt-0.5 shrink-0 ${
            noiseFilter.noise_regime === 'Noise Dominated' ? 'text-error' : 'text-warning'
          }`} />
          <p className="text-sm text-text-secondary leading-relaxed">{noiseFilter.regime_warning}</p>
        </div>
      )}

      {/* Significant model drift warning banner */}
      {hasDriftData && delta!.model_drift_level === 'Significant' && (
        <div className="rounded-lg border border-warning/40 bg-warning/8 px-4 py-3 flex items-start gap-3">
          <GitCompare className="w-4 h-4 mt-0.5 shrink-0 text-warning" />
          <div>
            <p className="text-sm font-semibold text-warning">Significant Model Drift Detected</p>
            <p className="text-xs text-text-secondary mt-0.5">
              Multiple probabilistic parameters shifted materially since the prior analysis. Review the Model Drift tab before acting on current outputs.
            </p>
          </div>
        </div>
      )}

      <Card className={`border ${borderClass || 'border-border'}`}>
        <CardHeader className="pb-3">
          <div className="flex items-start justify-between gap-2 flex-wrap">
            <CardTitle className="text-base font-semibold text-text-primary">
              Probabilistic Engine
            </CardTitle>
            <Tooltip>
              <TooltipTrigger asChild>
                <Info className="w-4 h-4 text-text-tertiary cursor-help mt-0.5" />
              </TooltipTrigger>
              <TooltipContent className="max-w-xs text-xs">
                Interpretability layer for the DVRG probabilistic model. Communicates what the model thinks,
                how stable that view is, and what is driving any sensitivity.
                No new math — pure transparency.
              </TooltipContent>
            </Tooltip>
          </div>

          {/* Always-visible summary strip */}
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 mt-3">
            {evStability && (
              <div className="rounded-md bg-surface-elevated p-2.5 text-center">
                <p className="text-xs text-text-tertiary mb-0.5">EV Stability</p>
                <p className={`text-xs font-semibold truncate ${stabilityColor(evStability.stability_class)}`}>
                  {evStability.stability_class}
                </p>
                <p className="text-xs text-text-tertiary">±{evStability.ev_sensitivity_band_pct.toFixed(1)}% band</p>
              </div>
            )}
            {confidenceInt && (
              <div className="rounded-md bg-surface-elevated p-2.5 text-center">
                <p className="text-xs text-text-tertiary mb-0.5">Model Confidence</p>
                <div className="flex items-center justify-center gap-1">
                  <p className={`text-xs font-semibold ${confidenceColor(confidenceInt.ev_confidence_level)}`}>
                    {confidenceInt.ev_confidence_level}
                  </p>
                  {confArrow}
                </div>
                <p className="text-xs text-text-tertiary">{confidenceInt.effective_confidence_pct.toFixed(0)}/100</p>
              </div>
            )}
            {scenarioWeights && (
              <div className="rounded-md bg-surface-elevated p-2.5 text-center">
                <p className="text-xs text-text-tertiary mb-0.5">Weight Rotation</p>
                <p className={`text-xs font-semibold ${
                  scenarioWeights.drift_label === 'Significant Rotation' ? 'text-warning' :
                  scenarioWeights.drift_label === 'Modest Rotation' ? 'text-amber-400' : 'text-success'
                }`}>
                  {scenarioWeights.drift_label}
                </p>
                <p className="text-xs text-text-tertiary">idx {scenarioWeights.scenario_rotation_index.toFixed(1)}</p>
              </div>
            )}
            {noiseFilter && (
              <div className="rounded-md bg-surface-elevated p-2.5 text-center">
                <p className="text-xs text-text-tertiary mb-0.5">
                  {hasDriftData ? (
                    <span className="flex items-center justify-center gap-1">
                      Stop Risk{stopArrow}
                    </span>
                  ) : 'Noise Regime'}
                </p>
                {hasDriftData && delta!.current_stop_probability_pct != null ? (
                  <>
                    <p className={`text-xs font-semibold ${
                      delta!.current_stop_probability_pct >= 50 ? 'text-error' :
                      delta!.current_stop_probability_pct >= 35 ? 'text-warning' :
                      delta!.current_stop_probability_pct >= 20 ? 'text-amber-400' : 'text-success'
                    }`}>
                      {delta!.current_stop_probability_pct.toFixed(0)}%
                    </p>
                    <p className="text-xs text-text-tertiary truncate">{noiseFilter.noise_regime}</p>
                  </>
                ) : (
                  <>
                    <p className={`text-xs font-semibold truncate ${noiseColor(noiseFilter.noise_regime)}`}>
                      {noiseFilter.noise_regime}
                    </p>
                    <p className="text-xs text-text-tertiary">{noiseFilter.noise_score}/100</p>
                  </>
                )}
              </div>
            )}
          </div>

          {/* Drift level badge in header when available */}
          {hasDriftData && delta!.model_drift_level && delta!.model_drift_level !== 'Stable' && (
            <div className="flex items-center gap-2 mt-2 pt-2 border-t border-border/30">
              <GitCompare className="w-3 h-3 text-text-tertiary" />
              <span className="text-[10px] text-text-tertiary">Run-to-run drift:</span>
              <span className={`text-[10px] font-bold ${driftLevelColor(delta!.model_drift_level)}`}>
                {delta!.model_drift_level}
              </span>
              {delta!.scenario_rotation_label && delta!.scenario_rotation_label !== 'STABLE' && (
                <span className={`text-[10px] font-bold ml-2 ${
                  delta!.scenario_rotation_label === 'SIGNIFICANT' ? 'text-warning' : 'text-amber-400'
                }`}>
                  · Scenario Rotation: {delta!.scenario_rotation_label}
                </span>
              )}
            </div>
          )}
        </CardHeader>

        <CardContent className="space-y-4">
          {/* Tabs */}
          {tabs.length > 1 && (
            <div className="flex gap-1 flex-wrap border-b border-border pb-2">
              {tabs.map(tab => (
                <button
                  key={tab.id}
                  onClick={() => setActiveTab(tab.id)}
                  className={`flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-md transition-colors ${
                    validTab === tab.id
                      ? 'bg-primary/10 text-primary'
                      : 'text-text-tertiary hover:text-text-secondary hover:bg-surface-elevated'
                  } ${tab.id === 'drift' && hasDriftData && delta!.model_drift_level === 'Significant' ? 'ring-1 ring-warning/40' : ''}`}
                >
                  {tab.icon}
                  {tab.label}
                </button>
              ))}
            </div>
          )}

          {/* Tab content */}
          {validTab === 'ev' && evStability && <EVStabilityPanel data={evStability} delta={delta} />}
          {validTab === 'confidence' && confidenceInt && <ConfidenceIntegrityPanel data={confidenceInt} delta={delta} />}
          {validTab === 'scenarios' && scenarioWeights && <ScenarioWeightsPanel data={scenarioWeights} delta={delta} />}
          {validTab === 'stop' && stopProb && <StopProbabilityPanel data={stopProb} delta={delta} />}
          {validTab === 'noise' && noiseFilter && <NoiseFilterPanel data={noiseFilter} delta={delta} />}
          {validTab === 'drift' && delta && <ModelDriftPanel delta={delta} />}
        </CardContent>
      </Card>
    </div>
  )
}
