import { getToken, UNAUTHORIZED_EVENT } from '@/echo/session'
import type { components } from './schema'

// Types come from ../openapi.json via `npm run gen:api` -- never hand-write API shapes.
export type Schemas = components['schemas']
export type Case = Schemas['Case']
export type CaseCreate = Schemas['CaseCreate']
export type Consult = Schemas['Consult']
export type ConsultMessage = Schemas['ConsultMessage']
export type MatchResult = Schemas['MatchResult']
export type Referral = Schemas['Referral']
export type ReferralCreate = Schemas['ReferralCreate']
export type Slot = Schemas['Slot']
export type Specialist = Schemas['Specialist']
export type User = Schemas['User']

export async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const token = getToken()
  const res = await fetch(`/api${path}`, {
    ...init,
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...init?.headers,
    },
  })
  // A 401 to a request that carried a session means it ended (expired or invalid): the app returns to sign-in.
  if (res.status === 401 && token) window.dispatchEvent(new Event(UNAUTHORIZED_EVENT))
  if (!res.ok) throw new Error(`${res.status} ${await res.text()}`)
  return res.json()
}

const post = <T>(path: string, body?: unknown) =>
  request<T>(path, { method: 'POST', body: body === undefined ? undefined : JSON.stringify(body) })

export const api = {
  me: () => request<User>('/me'),
  specialists: () => request<Specialist[]>('/specialists'),
  slots: (specialistId: string) => request<Slot[]>(`/specialists/${specialistId}/slots`),
  cases: () => request<Case[]>('/cases'),
  case: (id: string) => request<Case>(`/cases/${id}`),
  createCase: (body: CaseCreate) => post<Case>('/cases', body),
  match: (id: string) => post<MatchResult>(`/cases/${id}/match`),
  referrals: () => request<Referral[]>('/referrals'),
  createReferral: (body: ReferralCreate) => post<Referral>('/referrals', body),
  book: (referral_id: string, slot_id: string) => post<Referral>('/appointments', { referral_id, slot_id }),
  consults: () => request<Consult[]>('/consults'),
  messages: (consultId: string) => request<ConsultMessage[]>(`/consults/${consultId}/messages`),
}
