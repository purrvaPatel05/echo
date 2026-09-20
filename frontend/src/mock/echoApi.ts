import type { EchoApi } from '@/echo/api'
import type { Analysis, AnalysisCheck, AnalysisCheckKey, Referral } from '@/echo/types'
import { ConsultNotFoundError, ReferralNotFoundError, SlotUnavailableError } from '@/echo/errors'
import { acceptsInsurance, bookSlot, computeMatches, findMockSpecialist, slotsForSpecialist } from './matching'
import { COLLEAGUES, newMessage, replyText, REPLY_DELAY_MS, seedThreads, toSummary, toThread } from './consults'
import { PATIENTS, PHYSICIAN, REFERRAL_OPTIONS, seedReferrals } from './seed'
import { searchTrials, trialCriteriaFor } from './trials'

// In-memory state so later screens (approve, book) can mutate it and the dashboard reflects it.
const referrals = seedReferrals()
const state = {
  referrals,
  threads: seedThreads(),
  consultLoadFailed: false,
  consultSendFailed: false,
  trialFailures: new Set<string>(),
  nextId: 100,
  analyses: new Map<string, { startedAt: number; attempt: number; recorded: boolean; failFirst: boolean }>(),
  matchFailures: new Set<string>(),
  bookingFailures: new Set<string>(),
  referralFailures: new Map<string, number>(),
  slotsTaken: new Set<string>(),
}

const latency = (ms = 250) => new Promise((r) => setTimeout(r, ms))
/** The `?mock=` switch on the current URL (mock-only; the real API has none of these). */
const mockFlag = () => (typeof window !== 'undefined' ? new URLSearchParams(window.location.search).get('mock') : null)
const clone = <T>(v: T): T => structuredClone(v)

/** `?mock=consult-send-error`: the first send (a new consult or a message) fails; retrying succeeds. */
function failFirstSend() {
  if (mockFlag() === 'consult-send-error' && !state.consultSendFailed) {
    state.consultSendFailed = true
    throw new Error('Message could not be sent')
  }
}

/**
 * `?mock=consult-responded`: mock-only stand-in for colleagues answering (there is no colleague-facing screen).
 * Every conversation waiting on a reply gets one, so a waiting chat can be seen turning into an answered one.
 */
/**
 * The demo colleague: a few seconds after a message is sent, a canned reply arrives, marked as a demo reply. It never
 * answers twice in a row, and it is cancelled by a page reload (this state lives in the browser).
 */
function scheduleDemoReply(threadId: string) {
  setTimeout(() => {
    const t = state.threads.find((x) => x.id === threadId)
    if (!t || !t.messages[t.messages.length - 1].fromMe) return
    t.messages.push(newMessage(false, replyText(t.messages.filter((m) => m.fromMe).length), undefined, true))
  }, REPLY_DELAY_MS)
}

function answerPending() {
  if (mockFlag() !== 'consult-responded') return
  for (const t of state.threads) {
    if (t.messages[t.messages.length - 1].fromMe)
      t.messages.push(newMessage(false, replyText(t.messages.filter((m) => m.fromMe).length), undefined, true))
  }
}

// --- Analysis simulation -------------------------------------------------------------------------
// The UI only ever sees a snapshot of per-check states (see `Analysis`); the timer below is purely
// how this mock produces those snapshots. A real backend reports the same shape however it works.
const CHECK_ORDER: AnalysisCheckKey[] = ['clinical_fit', 'insurance', 'distance', 'urgency', 'availability']
const STEP_MS = 900
const MATCH_COUNT = 3

/**
 * Add `?mock=error` to the New Referral URL (or the Analysis URL) to see the failure state: the first attempt
 * fails on the last check and Try again succeeds. Mock-only; the real API has no such switch.
 */
const simulateFailure = () =>
  typeof window !== 'undefined' && new URLSearchParams(window.location.search).get('mock') === 'error'

function snapshot(referralId: string): Analysis {
  const record = state.analyses.get(referralId)
  // Referrals without a record (the seeded ones) were analyzed long ago.
  const elapsed = record ? Date.now() - record.startedAt : Infinity
  const fails = !!record && record.attempt === 1 && (record.failFirst || simulateFailure())

  let firstPending = true
  const checks: AnalysisCheck[] = CHECK_ORDER.map((key, i) => {
    if (elapsed >= (i + 1) * STEP_MS) {
      if (fails && i === CHECK_ORDER.length - 1) return { key, state: 'error' }
      return { key, state: 'done' }
    }
    if (firstPending) {
      firstPending = false
      return { key, state: 'active' }
    }
    return { key, state: 'waiting' }
  })

  const failed = checks.some((c) => c.state === 'error')
  const complete = checks.every((c) => c.state === 'done')
  if (complete && record && !record.recorded) {
    record.recorded = true
    const referral = state.referrals.find((r) => r.id === referralId)
    referral?.timeline.push({ kind: 'matches_found', at: new Date().toISOString() })
  }
  return {
    referralId,
    status: failed ? 'error' : complete ? 'complete' : 'running',
    checks,
    matchCount: complete ? MATCH_COUNT : null,
  }
}

export const mockEchoApi: EchoApi = {
  async me() {
    await latency()
    return clone(PHYSICIAN)
  },
  async referrals() {
    await latency()
    return clone(state.referrals).sort((a, b) => b.createdAt.localeCompare(a.createdAt))
  },
  async patients() {
    await latency()
    return clone(PATIENTS).sort((a, b) => a.name.localeCompare(b.name))
  },
  async referralOptions() {
    await latency()
    return clone(REFERRAL_OPTIONS)
  },
  async createReferral(input) {
    await latency()
    const record = PATIENTS.find((p) => p.id === input.patientId)
    if (!record) throw new Error(`Unknown patient ${input.patientId}`)
    const now = new Date().toISOString()
    const referral: Referral = {
      id: `ref_${state.nextId++}`,
      // Location and insurance may have been edited for this referral, so snapshot the submitted values.
      patient: { ...record, location: input.patientLocation, insurance: input.insurance },
      reason: input.reason,
      details: input.details,
      preferredDistanceMiles: input.preferredDistanceMiles,
      specialty: input.specialty,
      subspecialty: input.subspecialty ?? '',
      urgency: input.urgency,
      status: 'awaiting_approval',
      createdAt: now,
      specialist: null,
      appointmentAt: null,
      attention: null,
      patientConfirmation: { status: 'pending', respondedAt: null },
      timeline: [{ kind: 'created', at: now }],
    }
    state.referrals.push(referral)
    // Mock-confirmed behavior: the referral is saved when analysis begins. Verify against the real backend.
    state.analyses.set(referral.id, {
      startedAt: Date.now(),
      attempt: 1,
      recorded: false,
      failFirst: simulateFailure(),
    })
    return clone(referral)
  },
  async referral(id) {
    await latency()
    const referral = state.referrals.find((r) => r.id === id)
    if (!referral) throw new ReferralNotFoundError()
    const flag = typeof window !== 'undefined' ? new URLSearchParams(window.location.search).get('mock') : null
    // `?mock=referral-error` on the Patient Confirmation or Tracking URL: the first load fails, Try again succeeds.
    // (Fails twice so it survives the hook's single automatic retry and reaches the error state.)
    if (flag === 'referral-error' && (state.referralFailures.get(id) ?? 0) < 2) {
      state.referralFailures.set(id, (state.referralFailures.get(id) ?? 0) + 1)
      throw new Error('Referral unavailable')
    }
    const result = clone(referral)
    // `?mock=patient-confirmed` / `?mock=patient-declined`: mock-only stand-ins for the patient's response on a
    // booked referral. There is no patient-facing screen yet, so this is the only way to see those states.
    if (result.status === 'scheduled' && (flag === 'patient-confirmed' || flag === 'patient-declined')) {
      const at = new Date().toISOString() // after booking, so the timeline stays in order
      const confirmed = flag === 'patient-confirmed'
      result.patientConfirmation = { status: confirmed ? 'confirmed' : 'declined', respondedAt: at }
      result.timeline.push({ kind: confirmed ? 'patient_confirmed' : 'patient_declined', at })
    }
    return result
  },
  async selectSpecialist(referralId, specialistId) {
    await latency()
    const referral = state.referrals.find((r) => r.id === referralId)
    const specialist = findMockSpecialist(specialistId)
    if (!referral) throw new ReferralNotFoundError()
    if (!specialist) throw new Error(`Unknown specialist ${specialistId}`)
    referral.specialist = {
      id: specialist.id,
      name: specialist.name,
      specialty: specialist.specialty,
      subspecialty: referral.subspecialty || specialist.subspecialties[0],
      organization: specialist.organization,
      city: specialist.city,
    }
    // One "specialist selected" event, moved to the latest choice.
    referral.timeline = referral.timeline.filter((e) => e.kind !== 'specialist_selected')
    referral.timeline.push({ kind: 'specialist_selected', at: new Date().toISOString() })
    return clone(referral)
  },
  async analysis(referralId) {
    // No artificial latency: this is polled, and the snapshot is already time-based.
    if (!state.referrals.some((r) => r.id === referralId)) throw new Error(`Referral ${referralId} not found`)
    return snapshot(referralId)
  },
  async retryAnalysis(referralId) {
    await latency()
    const record = state.analyses.get(referralId)
    if (!record) throw new Error(`No analysis to retry for ${referralId}`)
    record.attempt += 1
    record.startedAt = Date.now()
    record.recorded = false
    return snapshot(referralId)
  },
  async matches(referralId, options) {
    await latency()
    const referral = state.referrals.find((r) => r.id === referralId)
    if (!referral) throw new Error(`Referral ${referralId} not found`)
    // `?mock=matches-error` on the Matches URL: the first request fails, Try again succeeds. Mock-only.
    const failOnce =
      typeof window !== 'undefined' && new URLSearchParams(window.location.search).get('mock') === 'matches-error'
    if (failOnce && !state.matchFailures.has(referralId)) {
      state.matchFailures.add(referralId)
      throw new Error('Matches unavailable')
    }
    // Matches exist only once analysis has finished, so record that event even if the analysis screen was skipped.
    if (!referral.timeline.some((e) => e.kind === 'matches_found'))
      referral.timeline.push({ kind: 'matches_found', at: new Date().toISOString() })
    return computeMatches(clone(referral), options)
  },
  async slots(specialistId) {
    await latency()
    return slotsForSpecialist(specialistId)
  },
  async approve(referralId, input) {
    await latency()
    const referral = state.referrals.find((r) => r.id === referralId)
    const specialist = findMockSpecialist(input.specialistId)
    if (!referral || !specialist) throw new Error('Referral or specialist not found')
    const flag = typeof window !== 'undefined' ? new URLSearchParams(window.location.search).get('mock') : null
    // `?mock=book-error` on the Approval URL: the first booking attempt fails, Try again succeeds. Mock-only.
    if (flag === 'book-error' && !state.bookingFailures.has(referralId)) {
      state.bookingFailures.add(referralId)
      throw new Error('Booking unavailable')
    }
    // `?mock=slot-taken`: the first attempt finds the chosen slot already taken by someone else. Mock-only.
    if (flag === 'slot-taken' && !state.slotsTaken.has(referralId)) {
      state.slotsTaken.add(referralId)
      bookSlot(input.slotId)
      throw new SlotUnavailableError()
    }
    const slot = slotsForSpecialist(input.specialistId).find((s) => s.id === input.slotId)
    if (!slot) throw new SlotUnavailableError()

    bookSlot(slot.id)
    const now = new Date().toISOString()
    referral.specialist = {
      id: specialist.id,
      name: specialist.name,
      specialty: specialist.specialty,
      subspecialty: referral.subspecialty || specialist.subspecialties[0],
      organization: specialist.organization,
      city: specialist.city,
    }
    referral.appointmentAt = slot.startsAt
    referral.status = 'scheduled'
    referral.attention = null
    referral.insuranceAccepted = acceptsInsurance(specialist.id, referral.patient.insurance)
    // "Sent to patient" is recorded here only to drive the Next steps list. No message is sent, and whether the
    // real backend notifies the patient is unverified (see docs/echo-api-contract-changes.md).
    if (!referral.timeline.some((e) => e.kind === 'specialist_selected'))
      referral.timeline.push({ kind: 'specialist_selected', at: now })
    referral.patientConfirmation = { status: 'pending', respondedAt: null }
    referral.timeline.push(
      { kind: 'approved', at: now },
      { kind: 'sent_to_patient', at: now },
      { kind: 'scheduled', at: now },
    )
    return clone(referral)
  },
  async colleagues() {
    await latency()
    return clone(COLLEAGUES)
  },
  async consults() {
    await latency()
    const flag = mockFlag()
    // `?mock=consult-load-error` on the Consults URL: the first load fails, Try again succeeds.
    if (flag === 'consult-load-error' && !state.consultLoadFailed) {
      state.consultLoadFailed = true
      throw new Error('Consults unavailable')
    }
    // `?mock=consults-empty`: nothing has been started yet, to see the empty state.
    if (flag === 'consults-empty') return []
    answerPending()
    return state.threads
      .map((t) => toSummary(t, state.referrals))
      .sort((a, b) => b.lastMessage.at.localeCompare(a.lastMessage.at))
  },
  async consultThread(id) {
    await latency()
    answerPending()
    const t = state.threads.find((x) => x.id === id)
    if (!t) throw new ConsultNotFoundError()
    return clone(toThread(t, state.referrals))
  },
  async startConsult(input) {
    await latency()
    if (!COLLEAGUES.some((c) => c.id === input.colleagueId) || !input.text.trim())
      throw new Error('A colleague and a message are required')
    failFirstSend()
    const referralId =
      input.referralId && state.referrals.some((r) => r.id === input.referralId) ? input.referralId : null
    // "Sent" means recorded here. Nothing is delivered to anyone, and nothing claims it was.
    const thread = {
      id: `cn_${state.nextId++}`,
      colleagueId: input.colleagueId,
      referralId,
      messages: [newMessage(true, input.text.trim())],
    }
    state.threads.push(thread)
    scheduleDemoReply(thread.id)
    return clone(toThread(thread, state.referrals))
  },
  async sendConsultMessage(threadId, text) {
    await latency()
    const t = state.threads.find((x) => x.id === threadId)
    if (!t) throw new ConsultNotFoundError()
    if (!text.trim()) throw new Error('Write a message')
    failFirstSend()
    t.messages.push(newMessage(true, text.trim()))
    scheduleDemoReply(t.id)
    return clone(toThread(t, state.referrals))
  },
  async trialCriteria(referralId, options) {
    await latency()
    const referral = state.referrals.find((r) => r.id === referralId)
    if (!referral) throw new ReferralNotFoundError()
    return trialCriteriaFor(referral, options)
  },
  async trials(referralId, options) {
    await latency(900) // slow enough to see the loading state
    const referral = state.referrals.find((r) => r.id === referralId)
    if (!referral) throw new ReferralNotFoundError()
    const flag = mockFlag()
    // `?mock=trials-error` on the Trials URL: the first load fails, Try again succeeds.
    if (flag === 'trials-error' && !state.trialFailures.has(referralId)) {
      state.trialFailures.add(referralId)
      throw new Error('ClinicalTrials.gov unavailable')
    }
    // `?mock=trials-empty`: the default search finds nothing; widening the location or including all statuses finds
    // trials, so the "What you can do" actions can be tried.
    const widened = options?.distanceMiles !== undefined || !!options?.allStatuses
    if (flag === 'trials-empty' && !widened) return { referralId, trials: [] }
    return { referralId, trials: searchTrials(referral, options) }
  },
}
