import { LayoutDashboard, MessagesSquare } from 'lucide-react'
import { Link, Navigate, NavLink, Route, Routes, useLocation, useParams } from 'react-router-dom'
import { useReferralRealtime } from '@/api/socket'
import { AccountMenu } from '@/components/echo/AccountMenu'
import { LogoMark, Pulse } from '@/components/echo/Pulse'
import { AuthProvider } from '@/echo/auth'
import { useAuth } from '@/echo/authContext'
import { useEchoMe } from '@/echo/hooks'
import { cn } from '@/lib/utils'
import AnalysisPage from '@/pages/AnalysisPage'
import ApprovalPage from '@/pages/ApprovalPage'
import BookedPage from '@/pages/BookedPage'
import CaseDetailPage from '@/pages/CaseDetailPage'
import CasesPage from '@/pages/CasesPage'
import ConsultsPage from '@/pages/ConsultsPage'
import DashboardPage from '@/pages/DashboardPage'
import LoginPage from '@/pages/LoginPage'
import MatchesPage from '@/pages/MatchesPage'
import NewReferralPage from '@/pages/NewReferralPage'
import PatientConfirmationPage from '@/pages/PatientConfirmationPage'
import ReferralsPage from '@/pages/ReferralsPage'
import TrackingPage from '@/pages/TrackingPage'
import TrialsPage from '@/pages/TrialsPage'

/** The old per-referral consult page is now the New consult form with that referral chosen. */
function OldConsultLink() {
  const { referralId = '' } = useParams()
  return <Navigate to={`/consults/new?referral=${referralId}`} replace />
}

// `alsoActiveFor`: the referral flow (new, analysis, matches...) belongs to Dashboard, as in Figma.
const nav = [
  { to: '/', label: 'Dashboard', icon: LayoutDashboard, end: true, alsoActiveFor: '/referral' },
  { to: '/consults', label: 'Consults', icon: MessagesSquare, alsoActiveFor: undefined },
]

const navLink = (isActive: boolean) =>
  cn(
    'flex h-[46px] items-center gap-3 rounded-full px-4 font-display text-sm font-medium focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-mint-300',
    isActive ? 'bg-violet-600 text-white' : 'text-white/75 hover:bg-white/10 hover:text-white',
  )

/**
 * Figma "Sidebar": a 248px navy panel with the logo, two destinations, the heartbeat, and the profile. Below the
 * `lg` breakpoint it becomes a top bar with the same pieces.
 */
function Shell() {
  const { data: me } = useEchoMe()
  const { pathname } = useLocation()
  useReferralRealtime()

  const items = nav.map(({ to, label, icon: Icon, end, alsoActiveFor }) => (
    <NavLink
      key={to}
      to={to}
      end={end}
      className={({ isActive }) => navLink(isActive || !!(alsoActiveFor && pathname.startsWith(alsoActiveFor)))}
    >
      {({ isActive }) => {
        const active = isActive || !!(alsoActiveFor && pathname.startsWith(alsoActiveFor))
        return (
          <>
            <Icon className="size-5" aria-hidden />
            {label}
            {active && <span aria-hidden className="ml-auto size-2 rounded-full bg-mint-300" />}
          </>
        )
      }}
    </NavLink>
  ))

  const brand = (
    <Link
      to="/"
      className="flex items-center gap-2.5 rounded-full focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-mint-300"
    >
      <LogoMark size={34} />
      <span className="font-brand text-[22px] leading-7 font-semibold text-white">Echo</span>
    </Link>
  )

  return (
    <div className="min-h-screen bg-canvas">
      <aside className="fixed inset-y-0 left-0 z-30 hidden w-[248px] flex-col bg-echo-y px-4 pt-7 pb-5 lg:flex">
        <div className="pl-2">{brand}</div>
        <nav aria-label="Main" className="mt-7 flex flex-col gap-1.5">
          {items}
        </nav>
        <div className="mt-auto pb-5">
          <Pulse width={216} height={64} beats={[[14, 1], [96, 0.6], [160, 0.3]]} strokeWidth={2} opacity={0.55} echo={10} className="w-full" />
        </div>
        {me && <AccountMenu me={me} />}
      </aside>

      <header className="bg-echo-x lg:hidden">
        <div className="flex flex-wrap items-center gap-x-4 gap-y-2 px-4 py-3">
          {brand}
          <nav aria-label="Main" className="order-3 flex w-full gap-1 sm:order-none sm:w-auto">
            {items}
          </nav>
          {me && (
            <div className="ml-auto">
              <AccountMenu me={me} variant="bar" />
            </div>
          )}
        </div>
      </header>

      <main className="mx-auto max-w-[1240px] px-4 py-8 lg:ml-[248px] lg:max-w-none lg:px-10">
        <div className="mx-auto max-w-[1160px]">
          <Routes>
            <Route path="/" element={<DashboardPage />} />
            <Route path="/referral/new" element={<NewReferralPage />} />
            <Route path="/referral/:referralId/analysis" element={<AnalysisPage />} />
            <Route path="/referral/:referralId/matches" element={<MatchesPage />} />
            <Route path="/referral/:referralId/review" element={<ApprovalPage />} />
            <Route path="/referral/:referralId/booked" element={<BookedPage />} />
            <Route path="/referral/:referralId/confirmation" element={<PatientConfirmationPage />} />
            <Route path="/referral/:referralId/consult" element={<OldConsultLink />} />
            <Route path="/referral/:referralId/trials" element={<TrialsPage />} />
            <Route path="/referral/:referralId" element={<TrackingPage />} />
            <Route path="/consults" element={<ConsultsPage />} />
            <Route path="/consults/new" element={<ConsultsPage />} />
            <Route path="/consults/:threadId" element={<ConsultsPage />} />
            {/* Original prototype screens, still wired to the real backend. Not in the nav. */}
            <Route path="/cases" element={<CasesPage />} />
            <Route path="/cases/:caseId" element={<CaseDetailPage />} />
            <Route path="/referrals" element={<ReferralsPage />} />
          </Routes>
        </div>
      </main>
    </div>
  )
}

/** Shows the login page until there is a valid session (only when the backend has a login; see AuthProvider). */
function Gate() {
  const { state } = useAuth()
  const location = useLocation()
  if (state.status === 'loading') {
    return (
      <div role="status" className="grid min-h-screen place-items-center bg-canvas text-body-sm text-muted-foreground">
        Loading…
      </div>
    )
  }
  if (state.status === 'anonymous') {
    return location.pathname === '/login' ? (
      <LoginPage />
    ) : (
      <Navigate to="/login" replace state={{ from: location.pathname + location.search }} />
    )
  }
  return location.pathname === '/login' ? <LoginPage /> : <Shell />
}

export default function App() {
  return (
    <AuthProvider>
      <Gate />
    </AuthProvider>
  )
}
