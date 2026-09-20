/** Props to spread on a form control so it's announced as invalid and linked to its error message (see `Field`). */
export const controlA11y = (id: string, error?: string) => ({
  id,
  'aria-invalid': error ? (true as const) : undefined,
  'aria-describedby': error ? `${id}-error` : undefined,
})
