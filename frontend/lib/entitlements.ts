/**
 * Feature Entitlements — Decision-Maturity Segmentation
 *
 * Tier progression mirrors analytical capability growth:
 *   Starter  → Awareness Engine     (observe, orient)
 *   Investor → Decision Intelligence (decide, size)
 *   Trader   → Allocation & Execution Infrastructure (deploy, manage)
 *
 * Rules:
 * - Admins always have full access.
 * - A higher tier inherits all lower-tier features.
 * - Features should feel like expansion, not unlocking basics.
 */

export type Tier = 'starter' | 'investor' | 'trader'

export type Feature =
  | 'historical_patterns'   // Historical Analog Panel — pattern framing
  | 'institutional_risk'    // Institutional Risk Dashboard — stability / noise / risk efficiency
  | 'probabilistic_engine'  // Probabilistic Engine — full EV model, stop probability, scenario distribution
  | 'analyst_verdict'       // Full Analyst Verdict — investment thesis, full agents report
  | 'execution_layer'       // Execution Layer — position sizing, portfolio risk, trade stability
  | 'export_pdf'            // PDF Export — institutional-grade downloadable report
  | 'trade_setup_details'   // Trader-only: enhanced trade setup table + fund/tech divergence

/** Minimum tier required to access each feature. */
const FEATURE_REQUIREMENTS: Record<Feature, Tier> = {
  historical_patterns:  'investor',
  institutional_risk:   'investor',
  probabilistic_engine: 'investor',
  analyst_verdict:      'investor',
  execution_layer:      'trader',
  export_pdf:           'investor',
  trade_setup_details:  'trader',
}

const TIER_ORDER: Record<Tier, number> = {
  starter:  0,
  investor: 1,
  trader:   2,
}

/** Returns true if `userTier` meets or exceeds the required tier for `feature`. */
export function canAccessFeature(feature: Feature, userTier: Tier | string | null | undefined): boolean {
  if (!userTier) return false
  const required = FEATURE_REQUIREMENTS[feature]
  const userLevel = TIER_ORDER[userTier as Tier] ?? -1
  const requiredLevel = TIER_ORDER[required]
  return userLevel >= requiredLevel
}

/** Display name for each tier. */
export const TIER_LABELS: Record<Tier, string> = {
  starter:  'Starter',
  investor: 'Investor',
  trader:   'Trader',
}

/** What each locked feature unlocks (for upgrade prompts). */
export const FEATURE_GATE_COPY: Record<Feature, {
  title: string
  description: string
  requiredTier: Tier
  bullets: string[]
}> = {
  historical_patterns: {
    title: 'Historical Pattern Framing',
    description: 'Structural context from analogous market regimes.',
    requiredTier: 'investor',
    bullets: [
      'Match current setup to historical analogs',
      'Understand base-rate outcomes for this pattern type',
      'Calibrate conviction with regime-level context',
    ],
  },
  institutional_risk: {
    title: 'Stability & Noise Diagnostics',
    description: 'Quantified signal reliability, factor exposure, and liquidity risk.',
    requiredTier: 'investor',
    bullets: [
      'Volatility regime & liquidity risk assessment',
      'Signal noise / reliability scoring',
      'Sensitivity attribution across risk factors',
      'Drift diagnostics — detect model instability early',
    ],
  },
  probabilistic_engine: {
    title: 'Probabilistic Engine & EV Model',
    description: 'Full expected value framework with scenario-weighted probabilities.',
    requiredTier: 'investor',
    bullets: [
      'Expected value across Bear / Base / Bull scenarios',
      'Stop probability framework & loss distribution',
      'Confidence interval calibration',
      'Longitudinal model drift comparison',
    ],
  },
  analyst_verdict: {
    title: 'Full Analyst Verdict',
    description: 'Structured investment thesis synthesised from all three agent reports.',
    requiredTier: 'investor',
    bullets: [
      'Company overview & recommendation summary',
      'Investment highlights with supporting data',
      'Key risks with specifics, not generics',
      'Entry strategy & investor fit guidance',
    ],
  },
  execution_layer: {
    title: 'Execution & Allocation Infrastructure',
    description: 'Capital deployment tools for position sizing and portfolio construction.',
    requiredTier: 'trader',
    bullets: [
      'Dynamic position sizing (noise-adjusted exposure)',
      'Portfolio risk engine & concentration diagnostics',
      'Factor exposure approximation',
      'Trade stability monitoring & correlation crowding',
    ],
  },
  export_pdf: {
    title: 'PDF Report Export',
    description: 'Institutional-grade PDF with full analysis, structured thesis, and price targets.',
    requiredTier: 'investor',
    bullets: [
      'Title page, table of contents, and appendix',
      'Structured investment thesis with highlights and risks',
      'Valuation tables, signal breakdown, and catalysts',
      'Print-ready format for client distribution or record-keeping',
    ],
  },
  trade_setup_details: {
    title: 'Trade Setup Details',
    description: 'Conservative vs aggressive entry/exit tables with 3-target playbook.',
    requiredTier: 'trader',
    bullets: [
      'Conservative and aggressive entry price levels',
      'Three-tier exit targets with partial-sell percentages',
      'Stop-loss levels and risk/reward ratios',
      'Fundamental vs technical divergence analysis',
    ],
  },
}
