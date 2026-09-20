import * as React from 'react'
import { cn } from '@/lib/utils'

interface FieldProps {
  /** Id of the control this labels. The error message gets id `${id}-error`. */
  id: string
  label: string
  error?: string
  children: React.ReactNode
  className?: string
}

/** Figma "Field": label, control, then an error message (icon-free text in red, never color alone with the red border). */
export function Field({ id, label, error, children, className }: FieldProps) {
  return (
    <div className={cn('flex min-w-0 flex-col gap-1', className)}>
      <label htmlFor={id} className="text-body-sm font-medium">
        {label}
      </label>
      {children}
      {error && (
        <p id={`${id}-error`} className="text-xs text-destructive">
          {error}
        </p>
      )}
    </div>
  )
}
