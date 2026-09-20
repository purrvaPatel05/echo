import * as React from 'react'
import { cn } from '@/lib/utils'

// Figma "Field": 44px, 12px corners, 1px border, 2px violet focus ring, 2px red error border.
export const fieldClass =
  'w-full rounded-md border border-input bg-background px-3.5 py-2 text-sm placeholder:text-muted-foreground focus-visible:outline-none focus-visible:border-ring focus-visible:ring-1 focus-visible:ring-ring aria-invalid:border-destructive aria-invalid:ring-1 aria-invalid:ring-destructive focus-visible:aria-invalid:border-destructive focus-visible:aria-invalid:ring-destructive disabled:cursor-not-allowed disabled:bg-secondary disabled:text-muted-foreground'

export const Input = ({ className, ...props }: React.InputHTMLAttributes<HTMLInputElement>) => (
  <input className={cn(fieldClass, 'h-11', className)} {...props} />
)

export const Textarea = ({ className, ...props }: React.TextareaHTMLAttributes<HTMLTextAreaElement>) => (
  <textarea className={cn(fieldClass, 'min-h-24', className)} {...props} />
)

export const Select = ({ className, ...props }: React.SelectHTMLAttributes<HTMLSelectElement>) => (
  <select className={cn(fieldClass, 'h-11', className)} {...props} />
)
