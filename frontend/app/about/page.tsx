import Link from 'next/link'

export const metadata = {
  title: 'About - DVRG',
  description: 'Learn about DVRG — AI-powered institutional-grade stock analysis that detects divergences before the market does.',
}

export default function AboutPage() {
  return (
    <div className="container mx-auto px-4 py-16">
      <div className="max-w-3xl mx-auto space-y-16">

        {/* Hero */}
        <div className="space-y-4">
          <h1 className="text-4xl font-bold text-text-primary">About DVRG</h1>
          <p className="text-xl text-text-secondary leading-relaxed">
            DVRG gives individual investors access to the same multi-signal analysis
            that institutional desks have used for decades — delivered in minutes, not days.
          </p>
        </div>

        {/* Mission */}
        <div className="space-y-4">
          <h2 className="text-2xl font-semibold text-text-primary">Our Mission</h2>
          <p className="text-text-secondary leading-relaxed">
            Wall Street has always had an information edge. Institutional research teams can
            cross-reference dark pool activity, insider filings, earnings revision trends,
            and macro signals simultaneously — and act before the public catches on.
          </p>
          <p className="text-text-secondary leading-relaxed">
            DVRG was built to close that gap. By combining AI-driven analysis across 13+
            data sources, we surface the divergences between what institutions are doing and
            what the public narrative says — so you can position ahead of the crowd, not after.
          </p>
        </div>

        {/* How It Works */}
        <div className="space-y-6">
          <h2 className="text-2xl font-semibold text-text-primary">How It Works</h2>
          <div className="grid gap-6 md:grid-cols-3">
            {[
              {
                step: '01',
                title: 'Multi-Agent Research',
                description:
                  'Three specialized AI agents run in parallel — a Fundamentalist, a News Hound, and a Quant — each analyzing different signal layers simultaneously.',
              },
              {
                step: '02',
                title: 'Signal Divergence Detection',
                description:
                  'Our manager agent cross-references 7 signals (news, earnings, analyst ratings, institutional flow, insider activity, dark pool, and technicals) to find where smart money diverges from public narrative.',
              },
              {
                step: '03',
                title: 'Actionable Thesis',
                description:
                  'Results are synthesized into a structured investment thesis with a clear recommendation, structural valuation reference, price targets, and key risks — not just raw data.',
              },
            ].map((item) => (
              <div key={item.step} className="bg-surface rounded-card p-6 space-y-3">
                <span className="text-xs font-mono text-primary">{item.step}</span>
                <h3 className="font-semibold text-text-primary">{item.title}</h3>
                <p className="text-sm text-text-secondary leading-relaxed">{item.description}</p>
              </div>
            ))}
          </div>
        </div>

        {/* Data Sources */}
        <div className="space-y-4">
          <h2 className="text-2xl font-semibold text-text-primary">Data Sources</h2>
          <p className="text-text-secondary leading-relaxed">
            DVRG pulls from public and regulatory sources including SEC 13F filings, FINRA
            ATS (dark pool) transparency data, OpenInsider insider transaction filings,
            earnings revision feeds, analyst consensus data, and real-time news sentiment.
            All data is processed through models purpose-built for financial signal extraction.
          </p>
        </div>

        {/* CTA */}
        <div className="bg-surface rounded-card p-8 text-center space-y-4">
          <h2 className="text-xl font-semibold text-text-primary">Ready to see it in action?</h2>
          <p className="text-text-secondary">Run your first analysis in under 5 minutes.</p>
          <Link
            href="/analyze"
            className="inline-block px-6 py-3 bg-primary text-white font-medium rounded-button hover:bg-primary/90 transition-colors"
          >
            Analyze a Stock
          </Link>
        </div>

      </div>
    </div>
  )
}
