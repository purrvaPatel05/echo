import { AlertTriangle, ArrowRight } from 'lucide-react'
import { Link } from 'react-router-dom'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import type { Referral } from '@/echo/types'
import { Avatar } from './Avatar'
import { StatusBadge } from './badges'

/** Figma "Needs attention": referrals that haven't become an appointment and need the physician to act, as cards. */
export function ReferralsAtRisk({ referrals }: { referrals: Referral[] }) {
  if (referrals.length === 0) return null

  return (
    <section aria-labelledby="at-risk-heading" className="space-y-3">
      <div className="flex items-center gap-2.5">
        <h2 id="at-risk-heading" className="text-xl font-semibold">
          Needs attention
        </h2>
        <Badge variant="warning">
          <AlertTriangle className="size-3" aria-hidden />
          {referrals.length}
        </Badge>
      </div>
      <ul className="grid gap-4 md:grid-cols-2">
        {referrals.map((r) => (
          <li key={r.id} className="flex min-w-0 flex-col gap-3 rounded-lg border border-warning-border bg-card p-5">
            <div className="flex flex-wrap items-center gap-3">
              <Avatar name={r.patient.name} />
              <div className="min-w-0 flex-1 basis-40">
                <div className="font-display font-medium">
                  {r.patient.name} · {r.patient.age}y {r.patient.sex}
                </div>
                <div className="truncate text-body-sm text-muted-foreground">{r.reason}</div>
              </div>
              <StatusBadge status={r.status} />
            </div>
            <div className="flex items-center gap-2 rounded-xl bg-warning-subtle px-3.5 py-2.5 text-body-sm font-medium text-warning-subtle-foreground">
              <AlertTriangle className="size-4 shrink-0" aria-hidden />
              <span className="text-foreground">{r.attention?.reason}</span>
            </div>
            <div>
              <Button asChild variant="outline" size="sm">
                <Link to={`/referral/${r.id}`}>
                  {r.attention?.action}
                  <ArrowRight className="size-4" aria-hidden />
                </Link>
              </Button>
            </div>
          </li>
        ))}
      </ul>
    </section>
  )
}
