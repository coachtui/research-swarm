import Link from 'next/link'
import { Button } from '@/components/ui/button'
import { PricingCards } from '@/components/pricing/PricingCards'
import {
  TrendingUp,
  Zap,
  Shield,
  BarChart3,
  CheckCircle2,
  ArrowRight,
  Target,
  AlertTriangle,
  LineChart,
  Newspaper,
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

/* ─── Agent row ──────────────────────────────────────────────────────────── */
function AgentRow({
  icon,
  title,
  body,
}: {
  icon: React.ReactNode
  title: string
  body: string
}) {
  return (
    <div className="flex items-start gap-4 py-4" style={{ borderBottom: '1px solid var(--border)' }}>
      <div
        className="w-9 h-9 rounded-md flex items-center justify-center shrink-0 text-primary"
        style={{ background: 'var(--accent-weak)', border: '1px solid var(--accent-border)' }}
      >
        {icon}
      </div>
      <div>
        <h4 className="text-sm font-semibold text-text-primary mb-0.5">{title}</h4>
        <p className="text-sm text-text-secondary leading-relaxed">{body}</p>
      </div>
    </div>
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
      <section className="py-24 md:py-32">
        <div className="container mx-auto px-4">
          <div className="max-w-3xl mx-auto text-center space-y-7">

            {/* Label chip */}
            <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full text-xs font-medium text-primary"
              style={{ background: 'var(--accent-weak)', border: '1px solid var(--accent-border)' }}>
              <Zap className="w-3.5 h-3.5" />
              Capital Allocation · Decision Engine
            </div>

            <h1 className="text-4xl md:text-6xl font-bold text-text-primary leading-tight tracking-tight">
              Structured Capital Allocation<br />
              for{' '}
              <span className="text-primary">Serious Investors</span>
            </h1>

            <p className="text-lg text-text-secondary leading-relaxed max-w-2xl mx-auto">
              DVRG models expected value, scenario probability, and stability to determine
              how much capital to deploy — and when.
            </p>

            <div className="flex flex-col sm:flex-row gap-3 justify-center pt-2">
              <Link href="#how-it-works">
                <Button size="lg" className="w-full sm:w-auto">
                  See How Allocation Is Structured <ArrowRight className="ml-2 w-4 h-4" />
                </Button>
              </Link>
              <Link href="/preview/nvda">
                <Button size="lg" variant="outline" className="w-full sm:w-auto">
                  View Sample Decision
                </Button>
              </Link>
            </div>

            {/* Trust strip */}
            <div className="flex flex-wrap items-center justify-center gap-6 text-xs text-text-secondary pt-4">
              {[
                'Expected Value',
                'Stop Probability',
                'Stability & Noise',
                'Scenario Distribution',
                'Position Sizing',
              ].map((item) => (
                <div key={item} className="flex items-center gap-1.5">
                  <CheckCircle2 className="w-3.5 h-3.5 text-success shrink-0" />
                  {item}
                </div>
              ))}
            </div>
          </div>
        </div>
      </section>

      {/* ── Pain Points ──────────────────────────────────────────────────── */}
      <section className="py-20" style={{ borderTop: '1px solid var(--border)', background: 'var(--surface-1)' }}>
        <div className="container mx-auto px-4">
          <div className="max-w-5xl mx-auto">
            <div className="mb-12">
              <SectionLabel>The Problem</SectionLabel>
              <h2 className="text-2xl md:text-4xl font-bold text-text-primary tracking-tight">
                Most Research Tools Optimize Narratives — Not Decisions
              </h2>
            </div>

            <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-px"
              style={{ background: 'var(--border)' }}>
              {[
                { icon: <Target className="w-5 h-5" />, title: 'Price Targets without Probability',
                  body: 'Single-point forecasts carry no probability weighting. Sizing off them is structurally unsound.' },
                { icon: <BarChart3 className="w-5 h-5" />, title: 'Signals without Capital Translation',
                  body: 'Indicators tell you direction. They say nothing about how much capital to deploy.' },
                { icon: <AlertTriangle className="w-5 h-5" />, title: 'Narratives without Position Logic',
                  body: 'Strong conviction is not the same as a large position. Markets punish sizing errors, not bad opinions.' },
                { icon: <LineChart className="w-5 h-5" />, title: 'Missing Risk Geometry',
                  body: 'No modeling of stop probability, distribution shape, or expected value efficiency.' },
                { icon: <Newspaper className="w-5 h-5" />, title: 'Information Overload',
                  body: 'More data, less clarity. No structured path from signal to allocation decision.' },
                { icon: <Shield className="w-5 h-5" />, title: 'The Gap',
                  body: 'Most tools stop at opinion. DVRG ends at allocation.' },
              ].map(({ icon, title, body }) => (
                <div key={title} className="p-6 bg-background flex gap-4 items-start">
                  <div className="w-8 h-8 rounded-md flex items-center justify-center shrink-0 text-error"
                    style={{ background: 'rgba(239,68,68,0.07)', border: '1px solid rgba(239,68,68,0.15)' }}>
                    {icon}
                  </div>
                  <div>
                    <h3 className="text-sm font-semibold text-text-primary mb-1">{title}</h3>
                    <p className="text-sm text-text-secondary leading-relaxed">{body}</p>
                  </div>
                </div>
              ))}
            </div>

            <p className="mt-8 text-center text-sm font-semibold text-text-primary">
              Most tools stop at opinion. DVRG ends at allocation.
            </p>
          </div>
        </div>
      </section>

      {/* ── Solution ─────────────────────────────────────────────────────── */}
      <section className="py-20" style={{ borderTop: '1px solid var(--border)' }}>
        <div className="container mx-auto px-4">
          <div className="max-w-5xl mx-auto">
            <div className="mb-12">
              <SectionLabel>The Solution</SectionLabel>
              <h2 className="text-2xl md:text-4xl font-bold text-text-primary tracking-tight">
                Meet DVRG: A Probabilistic Capital Allocation Engine
              </h2>
              <p className="mt-2 text-text-secondary max-w-xl">
                DVRG translates signal into conviction, conviction into position size, and position size
                into executable decisions. Every analysis ends with a deployable allocation framework.
              </p>
            </div>

            <div className="grid lg:grid-cols-2 gap-12">
              {/* Feature list */}
              <div>
                <div style={{ borderTop: '1px solid var(--border)' }}>
                  <AgentRow icon={<BarChart3 className="w-4 h-4" />} title="Expected Value Computation"
                    body="Opportunity quantified against scenario probability and risk geometry." />
                  <AgentRow icon={<TrendingUp className="w-4 h-4" />} title="Scenario-Weighted Outcomes"
                    body="Risk / Base / Re-rating paths modeled with probability distributions." />
                  <AgentRow icon={<Target className="w-4 h-4" />} title="Confidence Calibration"
                    body="Maps uncertainty into a structured conviction score before sizing." />
                  <AgentRow icon={<Shield className="w-4 h-4" />} title="Stability Diagnostics"
                    body="Identifies fragile setups before capital is committed." />
                  <AgentRow icon={<Zap className="w-4 h-4" />} title="Capital Translation Layer"
                    body="Every analysis ends with a structured, deployable allocation framework." />
                </div>
              </div>

              {/* Key differentiators panel */}
              <div
                className="rounded-card p-7"
                style={{ background: 'var(--surface-1)', border: '1px solid var(--border)' }}
              >
                <h4 className="text-sm font-semibold text-text-primary mb-5 uppercase tracking-wider text-text-secondary">
                  Key Differentiators
                </h4>
                <div className="space-y-3.5">
                  {[
                    ['Expected Value', 'not guesswork'],
                    ['Probability', 'not narrative'],
                    ['Conviction Sizing', 'not position guessing'],
                    ['Capital Translation', 'not data overload'],
                  ].map(([title, sub]) => (
                    <div key={title} className="flex items-start gap-3">
                      <CheckCircle2 className="w-4 h-4 text-success shrink-0 mt-0.5" />
                      <span className="text-sm text-text-secondary">
                        <strong className="text-text-primary">{title}</strong> &gt; {sub}
                      </span>
                    </div>
                  ))}
                </div>

                <div className="mt-6 pt-5" style={{ borderTop: '1px solid var(--border)' }}>
                  <p className="text-xs text-text-secondary leading-relaxed">
                    Replace fragmented research workflows with a unified decision system.
                  </p>
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
                body="Volatility, liquidity, and structural signals → market environment classification."
              />
              <Step
                n="2"
                title="Model Scenario-Weighted Outcomes"
                body="Maps plausible outcome distributions with probability-weighted paths."
              />
              <Step
                n="3"
                title="Quantify Expected Value"
                body="Opportunity computed against risk geometry and scenario weighting."
              />
              <Step
                n="4"
                title="Stress-Test Stability"
                body="Separates high-conviction setups from fragile, noise-driven signals."
              />
              <Step
                n="5"
                title="Translate into Capital Allocation"
                body="Allocation bias and position sizing derived from structured analysis — not opinion."
              />
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

      {/* ── Who DVRG Is For ───────────────────────────────────────────────── */}
      <section className="py-20" style={{ borderTop: '1px solid var(--border)' }}>
        <div className="container mx-auto px-4">
          <div className="max-w-5xl mx-auto">
            <div className="mb-12">
              <SectionLabel>Audience</SectionLabel>
              <h2 className="text-2xl md:text-4xl font-bold text-text-primary tracking-tight">
                Who DVRG Is For
              </h2>
            </div>

            <div className="grid md:grid-cols-2 gap-10">
              {/* Built For */}
              <div>
                <p className="text-xs font-semibold uppercase tracking-widest text-success mb-6">Built For</p>
                <div className="space-y-5">
                  {[
                    ['Active capital allocators', 'Investors who make deliberate, sized decisions — not passive accumulation.'],
                    ['Investors deploying meaningful capital', 'You need a structured process, not just more data or opinions.'],
                    ['Portfolio builders who size conviction', 'Position sizing is part of your edge. DVRG makes it systematic.'],
                  ].map(([title, body]) => (
                    <div key={title} className="flex gap-3 items-start">
                      <CheckCircle2 className="w-4 h-4 text-success shrink-0 mt-0.5" />
                      <div>
                        <p className="text-sm font-semibold text-text-primary">{title}</p>
                        <p className="text-sm text-text-secondary mt-0.5">{body}</p>
                      </div>
                    </div>
                  ))}
                </div>
              </div>

              {/* Not For */}
              <div>
                <p className="text-xs font-semibold uppercase tracking-widest text-text-tertiary mb-6">Not Built For</p>
                <div className="space-y-5">
                  {[
                    ['Headline traders', 'If your decisions are driven by breaking news or momentum alerts, this is not your tool.'],
                    ['Passive ETF allocators', 'DVRG is built for individual equity decisions, not index exposure.'],
                    ['Newsletter followers', 'This replaces opinion-based research stacks — not supplements them.'],
                  ].map(([title, body]) => (
                    <div key={title} className="flex gap-3 items-start">
                      <div className="w-4 h-4 shrink-0 mt-0.5 flex items-center justify-center">
                        <span className="text-text-tertiary font-bold text-sm leading-none">—</span>
                      </div>
                      <div>
                        <p className="text-sm font-semibold text-text-primary">{title}</p>
                        <p className="text-sm text-text-secondary mt-0.5">{body}</p>
                      </div>
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
                Choose Your Allocation Depth
              </h2>
            </div>
            <PricingCards />
            <p className="mt-8 text-center text-sm text-text-secondary">
              DVRG does not predict prices. It structures risk, probability, and deployable capital decisions.
            </p>
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
              Stop Guessing Conviction. Start Sizing Decisions.
            </h2>
            <p className="text-text-secondary">
              Replace fragmented research workflows with a unified capital allocation system.
            </p>
            <Link href="/welcome/free">
              <Button size="lg" variant="outline">
                Try Free — 2 Full Reports
              </Button>
            </Link>
          </div>
        </div>
      </section>

    </main>
  )
}
