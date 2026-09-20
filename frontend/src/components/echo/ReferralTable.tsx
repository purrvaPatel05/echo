import { ArrowRight } from 'lucide-react'
import { Link, useNavigate } from 'react-router-dom'
import { formatDate, nextAction } from '@/echo/referral'
import type { Referral } from '@/echo/types'
import { Avatar } from './Avatar'
import { AttentionBadge, StatusBadge, UrgencyBadge } from './badges'

const th = 'px-4 py-2 text-left text-xs font-medium uppercase tracking-[0.04em] text-muted-foreground'
const td = 'px-4 py-3 align-top'

// Column widths from the Figma table (1280px total), as percentages so the table scales.
const cols = [210, 250, 130, 100, 220, 90, 280].map((w) => `${(w / 1280) * 100}%`)

/**
 * Figma "Table header" + "Table row". Rows are interactive: hover tints the row, keyboard focus
 * draws an inset 2px teal ring. The patient name and next action are the real links (tab stops);
 * clicking anywhere else on the row opens the referral too.
 */
export function ReferralTable({ referrals }: { referrals: Referral[] }) {
  const navigate = useNavigate()

  return (
    <div className="overflow-x-auto rounded-3xl border bg-card">
      <table className="w-full min-w-[60rem] table-fixed border-collapse text-body-sm">
        <caption className="sr-only">Your referrals</caption>
        <colgroup>
          {cols.map((w, i) => (
            <col key={i} style={{ width: w }} />
          ))}
        </colgroup>
        <thead className="border-b bg-canvas">
          <tr>
            <th scope="col" className={th}>Patient</th>
            <th scope="col" className={th}>Referral reason</th>
            <th scope="col" className={th}>Specialty</th>
            <th scope="col" className={th}>Urgency</th>
            <th scope="col" className={th}>Status</th>
            <th scope="col" className={th}>Created</th>
            <th scope="col" className={th}>Next action</th>
          </tr>
        </thead>
        <tbody>
          {referrals.map((r) => {
            const href = `/referral/${r.id}`
            return (
              <tr
                key={r.id}
                onClick={(e) => {
                  if (!(e.target as HTMLElement).closest('a')) navigate(href)
                }}
                className="cursor-pointer border-b transition-colors last:border-b-0 hover:bg-canvas has-focus-visible:bg-canvas has-focus-visible:outline-2 has-focus-visible:-outline-offset-2 has-focus-visible:outline-ring"
              >
                <td className={td}>
                  <div className="flex items-center gap-2.5">
                    <Avatar name={r.patient.name} size="sm" />
                    <div className="min-w-0">
                      <Link to={href} className="font-medium text-primary focus-visible:outline-none">
                        {r.patient.name}
                      </Link>
                      <div className="text-xs text-muted-foreground">
                        {r.patient.age}y {r.patient.sex}
                      </div>
                    </div>
                  </div>
                </td>
                <td className={td}>{r.reason}</td>
                <td className={td}>
                  {r.specialty}
                  <div className="text-xs text-muted-foreground">{r.subspecialty}</div>
                </td>
                <td className={td}>
                  <UrgencyBadge urgency={r.urgency} />
                </td>
                <td className={td}>
                  <div className="flex flex-col items-start gap-1">
                    <StatusBadge status={r.status} />
                    {r.attention && <AttentionBadge />}
                  </div>
                </td>
                <td className={`${td} whitespace-nowrap text-muted-foreground`}>{formatDate(r.createdAt)}</td>
                <td className={td}>
                  <Link to={href} className="inline-flex items-center gap-1 font-medium focus-visible:outline-none">
                    {nextAction(r)}
                    <ArrowRight className="size-3.5 text-primary" aria-hidden />
                  </Link>
                </td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}
