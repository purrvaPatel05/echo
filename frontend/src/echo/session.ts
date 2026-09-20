// The signed-in session token (AUTH_MODE=session on the backend). Kept in localStorage so a reload stays signed in;
// every access is wrapped because storage can be blocked or empty (private windows, cleared site data).
const KEY = 'echo.session'

export const getToken = (): string | null => {
  try {
    return localStorage.getItem(KEY)
  } catch {
    return null
  }
}
export const setToken = (token: string) => {
  try {
    localStorage.setItem(KEY, token)
  } catch {
    /* storage unavailable: the session lasts until the page closes */
  }
}
export const clearToken = () => {
  try {
    localStorage.removeItem(KEY)
  } catch {
    /* nothing to clear */
  }
}

/** Fired when the API answers 401 to a request that carried a token: the session ended. */
export const UNAUTHORIZED_EVENT = 'echo:unauthorized'
