import { Link } from 'react-router-dom'
import { ConsultStatusBadge } from '@/components/echo/ConsultStatusBadge'
import { Button } from '@/components/ui/button'
import { formatListTime, formatStamp, initials } from '@/echo/referral'
import type { Colleague, ConsultMessage, ConsultSummary } from '@/echo/types'
import { cn } from '@/lib/utils'

/** Figma "Conversation item" avatar: initials in a lavender circle (violet when `plain`, i.e. the open conversation). */
export function Avatar({
  name,
  size = 40,
  plain,
  className,
}: {
  name: string
  size?: 28 | 40
  plain?: boolean
  className?: string
}) {
  return (
    <span
      aria-hidden
      className={cn(
        'grid shrink-0 place-items-center rounded-full font-display text-xs font-medium',
        plain ? 'bg-primary text-primary-foreground' : 'border border-lavender-200 bg-lavender-100 text-primary-subtle-foreground',
        size === 40 ? 'size-11 text-sm' : 'size-7',
        className,
      )}
    >
      {name === '+' ? '+' : initials(name)}
    </span>
  )
}

const itemBase =
  'flex w-full gap-3 border-b border-l-4 py-3.5 pr-4 pl-3.5 text-left focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-ring'

/** Figma "Conversation item": avatar, name and time, one-line preview, and the status. */
export function ConversationItem({ consult, selected }: { consult: ConsultSummary; selected: boolean }) {
  const { colleague, lastMessage } = consult
  return (
    <Link
      to={`/consults/${consult.id}`}
      aria-current={selected ? 'true' : undefined}
      className={cn(itemBase, selected ? 'border-l-primary bg-violet-50' : 'border-l-transparent bg-card hover:bg-canvas')}
    >
      <Avatar name={colleague.name} plain={selected} />
      <span className="flex min-w-0 flex-1 flex-col gap-1">
        <span className="flex items-baseline gap-2">
          <span className="min-w-0 flex-1 truncate text-sm font-medium">{colleague.name}</span>
          <span className="shrink-0 text-xs text-muted-foreground">{formatListTime(lastMessage.at)}</span>
        </span>
        <span className="truncate text-body-sm text-muted-foreground">
          {lastMessage.fromMe ? 'You: ' : `${colleague.name}: `}
          {lastMessage.text}
        </span>
        <span className="self-start">
          <ConsultStatusBadge status={consult.status} />
        </span>
      </span>
    </Link>
  )
}

/** The unsent draft shown at the top of the list while the New consult form is open. */
export function DraftItem() {
  return (
    <div aria-current="true" className={cn(itemBase, 'border-l-primary bg-violet-50')}>
      <Avatar name="+" plain />
      <span className="flex min-w-0 flex-1 flex-col gap-1">
        <span className="flex items-baseline gap-2">
          <span className="min-w-0 flex-1 truncate text-sm font-medium">New consult</span>
          <span className="shrink-0 text-xs text-muted-foreground">Draft</span>
        </span>
        <span className="truncate text-body-sm text-muted-foreground">Choose a colleague to start</span>
      </span>
    </div>
  )
}

/**
 * Figma "Message bubble". Mine are violet on the right, a colleague's are white on the left with their avatar.
 * A message that could not be sent shows "Not sent" and a Retry: nothing claims it was delivered.
 */
export function MessageBubble({
  message,
  colleague,
  failed,
  onRetry,
  retrying,
}: {
  message: Pick<ConsultMessage, 'text' | 'fromMe' | 'at' | 'simulated'>
  colleague: Colleague
  failed?: boolean
  onRetry?: () => void
  retrying?: boolean
}) {
  const mine = message.fromMe
  return (
    <div className={cn('flex items-start gap-2', mine && 'justify-end')}>
      {!mine && <Avatar name={colleague.name} size={28} />}
      <div className={cn('flex max-w-[560px] flex-col gap-1', mine && 'items-end')}>
        <p
          className={cn(
            'rounded-[20px] px-4 py-3 text-[15px] whitespace-pre-wrap',
            failed
              ? 'rounded-br-sm border border-destructive-border bg-destructive-subtle text-destructive-subtle-foreground'
              : mine
                ? 'rounded-br-sm bg-primary text-primary-foreground'
                : 'rounded-bl-sm border bg-card',
          )}
        >
          {message.text}
        </p>
        {failed ? (
          <span className="flex items-center gap-2 text-xs text-destructive-subtle-foreground">
            Not sent · Nothing was delivered.
            <Button size="sm" variant="ghost" onClick={onRetry} disabled={retrying}>
              Retry
            </Button>
          </span>
        ) : (
          <span className="text-xs text-muted-foreground">
            {mine
              ? `${formatStamp(message.at)} · Sent`
              : `${colleague.name} · ${formatStamp(message.at)}${message.simulated ? ' · Demo reply' : ''}`}
          </span>
        )}
      </div>
    </div>
  )
}

/** Static placeholder rows for the loading state (Figma "Consults / Chat — Loading"). */
export function ConversationSkeleton() {
  const bar = 'rounded-sm bg-secondary'
  return (
    <div aria-hidden>
      {[0, 1, 2, 3].map((i) => (
        <div key={i} className="flex gap-3 border-b px-4 py-3">
          <div className="size-11 shrink-0 rounded-full bg-secondary" />
          <div className="flex flex-1 flex-col gap-2">
            <div className={`${bar} h-3 w-36`} />
            <div className={`${bar} h-3 w-60`} />
            <div className={`${bar} h-5 w-28`} />
          </div>
        </div>
      ))}
    </div>
  )
}
