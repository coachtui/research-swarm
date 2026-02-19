import type { ManagerOutput, DecisionIntelligence, TriggerItem } from '@/types/api'
import type { Trigger } from '@/components/results/RatingTriggers'

interface RatingTriggersData {
  upgrade_triggers: Trigger[]
  downgrade_triggers: Trigger[]
  current_rating: string
}

/**
 * Generates intelligent upgrade and downgrade triggers based on analysis data.
 * These triggers tell users exactly what conditions would change the rating.
 */
export function generateRatingTriggers(
  fullOutput: ManagerOutput,
  decisionIntelligence?: DecisionIntelligence | null
): RatingTriggersData {
  const rating = decisionIntelligence?.rating || 'HOLD'

  // Start with existing triggers from backend if available
  const existingUpgrade = fullOutput.upgrade_triggers || []
  const existingDowngrade = fullOutput.downgrade_triggers || []

  // Convert existing triggers to new format
  const upgradeTriggers: Trigger[] = existingUpgrade.map((t) => ({
    condition: `${t.metric}: ${t.action}`,
    threshold: t.threshold,
    metric: t.metric,
  }))

  const downgradeTriggers: Trigger[] = existingDowngrade.map((t) => ({
    condition: `${t.metric}: ${t.action}`,
    threshold: t.threshold,
    metric: t.metric,
  }))

  // Generate additional intelligent triggers based on current state
  const generatedUpgrade = generateUpgradeTriggers(fullOutput, decisionIntelligence, rating)
  const generatedDowngrade = generateDowngradeTriggers(fullOutput, decisionIntelligence, rating)

  // Combine and deduplicate
  const allUpgrade = [...upgradeTriggers, ...generatedUpgrade]
  const allDowngrade = [...downgradeTriggers, ...generatedDowngrade]

  // Return top 5 of each
  return {
    upgrade_triggers: allUpgrade.slice(0, 5),
    downgrade_triggers: allDowngrade.slice(0, 5),
    current_rating: rating,
  }
}

function generateUpgradeTriggers(
  fullOutput: ManagerOutput,
  decisionIntelligence?: DecisionIntelligence | null,
  rating?: string
): Trigger[] {
  const triggers: Trigger[] = []

  // 1. Signal Divergence Resolution
  if (fullOutput.signal_breakdown?.has_divergence) {
    const breakdown = fullOutput.signal_breakdown

    // Check for bearish signals that need to improve
    const signals = [
      { name: 'Insider Activity', score: breakdown.insider_score },
      { name: 'Institutional Activity', score: breakdown.institutional_score },
      { name: 'Analyst Ratings', score: breakdown.analyst_score },
      { name: 'Earnings Revisions', score: breakdown.earnings_score },
    ]

    signals
      .filter((s) => s.score < 5.0)
      .forEach((signal) => {
        triggers.push({
          condition: `${signal.name} turns positive (shows market confidence)`,
          threshold: `${signal.name} score >6.0`,
          metric: signal.name.toLowerCase().replace(' ', '_'),
        })
      })
  }

  // 2. Technical Breakout
  if (decisionIntelligence?.recommended_strategy?.exit?.target_1?.price) {
    const target1Price = decisionIntelligence.recommended_strategy.exit.target_1.price
    triggers.push({
      condition: `Stock breaks above $${target1Price.toFixed(2)} resistance with volume`,
      threshold: `>$${target1Price.toFixed(2)}`,
      metric: 'price',
    })
  }

  // 3. Weak Components Improving
  const breakdown = fullOutput.moat_breakdown
  if (breakdown) {
    const components = [
      { name: 'Technical/Momentum', score: breakdown.technical_strength, key: 'technical_strength' },
      { name: 'Valuation', score: breakdown.valuation, key: 'valuation' },
      { name: 'Earnings Momentum', score: breakdown.earnings_momentum, key: 'earnings_momentum' },
    ]

    components
      .filter((c) => c.score < 6.0)
      .forEach((comp) => {
        if (comp.key === 'technical_strength') {
          triggers.push({
            condition: 'Technical momentum improves (ends downtrend)',
            threshold: 'Technical score >6.5',
            metric: 'technical',
          })
        } else if (comp.key === 'valuation' && comp.score < 5.0) {
          // Include fair value range if available
          const idealZone = decisionIntelligence?.recommended_strategy?.entry?.ideal_zone
          const condition = idealZone
            ? `Price pulls back to fair value range ($${idealZone.low.toFixed(2)}-$${idealZone.high.toFixed(2)})`
            : 'Price pulls back to fair value range'
          triggers.push({
            condition,
            threshold: 'Valuation score >6.0',
            metric: 'valuation',
          })
        } else if (comp.key === 'earnings_momentum') {
          triggers.push({
            condition: 'Earnings revisions turn positive',
            threshold: 'Earnings momentum >6.5',
            metric: 'earnings',
          })
        }
      })
  }

  // 4. Fundamental-Technical Divergence Resolution
  if (decisionIntelligence?.fund_tech_divergence?.has_divergence) {
    const ftd = decisionIntelligence.fund_tech_divergence
    if (ftd.fundamental_signal === 'STRONG' && ftd.technical_signal === 'WEAK') {
      triggers.push({
        condition: 'Technicals catch up to fundamentals (stock rallies)',
        threshold: 'Technical score matches fundamental strength',
        metric: 'divergence',
      })
    }
  }

  // 5. Catalyst Events
  // Add generic catalyst trigger if we don't have enough specific ones
  if (triggers.length < 3) {
    triggers.push({
      condition: 'Company announces positive catalyst (product launch, partnership, etc.)',
      threshold: 'Material positive news',
      metric: 'catalyst',
    })
  }

  return triggers
}

function generateDowngradeTriggers(
  fullOutput: ManagerOutput,
  decisionIntelligence?: DecisionIntelligence | null,
  rating?: string
): Trigger[] {
  const triggers: Trigger[] = []

  // 1. Technical Breakdown
  if (decisionIntelligence?.recommended_strategy?.exit?.stop_loss) {
    const stopLoss = decisionIntelligence.recommended_strategy.exit.stop_loss
    if (typeof stopLoss === 'number') {
      triggers.push({
        condition: `Stock breaks below $${stopLoss.toFixed(2)} support level`,
        threshold: `<$${stopLoss.toFixed(2)}`,
        metric: 'price',
      })
    }
  }

  // 2. Strong Components Weakening
  const breakdown = fullOutput.moat_breakdown
  if (breakdown) {
    const components = [
      { name: 'Financial Health', score: breakdown.financial_health, key: 'financial_health' },
      { name: 'Earnings Momentum', score: breakdown.earnings_momentum, key: 'earnings_momentum' },
      { name: 'Sentiment', score: breakdown.sentiment_catalysts, key: 'sentiment' },
    ]

    components
      .filter((c) => c.score >= 7.0)
      .forEach((comp) => {
        if (comp.key === 'financial_health') {
          triggers.push({
            condition: 'Financial health deteriorates (debt, cash flow issues)',
            threshold: 'Financial Health <6.0',
            metric: 'financial_health',
          })
        } else if (comp.key === 'earnings_momentum') {
          triggers.push({
            condition: 'Earnings estimates get cut (momentum reverses)',
            threshold: 'More downgrades than upgrades',
            metric: 'earnings',
          })
        }
      })
  }

  // 3. Signal Divergence Worsening
  if (fullOutput.signal_breakdown?.has_divergence) {
    const breakdown = fullOutput.signal_breakdown
    const bearishSignals = [
      { name: 'Insider Activity', score: breakdown.insider_score },
      { name: 'Institutional Activity', score: breakdown.institutional_score },
    ]

    bearishSignals
      .filter((s) => s.score < 4.0)
      .forEach((signal) => {
        triggers.push({
          condition: `${signal.name} worsens further (accelerated selling)`,
          threshold: `${signal.name} <${(signal.score - 1.0).toFixed(1)}`,
          metric: signal.name.toLowerCase().replace(' ', '_'),
        })
      })
  }

  // 4. Guidance/Catalyst Failures
  triggers.push({
    condition: 'Company misses earnings or guides down',
    threshold: 'Earnings miss or guidance cut',
    metric: 'guidance',
  })

  // 5. Competitive/Market Risks Materialize
  if (fullOutput.risk_factors && fullOutput.risk_factors.length > 0) {
    // Pick the most significant risk factor
    const topRisk = fullOutput.risk_factors[0]
    const riskKeyword = extractRiskKeyword(topRisk)

    triggers.push({
      condition: `${riskKeyword} risk materializes`,
      threshold: 'Material adverse development',
      metric: 'risk',
    })
  }

  // 6. Fundamental-Technical Divergence Worsens
  if (decisionIntelligence?.fund_tech_divergence?.has_divergence) {
    const ftd = decisionIntelligence.fund_tech_divergence
    if (ftd.fundamental_signal === 'WEAK' && ftd.technical_signal === 'STRONG') {
      triggers.push({
        condition: 'Fundamentals deteriorate further (technicals lose support)',
        threshold: 'Fundamental score <4.0',
        metric: 'divergence',
      })
    }
  }

  return triggers
}

function extractRiskKeyword(riskText: string): string {
  // Extract key risk category from risk factor text
  const riskKeywords = [
    'Competition',
    'Regulatory',
    'Margin',
    'Growth',
    'Valuation',
    'Execution',
    'Market',
    'Operational',
  ]

  for (const keyword of riskKeywords) {
    if (riskText.toLowerCase().includes(keyword.toLowerCase())) {
      return keyword
    }
  }

  return 'Key'
}
