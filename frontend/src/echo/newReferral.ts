import type { NewReferralInput, Urgency } from './types'

/** Form state for the New Referral screen. All strings so inputs stay controlled. */
export interface NewReferralValues {
  patientId: string
  patientLocation: string
  insurance: string
  specialty: string
  subspecialty: string // '' = any
  distance: string // miles, as a string for the <select>
  urgency: Urgency
  reason: string
  details: string
}

export const emptyValues: NewReferralValues = {
  patientId: '',
  patientLocation: '',
  insurance: '',
  specialty: '',
  subspecialty: '',
  distance: '25',
  urgency: 'routine',
  reason: '',
  details: '',
}

export type RequiredField = 'patientId' | 'patientLocation' | 'insurance' | 'specialty' | 'reason' | 'details'
export type FormErrors = Partial<Record<RequiredField, string>>

/** In on-screen order, so the first error gets focus. */
export const requiredFields: RequiredField[] = [
  'patientId',
  'patientLocation',
  'insurance',
  'specialty',
  'reason',
  'details',
]

/** Short names for the summary alert: "Specialty, referral reason and case details are required." */
export const fieldLabels: Record<RequiredField, string> = {
  patientId: 'patient',
  patientLocation: 'location',
  insurance: 'insurance',
  specialty: 'specialty',
  reason: 'referral reason',
  details: 'case details',
}

const messages: Record<RequiredField, string> = {
  patientId: 'Select a patient.',
  patientLocation: 'Enter a location.',
  insurance: 'Select insurance.',
  specialty: 'Select a specialty.',
  reason: 'Enter a reason.',
  details: 'Add symptoms or history.',
}

export const validateField = (field: RequiredField, values: NewReferralValues): string | undefined =>
  values[field].trim() === '' ? messages[field] : undefined

export function validate(values: NewReferralValues): FormErrors {
  const errors: FormErrors = {}
  for (const f of requiredFields) {
    const message = validateField(f, values)
    if (message) errors[f] = message
  }
  return errors
}

export const toInput = (v: NewReferralValues): NewReferralInput => ({
  patientId: v.patientId,
  patientLocation: v.patientLocation.trim(),
  insurance: v.insurance,
  specialty: v.specialty,
  subspecialty: v.subspecialty || null,
  preferredDistanceMiles: Number(v.distance),
  urgency: v.urgency,
  reason: v.reason.trim(),
  details: v.details.trim(),
})
