import { type ClassValue, clsx } from 'clsx'
import { extendTailwindMerge } from 'tailwind-merge'

// Teach tailwind-merge our custom 13px size (`text-body-sm`, see index.css) so it isn't
// mistaken for a text color and dropped when combined with e.g. `text-muted-foreground`.
const twMerge = extendTailwindMerge({
  extend: { classGroups: { 'font-size': [{ text: ['body-sm'] }] } },
})

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}
