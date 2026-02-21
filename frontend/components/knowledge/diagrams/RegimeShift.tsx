// Regime Shift — two distinct macro zones separated by a vertical boundary.
// The shift is a structural state change, not a gradual drift.

export function RegimeShiftDiagram() {
  const midX = 160

  return (
    <svg
      viewBox="0 0 320 155"
      className="w-full max-h-40"
      aria-label="Regime Shift diagram"
    >
      {/* Prior regime zone (left, calmer) */}
      <rect x="16" y="20" width={midX - 24} height="105" fill="#1d4ed8" fillOpacity="0.06" rx="4" />

      {/* New regime zone (right, stressed) */}
      <rect x={midX + 8} y="20" width={midX - 24} height="105" fill="#ef4444" fillOpacity="0.06" rx="4" />

      {/* Zone labels */}
      <text x={(midX - 24) / 2 + 16} y="38" fill="#6b7280" fontSize="9" fontFamily="monospace" textAnchor="middle">Prior Regime</text>
      <text x={midX + 8 + (midX - 24) / 2} y="38" fill="#6b7280" fontSize="9" fontFamily="monospace" textAnchor="middle">New Regime</text>

      {/* Prior regime descriptors */}
      {['Low rates', 'Tight spreads', 'Risk-on', 'Multiple expansion'].map((t, i) => (
        <text key={t} x={(midX - 24) / 2 + 16} y={56 + i * 16} fill="#4b5563" fontSize="8" fontFamily="monospace" textAnchor="middle">{t}</text>
      ))}

      {/* New regime descriptors */}
      {['Rising rates', 'Widening spreads', 'Risk-off', 'Multiple contraction'].map((t, i) => (
        <text key={t} x={midX + 8 + (midX - 24) / 2} y={56 + i * 16} fill="#4b5563" fontSize="8" fontFamily="monospace" textAnchor="middle">{t}</text>
      ))}

      {/* Transition boundary line */}
      <line x1={midX} y1="14" x2={midX} y2="132" stroke="#f59e0b" strokeWidth="2" strokeLinecap="round" />

      {/* Transition label */}
      <text x={midX} y="144" fill="#f59e0b" fontSize="8" fontFamily="monospace" textAnchor="middle">Regime Transition</text>
      <text x={midX} y="153" fill="#4b5563" fontSize="7.5" fontFamily="monospace" textAnchor="middle">Risk premiums reprice</text>

      {/* Arrow showing direction of shift */}
      <path d={`M${midX - 20},24 L${midX + 20},24`} fill="none" stroke="#f59e0b" strokeWidth="1.5" markerEnd="url(#arrowhead)" />
      <text x={midX} y="20" fill="#f59e0b" fontSize="7" fontFamily="monospace" textAnchor="middle">→</text>
    </svg>
  )
}
