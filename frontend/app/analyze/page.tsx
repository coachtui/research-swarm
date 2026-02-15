import { TickerSearchForm } from '@/components/analyze/TickerSearchForm'

export const metadata = {
  title: 'Analyze Stock - DVRG',
  description: 'Get institutional-quality AI stock analysis in 4 minutes. $14.99 per report.',
}

export default function AnalyzePage() {
  return (
    <div className="container mx-auto px-4 py-12">
      <div className="max-w-4xl mx-auto space-y-8">
        {/* Header */}
        <div className="text-center space-y-3">
          <h1 className="text-3xl md:text-4xl font-bold text-text-primary">
            Analyze Your Stock
          </h1>
          <p className="text-lg text-text-secondary max-w-2xl mx-auto">
            Get institutional-quality research powered by AI. We analyze 13+ data sources
            to detect what Wall Street doesn't tell you.
          </p>
        </div>

        {/* Form */}
        <TickerSearchForm />

        {/* Example Tickers - Static display */}
        <div className="text-center space-y-3">
          <p className="text-sm text-text-secondary">Popular stocks to analyze:</p>
          <div className="flex flex-wrap justify-center gap-2">
            {['NVDA', 'AAPL', 'MSFT', 'GOOGL', 'TSLA', 'META', 'AMZN', 'TSM'].map((ticker) => (
              <div
                key={ticker}
                className="px-3 py-1 rounded-button bg-surface text-text-secondary text-sm"
              >
                {ticker}
              </div>
            ))}
          </div>
        </div>

        {/* Guarantee */}
        <div className="rounded-card bg-primary/5 border border-primary/20 p-6 text-center space-y-2">
          <h3 className="font-semibold text-primary">Money-Back Guarantee</h3>
          <p className="text-sm text-text-secondary">
            If your analysis fails for any reason, we'll automatically issue a full refund.
            No questions asked.
          </p>
        </div>

        {/* Trust Indicators */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 text-center">
          <div className="space-y-1">
            <div className="text-2xl font-bold text-primary">~4 min</div>
            <div className="text-sm text-text-secondary">Average analysis time</div>
          </div>
          <div className="space-y-1">
            <div className="text-2xl font-bold text-primary">13+</div>
            <div className="text-sm text-text-secondary">Data sources analyzed</div>
          </div>
          <div className="space-y-1">
            <div className="text-2xl font-bold text-primary">$14.99</div>
            <div className="text-sm text-text-secondary">One-time payment</div>
          </div>
        </div>
      </div>
    </div>
  )
}
