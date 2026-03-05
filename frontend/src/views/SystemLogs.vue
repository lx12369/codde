<script setup>
import { ref, reactive, computed, onMounted, onBeforeUnmount } from 'vue'
import api from '@/api'
import { formatServerDateTime } from '@/utils/dateTime'

const logs = ref([])
const loading = ref(false)
const currentPage = ref(1)
const pageSize = ref(15)
const total = ref(0)
const lastUpdateTime = ref('')

const filterForm = reactive({
  module: 'all',
  action: 'all',
  operator: '',
  keyword: ''
})

const feedback = reactive({
  tone: 'info',
  message: ''
})

let feedbackTimer = null

const moduleOptions = ref([{ value: 'all', label: '全部模块' }])
const actionOptions = ref([{ value: 'all', label: '全部操作' }])

const pageSizeOptions = [5, 10, 15, 20, 25, 30, 35, 40, 45, 50]

const totalPages = computed(() => Math.ceil(total.value / pageSize.value) || 1)

const fromEntry = computed(() => {
  if (total.value === 0) return 0
  return (currentPage.value - 1) * pageSize.value + 1
})

const toEntry = computed(() => {
  if (total.value === 0) return 0
  return Math.min(currentPage.value * pageSize.value, total.value)
})

const visiblePages = computed(() => {
  const pages = []
  for (let page = 1; page <= totalPages.value; page += 1) {
    const shouldShow = page === 1 || page === totalPages.value || Math.abs(page - currentPage.value) <= 1
    if (shouldShow) {
      pages.push(page)
    } else if (pages[pages.length - 1] !== '...') {
      pages.push('...')
    }
  }
  return pages
})

const hasActiveFilter = computed(() => {
  return filterForm.module !== 'all'
    || filterForm.action !== 'all'
    || String(filterForm.operator || '').trim().length > 0
    || String(filterForm.keyword || '').trim().length > 0
})

const feedbackStyle = computed(() => {
  if (feedback.tone === 'success') {
    return 'border-emerald-200 bg-emerald-50 text-emerald-800'
  }
  if (feedback.tone === 'error') {
    return 'border-rose-200 bg-rose-50 text-rose-800'
  }
  return 'border-blue-200 bg-blue-50 text-blue-800'
})

function clearFeedbackTimer() {
  if (!feedbackTimer) return
  window.clearTimeout(feedbackTimer)
  feedbackTimer = null
}

function showFeedback(tone, message) {
  feedback.tone = tone
  feedback.message = message
  clearFeedbackTimer()
  feedbackTimer = window.setTimeout(() => {
    feedback.message = ''
    feedbackTimer = null
  }, 4200)
}

function closeFeedback() {
  feedback.message = ''
  clearFeedbackTimer()
}

function updateTime() {
  lastUpdateTime.value = new Date().toLocaleString('zh-CN')
}

function formatActivityTime(value) {
  return formatServerDateTime(value, {
    second: '2-digit',
    hour12: false
  })
}

function getModuleBadgeClass(module) {
  const classes = {
    auth: 'bg-blue-100 text-blue-800',
    customer: 'bg-cyan-100 text-cyan-800',
    activity: 'bg-violet-100 text-violet-800',
    billing: 'bg-amber-100 text-amber-800',
    transaction: 'bg-emerald-100 text-emerald-800',
    timer: 'bg-orange-100 text-orange-800',
    data: 'bg-rose-100 text-rose-800',
    bead_inventory: 'bg-teal-100 text-teal-800'
  }
  return classes[module] || 'bg-slate-100 text-slate-700'
}

function getActionBadgeClass(action) {
  const classes = {
    create: 'bg-emerald-50 text-emerald-700 border border-emerald-200',
    update: 'bg-amber-50 text-amber-700 border border-amber-200',
    delete: 'bg-rose-50 text-rose-700 border border-rose-200',
    login: 'bg-blue-50 text-blue-700 border border-blue-200',
    password_change: 'bg-fuchsia-50 text-fuchsia-700 border border-fuchsia-200',
    recharge: 'bg-emerald-50 text-emerald-700 border border-emerald-200',
    consumption: 'bg-orange-50 text-orange-700 border border-orange-200',
    settle: 'bg-orange-50 text-orange-700 border border-orange-200',
    cancel_recharge: 'bg-rose-50 text-rose-700 border border-rose-200',
    cancel_consumption: 'bg-rose-50 text-rose-700 border border-rose-200',
    cancel_bead_purchase: 'bg-rose-50 text-rose-700 border border-rose-200',
    backup: 'bg-indigo-50 text-indigo-700 border border-indigo-200',
    restore: 'bg-purple-50 text-purple-700 border border-purple-200',
    clear: 'bg-rose-50 text-rose-700 border border-rose-200',
    material_create: 'bg-teal-50 text-teal-700 border border-teal-200',
    material_update: 'bg-teal-50 text-teal-700 border border-teal-200',
    material_delete: 'bg-rose-50 text-rose-700 border border-rose-200',
    material_import: 'bg-cyan-50 text-cyan-700 border border-cyan-200',
    inbound: 'bg-emerald-50 text-emerald-700 border border-emerald-200',
    outbound: 'bg-orange-50 text-orange-700 border border-orange-200',
    loss: 'bg-amber-50 text-amber-700 border border-amber-200',
    stocktake: 'bg-violet-50 text-violet-700 border border-violet-200',
    conversion_standard_batch_update: 'bg-sky-50 text-sky-700 border border-sky-200',
    market_price_batch_update: 'bg-indigo-50 text-indigo-700 border border-indigo-200',
    safe_stock_batch_update_by_common_color: 'bg-fuchsia-50 text-fuchsia-700 border border-fuchsia-200'
  }
  return classes[action] || 'bg-slate-50 text-slate-700 border border-slate-200'
}

function normalizeLogItem(item = {}) {
  const timestamp = item.timestamp || item.created_at || null
  return {
    id: item.id ?? `${timestamp || 'log'}-${item.type || 'unknown'}`,
    module: item.module || 'other',
    moduleLabel: item.module_label || '其他',
    action: item.action || 'other',
    actionLabel: item.action_label || item.type_label || '其他',
    typeLabel: item.type_label || '其他',
    description: item.description || '-',
    operator: item.operator || '-',
    displayTime: formatActivityTime(timestamp)
  }
}

async function fetchLogs({ withFeedback = false } = {}) {
  loading.value = true
  try {
    const params = {
      page: currentPage.value,
      page_size: pageSize.value
    }

    if (filterForm.module && filterForm.module !== 'all') {
      params.module = filterForm.module
    }

    if (filterForm.action && filterForm.action !== 'all') {
      params.action = filterForm.action
    }

    const operator = filterForm.operator.trim()
    if (operator) {
      params.operator = operator
    }

    const keyword = filterForm.keyword.trim()
    if (keyword) {
      params.keyword = keyword
    }

    const response = await api.get('/logs', { params })
    const payload = response?.data ?? response ?? {}
    const items = Array.isArray(payload.items) ? payload.items : []
    const pagination = payload.pagination || {}
    const filters = payload.filters || {}

    logs.value = items.map(normalizeLogItem)
    total.value = Number(pagination.total ?? items.length) || 0

    if (Array.isArray(filters.modules) && filters.modules.length > 0) {
      moduleOptions.value = filters.modules
    }

    if (Array.isArray(filters.actions) && filters.actions.length > 0) {
      actionOptions.value = filters.actions
    }

    if (currentPage.value > totalPages.value) {
      currentPage.value = totalPages.value
      await fetchLogs({ withFeedback: false })
      return
    }

    updateTime()

    if (withFeedback) {
      showFeedback('success', '日志已刷新')
    }
  } catch (error) {
    console.error('Failed to fetch system logs:', error)
    logs.value = []
    total.value = 0
    showFeedback('error', '加载系统日志失败，请稍后重试。')
  } finally {
    loading.value = false
  }
}

async function handleRefresh() {
  await fetchLogs({ withFeedback: true })
}

async function handleSearch() {
  currentPage.value = 1
  await fetchLogs()
}

async function handleReset() {
  filterForm.module = 'all'
  filterForm.action = 'all'
  filterForm.operator = ''
  filterForm.keyword = ''
  currentPage.value = 1
  await fetchLogs({ withFeedback: true })
}

async function handlePageChange(page) {
  if (page < 1 || page > totalPages.value) return
  currentPage.value = page
  await fetchLogs()
}

async function handlePageSizeChange() {
  currentPage.value = 1
  await fetchLogs()
}

onMounted(() => {
  fetchLogs()
})

onBeforeUnmount(() => {
  clearFeedbackTimer()
})
</script>

<template>
  <div class="logs-page space-y-6">
    <section class="page-hero rounded-3xl p-6 sm:p-8">
      <div class="relative z-10 flex flex-col gap-6 lg:flex-row lg:items-end lg:justify-between">
        <div class="space-y-2">
          <p class="page-hero__eyebrow">Audit Console</p>
          <h1 class="page-hero__title">系统日志</h1>
          <p v-if="lastUpdateTime" class="page-hero__meta">最后更新：{{ lastUpdateTime }}</p>
        </div>

        <button
          type="button"
          :disabled="loading"
          @click="handleRefresh"
          class="page-hero__action"
        >
          <svg
            xmlns="http://www.w3.org/2000/svg"
            class="h-4 w-4"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
          >
            <path
              stroke-linecap="round"
              stroke-linejoin="round"
              stroke-width="2"
              d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"
            />
          </svg>
          <span>{{ loading ? '刷新中...' : '刷新日志' }}</span>
        </button>
      </div>

    </section>

    <Transition name="notice">
      <div
        v-if="feedback.message"
        role="status"
        aria-live="polite"
        :class="['rounded-2xl border px-4 py-3 sm:px-5 sm:py-4 text-sm shadow-sm', feedbackStyle]"
      >
        <div class="flex items-start justify-between gap-3">
          <span>{{ feedback.message }}</span>
          <button class="text-xs font-semibold opacity-80 hover:opacity-100" @click="closeFeedback">关闭</button>
        </div>
      </div>
    </Transition>

    <section class="panel-surface rounded-3xl border border-slate-200/80 p-5 sm:p-6 lg:p-8 space-y-6 shadow-sm">
      <section class="rounded-2xl border border-slate-200 bg-white p-4 sm:p-5">
        <div class="grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-[minmax(120px,0.72fr)_minmax(160px,1fr)_minmax(160px,1fr)_minmax(220px,1.2fr)_auto_auto] xl:items-end">
          <label class="text-sm text-slate-600">
            <span class="mb-1 block">模块</span>
            <select
              v-model="filterForm.module"
              class="w-full h-10 rounded-xl border border-slate-300 bg-white px-3 text-sm text-slate-700 focus:outline-none focus:ring-2 focus:ring-blue-500"
            >
              <option v-for="option in moduleOptions" :key="`module-${option.value}`" :value="option.value">
                {{ option.label }}
              </option>
            </select>
          </label>

          <label class="text-sm text-slate-600">
            <span class="mb-1 block">操作</span>
            <select
              v-model="filterForm.action"
              class="w-full h-10 rounded-xl border border-slate-300 bg-white px-3 text-sm text-slate-700 focus:outline-none focus:ring-2 focus:ring-blue-500"
            >
              <option v-for="option in actionOptions" :key="`action-${option.value}`" :value="option.value">
                {{ option.label }}
              </option>
            </select>
          </label>

          <label class="text-sm text-slate-600">
            <span class="mb-1 block">操作员</span>
            <input
              v-model="filterForm.operator"
              type="text"
              class="w-full h-10 rounded-xl border border-slate-300 px-3 text-sm text-slate-700 focus:outline-none focus:ring-2 focus:ring-blue-500"
              placeholder="输入操作员"
            >
          </label>

          <label class="text-sm text-slate-600">
            <span class="mb-1 block">关键字</span>
            <input
              v-model="filterForm.keyword"
              type="text"
              class="w-full h-10 rounded-xl border border-slate-300 px-3 text-sm text-slate-700 focus:outline-none focus:ring-2 focus:ring-blue-500"
              placeholder="描述关键字"
            >
          </label>

          <button
            type="button"
            :disabled="!hasActiveFilter || loading"
            @click="handleReset"
            class="h-10 rounded-xl border border-slate-300 px-4 text-sm font-medium text-slate-700 transition hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-50 xl:justify-self-end"
          >
            重置
          </button>
          <button
            type="button"
            :disabled="loading"
            @click="handleSearch"
            class="h-10 rounded-xl bg-blue-600 px-4 text-sm font-semibold text-white transition hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-55 xl:justify-self-start"
          >
            查询
          </button>
        </div>
      </section>

      <section class="rounded-2xl border border-slate-200 bg-white shadow-sm">
        <div class="flex flex-col gap-2 border-b border-slate-100 px-5 py-4 sm:flex-row sm:items-center sm:justify-between">
          <h2 class="text-lg font-bold text-slate-900">操作记录</h2>
          <span class="text-sm text-slate-500">
            显示 {{ fromEntry }} - {{ toEntry }} / 共 {{ total }} 条
          </span>
        </div>

        <div v-if="loading && logs.length === 0" class="space-y-2 p-5">
          <div v-for="n in 8" :key="n" class="h-11 animate-pulse rounded-lg bg-slate-100"></div>
        </div>

        <div v-else-if="!loading && total === 0" class="px-5 py-14 text-center">
          <h3 class="text-base font-semibold text-slate-700">暂无系统日志</h3>
          <p class="mt-2 text-sm text-slate-500">请调整筛选条件或稍后刷新重试。</p>
        </div>

        <template v-else>
          <div class="divide-y divide-slate-100 md:hidden">
            <article v-for="log in logs" :key="`mobile-${log.id}`" class="space-y-3 px-4 py-4">
              <div class="flex items-center justify-between gap-2">
                <p class="text-xs text-slate-500">{{ log.displayTime }}</p>
                <p class="text-xs text-slate-500">{{ log.operator }}</p>
              </div>
              <div class="flex items-center gap-2">
                <span :class="['rounded-full px-2 py-1 text-xs font-medium', getModuleBadgeClass(log.module)]">
                  {{ log.moduleLabel }}
                </span>
                <span :class="['rounded-full px-2 py-1 text-xs font-medium', getActionBadgeClass(log.action)]">
                  {{ log.actionLabel }}
                </span>
              </div>
              <p class="text-sm text-slate-700">{{ log.typeLabel }}</p>
              <p class="text-sm text-slate-600 leading-6">{{ log.description }}</p>
            </article>
          </div>

          <div class="hidden md:block overflow-x-auto">
            <table class="w-full min-w-[980px]">
              <thead class="bg-slate-50/80">
                <tr class="border-b border-slate-200">
                  <th class="px-4 py-3 text-left text-sm font-semibold text-slate-600">时间</th>
                  <th class="px-4 py-3 text-left text-sm font-semibold text-slate-600">模块</th>
                  <th class="px-4 py-3 text-left text-sm font-semibold text-slate-600">操作</th>
                  <th class="px-4 py-3 text-left text-sm font-semibold text-slate-600">类型</th>
                  <th class="px-4 py-3 text-left text-sm font-semibold text-slate-600">描述</th>
                  <th class="px-4 py-3 text-left text-sm font-semibold text-slate-600">操作员</th>
                </tr>
              </thead>
              <tbody>
                <tr
                  v-for="log in logs"
                  :key="log.id"
                  class="border-b border-slate-100 transition-colors hover:bg-slate-50/70"
                >
                  <td class="whitespace-nowrap px-4 py-3 text-sm text-slate-600">{{ log.displayTime }}</td>
                  <td class="px-4 py-3">
                    <span :class="['rounded-full px-2 py-1 text-xs font-medium', getModuleBadgeClass(log.module)]">
                      {{ log.moduleLabel }}
                    </span>
                  </td>
                  <td class="px-4 py-3">
                    <span :class="['rounded-full px-2 py-1 text-xs font-medium', getActionBadgeClass(log.action)]">
                      {{ log.actionLabel }}
                    </span>
                  </td>
                  <td class="px-4 py-3 text-sm text-slate-600">{{ log.typeLabel }}</td>
                  <td class="px-4 py-3 text-sm text-slate-600">
                    <p class="line-clamp-2">{{ log.description }}</p>
                  </td>
                  <td class="px-4 py-3 text-sm text-slate-600">{{ log.operator }}</td>
                </tr>
              </tbody>
            </table>
          </div>
        </template>

        <div v-if="total > 0" class="border-t border-slate-100 bg-slate-50/70 px-5 py-4">
          <div class="flex flex-col gap-3 xl:flex-row xl:items-center xl:justify-between">
            <p class="text-sm text-slate-600">
              显示 {{ fromEntry }} 到 {{ toEntry }} 条，共 {{ total }} 条记录
            </p>
            <div class="flex flex-col gap-3 sm:flex-row sm:items-center">
              <label class="flex items-center gap-2 text-sm text-slate-600">
                <span>每页</span>
                <select
                  v-model.number="pageSize"
                  @change="handlePageSizeChange"
                  class="h-9 min-w-[92px] rounded-lg border border-slate-300 bg-white px-3 text-sm text-slate-700 focus:outline-none focus:ring-2 focus:ring-blue-500"
                >
                  <option v-for="size in pageSizeOptions" :key="size" :value="size">{{ size }}条</option>
                </select>
              </label>
              <div class="flex items-center gap-1">
                <button
                  @click="handlePageChange(currentPage - 1)"
                  :disabled="currentPage === 1"
                  class="h-9 rounded-lg border border-slate-300 bg-white px-3 text-sm font-medium text-slate-700 transition hover:bg-slate-100 disabled:cursor-not-allowed disabled:opacity-45"
                >
                  上一页
                </button>
                <template v-for="(page, index) in visiblePages" :key="`system-log-page-${page}-${index}`">
                  <span v-if="page === '...'" class="w-9 select-none text-center text-sm text-slate-400">...</span>
                  <button
                    v-else
                    @click="handlePageChange(page)"
                    :class="[
                      'h-9 min-w-[2.25rem] rounded-lg border px-2 text-sm font-medium transition',
                      currentPage === page
                        ? 'border-blue-600 bg-blue-600 text-white shadow-sm shadow-blue-100'
                        : 'border-slate-300 bg-white text-slate-700 hover:bg-slate-100'
                    ]"
                  >
                    {{ page }}
                  </button>
                </template>
                <button
                  @click="handlePageChange(currentPage + 1)"
                  :disabled="currentPage === totalPages"
                  class="h-9 rounded-lg border border-slate-300 bg-white px-3 text-sm font-medium text-slate-700 transition hover:bg-slate-100 disabled:cursor-not-allowed disabled:opacity-45"
                >
                  下一页
                </button>
              </div>
            </div>
          </div>
        </div>
      </section>
    </section>
  </div>
</template>

<style scoped>
.panel-surface {
  background: linear-gradient(180deg, #ffffff 0%, #f8fbff 100%);
}

.line-clamp-2 {
  display: -webkit-box;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 2;
  overflow: hidden;
}

.notice-enter-active,
.notice-leave-active {
  transition: all 180ms ease;
}

.notice-enter-from,
.notice-leave-to {
  opacity: 0;
  transform: translateY(-6px);
}
</style>

