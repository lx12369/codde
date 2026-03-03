import { defineStore } from 'pinia'
import { ref, computed } from 'vue'

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
  const token = ref(localStorage.getItem('token') || sessionStorage.getItem('token') || '')
  
  const userJson = localStorage.getItem('user') || sessionStorage.getItem('user')
  const user = ref(userJson ? JSON.parse(userJson) : null)

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
    localStorage.removeItem('token')
    localStorage.removeItem('user')
    sessionStorage.removeItem('token')
    sessionStorage.removeItem('user')
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
