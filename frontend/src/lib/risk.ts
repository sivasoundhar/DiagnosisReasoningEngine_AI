/**
 * Semantic color mapping for the 4 risk levels the backend returns
 * (src/knowledge/risk_factors.json's risk_level_thresholds: LOW/MEDIUM/HIGH/
 * CRITICAL). One-off badge/panel colors, not full theme tokens, so kept as a
 * small lookup rather than new CSS variables.
 */
import type { RiskAssessment } from '@/types'

export type RiskLevel = RiskAssessment['risk_level']

interface RiskColors {
  badge: string
  panel: string
  icon: string
  bar: string
}

const RISK_COLORS: Record<RiskLevel, RiskColors> = {
  LOW: {
    badge: 'bg-emerald-100 text-emerald-700 border-emerald-200',
    panel: 'bg-emerald-50 border-emerald-200 text-emerald-800',
    icon: 'text-emerald-600',
    bar: 'bg-emerald-500',
  },
  MEDIUM: {
    badge: 'bg-amber-100 text-amber-700 border-amber-200',
    panel: 'bg-amber-50 border-amber-200 text-amber-800',
    icon: 'text-amber-600',
    bar: 'bg-amber-500',
  },
  HIGH: {
    badge: 'bg-orange-100 text-orange-700 border-orange-200',
    panel: 'bg-orange-50 border-orange-200 text-orange-800',
    icon: 'text-orange-600',
    bar: 'bg-orange-500',
  },
  CRITICAL: {
    badge: 'bg-red-100 text-red-700 border-red-200',
    panel: 'bg-red-50 border-red-200 text-red-800',
    icon: 'text-red-600',
    bar: 'bg-red-500',
  },
}

const FALLBACK: RiskColors = RISK_COLORS.MEDIUM

export function riskColors(level: string | undefined | null): RiskColors {
  if (!level) return FALLBACK
  return RISK_COLORS[level as RiskLevel] ?? FALLBACK
}

/** Colors for a lab's status (LabInterpretation.status: LOW|NORMAL|ELEVATED|CRITICAL). */
const LAB_STATUS_COLORS: Record<string, RiskColors> = {
  NORMAL: RISK_COLORS.LOW,
  LOW: RISK_COLORS.MEDIUM,
  ELEVATED: RISK_COLORS.HIGH,
  CRITICAL: RISK_COLORS.CRITICAL,
}

export function labStatusColors(status: string | undefined | null): RiskColors {
  if (!status) return FALLBACK
  return LAB_STATUS_COLORS[status] ?? FALLBACK
}
