'use client'

/**
 * TrancheDeploymentPath — 3-stage capital deployment timing panel.
 *
 * Renders the DVRG tranche scaling framework output:
 *   Stage 1 ✓  →  Stage 2  →  Stage 3
 *
 * Layer: Investor+ (gated by canSeeCapitalDiscipline in ResultsContent).
 * Sits below CapitalAllocationDiscipline in the results page.
 *
 * CRITICAL: This component is display-only — it does NOT modify any
 * EV, valuation, or allocation calculations.
 */

import { useState } from 'react'
import { ChevronDown, ChevronUp, Check, AlertTriangle, CircleDot, Circle } from 'lucide-react'
import type { TranchePlan, TrancheTriggerCondition, TranchBreakCondition } from '@/types/api'

// ── Sub-accordion ──────────────────────────────────────────────────────────────

function SubAccordion({
  title,
  badge,
  badgeVariant = 'neutral',
  defaultOpen = false,
  children,
}: {
  title: string
  badge?: string
  badgeVariant?: 'neutral' | 'warning' | 'success'
  defaultOpen?: boolean
  children: React.ReactNode
}) {
  const [open, setOpen] = useState(defaultOpen)
  const badgeColor =
    badgeVariant === 'warning' ? 'text-warning border-warning/40' :
    badgeVariant === 'success' ? 'text-success border-success/40' :
    'text-text-tertiary border-border'

  return (
    <div className="rounded-md border border-border/40 bg-surface-elevated/20 overflow-hidden">
      <button
        onClick={() => setOpen(o => !o)}
        className="w-full flex items-center justify-between px-4 py-2.5 text-left hover:bg-surface-elevated/40 transition-colors"
      >
        <div className="flex items-center gap-2">
          <span className="text-xs font-semibold text-text-secondary uppercase tracking-wide">
            {title}
          </span>
          {badge && (
            <span className={`text-[10px] font-medium border rounded px-1.5 py-0.5 ${badgeColor}`}>
              {badge}
            </span>
          )}
        </div>
        {open
          ? <ChevronUp className="h-3.5 w-3.5 text-text-tertiary flex-shrink-0" />
          : <ChevronDown className="h-3.5 w-3.5 text-text-tertiary flex-shrink-0" />}
      </button>
      {open && (
        <div className="border-t border-border/30 px-4 py-3 space-y-2">
          {children}
        </div>
      )}
    </div>
  )
}

// ── Stage node ─────────────────────────────────────────────────────────────────

type StageStatus = 'complete' | 'active' | 'pending'

function StageNode({
  num,
  label,
  addPct,
  status,
}: {
  num: number
  label: string
  addPct: number
  status: StageStatus
}) {
  const circleClass =
    status === 'complete' ? 'bg-success border-success text-white' :
    status === 'active'   ? 'bg-primary/15 border-primary text-primary' :
    'bg-surface border-border/50 text-text-tertiary/50'

  const labelClass =
    status === 'complete' ? 'text-success' :
    status === 'active'   ? 'text-primary' :
    'text-text-tertiary/50'

  const pctClass =
    status === 'complete' ? 'text-success/70' :
    status === 'active'   ? 'text-primary/70' :
    'text-text-tertiary/30'

  return (
    <div className="flex flex-col items-center gap-1 min-w-[64px]">
      {/* Circle */}
      <div className={`w-8 h-8 rounded-full border-2 flex items-center justify-center flex-shrink-0 ${circleClass}`}>
        {status === 'complete'
          ? <Check className="h-4 w-4" strokeWidth={2.5} />
          : status === 'active'
            ? <CircleDot className="h-4 w-4" />
            : <Circle className="h-4 w-4" strokeWidth={1.5} />}
      </div>
      {/* Stage num label */}
      <span className={`text-[11px] font-semibold uppercase tracking-wide ${labelClass}`}>
        Stage {num}
      </span>
      {/* Stage sub-label */}
      <span className={`text-[10px] ${labelClass}`}>{label}</span>
      {/* Add size */}
      <span className={`text-[10px] tabular-nums ${pctClass}`}>
        {num === 1 ? 'Starter' : `+${addPct.toFixed(1)}%`}
      </span>
    </div>
  )
}

// ── Connector line ─────────────────────────────────────────────────────────────

function Connector({ filled }: { filled: boolean }) {
  return (
    <div className="flex-1 flex items-start justify-center mt-[15px]">
      <div className={`h-0.5 w-full ${filled ? 'bg-success/50' : 'bg-border/40'}`} />
    </div>
  )
}

// ── Trigger row ────────────────────────────────────────────────────────────────

function TriggerRow({ condition }: { condition: TrancheTriggerCondition }) {
  return (
    <div className="flex items-start gap-2.5 py-1">
      <div className={`mt-0.5 w-4 h-4 rounded-full flex items-center justify-center flex-shrink-0 ${
        condition.met
          ? 'bg-success/15 text-success'
          : 'bg-surface-elevated border border-border/60 text-text-tertiary/40'
      }`}>
        {condition.met
          ? <Check className="h-2.5 w-2.5" strokeWidth={3} />
          : <span className="text-[8px] font-bold">○</span>}
      </div>
      <div className="flex-1 min-w-0">
        <p className={`text-[11px] font-medium ${condition.met ? 'text-text-primary' : 'text-text-secondary'}`}>
          {condition.label}
        </p>
        <p className="text-[10px] text-text-tertiary mt-0.5">{condition.detail}</p>
      </div>
      <span className={`text-[10px] font-semibold tabular-nums flex-shrink-0 mt-0.5 ${
        condition.met ? 'text-success' : 'text-text-tertiary/50'
      }`}>
        {condition.met ? 'Met' : 'Pending'}
      </span>
    </div>
  )
}

// ── Thesis break row ───────────────────────────────────────────────────────────

function BreakRow({ condition }: { condition: TranchBreakCondition }) {
  return (
    <div className="flex items-center gap-2.5 py-1">
      <div className={`w-4 h-4 rounded-full flex items-center justify-center flex-shrink-0 ${
        condition.active
          ? 'bg-error/15 text-error'
          : 'bg-success/10 text-success'
      }`}>
        {condition.active
          ? <AlertTriangle className="h-2.5 w-2.5" />
          : <Check className="h-2.5 w-2.5" strokeWidth={3} />}
      </div>
      <div className="flex-1 min-w-0">
        <p className={`text-[11px] font-medium ${condition.active ? 'text-error' : 'text-text-secondary'}`}>
          {condition.label}
        </p>
      </div>
      <div className="text-right flex-shrink-0">
        <p className={`text-[10px] tabular-nums font-medium ${condition.active ? 'text-error' : 'text-text-tertiary'}`}>
          {condition.current}
        </p>
        <p className="text-[9px] text-text-tertiary/50">{condition.threshold}</p>
      </div>
    </div>
  )
}

// ── Main ───────────────────────────────────────────────────────────────────────

interface TrancheDeploymentPathProps {
  tranchePlan: TranchePlan
}

export function TrancheDeploymentPath({ tranchePlan: p }: TrancheDeploymentPathProps) {
  const {
    stage,
    max_position_pct,
    starter_position_pct,
    stage2_add_pct,
    stage3_add_pct,
    current_position_pct,
    stage2_met,
    stage3_met,
    thesis_break_active,
    reduce_by_50_pct,
    next_add_trigger_conditions,
    next_add_size_pct,
    next_add_note,
    thesis_break_conditions,
    stage2_conditions,
    stage3_conditions,
    initiation_score,
  } = p

  // Stage statuses
  const s1Status: StageStatus = 'complete'  // always complete when plan exists
  const s2Status: StageStatus =
    stage === 3 || (stage === 2 && !thesis_break_active) ? 'complete' :
    stage === 2 ? 'active' :
    stage2_met ? 'active' : 'pending'
  const s3Status: StageStatus =
    stage === 3 && !thesis_break_active ? 'active' :
    stage3_met ? 'active' : 'pending'

  const nextStageCopy =
    stage === 1 ? 'Stage 2 triggers'
    : stage === 2 ? 'Stage 3 triggers'
    : null

  const activeBreaks = thesis_break_conditions.filter(c => c.active)

  return (
    <div className="rounded-xl border border-border/50 bg-surface/40 overflow-hidden">

      {/* ── Header ──────────────────────────────────────────────────────────── */}
      <div className="flex items-center justify-between px-5 py-3.5 border-b border-border/40">
        <div>
          <p className="text-sm font-semibold text-text-primary">Capital Deployment Path</p>
          <p className="text-[10px] text-text-tertiary mt-0.5">
            3-stage tranche framework · deployment timing
          </p>
        </div>
        <div className="flex items-center gap-2">
          {initiation_score !== null && initiation_score !== undefined && (
            <span className="text-[10px] text-text-tertiary tabular-nums">
              Score {initiation_score.toFixed(0)}/100
            </span>
          )}
          <span className={`text-[10px] font-semibold uppercase tracking-wide border rounded px-1.5 py-0.5 ${
            stage === 3 ? 'text-primary border-primary/40' :
            stage === 2 ? 'text-success border-success/40' :
            'text-warning border-warning/40'
          }`}>
            Stage {stage}
          </span>
        </div>
      </div>

      <div className="px-5 py-4 space-y-4">

        {/* ── Thesis break alert ─────────────────────────────────────────────── */}
        {thesis_break_active && (
          <div className="flex items-start gap-3 bg-error/8 border border-error/25 rounded-lg px-4 py-3">
            <AlertTriangle className="h-4 w-4 text-error flex-shrink-0 mt-0.5" />
            <div>
              <p className="text-xs font-semibold text-error">Thesis Break Active — Position Reduced 50%</p>
              <p className="text-[11px] text-error/70 mt-0.5">
                {activeBreaks.map(b => b.label).join(' · ')}
              </p>
            </div>
          </div>
        )}

        {/* ── Stage progression track ────────────────────────────────────────── */}
        <div className="flex items-start gap-0 mt-1">
          <StageNode num={1} label="Starter" addPct={starter_position_pct} status={s1Status} />
          <Connector filled={stage >= 2 && !thesis_break_active} />
          <StageNode num={2} label="Confirm" addPct={stage2_add_pct} status={s2Status} />
          <Connector filled={stage >= 3 && !thesis_break_active} />
          <StageNode num={3} label="Conviction" addPct={stage3_add_pct} status={s3Status} />
        </div>

        {/* ── Current position summary ───────────────────────────────────────── */}
        <div className="flex items-center justify-between rounded-lg bg-surface-elevated/40 border border-border/40 px-4 py-2.5">
          <div>
            <p className="text-[10px] text-text-tertiary uppercase tracking-wide">Current allocation</p>
            <p className="text-lg font-bold text-text-primary tabular-nums mt-0.5">
              {current_position_pct.toFixed(2)}%
              {reduce_by_50_pct && (
                <span className="text-xs font-normal text-error ml-1.5">(50% reduction active)</span>
              )}
            </p>
          </div>
          <div className="text-right">
            <p className="text-[10px] text-text-tertiary uppercase tracking-wide">Max allowed</p>
            <p className="text-sm font-semibold text-text-secondary tabular-nums mt-0.5">
              {max_position_pct.toFixed(2)}%
            </p>
          </div>
          {stage < 3 && next_add_size_pct > 0 && (
            <div className="text-right">
              <p className="text-[10px] text-text-tertiary uppercase tracking-wide">Next add</p>
              <p className="text-sm font-semibold text-success tabular-nums mt-0.5">
                +{next_add_size_pct.toFixed(2)}%
              </p>
            </div>
          )}
        </div>

        {/* ── Next add triggers ──────────────────────────────────────────────── */}
        {nextStageCopy && next_add_trigger_conditions.length > 0 && (
          <SubAccordion
            title={nextStageCopy}
            badge={next_add_note.includes('Any ONE') ? 'Any one' : 'All required'}
            badgeVariant={next_add_note.includes('Any ONE') ? 'success' : 'neutral'}
            defaultOpen={true}
          >
            <p className="text-[10px] text-text-tertiary mb-2">{next_add_note}</p>
            <div className="divide-y divide-border/30">
              {next_add_trigger_conditions.map((c, i) => (
                <TriggerRow key={i} condition={c} />
              ))}
            </div>
          </SubAccordion>
        )}

        {/* ── Stage 2 conditions (when at stage 3, show stage 2 as history) ── */}
        {stage === 3 && stage2_conditions.length > 0 && (
          <SubAccordion
            title="Stage 2 conditions"
            badge="Completed"
            badgeVariant="success"
            defaultOpen={false}
          >
            <div className="divide-y divide-border/30">
              {stage2_conditions.map((c, i) => (
                <TriggerRow key={i} condition={c} />
              ))}
            </div>
          </SubAccordion>
        )}

        {/* ── Thesis break monitor ───────────────────────────────────────────── */}
        <SubAccordion
          title="Thesis break monitor"
          badge={thesis_break_active ? `${activeBreaks.length} active` : 'Clear'}
          badgeVariant={thesis_break_active ? 'warning' : 'success'}
          defaultOpen={thesis_break_active}
        >
          <p className="text-[10px] text-text-tertiary mb-2">
            Any active condition triggers a 50% position reduction.
          </p>
          <div className="divide-y divide-border/30">
            {thesis_break_conditions.map((c, i) => (
              <BreakRow key={i} condition={c} />
            ))}
          </div>
        </SubAccordion>

      </div>
    </div>
  )
}
