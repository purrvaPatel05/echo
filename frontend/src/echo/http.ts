import { request } from '@/api/client'
import type { EchoApi } from './api'
import { ConsultNotFoundError, ReferralNotFoundError, SlotUnavailableError } from './errors'
import type {
  Analysis,
  Colleague,
  ConsultSummary,
  ConsultThread,
  MatchesResult,
  Patient,
  Physician,
  Referral,
  ReferralOptions,
  Slot,
  TrialCriteria,
  TrialSearchOptions,
  TrialsResult,
} from './types'

/** `distanceMiles=any` means any location; omitted means the default radius. */
function trialQuery(options?: TrialSearchOptions) {
  const q = new URLSearchParams()
  if (options?.distanceMiles === null) q.set('distanceMiles', 'any')
  else if (options?.distanceMiles) q.set('distanceMiles', String(options.distanceMiles))
  if (options?.allStatuses) q.set('allStatuses', 'true')
  const qs = q.toString()
  return qs ? `?${qs}` : ''
}

// Real-backend implementation of EchoApi. These paths are the contract we're proposing to the
// backend owners (see docs/echo-api-contract-changes.md); they 404 until the endpoints exist.
export const httpEchoApi: EchoApi = {
  me: () => request<Physician>('/echo/me'),
  referrals: () => request<Referral[]>('/echo/referrals'),
  patients: () => request<Patient[]>('/echo/patients'),
  referralOptions: () => request<ReferralOptions>('/echo/referral-options'),
  createReferral: (input) => request<Referral>('/echo/referrals', { method: 'POST', body: JSON.stringify(input) }),
  referral: async (id) => {
    try {
      return await request<Referral>(`/echo/referrals/${id}`)
    } catch (e) {
      if (e instanceof Error && e.message.startsWith('404')) throw new ReferralNotFoundError()
      throw e
    }
  },
  selectSpecialist: (referralId, specialistId) =>
    request<Referral>(`/echo/referrals/${referralId}/select`, {
      method: 'POST',
      body: JSON.stringify({ specialistId }),
    }),
  analysis: (referralId) => request<Analysis>(`/echo/referrals/${referralId}/analysis`),
  retryAnalysis: (referralId) => request<Analysis>(`/echo/referrals/${referralId}/analysis/retry`, { method: 'POST' }),
  matches: (referralId, options) => {
    const q = new URLSearchParams()
    if (options?.distanceMiles) q.set('distanceMiles', String(options.distanceMiles))
    if (options?.includePartial) q.set('includePartial', 'true')
    const qs = q.toString()
    return request<MatchesResult>(`/echo/referrals/${referralId}/matches${qs ? `?${qs}` : ''}`)
  },
  slots: (specialistId) => request<Slot[]>(`/echo/specialists/${specialistId}/slots`),
  approve: async (referralId, input) => {
    try {
      return await request<Referral>(`/echo/referrals/${referralId}/approve`, {
        method: 'POST',
        body: JSON.stringify(input),
      })
    } catch (e) {
      // `request` throws "409 <body>" for a taken slot; anything else stays a generic failure.
      if (e instanceof Error && e.message.startsWith('409')) throw new SlotUnavailableError()
      throw e
    }
  },
  colleagues: () => request<Colleague[]>('/echo/colleagues'),
  consults: () => request<ConsultSummary[]>('/echo/consults'),
  consultThread: async (id) => {
    try {
      return await request<ConsultThread>(`/echo/consults/${id}`)
    } catch (e) {
      if (e instanceof Error && e.message.startsWith('404')) throw new ConsultNotFoundError()
      throw e
    }
  },
  startConsult: (input) => request<ConsultThread>('/echo/consults', { method: 'POST', body: JSON.stringify(input) }),
  sendConsultMessage: (threadId, text) =>
    request<ConsultThread>(`/echo/consults/${threadId}/messages`, { method: 'POST', body: JSON.stringify({ text }) }),
  trialCriteria: (referralId, options) =>
    request<TrialCriteria>(`/echo/referrals/${referralId}/trials/criteria${trialQuery(options)}`),
  trials: (referralId, options) => request<TrialsResult>(`/echo/referrals/${referralId}/trials${trialQuery(options)}`),
}
