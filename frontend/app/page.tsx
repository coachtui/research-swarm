import Link from 'next/link'
import { Button } from '@/components/ui/button'
import { PricingCards } from '@/components/pricing/PricingCards'
import { LandingHero } from '@/components/landing/LandingHero'
import {
  TrendingUp,
  Zap,
  Shield,
  BarChart3,
  CheckCircle2,
  ArrowRight,
  Target,
  ChevronDown,
} from 'lucide-react'

/* ─── Shared section-header pattern ──────────────────────────────────────── */
function SectionLabel({ children }: { children: React.ReactNode }) {
  return (
    <p className="text-xs font-medium tracking-widest uppercase text-text-secondary mb-3">
      {children}
    </p>
  )
}

/* ─── FAQ item ───────────────────────────────────────────────────────────── */
function FaqItem({ q, a }: { q: string; a: string }) {
  return (
    <details
      className="group py-5"
      style={{ borderBottom: '1px solid var(--border)' }}
    >
      <summary className="flex items-center justify-between cursor-pointer list-none text-text-primary font-medium text-sm">
        {q}
        <ChevronDown
          size={16}
          className="text-text-secondary shrink-0 transition-transform duration-200 group-open:rotate-180"
        />
      </summary>
      <p className="mt-3 text-sm text-text-secondary leading-relaxed pr-6">
        {a}
      </p>
    </details>
  )
}

/* ─── Step ───────────────────────────────────────────────────────────────── */
function Step({ n, title, body, sub }: { n: string; title: string; body: string; sub?: React.ReactNode }) {
  return (
    <div className="flex gap-6 items-start py-8" style={{ borderBottom: '1px solid var(--border)' }}>
      <div
        className="w-9 h-9 rounded-full flex items-center justify-center text-sm font-bold text-primary shrink-0"
        style={{ border: '1px solid var(--accent-border)', background: 'var(--accent-weak)' }}
      >
        {n}
      </div>
      <div className="flex-1 min-w-0">
        <h3 className="text-base font-semibold text-text-primary mb-1">{title}</h3>
        <p className="text-sm text-text-secondary leading-relaxed">{body}</p>
        {sub}
      </div>
    </div>
  )
}

export default function Home() {
  return (
    <main className="min-h-screen bg-background">

      {/* ── Hero ─────────────────────────────────────────────────────────── */}
      <LandingHero />

      {/* ── Proof-of-edge strip ──────────────────────────────────────────── */}
      <div
        className="py-3"
        style={{
          background: 'var(--surface-1)',
          borderTop: '1px solid var(--border)',
          borderBottom: '1px solid var(--border)',
        }}
      >
        <div className="mx-auto max-w-6xl px-4 sm:px-6">
          <div className="flex items-center justify-center gap-6 sm:gap-10 flex-wrap">
            {[
              { label: 'EV Percentile',     value: '62nd' },
              { label: 'Risk Efficiency',   value: '76th percentile' },
              { label: 'Stop Risk Rank',    value: '75th percentile' },
            ].map(({ label, value }, i) => (
              <div key={label} className="flex items-center gap-2 text-xs">
                {i > 0 && (
                  <span className="text-text-tertiary hidden sm:block select-none">·</span>
                )}
                <span
                  className="uppercase tracking-wider"
                  style={{ fontSize: '9px', color: 'var(--text-subtle)' }}
                >
                  {label}:
                </span>
                <span className="font-mono font-semibold text-text-primary">{value}</span>
              </div>
            ))}
          </div>
          <p
            className="text-center mt-1.5 uppercase tracking-wider"
            style={{ fontSize: '9px', color: 'var(--text-subtle)' }}
          >
            Illustrative — relative to calibrated universe
          </p>
        </div>
      </div>

      {/* ── Bold tagline ─────────────────────────────────────────────────── */}
      <div
        className="py-8 text-center"
        style={{ borderTop: '1px solid var(--border)' }}
      >
        <p className="text-xl md:text-2xl font-bold text-text-primary tracking-tight leading-tight">
          Stop researching in isolation.
          <br />
          <span className="text-primary">Start building structured edge.</span>
        </p>
      </div>

      {/* ── The Problem ──────────────────────────────────────────────────── */}
      <section className="py-20" style={{ borderTop: '1px solid var(--border)', background: 'var(--surface-1)' }}>
        <div className="container mx-auto px-4">
          <div className="max-w-5xl mx-auto">
            <div className="mb-10">
              <SectionLabel>The Problem</SectionLabel>
              <h2 className="text-2xl md:text-4xl font-bold text-text-primary tracking-tight">
                Why Most Retail Research Breaks Down
              </h2>
              <p className="mt-4 text-sm text-text-secondary leading-relaxed max-w-2xl">
                The issue is not effort. Most retail investors research extensively.
                The issue is structure — or the absence of it.
              </p>
            </div>

            <div className="grid md:grid-cols-2 gap-6 mb-12">
              {[
                {
                  title: 'Fragmented Across Sources',
                  body: 'Research lives across dozens of tabs — earnings calls, screeners, newsletters, analyst reports. No unified output. No synthesis.',
                },
                {
                  title: 'Narrative Bias Distorts Conviction',
                  body: 'When research is story-driven, conviction follows narrative. It inflates on positive headlines and collapses on noise.',
                },
                {
                  title: 'Position Sizing is Emotional',
                  body: 'Without a probabilistic framework, allocation decisions default to instinct. Equal-weight or arbitrary sizing replaces disciplined deployment.',
                },
                {
                  title: 'Static Allocations Ignore Uncertainty',
                  body: 'Market regimes shift. Volatility changes. Most approaches treat allocation as fixed — ignoring the probability structure underlying each setup.',
                },
              ].map(({ title, body }) => (
                <div
                  key={title}
                  className="rounded-card p-5"
                  style={{ background: 'var(--surface-2)', border: '1px solid var(--border)' }}
                >
                  <div className="flex items-start gap-3">
                    <span
                      className="text-sm font-bold shrink-0 mt-0.5"
                      style={{ color: 'rgba(239,68,68,0.55)' }}
                    >
                      —
                    </span>
                    <div>
                      <h4 className="text-sm font-semibold text-text-primary mb-1.5">{title}</h4>
                      <p className="text-sm text-text-secondary leading-relaxed">{body}</p>
                    </div>
                  </div>
                </div>
              ))}
            </div>

            {/* ── Before / After contrast ── */}
            <div
              className="grid md:grid-cols-2 rounded-card overflow-hidden"
              style={{ border: '1px solid var(--border)' }}
            >
              {/* Left — Before */}
              <div
                className="p-8"
                style={{
                  background: 'rgba(239,68,68,0.04)',
                  borderRight: '1px solid var(--border)',
                }}
              >
                <p
                  className="text-xs font-semibold uppercase tracking-widest mb-6"
                  style={{ color: 'rgba(239,68,68,0.70)' }}
                >
                  Before DVRG
                </p>
                <div className="space-y-3">
                  {[
                    'Multiple tabs open, no synthesis',
                    'Conflicting signals, no resolution',
                    'Narrative-driven conviction',
                    'Static allocation size',
                  ].map((item) => (
                    <div key={item} className="flex items-center gap-3">
                      <span
                        className="text-xs font-bold shrink-0"
                        style={{ color: 'rgba(239,68,68,0.55)' }}
                      >
                        —
                      </span>
                      <span className="text-sm text-text-secondary">{item}</span>
                    </div>
                  ))}
                </div>
              </div>

              {/* Right — After */}
              <div
                className="p-8"
                style={{
                  background: 'rgba(16,185,129,0.04)',
                  borderLeft: '1px solid rgba(16,185,129,0.15)',
                }}
              >
                <p
                  className="text-xs font-semibold uppercase tracking-widest mb-6"
                  style={{ color: '#10B981' }}
                >
                  After DVRG
                </p>
                <div className="space-y-3">
                  {[
                    'Unified thesis from consolidated signals',
                    'Quantified expected value',
                    'Confidence calibration, not narrative',
                    'Probability-weighted position size',
                  ].map((item) => (
                    <div key={item} className="flex items-center gap-3">
                      <CheckCircle2 className="w-3.5 h-3.5 text-success shrink-0" />
                      <span className="text-sm text-text-secondary">{item}</span>
                    </div>
                  ))}
                </div>
              </div>
            </div>

          </div>
        </div>
      </section>

      {/* ── The Shift ────────────────────────────────────────────────────── */}
      <section className="py-20" style={{ borderTop: '1px solid var(--border)' }}>
        <div className="container mx-auto px-4">
          <div className="max-w-5xl mx-auto">
            <div className="mb-10">
              <SectionLabel>The Shift</SectionLabel>
              <h2 className="text-2xl md:text-4xl font-bold text-text-primary tracking-tight">
                The Edge Comes From Structure
              </h2>
              <p className="mt-4 text-sm text-text-secondary leading-relaxed max-w-2xl">
                DVRG does not give you better predictions. It gives you a better process.
                Structure is the edge.
              </p>
            </div>

            <div className="grid lg:grid-cols-2 gap-10">
              <div style={{ borderTop: '1px solid var(--border)' }}>
                {[
                  {
                    label: 'DVRG does not predict.',
                    detail: 'It structures uncertainty into a probability-weighted model across defined scenarios.',
                  },
                  {
                    label: 'DVRG quantifies expected value.',
                    detail: 'Not directional opinion — a calibrated EV computed across probability-weighted outcomes.',
                  },
                  {
                    label: 'DVRG calibrates confidence.',
                    detail: 'Conviction is measured against regime state and signal stability — not narrative momentum.',
                  },
                  {
                    label: 'DVRG converts conviction into exposure.',
                    detail: 'Allocation size is derived from EV and regime multiplier, not instinct.',
                  },
                  {
                    label: 'Capital discipline becomes systematic.',
                    detail: 'The same framework governs every analysis. No exceptions for high-conviction narratives.',
                  },
                ].map(({ label, detail }) => (
                  <div
                    key={label}
                    className="py-4"
                    style={{ borderBottom: '1px solid var(--border)' }}
                  >
                    <p className="text-sm font-semibold text-text-primary mb-0.5">{label}</p>
                    <p className="text-sm text-text-secondary leading-relaxed">{detail}</p>
                  </div>
                ))}
              </div>

              <div
                className="rounded-card p-6"
                style={{ background: 'var(--surface-1)', border: '1px solid var(--border)' }}
              >
                <h4 className="text-[10px] font-semibold uppercase tracking-widest text-text-tertiary mb-5">
                  What Structure Replaces
                </h4>
                <div className="space-y-3">
                  {[
                    ['Expected Value', 'replaces guesswork'],
                    ['Probability Modeling', 'replaces narrative'],
                    ['Conviction Sizing', 'replaces gut positioning'],
                    ['Regime Awareness', 'replaces static allocation'],
                    ['Unified Thesis', 'replaces fragmented research'],
                  ].map(([title, sub]) => (
                    <div key={title} className="flex items-center gap-3">
                      <CheckCircle2 className="w-3.5 h-3.5 text-success shrink-0" />
                      <span className="text-sm text-text-secondary">
                        <strong className="text-text-primary">{title}</strong>
                        <span className="text-text-tertiary"> — {sub}</span>
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* ── How It Works ─────────────────────────────────────────────────── */}
      <section id="how-it-works" className="py-20" style={{ borderTop: '1px solid var(--border)', background: 'var(--surface-1)' }}>
        <div className="container mx-auto px-4">
          <div className="max-w-3xl mx-auto">
            <div className="mb-12">
              <SectionLabel>Process</SectionLabel>
              <h2 className="text-2xl md:text-4xl font-bold text-text-primary tracking-tight">
                How DVRG Thinks
              </h2>
            </div>

            <div style={{ borderTop: '1px solid var(--border)' }}>
              <Step
                n="1"
                title="Detect Structural Divergence"
                body="Identify regime, liquidity, and volatility state."
              />
              <Step
                n="2"
                title="Weight Scenarios by Probability"
                body="Model stop, targets, and expansion paths."
              />
              <Step
                n="3"
                title="Quantify Expected Value"
                body="Compute probability-weighted return."
              />
              <Step
                n="4"
                title="Enforce Risk Stability"
                body="Apply multiplier and policy cap."
              />
              <Step
                n="5"
                title="Convert Probability into Size"
                body="Translate edge into allocation."
              />
            </div>

            {/* Risk-Off example card */}
            <div
              className="mt-8 rounded-card p-5"
              style={{ background: 'var(--surface-2)', border: '1px solid var(--border)' }}
            >
              <div className="flex items-start justify-between gap-4">
                <div className="min-w-0">
                  <p className="text-[9px] uppercase tracking-widest text-text-tertiary mb-1">
                    Risk-Off Example
                  </p>
                  <p className="text-sm font-semibold text-text-primary">
                    Allocation Compressed to 0.8%
                  </p>
                  <p className="text-xs text-text-secondary mt-1 leading-relaxed">
                    Elevated noise regime + low EV → execution multiplier near-zero.
                    The engine disciplines out the trade before capital is committed.
                  </p>
                </div>
                <div className="text-right shrink-0">
                  <p
                    className="text-2xl font-bold tracking-tight tabular-nums"
                    style={{ color: '#F59E0B' }}
                  >
                    0.8%
                  </p>
                  <p className="text-[9px] uppercase tracking-wider text-text-tertiary mt-0.5">
                    Final Allocation
                  </p>
                </div>
              </div>
              <div
                className="mt-3 pt-3 flex items-center gap-5 flex-wrap text-xs"
                style={{ borderTop: '1px solid var(--border)' }}
              >
                <span className="text-text-tertiary">
                  Base Weight:{' '}
                  <span className="font-mono text-text-secondary">4.5%</span>
                </span>
                <span className="text-text-tertiary">
                  Exec. Multiplier:{' '}
                  <span className="font-mono" style={{ color: '#F59E0B' }}>0.18×</span>
                </span>
                <span className="text-text-tertiary">
                  EV:{' '}
                  <span className="font-mono" style={{ color: '#EF4444' }}>+0.6%</span>
                </span>
              </div>
            </div>

            <div className="mt-10 text-center">
              <Link href="/welcome/free">
                <Button size="lg">
                  Try Free — 2 Full Reports <ArrowRight className="ml-2 w-4 h-4" />
                </Button>
              </Link>
            </div>
          </div>
        </div>
      </section>

      {/* ── Allocation Engine ─────────────────────────────────────────────── */}
      <section className="py-20" style={{ borderTop: '1px solid var(--border)' }}>
        <div className="container mx-auto px-4">
          <div className="max-w-5xl mx-auto">
            <div className="mb-10">
              <SectionLabel>The Engine</SectionLabel>
              <h2 className="text-2xl md:text-4xl font-bold text-text-primary tracking-tight">
                Capital Allocation, Made Systematic
              </h2>
              <p className="mt-4 text-sm text-text-secondary leading-relaxed max-w-2xl">
                Every analysis produces a binding allocation output. Not a recommendation — a structured capital decision derived from signal, probability, and regime state.
              </p>
            </div>

            <div className="grid lg:grid-cols-2 gap-10">
              {/* System component list */}
              <div style={{ borderTop: '1px solid var(--border)' }}>
                {[
                  { icon: <BarChart3 className="w-4 h-4" />, label: 'Expected value compression' },
                  { icon: <TrendingUp className="w-4 h-4" />, label: 'Regime-aware multipliers' },
                  { icon: <Target className="w-4 h-4" />, label: 'Stop probability modeling' },
                  { icon: <Shield className="w-4 h-4" />, label: 'Policy cap enforcement' },
                  { icon: <Zap className="w-4 h-4" />, label: 'Capital deployment translation' },
                ].map(({ icon, label }) => (
                  <div
                    key={label}
                    className="flex items-center gap-4 py-3.5"
                    style={{ borderBottom: '1px solid var(--border)' }}
                  >
                    <div
                      className="w-7 h-7 rounded flex items-center justify-center shrink-0 text-primary"
                      style={{ background: 'var(--accent-weak)', border: '1px solid var(--accent-border)' }}
                    >
                      {icon}
                    </div>
                    <span className="text-sm font-medium text-text-primary">{label}</span>
                  </div>
                ))}
              </div>

              {/* Key differentiators panel */}
              <div
                className="rounded-card p-6"
                style={{ background: 'var(--surface-1)', border: '1px solid var(--border)' }}
              >
                <h4 className="text-[10px] font-semibold uppercase tracking-widest text-text-tertiary mb-5">
                  Output vs Alternatives
                </h4>
                <div className="space-y-3">
                  {[
                    ['Expected Value', 'not guesswork'],
                    ['Probability', 'not narrative'],
                    ['Conviction Sizing', 'not gut positioning'],
                    ['Capital Translation', 'not data overload'],
                  ].map(([title, sub]) => (
                    <div key={title} className="flex items-center gap-3">
                      <CheckCircle2 className="w-3.5 h-3.5 text-success shrink-0" />
                      <span className="text-sm text-text-secondary">
                        <strong className="text-text-primary">{title}</strong>
                        <span className="text-text-tertiary"> — {sub}</span>
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* ── Pricing ──────────────────────────────────────────────────────── */}
      <section id="pricing" className="py-20" style={{ borderTop: '1px solid var(--border)', background: 'var(--surface-1)' }}>
        <div className="container mx-auto px-4">
          <div className="max-w-5xl mx-auto">
            <div className="mb-12">
              <SectionLabel>Pricing</SectionLabel>
              <h2 className="text-2xl md:text-4xl font-bold text-text-primary tracking-tight">
                Select Your Depth of Analysis
              </h2>
              <p className="mt-4 text-sm text-text-secondary leading-relaxed max-w-xl">
                Each tier unlocks a deeper layer of the allocation framework. Start with the structured core. Add diagnostics and advanced controls as your process matures.
              </p>
            </div>
            <PricingCards />
            <p className="mt-8 text-center text-sm text-text-secondary">
              Designed for systematic capital allocation workflows.
            </p>
          </div>
        </div>
      </section>

      {/* ── Who DVRG Is For ───────────────────────────────────────────────── */}
      <section className="py-20" style={{ borderTop: '1px solid var(--border)' }}>
        <div className="container mx-auto px-4">
          <div className="max-w-5xl mx-auto">
            <div className="mb-10">
              <SectionLabel>Audience</SectionLabel>
              <h2 className="text-2xl md:text-4xl font-bold text-text-primary tracking-tight">
                Who DVRG Is For
              </h2>
            </div>

            <div className="grid md:grid-cols-2 gap-10">
              {/* Built For */}
              <div>
                <p className="text-xs font-semibold uppercase tracking-widest text-success mb-5">Built For</p>
                <div style={{ borderTop: '1px solid var(--border)' }}>
                  {[
                    'Investors who want structure, not more data',
                    'Capital allocators who want a repeatable process',
                    'Active investors managing position size discipline',
                  ].map((item) => (
                    <div
                      key={item}
                      className="flex items-center gap-3 py-3.5"
                      style={{ borderBottom: '1px solid var(--border)' }}
                    >
                      <CheckCircle2 className="w-3.5 h-3.5 text-success shrink-0" />
                      <span className="text-sm font-medium text-text-primary">{item}</span>
                    </div>
                  ))}
                </div>
              </div>

              {/* Not For */}
              <div>
                <p className="text-xs font-semibold uppercase tracking-widest text-text-tertiary mb-5">Not Built For</p>
                <div style={{ borderTop: '1px solid var(--border)' }}>
                  {[
                    'Headline-driven traders',
                    'Passive ETF allocators',
                    'Narrative-only investors',
                  ].map((item) => (
                    <div
                      key={item}
                      className="flex items-center gap-3 py-3.5"
                      style={{ borderBottom: '1px solid var(--border)' }}
                    >
                      <span className="text-text-tertiary font-bold text-sm shrink-0 w-3.5 text-center">—</span>
                      <span className="text-sm font-medium text-text-secondary">{item}</span>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* ── What DVRG Is Not ─────────────────────────────────────────────── */}
      <section className="py-20" style={{ borderTop: '1px solid var(--border)', background: 'var(--surface-1)' }}>
        <div className="container mx-auto px-4">
          <div className="max-w-3xl mx-auto">
            <div className="mb-10">
              <SectionLabel>Clarity</SectionLabel>
              <h2 className="text-2xl md:text-4xl font-bold text-text-primary tracking-tight">
                What DVRG Is Not
              </h2>
              <p className="mt-4 text-sm text-text-secondary leading-relaxed">
                Precision about what a tool is not builds more trust than what it claims to be.
              </p>
            </div>
            <div style={{ borderTop: '1px solid var(--border)' }}>
              {[
                {
                  title: 'Not a day-trading signal service',
                  detail: 'DVRG is a structured capital allocation framework. It is not a real-time alert feed or a buy/sell trigger.',
                },
                {
                  title: 'Not a hype-driven recommendation engine',
                  detail: 'There are no hot stock picks, trending tickers, or urgency-based calls. Analysis is regime-aware and fundamentally grounded.',
                },
                {
                  title: 'Not a guarantee engine',
                  detail: 'No system predicts markets. DVRG structures probability. Outcomes remain uncertain — the process is what improves.',
                },
                {
                  title: 'Not a replacement for your judgment',
                  detail: 'DVRG provides a structured decision framework. You retain full discretion. It informs. You decide.',
                },
              ].map(({ title, detail }) => (
                <div
                  key={title}
                  className="flex items-start gap-4 py-5"
                  style={{ borderBottom: '1px solid var(--border)' }}
                >
                  <div
                    className="w-7 h-7 rounded flex items-center justify-center shrink-0 mt-0.5"
                    style={{
                      background: 'rgba(239,68,68,0.08)',
                      border: '1px solid rgba(239,68,68,0.20)',
                    }}
                  >
                    <span className="text-sm font-bold" style={{ color: 'rgba(239,68,68,0.55)' }}>—</span>
                  </div>
                  <div>
                    <h4 className="text-sm font-semibold text-text-primary mb-1">{title}</h4>
                    <p className="text-sm text-text-secondary leading-relaxed">{detail}</p>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </section>

      {/* ── FAQ ──────────────────────────────────────────────────────────── */}
      <section id="faq" className="py-20" style={{ borderTop: '1px solid var(--border)' }}>
        <div className="container mx-auto px-4">
          <div className="max-w-2xl mx-auto">
            <div className="mb-10">
              <SectionLabel>FAQ</SectionLabel>
              <h2 className="text-2xl md:text-4xl font-bold text-text-primary tracking-tight">
                Frequently Asked Questions
              </h2>
            </div>
            <div style={{ borderTop: '1px solid var(--border)' }}>
              <FaqItem
                q="What makes DVRG different from research tools?"
                a="Most research tools optimize for narratives. DVRG optimizes for decisions. It quantifies expected value, scenario probability, and setup stability — then translates that into a structured allocation framework. The output is not a report. It is a capital deployment decision."
              />
              <FaqItem
                q="Is this investment advice?"
                a="No. DVRG provides structured decision infrastructure, not personalized investment advice. Always do your own due diligence and consult a licensed financial advisor before making investment decisions."
              />
              <FaqItem
                q="Can I get a refund if I'm not satisfied?"
                a="Yes. We offer a 100% satisfaction guarantee. If you're not satisfied with your first analysis, contact us within 7 days for a full refund, no questions asked."
              />
              <FaqItem
                q="What stocks can I analyze?"
                a="Currently, we support all US-listed stocks (NYSE, NASDAQ). We're working on adding international markets and ETFs."
              />
              <FaqItem
                q="How is this different from free stock screeners?"
                a="Stock screeners show raw data. DVRG translates signal into conviction and conviction into position size. It replaces fragmented research workflows — spreadsheets, screeners, newsletters, analyst reports — with a single structured capital allocation system."
              />
              <FaqItem
                q="Do analyses get updated over time?"
                a="Each analysis is a snapshot in time. You can re-run analysis on the same stock to get an updated decision. All paid plan users receive watchlist alerts when significant changes are detected."
              />
            </div>
          </div>
        </div>
      </section>

      {/* ── Final CTA ────────────────────────────────────────────────────── */}
      <section className="py-20" style={{ borderTop: '1px solid var(--border)', background: 'var(--surface-1)' }}>
        <div className="container mx-auto px-4">
          <div className="max-w-2xl mx-auto text-center space-y-6">
            <h2 className="text-2xl md:text-4xl font-bold text-text-primary tracking-tight">
              Build Conviction. Deploy with Discipline.
            </h2>
            <p className="text-text-secondary">
              Replace fragmented research workflows with a single structured capital allocation system.
            </p>
            <Link href="/welcome/free">
              <Button size="lg" variant="outline">
                Try Free — 2 Full Reports
              </Button>
            </Link>
            <p
              className="text-[10px] uppercase tracking-widest"
              style={{ color: 'var(--text-subtle)' }}
            >
              Quantitative capital allocation framework.
            </p>
          </div>
        </div>
      </section>

    </main>
  )
}
