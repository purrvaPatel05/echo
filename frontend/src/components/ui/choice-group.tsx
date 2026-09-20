import { cn } from '@/lib/utils'

export interface ChoiceOption<T extends string> {
  value: T
  label: string
  description: string
}

interface ChoiceGroupProps<T extends string> {
  legend: string
  name: string
  options: ChoiceOption<T>[]
  value: T
  onChange: (value: T) => void
}

/**
 * Figma "Choice option" group: radio-style option cards. Native radios underneath, so arrow keys and
 * screen readers work. Selected = filled radio + violet border + inset ring (2px total, no layout shift) + tint.
 */
export function ChoiceGroup<T extends string>({ legend, name, options, value, onChange }: ChoiceGroupProps<T>) {
  return (
    <fieldset className="flex flex-col gap-1">
      <legend className="mb-1 text-body-sm font-medium">{legend}</legend>
      <div className="grid gap-3 sm:grid-cols-3">
        {options.map((o) => {
          const selected = o.value === value
          return (
            <label
              key={o.value}
              className={cn(
                'flex cursor-pointer items-center gap-3 rounded-2xl border px-3.5 py-3 transition-colors has-focus-visible:outline-2 has-focus-visible:outline-offset-2 has-focus-visible:outline-ring',
                selected
                  ? 'border-primary bg-primary-subtle text-primary-subtle-foreground ring-1 ring-primary ring-inset'
                  : 'border-input bg-background hover:border-border-strong hover:bg-canvas',
              )}
            >
              <input
                type="radio"
                name={name}
                value={o.value}
                checked={selected}
                onChange={() => onChange(o.value)}
                className="sr-only"
              />
              <span
                aria-hidden
                className={cn(
                  'grid size-4 shrink-0 place-items-center rounded-full border',
                  selected ? 'border-primary bg-primary' : 'border-input bg-background',
                )}
              >
                {selected && <span className="size-1.5 rounded-full bg-primary-foreground" />}
              </span>
              <span className="flex flex-col">
                <span className="text-body-sm font-medium">{o.label}</span>
                <span className={cn('text-xs', !selected && 'text-muted-foreground')}>{o.description}</span>
              </span>
            </label>
          )
        })}
      </div>
    </fieldset>
  )
}
