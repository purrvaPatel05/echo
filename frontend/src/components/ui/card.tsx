import * as React from 'react'
import { cn } from '@/lib/utils'

type DivProps = React.HTMLAttributes<HTMLDivElement>

export const Card = ({ className, ...props }: DivProps) => (
  <div className={cn('rounded-3xl border bg-card text-card-foreground', className)} {...props} />
)
export const CardHeader = ({ className, ...props }: DivProps) => (
  <div className={cn('flex flex-col gap-1 p-5 pb-2', className)} {...props} />
)
export const CardTitle = ({ className, ...props }: DivProps) => (
  <div className={cn('font-semibold leading-tight', className)} {...props} />
)
export const CardDescription = ({ className, ...props }: DivProps) => (
  <div className={cn('text-sm text-muted-foreground', className)} {...props} />
)
export const CardContent = ({ className, ...props }: DivProps) => (
  <div className={cn('p-5 pt-2', className)} {...props} />
)
