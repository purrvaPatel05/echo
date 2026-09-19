import * as React from 'react'
import { cn } from '@/lib/utils'

const field =
  'w-full rounded-md border bg-background px-3 py-2 text-sm shadow-xs placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:opacity-50'

export const Input = ({ className, ...props }: React.InputHTMLAttributes<HTMLInputElement>) => (
  <input className={cn(field, 'h-9', className)} {...props} />
)

export const Textarea = ({ className, ...props }: React.TextareaHTMLAttributes<HTMLTextAreaElement>) => (
  <textarea className={cn(field, 'min-h-24', className)} {...props} />
)

export const Select = ({ className, ...props }: React.SelectHTMLAttributes<HTMLSelectElement>) => (
  <select className={cn(field, 'h-9', className)} {...props} />
)
