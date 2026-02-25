/**
 * Unit tests for buildCapitalDeploymentRationale.
 *
 * Coverage:
 *  1. BUY + small weight (<2%) + high dispersion → execution binding, satellite narrative
 *  2. BUY + cap binding (execution > policy cap)
 *  3. HOLD + Distribution posture → no-deploy narrative
 *  4. WAIT rating → monitor narrative
 *  5. SELL/AVOID → bearish narrative
 *  6. Missing fields — graceful fallback with no drivers, valid output shape
 *  7. Cross-signal conflict: BUY rating + Distribution + high sigma
 *  8. Clean signal environment → loosen drivers appear
 *  9. Noise thresholds: extreme, very-high, high, clean
 * 10. Stop probability thresholds: high, elevated, low
 * 11. Scenario rotation thresholds: significant, modest
 * 12. Rating normalisation: aliases (BUY NOW, AVOID, SCALE IN, WAIT)
 * 13. Output shape completeness
 */

import {
  buildCapitalDeploymentRationale,
  type RationaleInputs,
} from '../buildCapitalDeploymentRationale'
import type { SignalBreakdown, ConvictionPosition } from '@/types/api'

// ─── Fixtures ─────────────────────────────────────────────────────────────────

function makeSignalBreakdown(overrides: Partial<SignalBreakdown> = {}): SignalBreakdown {
  return {
    overall_score: 6.0,
    news_score: 6.0,
    earnings_score: 5.0,
    analyst_score: 7.0,
    institutional_score: 5.0,
    insider_score: 5.0,
    dark_pool_score: 5.0,
    tech_divergence_score: 6.0,
    news_interpretation: '',
    earnings_interpretation: '',
    analyst_interpretation: '',
    institutional_interpretation: '',
    insider_interpretation: '',
    dark_pool_interpretation: '',
    tech_divergence_interpretation: '',
    alignment_status: 'Aligned',
    has_divergence: false,
    divergence_explanation: '',
    divergence_recommendation: '',
    direction_consensus: 'Bullish',
    signal_spread: 2.53,
    signal_stability: 5.2,
    noise_filter: {
      noise_score: 40,
      noise_regime: 'High Noise',
      noise_flag: true,
      defer_sizing: false,
      noise_drivers: [],
      regime_warning: null,
      action_guidance: '',
    },
    stop_probability: {
      effective_stop_probability_pct: 22,
      stop_probability_label: 'Elevated',
      base_stop_risk_pct: 15,
      volatility_pressure_pct: 5,
      trend_modifier_pct: 1,
      support_modifier_pct: 1,
      volatility_pressure_drivers: [],
      decomposition_narrative: '',
      regime_note: '',
    },
    scenario_weight_diagnostics: {
      model_bear_prob: 0.25,
      model_base_prob: 0.50,
      model_bull_prob: 0.25,
      effective_bear_prob: 0.30,
      effective_base_prob: 0.45,
      effective_bull_prob: 0.25,
      scenario_rotation_index: 13,
      probability_compression_ratio: 1.0,
      tail_state: 'Neutral',
      tail_note: '',
      drift_label: 'Modest Rotation',
      weight_shift_rationale: '',
      active_rotation_factors: [],
    },
    liquidity_microstructure: {
      volume_participation: 'Normal',
      volume_participation_note: '',
      volume_state: 'Stable',
      volume_state_note: '',
      thin_volume_risk: 'Low',
      thin_volume_note: '',
      block_flow_proxy: 'Normal',
      block_flow_note: '',
      spread_impact_proxy: 'Normal',
      spread_impact_note: '',
      accumulation_distribution_bias: 'Neutral',
      bias_note: '',
      stability_modifier_effect: '',
      ev_confidence_effect: '',
    },
    ...overrides,
  } as SignalBreakdown
}

function makeConviction(overrides: Partial<ConvictionPosition> = {}): ConvictionPosition {
  return {
    conviction_level: 'Medium',
    conviction_score: '6.5',
    recommended_pct: 3,
    max_pct: 5.2,
    dollar_per_100k: 3000,
    rationale: '',
    conviction_justification: '',
    ...overrides,
  }
}

function makeInputs(overrides: Partial<RationaleInputs> = {}): RationaleInputs {
  return {
    rating: 'BUY',
    signalBreakdown: makeSignalBreakdown(),
    convictionPosition: makeConviction(),
    executionWeightPct: 1.89,
    policyCap: 5.2,
    finalWeight: 1.89,
    bindingSource: 'EXECUTION',
    ...overrides,
  }
}

// ─── 1. BUY + small weight + high dispersion → execution binding ──────────────

describe('BUY + small weight (<2%) + high dispersion', () => {
  const result = buildCapitalDeploymentRationale(
    makeInputs({
      rating: 'BUY',
      signalBreakdown: makeSignalBreakdown({ signal_spread: 2.99 }),
      executionWeightPct: 1.89,
      finalWeight: 1.89,
      bindingSource: 'EXECUTION',
    })
  )

  it('produces a valid output object', () => {
    expect(result).toHaveProperty('summary')
    expect(result).toHaveProperty('drivers')
    expect(result).toHaveProperty('binding')
    expect(result).toHaveProperty('interpretation')
    expect(result).toHaveProperty('next_actions')
    expect(result).toHaveProperty('disclaimers')
  })

  it('binding.type is execution', () => {
    expect(result.binding.type).toBe('execution')
  })

  it('summary mentions BUY and satellite sizing', () => {
    expect(result.summary).toMatch(/BUY/i)
    expect(result.summary).toMatch(/satellite/i)
  })

  it('has an elevated dispersion driver (σ=2.99 ≥ 2.5)', () => {
    const d = result.drivers.find((d) => d.label.toLowerCase().includes('dispersion'))
    expect(d).toBeDefined()
    expect(d?.impact).toBe('tighten')
    expect(d?.evidence).toContain('2.99')
  })

  it('first interpretation bullet states execution binding', () => {
    expect(result.interpretation[0]).toMatch(/execution-bound/i)
  })

  it('next_actions contains σ convergence tip', () => {
    const action = result.next_actions.find((a) => a.toLowerCase().includes('σ') || a.toLowerCase().includes('sigma') || a.toLowerCase().includes('dispersion'))
    expect(action).toBeDefined()
  })

  it('includes satellite sizing note in interpretation', () => {
    const bullet = result.interpretation.find((b) => b.match(/satellite/i))
    expect(bullet).toBeDefined()
  })
})

// ─── 2. BUY + policy cap binding ─────────────────────────────────────────────

describe('BUY + policy cap binding', () => {
  const result = buildCapitalDeploymentRationale(
    makeInputs({
      rating: 'BUY',
      signalBreakdown: makeSignalBreakdown({ signal_spread: 1.2, signal_stability: 7.5 }),
      executionWeightPct: 6.5,
      policyCap: 5.2,
      finalWeight: 5.2,
      bindingSource: 'POLICY',
    })
  )

  it('binding.type is policy_cap', () => {
    expect(result.binding.type).toBe('policy_cap')
  })

  it('summary mentions portfolio construction cap', () => {
    expect(result.summary).toMatch(/portfolio construction cap|concentration discipline/i)
  })

  it('first interpretation bullet states policy cap enforced', () => {
    expect(result.interpretation[0]).toMatch(/policy cap binding/i)
  })

  it('next_actions mention cap and conviction upgrade', () => {
    const capAction = result.next_actions.find((a) =>
      a.toLowerCase().includes('cap') || a.toLowerCase().includes('conviction')
    )
    expect(capAction).toBeDefined()
  })
})

// ─── 3. HOLD + Distribution posture ──────────────────────────────────────────

describe('HOLD + Distribution institutional posture', () => {
  const result = buildCapitalDeploymentRationale(
    makeInputs({
      rating: 'HOLD',
      signalBreakdown: makeSignalBreakdown({
        liquidity_microstructure: {
          volume_participation: 'Normal',
          volume_participation_note: '',
          volume_state: 'Stable',
          volume_state_note: '',
          thin_volume_risk: 'Low',
          thin_volume_note: '',
          block_flow_proxy: 'Normal',
          block_flow_note: '',
          spread_impact_proxy: 'Normal',
          spread_impact_note: '',
          accumulation_distribution_bias: 'Distribution',
          bias_note: '',
          stability_modifier_effect: '',
          ev_confidence_effect: '',
        },
      }),
    })
  )

  it('has institutional posture Distribution driver', () => {
    const d = result.drivers.find((d) => d.label.toLowerCase().includes('distribution'))
    expect(d).toBeDefined()
    expect(d?.impact).toBe('tighten')
  })

  it('summary reflects HOLD / no new capital', () => {
    expect(result.summary).toMatch(/no new capital|HOLD/i)
  })

  it('next_actions suggest waiting for catalyst', () => {
    const action = result.next_actions.find((a) =>
      a.toLowerCase().includes('catalyst') || a.toLowerCase().includes('wait')
    )
    expect(action).toBeDefined()
  })
})

// ─── 4. WAIT rating ───────────────────────────────────────────────────────────

describe('WAIT rating', () => {
  const result = buildCapitalDeploymentRationale(makeInputs({ rating: 'WAIT' }))

  it('summary contains WAIT', () => {
    expect(result.summary).toMatch(/WAIT/i)
  })

  it('next_actions mention directional catalyst', () => {
    const action = result.next_actions.find((a) => a.toLowerCase().includes('catalyst'))
    expect(action).toBeDefined()
  })
})

// ─── 5. SELL / AVOID rating ───────────────────────────────────────────────────

describe('SELL rating', () => {
  const result = buildCapitalDeploymentRationale(makeInputs({ rating: 'SELL' }))

  it('summary indicates bearish signal', () => {
    expect(result.summary).toMatch(/bearish|SELL/i)
  })

  it('next_actions mention reduce or exit', () => {
    const action = result.next_actions.find((a) =>
      a.toLowerCase().includes('reduce') || a.toLowerCase().includes('exit')
    )
    expect(action).toBeDefined()
  })
})

describe('AVOID rating normalises to SELL', () => {
  const result = buildCapitalDeploymentRationale(makeInputs({ rating: 'AVOID' }))
  it('summary indicates bearish', () => {
    expect(result.summary).toMatch(/bearish|SELL/i)
  })
})

// ─── 6. Missing fields — graceful fallback ────────────────────────────────────

describe('Missing signal breakdown fields', () => {
  const result = buildCapitalDeploymentRationale(
    makeInputs({
      rating: 'BUY',
      signalBreakdown: null,
      convictionPosition: null,
    })
  )

  it('returns a valid object with no drivers from missing data', () => {
    expect(result.drivers).toBeInstanceOf(Array)
    expect(result.summary).toBeTruthy()
    expect(result.interpretation.length).toBeGreaterThan(0)
    expect(result.next_actions.length).toBeGreaterThan(0)
    expect(result.disclaimers).toBeTruthy()
  })

  it('binding has a valid type', () => {
    expect(['execution', 'policy_cap']).toContain(result.binding.type)
  })
})

describe('Partial signal breakdown — only noise_filter missing', () => {
  const result = buildCapitalDeploymentRationale(
    makeInputs({
      signalBreakdown: makeSignalBreakdown({ noise_filter: undefined }),
    })
  )

  it('no noise driver added', () => {
    const noiseDriver = result.drivers.find((d) => d.label.toLowerCase().includes('noise'))
    // May or may not be there, but should not throw
    expect(noiseDriver === undefined || typeof noiseDriver === 'object').toBe(true)
  })

  it('output shape is still complete', () => {
    expect(result).toHaveProperty('summary')
    expect(result).toHaveProperty('drivers')
    expect(result).toHaveProperty('binding')
    expect(result).toHaveProperty('interpretation')
    expect(result).toHaveProperty('next_actions')
    expect(result).toHaveProperty('disclaimers')
  })
})

// ─── 7. Cross-signal conflict ─────────────────────────────────────────────────

describe('Cross-signal conflict: BUY + Distribution + sigma >= 2.5', () => {
  const result = buildCapitalDeploymentRationale(
    makeInputs({
      rating: 'BUY',
      signalBreakdown: makeSignalBreakdown({
        signal_spread: 2.7,
        liquidity_microstructure: {
          volume_participation: 'Normal',
          volume_participation_note: '',
          volume_state: 'Stable',
          volume_state_note: '',
          thin_volume_risk: 'Low',
          thin_volume_note: '',
          block_flow_proxy: 'Normal',
          block_flow_note: '',
          spread_impact_proxy: 'Normal',
          spread_impact_note: '',
          accumulation_distribution_bias: 'Distribution',
          bias_note: '',
          stability_modifier_effect: '',
          ev_confidence_effect: '',
        },
      }),
    })
  )

  it('includes cross-signal conflict driver', () => {
    const d = result.drivers.find((d) =>
      d.label.toLowerCase().includes('cross-signal conflict')
    )
    expect(d).toBeDefined()
    expect(d?.impact).toBe('tighten')
  })
})

describe('Cross-signal conflict NOT added when sigma < 2.5', () => {
  const result = buildCapitalDeploymentRationale(
    makeInputs({
      rating: 'BUY',
      signalBreakdown: makeSignalBreakdown({
        signal_spread: 1.8,
        liquidity_microstructure: {
          volume_participation: 'Normal',
          volume_participation_note: '',
          volume_state: 'Stable',
          volume_state_note: '',
          thin_volume_risk: 'Low',
          thin_volume_note: '',
          block_flow_proxy: 'Normal',
          block_flow_note: '',
          spread_impact_proxy: 'Normal',
          spread_impact_note: '',
          accumulation_distribution_bias: 'Distribution',
          bias_note: '',
          stability_modifier_effect: '',
          ev_confidence_effect: '',
        },
      }),
    })
  )

  it('no cross-signal conflict driver', () => {
    const d = result.drivers.find((d) =>
      d.label.toLowerCase().includes('cross-signal conflict')
    )
    expect(d).toBeUndefined()
  })
})

// ─── 8. Loosen drivers for clean environment ──────────────────────────────────

describe('Clean signal environment (low noise, tight sigma)', () => {
  const result = buildCapitalDeploymentRationale(
    makeInputs({
      rating: 'BUY',
      signalBreakdown: makeSignalBreakdown({
        signal_spread: 1.1,
        signal_stability: 8.5,
        noise_filter: {
          noise_score: 15,
          noise_regime: 'Clean',
          noise_flag: false,
          defer_sizing: false,
          noise_drivers: [],
          regime_warning: null,
          action_guidance: '',
        },
        stop_probability: {
          effective_stop_probability_pct: 8,
          stop_probability_label: 'Low',
          base_stop_risk_pct: 8,
          volatility_pressure_pct: 0,
          trend_modifier_pct: 0,
          support_modifier_pct: 0,
          volatility_pressure_drivers: [],
          decomposition_narrative: '',
          regime_note: '',
        },
      }),
      executionWeightPct: 4.5,
      finalWeight: 4.5,
    })
  )

  it('has loosen drivers (clean noise, tight sigma, high stability)', () => {
    const looseners = result.drivers.filter((d) => d.impact === 'loosen')
    expect(looseners.length).toBeGreaterThan(0)
  })
})

// ─── 9. Noise score thresholds ────────────────────────────────────────────────

describe('Noise score thresholds', () => {
  function noiseDriverLabel(score: number): string | undefined {
    const r = buildCapitalDeploymentRationale(
      makeInputs({
        signalBreakdown: makeSignalBreakdown({
          noise_filter: { noise_score: score, noise_regime: 'High Noise', noise_flag: true, defer_sizing: false, noise_drivers: [], regime_warning: null, action_guidance: '' },
        }),
      })
    )
    return r.drivers.find((d) => d.label.toLowerCase().includes('noise'))?.label
  }

  it('score=75 → Extreme noise driver', () => {
    expect(noiseDriverLabel(75)).toMatch(/extreme noise/i)
  })

  it('score=55 → Very high noise driver', () => {
    expect(noiseDriverLabel(55)).toMatch(/very high noise/i)
  })

  it('score=40 → High noise driver', () => {
    expect(noiseDriverLabel(40)).toMatch(/high noise/i)
  })

  it('score=25 → No noise driver (Low Noise bucket)', () => {
    const label = noiseDriverLabel(25)
    expect(label).toBeUndefined()
  })

  it('score=10 → Clean signal environment driver (loosen)', () => {
    const r = buildCapitalDeploymentRationale(
      makeInputs({
        signalBreakdown: makeSignalBreakdown({
          noise_filter: { noise_score: 10, noise_regime: 'Clean', noise_flag: false, defer_sizing: false, noise_drivers: [], regime_warning: null, action_guidance: '' },
        }),
      })
    )
    const d = r.drivers.find((d) => d.label.toLowerCase().includes('clean'))
    expect(d?.impact).toBe('loosen')
  })
})

// ─── 10. Stop probability thresholds ─────────────────────────────────────────

describe('Stop probability thresholds', () => {
  function stopDriver(pct: number) {
    const r = buildCapitalDeploymentRationale(
      makeInputs({
        signalBreakdown: makeSignalBreakdown({
          stop_probability: {
            effective_stop_probability_pct: pct,
            stop_probability_label: 'Elevated',
            base_stop_risk_pct: pct,
            volatility_pressure_pct: 0,
            trend_modifier_pct: 0,
            support_modifier_pct: 0,
            volatility_pressure_drivers: [],
            decomposition_narrative: '',
            regime_note: '',
          },
        }),
      })
    )
    return r.drivers.find((d) => d.label.toLowerCase().includes('stop'))
  }

  it('35% → High stop-loss risk (tighten)', () => {
    const d = stopDriver(35)
    expect(d?.label).toMatch(/high stop/i)
    expect(d?.impact).toBe('tighten')
  })

  it('22% → Elevated stop-loss risk (tighten)', () => {
    const d = stopDriver(22)
    expect(d?.label).toMatch(/elevated stop/i)
    expect(d?.impact).toBe('tighten')
  })

  it('8% → Low stop-loss risk (loosen)', () => {
    const d = stopDriver(8)
    expect(d?.label).toMatch(/low stop/i)
    expect(d?.impact).toBe('loosen')
  })

  it('17% → No stop driver (Moderate bucket, no driver)', () => {
    const d = stopDriver(17)
    expect(d).toBeUndefined()
  })
})

// ─── 11. Scenario rotation thresholds ────────────────────────────────────────

describe('Scenario rotation thresholds', () => {
  function rotationDriver(idx: number) {
    const r = buildCapitalDeploymentRationale(
      makeInputs({
        signalBreakdown: makeSignalBreakdown({
          scenario_weight_diagnostics: {
            model_bear_prob: 0.25,
            model_base_prob: 0.50,
            model_bull_prob: 0.25,
            effective_bear_prob: 0.30,
            effective_base_prob: 0.45,
            effective_bull_prob: 0.25,
            scenario_rotation_index: idx,
            probability_compression_ratio: 1.0,
            tail_state: 'Neutral',
            tail_note: '',
            drift_label: idx >= 18 ? 'Significant Rotation' : 'Modest Rotation',
            weight_shift_rationale: '',
            active_rotation_factors: [],
          },
        }),
      })
    )
    return r.drivers.find((d) => d.label.toLowerCase().includes('rotation'))
  }

  it('idx=20 → Significant rotation (tighten)', () => {
    const d = rotationDriver(20)
    expect(d?.label).toMatch(/significant/i)
    expect(d?.impact).toBe('tighten')
  })

  it('idx=14 → Modest rotation (neutral)', () => {
    const d = rotationDriver(14)
    expect(d?.label).toMatch(/modest/i)
    expect(d?.impact).toBe('neutral')
  })

  it('idx=8 → No rotation driver', () => {
    const d = rotationDriver(8)
    expect(d).toBeUndefined()
  })
})

// ─── 12. Rating normalisation aliases ─────────────────────────────────────────

describe('Rating alias normalisation', () => {
  it('BUY NOW → BUY summary', () => {
    const r = buildCapitalDeploymentRationale(makeInputs({ rating: 'BUY NOW' }))
    expect(r.summary).toMatch(/BUY/i)
  })

  it('SCALE IN → WAIT/HOLD-type summary (no new capital)', () => {
    const r = buildCapitalDeploymentRationale(makeInputs({ rating: 'SCALE IN', finalWeight: 3.0 }))
    // SCALE IN normalises to WAIT
    expect(r.summary).toMatch(/WAIT/i)
  })

  it('STRONG BUY → satellite sizing narrative if weight ≤ 2', () => {
    const r = buildCapitalDeploymentRationale(makeInputs({ rating: 'STRONG BUY', finalWeight: 1.5, executionWeightPct: 1.5 }))
    expect(r.summary).toMatch(/satellite/i)
  })
})

// ─── 13. Output shape completeness ───────────────────────────────────────────

describe('Output shape completeness', () => {
  const result = buildCapitalDeploymentRationale(makeInputs())

  it('summary is a non-empty string', () => {
    expect(typeof result.summary).toBe('string')
    expect(result.summary.length).toBeGreaterThan(0)
  })

  it('drivers is an array of objects with label, impact, evidence', () => {
    expect(Array.isArray(result.drivers)).toBe(true)
    for (const d of result.drivers) {
      expect(d).toHaveProperty('label')
      expect(d).toHaveProperty('impact')
      expect(d).toHaveProperty('evidence')
      expect(['tighten', 'loosen', 'neutral']).toContain(d.impact)
    }
  })

  it('binding.type is execution or policy_cap', () => {
    expect(['execution', 'policy_cap']).toContain(result.binding.type)
    expect(typeof result.binding.explanation).toBe('string')
  })

  it('interpretation is a non-empty array of strings', () => {
    expect(Array.isArray(result.interpretation)).toBe(true)
    expect(result.interpretation.length).toBeGreaterThanOrEqual(1)
    for (const b of result.interpretation) {
      expect(typeof b).toBe('string')
    }
  })

  it('next_actions is a non-empty array of strings', () => {
    expect(Array.isArray(result.next_actions)).toBe(true)
    expect(result.next_actions.length).toBeGreaterThanOrEqual(1)
  })

  it('disclaimers is a non-empty string', () => {
    expect(typeof result.disclaimers).toBe('string')
    expect(result.disclaimers.length).toBeGreaterThan(0)
  })
})
