import type { ManagerOutput, DecisionIntelligence } from '@/types/api'

interface VerdictSummaryData {
  ticker: string
  overall_score: number
  rating: string
  key_strength: string
  key_concern: string
  the_call: string
}

export function generateVerdictSummary(
  fullOutput: ManagerOutput,
  decisionIntelligence?: DecisionIntelligence | null,
  moatScore?: number | null
): VerdictSummaryData {
  const ticker = fullOutput.ticker
  const score = moatScore ?? calculateScoreFromBreakdown(fullOutput)
  const rating = decisionIntelligence?.rating || inferRatingFromScore(score)

  // Extract key strength (highest scoring component)
  const key_strength = extractKeyStrength(fullOutput, decisionIntelligence)

  // Extract key concern (from divergence, risk factors, or lowest component)
  const key_concern = extractKeyConcern(fullOutput, decisionIntelligence)

  // Generate the call
  const the_call = generateTheCall(rating, score, decisionIntelligence, fullOutput)

  return {
    ticker,
    overall_score: score,
    rating,
    key_strength,
    key_concern,
    the_call,
  }
}

function calculateScoreFromBreakdown(fullOutput: ManagerOutput): number {
  const breakdown = fullOutput.moat_breakdown
  if (!breakdown) return 5.0

  // Calculate weighted average using v2.0 formula
  return (
    breakdown.earnings_momentum * 0.25 +
    breakdown.financial_health * 0.25 +
    breakdown.valuation * 0.2 +
    breakdown.technical_strength * 0.15 +
    breakdown.sentiment_catalysts * 0.15
  )
}

function inferRatingFromScore(score: number): string {
  if (score >= 8.0) return 'STRONG BUY'
  if (score >= 6.5) return 'BUY'
  if (score >= 4.5) return 'HOLD'
  if (score >= 3.0) return 'SELL'
  return 'STRONG SELL'
}

function extractKeyStrength(
  fullOutput: ManagerOutput,
  decisionIntelligence?: DecisionIntelligence | null
): string {
  const breakdown = fullOutput.moat_breakdown
  if (!breakdown) return 'The business has solid fundamentals'

  // Find the highest scoring component
  const components = [
    { name: 'financial_health', score: breakdown.financial_health, label: 'Financial Health' },
    { name: 'earnings_momentum', score: breakdown.earnings_momentum, label: 'Earnings Momentum' },
    { name: 'valuation', score: breakdown.valuation, label: 'Valuation' },
    { name: 'technical_strength', score: breakdown.technical_strength, label: 'Technical Strength' },
    { name: 'sentiment_catalysts', score: breakdown.sentiment_catalysts, label: 'Sentiment' },
  ]

  const topComponent = components.reduce((max, current) =>
    current.score > max.score ? current : max
  )

  // Format strength based on component type
  const strengthTemplates: Record<string, (score: number) => string> = {
    financial_health: (s) =>
      `The business is rock-solid (${s.toFixed(1)}/10 financial health)`,
    earnings_momentum: (s) =>
      `Earnings are accelerating (${s.toFixed(1)}/10 momentum score)`,
    valuation: (s) =>
      `It's trading at an attractive price (${s.toFixed(1)}/10 valuation)`,
    technical_strength: (s) =>
      `Technical momentum is strong (${s.toFixed(1)}/10 technical score)`,
    sentiment_catalysts: (s) =>
      `Market sentiment is bullish (${s.toFixed(1)}/10 sentiment)`,
  }

  return (
    strengthTemplates[topComponent.name]?.(topComponent.score) || 'Strong fundamentals across the board'
  )
}

function extractKeyConcern(
  fullOutput: ManagerOutput,
  decisionIntelligence?: DecisionIntelligence | null
): string {
  // First check for signal divergence
  if (fullOutput.signal_breakdown?.has_divergence) {
    const divergence = fullOutput.signal_breakdown
    return divergence.divergence_explanation || 'Signals are showing mixed readings'
  }

  // Check for fundamental-technical divergence
  if (decisionIntelligence?.fund_tech_divergence?.has_divergence) {
    const ftd = decisionIntelligence.fund_tech_divergence
    if (ftd.severity === 'HIGH') {
      return ftd.interpretation || 'Major disconnect between fundamentals and technicals'
    }
  }

  // Otherwise look at weakest component
  const breakdown = fullOutput.moat_breakdown
  if (!breakdown) return 'Execution risks remain'

  const components = [
    { name: 'financial_health', score: breakdown.financial_health, label: 'financial health' },
    { name: 'earnings_momentum', score: breakdown.earnings_momentum, label: 'earnings momentum' },
    { name: 'valuation', score: breakdown.valuation, label: 'valuation' },
    { name: 'technical_strength', score: breakdown.technical_strength, label: 'technicals' },
    { name: 'sentiment_catalysts', score: breakdown.sentiment_catalysts, label: 'sentiment' },
  ]

  const weakestComponent = components.reduce((min, current) =>
    current.score < min.score ? current : min
  )

  // Format concern based on component type
  const concernTemplates: Record<string, (score: number, label: string) => string> = {
    financial_health: (s, l) =>
      `${l} is concerning (${s.toFixed(1)}/10 score)`,
    earnings_momentum: (s, l) =>
      `${l} is fading (${s.toFixed(1)}/10 score)`,
    valuation: (s, l) =>
      `you're paying a premium (${s.toFixed(1)}/10 ${l})`,
    technical_strength: (s, l) =>
      `the stock is technically weak (${s.toFixed(1)}/10 score)`,
    sentiment_catalysts: (s, l) =>
      `${l} is mixed (${s.toFixed(1)}/10 score)`,
  }

  return (
    concernTemplates[weakestComponent.name]?.(weakestComponent.score, weakestComponent.label) ||
    'There are execution risks to monitor'
  )
}

function generateTheCall(
  rating: string,
  score: number,
  decisionIntelligence?: DecisionIntelligence | null,
  fullOutput?: ManagerOutput
): string {
  if (rating.includes('BUY')) {
    const idealEntry = decisionIntelligence?.recommended_strategy?.entry?.ideal_zone
    if (idealEntry) {
      return `The call: ${rating} - start building a position around $${idealEntry.low.toFixed(2)}-$${idealEntry.high.toFixed(2)}.`
    }
    return `The call: ${rating} - start building a position.`
  } else if (rating === 'HOLD') {
    // Look for what to wait for
    const upgradeTriggers = fullOutput?.upgrade_triggers
    const waitFor = upgradeTriggers?.[0]
      ? `wait for ${upgradeTriggers[0].metric.toLowerCase()}`
      : 'wait for a better entry or catalyst'

    return `The call: HOLD if you own it, ${waitFor} if you don't.`
  } else {
    return `The call: ${rating} - the risks outweigh the potential.`
  }
}
