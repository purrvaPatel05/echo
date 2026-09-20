import { request } from '@/api/client'
import type { Physician } from './types'

/** What the backend says about signing in. `login: false` = no login screen (local dev mode). */
export interface AuthConfig {
  login: boolean
  demoAccounts: boolean
}
export interface DemoAccount {
  id: string
  name: string
  specialty: string
  organization: string
}
export interface Session {
  token: string
  physician: Physician
}

// Real backend only. Mock mode has no accounts and never calls these.
export const getAuthConfig = () => request<AuthConfig>('/echo/auth/config')
export const getDemoAccounts = () => request<DemoAccount[]>('/echo/auth/demo-accounts')
export const login = (email: string, password: string) =>
  request<Session>('/echo/auth/login', { method: 'POST', body: JSON.stringify({ email, password }) })
export const demoLogin = (physicianId: string) =>
  request<Session>('/echo/auth/demo-login', { method: 'POST', body: JSON.stringify({ physicianId }) })
