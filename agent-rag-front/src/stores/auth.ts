import { create } from 'zustand'
import { api, clearToken, setToken } from '../api/client'
import type { User } from '../types'

interface AuthState {
  user: User | null
  login: (username: string, password: string) => Promise<void>
  logout: () => void
}

export const useAuthStore = create<AuthState>((set) => ({
  user: null,
  async login(username, password) {
    const data = await api.post<{ token: string; user: User }>('/api/auth/login', {
      username,
      password,
    })
    setToken(data.token)
    set({ user: data.user })
  },
  logout() {
    clearToken()
    set({ user: null })
    window.location.href = '/login'
  },
}))
