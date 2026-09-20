import { Link } from 'react-router-dom'
import { Button } from '@/components/ui/button'
import { formatSlotShort } from '@/echo/referral'
import type { SpecialistMatch } from '@/echo/types'

interface SelectionBarProps {
  selected: SpecialistMatch | null
  /** Where "Review selection" goes once a specialist is chosen. */
  reviewTo: string
  /** Called when the physician continues, e.g. to record the choice. */
  onReview?: () => void
}

/**
 * Figma "Selection bar": a navy pill floating at the bottom of the content. Says what is selected and that nothing is
 * booked until approval. The action stays disabled until a specialist is selected.
 */
export function SelectionBar({ selected, reviewTo, onReview }: SelectionBarProps) {
  const s = selected?.specialist
  return (
    <div className="pointer-events-none fixed inset-x-0 bottom-4 z-20 px-4 lg:left-[248px] lg:px-10">
      <div className="pointer-events-auto mx-auto flex min-h-16 max-w-[1160px] items-center gap-4 rounded-[2rem] bg-navy-900 py-2.5 pr-2.5 pl-7 shadow-[0_8px_24px_-6px_rgb(14_19_48/0.35)]">
        <div aria-live="polite" className="min-w-0 flex-1">
          {s ? (
            <>
              <div className="truncate font-display text-base font-medium text-white">
                {s.name} · {s.specialty} · {s.subspecialty}
              </div>
              <div className="text-xs text-mint-300">
                {selected.nextSlot ? `Earliest ${formatSlotShort(selected.nextSlot.startsAt)} · ` : ''}Nothing is booked until you approve.
              </div>
            </>
          ) : (
            <>
              <div className="font-display text-base font-medium text-white/80">No specialist selected</div>
              <div className="text-xs text-mint-300">Select a specialist above to continue.</div>
            </>
          )}
        </div>
        {s ? (
          <Button asChild>
            <Link to={reviewTo} onClick={onReview}>
              Review selection
            </Link>
          </Button>
        ) : (
          <Button disabled>Review selection</Button>
        )}
      </div>
    </div>
  )
}
