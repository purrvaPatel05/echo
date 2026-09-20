import { Check, ChevronDown } from 'lucide-react'
import { useMemo, useState } from 'react'
import { fieldClass } from '@/components/ui/input'
import type { Patient } from '@/echo/types'
import { cn } from '@/lib/utils'

interface PatientComboboxProps {
  id: string
  patients: Patient[] | undefined
  value: string
  onSelect: (patient: Patient) => void
  'aria-invalid'?: boolean
  'aria-describedby'?: string
}

const label = (p: Patient) => `${p.name} · ${p.age}y ${p.sex}`

/**
 * Searchable patient picker (ARIA combobox with a listbox). Patients are records, not free text:
 * you can only submit a selection. The open list isn't in Figma yet; it uses only existing tokens.
 */
export function PatientCombobox({ id, patients, value, onSelect, ...aria }: PatientComboboxProps) {
  const [open, setOpen] = useState(false)
  const [query, setQuery] = useState('')
  const [active, setActive] = useState(0)
  const selected = patients?.find((p) => p.id === value)
  const listId = `${id}-list`

  const results = useMemo(() => {
    const q = query.trim().toLowerCase()
    return (patients ?? []).filter((p) => !q || p.name.toLowerCase().includes(q))
  }, [patients, query])

  const close = () => {
    setOpen(false)
    setQuery('')
  }
  const choose = (p: Patient) => {
    onSelect(p)
    close()
  }

  const onKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
      e.preventDefault()
      if (!open) return setOpen(true)
      const n = results.length
      if (n) setActive((a) => (e.key === 'ArrowDown' ? (a + 1) % n : (a - 1 + n) % n))
    } else if (e.key === 'Enter' && open) {
      e.preventDefault()
      if (results[active]) choose(results[active])
    } else if (e.key === 'Escape' && open) {
      e.preventDefault()
      close()
    }
  }

  return (
    <div
      className="relative"
      onBlur={(e) => {
        if (!e.currentTarget.contains(e.relatedTarget)) close()
      }}
    >
      <input
        id={id}
        role="combobox"
        aria-expanded={open}
        aria-controls={listId}
        aria-autocomplete="list"
        aria-activedescendant={open && results[active] ? `${id}-option-${results[active].id}` : undefined}
        autoComplete="off"
        disabled={!patients}
        placeholder={patients ? 'Select patient' : 'Loading patients…'}
        value={open ? query : selected ? label(selected) : ''}
        onChange={(e) => {
          setQuery(e.target.value)
          setActive(0)
          setOpen(true)
        }}
        // Opens on click, typing or arrow keys, but not on programmatic focus (e.g. after a failed submit).
        onClick={() => setOpen(true)}
        onKeyDown={onKeyDown}
        className={cn(fieldClass, 'h-9 pr-9')}
        {...aria}
      />
      <ChevronDown
        className="pointer-events-none absolute top-1/2 right-3 size-4 -translate-y-1/2 text-muted-foreground"
        aria-hidden
      />
      {open && (
        <ul
          id={listId}
          role="listbox"
          aria-label="Patients"
          className="absolute z-10 mt-1 max-h-60 w-full overflow-auto rounded-md border bg-background p-1 shadow-sm"
        >
          {results.length === 0 && <li className="px-2 py-2 text-body-sm text-muted-foreground">No matching patients</li>}
          {results.map((p, i) => (
            <li
              key={p.id}
              id={`${id}-option-${p.id}`}
              role="option"
              aria-selected={p.id === value}
              // mousedown (not click) so the input keeps focus and the blur handler doesn't close the list first
              onMouseDown={(e) => e.preventDefault()}
              onClick={() => choose(p)}
              onMouseMove={() => setActive(i)}
              className={cn(
                'flex cursor-pointer items-center gap-2 rounded-sm px-2 py-2',
                i === active && 'bg-secondary',
              )}
            >
              <span className="min-w-0 flex-1">
                <span className="block text-body-sm font-medium">{p.name}</span>
                <span className="block truncate text-xs text-muted-foreground">
                  {p.age}y {p.sex} · {p.location}
                </span>
              </span>
              {p.id === value && <Check className="size-4 text-primary" aria-hidden />}
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
