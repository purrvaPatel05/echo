import { ClipboardCheck, Plus } from 'lucide-react'
import { Link } from 'react-router-dom'
import { Button } from '@/components/ui/button'

interface EmptyStateProps {
  title: string
  description: string
  /** The one action. Defaults to New Referral; `null` shows none. */
  action?: { label: string; to: string; icon?: boolean } | null
}

const NEW_REFERRAL = { label: 'New Referral', to: '/referral/new', icon: true }

/** Figma "Empty state": dashed card, icon chip, title, description, one action. */
export function EmptyState({ title, description, action = NEW_REFERRAL }: EmptyStateProps) {
  return (
    <div className="flex flex-col items-center gap-3 rounded-lg border border-dashed bg-card px-6 py-10 text-center">
      <span className="grid size-10 place-items-center rounded-full bg-secondary text-muted-foreground">
        <ClipboardCheck className="size-4" aria-hidden />
      </span>
      <h3 className="text-sm font-semibold">{title}</h3>
      <p className="max-w-sm text-body-sm text-muted-foreground">{description}</p>
      {action && (
        <Button asChild variant="outline" size="sm">
          <Link to={action.to}>
            {action.icon && <Plus className="size-4" aria-hidden />} {action.label}
          </Link>
        </Button>
      )}
    </div>
  )
}

/** Figma "Loading skeleton": static placeholder rows, no animation. */
export function LoadingRows({ label = 'Loading referrals…' }: { label?: string }) {
  return (
    <div role="status" className="space-y-4 rounded-3xl border bg-card p-4">
      {[0, 1, 2].map((i) => (
        <div key={i} aria-hidden className="flex items-center gap-4">
          {[120, 240, 90, 110].map((w) => (
            <div key={w} className="h-3 rounded-sm bg-secondary" style={{ width: w }} />
          ))}
        </div>
      ))}
      <p className="text-xs text-muted-foreground">{label}</p>
    </div>
  )
}
