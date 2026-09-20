/** Figma detail rows: a muted label and a value, on a shared 84px label column. */
export function DetailList({ rows }: { rows: [label: string, value: React.ReactNode][] }) {
  return (
    <dl className="grid grid-cols-[84px_minmax(0,1fr)] gap-x-3 gap-y-3">
      {rows.map(([label, value]) => (
        <div key={label} className="contents">
          <dt className="text-xs text-muted-foreground">{label}</dt>
          <dd className="text-body-sm">{value}</dd>
        </div>
      ))}
    </dl>
  )
}
