import { ChevronDown } from 'lucide-react'
import * as React from 'react'
import { cn } from '@/lib/utils'
import { fieldClass } from './input'

/** Figma "Field" (select): a native <select> (best keyboard/mobile behavior) with the design's chevron. */
export function NativeSelect({ className, children, ...props }: React.SelectHTMLAttributes<HTMLSelectElement>) {
  return (
    <div className="relative">
      <select
        className={cn(
          fieldClass,
          'h-9 appearance-none pr-9 [&>option]:text-foreground',
          props.value === '' && 'text-muted-foreground',
          className,
        )}
        {...props}
      >
        {children}
      </select>
      <ChevronDown
        className="pointer-events-none absolute top-1/2 right-3 size-4 -translate-y-1/2 text-muted-foreground"
        aria-hidden
      />
    </div>
  )
}
