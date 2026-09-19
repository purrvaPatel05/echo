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

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`/api${path}`, {
    ...init,
    headers: { 'Content-Type': 'application/json', ...init?.headers },
  })
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
