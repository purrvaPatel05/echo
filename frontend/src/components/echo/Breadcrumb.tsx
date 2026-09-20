import { Fragment } from 'react'
import { Link } from 'react-router-dom'

/** Figma breadcrumb: teal links, a slash between, and the current page in muted text. */
export function Breadcrumb({ items }: { items: { label: string; to?: string }[] }) {
  return (
    <nav aria-label="Breadcrumb">
      <ol className="flex items-center gap-1 text-xs">
        {items.map((item, i) => (
          <Fragment key={item.label}>
            {i > 0 && (
              <li aria-hidden className="text-muted-foreground">
                /
              </li>
            )}
            {item.to ? (
              <li>
                <Link to={item.to} className="text-primary hover:underline">
                  {item.label}
                </Link>
              </li>
            ) : (
              <li aria-current="page" className="text-muted-foreground">
                {item.label}
              </li>
            )}
          </Fragment>
        ))}
      </ol>
    </nav>
  )
}
