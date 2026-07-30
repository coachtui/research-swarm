'use client'

import { useState } from 'react'
import { Badge } from '@/components/ui/badge'
import type { WeekPosition } from '@/types/api'

const money = (n: number | null | undefined) =>
  n == null ? '—' : n.toLocaleString('en-US', { style: 'currency', currency: 'USD', maximumFractionDigits: 2 })

function Why({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <p className="mt-1.5 text-sm text-muted-foreground max-w-[70ch]">
      <span className="uppercase text-[0.62rem] tracking-wider font-semibold text-primary mr-2">{label}</span>
      {children}
    </p>
  )
}

/** "pullback limit $382.31 = price $391.00 − ATR $8.70, floored at SMA20 $380.10" */
function priceMathSentence(f: NonNullable<WeekPosition['entry_forensics']>): string | null {
  if (f.limit_price == null) return null
  if (f.entry_style === 'on_pullback' && f.price != null && f.atr != null && f.sma20 != null) {
    return `pullback limit ${money(f.limit_price)} = price ${money(f.price)} − ATR ${money(f.atr)}, floored at SMA20 ${money(f.sma20)}`
  }
  if (f.entry_style === 'at_market') {
    return `at-market limit ${money(f.limit_price)} = last close at decision`
  }
  return `limit ${money(f.limit_price)}${f.entry_style ? ` (${f.entry_style})` : ''}`
}

function Ladder({ plan, current }: { plan: NonNullable<WeekPosition['plan']>; current: number }) {
  const rungs = [...plan.ladder].sort((a, b) => b.price - a.price)
  return (
    <div className="mt-2 border-l-2 border-muted pl-3 flex flex-col gap-1">
      {rungs.map((r, i) => (
        <div key={i} className="flex flex-wrap items-baseline gap-x-2 text-sm">
          <span className="font-mono tabular-nums">{money(r.price)}</span>
          <span className="text-xs text-muted-foreground">×{(r.size_pct * 100).toFixed(0)}%</span>
          {current >= r.price ? (
            <Badge variant="secondary" className="text-[0.6rem]">below current</Badge>
          ) : (
            <Badge variant="warning" className="text-[0.6rem]">above current</Badge>
          )}
          <span className="text-xs text-muted-foreground">{r.why}</span>
        </div>
      ))}
      <div className="text-xs text-muted-foreground">
        current ≈ <span className="font-mono">{money(current)}</span>
      </div>
    </div>
  )
}

export function PositionCard({ p }: { p: WeekPosition }) {
  const [open, setOpen] = useState(false)
  const up = p.unrealized_pl >= 0
  const currentPrice = p.qty > 0 ? p.market_value / p.qty : 0
  const f = p.entry_forensics
  const math = f ? priceMathSentence(f) : null

  return (
    <div className="border-b last:border-b-0 py-3">
      <button type="button" onClick={() => setOpen(!open)} className="w-full text-left">
        <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
          <span className="font-mono font-semibold">{p.symbol}</span>
          {p.sleeve && <Badge variant="secondary" className="text-[0.65rem]">Sleeve {p.sleeve}</Badge>}
          {p.themes.map((t) => (
            <Badge key={t} variant="secondary" className="text-[0.65rem]">{t}</Badge>
          ))}
          {p.plan ? (
            <Badge variant="secondary" className="text-[0.65rem]">plan</Badge>
          ) : (
            p.sleeve === 'A' && <Badge variant="warning" className="text-[0.65rem]">no plan</Badge>
          )}
          <span className="ml-auto font-mono text-sm tabular-nums text-muted-foreground">
            {p.qty} sh · {money(p.market_value)}
          </span>
          <span className={`font-mono text-sm tabular-nums ${up ? 'text-emerald-600' : 'text-red-600'}`}>
            {up ? '+' : ''}{p.unrealized_pl.toFixed(0)} ({(p.unrealized_plpc * 100).toFixed(1)}%)
          </span>
        </div>
      </button>

      {p.why_now && <Why label="Why now">{p.why_now}</Why>}
      {p.why_this_expression && <Why label="Why this name">{p.why_this_expression}</Why>}

      {open && (
        <div className="mt-2 rounded-md bg-muted/40 px-3 py-2">
          {math && <Why label="Why this price">{math}</Why>}
          {p.plan ? (
            <>
              <Why label="Thesis breaks if">{p.plan.thesis_break}</Why>
              {p.plan.exit_plan && (
                <Why label={`Exit posture · ${p.plan.exit_plan.posture.replace(/_/g, ' ')}`}>
                  {p.plan.exit_plan.why}
                </Why>
              )}
              {p.plan.ladder.length > 0 && <Ladder plan={p.plan} current={currentPrice} />}
            </>
          ) : (
            <p className="mt-1.5 text-sm italic text-muted-foreground">
              No plan recorded (pre–Phase C entry). The next memo action on this
              name will persist one.
            </p>
          )}
        </div>
      )}
    </div>
  )
}
