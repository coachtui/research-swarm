// Signal Dispersion — side-by-side comparison: tight cluster (low dispersion)
// vs wide scatter (high dispersion). Same axis scale to make the contrast legible.

// Predefined dot positions for both panels
const LOW_DISPERSION_DOTS = [
  { cx: 0.48, cy: 0.46 },
  { cx: 0.50, cy: 0.52 },
  { cx: 0.52, cy: 0.44 },
  { cx: 0.49, cy: 0.56 },
  { cx: 0.51, cy: 0.50 },
  { cx: 0.47, cy: 0.53 },
]

const HIGH_DISPERSION_DOTS = [
  { cx: 0.12, cy: 0.20 },
  { cx: 0.85, cy: 0.75 },
  { cx: 0.30, cy: 0.80 },
  { cx: 0.70, cy: 0.18 },
  { cx: 0.55, cy: 0.60 },
  { cx: 0.20, cy: 0.45 },
]

interface ScatterPanelProps {
  x: number
  y: number
  w: number
  h: number
  dots: { cx: number; cy: number }[]
  label: string
  sublabel: string
  accent: boolean
}

function ScatterPanel({ x, y, w, h, dots, label, sublabel, accent }: ScatterPanelProps) {
  const dotColor = accent ? '#3b82f6' : '#6b7280'
  const dotOpacity = accent ? 0.85 : 0.6

  return (
    <g>
      {/* Panel border */}
      <rect x={x} y={y} width={w} height={h} fill="#111827" rx="4" stroke="#1f2937" strokeWidth="1" />

      {/* Dots */}
      {dots.map((d, i) => (
        <circle
          key={i}
          cx={x + d.cx * w}
          cy={y + d.cy * h}
          r={4}
          fill={dotColor}
          fillOpacity={dotOpacity}
        />
      ))}

      {/* Label */}
      <text x={x + w / 2} y={y + h + 14} fill={accent ? '#3b82f6' : '#6b7280'} fontSize="8.5" fontFamily="monospace" textAnchor="middle">
        {label}
      </text>
      <text x={x + w / 2} y={y + h + 24} fill="#4b5563" fontSize="7.5" fontFamily="monospace" textAnchor="middle">
        {sublabel}
      </text>
    </g>
  )
}

export function SignalDispersionDiagram() {
  return (
    <svg
      viewBox="0 0 320 155"
      className="w-full max-h-40"
      aria-label="Signal Dispersion diagram"
    >
      {/* Title */}
      <text x="160" y="14" fill="#6b7280" fontSize="8" fontFamily="monospace" textAnchor="middle">
        Same signal set — different dispersion profiles
      </text>

      {/* Low dispersion panel */}
      <ScatterPanel
        x={16} y={22} w={124} h={96}
        dots={LOW_DISPERSION_DOTS}
        label="Low Dispersion"
        sublabel="Analytical consensus"
        accent={true}
      />

      {/* VS divider */}
      <text x="160" y="76" fill="#374151" fontSize="10" fontFamily="monospace" textAnchor="middle">vs</text>

      {/* High dispersion panel */}
      <ScatterPanel
        x={180} y={22} w={124} h={96}
        dots={HIGH_DISPERSION_DOTS}
        label="High Dispersion"
        sublabel="Fragmented consensus"
        accent={false}
      />

      {/* Range arrow for high dispersion */}
      <line x1="182" y1="115" x2="302" y2="115" stroke="#6b7280" strokeWidth="0.75" markerEnd="url(#arr)" opacity="0.5" />
    </svg>
  )
}
