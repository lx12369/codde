<script setup>
import { ref, reactive, onMounted } from 'vue'
import api from '@/api'

const activeTab = ref('security')

const passwordForm = reactive({
  currentPassword: '',
  newPassword: '',
  confirmPassword: ''
})

const passwordErrors = reactive({
  currentPassword: '',
  newPassword: '',
  confirmPassword: ''
})

const passwordLoading = ref(false)
const passwordSuccess = ref('')
const passwordError = ref('')

const dataStatus = reactive({
  storageLocation: '',
  dataSize: '0 KB',
  customerCount: 0,
  transactionCount: 0
})

const dataLoading = ref(false)
const showClearConfirm = ref(false)
const clearLoading = ref(false)

const fileInput = ref(null)
const restoreLoading = ref(false)

const formatFileSize = (bytes) => {
  const size = Number(bytes)
  if (!Number.isFinite(size) || size <= 0) return '0 KB'

  if (size < 1024) return `${size} B`
  if (size < 1024 * 1024) return `${(size / 1024).toFixed(2)} KB`
  if (size < 1024 * 1024 * 1024) return `${(size / (1024 * 1024)).toFixed(2)} MB`
  return `${(size / (1024 * 1024 * 1024)).toFixed(2)} GB`
}

const validatePasswordForm = () => {
  let isValid = true
  passwordErrors.currentPassword = ''
  passwordErrors.newPassword = ''
  passwordErrors.confirmPassword = ''
  passwordSuccess.value = ''
  passwordError.value = ''

  if (!passwordForm.currentPassword) {
    passwordErrors.currentPassword = '请输入当前密码'
    isValid = false
  }

  if (!passwordForm.newPassword) {
    passwordErrors.newPassword = '请输入新密码'
    isValid = false
  } else if (passwordForm.newPassword.length < 6) {
    passwordErrors.newPassword = '密码至少需要6个字符'
    isValid = false
  }

  if (!passwordForm.confirmPassword) {
    passwordErrors.confirmPassword = '请确认新密码'
    isValid = false
  } else if (passwordForm.newPassword !== passwordForm.confirmPassword) {
    passwordErrors.confirmPassword = '两次输入的密码不一致'
    isValid = false
  }

  return isValid
}

const changePassword = async () => {
  if (!validatePasswordForm()) return

  passwordLoading.value = true
  try {
    await api.put('/auth/password', {
      current_password: passwordForm.currentPassword,
      new_password: passwordForm.newPassword
    })
    passwordSuccess.value = '密码修改成功'
    passwordForm.currentPassword = ''
    passwordForm.newPassword = ''
    passwordForm.confirmPassword = ''
  } catch (error) {
    console.error('Failed to change password:', error)
    passwordError.value = error.response?.data?.message || '密码修改失败'
  } finally {
    passwordLoading.value = false
  }
}

const fetchDataStatus = async () => {
  dataLoading.value = true
  try {
    const [statsResponse, backupResponse] = await Promise.all([
      api.get('/dashboard/stats'),
      api.get('/data/backup')
    ])

    const stats = statsResponse?.data || statsResponse || {}
    const backupData = backupResponse?.data || backupResponse || {}
    const backupText = JSON.stringify(backupData)

    dataStatus.storageLocation = '本地数据库'
    dataStatus.dataSize = formatFileSize(new Blob([backupText]).size)
    dataStatus.customerCount = Number(stats.total_customers ?? backupData?.customers?.length ?? 0)
    dataStatus.transactionCount = Number(stats.total_transactions ?? backupData?.transactions?.length ?? 0)
  } catch (error) {
    console.error('Failed to fetch data status:', error)
    dataStatus.storageLocation = '本地数据库'
    dataStatus.dataSize = '0 KB'
    dataStatus.customerCount = 0
    dataStatus.transactionCount = 0
  } finally {
    dataLoading.value = false
  }
}

const backupData = async () => {
  dataLoading.value = true
  try {
    const response = await api.get('/data/backup')
    const payload = response?.data || response || {}
    const content = JSON.stringify(payload, null, 2)
    const blob = new Blob([content], { type: 'application/json;charset=utf-8' })
    const url = window.URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    const timestamp = new Date().toISOString().slice(0, 19).replace(/[:-]/g, '')
    link.setAttribute('download', `backup_${timestamp}.json`)
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
    window.URL.revokeObjectURL(url)
  } catch (error) {
    console.error('Failed to backup data:', error)
    alert('备份失败，请重试。')
  } finally {
    dataLoading.value = false
  }
}

const triggerRestore = () => {
  fileInput.value?.click()
}

const restoreData = async (event) => {
  const file = event.target.files?.[0]
  if (!file) return

  if (!file.name.endsWith('.json')) {
    alert('请选择JSON文件')
    return
  }

  restoreLoading.value = true
  try {
    const fileContent = await file.text()
    const jsonData = JSON.parse(fileContent)

    await api.post('/data/restore', jsonData)
    alert('数据恢复成功')
    fetchDataStatus()
  } catch (error) {
    console.error('Failed to restore data:', error)
    alert('恢复失败，请检查文件格式。')
  } finally {
    restoreLoading.value = false
    if (fileInput.value) {
      fileInput.value.value = ''
    }
  }
}

const confirmClearData = () => {
  showClearConfirm.value = true
}

const clearAllData = async () => {
  clearLoading.value = true
  try {
    await api.delete('/data/clear')
    showClearConfirm.value = false
    fetchDataStatus()
    alert('所有数据已清除')
  } catch (error) {
    console.error('Failed to clear data:', error)
    alert('清除数据失败，请重试。')
  } finally {
    clearLoading.value = false
  }
}

const formatNumber = (num) => {
  if (num === null || num === undefined) return '0'
  return num.toLocaleString()
}

onMounted(() => {
  fetchDataStatus()
})
</script>

<template>
  <div class="space-y-6">
    <div>
      <h1 class="text-2xl font-bold text-gray-800">系统设置</h1>
      <p class="text-gray-500 mt-1">配置系统参数和管理数据</p>
    </div>

    <div class="bg-white rounded-lg shadow-sm">
      <div class="border-b border-gray-200">
        <nav class="flex -mb-px">
          <button
            @click="activeTab = 'security'"
            :class="[
              'px-6 py-4 text-sm font-medium border-b-2 transition-colors',
              activeTab === 'security'
                ? 'border-[#1e40af] text-[#1e40af]'
                : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
            ]"
          >
            <div class="flex items-center gap-2">
              <svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z" />
              </svg>
              安全设置
            </div>
          </button>
          <button
            @click="activeTab = 'data'"
            :class="[
              'px-6 py-4 text-sm font-medium border-b-2 transition-colors',
              activeTab === 'data'
                ? 'border-[#1e40af] text-[#1e40af]'
                : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
            ]"
          >
            <div class="flex items-center gap-2">
              <svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 7v10c0 2.21 3.582 4 8 4s8-1.79 8-4V7M4 7c0 2.21 3.582 4 8 4s8-1.79 8-4M4 7c0-2.21 3.582-4 8-4s8 1.79 8 4m0 5c0 2.21-3.582 4-8 4s-8-1.79-8-4" />
              </svg>
              数据管理
            </div>
          </button>
        </nav>
      </div>

      <div class="p-6">
        <div v-if="activeTab === 'security'" class="max-w-md">
          <h2 class="text-lg font-medium text-gray-900 mb-6">修改密码</h2>

          <div v-if="passwordSuccess" class="mb-4 p-4 bg-green-50 border border-green-200 rounded-lg">
            <div class="flex items-center gap-2">
              <svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5 text-green-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7" />
              </svg>
              <span class="text-green-800">{{ passwordSuccess }}</span>
            </div>
          </div>

          <div v-if="passwordError" class="mb-4 p-4 bg-red-50 border border-red-200 rounded-lg">
            <div class="flex items-center gap-2">
              <svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5 text-red-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
              <span class="text-red-800">{{ passwordError }}</span>
            </div>
          </div>

          <form @submit.prevent="changePassword" class="space-y-4">
            <div>
              <label for="currentPassword" class="block text-sm font-medium text-gray-700 mb-1">当前密码</label>
              <input
                id="currentPassword"
                v-model="passwordForm.currentPassword"
                type="password"
                :class="[
                  'w-full px-3 py-2 border rounded-lg focus:outline-none focus:ring-2 focus:ring-[#1e40af] focus:border-transparent',
                  passwordErrors.currentPassword ? 'border-red-500' : 'border-gray-300'
                ]"
                placeholder="请输入当前密码"
              />
              <p v-if="passwordErrors.currentPassword" class="text-red-500 text-xs mt-1">{{ passwordErrors.currentPassword }}</p>
            </div>

            <div>
              <label for="newPassword" class="block text-sm font-medium text-gray-700 mb-1">新密码</label>
              <input
                id="newPassword"
                v-model="passwordForm.newPassword"
                type="password"
                :class="[
                  'w-full px-3 py-2 border rounded-lg focus:outline-none focus:ring-2 focus:ring-[#1e40af] focus:border-transparent',
                  passwordErrors.newPassword ? 'border-red-500' : 'border-gray-300'
                ]"
                placeholder="请输入新密码"
              />
              <p v-if="passwordErrors.newPassword" class="text-red-500 text-xs mt-1">{{ passwordErrors.newPassword }}</p>
            </div>

            <div>
              <label for="confirmPassword" class="block text-sm font-medium text-gray-700 mb-1">确认新密码</label>
              <input
                id="confirmPassword"
                v-model="passwordForm.confirmPassword"
                type="password"
                :class="[
                  'w-full px-3 py-2 border rounded-lg focus:outline-none focus:ring-2 focus:ring-[#1e40af] focus:border-transparent',
                  passwordErrors.confirmPassword ? 'border-red-500' : 'border-gray-300'
                ]"
                placeholder="请确认新密码"
              />
              <p v-if="passwordErrors.confirmPassword" class="text-red-500 text-xs mt-1">{{ passwordErrors.confirmPassword }}</p>
            </div>

            <button
              type="submit"
              :disabled="passwordLoading"
              class="w-full px-4 py-2 bg-[#1e40af] text-white rounded-lg hover:bg-[#1e3a8a] transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            >
              <span v-if="passwordLoading" class="flex items-center justify-center">
                <svg class="animate-spin -ml-1 mr-2 h-4 w-4 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                  <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
                  <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                </svg>
                处理中...
              </span>
              <span v-else>修改密码</span>
            </button>
          </form>
        </div>

        <div v-if="activeTab === 'data'" class="space-y-6">
          <div class="bg-gray-50 rounded-lg p-6">
            <h3 class="text-lg font-medium text-gray-900 mb-4">数据存储状态</h3>
            <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
              <div class="bg-white rounded-lg p-4 shadow-sm">
                <div class="flex items-center gap-3">
                  <div class="p-2 bg-blue-100 rounded-lg">
                    <svg xmlns="http://www.w3.org/2000/svg" class="h-6 w-6 text-blue-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 7v10a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-6l-2-2H5a2 2 0 00-2 2z" />
                    </svg>
                  </div>
                  <div>
                    <p class="text-xs text-gray-500">存储位置</p>
                    <p class="text-sm font-medium text-gray-900">{{ dataStatus.storageLocation }}</p>
                  </div>
                </div>
              </div>

              <div class="bg-white rounded-lg p-4 shadow-sm">
                <div class="flex items-center gap-3">
                  <div class="p-2 bg-green-100 rounded-lg">
                    <svg xmlns="http://www.w3.org/2000/svg" class="h-6 w-6 text-green-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                    </svg>
                  </div>
                  <div>
                    <p class="text-xs text-gray-500">数据大小</p>
                    <p class="text-sm font-medium text-gray-900">{{ dataStatus.dataSize }}</p>
                  </div>
                </div>
              </div>

              <div class="bg-white rounded-lg p-4 shadow-sm">
                <div class="flex items-center gap-3">
                  <div class="p-2 bg-purple-100 rounded-lg">
                    <svg xmlns="http://www.w3.org/2000/svg" class="h-6 w-6 text-purple-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0zm6 3a2 2 0 11-4 0 2 2 0 014 0zM7 10a2 2 0 11-4 0 2 2 0 014 0z" />
                    </svg>
                  </div>
                  <div>
                    <p class="text-xs text-gray-500">客户数量</p>
                    <p class="text-sm font-medium text-gray-900">{{ formatNumber(dataStatus.customerCount) }}</p>
                  </div>
                </div>
              </div>

              <div class="bg-white rounded-lg p-4 shadow-sm">
                <div class="flex items-center gap-3">
                  <div class="p-2 bg-orange-100 rounded-lg">
                    <svg xmlns="http://www.w3.org/2000/svg" class="h-6 w-6 text-orange-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-3 7h3m-3 4h3m-6-4h.01M9 16h.01" />
                    </svg>
                  </div>
                  <div>
                    <p class="text-xs text-gray-500">交易记录</p>
                    <p class="text-sm font-medium text-gray-900">{{ formatNumber(dataStatus.transactionCount) }}</p>
                  </div>
                </div>
              </div>
            </div>
          </div>

          <div class="grid grid-cols-1 lg:grid-cols-3 gap-6">
            <div class="bg-white border border-gray-200 rounded-lg p-6">
              <div class="flex items-center gap-3 mb-4">
                <div class="p-2 bg-green-100 rounded-lg">
                  <svg xmlns="http://www.w3.org/2000/svg" class="h-6 w-6 text-green-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-8l-4-4m0 0L8 8m4-4v12" />
                  </svg>
                </div>
                <h3 class="text-lg font-medium text-gray-900">数据备份</h3>
              </div>
              <p class="text-sm text-gray-500 mb-4">将所有系统数据导出为JSON文件进行备份。</p>
              <button
                @click="backupData"
                :disabled="dataLoading"
                class="w-full px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
              >
                <span v-if="dataLoading" class="flex items-center justify-center">
                  <svg class="animate-spin -ml-1 mr-2 h-4 w-4 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                    <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
                    <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                  </svg>
                  备份中...
                </span>
                <span v-else>备份数据到文件</span>
              </button>
            </div>

            <div class="bg-white border border-gray-200 rounded-lg p-6">
              <div class="flex items-center gap-3 mb-4">
                <div class="p-2 bg-blue-100 rounded-lg">
                  <svg xmlns="http://www.w3.org/2000/svg" class="h-6 w-6 text-blue-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
                  </svg>
                </div>
                <h3 class="text-lg font-medium text-gray-900">数据恢复</h3>
              </div>
              <p class="text-sm text-gray-500 mb-4">上传JSON备份文件恢复系统数据。</p>
              <input
                ref="fileInput"
                type="file"
                accept=".json"
                class="hidden"
                @change="restoreData"
              />
              <button
                @click="triggerRestore"
                :disabled="restoreLoading"
                class="w-full px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
              >
                <span v-if="restoreLoading" class="flex items-center justify-center">
                  <svg class="animate-spin -ml-1 mr-2 h-4 w-4 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                    <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
                    <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                  </svg>
                  恢复中...
                </span>
                <span v-else>上传 JSON 文件恢复数据</span>
              </button>
            </div>

            <div class="bg-white border border-red-200 rounded-lg p-6">
              <div class="flex items-center gap-3 mb-4">
                <div class="p-2 bg-red-100 rounded-lg">
                  <svg xmlns="http://www.w3.org/2000/svg" class="h-6 w-6 text-red-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
                  </svg>
                </div>
                <h3 class="text-lg font-medium text-gray-900">数据清除</h3>
              </div>
              <p class="text-sm text-gray-500 mb-4">永久删除所有数据，此操作无法撤销。</p>
              <button
                @click="confirmClearData"
                class="w-full px-4 py-2 bg-red-600 text-white rounded-lg hover:bg-red-700 transition-colors"
              >
                清除所有数据
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>

    <div v-if="showClearConfirm" class="fixed inset-0 z-50 overflow-y-auto">
      <div class="flex items-center justify-center min-h-screen px-4 pt-4 pb-20 text-center sm:block sm:p-0">
        <div class="fixed inset-0 transition-opacity" @click="showClearConfirm = false">
          <div class="absolute inset-0 bg-gray-500 opacity-75"></div>
        </div>
        <span class="hidden sm:inline-block sm:align-middle sm:h-screen">&#8203;</span>
        <div class="inline-block align-bottom bg-white rounded-lg text-left overflow-hidden shadow-xl transform transition-all sm:my-8 sm:align-middle sm:max-w-lg sm:w-full">
          <div class="bg-white px-4 pt-5 pb-4 sm:p-6 sm:pb-4">
            <div class="sm:flex sm:items-start">
              <div class="mx-auto flex-shrink-0 flex items-center justify-center h-12 w-12 rounded-full bg-red-100 sm:mx-0 sm:h-10 sm:w-10">
                <svg xmlns="http://www.w3.org/2000/svg" class="h-6 w-6 text-red-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
                </svg>
              </div>
              <div class="mt-3 text-center sm:mt-0 sm:ml-4 sm:text-left">
                <h3 class="text-lg leading-6 font-medium text-gray-900">确认清除所有数据</h3>
                <div class="mt-2">
                  <p class="text-sm text-gray-500">
                    这将永久删除所有客户、交易和其他数据。此操作无法撤销。确定要继续吗？
                  </p>
                </div>
              </div>
            </div>
          </div>
          <div class="bg-gray-50 px-4 py-3 sm:px-6 sm:flex sm:flex-row-reverse gap-2">
            <button
              @click="clearAllData"
              :disabled="clearLoading"
              class="w-full inline-flex justify-center rounded-lg border border-transparent shadow-sm px-4 py-2 bg-red-600 text-base font-medium text-white hover:bg-red-700 focus:outline-none sm:w-auto sm:text-sm transition-colors"
            >
              <span v-if="clearLoading" class="flex items-center">
                <svg class="animate-spin -ml-1 mr-2 h-4 w-4 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                  <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
                  <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                </svg>
                清除中...
              </span>
              <span v-else>确认清除</span>
            </button>
            <button
              @click="showClearConfirm = false"
              type="button"
              class="mt-3 w-full inline-flex justify-center rounded-lg border border-gray-300 shadow-sm px-4 py-2 bg-white text-base font-medium text-gray-700 hover:bg-gray-50 focus:outline-none sm:mt-0 sm:w-auto sm:text-sm transition-colors"
            >
              取消
            </button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
</style>
