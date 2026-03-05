<script setup>
import { ref, reactive, computed, onMounted, onBeforeUnmount } from 'vue'
import api from '@/api'

const activities = ref([])
const loading = ref(false)
const submitting = ref(false)
const deleting = ref(false)
const showModal = ref(false)
const showDeleteConfirm = ref(false)
const isEditing = ref(false)
const activityToDelete = ref(null)
const requestError = ref('')

const filters = reactive({
  status: 'all',
  keyword: ''
})

const feedback = reactive({
  visible: false,
  type: 'success',
  message: ''
})

let feedbackTimer = null

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
  { value: 'active', label: '启用' },
  { value: 'inactive', label: '停用' }
]

const filterStatusOptions = [
  { value: 'all', label: '全部状态' },
  { value: 'active', label: '启用中' },
  { value: 'inactive', label: '已停用' }
]

const feedbackStyle = computed(() => {
  if (feedback.type === 'success') {
    return 'border-emerald-200 bg-emerald-50 text-emerald-800'
  }
  if (feedback.type === 'error') {
    return 'border-rose-200 bg-rose-50 text-rose-800'
  }
  return 'border-blue-200 bg-blue-50 text-blue-800'
})

const unwrapData = (payload, fallback) => {
  if (payload && typeof payload === 'object' && 'data' in payload) {
    return payload.data ?? fallback
  }
  return payload ?? fallback
}

const getErrorMessage = (error, fallback) => {
  return error?.response?.data?.message || error?.message || fallback
}

const showFeedback = (type, message, duration = 3200) => {
  feedback.type = type
  feedback.message = message
  feedback.visible = true

  if (feedbackTimer) {
    clearTimeout(feedbackTimer)
  }

  feedbackTimer = setTimeout(() => {
    feedback.visible = false
  }, duration)
}

const closeFeedback = () => {
  feedback.visible = false
  if (feedbackTimer) {
    clearTimeout(feedbackTimer)
    feedbackTimer = null
  }
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

const parseDate = (value) => {
  if (!value) return null
  const parsed = new Date(value)
  return Number.isNaN(parsed.getTime()) ? null : parsed
}

const getActivityPhase = (activity) => {
  if (activity.status !== 'active') return 'inactive'

  const now = Date.now()
  const start = parseDate(activity.startDate)
  const end = parseDate(activity.endDate)

  if (start && now < start.getTime()) return 'upcoming'
  if (end && now > end.getTime()) return 'ended'
  return 'running'
}

const getPhaseMeta = (activity) => {
  const phase = getActivityPhase(activity)
  const phaseMap = {
    running: {
      label: '进行中',
      className: 'bg-emerald-100 text-emerald-800 border-emerald-200',
      toneClass: 'text-emerald-700'
    },
    upcoming: {
      label: '即将开始',
      className: 'bg-blue-100 text-blue-800 border-blue-200',
      toneClass: 'text-blue-700'
    },
    ended: {
      label: '已结束',
      className: 'bg-amber-100 text-amber-800 border-amber-200',
      toneClass: 'text-amber-700'
    },
    inactive: {
      label: '已停用',
      className: 'bg-slate-100 text-slate-700 border-slate-200',
      toneClass: 'text-slate-600'
    }
  }

  return phaseMap[phase]
}

const filteredActivities = computed(() => {
  const keyword = String(filters.keyword || '').trim().toLowerCase()

  return activities.value.filter(activity => {
    if (filters.status !== 'all' && activity.status !== filters.status) {
      return false
    }

    if (!keyword) return true

    return `${activity.name} ${activity.description}`.toLowerCase().includes(keyword)
  })
})

const hasFilterApplied = computed(() => {
  return filters.status !== 'all' || String(filters.keyword || '').trim().length > 0
})

const formatDate = (date) => {
  const parsed = parseDate(date)
  if (!parsed) return '-'
  return parsed.toLocaleDateString('zh-CN')
}

const formatCurrency = (amount) => {
  const n = Number(amount)
  return Number.isFinite(n) ? `￥${n.toFixed(2)}` : '￥0.00'
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

const closeModal = () => {
  if (submitting.value) return
  showModal.value = false
  resetForm()
}

const closeDeleteConfirm = () => {
  if (deleting.value) return
  showDeleteConfirm.value = false
  activityToDelete.value = null
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

const fetchActivities = async () => {
  loading.value = true
  requestError.value = ''

  try {
    const response = await api.get('/activities')
    const payload = unwrapData(response, [])
    const items = Array.isArray(payload) ? payload : []
    activities.value = items.map(normalizeActivity)
  } catch (error) {
    console.error('Failed to fetch activities:', error)
    activities.value = []
    requestError.value = getErrorMessage(error, '加载活动失败，请稍后重试')
    showFeedback('error', requestError.value)
  } finally {
    loading.value = false
  }
}

const submitForm = async () => {
  if (!validateForm()) return

  submitting.value = true

  try {
    const successMessage = isEditing.value ? '活动已更新' : '活动已创建'

    const payload = {
      name: String(form.name || '').trim(),
      description: String(form.description || '').trim(),
      min_amount: Number(form.minRechargeAmount),
      bonus_amount: Number(form.bonusAmount),
      start_date: form.startDate,
      end_date: form.endDate,
      status: form.status
    }

    if (!payload.description) {
      delete payload.description
    }

    if (isEditing.value) {
      await api.put(`/activities/${form.id}`, payload)
    } else {
      await api.post('/activities', payload)
    }

    showModal.value = false
    resetForm()
    await fetchActivities()
    if (!requestError.value) {
      showFeedback('success', successMessage)
    }
  } catch (error) {
    console.error('Failed to save activity:', error)
    showFeedback('error', getErrorMessage(error, '保存活动失败'))
  } finally {
    submitting.value = false
  }
}

const confirmDelete = (activity) => {
  activityToDelete.value = activity
  showDeleteConfirm.value = true
}

const deleteActivity = async () => {
  if (!activityToDelete.value) return

  deleting.value = true

  try {
    await api.delete(`/activities/${activityToDelete.value.id}`)
    showDeleteConfirm.value = false
    activityToDelete.value = null
    await fetchActivities()
    if (!requestError.value) {
      showFeedback('success', '活动已删除')
    }
  } catch (error) {
    console.error('Failed to delete activity:', error)
    showFeedback('error', getErrorMessage(error, '删除活动失败'))
  } finally {
    deleting.value = false
  }
}

const resetFilters = () => {
  filters.status = 'all'
  filters.keyword = ''
}

onMounted(() => {
  fetchActivities()
})

onBeforeUnmount(() => {
  if (feedbackTimer) {
    clearTimeout(feedbackTimer)
    feedbackTimer = null
  }
})
</script>

<template>
  <div class="activities-page space-y-6">
    <section class="page-hero rounded-3xl p-6 sm:p-8">
      <div class="relative z-10 flex flex-col gap-5 lg:flex-row lg:items-end lg:justify-between">
        <div class="space-y-2">
          <p class="page-hero__eyebrow">Operation Board</p>
          <h1 class="page-hero__title">活动管理</h1>
        </div>
        <button
          @click="openAddModal"
          class="page-hero__action"
        >
          <svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2.1" d="M12 4v16m8-8H4" />
          </svg>
          创建活动
        </button>
      </div>
    </section>

    <Transition name="slide-fade">
      <section
        v-if="feedback.visible"
        :class="[
          'rounded-2xl border px-4 py-3 sm:px-5 sm:py-4 text-sm shadow-sm',
          feedbackStyle
        ]"
      >
        <div class="flex items-start justify-between gap-3">
          <div class="flex items-start gap-2">
          <svg
            v-if="feedback.type === 'success'"
            xmlns="http://www.w3.org/2000/svg"
            class="mt-0.5 h-4 w-4 flex-none"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
          >
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2.2" d="M5 13l4 4L19 7" />
          </svg>
          <svg
            v-else
            xmlns="http://www.w3.org/2000/svg"
            class="mt-0.5 h-4 w-4 flex-none"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
          >
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2.2" d="M12 9v4m0 4h.01M5.07 19h13.86c1.54 0 2.5-1.67 1.73-3L13.73 4c-.77-1.33-2.69-1.33-3.46 0L3.34 16c-.77 1.33.19 3 1.73 3z" />
          </svg>
          <p>{{ feedback.message }}</p>
          </div>
          <button
            class="rounded-md px-2 py-0.5 text-xs font-semibold transition hover:bg-black/5"
            @click="closeFeedback"
          >
            关闭
          </button>
        </div>
      </section>
    </Transition>

    <section class="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm sm:p-5">
      <div class="grid gap-3 lg:grid-cols-[220px_minmax(0,1fr)_auto]">
        <div>
          <label for="statusFilter" class="mb-1.5 block text-sm font-medium text-slate-700">状态筛选</label>
          <select
            id="statusFilter"
            v-model="filters.status"
            class="w-full rounded-xl border border-slate-300 px-3 py-2 text-sm text-slate-700 focus:outline-none focus:ring-2 focus:ring-[#1d4ed8] focus:ring-offset-1"
          >
            <option v-for="option in filterStatusOptions" :key="option.value" :value="option.value">
              {{ option.label }}
            </option>
          </select>
        </div>
        <div>
          <label for="keywordFilter" class="mb-1.5 block text-sm font-medium text-slate-700">关键词</label>
          <input
            id="keywordFilter"
            v-model="filters.keyword"
            type="text"
            placeholder="按活动名称或描述搜索"
            class="w-full rounded-xl border border-slate-300 px-3 py-2 text-sm text-slate-700 placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-[#1d4ed8] focus:ring-offset-1"
          />
        </div>
        <div class="flex items-end">
          <button
            class="inline-flex min-h-[44px] items-center rounded-xl border border-slate-300 px-4 py-2 text-sm font-medium text-slate-700 transition hover:bg-slate-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#1d4ed8]"
            :disabled="!hasFilterApplied"
            :class="!hasFilterApplied ? 'cursor-not-allowed opacity-50' : ''"
            @click="resetFilters"
          >
            重置筛选
          </button>
        </div>
      </div>

      <div class="mt-4 flex flex-wrap items-center justify-between gap-2 text-sm text-slate-500">
        <p>
          当前展示
          <span class="font-semibold text-slate-700">{{ filteredActivities.length }}</span>
          /
          <span class="font-semibold text-slate-700">{{ activities.length }}</span>
          个活动
        </p>
        <button
          v-if="requestError && !loading"
          class="inline-flex min-h-[36px] items-center gap-1 rounded-lg border border-rose-200 px-3 py-1.5 text-xs font-medium text-rose-700 transition hover:bg-rose-50"
          @click="fetchActivities"
        >
          重试加载
        </button>
      </div>
    </section>

    <section v-if="loading && activities.length === 0" class="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3">
      <article
        v-for="n in 6"
        :key="n"
        class="animate-pulse rounded-2xl border border-slate-200 bg-white p-5 shadow-sm"
      >
        <div class="h-5 w-1/2 rounded bg-slate-200"></div>
        <div class="mt-3 h-4 w-full rounded bg-slate-100"></div>
        <div class="mt-2 h-4 w-5/6 rounded bg-slate-100"></div>
        <div class="mt-5 space-y-2">
          <div class="h-4 rounded bg-slate-100"></div>
          <div class="h-4 rounded bg-slate-100"></div>
          <div class="h-4 rounded bg-slate-100"></div>
        </div>
      </article>
    </section>

    <section
      v-else-if="requestError && activities.length === 0"
      class="rounded-2xl border border-rose-200 bg-rose-50/70 p-10 text-center"
    >
      <h2 class="text-lg font-semibold text-rose-800">活动数据加载失败</h2>
      <p class="mt-2 text-sm text-rose-700">{{ requestError }}</p>
      <button
        class="mt-5 inline-flex min-h-[44px] items-center rounded-xl border border-rose-300 bg-white px-4 py-2 text-sm font-medium text-rose-700 transition hover:bg-rose-50"
        @click="fetchActivities"
      >
        重新加载
      </button>
    </section>

    <section
      v-else-if="filteredActivities.length === 0"
      class="rounded-2xl border border-slate-200 bg-white p-10 text-center shadow-sm"
    >
      <h2 class="text-lg font-semibold text-slate-800">
        {{ hasFilterApplied ? '没有符合筛选条件的活动' : '暂无活动数据' }}
      </h2>
      <p class="mt-2 text-sm text-slate-500">
        {{ hasFilterApplied ? '请调整筛选条件后重试。' : '点击右上角“创建活动”开始配置。' }}
      </p>
      <button
        v-if="hasFilterApplied"
        class="mt-5 inline-flex min-h-[44px] items-center rounded-xl border border-slate-300 px-4 py-2 text-sm font-medium text-slate-700 transition hover:bg-slate-50"
        @click="resetFilters"
      >
        清空筛选
      </button>
    </section>

    <section v-else class="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3">
      <article
        v-for="activity in filteredActivities"
        :key="activity.id"
        class="group relative overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm transition duration-200 hover:-translate-y-0.5 hover:shadow-lg"
      >
        <div class="absolute inset-x-0 top-0 h-1 bg-gradient-to-r from-[#2563eb] via-[#06b6d4] to-[#0ea5e9]"></div>
        <div class="space-y-4 p-5">
          <div class="flex items-start justify-between gap-3">
            <div class="min-w-0 flex-1">
              <h3 class="truncate text-lg font-semibold text-slate-900">{{ activity.name }}</h3>
              <p class="mt-1 text-sm leading-6 text-slate-500 line-clamp-2">{{ activity.description || '暂无描述' }}</p>
            </div>
            <span
              :class="[
                'flex-none rounded-full border px-2.5 py-1 text-xs font-semibold',
                getPhaseMeta(activity).className
              ]"
            >
              {{ getPhaseMeta(activity).label }}
            </span>
          </div>

          <dl class="space-y-2.5 text-sm">
            <div class="flex items-center justify-between gap-2">
              <dt class="text-slate-500">最低充值金额</dt>
              <dd class="font-semibold text-slate-900">{{ formatCurrency(activity.minRechargeAmount) }}</dd>
            </div>
            <div class="flex items-center justify-between gap-2">
              <dt class="text-slate-500">赠送金额</dt>
              <dd class="font-semibold text-emerald-700">{{ formatCurrency(activity.bonusAmount) }}</dd>
            </div>
            <div class="flex items-start justify-between gap-2">
              <dt class="text-slate-500">活动时间</dt>
              <dd class="text-right text-slate-700">
                <span>{{ formatDate(activity.startDate) }}</span>
                <span class="mx-1 text-slate-400">至</span>
                <span>{{ formatDate(activity.endDate) }}</span>
              </dd>
            </div>
          </dl>

          <p class="text-xs font-medium" :class="getPhaseMeta(activity).toneClass">
            {{ getPhaseMeta(activity).label }}活动
          </p>
        </div>

        <footer class="flex items-center justify-end gap-2 border-t border-slate-100 bg-slate-50/90 px-5 py-3.5">
          <button
            class="inline-flex min-h-[38px] items-center rounded-lg px-3 text-sm font-medium text-blue-700 transition hover:bg-blue-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-600/70"
            @click="openEditModal(activity)"
          >
            编辑
          </button>
          <button
            class="inline-flex min-h-[38px] items-center rounded-lg px-3 text-sm font-medium text-rose-700 transition hover:bg-rose-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-rose-600/70"
            @click="confirmDelete(activity)"
          >
            删除
          </button>
        </footer>
      </article>
    </section>

    <Teleport to="body">
      <div v-if="showModal" class="fixed inset-0 z-50 flex items-center justify-center p-4">
        <div class="absolute inset-0 bg-slate-900/55 backdrop-blur-sm" @click="closeModal"></div>
        <div class="relative w-full max-w-2xl overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-2xl">
          <div class="border-b border-slate-100 bg-slate-50/80 px-5 py-4">
            <h3 class="text-lg font-semibold text-slate-900">{{ isEditing ? '编辑活动' : '创建活动' }}</h3>
            <p class="mt-1 text-xs text-slate-500">请确认活动门槛、赠送金额和时间区间</p>
          </div>

          <form @submit.prevent="submitForm" class="max-h-[70vh] space-y-4 overflow-y-auto px-5 py-5">
            <div>
              <label for="name" class="mb-1.5 block text-sm font-medium text-slate-700">活动名称</label>
              <input
                id="name"
                v-model="form.name"
                type="text"
                :class="[
                  'w-full rounded-xl border px-3 py-2 text-sm text-slate-700 focus:outline-none focus:ring-2 focus:ring-[#1d4ed8] focus:ring-offset-1',
                  formErrors.name ? 'border-rose-400 bg-rose-50/50' : 'border-slate-300'
                ]"
              />
              <p v-if="formErrors.name" class="mt-1 text-xs text-rose-600">{{ formErrors.name }}</p>
            </div>

            <div>
              <label for="description" class="mb-1.5 block text-sm font-medium text-slate-700">活动描述</label>
              <textarea
                id="description"
                v-model="form.description"
                rows="3"
                class="w-full resize-none rounded-xl border border-slate-300 px-3 py-2 text-sm text-slate-700 focus:outline-none focus:ring-2 focus:ring-[#1d4ed8] focus:ring-offset-1"
              ></textarea>
            </div>

            <div class="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <div>
                <label for="minRechargeAmount" class="mb-1.5 block text-sm font-medium text-slate-700">最低充值金额</label>
                <input
                  id="minRechargeAmount"
                  v-model="form.minRechargeAmount"
                  type="number"
                  step="0.01"
                  min="0"
                  :class="[
                    'w-full rounded-xl border px-3 py-2 text-sm text-slate-700 focus:outline-none focus:ring-2 focus:ring-[#1d4ed8] focus:ring-offset-1',
                    formErrors.minRechargeAmount ? 'border-rose-400 bg-rose-50/50' : 'border-slate-300'
                  ]"
                />
                <p v-if="formErrors.minRechargeAmount" class="mt-1 text-xs text-rose-600">{{ formErrors.minRechargeAmount }}</p>
              </div>

              <div>
                <label for="bonusAmount" class="mb-1.5 block text-sm font-medium text-slate-700">赠送金额</label>
                <input
                  id="bonusAmount"
                  v-model="form.bonusAmount"
                  type="number"
                  step="0.01"
                  min="0"
                  :class="[
                    'w-full rounded-xl border px-3 py-2 text-sm text-slate-700 focus:outline-none focus:ring-2 focus:ring-[#1d4ed8] focus:ring-offset-1',
                    formErrors.bonusAmount ? 'border-rose-400 bg-rose-50/50' : 'border-slate-300'
                  ]"
                />
                <p v-if="formErrors.bonusAmount" class="mt-1 text-xs text-rose-600">{{ formErrors.bonusAmount }}</p>
              </div>
            </div>

            <div class="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <div>
                <label for="startDate" class="mb-1.5 block text-sm font-medium text-slate-700">开始日期</label>
                <input
                  id="startDate"
                  v-model="form.startDate"
                  type="date"
                  :class="[
                    'w-full rounded-xl border px-3 py-2 text-sm text-slate-700 focus:outline-none focus:ring-2 focus:ring-[#1d4ed8] focus:ring-offset-1',
                    formErrors.startDate ? 'border-rose-400 bg-rose-50/50' : 'border-slate-300'
                  ]"
                />
                <p v-if="formErrors.startDate" class="mt-1 text-xs text-rose-600">{{ formErrors.startDate }}</p>
              </div>

              <div>
                <label for="endDate" class="mb-1.5 block text-sm font-medium text-slate-700">结束日期</label>
                <input
                  id="endDate"
                  v-model="form.endDate"
                  type="date"
                  :class="[
                    'w-full rounded-xl border px-3 py-2 text-sm text-slate-700 focus:outline-none focus:ring-2 focus:ring-[#1d4ed8] focus:ring-offset-1',
                    formErrors.endDate ? 'border-rose-400 bg-rose-50/50' : 'border-slate-300'
                  ]"
                />
                <p v-if="formErrors.endDate" class="mt-1 text-xs text-rose-600">{{ formErrors.endDate }}</p>
              </div>
            </div>

            <div>
              <label for="status" class="mb-1.5 block text-sm font-medium text-slate-700">状态</label>
              <select
                id="status"
                v-model="form.status"
                class="w-full rounded-xl border border-slate-300 px-3 py-2 text-sm text-slate-700 focus:outline-none focus:ring-2 focus:ring-[#1d4ed8] focus:ring-offset-1"
              >
                <option v-for="option in statusOptions" :key="option.value" :value="option.value">
                  {{ option.label }}
                </option>
              </select>
            </div>
          </form>

          <div class="flex flex-col-reverse gap-2 border-t border-slate-100 bg-slate-50/80 px-5 py-4 sm:flex-row sm:justify-end">
            <button
              type="button"
              class="inline-flex min-h-[44px] items-center justify-center rounded-xl border border-slate-300 bg-white px-4 py-2 text-sm font-medium text-slate-700 transition hover:bg-slate-50"
              :disabled="submitting"
              :class="submitting ? 'cursor-not-allowed opacity-60' : ''"
              @click="closeModal"
            >
              取消
            </button>
            <button
              class="inline-flex min-h-[44px] items-center justify-center rounded-xl border border-transparent bg-[#1d4ed8] px-4 py-2 text-sm font-medium text-white transition hover:bg-[#1e40af] disabled:cursor-not-allowed disabled:opacity-60"
              :disabled="submitting"
              @click="submitForm"
            >
              {{ submitting ? '保存中...' : '保存' }}
            </button>
          </div>
        </div>
      </div>
    </Teleport>

    <Teleport to="body">
      <div v-if="showDeleteConfirm" class="fixed inset-0 z-50 flex items-center justify-center p-4">
        <div class="absolute inset-0 bg-slate-900/55 backdrop-blur-sm" @click="closeDeleteConfirm"></div>
        <div class="relative w-full max-w-md overflow-hidden rounded-2xl border border-rose-100 bg-white shadow-2xl">
          <div class="border-b border-rose-100 bg-rose-50/70 px-5 py-4">
            <h3 class="text-lg font-semibold text-rose-900">确认删除活动</h3>
            <p class="mt-1 text-xs text-rose-700">该操作不可撤销，请再次确认。</p>
          </div>

          <div class="px-5 py-5">
            <p class="text-sm leading-6 text-slate-600">
              确定要删除活动
              <span class="font-semibold text-slate-900">“{{ activityToDelete?.name }}”</span>
              吗？
            </p>
          </div>

          <div class="flex flex-col-reverse gap-2 border-t border-slate-100 bg-slate-50/80 px-5 py-4 sm:flex-row sm:justify-end">
            <button
              type="button"
              class="inline-flex min-h-[44px] items-center justify-center rounded-xl border border-slate-300 bg-white px-4 py-2 text-sm font-medium text-slate-700 transition hover:bg-slate-50"
              :disabled="deleting"
              :class="deleting ? 'cursor-not-allowed opacity-60' : ''"
              @click="closeDeleteConfirm"
            >
              取消
            </button>
            <button
              class="inline-flex min-h-[44px] items-center justify-center rounded-xl border border-transparent bg-rose-600 px-4 py-2 text-sm font-medium text-white transition hover:bg-rose-700 disabled:cursor-not-allowed disabled:opacity-60"
              :disabled="deleting"
              @click="deleteActivity"
            >
              {{ deleting ? '删除中...' : '确认删除' }}
            </button>
          </div>
        </div>
      </div>
    </Teleport>
  </div>
</template>

<style scoped>
.line-clamp-2 {
  display: -webkit-box;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 2;
  overflow: hidden;
}

.slide-fade-enter-active,
.slide-fade-leave-active {
  transition: all 0.2s ease;
}

.slide-fade-enter-from,
.slide-fade-leave-to {
  opacity: 0;
  transform: translateY(-6px);
}

@media (prefers-reduced-motion: reduce) {
  .slide-fade-enter-active,
  .slide-fade-leave-active {
    transition: none;
  }
}
</style>


