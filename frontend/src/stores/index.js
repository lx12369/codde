import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { clearAuthStorage, readAuthSession } from '@/utils/authStorage'

export const useAppStore = defineStore('app', () => {
  const isLoading = ref(false)
  
  function setLoading(value) {
    isLoading.value = value
  }

  return { 
    isLoading, 
    setLoading
  }
})

export const useAuthStore = defineStore('auth', () => {
  const session = readAuthSession()
  const token = ref(session.token || '')
  const user = ref(session.user || null)

  const isAuthenticated = computed(() => !!token.value)

  function setToken(value) {
    token.value = value
  }

  function setUser(value) {
    user.value = value
  }

  function logout() {
    token.value = ''
    user.value = null
    clearAuthStorage()
  }

  return { 
    token,
    user,
    isAuthenticated,
    setToken, 
    setUser,
    logout
  }
})
