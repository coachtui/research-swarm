/**
 * Decision Dimension Interpreter
 *
 * Pure semantic mapping: existing model outputs → dual-dimension decision taxonomy.
 *
 * HARD CONSTRAINT: Zero new calculations. Presentation-layer interpretation only.
 *
 * Structural Bias  = "Should this asset exist in my portfolio?"
 *   Anchors to: rating, business quality, fundamental regime, long-term EV direction
 *
 * Tactical Stance  = "Should I deploy capital now?"
 *   Anchors to: action, entry conditions, signal dispersion, smart money, valuation regime
 */

export type StructuralBias = 'Bullish' | 'Neutral' | 'Bearish'

export type TacticalStance =
  | 'Favorable'
  | 'Opportunistic'
  | 'Deferred'
  | 'Constrained'
  | 'Defensive'

/**
 * Derives Structural Bias from the model-computed rating string.
 * Mapping: BUY-family → Bullish | HOLD → Neutral | SELL-family → Bearish
 */
export function deriveStructuralBias(rating: string | null | undefined): StructuralBias {
  if (!rating) return 'Neutral'
  const r = rating.toUpperCase()
  if (r.includes('BUY')) return 'Bullish'
  if (r === 'HOLD') return 'Neutral'
  return 'Bearish'
}

/**
 * Derives Tactical Stance from the existing action label, divergence state,
 * and structural dislocation flag. No math — pure interpretation mapping.
 *
 * Mapping table:
 *   BUY NOW  + no high divergence        → Favorable
 *   BUY NOW  + HIGH divergence           → Opportunistic (signals split but entry valid)
 *   SCALE IN + no high divergence        → Opportunistic
 *   SCALE IN + HIGH divergence           → Constrained
 *   WAIT     + structural dislocation    → Deferred (valuation regime extended)
 *   WAIT     + HIGH divergence           → Constrained (signal dispersion blocking)
 *   WAIT     + other                     → Deferred
 *   AVOID    + HIGH divergence + bearish → Defensive
 *   AVOID    + other                     → Constrained
 *   SELL / STRONG SELL                   → Defensive
 *   ADD                                  → Favorable / Opportunistic (per divergence)
 *   HOLD rating (fallback)               → Constrained / Deferred
 */
export function deriveTacticalStance(
  action: string | null | undefined,
  rating: string | null | undefined,
  hasDivergence: boolean,
  divergenceSeverity: 'HIGH' | 'MODERATE' | null | undefined,
  isStructuralDislocation: boolean,
): TacticalStance {
  const a = (action ?? '').toUpperCase()
  const r = (rating ?? '').toUpperCase()
  const highSeverity = divergenceSeverity === 'HIGH'

  if (r === 'STRONG SELL' || r === 'SELL') return 'Defensive'

  if (a === 'AVOID') return hasDivergence && highSeverity ? 'Defensive' : 'Constrained'

  if (a === 'WAIT') {
    if (isStructuralDislocation) return 'Deferred'
    if (highSeverity) return 'Constrained'
    return 'Deferred'
  }

  if (a === 'SCALE IN') return highSeverity ? 'Constrained' : 'Opportunistic'

  if (a === 'BUY NOW') return highSeverity ? 'Opportunistic' : 'Favorable'

  if (a === 'ADD') return hasDivergence ? 'Opportunistic' : 'Favorable'

  // Fallback via rating when action is absent
  if (r === 'HOLD') return hasDivergence ? 'Constrained' : 'Deferred'

  return 'Opportunistic'
}

// ---------------------------------------------------------------------------
// Color tokens — maps dimension values to Tailwind class sets
// ---------------------------------------------------------------------------

export function structuralBiasColor(bias: StructuralBias): {
  text: string
  bg: string
  border: string
} {
  switch (bias) {
    // Teal accent: analytical classification, not directional endorsement
    case 'Bullish': return { text: 'text-primary',        bg: 'bg-primary/8',       border: 'border-primary/25'  }
    // Slate/neutral: classification without alarm — Bearish is posture, not danger
    case 'Bearish': return { text: 'text-text-secondary', bg: 'bg-surface-elevated', border: 'border-border'      }
    default:        return { text: 'text-text-tertiary',  bg: 'bg-surface-elevated', border: 'border-border/60'   }
  }
}

export function tacticalStanceColor(stance: TacticalStance): {
  text: string
  bg: string
  border: string
} {
  switch (stance) {
    case 'Favorable':     return { text: 'text-success', bg: 'bg-success/8',  border: 'border-success/25'  }
    case 'Opportunistic': return { text: 'text-primary', bg: 'bg-primary/8',  border: 'border-primary/25'  }
    case 'Deferred':      return { text: 'text-warning',  bg: 'bg-warning/8',  border: 'border-warning/25' }
    case 'Constrained':   return { text: 'text-warning',  bg: 'bg-warning/8',  border: 'border-warning/25' }
    case 'Defensive':     return { text: 'text-error',    bg: 'bg-error/8',    border: 'border-error/25'   }
  }
}

// ---------------------------------------------------------------------------
// Badge-style variant helper (for components using shadcn Badge)
// ---------------------------------------------------------------------------

export function structuralBiasBadgeVariant(
  bias: StructuralBias,
): 'success' | 'warning' | 'error' | 'default' | 'secondary' {
  switch (bias) {
    case 'Bullish': return 'default'    // Teal/primary — classification, not promotion
    case 'Bearish': return 'secondary'  // Neutral slate — posture, not alarm
    default:        return 'secondary'  // Muted — balanced classification
  }
}

export function tacticalStanceBadgeVariant(
  stance: TacticalStance,
): 'success' | 'warning' | 'error' | 'default' {
  switch (stance) {
    case 'Favorable':     return 'success'
    case 'Opportunistic': return 'default'
    case 'Deferred':      return 'warning'
    case 'Constrained':   return 'warning'
    case 'Defensive':     return 'error'
  }
}

// ---------------------------------------------------------------------------
// Portfolio Bias — institutional capital language mapped from rating
// ---------------------------------------------------------------------------

export type PortfolioBias = 'Accumulate' | 'Maintain' | 'Reduce'

/**
 * Maps the model's rating string to institutional portfolio-action language.
 * BUY-family → Accumulate | HOLD → Maintain | SELL-family → Reduce
 */
export function derivePortfolioBias(rating: string | null | undefined): PortfolioBias {
  if (!rating) return 'Maintain'
  const r = rating.toUpperCase()
  if (r.includes('BUY')) return 'Accumulate'
  if (r === 'HOLD') return 'Maintain'
  return 'Reduce'
}

// ---------------------------------------------------------------------------
// Capital Posture — 5-state institutional capital deployment taxonomy
// ---------------------------------------------------------------------------

/**
 * Capital Posture separates the portfolio decision from the analytical thesis.
 *
 * Accumulate → Thesis attractive + deployment conditions acceptable
 * Maintain   → Thesis intact + balanced risk/reward
 * Reduce     → Thesis deteriorating / asymmetric downside risk
 * Deferred   → Thesis intact but entry unfavorable (valuation, regime, noise)
 * Avoid      → Thesis unattractive for new capital
 *
 * NOTE: Thesis Direction (Bullish/Neutral/Bearish) and Capital Posture are
 * independent dimensions — Bullish thesis does NOT auto-map to Accumulate.
 */
export type CapitalPosture = 'Accumulate' | 'Maintain' | 'Reduce' | 'Deferred' | 'Avoid'

/**
 * Derives Capital Posture from rating + decision framework actions.
 * Pure semantic mapping — no new calculations.
 *
 * Priority order:
 *   SELL/STRONG SELL rating  → Reduce (thesis degraded)
 *   AVOID (new buyers)       → Avoid  (unattractive for new capital)
 *   WAIT  (new buyers)       → Deferred (thesis intact, entry unfavorable)
 *   BUY NOW / SCALE IN       → Accumulate (conditions support deployment)
 *   REDUCE (current holders) → Reduce
 *   ADD   (current holders)  → Accumulate
 *   HOLD  (current holders)  → Maintain
 *   Fallback                 → Maintain
 */
export function deriveCapitalPosture(
  rating: string | null | undefined,
  holdersAction: string | null | undefined,
  buyersAction: string | null | undefined,
): CapitalPosture {
  const r = (rating ?? '').toUpperCase()
  const h = (holdersAction ?? '').toUpperCase()
  const b = (buyersAction ?? '').toUpperCase()

  if (r === 'STRONG SELL' || r === 'SELL') return 'Reduce'
  if (b === 'AVOID') return 'Avoid'
  if (b === 'WAIT') return 'Deferred'
  if (b === 'BUY NOW' || b === 'SCALE IN') return 'Accumulate'
  if (h === 'REDUCE') return 'Reduce'
  if (h === 'ADD') return 'Accumulate'
  if (h === 'HOLD') return 'Maintain'
  return 'Maintain'
}

export function capitalPostureColor(posture: CapitalPosture): {
  text: string
  bg: string
  border: string
} {
  switch (posture) {
    case 'Accumulate': return { text: 'text-success',        bg: 'bg-success/8',       border: 'border-success/25'  }
    case 'Maintain':   return { text: 'text-primary',        bg: 'bg-primary/8',       border: 'border-primary/25'  }
    case 'Deferred':   return { text: 'text-warning',        bg: 'bg-warning/8',       border: 'border-warning/25'  }
    case 'Reduce':     return { text: 'text-error',          bg: 'bg-error/8',         border: 'border-error/25'    }
    case 'Avoid':      return { text: 'text-text-secondary', bg: 'bg-surface-elevated', border: 'border-border'     }
  }
}

// ---------------------------------------------------------------------------
// Deployment Gate copy — deterministic banner text derived from Tactical Stance
// ---------------------------------------------------------------------------

export function deploymentGateCopy(stance: TacticalStance): { title: string; subtitle: string } {
  switch (stance) {
    case 'Favorable':
    case 'Opportunistic':
      return {
        title: 'Deployment: Active',
        subtitle: 'Conditions support initiating or adding exposure.',
      }
    case 'Deferred':
      return {
        title: 'Deployment: Deferred',
        subtitle: 'Thesis intact, but entry conditions are not favorable at current levels.',
      }
    case 'Constrained':
      return {
        title: 'Deployment: Constrained',
        subtitle: 'Signals/dispersion reduce allowable deployment size; scaling is gated.',
      }
    case 'Defensive':
      return {
        title: 'Deployment: Defensive',
        subtitle: 'Risk regime dominates; prioritize protection over expansion.',
      }
  }
}

/** Returns true when Tactical Stance gates capital deployment. */
export function isDeploymentGated(stance: TacticalStance): boolean {
  return stance === 'Deferred' || stance === 'Constrained' || stance === 'Defensive'
}
