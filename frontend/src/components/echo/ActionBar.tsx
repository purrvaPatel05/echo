interface ActionBarProps {
  title: string
  detail: string
  /** Secondary then primary action. */
  children: React.ReactNode
}

/**
 * Figma "Action bar": a navy pill floating at the bottom of the content for decision screens. What will happen on
 * the left, actions on the right. Secondary actions inside it use `variant="onDark"`.
 */
export function ActionBar({ title, detail, children }: ActionBarProps) {
  return (
    <div className="pointer-events-none fixed inset-x-0 bottom-4 z-20 px-4 lg:left-[248px] lg:px-10">
      <div className="pointer-events-auto mx-auto flex min-h-16 max-w-[1160px] flex-wrap items-center gap-x-4 gap-y-2 rounded-[2rem] bg-navy-900 py-2.5 pr-2.5 pl-7 shadow-[0_8px_24px_-6px_rgb(14_19_48/0.35)]">
        <div aria-live="polite" className="mr-auto min-w-0">
          <div className="truncate font-display text-base font-medium text-white">{title}</div>
          <div className="text-xs text-mint-300">{detail}</div>
        </div>
        <div className="flex flex-wrap items-center gap-2.5">{children}</div>
      </div>
    </div>
  )
}
