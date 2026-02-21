'use client'

// ─────────────────────────────────────────────────────────────────────────────
// ConceptPanel — right-side slide panel for deep-concept exploration.
// Displays structured Knowledge Index content for the active term.
// Supports breadcrumb navigation via related concept chips.
// ─────────────────────────────────────────────────────────────────────────────

import { useEffect } from 'react'
import { X, ChevronLeft } from 'lucide-react'
import { getTerm, CATEGORY_LABELS } from '@/lib/knowledge-index'
import { DIAGRAM_REGISTRY } from './diagrams'
import { useKnowledge } from './KnowledgeProvider'

interface ConceptPanelProps {
  termId: string
  onClose: () => void
  onBack: () => void
  history: string[]
}

export function ConceptPanel({ termId, onClose, onBack, history }: ConceptPanelProps) {
  const term = getTerm(termId)
  const { openTerm } = useKnowledge()

  // Close on Escape key
  useEffect(() => {
    const handler = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose() }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [onClose])

  if (!term) return null

  const DiagramComponent = DIAGRAM_REGISTRY[termId] ?? null
  const canGoBack = history.length > 1

  // Breadcrumb — show up to last 3 items
  const breadcrumb = history.slice(-3)
  const isTruncated = history.length > 3

  return (
    <>
      {/* Scrim */}
      <div
        className="fixed inset-0 z-40 bg-black/30 backdrop-blur-[1px]"
        onClick={onClose}
        aria-hidden="true"
      />

      {/* Panel */}
      <aside
        className="fixed inset-y-0 right-0 z-50 flex w-[380px] flex-col bg-gray-950 border-l border-gray-800 shadow-2xl"
        role="complementary"
        aria-label={`Knowledge: ${term.name}`}
      >
        {/* Header */}
        <div className="flex items-start justify-between gap-3 px-5 pt-5 pb-4 border-b border-gray-800 shrink-0">
          <div className="flex-1 min-w-0">
            {/* Breadcrumb navigation */}
            {(canGoBack || isTruncated) && (
              <div className="flex items-center gap-1 mb-2 text-xs font-mono text-gray-500 flex-wrap">
                {isTruncated && <span className="text-gray-600">…</span>}
                {breadcrumb.slice(0, -1).map((id, i) => {
                  const t = getTerm(id)
                  return (
                    <span key={id} className="flex items-center gap-1">
                      <button
                        onClick={() => openTerm(id)}
                        className="hover:text-gray-300 transition-colors truncate max-w-[100px]"
                      >
                        {t?.name ?? id}
                      </button>
                      {i < breadcrumb.length - 2 && <span className="text-gray-700">›</span>}
                    </span>
                  )
                })}
                {canGoBack && <span className="text-gray-700">›</span>}
              </div>
            )}

            {/* Category tag */}
            <span className="text-[10px] font-mono tracking-widest uppercase text-gray-500 mb-1 block">
              {CATEGORY_LABELS[term.category]}
            </span>

            {/* Term name */}
            <h2 className="text-base font-semibold text-white leading-tight">
              {term.name}
            </h2>
          </div>

          {/* Controls */}
          <div className="flex items-center gap-1 shrink-0 mt-0.5">
            {canGoBack && (
              <button
                onClick={onBack}
                className="p-1.5 text-gray-400 hover:text-white hover:bg-gray-800 rounded transition-colors"
                aria-label="Back"
              >
                <ChevronLeft size={16} />
              </button>
            )}
            <button
              onClick={onClose}
              className="p-1.5 text-gray-400 hover:text-white hover:bg-gray-800 rounded transition-colors"
              aria-label="Close"
            >
              <X size={16} />
            </button>
          </div>
        </div>

        {/* Scrollable content */}
        <div className="flex-1 overflow-y-auto">
          <div className="px-5 py-4 space-y-5">

            {/* Quick read */}
            <section>
              <SectionLabel>Quick Read</SectionLabel>
              <p className="text-sm text-gray-200 leading-relaxed font-mono">
                {term.quickDefinition}
              </p>
            </section>

            <Divider />

            {/* Analytical definition */}
            <section>
              <SectionLabel>Analytical Definition</SectionLabel>
              <p className="text-sm text-gray-300 leading-relaxed">
                {term.analyticalDefinition}
              </p>
            </section>

            <Divider />

            {/* Conceptual intuition */}
            <section>
              <SectionLabel>Conceptual Intuition</SectionLabel>
              <p className="text-sm text-gray-300 leading-relaxed">
                {term.conceptualIntuition}
              </p>
            </section>

            <Divider />

            {/* Practical interpretation */}
            <section>
              <SectionLabel>Practical Interpretation</SectionLabel>
              <p className="text-sm text-gray-300 leading-relaxed">
                {term.practicalInterpretation}
              </p>
            </section>

            {/* Micro-diagram */}
            {DiagramComponent && (
              <>
                <Divider />
                <section>
                  <SectionLabel>Conceptual Model</SectionLabel>
                  <div className="mt-2 rounded-md bg-gray-900 p-3 border border-gray-800">
                    <DiagramComponent />
                  </div>
                </section>
              </>
            )}

            <Divider />

            {/* Common misinterpretations */}
            <section>
              <SectionLabel>Common Misinterpretations</SectionLabel>
              <ul className="space-y-2.5">
                {term.commonMisinterpretations.map((m, i) => (
                  <li key={i} className="flex gap-2.5">
                    <span className="text-red-400 text-xs mt-0.5 shrink-0 font-mono">✕</span>
                    <p className="text-sm text-gray-400 leading-relaxed">{m}</p>
                  </li>
                ))}
              </ul>
            </section>

            {/* Related concepts */}
            {term.relatedTermIds.length > 0 && (
              <>
                <Divider />
                <section>
                  <SectionLabel>Related Concepts</SectionLabel>
                  <div className="flex flex-wrap gap-2 mt-1">
                    {term.relatedTermIds.map(id => {
                      const related = getTerm(id)
                      if (!related) return null
                      return (
                        <button
                          key={id}
                          onClick={() => openTerm(id)}
                          className="px-2.5 py-1 text-xs font-mono text-gray-300 bg-gray-800 hover:bg-gray-700 hover:text-white border border-gray-700 hover:border-gray-500 rounded transition-all"
                        >
                          {related.name}
                        </button>
                      )
                    })}
                  </div>
                </section>
              </>
            )}

          </div>

          {/* Bottom padding so last item clears the viewport */}
          <div className="h-8" />
        </div>
      </aside>
    </>
  )
}

// ── Internal sub-components ───────────────────────────────────────────────────

function SectionLabel({ children }: { children: React.ReactNode }) {
  return (
    <p className="text-[10px] font-mono tracking-widest uppercase text-gray-500 mb-1.5">
      {children}
    </p>
  )
}

function Divider() {
  return <hr className="border-gray-800" />
}
