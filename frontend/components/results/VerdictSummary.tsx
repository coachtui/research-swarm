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

function generateVerdictText(
  ticker: string,
  score: number,
  rating: string,
  strength: string,
  concern: string,
  call: string
): string {
  // Focus on WHY (thesis, divergence, drivers) not WHAT (action)
  // Remove action guidance - that's in DecisionAction card

  if (score >= 8.0 || rating.includes('STRONG BUY')) {
    return `${ticker} is firing on all cylinders. ${strength} creates a compelling opportunity with minimal friction. The fundamentals, technicals, and market sentiment are all aligned in a rare "green light" scenario.`
  } else if (score >= 6.5 || rating === 'BUY') {
    return `${ticker} shows solid fundamentals but faces timing headwinds. ${strength} provides long-term upside, but ${concern} suggests patience may be rewarded with better entry points.`
  } else if (score >= 5.0 || rating === 'HOLD') {
    return `${ticker} is caught in a tug-of-war between competing signals. ${strength} on one side, ${concern} on the other. The divergence suggests waiting for clearer directional alignment before making strong commitments.`
  } else {
    return `${ticker} faces significant structural headwinds that outweigh near-term positives. ${concern} The risk-reward profile is unfavorable until these fundamental issues are resolved.`
  }
}
