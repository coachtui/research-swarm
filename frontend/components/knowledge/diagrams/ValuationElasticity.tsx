// Valuation Elasticity — two panels: narrow FV range (low elasticity, anchored)
// vs wide FV range (high elasticity, assumption-driven). Same input change.

export function ValuationElasticityDiagram() {
  return (
    <svg
      viewBox="0 0 320 155"
      className="w-full max-h-40"
      aria-label="Valuation Elasticity diagram"
    >
      {/* Shared input label */}
      <text x="160" y="13" fill="#4b5563" fontSize="8" fontFamily="monospace" textAnchor="middle">
        Same ±1% growth assumption change applied to both
      </text>

      {/* ── Low Elasticity Panel ── */}
      <g transform="translate(16, 22)">
        <rect x="0" y="0" width="128" height="88" fill="#111827" rx="4" stroke="#1f2937" strokeWidth="1" />

        {/* Fair value range bar */}
        <rect x="24" y="20" width="80" height="48" fill="#3b82f6" fillOpacity="0.15" rx="3" />
        <line x1="24" y1="20" x2="104" y2="20" stroke="#3b82f6" strokeWidth="1.5" />
        <line x1="24" y1="68" x2="104" y2="68" stroke="#3b82f6" strokeWidth="1.5" />

        {/* Center point */}
        <line x1="24" y1="44" x2="104" y2="44" stroke="#3b82f6" strokeWidth="0.75" strokeDasharray="3,3" />
        <circle cx="64" cy="44" r="3" fill="#3b82f6" />

        {/* Range caps */}
        <line x1="24" y1="14" x2="24" y2="74" stroke="#3b82f6" strokeWidth="1" />
        <line x1="104" y1="14" x2="104" y2="74" stroke="#3b82f6" strokeWidth="1" />

        {/* Labels */}
        <text x="64" y="84" fill="#3b82f6" fontSize="7.5" fontFamily="monospace" textAnchor="middle">$95 — $115</text>
        <text x="64" y="100" fill="#6b7280" fontSize="7.5" fontFamily="monospace" textAnchor="middle">Low Elasticity</text>
        <text x="64" y="109" fill="#4b5563" fontSize="7" fontFamily="monospace" textAnchor="middle">Anchored by earnings</text>
      </g>

      {/* vs divider */}
      <text x="160" y="70" fill="#374151" fontSize="10" fontFamily="monospace" textAnchor="middle">vs</text>

      {/* ── High Elasticity Panel ── */}
      <g transform="translate(176, 22)">
        <rect x="0" y="0" width="128" height="88" fill="#111827" rx="4" stroke="#1f2937" strokeWidth="1" />

        {/* Wide fair value range bar */}
        <rect x="8" y="8" width="112" height="72" fill="#f59e0b" fillOpacity="0.10" rx="3" />
        <line x1="8" y1="8" x2="120" y2="8" stroke="#f59e0b" strokeWidth="1.5" />
        <line x1="8" y1="80" x2="120" y2="80" stroke="#f59e0b" strokeWidth="1.5" />

        {/* Center point */}
        <line x1="8" y1="44" x2="120" y2="44" stroke="#f59e0b" strokeWidth="0.75" strokeDasharray="3,3" />
        <circle cx="64" cy="44" r="3" fill="#f59e0b" />

        {/* Range caps */}
        <line x1="8" y1="2" x2="8" y2="86" stroke="#f59e0b" strokeWidth="1" />
        <line x1="120" y1="2" x2="120" y2="86" stroke="#f59e0b" strokeWidth="1" />

        {/* Labels */}
        <text x="64" y="97" fill="#f59e0b" fontSize="7.5" fontFamily="monospace" textAnchor="middle">$60 — $210</text>
        <text x="64" y="109" fill="#6b7280" fontSize="7.5" fontFamily="monospace" textAnchor="middle">High Elasticity</text>
        <text x="64" y="118" fill="#4b5563" fontSize="7" fontFamily="monospace" textAnchor="middle">Growth-assumption driven</text>
      </g>

      {/* Bottom note */}
      <text x="160" y="150" fill="#4b5563" fontSize="7.5" fontFamily="monospace" textAnchor="middle">
        Point estimate is the center. Width is the uncertainty.
      </text>
    </svg>
  )
}
