'use client'

import { useCallback, useEffect, useRef, useState } from 'react'
import Link from 'next/link'
import { Button } from '@/components/ui/button'
import { ArrowRight, CheckCircle2, Zap } from 'lucide-react'

/* ─── Types ───────────────────────────────────────────────────────────────── */

type StateKey = 'press' | 'hold' | 'avoid'

interface ScenarioRow {
  label: string
  prob: number
  ret: string
  evContrib: number
  positive: boolean
}

interface EngineStateData {
  allocation: number
  baseWeight: number
  multiplier: number
  totalEvStr: string
  riskEff: number
  stopProb: number       // decimal, e.g. 0.20
  stopProbStr: string
  evPercentile: string
  badge: string
  badgeColor: string
  badgeBg: string
  badgeBorder: string
  regime: string
  regimeColor: string
  policyCap: string
  scenarios: ScenarioRow[]
}

/* ─── State data ──────────────────────────────────────────────────────────── */

const STATES: Record<StateKey, EngineStateData> = {
  hold: {
    allocation: 6.2,
    baseWeight: 8.9,
    multiplier: 0.70,
    totalEvStr: '+7.41%',
    riskEff: 0.49,
    stopProb: 0.20,
    stopProbStr: '20%',
    evPercentile: '62nd',
    badge: 'Execution-Bound',
    badgeColor: '#F59E0B',
    badgeBg: 'rgba(245,158,11,0.12)',
    badgeBorder: 'rgba(245,158,11,0.30)',
    regime: 'Elevated',
    regimeColor: '#F59E0B',
    policyCap: 'Policy cap 8.4% applied',
    scenarios: [
      { label: 'Stop', prob: 35, ret: '−12.0%', evContrib: -4.20, positive: false },
      { label: 'T1',   prob: 38, ret: '+14.5%', evContrib:  5.51, positive: true  },
      { label: 'T2',   prob: 20, ret: '+20.3%', evContrib:  4.06, positive: true  },
      { label: 'T3',   prob:  5, ret: '+29.5%', evContrib:  1.48, positive: true  },
      { label: 'T4',   prob:  1, ret: '+48.9%', evContrib:  0.49, positive: true  },
    ],
  },
  press: {
    allocation: 8.4,
    baseWeight: 8.9,
    multiplier: 1.00,
    totalEvStr: '+12.6%',
    riskEff: 0.63,
    stopProb: 0.18,
    stopProbStr: '18%',
    evPercentile: '78th',
    badge: 'Press Advantage',
    badgeColor: '#10B981',
    badgeBg: 'rgba(16,185,129,0.12)',
    badgeBorder: 'rgba(16,185,129,0.30)',
    regime: 'Favorable',
    regimeColor: '#10B981',
    policyCap: 'Policy cap binding at 8.4%',
    scenarios: [
      { label: 'Stop', prob: 18, ret: '−11.0%', evContrib: -1.98, positive: false },
      { label: 'T1',   prob: 42, ret: '+14.5%', evContrib:  6.09, positive: true  },
      { label: 'T2',   prob: 28, ret: '+18.0%', evContrib:  5.04, positive: true  },
      { label: 'T3',   prob: 10, ret: '+26.0%', evContrib:  2.60, positive: true  },
      { label: 'T4',   prob:  2, ret: '+44.0%', evContrib:  0.88, positive: true  },
    ],
  },
  avoid: {
    allocation: 0.8,
    baseWeight: 5.0,
    multiplier: 0.15,
    totalEvStr: '+1.1%',
    riskEff: 0.18,
    stopProb: 0.42,
    stopProbStr: '42%',
    evPercentile: '28th',
    badge: 'Risk-Off',
    badgeColor: '#EF4444',
    badgeBg: 'rgba(239,68,68,0.12)',
    badgeBorder: 'rgba(239,68,68,0.30)',
    regime: 'Stressed',
    regimeColor: '#EF4444',
    policyCap: 'Capital preserved — no deployment',
    scenarios: [
      { label: 'Stop', prob: 42, ret: '−11.5%', evContrib: -4.83, positive: false },
      { label: 'T1',   prob: 33, ret:  '+7.5%', evContrib:  2.48, positive: true  },
      { label: 'T2',   prob: 16, ret: '+11.0%', evContrib:  1.76, positive: true  },
      { label: 'T3',   prob:  6, ret: '+16.0%', evContrib:  0.96, positive: true  },
      { label: 'T4',   prob:  3, ret: '+24.0%', evContrib:  0.72, positive: true  },
    ],
  },
}

const TOGGLE_BUTTONS: { key: StateKey; label: string }[] = [
  { key: 'press', label: 'Press Advantage' },
  { key: 'hold',  label: 'Execution-Bound' },
  { key: 'avoid', label: 'Risk-Off' },
]

const MICRO_PROOF = [
  { label: 'Expected Value',   value: '+7.41%', green: true  },
  { label: 'Risk Efficiency',  value: '0.49',   green: true  },
  { label: 'Stop Probability', value: '20%',    green: false },
  { label: 'Final Allocation', value: '6.2%',   green: false },
]

/* ─── Probability Distribution Curve ─────────────────────────────────────── */

function ProbDistCurve({ stopProb }: { stopProb: number }) {
  const W = 280
  const H = 54
  const padX = 6
  const innerW = W - padX * 2
  const baseY = H - 2

  // Bell curve: center right-of-middle (positive EV skew)
  const mu = 0.58
  const sigma = 0.17
  const gauss = (x: number) => Math.exp(-0.5 * ((x - mu) / sigma) ** 2)

  const N = 100
  const pts: [number, number][] = []
  for (let i = 0; i <= N; i++) {
    const xn = i / N
    pts.push([xn, gauss(xn)])
  }
  const maxY = Math.max(...pts.map(([, y]) => y))
  const norm = pts.map(([x, y]): [number, number] => [x, y / maxY])

  const toSvg = ([xn, yn]: [number, number]) =>
    `${(padX + xn * innerW).toFixed(1)},${(baseY - yn * (H - 10)).toFixed(1)}`

  // Visual mapping: stopProb [0.15, 0.45] → cutoffNorm [0.22, 0.40]
  const rawCutoff = 0.22 + ((stopProb - 0.15) / 0.30) * 0.18
  const cutoffNorm = Math.max(0.14, Math.min(0.44, rawCutoff))
  const cutoffX = (padX + cutoffNorm * innerW).toFixed(1)

  // Expansion tail start
  const expNorm = 0.83
  const expX = (padX + expNorm * innerW).toFixed(1)
  const rightEndX = (padX + innerW).toFixed(1)

  // Left fill path (stop zone)
  const leftPts = norm.filter(([x]) => x <= cutoffNorm)
  const leftArea =
    `M ${padX},${baseY} ` +
    leftPts.map(toSvg).join(' ') +
    ` L ${cutoffX},${baseY} Z`

  // Right fill path (expansion tail)
  const rightPts = norm.filter(([x]) => x >= expNorm)
  const rightArea =
    `M ${expX},${baseY} ` +
    rightPts.map(toSvg).join(' ') +
    ` L ${rightEndX},${baseY} Z`

  return (
    <div>
      <svg
        width="100%"
        viewBox={`0 0 ${W} ${H}`}
        style={{ display: 'block', overflow: 'visible' }}
        aria-hidden
      >
        <path d={leftArea}  fill="rgba(239,68,68,0.22)" />
        <path d={rightArea} fill="rgba(16,185,129,0.20)" />
        <polyline
          points={norm.map(toSvg).join(' ')}
          fill="none"
          stroke="rgba(255,255,255,0.22)"
          strokeWidth="1.5"
          strokeLinejoin="round"
        />
        <line
          x1={cutoffX} y1="2"
          x2={cutoffX} y2={String(baseY)}
          stroke="rgba(239,68,68,0.38)"
          strokeWidth="1"
          strokeDasharray="2,3"
        />
      </svg>
      <div className="grid grid-cols-3 mt-0.5">
        <span className="text-[9px] leading-tight" style={{ color: 'rgba(239,68,68,0.72)' }}>
          Stop Risk ({Math.round(stopProb * 100)}%)
        </span>
        <span className="text-[9px] leading-tight text-center" style={{ color: 'var(--text-subtle)' }}>
          Primary Cluster
        </span>
        <span className="text-[9px] leading-tight text-right" style={{ color: 'rgba(16,185,129,0.62)' }}>
          Expansion Tail
        </span>
      </div>
    </div>
  )
}

/* ─── EV Contribution Bars ────────────────────────────────────────────────── */

function EvContribBars({
  scenarios,
  totalEvStr,
}: {
  scenarios: ScenarioRow[]
  totalEvStr: string
}) {
  const maxAbs = Math.max(...scenarios.map((s) => Math.abs(s.evContrib)))

  return (
    <div>
      <p className="text-[9px] uppercase tracking-widest text-text-tertiary mb-2">
        EV Contribution by Scenario
      </p>
      <div className="space-y-[3px]">
        {scenarios.map(({ label, evContrib, positive }) => {
          // Scale bar: 100% of available half-width = maxAbs contribution
          const barPct = (Math.abs(evContrib) / maxAbs) * 100
          const sign = evContrib >= 0 ? '+' : ''
          return (
            <div
              key={label}
              className="grid items-center gap-x-1"
              style={{ gridTemplateColumns: '2rem 1fr 1fr 4.5rem' }}
            >
              {/* Label */}
              <span className="text-[10px] font-mono font-semibold text-text-secondary">
                {label}
              </span>

              {/* Negative zone — bar grows from right edge leftward */}
              <div className="flex justify-end h-[14px] items-center">
                {!positive && (
                  <div
                    style={{
                      width: `${barPct * 0.85}%`,
                      height: '6px',
                      background: 'rgba(239,68,68,0.55)',
                      borderRadius: '2px 0 0 2px',
                    }}
                  />
                )}
              </div>

              {/* Positive zone — bar grows from left edge rightward */}
              <div
                className="flex justify-start h-[14px] items-center"
                style={{ borderLeft: '1px solid rgba(255,255,255,0.10)' }}
              >
                {positive && (
                  <div
                    style={{
                      width: `${barPct * 0.85}%`,
                      height: '6px',
                      background: 'rgba(16,185,129,0.55)',
                      borderRadius: '0 2px 2px 0',
                    }}
                  />
                )}
              </div>

              {/* Value */}
              <span
                className="text-[10px] font-mono tabular-nums text-right"
                style={{ color: positive ? '#10B981' : '#EF4444' }}
              >
                {sign}{evContrib.toFixed(2)}%
              </span>
            </div>
          )
        })}
      </div>

      {/* Total EV */}
      <div
        className="flex items-center justify-between mt-2 pt-2"
        style={{ borderTop: '1px solid var(--border)' }}
      >
        <span className="text-[9px] uppercase tracking-widest text-text-tertiary">
          Total Expected Value
        </span>
        <span
          className="text-xs font-bold font-mono tabular-nums"
          style={{ color: '#10B981' }}
        >
          {totalEvStr}
        </span>
      </div>
    </div>
  )
}

/* ─── EngineCard ──────────────────────────────────────────────────────────── */

function EngineCard() {
  const [activeKey, setActiveKey] = useState<StateKey>('hold')
  const [allocDisplay, setAllocDisplay] = useState(STATES.hold.baseWeight)
  const [metricsVisible, setMetricsVisible] = useState(true)
  const [initDone, setInitDone] = useState(false)

  const allocRef  = useRef(STATES.hold.baseWeight)
  const rafRef    = useRef<number | null>(null)
  const timerRef  = useRef<ReturnType<typeof setTimeout> | null>(null)

  const animateTo = useCallback(
    (to: number, duration: number, onComplete?: () => void) => {
      if (rafRef.current) cancelAnimationFrame(rafRef.current)
      const from = allocRef.current
      const t0 = performance.now()
      const tick = (now: number) => {
        const p = Math.min((now - t0) / duration, 1)
        const ease = 1 - Math.pow(1 - p, 3)
        const val = Math.round((from + (to - from) * ease) * 10) / 10
        allocRef.current = val
        setAllocDisplay(val)
        if (p < 1) {
          rafRef.current = requestAnimationFrame(tick)
        } else {
          allocRef.current = to
          setAllocDisplay(to)
          onComplete?.()
        }
      }
      rafRef.current = requestAnimationFrame(tick)
    },
    [],
  )

  // Initial mount: count from baseWeight → allocation
  useEffect(() => {
    timerRef.current = setTimeout(() => {
      animateTo(STATES.hold.allocation, 850, () => setInitDone(true))
    }, 450)
    return () => {
      if (timerRef.current) clearTimeout(timerRef.current)
      if (rafRef.current) cancelAnimationFrame(rafRef.current)
    }
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  const handleToggle = useCallback(
    (key: StateKey) => {
      if (key === activeKey) return
      setMetricsVisible(false)
      if (timerRef.current) clearTimeout(timerRef.current)
      timerRef.current = setTimeout(() => {
        setActiveKey(key)
        setMetricsVisible(true)
        animateTo(STATES[key].allocation, 250)
      }, 80)
    },
    [activeKey, animateTo],
  )

  const state = STATES[activeKey]

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
            background: state.badgeBg,
            border: `1px solid ${state.badgeBorder}`,
            color: state.badgeColor,
            transition: 'all 200ms ease-out',
          }}
        >
          {state.badge}
        </span>
      </div>

      {/* ── Toggle controls ── */}
      <div
        className="flex gap-2 px-4 py-2.5"
        style={{ borderBottom: '1px solid var(--border)' }}
      >
        {TOGGLE_BUTTONS.map(({ key, label }) => (
          <button
            key={key}
            onClick={() => handleToggle(key)}
            className="flex-1 py-1.5 rounded-full text-[9px] font-semibold uppercase tracking-wider"
            style={{
              transition: 'all 200ms ease-out',
              ...(activeKey === key
                ? {
                    background: 'var(--accent)',
                    color: 'var(--bg-base, #080C18)',
                    border: '1px solid transparent',
                  }
                : {
                    background: 'transparent',
                    color: 'var(--text-secondary)',
                    border: '1px solid var(--border-strong)',
                  }),
            }}
          >
            {label}
          </button>
        ))}
      </div>

      {/* ── Allocation zone ── */}
      <div
        className="px-5 pt-4 pb-4"
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
              {allocDisplay.toFixed(1)}%
            </p>
            <p className="text-xs text-text-secondary mt-2">Satellite Position</p>
          </div>

          {/* Computation ledger — fades on state switch */}
          <div
            className="flex-1 font-mono text-[11px]"
            style={{
              opacity: metricsVisible ? 1 : 0,
              transition: 'opacity 200ms ease-out',
            }}
          >
            <div className="flex items-baseline justify-between gap-2 pb-1">
              <span style={{ color: 'var(--text-subtle)' }}>Base Weight</span>
              <span className="font-medium text-text-secondary tabular-nums">
                {state.baseWeight.toFixed(1)}%
              </span>
            </div>
            <div className="flex items-baseline justify-between gap-2 pb-1.5">
              <span style={{ color: 'var(--text-subtle)' }}>
                <span style={{ color: state.badgeColor }}>×</span> Exec. Multiplier
              </span>
              <span className="font-medium tabular-nums" style={{ color: state.badgeColor }}>
                {state.multiplier.toFixed(2)}×
              </span>
            </div>
            <div className="mb-1.5" style={{ borderTop: '1px solid var(--border-strong)' }} />
            {/* Result row fades in after initial animation */}
            <div
              className="flex items-baseline justify-between gap-2"
              style={{
                opacity: initDone ? 1 : 0,
                transition: 'opacity 700ms',
              }}
            >
              <span className="font-semibold text-text-primary">Final Allocation</span>
              <span className="font-bold tabular-nums" style={{ color: 'var(--accent)' }}>
                {state.allocation.toFixed(1)}%
              </span>
            </div>
            <p
              className="text-[9px] text-right mt-1.5 leading-none"
              style={{ color: 'var(--text-subtle)' }}
            >
              {state.policyCap}
            </p>
          </div>
        </div>
      </div>

      {/* ── EV Contribution Bars ── */}
      <div
        className="px-5 py-3.5"
        style={{
          borderBottom: '1px solid var(--border)',
          opacity: metricsVisible ? 1 : 0,
          transition: 'opacity 200ms ease-out',
        }}
      >
        <EvContribBars scenarios={state.scenarios} totalEvStr={state.totalEvStr} />
      </div>

      {/* ── Probability Distribution Curve ── */}
      <div
        className="px-5 py-3"
        style={{
          borderBottom: '1px solid var(--border)',
          opacity: metricsVisible ? 1 : 0,
          transition: 'opacity 200ms ease-out',
        }}
      >
        <p className="text-[9px] uppercase tracking-widest text-text-tertiary mb-1.5">
          Probability Distribution
        </p>
        <ProbDistCurve stopProb={state.stopProb} />
      </div>

      {/* ── Metrics strip ── */}
      <div
        className="px-5 py-3 grid grid-cols-3"
        style={{
          borderBottom: '1px solid var(--border)',
          opacity: metricsVisible ? 1 : 0,
          transition: 'opacity 200ms ease-out',
        }}
      >
        <div className="text-center">
          <p className="text-xs font-bold font-mono" style={{ color: '#10B981' }}>
            {state.totalEvStr}
          </p>
          <p className="text-[9px] uppercase tracking-wider text-text-tertiary mt-0.5">
            Expected Value
          </p>
        </div>
        <div
          className="text-center"
          style={{
            borderLeft: '1px solid var(--border)',
            borderRight: '1px solid var(--border)',
          }}
        >
          <p className="text-xs font-bold font-mono text-text-primary">
            {state.evPercentile}
          </p>
          <p className="text-[9px] uppercase tracking-wider text-text-tertiary mt-0.5">
            EV Percentile
          </p>
          <p className="text-[9px] text-text-tertiary mt-0.5 leading-none">
            vs calibrated universe
          </p>
        </div>
        <div className="text-center">
          <p className="text-xs font-bold font-mono" style={{ color: '#10B981' }}>
            {state.riskEff.toFixed(2)}
          </p>
          <p className="text-[9px] uppercase tracking-wider text-text-tertiary mt-0.5">
            Risk Efficiency
          </p>
          <p className="text-[9px] text-text-tertiary mt-0.5 leading-none">
            ≥ 0.30 institutional
          </p>
        </div>
      </div>

      {/* ── Risk framing strip ── */}
      <div
        className="px-5 py-3"
        style={{
          opacity: metricsVisible ? 1 : 0,
          transition: 'opacity 200ms ease-out',
        }}
      >
        <div className="flex items-center gap-x-5 gap-y-1 flex-wrap text-xs">
          <div>
            <span className="text-text-tertiary">Stop Prob.: </span>
            <span className="font-mono font-medium text-text-primary">{state.stopProbStr}</span>
            <span className="text-text-tertiary ml-1 text-[9px]">(inst. range 15–35%)</span>
          </div>
          <div>
            <span className="text-text-tertiary">Vol. Regime: </span>
            <span className="font-mono font-medium" style={{ color: state.regimeColor }}>
              {state.regime}
            </span>
          </div>
        </div>
      </div>

      {/* ── Footer ── */}
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

            {/* Micro authority line */}
            <p
              className="text-[10px] font-medium uppercase tracking-widest"
              style={{ color: 'var(--text-subtle)' }}
            >
              Designed for disciplined capital allocators — not narrative traders.
            </p>

            {/* Edge line */}
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
            <div className="pt-4" style={{ borderTop: '1px solid var(--border)' }}>
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
          <div className="w-full">
            <EngineCard />
          </div>

        </div>
      </div>
    </section>
  )
}

export default LandingHero
