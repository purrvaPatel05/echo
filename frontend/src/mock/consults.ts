import type {
  Colleague,
  ConsultContext,
  ConsultMessage,
  ConsultReferralRef,
  ConsultSummary,
  ConsultThread,
  Referral,
} from '@/echo/types'

const MIN = 60_000
const HOUR = 60 * MIN
const DAY = 24 * HOUR
const ago = (ms: number) => new Date(Date.now() - ms).toISOString()

export const COLLEAGUES: Colleague[] = [
  { id: 'c_ortiz', name: 'Dr. Daniel Ortiz', specialty: 'Orthopedics', organization: 'Carilion Clinic' },
  { id: 'c_nair', name: 'Dr. Priya Nair', specialty: 'Cardiology', organization: 'VCU Medical Center' },
  { id: 'c_lee', name: 'Dr. Hannah Lee', specialty: 'Neurology', organization: 'Duke University Hospital' },
  { id: 'c_petrova', name: 'Dr. Elena Petrova', specialty: 'Oncology', organization: 'UVA Cancer Center' },
  { id: 'c_shah', name: 'Dr. Nikhil Shah', specialty: 'Radiology', organization: 'Carilion Clinic' },
]

/** What a colleague is given about a case: age, sex, reason and summary. No patient name. */
export const contextFor = (r: Referral): ConsultContext => ({
  age: r.patient.age,
  sex: r.patient.sex,
  reason: r.reason,
  summary: r.details,
})

/** A stored conversation. `fromMe` is relative to the signed-in physician. */
export interface MockThread {
  id: string
  colleagueId: string
  referralId: string | null
  messages: ConsultMessage[]
}

export const REPLY =
  'MRI first is reasonable given the locking and swelling. If it confirms a meniscal tear, referring to a knee surgeon makes sense.'

/** Canned demo replies, the same ones the backend simulator sends. Neutral questions, no medical advice. */
export const REPLIES = [
  'Thanks for sending this. Could you share the most recent results?',
  "That's helpful. How long has this been going on, and has anything changed recently?",
  "Understood. Please send anything new before the visit and I'll review it.",
  'Sounds reasonable to me. Let me know how the patient responds.',
]
export const replyText = (myMessageCount: number) => REPLIES[(Math.max(myMessageCount, 1) - 1) % REPLIES.length]
export const REPLY_DELAY_MS = 3000

let nextMessage = 1
export const newMessage = (
  fromMe: boolean,
  text: string,
  at = new Date().toISOString(),
  simulated = false,
): ConsultMessage => ({
  id: `msg_${nextMessage++}`,
  fromMe,
  text,
  at,
  ...(simulated ? { simulated: true } : {}),
})

/** Conversations on file for the demo. Each is about a seeded referral; a new one can be about none. */
export const seedThreads = (): MockThread[] => [
  {
    id: 'cn_1',
    colleagueId: 'c_ortiz',
    referralId: 'ref_1',
    messages: [
      newMessage(
        true,
        'Second opinion on imaging before referral: MRI first, or refer directly to knee surgery?',
        ago(1 * HOUR),
      ),
    ],
  },
  {
    id: 'cn_2',
    colleagueId: 'c_nair',
    referralId: 'ref_5',
    messages: [
      newMessage(true, 'Rate or rhythm control for a first episode?', ago(1 * DAY + 3 * HOUR)),
      newMessage(
        false,
        'Rate control first, and anticoagulate per CHA2DS2-VASc. Refer if symptoms persist, and I can see him within a week.',
        ago(2 * HOUR),
      ),
    ],
  },
  {
    id: 'cn_3',
    colleagueId: 'c_lee',
    referralId: 'ref_6',
    messages: [newMessage(true, 'Start the workup before the specialist visit?', ago(1 * DAY + 5 * HOUR))],
  },
  {
    id: 'cn_4',
    colleagueId: 'c_petrova',
    referralId: 'ref_4',
    messages: [
      newMessage(true, 'Imaging follow-up sequence before biopsy?', ago(6 * DAY)),
      newMessage(
        false,
        'Diagnostic mammogram with ultrasound first; biopsy only after that.',
        ago(5 * DAY + 20 * HOUR),
      ),
    ],
  },
]

const colleague = (id: string) => COLLEAGUES.find((c) => c.id === id)!

function refFor(t: MockThread, referrals: Referral[]): ConsultReferralRef | null {
  const r = t.referralId ? referrals.find((x) => x.id === t.referralId) : undefined
  return r ? { id: r.id, patientName: r.patient.name, age: r.patient.age, sex: r.patient.sex, reason: r.reason } : null
}

export function toSummary(t: MockThread, referrals: Referral[]): ConsultSummary {
  const last = t.messages[t.messages.length - 1]
  return {
    id: t.id,
    colleague: colleague(t.colleagueId),
    referral: refFor(t, referrals),
    status: last.fromMe ? 'pending' : 'responded',
    lastMessage: { text: last.text, at: last.at, fromMe: last.fromMe },
  }
}

export function toThread(t: MockThread, referrals: Referral[]): ConsultThread {
  const r = t.referralId ? referrals.find((x) => x.id === t.referralId) : undefined
  return { ...toSummary(t, referrals), messages: [...t.messages], sharedContext: r ? contextFor(r) : null }
}
