import { Card, CardContent } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import type { SignalBreakdown, FundTechDivergence } from '@/types/api'

interface SignalDivergenceHeroProps {
  signalBreakdown: SignalBreakdown
  fundTechDivergence?: FundTechDivergence | null
}

export function SignalDivergenceHero({ signalBreakdown, fundTechDivergence }: SignalDivergenceHeroProps) {
  const hasDivergence = signalBreakdown.has_divergence

  if (hasDivergence) {
    const severity = fundTechDivergence?.severity || 'MODERATE'
    const isHigh = severity === 'HIGH'

    return (
      <Card className={`border-2 ${isHigh ? 'border-error/40 bg-error/5' : 'border-warning/40 bg-warning/5'}`}>
        <CardContent className="pt-6 space-y-3">
          <div className="flex items-center gap-3">
            <Badge variant={isHigh ? 'error' : 'warning'}>
              {severity} DIVERGENCE
            </Badge>
            <span className="text-sm font-medium text-text-secondary">
              {signalBreakdown.alignment_status}
            </span>
          </div>

          <p className="text-base font-semibold text-text-primary leading-relaxed">
            {signalBreakdown.divergence_explanation}
          </p>

          <p className="text-sm text-text-secondary">
            <span className="font-medium">Recommendation:</span>{' '}
            {signalBreakdown.divergence_recommendation}
          </p>

          {fundTechDivergence?.resolution_bias && (
            <p className="text-xs text-text-tertiary italic">
              Resolution bias: {fundTechDivergence.resolution_bias}
            </p>
          )}
        </CardContent>
      </Card>
    )
  }

  // All clear state
  return (
    <Card className="border-success/30 bg-success/5">
      <CardContent className="pt-6 space-y-3">
        <div className="flex items-start gap-3">
          <Badge variant="success" className="mt-0.5">ALL CLEAR</Badge>
          <div className="flex-1 space-y-2">
            <p className="text-base font-semibold text-text-primary leading-relaxed">
              No Signal Divergence Detected
            </p>
            <p className="text-sm text-text-secondary">
              All sentiment signals (news, analyst ratings, earnings revisions, institutional activity,
              and insider activity) are aligned in the same direction. {signalBreakdown.direction_consensus.charAt(0).toUpperCase() +
              signalBreakdown.direction_consensus.slice(1)}.
            </p>
            <p className="text-xs text-text-tertiary italic">
              Status: {signalBreakdown.alignment_status}
            </p>
          </div>
        </div>
      </CardContent>
    </Card>
  )
}
