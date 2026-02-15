'use client'

import { Card, CardContent } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'

interface DataDebuggerProps {
  data: any
  label?: string
}

export function DataDebugger({ data, label = "Signal Breakdown Data" }: DataDebuggerProps) {
  // Check what signal-related data exists
  const signalBreakdown = data?.signal_breakdown || data?.full_output?.signal_breakdown
  const newsHoundOutput = data?.news_hound_output || data?.full_output?.news_hound_output

  return (
    <div className="my-4 p-4 bg-yellow-100 dark:bg-yellow-900/20 border-2 border-yellow-500 rounded">
      <h3 className="font-bold mb-3 flex items-center gap-2">
        <span>🐛</span>
        DEBUG: {label}
      </h3>

      <div className="space-y-3 text-sm">
        {/* Signal Breakdown Status */}
        <div className="space-y-1">
          <div className="font-semibold">Signal Breakdown:</div>
          <div className="ml-4 space-y-1">
            <div className="flex items-center gap-2">
              <Badge variant={signalBreakdown ? "success" : "error"}>
                {signalBreakdown ? '✓ EXISTS' : '✗ MISSING'}
              </Badge>
            </div>
            {signalBreakdown && (
              <div className="text-xs space-y-0.5 ml-2">
                <div>News Score: <span className="font-mono">{signalBreakdown.news_score}</span></div>
                <div>Earnings Score: <span className="font-mono">{signalBreakdown.earnings_score}</span></div>
                <div>Analyst Score: <span className="font-mono">{signalBreakdown.analyst_score}</span></div>
                <div>Institutional Score: <span className="font-mono">{signalBreakdown.institutional_score}</span></div>
                <div>Insider Score: <span className="font-mono">{signalBreakdown.insider_score}</span></div>
                <div className="mt-1 pt-1 border-t border-yellow-400/30">
                  <strong>Has Divergence:</strong> {signalBreakdown.has_divergence ? 'YES' : 'NO'}
                </div>
                <div>
                  <strong>Status:</strong> {signalBreakdown.alignment_status}
                </div>
              </div>
            )}
          </div>
        </div>

        {/* News Hound Output Status */}
        <div className="space-y-1 pt-2 border-t border-yellow-400/30">
          <div className="font-semibold">News Hound Output:</div>
          <div className="ml-4">
            <Badge variant={newsHoundOutput ? "success" : "error"}>
              {newsHoundOutput ? '✓ EXISTS' : '✗ MISSING'}
            </Badge>
            {newsHoundOutput && (
              <div className="text-xs space-y-0.5 ml-2 mt-1">
                <div>
                  sentiment_score: {newsHoundOutput.sentiment_score ?
                    <span className="font-mono text-green-600">{newsHoundOutput.sentiment_score}</span> :
                    <span className="text-red-600">missing</span>
                  }
                </div>
                <div>
                  earnings_estimates: {newsHoundOutput.earnings_estimates ?
                    <span className="text-green-600">✓ present</span> :
                    <span className="text-red-600">✗ missing</span>
                  }
                </div>
                <div>
                  analyst_consensus: {newsHoundOutput.analyst_consensus ?
                    <span className="text-green-600">✓ present</span> :
                    <span className="text-red-600">✗ missing</span>
                  }
                </div>
                <div>
                  institutional_activity: {newsHoundOutput.institutional_activity ?
                    <span className="text-green-600">✓ present</span> :
                    <span className="text-red-600">✗ missing</span>
                  }
                </div>
                <div>
                  insider_activity: {newsHoundOutput.insider_activity ?
                    <span className="text-green-600">✓ present</span> :
                    <span className="text-red-600">✗ missing</span>
                  }
                </div>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Full Data View */}
      <details className="mt-4">
        <summary className="cursor-pointer font-semibold hover:text-yellow-700 dark:hover:text-yellow-300">
          View Full Data Structure (Click to expand)
        </summary>
        <pre className="mt-2 p-2 bg-black text-green-400 rounded overflow-auto text-xs max-h-96">
          {JSON.stringify({
            signal_breakdown: signalBreakdown,
            news_hound_output: newsHoundOutput ? {
              sentiment_score: newsHoundOutput.sentiment_score,
              earnings_estimates: newsHoundOutput.earnings_estimates,
              analyst_consensus: newsHoundOutput.analyst_consensus,
              institutional_activity: newsHoundOutput.institutional_activity,
              insider_activity: newsHoundOutput.insider_activity,
            } : null,
          }, null, 2)}
        </pre>
      </details>
    </div>
  )
}
