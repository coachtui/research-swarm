export default function Home() {
  return (
    <main className="min-h-screen">
      <div className="container mx-auto px-4 py-16">
        <div className="text-center space-y-8">
          {/* Hero Section */}
          <div className="space-y-4">
            <h1 className="text-4xl md:text-5xl font-bold text-text-primary">
              AI-Powered Stock Analysis
            </h1>
            <h2 className="text-4xl md:text-5xl font-bold">
              That Detects What Wall Street{' '}
              <span className="text-primary">Doesn't Tell You</span>
            </h2>
            <p className="text-lg text-text-secondary max-w-2xl mx-auto mt-6">
              Get institutional-quality research in 4 minutes. $14.99 per report, no subscription.
            </p>
          </div>

          {/* CTA Button */}
          <div className="pt-8">
            <a
              href="/analyze"
              className="inline-block bg-primary hover:bg-primary-dark text-white font-semibold px-8 py-4 rounded-button text-lg transition-all transform hover:scale-105"
            >
              Analyze Your First Stock
            </a>
          </div>

          {/* Status Indicator */}
          <div className="pt-12 flex items-center justify-center gap-2 text-sm text-text-secondary">
            <div className="w-2 h-2 rounded-full bg-success animate-pulse"></div>
            <span>Backend API deployed and operational</span>
          </div>
        </div>
      </div>
    </main>
  )
}
