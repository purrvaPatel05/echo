import { Link } from 'react-router-dom'
import { Alert } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { ReferralNotFoundError } from '@/echo/errors'
import type { Referral } from '@/echo/types'
import { LoadingRows } from './states'

interface GateProps {
  referral: Referral | undefined
  error: unknown
  isError: boolean
  onRetry: () => void
  /** Copy for a failed load, e.g. "Couldn't load the confirmation". */
  loadFailedTitle: string
  /** What to show while the referral loads. Defaults to the table skeleton. */
  loading?: React.ReactNode
  children: (referral: Referral) => React.ReactNode
}

/**
 * Shared loading / not-found / error handling for the referral status screens.
 * - Unknown id: "We couldn't find that referral" (nothing to retry).
 * - Any other failed load: an alert with Try again (primary) and Back to Dashboard (Figma error frames).
 */
export function ReferralStatusGate({ referral, error, isError, onRetry, loadFailedTitle, loading, children }: GateProps) {
  if (isError && error instanceof ReferralNotFoundError) {
    return (
      <Alert
        tone="destructive"
        title="We couldn't find that referral"
        action={
          <Button asChild size="sm" variant="outline">
            <Link to="/">Back to Dashboard</Link>
          </Button>
        }
      >
        It may have been removed, or the link is wrong.
      </Alert>
    )
  }
  if (isError) {
    return (
      <>
        <Alert tone="destructive" title={loadFailedTitle}>
          Your referral is saved.
        </Alert>
        <div className="flex gap-2">
          <Button onClick={onRetry}>Try again</Button>
          <Button asChild variant="ghost">
            <Link to="/">Back to Dashboard</Link>
          </Button>
        </div>
      </>
    )
  }
  if (!referral) return <>{loading ?? <LoadingRows />}</>
  return <>{children(referral)}</>
}
