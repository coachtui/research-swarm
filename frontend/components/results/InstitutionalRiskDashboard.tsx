'use client'

/**
 * Institutional Risk System — Portfolio Decision Engine
 *
 * 5-module analytical dashboard extending the DVRG framework:
 *   1. Factor & Exposure Diagnostics
 *   2. Volatility Regime Dynamics
 *   3. Liquidity & Microstructure
 *   4. Model Error Sensitivity Attribution
 *   5. Portfolio Action Panel (Decision Translation Layer)
 *
 * Design constraints preserved:
 *   - Probabilistic framing throughout — no deterministic language
 *   - Institutional tone — no buy/sell signals
 *   - Regime-conditioned interpretation for every metric
 *   - Progressive disclosure — summary strip always visible, details on demand
 */

import { useState } from 'react'
import { Info } from 'lucide-react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip'
import type {
  SignalBreakdown,
  FactorDiagnostics,
  VolatilityRegimeDynamics,
  LiquidityMicrostructure,
  ModelSensitivityAttribution,
  PortfolioAction,
} from '@/types/api'

interface InstitutionalRiskDashboardProps {
  breakdown: SignalBreakdown
}

type TabId = 'action' | 'factor' | 'volatility' | 'liquidity' | 'sensitivity'

// ── Color helpers ──────────────────────────────────────────────────────────

function sensitivityColor(level: 'High' | 'Moderate' | 'Low' | string) {
  if (level === 'High') return 'text-error'
  if (level === 'Moderate') return 'text-warning'
  return 'text-success'
}

function allocationColor(bias: string) {
  if (bias === 'Add') return 'text-success'
  if (bias === 'Hold') return 'text-warning'
  if (bias === 'Reduce') return 'text-error'
  return 'text-error'
}

function allocationVariant(bias: string): 'success' | 'warning' | 'error' | 'default' {
  if (bias === 'Add') return 'success'
  if (bias === 'Hold') return 'warning'
  return 'error'
}

function riskColor(level: string) {
  if (level === 'High') return 'text-error'
  if (level === 'Moderate') return 'text-warning'
  return 'text-success'
}

function volTrendColor(trend: string) {
  if (trend === 'Expanding') return 'text-error'
  if (trend === 'Contracting') return 'text-success'
  return 'text-text-secondary'
}

function interactionColor(interaction: string) {
  if (interaction === 'Concentrating') return 'text-error'
  if (interaction === 'Diversifying') return 'text-success'
  return 'text-text-secondary'
}

function accDistColor(bias: string) {
  if (bias.includes('Accumulation')) return 'text-success'
  if (bias.includes('Distribution')) return 'text-error'
  return 'text-text-secondary'
}

// ── Metric row: compact label + value + optional note ──────────────────────

function MetricRow({
  label,
  value,
  valueClass = 'text-text-secondary',
  note,
  tooltip,
}: {
  label: string
  value: string
  valueClass?: string
  note?: string
  tooltip?: string
}) {
  return (
    <div className="py-1.5 border-b border-border/30 last:border-0">
      <div className="flex items-baseline justify-between gap-2">
        <span className="text-xs text-text-tertiary shrink-0">{label}</span>
        <span className={`text-xs font-semibold text-right ${valueClass}`}>{value}</span>
      </div>
      {note && (
        <p className="text-[10px] text-text-tertiary/60 leading-relaxed mt-0.5">{note}</p>
      )}
    </div>
  )
}

// ── Grid cell: compact card for 2-col grids ────────────────────────────────

function GridCell({
  label,
  value,
  valueClass = 'text-text-secondary',
  note,
}: {
  label: string
  value: string
  valueClass?: string
  note?: string
}) {
  return (
    <div className="rounded border border-border/40 bg-surface-elevated px-2.5 py-2">
      <div className="text-[9px] uppercase tracking-wider text-text-tertiary/70 mb-0.5 font-medium">{label}</div>
      <div className={`text-xs font-semibold ${valueClass}`}>{value}</div>
      {note && <p className="text-[10px] text-text-tertiary/70 mt-0.5 leading-tight">{note}</p>}
    </div>
  )
}

// ══════════════════════════════════════════════════════════════════════════════
// MODULE 1 — Factor & Exposure Diagnostics
// ══════════════════════════════════════════════════════════════════════════════

function FactorDiagnosticsPanel({ fd }: { fd: FactorDiagnostics }) {
  return (
    <div className="space-y-4">
      {/* Factor loading grid */}
      <div>
        <p className="text-[10px] uppercase tracking-wider text-text-tertiary/70 mb-2 font-semibold">
          Factor Loading Estimates
        </p>
        <div className="grid grid-cols-2 gap-2">
          <GridCell
            label="Beta Estimate"
            value={`${fd.beta_estimate.toFixed(2)} — ${fd.beta_label}`}
            valueClass={
              fd.beta_label === 'High' ? 'text-error' :
              fd.beta_label === 'Above-Market' ? 'text-warning' :
              fd.beta_label === 'Below-Market' ? 'text-success' :
              'text-text-secondary'
            }
            note="Sector baseline + momentum signal adjustment"
          />
          <GridCell
            label="Growth Loading"
            value={`${fd.growth_factor_loading.toFixed(1)}/10 — ${fd.growth_factor_label}`}
            valueClass={fd.growth_factor_label === 'High' ? 'text-warning' : fd.growth_factor_label === 'Low' ? 'text-success' : 'text-text-secondary'}
            note="Derived from VGM growth score"
          />
          <GridCell
            label="Momentum Loading"
            value={`${fd.momentum_factor_loading.toFixed(1)}/10`}
            note={fd.momentum_factor_label}
          />
          <GridCell
            label="Quality Proxy"
            value={`${fd.quality_factor_proxy.toFixed(1)}/10`}
            valueClass={
              fd.quality_factor_label.startsWith('High') ? 'text-success' :
              fd.quality_factor_label.startsWith('Low') ? 'text-error' :
              'text-text-secondary'
            }
            note={fd.quality_factor_label}
          />
        </div>
      </div>

      {/* Risk interaction */}
      <div>
        <p className="text-[10px] uppercase tracking-wider text-text-tertiary/70 mb-2 font-semibold">
          Portfolio Interaction
        </p>
        <div className="grid grid-cols-2 gap-2">
          <GridCell
            label="Portfolio Interaction"
            value={fd.portfolio_interaction}
            valueClass={interactionColor(fd.portfolio_interaction)}
            note={fd.portfolio_interaction_note}
          />
          <GridCell
            label="Vol Sensitivity"
            value={fd.vol_sensitivity}
            valueClass={sensitivityColor(fd.vol_sensitivity)}
            note={fd.vol_sensitivity_note}
          />
          <GridCell
            label="Crowding Proxy"
            value={fd.crowding_proxy}
            valueClass={
              fd.crowding_proxy === 'Elevated' ? 'text-error' :
              fd.crowding_proxy === 'Moderate' ? 'text-warning' :
              fd.crowding_proxy === 'Low' ? 'text-success' : 'text-text-tertiary'
            }
            note={fd.crowding_proxy_note}
          />
          <GridCell
            label="Correlation Sensitivity"
            value={fd.correlation_sensitivity}
            valueClass={sensitivityColor(fd.correlation_sensitivity)}
          />
        </div>
      </div>

      {/* Regime sensitivity flags */}
      {fd.regime_sensitivity_flags.length > 0 && (
        <div>
          <p className="text-[10px] uppercase tracking-wider text-text-tertiary/70 mb-1.5 font-semibold">
            Regime Sensitivity Flags
          </p>
          <ul className="space-y-1">
            {fd.regime_sensitivity_flags.map((flag, i) => (
              <li key={i} className="flex items-start gap-1.5 text-[11px] text-text-tertiary">
                <span className={`mt-0.5 shrink-0 ${flag.startsWith('No elevated') ? 'text-success' : 'text-warning'}`}>
                  {flag.startsWith('No elevated') ? '✓' : '◆'}
                </span>
                <span>{flag}</span>
              </li>
            ))}
          </ul>
        </div>
      )}

      <p className="text-[10px] text-text-tertiary/50 italic leading-relaxed">{fd.estimation_note}</p>
    </div>
  )
}

// ══════════════════════════════════════════════════════════════════════════════
// MODULE 2 — Volatility Regime Dynamics
// ══════════════════════════════════════════════════════════════════════════════

function VolatilityRegimePanel({ vrd }: { vrd: VolatilityRegimeDynamics }) {
  return (
    <div className="space-y-4">
      {/* Regime header */}
      <div className="px-3 py-2 rounded-md bg-surface-elevated border border-border/60">
        <span className={`text-xs font-semibold ${volTrendColor(vrd.vol_trend)}`}>
          {vrd.regime_label}
        </span>
        <p className="text-[11px] text-text-tertiary leading-relaxed mt-0.5">{vrd.vol_trend_note}</p>
      </div>

      {/* Vol state grid */}
      <div className="grid grid-cols-2 gap-2">
        <GridCell
          label="Vol Trend"
          value={vrd.vol_trend}
          valueClass={volTrendColor(vrd.vol_trend)}
        />
        <GridCell
          label="Implied/Realized Spread"
          value={vrd.implied_realized_spread}
          valueClass={
            vrd.implied_realized_spread === 'Elevated' ? 'text-error' :
            vrd.implied_realized_spread === 'Compressed' ? 'text-warning' :
            'text-success'
          }
          note={vrd.implied_realized_note}
        />
        <GridCell
          label="Vol Compression Risk"
          value={vrd.compression_probability}
          valueClass={
            vrd.compression_probability === 'High' ? 'text-error' :
            vrd.compression_probability === 'Moderate' ? 'text-warning' :
            'text-success'
          }
          note={vrd.compression_note}
        />
        <GridCell
          label="Event Vol Condition"
          value={vrd.event_vol_condition ? 'Active' : 'Not Active'}
          valueClass={vrd.event_vol_condition ? 'text-warning' : 'text-success'}
          note={vrd.event_vol_note ?? undefined}
        />
      </div>

      {/* Model impact */}
      <div>
        <p className="text-[10px] uppercase tracking-wider text-text-tertiary/70 mb-1.5 font-semibold">
          Impact on Model Outputs
        </p>
        <div className="space-y-2">
          <div className="px-2.5 py-2 rounded border border-border/40 bg-surface-elevated">
            <span className="text-[9px] uppercase tracking-wider text-text-tertiary/70 block mb-0.5 font-medium">EV Reliability</span>
            <p className="text-[11px] text-text-tertiary leading-relaxed">{vrd.ev_reliability_impact}</p>
          </div>
          <div className="px-2.5 py-2 rounded border border-border/40 bg-surface-elevated">
            <span className="text-[9px] uppercase tracking-wider text-text-tertiary/70 block mb-0.5 font-medium">Stop Trigger Probability</span>
            <p className="text-[11px] text-text-tertiary leading-relaxed">{vrd.stop_probability_modifier}</p>
          </div>
        </div>
      </div>
    </div>
  )
}

// ══════════════════════════════════════════════════════════════════════════════
// MODULE 3 — Liquidity & Microstructure
// ══════════════════════════════════════════════════════════════════════════════

function LiquidityMicrostructurePanel({ lm }: { lm: LiquidityMicrostructure }) {
  return (
    <div className="space-y-4">
      {/* Accumulation/distribution header */}
      <div className="px-3 py-2 rounded-md bg-surface-elevated border border-border/60">
        <span className={`text-xs font-semibold ${accDistColor(lm.accumulation_distribution_bias)}`}>
          {lm.accumulation_distribution_bias}
        </span>
        <p className="text-[11px] text-text-tertiary leading-relaxed mt-0.5">{lm.bias_note}</p>
      </div>

      {/* Participation grid */}
      <div className="grid grid-cols-2 gap-2">
        <GridCell
          label="Volume Participation"
          value={lm.volume_participation}
          valueClass={
            lm.volume_participation === 'Above-ADV' ? 'text-success' :
            lm.volume_participation === 'Sub-ADV' ? 'text-error' :
            'text-text-secondary'
          }
          note={lm.volume_participation_note}
        />
        <GridCell
          label="Volume State"
          value={lm.volume_state}
          valueClass={
            lm.volume_state === 'Expansion' ? 'text-success' :
            lm.volume_state === 'Contraction' ? 'text-warning' :
            lm.volume_state === 'Suspect' ? 'text-error' :
            'text-text-secondary'
          }
        />
        <GridCell
          label="Thin-Volume Risk"
          value={lm.thin_volume_risk}
          valueClass={
            lm.thin_volume_risk === 'High' ? 'text-error' :
            lm.thin_volume_risk === 'Moderate' ? 'text-warning' :
            'text-success'
          }
          note={lm.thin_volume_note}
        />
        <GridCell
          label="Block Flow"
          value={lm.block_flow_proxy}
          valueClass={
            lm.block_flow_proxy === 'Active' ? 'text-success' :
            lm.block_flow_proxy === 'Limited' ? 'text-warning' :
            lm.block_flow_proxy === 'Unavailable' ? 'text-text-tertiary' :
            'text-text-secondary'
          }
          note={lm.block_flow_note}
        />
        <GridCell
          label="Spread / Impact"
          value={lm.spread_impact_proxy}
          valueClass={
            lm.spread_impact_proxy === 'Tight' ? 'text-success' :
            lm.spread_impact_proxy === 'Wide' ? 'text-warning' :
            'text-text-secondary'
          }
          note={lm.spread_impact_note}
        />
      </div>

      {/* Downstream effects */}
      <div>
        <p className="text-[10px] uppercase tracking-wider text-text-tertiary/70 mb-1.5 font-semibold">
          Downstream Effects
        </p>
        <div className="space-y-2">
          <div className="px-2.5 py-2 rounded border border-border/40 bg-surface-elevated">
            <span className="text-[9px] uppercase tracking-wider text-text-tertiary/70 block mb-0.5 font-medium">Stability Modifier</span>
            <p className="text-[11px] text-text-tertiary leading-relaxed">{lm.stability_modifier_effect}</p>
          </div>
          <div className="px-2.5 py-2 rounded border border-border/40 bg-surface-elevated">
            <span className="text-[9px] uppercase tracking-wider text-text-tertiary/70 block mb-0.5 font-medium">EV Confidence</span>
            <p className="text-[11px] text-text-tertiary leading-relaxed">{lm.ev_confidence_effect}</p>
          </div>
        </div>
      </div>
    </div>
  )
}

// ══════════════════════════════════════════════════════════════════════════════
// MODULE 4 — Model Sensitivity Attribution
// ══════════════════════════════════════════════════════════════════════════════

function ModelSensitivityPanel({ msa }: { msa: ModelSensitivityAttribution }) {
  return (
    <div className="space-y-4">
      {/* Overall + dominant driver */}
      <div className="px-3 py-2.5 rounded-md bg-surface-elevated border border-border/60">
        <div className="flex items-center gap-2 mb-1">
          <span className="text-[10px] uppercase tracking-wider text-text-tertiary/70 font-semibold">
            Overall Sensitivity
          </span>
          <span className={`text-xs font-bold ${sensitivityColor(msa.overall_sensitivity)}`}>
            {msa.overall_sensitivity}
          </span>
        </div>
        <div className="mb-1">
          <span className="text-[10px] text-text-tertiary">Dominant driver: </span>
          <span className="text-[10px] font-semibold text-text-secondary">{msa.dominant_driver}</span>
        </div>
        <p className="text-[11px] text-text-tertiary leading-relaxed">{msa.dominant_driver_rationale}</p>
      </div>

      {/* Driver ranking */}
      <div>
        <p className="text-[10px] uppercase tracking-wider text-text-tertiary/70 mb-2 font-semibold">
          Instability Driver Ranking
        </p>
        <div className="space-y-1.5">
          {msa.sensitivity_drivers.map((d) => (
            <div key={d.factor} className="flex items-start gap-2">
              <span className="text-[10px] text-text-tertiary/60 w-4 shrink-0 mt-0.5 text-right">
                #{d.rank}
              </span>
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-1.5">
                  <span className="text-[11px] text-text-secondary font-medium">{d.factor}</span>
                  <span className={`text-[9px] font-semibold px-1 rounded border ${
                    d.sensitivity === 'High' ? 'text-error border-error/30 bg-error/10' :
                    d.sensitivity === 'Moderate' ? 'text-warning border-warning/30 bg-warning/10' :
                    'text-success border-success/30 bg-success/10'
                  }`}>
                    {d.sensitivity}
                  </span>
                </div>
                <p className="text-[10px] text-text-tertiary/70 leading-relaxed mt-0.5">{d.elasticity_note}</p>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Confidence degradation + failure risk */}
      <div className="space-y-2">
        <div className="px-2.5 py-2 rounded border border-border/40 bg-surface-elevated">
          <span className="text-[9px] uppercase tracking-wider text-text-tertiary/70 block mb-0.5 font-medium">Confidence Degradation</span>
          <p className="text-[11px] text-text-tertiary leading-relaxed">{msa.confidence_degradation_rationale}</p>
        </div>
        <div className="px-2.5 py-2 rounded border border-border/40 bg-surface-elevated">
          <span className="text-[9px] uppercase tracking-wider text-text-tertiary/70 block mb-0.5 font-medium">Dominant Risk of Model Failure</span>
          <p className="text-[11px] text-text-tertiary leading-relaxed">{msa.model_failure_risk}</p>
        </div>
      </div>
    </div>
  )
}

// ══════════════════════════════════════════════════════════════════════════════
// MODULE 5 — Portfolio Action Panel (Decision Translation Layer)
// ══════════════════════════════════════════════════════════════════════════════

function PortfolioActionPanel({ pa }: { pa: PortfolioAction }) {
  return (
    <div className="space-y-4">
      {/* Primary decision strip */}
      <div className="grid grid-cols-3 gap-2">
        {/* Allocation bias */}
        <div className="col-span-1 rounded border border-border/40 bg-surface-elevated px-2.5 py-3 flex flex-col items-center gap-1">
          <span className="text-[9px] uppercase tracking-wider text-text-tertiary/70 font-medium">Allocation Bias</span>
          <span className={`text-lg font-bold ${allocationColor(pa.allocation_bias)}`}>
            {pa.allocation_bias}
          </span>
        </div>

        {/* Mandate fit */}
        <div className="col-span-2 rounded border border-border/40 bg-surface-elevated px-2.5 py-2">
          <span className="text-[9px] uppercase tracking-wider text-text-tertiary/70 block mb-0.5 font-medium">Mandate Fit</span>
          <span className="text-xs font-semibold text-text-secondary">{pa.mandate_fit}</span>
          <p className="text-[10px] text-text-tertiary/70 leading-tight mt-0.5">{pa.mandate_fit_rationale}</p>
        </div>
      </div>

      {/* Allocation note */}
      <div className="px-2.5 py-2 rounded border border-border/40 bg-surface-elevated">
        <span className="text-[9px] uppercase tracking-wider text-text-tertiary/70 block mb-0.5 font-medium">Allocation Rationale</span>
        <p className="text-[11px] text-text-tertiary leading-relaxed">{pa.allocation_bias_note}</p>
      </div>

      {/* Conviction + risk budget */}
      <div className="grid grid-cols-2 gap-2">
        <GridCell
          label={`Conviction Multiplier — ${pa.conviction_scaling_label}`}
          value={`${pa.conviction_scaling_multiplier.toFixed(2)}×`}
          valueClass={
            pa.conviction_scaling_multiplier >= 1.25 ? 'text-success' :
            pa.conviction_scaling_multiplier >= 1.0 ? 'text-text-secondary' :
            pa.conviction_scaling_multiplier >= 0.75 ? 'text-warning' :
            'text-error'
          }
          note={pa.conviction_scaling_rationale}
        />
        <GridCell
          label="Risk Budget Impact"
          value={pa.risk_budget_impact}
          valueClass={riskColor(pa.risk_budget_impact)}
          note={pa.risk_budget_note}
        />
      </div>

      {/* Conviction drivers */}
      {pa.conviction_multiplier_drivers.length > 0 && (
        <div>
          <p className="text-[10px] uppercase tracking-wider text-text-tertiary/70 mb-1 font-semibold">
            Conviction Multiplier Drivers
          </p>
          <ul className="space-y-0.5">
            {pa.conviction_multiplier_drivers.map((d, i) => (
              <li key={i} className="text-[11px] text-text-tertiary flex items-start gap-1.5">
                <span className="text-text-tertiary/50 shrink-0">·</span>
                <span>{d}</span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Sizing guidance */}
      <div className="px-2.5 py-2 rounded border border-border/40 bg-surface-elevated">
        <span className="text-[9px] uppercase tracking-wider text-text-tertiary/70 block mb-0.5 font-medium">Sizing Guidance</span>
        <p className="text-[11px] text-text-tertiary leading-relaxed">{pa.sizing_guidance}</p>
      </div>

      {/* Regime break condition */}
      <div className="px-2.5 py-2 rounded border border-error/20 bg-error/5">
        <span className="text-[9px] uppercase tracking-wider text-error/70 block mb-0.5 font-medium">What Breaks This Trade</span>
        <p className="text-[11px] text-text-tertiary leading-relaxed">{pa.regime_break_condition}</p>
      </div>
    </div>
  )
}

// ══════════════════════════════════════════════════════════════════════════════
// Main Component
// ══════════════════════════════════════════════════════════════════════════════

const TABS: { id: TabId; label: string; shortLabel: string }[] = [
  { id: 'action', label: 'Portfolio Action', shortLabel: 'Action' },
  { id: 'factor', label: 'Factor Profile', shortLabel: 'Factor' },
  { id: 'volatility', label: 'Vol Regime', shortLabel: 'Vol' },
  { id: 'liquidity', label: 'Liquidity', shortLabel: 'Liquidity' },
  { id: 'sensitivity', label: 'Model Sensitivity', shortLabel: 'Sensitivity' },
]

export function InstitutionalRiskDashboard({ breakdown }: InstitutionalRiskDashboardProps) {
  const [activeTab, setActiveTab] = useState<TabId>('action')

  const {
    factor_diagnostics: fd,
    volatility_regime_dynamics: vrd,
    liquidity_microstructure: lm,
    model_sensitivity_attribution: msa,
    portfolio_action: pa,
  } = breakdown

  // Only render if at least one module is available
  if (!fd && !vrd && !lm && !msa && !pa) return null

  // Summary strip values
  const allocationBias = pa?.allocation_bias ?? '—'
  const mandateFit = pa?.mandate_fit ?? '—'
  const overallSensitivity = msa?.overall_sensitivity ?? '—'
  const volTrend = vrd?.vol_trend ?? '—'

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
          <div>
            <div className="flex items-center gap-1.5">
              <CardTitle>Portfolio Risk Engine</CardTitle>
              <Tooltip>
                <TooltipTrigger asChild>
                  <button type="button" className="text-text-tertiary/40 hover:text-text-tertiary/70 transition-colors flex-shrink-0">
                    <Info className="h-3 w-3" />
                  </button>
                </TooltipTrigger>
                <TooltipContent className="max-w-xs" side="bottom">
                  <p className="text-xs font-medium leading-snug">Institutional risk system — five-module portfolio decision engine.</p>
                  <p className="text-xs leading-relaxed mt-1 opacity-75">
                    Extends the signal framework with factor diagnostics, volatility regime analysis,
                    liquidity microstructure, model sensitivity attribution, and decision translation.
                    All outputs are probabilistic — not price targets or buy/sell signals.
                  </p>
                </TooltipContent>
              </Tooltip>
            </div>
            <p className="text-[10px] text-text-tertiary/70 mt-0.5">
              Factor · Vol Regime · Liquidity · Model Sensitivity · Action
            </p>
          </div>

          {/* Always-visible summary strip */}
          <div className="flex flex-col items-end gap-1">
            {pa && (
              <Badge variant={allocationVariant(allocationBias)} className="text-xs font-semibold">
                {allocationBias}
              </Badge>
            )}
            {msa && (
              <span className={`text-[10px] font-medium ${sensitivityColor(overallSensitivity)}`}>
                Model: {overallSensitivity} sensitivity
              </span>
            )}
          </div>
        </div>
      </CardHeader>

      <CardContent>
        {/* Summary context bar */}
        <div className="mb-4 grid grid-cols-4 gap-2 text-center">
          {pa && (
            <div className="rounded bg-surface-elevated border border-border/40 px-1.5 py-1.5">
              <div className="text-[9px] uppercase tracking-wider text-text-tertiary/60 font-medium">Mandate</div>
              <div className="text-[10px] font-semibold text-text-secondary leading-tight mt-0.5">{mandateFit.replace(' ', '\u00a0')}</div>
            </div>
          )}
          {vrd && (
            <div className="rounded bg-surface-elevated border border-border/40 px-1.5 py-1.5">
              <div className="text-[9px] uppercase tracking-wider text-text-tertiary/60 font-medium">Vol Trend</div>
              <div className={`text-[10px] font-semibold leading-tight mt-0.5 ${volTrendColor(volTrend)}`}>{volTrend}</div>
            </div>
          )}
          {lm && (
            <div className="rounded bg-surface-elevated border border-border/40 px-1.5 py-1.5">
              <div className="text-[9px] uppercase tracking-wider text-text-tertiary/60 font-medium">Acc/Dist</div>
              <div className={`text-[10px] font-semibold leading-tight mt-0.5 ${accDistColor(lm.accumulation_distribution_bias)}`}>
                {lm.accumulation_distribution_bias.replace('Mild ', '')}
              </div>
            </div>
          )}
          {msa && (
            <div className="rounded bg-surface-elevated border border-border/40 px-1.5 py-1.5">
              <div className="text-[9px] uppercase tracking-wider text-text-tertiary/60 font-medium">Model Risk</div>
              <div className={`text-[10px] font-semibold leading-tight mt-0.5 ${sensitivityColor(overallSensitivity)}`}>{overallSensitivity}</div>
            </div>
          )}
        </div>

        {/* Tab navigation */}
        <div className="flex gap-1 mb-4 overflow-x-auto">
          {TABS.map((tab) => {
            const available =
              tab.id === 'action' ? !!pa :
              tab.id === 'factor' ? !!fd :
              tab.id === 'volatility' ? !!vrd :
              tab.id === 'liquidity' ? !!lm :
              !!msa
            if (!available) return null
            return (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={`text-xs px-2.5 py-1.5 rounded border transition-colors whitespace-nowrap shrink-0 ${
                  activeTab === tab.id
                    ? 'bg-primary/10 text-primary border-primary/30 font-semibold'
                    : 'text-text-tertiary border-border/40 hover:text-text-secondary hover:border-border'
                }`}
              >
                {tab.shortLabel}
              </button>
            )
          })}
        </div>

        {/* Tab content */}
        <div className="min-h-0">
          {activeTab === 'action' && pa && <PortfolioActionPanel pa={pa} />}
          {activeTab === 'factor' && fd && <FactorDiagnosticsPanel fd={fd} />}
          {activeTab === 'volatility' && vrd && <VolatilityRegimePanel vrd={vrd} />}
          {activeTab === 'liquidity' && lm && <LiquidityMicrostructurePanel lm={lm} />}
          {activeTab === 'sensitivity' && msa && <ModelSensitivityPanel msa={msa} />}
        </div>

        {/* Methodology note */}
        <p className="text-[10px] text-text-tertiary/40 italic mt-4 leading-relaxed">
          All outputs are probabilistic model estimates derived from signal data and VGM factor scores.
          Not investment advice. Regime classifications are heuristic approximations, not market-data-sourced measurements.
        </p>
      </CardContent>
    </Card>
  )
}
