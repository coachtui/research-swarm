import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'

interface InvestmentThesisProps {
  thesis: string
  ticker: string
}

export function InvestmentThesis({ thesis, ticker }: InvestmentThesisProps) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Investment Thesis</CardTitle>
      </CardHeader>
      <CardContent>
        <p className="text-text-secondary leading-relaxed whitespace-pre-wrap">
          {thesis}
        </p>
      </CardContent>
    </Card>
  )
}
