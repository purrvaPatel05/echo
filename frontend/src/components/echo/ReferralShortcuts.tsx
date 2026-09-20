import { Link } from 'react-router-dom'
import { Button } from '@/components/ui/button'

/**
 * Entry points from a referral screen to its two side features. Quiet outline buttons at the top right of the page
 * header, so they never compete with the screen's own primary action.
 */
export function ReferralShortcuts({ referralId }: { referralId: string }) {
  return (
    <div className="flex gap-2">
      <Button asChild variant="outline" size="sm">
        <Link to={`/consults/new?referral=${referralId}`}>Consult a colleague</Link>
      </Button>
      <Button asChild variant="outline" size="sm">
        <Link to={`/referral/${referralId}/trials`}>Clinical trials</Link>
      </Button>
    </div>
  )
}
