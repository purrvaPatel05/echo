import { Check, Hourglass } from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import type { ConsultStatus } from '@/echo/types'

/** Consult status: icon + text, never color alone. */
export function ConsultStatusBadge({ status }: { status: ConsultStatus }) {
  return status === 'responded' ? (
    <Badge variant="success">
      <Check className="size-3" aria-hidden />
      Responded
    </Badge>
  ) : (
    <Badge variant="info">
      <Hourglass className="size-3" aria-hidden />
      Awaiting response
    </Badge>
  )
}
