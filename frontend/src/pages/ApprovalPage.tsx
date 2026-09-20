import { useState } from 'react'
import { Link, useNavigate, useParams, useSearchParams } from 'react-router-dom'
import { ActionBar } from '@/components/echo/ActionBar'
import { UrgencyBadge } from '@/components/echo/badges'
import { DetailList } from '@/components/echo/DetailList'
import { MatchFactor } from '@/components/echo/MatchFactor'
import { ReferralShortcuts } from '@/components/echo/ReferralShortcuts'
import { LoadingRows } from '@/components/echo/states'
import { StrengthBadge } from '@/components/echo/StrengthBadge'
import { Alert } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { Dialog } from '@/components/ui/dialog'
import { Field } from '@/components/ui/field'
import { NativeSelect } from '@/components/ui/native-select'
import { SlotUnavailableError } from '@/echo/errors'
import { useApprove, useEchoReferral, useMatches, useSpecialistSlots } from '@/echo/hooks'
import { formatSlotShort } from '@/echo/referral'
import type { MatchSearchOptions } from '@/echo/types'
import { controlA11y } from '@/lib/control-a11y'

/**
 * Review and approve. Receives the selected specialist (and the search that produced the match) from the URL:
 * /referral/:id/review?specialist=ms_chen[&distance=50][&partial=1]. Nothing is booked until the physician clicks
 * Approve & Book here AND confirms in the dialog.
 */
export default function ApprovalPage() {
  const { referralId = '' } = useParams()
  const [params] = useSearchParams()
  const navigate = useNavigate()
  const specialistId = params.get('specialist') ?? ''
  const search: MatchSearchOptions = {}
  if (params.get('distance')) search.distanceMiles = Number(params.get('distance'))
  if (params.get('partial') === '1') search.includePartial = true

  const { data: referral, isError: referralMissing } = useEchoReferral(referralId)
  const matchesQ = useMatches(referralId, search)
  const slotsQ = useSpecialistSlots(specialistId)
  const approve = useApprove(referralId)
  const [chosen, setChosen] = useState<string | null>(null) // null = default to the earliest opening
  const [dialogOpen, setDialogOpen] = useState(false)

  const match = matchesQ.data?.matches.find((m) => m.specialist.id === specialistId)
  const slots = slotsQ.data ?? []
  const requested = chosen ?? match?.nextSlot?.id ?? slots[0]?.id ?? ''
  const slotId = slots.some((s) => s.id === requested) ? requested : '' // a taken slot is no longer valid
  const slot = slots.find((s) => s.id === slotId)

  const unavailable = approve.error instanceof SlotUnavailableError
  const bookingFailed = approve.isError && !unavailable
  const slotsLoaded = slotsQ.isSuccess
  const slotError =
    slotsLoaded && slots.length === 0
      ? 'No open times. Choose another specialist.'
      : unavailable && !slotId
        ? 'Choose another time.'
        : undefined

  const confirm = () =>
    approve.mutate(
      { specialistId, slotId },
      {
        onSuccess: () => navigate(`/referral/${referralId}/booked`),
        onError: (e) => {
          setDialogOpen(false)
          if (e instanceof SlotUnavailableError) setChosen('') // make the physician pick a currently open time
        },
      },
    )

  if (referralMissing) {
    return (
      <Alert
        tone="destructive"
        title="We couldn't find that referral"
        action={
          <Button asChild size="sm" variant="outline">
            <Link to="/">Back to Dashboard</Link>
          </Button>
        }
      >
        It may have been removed, or the link is wrong.
      </Alert>
    )
  }

  const matchesUrl = `/referral/${referralId}/matches`
  const loading = !referral || matchesQ.isLoading || (!!specialistId && slotsQ.isLoading)

  return (
    <div className="space-y-6 pb-24">
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
              <li>
                <Link to={matchesUrl} className="text-primary hover:underline">
                  Matches
                </Link>
              </li>
              <li aria-hidden className="text-muted-foreground">
                /
              </li>
              <li aria-current="page" className="text-muted-foreground">
                Review
              </li>
            </ol>
          </nav>
          <h1 className="text-[1.75rem] leading-9 font-semibold">Review and approve</h1>
        </div>
        {referral && <ReferralShortcuts referralId={referralId} />}
      </div>

      {matchesQ.isError && (
        <Alert
          tone="destructive"
          title="Couldn't load the specialist"
          action={
            <Button size="sm" variant="outline" onClick={() => matchesQ.refetch()}>
              Try again
            </Button>
          }
        >
          Your referral is saved.
        </Alert>
      )}

      {loading && !matchesQ.isError && <LoadingRows />}

      {referral && matchesQ.isSuccess && !match && (
        <Alert
          tone="warning"
          title="We couldn't find that specialist"
          action={
            <Button asChild size="sm" variant="outline">
              <Link to={matchesUrl}>Back to matches</Link>
            </Button>
          }
        >
          Choose a specialist from the matches.
        </Alert>
      )}

      {referral && match && (
        <>
          {bookingFailed ? (
            <Alert tone="destructive" title="Couldn't book the appointment">
              Nothing was booked. Try again.
            </Alert>
          ) : unavailable ? (
            <Alert tone="warning" title="That appointment is no longer available">
              Choose another time or specialist.
            </Alert>
          ) : (
            <Alert tone="info" title="Not booked yet">
              Approving books the appointment.
            </Alert>
          )}

          <div className="grid items-start gap-4 md:grid-cols-2">
            <section aria-labelledby="patient-heading" className="flex flex-col gap-4 rounded-3xl border bg-card p-5">
              <h2 id="patient-heading" className="text-sm font-semibold">
                Patient & referral
              </h2>
              <DetailList
                rows={[
                  ['Patient', `${referral.patient.name} · ${referral.patient.age}y ${referral.patient.sex}`],
                  ['Reason', referral.reason],
                  [
                    'Specialty',
                    referral.subspecialty ? `${referral.specialty} · ${referral.subspecialty}` : referral.specialty,
                  ],
                  ['Urgency', <UrgencyBadge key="urgency" urgency={referral.urgency} />],
                  ['Insurance', referral.patient.insurance],
                ]}
              />
            </section>

            <section aria-labelledby="specialist-heading" className="flex flex-col gap-4 rounded-3xl border bg-card p-5">
              <h2 id="specialist-heading" className="text-sm font-semibold">
                Specialist & appointment
              </h2>
              <Field id="approval-slot" label="Appointment" error={slotError}>
                <NativeSelect
                  value={slotId}
                  disabled={approve.isPending}
                  onChange={(e) => {
                    setChosen(e.target.value)
                    approve.reset() // picking a time clears the previous booking message
                  }}
                  {...controlA11y('approval-slot', slotError)}
                >
                  <option value="">Select a time</option>
                  {slots.map((s) => (
                    <option key={s.id} value={s.id}>
                      {formatSlotShort(s.startsAt)}
                    </option>
                  ))}
                </NativeSelect>
              </Field>
              <DetailList
                rows={[
                  [
                    'Specialist',
                    `${match.specialist.name} · ${match.specialist.specialty} · ${match.specialist.subspecialty}`,
                  ],
                  ['Location', `${match.specialist.organization} · ${match.specialist.city}`],
                  ['Distance', `${match.distanceMiles} miles`],
                  ['Match', <StrengthBadge key="match" strength={match.strength} />],
                ]}
              />
              <div className="rounded-2xl border border-violet-100 bg-violet-50 p-3">
                <div className="text-xs font-medium text-primary-subtle-foreground">Why this match?</div>
                <p className="text-body-sm text-foreground/80">{match.why}</p>
              </div>
              {match.factors.some((f) => f.status !== 'met') && (
                <ul className="flex flex-col gap-3">
                  {match.factors
                    .filter((f) => f.status !== 'met')
                    .map((f) => (
                      <MatchFactor key={f.key} factor={f} />
                    ))}
                </ul>
              )}
            </section>
          </div>

          <ActionBar
            title={slot ? `${match.specialist.name} · ${formatSlotShort(slot.startsAt)}` : match.specialist.name}
            detail={bookingFailed || unavailable ? 'Nothing was booked.' : 'Nothing is booked until you approve.'}
          >
            <Button asChild variant="onDark">
              <Link to={matchesUrl}>Choose another specialist</Link>
            </Button>
            <Button disabled={!slotId || approve.isPending} onClick={() => setDialogOpen(true)}>
              {bookingFailed ? 'Try again' : 'Approve & Book'}
            </Button>
          </ActionBar>

          <Dialog
            open={dialogOpen}
            onClose={() => !approve.isPending && setDialogOpen(false)}
            title="Book this appointment?"
            footer={
              <>
                <Button variant="outline" autoFocus disabled={approve.isPending} onClick={() => setDialogOpen(false)}>
                  Cancel
                </Button>
                <Button disabled={approve.isPending} aria-busy={approve.isPending} onClick={confirm}>
                  Approve & Book
                </Button>
              </>
            }
          >
            {referral.patient.name} with {match.specialist.name}, {slot ? formatSlotShort(slot.startsAt) : ''}.
          </Dialog>
        </>
      )}
    </div>
  )
}
