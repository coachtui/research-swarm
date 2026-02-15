import { Card, CardContent } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import type { FundTechDivergence } from '@/types/api'

interface DivergenceAlertProps {
  divergence: FundTechDivergence
}

export function DivergenceAlert({ divergence }: DivergenceAlertProps) {
  const isHigh = divergence.severity === 'HIGH'
  const borderColor = isHigh ? 'border-error/40' : 'border-warning/40'
  const bgColor = isHigh ? 'bg-error/5' : 'bg-warning/5'

  return (
    <Card className={`${borderColor} ${bgColor}`}>
      <CardContent className="pt-5 space-y-3">
        {/* Header */}
        <div className="flex items-center gap-2 flex-wrap">
          <Badge variant={isHigh ? 'error' : 'warning'}>
            {divergence.severity} DIVERGENCE
          </Badge>
          <span className="text-sm text-text-secondary">
            Fundamental: <strong>{divergence.fundamental_signal}</strong>
            {' vs '}
            Technical: <strong>{divergence.technical_signal}</strong>
          </span>
        </div>

        {/* Interpretation */}
        <p className="text-sm text-text-secondary leading-relaxed">
          {divergence.interpretation}
        </p>

        {/* Recommendation */}
        <div className="rounded-md bg-surface p-3 border border-surface-elevated">
          <p className="text-sm text-text-secondary">
            <span className="font-medium text-text-primary">Recommendation: </span>
            {divergence.recommendation}
          </p>
          <p className="text-xs text-text-tertiary mt-1 italic">
            {divergence.resolution_bias}
          </p>
        </div>
      </CardContent>
    </Card>
  )
}
