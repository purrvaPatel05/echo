import { AlertTriangle, Check } from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { STRENGTH_META } from '@/echo/matches'
import type { SpecialistMatch } from '@/echo/types'
import { cn } from '@/lib/utils'
import { Avatar } from './Avatar'
import { MatchFactor } from './MatchFactor'
import { Pulse } from './Pulse'

interface MatchCardProps {
  match: SpecialistMatch
  selected: boolean
  onSelect: () => void
  /** Radio group name shared by all cards on the screen. */
  name: string
}

/**
 * Figma "Match card". The whole card is a radio option (native input, so arrow keys and screen readers work).
 * Selected = 2px violet border (1px border + inset ring, so nothing shifts) + filled radio + "Selected" button.
 * Selecting only marks a choice; nothing is booked from here. The navy header carries the heartbeat.
 */
export function MatchCard({ match, selected, onSelect, name }: MatchCardProps) {
  const { specialist: s, strength } = match
  const id = `match-${s.id}`
  const meta = STRENGTH_META[strength]

  return (
    <label
      className={cn(
        'flex cursor-pointer flex-col overflow-hidden rounded-3xl border bg-card transition-colors has-focus-visible:outline-2 has-focus-visible:outline-offset-2 has-focus-visible:outline-ring',
        selected ? 'border-primary ring-1 ring-primary ring-inset' : 'hover:border-border-strong',
      )}
    >
      <input
        type="radio"
        name={name}
        value={s.id}
        checked={selected}
        onChange={onSelect}
        className="sr-only"
        aria-labelledby={`${id}-name`}
        aria-describedby={`${id}-strength ${id}-why`}
      />

      <div className="relative h-[88px] bg-echo-x">
        <Pulse
          width={300}
          height={44}
          beats={[[150, 1], [230, 0.5]]}
          strokeWidth={2}
          opacity={0.9}
          echo={8}
          className="pointer-events-none absolute right-5 bottom-3 w-[calc(100%-2.5rem)]"
        />
        <div className="relative flex items-start justify-between p-4">
          <Badge id={`${id}-strength`} variant={meta.variant}>
            {strength === 'partial' ? <AlertTriangle className="size-3" aria-hidden /> : <Check className="size-3" aria-hidden />}
            {meta.label}
          </Badge>
          <span
            aria-hidden
            className={cn(
              'grid size-6 place-items-center rounded-full',
              selected ? 'bg-primary text-primary-foreground' : 'border-2 border-white',
            )}
          >
            {selected && <Check className="size-3.5" />}
          </span>
        </div>
      </div>

      <div className="flex flex-1 flex-col gap-4 p-5">
        <div className="flex items-center gap-3">
          <Avatar name={s.name} size="lg" />
          <div className="min-w-0">
            <h3 id={`${id}-name`} className="text-xl leading-7 font-semibold">
              {s.name}
            </h3>
            <div className="text-body-sm text-foreground/80">
              {s.specialty} · {s.subspecialty}
            </div>
            <div className="text-xs text-muted-foreground">
              {s.organization} · {s.city}
            </div>
          </div>
        </div>

        <ul className="flex flex-col gap-2.5">
          {match.factors.map((f) => (
            <MatchFactor key={f.key} factor={f} />
          ))}
        </ul>

        <div className="mt-auto rounded-2xl border border-violet-100 bg-violet-50 p-3">
          <div className="text-xs font-medium text-primary-subtle-foreground">Why this match?</div>
          <p id={`${id}-why`} className="text-body-sm text-foreground/80">
            {match.why}
          </p>
        </div>

        {/* Looks like the Figma button but isn't a second control: the radio above is the control. */}
        <Button asChild variant={selected ? 'default' : 'outline'} className="w-full">
          <span aria-hidden>
            {selected && <Check className="size-4" />}
            {selected ? 'Selected' : 'Select'}
          </span>
        </Button>
      </div>
    </label>
  )
}

/** Loading placeholder shaped like a match card. Static, no animation. */
export function MatchCardSkeleton() {
  const bar = (w: number | string, h = 12) => <div className="rounded-sm bg-secondary" style={{ width: w, height: h }} />
  return (
    <div aria-hidden className="flex flex-col gap-4 rounded-3xl border bg-card p-5">
      {bar(96, 22)}
      {bar(180, 20)}
      {bar(140, 14)}
      {bar(220)}
      {[0, 1, 2, 3, 4].map((i) => (
        <div key={i} className="flex items-center gap-2">
          {bar(16, 16)}
          {bar('70%')}
        </div>
      ))}
      {bar('90%')}
      {bar('80%')}
      {bar('100%', 36)}
    </div>
  )
}
