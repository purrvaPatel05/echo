import { AlertTriangle, Check } from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { STRENGTH_META } from '@/echo/matches'
import type { MatchStrength } from '@/echo/types'

/** Strong / Good / Partial match: a label with an icon, never a number. */
export function StrengthBadge({ strength }: { strength: MatchStrength }) {
  const meta = STRENGTH_META[strength]
  return (
    <Badge variant={meta.variant}>
      {strength === 'partial' ? <AlertTriangle className="size-3" aria-hidden /> : <Check className="size-3" aria-hidden />}
      {meta.label}
    </Badge>
  )
}
