/**
 * DVRG Probability & Portfolio Math Engine
 *
 * Probability-weighted outcome modeling for institutional portfolio decision support.
 * All computations are heuristic approximations derived from structural trade parameters —
 * not historical backtests or realized probability distributions.
 *
 * Module 1: Outcome Distribution (per-scenario probability + EV contribution)
 * Module 2: Expected Value Engine (EV, Expected Gain/Loss, Payoff Skew)
 * Module 3: Statistical Stop Risk (stop trigger probability, drawdown path, tail flag)
 * Module 4: Risk Efficiency (EV / ExpectedVolatility, annualized return per unit of risk)
 * Module 5: Portfolio Risk Contribution (beta, vol contribution, correlation sensitivity)
 * Module 6: EV Horizon Anchoring (time-bound EV, annualized expectation, horizon efficiency)
 * Module 7: Volatility Context Layer (regime classification, probability modifiers)
 * Module 8: Cross-Universe Benchmarking (percentile ranks vs. calibrated reference universe)
 * Module 9: Probability Stability Score (model robustness, EV confidence, sensitivity flags)
 * Module 10: Refined Risk Contribution (risk vs. diversification decomposition)
 */

export type RegimeMode = 'STANDARD' | 'MOMENTUM' | 'DISTRESSED' | null | undefined

// ──────────────────────────────────────────────────────────────
// Module 6: EV Horizon Anchoring
// ──────────────────────────────────────────────────────────────

export type HorizonEfficiencyFlag = 'Efficient' | 'Acceptable' | 'Extended' | 'Diluted'

export interface EVHorizonContext {
  primaryHorizon: string          // e.g. "12–18 mo"
  annualizedExpectation: number   // heuristic annualized EV (%)
  horizonEfficiencyFlag: HorizonEfficiencyFlag
  timeLabel: string               // Institutional phrasing: "Expected Value (12–18 mo)"
}

// ──────────────────────────────────────────────────────────────
// Module 7: Volatility Context Layer
// ──────────────────────────────────────────────────────────────

export type VolatilityRegimeState = 'Suppressed' | 'Normal' | 'Elevated' | 'Stress'

export interface VolatilityContext {
  state: VolatilityRegimeState
  percentile: number              // Heuristic vol percentile (0–100)
  regimeModifierActive: boolean   // True when non-Normal or signal conflict active
  stopProbAdjustment: number      // Signed stop prob delta from vol regime
  targetProbCompression: number   // Signed target prob delta from vol regime
}

// ──────────────────────────────────────────────────────────────
// Module 8: Cross-Universe Benchmarking
// ──────────────────────────────────────────────────────────────

export interface UniversePercentiles {
  evPercentile: number              // Higher = better (vs. calibrated universe)
  riskEfficiencyPercentile: number  // Higher = better
  stopRiskPercentile: number        // Higher = lower stop risk (inverted scale)
  payoffSkewPercentile: number      // Higher = more favorable skew
}

// ──────────────────────────────────────────────────────────────
// Module 9: Probability Stability Score
// ──────────────────────────────────────────────────────────────

export type StabilityTier = 'Robust' | 'Stable' | 'Moderate' | 'Fragile' | 'Highly Unstable'
export type EVConfidenceLevel = 'High' | 'Moderate' | 'Low' | 'Unreliable'

export interface ProbabilityStability {
  score: number                   // 0–100 (100 = maximum stability)
  tier: StabilityTier
  stabilityModifierActive: boolean
  modelSensitivityFlag: boolean
  evConfidenceLevel: EVConfidenceLevel
  stabilityAdjustedEV: number     // EV scaled by confidence multiplier
  evBandLow: number               // EV lower uncertainty bound
  evBandHigh: number              // EV upper uncertainty bound
}

// ──────────────────────────────────────────────────────────────
// Module 1 + 2: Outcome Distribution & EV Engine
// ──────────────────────────────────────────────────────────────

export interface OutcomeSlice {
  label: string
  prob: number         // 0–1
  returnPct: number    // signed % return vs entry
  evContrib: number    // P_i × R_i contribution to total EV
}

export interface OutcomeDistribution {
  stop: OutcomeSlice
  targets: OutcomeSlice[]
  // Module 2 outputs
  ev: number                  // Expected Value (%)
  expectedGain: number        // Σ positive EV contributions (%)
  expectedLoss: number        // |negative EV contribution| (%)
  payoffSkew: number          // expectedGain / expectedLoss
  upsideSkew: number          // P-weighted upside magnitude
  downsideSkew: number        // P-weighted downside magnitude
  // Module 4 outputs
  expectedVolatility: number  // std dev of outcome distribution (%)
  riskEfficiency: number      // EV / ExpectedVolatility
  // Module 3 outputs
  stopTriggerProb: number     // 0–1
  stopTailRiskFlag: boolean   // elevated stop probability warning
  expectedDrawdownPath: string
  // Module 6: EV Horizon Anchoring
  horizonContext: EVHorizonContext
  // Module 7: Volatility Context
  volatilityContext: VolatilityContext
  // Module 8: Cross-Universe Benchmarking
  universePercentiles: UniversePercentiles
  // Module 9: Probability Stability Score (also covers Module 10/6 EV confidence)
  probabilityStability: ProbabilityStability
}

export interface ProbabilityEngineParams {
  entry: number
  stopLoss: number
  targets: Array<{ price: number; label: string; sell_pct?: number }>
  regimeMode: RegimeMode
  hasDivergence: boolean
  bearishSignalCount?: number  // signals scoring < 4 out of 10
  signalSpread?: number        // σ across all 7 signals (from signal_breakdown.signal_spread)
}

// ──────────────────────────────────────────────────────────────
// Internal: Module 6 — EV Horizon computation
// ──────────────────────────────────────────────────────────────

function computeEVHorizon(
  ev: number,
  validTargetCount: number,
  regimeMode: RegimeMode,
): EVHorizonContext {
  // Estimate primary holding horizon from target count and regime
  let avgMonths = 12  // default position horizon
  if (regimeMode === 'DISTRESSED') {
    avgMonths = 6
  } else if (validTargetCount <= 1) {
    avgMonths = 6   // T1 only: tactical
  } else if (validTargetCount === 2) {
    avgMonths = 12  // T1 + T2: position horizon
  } else if (validTargetCount === 3) {
    avgMonths = 18  // T1 + T2 + T3: structural re-rating
  } else {
    avgMonths = 24  // T1–T4: regime expansion included
  }

  const primaryHorizon =
    avgMonths <= 6  ? '3–6 mo'   :
    avgMonths <= 12 ? '6–12 mo'  :
    avgMonths <= 18 ? '12–18 mo' : '18–36 mo'

  const years = avgMonths / 12
  const annualizedExpectation = years > 0
    ? Math.round((ev / years) * 100) / 100
    : 0

  const horizonEfficiencyFlag: HorizonEfficiencyFlag =
    annualizedExpectation > 8  ? 'Efficient'  :
    annualizedExpectation > 4  ? 'Acceptable' :
    annualizedExpectation > 2  ? 'Extended'   : 'Diluted'

  const timeLabel = `Expected Value (${primaryHorizon})`

  return { primaryHorizon, annualizedExpectation, horizonEfficiencyFlag, timeLabel }
}

// ──────────────────────────────────────────────────────────────
// Internal: Module 7 — Volatility Context computation
// ──────────────────────────────────────────────────────────────

function computeVolatilityContext(
  stopLossPct: number,    // stop distance as % of entry (ATR proxy)
  regimeMode: RegimeMode,
  hasDivergence: boolean,
): VolatilityContext {
  const state: VolatilityRegimeState =
    stopLossPct < 3  ? 'Suppressed' :
    stopLossPct < 8  ? 'Normal'     :
    stopLossPct < 15 ? 'Elevated'   : 'Stress'

  // Heuristic percentile (calibrated to broad market ATR distribution norms)
  const percentile =
    state === 'Suppressed' ? 22 :
    state === 'Normal'     ? 50 :
    state === 'Elevated'   ? 76 : 91

  const regimeModifierActive = state !== 'Normal' || regimeMode !== 'STANDARD' || hasDivergence

  // Stop probability adjustment from vol regime (additive modifier)
  const stopProbAdjustment =
    state === 'Stress'     ? +0.08 :
    state === 'Elevated'   ? +0.04 :
    state === 'Suppressed' ? -0.03 : 0

  // Target probability compression from elevated vol
  const targetProbCompression =
    state === 'Stress'     ? -0.06 :
    state === 'Elevated'   ? -0.03 :
    state === 'Suppressed' ? +0.02 : 0

  return { state, percentile, regimeModifierActive, stopProbAdjustment, targetProbCompression }
}

// ──────────────────────────────────────────────────────────────
// Internal: Module 8 — Cross-Universe Benchmarking
// ──────────────────────────────────────────────────────────────

function computeUniversePercentiles(
  ev: number,
  riskEfficiency: number,
  stopTriggerProb: number,
  payoffSkew: number,
): UniversePercentiles {
  // Reference distributions (calibrated heuristics from institutional setup universe):
  // EV: typical range −5% to +15%.
  // Clamp input to calibration bounds first so out-of-range EV values produce
  // 0 or 100 (at the boundary) rather than nonsense percentiles.
  const evClamped = Math.max(-5, Math.min(15, ev))
  const evPercentile = Math.round(((evClamped + 5) / 20) * 100)

  // Risk Efficiency: −0.50 to +0.80
  const riskEfficiencyPercentile = Math.round(
    Math.max(0, Math.min(100, ((riskEfficiency + 0.50) / 1.30) * 100))
  )

  // Stop Risk: 10%–50% — inverted (lower stop risk = higher percentile)
  const stopRiskPercentile = Math.round(
    Math.max(0, Math.min(100, (1 - (stopTriggerProb - 0.10) / 0.40) * 100))
  )

  // Payoff Skew: 0.5× to 4.0×
  const payoffSkewPercentile = Math.round(
    Math.max(0, Math.min(100, ((payoffSkew - 0.5) / 3.5) * 100))
  )

  return { evPercentile, riskEfficiencyPercentile, stopRiskPercentile, payoffSkewPercentile }
}

// ──────────────────────────────────────────────────────────────
// Internal: Module 9 — Probability Stability Score
// ──────────────────────────────────────────────────────────────

function computeProbabilityStability(
  ev: number,
  signalSpread: number,
  regimeMode: RegimeMode,
  bearishSignalCount: number,
  hasDivergence: boolean,
  volatilityState: VolatilityRegimeState,
): ProbabilityStability {
  let score = 100

  // Signal dispersion penalty: high spread → models less reliable
  const dispersionPenalty =
    signalSpread < 1.5 ? 0  :
    signalSpread < 2.5 ? 15 :
    signalSpread < 3.5 ? 30 : 45
  score -= dispersionPenalty

  // Regime instability: distressed / momentum = more uncertainty
  const regimePenalty =
    regimeMode === 'DISTRESSED' ? 25 :
    regimeMode === 'MOMENTUM'   ? 10 : 0
  score -= regimePenalty

  // Active signal divergence flag
  score -= hasDivergence ? 20 : 0

  // Bearish signal concentration (each bearish = 5pt, capped 25)
  score -= Math.min(25, bearishSignalCount * 5)

  // Volatility regime instability
  const volPenalty =
    volatilityState === 'Stress'   ? 10 :
    volatilityState === 'Elevated' ? 5  : 0
  score -= volPenalty

  score = Math.max(0, Math.min(100, score))

  const tier: StabilityTier =
    score >= 85 ? 'Robust'          :
    score >= 70 ? 'Stable'          :
    score >= 55 ? 'Moderate'        :
    score >= 40 ? 'Fragile'         : 'Highly Unstable'

  const stabilityModifierActive = score < 70
  const modelSensitivityFlag = score < 55

  const evConfidenceLevel: EVConfidenceLevel =
    score >= 85 ? 'High'       :
    score >= 70 ? 'Moderate'   :
    score >= 55 ? 'Low'        : 'Unreliable'

  // EV confidence multiplier — scales down expectation under uncertainty
  const confidenceMultiplier =
    score >= 85 ? 1.00 :
    score >= 70 ? 0.90 :
    score >= 55 ? 0.75 :
    score >= 40 ? 0.55 : 0.30

  const stabilityAdjustedEV = Math.round(ev * confidenceMultiplier * 100) / 100

  // Confidence band width scales inversely with stability
  const bandWidth =
    score >= 85 ? Math.abs(ev) * 0.20 :
    score >= 70 ? Math.abs(ev) * 0.40 :
    score >= 55 ? Math.abs(ev) * 0.70 : Math.abs(ev) * 1.20

  const evBandLow  = Math.round((ev - bandWidth) * 100) / 100
  const evBandHigh = Math.round((ev + bandWidth) * 100) / 100

  return {
    score,
    tier,
    stabilityModifierActive,
    modelSensitivityFlag,
    evConfidenceLevel,
    stabilityAdjustedEV,
    evBandLow,
    evBandHigh,
  }
}

/**
 * Core computation: probability-weighted outcome distribution.
 *
 * Probability derivation logic:
 *   P_i = BaseProbability × DistanceFactor × TrendFactor × ConflictFactor
 *
 * Where:
 *   DistanceFactor = exp(-Distance_i / (2 × ATR_proxy)) — distance decay
 *   TrendFactor    = regime-aware multiplier (MOMENTUM reduces stop prob)
 *   ConflictFactor = signal divergence multiplier (divergence elevates stop)
 *   ATR_proxy      = entry - stop_loss (stop is placed at ~1 ATR)
 *
 * All raw scores are normalized to sum to 1.0 before use.
 */
export function computeOutcomeDistribution(params: ProbabilityEngineParams): OutcomeDistribution | null {
  const {
    entry,
    stopLoss,
    targets,
    regimeMode,
    hasDivergence,
    bearishSignalCount = 0,
    signalSpread = 1.5,
  } = params

  if (entry <= 0 || stopLoss <= 0 || stopLoss >= entry || targets.length === 0) return null

  const atr = entry - stopLoss  // ATR proxy (stop distance ≈ 1 ATR)
  const stopLossPct = (atr / entry) * 100  // stop distance as % — ATR proxy for vol classification

  // Filter to valid targets above current entry
  const validTargets = targets.filter(t => t.price > entry)
  if (validTargets.length === 0) return null

  // ── Module 7: Volatility Context ───────────────────────────
  const volatilityContext = computeVolatilityContext(stopLossPct, regimeMode, hasDivergence)

  // ── Base probabilities (pre-adjustment) ────────────────────
  const BASE_STOP = 0.22
  const BASE_TARGET = [0.38, 0.26, 0.10, 0.04]  // T1 → T4 (index-based)

  // ── Regime (Trend) modifiers ────────────────────────────────
  const regimeMod = {
    stop:    regimeMode === 'MOMENTUM'   ? 0.72 : regimeMode === 'DISTRESSED' ? 1.42 : 1.00,
    targets: regimeMode === 'MOMENTUM'   ? 1.08 : regimeMode === 'DISTRESSED' ? 0.74 : 1.00,
  }

  // ── Signal conflict modifiers ───────────────────────────────
  const highBearish = bearishSignalCount > 2
  const conflictMod = {
    stop:    hasDivergence ? (highBearish ? 1.38 : 1.22) : 0.92,
    targets: hasDivergence ? 0.87 : 1.04,
  }

  // ── Raw (unnormalized) probability scores ───────────────────
  const rawStop = BASE_STOP * regimeMod.stop * conflictMod.stop

  const rawTargets = validTargets.map((t, i) => {
    const base = BASE_TARGET[Math.min(i, BASE_TARGET.length - 1)]
    const distance = t.price - entry
    const distanceFactor = Math.exp(-distance / (2 * atr))
    return base * distanceFactor * regimeMod.targets * conflictMod.targets
  })

  // ── Normalize to sum = 1.0 ──────────────────────────────────
  const totalRaw = rawStop + rawTargets.reduce((s, v) => s + v, 0)
  if (totalRaw <= 0) return null

  const pStop = rawStop / totalRaw
  const pTargets = rawTargets.map(r => r / totalRaw)

  // ── Returns as % of entry ───────────────────────────────────
  const rStop = ((stopLoss - entry) / entry) * 100
  const rTargets = validTargets.map(t => ((t.price - entry) / entry) * 100)

  // ── EV contributions ────────────────────────────────────────
  const evStop = pStop * rStop
  const evTargets = pTargets.map((p, i) => p * rTargets[i])
  const ev = evStop + evTargets.reduce((s, v) => s + v, 0)

  // ── Module 2: EV summary metrics ────────────────────────────
  const expectedGain = evTargets.reduce((s, v) => s + Math.max(0, v), 0)
  const expectedLoss = Math.abs(evStop)
  const payoffSkew = expectedLoss > 0 ? Math.round((expectedGain / expectedLoss) * 100) / 100 : 0

  const upsideSkew = pTargets.reduce((s, p, i) => s + p * rTargets[i], 0)
  const downsideSkew = Math.abs(pStop * rStop)

  // ── Module 4: Risk Efficiency ───────────────────────────────
  const eR2 = pStop * rStop * rStop + pTargets.reduce((s, p, i) => s + p * rTargets[i] * rTargets[i], 0)
  const variance = eR2 - ev * ev
  const expectedVolatility = variance > 0 ? Math.sqrt(variance) : 0.001
  const riskEfficiency = Math.round((ev / expectedVolatility) * 1000) / 1000

  // ── Module 3: Stop Trigger Probability ─────────────────────
  const BASE_STOP_RISK = 0.20
  const volPressure = 1.0
  const trendMod = regimeMode === 'MOMENTUM' ? 0.75 : regimeMode === 'DISTRESSED' ? 1.38 : 1.00
  const supportMod = hasDivergence ? 1.25 : 1.00
  const stopTriggerProb = Math.min(0.82, BASE_STOP_RISK * volPressure * trendMod * supportMod)
  const stopTailRiskFlag = stopTriggerProb > 0.34 || (hasDivergence && regimeMode === 'DISTRESSED')

  const stopLossPctAbs = Math.abs(rStop)
  const expectedDrawdownPath = hasDivergence
    ? `−${(stopLossPctAbs * 1.2).toFixed(1)}% drawdown path (elevated — signal divergence active)`
    : `−${stopLossPctAbs.toFixed(1)}% to risk control`

  // ── Module 6: EV Horizon Anchoring ─────────────────────────
  const horizonContext = computeEVHorizon(ev, validTargets.length, regimeMode)

  // ── Module 8: Cross-Universe Benchmarking ──────────────────
  const universePercentiles = computeUniversePercentiles(ev, riskEfficiency, stopTriggerProb, payoffSkew)

  // ── Module 9: Probability Stability Score ──────────────────
  const probabilityStability = computeProbabilityStability(
    ev,
    signalSpread,
    regimeMode,
    bearishSignalCount,
    hasDivergence,
    volatilityContext.state,
  )

  return {
    stop: {
      label: 'Stop',
      prob: pStop,
      returnPct: rStop,
      evContrib: evStop,
    },
    targets: validTargets.map((t, i) => ({
      label: t.label,
      prob: pTargets[i],
      returnPct: rTargets[i],
      evContrib: evTargets[i],
    })),
    ev,
    expectedGain,
    expectedLoss,
    payoffSkew,
    upsideSkew,
    downsideSkew,
    expectedVolatility,
    riskEfficiency,
    stopTriggerProb,
    stopTailRiskFlag,
    expectedDrawdownPath,
    horizonContext,
    volatilityContext,
    universePercentiles,
    probabilityStability,
  }
}

// ──────────────────────────────────────────────────────────────
// Module 5 + 10: Portfolio Risk Contribution (refined)
// ──────────────────────────────────────────────────────────────

/** Sector beta proxies — heuristic approximations for factor exposure. */
const SECTOR_BETA: Record<string, number> = {
  Technology:                  1.30,
  'Information Technology':    1.30,
  Financials:                  1.10,
  Healthcare:                  0.82,
  Energy:                      1.18,
  Industrials:                 1.02,
  'Consumer Discretionary':    1.12,
  'Consumer Staples':          0.70,
  Utilities:                   0.62,
  'Real Estate':               0.88,
  Materials:                   1.08,
  'Communication Services':    1.20,
}

/**
 * Factor tilt classification by sector.
 * Returns a concise characterization of the dominant factor exposure.
 */
function getFactorTilt(sector: string, beta: number): string {
  const s = sector.toLowerCase()
  if (s.includes('technology') || s.includes('communication')) return 'Growth / Tech'
  if (s.includes('utilities') || s.includes('staples') || s.includes('real estate')) return 'Defensive / Income'
  if (s.includes('energy') || s.includes('materials') || s.includes('industrials')) return 'Cyclical / Value'
  if (s.includes('healthcare')) return 'Defensive / Growth'
  if (s.includes('financial')) return 'Cyclical / Rate-Sensitive'
  if (s.includes('consumer discret')) return 'Cyclical / Consumer'
  // Fallback by beta
  if (beta > 1.25) return 'High-Beta / Growth'
  if (beta < 0.80) return 'Low-Beta / Defensive'
  return 'Market-Correlated'
}

export function getSectorBeta(sector: string): number {
  if (SECTOR_BETA[sector]) return SECTOR_BETA[sector]
  for (const key of Object.keys(SECTOR_BETA)) {
    if (sector.toLowerCase().includes(key.toLowerCase())) return SECTOR_BETA[key]
  }
  return 1.10  // default market-like beta
}

export interface PortfolioRiskMetrics {
  // Risk Contribution
  betaEstimate: number
  betaCategory: 'Low' | 'Moderate' | 'Elevated'
  betaContributionPct: number        // Position-weight × beta (systematic exposure)
  volContribution: number            // Position's estimated contribution to portfolio vol (%)
  drawdownContribution: number       // Position weight × estimated max drawdown (%)
  // Diversification Profile
  corrImpact: 'Diversifying' | 'Neutral' | 'Concentrating'
  factorTilt: string                 // e.g. "Growth / Tech"
  concentrationImpact: 'Minimal' | 'Moderate' | 'Elevated'
  // Legacy / existing
  expectedDrawdownPath: string
  riskBudgetEfficiency: string
}

export function computePortfolioRiskMetrics(params: {
  positionPct: number      // position size % of portfolio (e.g. 5 = 5%)
  sector: string
  stopLossPct: number      // stop distance as % (e.g. 8 = 8% stop)
  hasDivergence: boolean
  riskEfficiency?: number  // from outcome distribution (EV / vol)
}): PortfolioRiskMetrics {
  const { positionPct, sector, stopLossPct, hasDivergence, riskEfficiency = 0 } = params

  const beta = getSectorBeta(sector)
  const betaCategory: 'Low' | 'Moderate' | 'Elevated' =
    beta < 0.90 ? 'Low' : beta < 1.22 ? 'Moderate' : 'Elevated'

  const positionWeight = positionPct / 100

  // Stock annualized volatility proxy: stop distance × 4
  const stockVolatilityProxy = stopLossPct * 4
  const volContribution = Math.round(positionWeight * stockVolatilityProxy * 100) / 100

  // Systematic (beta) contribution: weight × beta × market vol proxy (assume 15% mkt vol)
  const betaContributionPct = Math.round(positionWeight * beta * 15 * 100) / 100

  // Drawdown contribution: weight × estimated max drawdown (stop × 1.5 heuristic for tail)
  const estMaxDrawdown = stopLossPct * 1.5  // rough 1.5× ATR for tail drawdown
  const drawdownContribution = Math.round(positionWeight * estMaxDrawdown * 100) / 100

  // Correlation / diversification impact: beta-driven
  const corrImpact: 'Diversifying' | 'Neutral' | 'Concentrating' =
    beta < 0.88 ? 'Diversifying' : beta > 1.20 ? 'Concentrating' : 'Neutral'

  // Factor tilt
  const factorTilt = getFactorTilt(sector, beta)

  // Concentration impact: above 5% = elevated; 2–5% = moderate; below 2% = minimal
  const concentrationImpact: 'Minimal' | 'Moderate' | 'Elevated' =
    positionPct > 5 ? 'Elevated' : positionPct > 2 ? 'Moderate' : 'Minimal'

  const expectedDrawdownPath = hasDivergence
    ? `−${(stopLossPct * 1.2).toFixed(1)}% path (elevated — divergence active)`
    : `−${stopLossPct.toFixed(1)}% to risk control`

  const riskBudgetEfficiency =
    riskEfficiency > 0.40  ? 'Efficient — positive EV per unit of risk' :
    riskEfficiency > 0.10  ? 'Marginal — limited return per unit of risk' :
    riskEfficiency > -0.10 ? 'Breakeven — EV near zero; monitor closely' :
                             'Inefficient — negative expected value at current parameters'

  return {
    betaEstimate: Math.round(beta * 100) / 100,
    betaCategory,
    betaContributionPct,
    volContribution,
    drawdownContribution,
    corrImpact,
    factorTilt,
    concentrationImpact,
    expectedDrawdownPath,
    riskBudgetEfficiency,
  }
}
