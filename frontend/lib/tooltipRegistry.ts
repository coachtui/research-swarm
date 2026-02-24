/**
 * DVRG Tooltip Registry
 *
 * Two responsibilities:
 *
 * 1. First-occurrence tracking — each term should show its tooltip trigger icon
 *    only on the first appearance per SPA session. The Set resets on full page
 *    reload, which matches the "per session" intent.
 *
 * 2. Level preference — users can opt into minimal mode (L1 only) via a
 *    persistent localStorage flag. Default is 'full' (L1 + L2 stacked).
 *
 * Usage in components:
 *
 *   import { isFirstOccurrence, getTooltipLevel } from '@/lib/tooltipRegistry'
 *
 *   // In a useRef-gated render check (avoids React strict-mode double-call):
 *   const checked = useRef(false)
 *   const showIcon = useRef(true)
 *   if (!checked.current) {
 *     checked.current = true
 *     showIcon.current = isFirstOccurrence('risk-environment')
 *   }
 */

/** Module-level session Set. Resets on page reload — intentional. */
const _seenTerms = new Set<string>()

/**
 * Returns true if this is the first time `termId` has been seen in the current
 * SPA session. Marks the term as seen as a side effect of the first call.
 *
 * Thread-safe for React's concurrent mode: multiple simultaneous calls with
 * different termIds are independent. Multiple calls with the same termId after
 * the first return false immediately.
 */
export function isFirstOccurrence(termId: string): boolean {
  if (_seenTerms.has(termId)) return false
  _seenTerms.add(termId)
  return true
}

/** Flush all seen state — for testing or explicit user reset. */
export function resetSeenTerms(): void {
  _seenTerms.clear()
}

// ── Level preference ──────────────────────────────────────────────────────────

export type TooltipLevel = 'full' | 'minimal'

/**
 * Returns the user's preferred tooltip depth.
 *   'full'    → show L1 micro-clarifier + L2 analytical interpretation (default)
 *   'minimal' → show L1 only — experienced users who scan quickly
 */
export function getTooltipLevel(): TooltipLevel {
  try {
    const stored = localStorage.getItem('dvrg_tooltip_level')
    return stored === 'minimal' ? 'minimal' : 'full'
  } catch {
    return 'full'
  }
}

/** Persist a level preference across sessions. */
export function setTooltipLevel(level: TooltipLevel): void {
  try {
    localStorage.setItem('dvrg_tooltip_level', level)
  } catch {
    // localStorage unavailable (SSR, private browsing restrictions)
  }
}
