'use client'

// ─────────────────────────────────────────────────────────────────────────────
// OnboardingPanel — bottom collapsible panel teaching five analytical framework
// constructs. Teaches interpretation, not navigation.
//
// Behavior:
//   - First visit: auto-expands, persists state in localStorage
//   - Subsequent visits: collapsed to tab handle, re-expandable via button
//   - Completing all 5 constructs: shows confirmation, then collapses to handle
//   - "Skip" dismisses permanently
//   - Contextual trigger: parent can call openConstruct(id) to deep-link to a
//     specific construct based on analytical conditions in the results data
// ─────────────────────────────────────────────────────────────────────────────

import { useState, useEffect, useCallback, createContext, useContext } from 'react'
import type { ReactNode } from 'react'
import { ChevronUp, ChevronDown, X, ChevronLeft, ChevronRight } from 'lucide-react'
import { ONBOARDING_CONSTRUCTS, ONBOARDING_STORAGE_KEY, ONBOARDING_STEP_KEY } from '@/lib/onboarding-constructs'
import type { OnboardingConstruct } from '@/lib/onboarding-constructs'
import { TermTooltip } from './TermTooltip'

// ── Onboarding Context (for contextual triggering from other components) ─────

interface OnboardingContextValue {
  openConstruct: (constructId: string) => void
  isOpen: boolean
}

const OnboardingContext = createContext<OnboardingContextValue | null>(null)

export function useOnboarding() {
  return useContext(OnboardingContext)
}

// ── Main Component ────────────────────────────────────────────────────────────

interface OnboardingPanelProps {
  children?: ReactNode
}

export function OnboardingPanel({ children }: OnboardingPanelProps) {
  const [isOpen, setIsOpen] = useState(false)
  const [stepIndex, setStepIndex] = useState(0)
  const [isDismissed, setIsDismissed] = useState(false)
  const [isComplete, setIsComplete] = useState(false)
  const [mounted, setMounted] = useState(false)

  // Hydrate from localStorage after mount (prevents SSR mismatch)
  useEffect(() => {
    setMounted(true)
    const dismissed = localStorage.getItem(ONBOARDING_STORAGE_KEY) === 'true'
    const savedStep = parseInt(localStorage.getItem(ONBOARDING_STEP_KEY) ?? '0', 10)
    setIsDismissed(dismissed)
    setStepIndex(savedStep)
    // Auto-expand on first visit
    if (!dismissed) setIsOpen(true)
  }, [])

  const saveStep = useCallback((step: number) => {
    setStepIndex(step)
    localStorage.setItem(ONBOARDING_STEP_KEY, String(step))
  }, [])

  const handleNext = () => {
    const next = stepIndex + 1
    if (next >= ONBOARDING_CONSTRUCTS.length) {
      setIsComplete(true)
      setTimeout(() => {
        setIsOpen(false)
        setIsComplete(false)
      }, 2000)
    } else {
      saveStep(next)
    }
  }

  const handlePrev = () => {
    if (stepIndex > 0) saveStep(stepIndex - 1)
  }

  const handleDismiss = () => {
    localStorage.setItem(ONBOARDING_STORAGE_KEY, 'true')
    setIsDismissed(true)
    setIsOpen(false)
  }

  const openConstruct = useCallback((constructId: string) => {
    const idx = ONBOARDING_CONSTRUCTS.findIndex(c => c.id === constructId)
    if (idx !== -1) {
      saveStep(idx)
      setIsOpen(true)
    }
  }, [saveStep])

  const currentConstruct = ONBOARDING_CONSTRUCTS[stepIndex]

  // Don't render until hydrated (avoid flash)
  if (!mounted) return <>{children}</>

  return (
    <OnboardingContext.Provider value={{ openConstruct, isOpen }}>
      {children}

      {/* ── Tab Handle (always visible after first visit) ── */}
      {!isOpen && (
        <button
          onClick={() => setIsOpen(true)}
          className="fixed bottom-0 right-6 z-30 flex items-center gap-1.5 px-3 py-1.5 bg-gray-900 border border-gray-700 border-b-0 rounded-t-md text-xs font-mono text-gray-400 hover:text-gray-200 hover:bg-gray-800 transition-colors shadow-lg"
          aria-label="Open Framework Guide"
        >
          <span className="text-[10px] tracking-widest uppercase">Framework Guide</span>
          <ChevronUp size={12} />
        </button>
      )}

      {/* ── Bottom Panel ── */}
      {isOpen && currentConstruct && (
        <div
          className="fixed bottom-0 inset-x-0 z-30 border-t border-gray-800 bg-gray-950 shadow-2xl"
          role="complementary"
          aria-label="Framework Guide"
        >
          {isComplete ? (
            <CompletionMessage onDone={() => setIsOpen(false)} />
          ) : (
            <ConstructView
              construct={currentConstruct}
              stepIndex={stepIndex}
              total={ONBOARDING_CONSTRUCTS.length}
              onNext={handleNext}
              onPrev={handlePrev}
              onDismiss={handleDismiss}
              onCollapse={() => setIsOpen(false)}
            />
          )}
        </div>
      )}
    </OnboardingContext.Provider>
  )
}

// ── Construct View ────────────────────────────────────────────────────────────

interface ConstructViewProps {
  construct: OnboardingConstruct
  stepIndex: number
  total: number
  onNext: () => void
  onPrev: () => void
  onDismiss: () => void
  onCollapse: () => void
}

function ConstructView({
  construct,
  stepIndex,
  total,
  onNext,
  onPrev,
  onDismiss,
  onCollapse,
}: ConstructViewProps) {
  return (
    <div className="max-w-5xl mx-auto px-4 pt-3 pb-4">
      {/* Header row */}
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <span className="text-[10px] font-mono tracking-widest uppercase text-gray-500">
            Framework Guide
          </span>
          {/* Progress dots */}
          <div className="flex items-center gap-1 ml-1">
            {Array.from({ length: total }).map((_, i) => (
              <div
                key={i}
                className={`w-1.5 h-1.5 rounded-full transition-colors ${
                  i === stepIndex ? 'bg-blue-500' : 'bg-gray-700'
                }`}
              />
            ))}
          </div>
          <span className="text-[10px] font-mono text-gray-600">{stepIndex + 1} of {total}</span>
        </div>

        <div className="flex items-center gap-1">
          <button
            onClick={onCollapse}
            className="p-1 text-gray-500 hover:text-gray-300 transition-colors"
            aria-label="Collapse"
          >
            <ChevronDown size={14} />
          </button>
          <button
            onClick={onDismiss}
            className="p-1 text-gray-500 hover:text-gray-300 transition-colors"
            aria-label="Dismiss permanently"
          >
            <X size={14} />
          </button>
        </div>
      </div>

      {/* Main construct content */}
      <div className="grid grid-cols-[1fr_auto_1fr_2fr] gap-4 items-start">

        {/* Left concept */}
        <div className="space-y-1">
          <p className="text-[10px] font-mono tracking-widest uppercase text-gray-500">
            {construct.title.split(' vs. ')[0]}
          </p>
          <p className="text-sm font-semibold text-white">{construct.left.label}</p>
          <ul className="space-y-0.5">
            {construct.left.descriptors.map(d => (
              <li key={d} className="text-xs text-gray-400 font-mono">{d}</li>
            ))}
          </ul>
        </div>

        {/* VS divider */}
        <div className="flex flex-col items-center justify-center pt-4 gap-1">
          <div className="w-px h-8 bg-gray-700" />
          <span className="text-xs font-mono text-gray-600">vs</span>
          <div className="w-px h-8 bg-gray-700" />
        </div>

        {/* Right concept */}
        <div className="space-y-1">
          <p className="text-[10px] font-mono tracking-widest uppercase text-gray-500">
            {construct.title.split(' vs. ')[1]}
          </p>
          <p className="text-sm font-semibold text-white">{construct.right.label}</p>
          <ul className="space-y-0.5">
            {construct.right.descriptors.map(d => (
              <li key={d} className="text-xs text-gray-400 font-mono">{d}</li>
            ))}
          </ul>
        </div>

        {/* Bridge statement + related terms */}
        <div className="space-y-2 pl-4 border-l border-gray-800">
          <p className="text-xs text-gray-300 leading-relaxed italic">
            &ldquo;{construct.bridgeStatement}&rdquo;
          </p>
          <p className="text-xs text-gray-500 leading-relaxed">
            {construct.whyItMatters}
          </p>

          {/* Related term chips */}
          {construct.relatedTermIds.length > 0 && (
            <div className="flex flex-wrap gap-1.5 pt-1">
              <span className="text-[10px] font-mono text-gray-600 uppercase tracking-wider self-center">
                In this analysis:
              </span>
              {construct.relatedTermIds.map(id => (
                <TermTooltip key={id} termId={id}>
                  <span className="px-2 py-0.5 text-[10px] font-mono text-gray-300 bg-gray-800 border border-gray-700 rounded hover:border-gray-500 cursor-pointer transition-colors">
                    {id.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase())}
                  </span>
                </TermTooltip>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Navigation row */}
      <div className="flex items-center justify-between mt-3 pt-3 border-t border-gray-800">
        <button
          onClick={onPrev}
          disabled={stepIndex === 0}
          className="flex items-center gap-1 text-xs font-mono text-gray-500 hover:text-gray-300 disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
        >
          <ChevronLeft size={13} /> Prev
        </button>

        <button
          onClick={onDismiss}
          className="text-[10px] font-mono text-gray-600 hover:text-gray-400 transition-colors"
        >
          Skip Framework Guide
        </button>

        <button
          onClick={onNext}
          className="flex items-center gap-1 text-xs font-mono text-blue-400 hover:text-blue-300 transition-colors"
        >
          {stepIndex === ONBOARDING_CONSTRUCTS.length - 1 ? 'Complete' : 'Next'}
          <ChevronRight size={13} />
        </button>
      </div>
    </div>
  )
}

// ── Completion Message ────────────────────────────────────────────────────────

function CompletionMessage({ onDone }: { onDone: () => void }) {
  return (
    <div className="flex items-center justify-center gap-3 py-4 px-4">
      <span className="text-xs font-mono text-gray-400">Framework guide complete.</span>
      <span className="text-xs font-mono text-gray-500">
        Access anytime via the tab handle below.
      </span>
    </div>
  )
}
