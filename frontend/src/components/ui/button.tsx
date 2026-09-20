import { Slot } from '@radix-ui/react-slot'
import { cva, type VariantProps } from 'class-variance-authority'
import * as React from 'react'
import { cn } from '@/lib/utils'

// Figma "Button": a pill, 44px (36px compact), Outfit.
const buttonVariants = cva(
  'inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-full font-display font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:pointer-events-none disabled:opacity-50',
  {
    variants: {
      variant: {
        default: 'bg-primary text-primary-foreground hover:bg-primary-hover',
        secondary: 'bg-secondary text-secondary-foreground hover:bg-border',
        outline: 'border border-border-strong bg-background text-foreground hover:bg-secondary',
        ghost: 'text-primary-subtle-foreground hover:bg-primary-subtle',
        onDark: 'border border-navy-700 text-white hover:bg-white/10 focus-visible:ring-mint-300',
        destructive: 'bg-destructive text-destructive-foreground hover:bg-destructive-hover',
      },
      size: {
        default: 'h-11 px-[22px] text-sm',
        sm: 'h-9 px-4 text-body-sm',
      },
    },
    defaultVariants: { variant: 'default', size: 'default' },
  },
)

export interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {
  asChild?: boolean
}

export function Button({ className, variant, size, asChild, ...props }: ButtonProps) {
  const Comp = asChild ? Slot : 'button'
  return <Comp className={cn(buttonVariants({ variant, size }), className)} {...props} />
}
