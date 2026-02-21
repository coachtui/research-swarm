'use client'

// ─────────────────────────────────────────────────────────────────────────────
// TermTooltip — annotated term wrapper. Two-stage disclosure:
//   Stage 1: Hover → Radix tooltip showing quick one-sentence definition
//   Stage 2: Click → ConceptPanel slides in with full structured content
//
// Usage:
//   <TermTooltip termId="signal_divergence">Signal Divergence</TermTooltip>
//   <TermTooltip termId="conviction_score" as="span">Conviction</TermTooltip>
// ─────────────────────────────────────────────────────────────────────────────

import type { ReactNode, ElementType } from 'react'
import { getTerm } from '@/lib/knowledge-index'
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from '@/components/ui/tooltip'
import { useKnowledge } from './KnowledgeProvider'

interface TermTooltipProps {
  /** Term ID from the knowledge index. */
  termId: string
  children: ReactNode
  /** Rendered element type. Defaults to 'span'. */
  as?: ElementType
  /** Additional class names on the trigger element. */
  className?: string
}

export function TermTooltip({
  termId,
  children,
  as: Tag = 'span',
  className = '',
}: TermTooltipProps) {
  const term = getTerm(termId)
  const { openTerm } = useKnowledge()

  // If the term isn't in the index, render children undecorated.
  if (!term) return <>{children}</>

  return (
    <Tooltip>
      <TooltipTrigger asChild>
        {/*
         * The trigger is a semantically neutral inline element.
         * Dotted underline is the institutional convention for annotated terms.
         * cursor-help on hover, cursor-pointer signals click-to-expand.
         */}
        <Tag
          className={[
            'border-b border-dotted border-gray-500 cursor-help',
            'hover:border-gray-300 hover:text-gray-100 transition-colors duration-150',
            className,
          ].join(' ')}
          onClick={(e: React.MouseEvent) => {
            e.stopPropagation()
            openTerm(termId)
          }}
          role="button"
          tabIndex={0}
          onKeyDown={(e: React.KeyboardEvent) => {
            if (e.key === 'Enter' || e.key === ' ') {
              e.preventDefault()
              openTerm(termId)
            }
          }}
          aria-label={`Open explanation: ${term.name}`}
        >
          {children}
        </Tag>
      </TooltipTrigger>

      {/* Stage 1: Hover layer — quick definition only */}
      <TooltipContent
        side="top"
        sideOffset={6}
        className="max-w-[280px] bg-gray-900 border border-gray-700 shadow-xl px-3 py-2.5"
      >
        <p className="text-[10px] font-mono tracking-widest uppercase text-gray-500 mb-1">
          {term.name}
        </p>
        <p className="text-xs text-gray-200 leading-relaxed font-mono">
          {term.quickDefinition}
        </p>
        <p className="text-[10px] text-gray-500 mt-1.5 font-mono">
          Click to expand →
        </p>
      </TooltipContent>
    </Tooltip>
  )
}
