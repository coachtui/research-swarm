'use client'

import { useAnalysis } from '@/lib/hooks/useAnalysis'
import { LoadingSpinner } from '@/components/shared/LoadingSpinner'
import { Card, CardContent } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import Link from 'next/link'
import { ArrowLeft, Download, Printer } from 'lucide-react'
import { ProfessionalExecutiveSummary } from '@/components/professional/ProfessionalExecutiveSummary'
import { ProfessionalValuation } from '@/components/professional/ProfessionalValuation'
import { ProfessionalPeerComparison } from '@/components/professional/ProfessionalPeerComparison'
import { ProfessionalRiskFactors } from '@/components/professional/ProfessionalRiskFactors'
import { ProfessionalTradeSetup } from '@/components/professional/ProfessionalTradeSetup'

interface ProfessionalAnalysisPageProps {
  params: { run_id: string }
}

export default function ProfessionalAnalysisPage({ params }: ProfessionalAnalysisPageProps) {
  const { run_id } = params
  const { data: run, isLoading, error } = useAnalysis(run_id)

  // Error state
  if (error) {
    return (
      <div className="container mx-auto px-4 py-12">
        <Card className="max-w-2xl mx-auto">
          <CardContent className="pt-6">
            <div className="text-center space-y-4">
              <h2 className="text-xl font-semibold">Analysis Not Available</h2>
              <p className="text-text-secondary">
                {error instanceof Error ? error.message : 'Unable to load analysis.'}
              </p>
              <Link href="/analyze">
                <Button>Return to Analyze</Button>
              </Link>
            </div>
          </CardContent>
        </Card>
      </div>
    )
  }

  // Loading state
  if (isLoading || !run || run.status !== 'completed') {
    return (
      <div className="container mx-auto px-4 py-12">
        <LoadingSpinner estimatedMinutes={4} currentStep="Loading analysis..." />
      </div>
    )
  }

  const result = run.results?.[0]
  if (!result || !result.full_output) {
    return (
      <div className="container mx-auto px-4 py-12">
        <Card className="max-w-2xl mx-auto">
          <CardContent className="pt-6">
            <div className="text-center space-y-4">
              <h2 className="text-xl font-semibold">No Results Available</h2>
              <Link href="/analyze">
                <Button>Return to Analyze</Button>
              </Link>
            </div>
          </CardContent>
        </Card>
      </div>
    )
  }

  const { full_output, moat_score } = result

  const handlePrint = () => {
    window.print()
  }

  const handleDownloadHTML = () => {
    // Create a blob with the HTML content
    const element = document.getElementById('professional-report')
    if (!element) return

    const htmlContent = `
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Professional Analysis - ${result.ticker}</title>
  <style>
    body { font-family: Georgia, serif; max-width: 8.5in; margin: 0 auto; padding: 1in; }
    h1 { font-size: 24pt; margin-bottom: 0.5em; }
    h2 { font-size: 18pt; margin-top: 1.5em; margin-bottom: 0.5em; border-bottom: 2px solid #333; }
    h3 { font-size: 14pt; margin-top: 1em; }
    p { line-height: 1.6; margin-bottom: 1em; }
    table { width: 100%; border-collapse: collapse; margin: 1em 0; }
    th, td { padding: 8px; border: 1px solid #ccc; text-align: left; }
    th { background-color: #f5f5f5; font-weight: bold; }
    .section { margin-bottom: 2em; }
  </style>
</head>
<body>
  ${element.innerHTML}
</body>
</html>
    `

    const blob = new Blob([htmlContent], { type: 'text/html' })
    const url = window.URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `professional-analysis-${result.ticker}-${run_id.slice(0, 8)}.html`
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
    window.URL.revokeObjectURL(url)
  }

  return (
    <div className="min-h-screen bg-background">
      {/* Action Bar - Hidden on print */}
      <div className="sticky top-0 z-50 bg-background/95 backdrop-blur border-b print:hidden">
        <div className="container mx-auto px-4 py-3">
          <div className="flex items-center justify-between">
            <Link href={`/results/${run_id}`}>
              <Button variant="ghost" size="sm">
                <ArrowLeft className="h-4 w-4 mr-2" />
                Back to Summary
              </Button>
            </Link>
            <div className="flex items-center gap-2">
              <Button variant="outline" size="sm" onClick={handlePrint}>
                <Printer className="h-4 w-4 mr-2" />
                Print
              </Button>
              <Button variant="outline" size="sm" onClick={handleDownloadHTML}>
                <Download className="h-4 w-4 mr-2" />
                Download HTML
              </Button>
            </div>
          </div>
        </div>
      </div>

      {/* Professional Report Content */}
      <div id="professional-report" className="container mx-auto px-4 py-8 max-w-5xl">
        <div className="bg-white dark:bg-surface-elevated rounded-lg shadow-lg p-12 space-y-8">

          {/* Header */}
          <header className="border-b-2 border-border pb-6">
            <h1 className="text-4xl font-serif font-bold text-text-primary mb-2">
              Professional Investment Analysis
            </h1>
            <div className="flex items-center justify-between text-sm text-text-secondary">
              <div>
                <p className="text-2xl font-semibold text-text-primary">{result.ticker}</p>
                <p>Analysis Date: {new Date(run.completed_at || run.created_at).toLocaleDateString('en-US', {
                  year: 'numeric',
                  month: 'long',
                  day: 'numeric'
                })}</p>
              </div>
              {full_output.decision_intelligence?.rating && (
                <div className="text-right">
                  <p className="text-xs uppercase tracking-wide text-text-tertiary">Investment Rating</p>
                  <p className="text-2xl font-bold text-text-primary">
                    {full_output.decision_intelligence.rating}
                  </p>
                </div>
              )}
            </div>
          </header>

          {/* Professional Analysis Components */}
          <ProfessionalExecutiveSummary
            ticker={result.ticker}
            full_output={full_output}
            decision_intelligence={full_output.decision_intelligence}
            moat_score={moat_score}
          />

          <ProfessionalValuation
            ticker={result.ticker}
            full_output={full_output}
            decision_intelligence={full_output.decision_intelligence}
          />

          <ProfessionalPeerComparison
            ticker={result.ticker}
            full_output={full_output}
          />

          <ProfessionalRiskFactors
            full_output={full_output}
          />

          <ProfessionalTradeSetup
            ticker={result.ticker}
            decision_intelligence={full_output.decision_intelligence}
          />

          {/* Disclaimer */}
          <footer className="border-t-2 border-border pt-6 mt-12">
            <p className="text-xs text-text-tertiary leading-relaxed">
              <strong>Disclaimer:</strong> This analysis is provided for informational purposes only
              and does not constitute investment advice, financial advice, trading advice, or any
              other sort of advice. The information contained herein is based on sources believed
              to be reliable but is not guaranteed as to accuracy or completeness. Past performance
              is not indicative of future results. You should not make any investment decision
              based solely on this analysis. Please consult with a qualified financial advisor
              before making any investment decisions.
            </p>
          </footer>
        </div>
      </div>
    </div>
  )
}
