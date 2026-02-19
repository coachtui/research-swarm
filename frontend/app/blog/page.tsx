import Link from 'next/link'

export const metadata = {
  title: 'Blog - DVRG',
  description: 'Insights on AI-powered investing, signal divergence, dark pool analysis, and institutional flow detection.',
}

export default function BlogPage() {
  return (
    <div className="container mx-auto px-4 py-16">
      <div className="max-w-3xl mx-auto space-y-12">

        {/* Header */}
        <div className="space-y-3">
          <h1 className="text-4xl font-bold text-text-primary">Blog</h1>
          <p className="text-lg text-text-secondary">
            Insights on signal divergence, institutional flow, and AI-driven investing.
          </p>
        </div>

        {/* Coming Soon State */}
        <div className="bg-surface rounded-card p-12 text-center space-y-4">
          <div className="flex h-14 w-14 items-center justify-center rounded-full bg-primary/10 mx-auto">
            <svg className="h-7 w-7 text-primary" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5}
                d="M19.5 14.25v-2.625a3.375 3.375 0 00-3.375-3.375h-1.5A1.125 1.125 0 0113.5 7.125v-1.5a3.375 3.375 0 00-3.375-3.375H8.25m0 12.75h7.5m-7.5 3H12M10.5 2.25H5.625c-.621 0-1.125.504-1.125 1.125v17.25c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 00-9-9z" />
            </svg>
          </div>
          <h2 className="text-xl font-semibold text-text-primary">Posts coming soon</h2>
          <p className="text-text-secondary max-w-md mx-auto">
            We&apos;re working on deep-dives into dark pool mechanics, institutional signal
            interpretation, and how to use DVRG to find divergence plays before earnings.
          </p>
        </div>

        {/* Topic previews */}
        <div className="space-y-4">
          <h2 className="text-lg font-semibold text-text-primary">What we&apos;ll cover</h2>
          <ul className="space-y-3">
            {[
              'How to read dark pool ATS data — and when it matters',
              'The 7 signals DVRG tracks and how they interact',
              'Insider buying patterns that precede breakouts',
              'Earnings revision divergence: the most underused edge in retail investing',
              'Blended valuation methodologies vs. pure DCF',
            ].map((topic) => (
              <li key={topic} className="flex items-start gap-3 text-text-secondary text-sm">
                <span className="mt-1 h-1.5 w-1.5 rounded-full bg-primary flex-shrink-0" />
                {topic}
              </li>
            ))}
          </ul>
        </div>

        {/* CTA */}
        <div className="pt-4 border-t border-surface-elevated">
          <p className="text-text-secondary text-sm">
            In the meantime, try the platform —{' '}
            <Link href="/analyze" className="text-primary hover:underline">
              analyze a stock now
            </Link>.
          </p>
        </div>

      </div>
    </div>
  )
}
