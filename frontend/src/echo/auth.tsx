import { useQueryClient } from '@tanstack/react-query'
import { useCallback, useEffect, useMemo, useState } from 'react'
import { echoApi, usingMock } from './api'
import { getAuthConfig } from './authApi'
import { AuthContext, type AuthState } from './authContext'
import { clearToken, getToken, setToken, UNAUTHORIZED_EVENT } from './session'
import type { Physician } from './types'

/**
 * Decides whether the app shows the login page. Mock mode and dev backends have no login. With a session backend
 * (`/api/echo/auth/config` says login: true) the app needs a valid token: none, or one the API rejects, means sign in.
 */
export function AuthProvider({ children }: { children: React.ReactNode }) {
  const qc = useQueryClient()
  const [state, setState] = useState<AuthState>({ status: 'loading' })

  useEffect(() => {
    let cancelled = false
    ;(async () => {
      const config = usingMock ? { login: false } : await getAuthConfig().catch(() => ({ login: false }))
      if (config.login && !getToken()) return !cancelled && setState({ status: 'anonymous' })
      try {
        const me = await echoApi.me()
        if (!cancelled) setState({ status: 'signed-in', me, canSignOut: config.login })
      } catch {
        if (cancelled) return
        if (config.login) {
          clearToken()
          setState({ status: 'anonymous', reason: 'expired' })
        } else {
          setState({ status: 'signed-in', me: null, canSignOut: false }) // no login to fall back to: let the screens show their own errors
        }
      }
    })()
    return () => {
      cancelled = true
    }
  }, [])

  const signIn = useCallback(
    (token: string, me: Physician) => {
      setToken(token)
      qc.clear() // never show the previous account's data
      setState({ status: 'signed-in', me, canSignOut: true })
    },
    [qc],
  )
  const signOut = useCallback(() => {
    clearToken()
    qc.clear()
    setState({ status: 'anonymous' })
  }, [qc])

  // The API said the session is no longer valid.
  useEffect(() => {
    const onUnauthorized = () => {
      clearToken()
      qc.clear()
      setState((s) => (s.status === 'signed-in' && s.canSignOut ? { status: 'anonymous', reason: 'expired' } : s))
    }
    window.addEventListener(UNAUTHORIZED_EVENT, onUnauthorized)
    return () => window.removeEventListener(UNAUTHORIZED_EVENT, onUnauthorized)
  }, [qc])

  const value = useMemo(() => ({ state, signIn, signOut }), [state, signIn, signOut])
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}
