import { X } from 'lucide-react'
import { useEffect, useId, useRef } from 'react'

interface DialogProps {
  open: boolean
  onClose: () => void
  title: string
  children: React.ReactNode
  /** Buttons, right-aligned. */
  footer: React.ReactNode
}

/**
 * Figma "Dialog": 480px modal for confirmations. Built on the native <dialog> element, so focus is trapped,
 * Escape closes it, and the page behind is inert while it is open.
 */
export function Dialog({ open, onClose, title, children, footer }: DialogProps) {
  const ref = useRef<HTMLDialogElement>(null)
  const id = useId()

  useEffect(() => {
    const d = ref.current
    if (!d) return
    if (open && !d.open) d.showModal()
    if (!open && d.open) d.close()
  }, [open])

  return (
    <dialog
      ref={ref}
      aria-labelledby={`${id}-title`}
      aria-describedby={`${id}-body`}
      onCancel={(e) => {
        e.preventDefault() // let React state own closing
        onClose()
      }}
      onClick={(e) => {
        if (e.target === ref.current) onClose() // click on the backdrop
      }}
      className="m-auto w-[480px] max-w-[calc(100vw-2rem)] rounded-3xl border bg-card p-0 text-foreground shadow-[0_12px_32px_-4px_rgb(15_23_42/0.12),0_2px_6px_rgb(15_23_42/0.06)] backdrop:bg-foreground/40"
    >
      <div className="flex items-start gap-2 px-6 pt-5 pb-2">
        <h2 id={`${id}-title`} className="flex-1 text-base font-semibold">
          {title}
        </h2>
        <button
          type="button"
          onClick={onClose}
          aria-label="Close"
          className="rounded-sm p-0.5 text-muted-foreground hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
        >
          <X className="size-4" aria-hidden />
        </button>
      </div>
      <div id={`${id}-body`} className="px-6 py-2 text-body-sm text-muted-foreground">
        {children}
      </div>
      <div className="flex justify-end gap-2 px-6 pt-4 pb-5">{footer}</div>
    </dialog>
  )
}
