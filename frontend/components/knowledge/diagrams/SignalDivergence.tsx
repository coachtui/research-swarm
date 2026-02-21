// Signal Divergence — four signal tracks with directional indicators.
// Bullish signals (accent) vs bearish signals (muted) in visual opposition.

const SIGNALS = [
  { label: 'Fundamental', score: 0.80, bullish: true },
  { label: 'Technical',   score: 0.25, bullish: false },
  { label: 'Quantitative',score: 0.72, bullish: true },
  { label: 'Sentiment',   score: 0.30, bullish: false },
]

export function SignalDivergenceDiagram() {
  const rowH = 28
  const topPad = 20
  const leftPad = 80
  const barMax = 180
  const midX = leftPad + barMax / 2

  return (
    <svg
      viewBox="0 0 320 155"
      className="w-full max-h-40"
      aria-label="Signal Divergence diagram"
    >
      {/* Center neutral axis */}
      <line x1={midX} y1={topPad - 8} x2={midX} y2={topPad + rowH * 4 + 2} stroke="#374151" strokeWidth="1" strokeDasharray="3,3" />
      <text x={midX} y={topPad - 11} fill="#4b5563" fontSize="7.5" fontFamily="monospace" textAnchor="middle">NEUTRAL</text>

      {/* Axis extremes */}
      <text x={leftPad} y={topPad - 11} fill="#6b7280" fontSize="7.5" fontFamily="monospace" textAnchor="middle">BEARISH</text>
      <text x={leftPad + barMax} y={topPad - 11} fill="#6b7280" fontSize="7.5" fontFamily="monospace" textAnchor="middle">BULLISH</text>

      {SIGNALS.map((sig, i) => {
        const y = topPad + i * rowH
        const barWidth = (sig.score - 0.5) * barMax  // can be negative
        const barX = sig.bullish ? midX : midX + barWidth
        const absWidth = Math.abs(barWidth)
        const fill = sig.bullish ? '#3b82f6' : '#6b7280'
        const fillOpacity = sig.bullish ? 0.75 : 0.45
        const arrowX = sig.bullish ? midX + absWidth + 6 : midX - absWidth - 6
        const arrowDir = sig.bullish ? '▶' : '◀'

        return (
          <g key={sig.label}>
            {/* Row background */}
            <rect x={leftPad} y={y + 2} width={barMax} height={rowH - 4} fill="#111827" rx="2" />

            {/* Signal bar */}
            <rect
              x={barX}
              y={y + 6}
              width={absWidth}
              height={rowH - 12}
              fill={fill}
              fillOpacity={fillOpacity}
              rx="2"
            />

            {/* Label */}
            <text x={leftPad - 4} y={y + rowH / 2 + 3} fill="#9ca3af" fontSize="8.5" fontFamily="monospace" textAnchor="end">
              {sig.label}
            </text>

            {/* Direction arrow */}
            <text
              x={arrowX}
              y={y + rowH / 2 + 4}
              fill={fill}
              fontSize="9"
              fontFamily="monospace"
              textAnchor="middle"
              fillOpacity={0.9}
            >
              {arrowDir}
            </text>
          </g>
        )
      })}

      {/* Divergence annotation */}
      <text x="160" y="148" fill="#3b82f6" fontSize="7.5" fontFamily="monospace" textAnchor="middle" opacity="0.7">
        ← Divergence active: signals in structural conflict →
      </text>
    </svg>
  )
}
