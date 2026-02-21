// Expectation Compression — two lines over time: Market-Implied curves down
// toward the flat Structural Value Anchor. The narrowing gap = compression.

export function ExpectationCompressionDiagram() {
  return (
    <svg
      viewBox="0 0 320 160"
      className="w-full max-h-40"
      aria-label="Expectation Compression diagram"
    >
      {/* Axes */}
      <line x1="36" y1="16" x2="36" y2="138" stroke="#374151" strokeWidth="1" />
      <line x1="36" y1="138" x2="308" y2="138" stroke="#374151" strokeWidth="1" />

      {/* Axis labels */}
      <text x="8" y="80" fill="#6b7280" fontSize="8" fontFamily="monospace" transform="rotate(-90,8,80)" textAnchor="middle">Value</text>
      <text x="295" y="150" fill="#6b7280" fontSize="8" fontFamily="monospace">Time →</text>

      {/* Structural Value Anchor — flat dashed line */}
      <line x1="40" y1="108" x2="304" y2="108" stroke="#4b5563" strokeWidth="1.5" strokeDasharray="5,3" />
      <text x="42" y="104" fill="#6b7280" fontSize="8" fontFamily="monospace">Structural Value Anchor</text>

      {/* Compression fill zone (between the two curves) */}
      <path
        d="M40,34 C90,34 130,55 170,75 S240,102 304,108 L304,108 L40,108 Z"
        fill="#3b82f6"
        fillOpacity="0.07"
      />

      {/* Market-Implied Value curve — starts high, converges to anchor */}
      <path
        d="M40,34 C90,34 130,55 170,75 S240,102 304,108"
        fill="none"
        stroke="#3b82f6"
        strokeWidth="2"
        strokeLinecap="round"
      />

      {/* Labels */}
      <text x="42" y="29" fill="#3b82f6" fontSize="8" fontFamily="monospace">Market-Implied Value</text>

      {/* Compression zone annotation */}
      <text x="148" y="74" fill="#3b82f6" fontSize="7.5" fontFamily="monospace" textAnchor="middle" opacity="0.8">Compression</text>
      <line x1="148" y1="77" x2="148" y2="104" stroke="#3b82f6" strokeWidth="0.75" strokeDasharray="2,2" opacity="0.5" />

      {/* Time markers */}
      <text x="40" y="150" fill="#4b5563" fontSize="7.5" fontFamily="monospace" textAnchor="middle">T₀</text>
      <text x="172" y="150" fill="#4b5563" fontSize="7.5" fontFamily="monospace" textAnchor="middle">T₁</text>
      <text x="304" y="150" fill="#4b5563" fontSize="7.5" fontFamily="monospace" textAnchor="middle">T₂</text>
    </svg>
  )
}
