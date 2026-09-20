import { Fragment, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { UrgencyBadge } from '@/components/echo/badges'
import { Avatar } from '@/components/echo/Avatar'
import { MatchCard, MatchCardSkeleton } from '@/components/echo/MatchCard'
import { ReferralShortcuts } from '@/components/echo/ReferralShortcuts'
import { SelectionBar } from '@/components/echo/SelectionBar'
import { Alert } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { useEchoReferral, useMatches, useSelectSpecialist } from '@/echo/hooks'
import type { MatchSearchOptions, Referral } from '@/echo/types'

const DEFAULT_SUBTITLE = 'Select a specialist to review. Ordered by fit.'
const NO_MATCH_SUBTITLE = 'Nothing is booked.'

// Cards share the width: two matches get two wide columns rather than leaving an empty third.
const columns: Record<number, string> = {
  1: 'lg:grid-cols-1 lg:max-w-2xl',
  2: 'lg:grid-cols-2',
  3: 'lg:grid-cols-3',
}

function ReferralContext({ referral, distance }: { referral: Referral; distance: number }) {
  const parts: React.ReactNode[] = [
    <span key="patient" className="font-medium text-foreground">
      {referral.patient.name} · {referral.patient.age}y {referral.patient.sex}
    </span>,
    <span key="reason">{referral.reason}</span>,
    <UrgencyBadge key="urgency" urgency={referral.urgency} />,
    <span key="insurance">{referral.patient.insurance}</span>,
    <span key="location">
      {referral.patient.location} · within {distance} miles
    </span>,
  ]
  return (
    <div className="flex w-fit max-w-full flex-wrap items-center gap-x-2 gap-y-1 rounded-3xl border bg-card py-1.5 pr-4 pl-1.5 text-body-sm text-muted-foreground">
      <Avatar name={referral.patient.name} size="sm" className="mr-1" />
      {parts.map((p, i) => (
        <Fragment key={i}>
          {i > 0 && <span aria-hidden>·</span>}
          {p}
        </Fragment>
      ))}
    </div>
  )
}

export default function MatchesPage() {
  const { referralId = '' } = useParams()
  const { data: referral, isError: referralMissing } = useEchoReferral(referralId)
  const [search, setSearch] = useState<MatchSearchOptions>({})
  const { data, isLoading, isError, refetch } = useMatches(referralId, search)
  const select = useSelectSpecialist(referralId)
  const [selectedId, setSelectedId] = useState<string | null>(null)

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

  const matches = data?.matches ?? []
  const selected = matches.find((m) => m.specialist.id === selectedId) ?? null
  const distance = data?.searchDistanceMiles ?? referral?.preferredDistanceMiles ?? 25
  const noMatches = !!data && matches.length === 0
  const hasResults = !!data && matches.length > 0
  // The approval screen gets the selected specialist plus the search that produced the match (see ApprovalPage).
  const reviewParams = new URLSearchParams({
    specialist: selected?.specialist.id ?? '',
  })
  if (search.distanceMiles) reviewParams.set('distance', String(search.distanceMiles))
  if (search.includePartial) reviewParams.set('partial', '1')
  const reviewUrl = `/referral/${referralId}/review?${reviewParams}`

  return (
    <div className={hasResults ? 'space-y-6 pb-24' : 'space-y-6'}>
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
                <Link to="/referral/new" className="text-primary hover:underline">
                  New Referral
                </Link>
              </li>
              <li aria-hidden className="text-muted-foreground">
                /
              </li>
              <li>
                <Link to={`/referral/${referralId}/analysis`} className="text-primary hover:underline">
                  Analysis
                </Link>
              </li>
              <li aria-hidden className="text-muted-foreground">
                /
              </li>
              <li aria-current="page" className="text-muted-foreground">
                Matches
              </li>
            </ol>
          </nav>
          <h1 className="text-[1.75rem] leading-9 font-semibold">Specialist matches</h1>
          <p className="text-body-sm text-muted-foreground">{noMatches ? NO_MATCH_SUBTITLE : DEFAULT_SUBTITLE}</p>
        </div>
        {referral && <ReferralShortcuts referralId={referralId} />}
      </div>
      {referral && <ReferralContext referral={referral} distance={distance} />}

      {isError && (
        <>
          <Alert tone="destructive" title="Couldn't load matches">
            Your referral is saved.
          </Alert>
          <div className="flex gap-2">
            <Button onClick={() => refetch()}>Try again</Button>
            <Button asChild variant="ghost">
              <Link to="/">Back to Dashboard</Link>
            </Button>
          </div>
        </>
      )}

      {isLoading && (
        <div role="status">
          <div className="grid gap-4 lg:grid-cols-3">
            {[0, 1, 2].map((i) => (
              <MatchCardSkeleton key={i} />
            ))}
          </div>
          <p className="mt-6 text-xs text-muted-foreground">Loading specialist matches…</p>
        </div>
      )}

      {noMatches && (
        <>
          <Alert tone="warning" title="No strong match">
            {data.noMatchReason}
          </Alert>
          <section
            aria-labelledby="options-heading"
            className="overflow-hidden rounded-3xl border bg-card lg:max-w-[880px]"
          >
            <h2 id="options-heading" className="px-5 pt-4 pb-3 text-sm font-semibold">
              What you can do
            </h2>
            {[50, 100].some((d) => d > distance) && (
              <div className="flex flex-col gap-3 border-t px-5 py-4 sm:flex-row sm:items-center">
                <div className="flex-1">
                  <div className="text-body-sm font-medium">Widen distance</div>
                  <div className="text-xs text-muted-foreground">Currently {distance} miles</div>
                </div>
                <div className="flex gap-2">
                  {[50, 100]
                    .filter((d) => d > distance)
                    .map((d) => (
                      <Button
                        key={d}
                        variant="outline"
                        size="sm"
                        aria-label={`Search within ${d} miles`}
                        onClick={() => setSearch((s) => ({ ...s, distanceMiles: d }))}
                      >
                        {d} miles
                      </Button>
                    ))}
                </div>
              </div>
            )}
            {!search.includePartial && (
              <div className="flex flex-col gap-3 border-t px-5 py-4 sm:flex-row sm:items-center">
                <div className="flex-1">
                  <div className="text-body-sm font-medium">Partial matches</div>
                  <div className="text-xs text-muted-foreground">Meet most, not all, criteria</div>
                </div>
                <Button
                  variant="outline"
                  size="sm"
                  aria-label="Show partial matches"
                  onClick={() => setSearch((s) => ({ ...s, includePartial: true }))}
                >
                  Show
                </Button>
              </div>
            )}
            <div className="flex flex-col gap-3 border-t px-5 py-4 sm:flex-row sm:items-center">
              <div className="flex-1">
                <div className="text-body-sm font-medium">Consult a colleague</div>
                <div className="text-xs text-muted-foreground">Ask a peer about this case</div>
              </div>
              <Button asChild variant="outline" size="sm">
                <Link to={`/consults/new?referral=${referralId}`} aria-label="Consult a colleague about this case">
                  Consult
                </Link>
              </Button>
            </div>
          </section>
        </>
      )}

      {hasResults && (
        <>
          <fieldset>
            <legend className="sr-only">Specialist matches. Select one to review.</legend>
            <div className={`grid gap-4 ${columns[matches.length] ?? columns[3]}`}>
              {matches.map((m) => (
                <MatchCard
                  key={m.specialist.id}
                  match={m}
                  name="specialist"
                  selected={m.specialist.id === selected?.specialist.id}
                  onSelect={() => setSelectedId(m.specialist.id)}
                />
              ))}
            </div>
          </fieldset>
          <SelectionBar
            selected={selected}
            reviewTo={reviewUrl}
            onReview={() => selected && select.mutate(selected.specialist.id)}
          />
        </>
      )}
    </div>
  )
}
