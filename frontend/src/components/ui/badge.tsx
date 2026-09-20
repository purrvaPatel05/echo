import { cva, type VariantProps } from 'class-variance-authority'
import * as React from 'react'
import { cn } from '@/lib/utils'

// Figma "Chip": a 22px pill with a subtle tint + border.
// `default` stays a solid violet chip for the original prototype screens.
const badgeVariants = cva(
  'inline-flex h-[22px] items-center justify-center gap-1 rounded-full border px-2.5 text-xs font-medium whitespace-nowrap',
  {
    variants: {
      variant: {
        default: 'border-transparent bg-primary text-primary-foreground',
        secondary: 'border-border bg-secondary text-foreground',
        primary: 'border-primary-border bg-primary-subtle text-primary-subtle-foreground',
        success: 'border-success-border bg-success-subtle text-success-subtle-foreground',
        warning: 'border-warning-border bg-warning-subtle text-warning-subtle-foreground',
        info: 'border-info-border bg-info-subtle text-info-subtle-foreground',
        destructive: 'border-destructive-border bg-destructive-subtle text-destructive-subtle-foreground',
      },
    },
    defaultVariants: { variant: 'secondary' },
  },
)

export function Badge({
  className,
  variant,
  ...props
}: React.HTMLAttributes<HTMLSpanElement> & VariantProps<typeof badgeVariants>) {
  return <span className={cn(badgeVariants({ variant }), className)} {...props} />
}
