import { Link, useParams } from 'react-router-dom'
import { ActionBar } from '@/components/echo/ActionBar'
import { LifecycleBadge } from '@/components/echo/LifecycleBadge'
import { ReferralShortcuts } from '@/components/echo/ReferralShortcuts'
import { ReferralStatusGate } from '@/components/echo/ReferralStatusGate'
import { TimelineStep } from '@/components/echo/TimelineStep'
import { Button } from '@/components/ui/button'
import { useReferralStatus } from '@/echo/hooks'
import { buildTimeline } from '@/echo/lifecycle'
import { formatSlotShort } from '@/echo/referral'
import type { Referral } from '@/echo/types'

function Cell({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="min-w-0">
      <div className="text-xs text-muted-foreground">{label}</div>
      <div className="text-body-sm">{children}</div>
    </div>
  )
}

/**
 * Referral Tracking: the full lifecycle of one referral. The pinned action bar appears only when the physician has
 * something to do: approve a pending referral, or follow up on a declined one.
 */
function TrackingBody({ referral: r }: { referral: Referral }) {
  const rows = buildTimeline(r)
  const declined = r.patientConfirmation.status === 'declined'
  const awaitingApproval = r.status === 'awaiting_approval' && r.patientConfirmation.status === 'pending'
  const hasBar = declined || awaitingApproval
  const matchesUrl = `/referral/${r.id}/matches`

  return (
    <div className={hasBar ? 'space-y-6 pb-24' : 'space-y-6'}>
      <section
        aria-label="Referral summary"
        className="grid gap-x-6 gap-y-4 rounded-3xl border bg-card p-5 sm:grid-cols-2 lg:grid-cols-3"
      >
        <Cell label="Patient">
          {r.patient.name} · {r.patient.age}y {r.patient.sex}
        </Cell>
        <Cell label="Reason">{r.reason}</Cell>
        <Cell label="Specialty">{r.subspecialty ? `${r.specialty} · ${r.subspecialty}` : r.specialty}</Cell>
        <Cell label="Specialist">{r.specialist?.name ?? 'Not selected'}</Cell>
        <Cell label="Appointment">{r.appointmentAt ? formatSlotShort(r.appointmentAt) : 'Not booked'}</Cell>
        <Cell label="Status">
          <LifecycleBadge referral={r} />
        </Cell>
      </section>

      <section aria-labelledby="timeline-heading" className="rounded-3xl border bg-card p-3">
        <h2 id="timeline-heading" className="px-3 py-2 text-sm font-semibold">
          Timeline
        </h2>
        <ol aria-label="Referral timeline">
          {rows.map((row) => (
            <TimelineStep
              key={row.id}
              {...row}
              titleTo={row.id === 'patient' && r.status === 'scheduled' ? `/referral/${r.id}/confirmation` : undefined}
            />
          ))}
        </ol>
      </section>

      {awaitingApproval && (
        <ActionBar title={r.specialist?.name ?? 'No specialist selected'} detail="Not booked yet.">
          {r.specialist ? (
            <>
              <Button asChild variant="onDark">
                <Link to={matchesUrl}>Choose another specialist</Link>
              </Button>
              <Button asChild>
                <Link to={`/referral/${r.id}/review?specialist=${r.specialist.id}`}>Review and approve</Link>
              </Button>
            </>
          ) : (
            <Button asChild>
              <Link to={matchesUrl}>Review matches</Link>
            </Button>
          )}
        </ActionBar>
      )}
      {declined && (
        <ActionBar title="Follow-up needed" detail="Patient declined the appointment.">
          <Button asChild variant="onDark">
            <Link to="/">Back to Dashboard</Link>
          </Button>
          <Button asChild>
            <Link to={matchesUrl}>Choose another specialist</Link>
          </Button>
        </ActionBar>
      )}
    </div>
  )
}

export default function TrackingPage() {
  const { referralId = '' } = useParams()
  const q = useReferralStatus(referralId)

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div className="space-y-1">
          <nav aria-label="Breadcrumb">
            <ol className="flex items-center gap-1 text-xs">
              <li>
                <Link to="/" className="text-primary hover:underline">
                  Dashboard
                </Link>
              </li>
              <li aria-hidden className="text-muted-foreground">
                /
              </li>
              <li aria-current="page" className="text-muted-foreground">
                Referral
              </li>
            </ol>
          </nav>
          <h1 className="text-[1.75rem] leading-9 font-semibold">Referral</h1>
        </div>
        {q.data && <ReferralShortcuts referralId={referralId} />}
      </div>
      <ReferralStatusGate
        referral={q.data}
        error={q.error}
        isError={q.isError}
        onRetry={() => q.refetch()}
        loadFailedTitle="Couldn't load the referral"
      >
        {(r) => <TrackingBody referral={r} />}
      </ReferralStatusGate>
    </div>
  )
}
