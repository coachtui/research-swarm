'use client'

// Report audience mode toggle — Investor | Advisor | Allocator
// Controls section visibility and default open states in ResultsContent.
// No backend changes — pure presentation layer.

export type ReportMode = 'investor' | 'advisor' | 'allocator'

const MODES: { value: ReportMode; label: string }[] = [
  { value: 'investor', label: 'Investor' },
  { value: 'advisor', label: 'Advisor' },
  { value: 'allocator', label: 'Allocator' },
]

export function ModeToggle({
  mode,
  onChange,
}: {
  mode: ReportMode
  onChange: (m: ReportMode) => void
}) {
  return (
    <div className="flex items-center rounded-lg border border-border overflow-hidden">
      {MODES.map(m => (
        <button
          key={m.value}
          onClick={() => onChange(m.value)}
          className={`px-3 py-1.5 text-[11px] font-semibold tracking-wide transition-colors ${
            mode === m.value
              ? 'bg-primary/15 text-primary'
              : 'text-text-tertiary hover:text-text-secondary hover:bg-surface-elevated/30'
          }`}
        >
          {m.label}
        </button>
      ))}
    </div>
  )
}
