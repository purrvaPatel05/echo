import type { MatchFactorKey, MatchFactorStatus, MatchStrength } from './types'

export const FACTOR_LABEL: Record<MatchFactorKey, string> = {
  clinical_fit: 'Clinical fit',
  insurance: 'Insurance',
  distance: 'Distance',
  availability: 'Availability',
  urgency: 'Urgency',
}

/** Read out by screen readers next to each factor's icon, so status never depends on the icon alone. */
export const FACTOR_STATUS_WORD: Record<MatchFactorStatus, string> = {
  met: 'Meets',
  partial: 'Partly meets',
  unmet: 'Does not meet',
}

/** Strength is a label, never a number (Figma: Strong / Good / Partial match). */
export const STRENGTH_META: Record<MatchStrength, { label: string; variant: 'success' | 'primary' | 'warning' }> = {
  strong: { label: 'Strong match', variant: 'success' },
  good: { label: 'Good match', variant: 'primary' },
  partial: { label: 'Partial match', variant: 'warning' },
}
