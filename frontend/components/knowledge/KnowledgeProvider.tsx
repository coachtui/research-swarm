'use client'

// ─────────────────────────────────────────────────────────────────────────────
// KnowledgeProvider — global context for the interpretability engine.
// Manages: active term panel, navigation history, and panel open/close state.
// Renders the ConceptPanel inside the provider tree (portal-equivalent via
// fixed positioning) so it is available from any depth without prop drilling.
// ─────────────────────────────────────────────────────────────────────────────

import { createContext, useCallback, useContext, useState } from 'react'
import type { ReactNode } from 'react'
import { ConceptPanel } from './ConceptPanel'

interface KnowledgeContextValue {
  /** Open the panel for a given term ID. Pushes to navigation history. */
  openTerm: (termId: string) => void
  /** Close the panel and clear history. */
  closeTerm: () => void
  /** Navigate back one step in the related-concept history. */
  goBack: () => void
  /** Currently displayed term ID, or null if panel is closed. */
  activeTerm: string | null
  /** Navigation breadcrumb stack (most recent last). */
  history: string[]
}

const KnowledgeContext = createContext<KnowledgeContextValue | null>(null)

export function KnowledgeProvider({ children }: { children: ReactNode }) {
  const [history, setHistory] = useState<string[]>([])

  const activeTerm = history.length > 0 ? history[history.length - 1] : null

  const openTerm = useCallback((termId: string) => {
    setHistory(prev => {
      // Avoid duplicate consecutive entries
      if (prev[prev.length - 1] === termId) return prev
      return [...prev, termId]
    })
  }, [])

  const closeTerm = useCallback(() => {
    setHistory([])
  }, [])

  const goBack = useCallback(() => {
    setHistory(prev => prev.slice(0, -1))
  }, [])

  return (
    <KnowledgeContext.Provider value={{ openTerm, closeTerm, goBack, activeTerm, history }}>
      {children}
      {/* ConceptPanel is rendered here so it sits above all page content */}
      {activeTerm && (
        <ConceptPanel termId={activeTerm} onClose={closeTerm} onBack={goBack} history={history} />
      )}
    </KnowledgeContext.Provider>
  )
}

/** Access the knowledge engine from any child component. */
export function useKnowledge(): KnowledgeContextValue {
  const ctx = useContext(KnowledgeContext)
  if (!ctx) throw new Error('useKnowledge must be used within KnowledgeProvider')
  return ctx
}
