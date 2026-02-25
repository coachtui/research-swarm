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
  const verdictText = generateVerdictText(ticker, overall_score, rating, key_strength, key_concern, the_call)

  return (
    <Card className="mt-6 p-6 bg-gradient-to-br from-primary/5 to-primary/10 border-l-4 border-l-primary">
      <div className="flex items-start gap-3">
        <div className="h-10 w-10 rounded-full bg-primary/10 flex items-center justify-center flex-shrink-0">
          <MessageCircle className="h-5 w-5 text-primary" />
        </div>
        <div className="flex-1">
          <h3 className="font-semibold text-lg mb-3 flex items-center gap-2">
            Structural Analysis Summary
            <span className="text-xs font-normal text-muted-foreground">
              · Thesis overview
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
  // Focus on WHY (thesis, divergence, structural regime) not WHAT (action)
  // Institutional portfolio-management voice — deterministic, no conversational phrasing

  if (score >= 8.0 || rating.includes('STRONG BUY')) {
    const variants = [
      `${ticker} exhibits rare cross-signal convergence. ${strength}. Structural thesis, fundamental quality, and capital flow indicators are fully aligned — a configuration consistent with high-conviction deployment environments.`,
      `${ticker} presents an unusually coherent structural thesis. ${strength}. Full alignment across fundamental quality, institutional positioning, and directional momentum validates the long-term constructive posture.`,
      `${ticker} demonstrates exceptional analytical coherence across all evaluation dimensions. ${strength}. Signal convergence at this magnitude is uncommon and supports a high-conviction structural case.`,
    ]
    return variants[tickerVariant(ticker, variants.length)]

  } else if (score >= 6.5 || rating === 'BUY') {
    const variants = [
      `${ticker} presents a constructive structural thesis with identifiable tactical constraints. ${strength}. ${concern} introduces positioning discipline requirements without impairing the long-term directional case.`,
      `${ticker} exhibits solid fundamental quality with execution-layer friction. ${strength}. ${concern} — the structural thesis remains intact, but optimal deployment awaits improved signal convergence.`,
      `${ticker} warrants portfolio consideration under a calibrated deployment framework. ${strength}. ${concern} requires risk-adjusted entry discipline rather than immediate full deployment.`,
    ]
    return variants[tickerVariant(ticker, variants.length)]

  } else if (score >= 5.0 || rating === 'HOLD') {
    const variants = [
      `${ticker} presents a mixed analytical profile. ${strength}. ${concern}. Directional conviction is constrained pending catalyst resolution.`,
      `${ticker} exhibits cross-signal tension that prevents clear directional positioning. ${strength}. ${concern}. Capital deployment is deferred pending narrative resolution.`,
      `${ticker} is at a fundamental inflection point. ${strength}. ${concern}. The analytical framework requires catalyst input before a constructive structural posture can be established.`,
      `${ticker} reflects genuine analytical ambiguity that limits actionable conviction. ${strength}. ${concern}. Signal architecture is insufficient for high-conviction deployment under current conditions.`,
      `${ticker} demonstrates balanced risk parameters that constrain directional conviction. ${strength}. ${concern}. Tactical monitoring is appropriate over active capital deployment.`,
    ]
    return variants[tickerVariant(ticker, variants.length)]

  } else {
    const variants = [
      `${ticker} faces structural headwinds that materially impair the investment thesis. ${concern}. Risk/reward profile does not support deployment under current conditions.`,
      `${ticker} exhibits fundamental deterioration that outweighs residual positive signals. ${concern}. Capital preservation is the appropriate posture until structural improvement is evident.`,
      `${ticker} presents an impaired analytical profile with limited near-term recovery visibility. ${concern}. The structural case requires meaningful rehabilitation before deployment is warranted.`,
    ]
    return variants[tickerVariant(ticker, variants.length)]
  }
}
