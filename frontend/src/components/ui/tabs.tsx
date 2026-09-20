import { useRef } from 'react'
import { cn } from '@/lib/utils'

export interface TabItem<T extends string> {
  key: T
  label: string
  count?: number
  /** `alert` renders the count chip in red (e.g. "Needs Attention"). */
  tone?: 'default' | 'alert'
}

interface TabsProps<T extends string> {
  tabs: TabItem<T>[]
  value: T
  onChange: (key: T) => void
  label: string
  /** Must match the `id` of the tabpanel this controls. */
  panelId: string
}

/** Accessible tab list (roving tabindex, arrow/Home/End keys). Render your own `role="tabpanel"`. Figma pill tabs. */
export function Tabs<T extends string>({ tabs, value, onChange, label, panelId }: TabsProps<T>) {
  const refs = useRef<Record<string, HTMLButtonElement | null>>({})

  const onKeyDown = (e: React.KeyboardEvent, index: number) => {
    const last = tabs.length - 1
    const next =
      e.key === 'ArrowRight' ? (index === last ? 0 : index + 1)
      : e.key === 'ArrowLeft' ? (index === 0 ? last : index - 1)
      : e.key === 'Home' ? 0
      : e.key === 'End' ? last
      : null
    if (next === null) return
    e.preventDefault()
    onChange(tabs[next].key)
    refs.current[tabs[next].key]?.focus()
  }

  return (
    <div role="tablist" aria-label={label} className="flex flex-wrap gap-2">
      {tabs.map((t, i) => {
        const selected = t.key === value
        return (
          <button
            key={t.key}
            ref={(el) => {
              refs.current[t.key] = el
            }}
            role="tab"
            id={`${panelId}-tab-${t.key}`}
            aria-selected={selected}
            aria-controls={panelId}
            tabIndex={selected ? 0 : -1}
            onClick={() => onChange(t.key)}
            onKeyDown={(e) => onKeyDown(e, i)}
            className={cn(
              'flex items-center gap-2 rounded-full border py-2 pr-3 pl-4 font-display text-body-sm font-medium focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2',
              selected
                ? 'border-transparent bg-primary text-primary-foreground'
                : 'border-border-strong bg-background text-muted-foreground hover:bg-secondary hover:text-foreground',
            )}
          >
            {t.label}
            {t.count !== undefined && (
              <span
                className={cn(
                  'min-w-5 rounded-full px-1.5 text-center text-xs font-medium tabular-nums',
                  t.tone === 'alert' && !selected
                    ? 'bg-destructive-subtle text-destructive-subtle-foreground'
                    : selected
                      ? 'bg-violet-500 text-white'
                      : 'bg-secondary text-foreground',
                )}
              >
                {t.count}
              </span>
            )}
          </button>
        )
      })}
    </div>
  )
}
