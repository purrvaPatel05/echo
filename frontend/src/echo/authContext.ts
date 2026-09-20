import { createContext, useContext } from 'react'
import type { Physician } from './types'

export type AuthState =
  | { status: 'loading' }
  | { status: 'anonymous'; reason?: 'expired' }
  /** `canSignOut` is false without a login screen (mock, or a dev backend that signs everyone in). */
  | { status: 'signed-in'; me: Physician | null; canSignOut: boolean }

export interface AuthContextValue {
  state: AuthState
  signIn: (token: string, me: Physician) => void
  signOut: () => void
}

export const AuthContext = createContext<AuthContextValue | null>(null)

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used inside AuthProvider')
  return ctx
}
