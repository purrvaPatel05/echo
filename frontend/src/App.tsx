import { MessagesSquare, Send, Stethoscope } from 'lucide-react'
import { NavLink, Route, Routes } from 'react-router-dom'
import { useMe } from '@/api/hooks'
import { useReferralRealtime } from '@/api/socket'
import { cn } from '@/lib/utils'
import CaseDetailPage from '@/pages/CaseDetailPage'
import CasesPage from '@/pages/CasesPage'
import ConsultsPage from '@/pages/ConsultsPage'
import ReferralsPage from '@/pages/ReferralsPage'

const nav = [
  { to: '/', label: 'Cases', icon: Stethoscope, end: true },
  { to: '/referrals', label: 'Referrals', icon: Send },
  { to: '/consults', label: 'Consults', icon: MessagesSquare },
]

export default function App() {
  const { data: me } = useMe()
  useReferralRealtime()

  return (
    <div className="min-h-screen bg-secondary/40">
      <header className="border-b bg-background">
        <div className="mx-auto flex h-14 max-w-5xl items-center gap-6 px-4">
          <span className="font-semibold text-primary">OpenEvidence Referrals</span>
          <nav className="flex gap-1">
            {nav.map(({ to, label, icon: Icon, end }) => (
              <NavLink
                key={to}
                to={to}
                end={end}
                className={({ isActive }) =>
                  cn(
                    'flex items-center gap-2 rounded-md px-3 py-1.5 text-sm',
                    isActive ? 'bg-secondary font-medium' : 'text-muted-foreground hover:bg-secondary',
                  )
                }
              >
                <Icon className="size-4" />
                {label}
              </NavLink>
            ))}
          </nav>
          <span className="ml-auto text-sm text-muted-foreground">{me?.name}</span>
        </div>
      </header>
      <main className="mx-auto max-w-5xl px-4 py-6">
        <Routes>
          <Route path="/" element={<CasesPage />} />
          <Route path="/cases/:caseId" element={<CaseDetailPage />} />
          <Route path="/referrals" element={<ReferralsPage />} />
          <Route path="/consults" element={<ConsultsPage />} />
        </Routes>
      </main>
    </div>
  )
}
