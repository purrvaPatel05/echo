import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { echoApi } from './api'
import { ReferralNotFoundError, SlotUnavailableError } from './errors'
import type { ApproveInput, ConsultThread, MatchSearchOptions, StartConsultInput, TrialSearchOptions } from './types'

export const useEchoMe = () => useQuery({ queryKey: ['echo', 'me'], queryFn: echoApi.me })
export const useEchoReferrals = () => useQuery({ queryKey: ['echo', 'referrals'], queryFn: echoApi.referrals })
export const useEchoPatients = () => useQuery({ queryKey: ['echo', 'patients'], queryFn: echoApi.patients })
export const useReferralOptions = () =>
  useQuery({ queryKey: ['echo', 'referral-options'], queryFn: echoApi.referralOptions })

export function useCreateEchoReferral() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: echoApi.createReferral,
    onSuccess: () => qc.invalidateQueries({ queryKey: ['echo', 'referrals'] }),
  })
}

export const useEchoReferral = (id: string) =>
  // One retry: a wrong id shouldn't leave the page spinning through React Query's default three.
  useQuery({ queryKey: ['echo', 'referral', id], queryFn: () => echoApi.referral(id), retry: 1 })

/** Polls the analysis snapshot while it is running; stops once it completes or fails. */
export const useAnalysis = (referralId: string) =>
  useQuery({
    queryKey: ['echo', 'analysis', referralId],
    queryFn: () => echoApi.analysis(referralId),
    retry: 1,
    refetchInterval: (query) => (query.state.data?.status === 'running' ? 700 : false),
  })

export function useRetryAnalysis(referralId: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: () => echoApi.retryAnalysis(referralId),
    onSuccess: (analysis) => qc.setQueryData(['echo', 'analysis', referralId], analysis),
  })
}

/**
 * Specialist matches for a referral. No automatic retry: a failure shows the error state, and "Try again"
 * is the physician's call. Changing `options` (wider distance, partial matches) is a new query.
 */
export const useMatches = (referralId: string, options: MatchSearchOptions) =>
  useQuery({
    queryKey: ['echo', 'matches', referralId, options],
    queryFn: () => echoApi.matches(referralId, options),
    retry: false,
  })

/** A specialist's open slots for the Appointment select on the approval screen. */
export const useSpecialistSlots = (specialistId: string) =>
  useQuery({
    queryKey: ['echo', 'slots', specialistId],
    queryFn: () => echoApi.slots(specialistId),
    enabled: !!specialistId,
  })

/**
 * Approve & Book. On success the referral cache is replaced with the scheduled referral; if the slot was taken,
 * the slot list is refetched so the physician can pick another currently open time. No automatic retry:
 * a failed booking is the physician's call to try again.
 */
export function useApprove(referralId: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (input: ApproveInput) => echoApi.approve(referralId, input),
    onSuccess: (referral) => {
      qc.setQueryData(['echo', 'referral', referralId], referral)
      qc.invalidateQueries({ queryKey: ['echo', 'referrals'] })
      qc.invalidateQueries({ queryKey: ['echo', 'slots'] })
    },
    onError: (error) => {
      if (error instanceof SlotUnavailableError) qc.invalidateQueries({ queryKey: ['echo', 'slots'] })
    },
  })
}

/**
 * The referral for the status screens (Patient Confirmation, Referral Tracking). Always refetches when the screen
 * opens, since the patient's response can change between visits. An unknown id (`ReferralNotFoundError`) is not
 * retried; any other failure gets one retry and then shows the error state with a manual "Try again".
 */
export const useReferralStatus = (id: string) =>
  useQuery({
    queryKey: ['echo', 'referral', id],
    queryFn: () => echoApi.referral(id),
    refetchOnMount: 'always',
    retry: (count, error) => !(error instanceof ReferralNotFoundError) && count < 1,
  })

/** Saves the chosen specialist as the physician moves from Matches to Approval, so Tracking can show it. */
export function useSelectSpecialist(referralId: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (specialistId: string) => echoApi.selectSpecialist(referralId, specialistId),
    onSuccess: (referral) => {
      qc.setQueryData(['echo', 'referral', referralId], referral)
      qc.invalidateQueries({ queryKey: ['echo', 'referrals'] })
    },
  })
}

export const useColleagues = () => useQuery({ queryKey: ['echo', 'colleagues'], queryFn: echoApi.colleagues })

/** The conversation list. Always refetches when opened: a colleague may have answered since the last visit. */
export const useEchoConsults = () =>
  useQuery({
    queryKey: ['echo', 'consults'],
    queryFn: echoApi.consults,
    refetchOnMount: 'always',
    retry: false,
    // New replies appear without a reload. Stops while the list is in an error state.
    refetchInterval: (q) => (q.state.status === 'error' ? false : 5000),
  })

/** One conversation. No automatic retry: a failure shows the error state and "Try again" is the physician's call. */
export const useConsultThread = (id: string | undefined) =>
  useQuery({
    queryKey: ['echo', 'consult', id],
    queryFn: () => echoApi.consultThread(id ?? ''),
    enabled: !!id,
    refetchOnMount: 'always',
    retry: false,
    // While I'm waiting on a reply, look for it every few seconds.
    refetchInterval: (q) => (q.state.status !== 'error' && q.state.data?.status === 'pending' ? 3000 : false),
  })

const putThread = (qc: ReturnType<typeof useQueryClient>, thread: ConsultThread) => {
  qc.setQueryData(['echo', 'consult', thread.id], thread)
  qc.invalidateQueries({ queryKey: ['echo', 'consults'] })
}

/** Start a conversation. On success the new conversation is cached; a failure keeps the form as typed. */
export function useStartConsult() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (input: StartConsultInput) => echoApi.startConsult(input),
    onSuccess: (t) => putThread(qc, t),
  })
}

/** Send a message in a conversation. No automatic retry: a failed send shows "Not sent" with Retry. */
export function useSendConsultMessage(threadId: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (text: string) => echoApi.sendConsultMessage(threadId, text),
    onSuccess: (t) => putThread(qc, t),
  })
}

/** What the trial search uses. Loads faster than the results so the criteria card can show while they load. */
export const useTrialCriteria = (referralId: string, options: TrialSearchOptions) =>
  useQuery({
    queryKey: ['echo', 'trial-criteria', referralId, options],
    queryFn: () => echoApi.trialCriteria(referralId, options),
    retry: false,
  })

/** Trials for a referral. No automatic retry; changing `options` (widen location, all statuses) is a new query. */
export const useTrials = (referralId: string, options: TrialSearchOptions) =>
  useQuery({
    queryKey: ['echo', 'trials', referralId, options],
    queryFn: () => echoApi.trials(referralId, options),
    retry: false,
  })
