import { Navigate, Outlet } from 'react-router-dom'
import { ErrorState, LoadingState } from './AsyncState'
import { useAuth } from '../context/useAuth'

export default function RequireAuth() {
  const { user, loading, sessionError, checkSession } = useAuth()
  if (loading) return <LoadingState label="Checking your session" />
  if (sessionError) return <ErrorState message={sessionError} retry={() => { void checkSession() }} />
  return user ? <Outlet /> : <Navigate to="/login" replace />
}