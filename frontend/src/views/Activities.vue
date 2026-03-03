<script setup>
import { ref, reactive, onMounted } from 'vue'
import api from '@/api'

const activities = ref([])
const loading = ref(false)
const showModal = ref(false)
const showDeleteConfirm = ref(false)
const isEditing = ref(false)
const activityToDelete = ref(null)

const form = reactive({
  id: null,
  name: '',
  description: '',
  minRechargeAmount: '',
  bonusAmount: '',
  startDate: '',
  endDate: '',
  status: 'active'
})

const formErrors = reactive({
  name: '',
  minRechargeAmount: '',
  bonusAmount: '',
  startDate: '',
  endDate: ''
})

const statusOptions = [
  { value: 'active', label: '进行中' },
  { value: 'inactive', label: '已停用' }
]

const unwrapData = (payload, fallback) => {
  if (payload && typeof payload === 'object' && 'data' in payload) {
    return payload.data ?? fallback
  }
  return payload ?? fallback
}

const normalizeActivity = (activity = {}) => ({
  id: activity.id,
  name: activity.name || '',
  description: activity.description || '',
  minRechargeAmount: activity.minRechargeAmount ?? activity.min_amount ?? 0,
  bonusAmount: activity.bonusAmount ?? activity.bonus_amount ?? activity.bonus_rate ?? 0,
  startDate: activity.startDate ?? activity.start_date ?? null,
  endDate: activity.endDate ?? activity.end_date ?? null,
  status: activity.status || 'active'
})

const fetchActivities = async () => {
  loading.value = true
  try {
    const response = await api.get('/activities')
    const payload = unwrapData(response, [])
    const items = Array.isArray(payload) ? payload : []
    activities.value = items.map(normalizeActivity)
  } catch (error) {
    console.error('Failed to fetch activities:', error)
    activities.value = []
  } finally {
    loading.value = false
  }
}

const clearErrors = () => {
  formErrors.name = ''
  formErrors.minRechargeAmount = ''
  formErrors.bonusAmount = ''
  formErrors.startDate = ''
  formErrors.endDate = ''
}

const resetForm = () => {
  form.id = null
  form.name = ''
  form.description = ''
  form.minRechargeAmount = ''
  form.bonusAmount = ''
  form.startDate = ''
  form.endDate = ''
  form.status = 'active'
  clearErrors()
}

const openAddModal = () => {
  isEditing.value = false
  resetForm()
  showModal.value = true
}

const openEditModal = (activity) => {
  isEditing.value = true
  form.id = activity.id
  form.name = activity.name
  form.description = activity.description || ''
  form.minRechargeAmount = activity.minRechargeAmount
  form.bonusAmount = activity.bonusAmount
  form.startDate = activity.startDate ? String(activity.startDate).split('T')[0] : ''
  form.endDate = activity.endDate ? String(activity.endDate).split('T')[0] : ''
  form.status = activity.status || 'active'
  clearErrors()
  showModal.value = true
}

const validateForm = () => {
  let isValid = true
  clearErrors()

  if (!String(form.name || '').trim()) {
    formErrors.name = '请输入活动名称'
    isValid = false
  }

  const minRechargeAmount = Number(form.minRechargeAmount)
  if (!Number.isFinite(minRechargeAmount) || minRechargeAmount < 0) {
    formErrors.minRechargeAmount = '请输入有效的最低充值金额'
    isValid = false
  }

  const bonusAmount = Number(form.bonusAmount)
  if (!Number.isFinite(bonusAmount) || bonusAmount < 0) {
    formErrors.bonusAmount = '请输入有效的赠送金额'
    isValid = false
  }

  if (!form.startDate) {
    formErrors.startDate = '请选择开始日期'
    isValid = false
  }

  if (!form.endDate) {
    formErrors.endDate = '请选择结束日期'
    isValid = false
  }

  if (form.startDate && form.endDate && new Date(form.startDate) > new Date(form.endDate)) {
    formErrors.endDate = '结束日期必须晚于或等于开始日期'
    isValid = false
  }

  return isValid
}

const submitForm = async () => {
  if (!validateForm()) return

  loading.value = true
  try {
    const data = {
      name: String(form.name || '').trim(),
      description: String(form.description || '').trim(),
      min_amount: Number(form.minRechargeAmount),
      bonus_amount: Number(form.bonusAmount),
      start_date: form.startDate,
      end_date: form.endDate,
      status: form.status
    }

    if (!data.description) {
      delete data.description
    }

    if (isEditing.value) {
      await api.put(`/activities/${form.id}`, data)
    } else {
      await api.post('/activities', data)
    }

    showModal.value = false
    await fetchActivities()
  } catch (error) {
    console.error('Failed to save activity:', error)
    alert(error?.response?.data?.message || error?.message || '保存活动失败')
  } finally {
    loading.value = false
  }
}

const confirmDelete = (activity) => {
  activityToDelete.value = activity
  showDeleteConfirm.value = true
}

const deleteActivity = async () => {
  if (!activityToDelete.value) return

  loading.value = true
  try {
    await api.delete(`/activities/${activityToDelete.value.id}`)
    showDeleteConfirm.value = false
    activityToDelete.value = null
    await fetchActivities()
  } catch (error) {
    console.error('Failed to delete activity:', error)
    alert(error?.response?.data?.message || error?.message || '删除活动失败')
  } finally {
    loading.value = false
  }
}

const formatDate = (date) => {
  if (!date) return '-'
  return new Date(date).toLocaleDateString('zh-CN')
}

const formatCurrency = (amount) => {
  if (amount === null || amount === undefined) return '¥0.00'
  const n = Number(amount)
  return Number.isFinite(n) ? `¥${n.toFixed(2)}` : '¥0.00'
}

const getStatusLabel = (status) => {
  const statusMap = {
    active: '进行中',
    inactive: '已停用'
  }
  return statusMap[status] || status
}

const getStatusClass = (status) => {
  const classMap = {
    active: 'bg-green-100 text-green-800',
    inactive: 'bg-gray-100 text-gray-800'
  }
  return classMap[status] || 'bg-gray-100 text-gray-800'
}

const isActivityActive = (activity) => {
  if (activity.status !== 'active') return false
  if (!activity.startDate || !activity.endDate) return false

  const now = new Date()
  const start = new Date(activity.startDate)
  const end = new Date(activity.endDate)
  return now >= start && now <= end
}

onMounted(() => {
  fetchActivities()
})
</script>

<template>
  <div class="space-y-6">
    <div class="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
      <div>
        <h1 class="text-2xl font-bold text-gray-800">活动管理</h1>
        <p class="text-gray-500 mt-1">创建和管理充值活动</p>
      </div>
      <button
        @click="openAddModal"
        class="inline-flex items-center px-4 py-2 bg-[#1e40af] text-white rounded-lg hover:bg-[#1e3a8a] transition-colors"
      >
        <svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5 mr-2" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4v16m8-8H4" />
        </svg>
        创建活动
      </button>
    </div>

    <div v-if="loading && activities.length === 0" class="flex items-center justify-center py-12">
      <svg class="animate-spin h-8 w-8 text-[#1e40af]" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
        <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
        <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
      </svg>
    </div>

    <div v-else-if="activities.length === 0" class="bg-white rounded-lg shadow-sm p-12 text-center">
      <p class="text-gray-500">暂无活动数据</p>
    </div>

    <div v-else class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
      <div
        v-for="activity in activities"
        :key="activity.id"
        class="bg-white rounded-lg shadow-sm overflow-hidden hover:shadow-md transition-shadow"
      >
        <div class="p-6">
          <div class="flex items-start justify-between mb-4">
            <div class="flex-1">
              <h3 class="text-lg font-semibold text-gray-900">{{ activity.name }}</h3>
              <p class="text-sm text-gray-500 mt-1 line-clamp-2">{{ activity.description || '暂无描述' }}</p>
            </div>
            <span
              :class="[
                'px-2 py-1 text-xs font-medium rounded-full ml-2',
                getStatusClass(activity.status)
              ]"
            >
              {{ getStatusLabel(activity.status) }}
            </span>
          </div>

          <div class="space-y-3">
            <div class="flex items-center justify-between text-sm">
              <span class="text-gray-500">最低充值金额</span>
              <span class="font-medium text-gray-900">{{ formatCurrency(activity.minRechargeAmount) }}</span>
            </div>
            <div class="flex items-center justify-between text-sm">
              <span class="text-gray-500">赠送金额</span>
              <span class="font-medium text-green-600">{{ formatCurrency(activity.bonusAmount) }}</span>
            </div>
            <div class="flex items-center justify-between text-sm">
              <span class="text-gray-500">活动时间</span>
              <span class="text-gray-900">{{ formatDate(activity.startDate) }} - {{ formatDate(activity.endDate) }}</span>
            </div>
          </div>

          <div v-if="isActivityActive(activity)" class="mt-4 p-2 bg-green-50 rounded-lg">
            <p class="text-xs text-green-700 text-center font-medium">活动进行中</p>
          </div>
        </div>

        <div class="px-6 py-4 bg-gray-50 border-t border-gray-100 flex justify-end space-x-2">
          <button
            @click="openEditModal(activity)"
            class="inline-flex items-center px-3 py-1.5 text-sm text-blue-600 hover:text-blue-800 hover:bg-blue-50 rounded-lg transition-colors"
          >
            编辑
          </button>
          <button
            @click="confirmDelete(activity)"
            class="inline-flex items-center px-3 py-1.5 text-sm text-red-600 hover:text-red-800 hover:bg-red-50 rounded-lg transition-colors"
          >
            删除
          </button>
        </div>
      </div>
    </div>

    <div v-if="showModal" class="fixed inset-0 z-50 overflow-y-auto">
      <div class="flex items-center justify-center min-h-screen px-4 pt-4 pb-20 text-center sm:block sm:p-0">
        <div class="fixed inset-0 transition-opacity" @click="showModal = false">
          <div class="absolute inset-0 bg-gray-500 opacity-75"></div>
        </div>
        <span class="hidden sm:inline-block sm:align-middle sm:h-screen">&#8203;</span>
        <div class="inline-block align-bottom bg-white rounded-lg text-left overflow-hidden shadow-xl transform transition-all sm:my-8 sm:align-middle sm:max-w-lg sm:w-full">
          <div class="bg-white px-4 pt-5 pb-4 sm:p-6 sm:pb-4">
            <h3 class="text-lg font-medium text-gray-900 mb-4">{{ isEditing ? '编辑活动' : '创建活动' }}</h3>

            <form @submit.prevent="submitForm" class="space-y-4">
              <div>
                <label for="name" class="block text-sm font-medium text-gray-700 mb-1">活动名称</label>
                <input
                  id="name"
                  v-model="form.name"
                  type="text"
                  :class="[
                    'w-full px-3 py-2 border rounded-lg focus:outline-none focus:ring-2 focus:ring-[#1e40af] focus:border-transparent',
                    formErrors.name ? 'border-red-500' : 'border-gray-300'
                  ]"
                />
                <p v-if="formErrors.name" class="text-red-500 text-xs mt-1">{{ formErrors.name }}</p>
              </div>

              <div>
                <label for="description" class="block text-sm font-medium text-gray-700 mb-1">活动描述</label>
                <textarea
                  id="description"
                  v-model="form.description"
                  rows="3"
                  class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-[#1e40af] focus:border-transparent resize-none"
                ></textarea>
              </div>

              <div class="grid grid-cols-2 gap-4">
                <div>
                  <label for="minRechargeAmount" class="block text-sm font-medium text-gray-700 mb-1">最低充值金额</label>
                  <input
                    id="minRechargeAmount"
                    v-model="form.minRechargeAmount"
                    type="number"
                    step="0.01"
                    min="0"
                    :class="[
                      'w-full px-3 py-2 border rounded-lg focus:outline-none focus:ring-2 focus:ring-[#1e40af] focus:border-transparent',
                      formErrors.minRechargeAmount ? 'border-red-500' : 'border-gray-300'
                    ]"
                  />
                  <p v-if="formErrors.minRechargeAmount" class="text-red-500 text-xs mt-1">{{ formErrors.minRechargeAmount }}</p>
                </div>

                <div>
                  <label for="bonusAmount" class="block text-sm font-medium text-gray-700 mb-1">赠送金额</label>
                  <input
                    id="bonusAmount"
                    v-model="form.bonusAmount"
                    type="number"
                    step="0.01"
                    min="0"
                    :class="[
                      'w-full px-3 py-2 border rounded-lg focus:outline-none focus:ring-2 focus:ring-[#1e40af] focus:border-transparent',
                      formErrors.bonusAmount ? 'border-red-500' : 'border-gray-300'
                    ]"
                  />
                  <p v-if="formErrors.bonusAmount" class="text-red-500 text-xs mt-1">{{ formErrors.bonusAmount }}</p>
                </div>
              </div>

              <div class="grid grid-cols-2 gap-4">
                <div>
                  <label for="startDate" class="block text-sm font-medium text-gray-700 mb-1">开始日期</label>
                  <input
                    id="startDate"
                    v-model="form.startDate"
                    type="date"
                    :class="[
                      'w-full px-3 py-2 border rounded-lg focus:outline-none focus:ring-2 focus:ring-[#1e40af] focus:border-transparent',
                      formErrors.startDate ? 'border-red-500' : 'border-gray-300'
                    ]"
                  />
                  <p v-if="formErrors.startDate" class="text-red-500 text-xs mt-1">{{ formErrors.startDate }}</p>
                </div>

                <div>
                  <label for="endDate" class="block text-sm font-medium text-gray-700 mb-1">结束日期</label>
                  <input
                    id="endDate"
                    v-model="form.endDate"
                    type="date"
                    :class="[
                      'w-full px-3 py-2 border rounded-lg focus:outline-none focus:ring-2 focus:ring-[#1e40af] focus:border-transparent',
                      formErrors.endDate ? 'border-red-500' : 'border-gray-300'
                    ]"
                  />
                  <p v-if="formErrors.endDate" class="text-red-500 text-xs mt-1">{{ formErrors.endDate }}</p>
                </div>
              </div>

              <div>
                <label for="status" class="block text-sm font-medium text-gray-700 mb-1">状态</label>
                <select
                  id="status"
                  v-model="form.status"
                  class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-[#1e40af] focus:border-transparent"
                >
                  <option v-for="option in statusOptions" :key="option.value" :value="option.value">
                    {{ option.label }}
                  </option>
                </select>
              </div>
            </form>
          </div>

          <div class="bg-gray-50 px-4 py-3 sm:px-6 sm:flex sm:flex-row-reverse gap-2">
            <button
              @click="submitForm"
              :disabled="loading"
              class="w-full inline-flex justify-center rounded-lg border border-transparent shadow-sm px-4 py-2 bg-[#1e40af] text-base font-medium text-white hover:bg-[#1e3a8a] focus:outline-none sm:w-auto sm:text-sm transition-colors"
            >
              保存
            </button>
            <button
              @click="showModal = false"
              type="button"
              class="mt-3 w-full inline-flex justify-center rounded-lg border border-gray-300 shadow-sm px-4 py-2 bg-white text-base font-medium text-gray-700 hover:bg-gray-50 focus:outline-none sm:mt-0 sm:w-auto sm:text-sm transition-colors"
            >
              取消
            </button>
          </div>
        </div>
      </div>
    </div>

    <div v-if="showDeleteConfirm" class="fixed inset-0 z-50 overflow-y-auto">
      <div class="flex items-center justify-center min-h-screen px-4 pt-4 pb-20 text-center sm:block sm:p-0">
        <div class="fixed inset-0 transition-opacity" @click="showDeleteConfirm = false">
          <div class="absolute inset-0 bg-gray-500 opacity-75"></div>
        </div>
        <span class="hidden sm:inline-block sm:align-middle sm:h-screen">&#8203;</span>
        <div class="inline-block align-bottom bg-white rounded-lg text-left overflow-hidden shadow-xl transform transition-all sm:my-8 sm:align-middle sm:max-w-lg sm:w-full">
          <div class="bg-white px-4 pt-5 pb-4 sm:p-6 sm:pb-4">
            <h3 class="text-lg leading-6 font-medium text-gray-900">确认删除</h3>
            <div class="mt-2">
              <p class="text-sm text-gray-500">确定要删除活动 “{{ activityToDelete?.name }}” 吗？此操作无法撤销。</p>
            </div>
          </div>

          <div class="bg-gray-50 px-4 py-3 sm:px-6 sm:flex sm:flex-row-reverse gap-2">
            <button
              @click="deleteActivity"
              :disabled="loading"
              class="w-full inline-flex justify-center rounded-lg border border-transparent shadow-sm px-4 py-2 bg-red-600 text-base font-medium text-white hover:bg-red-700 focus:outline-none sm:w-auto sm:text-sm transition-colors"
            >
              删除
            </button>
            <button
              @click="showDeleteConfirm = false"
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
.line-clamp-2 {
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
</style>
