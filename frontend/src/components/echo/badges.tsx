import { AlertTriangle, CalendarCheck, ClipboardCheck, Clock, Hourglass, Zap } from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { STATUS_LABEL, URGENCY_LABEL } from '@/echo/referral'
import type { ReferralStatus, Urgency } from '@/echo/types'

// Every state pairs an icon with text so meaning never depends on color alone.

const statusStyle = {
  awaiting_approval: { variant: 'warning', Icon: ClipboardCheck },
  awaiting_patient: { variant: 'info', Icon: Hourglass },
  scheduled: { variant: 'success', Icon: CalendarCheck },
} as const

export function StatusBadge({ status }: { status: ReferralStatus }) {
  const { variant, Icon } = statusStyle[status]
  return (
    <Badge variant={variant} className="gap-1">
      <Icon className="size-3" aria-hidden />
      {STATUS_LABEL[status]}
    </Badge>
  )
}

const urgencyStyle = {
  routine: { variant: 'secondary', Icon: null },
  soon: { variant: 'warning', Icon: Clock },
  urgent: { variant: 'destructive', Icon: Zap },
} as const

export function UrgencyBadge({ urgency }: { urgency: Urgency }) {
  const { variant, Icon } = urgencyStyle[urgency]
  return (
    <Badge variant={variant} className="gap-1">
      {Icon && <Icon className="size-3" aria-hidden />}
      {URGENCY_LABEL[urgency]}
    </Badge>
  )
}

export function AttentionBadge() {
  return (
    <Badge variant="destructive" className="gap-1">
      <AlertTriangle className="size-3" aria-hidden />
      Needs attention
    </Badge>
  )
}
