import type { Referral } from '@/echo/types'
import { UrgencyBadge } from './badges'

/** Figma "Referral summary": what was submitted, so the physician sees what is being evaluated. */
export function ReferralSummary({ referral: r }: { referral: Referral }) {
  const rows: [string, React.ReactNode][] = [
    ['Patient', `${r.patient.name} · ${r.patient.age}y ${r.patient.sex}`],
    ['Reason', r.reason],
    ['Specialty', r.subspecialty ? `${r.specialty} · ${r.subspecialty}` : r.specialty],
    ['Urgency', <UrgencyBadge key="urgency" urgency={r.urgency} />],
    ['Insurance', r.patient.insurance],
    ['Location', r.patient.location],
    ['Distance', `Within ${r.preferredDistanceMiles} miles`],
  ]
  return (
    <aside aria-labelledby="summary-heading" className="flex flex-col gap-4 rounded-3xl border bg-card p-5">
      <h2 id="summary-heading" className="text-sm font-semibold">
        Referral summary
      </h2>
      <dl className="grid grid-cols-[84px_minmax(0,1fr)] gap-x-3 gap-y-3">
        {rows.map(([label, value]) => (
          <div key={label} className="contents">
            <dt className="text-xs text-muted-foreground">{label}</dt>
            <dd className="text-body-sm">{value}</dd>
          </div>
        ))}
      </dl>
    </aside>
  )
}
