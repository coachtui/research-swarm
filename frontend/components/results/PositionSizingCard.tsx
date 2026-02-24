'use client'

/**
 * PositionSizingCard — Noise-Adjusted Exposure Engine
 *
 * Renders a fully explainable position sizing recommendation derived from
 * the stock's signal regime diagnostics. Computes client-side via
 * computePositionSizing() using data already present in the analysis result.
 *
 * Inputs (extracted from SignalBreakdown + ConvictionPosition):
 *   - noise_score        ← signalBreakdown.noise_filter.noise_score
 *   - overall_sensitivity← signalBreakdown.model_sensitivity_attribution.overall_sensitivity
 *   - signal_dispersion_sigma ← signalBreakdown.signal_spread
 *   - stop_probability   ← signalBreakdown.stop_probability.effective_stop_probability_pct / 100
 *   - beta               ← signalBreakdown.factor_diagnostics.beta_estimate
 *   - classification     ← derived from convictionPosition.recommended_pct
 *   - flags              ← derived from signalBreakdown.has_divergence
 */

import { useMemo, useState } from 'react'
import { ChevronDown, ChevronUp, Sliders, Shield, AlertTriangle, Info } from 'lucide-react'
import { cn } from '@/lib/utils/cn'
import { computePositionSizing, defaultConfig } from '@/lib/engine/computePositionSizing'
import type { PositionSizingInput, PositionSizingOutput, MultiplierDetail } from '@/lib/engine/types'
import type { SignalBreakdown, ConvictionPosition } from '@/types/api'

// ─── Props ────────────────────────────────────────────────────────────────────

interface PositionSizingCardProps {
  ticker: string
  signalBreakdown?: SignalBreakdown | null
  convictionPosition?: ConvictionPosition | null
  /** Pass a custom portfolio size for the dollar calculator (default: asks user) */
  customPortfolioSize?: number
}

// ─── Helpers ──────────────────────────────────────────────────────────────────

/** Normalise ModelSensitivityAttribution title-case to engine uppercase */
function normaliseSensitivity(raw?: string): 'LOW' | 'MODERATE' | 'HIGH' {
  const v = (raw ?? '').toUpperCase()
  if (v === 'HIGH') return 'HIGH'
  if (v === 'LOW') return 'LOW'
  return 'MODERATE'
}

function multiplierColor(value: number): string {
  if (value >= 1.1) return 'text-success'
  if (value >= 1.0) return 'text-success/70'
  if (value >= 0.8) return 'text-warning'
  if (value >= 0.65) return 'text-orange-400'
  return 'text-error'
}

function weightColor(pct: number): string {
  if (pct >= 8) return 'text-success'
  if (pct >= 4) return 'text-warning'
  if (pct >= 1) return 'text-text-primary'
  return 'text-text-tertiary'
}

const MULTIPLIER_LABELS: Record<string, string> = {
  noise: 'Noise Regime',
  sensitivity: 'Model Sensitivity',
  dispersion: 'Signal Dispersion',
  stoprisk: 'Stop Risk',
  beta: 'Beta Adjustment',
  ev_percentile: 'EV Percentile',
}

const PORTFOLIO_SIZES = [10000, 50000, 100000]

// ─── Sub-component: single multiplier row ────────────────────────────────────

function MultiplierRow({
  name,
  detail,
}: {
  name: string
  detail: MultiplierDetail
}) {
  const label = MULTIPLIER_LABELS[name] ?? name
  const color = multiplierColor(detail.value)
  const isBoost = detail.value > 1.0
  const isNeutral = detail.value === 1.0
  const isCompress = detail.value < 1.0

  return (
    <div className="flex items-center gap-3 py-2 border-b border-border/40 last:border-0">
      {/* Name + bucket */}
      <div className="flex-1 min-w-0">
        <span className="text-xs font-medium text-text-secondary">{label}</span>
        <span className="ml-2 text-[10px] text-text-tertiary">·</span>
        <span className="ml-1 text-[10px] text-text-tertiary">{detail.bucket_label}</span>
      </div>

      {/* Mini direction indicator */}
      <span
        className={cn(
          'text-[10px] font-mono px-1.5 py-0.5 rounded',
          isBoost ? 'bg-success/10 text-success' :
          isNeutral ? 'bg-surface-elevated text-text-tertiary' :
          'bg-error/10 text-error'
        )}
      >
        {isBoost ? '↑' : isNeutral ? '→' : '↓'}
      </span>

      {/* Multiplier value */}
      <span className={cn('text-sm font-bold font-mono w-12 text-right tabular-nums', color)}>
        {detail.value.toFixed(2)}×
      </span>
    </div>
  )
}

// ─── Main component ───────────────────────────────────────────────────────────

export function PositionSizingCard({
  ticker,
  signalBreakdown,
  convictionPosition,
  customPortfolioSize,
}: PositionSizingCardProps) {
  const [explainOpen, setExplainOpen] = useState(false)
  const [portfolioInput, setPortfolioInput] = useState<string>(
    customPortfolioSize ? String(customPortfolioSize) : ''
  )

  // ── Build engine input from available signal data ──────────────────────────
  const engineInput = useMemo((): PositionSizingInput | null => {
    const noiseScore = signalBreakdown?.noise_filter?.noise_score
    const sensitivity = signalBreakdown?.model_sensitivity_attribution?.overall_sensitivity
    const sigma = signalBreakdown?.signal_spread
    const stopProbPct = signalBreakdown?.stop_probability?.effective_stop_probability_pct

    // Require core fields to compute
    if (
      noiseScore == null ||
      sigma == null ||
      stopProbPct == null
    ) {
      return null
    }

    // Classification: CORE if conviction >= 5%, else SATELLITE
    const recPct = convictionPosition?.recommended_pct ?? 0
    const classification = recPct >= 5 ? 'CORE' : 'SATELLITE'

    // Beta from factor diagnostics
    const beta = signalBreakdown?.factor_diagnostics?.beta_estimate

    // Flags: cap at satellite if has_divergence is active
    const hasDivergence = signalBreakdown?.has_divergence ?? false

    return {
      symbol: ticker,
      classification,
      noise_score: noiseScore,
      overall_sensitivity: normaliseSensitivity(sensitivity),
      signal_dispersion_sigma: sigma,
      stop_probability: stopProbPct / 100,
      ...(beta != null && beta > 0 ? { beta } : {}),
      flags: {
        signal_conflict_active: hasDivergence,
        cap_at_satellite: hasDivergence,
      },
    }
  }, [ticker, signalBreakdown, convictionPosition])

  // ── Compute output ─────────────────────────────────────────────────────────
  const output = useMemo((): PositionSizingOutput | null => {
    if (!engineInput) return null
    try {
      return computePositionSizing(engineInput, defaultConfig)
    } catch {
      return null
    }
  }, [engineInput])

  // ── Dollar calculator ──────────────────────────────────────────────────────
  const customSize = parseInt(portfolioInput.replace(/,/g, ''), 10)
  const customDollar =
    output && !isNaN(customSize) && customSize > 0
      ? Math.round(customSize * output.adjusted_weight)
      : null

  // ── Early return: no data ──────────────────────────────────────────────────
  if (!output) {
    return (
      <div className="rounded-lg border border-border/60 bg-surface/30 p-4">
        <div className="flex items-center gap-2 text-text-tertiary">
          <Sliders className="h-4 w-4" />
          <span className="text-xs">
            Noise-adjusted sizing unavailable — requires noise filter, dispersion, and stop
            probability diagnostics.
          </span>
        </div>
      </div>
    )
  }

  const sortedMultipliers = Object.entries(output.multipliers)

  return (
    <div className="rounded-lg border border-border bg-surface overflow-hidden">

      {/* ── Header ─────────────────────────────────────────────────────────── */}
      <div className="flex items-center justify-between px-4 py-3 bg-surface-elevated/50 border-b border-border/60">
        <div className="flex items-center gap-2">
          <Sliders className="h-4 w-4 text-text-tertiary" />
          <span className="text-xs font-semibold text-text-primary uppercase tracking-wide">
            Noise-Adjusted Exposure Engine
          </span>
        </div>
        <div className="flex items-center gap-2">
          {output.cap_state.active && (
            <span className="flex items-center gap-1 text-[10px] font-medium text-warning bg-warning/10 px-2 py-0.5 rounded-full">
              <Shield className="h-3 w-3" />
              Guardrail Active
            </span>
          )}
          <span className="text-[10px] text-text-tertiary font-mono">
            {output.config_version}
          </span>
        </div>
      </div>

      <div className="p-4 space-y-4">

        {/* ── Base weight + classification ────────────────────────────────── */}
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <span className="text-[10px] uppercase tracking-wider text-text-tertiary font-semibold">
              Base Weight
            </span>
            <span
              className={cn(
                'text-[10px] font-medium px-2 py-0.5 rounded-full',
                engineInput?.classification === 'CORE'
                  ? 'bg-primary/15 text-primary'
                  : 'bg-surface-elevated text-text-secondary border border-border'
              )}
            >
              {engineInput?.classification ?? '—'}
            </span>
          </div>
          <span className="text-sm font-bold text-text-primary font-mono">
            {((output.base_weight) * 100).toFixed(0)}%
          </span>
        </div>

        {/* ── Multiplier breakdown ────────────────────────────────────────── */}
        <div className="rounded-lg border border-border/60 bg-surface/40 px-3 py-1">
          <p className="text-[10px] uppercase tracking-wider text-text-tertiary font-semibold pt-2 pb-1">
            Multipliers
          </p>
          {sortedMultipliers.map(([name, detail]) => (
            <MultiplierRow key={name} name={name} detail={detail} />
          ))}

          {/* Product line */}
          <div className="flex items-center justify-between pt-2 pb-1 border-t border-border/40 mt-1">
            <span className="text-[10px] text-text-tertiary font-mono">
              Product of multipliers
            </span>
            <span className="text-xs font-bold font-mono text-text-secondary">
              {output.product_of_multipliers.toFixed(4)}×
            </span>
          </div>
        </div>

        {/* ── Final weight (hero) ──────────────────────────────────────────── */}
        <div className="rounded-lg border border-border bg-surface p-4 text-center">
          <p className="text-[10px] uppercase tracking-widest text-text-tertiary font-semibold mb-1">
            Recommended Position Weight
          </p>
          <div className="flex items-baseline justify-center gap-1">
            <span className={cn('text-4xl font-bold tabular-nums', weightColor(output.adjusted_weight_pct))}>
              {output.adjusted_weight_pct.toFixed(2)}
            </span>
            <span className="text-xl font-semibold text-text-tertiary">%</span>
          </div>
          <p className="text-[10px] text-text-tertiary mt-1">
            {output.base_weight * 100}% × {output.product_of_multipliers.toFixed(4)}× multiplier
          </p>
          {output.cap_state.active && (
            <p className="text-[10px] text-warning mt-1 flex items-center justify-center gap-1">
              <AlertTriangle className="h-3 w-3" />
              {output.cap_state.reason}
            </p>
          )}
        </div>

        {/* ── Dollar exposure examples ─────────────────────────────────────── */}
        <div className="space-y-2">
          <p className="text-[10px] uppercase tracking-wider text-text-tertiary font-semibold">
            Dollar Exposure Calculator
          </p>
          <div className="rounded-lg border border-border/60 bg-surface/40 divide-y divide-border/30">
            {PORTFOLIO_SIZES.map((size) => (
              <div key={size} className="flex items-center justify-between px-3 py-2 text-xs">
                <span className="text-text-tertiary">
                  ${(size / 1000).toFixed(0)}K portfolio
                </span>
                <span className="font-semibold text-text-primary tabular-nums">
                  ${(output.exposure_examples[String(size)] ?? 0).toLocaleString()}
                </span>
              </div>
            ))}
          </div>

          {/* Custom size input */}
          <div className="flex items-center gap-2">
            <span className="text-[10px] text-text-tertiary whitespace-nowrap">Custom:</span>
            <div className="flex-1 flex items-center gap-1">
              <span className="text-xs text-text-tertiary">$</span>
              <input
                type="text"
                inputMode="numeric"
                placeholder="Enter portfolio size"
                value={portfolioInput}
                onChange={(e) => setPortfolioInput(e.target.value)}
                className="flex-1 text-xs bg-surface border border-border rounded px-2 py-1 text-text-primary placeholder-text-tertiary focus:outline-none focus:ring-1 focus:ring-primary/50"
              />
            </div>
            {customDollar != null && (
              <span className="text-xs font-semibold text-primary whitespace-nowrap">
                → ${customDollar.toLocaleString()}
              </span>
            )}
          </div>
        </div>

        {/* ── Notes ────────────────────────────────────────────────────────── */}
        {output.notes.length > 0 && (
          <ul className="space-y-1">
            {output.notes.map((note, i) => (
              <li key={i} className="text-[11px] text-text-tertiary flex items-start gap-1.5">
                <span className="mt-0.5 text-text-tertiary/50 flex-shrink-0">·</span>
                {note}
              </li>
            ))}
          </ul>
        )}

        {/* ── Collapsible explain panel ─────────────────────────────────────── */}
        <div className="rounded-lg border border-border/60 overflow-hidden">
          <button
            onClick={() => setExplainOpen((v) => !v)}
            className="w-full flex items-center justify-between px-3 py-2.5 bg-surface-elevated/30 hover:bg-surface-elevated/50 transition-colors text-left"
          >
            <div className="flex items-center gap-1.5">
              <Info className="h-3.5 w-3.5 text-text-tertiary" />
              <span className="text-[11px] font-medium text-text-secondary">
                Explain Sizing Rationale
              </span>
            </div>
            {explainOpen
              ? <ChevronUp className="h-3.5 w-3.5 text-text-tertiary" />
              : <ChevronDown className="h-3.5 w-3.5 text-text-tertiary" />
            }
          </button>

          {explainOpen && (
            <div className="px-3 py-3 bg-surface/20 border-t border-border/40 space-y-3">
              <p className="text-[11px] text-text-tertiary leading-relaxed">
                The recommended weight is computed as:
              </p>
              <div className="rounded bg-surface-elevated/50 p-3 font-mono text-[10px] text-text-secondary leading-relaxed">
                <div className="text-text-tertiary mb-1">AdjustedWeight =</div>
                <div className="pl-2">
                  BaseWeight ({(output.base_weight * 100).toFixed(0)}%)
                  <br />
                  {sortedMultipliers.map(([name, detail]) => (
                    <span key={name}>
                      {' '}× M_{name} ({detail.value.toFixed(2)})
                      <br />
                    </span>
                  ))}
                  {'='}&nbsp;
                  <span className="font-bold text-text-primary">
                    {output.adjusted_weight_pct.toFixed(2)}%
                  </span>
                </div>
              </div>

              {/* Per-multiplier rationale */}
              <div className="space-y-2">
                {sortedMultipliers.map(([name, detail]) => (
                  <div key={name} className="text-[11px]">
                    <span className="font-semibold text-text-secondary">
                      {MULTIPLIER_LABELS[name] ?? name}
                    </span>
                    <span className={cn('ml-2 font-mono', multiplierColor(detail.value))}>
                      {detail.value.toFixed(2)}×
                    </span>
                    <p className="text-text-tertiary mt-0.5 leading-relaxed">{detail.reason}</p>
                  </div>
                ))}
              </div>

              {output.cap_state.active && (
                <div className="rounded bg-warning/10 border border-warning/20 px-3 py-2">
                  <p className="text-[11px] text-warning font-medium">Guardrail Applied</p>
                  <p className="text-[10px] text-warning/80 mt-0.5">{output.cap_state.reason}</p>
                </div>
              )}

              <p className="text-[10px] text-text-tertiary/60 italic">
                All thresholds from config {output.config_version}. Sizes are heuristic
                approximations — not a substitute for full portfolio risk management.
              </p>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
