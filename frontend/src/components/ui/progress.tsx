interface ProgressProps {
  value: number
  max: number
  label: string
}

/** Figma "Checks" progress bar: 10px pill track, violet fill. Determinate only (a step count, never a time estimate). */
export function Progress({ value, max, label }: ProgressProps) {
  return (
    <div
      role="progressbar"
      aria-label={label}
      aria-valuemin={0}
      aria-valuemax={max}
      aria-valuenow={value}
      className="h-2.5 overflow-hidden rounded-full bg-secondary"
    >
      <div className="h-full rounded-full bg-primary transition-[width] duration-300" style={{ width: `${(value / max) * 100}%` }} />
    </div>
  )
}
