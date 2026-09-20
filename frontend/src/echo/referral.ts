import type { Referral, ReferralStatus, Urgency } from './types'

export const STATUS_LABEL: Record<ReferralStatus, string> = {
  awaiting_approval: 'Awaiting your approval',
  awaiting_patient: 'Awaiting patient',
  scheduled: 'Scheduled',
}

export const URGENCY_LABEL: Record<Urgency, string> = {
  routine: 'Routine',
  soon: 'Soon',
  urgent: 'Urgent',
}

export type ReferralFilter = 'active' | 'scheduled' | 'awaiting_patient' | 'needs_attention'

export const FILTERS: { key: ReferralFilter; label: string; alert?: boolean }[] = [
  { key: 'active', label: 'Active' },
  { key: 'scheduled', label: 'Scheduled' },
  { key: 'awaiting_patient', label: 'Awaiting Patient' },
  { key: 'needs_attention', label: 'Needs Attention', alert: true },
]

const matchers: Record<ReferralFilter, (r: Referral) => boolean> = {
  active: (r) => r.status !== 'scheduled',
  scheduled: (r) => r.status === 'scheduled',
  awaiting_patient: (r) => r.status === 'awaiting_patient',
  needs_attention: (r) => r.attention !== null,
}

export const matchesFilter = (r: Referral, f: ReferralFilter) => matchers[f](r)

/** The single thing the physician should do next on this referral. */
export function nextAction(r: Referral): string {
  if (r.attention) return r.attention.action
  switch (r.status) {
    case 'awaiting_approval':
      return 'Review matches'
    case 'awaiting_patient':
      return 'Waiting on patient'
    case 'scheduled':
      return 'View appointment'
  }
}

export const initials = (name: string) =>
  name
    .replace(/^Dr\.?\s+/i, '')
    .split(/\s+/)
    .map((w) => w[0])
    .slice(0, 2)
    .join('')
    .toUpperCase()

export const formatDate = (iso: string) =>
  new Date(iso).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })

/** "Tue, Sep 22 · 10:30 AM": how appointment times read across Matches, Approval and Booking. */
export function formatSlotShort(iso: string): string {
  const d = new Date(iso)
  const day = d.toLocaleDateString('en-US', { weekday: 'short', month: 'short', day: 'numeric' })
  const time = d.toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit' })
  return `${day} · ${time}`
}

/** "Sep 19 · 10:42 AM": when something happened. */
export function formatStamp(iso: string): string {
  const d = new Date(iso)
  const day = d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' })
  const time = d.toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit' })
  return `${day} · ${time}`
}

const sameDay = (a: Date, b: Date) => a.toDateString() === b.toDateString()

/** Conversation list time: "10:52 AM" for today, otherwise "Sep 18". */
export function formatListTime(iso: string): string {
  const d = new Date(iso)
  return sameDay(d, new Date()) ? d.toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit' }) : formatDate(iso)
}

/** Day divider inside a conversation: "Today" or "Sep 18". */
export const dayLabel = (iso: string) => (sameDay(new Date(iso), new Date()) ? 'Today' : formatDate(iso))
