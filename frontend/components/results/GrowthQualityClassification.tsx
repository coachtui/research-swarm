'use client'

import type { MoatBreakdown, FundamentalistOutput } from '@/types/api'

interface GrowthQualityClassificationProps {
  moatBreakdown?: MoatBreakdown | null
  fundamentalistOutput?: FundamentalistOutput | null
  qualityScore?: number | null
  moatScore?: number | null
}

/**
 * GrowthQualityClassification — compounding characterization.
 *
 * Shows company classification (Durable Growth Compounder / Quality Compounder / etc.),
 * quality score, revenue growth, margin trend, FCF conversion, balance sheet strength.
 *
 * All data sourced from existing full_output — no new API calls.
 */
export function GrowthQualityClassification({
  moatBreakdown,
  fundamentalistOutput,
  qualityScore,
  moatScore,
}: GrowthQualityClassificationProps) {
  if (!moatBreakdown && !fundamentalistOutput) return null

  // ── Classification Logic ──────────────────────────────────────────────────
  // quality ≥ 7 AND growth ≥ 10% → "Durable Growth Compounder"
  // quality ≥ 7 AND growth < 10% → "Durable Quality Compounder"
  // quality ≥ 5 AND growth ≥ 20% → "High-Growth Emerging Compounder"
  // default → "Quality Assessment Pending"

  const quality = qualityScore ?? moatScore ?? 0
  const revenueGrowthYoy = fundamentalistOutput?.financial_metrics?.revenue_growth_yoy ?? 0

  let classificationLabel = 'Quality Assessment Pending'
  let classificationColor = 'text-text-tertiary'

  if (quality >= 7 && revenueGrowthYoy >= 10) {
    classificationLabel = 'Durable Growth Compounder'
    classificationColor = 'text-success'
  } else if (quality >= 7 && revenueGrowthYoy < 10) {
    classificationLabel = 'Durable Quality Compounder'
    classificationColor = 'text-success'
  } else if (quality >= 5 && revenueGrowthYoy >= 20) {
    classificationLabel = 'High-Growth Emerging Compounder'
    classificationColor = 'text-primary'
  }

  // ── Sub-metrics ──────────────────────────────────────────────────────────

  // Margin Trend: the categorical read the valuation actually used. Falls back
  // to the quarterly gross-margin series for reports saved before dcf_inputs
  // was serialized, so older analyses stop showing a permanent em dash.
  const marginTrend = fundamentalistOutput?.dcf_inputs?.operating_margin_trend ?? null
  let marginTrendLabel = '—'
  if (marginTrend === 'expanding') marginTrendLabel = 'Expanding'
  else if (marginTrend === 'stable') marginTrendLabel = 'Stable'
  else if (marginTrend === 'contracting') marginTrendLabel = 'Contracting'
  else {
    const series = (fundamentalistOutput?.quarterly_trends?.margin_trend ?? []).filter(
      (m): m is number => typeof m === 'number'
    )
    if (series.length >= 2) {
      // Compare the latest margin against the mean of the earlier quarters;
      // ±0.5pp of gross margin is the same threshold the backend uses.
      const latest = series[series.length - 1]
      const prior = series.slice(0, -1)
      const priorAvg = prior.reduce((a, b) => a + b, 0) / prior.length
      const delta = latest - priorAvg
      if (delta > 0.5) marginTrendLabel = 'Expanding'
      else if (delta < -0.5) marginTrendLabel = 'Contracting'
      else marginTrendLabel = 'Stable'
    }
  }

  // FCF Conversion: (free_cash_flow / revenue) * 100
  let fcfConversion = '—'
  if (
    fundamentalistOutput?.financial_metrics?.free_cash_flow &&
    fundamentalistOutput?.financial_metrics?.revenue &&
    fundamentalistOutput.financial_metrics.revenue > 0
  ) {
    const fcf = fundamentalistOutput.financial_metrics.free_cash_flow
    const revenue = fundamentalistOutput.financial_metrics.revenue
    const conversion = (fcf / revenue) * 100
    fcfConversion = `${conversion.toFixed(1)}%`
  }

  // Balance Sheet: from financial_health component score
  let balanceSheetLabel = '—'
  let balanceSheetColor = 'text-text-secondary'
  const bsScore = moatBreakdown?.financial_health ?? null
  if (bsScore !== null) {
    if (bsScore >= 7) {
      balanceSheetLabel = 'Strong'
      balanceSheetColor = 'text-success'
    } else if (bsScore >= 4) {
      balanceSheetLabel = 'Moderate'
      balanceSheetColor = 'text-warning'
    } else {
      balanceSheetLabel = 'Levered'
      balanceSheetColor = 'text-error'
    }
  }

  return (
    <div className="rounded-xl border border-border/60 bg-surface/30 overflow-hidden">
      <div className="px-5 py-4 space-y-4">
        {/* Classification header */}
        <div>
          <p className="text-[10px] font-semibold uppercase tracking-wider text-text-tertiary">
            Company Classification
          </p>
          <p className={`text-lg font-bold mt-1.5 ${classificationColor}`}>
            {classificationLabel}
          </p>
        </div>

        {/* Metrics grid — 2 rows × 3 cols */}
        <div className="grid grid-cols-3 gap-3">
          <ClassificationTile label="Quality Score" value={quality.toFixed(1)} sublabel="/ 10" />
          <ClassificationTile
            label="Revenue Growth"
            value={`${revenueGrowthYoy.toFixed(1)}%`}
            sublabel="YoY"
          />
          <ClassificationTile label="Margin Trend" value={marginTrendLabel} />

          <ClassificationTile label="FCF Conversion" value={fcfConversion} />
          <ClassificationTile label="Balance Sheet" value={balanceSheetLabel} valueColor={balanceSheetColor} />
          <ClassificationTile label="Moat Score" value={moatScore != null ? moatScore.toFixed(1) : '—'} sublabel="/ 10" />
        </div>
      </div>
    </div>
  )
}

function ClassificationTile({
  label,
  value,
  sublabel,
  valueColor,
}: {
  label: string
  value: string
  sublabel?: string
  valueColor?: string
}) {
  return (
    <div className="rounded-lg border border-border/40 bg-surface-elevated/50 px-3 py-2.5">
      <p className="text-[10px] font-semibold uppercase tracking-wider text-text-tertiary">{label}</p>
      <p className={`text-sm font-bold mt-0.5 font-mono tabular-nums ${valueColor || 'text-text-primary'}`}>
        {value}
      </p>
      {sublabel && <p className="text-[10px] text-text-tertiary mt-0.5">{sublabel}</p>}
    </div>
  )
}
