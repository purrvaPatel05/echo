import { AlertTriangle, Check, X } from 'lucide-react'
import { FACTOR_LABEL, FACTOR_STATUS_WORD } from '@/echo/matches'
import type { MatchFactor as Factor, MatchFactorStatus } from '@/echo/types'
import { cn } from '@/lib/utils'

// Figma "Match factor": icon + label + value. The icon AND the wording carry the meaning.
const icons: Record<MatchFactorStatus, { Icon: typeof Check; className: string }> = {
  met: { Icon: Check, className: 'bg-success-subtle text-success' },
  partial: { Icon: AlertTriangle, className: 'bg-warning-subtle text-warning' },
  unmet: { Icon: X, className: 'bg-destructive-subtle text-destructive' },
}

export function MatchFactor({ factor }: { factor: Factor }) {
  const { Icon, className } = icons[factor.status]
  return (
    <li className="flex items-center gap-2.5">
      <span aria-hidden className={cn('grid size-[26px] shrink-0 place-items-center rounded-full', className)}>
        <Icon className="size-3.5" />
      </span>
      <div className="min-w-0">
        <div className="text-xs text-muted-foreground">{FACTOR_LABEL[factor.key]}</div>
        <div className="text-body-sm">
          <span className="sr-only">{FACTOR_STATUS_WORD[factor.status]}: </span>
          {factor.detail}
        </div>
      </div>
    </li>
  )
}
