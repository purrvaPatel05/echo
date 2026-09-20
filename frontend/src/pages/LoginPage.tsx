import { useQuery } from '@tanstack/react-query'
import { ArrowRight } from 'lucide-react'
import { useState } from 'react'
import { Link, Navigate, useLocation, useNavigate } from 'react-router-dom'
import { Avatar } from '@/components/echo/Avatar'
import { LogoMark, Pulse } from '@/components/echo/Pulse'
import { Alert } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { Field } from '@/components/ui/field'
import { Input } from '@/components/ui/input'
import { useAuth } from '@/echo/authContext'
import { demoLogin, getDemoAccounts, login, type Session } from '@/echo/authApi'
import { controlA11y } from '@/lib/control-a11y'
import { cn } from '@/lib/utils'

const ids = { email: 'login-email', password: 'login-password' }

const steps = [
  { title: 'Read', text: 'Echo reads the case and pulls out what matters.' },
  { title: 'Match', text: 'Nearby specialists are ranked, with the reason for each.' },
  { title: 'Approve', text: 'Nothing is sent or booked until you approve it.' },
]

type Failure = 'invalid' | 'throttled' | 'unreachable'
const failureOf = (e: unknown): Failure => {
  const status = e instanceof Error ? Number(e.message.slice(0, 3)) : 0
  return status === 401 ? 'invalid' : status === 429 ? 'throttled' : 'unreachable'
}
const failureAlert: Record<Failure, [string, string]> = {
  invalid: ["Couldn't sign in", 'Check your email and password.'],
  throttled: ['Too many attempts', 'Wait a minute, then try again.'],
  unreachable: ["Couldn't reach ECHO", 'Check your connection and try again.'],
}

/** Physician sign-in (Figma "Login"): email + password, and one-click demo accounts when the backend offers them. */
export default function LoginPage() {
  const { state, signIn } = useAuth()
  const navigate = useNavigate()
  const from = (useLocation().state as { from?: string } | null)?.from ?? '/'
  const demo = useQuery({ queryKey: ['auth', 'demo-accounts'], queryFn: getDemoAccounts, retry: false })

  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [errors, setErrors] = useState<{ email?: string; password?: string }>({})
  const [failure, setFailure] = useState<Failure | null>(null)
  const [busy, setBusy] = useState(false)
  const errorCount = Object.values(errors).filter(Boolean).length
  const hasDemo = !!demo.data && demo.data.length > 0

  if (state.status === 'signed-in') return <Navigate to={from} replace />

  const finish = (session: Session) => {
    signIn(session.token, session.physician)
    navigate(from, { replace: true })
  }
  const attempt = async (run: () => Promise<Session>) => {
    setBusy(true)
    setFailure(null)
    try {
      finish(await run())
    } catch (e) {
      setFailure(failureOf(e))
      setBusy(false)
    }
  }
  const submit = (e: React.FormEvent) => {
    e.preventDefault()
    const next: typeof errors = {}
    if (!email.trim()) next.email = 'Enter your email.'
    if (!password) next.password = 'Enter your password.'
    setErrors(next)
    if (next.email || next.password) {
      document.getElementById(next.email ? ids.email : ids.password)?.focus()
      return
    }
    void attempt(() => login(email.trim(), password))
  }

  return (
    <div className="grid min-h-screen bg-background lg:grid-cols-[minmax(0,1fr)_600px]">
      <main className="flex items-center justify-center px-4 py-10 sm:px-10">
        <div className="flex w-full max-w-[400px] flex-col gap-[22px]">
          <Link to="/" className="flex items-center gap-2.5 self-start rounded-full focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring">
            <LogoMark size={36} />
            <span className="font-brand text-[22px] leading-7 font-semibold text-navy-900">Echo</span>
          </Link>
          <div className="space-y-1.5">
            <h1 className="text-[1.75rem] leading-9 font-semibold">Sign in</h1>
            <p className="text-body-sm text-muted-foreground">Use the email and password for your practice account.</p>
          </div>

          {errorCount > 0 ? (
            <Alert
              tone="destructive"
              title={`${errorCount} ${errorCount === 1 ? 'field needs' : 'fields need'} attention`}
            >
              {errors.email && errors.password
                ? 'Email and password are required.'
                : errors.email
                  ? 'Email is required.'
                  : 'Password is required.'}
            </Alert>
          ) : failure ? (
            <Alert tone="destructive" title={failureAlert[failure][0]}>
              {failureAlert[failure][1]}
              {failure === 'invalid' && hasDemo && ' Or sign in as a demo doctor below.'}
            </Alert>
          ) : (
            state.status === 'anonymous' &&
            state.reason === 'expired' && (
              <Alert tone="info" title="Your session ended">
                Sign in again to continue. Your referrals are saved.
              </Alert>
            )
          )}

          <form noValidate onSubmit={submit} className="flex flex-col gap-[22px]">
            <Field id={ids.email} label="Email" error={errors.email}>
              <Input
                type="email"
                autoComplete="username"
                placeholder={demo.data?.[0]?.email ?? 'you@practice.org'}
                value={email}
                disabled={busy}
                onChange={(e) => {
                  setEmail(e.target.value)
                  setErrors((x) => ({ ...x, email: undefined }))
                }}
                {...controlA11y(ids.email, errors.email)}
              />
            </Field>
            <Field id={ids.password} label="Password" error={errors.password}>
              <Input
                type="password"
                autoComplete="current-password"
                placeholder="Password"
                value={password}
                disabled={busy}
                onChange={(e) => {
                  setPassword(e.target.value)
                  setErrors((x) => ({ ...x, password: undefined }))
                }}
                {...controlA11y(ids.password, errors.password)}
              />
            </Field>
            <Button type="submit" disabled={busy} aria-busy={busy}>
              {busy ? 'Signing in…' : 'Sign in'}
            </Button>
          </form>

          {demo.data && demo.data.length > 0 && (
            <>
              <div className="flex items-center gap-3">
                <div className="h-px flex-1 bg-border" />
                <span className="text-xs text-muted-foreground">or try a demo doctor</span>
                <div className="h-px flex-1 bg-border" />
              </div>
              <ul className="flex flex-col gap-3">
                {demo.data.map((a) => (
                  <li key={a.id}>
                    <button
                      type="button"
                      disabled={busy}
                      onClick={() => void attempt(() => demoLogin(a.id))}
                      aria-label={`Sign in as ${a.name}, ${a.specialty}`}
                      className="flex w-full items-center gap-3 rounded-2xl border bg-card py-2.5 pr-4 pl-3 text-left hover:bg-canvas focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring disabled:cursor-not-allowed disabled:bg-secondary disabled:text-muted-foreground"
                    >
                      <Avatar name={a.name} />
                      <span className="min-w-0 flex-1">
                        <span className="block truncate text-body-sm font-medium">{a.name}</span>
                        <span className="block truncate text-xs text-muted-foreground">{a.specialty}</span>
                        <span className="block truncate text-xs text-muted-foreground">{a.email}</span>
                      </span>
                      <ArrowRight className="size-4 text-primary" aria-hidden />
                    </button>
                  </li>
                ))}
              </ul>
              <p className="text-xs text-muted-foreground">
                Each demo account has its own referrals and conversations. No real patient data.
              </p>
            </>
          )}
        </div>
      </main>

      <aside className="hidden flex-col justify-center gap-10 bg-echo-y px-16 py-12 text-white lg:flex">
        <Pulse width={472} height={120} beats={[[30, 1], [150, 0.66], [260, 0.36], [360, 0.16]]} echo={26} className="w-full" />
        <div className="space-y-3">
          <p className="font-display text-sm font-medium text-mint-300">For referring physicians</p>
          <p className="font-display text-[1.75rem] leading-9 font-semibold">Referrals with the evidence attached.</p>
        </div>
        <ol>
          {steps.map((step, i) => (
            <li key={step.title} className={cn('flex gap-4 py-4', i > 0 && 'border-t border-navy-700')}>
              <span
                aria-hidden
                className="grid size-8 shrink-0 place-items-center rounded-full border border-mint-300 font-display text-sm font-medium text-mint-300"
              >
                {i + 1}
              </span>
              <div>
                <div className="font-display font-medium">{step.title}</div>
                <div className="text-body-sm text-white/70">{step.text}</div>
              </div>
            </li>
          ))}
        </ol>
      </aside>
    </div>
  )
}
