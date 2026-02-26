import Link from 'next/link'
import { Button } from '@/components/ui/button'
import { ArrowRight, CheckCircle2, Zap } from 'lucide-react'

/* ─── Static engine preview data ─────────────────────────────────────────── */

const MULTIPLIERS = [
  { label: 'Noise Regime',      value: '0.70×' },
  { label: 'Model Sensitivity', value: '0.90×' },
  { label: 'Signal Dispersion', value: '0.75×' },
  { label: 'Stop Risk',         value: '0.80×' },
] as const

const SCENARIOS = [
  { label: 'Stop', prob: 43, ret: '−8.0%',  ev: '−3.44%', positive: false as const },
  { label: 'T1',   prob: 43, ret: '+10.0%', ev: '+4.25%', positive: true  as const },
  { label: 'T2',   prob:  9, ret: '+28.9%', ev: '+2.58%', positive: true  as const },
  { label: 'T3',   prob:  6, ret: '+21.3%', ev: '+1.18%', positive: true  as const },
]

const KPIS = [
  { label: 'Expected Value',   value: '+4.57%', color: '#10B981' },
  { label: 'Stop Probability', value: '19%',    color: null      },
  { label: 'Risk Efficiency',  value: '0.38',   color: null      },
]

const TRUST_ITEMS = [
  'Scenario-weighted EV — not single-point forecasts',
  'Conviction-to-position sizing framework',
  'Structural noise & stability diagnostics',
  'Binding allocation output per analysis',
]

/* ─── EnginePreviewCard ───────────────────────────────────────────────────── */

function EnginePreviewCard() {
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
      {/* Header row */}
      <div
        className="flex items-center justify-between px-5 py-3.5"
        style={{ borderBottom: '1px solid var(--border)' }}
      >
        <div className="flex items-center gap-2 min-w-0">
          <span
            className="w-1.5 h-1.5 rounded-full shrink-0"
            style={{ background: 'var(--accent)' }}
          />
          <span className="text-[10px] font-semibold uppercase tracking-widest text-text-secondary truncate">
            Noise-Adjusted Exposure Engine
          </span>
        </div>
        <span
          className="ml-3 shrink-0 text-[9px] font-bold uppercase tracking-wider px-2 py-0.5 rounded"
          style={{
            background: 'rgba(0,217,181,0.1)',
            border: '1px solid rgba(0,217,181,0.28)',
            color: 'var(--accent)',
          }}
        >
          Execution-Bound
        </span>
      </div>

      {/* Allocation band */}
      <div
        className="px-5 py-4 flex items-end justify-between gap-6"
        style={{ borderBottom: '1px solid var(--border)' }}
      >
        <div className="flex items-center gap-5">
          <div>
            <p className="text-[9px] uppercase tracking-widest text-text-tertiary mb-1">
              Base Weight
            </p>
            <p className="text-sm font-semibold text-text-primary font-mono">5.0%</p>
          </div>
          <span className="text-text-tertiary text-xl font-light leading-none">×</span>
          <div>
            <p className="text-[9px] uppercase tracking-widest text-text-tertiary mb-1">
              Signal Compression
            </p>
            <p className="text-sm font-semibold text-text-primary font-mono">0.378×</p>
          </div>
        </div>
        <div className="text-right shrink-0">
          <p className="text-[9px] uppercase tracking-widest text-text-tertiary mb-1">
            Final Allocation
          </p>
          <p
            className="text-4xl font-bold tracking-tighter leading-none"
            style={{ color: 'var(--accent)' }}
          >
            1.89%
          </p>
        </div>
      </div>

      {/* Compression multipliers */}
      <div
        className="px-5 py-3.5"
        style={{ borderBottom: '1px solid var(--border)' }}
      >
        <p className="text-[9px] uppercase tracking-widest text-text-tertiary mb-2.5">
          Compression Multipliers
        </p>
        <div className="grid grid-cols-2 gap-x-6 gap-y-1.5">
          {MULTIPLIERS.map(({ label, value }) => (
            <div key={label} className="flex items-center justify-between gap-2">
              <span className="text-xs text-text-secondary">{label}</span>
              <span
                className="text-xs font-mono font-semibold shrink-0"
                style={{ color: '#F59E0B' }}
              >
                {value}
              </span>
            </div>
          ))}
        </div>
      </div>

      {/* Outcome distribution */}
      <div
        className="px-5 py-3.5"
        style={{ borderBottom: '1px solid var(--border)' }}
      >
        <p className="text-[9px] uppercase tracking-widest text-text-tertiary mb-2.5">
          Outcome Distribution
        </p>

        {/* Column headers */}
        <div className="grid grid-cols-[2.5rem_1fr_3.5rem_3.5rem] gap-x-2 mb-1">
          {['Scenario', 'Probability', 'Return', 'EV Contrib.'].map((h) => (
            <p key={h} className="text-[9px] uppercase tracking-wider text-text-tertiary">
              {h}
            </p>
          ))}
        </div>

        {/* Data rows */}
        {SCENARIOS.map(({ label, prob, ret, ev, positive }) => (
          <div
            key={label}
            className="grid grid-cols-[2.5rem_1fr_3.5rem_3.5rem] gap-x-2 items-center py-1.5"
            style={{ borderTop: '1px solid var(--border)' }}
          >
            <span className="text-xs font-mono font-semibold text-text-primary">{label}</span>

            {/* Probability bar + label */}
            <div className="flex items-center gap-1.5">
              <div
                className="flex-1 h-[3px] rounded-full overflow-hidden"
                style={{ background: 'rgba(255,255,255,0.07)' }}
              >
                <div
                  className="h-[3px] rounded-full"
                  style={{
                    width: `${prob}%`,
                    background: positive
                      ? 'rgba(16,185,129,0.55)'
                      : 'rgba(239,68,68,0.50)',
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
            <span
              className="text-[11px] font-mono text-right tabular-nums"
              style={{ color: positive ? '#10B981' : '#EF4444' }}
            >
              {ev}
            </span>
          </div>
        ))}
      </div>

      {/* KPI strip */}
      <div className="grid grid-cols-3">
        {KPIS.map(({ label, value, color }, i) => (
          <div
            key={label}
            className="px-4 py-3.5 text-center"
            style={i > 0 ? { borderLeft: '1px solid var(--border)' } : undefined}
          >
            <p
              className="text-sm font-bold tracking-tight font-mono"
              style={{ color: color ?? 'var(--text-primary)' }}
            >
              {value}
            </p>
            <p className="text-[9px] uppercase tracking-wider text-text-tertiary mt-0.5 leading-tight">
              {label}
            </p>
          </div>
        ))}
      </div>

      {/* Sample label */}
      <div
        className="px-5 py-2 text-center"
        style={{ borderTop: '1px solid var(--border)' }}
      >
        <p className="text-[9px] uppercase tracking-wider text-text-tertiary">
          Example output — illustrative values only
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

        {/* Two-column grid: 44% copy / 56% preview on desktop, stacked on mobile */}
        <div className="grid lg:grid-cols-[44%_56%] gap-10 lg:gap-16 items-start">

          {/* ── LEFT: Copy column ───────────────────────────────────────────── */}
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

            {/* Subhead */}
            <p className="text-base text-text-secondary leading-relaxed max-w-[30rem]">
              DVRG converts conviction into scenario-weighted position sizing — modeling expected
              value across stop, target, and re-rating paths, then compressing through structural
              noise diagnostics to output an execution-bound allocation percentage.
            </p>

            {/* Microproof */}
            <p className="text-sm font-medium" style={{ color: 'var(--text-muted)' }}>
              Five AI agents.{' '}
              <span className="text-text-primary">One binding capital decision.</span>{' '}
              <span style={{ color: 'var(--text-subtle)' }}>No gut-sized positions.</span>
            </p>

            {/* CTAs */}
            <div className="flex flex-col sm:flex-row gap-3 pt-1">
              <Link href="/welcome/free">
                <Button size="lg" className="w-full sm:w-auto">
                  Run 2 Free Reports <ArrowRight className="ml-1.5 w-4 h-4" />
                </Button>
              </Link>
              <Link href="/preview/nvda">
                <Button size="lg" variant="outline" className="w-full sm:w-auto">
                  View Sample Output
                </Button>
              </Link>
            </div>

            {/* Trust row */}
            <div
              className="pt-5"
              style={{ borderTop: '1px solid var(--border)' }}
            >
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-y-2.5 gap-x-4">
                {TRUST_ITEMS.map((item) => (
                  <div key={item} className="flex items-start gap-2 text-xs text-text-secondary">
                    <CheckCircle2 className="w-3.5 h-3.5 text-success shrink-0 mt-0.5" />
                    <span>{item}</span>
                  </div>
                ))}
              </div>
            </div>

            {/* Micro-disclaimer */}
            <p className="text-[11px] leading-relaxed max-w-sm" style={{ color: 'var(--text-subtle)' }}>
              For informational purposes only. Not investment advice. All outputs are
              model-derived. Consult a licensed financial professional before making
              any investment decision.
            </p>
          </div>

          {/* ── RIGHT: Engine Preview ────────────────────────────────────────── */}
          <div className="w-full">
            <EnginePreviewCard />
          </div>

        </div>
      </div>
    </section>
  )
}

export default LandingHero
