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
  | 'historical_patterns'       // Historical Analog Panel — pattern framing
  | 'institutional_risk'        // Institutional Risk Dashboard — stability / noise / risk efficiency
  | 'probabilistic_engine'      // Probabilistic Engine — full EV model, stop probability, scenario distribution
  | 'analyst_verdict'           // Full Analyst Verdict — investment thesis, full agents report
  | 'execution_layer'           // Execution Layer — position sizing, portfolio risk, trade stability
  | 'trade_setup_details'       // Trader-only: enhanced trade setup table + fund/tech divergence
  // ── Engine diagnostics (granular sub-section gates) ──────────────────────
  | 'sizing_summary'            // All tiers: allocation % + plain-language rationale
  | 'signal_metrics'            // Investor+: σ band, noise score, stop probability headline
  | 'stop_probability_detail'   // Investor+: stop prob decomposition table
  | 'engine_diagnostics'        // Trader: full engine panels + driver ranking
  | 'scenario_weights'          // Trader: model vs effective scenario weights + rotation
  | 'multiplier_stack'          // Trader: position-sizing multiplier list + product
  | 'risk_matrix_full'          // Trader: full portfolio interaction metrics

/** Minimum tier required to access each feature. */
const FEATURE_REQUIREMENTS: Record<Feature, Tier> = {
  historical_patterns:      'investor',
  institutional_risk:       'investor',
  probabilistic_engine:     'investor',
  analyst_verdict:          'investor',
  execution_layer:          'trader',
  trade_setup_details:      'trader',
  // Engine diagnostics
  sizing_summary:           'starter',
  signal_metrics:           'investor',
  stop_probability_detail:  'investor',
  engine_diagnostics:       'trader',
  scenario_weights:         'trader',
  multiplier_stack:         'trader',
  risk_matrix_full:         'trader',
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
  sizing_summary: {
    title: 'Position Sizing Summary',
    description: 'Recommended allocation percentage and plain-language sizing rationale.',
    requiredTier: 'starter',
    bullets: [
      'Recommended portfolio allocation %',
      'Plain-language conviction rationale',
    ],
  },
  signal_metrics: {
    title: 'Signal Metrics',
    description: 'Numeric engine diagnostics: σ dispersion, noise score, and stop probability headline.',
    requiredTier: 'investor',
    bullets: [
      'EV sensitivity band (σ) and stability classification',
      'Noise score and noise regime label',
      'Stop probability headline value',
      'EV confidence level and dispersion',
    ],
  },
  stop_probability_detail: {
    title: 'Stop Probability Decomposition',
    description: 'Component-level breakdown of what drives your stop-out probability.',
    requiredTier: 'investor',
    bullets: [
      'Base stop risk from volatility regime',
      'Trend and support modifiers',
      'Effective stop probability with narrative',
    ],
  },
  engine_diagnostics: {
    title: 'Full Engine Diagnostics',
    description: 'Complete probabilistic engine output with driver ranking and attribution.',
    requiredTier: 'trader',
    bullets: [
      'EV sensitivity attribution by driver type',
      'Signal vs market movement decomposition',
      'Confidence integrity with degradation breakdown',
      'Full diagnostic panels for all engine modules',
    ],
  },
  scenario_weights: {
    title: 'Scenario Weight Diagnostics',
    description: 'Model vs effective scenario probabilities with rotation and compression analysis.',
    requiredTier: 'trader',
    bullets: [
      'Bear / Base / Bull model vs effective weights',
      'Scenario rotation index and compression ratio',
      'Tail state classification (Expanded / Neutral / Compressed)',
      'Active rotation factors driving weight shifts',
    ],
  },
  multiplier_stack: {
    title: 'Position Sizing Multiplier Stack',
    description: 'Full multiplier breakdown showing how each factor adjusts your position size.',
    requiredTier: 'trader',
    bullets: [
      'Noise, sensitivity, dispersion, and stop-risk multipliers',
      'Product of multipliers and net adjustment',
      'Cap state and constraint events',
      'Conviction justification for the final allocation',
    ],
  },
  risk_matrix_full: {
    title: 'Full Risk Matrix',
    description: 'Complete portfolio interaction metrics including correlation and crowding data.',
    requiredTier: 'trader',
    bullets: [
      'Correlation with existing portfolio positions',
      'Crowding and concentration risk flags',
      'Factor exposure breakdown',
      'Liquidity and volatility risk interaction metrics',
    ],
  },
}
