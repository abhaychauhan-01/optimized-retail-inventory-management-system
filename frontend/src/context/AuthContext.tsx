import { useCallback, useEffect, useState, type PropsWithChildren } from 'react'
import { authLogin, authLogout, errorMessage, getCurrentUser, isUnauthorizedError } from '../services/api'
import type { AuthUser } from '../types'
import { AuthContext } from './auth-context'

export function AuthProvider({ children }: PropsWithChildren) {
  const [user, setUser] = useState<AuthUser | null>(null)
  const [loading, setLoading] = useState(true)
  const [sessionError, setSessionError] = useState('')

  const loadSession = useCallback(async () => {
    try {
      setUser(await getCurrentUser())
      setSessionError('')
    } catch (reason) {
      setUser(null)
      setSessionError(isUnauthorizedError(reason) ? '' : errorMessage(reason))
    } finally {
      setLoading(false)
    }
  }, [])

  const checkSession = useCallback(async () => {
    setLoading(true)
    await loadSession()
  }, [loadSession])

  useEffect(() => {
    let active = true
    void getCurrentUser()
      .then((authenticatedUser) => {
        if (active) {
          setUser(authenticatedUser)
          setSessionError('')
        }
      })
      .catch((reason: unknown) => {
        if (active) {
          setUser(null)
          setSessionError(isUnauthorizedError(reason) ? '' : errorMessage(reason))
        }
      })
      .finally(() => {
        if (active) setLoading(false)
      })
    const handleExpired = () => setUser(null)
    window.addEventListener('auth:expired', handleExpired)
    return () => {
      active = false
      window.removeEventListener('auth:expired', handleExpired)
    }
  }, [])

  const signIn = useCallback(async (email: string, password: string) => {
    const authenticatedUser = await authLogin(email, password)
    setUser(authenticatedUser)
    setSessionError('')
  }, [])

  const signOut = useCallback(async () => {
    await authLogout()
    setUser(null)
  }, [])

  return <AuthContext.Provider value={{ user, loading, sessionError, checkSession, signIn, signOut }}>{children}</AuthContext.Provider>
}
