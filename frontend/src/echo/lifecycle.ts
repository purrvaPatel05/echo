import { formatSlotShort, formatStamp } from './referral'
import type { Referral, TimelineKind } from './types'

export type TimelineState = 'done' | 'current' | 'waiting' | 'attention'

export interface TimelineRow {
  id: 'created' | 'analysis' | 'specialist' | 'approved' | 'sent' | 'scheduled' | 'patient'
  title: string
  time: string // "Sep 19 · 10:42 AM" or "Not yet"
  detail: string
  state: TimelineState
  /** The word shown with the state: Complete, Current, Waiting, Confirmed or Declined. Never color alone. */
  status: string
}

/**
 * The referral lifecycle as the physician reads it. Built from the referral's timeline events plus its patient
 * confirmation. Note the UI names `matches_found` "Analysis completed": the backend event keeps its name.
 */
export function buildTimeline(r: Referral): TimelineRow[] {
  const at = (kind: TimelineKind) => r.timeline.find((e) => e.kind === kind)?.at
  const conf = r.patientConfirmation

  const steps: { key: TimelineRow['id']; title: string; when: string | undefined; detail: string }[] = [
    { key: 'created', title: 'Referral created', when: at('created'), detail: 'You' },
    { key: 'analysis', title: 'Analysis completed', when: at('matches_found'), detail: 'Matches ready' },
    { key: 'specialist', title: 'Specialist selected', when: at('specialist_selected'), detail: r.specialist?.name ?? 'Not selected' },
    { key: 'approved', title: 'Approved', when: at('approved'), detail: 'You' },
    { key: 'sent', title: 'Sent to patient', when: at('sent_to_patient'), detail: r.patient.name },
    { key: 'scheduled', title: 'Scheduled', when: at('scheduled'), detail: r.appointmentAt ? formatSlotShort(r.appointmentAt) : 'Not booked' },
    {
      key: 'patient',
      title: 'Patient confirmation',
      when: conf.status === 'pending' ? undefined : (conf.respondedAt ?? at(conf.status === 'confirmed' ? 'patient_confirmed' : 'patient_declined')),
      detail: r.patient.name,
    },
  ]

  let currentAssigned = false
  return steps.map((s) => {
    const isPatient = s.key === 'patient'
    if (isPatient && conf.status === 'declined') {
      return { id: s.key, title: s.title, time: s.when ? formatStamp(s.when) : 'Not yet', detail: s.detail, state: 'attention', status: 'Declined' }
    }
    const done = isPatient ? conf.status === 'confirmed' : !!s.when
    if (done) {
      return {
        id: s.key,
        title: s.title,
        time: s.when ? formatStamp(s.when) : 'Not yet',
        detail: s.detail,
        state: 'done',
        status: isPatient ? 'Confirmed' : 'Complete',
      }
    }
    // The first step that isn't done is the current one; everything after it is waiting.
    const state: TimelineState = currentAssigned ? 'waiting' : 'current'
    currentAssigned = true
    return { id: s.key, title: s.title, time: 'Not yet', detail: s.detail, state, status: state === 'current' ? 'Current' : 'Waiting' }
  })
}

export interface LifecycleBadgeInfo {
  variant: 'info' | 'success' | 'warning'
  label: string
  icon: 'clipboard' | 'hourglass' | 'check' | 'alert'
}

/** The referral's status as shown on the tracking and confirmation screens. */
export function lifecycleBadge(r: Referral): LifecycleBadgeInfo {
  if (r.patientConfirmation.status === 'confirmed') return { variant: 'success', label: 'Confirmed', icon: 'check' }
  if (r.patientConfirmation.status === 'declined') return { variant: 'warning', label: 'Declined', icon: 'alert' }
  if (r.status === 'awaiting_approval') return { variant: 'warning', label: 'Awaiting your approval', icon: 'clipboard' }
  return { variant: 'info', label: 'Awaiting patient', icon: 'hourglass' }
}
