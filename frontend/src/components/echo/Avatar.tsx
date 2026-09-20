import { initials } from '@/echo/referral'
import { cn } from '@/lib/utils'

const sizes = { sm: 'size-8 text-xs', md: 'size-10 text-sm', lg: 'size-12 text-base' } as const

/** Figma "Avatar": a lavender disc with the person's initials (violet when `tone="violet"`, e.g. the open conversation). */
export function Avatar({
  name,
  size = 'md',
  tone = 'lavender',
  className,
}: {
  name: string
  size?: keyof typeof sizes
  tone?: 'lavender' | 'violet'
  className?: string
}) {
  return (
    <span
      aria-hidden
      className={cn(
        'grid shrink-0 place-items-center rounded-full font-display font-medium',
        tone === 'violet'
          ? 'bg-violet-600 text-white'
          : 'border border-lavender-200 bg-lavender-100 text-primary-subtle-foreground',
        sizes[size],
        className,
      )}
    >
      {initials(name)}
    </span>
  )
}
