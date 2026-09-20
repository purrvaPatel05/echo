import { useAuth } from '@/echo/authContext'
import { initials } from '@/echo/referral'
import type { Physician } from '@/echo/types'
import { cn } from '@/lib/utils'

/**
 * The signed-in physician (Figma "Profile"): avatar, name, specialty, and Sign out. Without a login (mock, dev
 * backend) there is nothing to sign out of, so it is just the name. `bar` is the compact form for the small-screen top bar.
 */
export function AccountMenu({ me, variant = 'sidebar' }: { me: Physician; variant?: 'sidebar' | 'bar' }) {
  const { state, signOut } = useAuth()
  const canSignOut = state.status === 'signed-in' && state.canSignOut
  const bar = variant === 'bar'

  const signOutButton = canSignOut && (
    <button
      type="button"
      onClick={signOut}
      className={cn(
        'rounded-full text-body-sm font-medium text-white/80 hover:text-white focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-mint-300',
        bar ? 'px-3 py-1.5' : 'px-1 py-0.5 text-left',
      )}
    >
      Sign out
    </button>
  )

  return (
    <div className={cn(bar ? 'flex items-center gap-2' : 'flex flex-col gap-2.5 rounded-[18px] bg-navy-800 p-3.5')}>
      <div className="flex min-w-0 items-center gap-2.5">
        <span
          aria-hidden
          className="grid size-10 shrink-0 place-items-center rounded-full bg-violet-600 font-display text-sm font-medium text-white"
        >
          {initials(me.name)}
        </span>
        <span className={cn('min-w-0', bar && 'hidden sm:block')}>
          <span className="block truncate font-display text-sm font-medium text-white">{me.name}</span>
          <span className="block truncate text-xs text-mint-300">{me.specialty}</span>
        </span>
      </div>
      {signOutButton}
    </div>
  )
}
