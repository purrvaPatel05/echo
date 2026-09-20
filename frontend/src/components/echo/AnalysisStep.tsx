import { AlertTriangle, Check, LoaderCircle } from 'lucide-react'
import { Link } from 'react-router-dom'
import type { AnalysisCheckState } from '@/echo/types'
import { cn } from '@/lib/utils'

// Figma "Analysis step". Every state has an icon AND a text label, never color alone.
const states: Record<AnalysisCheckState, { indicator: string; label: string; labelClass: string }> = {
  done: { indicator: 'border-primary bg-primary text-primary-foreground', label: 'Complete', labelClass: 'text-muted-foreground' },
  active: {
    indicator: 'border-primary-border bg-primary-subtle text-primary',
    label: 'In progress',
    labelClass: 'text-primary-subtle-foreground',
  },
  waiting: { indicator: 'border-input bg-background', label: 'Waiting', labelClass: 'text-muted-foreground' },
  error: {
    indicator: 'border-destructive-border bg-destructive-subtle text-destructive-subtle-foreground',
    label: "Couldn't complete",
    labelClass: 'text-destructive-subtle-foreground',
  },
}

interface AnalysisStepProps {
  state: AnalysisCheckState
  title: string
  description: string
  detail: string
  /** Makes the title a link. */
  titleTo?: string
}

export function AnalysisStep({ state, title, description, detail, titleTo }: AnalysisStepProps) {
  const s = states[state]
  const waiting = state === 'waiting'
  return (
    <li className="flex items-start gap-3 border-b py-3 last:border-b-0">
      <span aria-hidden className={cn('grid size-5 shrink-0 place-items-center rounded-full border', s.indicator)}>
        {state === 'done' && <Check className="size-3" strokeWidth={1.5} />}
        {/* Spins only when the user hasn't asked for reduced motion; otherwise it's a static ring. */}
        {state === 'active' && <LoaderCircle className="size-3 motion-safe:animate-spin" strokeWidth={1.5} />}
        {state === 'error' && <AlertTriangle className="size-3" strokeWidth={1.5} />}
      </span>
      <div className="min-w-0 flex-1">
        <div className={cn('text-body-sm font-medium', waiting && 'text-muted-foreground')}>
          {titleTo ? (
            <Link to={titleTo} className="hover:underline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring">
              {title}
            </Link>
          ) : (
            title
          )}
        </div>
        <div className="text-xs text-muted-foreground">{description}</div>
      </div>
      <div className="shrink-0 text-right">
        <div className={cn('text-body-sm', waiting && 'text-muted-foreground')}>{detail}</div>
        <div className={cn('text-xs', s.labelClass)}>{s.label}</div>
      </div>
    </li>
  )
}
