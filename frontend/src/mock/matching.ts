import type {
  MatchFactor,
  MatchSearchOptions,
  MatchesResult,
  MatchStrength,
  Referral,
  Slot,
  SpecialistMatch,
  Urgency,
} from '@/echo/types'

/**
 * Mock matching engine and slot book. The real backend owns this logic (and returns the same shapes);
 * nothing in the UI depends on how strength, ordering or availability is decided here.
 */

interface MockSpecialist {
  id: string
  name: string
  specialty: string
  subspecialties: string[]
  organization: string
  city: string
  /** Fixed distance from a Roanoke-area patient. The mock ignores the patient's actual location. */
  milesAway: number
  accepts: string[]
  /** Days until the earliest open appointment, or null when there are none. */
  daysUntilOpening: number | null
  hour: number
  minute: number
}

const COMMON = ['Aetna', 'Blue Cross Blue Shield', 'Cigna', 'Medicare', 'UnitedHealthcare']

const SPECIALISTS: MockSpecialist[] = [
  { id: 'ms_chen', name: 'Dr. Sarah Chen', specialty: 'Orthopedics', subspecialties: ['Knee'], organization: 'Carilion Orthopedics', city: 'Roanoke, VA', milesAway: 8.4, accepts: COMMON, daysUntilOpening: 3, hour: 10, minute: 30 },
  { id: 'ms_webb', name: 'Dr. Marcus Webb', specialty: 'Orthopedics', subspecialties: ['Sports medicine', 'Spine'], organization: 'Carilion Orthopedics', city: 'Salem, VA', milesAway: 14.2, accepts: COMMON, daysUntilOpening: 5, hour: 14, minute: 0 },
  { id: 'ms_rao', name: 'Dr. Anita Rao', specialty: 'Orthopedics', subspecialties: ['Knee', 'Hip'], organization: 'UVA Orthopedics', city: 'Charlottesville, VA', milesAway: 64.8, accepts: COMMON, daysUntilOpening: 2, hour: 9, minute: 0 },
  { id: 'ms_nguyen', name: 'Dr. Paul Nguyen', specialty: 'Orthopedics', subspecialties: ['Shoulder', 'Hip'], organization: 'LewisGale Medical Center', city: 'Salem, VA', milesAway: 12.7, accepts: COMMON, daysUntilOpening: 9, hour: 11, minute: 15 },

  { id: 'ms_ortiz', name: 'Dr. Elena Ortiz', specialty: 'Cardiology', subspecialties: ['Arrhythmia'], organization: 'Carilion Clinic', city: 'Roanoke, VA', milesAway: 6.1, accepts: COMMON, daysUntilOpening: 2, hour: 8, minute: 30 },
  { id: 'ms_park', name: 'Dr. James Park', specialty: 'Cardiology', subspecialties: ['Heart failure'], organization: 'LewisGale Medical Center', city: 'Salem, VA', milesAway: 12.7, accepts: COMMON, daysUntilOpening: 4, hour: 13, minute: 0 },
  { id: 'ms_nair', name: 'Dr. Priya Nair', specialty: 'Cardiology', subspecialties: ['Heart failure', 'Arrhythmia'], organization: 'VCU Medical Center', city: 'Richmond, VA', milesAway: 168, accepts: COMMON, daysUntilOpening: 6, hour: 9, minute: 45 },

  { id: 'ms_lee', name: 'Dr. Hannah Lee', specialty: 'Neurology', subspecialties: ['Epilepsy'], organization: 'Carilion Clinic', city: 'Roanoke, VA', milesAway: 7.5, accepts: COMMON, daysUntilOpening: 3, hour: 10, minute: 0 },
  { id: 'ms_siddiqui', name: 'Dr. Omar Siddiqui', specialty: 'Neurology', subspecialties: ['Migraine'], organization: 'LewisGale Medical Center', city: 'Salem, VA', milesAway: 13, accepts: COMMON, daysUntilOpening: 8, hour: 15, minute: 30 },

  { id: 'ms_petrova', name: 'Dr. Elena Petrova', specialty: 'Oncology', subspecialties: ['Lymphoma', 'Leukemia'], organization: 'Carilion Clinic', city: 'Roanoke, VA', milesAway: 5.9, accepts: COMMON, daysUntilOpening: 2, hour: 9, minute: 15 },
  { id: 'ms_bennett', name: 'Dr. Laura Bennett', specialty: 'Oncology', subspecialties: ['Breast cancer'], organization: 'Carilion Clinic', city: 'Roanoke, VA', milesAway: 9.2, accepts: COMMON, daysUntilOpening: 4, hour: 11, minute: 0 },
  { id: 'ms_mchen', name: 'Dr. Marcus Chen', specialty: 'Oncology', subspecialties: ['Breast cancer', 'Lung cancer'], organization: 'UVA Cancer Center', city: 'Charlottesville, VA', milesAway: 87, accepts: COMMON, daysUntilOpening: 5, hour: 10, minute: 45 },
]

// --- slots --------------------------------------------------------------------------------------

/** Slot ids taken during this session (by a booking here, or simulated as taken by someone else). */
const booked = new Set<string>()

export const findMockSpecialist = (id: string) => SPECIALISTS.find((s) => s.id === id)
export const bookSlot = (slotId: string) => void booked.add(slotId)
export const acceptsInsurance = (specialistId: string, insurance: string) =>
  !!findMockSpecialist(specialistId)?.accepts.includes(insurance)

/** A specialist's open slots, earliest first: the headline opening plus a few later ones. */
export function slotsForSpecialist(specialistId: string): Slot[] {
  const s = findMockSpecialist(specialistId)
  if (!s || s.daysUntilOpening === null) return []
  const base = s.daysUntilOpening
  const times: [number, number, number][] = [
    [base, s.hour, s.minute],
    [base + 1, 14, 30],
    [base + 2, 9, 0],
    [base + 4, 11, 15],
  ]
  return times
    .map(([days, hour, minute], i) => {
      const d = new Date()
      d.setDate(d.getDate() + days)
      d.setHours(hour, minute, 0, 0)
      return { id: `slot_${s.id}_${i + 1}`, startsAt: d.toISOString() }
    })
    .filter((slot) => !booked.has(slot.id))
}

const daysUntil = (iso: string) => {
  const today = new Date()
  today.setHours(0, 0, 0, 0)
  const target = new Date(iso)
  target.setHours(0, 0, 0, 0)
  return Math.round((target.getTime() - today.getTime()) / 86_400_000)
}

// --- matching -----------------------------------------------------------------------------------

/** Longest wait, in days, that still counts as within the timeframe for each urgency level. */
const MAX_DAYS: Record<Urgency, number> = { routine: 30, soon: 7, urgent: 3 }

/** Specialists farther than this many times the preferred distance are not searched at all. */
const SEARCH_RADIUS_FACTOR = 3

/** `?mock=no-matches` on the Matches URL: nothing qualifies until "Show partial matches" relaxes the criteria. */
const forceNoMatches = () =>
  typeof window !== 'undefined' && new URLSearchParams(window.location.search).get('mock') === 'no-matches'

const dayWord = (n: number) => `${n} ${n === 1 ? 'day' : 'days'}`
const miles = (n: number) => `${Number.isInteger(n) ? n : n.toFixed(1)} miles`

const slotText = (iso: string) => {
  const d = new Date(iso)
  return `${d.toLocaleDateString('en-US', { weekday: 'short', month: 'short', day: 'numeric' })} · ${d.toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit' })}`
}

interface Candidate {
  match: SpecialistMatch
  penalty: number
  unmet: number
  days: number
  miles: number
}

function evaluate(s: MockSpecialist, r: Referral, distancePref: number, noInsurance: boolean): Candidate {
  const sub = r.subspecialty
  const slot = slotsForSpecialist(s.id)[0] ?? null
  const days = slot ? daysUntil(slot.startsAt) : null
  const factors: MatchFactor[] = []
  let penalty = 0
  let unmet = 0

  // Clinical fit
  const theirSub = s.subspecialties[0]
  let fitMet = true
  if (!sub) {
    factors.push({ key: 'clinical_fit', status: 'met', detail: `${s.specialty} specialist` })
  } else if (s.subspecialties.includes(sub)) {
    factors.push({ key: 'clinical_fit', status: 'met', detail: `${sub} subspecialty` })
  } else {
    fitMet = false
    penalty += 1
    factors.push({ key: 'clinical_fit', status: 'partial', detail: `${theirSub}, not ${sub.toLowerCase()}` })
  }

  // Insurance
  const accepted = !noInsurance && s.accepts.includes(r.patient.insurance)
  if (!accepted) unmet += 1
  factors.push({ key: 'insurance', status: accepted ? 'met' : 'unmet', detail: accepted ? 'Accepted' : 'Not accepted' })

  // Distance
  if (s.milesAway <= distancePref) {
    factors.push({ key: 'distance', status: 'met', detail: miles(s.milesAway) })
  } else {
    penalty += 2
    factors.push({ key: 'distance', status: 'partial', detail: `${miles(s.milesAway)} · over ${distancePref}-mile preference` })
  }

  // Availability
  if (slot && days !== null) {
    factors.push({ key: 'availability', status: 'met', detail: `${slotText(slot.startsAt)} (${dayWord(days)})` })
  } else {
    unmet += 1
    factors.push({ key: 'availability', status: 'unmet', detail: 'No open appointments' })
  }

  // Urgency
  if (days !== null && days <= MAX_DAYS[r.urgency]) {
    factors.push({ key: 'urgency', status: 'met', detail: 'Within timeframe' })
  } else {
    penalty += 1
    factors.push({ key: 'urgency', status: days === null ? 'unmet' : 'partial', detail: days === null ? 'No opening' : 'Later than requested' })
  }

  // Strength is a label, decided by how many criteria are only partly met; unmet criteria always make it Partial.
  const strength: MatchStrength = unmet > 0 || penalty > 1 ? 'partial' : penalty === 1 ? 'good' : 'strong'

  // "Why this match?": one short factual sentence, no judgement about what the physician should accept.
  const fit = fitMet ? 'Strong clinical fit' : 'Partial clinical fit'
  const why =
    days !== null
      ? `${fit}; earliest opening in ${dayWord(days)}, ${miles(s.milesAway)} away.`
      : `${fit}; no open appointments, ${miles(s.milesAway)} away.`

  return {
    match: {
      specialist: { id: s.id, name: s.name, specialty: s.specialty, subspecialty: sub && s.subspecialties.includes(sub) ? sub : theirSub, organization: s.organization, city: s.city },
      distanceMiles: s.milesAway,
      strength,
      factors,
      why,
      nextSlot: slot,
    },
    penalty,
    unmet,
    days: days ?? Infinity,
    miles: s.milesAway,
  }
}

const RANK: Record<MatchStrength, number> = { strong: 0, good: 1, partial: 2 }

export function computeMatches(referral: Referral, options: MatchSearchOptions = {}): MatchesResult {
  const distancePref = options.distanceMiles ?? referral.preferredDistanceMiles
  const cutoff = distancePref * SEARCH_RADIUS_FACTOR
  const noInsurance = forceNoMatches()

  const candidates = SPECIALISTS.filter((s) => s.specialty === referral.specialty && s.milesAway <= cutoff)
    .map((s) => evaluate(s, referral, distancePref, noInsurance))
    // Default: no unmet criteria. "Show partial matches" also returns specialists with an unmet criterion.
    .filter((c) => options.includePartial || c.unmet === 0)
    .sort((a, b) => RANK[a.match.strength] - RANK[b.match.strength] || a.days - b.days || a.miles - b.miles)
    .slice(0, 3)

  const label = referral.subspecialty ? `${referral.specialty} · ${referral.subspecialty}` : referral.specialty
  return {
    referralId: referral.id,
    searchDistanceMiles: distancePref,
    matches: candidates.map((c) => c.match),
    noMatchReason:
      candidates.length === 0 ? `No ${label} specialist near ${referral.patient.location} accepts this plan and has an opening.` : null,
  }
}
