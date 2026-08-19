'use client'

import { Globe, TrendingDown, TrendingUp, Minus } from 'lucide-react'
import type { MacroContext } from '@/types/report'

/**
 * MacroContextPanel — the market backdrop the analysis was written against,
 * plus the macro/geopolitical themes that have a concrete channel to this
 * company.
 *
 * The distinction the layout has to carry: "What's happening" is the shared,
 * company-neutral description scanned once for every ticker, while "Impact on
 * <TICKER>" is written specifically for this company. Presenting them as one
 * paragraph would make the shared half read as bespoke analysis, so they are
 * visually separated and the company-specific half is the one that gets weight.
 */
export function MacroContextPanel({
  macro,
  ticker,
}: {
  macro?: MacroContext | null
  ticker: string
}) {
  if (!macro) return null

  const themes = macro.themes ?? []
  const screened = macro.themes_considered ?? 0
  const leaders = macro.sector_leaders ?? []
  const laggards = macro.sector_laggards ?? []

  const regimeStyle = (regime?: string | null) => {
    switch (regime) {
      case 'risk-off':
        return 'text-danger border-danger/40 bg-danger/5'
      case 'risk-on':
        return 'text-success border-success/40 bg-success/5'
      default:
        return 'text-text-secondary border-border bg-surface-elevated/50'
    }
  }

  const directionIcon = (direction?: string) => {
    if (direction === 'headwind') return <TrendingDown className="h-3.5 w-3.5 text-danger" />
    if (direction === 'tailwind') return <TrendingUp className="h-3.5 w-3.5 text-success" />
    return <Minus className="h-3.5 w-3.5 text-text-tertiary" />
  }

  const materialityStyle = (level?: string | null) => {
    switch (level) {
      case 'high':
        return 'text-danger border-danger/40'
      case 'moderate':
        return 'text-warning border-warning/40'
      case 'low':
        return 'text-text-tertiary border-border'
      default:
        return 'text-text-tertiary border-border'
    }
  }

  const pct = (v?: number | null) =>
    typeof v === 'number' ? `${v >= 0 ? '+' : ''}${v.toFixed(1)}%` : null

  const marketStats: { label: string; value: string }[] = []
  if (pct(macro.market_return_1m)) marketStats.push({ label: 'S&P 1M', value: pct(macro.market_return_1m)! })
  if (pct(macro.market_return_3m)) marketStats.push({ label: 'S&P 3M', value: pct(macro.market_return_3m)! })
  if (typeof macro.vix_level === 'number') marketStats.push({ label: 'VIX', value: macro.vix_level.toFixed(1) })
  if (typeof macro.yield_curve_slope === 'number') {
    marketStats.push({
      label: 'Curve 10Y−3M',
      value: `${macro.yield_curve_slope >= 0 ? '+' : ''}${macro.yield_curve_slope.toFixed(2)}pp`,
    })
  }

  return (
    <div className="space-y-4">
      {/* ── Market regime + measured state ─────────────────────────────── */}
      <div>
        <div className="flex items-center gap-2 mb-2">
          <Globe className="h-3.5 w-3.5 text-text-tertiary" />
          <h4 className="text-[11px] font-semibold uppercase tracking-wider text-text-tertiary">
            Market Backdrop
          </h4>
          {macro.regime && (
            <span
              className={`text-[9px] font-semibold uppercase border rounded px-1.5 py-0.5 ${regimeStyle(macro.regime)}`}
            >
              {macro.regime}
            </span>
          )}
        </div>

        {marketStats.length > 0 && (
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 mb-2">
            {marketStats.map(stat => (
              <div key={stat.label} className="rounded-lg bg-surface-elevated/50 px-3 py-2">
                <p className="text-[9px] uppercase tracking-wider text-text-tertiary">{stat.label}</p>
                <p className="text-sm font-mono font-medium text-text-primary tabular-nums">{stat.value}</p>
              </div>
            ))}
          </div>
        )}

        {macro.regime_rationale && (
          <p className="text-[10px] text-text-tertiary leading-relaxed">{macro.regime_rationale}</p>
        )}

        {leaders.length > 0 && (
          <p className="text-[10px] text-text-tertiary mt-1.5">
            <span className="text-text-secondary">Sector rotation (1M):</span>{' '}
            leading {leaders.join(', ')}
            {laggards.length > 0 && <> · lagging {laggards.join(', ')}</>}
          </p>
        )}
      </div>

      {/* ── Themes with a channel to this company ──────────────────────── */}
      <div>
        <h4 className="text-[11px] font-semibold uppercase tracking-wider text-text-tertiary mb-2">
          Macro Exposure
          {screened > 0 && (
            <span className="ml-1.5 font-normal normal-case tracking-normal text-text-tertiary/70">
              ({themes.length} of {screened} themes reach {ticker})
            </span>
          )}
        </h4>

        {themes.length === 0 ? (
          <p className="text-xs text-text-tertiary leading-relaxed rounded-lg bg-surface-elevated/50 px-3 py-2.5">
            None of the {screened} live macro or geopolitical themes screened this period have a
            concrete channel to {ticker}. Its recent performance is best explained by
            company-specific and sector factors rather than the macro backdrop.
          </p>
        ) : (
          <div className="space-y-2">
            {themes.map((theme, i) => (
              <div key={i} className="rounded-lg border border-border bg-surface-elevated/40 px-3 py-2.5">
                <div className="flex items-start gap-2">
                  <span className="mt-0.5 flex-shrink-0">{directionIcon(theme.direction)}</span>
                  <div className="min-w-0 flex-1">
                    <div className="flex items-start justify-between gap-2">
                      <p className="text-xs font-semibold text-text-primary">{theme.name}</p>
                      <span
                        className={`flex-shrink-0 text-[9px] font-semibold uppercase border rounded px-1.5 py-0.5 ${materialityStyle(
                          theme.materiality ?? theme.relevance
                        )}`}
                      >
                        {theme.materiality ?? theme.relevance}
                      </span>
                    </div>

                    <p className="text-[10px] text-text-tertiary mt-0.5">
                      {theme.status} · {theme.direction} · confidence {theme.confidence}
                      {theme.already_visible && <> · {theme.already_visible}</>}
                    </p>

                    {/* Company-specific read — the analytical half, given weight */}
                    {theme.company_impact && (
                      <div className="mt-2 border-l-2 border-primary/40 pl-2.5">
                        <p className="text-[9px] uppercase tracking-wider text-text-tertiary mb-0.5">
                          Impact on {ticker}
                        </p>
                        <p className="text-xs text-text-primary leading-relaxed">{theme.company_impact}</p>
                      </div>
                    )}

                    {/* Shared, company-neutral description — deliberately secondary */}
                    {theme.summary && (
                      <details className="mt-2 group">
                        <summary className="text-[10px] text-text-tertiary cursor-pointer hover:text-text-secondary list-none">
                          <span className="group-open:hidden">What&rsquo;s happening ▸</span>
                          <span className="hidden group-open:inline">What&rsquo;s happening ▾</span>
                        </summary>
                        <div className="mt-1.5 space-y-1">
                          <p className="text-[10px] text-text-tertiary leading-relaxed">{theme.summary}</p>
                          {theme.transmission && (
                            <p className="text-[10px] text-text-tertiary leading-relaxed">
                              <span className="text-text-secondary">Transmission:</span> {theme.transmission}
                            </p>
                          )}
                          {theme.evidence && (
                            <p className="text-[10px] text-text-tertiary/80 leading-relaxed italic">
                              {theme.evidence}
                            </p>
                          )}
                          {theme.why_relevant && (
                            <p className="text-[10px] text-text-tertiary/80 leading-relaxed">
                              <span className="text-text-secondary">Screened in because:</span>{' '}
                              {theme.why_relevant}
                            </p>
                          )}
                        </div>
                      </details>
                    )}
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}

        {macro.backdrop && (
          <p className="text-[10px] text-text-tertiary leading-relaxed mt-2.5 border-l-2 border-border pl-2.5">
            {macro.backdrop}
          </p>
        )}
      </div>
    </div>
  )
}
