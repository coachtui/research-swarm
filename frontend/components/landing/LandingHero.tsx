'use client'

import { useEffect, useState } from 'react'
import Link from 'next/link'
import { Button } from '@/components/ui/button'
import { ArrowRight, CheckCircle2, Zap } from 'lucide-react'

/* ─── TSM illustrative data ───────────────────────────────────────────────── */

const SCENARIOS = [
  { label: 'Stop', prob: 35, ret: '−12.0%', positive: false },
  { label: 'T1',   prob: 38, ret: '+14.5%', positive: true  },
  { label: 'T2',   prob: 20, ret: '+20.3%', positive: true  },
  { label: 'T3',   prob:  5, ret: '+29.5%', positive: true  },
  { label: 'T4',   prob:  1, ret: '+48.9%', positive: true  },
]

const MICRO_PROOF = [
  { label: 'Expected Value',   value: '+7.41%', green: true  },
  { label: 'Risk Efficiency',  value: '0.49',   green: true  },
  { label: 'Stop Probability', value: '20%',    green: false },
  { label: 'Final Allocation', value: '6.2%',   green: false },
]

/* ─── Allocation counter hook ─────────────────────────────────────────────── */

function useCountDown(from: number, to: number, delay = 450, duration = 850) {
  const [val, setVal] = useState(from)
  const [done, setDone] = useState(false)

  useEffect(() => {
    const t = setTimeout(() => {
      const t0 = performance.now()
      const tick = (now: number) => {
        const p = Math.min((now - t0) / duration, 1)
        const ease = 1 - Math.pow(1 - p, 3)
        setVal(Math.round((from + (to - from) * ease) * 10) / 10)
        if (p < 1) requestAnimationFrame(tick)
        else { setVal(to); setDone(true) }
      }
      requestAnimationFrame(tick)
    }, delay)
    return () => clearTimeout(t)
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  return { val, done }
}

/* ─── EngineCard ──────────────────────────────────────────────────────────── */

function EngineCard() {
  const { val: allocVal, done: animDone } = useCountDown(8.9, 6.2)

  return (
    <div
      className="w-full rounded-2xl overflow-hidden"
      style={{
        background: 'var(--surface-1)',
        border: '1px solid var(--border-strong)',
        boxShadow:
          '0 12px 48px rgba(0,0,0,0.55), 0 0 0 1px rgba(0,217,181,0.06), inset 0 1px 0 rgba(255,255,255,0.04)',
      }}
    >
      {/* ── Header bar ── */}
      <div
        className="flex items-center justify-between px-5 py-3"
        style={{ borderBottom: '1px solid var(--border)' }}
      >
        <div className="flex items-center gap-2 min-w-0">
          <span
            className="w-1.5 h-1.5 rounded-full shrink-0"
            style={{ background: 'var(--accent)' }}
          />
          <span className="text-[10px] font-semibold uppercase tracking-widest text-text-secondary truncate">
            Capital Allocation Engine
          </span>
        </div>
        <span
          className="ml-3 shrink-0 text-[9px] font-bold uppercase tracking-wider px-2 py-0.5 rounded"
          style={{
            background: 'rgba(245,158,11,0.12)',
            border: '1px solid rgba(245,158,11,0.30)',
            color: '#F59E0B',
          }}
        >
          Execution-Bound
        </span>
      </div>

      {/* ── Dominant allocation zone ── */}
      <div
        className="px-5 pt-5 pb-4"
        style={{ borderBottom: '1px solid var(--border)' }}
      >
        <p className="text-[9px] uppercase tracking-widest text-text-tertiary mb-3">
          Final Allowed Allocation
        </p>
        <div className="flex items-start justify-between gap-6">
          {/* Animated big number */}
          <div className="shrink-0">
            <p
              className="font-bold leading-none tracking-tighter tabular-nums"
              style={{ color: 'var(--accent)', fontSize: '3.25rem' }}
            >
              {allocVal.toFixed(1)}%
            </p>
            <p className="text-xs text-text-secondary mt-2">Satellite Position</p>
          </div>

          {/* Vertical computation ledger */}
          <div className="flex-1 font-mono text-[11px]">
            {/* Row 1 */}
            <div className="flex items-baseline justify-between gap-2 pb-1">
              <span style={{ color: 'var(--text-subtle)' }}>Base Weight</span>
              <span className="font-medium text-text-secondary tabular-nums">8.9%</span>
            </div>
            {/* Row 2 */}
            <div className="flex items-baseline justify-between gap-2 pb-1.5">
              <span style={{ color: 'var(--text-subtle)' }}>
                <span style={{ color: '#F59E0B' }}>×</span> Exec. Multiplier
              </span>
              <span className="font-medium tabular-nums" style={{ color: '#F59E0B' }}>0.7×</span>
            </div>
            {/* Divider */}
            <div className="mb-1.5" style={{ borderTop: '1px solid var(--border-strong)' }} />
            {/* Result row — fades in after animation */}
            <div
              className="flex items-baseline justify-between gap-2 transition-opacity duration-700"
              style={{ opacity: animDone ? 1 : 0 }}
            >
              <span className="font-semibold text-text-primary">Final Allocation</span>
              <span className="font-bold tabular-nums" style={{ color: 'var(--accent)' }}>6.2%</span>
            </div>
            {/* Policy cap note */}
            <p
              className="text-[9px] text-right mt-1.5 leading-none"
              style={{ color: 'var(--text-subtle)' }}
            >
              Policy cap 8.4% applied
            </p>
          </div>
        </div>
      </div>

      {/* ── Outcome distribution ── */}
      <div
        className="px-5 py-3.5"
        style={{ borderBottom: '1px solid var(--border)' }}
      >
        <p className="text-[9px] uppercase tracking-widest text-text-tertiary mb-2">
          Outcome Distribution
        </p>

        {/* Column headers */}
        <div className="grid grid-cols-[2.5rem_1fr_3.5rem] gap-x-2 mb-1">
          {['Scenario', 'Probability', 'Return'].map((h) => (
            <p key={h} className="text-[9px] uppercase tracking-wider text-text-tertiary">
              {h}
            </p>
          ))}
        </div>

        {/* Scenario rows */}
        {SCENARIOS.map(({ label, prob, ret, positive }) => (
          <div
            key={label}
            className="grid grid-cols-[2.5rem_1fr_3.5rem] gap-x-2 items-center py-1"
            style={{ borderTop: '1px solid var(--border)' }}
          >
            <span className="text-xs font-mono font-semibold text-text-primary">{label}</span>
            <div className="flex items-center gap-1.5">
              <div
                className="flex-1 h-[3px] rounded-full overflow-hidden"
                style={{ background: 'rgba(255,255,255,0.07)' }}
              >
                <div
                  className="h-[3px] rounded-full"
                  style={{
                    width: `${prob}%`,
                    background: positive ? 'rgba(16,185,129,0.55)' : 'rgba(239,68,68,0.50)',
                  }}
                />
              </div>
              <span className="text-[10px] font-mono text-text-secondary w-6 text-right shrink-0">
                {prob}%
              </span>
            </div>
            <span
              className="text-[11px] font-mono text-right tabular-nums"
              style={{ color: positive ? '#10B981' : '#EF4444' }}
            >
              {ret}
            </span>
          </div>
        ))}

        {/* EV sub-strip */}
        <div
          className="mt-3 pt-3 grid grid-cols-3"
          style={{ borderTop: '1px solid var(--border)' }}
        >
          <div className="text-center">
            <p className="text-xs font-bold font-mono" style={{ color: '#10B981' }}>+7.41%</p>
            <p className="text-[9px] uppercase tracking-wider text-text-tertiary mt-0.5">Expected Value</p>
          </div>
          <div
            className="text-center"
            style={{ borderLeft: '1px solid var(--border)', borderRight: '1px solid var(--border)' }}
          >
            <p className="text-xs font-bold font-mono text-text-primary">62nd</p>
            <p className="text-[9px] uppercase tracking-wider text-text-tertiary mt-0.5">EV Percentile</p>
            <p className="text-[9px] text-text-tertiary mt-0.5 leading-none">vs calibrated universe</p>
          </div>
          <div className="text-center">
            <p className="text-xs font-bold font-mono" style={{ color: '#10B981' }}>
              0.49
              <span className="text-[9px] font-medium ml-1" style={{ color: 'rgba(16,185,129,0.7)' }}>
                Efficient
              </span>
            </p>
            <p className="text-[9px] uppercase tracking-wider text-text-tertiary mt-0.5">Risk Efficiency</p>
            <p className="text-[9px] text-text-tertiary mt-0.5 leading-none">≥ 0.30 institutional</p>
          </div>
        </div>
      </div>

      {/* ── Risk framing strip ── */}
      <div className="px-5 py-3">
        <div className="flex items-center gap-x-5 gap-y-1 flex-wrap text-xs">
          <div>
            <span className="text-text-tertiary">Stop Trigger Prob.: </span>
            <span className="font-mono font-medium text-text-primary">20%</span>
            <span className="text-text-tertiary ml-1 text-[9px]">(inst. range 15–35%)</span>
          </div>
          <div>
            <span className="text-text-tertiary">Volatility Regime: </span>
            <span className="font-mono font-medium" style={{ color: '#F59E0B' }}>Elevated</span>
          </div>
          <div>
            <span className="text-text-tertiary">Sizing Confidence: </span>
            <span className="font-mono font-medium text-text-primary">Moderate</span>
          </div>
        </div>
      </div>

      {/* ── Footer label ── */}
      <div
        className="px-5 py-2 text-center"
        style={{ borderTop: '1px solid var(--border)' }}
      >
        <p className="text-[9px] uppercase tracking-wider text-text-tertiary">
          Illustrative output — example values only
        </p>
      </div>
    </div>
  )
}

/* ─── LandingHero ─────────────────────────────────────────────────────────── */

export function LandingHero() {
  return (
    <section className="pt-20 pb-16 md:pt-28 md:pb-24">
      <div className="mx-auto max-w-6xl px-4 sm:px-6">
        <div className="grid lg:grid-cols-2 gap-10 lg:gap-16 items-start">

          {/* ── LEFT: Copy ───────────────────────────────────────────────────── */}
          <div className="space-y-6 lg:pt-2">

            {/* Label chip */}
            <div
              className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full text-[11px] font-medium text-primary"
              style={{ background: 'var(--accent-weak)', border: '1px solid var(--accent-border)' }}
            >
              <Zap className="w-3.5 h-3.5 shrink-0" />
              Probabilistic Capital Allocation Engine
            </div>

            {/* Headline */}
            <h1 className="text-[2.25rem] md:text-[2.75rem] font-bold text-text-primary leading-[1.15] tracking-tight">
              Your conviction,
              <br />
              converted into
              <br />
              <span style={{ color: 'var(--accent)' }}>a precise position size.</span>
            </h1>

            {/* Tension line */}
            <p className="text-base md:text-lg font-semibold text-text-primary leading-tight tracking-tight">
              Most research ends at conviction.
              <br />
              DVRG ends at capital allocation.
            </p>

            {/* Edge micro-line */}
            <p className="text-xs leading-snug" style={{ color: 'var(--text-subtle)' }}>
              Capital is deployed only when probabilistic edge exceeds risk threshold.
            </p>

            {/* Micro-proof bullets */}
            <div
              className="rounded-card p-4 space-y-2.5"
              style={{ background: 'var(--surface-1)', border: '1px solid var(--border)' }}
            >
              {MICRO_PROOF.map(({ label, value, green }) => (
                <div key={label} className="flex items-center justify-between gap-4">
                  <span className="text-xs text-text-secondary">• {label}</span>
                  <span
                    className="text-xs font-bold font-mono tabular-nums shrink-0"
                    style={{ color: green ? '#10B981' : 'var(--text-primary)' }}
                  >
                    {value}
                  </span>
                </div>
              ))}
            </div>

            {/* CTAs */}
            <div className="flex flex-col sm:flex-row gap-3 pt-1">
              <Link href="/welcome/free">
                <Button size="lg" className="w-full sm:w-auto">
                  Start Free – 2 Full Reports <ArrowRight className="ml-1.5 w-4 h-4" />
                </Button>
              </Link>
              <Link href="/preview/nvda">
                <Button size="lg" variant="outline" className="w-full sm:w-auto">
                  View Live Example
                </Button>
              </Link>
            </div>

            {/* Trust row */}
            <div
              className="pt-4"
              style={{ borderTop: '1px solid var(--border)' }}
            >
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-y-2.5 gap-x-4">
                {[
                  'Scenario-weighted EV — not single-point forecasts',
                  'Conviction-to-position sizing framework',
                  'Structural noise & stability diagnostics',
                  'Binding allocation output per analysis',
                ].map((item) => (
                  <div key={item} className="flex items-start gap-2 text-xs text-text-secondary">
                    <CheckCircle2 className="w-3.5 h-3.5 text-success shrink-0 mt-0.5" />
                    <span>{item}</span>
                  </div>
                ))}
              </div>
            </div>

            {/* Micro-disclaimer */}
            <p
              className="text-[11px] leading-relaxed max-w-sm"
              style={{ color: 'var(--text-subtle)' }}
            >
              For informational purposes only. Not investment advice. All outputs are
              model-derived. Consult a licensed financial professional before making any
              investment decision.
            </p>
          </div>

          {/* ── RIGHT: Engine card ────────────────────────────────────────────── */}
          <div id="engine-state-container" className="w-full">
            <EngineCard />
          </div>

        </div>
      </div>
    </section>
  )
}

export default LandingHero
