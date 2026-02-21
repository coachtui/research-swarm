// Structural Premium — stacked zone diagram showing the three layers:
// discount zone → structural anchor → justified premium → speculative excess.

export function StructuralPremiumDiagram() {
  return (
    <svg
      viewBox="0 0 320 160"
      className="w-full max-h-40"
      aria-label="Structural Premium diagram"
    >
      {/* Zone fills */}
      {/* Speculative Excess (top, red-tinted) */}
      <rect x="60" y="16" width="200" height="30" fill="#ef4444" fillOpacity="0.08" />
      {/* Structural Premium zone (accent, justified) */}
      <rect x="60" y="46" width="200" height="36" fill="#3b82f6" fillOpacity="0.12" />
      {/* Discount zone (bottom, muted green) */}
      <rect x="60" y="108" width="200" height="30" fill="#10b981" fillOpacity="0.06" />

      {/* Structural Value Anchor line (solid) */}
      <line x1="44" y1="108" x2="276" y2="108" stroke="#4b5563" strokeWidth="1.5" strokeDasharray="5,3" />

      {/* Current Price indicator */}
      <line x1="44" y1="70" x2="276" y2="70" stroke="#3b82f6" strokeWidth="1.5" />
      <circle cx="44" cy="70" r="3" fill="#3b82f6" />

      {/* Zone labels (right side) */}
      <text x="268" y="34" fill="#ef4444" fontSize="8" fontFamily="monospace" textAnchor="start" opacity="0.9">Speculative</text>
      <text x="268" y="44" fill="#ef4444" fontSize="8" fontFamily="monospace" textAnchor="start" opacity="0.9">Excess</text>

      <text x="268" y="61" fill="#3b82f6" fontSize="8" fontFamily="monospace" textAnchor="start">Structural</text>
      <text x="268" y="71" fill="#3b82f6" fontSize="8" fontFamily="monospace" textAnchor="start">Premium ✓</text>

      <text x="268" y="120" fill="#6b7280" fontSize="8" fontFamily="monospace" textAnchor="start">Discount</text>
      <text x="268" y="130" fill="#6b7280" fontSize="8" fontFamily="monospace" textAnchor="start">Zone</text>

      {/* Left labels */}
      <text x="8" y="73" fill="#3b82f6" fontSize="8" fontFamily="monospace">Price</text>
      <text x="8" y="111" fill="#6b7280" fontSize="8" fontFamily="monospace">Anchor</text>

      {/* Left bracket lines */}
      <line x1="56" y1="46" x2="44" y2="46" stroke="#374151" strokeWidth="0.75" />
      <line x1="56" y1="46" x2="56" y2="108" stroke="#374151" strokeWidth="0.75" />
      <line x1="56" y1="108" x2="44" y2="108" stroke="#374151" strokeWidth="0.75" />
      <text x="22" y="82" fill="#3b82f6" fontSize="7.5" fontFamily="monospace" textAnchor="middle">Premium</text>
      <text x="22" y="91" fill="#3b82f6" fontSize="7.5" fontFamily="monospace" textAnchor="middle">Zone</text>

      {/* Footer note */}
      <text x="160" y="152" fill="#4b5563" fontSize="7.5" fontFamily="monospace" textAnchor="middle">← Competitive Advantage Durability →</text>
    </svg>
  )
}
