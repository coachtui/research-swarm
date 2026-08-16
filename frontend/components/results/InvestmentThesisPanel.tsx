'use client'

import { CheckCircle2, AlertTriangle } from 'lucide-react'
import type { InvestmentThesisStructured } from '@/types/api'

/**
 * InvestmentThesisPanel — narrative capital memo.
 *
 * Renders the structured investment thesis:
 *   - Company overview
 *   - Recommendation summary (highlighted)
 *   - Investment highlights (bulleted)
 *   - Valuation & signal context
 *   - Key risks (bulleted)
 *   - Entry strategy note
 */
export function InvestmentThesisPanel({
  thesis,
}: {
  thesis: InvestmentThesisStructured | string | null | undefined
}) {
  if (!thesis) return null

  // Legacy plain-string format
  if (typeof thesis === 'string') {
    return (
      <p className="text-sm text-text-secondary leading-relaxed whitespace-pre-wrap">
        {thesis}
      </p>
    )
  }

  return (
    <div className="space-y-4">

      {/* Company overview */}
      {thesis.company_overview && (
        <p className="text-sm text-text-secondary leading-relaxed">
          {thesis.company_overview}
        </p>
      )}

      {/* recommendation_summary is deliberately NOT rendered here — it is the
          headline of VerdictHeader at the top of the report. Showing it twice
          made the two thesis blocks read as duplicates of each other. */}

      {/* Investment highlights */}
      {thesis.investment_highlights && thesis.investment_highlights.length > 0 && (
        <div>
          <p className="text-[11px] font-semibold uppercase tracking-wider text-text-tertiary mb-2">
            Investment Highlights
          </p>
          <ul className="space-y-1.5">
            {thesis.investment_highlights.map((h, i) => (
              <li key={i} className="flex items-start gap-2">
                <CheckCircle2 className="h-3.5 w-3.5 text-success mt-0.5 flex-shrink-0" />
                <span className="text-sm text-text-secondary">{h}</span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Valuation & signal analysis */}
      {thesis.valuation_signal_analysis && (
        <div>
          <p className="text-[11px] font-semibold uppercase tracking-wider text-text-tertiary mb-1.5">
            Valuation & Signal Context
          </p>
          <p className="text-sm text-text-secondary leading-relaxed">
            {thesis.valuation_signal_analysis}
          </p>
        </div>
      )}

      {/* Key risks */}
      {thesis.key_risks && thesis.key_risks.length > 0 && (
        <div>
          <p className="text-[11px] font-semibold uppercase tracking-wider text-text-tertiary mb-2">
            Key Risks
          </p>
          <ul className="space-y-1.5">
            {thesis.key_risks.map((r, i) => (
              <li key={i} className="flex items-start gap-2">
                <AlertTriangle className="h-3.5 w-3.5 text-warning mt-0.5 flex-shrink-0" />
                <span className="text-sm text-text-secondary">{r}</span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Entry strategy */}
      {thesis.entry_strategy && (
        <div className="border-t border-border/40 pt-3">
          <p className="text-[11px] font-semibold uppercase tracking-wider text-text-tertiary mb-1.5">
            Entry Context
          </p>
          <p className="text-sm text-text-tertiary italic leading-relaxed">
            {thesis.entry_strategy}
          </p>
        </div>
      )}

    </div>
  )
}
