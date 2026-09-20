import { Link, useParams } from 'react-router-dom'
import { AnalysisStep } from '@/components/echo/AnalysisStep'
import { LoadingRows } from '@/components/echo/states'
import { ReferralSummary } from '@/components/echo/ReferralSummary'
import { Alert } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { Progress } from '@/components/ui/progress'
import { CHECK_COPY, checkDetail, doneCount } from '@/echo/analysis'
import { useAnalysis, useEchoReferral, useRetryAnalysis } from '@/echo/hooks'
import type { AnalysisStatus } from '@/echo/types'

const NUMBER_WORDS = ['none', 'one', 'two', 'three', 'four', 'five']

const copy: Record<AnalysisStatus, { title: string; subtitle: string }> = {
  running: { title: 'Analyzing referral', subtitle: 'ECHO is checking specialists against this referral.' },
  complete: { title: 'Analysis complete', subtitle: 'All checks are complete.' },
  error: { title: "Analysis couldn't finish", subtitle: 'Try again, or edit the referral.' },
}

export default function AnalysisPage() {
  const { referralId = '' } = useParams()
  const { data: referral, isError: referralMissing } = useEchoReferral(referralId)
  const { data: analysis, isError: analysisFailed, refetch } = useAnalysis(referralId)
  const retry = useRetryAnalysis(referralId)

  if (referralMissing) {
    return (
      <div className="space-y-6">
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
      </div>
    )
  }

  const status = analysis?.status ?? 'running'
  const { title, subtitle } = copy[status]
  const total = analysis?.checks.length ?? 5
  const done = analysis ? doneCount(analysis) : 0
  const failed = analysis?.checks.find((c) => c.state === 'error')
  const matches = analysis?.matchCount ?? 0

  return (
    <div className="space-y-6">
      <div className="space-y-1">
        <nav aria-label="Breadcrumb">
          <ol className="flex items-center gap-1 text-xs">
            <li>
              <Link to="/" className="text-primary hover:underline">
                Dashboard
              </Link>
            </li>
            <li aria-hidden className="text-muted-foreground">
              /
            </li>
            <li>
              <Link to="/referral/new" className="text-primary hover:underline">
                New Referral
              </Link>
            </li>
            <li aria-hidden className="text-muted-foreground">
              /
            </li>
            <li aria-current="page" className="text-muted-foreground">
              Analysis
            </li>
          </ol>
        </nav>
        <h1 className="text-[1.75rem] leading-9 font-semibold">{title}</h1>
        <p className="text-body-sm text-muted-foreground">{subtitle}</p>
      </div>

      {status === 'complete' && (
        <Alert tone="success" title={`${matches} specialist ${matches === 1 ? 'match' : 'matches'} ready`}>
          Nothing is booked until you approve.
        </Alert>
      )}
      {status === 'error' && failed && analysis && (
        <Alert tone="destructive" title={`Couldn't check ${CHECK_COPY[failed.key].failedLabel}`}>
          {done > 0 ? `The other ${NUMBER_WORDS[done] ?? done} ${done === 1 ? 'check' : 'checks'} completed.` : 'Nothing has completed yet.'}
        </Alert>
      )}
      {(analysisFailed || retry.isError) && (
        <Alert
          tone="destructive"
          title="Couldn't load the analysis"
          action={
            <Button size="sm" variant="outline" onClick={() => refetch()}>
              Reload
            </Button>
          }
        >
          Your referral is still saved. Check your connection and reload.
        </Alert>
      )}

      {!analysis || !referral ? (
        <LoadingRows />
      ) : (
        <div className="grid items-start gap-6 lg:grid-cols-[minmax(0,1fr)_376px]">
          <section aria-labelledby="checks-heading" className="overflow-hidden rounded-3xl border bg-card">
            <div className="flex flex-col gap-4 px-6 pt-5 pb-2">
              <div className="flex items-center justify-between">
                <h2 id="checks-heading" className="text-sm font-semibold">
                  Checks
                </h2>
                <p aria-live="polite" className="text-xs text-muted-foreground">
                  {done} of {total} complete
                </p>
              </div>
              <Progress value={done} max={total} label="Analysis progress" />
              <ol aria-label="Analysis checks">
                {analysis.checks.map((c) => (
                  <AnalysisStep
                    key={c.key}
                    state={c.state}
                    title={CHECK_COPY[c.key].title}
                    description={CHECK_COPY[c.key].description}
                    detail={checkDetail(c.key, referral)}
                  />
                ))}
              </ol>
            </div>

            <div className="flex items-center gap-2 border-t bg-canvas px-6 py-4">
              <p className="mr-auto text-xs text-muted-foreground">
                {status === 'error' ? 'Your referral is saved.' : 'Nothing is booked until you approve.'}
              </p>
              {status === 'running' && (
                <Button asChild variant="outline">
                  <Link to="/">Back to Dashboard</Link>
                </Button>
              )}
              {status === 'complete' && (
                <Button asChild>
                  <Link to={`/referral/${referralId}/matches`}>Review matches</Link>
                </Button>
              )}
              {status === 'error' && (
                <>
                  <Button asChild variant="ghost">
                    <Link to="/">Back to Dashboard</Link>
                  </Button>
                  <Button asChild variant="outline">
                    <Link to="/referral/new">Edit referral</Link>
                  </Button>
                  <Button onClick={() => retry.mutate()} disabled={retry.isPending} aria-busy={retry.isPending}>
                    Try again
                  </Button>
                </>
              )}
            </div>
          </section>

          <ReferralSummary referral={referral} />
        </div>
      )}
    </div>
  )
}
