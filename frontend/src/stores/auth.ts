import { ref } from 'vue'

import { fetchCurrentUser, loginAccount, registerAccount } from '../api'
import type { Credentials, User } from '../types'

const user = ref<User | null>(null)
const ready = ref(false)

function persistSession(accessToken: string, currentUser: User): void {
  localStorage.setItem('bead_access_token', accessToken)
  localStorage.setItem('bead_user', JSON.stringify(currentUser))
  user.value = currentUser
}

function clearSession(): void {
  localStorage.removeItem('bead_access_token')
  localStorage.removeItem('bead_user')
  user.value = null
}

export function useAuthStore() {
  async function initialize(): Promise<void> {
    if (ready.value) return
    const cached = localStorage.getItem('bead_user')
    if (cached) {
      try {
        user.value = JSON.parse(cached) as User
      } catch {
        clearSession()
      }
    }
    if (localStorage.getItem('bead_access_token')) {
      try {
        user.value = await fetchCurrentUser()
        localStorage.setItem('bead_user', JSON.stringify(user.value))
      } catch {
        clearSession()
      }
    }
    ready.value = true
  }

  async function login(credentials: Credentials): Promise<void> {
    const result = await loginAccount(credentials)
    persistSession(result.access_token, result.user)
  }

  async function register(credentials: Credentials): Promise<void> {
    const result = await registerAccount(credentials)
    persistSession(result.access_token, result.user)
  }

  return { user, ready, initialize, login, register, logout: clearSession }
}
