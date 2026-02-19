import { Card, CardContent } from '@/components/ui/card'
import type { InvestmentThesisStructured, TriggerItem } from '@/types/api'

interface AnalystVerdictProps {
  thesis: InvestmentThesisStructured | string
  upgradeTriggers?: TriggerItem[] | null
  downgradeTriggers?: TriggerItem[] | null
}

export function AnalystVerdict({ thesis, upgradeTriggers, downgradeTriggers }: AnalystVerdictProps) {
  const hasStructuredThesis = typeof thesis !== 'string'
  const hasTriggers = (upgradeTriggers?.length ?? 0) > 0 || (downgradeTriggers?.length ?? 0) > 0

  return (
    <Card className="border border-border-subtle">
      <CardContent className="pt-6 space-y-6">
        <h2 className="text-xl font-semibold text-text-primary">Analyst Verdict</h2>

        {hasStructuredThesis ? (
          <div className="space-y-5">
            {/* Company Overview */}
            <div>
              <h3 className="text-sm font-semibold text-text-secondary uppercase tracking-wide mb-1.5">
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

            {/* Why at this level — investment highlights */}
            <div>
              <h3 className="text-sm font-semibold text-text-secondary uppercase tracking-wide mb-2">
                Investment Highlights
              </h3>
              <ul className="space-y-2">
                {(thesis as InvestmentThesisStructured).investment_highlights.map((item, idx) => (
                  <li key={idx} className="flex items-start gap-2 text-sm text-text-secondary">
                    <span className="text-success mt-1 flex-shrink-0">·</span>
                    <span>{item}</span>
                  </li>
                ))}
              </ul>
            </div>

            {/* Valuation & signal analysis */}
            <div>
              <h3 className="text-sm font-semibold text-text-secondary uppercase tracking-wide mb-1.5">
                Valuation &amp; Signal Analysis
              </h3>
              <p className="text-text-secondary text-sm leading-relaxed">
                {(thesis as InvestmentThesisStructured).valuation_signal_analysis}
              </p>
            </div>

            {/* Strongest counterpoint — key risks */}
            <div>
              <h3 className="text-sm font-semibold text-text-secondary uppercase tracking-wide mb-2">
                Risks
              </h3>
              <ul className="space-y-2">
                {(thesis as InvestmentThesisStructured).key_risks.map((item, idx) => (
                  <li key={idx} className="flex items-start gap-2 text-sm text-text-secondary">
                    <span className="text-error mt-1 flex-shrink-0">·</span>
                    <span>{item}</span>
                  </li>
                ))}
              </ul>
            </div>

            {/* Entry strategy & investor fit */}
            <div>
              <h3 className="text-sm font-semibold text-text-secondary uppercase tracking-wide mb-1.5">
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

        {/* What changes the rating — merged from BottomLine */}
        {hasTriggers && (
          <div className="border-t border-border pt-5 space-y-4">
            <h3 className="text-sm font-semibold text-text-secondary uppercase tracking-wide">
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
