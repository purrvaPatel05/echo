import { AlertTriangle, Check } from 'lucide-react'
import { Link } from 'react-router-dom'
import type { TimelineRow } from '@/echo/lifecycle'
import { cn } from '@/lib/utils'

// Figma "Timeline step". The state is carried by the indicator's shape AND a word, never color alone:
// done = teal check + "Complete"/"Confirmed", current = ringed dot on a tint + "Current",
// waiting = empty ring + "Waiting", attention = amber triangle + "Declined".
const indicator = {
  done: 'border-primary bg-primary text-primary-foreground',
  current: 'border-2 border-primary bg-background',
  waiting: 'border-input bg-background',
  attention: 'border-warning-border bg-warning-subtle text-warning-subtle-foreground',
} as const

const statusClass = {
  done: 'text-muted-foreground',
  current: 'font-medium text-primary-subtle-foreground',
  waiting: 'text-muted-foreground',
  attention: 'font-medium text-warning-subtle-foreground',
} as const

interface TimelineStepProps extends Omit<TimelineRow, 'id'> {
  /** Makes the title a link (e.g. from a timeline row to its detail screen). */
  titleTo?: string
}

export function TimelineStep({ title, time, detail, state, status, titleTo }: TimelineStepProps) {
  const waiting = state === 'waiting'
  return (
    <li
      aria-current={state === 'current' ? 'step' : undefined}
      className={cn('flex items-start gap-3 rounded-md px-3 py-3', state === 'current' ? 'bg-primary-subtle' : 'border-b last:border-b-0')}
    >
      <span aria-hidden className={cn('grid size-5 shrink-0 place-items-center rounded-full border', indicator[state])}>
        {state === 'done' && <Check className="size-3" strokeWidth={1.5} />}
        {state === 'current' && <span className="size-2 rounded-full bg-primary" />}
        {state === 'attention' && <AlertTriangle className="size-3" strokeWidth={1.5} />}
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
        <div className="text-xs text-muted-foreground">{time}</div>
      </div>
      <div className="shrink-0 text-right">
        <div className={cn('text-body-sm', waiting && 'text-muted-foreground')}>{detail}</div>
        <div className={cn('text-xs', statusClass[state])}>{status}</div>
      </div>
    </li>
  )
}
