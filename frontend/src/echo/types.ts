// ECHO frontend view of the API. These are the shapes the UI expects; the mock service in
// src/mock/ returns them today, and the real endpoints should return the same shapes.
// The generated types in src/api/schema.d.ts don't cover these yet.

export type Urgency = 'routine' | 'soon' | 'urgent'

/** Where a referral is in the physician's workflow. */
export type ReferralStatus = 'awaiting_approval' | 'awaiting_patient' | 'scheduled'

export interface Physician {
  id: string
  name: string
  specialty: string
  organization: string
}

export interface Patient {
  id: string
  name: string
  age: number
  sex: 'F' | 'M' | 'X'
  insurance: string
  location: string
}

export interface SpecialistSummary {
  id: string
  name: string
  specialty: string
  subspecialty: string
  organization: string
  city?: string // set once a specialist is chosen (shown as the appointment location)
}

export type TimelineKind =
  | 'created'
  | 'matches_found'
  | 'specialist_selected'
  | 'approved'
  | 'sent_to_patient'
  | 'patient_viewed'
  | 'scheduled'
  | 'patient_confirmed'
  | 'patient_declined'

/** The patient's response to a booked appointment. */
export type PatientConfirmationStatus = 'pending' | 'confirmed' | 'declined'

export interface PatientConfirmation {
  status: PatientConfirmationStatus
  respondedAt: string | null // ISO 8601, set once confirmed or declined
}

export interface TimelineEvent {
  kind: TimelineKind
  at: string // ISO 8601
}

/** Set when a referral is stuck and needs the physician to do something. */
export interface Attention {
  reason: string
  action: string // button label, e.g. "Choose another slot"
}

export interface Referral {
  id: string
  /** Snapshot of the patient at referral time (location/insurance may be edited per referral). */
  patient: Patient
  reason: string
  details: string // symptoms, history, physician notes
  preferredDistanceMiles: number
  specialty: string
  subspecialty: string
  urgency: Urgency
  status: ReferralStatus
  createdAt: string // ISO 8601
  specialist: SpecialistSummary | null // null until the physician picks a match
  appointmentAt: string | null // ISO 8601, only once scheduled
  attention: Attention | null
  /** Whether the booked specialist accepts the patient's insurance. Unset until booked. */
  insuranceAccepted?: boolean
  patientConfirmation: PatientConfirmation
  timeline: TimelineEvent[]
}

export interface SpecialtyOption {
  name: string
  subspecialties: string[]
}

/** Choices offered by the referral form. Served by the backend so they stay in sync with the matching engine. */
export interface ReferralOptions {
  specialties: SpecialtyOption[]
  insurers: string[]
  distancesMiles: number[]
}

/** What the New Referral form submits. */
export interface NewReferralInput {
  patientId: string
  patientLocation: string
  insurance: string
  specialty: string
  subspecialty: string | null
  preferredDistanceMiles: number
  urgency: Urgency
  reason: string
  details: string
}

export type AnalysisCheckKey = 'clinical_fit' | 'insurance' | 'distance' | 'urgency' | 'availability'
export type AnalysisCheckState = 'done' | 'active' | 'waiting' | 'error'
/** running = still working, complete = matches ready, error = a check failed (can be retried). */
export type AnalysisStatus = 'running' | 'complete' | 'error'

export interface AnalysisCheck {
  key: AnalysisCheckKey
  state: AnalysisCheckState
}

/**
 * Snapshot of the analysis for one referral. The UI polls this until `status` is no longer `running`,
 * so it never depends on how long the backend takes or how the backend reports progress.
 */
export interface Analysis {
  referralId: string
  status: AnalysisStatus
  checks: AnalysisCheck[] // in display order
  matchCount: number | null // set once status is `complete`
}

export type MatchFactorKey = 'clinical_fit' | 'insurance' | 'distance' | 'availability' | 'urgency'
/** met = criterion satisfied, partial = satisfied in part (or outside a preference), unmet = not satisfied. */
export type MatchFactorStatus = 'met' | 'partial' | 'unmet'
/** A label, never a number: the UI shows Strong / Good / Partial match. */
export type MatchStrength = 'strong' | 'good' | 'partial'

export interface MatchFactor {
  key: MatchFactorKey
  status: MatchFactorStatus
  detail: string // short factual text shown on the card, e.g. "8.4 miles · Roanoke, VA"
}

export interface Slot {
  id: string
  startsAt: string // ISO 8601
}

export interface SpecialistMatch {
  specialist: SpecialistSummary & { city: string }
  distanceMiles: number
  strength: MatchStrength
  factors: MatchFactor[] // in display order
  /** "Why this match?" Evidence-based and neutral: states facts, never what the physician should accept. */
  why: string
  nextSlot: Slot | null // earliest open appointment
}

export interface MatchSearchOptions {
  /** Override the referral's preferred travel distance (the "Expand the travel distance" action). */
  distanceMiles?: number
  /** Also return specialists who meet most, but not all, criteria (the "Show partial matches" action). */
  includePartial?: boolean
}

export interface MatchesResult {
  referralId: string
  searchDistanceMiles: number // the distance preference actually used
  matches: SpecialistMatch[] // 0-3, already ordered by the matching logic
  /** Why nothing qualified. Set only when `matches` is empty. */
  noMatchReason: string | null
}

/** What Approve & Book submits: the chosen specialist and one of their currently open slots. */
export interface ApproveInput {
  specialistId: string
  slotId: string
}

// --- Physician consult (a chat between two physicians) ----------------------------------------------------

/** A physician the user can ask for input. */
export interface Colleague {
  id: string
  name: string
  specialty: string
  organization: string
}

/** pending = my message is the last one, so I'm waiting. responded = the colleague's message is the last one. */
export type ConsultStatus = 'pending' | 'responded'

/**
 * What a colleague is given about a case: age, sex, reason and summary. Deliberately no patient name.
 * (Mock/demo behavior; real privacy rules are a backend and product decision.)
 */
export interface ConsultContext {
  age: number
  sex: Patient['sex']
  reason: string
  summary: string
}

/** The referral a consult is about, as its sender sees it. A consult does not need one. */
export interface ConsultReferralRef {
  id: string
  patientName: string
  age: number
  sex: Patient['sex']
  reason: string
}

export interface ConsultMessage {
  id: string
  fromMe: boolean
  text: string
  at: string // ISO 8601
  /** A canned reply from the demo colleague, not written by a person. Always labelled "Demo reply". */
  simulated?: boolean
}

/** One row of the conversation list. */
export interface ConsultSummary {
  id: string
  colleague: Colleague
  referral: ConsultReferralRef | null
  status: ConsultStatus
  lastMessage: { text: string; at: string; fromMe: boolean }
}

export interface ConsultThread extends ConsultSummary {
  messages: ConsultMessage[]
  /** Set when a referral is attached: what the colleague is given about it. */
  sharedContext: ConsultContext | null
}

export interface StartConsultInput {
  colleagueId: string
  text: string
  referralId?: string | null
}

// --- Clinical trials ----------------------------------------------------------------------------------------

export type TrialStatus = 'recruiting' | 'not_yet_recruiting' | 'active_not_recruiting'

/** How the physician widens a search that found nothing. Defaults: within 100 miles, recruiting or not yet recruiting. */
export interface TrialSearchOptions {
  /** Search radius in miles; `null` = any location. Omitted = the default radius. */
  distanceMiles?: number | null
  /** Also include trials that are active but no longer recruiting. */
  allStatuses?: boolean
}

/** What the search actually used, as display-ready text. Shown so the physician sees the search is the case's, not a black box. */
export interface TrialCriteria {
  condition: string
  patient: string
  location: string
  status: string
  source: string
  /** The radius in miles the search used, or null for any location (drives the "Widen location" choices). */
  distanceMiles: number | null
  allStatuses: boolean
}

export interface Trial {
  nctId: string
  title: string
  condition: string
  intervention: string
  location: string
  distanceMiles: number | null
  status: TrialStatus
  /** One short factual sentence tying the trial to the recorded condition. No score, no eligibility statement. */
  relevance: string | null
  url: string // ClinicalTrials.gov page
}

export interface TrialsResult {
  referralId: string
  trials: Trial[] // ordered by distance, nearest first
}
