// Thesis Stability — two curves over "Assumption Variation" axis.
// Stable thesis (accent, smooth) vs fragile thesis (muted, volatile).

export function ThesisStabilityDiagram() {
  return (
    <svg
      viewBox="0 0 320 155"
      className="w-full max-h-40"
      aria-label="Thesis Stability diagram"
    >
      {/* Axes */}
      <line x1="36" y1="14" x2="36" y2="122" stroke="#374151" strokeWidth="1" />
      <line x1="36" y1="122" x2="306" y2="122" stroke="#374151" strokeWidth="1" />

      {/* Axis labels */}
      <text x="8" y="72" fill="#6b7280" fontSize="7.5" fontFamily="monospace" transform="rotate(-90,8,72)" textAnchor="middle">Thesis Score</text>
      <text x="160" y="138" fill="#6b7280" fontSize="7.5" fontFamily="monospace" textAnchor="middle">Assumption Variation →</text>

      {/* X-axis scenario markers */}
      {['Base', 'Bull', 'Bear', 'Rate+', 'Rate−'].map((label, i) => {
        const x = 52 + i * 54
        return (
          <g key={label}>
            <line x1={x} y1="120" x2={x} y2="125" stroke="#374151" strokeWidth="1" />
            <text x={x} y="133" fill="#4b5563" fontSize="7" fontFamily="monospace" textAnchor="middle">{label}</text>
          </g>
        )
      })}

      {/* High stability curve — smooth, minimal variation */}
      <path
        d="M52,52 C106,50 160,54 214,52 S268,56 268,54"
        fill="none"
        stroke="#3b82f6"
        strokeWidth="2.5"
        strokeLinecap="round"
      />

      {/* Low stability curve — volatile, high variation */}
      <path
        d="M52,60 C80,30 106,95 160,40 S214,90 268,55"
        fill="none"
        stroke="#6b7280"
        strokeWidth="1.5"
        strokeDasharray="5,3"
        strokeLinecap="round"
      />

      {/* Legend */}
      <line x1="44" y1="20" x2="64" y2="20" stroke="#3b82f6" strokeWidth="2.5" />
      <text x="68" y="23" fill="#3b82f6" fontSize="8" fontFamily="monospace">High Stability — thesis survives perturbation</text>

      <line x1="44" y1="34" x2="64" y2="34" stroke="#6b7280" strokeWidth="1.5" strokeDasharray="4,3" />
      <text x="68" y="37" fill="#6b7280" fontSize="8" fontFamily="monospace">Low Stability — assumption-dependent</text>
    </svg>
  )
}
