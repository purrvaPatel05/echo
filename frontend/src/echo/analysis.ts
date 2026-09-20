import { URGENCY_LABEL } from './referral'
import type { Analysis, AnalysisCheckKey, Referral } from './types'

/** Copy for each check, from the Figma "Analysis step" list. Order comes from the API, not from here. */
export const CHECK_COPY: Record<AnalysisCheckKey, { title: string; description: string; failedLabel: string }> = {
  clinical_fit: {
    title: 'Clinical fit',
    description: 'Case vs. specialty',
    failedLabel: 'clinical fit',
  },
  insurance: {
    title: 'Insurance',
    description: 'Plan accepted',
    failedLabel: 'insurance',
  },
  distance: {
    title: 'Distance',
    description: 'Travel from patient',
    failedLabel: 'distance',
  },
  urgency: {
    title: 'Urgency',
    description: 'Requested timeframe',
    failedLabel: 'urgency',
  },
  availability: {
    title: 'Availability',
    description: 'Earliest openings',
    failedLabel: 'availability',
  },
}

/** The referral input each check is working from, shown on the right of its row. */
export function checkDetail(key: AnalysisCheckKey, r: Referral): string {
  switch (key) {
    case 'clinical_fit':
      return r.subspecialty ? `${r.specialty} · ${r.subspecialty}` : r.specialty
    case 'insurance':
      return r.patient.insurance
    case 'distance':
      return `${r.patient.location} · within ${r.preferredDistanceMiles} miles`
    case 'urgency':
      return URGENCY_LABEL[r.urgency]
    case 'availability':
      return 'Open slots'
  }
}

export const doneCount = (a: Analysis) => a.checks.filter((c) => c.state === 'done').length

const lower = (s: string) => s.charAt(0).toLowerCase() + s.slice(1)

/** "Clinical fit, insurance and distance" from the checks that completed. */
export function completedList(a: Analysis): string {
  const names = a.checks.filter((c) => c.state === 'done').map((c, i) => (i === 0 ? CHECK_COPY[c.key].title : lower(CHECK_COPY[c.key].title)))
  if (names.length <= 1) return names.join('')
  return `${names.slice(0, -1).join(', ')} and ${names[names.length - 1]}`
}
