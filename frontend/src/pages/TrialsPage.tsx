import { Check, Clock, ExternalLink } from 'lucide-react'
import { Fragment, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { Breadcrumb } from '@/components/echo/Breadcrumb'
import { ReferralStatusGate } from '@/components/echo/ReferralStatusGate'
import { Alert } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { useReferralStatus, useTrialCriteria, useTrials } from '@/echo/hooks'
import type { Referral, Trial, TrialCriteria, TrialSearchOptions, TrialStatus } from '@/echo/types'

const th = 'px-4 py-2 text-left text-xs font-medium uppercase tracking-[0.04em] text-muted-foreground'
const td = 'px-4 py-3 align-top'
// Column widths from the Figma table (1280px total), as percentages so the table scales.
const cols = [380, 250, 190, 170, 290].map((w) => `${(w / 1280) * 100}%`)
const heads = ['Trial', 'Condition · intervention', 'Location', 'Status', 'Why it may be relevant']

/** Recruitment status: icon + text, never color alone. "Active, not recruiting" is plain neutral text. */
function TrialStatusBadge({ status }: { status: TrialStatus }) {
  if (status === 'recruiting') {
    return (
      <Badge variant="success">
        <Check className="size-3" aria-hidden />
        Recruiting
      </Badge>
    )
  }
  if (status === 'not_yet_recruiting') {
    return (
      <Badge variant="info">
        <Clock className="size-3" aria-hidden />
        Not yet recruiting
      </Badge>
    )
  }
  return <Badge>Active, not recruiting</Badge>
}

const criteriaLabels: [keyof TrialCriteria, string][] = [
  ['condition', 'Condition'],
  ['patient', 'Patient'],
  ['location', 'Location'],
  ['status', 'Status'],
  ['source', 'Source'],
]

/** Figma "Search criteria": what the search actually used. */
function CriteriaCard({ criteria }: { criteria: TrialCriteria | undefined }) {
  return (
    <section aria-labelledby="criteria-heading" className="flex flex-col gap-3 rounded-3xl border bg-card p-5">
      <h2 id="criteria-heading" className="text-sm font-semibold">
        Search criteria
      </h2>
      <dl className="grid gap-x-6 gap-y-4 sm:grid-cols-2 lg:grid-cols-5">
        {criteriaLabels.map(([key, label]) => (
          <div key={key} className="min-w-0">
            <dt className="text-xs text-muted-foreground">{label}</dt>
            <dd className="text-body-sm">
              {criteria ? (
                String(criteria[key])
              ) : (
                <span aria-hidden className="mt-1 block h-3 w-3/4 rounded-sm bg-secondary" />
              )}
            </dd>
          </div>
        ))}
      </dl>
    </section>
  )
}

function TableShell({
  children,
  footer,
  busy,
}: {
  children: React.ReactNode
  footer: React.ReactNode
  busy?: boolean
}) {
  return (
    <div className="overflow-hidden rounded-3xl border bg-card" aria-busy={busy}>
      <div className="overflow-x-auto">
        <table className="w-full min-w-[60rem] table-fixed border-collapse text-body-sm">
          <caption className="sr-only">Clinical trials to review</caption>
          <colgroup>
            {cols.map((w, i) => (
              <col key={i} style={{ width: w }} />
            ))}
          </colgroup>
          <thead className="border-b bg-canvas">
            <tr>
              {heads.map((h) => (
                <th key={h} scope="col" className={th}>
                  {h}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>{children}</tbody>
        </table>
      </div>
      <div className="border-t bg-canvas px-4 py-3 text-xs text-muted-foreground">{footer}</div>
    </div>
  )
}

/** Figma "Trial row". The title links to the trial's own ClinicalTrials.gov page, in a new tab. */
function TrialRow({ trial: t }: { trial: Trial }) {
  return (
    <tr className="border-b last:border-b-0">
      <td className={td}>
        <a href={t.url} target="_blank" rel="noopener noreferrer" className="font-medium text-primary hover:underline">
          {t.title}
          <span className="sr-only"> (opens on ClinicalTrials.gov in a new tab)</span>
        </a>
        <div className="flex items-center gap-1 text-xs text-muted-foreground">
          {t.nctId} · ClinicalTrials.gov
          <ExternalLink className="size-3" aria-hidden />
        </div>
      </td>
      <td className={td}>
        {t.condition}
        <div className="text-xs text-muted-foreground">{t.intervention}</div>
      </td>
      <td className={td}>
        {t.location}
        {t.distanceMiles !== null && <div className="text-xs text-muted-foreground">{t.distanceMiles} miles</div>}
      </td>
      <td className={td}>
        <TrialStatusBadge status={t.status} />
      </td>
      <td className={td}>{t.relevance ?? 'Condition matches the search.'}</td>
    </tr>
  )
}

function SkeletonRows() {
  const widths = [340, 210, 150, 110, 260]
  return (
    <>
      {[0, 1, 2, 3].map((i) => (
        <tr key={i} aria-hidden className="border-b">
          {widths.map((w) => (
            <td key={w} className="px-4 py-4">
              <div className="h-3 max-w-full rounded-sm bg-secondary" style={{ width: w }} />
            </td>
          ))}
        </tr>
      ))}
    </>
  )
}

function ReferralLine({ referral: r }: { referral: Referral }) {
  const parts = [
    <span key="patient" className="font-medium text-foreground">
      {r.patient.name} · {r.patient.age}y {r.patient.sex}
    </span>,
    <span key="reason">{r.reason}</span>,
    <span key="specialty">{r.subspecialty ? `${r.specialty} · ${r.subspecialty}` : r.specialty}</span>,
  ]
  return (
    <p className="flex flex-wrap items-center gap-x-2 gap-y-1 text-body-sm text-muted-foreground">
      {parts.map((p, i) => (
        <Fragment key={i}>
          {i > 0 && <span aria-hidden>·</span>}
          {p}
        </Fragment>
      ))}
    </p>
  )
}

/** Widen choices offered when a search finds nothing. Each is a new search, run only when the physician picks it. */
function NoResultsOptions({
  criteria,
  onChange,
}: {
  criteria: TrialCriteria
  onChange: (o: (s: TrialSearchOptions) => TrialSearchOptions) => void
}) {
  const d = criteria.distanceMiles
  const widerDistances = d === null ? [] : [250].filter((m) => m > d)
  const canWiden = d !== null
  if (!canWiden && criteria.allStatuses) return null
  return (
    <section aria-labelledby="options-heading" className="overflow-hidden rounded-3xl border bg-card lg:max-w-[880px]">
      <h2 id="options-heading" className="px-5 pt-4 pb-3 text-sm font-semibold">
        What you can do
      </h2>
      {canWiden && (
        <div className="flex flex-col gap-3 border-t px-5 py-4 sm:flex-row sm:items-center">
          <div className="flex-1">
            <div className="text-body-sm font-medium">Widen location</div>
            <div className="text-xs text-muted-foreground">Currently within {d} miles</div>
          </div>
          <div className="flex gap-2">
            {widerDistances.map((m) => (
              <Button
                key={m}
                variant="outline"
                size="sm"
                aria-label={`Search within ${m} miles`}
                onClick={() => onChange((s) => ({ ...s, distanceMiles: m }))}
              >
                {m} miles
              </Button>
            ))}
            <Button
              variant="outline"
              size="sm"
              aria-label="Search any location"
              onClick={() => onChange((s) => ({ ...s, distanceMiles: null }))}
            >
              Any location
            </Button>
          </div>
        </div>
      )}
      {!criteria.allStatuses && (
        <div className="flex flex-col gap-3 border-t px-5 py-4 sm:flex-row sm:items-center">
          <div className="flex-1">
            <div className="text-body-sm font-medium">Include all statuses</div>
            <div className="text-xs text-muted-foreground">Now recruiting or not yet recruiting</div>
          </div>
          <Button
            variant="outline"
            size="sm"
            aria-label="Include all statuses"
            onClick={() => onChange((s) => ({ ...s, allStatuses: true }))}
          >
            Include
          </Button>
        </div>
      )}
    </section>
  )
}

function TrialsBody({ referral }: { referral: Referral }) {
  const [search, setSearch] = useState<TrialSearchOptions>({})
  const criteriaQ = useTrialCriteria(referral.id, search)
  const trialsQ = useTrials(referral.id, search)
  const trials = trialsQ.data?.trials ?? []
  const empty = trialsQ.isSuccess && trials.length === 0
  const results = trialsQ.isSuccess && trials.length > 0

  if (trialsQ.isError) {
    return (
      <>
        <Alert tone="destructive" title="Couldn't load trials">
          ClinicalTrials.gov didn't respond.
        </Alert>
        <div className="flex gap-2">
          <Button onClick={() => trialsQ.refetch()}>Try again</Button>
          <Button asChild variant="ghost">
            <Link to={`/referral/${referral.id}`}>View referral</Link>
          </Button>
        </div>
      </>
    )
  }

  return (
    <>
      {!empty && (
        <Alert tone="info" title="For your review">
          Trials from ClinicalTrials.gov. Not recommendations; eligibility is not checked.
        </Alert>
      )}
      <CriteriaCard criteria={criteriaQ.data} />
      {trialsQ.isLoading && (
        <div role="status">
          <TableShell busy footer="Loading trials…">
            <SkeletonRows />
          </TableShell>
        </div>
      )}
      {empty && (
        <>
          <Alert tone="warning" title="No trials found">
            Nothing matched these criteria.
          </Alert>
          {criteriaQ.data && <NoResultsOptions criteria={criteriaQ.data} onChange={setSearch} />}
        </>
      )}
      {results && (
        <TableShell
          footer={`${trials.length} ${trials.length === 1 ? 'trial' : 'trials'} from ClinicalTrials.gov · Sorted by distance`}
        >
          {trials.map((t) => (
            <TrialRow key={t.nctId} trial={t} />
          ))}
        </TableShell>
      )}
    </>
  )
}

/**
 * Clinical trials to review for one referral. Trials come from ClinicalTrials.gov; the screen shows no scores, no
 * "best match" and no eligibility claim. Each row links out; there is no separate detail page.
 */
export default function TrialsPage() {
  const { referralId = '' } = useParams()
  const q = useReferralStatus(referralId)

  return (
    <div className="space-y-6">
      <div className="space-y-1">
        <Breadcrumb
          items={[
            { label: 'Dashboard', to: '/' },
            { label: 'Referral', to: `/referral/${referralId}` },
            { label: 'Trials' },
          ]}
        />
        <h1 className="text-[1.75rem] leading-9 font-semibold">Clinical trials</h1>
        {q.data && <ReferralLine referral={q.data} />}
      </div>
      <ReferralStatusGate
        referral={q.data}
        error={q.error}
        isError={q.isError}
        onRetry={() => q.refetch()}
        loadFailedTitle="Couldn't load trials"
        loading={
          <p role="status" className="text-xs text-muted-foreground">
            Loading trials…
          </p>
        }
      >
        {(r) => <TrialsBody referral={r} />}
      </ReferralStatusGate>
    </div>
  )
}
