import type { Patient, Physician, Referral, ReferralOptions, SpecialistSummary, TimelineEvent, TimelineKind } from '@/echo/types'

const HOUR = 3_600_000
const DAY = 24 * HOUR

// Dates are relative to "now" so the demo always looks current.
const ago = (ms: number) => new Date(Date.now() - ms).toISOString()
const fromNow = (ms: number) => new Date(Date.now() + ms).toISOString()

/** Build a timeline from [kind, ms-ago] pairs, oldest first. */
const timeline = (...steps: [TimelineKind, number][]): TimelineEvent[] =>
  steps.map(([kind, msAgo]) => ({ kind, at: ago(msAgo) }))

/** Patient records the physician can pick from when creating a referral. */
export const PATIENTS: Patient[] = [
  { id: 'p_1', name: 'Alex Johnson', age: 47, sex: 'M', insurance: 'Blue Cross Blue Shield', location: 'Roanoke, VA' },
  { id: 'p_2', name: 'Maria Gonzalez', age: 62, sex: 'F', insurance: 'Aetna', location: 'Salem, VA' },
  { id: 'p_3', name: 'Daniel Kim', age: 34, sex: 'M', insurance: 'Cigna', location: 'Blacksburg, VA' },
  { id: 'p_4', name: 'Linda Brooks', age: 58, sex: 'F', insurance: 'Medicare', location: 'Roanoke, VA' },
  { id: 'p_5', name: 'Robert Hayes', age: 71, sex: 'M', insurance: 'Medicare', location: 'Vinton, VA' },
  { id: 'p_6', name: 'Sofia Ramirez', age: 29, sex: 'F', insurance: 'UnitedHealthcare', location: 'Floyd, VA' },
  { id: 'p_7', name: 'Tom Becker', age: 52, sex: 'M', insurance: 'Aetna', location: 'Roanoke, VA' },
  { id: 'p_8', name: 'Grace Liu', age: 41, sex: 'F', insurance: 'Cigna', location: 'Christiansburg, VA' },
  { id: 'p_9', name: 'Omar Haddad', age: 66, sex: 'M', insurance: 'Medicare', location: 'Salem, VA' },
  { id: 'p_10', name: 'Emily Carter', age: 38, sex: 'F', insurance: 'Aetna', location: 'Roanoke, VA' },
]

const patient = (id: string): Patient => PATIENTS.find((p) => p.id === id)!

export const PHYSICIAN: Physician = {
  id: 'u_1',
  name: 'Dr. Alex Rivera',
  specialty: 'Family Medicine',
  organization: 'Roanoke Primary Care',
}

const nair: SpecialistSummary = {
  id: 'sp_nair',
  name: 'Dr. Priya Nair',
  specialty: 'Cardiology',
  subspecialty: 'Heart failure',
  organization: 'VCU Medical Center',
}
const okafor: SpecialistSummary = {
  id: 'sp_okafor',
  name: 'Dr. Sofia Okafor',
  specialty: 'Neurology',
  subspecialty: 'Migraine',
  organization: 'Duke University Hospital',
}
const marcusChen: SpecialistSummary = {
  id: 'sp_mchen',
  name: 'Dr. Marcus Chen',
  specialty: 'Oncology',
  subspecialty: 'Breast cancer',
  organization: 'UVA Cancer Center',
}
const webb: SpecialistSummary = {
  id: 'sp_webb',
  name: 'Dr. Marcus Webb',
  specialty: 'Orthopedics',
  subspecialty: 'Spine',
  organization: 'Carilion Orthopedics',
}

export const seedReferrals = (): Referral[] => [
  {
    id: 'ref_1',
    patient: patient('p_1'),
    reason: 'Knee pain, suspected meniscal tear',
    details: 'Right knee pain for 6 weeks after a twisting injury. Locking and swelling on stairs. Positive McMurray test. MRI pending.',
    preferredDistanceMiles: 25,
    specialty: 'Orthopedics',
    subspecialty: 'Knee',
    urgency: 'soon',
    status: 'awaiting_approval',
    createdAt: ago(2 * HOUR),
    specialist: null,
    appointmentAt: null,
    attention: null,
    patientConfirmation: { status: 'pending', respondedAt: null },
    timeline: timeline(['created', 2 * HOUR], ['matches_found', 2 * HOUR - 60_000]),
  },
  {
    id: 'ref_2',
    patient: patient('p_2'),
    reason: 'Exertional dyspnea and edema, suspected heart failure',
    details: 'Progressive shortness of breath over 3 weeks with bilateral leg edema. Elevated BNP. Echo shows reduced EF.',
    preferredDistanceMiles: 25,
    specialty: 'Cardiology',
    subspecialty: 'Heart failure',
    urgency: 'urgent',
    status: 'scheduled',
    createdAt: ago(3 * DAY),
    specialist: nair,
    appointmentAt: fromNow(3 * DAY),
    attention: null,
    patientConfirmation: { status: 'confirmed', respondedAt: ago(2 * DAY - 2 * HOUR) },
    timeline: timeline(
      ['created', 3 * DAY],
      ['matches_found', 3 * DAY - 60_000],
      ['specialist_selected', 3 * DAY - 20 * 60_000 + 60_000],
      ['approved', 3 * DAY - 20 * 60_000],
      ['sent_to_patient', 3 * DAY - 21 * 60_000],
      ['patient_viewed', 2 * DAY],
      ['scheduled', 2 * DAY - HOUR],
    ),
  },
  {
    id: 'ref_3',
    patient: patient('p_3'),
    reason: 'Persistent migraines with aura',
    details: 'Migraines with visual aura, 3-4 per month for 6 months, not responding to first-line treatment.',
    preferredDistanceMiles: 25,
    specialty: 'Neurology',
    subspecialty: 'Migraine',
    urgency: 'routine',
    status: 'awaiting_patient',
    createdAt: ago(2 * DAY),
    specialist: okafor,
    appointmentAt: null,
    attention: null,
    patientConfirmation: { status: 'pending', respondedAt: null },
    timeline: timeline(
      ['created', 2 * DAY],
      ['matches_found', 2 * DAY - 60_000],
      ['specialist_selected', 2 * DAY - 30 * 60_000 + 60_000],
      ['approved', 2 * DAY - 30 * 60_000],
      ['sent_to_patient', 2 * DAY - 31 * 60_000],
    ),
  },
  {
    id: 'ref_4',
    patient: patient('p_4'),
    reason: 'Abnormal screening mammogram',
    details: 'BI-RADS 4 finding on screening mammogram. Needs diagnostic workup and biopsy consideration.',
    preferredDistanceMiles: 25,
    specialty: 'Oncology',
    subspecialty: 'Breast cancer',
    urgency: 'urgent',
    status: 'awaiting_patient',
    createdAt: ago(6 * DAY),
    specialist: marcusChen,
    appointmentAt: null,
    attention: { reason: "Patient hasn't responded in 5 days", action: 'Contact patient' },
    patientConfirmation: { status: 'pending', respondedAt: null },
    timeline: timeline(
      ['created', 6 * DAY],
      ['matches_found', 6 * DAY - 60_000],
      ['specialist_selected', 5 * DAY + 60_000],
      ['approved', 5 * DAY],
      ['sent_to_patient', 5 * DAY - 60_000],
    ),
  },
  {
    id: 'ref_5',
    patient: patient('p_5'),
    reason: 'New-onset atrial fibrillation',
    details: 'Palpitations for 2 days. ECG confirms atrial fibrillation with rapid ventricular response.',
    preferredDistanceMiles: 25,
    specialty: 'Cardiology',
    subspecialty: 'Arrhythmia',
    urgency: 'urgent',
    status: 'awaiting_approval',
    createdAt: ago(1 * DAY),
    specialist: nair,
    appointmentAt: null,
    attention: { reason: 'Selected appointment is no longer available', action: 'Choose another slot' },
    patientConfirmation: { status: 'pending', respondedAt: null },
    timeline: timeline(['created', 1 * DAY], ['matches_found', 1 * DAY - 60_000], ['specialist_selected', 1 * DAY - 120_000]),
  },
  {
    id: 'ref_6',
    patient: patient('p_6'),
    reason: 'Recurrent seizures, first evaluation',
    details: 'Two witnessed seizures in the past month. No prior neurologic history. Normal CT head.',
    preferredDistanceMiles: 25,
    specialty: 'Neurology',
    subspecialty: 'Epilepsy',
    urgency: 'urgent',
    status: 'awaiting_approval',
    createdAt: ago(4 * HOUR),
    specialist: null,
    appointmentAt: null,
    attention: { reason: 'No strong match within 25 miles', action: 'Expand search' },
    patientConfirmation: { status: 'pending', respondedAt: null },
    timeline: timeline(['created', 4 * HOUR]),
  },
  {
    id: 'ref_7',
    patient: patient('p_7'),
    reason: 'Chronic low back pain, failed conservative therapy',
    details: 'Low back pain for 9 months. No improvement after physical therapy and NSAIDs. No red-flag symptoms.',
    preferredDistanceMiles: 25,
    specialty: 'Orthopedics',
    subspecialty: 'Spine',
    urgency: 'routine',
    status: 'scheduled',
    createdAt: ago(8 * DAY),
    specialist: webb,
    appointmentAt: fromNow(6 * DAY),
    attention: null,
    patientConfirmation: { status: 'pending', respondedAt: null },
    timeline: timeline(
      ['created', 8 * DAY],
      ['matches_found', 8 * DAY - 60_000],
      ['specialist_selected', 7 * DAY + 60_000],
      ['approved', 7 * DAY],
      ['sent_to_patient', 7 * DAY - 60_000],
      ['patient_viewed', 6 * DAY],
      ['scheduled', 6 * DAY - HOUR],
    ),
  },
]

export const REFERRAL_OPTIONS: ReferralOptions = {
  specialties: [
    { name: 'Cardiology', subspecialties: ['Arrhythmia', 'Heart failure', 'Interventional'] },
    { name: 'Neurology', subspecialties: ['Epilepsy', 'Migraine', 'Movement disorders'] },
    { name: 'Oncology', subspecialties: ['Breast cancer', 'Lung cancer', 'Lymphoma'] },
    { name: 'Orthopedics', subspecialties: ['Hip', 'Knee', 'Shoulder', 'Spine', 'Sports medicine'] },
  ],
  insurers: ['Aetna', 'Blue Cross Blue Shield', 'Cigna', 'Medicaid', 'Medicare', 'UnitedHealthcare'],
  distancesMiles: [10, 25, 50, 100],
}
