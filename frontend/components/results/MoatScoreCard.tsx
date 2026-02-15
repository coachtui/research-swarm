import { Card, CardContent } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { scoreToGrade, scoreToRating, scoreToColor } from '@/lib/utils/formatting'

interface MoatScoreCardProps {
  score: number
  ticker: string
}

export function MoatScoreCard({ score, ticker }: MoatScoreCardProps) {
  const rating = scoreToRating(score)
  const grade = scoreToGrade(score)
  const colorClass = scoreToColor(score)

  // Determine badge variant
  const badgeVariant = score >= 7.0 ? 'success' : score >= 5.0 ? 'warning' : 'error'

  return (
    <Card>
      <CardContent className="pt-6">
        <div className="flex flex-col md:flex-row items-center justify-between gap-6">
          {/* Score Display */}
          <div className="text-center md:text-left space-y-2">
            <h2 className="text-sm font-medium text-text-secondary uppercase tracking-wide">
              Overall Score
            </h2>
            <div className="flex items-baseline gap-2">
              <span className={`text-6xl font-bold ${colorClass}`}>
                {score.toFixed(1)}
              </span>
              <span className="text-2xl text-text-tertiary">/10</span>
            </div>
            <div className="flex items-center gap-2">
              <Badge variant={badgeVariant}>{rating}</Badge>
              <span className="text-sm text-text-secondary">Grade: {grade}</span>
            </div>
            {/* Score band context */}
            <div className="flex items-center gap-0.5 text-xs text-text-tertiary mt-1 flex-wrap">
              {[
                { threshold: 8.5, label: '8.5+ Strong Buy', check: score >= 8.5 },
                { threshold: 7.0, label: '7.0–8.4 Buy', check: score >= 7.0 && score < 8.5 },
                { threshold: 5.0, label: '5.0–6.9 Hold', check: score >= 5.0 && score < 7.0 },
                { threshold: 3.0, label: '3.0–4.9 Sell', check: score >= 3.0 && score < 5.0 },
                { threshold: 0, label: '<3.0 Strong Sell', check: score < 3.0 },
              ].map(({ threshold, label, check }, i) => (
                <span key={threshold}>
                  {i > 0 && <span className="mx-0.5">&middot;</span>}
                  <span className={check ? 'font-semibold text-text-primary bg-primary/10 px-1 py-0.5 rounded' : ''}>
                    {label}
                  </span>
                </span>
              ))}
            </div>
          </div>

          {/* Gauge Visualization */}
          <div className="relative w-40 h-40">
            <svg className="w-full h-full transform -rotate-90" viewBox="0 0 160 160">
              {/* Background circle */}
              <circle
                cx="80"
                cy="80"
                r="70"
                fill="none"
                stroke="currentColor"
                strokeWidth="12"
                className="text-surface-elevated"
              />
              {/* Progress circle */}
              <circle
                cx="80"
                cy="80"
                r="70"
                fill="none"
                stroke="currentColor"
                strokeWidth="12"
                strokeDasharray={`${(score / 10) * 439.6} 439.6`}
                strokeLinecap="round"
                className={colorClass}
              />
            </svg>
            <div className="absolute inset-0 flex items-center justify-center">
              <div className="text-center">
                <div className={`text-3xl font-bold ${colorClass}`}>{score.toFixed(1)}</div>
                <div className="text-xs text-text-tertiary">Score</div>
              </div>
            </div>
          </div>

          {/* Ticker Info */}
          <div className="text-center md:text-right space-y-1">
            <div className="text-2xl font-bold text-text-primary">{ticker}</div>
            <div className="text-sm text-text-secondary">
              Analysis Date: {new Date().toLocaleDateString()}
            </div>
          </div>
        </div>
      </CardContent>
    </Card>
  )
}
