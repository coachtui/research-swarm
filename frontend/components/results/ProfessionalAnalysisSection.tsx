'use client'

import Link from 'next/link'
import { Card } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { FileText, Download, Eye } from 'lucide-react'

interface ProfessionalAnalysisSectionProps {
  ticker: string
  run_id: string
  onDownloadPDF: () => void
}

export function ProfessionalAnalysisSection({
  ticker,
  run_id,
  onDownloadPDF,
}: ProfessionalAnalysisSectionProps) {
  return (
    <Card className="p-8 mt-8 bg-gradient-to-br from-slate-900 to-slate-800 text-white border-slate-700">
      <div className="flex items-start gap-6">
        {/* Icon */}
        <div className="h-16 w-16 rounded-lg bg-primary/10 border border-primary/20 flex items-center justify-center flex-shrink-0">
          <FileText className="h-8 w-8 text-primary" />
        </div>

        {/* Content */}
        <div className="flex-1">
          <h3 className="text-2xl font-bold mb-2">
            Professional Analysis
          </h3>
          <p className="text-slate-300 text-sm mb-6">
            For seasoned investors and financial professionals who need institutional-quality depth
          </p>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-6">
            {/* What's on this page */}
            <div className="p-4 rounded-lg bg-slate-800/50 border border-slate-700">
              <h4 className="font-semibold text-sm mb-3 text-slate-400">
                This Page (Quick Overview)
              </h4>
              <ul className="space-y-2 text-xs text-slate-300">
                <li className="flex items-center gap-2">
                  <span className="text-green-400">✓</span>
                  Conversational summary & verdict
                </li>
                <li className="flex items-center gap-2">
                  <span className="text-green-400">✓</span>
                  Signal divergence analysis
                </li>
                <li className="flex items-center gap-2">
                  <span className="text-green-400">✓</span>
                  Simplified key points
                </li>
                <li className="flex items-center gap-2">
                  <span className="text-green-400">✓</span>
                  Quick action checklist
                </li>
              </ul>
              <p className="mt-3 text-xs text-slate-400 italic">
                Best for: Quick decisions, mobile viewing, learning
              </p>
            </div>

            {/* What's in professional version */}
            <div className="p-4 rounded-lg bg-primary/10 border-2 border-primary/30">
              <h4 className="font-semibold text-sm mb-3 text-primary">
                Professional Report (Institutional Depth)
              </h4>
              <ul className="space-y-2 text-xs text-white">
                <li className="flex items-center gap-2">
                  <span className="text-primary">+</span>
                  <strong>DCF valuation model</strong> with assumptions
                </li>
                <li className="flex items-center gap-2">
                  <span className="text-primary">+</span>
                  <strong>Bull/Base/Bear price targets</strong> (probabilities)
                </li>
                <li className="flex items-center gap-2">
                  <span className="text-primary">+</span>
                  <strong>Peer comparison analysis</strong> (8-10 metrics)
                </li>
                <li className="flex items-center gap-2">
                  <span className="text-primary">+</span>
                  <strong>Comprehensive risk factors</strong> (6 categories)
                </li>
                <li className="flex items-center gap-2">
                  <span className="text-primary">+</span>
                  <strong>Detailed trade playbook</strong> (entry/exit/sizing)
                </li>
                <li className="flex items-center gap-2">
                  <span className="text-primary">+</span>
                  <strong>Professional tone & formatting</strong>
                </li>
              </ul>
              <p className="mt-3 text-xs text-primary/80 italic">
                Best for: Due diligence, team sharing, advisors
              </p>
            </div>
          </div>

          {/* Buttons */}
          <div className="flex gap-3">
            <Link href={`/results/${run_id}/professional`} className="flex-1">
              <Button
                size="lg"
                className="w-full"
              >
                <Eye className="mr-2 h-4 w-4" />
                View Professional Analysis
              </Button>
            </Link>

            <Button
              size="lg"
              variant="outline"
              className="border-primary/30 hover:bg-primary/10"
              onClick={onDownloadPDF}
            >
              <Download className="mr-2 h-4 w-4" />
              Download PDF
            </Button>
          </div>

          <p className="text-xs text-slate-400 mt-4">
            💼 The professional version uses formal language, detailed tables, and comprehensive methodology—designed for investment professionals and advisors.
          </p>
        </div>
      </div>
    </Card>
  )
}
