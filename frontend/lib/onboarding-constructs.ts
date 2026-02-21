// ─────────────────────────────────────────────────────────────────────────────
// Onboarding Constructs — five conceptual framework pairs that orient users to
// the platform's analytical logic. Teaches interpretation, not navigation.
// ─────────────────────────────────────────────────────────────────────────────

export interface FrameworkSide {
  label: string
  descriptors: string[]
}

export interface OnboardingConstruct {
  id: string
  title: string
  left: FrameworkSide
  right: FrameworkSide
  /** The central interpretive insight users must internalize. */
  bridgeStatement: string
  /** Why this construct matters for interpreting platform outputs. */
  whyItMatters: string
  /** Term IDs from the knowledge index that this construct references. */
  relatedTermIds: string[]
  /**
   * Analytical condition that triggers contextual in-page prompt.
   * Matches signal state from the analysis output.
   */
  contextualTrigger?: {
    condition: string
    threshold?: number
  }
}

export const ONBOARDING_CONSTRUCTS: OnboardingConstruct[] = [
  {
    id: 'structural_vs_tactical',
    title: 'Structural vs. Tactical',
    left: {
      label: 'Structural',
      descriptors: ['Long-horizon', 'Fundamental value', 'Business quality', 'Regime-agnostic'],
    },
    right: {
      label: 'Tactical',
      descriptors: ['Near-term', 'Price structure', 'Market positioning', 'Regime-conditional'],
    },
    bridgeStatement:
      'When these two frames conflict, the question is not "which is right" — it is "what is the horizon of my decision?"',
    whyItMatters:
      'The platform maintains both frames simultaneously. A structurally compelling thesis can coexist with near-term tactical fragility. Understanding which layer you are operating in changes how you size, enter, and hold a position.',
    relatedTermIds: ['structural_value_anchor', 'technical_fragility', 'thesis_stability'],
    contextualTrigger: {
      condition: 'technical_fragility_detected',
    },
  },
  {
    id: 'valuation_vs_expectations',
    title: 'Valuation vs. Expectations',
    left: {
      label: 'Valuation',
      descriptors: ['Intrinsic worth', 'Fundamental earnings power', 'DCF / multiples', 'What it should be worth'],
    },
    right: {
      label: 'Expectations',
      descriptors: ['Market-implied assumptions', 'Consensus narrative', 'What is already priced', 'What it must deliver'],
    },
    bridgeStatement:
      'Valuation tells you what should happen. Expectations tell you what the market thinks will happen. Divergence between these two is where the most important decisions live.',
    whyItMatters:
      'A business can be fundamentally undervalued while the stock is simultaneously dangerous — if market-implied expectations have been elevated beyond what the business can deliver. Price convergence to intrinsic value requires catalysts, time, and the right expectation environment.',
    relatedTermIds: [
      'structural_value_anchor',
      'market_implied_value',
      'expectation_compression',
      'structural_premium',
    ],
    contextualTrigger: {
      condition: 'market_implied_above_anchor',
      threshold: 0.3,
    },
  },
  {
    id: 'signals_vs_regimes',
    title: 'Signals vs. Regimes',
    left: {
      label: 'Signals',
      descriptors: ['What the data says', 'Point-in-time assessments', 'Fundamental & technical', 'Cross-sectional view'],
    },
    right: {
      label: 'Regimes',
      descriptors: ['Environment the signals live in', 'Rate cycles, liquidity, risk appetite', 'How reliable are the signals', 'Time-series context'],
    },
    bridgeStatement:
      'Signals tell you what the analytical picture looks like. Regimes tell you how much to trust that picture given current macro conditions.',
    whyItMatters:
      'The same fundamental signal that indicates a compelling opportunity in one regime may indicate a value trap in another. Signals are not regime-neutral — their reliability and predictive validity shift as macro conditions evolve.',
    relatedTermIds: [
      'volatility_regime',
      'liquidity_regime',
      'regime_sensitivity',
      'signal_divergence',
    ],
    contextualTrigger: {
      condition: 'high_regime_sensitivity',
    },
  },
  {
    id: 'stability_vs_conviction',
    title: 'Stability vs. Conviction',
    left: {
      label: 'Stability',
      descriptors: ['Analytical durability', 'Consistency over time', 'Signal convergence history', 'How earned is the picture'],
    },
    right: {
      label: 'Conviction',
      descriptors: ['Directional confidence now', 'Strength of current view', 'Cross-dimensional alignment', 'How strong is the case'],
    },
    bridgeStatement:
      'Stability tells you whether the analytical picture has earned trust over time. Conviction tells you how strongly that picture currently supports a directional view. Both are necessary inputs to position sizing.',
    whyItMatters:
      'High conviction on an unstable analytical base is overconfidence. Low conviction on a highly stable base suggests premature signal clustering. Calibrating between them governs position sizing more precisely than any single score.',
    relatedTermIds: [
      'stability_score',
      'conviction_score',
      'thesis_stability',
      'signal_dispersion',
    ],
    contextualTrigger: {
      condition: 'low_stability_score',
      threshold: 4.0,
    },
  },
  {
    id: 'conflict_vs_confirmation',
    title: 'Conflict vs. Confirmation',
    left: {
      label: 'Conflict',
      descriptors: ['Signals in opposition', 'Analytical uncertainty', 'Non-consensus territory', 'Requires diagnosis'],
    },
    right: {
      label: 'Confirmation',
      descriptors: ['Signals in alignment', 'High consensus state', 'Analytically validated', 'Often already priced'],
    },
    bridgeStatement:
      'Confirmation gives you confidence. Conflict gives you questions that, when answered correctly, give you edge. Never dismiss divergence — diagnose it.',
    whyItMatters:
      'Signal confirmation is the high-conviction environment — but it is rare and often reflects information already embedded in price. Signal conflict is uncomfortable — but it is frequently where non-consensus opportunities exist, provided the analyst correctly identifies which signal dimension is leading versus lagging.',
    relatedTermIds: [
      'signal_divergence',
      'signal_dispersion',
      'conviction_score',
      'technical_fragility',
    ],
    contextualTrigger: {
      condition: 'signal_divergence_high',
      threshold: 3.0,
    },
  },
]

export const ONBOARDING_STORAGE_KEY = 'rsw_onboarding_complete'
export const ONBOARDING_STEP_KEY = 'rsw_onboarding_step'
