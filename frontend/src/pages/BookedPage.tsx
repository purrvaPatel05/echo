import { CalendarCheck } from 'lucide-react'
import { Link, useParams } from 'react-router-dom'
import { AnalysisStep } from '@/components/echo/AnalysisStep'
import { DetailList } from '@/components/echo/DetailList'
import { LoadingRows } from '@/components/echo/states'
import { Alert } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { useEchoReferral } from '@/echo/hooks'
import { formatSlotShort, formatStamp } from '@/echo/referral'
import type { TimelineKind } from '@/echo/types'

const backToDashboard = (
  <Button asChild variant="outline" size="sm">
    <Link to="/">Back to Dashboard</Link>
  </Button>
)

/** Booking confirmation. Reads the scheduled referral; everything shown comes from the booked referral itself. */
export default function BookedPage() {
  const { referralId = '' } = useParams()
  const { data: r, isError } = useEchoReferral(referralId)

  if (isError) {
    return (
      <Alert tone="destructive" title="We couldn't find that referral" action={backToDashboard}>
        It may have been removed, or the link is wrong.
      </Alert>
    )
  }
  if (!r) return <LoadingRows />
  if (r.status !== 'scheduled' || !r.appointmentAt || !r.specialist) {
    return (
      <Alert tone="warning" title="This referral isn't booked yet" action={backToDashboard}>
        Nothing has been booked.
      </Alert>
    )
  }

  const s = r.specialist
  const when = formatSlotShort(r.appointmentAt)
  const confirmed = r.patientConfirmation.status === 'confirmed'
  const at = (kind: TimelineKind) =>
    kind === 'patient_viewed'
      ? confirmed
        ? (r.patientConfirmation.respondedAt ?? undefined)
        : undefined
      : r.timeline.find((e) => e.kind === kind)?.at
  const steps: { key: TimelineKind; title: string; who: string }[] = [
    { key: 'approved', title: 'Approved', who: 'You' },
    { key: 'sent_to_patient', title: 'Sent to patient', who: r.patient.name },
    { key: 'patient_viewed', title: 'Patient confirmation', who: r.patient.name },
  ]
  const insuranceNote = r.insuranceAccepted === true ? ' · Accepted' : r.insuranceAccepted === false ? ' · Not accepted' : ''

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
            <li aria-current="page" className="text-muted-foreground">
              Booked
            </li>
          </ol>
        </nav>
        <h1 className="text-[1.75rem] leading-9 font-semibold">Referral scheduled</h1>
      </div>

      <Alert tone="success" title="Appointment booked">
        {when} with {s.name}.
      </Alert>

      <div className="grid items-start gap-6 lg:grid-cols-[minmax(0,1fr)_376px]">
        <section aria-labelledby="appointment-heading" className="overflow-hidden rounded-3xl border bg-card">
          <div className="flex flex-col gap-4 px-6 py-5">
            <h2 id="appointment-heading" className="text-sm font-semibold">
              Appointment
            </h2>
            <DetailList
              rows={[
                ['When', when],
                ['Specialist', `${s.name} · ${s.specialty} · ${s.subspecialty}`],
                ['Location', `${s.organization}${s.city ? ` · ${s.city}` : ''}`],
                ['Patient', `${r.patient.name} · ${r.patient.age}y ${r.patient.sex}`],
                ['Insurance', `${r.patient.insurance}${insuranceNote}`],
                [
                  'Status',
                  <Badge key="status" variant="success">
                    <CalendarCheck className="size-3" aria-hidden />
                    Scheduled
                  </Badge>,
                ],
              ]}
            />
          </div>
          <div className="flex justify-end gap-2 border-t bg-canvas px-6 py-4">
            <Button asChild variant="outline">
              <Link to="/">Back to Dashboard</Link>
            </Button>
            <Button asChild>
              <Link to={`/referral/${r.id}`}>View referral</Link>
            </Button>
          </div>
        </section>

        <aside aria-labelledby="next-heading" className="rounded-3xl border bg-card px-5 pt-5 pb-3">
          <h2 id="next-heading" className="mb-2 text-sm font-semibold">
            Next steps
          </h2>
          <ol aria-label="Next steps">
            {steps.map((st) => {
              const time = at(st.key)
              return (
                <AnalysisStep
                  key={st.key}
                  state={time ? 'done' : 'waiting'}
                  title={st.title}
                  description={time ? formatStamp(time) : 'Not yet'}
                  detail={st.who}
                  titleTo={st.key === 'patient_viewed' ? `/referral/${r.id}/confirmation` : undefined}
                />
              )
            })}
          </ol>
        </aside>
      </div>
    </div>
  )
}
