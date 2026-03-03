<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores'
import api from '@/api'

const router = useRouter()
const authStore = useAuthStore()

const form = ref({
  username: '',
  password: '',
  rememberMe: false
})

const errors = ref({
  username: '',
  password: ''
})

const isLoading = ref(false)
const errorMessage = ref('')

function validateForm() {
  let isValid = true
  errors.value = { username: '', password: '' }

  if (!form.value.username.trim()) {
    errors.value.username = '请输入用户名'
    isValid = false
  }

  if (!form.value.password) {
    errors.value.password = '请输入密码'
    isValid = false
  }

  return isValid
}

async function handleLogin() {
  errorMessage.value = ''

  if (!validateForm()) {
    return
  }

  isLoading.value = true

  try {
    const response = await api.post('/auth/login', {
      username: form.value.username,
      password: form.value.password
    })

    const data = response.data || response
    const token = data.token
    const user = data.user

    if (!token) {
      throw new Error('\u767b\u5f55\u5931\u8d25\uff1a\u670d\u52a1\u7aef\u672a\u8fd4\u56de\u4ee4\u724c')
    }

    authStore.setToken(token)
    authStore.setUser(user)

    if (form.value.rememberMe) {
      localStorage.setItem('token', token)
      localStorage.setItem('user', JSON.stringify(user))
    } else {
      sessionStorage.setItem('token', token)
      sessionStorage.setItem('user', JSON.stringify(user))
    }

    router.push({ name: 'dashboard' })
  } catch (error) {
    console.error('Login failed:', error)
    errorMessage.value = error.response?.data?.message || error.message || '登录失败，请检查用户名和密码'
  } finally {
    isLoading.value = false
  }
}
</script>

<template>
  <div class="min-h-screen flex items-center justify-center bg-gradient-to-br from-blue-50 to-blue-100 py-12 px-4 sm:px-6 lg:px-8">
    <div class="max-w-md w-full">
      <div class="bg-white rounded-2xl shadow-xl p-8 space-y-8">
        <div class="text-center">
          <h1 class="text-3xl font-bold text-[#1e40af]">
            织雾拼豆会员管理系统
          </h1>
          <p class="mt-2 text-gray-600">
            请登录以访问系统
          </p>
        </div>

        <form @submit.prevent="handleLogin" class="space-y-6">
          <div v-if="errorMessage" class="bg-red-50 border border-red-200 text-red-600 px-4 py-3 rounded-lg text-sm">
            {{ errorMessage }}
          </div>

          <div class="space-y-2">
            <label for="username" class="block text-sm font-medium text-gray-700">
              用户名
            </label>
            <input
              id="username"
              v-model="form.username"
              type="text"
              autocomplete="username"
              :class="[
                'w-full px-4 py-3 border rounded-lg focus:outline-none focus:ring-2 focus:ring-[#1e40af] focus:border-transparent transition-all duration-200',
                errors.username ? 'border-red-500 bg-red-50' : 'border-gray-300 hover:border-gray-400'
              ]"
              placeholder="请输入用户名"
            />
            <p v-if="errors.username" class="text-red-500 text-xs mt-1">
              {{ errors.username }}
            </p>
          </div>

          <div class="space-y-2">
            <label for="password" class="block text-sm font-medium text-gray-700">
              密码
            </label>
            <input
              id="password"
              v-model="form.password"
              type="password"
              autocomplete="current-password"
              :class="[
                'w-full px-4 py-3 border rounded-lg focus:outline-none focus:ring-2 focus:ring-[#1e40af] focus:border-transparent transition-all duration-200',
                errors.password ? 'border-red-500 bg-red-50' : 'border-gray-300 hover:border-gray-400'
              ]"
              placeholder="请输入密码"
            />
            <p v-if="errors.password" class="text-red-500 text-xs mt-1">
              {{ errors.password }}
            </p>
          </div>

          <div class="flex items-center">
            <input
              id="remember-me"
              v-model="form.rememberMe"
              type="checkbox"
              class="h-4 w-4 text-[#1e40af] focus:ring-[#1e40af] border-gray-300 rounded cursor-pointer"
            />
            <label for="remember-me" class="ml-2 block text-sm text-gray-700 cursor-pointer">
              记住我
            </label>
          </div>

          <button
            type="submit"
            :disabled="isLoading"
            :class="[
              'w-full py-3 px-4 rounded-lg text-white font-medium transition-all duration-200',
              isLoading
                ? 'bg-gray-400 cursor-not-allowed'
                : 'bg-[#1e40af] hover:bg-[#1e3a8a] hover:shadow-lg active:transform active:scale-[0.98]'
            ]"
          >
            <span v-if="isLoading" class="flex items-center justify-center">
              <svg class="animate-spin -ml-1 mr-3 h-5 w-5 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
                <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
              </svg>
              登录中...
            </span>
            <span v-else>登录</span>
          </button>
        </form>
      </div>

      <p class="mt-4 text-center text-sm text-gray-500">
        &copy; 2024 织雾拼豆会员管理系统. 版权所有。
      </p>
    </div>
  </div>
</template>

<style scoped>
</style>
