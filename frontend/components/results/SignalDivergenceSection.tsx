'use client'

import { useState } from 'react'
import { Card, CardContent } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from '@/components/ui/tooltip'
import { HelpCircle, AlertTriangle, CheckCircle, Info } from 'lucide-react'
import type { SignalBreakdown } from '@/types/api'

interface SignalDivergenceSectionProps {
  breakdown: SignalBreakdown
  recentNews?: Array<{ date: string; headline: string; source?: string }>
  nextEarningsDate?: string
}

interface SignalRow {
  name: string
  icon: string
  score: number
  hasData: boolean
  interpretation: string
  tooltip: string
}

function getDirection(interpretation: string): 'BULLISH' | 'BEARISH' | 'NEUTRAL' {
  if (interpretation.includes('Bullish') || interpretation.includes('🟢')) return 'BULLISH'
  if (interpretation.includes('Bearish') || interpretation.includes('🔴')) return 'BEARISH'
  return 'NEUTRAL'
}

function getSeverity(breakdown: SignalBreakdown): 'low' | 'medium' | 'high' {
  if (!breakdown.has_divergence) return 'low'
  const scores = [
    breakdown.news_score,
    breakdown.earnings_score,
    breakdown.analyst_score,
    breakdown.institutional_score,
    breakdown.insider_score,
  ]
  const mean = scores.reduce((a, b) => a + b, 0) / scores.length
  const variance = scores.reduce((sum, s) => sum + Math.pow(s - mean, 2), 0) / scores.length
  const stdDev = Math.sqrt(variance)
  if (stdDev >= 3.0) return 'high'
  if (stdDev >= 2.0) return 'medium'
  return 'low'
}

// Issue 8: Signal credibility — derived from existing signal data, no new backend required.
// Measures three independent axes of signal quality.
interface SignalCredibility {
  strength: number   // 0–10: how far signals deviate from neutral (5.0)
  stability: number  // 0–10: inverse of inter-signal variance
  agreement: number  // 0–10: fraction of signals pointing same direction
}

function deriveCredibility(breakdown: SignalBreakdown): SignalCredibility {
  const scores = [
    breakdown.news_score,
    breakdown.earnings_score,
    breakdown.analyst_score,
    breakdown.institutional_score,
    breakdown.insider_score,
  ].filter(s => typeof s === 'number' && !isNaN(s))

  if (scores.length === 0) return { strength: 5, stability: 5, agreement: 5 }

  const mean = scores.reduce((a, b) => a + b, 0) / scores.length
  const deviation = scores.reduce((sum, s) => sum + Math.abs(s - 5), 0) / scores.length
  const stdDev = Math.sqrt(scores.reduce((sum, s) => sum + Math.pow(s - mean, 2), 0) / scores.length)

  const bullish = scores.filter(s => s > 6).length
  const bearish = scores.filter(s => s < 4).length
  const directionalAgreement = Math.max(bullish, bearish) / scores.length

  return {
    strength: Math.min(10, deviation * 2),
    stability: Math.max(0, 10 - stdDev * 2),
    agreement: directionalAgreement * 10,
  }
}

function CredibilityBar({ label, value, tooltip }: { label: string; value: number; tooltip: string }) {
  const color =
    value >= 7 ? 'bg-success' :
    value >= 4 ? 'bg-warning' :
    'bg-error/70'

  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <div className="flex items-center gap-2 cursor-default">
          <span className="text-xs text-text-tertiary w-20 shrink-0">{label}</span>
          <div className="flex-1 h-1 bg-surface-elevated rounded-full overflow-hidden">
            <div
              className={`h-full rounded-full transition-all duration-700 ${color}`}
              style={{ width: `${(value / 10) * 100}%` }}
            />
          </div>
          <span className="text-xs font-mono text-text-tertiary w-6 text-right">{value.toFixed(1)}</span>
        </div>
      </TooltipTrigger>
      <TooltipContent className="max-w-xs">
        <p className="text-xs leading-relaxed">{tooltip}</p>
      </TooltipContent>
    </Tooltip>
  )
}

// Issue 5: Reconciliation statements — when specific signal combinations contradict each other,
// surface an interpretive bridge rather than leaving the user to resolve the conflict.
function buildReconciliationStatement(breakdown: SignalBreakdown): string | null {
  const hasBullishTech = (breakdown.tech_divergence_score ?? 5) > 6
  const hasBearishInst = breakdown.institutional_score < 4
  const hasBullishAnalyst = breakdown.analyst_score > 6
  const hasBearishInsider = breakdown.insider_score < 4
  const hasBearishDarkPool = (breakdown.dark_pool_score ?? 5) < 4
  const hasBullishNews = breakdown.news_score > 6

  // Priority order: most analytically significant conflict first
  if (hasBullishTech && hasBearishInst)
    return 'Technical improvement is occurring under institutional distribution — price structure strengthens while smart money reduces exposure. This increases setup fragility.'

  if (hasBullishAnalyst && hasBearishInsider)
    return 'Analysts are bullish while insiders are selling. Insiders operate with material non-public context that sell-side coverage does not reflect. This pattern has historically tended to resolve toward insider direction in large-cap studies; outcomes vary significantly in small and mid-cap names.'

  if (hasBullishTech && hasBearishDarkPool)
    return 'Bullish price structure is forming amid elevated dark pool selling. Momentum may be technically valid but lacks institutional conviction.'

  if (hasBullishNews && hasBearishInst)
    return 'Positive news flow is occurring alongside institutional distribution. Headlines may reflect forward guidance while institutions position ahead of deterioration.'

  return null
}

export function SignalDivergenceSection({
  breakdown,
  nextEarningsDate,
}: SignalDivergenceSectionProps) {
  const [showExplainer, setShowExplainer] = useState(false)

  // C5 + H3: Compute divergence magnitude using only signals that have confirmed data.
  // Including no-data defaults (5.0) would artificially compress the spread.
  const _scoredWithData = [
    { score: breakdown.news_score, hasData: breakdown.news_has_data !== false },
    { score: breakdown.earnings_score, hasData: breakdown.earnings_has_data !== false },
    { score: breakdown.analyst_score, hasData: breakdown.analyst_has_data !== false },
    { score: breakdown.institutional_score, hasData: breakdown.institutional_has_data !== false },
    { score: breakdown.insider_score, hasData: breakdown.insider_has_data !== false },
  ].filter(s => s.hasData).map(s => s.score)

  const divergenceMagnitude = _scoredWithData.length >= 2
    ? Math.max(..._scoredWithData) - Math.min(..._scoredWithData)
    : 0

  const signals: SignalRow[] = [
    {
      name: 'News Sentiment',
      icon: '📰',
      score: breakdown.news_score,
      hasData: breakdown.news_has_data !== false,
      interpretation: breakdown.news_interpretation,
      tooltip: 'Media coverage sentiment over the past 30 days. High = positive news flow and bullish headlines. Low = negative coverage or controversy.',
    },
    {
      name: 'Earnings Revisions',
      icon: '📈',
      score: breakdown.earnings_score,
      hasData: breakdown.earnings_has_data !== false,
      interpretation: breakdown.earnings_interpretation,
      tooltip: 'Whether analysts are raising or lowering earnings estimates. High = improving expectations. Low = deteriorating estimates.',
    },
    {
      name: 'Analyst Ratings',
      icon: '👔',
      score: breakdown.analyst_score,
      hasData: breakdown.analyst_has_data !== false,
      interpretation: breakdown.analyst_interpretation,
      tooltip: 'Wall Street consensus based on buy/hold/sell recommendations. High = majority buy-rated. Low = majority sell-rated.',
    },
    {
      name: 'Institutional Activity',
      icon: '🏛️',
      score: breakdown.institutional_score,
      hasData: breakdown.institutional_has_data !== false,
      interpretation: breakdown.institutional_interpretation,
      tooltip: 'Net buying or selling by pension funds, hedge funds, and mutual funds. High = accumulation. Low = distribution.',
    },
    {
      name: 'Insider Activity',
      icon: '👤',
      score: breakdown.insider_score,
      hasData: breakdown.insider_has_data !== false,
      interpretation: breakdown.insider_interpretation,
      tooltip: 'CEO, CFO, and board member trades (Form 4 filings). High = insider buying. Low = insider selling. Insiders have informational edge.',
    },
  ]

  // Add dark pool and tech divergence if present
  if (breakdown.dark_pool_score !== undefined) {
    signals.push({
      name: 'Dark Pool Activity',
      icon: '🌊',
      score: breakdown.dark_pool_score,
      hasData: breakdown.dark_pool_has_data !== false,
      interpretation: breakdown.dark_pool_interpretation || '',
      tooltip: 'Institutional off-exchange block trades. Sustained dark pool buying above baseline suggests institutional accumulation ahead of public moves.',
    })
  }
  if (breakdown.tech_divergence_score !== undefined) {
    signals.push({
      name: 'Technical Divergence',
      icon: '📊',
      score: breakdown.tech_divergence_score,
      hasData: breakdown.tech_divergence_has_data !== false,
      interpretation: breakdown.tech_divergence_interpretation || '',
      tooltip: 'Whether price momentum and technicals confirm or conflict with the fundamental picture. Divergence here often precedes reversals.',
    })
  }

  const severity = getSeverity(breakdown)
  const hasDivergence = breakdown.has_divergence

  const bearishSignals = signals.filter(s => s.hasData && getDirection(s.interpretation) === 'BEARISH')
  const bullishSignals = signals.filter(s => s.hasData && getDirection(s.interpretation) === 'BULLISH')

  // Issue 8: Credibility metrics
  const credibility = deriveCredibility(breakdown)
  const allHighCredibility = credibility.strength >= 7 && credibility.stability >= 7 && credibility.agreement >= 7

  // C4: "Signals Aligned" badge requires Agreement ≥ 5.0 AND no individual signal score below 3.0.
  // Prevents badge firing on weak or partial consensus.
  const minDataScore = signals.filter(s => s.hasData).reduce(
    (min, s) => Math.min(min, s.score), 10
  )
  const isFullyAligned = !hasDivergence && credibility.agreement >= 5.0 && minDataScore >= 3.0
  const isPartiallyAligned = !hasDivergence && !isFullyAligned && credibility.agreement >= 3.0
  // Anything else with hasDivergence shows the existing Divergence badge

  // Issue 5: Reconciliation statement
  const reconciliation = hasDivergence ? buildReconciliationStatement(breakdown) : null

  // High-signal pattern: insiders selling while analysts are uniformly bullish.
  // This specific pairing has outsized predictive weight vs generic signal count conflicts.
  const isInsiderAnalystDivergence = Boolean(
    hasDivergence &&
    breakdown.insider_has_data !== false &&
    breakdown.analyst_has_data !== false &&
    breakdown.insider_score < 3.0 &&
    breakdown.analyst_score > 7.0 &&
    (breakdown.analyst_score - breakdown.insider_score) > 4.0
  )

  return (
    <section>
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-xl font-semibold flex items-center gap-2">
          Signal Analysis
        </h2>
        <div className="flex items-center gap-2">
          {hasDivergence ? (
            <Badge variant={severity === 'high' ? 'error' : 'warning'}>
              {severity === 'high' ? 'High' : 'Moderate'} Divergence
            </Badge>
          ) : isFullyAligned ? (
            <Badge variant="success">Signals Aligned</Badge>
          ) : isPartiallyAligned ? (
            <Badge variant="secondary">Partial Alignment</Badge>
          ) : (
            <Badge variant="warning">Signal Conflict</Badge>
          )}
          <button
            onClick={() => setShowExplainer(true)}
            className="text-xs text-primary hover:text-primary/80 transition-colors"
          >
            What is this? →
          </button>
        </div>
      </div>

      <Card className={`border ${
        severity === 'high' ? 'border-error/30' :
        severity === 'medium' ? 'border-warning/30' :
        'border-border-subtle'
      }`}>
        <CardContent className="pt-5 pb-4">

          {/* Issue 8: Signal Credibility Strip — compact 3-axis quality indicator.
              Derived entirely from existing signal data. Shown above the matrix so
              users calibrate their reading before interpreting individual signals. */}
          <div className="mb-5 p-3 rounded-md bg-surface-elevated border border-border">
            <div className="flex items-center justify-between mb-2">
              <span className="text-xs font-medium text-text-secondary">Signal Credibility</span>
              {allHighCredibility && (
                <span className="text-xs text-success font-medium">✓ High signal conviction</span>
              )}
              {!allHighCredibility && credibility.stability < 4 && hasDivergence && (
                <span className="text-xs text-warning font-medium">⚠ Unstable — divergence may be transient</span>
              )}
              {!allHighCredibility && credibility.agreement < 5 && (
                <span className="text-xs text-text-tertiary">Low directional agreement</span>
              )}
            </div>
            <div className="space-y-1.5">
              <CredibilityBar
                label="Strength"
                value={credibility.strength}
                tooltip="How decisively signals deviate from neutral. High = signals are making strong directional statements. Low = all signals near 5.0 (neutral)."
              />
              <CredibilityBar
                label="Stability"
                value={credibility.stability}
                tooltip="How consistent signals are with each other. High = signals cluster together. Low = wide spread between highest and lowest signal (chaotic reading)."
              />
              <CredibilityBar
                label="Agreement"
                value={credibility.agreement}
                tooltip="What fraction of signals point the same direction. High = clear majority consensus. Low = signals are split between bullish and bearish."
              />
            </div>
          </div>

          {/* Signal matrix — scoreboard */}
          <div className="space-y-3 mb-5">
            {signals.map((signal, idx) => {
              const direction = signal.hasData ? getDirection(signal.interpretation) : null
              const isConflicting = hasDivergence && direction === 'BEARISH' && bullishSignals.length > 0

              return (
                <div key={idx} className="space-y-1.5">
                  <div className="flex items-center justify-between text-sm">
                    {/* Left: name + tooltip */}
                    <div className="flex items-center gap-1.5">
                      <span>{signal.icon}</span>
                      <span className={`font-medium ${isConflicting ? 'text-warning' : 'text-text-primary'}`}>
                        {signal.name}
                      </span>
                      {isConflicting && <span className="text-warning text-xs">⚠</span>}
                      <Tooltip>
                        <TooltipTrigger asChild>
                          <button className="text-text-tertiary hover:text-text-secondary transition-colors">
                            <HelpCircle className="h-3.5 w-3.5" />
                          </button>
                        </TooltipTrigger>
                        <TooltipContent className="max-w-xs">
                          <p className="text-xs leading-relaxed">{signal.tooltip}</p>
                        </TooltipContent>
                      </Tooltip>
                    </div>

                    {/* Right: direction label + score */}
                    <div className="flex items-center gap-3">
                      {!signal.hasData ? (
                        <span className="text-xs text-text-tertiary">N/A</span>
                      ) : (
                        <span className={`text-sm font-medium ${
                          direction === 'BULLISH' ? 'text-success' :
                          direction === 'BEARISH' ? 'text-error' :
                          'text-text-tertiary'
                        }`}>
                          {direction === 'BULLISH' && '🟢 Bullish'}
                          {direction === 'BEARISH' && '🔴 Bearish'}
                          {direction === 'NEUTRAL' && '⚪ Neutral'}
                        </span>
                      )}
                      <span className="text-text-secondary text-sm w-10 text-right font-mono">
                        {signal.hasData ? signal.score.toFixed(1) : '—'}
                      </span>
                    </div>
                  </div>

                  {/* Progress bar */}
                  <div className="w-full bg-surface-elevated rounded-full h-1.5">
                    <div
                      className={`h-1.5 rounded-full transition-all duration-700 ${
                        !signal.hasData ? 'bg-surface-elevated w-0' :
                        direction === 'BULLISH' ? 'bg-success' :
                        direction === 'BEARISH' ? 'bg-error' :
                        'bg-text-tertiary'
                      }`}
                      style={{ width: signal.hasData ? `${(signal.score / 10) * 100}%` : '0%' }}
                    />
                  </div>
                </div>
              )
            })}
          </div>

          {/* Signal Conflict Summary */}
          {hasDivergence && breakdown.divergence_explanation && (
            <div className={`rounded-lg border p-4 ${
              severity === 'high'
                ? 'bg-error/5 border-error/25'
                : 'bg-warning/5 border-warning/25'
            }`}>
              <div className="flex items-start gap-2.5">
                <AlertTriangle className={`h-4 w-4 mt-0.5 flex-shrink-0 ${
                  severity === 'high' ? 'text-error' : 'text-warning'
                }`} />
                <div className="space-y-2">
                  <p className="text-sm font-medium text-text-primary">
                    {isInsiderAnalystDivergence
                      ? 'Signal Conflict — High-Signal Insider/Analyst Divergence Detected'
                      : `Signal Conflict — ${bearishSignals.length} of ${signals.filter(s => s.hasData).length} signals disagree`}
                  </p>

                  {/* High-signal callout: surfaces ABOVE generic divergence text when the
                      insider-selling / analyst-bullish pattern is detected. This pairing has
                      distinct predictive weight vs. a generic signal count conflict. */}
                  {isInsiderAnalystDivergence && (
                    <div className="flex items-start gap-2.5 p-3 rounded-md bg-warning/8 border border-warning/30">
                      <span className="text-base leading-none mt-0.5 flex-shrink-0">⚡</span>
                      <div className="space-y-1">
                        <p className="text-xs font-semibold text-warning">High-Signal Pattern</p>
                        <p className="text-xs text-text-secondary leading-relaxed">
                          Insiders selling while analysts are bullish — this specific divergence
                          (Insider: {breakdown.insider_score.toFixed(1)} vs Analyst: {breakdown.analyst_score.toFixed(1)}) carries
                          elevated predictive weight. Insiders operate with material non-public context
                          that sell-side coverage does not reflect. This pattern historically resolves
                          toward insider direction more frequently than generic signal conflicts.
                        </p>
                      </div>
                    </div>
                  )}

                  <p className="text-sm text-text-secondary leading-relaxed">
                    {breakdown.divergence_explanation}
                  </p>

                  {/* Issue 5: Reconciliation statement — bridges the specific conflict
                      between pairs of signals rather than generic conflict language. */}
                  {reconciliation && (
                    <div className="flex items-start gap-2 p-2.5 rounded-md bg-primary/5 border border-primary/15">
                      <Info className="h-3.5 w-3.5 mt-0.5 flex-shrink-0 text-primary/70" />
                      <p className="text-xs text-text-secondary leading-relaxed">{reconciliation}</p>
                    </div>
                  )}

                  {divergenceMagnitude >= 4 && (
                    <p className="text-xs text-text-tertiary">
                      Divergence magnitude: {divergenceMagnitude.toFixed(1)} pts ·{' '}
                      Model heuristic (not backtested): similar conflicts have historically tended to resolve within 2–8 weeks in the direction of fundamentals.
                    </p>
                  )}
                  {breakdown.divergence_recommendation && (
                    <p className="text-xs text-text-secondary font-medium">
                      {breakdown.divergence_recommendation}
                    </p>
                  )}
                  {/* Alert checklist */}
                  <div className="pt-1">
                    <p className="text-xs text-text-tertiary mb-1.5">Set alerts for:</p>
                    <ul className="space-y-1 text-xs text-text-secondary">
                      <li className="flex items-start gap-1.5">
                        <span className="text-primary mt-0.5">·</span>
                        Insider buying activity (Form 4 filings)
                      </li>
                      {nextEarningsDate && (
                        <li className="flex items-start gap-1.5">
                          <span className="text-primary mt-0.5">·</span>
                          Next earnings ({nextEarningsDate}) — validates or refutes analyst estimates
                        </li>
                      )}
                      <li className="flex items-start gap-1.5">
                        <span className="text-primary mt-0.5">·</span>
                        Institutional ownership changes (13F filings)
                      </li>
                    </ul>
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* All-clear strip */}
          {isFullyAligned && (
            <div className="flex items-center gap-2 text-xs text-text-secondary pt-1">
              <CheckCircle className="h-3.5 w-3.5 text-success flex-shrink-0" />
              <span>{breakdown.alignment_status} · All signals confirm direction</span>
            </div>
          )}
          {isPartiallyAligned && (
            <div className="flex items-center gap-2 text-xs text-text-secondary pt-1">
              <Info className="h-3.5 w-3.5 text-text-tertiary flex-shrink-0" />
              <span>{breakdown.alignment_status} · Directional agreement is partial — monitor for confirmation</span>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Explainer modal */}
      {showExplainer && (
        <div
          className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4"
          onClick={() => setShowExplainer(false)}
        >
          <Card className="max-w-lg w-full" onClick={(e) => e.stopPropagation()}>
            <CardContent className="pt-6 space-y-4">
              <h3 className="text-lg font-bold">What is Signal Divergence?</h3>
              <p className="text-sm text-text-secondary">
                Most analysis looks at each signal in isolation. Signal divergence measures how signals
                interact — especially when they disagree.
              </p>
              <div className="bg-primary/10 p-4 rounded-lg border border-primary/20">
                <p className="text-sm font-medium mb-1">Example</p>
                <p className="text-sm text-text-secondary">
                  Analysts are bullish, but insiders are selling. Insiders know things analysts don't.
                  This kind of divergence often predicts trouble before the market catches on.
                </p>
              </div>
              <p className="text-sm text-text-secondary">
                The biggest opportunities and risks often hide in these disagreements — where smart
                money diverges from the headlines.
              </p>
              <button
                onClick={() => setShowExplainer(false)}
                className="w-full bg-primary text-primary-foreground px-4 py-2 rounded-md text-sm hover:bg-primary/90 transition-colors"
              >
                Got it
              </button>
            </CardContent>
          </Card>
        </div>
      )}
    </section>
  )
}
