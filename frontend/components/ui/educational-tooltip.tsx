'use client'

import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from '@/components/ui/tooltip'

interface EducationalTooltipProps {
  term: string
  definition: string
  example?: string
  children: React.ReactNode
}

export function EducationalTooltip({
  term,
  definition,
  example,
  children
}: EducationalTooltipProps) {
  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <span className="underline decoration-dotted decoration-primary/50 cursor-help hover:decoration-solid transition-all">
          {children}
        </span>
      </TooltipTrigger>
      <TooltipContent
        className="max-w-xs p-4 bg-slate-900 text-white border-primary/20"
        side="top"
      >
        <div className="space-y-2">
          <p className="font-semibold text-sm text-primary">{term}</p>
          <p className="text-xs leading-relaxed">{definition}</p>
          {example && (
            <div className="pt-2 border-t border-white/10">
              <p className="text-xs text-slate-300">
                <strong>Example:</strong> {example}
              </p>
            </div>
          )}
        </div>
      </TooltipContent>
    </Tooltip>
  )
}
