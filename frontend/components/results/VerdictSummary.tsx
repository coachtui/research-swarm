import { Card } from '@/components/ui/card'
import { MessageCircle } from 'lucide-react'

interface VerdictSummaryProps {
  ticker: string
  overall_score: number
  rating: string
  key_strength: string
  key_concern: string
  the_call: string
}

export function VerdictSummary({
  ticker,
  overall_score,
  rating,
  key_strength,
  key_concern,
  the_call,
}: VerdictSummaryProps) {
  // Generate conversational summary based on score
  const verdictText = generateVerdictText(ticker, overall_score, rating, key_strength, key_concern, the_call)

  return (
    <Card className="mt-6 p-6 bg-gradient-to-br from-primary/5 to-primary/10 border-l-4 border-l-primary">
      <div className="flex items-start gap-3">
        <div className="h-10 w-10 rounded-full bg-primary/10 flex items-center justify-center flex-shrink-0">
          <MessageCircle className="h-5 w-5 text-primary" />
        </div>
        <div className="flex-1">
          <h3 className="font-semibold text-lg mb-3 flex items-center gap-2">
            The Verdict
            <span className="text-xs font-normal text-muted-foreground">
              • 30-second summary
            </span>
          </h3>
          <div className="prose prose-sm dark:prose-invert max-w-none">
            <p className="text-foreground/90 leading-relaxed mb-0">
              {verdictText}
            </p>
          </div>
        </div>
      </div>
    </Card>
  )
}

// Pick a variant index deterministically from the ticker string
function tickerVariant(ticker: string, count: number): number {
  const sum = ticker.split('').reduce((acc, c) => acc + c.charCodeAt(0), 0)
  return sum % count
}

function generateVerdictText(
  ticker: string,
  score: number,
  rating: string,
  strength: string,
  concern: string,
  _call: string
): string {
  // Focus on WHY (thesis, divergence, drivers) not WHAT (action)
  // Remove action guidance - that's in DecisionAction card

  if (score >= 8.0 || rating.includes('STRONG BUY')) {
    const variants = [
      `${ticker} is firing on all cylinders. ${strength} creates a compelling opportunity with minimal friction. The fundamentals, technicals, and market sentiment are all aligned in a rare "green light" scenario.`,
      `${ticker} has everything going for it right now. ${strength} — and the broader signal picture confirms it. Rare moments of full convergence like this are exactly what high-conviction setups look like.`,
      `The bull case for ${ticker} is unusually clean. ${strength}, and there are few credible counterarguments at this stage. Market sentiment, fundamentals, and momentum are all reading from the same playbook.`,
    ]
    return variants[tickerVariant(ticker, variants.length)]

  } else if (score >= 6.5 || rating === 'BUY') {
    const variants = [
      `${ticker} shows solid fundamentals but faces timing headwinds. ${strength} provides long-term upside, but ${concern} suggests patience may be rewarded with better entry points.`,
      `${ticker} is a compelling story with one chapter still unresolved. ${strength} anchors the bull case — the hangup is ${concern}. Quality is here; the question is when the market agrees.`,
      `${ticker} earns its place on a buy list, but not without caveats. ${strength} is a genuine positive. ${concern} means the setup isn't perfect yet — better entries may come to those who wait.`,
    ]
    return variants[tickerVariant(ticker, variants.length)]

  } else if (score >= 5.0 || rating === 'HOLD') {
    const variants = [
      `${ticker} is telling two stories at once. ${strength}, which supports the bull case. But ${concern} keeps conviction in check. The market needs a catalyst to pick a direction.`,
      `The picture for ${ticker} is genuinely mixed. ${strength} points toward upside, while ${concern} is hard to ignore. It's a name for watchlists, not portfolios — until one narrative wins out.`,
      `${ticker} is at a fork in the road. ${strength} builds the case for patience. ${concern} is the friction preventing a breakout. How upcoming catalysts resolve this gap will determine the trade.`,
      `${ticker} has real positives, but the math doesn't add up to a clear entry. ${strength} is legitimate. So is ${concern}. The signals are splitting the difference, which usually means the market is too.`,
      `Right now, ${ticker} rewards careful observers more than active traders. ${strength} builds a long-term case, but ${concern} is stalling near-term momentum. Conviction is hard to sustain in both directions.`,
    ]
    return variants[tickerVariant(ticker, variants.length)]

  } else {
    const variants = [
      `${ticker} faces significant structural headwinds that outweigh near-term positives. ${concern} The risk-reward profile is unfavorable until these fundamental issues are resolved.`,
      `The bear case for ${ticker} is hard to argue against right now. ${concern} What looked like temporary friction is looking more like a structural issue — and the signal picture reflects it.`,
      `${ticker} is showing the kind of deterioration that's hard to ignore. ${concern} The positives exist but they're fighting uphill. This is a name to revisit when the damage is better understood.`,
    ]
    return variants[tickerVariant(ticker, variants.length)]
  }
}
