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
  Newspaper
} from 'lucide-react'

export default function Home() {
  return (
    <main className="min-h-screen">
      {/* Hero Section */}
      <section className="relative overflow-hidden bg-gradient-to-b from-surface to-background">
        <div className="container mx-auto px-4 py-20 md:py-28">
          <div className="text-center space-y-8 max-w-5xl mx-auto">
            <div className="inline-flex items-center gap-2 px-4 py-2 rounded-full bg-primary/10 border border-primary/20 text-primary text-sm font-medium">
              <Zap className="w-4 h-4" />
              Institutional-Quality Research in 4 Minutes
            </div>

            <h1 className="text-5xl md:text-7xl font-bold text-text-primary leading-tight">
              AI-Powered Stock Analysis<br />
              That Detects What Wall Street{' '}
              <span className="text-primary">Doesn't Tell You</span>
            </h1>

            <p className="text-xl md:text-2xl text-text-secondary max-w-3xl mx-auto">
              Stop relying on biased analyst reports and incomplete data.
              Get multi-agent AI analysis that uncovers divergences before the market does.
            </p>

            <div className="flex flex-col sm:flex-row gap-4 justify-center pt-6">
              <Link href="/sign-up">
                <Button size="lg" className="text-lg px-8 py-6 w-full sm:w-auto">
                  Start Analyzing <ArrowRight className="ml-2 w-5 h-5" />
                </Button>
              </Link>
              <Link href="#how-it-works">
                <Button size="lg" variant="outline" className="text-lg px-8 py-6 w-full sm:w-auto">
                  See How It Works
                </Button>
              </Link>
            </div>

            <div className="pt-8 flex flex-wrap items-center justify-center gap-8 text-sm text-text-secondary">
              <div className="flex items-center gap-2">
                <CheckCircle2 className="w-5 h-5 text-success" />
                <span>Starting at $19.99/month</span>
              </div>
              <div className="flex items-center gap-2">
                <CheckCircle2 className="w-5 h-5 text-success" />
                <span>10-30 reports per month</span>
              </div>
              <div className="flex items-center gap-2">
                <CheckCircle2 className="w-5 h-5 text-success" />
                <span>4-minute analysis</span>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* Pain Points Section */}
      <section className="py-20 bg-background">
        <div className="container mx-auto px-4">
          <div className="text-center mb-16">
            <h2 className="text-3xl md:text-5xl font-bold text-text-primary mb-4">
              The Problem with Traditional Stock Research
            </h2>
            <p className="text-xl text-text-secondary max-w-3xl mx-auto">
              Retail investors are at a massive disadvantage
            </p>
          </div>

          <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-8 max-w-6xl mx-auto">
            {/* Pain Point 1 */}
            <div className="p-6 rounded-xl bg-surface border border-surface-elevated">
              <div className="w-12 h-12 rounded-lg bg-error/10 flex items-center justify-center mb-4">
                <DollarSign className="w-6 h-6 text-error" />
              </div>
              <h3 className="text-xl font-semibold text-text-primary mb-2">
                Expensive Research
              </h3>
              <p className="text-text-secondary">
                Professional analyst reports cost $500-$2,000+ each, or require expensive Bloomberg/FactSet subscriptions at $2,000+/month.
              </p>
            </div>

            {/* Pain Point 2 */}
            <div className="p-6 rounded-xl bg-surface border border-surface-elevated">
              <div className="w-12 h-12 rounded-lg bg-error/10 flex items-center justify-center mb-4">
                <Clock className="w-6 h-6 text-error" />
              </div>
              <h3 className="text-xl font-semibold text-text-primary mb-2">
                Time-Consuming Analysis
              </h3>
              <p className="text-text-secondary">
                Proper due diligence requires 10-20+ hours per stock, analyzing financials, technicals, news, and market sentiment.
              </p>
            </div>

            {/* Pain Point 3 */}
            <div className="p-6 rounded-xl bg-surface border border-surface-elevated">
              <div className="w-12 h-12 rounded-lg bg-error/10 flex items-center justify-center mb-4">
                <AlertTriangle className="w-6 h-6 text-error" />
              </div>
              <h3 className="text-xl font-semibold text-text-primary mb-2">
                Biased Information
              </h3>
              <p className="text-text-secondary">
                Wall Street analysts have conflicts of interest. Their "buy" ratings often protect banking relationships, not your portfolio.
              </p>
            </div>

            {/* Pain Point 4 */}
            <div className="p-6 rounded-xl bg-surface border border-surface-elevated">
              <div className="w-12 h-12 rounded-lg bg-error/10 flex items-center justify-center mb-4">
                <Target className="w-6 h-6 text-error" />
              </div>
              <h3 className="text-xl font-semibold text-text-primary mb-2">
                Missing Divergences
              </h3>
              <p className="text-text-secondary">
                Critical signals when fundamentals and technicals don't align go unnoticed until it's too late.
              </p>
            </div>

            {/* Pain Point 5 */}
            <div className="p-6 rounded-xl bg-surface border border-surface-elevated">
              <div className="w-12 h-12 rounded-lg bg-error/10 flex items-center justify-center mb-4">
                <BarChart3 className="w-6 h-6 text-error" />
              </div>
              <h3 className="text-xl font-semibold text-text-primary mb-2">
                Information Overload
              </h3>
              <p className="text-text-secondary">
                Thousands of data points across earnings calls, SEC filings, news, and charts—impossible to synthesize manually.
              </p>
            </div>

            {/* Pain Point 6 */}
            <div className="p-6 rounded-xl bg-surface border border-surface-elevated">
              <div className="w-12 h-12 rounded-lg bg-error/10 flex items-center justify-center mb-4">
                <Shield className="w-6 h-6 text-error" />
              </div>
              <h3 className="text-xl font-semibold text-text-primary mb-2">
                No Access to Institutional Tools
              </h3>
              <p className="text-text-secondary">
                Hedge funds use sophisticated quant models and alternative data. Retail investors are left with basic screeners.
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* Solution Section - What is DVRG */}
      <section className="py-20 bg-gradient-to-b from-surface to-background">
        <div className="container mx-auto px-4">
          <div className="max-w-6xl mx-auto">
            <div className="text-center mb-16">
              <h2 className="text-3xl md:text-5xl font-bold text-text-primary mb-4">
                Meet DVRG: Your AI Research Team
              </h2>
              <p className="text-xl text-text-secondary max-w-3xl mx-auto">
                Multi-agent AI system that delivers institutional-quality analysis at a fraction of the cost and time
              </p>
            </div>

            <div className="grid lg:grid-cols-2 gap-12 items-center mb-16">
              <div className="space-y-6">
                <h3 className="text-2xl md:text-3xl font-bold text-text-primary">
                  What is DVRG?
                </h3>
                <p className="text-lg text-text-secondary">
                  DVRG is an AI-powered stock analysis platform that deploys four specialized research agents to analyze any stock in under 4 minutes:
                </p>
                <div className="space-y-4">
                  <div className="flex items-start gap-3">
                    <div className="w-10 h-10 rounded-lg bg-primary/10 flex items-center justify-center flex-shrink-0">
                      <BarChart3 className="w-5 h-5 text-primary" />
                    </div>
                    <div>
                      <h4 className="font-semibold text-text-primary mb-1">Fundamentalist Agent</h4>
                      <p className="text-text-secondary">Deep-dives into financials, moat strength, competitive positioning, and valuation metrics</p>
                    </div>
                  </div>
                  <div className="flex items-start gap-3">
                    <div className="w-10 h-10 rounded-lg bg-primary/10 flex items-center justify-center flex-shrink-0">
                      <LineChart className="w-5 h-5 text-primary" />
                    </div>
                    <div>
                      <h4 className="font-semibold text-text-primary mb-1">Quant Technician Agent</h4>
                      <p className="text-text-secondary">Analyzes price action, momentum, volume patterns, and technical indicators</p>
                    </div>
                  </div>
                  <div className="flex items-start gap-3">
                    <div className="w-10 h-10 rounded-lg bg-primary/10 flex items-center justify-center flex-shrink-0">
                      <Newspaper className="w-5 h-5 text-primary" />
                    </div>
                    <div>
                      <h4 className="font-semibold text-text-primary mb-1">News Hound Agent</h4>
                      <p className="text-text-secondary">Scans recent news, earnings calls, and market sentiment to gauge market perception</p>
                    </div>
                  </div>
                  <div className="flex items-start gap-3">
                    <div className="w-10 h-10 rounded-lg bg-primary/10 flex items-center justify-center flex-shrink-0">
                      <TrendingUp className="w-5 h-5 text-primary" />
                    </div>
                    <div>
                      <h4 className="font-semibold text-text-primary mb-1">Manager Agent</h4>
                      <p className="text-text-secondary">Synthesizes all findings, detects signal divergences, and generates actionable investment thesis</p>
                    </div>
                  </div>
                </div>
              </div>

              <div className="p-8 rounded-xl bg-surface border border-surface-elevated">
                <h4 className="text-xl font-semibold text-text-primary mb-6">Key Deliverables</h4>
                <div className="space-y-4">
                  <div className="flex items-center gap-3">
                    <CheckCircle2 className="w-5 h-5 text-success flex-shrink-0" />
                    <span className="text-text-secondary"><strong className="text-text-primary">Moat Score (0-10):</strong> Competitive advantage strength</span>
                  </div>
                  <div className="flex items-center gap-3">
                    <CheckCircle2 className="w-5 h-5 text-success flex-shrink-0" />
                    <span className="text-text-secondary"><strong className="text-text-primary">Signal Breakdown:</strong> 5 key metrics with divergence detection</span>
                  </div>
                  <div className="flex items-center gap-3">
                    <CheckCircle2 className="w-5 h-5 text-success flex-shrink-0" />
                    <span className="text-text-secondary"><strong className="text-text-primary">Investment Thesis:</strong> Clear bull/bear case with catalysts</span>
                  </div>
                  <div className="flex items-center gap-3">
                    <CheckCircle2 className="w-5 h-5 text-success flex-shrink-0" />
                    <span className="text-text-secondary"><strong className="text-text-primary">Risk Assessment:</strong> Key risks and downside scenarios</span>
                  </div>
                  <div className="flex items-center gap-3">
                    <CheckCircle2 className="w-5 h-5 text-success flex-shrink-0" />
                    <span className="text-text-secondary"><strong className="text-text-primary">Full Report:</strong> Comprehensive analysis with data citations</span>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* How It Works */}
      <section id="how-it-works" className="py-20 bg-background">
        <div className="container mx-auto px-4">
          <div className="text-center mb-16">
            <h2 className="text-3xl md:text-5xl font-bold text-text-primary mb-4">
              How It Works
            </h2>
            <p className="text-xl text-text-secondary max-w-3xl mx-auto">
              From ticker symbol to comprehensive analysis in three simple steps
            </p>
          </div>

          <div className="max-w-4xl mx-auto space-y-8">
            {/* Step 1 */}
            <div className="flex flex-col md:flex-row gap-6 items-start">
              <div className="w-16 h-16 rounded-xl bg-primary/10 border-2 border-primary flex items-center justify-center flex-shrink-0">
                <span className="text-2xl font-bold text-primary">1</span>
              </div>
              <div className="flex-1">
                <h3 className="text-2xl font-semibold text-text-primary mb-2">Enter a Ticker Symbol</h3>
                <p className="text-lg text-text-secondary">
                  Type any US stock ticker (e.g., AAPL, TSLA, NVDA). Our system instantly fetches real-time data from financial APIs.
                </p>
              </div>
            </div>

            {/* Step 2 */}
            <div className="flex flex-col md:flex-row gap-6 items-start">
              <div className="w-16 h-16 rounded-xl bg-primary/10 border-2 border-primary flex items-center justify-center flex-shrink-0">
                <span className="text-2xl font-bold text-primary">2</span>
              </div>
              <div className="flex-1">
                <h3 className="text-2xl font-semibold text-text-primary mb-2">AI Agents Analyze in Parallel</h3>
                <p className="text-lg text-text-secondary mb-3">
                  Four specialized AI agents work simultaneously, each bringing their unique expertise:
                </p>
                <ul className="space-y-2 text-text-secondary">
                  <li className="flex items-start gap-2">
                    <span className="text-primary mt-1">•</span>
                    <span><strong>Fundamentalist</strong> evaluates business model, competitive moat, and financial health</span>
                  </li>
                  <li className="flex items-start gap-2">
                    <span className="text-primary mt-1">•</span>
                    <span><strong>Quant Technician</strong> analyzes price trends, momentum, and technical signals</span>
                  </li>
                  <li className="flex items-start gap-2">
                    <span className="text-primary mt-1">•</span>
                    <span><strong>News Hound</strong> processes recent news, sentiment, and market narratives</span>
                  </li>
                  <li className="flex items-start gap-2">
                    <span className="text-primary mt-1">•</span>
                    <span><strong>Manager</strong> synthesizes findings and detects signal divergences</span>
                  </li>
                </ul>
              </div>
            </div>

            {/* Step 3 */}
            <div className="flex flex-col md:flex-row gap-6 items-start">
              <div className="w-16 h-16 rounded-xl bg-primary/10 border-2 border-primary flex items-center justify-center flex-shrink-0">
                <span className="text-2xl font-bold text-primary">3</span>
              </div>
              <div className="flex-1">
                <h3 className="text-2xl font-semibold text-text-primary mb-2">Get Your Report</h3>
                <p className="text-lg text-text-secondary">
                  Receive a comprehensive investment report with moat score, signal breakdown, thesis, risks, and full analysis—all in under 4 minutes. Download as PDF or save to your dashboard.
                </p>
              </div>
            </div>
          </div>

          <div className="text-center mt-12">
            <Link href="/sign-up">
              <Button size="lg" className="text-lg px-8 py-6">
                Try It Now <ArrowRight className="ml-2 w-5 h-5" />
              </Button>
            </Link>
          </div>
        </div>
      </section>

      {/* Pricing */}
      <section id="pricing" className="py-20 bg-surface">
        <div className="container mx-auto px-4">
          <div className="text-center mb-16">
            <h2 className="text-3xl md:text-5xl font-bold text-text-primary mb-4">
              Simple, Transparent Pricing
            </h2>
            <p className="text-xl text-text-secondary max-w-3xl mx-auto">
              Choose the plan that fits your research needs
            </p>
          </div>

          <PricingCards />

          <div className="text-center mt-12 text-text-secondary">
            <p>Compare to traditional analyst reports at $500-$2,000 each or Bloomberg Terminal at $24,000/year</p>
          </div>
        </div>
      </section>

      {/* FAQ */}
      <section id="faq" className="py-20 bg-background">
        <div className="container mx-auto px-4">
          <div className="text-center mb-16">
            <h2 className="text-3xl md:text-5xl font-bold text-text-primary mb-4">
              Frequently Asked Questions
            </h2>
          </div>

          <div className="max-w-3xl mx-auto space-y-6">
            <details className="p-6 rounded-xl bg-surface border border-surface-elevated group">
              <summary className="font-semibold text-lg text-text-primary cursor-pointer list-none flex justify-between items-center">
                How accurate is the AI analysis?
                <span className="text-primary group-open:rotate-180 transition-transform">▼</span>
              </summary>
              <p className="mt-4 text-text-secondary">
                Our AI agents use the same data sources as institutional investors (financial statements, SEC filings, market data). While no analysis can predict the future with certainty, DVRG excels at synthesizing large amounts of data objectively and detecting signal divergences that humans often miss.
              </p>
            </details>

            <details className="p-6 rounded-xl bg-surface border border-surface-elevated group">
              <summary className="font-semibold text-lg text-text-primary cursor-pointer list-none flex justify-between items-center">
                Is this investment advice?
                <span className="text-primary group-open:rotate-180 transition-transform">▼</span>
              </summary>
              <p className="mt-4 text-text-secondary">
                No. DVRG provides analysis and research, not personalized investment advice. Always do your own due diligence and consult a licensed financial advisor before making investment decisions.
              </p>
            </details>

            <details className="p-6 rounded-xl bg-surface border border-surface-elevated group">
              <summary className="font-semibold text-lg text-text-primary cursor-pointer list-none flex justify-between items-center">
                Can I get a refund if I'm not satisfied?
                <span className="text-primary group-open:rotate-180 transition-transform">▼</span>
              </summary>
              <p className="mt-4 text-text-secondary">
                Yes! We offer a 100% satisfaction guarantee. If you're not happy with your first report, contact us within 7 days for a full refund, no questions asked.
              </p>
            </details>

            <details className="p-6 rounded-xl bg-surface border border-surface-elevated group">
              <summary className="font-semibold text-lg text-text-primary cursor-pointer list-none flex justify-between items-center">
                What stocks can I analyze?
                <span className="text-primary group-open:rotate-180 transition-transform">▼</span>
              </summary>
              <p className="mt-4 text-text-secondary">
                Currently, we support all US-listed stocks (NYSE, NASDAQ). We're working on adding international markets, ETFs, and cryptocurrencies soon.
              </p>
            </details>

            <details className="p-6 rounded-xl bg-surface border border-surface-elevated group">
              <summary className="font-semibold text-lg text-text-primary cursor-pointer list-none flex justify-between items-center">
                How is this different from free stock screeners?
                <span className="text-primary group-open:rotate-180 transition-transform">▼</span>
              </summary>
              <p className="mt-4 text-text-secondary">
                Stock screeners show you raw data. DVRG synthesizes that data into actionable insights, detects divergences between signals, and delivers a comprehensive investment thesis—like having a team of analysts working for you.
              </p>
            </details>

            <details className="p-6 rounded-xl bg-surface border border-surface-elevated group">
              <summary className="font-semibold text-lg text-text-primary cursor-pointer list-none flex justify-between items-center">
                Do reports get updated over time?
                <span className="text-primary group-open:rotate-180 transition-transform">▼</span>
              </summary>
              <p className="mt-4 text-text-secondary">
                Each report is a snapshot in time. However, you can re-run analysis on the same stock to get updated insights. Pro plan users receive automatic watchlist alerts when significant changes are detected.
              </p>
            </details>
          </div>
        </div>
      </section>

      {/* Final CTA */}
      <section className="py-20 bg-gradient-to-b from-surface to-background">
        <div className="container mx-auto px-4">
          <div className="max-w-4xl mx-auto text-center space-y-8">
            <h2 className="text-4xl md:text-5xl font-bold text-text-primary">
              Ready to Level Up Your Stock Research?
            </h2>
            <p className="text-xl text-text-secondary">
              Join investors who are making smarter decisions with AI-powered analysis
            </p>
            <div className="flex flex-col sm:flex-row gap-4 justify-center">
              <Link href="/sign-up">
                <Button size="lg" className="text-lg px-8 py-6 w-full sm:w-auto">
                  Start Free Trial <ArrowRight className="ml-2 w-5 h-5" />
                </Button>
              </Link>
              <Link href="/analyze">
                <Button size="lg" variant="outline" className="text-lg px-8 py-6 w-full sm:w-auto">
                  Analyze Your First Stock
                </Button>
              </Link>
            </div>
          </div>
        </div>
      </section>
    </main>
  )
}
