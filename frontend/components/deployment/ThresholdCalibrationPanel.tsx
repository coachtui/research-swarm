'use client'

import React, { useState, useEffect, useCallback } from 'react'
import type {
  ThresholdCalibrationResponse,
  CalibrationSensitivityRow,
  TargetHitRateRow,
  CalibrationNote,
} from '@/types/api'
import { useCalibration } from '@/lib/hooks/useCalibration'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { SlidersHorizontal, AlertCircle, Check, ChevronDown, ChevronUp } from 'lucide-react'

// ── Gate selector ─────────────────────────────────────────────────────────────

const GATE_OPTIONS = [55, 60, 65, 70] as const
type Gate = (typeof GATE_OPTIONS)[number]

function GateSelector({
  value,
  onChange,
}: {
  value: Gate
  onChange: (g: Gate) => void
}) {
  return (
    <div className="flex items-center gap-2">
      <span className="text-xs text-text-secondary">Percentile gate:</span>
      <div className="flex rounded-md border border-surface-elevated overflow-hidden">
        {GATE_OPTIONS.map(g => (
          <button
            key={g}
            onClick={() => onChange(g)}
            className={`px-3 py-1.5 text-xs font-mono transition-colors ${
              g === value
                ? 'bg-amber-500/20 text-amber-300 font-semibold'
                : 'text-text-secondary hover:bg-surface-elevated hover:text-text-primary'
            }`}
          >
            p{g}
          </button>
        ))}
      </div>
    </div>
  )
}

// ── Implied values section ────────────────────────────────────────────────────

function ImpliedValuesCard({
  data,
}: {
  data: ThresholdCalibrationResponse
}) {
  const iv = data.implied_values
  const fmt = (v: number | null, suffix = '%') =>
    v !== null ? `${v.toFixed(2)}${suffix}` : '—'

  return (
    <div className="rounded-lg border border-surface-elevated bg-surface p-4 space-y-3">
      <p className="text-xs font-semibold text-text-secondary uppercase tracking-wide">
        Threshold Implied Values — p{iv.percentile_gate}
      </p>
      <p className="text-xs text-text-secondary leading-relaxed">
        At the{' '}
        <span className="text-amber-300 font-mono font-semibold">{iv.percentile_gate}th percentile</span>,
        the current snapshot requires:
      </p>
      <div className="space-y-2">
        <ImpliedRow
          label="Risk-Adjusted Edge"
          value={fmt(iv.risk_adj_edge_pct)}
          color="emerald"
          note="edge × (1 − stop/100) — ranked for gating"
        />
        <ImpliedRow
          label="Raw Upside Edge"
          value={fmt(iv.edge_pct)}
          color="violet"
          note="(EV / price − 1) × 100"
        />
        <ImpliedRow
          label="Stop Probability"
          value={fmt(iv.stop_prob)}
          color="red"
          note="p60 of the stop-prob distribution (gated separately at ≤ 25%)"
        />
      </div>
    </div>
  )
}

function ImpliedRow({
  label,
  value,
  color,
  note,
}: {
  label: string
  value: string
  color: 'emerald' | 'violet' | 'red'
  note: string
}) {
  const colors = {
    emerald: 'text-emerald-300',
    violet: 'text-violet-300',
    red: 'text-red-400',
  }
  return (
    <div className="flex items-start justify-between gap-3">
      <div>
        <p className="text-xs text-text-primary font-medium">{label}</p>
        <p className="text-xs text-text-secondary mt-0.5">{note}</p>
      </div>
      <span className={`font-mono text-sm font-semibold shrink-0 ${colors[color]}`}>
        {value}
      </span>
    </div>
  )
}

// ── Sensitivity table ─────────────────────────────────────────────────────────

function SensitivityTable({
  rows,
}: {
  rows: CalibrationSensitivityRow[]
}) {
  return (
    <div>
      <p className="text-xs font-semibold text-text-secondary uppercase tracking-wide mb-2">
        Sensitivity Table — EV Percentile Gate
      </p>
      <p className="text-xs text-text-secondary mb-3 leading-relaxed">
        Eligible counts if only the percentile gate changes.
        All other rules held fixed: delta &gt; 0, stop ≤ 25%, regime stable.
      </p>
      <div className="overflow-x-auto rounded-lg border border-surface-elevated">
        <table className="w-full text-xs">
          <thead>
            <tr className="border-b border-surface-elevated text-text-secondary uppercase tracking-wide bg-surface-elevated/30">
              <th className="text-left py-2 px-3 font-medium">Percentile Gate</th>
              <th className="text-right py-2 px-3 font-medium">Tier 1 Eligible</th>
              <th className="text-right py-2 px-3 font-medium">Tier 2 Near-Miss</th>
            </tr>
          </thead>
          <tbody>
            {rows.map(row => (
              <tr
                key={row.percentile_gate}
                className={`border-b border-surface-elevated/30 ${
                  row.is_current ? 'bg-amber-500/8' : ''
                }`}
              >
                <td className="py-2.5 px-3 font-mono font-medium text-text-primary">
                  p{row.percentile_gate}
                  {row.is_current && (
                    <span className="ml-2 text-xs bg-amber-500/20 text-amber-300 border border-amber-500/30 rounded-full px-1.5 py-0.5">
                      live
                    </span>
                  )}
                </td>
                <td className={`text-right py-2.5 px-3 font-mono font-semibold ${
                  row.tier1_eligible > 0 ? 'text-emerald-400' : 'text-text-secondary'
                }`}>
                  {row.tier1_eligible}
                </td>
                <td className={`text-right py-2.5 px-3 font-mono ${
                  row.tier2_eligible > 0 ? 'text-violet-300' : 'text-text-secondary'
                }`}>
                  {row.tier2_eligible}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}

// ── Target hit rate guidance ──────────────────────────────────────────────────

function TargetHitRates({
  rows,
}: {
  rows: TargetHitRateRow[]
}) {
  return (
    <div>
      <p className="text-xs font-semibold text-text-secondary uppercase tracking-wide mb-2">
        Target Hit Rate Guidance
      </p>
      <p className="text-xs text-text-secondary mb-3 leading-relaxed">
        Informational only — shows the tightest percentile gate that yields a desired count.
        No thresholds are changed automatically.
      </p>
      <div className="space-y-2">
        {rows.map(row => (
          <TargetRow key={row.label} row={row} />
        ))}
      </div>
    </div>
  )
}

function TargetRow({ row }: { row: TargetHitRateRow }) {
  const tierColor = row.tier === 1 ? 'emerald' : 'violet'
  const tierLabel = row.tier === 1 ? 'T1' : 'T2'
  const tierBg = row.tier === 1
    ? 'bg-emerald-500/15 text-emerald-300 border-emerald-500/30'
    : 'bg-violet-500/15 text-violet-300 border-violet-500/30'

  return (
    <div className="flex items-center justify-between gap-3 rounded-lg border border-surface-elevated bg-surface px-3 py-2.5">
      <div className="flex items-center gap-2 min-w-0">
        <span className={`inline-flex items-center rounded-full border px-2 py-0.5 text-xs font-semibold shrink-0 ${tierBg}`}>
          {tierLabel}
        </span>
        <span className="text-xs text-text-primary truncate">{row.label}</span>
      </div>
      <div className="flex items-center gap-2 shrink-0">
        {row.suggested_gate !== null ? (
          <>
            <span className="text-xs text-text-secondary">→ use</span>
            <span className={`font-mono font-semibold text-sm ${
              tierColor === 'emerald' ? 'text-emerald-400' : 'text-violet-300'
            }`}>
              p{row.suggested_gate}
            </span>
          </>
        ) : (
          <span className="text-xs text-zinc-500 italic">unachievable with current universe</span>
        )}
      </div>
    </div>
  )
}

// ── Calibration notes section ─────────────────────────────────────────────────

function NotesSection({
  notes,
  onSave,
  isSaving,
}: {
  notes: CalibrationNote[]
  onSave: (text: string) => Promise<boolean>
  isSaving: boolean
}) {
  const [draft, setDraft] = useState('')
  const [saved, setSaved] = useState(false)
  const [open, setOpen] = useState(false)

  const handleSave = useCallback(async () => {
    if (!draft.trim()) return
    const ok = await onSave(draft.trim())
    if (ok) {
      setDraft('')
      setSaved(true)
      setTimeout(() => setSaved(false), 2000)
    }
  }, [draft, onSave])

  return (
    <div className="rounded-lg border border-surface-elevated bg-surface">
      {/* Header — toggle */}
      <button
        onClick={() => setOpen(v => !v)}
        className="flex w-full items-center justify-between px-4 py-3 text-left"
      >
        <p className="text-xs font-semibold text-text-secondary uppercase tracking-wide">
          Operator Notes
          {notes.length > 0 && (
            <span className="ml-2 text-xs font-mono text-text-secondary normal-case tracking-normal">
              ({notes.length})
            </span>
          )}
        </p>
        {open ? (
          <ChevronUp className="h-3.5 w-3.5 text-text-secondary shrink-0" />
        ) : (
          <ChevronDown className="h-3.5 w-3.5 text-text-secondary shrink-0" />
        )}
      </button>

      {open && (
        <div className="px-4 pb-4 space-y-3 border-t border-surface-elevated">
          <p className="text-xs text-text-secondary pt-3 leading-relaxed">
            Short operator notes about the current threshold regime.
            Notes are non-persistent — cleared on server restart.
          </p>

          {/* Draft input */}
          <div className="space-y-2">
            <textarea
              value={draft}
              onChange={e => setDraft(e.target.value.slice(0, 500))}
              placeholder="e.g. p60 too strict in current regime; consider p55 for Tier 2."
              rows={3}
              className="w-full rounded-md border border-surface-elevated bg-background px-3 py-2 text-xs text-text-primary placeholder:text-text-secondary resize-none focus:outline-none focus:ring-1 focus:ring-amber-500/50"
            />
            <div className="flex items-center justify-between">
              <span className="text-xs text-text-secondary font-mono">
                {draft.length}/500
              </span>
              <Button
                size="sm"
                variant="outline"
                onClick={handleSave}
                disabled={!draft.trim() || isSaving}
                className="text-xs border-amber-500/30 text-amber-300 hover:bg-amber-500/10 gap-1.5"
              >
                {saved ? (
                  <>
                    <Check className="h-3 w-3" />
                    Saved
                  </>
                ) : (
                  isSaving ? 'Saving…' : 'Save Note'
                )}
              </Button>
            </div>
          </div>

          {/* Existing notes */}
          {notes.length > 0 && (
            <div className="space-y-2 mt-2">
              {notes.map(note => (
                <div
                  key={note.id}
                  className="rounded border border-surface-elevated bg-surface-elevated/20 px-3 py-2 space-y-1"
                >
                  <p className="text-xs text-text-primary leading-relaxed">{note.text}</p>
                  <p className="text-xs text-text-secondary font-mono">
                    {new Date(note.saved_at).toLocaleString()} · #{note.id}
                  </p>
                </div>
              ))}
            </div>
          )}

          {notes.length === 0 && (
            <p className="text-xs text-text-secondary text-center py-2">No notes yet.</p>
          )}
        </div>
      )}
    </div>
  )
}

// ── Main panel ────────────────────────────────────────────────────────────────

export function ThresholdCalibrationPanel() {
  const { data, notes, isLoading, isSavingNote, error, run, loadNotes, saveNote } =
    useCalibration()
  const [gate, setGate] = useState<Gate>(60)

  // Load notes on first open
  useEffect(() => {
    loadNotes()
  }, [loadNotes])

  const handleGateChange = useCallback(
    (g: Gate) => {
      setGate(g)
      if (data) run(g) // re-fetch implied values when gate changes
    },
    [data, run],
  )

  return (
    <Card className="mt-6 border-dashed border-amber-500/20 bg-amber-500/5">
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between gap-3 flex-wrap">
          <div className="flex items-center gap-2">
            <SlidersHorizontal className="h-4 w-4 text-amber-400 shrink-0" />
            <CardTitle className="text-base text-text-primary">
              Threshold Calibration
            </CardTitle>
            <span className="rounded-full bg-amber-500/15 border border-amber-500/30 px-2 py-0.5 text-xs text-amber-300 font-medium">
              Admin Only
            </span>
          </div>

          <div className="flex items-center gap-3 flex-wrap">
            <GateSelector value={gate} onChange={handleGateChange} />
            <Button
              variant="outline"
              size="sm"
              onClick={() => run(gate)}
              disabled={isLoading}
              className="text-xs border-amber-500/30 text-amber-300 hover:bg-amber-500/10"
            >
              {isLoading ? 'Loading…' : data ? 'Refresh' : 'Load Calibration'}
            </Button>
          </div>
        </div>
        <p className="text-xs text-text-secondary mt-1.5 leading-relaxed">
          Decision support only — shows what the current thresholds imply in real units
          and what count each gate would produce. No thresholds are modified automatically.
        </p>
      </CardHeader>

      <CardContent className="space-y-6">
        {/* Error */}
        {error && !isLoading && (
          <div className="flex items-center gap-2 rounded-lg border border-red-500/30 bg-red-500/10 p-3 text-sm text-red-300">
            <AlertCircle className="h-4 w-4 shrink-0" />
            {error.message}
          </div>
        )}

        {/* Empty prompt */}
        {!data && !isLoading && !error && (
          <p className="text-sm text-text-secondary text-center py-4">
            Click{' '}
            <span className="text-amber-300 font-medium">Load Calibration</span>{' '}
            to compute implied values and sensitivity for the current snapshot.
          </p>
        )}

        {/* Skeleton */}
        {isLoading && (
          <div className="space-y-4 animate-pulse">
            <div className="h-4 w-40 rounded bg-surface-elevated" />
            <div className="h-24 rounded bg-surface-elevated" />
            <div className="h-32 rounded bg-surface-elevated" />
          </div>
        )}

        {/* Results */}
        {data && !isLoading && (
          <>
            <div className="grid grid-cols-1 xl:grid-cols-2 gap-6">
              {/* A — Implied values */}
              <ImpliedValuesCard data={data} />

              {/* B — Sensitivity table */}
              <SensitivityTable rows={data.sensitivity_table} />
            </div>

            {/* C — Target hit rate guidance */}
            <TargetHitRates rows={data.target_hit_rates} />

            <p className="text-xs text-zinc-600 text-right">
              Snapshot {data.snapshot_id.slice(0, 8)}… ·{' '}
              Universe {data.universe_size} · Confirmed {data.confirmed_count} · read-only
            </p>
          </>
        )}

        {/* D — Notes (always shown) */}
        <NotesSection notes={notes} onSave={saveNote} isSaving={isSavingNote} />
      </CardContent>
    </Card>
  )
}
