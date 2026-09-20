import { ArrowRight, Hourglass, Plus } from 'lucide-react'
import { useQueryClient } from '@tanstack/react-query'
import { Fragment, useEffect, useRef, useState } from 'react'
import { Link, useLocation, useNavigate, useParams, useSearchParams } from 'react-router-dom'
import { Avatar, ConversationItem, ConversationSkeleton, DraftItem, MessageBubble } from '@/components/echo/chat'
import { EmptyState } from '@/components/echo/states'
import { Alert } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Field } from '@/components/ui/field'
import { Textarea } from '@/components/ui/input'
import { NativeSelect } from '@/components/ui/native-select'
import { ConsultNotFoundError } from '@/echo/errors'
import {
  useColleagues,
  useConsultThread,
  useEchoConsults,
  useEchoReferrals,
  useSendConsultMessage,
  useStartConsult,
} from '@/echo/hooks'
import { dayLabel } from '@/echo/referral'
import type { ConsultThread } from '@/echo/types'
import { controlA11y } from '@/lib/control-a11y'

const ids = { colleague: 'consult-colleague', referral: 'consult-referral', message: 'consult-message' }

/** Messages grouped under day dividers, with the sender's-context note under the first one. */
function Messages({
  thread,
  failed,
  onRetry,
  retrying,
}: {
  thread: ConsultThread
  failed: string | null
  onRetry: () => void
  retrying: boolean
}) {
  const end = useRef<HTMLDivElement>(null)
  // Keep the newest message in view when a conversation opens or grows.
  useEffect(() => {
    end.current?.scrollIntoView({ block: 'end' })
  }, [thread.id, thread.messages.length, failed])
  return (
    <div
      className="flex flex-1 flex-col gap-4 overflow-y-auto bg-canvas p-6"
      role="log"
      aria-label={`Conversation with ${thread.colleague.name}`}
    >
      {thread.messages.map((m, i) => {
        const day = dayLabel(m.at)
        const showDay = i === 0 || day !== dayLabel(thread.messages[i - 1].at)
        return (
          <Fragment key={m.id}>
            {showDay && (
              <div className="flex justify-center">
                <span className="rounded-full border bg-card px-3 py-0.5 text-xs font-medium text-secondary-foreground">
                  {day}
                </span>
              </div>
            )}
            {i === 0 && thread.referral && (
              <p className="text-center text-xs text-muted-foreground">
                Shared with {thread.colleague.name}: age, sex, reason and case summary. Not the patient&apos;s name.
              </p>
            )}
            <MessageBubble message={m} colleague={thread.colleague} />
          </Fragment>
        )
      })}
      {failed && (
        <MessageBubble
          message={{ text: failed, fromMe: true, at: '' }}
          colleague={thread.colleague}
          failed
          onRetry={onRetry}
          retrying={retrying}
        />
      )}
      {!failed && thread.status === 'pending' && (
        <div className="flex justify-center">
          <Badge variant="info">
            <Hourglass className="size-3" aria-hidden />
            Waiting for response
          </Badge>
        </div>
      )}
      <div ref={end} />
    </div>
  )
}

/** The composer at the bottom of a conversation. Nothing is sent until the physician clicks Send. */
function Composer({ thread }: { thread: ConsultThread }) {
  const send = useSendConsultMessage(thread.id)
  const [text, setText] = useState('')
  const [failed, setFailed] = useState<string | null>(null)

  const submit = (value: string) => {
    if (!value.trim() || send.isPending) return
    setFailed(null)
    send.mutate(value.trim(), { onError: () => setFailed(value.trim()) })
  }
  return (
    <>
      <Messages thread={thread} failed={failed} onRetry={() => failed && submit(failed)} retrying={send.isPending} />
      <form
        className="flex flex-col gap-2 border-t bg-card px-6 py-4"
        onSubmit={(e) => {
          e.preventDefault()
          const value = text
          if (!value.trim()) return
          setText('')
          submit(value)
        }}
      >
        <div className="flex items-center gap-3">
          <Textarea
            aria-label={`Message to ${thread.colleague.name}`}
            placeholder="Write a message…"
            value={text}
            rows={1}
            className="min-h-12 flex-1 resize-none rounded-3xl px-5 py-3"
            onChange={(e) => setText(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) e.currentTarget.form?.requestSubmit()
            }}
          />
          <Button type="submit" disabled={send.isPending} aria-busy={send.isPending} className="size-12 shrink-0 px-0">
            <ArrowRight className="size-5" aria-hidden />
            <span className="sr-only">Send</span>
          </Button>
        </div>
        <p className="text-xs text-muted-foreground">Nothing is sent until you click Send.</p>
      </form>
    </>
  )
}

function ThreadHeader({ thread }: { thread: ConsultThread }) {
  const { colleague, referral, sharedContext } = thread
  return (
    <>
    <div className="flex items-center gap-3 border-b px-6 py-4">
      <Avatar name={colleague.name} />
      <div className="min-w-0 flex-1">
        <h2 className="truncate text-sm font-semibold">{colleague.name}</h2>
        <p className="truncate text-xs text-muted-foreground">
          {colleague.specialty} · {colleague.organization}
        </p>
      </div>
      {referral && (
        <div className="flex items-center gap-2">
          <span className="text-body-sm text-muted-foreground">
            About {referral.patientName} · {referral.age}y {referral.sex}
          </span>
          <Button asChild size="sm" variant="outline">
            <Link to={`/referral/${referral.id}`}>
              <ArrowRight className="size-4" aria-hidden /> View referral
            </Link>
          </Button>
        </div>
      )}
    </div>
    {sharedContext && (
      <div className="flex flex-wrap items-center gap-x-2.5 gap-y-1 bg-lavender-100 px-6 py-2.5 text-body-sm">
        <span className="font-medium text-primary-subtle-foreground">Case shared</span>
        <span className="text-foreground/80">
          {sharedContext.age}y {sharedContext.sex} · {sharedContext.reason}
        </span>
      </div>
    )}
    </>
  )
}

/** The "+ New consult" form. A referral is optional: the physician can consult a colleague any time. */
function NewConsult({ referralId }: { referralId: string }) {
  const navigate = useNavigate()
  const colleagues = useColleagues()
  const referrals = useEchoReferrals()
  const start = useStartConsult()
  const [colleagueId, setColleagueId] = useState('')
  const [about, setAbout] = useState(referralId)
  const [text, setText] = useState('')
  const [errors, setErrors] = useState<{ colleague?: string; message?: string }>({})
  const errorCount = Object.values(errors).filter(Boolean).length

  const submit = (e: React.FormEvent) => {
    e.preventDefault()
    const next: typeof errors = {}
    if (!colleagueId) next.colleague = 'Select a colleague.'
    if (!text.trim()) next.message = 'Enter a message.'
    setErrors(next)
    if (next.colleague || next.message) {
      document.getElementById(next.colleague ? ids.colleague : ids.message)?.focus()
      return
    }
    start.mutate(
      { colleagueId, text: text.trim(), referralId: about || null },
      { onSuccess: (t) => navigate(`/consults/${t.id}`) },
    )
  }

  return (
    <form noValidate onSubmit={submit} className="flex min-h-0 flex-1 flex-col">
      <div className="border-b px-6 py-4">
        <h2 className="text-sm font-semibold">New consult</h2>
        <p className="text-xs text-muted-foreground">Ask a colleague a question. A referral is optional.</p>
      </div>
      <div className="flex flex-1 flex-col gap-4 overflow-y-auto px-6 py-6">
        {errorCount > 0 ? (
          <Alert
            tone="destructive"
            title={`${errorCount} ${errorCount === 1 ? 'field needs' : 'fields need'} attention`}
          >
            {errors.colleague && errors.message
              ? 'Colleague and message are required.'
              : errors.colleague
                ? 'Colleague is required.'
                : 'Message is required.'}
          </Alert>
        ) : (
          start.isError && (
            <Alert tone="destructive" title="Couldn't send the consult">
              Nothing was sent. Your message is still here.
            </Alert>
          )
        )}
        <div className="flex w-full max-w-[560px] flex-col gap-4">
          <Field id={ids.colleague} label="To" error={errors.colleague}>
            <NativeSelect
              value={colleagueId}
              disabled={start.isPending}
              onChange={(e) => {
                setColleagueId(e.target.value)
                setErrors((x) => ({ ...x, colleague: undefined }))
              }}
              {...controlA11y(ids.colleague, errors.colleague)}
            >
              <option value="">Select colleague</option>
              {(colleagues.data ?? []).map((c) => (
                <option key={c.id} value={c.id}>
                  {c.name} · {c.specialty} · {c.organization}
                </option>
              ))}
            </NativeSelect>
          </Field>
          <div className="flex flex-col gap-1">
            <Field id={ids.referral} label="About a referral (optional)">
              <NativeSelect
                value={about}
                disabled={start.isPending}
                onChange={(e) => setAbout(e.target.value)}
                aria-describedby={`${ids.referral}-help`}
                id={ids.referral}
              >
                <option value="">No referral</option>
                {(referrals.data ?? []).map((r) => (
                  <option key={r.id} value={r.id}>
                    {r.patient.name} · {r.reason.length > 48 ? `${r.reason.slice(0, 48)}…` : r.reason}
                  </option>
                ))}
              </NativeSelect>
            </Field>
            <p id={`${ids.referral}-help`} className="text-xs text-muted-foreground">
              Shares the patient&apos;s age, sex, reason and case summary. Never the name.
            </p>
          </div>
          <Field id={ids.message} label="Message" error={errors.message}>
            <Textarea
              value={text}
              placeholder="What input do you need?"
              disabled={start.isPending}
              className="min-h-[120px]"
              onChange={(e) => {
                setText(e.target.value)
                setErrors((x) => ({ ...x, message: undefined }))
              }}
              {...controlA11y(ids.message, errors.message)}
            />
          </Field>
        </div>
      </div>
      <div className="flex items-center justify-between gap-4 border-t bg-canvas px-6 py-4">
        <p className="text-xs text-muted-foreground">Nothing is sent until you click Send consult.</p>
        <div className="flex gap-2">
          <Button asChild variant="outline">
            <Link to="/consults">Cancel</Link>
          </Button>
          <Button type="submit" disabled={start.isPending} aria-busy={start.isPending}>
            Send consult
          </Button>
        </div>
      </div>
    </form>
  )
}

function ThreadSkeleton() {
  const bar = 'rounded-sm bg-secondary'
  return (
    <div role="status" className="flex min-h-0 flex-1 flex-col" aria-label="Loading conversation">
      <div aria-hidden className="flex items-center gap-3 border-b px-6 py-4">
        <div className="size-10 rounded-full bg-secondary" />
        <div className="flex flex-col gap-1.5">
          <div className={`${bar} h-3 w-40`} />
          <div className={`${bar} h-2.5 w-56`} />
        </div>
      </div>
      <div aria-hidden className="flex flex-1 flex-col gap-4 bg-canvas p-6">
        <div className={`${bar} ml-auto h-11 w-[360px]`} />
        <div className={`${bar} h-16 w-[440px]`} />
      </div>
      <div aria-hidden className="border-t px-6 py-4">
        <div className={`${bar} h-14 w-full`} />
      </div>
    </div>
  )
}

/** Consults, as a chat: conversations on the left, the open conversation on the right. */
export default function ConsultsPage() {
  const { threadId } = useParams()
  const [params] = useSearchParams()
  const { pathname } = useLocation()
  const isNew = pathname === '/consults/new'
  const list = useEchoConsults()
  const consults = list.data ?? []
  const selectedId = isNew ? undefined : (threadId ?? consults[0]?.id)
  const thread = useConsultThread(selectedId)
  // When the open conversation gains a message (a reply arrived), refresh the list too so its status and preview agree.
  const qc = useQueryClient()
  const messageCount = thread.data?.messages.length
  useEffect(() => {
    if (messageCount !== undefined) qc.invalidateQueries({ queryKey: ['echo', 'consults'] })
  }, [messageCount, qc])

  const newButton = (
    <Button asChild>
      <Link to="/consults/new">
        <Plus className="size-4" aria-hidden /> New consult
      </Link>
    </Button>
  )
  const header = (
    <div className="flex items-center justify-between gap-4">
      <h1 className="text-[1.75rem] leading-9 font-semibold">Consults</h1>
      {newButton}
    </div>
  )

  if (list.isError) {
    return (
      <div className="space-y-6">
        {header}
        <Alert tone="destructive" title="Couldn't load consults">
          Your referrals are saved.
        </Alert>
        <div className="flex gap-2">
          <Button onClick={() => list.refetch()}>Try again</Button>
          <Button asChild variant="ghost">
            <Link to="/">Back to Dashboard</Link>
          </Button>
        </div>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {header}
      <div className="grid h-[calc(100vh-180px)] min-h-[480px] overflow-hidden rounded-3xl border bg-card lg:grid-cols-[360px_minmax(0,1fr)]">
        <section aria-label="Conversations" className="flex min-h-0 flex-col border-r bg-card">
          <h2 className="border-b p-4 text-sm font-semibold">Conversations</h2>
          <div className="min-h-0 flex-1 overflow-y-auto">
            {list.isLoading && (
              <div role="status">
                <ConversationSkeleton />
                <p className="p-4 text-xs text-muted-foreground">Loading consults…</p>
              </div>
            )}
            {isNew && <DraftItem />}
            {consults.map((c) => (
              <ConversationItem key={c.id} consult={c} selected={c.id === selectedId} />
            ))}
            {list.isSuccess && consults.length === 0 && !isNew && (
              <p className="p-4 text-body-sm text-muted-foreground">Conversations appear here.</p>
            )}
          </div>
        </section>

        <section aria-label={isNew ? 'New consult' : 'Conversation'} className="flex min-h-0 min-w-0 flex-col">
          {isNew ? (
            <NewConsult referralId={params.get('referral') ?? ''} />
          ) : list.isLoading || (selectedId && thread.isLoading) ? (
            <ThreadSkeleton />
          ) : thread.isError ? (
            <div className="space-y-4 p-6">
              <Alert
                tone="destructive"
                title={
                  thread.error instanceof ConsultNotFoundError
                    ? "We couldn't find that conversation"
                    : "Couldn't load the conversation"
                }
              >
                {thread.error instanceof ConsultNotFoundError
                  ? 'It may have been removed, or the link is wrong.'
                  : 'Your messages are saved.'}
              </Alert>
              {!(thread.error instanceof ConsultNotFoundError) && (
                <Button onClick={() => thread.refetch()}>Try again</Button>
              )}
            </div>
          ) : thread.data ? (
            <>
              <ThreadHeader thread={thread.data} />
              <Composer key={thread.data.id} thread={thread.data} />
            </>
          ) : (
            <div className="grid flex-1 place-items-center bg-canvas p-6">
              <div className="w-full max-w-[480px]">
                <EmptyState
                  title="No consults yet"
                  description="Start a conversation with a colleague."
                  action={{ label: 'New consult', to: '/consults/new', icon: true }}
                />
              </div>
            </div>
          )}
        </section>
      </div>
    </div>
  )
}
