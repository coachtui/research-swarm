import Link from 'next/link'
import { Button } from '@/components/ui/button'
import { PricingCards } from '@/components/pricing/PricingCards'
import {
  TrendingUp,
  Zap,
  Shield,
  DollarSign,
  Clock,
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
              Institutional-Quality Research in 4 Minutes
            </div>

            <h1 className="text-4xl md:text-6xl font-bold text-text-primary leading-tight tracking-tight">
              AI-Powered Stock Analysis<br />
              That Detects What Wall Street{' '}
              <span className="text-primary">Doesn&apos;t Tell You</span>
            </h1>

            <p className="text-lg text-text-secondary leading-relaxed max-w-2xl mx-auto">
              Stop relying on biased analyst reports and incomplete data.
              Multi-agent AI analysis that uncovers divergences before the market does.
            </p>

            <div className="flex flex-col sm:flex-row gap-3 justify-center pt-2">
              <Link href="/sign-up">
                <Button size="lg" className="w-full sm:w-auto">
                  Start Analyzing <ArrowRight className="ml-2 w-4 h-4" />
                </Button>
              </Link>
              <Link href="#how-it-works">
                <Button size="lg" variant="outline" className="w-full sm:w-auto">
                  See How It Works
                </Button>
              </Link>
            </div>

            {/* Trust strip */}
            <div className="flex flex-wrap items-center justify-center gap-6 text-xs text-text-secondary pt-4">
              {[
                'Starting at $19.99/month',
                '5–50 analyses per month',
                '4-minute analysis',
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
                Traditional Stock Research Is Broken
              </h2>
              <p className="mt-2 text-text-secondary max-w-xl">
                Retail investors are at a massive disadvantage.
              </p>
            </div>

            <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-px"
              style={{ background: 'var(--border)' }}>
              {[
                { icon: <DollarSign className="w-5 h-5" />, title: 'Expensive Research',
                  body: 'Professional analyst reports cost $500–$2,000+ each, or expensive Bloomberg/FactSet subscriptions at $2,000+/month.' },
                { icon: <Clock className="w-5 h-5" />, title: 'Time-Consuming Analysis',
                  body: 'Proper due diligence requires 10–20+ hours per stock, analyzing financials, technicals, news, and sentiment.' },
                { icon: <AlertTriangle className="w-5 h-5" />, title: 'Biased Information',
                  body: 'Wall Street analysts have conflicts of interest. Their "buy" ratings often protect banking relationships, not your portfolio.' },
                { icon: <Target className="w-5 h-5" />, title: 'Missing Divergences',
                  body: 'Critical signals when fundamentals and technicals don\'t align go unnoticed until it\'s too late.' },
                { icon: <BarChart3 className="w-5 h-5" />, title: 'Information Overload',
                  body: 'Thousands of data points across earnings calls, SEC filings, news, and charts—impossible to synthesize manually.' },
                { icon: <Shield className="w-5 h-5" />, title: 'No Institutional Tools',
                  body: 'Hedge funds use sophisticated quant models and alternative data. Retail investors are left with basic screeners.' },
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
                Meet DVRG: Your AI Research Team
              </h2>
              <p className="mt-2 text-text-secondary max-w-xl">
                Multi-agent AI delivering institutional-quality analysis at a fraction of the cost and time.
              </p>
            </div>

            <div className="grid lg:grid-cols-2 gap-12">
              {/* Agent list */}
              <div>
                <div style={{ borderTop: '1px solid var(--border)' }}>
                  <AgentRow icon={<BarChart3 className="w-4 h-4" />} title="Fundamentalist Agent"
                    body="Deep-dives into financials, moat strength, competitive positioning, and valuation metrics." />
                  <AgentRow icon={<LineChart className="w-4 h-4" />} title="Quant Technician Agent"
                    body="Analyzes price action, momentum, volume patterns, and technical indicators." />
                  <AgentRow icon={<Newspaper className="w-4 h-4" />} title="News Hound Agent"
                    body="Scans recent news, earnings calls, and market sentiment to gauge market perception." />
                  <AgentRow icon={<TrendingUp className="w-4 h-4" />} title="Manager Agent"
                    body="Synthesizes all findings, detects signal divergences, and generates actionable investment thesis." />
                </div>
              </div>

              {/* Deliverables panel */}
              <div
                className="rounded-card p-7"
                style={{ background: 'var(--surface-1)', border: '1px solid var(--border)' }}
              >
                <h4 className="text-sm font-semibold text-text-primary mb-5 uppercase tracking-wider text-text-secondary">
                  Key Deliverables
                </h4>
                <div className="space-y-3.5">
                  {[
                    ['Moat Score (0–10)', 'Competitive advantage strength'],
                    ['Signal Breakdown', '5 key metrics with divergence detection'],
                    ['Investment Thesis', 'Clear bull/bear case with catalysts'],
                    ['Risk Assessment', 'Key risks and downside scenarios'],
                    ['Full Report', 'Comprehensive analysis with data citations'],
                  ].map(([title, sub]) => (
                    <div key={title} className="flex items-start gap-3">
                      <CheckCircle2 className="w-4 h-4 text-success shrink-0 mt-0.5" />
                      <span className="text-sm text-text-secondary">
                        <strong className="text-text-primary">{title}:</strong> {sub}
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
                How It Works
              </h2>
              <p className="mt-2 text-text-secondary">
                From ticker symbol to comprehensive analysis in three simple steps.
              </p>
            </div>

            <div style={{ borderTop: '1px solid var(--border)' }}>
              <Step
                n="1"
                title="Enter a Ticker Symbol"
                body="Type any US stock ticker (e.g., AAPL, TSLA, NVDA). Our system instantly fetches real-time data from financial APIs."
              />
              <Step
                n="2"
                title="AI Agents Analyze in Parallel"
                body="Four specialized AI agents work simultaneously, each bringing unique expertise."
                sub={
                  <ul className="mt-3 space-y-1.5 text-sm text-text-secondary">
                    {[
                      ['Fundamentalist', 'evaluates business model, competitive moat, and financial health'],
                      ['Quant Technician', 'analyzes price trends, momentum, and technical signals'],
                      ['News Hound', 'processes recent news, sentiment, and market narratives'],
                      ['Manager', 'synthesizes findings and detects signal divergences'],
                    ].map(([name, desc]) => (
                      <li key={name} className="flex gap-2">
                        <span className="text-primary shrink-0">·</span>
                        <span><strong className="text-text-primary">{name}</strong> {desc}</span>
                      </li>
                    ))}
                  </ul>
                }
              />
              <Step
                n="3"
                title="Get Your Report"
                body="Receive a comprehensive investment report with moat score, signal breakdown, thesis, risks, and full analysis—all in under 4 minutes. Download as PDF or save to your dashboard."
              />
            </div>

            <div className="mt-10 text-center">
              <Link href="/sign-up">
                <Button size="lg">
                  Try It Now <ArrowRight className="ml-2 w-4 h-4" />
                </Button>
              </Link>
            </div>
          </div>
        </div>
      </section>

      {/* ── Pricing ──────────────────────────────────────────────────────── */}
      <section id="pricing" className="py-20" style={{ borderTop: '1px solid var(--border)' }}>
        <div className="container mx-auto px-4">
          <div className="max-w-5xl mx-auto">
            <div className="mb-12">
              <SectionLabel>Pricing</SectionLabel>
              <h2 className="text-2xl md:text-4xl font-bold text-text-primary tracking-tight">
                Simple, Transparent Pricing
              </h2>
              <p className="mt-2 text-text-secondary">
                Choose the plan that fits your research needs.
              </p>
            </div>
            <PricingCards />
            <p className="mt-8 text-center text-sm text-text-secondary">
              Compare to analyst reports at $500–$2,000 each or Bloomberg Terminal at $24,000/year.
            </p>
          </div>
        </div>
      </section>

      {/* ── FAQ ──────────────────────────────────────────────────────────── */}
      <section id="faq" className="py-20" style={{ borderTop: '1px solid var(--border)', background: 'var(--surface-1)' }}>
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
                q="How accurate is the AI analysis?"
                a="Our AI agents use the same data sources as institutional investors (financial statements, SEC filings, market data). While no analysis can predict the future with certainty, DVRG excels at synthesizing large amounts of data objectively and detecting signal divergences that humans often miss."
              />
              <FaqItem
                q="Is this investment advice?"
                a="No. DVRG provides analysis and research, not personalized investment advice. Always do your own due diligence and consult a licensed financial advisor before making investment decisions."
              />
              <FaqItem
                q="Can I get a refund if I'm not satisfied?"
                a="Yes! We offer a 100% satisfaction guarantee. If you're not happy with your first report, contact us within 7 days for a full refund, no questions asked."
              />
              <FaqItem
                q="What stocks can I analyze?"
                a="Currently, we support all US-listed stocks (NYSE, NASDAQ). We're working on adding international markets, ETFs, and cryptocurrencies soon."
              />
              <FaqItem
                q="How is this different from free stock screeners?"
                a="Stock screeners show you raw data. DVRG synthesizes that data into actionable insights, detects divergences between signals, and delivers a comprehensive investment thesis—like having a team of analysts working for you."
              />
              <FaqItem
                q="Do reports get updated over time?"
                a="Each report is a snapshot in time. However, you can re-run analysis on the same stock to get updated insights. All paid plan users receive automatic watchlist alerts when significant changes are detected."
              />
            </div>
          </div>
        </div>
      </section>

      {/* ── Final CTA ────────────────────────────────────────────────────── */}
      <section className="py-20" style={{ borderTop: '1px solid var(--border)' }}>
        <div className="container mx-auto px-4">
          <div className="max-w-2xl mx-auto text-center space-y-6">
            <h2 className="text-2xl md:text-4xl font-bold text-text-primary tracking-tight">
              Ready to Level Up Your Stock Research?
            </h2>
            <p className="text-text-secondary">
              Join investors making smarter decisions with AI-powered analysis.
            </p>
            <Link href="/analyze">
              <Button size="lg" variant="outline">
                Analyze Your First Stock
              </Button>
            </Link>
          </div>
        </div>
      </section>

    </main>
  )
}
