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
 * Visual Drift Encoding (item 8):
 *   - EV flicker band: sensitivity range rendered as a visual band
 *   - Confidence decay coloring: card borders/backgrounds reflect confidence level
 *   - Noise regime banner: warning strip at top when noise_flag is true
 *   - Sensitivity warning gradient on EV stability display
 *
 * Design constraints:
 *   - Probabilistic framing throughout — no deterministic language
 *   - Institutional tone — outputs communicate What / How Stable / Why Changed
 *   - Minimal cognitive overload — progressive disclosure, summary strip always visible
 */

import { useState } from 'react'
import { AlertTriangle, Shield, Activity, TrendingDown, BarChart3, Info } from 'lucide-react'
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
} from '@/types/api'

interface ProbabilisticEngineDashboardProps {
  breakdown: SignalBreakdown
}

type TabId = 'ev' | 'confidence' | 'scenarios' | 'stop' | 'noise'

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

function EVStabilityPanel({ data }: { data: EVStabilityClass }) {
  const bandHalf = data.ev_sensitivity_band_pct
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
                data.stability_class === 'Noise Dominated' ? 'bg-error' :
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
          value={`${data.signal_driver_score}/10`}
          className={data.signal_driver_score >= 4 ? 'text-warning' : 'text-text-secondary'}
        />
        <MetricRow
          label="Market-side instability score"
          value={`${data.market_driver_score}/10`}
          className={data.market_driver_score >= 4 ? 'text-warning' : 'text-text-secondary'}
        />
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

function ConfidenceIntegrityPanel({ data }: { data: ConfidenceIntegrity }) {
  return (
    <div className="space-y-4">
      {/* EV vs Confidence separation — key visual */}
      <div className="grid grid-cols-2 gap-3">
        <div className="rounded-md bg-surface-elevated p-4 text-center">
          <p className="text-xs text-text-tertiary mb-1">EV Signal</p>
          <p className="text-lg font-bold text-text-primary">Intact</p>
          <p className="text-xs text-text-tertiary mt-1">Directional estimate retained</p>
        </div>
        <div className="rounded-md bg-surface-elevated p-4 text-center">
          <p className="text-xs text-text-tertiary mb-1">Confidence in EV</p>
          <p className={`text-lg font-bold ${confidenceColor(data.ev_confidence_level)}`}>
            {data.ev_confidence_level}
          </p>
          <p className="text-xs text-text-tertiary mt-1">{data.effective_confidence_pct.toFixed(0)}/100</p>
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

function ScenarioWeightsPanel({ data }: { data: ScenarioWeightDiagnostics }) {
  const scenarios = [
    { label: 'Bear (Risk)', model: data.model_bear_prob, effective: data.effective_bear_prob, color: 'bg-error' },
    { label: 'Base (Continuation)', model: data.model_base_prob, effective: data.effective_base_prob, color: 'bg-primary' },
    { label: 'Bull (Re-rating)', model: data.model_bull_prob, effective: data.effective_bull_prob, color: 'bg-success' },
  ]

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
        {scenarios.map(s => (
          <div key={s.label} className="space-y-1">
            <div className="flex justify-between text-xs">
              <span className="text-text-tertiary">{s.label}</span>
              <span className="text-text-secondary">
                Model {(s.model * 100).toFixed(0)}% → Effective {(s.effective * 100).toFixed(0)}%
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
        ))}
      </div>

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

function StopProbabilityPanel({ data }: { data: StopProbabilityDecomposition }) {
  const components = [
    { label: 'Base Stop Risk', value: data.base_stop_risk_pct, note: 'Bear scenario prior (25%)' },
    { label: 'Volatility Pressure', value: data.volatility_pressure_pct, note: data.volatility_pressure_drivers.join(', ') || 'Stable regime' },
    { label: 'Trend Modifier', value: data.trend_modifier_pct, note: 'Technical momentum alignment' },
    { label: 'Support Modifier', value: data.support_modifier_pct, note: 'Aggregate signal score proxy' },
  ]

  return (
    <div className="space-y-4">
      {/* Headline */}
      <div className="flex items-center gap-3">
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
        {components.map((c, i) => (
          <div key={i} className="flex items-start justify-between gap-3 text-xs py-1.5 border-b border-border/30 last:border-0">
            <div>
              <p className="text-text-secondary font-medium">{c.label}</p>
              {c.note && <p className="text-text-tertiary mt-0.5">{c.note}</p>}
            </div>
            <span className={`font-mono font-semibold shrink-0 ${
              c.value > 0 ? 'text-error' : c.value < 0 ? 'text-success' : 'text-text-tertiary'
            }`}>
              {c.value > 0 ? '+' : ''}{c.value.toFixed(1)}%
            </span>
          </div>
        ))}
        {/* Narrative */}
        <p className="text-xs text-text-tertiary font-mono pt-1 border-t border-border/30">
          {data.decomposition_narrative}
        </p>
      </div>

      {/* Regime note */}
      <div className="rounded-md bg-surface-elevated p-4">
        <SectionLabel>Regime Context</SectionLabel>
        <p className="text-sm text-text-secondary leading-relaxed">{data.regime_note}</p>
      </div>
    </div>
  )
}

// ── Noise Filter Panel ───────────────────────────────────────────────────────

function NoiseFilterPanel({ data }: { data: NoiseFilter }) {
  return (
    <div className="space-y-4">
      {/* Headline */}
      <div className="flex items-center gap-3">
        <p className={`text-2xl font-bold ${noiseColor(data.noise_regime)}`}>{data.noise_regime}</p>
        <div className="text-right">
          <p className="text-xs text-text-tertiary">Noise Score</p>
          <p className={`text-lg font-bold ${noiseColor(data.noise_regime)}`}>{data.noise_score}/100</p>
        </div>
      </div>

      {/* Noise score bar */}
      <div className="h-2 rounded-full bg-border/40 overflow-hidden">
        <div
          className={`h-full rounded-full ${
            data.noise_regime === 'Noise Dominated' ? 'bg-error' :
            data.noise_regime === 'High Noise' ? 'bg-warning' :
            data.noise_regime === 'Moderate Noise' ? 'bg-amber-400' :
            'bg-success'
          }`}
          style={{ width: `${data.noise_score}%` }}
        />
      </div>

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

// ── Main Component ───────────────────────────────────────────────────────────

export function ProbabilisticEngineDashboard({ breakdown }: ProbabilisticEngineDashboardProps) {
  const [activeTab, setActiveTab] = useState<TabId>('ev')

  const evStability = breakdown.ev_stability
  const confidenceInt = breakdown.confidence_integrity
  const scenarioWeights = breakdown.scenario_weight_diagnostics
  const stopProb = breakdown.stop_probability
  const noiseFilter = breakdown.noise_filter

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
  ]
  const tabs = allTabs.filter(t => t.available)

  // Keep active tab valid if data isn't present
  const validTab = tabs.find(t => t.id === activeTab) ? activeTab : (tabs[0]?.id ?? 'ev')

  const borderClass = noiseBorderClass(noiseFilter)

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
                <p className={`text-xs font-semibold ${confidenceColor(confidenceInt.ev_confidence_level)}`}>
                  {confidenceInt.ev_confidence_level}
                </p>
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
                <p className="text-xs text-text-tertiary mb-0.5">Noise Regime</p>
                <p className={`text-xs font-semibold truncate ${noiseColor(noiseFilter.noise_regime)}`}>
                  {noiseFilter.noise_regime}
                </p>
                <p className="text-xs text-text-tertiary">{noiseFilter.noise_score}/100</p>
              </div>
            )}
          </div>
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
                  }`}
                >
                  {tab.icon}
                  {tab.label}
                </button>
              ))}
            </div>
          )}

          {/* Tab content */}
          {validTab === 'ev' && evStability && <EVStabilityPanel data={evStability} />}
          {validTab === 'confidence' && confidenceInt && <ConfidenceIntegrityPanel data={confidenceInt} />}
          {validTab === 'scenarios' && scenarioWeights && <ScenarioWeightsPanel data={scenarioWeights} />}
          {validTab === 'stop' && stopProb && <StopProbabilityPanel data={stopProb} />}
          {validTab === 'noise' && noiseFilter && <NoiseFilterPanel data={noiseFilter} />}
        </CardContent>
      </Card>
    </div>
  )
}
