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
 */

export type RegimeMode = 'STANDARD' | 'MOMENTUM' | 'DISTRESSED' | null | undefined

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
}

export interface ProbabilityEngineParams {
  entry: number
  stopLoss: number
  targets: Array<{ price: number; label: string; sell_pct?: number }>
  regimeMode: RegimeMode
  hasDivergence: boolean
  bearishSignalCount?: number  // signals scoring < 4 out of 10
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
  const { entry, stopLoss, targets, regimeMode, hasDivergence, bearishSignalCount = 0 } = params

  if (entry <= 0 || stopLoss <= 0 || stopLoss >= entry || targets.length === 0) return null

  const atr = entry - stopLoss  // ATR proxy (stop distance ≈ 1 ATR)

  // Filter to valid targets above current entry
  const validTargets = targets.filter(t => t.price > entry)
  if (validTargets.length === 0) return null

  // ── Base probabilities (pre-adjustment) ────────────────────
  // Stop receives fixed base; targets receive position-indexed decaying bases
  const BASE_STOP = 0.22
  const BASE_TARGET = [0.38, 0.26, 0.10, 0.04]  // T1 → T4 (index-based)

  // ── Regime (Trend) modifiers ────────────────────────────────
  // MOMENTUM  → trend is intact, stops less likely, near-term targets more likely
  // DISTRESSED → structure broken, stops elevated, far targets suppressed
  const regimeMod = {
    stop:    regimeMode === 'MOMENTUM'   ? 0.72 : regimeMode === 'DISTRESSED' ? 1.42 : 1.00,
    targets: regimeMode === 'MOMENTUM'   ? 1.08 : regimeMode === 'DISTRESSED' ? 0.74 : 1.00,
  }

  // ── Signal conflict modifiers ───────────────────────────────
  // Active divergence: stop risk elevated, target probability compressed
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
    // Distance decay: exponential — further targets are harder to reach
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

  // Upside/downside skew = probability-weighted magnitude
  const upsideSkew = pTargets.reduce((s, p, i) => s + p * rTargets[i], 0)
  const downsideSkew = Math.abs(pStop * rStop)

  // ── Module 4: Risk Efficiency ───────────────────────────────
  // ExpectedVolatility = sqrt(E[R²] - E[R]²) — std dev of return distribution
  const eR2 = pStop * rStop * rStop + pTargets.reduce((s, p, i) => s + p * rTargets[i] * rTargets[i], 0)
  const variance = eR2 - ev * ev
  const expectedVolatility = variance > 0 ? Math.sqrt(variance) : 0.001
  const riskEfficiency = Math.round((ev / expectedVolatility) * 1000) / 1000

  // ── Module 3: Stop Trigger Probability ─────────────────────
  // P(StopHit) = BaseStopRisk × VolatilityPressure × TrendModifier × SupportModifier
  // VolatilityPressure = ATR / DistanceToStop = 1.0 by design (stop ≈ 1 ATR)
  const BASE_STOP_RISK = 0.20
  const volPressure = 1.0
  const trendMod = regimeMode === 'MOMENTUM' ? 0.75 : regimeMode === 'DISTRESSED' ? 1.38 : 1.00
  const supportMod = hasDivergence ? 1.25 : 1.00
  const stopTriggerProb = Math.min(0.82, BASE_STOP_RISK * volPressure * trendMod * supportMod)
  const stopTailRiskFlag = stopTriggerProb > 0.34 || (hasDivergence && regimeMode === 'DISTRESSED')

  const stopLossPct = Math.abs(rStop)
  const expectedDrawdownPath = hasDivergence
    ? `−${(stopLossPct * 1.2).toFixed(1)}% drawdown path (elevated — signal divergence active)`
    : `−${stopLossPct.toFixed(1)}% to risk control`

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
  }
}

// ──────────────────────────────────────────────────────────────
// Module 5: Portfolio Risk Contribution
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

export function getSectorBeta(sector: string): number {
  // Exact match first, then partial match
  if (SECTOR_BETA[sector]) return SECTOR_BETA[sector]
  for (const key of Object.keys(SECTOR_BETA)) {
    if (sector.toLowerCase().includes(key.toLowerCase())) return SECTOR_BETA[key]
  }
  return 1.10  // default market-like beta
}

export interface PortfolioRiskMetrics {
  betaEstimate: number
  betaCategory: 'Low' | 'Moderate' | 'Elevated'
  volContribution: number        // position's estimated contribution to portfolio vol (%)
  corrImpact: 'Diversifying' | 'Neutral' | 'Concentrating'
  expectedDrawdownPath: string   // qualitative description
  riskBudgetEfficiency: string   // qualitative efficiency label
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

  // Stock annualized volatility proxy: stop distance × 4 (rough annualization heuristic)
  // E.g. 8% stop → ~32% annualized vol proxy
  const stockVolatilityProxy = stopLossPct * 4
  const positionWeight = positionPct / 100
  // Volatility contribution ≈ position weight × stock vol (simplified marginal contribution)
  const volContribution = Math.round(positionWeight * stockVolatilityProxy * 100) / 100

  // Correlation / diversification impact: beta-driven heuristic
  const corrImpact: 'Diversifying' | 'Neutral' | 'Concentrating' =
    beta < 0.88 ? 'Diversifying' : beta > 1.20 ? 'Concentrating' : 'Neutral'

  const expectedDrawdownPath = hasDivergence
    ? `−${(stopLossPct * 1.2).toFixed(1)}% path (elevated — divergence active)`
    : `−${stopLossPct.toFixed(1)}% to risk control`

  // Risk budget efficiency narrative from EV/vol ratio
  const riskBudgetEfficiency =
    riskEfficiency > 0.40  ? 'Efficient — positive EV per unit of risk' :
    riskEfficiency > 0.10  ? 'Marginal — limited return per unit of risk' :
    riskEfficiency > -0.10 ? 'Breakeven — EV near zero; monitor closely' :
                             'Inefficient — negative expected value at current parameters'

  return {
    betaEstimate: Math.round(beta * 100) / 100,
    betaCategory,
    volContribution,
    corrImpact,
    expectedDrawdownPath,
    riskBudgetEfficiency,
  }
}
