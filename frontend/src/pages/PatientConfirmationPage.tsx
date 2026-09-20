import { Link, useParams } from 'react-router-dom'
import { DetailList } from '@/components/echo/DetailList'
import { LifecycleBadge } from '@/components/echo/LifecycleBadge'
import { ReferralStatusGate } from '@/components/echo/ReferralStatusGate'
import { TimelineStep } from '@/components/echo/TimelineStep'
import { Alert } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { useReferralStatus } from '@/echo/hooks'
import { buildTimeline } from '@/echo/lifecycle'
import { formatSlotShort, formatStamp } from '@/echo/referral'
import type { Referral } from '@/echo/types'

/** The keys of the timeline shown in the "Patient response" panel. */
const RESPONSE_STEPS = ['approved', 'sent', 'patient'] as const

function StatusAlert({ referral: r }: { referral: Referral }) {
  const c = r.patientConfirmation
  if (c.status === 'confirmed') {
    return (
      <Alert tone="success" title="Patient confirmed">
        {r.patient.name} confirmed{c.respondedAt ? ` on ${formatStamp(c.respondedAt)}` : ''}.
      </Alert>
    )
  }
  if (c.status === 'declined') {
    return (
      <Alert tone="warning" title="Patient declined">
        Needs follow-up. Choose another time or specialist.
      </Alert>
    )
  }
  return (
    <Alert tone="info" title="Waiting for patient">
      {r.patient.name} has not responded yet.
    </Alert>
  )
}

/**
 * Patient Confirmation: focused on the patient's response to a booked appointment. "Sent to patient" is a recorded
 * timeline event only; this screen makes no claim about how, or whether, anything was delivered.
 */
export default function PatientConfirmationPage() {
  const { referralId = '' } = useParams()
  const q = useReferralStatus(referralId)
  const declined = q.data?.patientConfirmation.status === 'declined'

  return (
    <div className="space-y-6">
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
            <li>
              <Link to={`/referral/${referralId}`} className="text-primary hover:underline">
                Referral
              </Link>
            </li>
            <li aria-hidden className="text-muted-foreground">
              /
            </li>
            <li aria-current="page" className="text-muted-foreground">
              Confirmation
            </li>
          </ol>
        </nav>
        <h1 className="text-[1.75rem] leading-9 font-semibold">Patient confirmation</h1>
      </div>

      <ReferralStatusGate
        referral={q.data}
        error={q.error}
        isError={q.isError}
        onRetry={() => q.refetch()}
        loadFailedTitle="Couldn't load the confirmation"
      >
        {(r) => {
          if (r.status !== 'scheduled' || !r.appointmentAt || !r.specialist) {
            return (
              <Alert
                tone="warning"
                title="This referral isn't booked yet"
                action={
                  <Button asChild size="sm" variant="outline">
                    <Link to={`/referral/${r.id}`}>View referral</Link>
                  </Button>
                }
              >
                There is nothing to confirm yet.
              </Alert>
            )
          }
          const s = r.specialist
          const rows = buildTimeline(r).filter((row) => (RESPONSE_STEPS as readonly string[]).includes(row.id))
          return (
            <>
              <StatusAlert referral={r} />
              <div className="grid items-start gap-6 lg:grid-cols-[minmax(0,1fr)_376px]">
                <section aria-labelledby="appointment-heading" className="overflow-hidden rounded-3xl border bg-card">
                  <div className="flex flex-col gap-4 px-6 py-5">
                    <h2 id="appointment-heading" className="text-sm font-semibold">
                      Referral & appointment
                    </h2>
                    <DetailList
                      rows={[
                        ['Patient', `${r.patient.name} · ${r.patient.age}y ${r.patient.sex}`],
                        ['Reason', r.reason],
                        ['Specialty', r.subspecialty ? `${r.specialty} · ${r.subspecialty}` : r.specialty],
                        ['Specialist', s.name],
                        ['When', formatSlotShort(r.appointmentAt)],
                        ['Location', `${s.organization}${s.city ? ` · ${s.city}` : ''}`],
                        ['Status', <LifecycleBadge key="status" referral={r} />],
                      ]}
                    />
                  </div>
                  <div className="flex justify-end gap-2 border-t bg-canvas px-6 py-4">
                    <Button asChild variant={declined ? 'ghost' : 'outline'}>
                      <Link to="/">Back to Dashboard</Link>
                    </Button>
                    <Button asChild variant={declined ? 'outline' : 'default'}>
                      <Link to={`/referral/${r.id}`}>View referral</Link>
                    </Button>
                    {declined && (
                      <Button asChild>
                        <Link to={`/referral/${r.id}/matches`}>Choose another specialist</Link>
                      </Button>
                    )}
                  </div>
                </section>

                <aside aria-labelledby="response-heading" className="rounded-3xl border bg-card p-3">
                  <h2 id="response-heading" className="px-3 py-1 text-sm font-semibold">
                    Patient response
                  </h2>
                  <ol aria-label="Patient response">
                    {rows.map((row) => (
                      <TimelineStep key={row.id} {...row} />
                    ))}
                  </ol>
                </aside>
              </div>
            </>
          )
        }}
      </ReferralStatusGate>
    </div>
  )
}
