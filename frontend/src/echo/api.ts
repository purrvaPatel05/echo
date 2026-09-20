import { mockEchoApi } from '@/mock/echoApi'
import { httpEchoApi } from './http'
import type {
  Analysis,
  ApproveInput,
  Colleague,
  ConsultSummary,
  ConsultThread,
  MatchesResult,
  MatchSearchOptions,
  NewReferralInput,
  Patient,
  Physician,
  Referral,
  ReferralOptions,
  StartConsultInput,
  Slot,
  TrialCriteria,
  TrialSearchOptions,
  TrialsResult,
} from './types'

/** Everything the ECHO screens need from the backend. Grows as screens are built. */
export interface EchoApi {
  me(): Promise<Physician>
  referrals(): Promise<Referral[]>
  /** Patient records the physician can pick from when creating a referral. */
  patients(): Promise<Patient[]>
  /** Specialties, insurers and distance choices for the referral form. */
  referralOptions(): Promise<ReferralOptions>
  createReferral(input: NewReferralInput): Promise<Referral>
  /** Rejects with `ReferralNotFoundError` for an unknown id. */
  referral(id: string): Promise<Referral>
  /** Current state of each analysis check. Poll until `status` is `complete` or `error`. */
  analysis(referralId: string): Promise<Analysis>
  /** Re-run a failed analysis and return the fresh snapshot. */
  retryAnalysis(referralId: string): Promise<Analysis>
  /** Ranked specialist matches with per-factor evidence. Empty `matches` means nothing qualified. */
  matches(referralId: string, options?: MatchSearchOptions): Promise<MatchesResult>
  /** A specialist's currently open appointment slots, earliest first. */
  slots(specialistId: string): Promise<Slot[]>
  /**
   * The physician's explicit approval: books the slot and returns the updated (scheduled) referral.
   * Rejects with `SlotUnavailableError` if the slot was taken; any other rejection is a generic failure.
   */
  approve(referralId: string, input: ApproveInput): Promise<Referral>
  /** Records the physician's choice of specialist (before approval) and returns the updated referral. */
  selectSpecialist(referralId: string, specialistId: string): Promise<Referral>

  /** Colleagues the physician can send a consult to. */
  colleagues(): Promise<Colleague[]>
  /** My conversations (started by me or by a colleague), newest activity first. */
  consults(): Promise<ConsultSummary[]>
  /** One conversation with all its messages. Rejects with `ConsultNotFoundError` for an unknown id. */
  consultThread(id: string): Promise<ConsultThread>
  /** Starts a conversation (the physician's explicit action). A referral is optional. */
  startConsult(input: StartConsultInput): Promise<ConsultThread>
  /** Adds a message to a conversation and returns the updated conversation. */
  sendConsultMessage(threadId: string, text: string): Promise<ConsultThread>

  /** What the trial search uses for this referral and options. Cheap: shown while the results load. */
  trialCriteria(referralId: string, options?: TrialSearchOptions): Promise<TrialCriteria>
  /** Trials to review, nearest first. Empty `trials` is a normal result. */
  trials(referralId: string, options?: TrialSearchOptions): Promise<TrialsResult>
}

// Mock is the default. Set VITE_USE_MOCK=false in frontend/.env to call the real backend.
const useMock = import.meta.env.VITE_USE_MOCK !== 'false'

/** True when the ECHO screens run on the in-browser mock: one built-in physician, no sign-in. */
export const usingMock = useMock

export const echoApi: EchoApi = useMock ? mockEchoApi : httpEchoApi
