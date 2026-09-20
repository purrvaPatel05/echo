import { AlertTriangle, Check, ClipboardCheck, Hourglass } from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { lifecycleBadge } from '@/echo/lifecycle'
import type { Referral } from '@/echo/types'

const icons = { clipboard: ClipboardCheck, hourglass: Hourglass, check: Check, alert: AlertTriangle }

/** Status badge for the tracking and confirmation screens: icon + text, never color alone. */
export function LifecycleBadge({ referral }: { referral: Referral }) {
  const { variant, label, icon } = lifecycleBadge(referral)
  const Icon = icons[icon]
  return (
    <Badge variant={variant}>
      <Icon className="size-3" aria-hidden />
      {label}
    </Badge>
  )
}
