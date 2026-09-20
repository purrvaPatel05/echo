import { Plus } from 'lucide-react'
import { useState } from 'react'
import { Link } from 'react-router-dom'
import { Pulse } from '@/components/echo/Pulse'
import { ReferralsAtRisk } from '@/components/echo/ReferralsAtRisk'
import { ReferralTable } from '@/components/echo/ReferralTable'
import { EmptyState, LoadingRows } from '@/components/echo/states'
import { Alert } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { Tabs } from '@/components/ui/tabs'
import { FILTERS, matchesFilter, type ReferralFilter } from '@/echo/referral'
import { useEchoMe, useEchoReferrals } from '@/echo/hooks'

const PANEL_ID = 'referrals-panel'

/**
 * "Dr. Rivera, 2 referrals need you today." Referrals with a problem come first, then ones waiting on the physician's
 * approval; only when neither exists is the physician "all caught up". Plain welcome while the name loads.
 */
function greeting(name: string | undefined, needs: number, awaitingApproval: number): string {
  const last = name?.trim().split(/\s+/).at(-1)
  const who = last ? `Dr. ${last}` : 'Welcome back'
  if (needs > 0) return `${who}, ${needs} ${needs === 1 ? 'referral needs' : 'referrals need'} you today.`
  if (awaitingApproval > 0) {
    return `${who}, ${awaitingApproval} ${awaitingApproval === 1 ? 'referral is' : 'referrals are'} waiting for your approval.`
  }
  return last ? `${who}, you're all caught up.` : 'Your referrals'
}

export default function DashboardPage() {
  const { data: referrals, isLoading, isError, refetch } = useEchoReferrals()
  const { data: me } = useEchoMe()
  const [filter, setFilter] = useState<ReferralFilter>('active')

  const tabs = FILTERS.map((f) => ({
    key: f.key,
    label: f.label,
    count: referrals?.filter((r) => matchesFilter(r, f.key)).length,
    tone: f.alert ? ('alert' as const) : ('default' as const),
  }))
  const visible = referrals?.filter((r) => matchesFilter(r, filter)) ?? []
  const atRisk = referrals?.filter((r) => r.attention) ?? []

  return (
    <div className="space-y-6">
      <section aria-labelledby="dashboard-heading" className="relative overflow-hidden rounded-3xl bg-echo-x px-6 py-8 text-white sm:px-10">
        <div className="relative z-10 flex max-w-[520px] flex-col items-start gap-2.5">
          <p className="font-display text-sm font-medium text-mint-300">Your referrals</p>
          <h1 id="dashboard-heading" className="text-[1.75rem] leading-9 font-semibold">
            {greeting(me?.name, atRisk.length, referrals?.filter((r) => r.status === 'awaiting_approval').length ?? 0)}
          </h1>
          <p className="text-body-sm text-white/75">
            {referrals ? `${referrals.filter((r) => matchesFilter(r, 'active')).length} active. ` : ''}Nothing is booked until you approve.
          </p>
          <Button asChild className="mt-1.5">
            <Link to="/referral/new">
              <Plus className="size-4" aria-hidden /> New Referral
            </Link>
          </Button>
        </div>
        <Pulse
          width={512}
          height={120}
          beats={[[30, 1], [170, 0.66], [300, 0.36], [420, 0.16]]}
          echo={26}
          className="pointer-events-none absolute top-1/2 right-0 hidden w-[512px] -translate-y-1/2 lg:block"
        />
      </section>

      {isError && (
        <Alert
          tone="destructive"
          title="Couldn't load your referrals"
          action={
            <Button size="sm" variant="outline" onClick={() => refetch()}>
              Try again
            </Button>
          }
        >
          Check your connection and try again.
        </Alert>
      )}

      {isLoading && <LoadingRows />}

      {referrals && (
        <>
          <ReferralsAtRisk referrals={atRisk} />

          <section aria-label="All referrals" className="space-y-3">
            <Tabs<ReferralFilter> tabs={tabs} value={filter} onChange={setFilter} label="Filter referrals" panelId={PANEL_ID} />
            <div id={PANEL_ID} role="tabpanel" aria-labelledby={`${PANEL_ID}-tab-${filter}`}>
              {visible.length > 0 ? (
                <ReferralTable referrals={visible} />
              ) : (
                <EmptyState
                  title="No referrals in this view"
                  description="Referrals you create appear here."
                />
              )}
            </div>
          </section>
        </>
      )}
    </div>
  )
}
