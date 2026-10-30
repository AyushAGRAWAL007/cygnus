import { createContext, useContext } from 'react'
import type { AuthUser, LoginInput, RegisterInput } from './api'

export interface AuthState {
  user: AuthUser | null
  loading: boolean
  error: string
  login: (input: LoginInput) => Promise<void>
  register: (input: RegisterInput) => Promise<void>
  logout: () => Promise<void>
  refresh: () => Promise<void>
}
export const AuthContext = createContext<AuthState | null>(null)
export function useAuth(): AuthState {
  const value = useContext(AuthContext)
  if (!value) throw new Error('AuthProvider is required')
  return value
}
