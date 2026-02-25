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
    case 'Bullish': return { text: 'text-success', bg: 'bg-success/10', border: 'border-success/30' }
    case 'Bearish': return { text: 'text-error',   bg: 'bg-error/10',   border: 'border-error/30'   }
    default:        return { text: 'text-warning',  bg: 'bg-warning/10', border: 'border-warning/30' }
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
): 'success' | 'warning' | 'error' | 'default' {
  switch (bias) {
    case 'Bullish': return 'success'
    case 'Bearish': return 'error'
    default:        return 'warning'
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
