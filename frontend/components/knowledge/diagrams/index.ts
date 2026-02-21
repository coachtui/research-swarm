// Diagram component registry — maps term IDs to their SVG diagram components.
// Add new diagrams here; the ConceptPanel reads this registry automatically.

import type { ComponentType } from 'react'
import { ExpectationCompressionDiagram } from './ExpectationCompression'
import { StructuralPremiumDiagram } from './StructuralPremium'
import { SignalDivergenceDiagram } from './SignalDivergence'
import { SignalDispersionDiagram } from './SignalDispersion'
import { RegimeShiftDiagram } from './RegimeShift'
import { ThesisStabilityDiagram } from './ThesisStability'
import { ValuationElasticityDiagram } from './ValuationElasticity'

export const DIAGRAM_REGISTRY: Record<string, ComponentType> = {
  expectation_compression: ExpectationCompressionDiagram,
  structural_premium:      StructuralPremiumDiagram,
  signal_divergence:       SignalDivergenceDiagram,
  signal_dispersion:       SignalDispersionDiagram,
  regime_shift:            RegimeShiftDiagram,
  thesis_stability:        ThesisStabilityDiagram,
  valuation_elasticity:    ValuationElasticityDiagram,
}
