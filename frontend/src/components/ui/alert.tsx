import { AlertTriangle, Check, Info } from 'lucide-react'
import * as React from 'react'
import { cn } from '@/lib/utils'

// Matches the Figma "Alert" component. Always icon + title + text, never color alone.
const tones = {
  info: { box: 'border-info-border bg-info-subtle text-info-subtle-foreground', Icon: Info },
  success: { box: 'border-success-border bg-success-subtle text-success-subtle-foreground', Icon: Check },
  warning: { box: 'border-warning-border bg-warning-subtle text-warning-subtle-foreground', Icon: AlertTriangle },
  destructive: {
    box: 'border-destructive-border bg-destructive-subtle text-destructive-subtle-foreground',
    Icon: AlertTriangle,
  },
} as const

interface AlertProps extends Omit<React.HTMLAttributes<HTMLDivElement>, 'title'> {
  tone?: keyof typeof tones
  title: string
  /** Optional right-aligned action, e.g. a retry button. */
  action?: React.ReactNode
}

export function Alert({ tone = 'info', title, action, className, children, ...props }: AlertProps) {
  const { box, Icon } = tones[tone]
  return (
    <div
      role={tone === 'destructive' ? 'alert' : 'status'}
      className={cn('flex items-center gap-3 rounded-2xl border py-3 pr-4 pl-3.5', box, className)}
      {...props}
    >
      <span aria-hidden className="grid size-7 shrink-0 place-items-center rounded-full bg-white">
        <Icon className="size-4" />
      </span>
      <div className="min-w-0 flex-1">
        <p className="text-body-sm font-medium text-foreground">{title}</p>
        {children && <p className="text-body-sm text-foreground/80">{children}</p>}
      </div>
      {action}
    </div>
  )
}
