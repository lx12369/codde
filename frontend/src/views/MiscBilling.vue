<script setup>
import { computed, onMounted, onUnmounted, reactive, ref } from 'vue'
import { billingApi } from '@/api'

const loading = ref(false)
const saving = ref(false)
const requestError = ref('')
const miscItems = ref([])
const editingId = ref('')

const createForm = reactive({
  name: '',
  unit_price: '',
  unit_label: '个',
  initial_stock: '',
  safe_stock: '',
  low_stock_alert: true,
  enabled: true
})

const editForm = reactive({
  name: '',
  unit_price: '',
  unit_label: '个',
  safe_stock: '',
  low_stock_alert: true
})

const createErrors = reactive({
  name: '',
  unit_price: '',
  unit_label: '',
  initial_stock: '',
  safe_stock: ''
})
const editError = ref('')

const feedback = reactive({
  tone: 'info',
  message: ''
})
let feedbackTimer = null

const sortedItems = computed(() =>
  [...miscItems.value].sort((left, right) => {
    const leftOrder = Number(left.sort_order || 0)
    const rightOrder = Number(right.sort_order || 0)
    if (leftOrder !== rightOrder) return leftOrder - rightOrder
    return String(left.name || '').localeCompare(String(right.name || ''), 'zh-CN')
  })
)

const miscMetrics = computed(() => {
  const total = sortedItems.value.length
  const enabled = sortedItems.value.filter((item) => item.enabled).length
  const disabled = Math.max(0, total - enabled)
  const totalStock = sortedItems.value.reduce((sum, item) => sum + (Number(item.current_stock) || 0), 0)
  const lowStock = sortedItems.value.filter((item) => isLowStock(item)).length
  const averagePrice = total > 0
    ? sortedItems.value.reduce((sum, item) => sum + (Number(item.unit_price) || 0), 0) / total
    : 0

  return {
    total,
    enabled,
    disabled,
    totalStock,
    lowStock,
    averagePrice
  }
})

const lowStockItems = computed(() =>
  sortedItems.value.filter((item) => isLowStock(item))
)

const tableFilters = reactive({
  keyword: '',
  status: 'all',
  stock: 'all'
})

const hasActiveTableFilters = computed(() =>
  String(tableFilters.keyword || '').trim().length > 0
  || tableFilters.status !== 'all'
  || tableFilters.stock !== 'all'
)

const filteredItems = computed(() => {
  const keyword = String(tableFilters.keyword || '').trim().toLowerCase()

  return sortedItems.value.filter((item) => {
    if (keyword) {
      const searchable = `${item.name || ''} ${item.unit_label || ''}`.toLowerCase()
      if (!searchable.includes(keyword)) return false
    }

    if (tableFilters.status === 'enabled' && !item.enabled) return false
    if (tableFilters.status === 'disabled' && item.enabled) return false

    if (tableFilters.stock === 'low' && !isLowStock(item)) return false
    if (tableFilters.stock === 'normal' && isLowStock(item)) return false

    return true
  })
})

function formatYuan(value) {
  return `¥${(Number(value) || 0).toFixed(2)}`
}

function formatStock(value) {
  return (Number(value) || 0).toLocaleString('zh-CN', { maximumFractionDigits: 3 })
}

function isTruthy(value, fallback = false) {
  if (typeof value === 'boolean') return value
  if (value === null || value === undefined) return fallback
  const normalized = String(value).trim().toLowerCase()
  if (['1', 'true', 'yes', 'y', 'on'].includes(normalized)) return true
  if (['0', 'false', 'no', 'n', 'off'].includes(normalized)) return false
  return fallback
}

function unwrapData(payload, fallback = {}) {
  if (payload && typeof payload === 'object' && Object.prototype.hasOwnProperty.call(payload, 'data')) {
    return payload.data ?? fallback
  }
  return payload ?? fallback
}

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
  }, 3600)
}

function getFeedbackClass(tone) {
  if (tone === 'success') return 'management-feedback--success'
  if (tone === 'error') return 'management-feedback--error'
  return 'management-feedback--info'
}

function normalizePrice(value) {
  const parsed = Number(value)
  if (!Number.isFinite(parsed)) return null
  if (parsed < 0) return null
  return Math.round((parsed + Number.EPSILON) * 100) / 100
}

function normalizeStock(value, fallback = null) {
  if (value === '' || value === null || value === undefined) return fallback
  const parsed = Number(value)
  if (!Number.isFinite(parsed)) return null
  if (parsed < 0) return null
  return Math.round((parsed + Number.EPSILON) * 1000) / 1000
}

function isLowStock(item) {
  if (!isTruthy(item?.low_stock_alert, true)) return false
  const currentStock = Number(item?.current_stock) || 0
  const safeStock = Number(item?.safe_stock) || 0
  return currentStock <= safeStock
}

function normalizeLocalItems(rawItems = []) {
  if (!Array.isArray(rawItems)) return []
  return rawItems
    .filter((item) => item && typeof item === 'object')
    .map((item, index) => ({
      id: String(item.id || `misc_local_${index + 1}`).trim() || `misc_local_${index + 1}`,
      name: String(item.name || '').trim(),
      unit_price: Number(item.unit_price) || 0,
      unit_label: String(item.unit_label || '个').trim() || '个',
      enabled: Boolean(item.enabled),
      current_stock: Math.max(0, Number(item.current_stock) || 0),
      safe_stock: Math.max(0, Number(item.safe_stock) || 0),
      low_stock_alert: isTruthy(item.low_stock_alert, true),
      sort_order: Number.isFinite(Number(item.sort_order)) ? Number(item.sort_order) : index + 1
    }))
    .filter((item) => item.name)
    .sort((left, right) => Number(left.sort_order || 0) - Number(right.sort_order || 0))
    .map((item, index) => ({
      ...item,
      sort_order: index + 1
    }))
}

function buildPersistItems(items = []) {
  return normalizeLocalItems(items).map((item, index) => ({
    id: item.id,
    name: item.name,
    unit_price: Math.round((Number(item.unit_price || 0) + Number.EPSILON) * 100) / 100,
    unit_label: item.unit_label || '个',
    enabled: Boolean(item.enabled),
    current_stock: Math.round((Math.max(0, Number(item.current_stock) || 0) + Number.EPSILON) * 1000) / 1000,
    safe_stock: Math.round((Math.max(0, Number(item.safe_stock) || 0) + Number.EPSILON) * 1000) / 1000,
    low_stock_alert: isTruthy(item.low_stock_alert, true),
    sort_order: index + 1
  }))
}

function hasDuplicateName(name, excludeId = '') {
  const target = String(name || '').trim().toLowerCase()
  if (!target) return false
  return miscItems.value.some((item) => (
    String(item.id || '') !== String(excludeId || '')
    && String(item.name || '').trim().toLowerCase() === target
  ))
}

async function fetchMiscRules() {
  loading.value = true
  requestError.value = ''
  try {
    const response = await billingApi.getMiscBillingRules()
    const data = unwrapData(response, {})
    const misc = data.misc || { items: [] }
    miscItems.value = normalizeLocalItems(misc.items)
  } catch (error) {
    console.error('加载杂项规则失败:', error)
    requestError.value = error?.response?.data?.message || error?.message || '加载杂项规则失败'
    miscItems.value = []
  } finally {
    loading.value = false
  }
}

async function persistItems(nextItems, successMessage) {
  saving.value = true
  requestError.value = ''
  try {
    const payloadItems = buildPersistItems(nextItems)
    const response = await billingApi.updateMiscBillingRules(payloadItems)
    const data = unwrapData(response, {})
    const misc = data.misc || { items: payloadItems }
    miscItems.value = normalizeLocalItems(misc.items)
    editingId.value = ''
    editError.value = ''
    showFeedback('success', successMessage)
  } catch (error) {
    console.error('保存杂项规则失败:', error)
    requestError.value = error?.response?.data?.message || error?.message || '保存杂项规则失败'
    showFeedback('error', requestError.value)
    throw error
  } finally {
    saving.value = false
  }
}

function resetCreateErrors() {
  createErrors.name = ''
  createErrors.unit_price = ''
  createErrors.unit_label = ''
  createErrors.initial_stock = ''
  createErrors.safe_stock = ''
}

async function addRule() {
  resetCreateErrors()

  const name = String(createForm.name || '').trim()
  const unitLabel = String(createForm.unit_label || '').trim() || '个'
  const unitPrice = normalizePrice(createForm.unit_price)
  const initialStock = normalizeStock(createForm.initial_stock, 0)
  const safeStock = normalizeStock(createForm.safe_stock, 0)

  if (!name) createErrors.name = '请输入杂项名称'
  if (hasDuplicateName(name)) createErrors.name = '杂项名称不能重复'
  if (unitPrice === null) createErrors.unit_price = '请输入大于等于 0 的单价'
  if (!unitLabel) createErrors.unit_label = '请输入单位'
  if (initialStock === null) createErrors.initial_stock = '请输入大于等于 0 的库存'
  if (safeStock === null) createErrors.safe_stock = '请输入大于等于 0 的预警线'

  if (createErrors.name || createErrors.unit_price || createErrors.unit_label || createErrors.initial_stock || createErrors.safe_stock) return

  const nextItems = [
    ...miscItems.value,
    {
      id: `misc_local_${Date.now()}`,
      name,
      unit_price: unitPrice,
      unit_label: unitLabel,
      enabled: Boolean(createForm.enabled),
      current_stock: initialStock,
      safe_stock: safeStock,
      low_stock_alert: Boolean(createForm.low_stock_alert),
      sort_order: miscItems.value.length + 1
    }
  ]

  await persistItems(nextItems, '杂项规则已新增')

  createForm.name = ''
  createForm.unit_price = ''
  createForm.unit_label = '个'
  createForm.initial_stock = ''
  createForm.safe_stock = ''
  createForm.low_stock_alert = true
  createForm.enabled = true
}

function startEdit(item) {
  editingId.value = item.id
  editForm.name = item.name
  editForm.unit_price = String(item.unit_price)
  editForm.unit_label = item.unit_label || '个'
  editForm.safe_stock = String(item.safe_stock ?? 0)
  editForm.low_stock_alert = isTruthy(item.low_stock_alert, true)
  editError.value = ''
}

function cancelEdit() {
  editingId.value = ''
  editError.value = ''
}

async function saveEdit(item) {
  const name = String(editForm.name || '').trim()
  const unitLabel = String(editForm.unit_label || '').trim() || '个'
  const unitPrice = normalizePrice(editForm.unit_price)
  const safeStock = normalizeStock(editForm.safe_stock, 0)

  if (!name) {
    editError.value = '请输入杂项名称'
    return
  }
  if (hasDuplicateName(name, item.id)) {
    editError.value = '杂项名称不能重复'
    return
  }
  if (unitPrice === null) {
    editError.value = '请输入大于等于 0 的单价'
    return
  }
  if (!unitLabel) {
    editError.value = '请输入单位'
    return
  }
  if (safeStock === null) {
    editError.value = '请输入大于等于 0 的预警线'
    return
  }

  const nextItems = miscItems.value.map((current) => (
    current.id === item.id
      ? {
        ...current,
        name,
        unit_price: unitPrice,
        unit_label: unitLabel,
        safe_stock: safeStock,
        low_stock_alert: Boolean(editForm.low_stock_alert)
      }
      : current
  ))

  await persistItems(nextItems, '杂项规则已更新')
}

async function toggleEnabled(item) {
  const nextItems = miscItems.value.map((current) => (
    current.id === item.id
      ? { ...current, enabled: !Boolean(current.enabled) }
      : current
  ))
  await persistItems(nextItems, Boolean(item.enabled) ? '规则已停用' : '规则已启用')
}

async function adjustStock(item, movement) {
  if (!item?.id) return
  if (saving.value) return

  const movementLabel = movement === 'inbound' ? '入库' : '出库'
  const unitLabel = item.unit_label || '个'
  const quantityInput = window.prompt(`请输入${item.name}的${movementLabel}数量（单位：${unitLabel}）`, '')
  if (quantityInput === null) return

  const quantity = normalizeStock(quantityInput, null)
  if (quantity === null || quantity <= 0) {
    showFeedback('error', `${movementLabel}数量必须大于 0`)
    return
  }

  const noteInput = window.prompt('备注（可选）', '')
  const note = noteInput === null ? '' : String(noteInput || '').trim()

  saving.value = true
  requestError.value = ''
  try {
    const response = movement === 'inbound'
      ? await billingApi.inboundMiscBillingStock(item.id, { quantity, note })
      : await billingApi.outboundMiscBillingStock(item.id, { quantity, note })
    const payload = unwrapData(response, {})
    const misc = payload.misc || { items: [] }
    miscItems.value = normalizeLocalItems(misc.items)

    const latestItem = miscItems.value.find((current) => current.id === item.id)
    const lowStockText = latestItem && isLowStock(latestItem) ? '（当前触发低库存预警）' : ''
    showFeedback('success', `${movementLabel}成功：${item.name} ${formatStock(quantity)}${unitLabel}${lowStockText}`)
  } catch (error) {
    console.error(`${movementLabel}失败:`, error)
    requestError.value = error?.response?.data?.message || error?.message || `${movementLabel}失败`
    showFeedback('error', requestError.value)
  } finally {
    saving.value = false
  }
}

async function removeRule(item) {
  const confirmed = window.confirm(`确认删除杂项规则“${item.name}”吗？`)
  if (!confirmed) return
  const nextItems = miscItems.value.filter((current) => current.id !== item.id)
  await persistItems(nextItems, '杂项规则已删除')
}

function resetTableFilters() {
  tableFilters.keyword = ''
  tableFilters.status = 'all'
  tableFilters.stock = 'all'
}

function getStockProgress(item) {
  const currentStock = Math.max(0, Number(item?.current_stock) || 0)
  const safeStock = Math.max(0, Number(item?.safe_stock) || 0)
  if (currentStock <= 0) return 0
  if (safeStock <= 0) return 100
  const ratio = (currentStock / (safeStock * 2)) * 100
  return Math.max(0, Math.min(100, Math.round(ratio)))
}

function getStockProgressClass(item) {
  if (isLowStock(item)) return 'misc-stock-progress__bar--low'
  return 'misc-stock-progress__bar--ok'
}

onMounted(() => {
  fetchMiscRules()
})

onUnmounted(() => {
  clearFeedbackTimer()
})
</script>

<template>
  <div class="space-y-6">
    <section class="page-hero rounded-3xl p-6 sm:p-8">
      <div class="relative z-10 flex flex-col gap-6 lg:flex-row lg:items-start lg:justify-between">
        <div class="max-w-2xl space-y-2">
          <p class="page-hero__eyebrow">Misc Pricing Desk</p>
          <h1 class="page-hero__title">杂项计费</h1>
          <p class="page-hero__subtitle">
            配置店内杂项计费规则，并维护库存入库/出库与低库存预警。
          </p>
        </div>
        <button @click="fetchMiscRules" :disabled="loading || saving" class="page-hero__action">
          {{ loading ? '加载中...' : '刷新规则' }}
        </button>
      </div>
    </section>

    <Transition name="notice">
      <div
        v-if="feedback.message"
        role="status"
        aria-live="polite"
        :class="['management-feedback flex items-center gap-2', getFeedbackClass(feedback.tone)]"
      >
        <svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12l2 2 4-4" />
        </svg>
        <span>{{ feedback.message }}</span>
      </div>
    </Transition>

    <p v-if="requestError" class="management-feedback management-feedback--error">
      {{ requestError }}
    </p>

    <section class="misc-overview-grid" aria-label="杂项规则概况">
      <article class="misc-kpi-card">
        <p class="misc-kpi-card__label">杂项总数</p>
        <p class="misc-kpi-card__value">{{ miscMetrics.total }}</p>
      </article>
      <article class="misc-kpi-card misc-kpi-card--alive">
        <p class="misc-kpi-card__label">当前启用</p>
        <p class="misc-kpi-card__value">{{ miscMetrics.enabled }}</p>
      </article>
      <article class="misc-kpi-card misc-kpi-card--stock">
        <p class="misc-kpi-card__label">库存总量</p>
        <p class="misc-kpi-card__value">{{ formatStock(miscMetrics.totalStock) }}</p>
      </article>
      <article class="misc-kpi-card misc-kpi-card--warning">
        <p class="misc-kpi-card__label">低库存预警</p>
        <p class="misc-kpi-card__value">{{ miscMetrics.lowStock }}</p>
      </article>
    </section>

    <section class="management-surface misc-panel misc-panel--composer p-5 sm:p-6 space-y-5">
      <div class="misc-panel__head">
        <div>
          <h2 class="text-lg font-semibold text-slate-900">新增杂项规则</h2>
          <p class="text-sm text-slate-500 mt-1">新增后会同步到消费结算，金额自动计入订单总价。</p>
        </div>
        <span class="misc-sync-pill">实时同步</span>
      </div>

      <div class="misc-form-grid">
        <div class="misc-field">
          <label class="misc-field__label">名称</label>
          <input
            v-model="createForm.name"
            type="text"
            placeholder="例如：钥匙串"
            :class="['misc-field__control', createErrors.name ? 'misc-field__control--error' : '']"
          >
          <p v-if="createErrors.name" class="misc-field__error">{{ createErrors.name }}</p>
        </div>

        <div class="misc-field">
          <label class="misc-field__label">单价</label>
          <input
            v-model="createForm.unit_price"
            type="number"
            min="0"
            step="0.01"
            placeholder="0.00"
            :class="['misc-field__control', createErrors.unit_price ? 'misc-field__control--error' : '']"
          >
          <p v-if="createErrors.unit_price" class="misc-field__error">{{ createErrors.unit_price }}</p>
        </div>

        <div class="misc-field">
          <label class="misc-field__label">单位</label>
          <input
            v-model="createForm.unit_label"
            type="text"
            placeholder="个"
            :class="['misc-field__control', createErrors.unit_label ? 'misc-field__control--error' : '']"
          >
          <p v-if="createErrors.unit_label" class="misc-field__error">{{ createErrors.unit_label }}</p>
        </div>

        <div class="misc-field">
          <label class="misc-field__label">初始库存</label>
          <input
            v-model="createForm.initial_stock"
            type="number"
            min="0"
            step="0.001"
            placeholder="0"
            :class="['misc-field__control', createErrors.initial_stock ? 'misc-field__control--error' : '']"
          >
          <p v-if="createErrors.initial_stock" class="misc-field__error">{{ createErrors.initial_stock }}</p>
        </div>

        <div class="misc-field">
          <label class="misc-field__label">低库存预警线</label>
          <input
            v-model="createForm.safe_stock"
            type="number"
            min="0"
            step="0.001"
            placeholder="0"
            :class="['misc-field__control', createErrors.safe_stock ? 'misc-field__control--error' : '']"
          >
          <p v-if="createErrors.safe_stock" class="misc-field__error">{{ createErrors.safe_stock }}</p>
        </div>

        <div class="misc-submit-box">
          <div class="flex flex-col gap-2">
            <label class="misc-toggle">
              <input v-model="createForm.enabled" type="checkbox" class="h-4 w-4 rounded border-slate-300 text-amber-600">
              <span>默认启用</span>
            </label>
            <label class="misc-toggle">
              <input v-model="createForm.low_stock_alert" type="checkbox" class="h-4 w-4 rounded border-slate-300 text-amber-600">
              <span>开启低库存预警</span>
            </label>
          </div>
          <button @click="addRule" :disabled="saving" class="misc-btn misc-btn--primary">
            {{ saving ? '保存中...' : '添加规则' }}
          </button>
        </div>
      </div>
    </section>

    <section v-if="lowStockItems.length > 0" class="management-surface misc-panel misc-panel--warning p-5 sm:p-6">
      <div class="flex flex-wrap items-center justify-between gap-3">
        <h2 class="text-lg font-semibold text-amber-900">低库存预警（{{ lowStockItems.length }}）</h2>
      </div>
      <div class="mt-3 flex flex-wrap gap-2">
        <button
          v-for="item in lowStockItems"
          :key="`warn-${item.id}`"
          type="button"
          @click="startEdit(item)"
          class="misc-warning-chip"
        >
          {{ item.name }}：{{ formatStock(item.current_stock) }} / {{ formatStock(item.safe_stock) }} {{ item.unit_label || '个' }}
        </button>
      </div>
    </section>

    <section class="management-surface misc-panel p-5 sm:p-6">
      <div class="mb-4 flex flex-wrap items-center justify-between gap-3">
        <h2 class="text-lg font-semibold text-slate-900">杂项列表</h2>
        <div class="flex flex-wrap items-center gap-2 text-xs">
          <span class="misc-pill">共 {{ sortedItems.length }} 项</span>
          <span class="misc-pill">筛选后 {{ filteredItems.length }} 项</span>
          <span class="misc-pill misc-pill--success">启用 {{ miscMetrics.enabled }}</span>
          <span class="misc-pill misc-pill--muted">停用 {{ miscMetrics.disabled }}</span>
          <span class="misc-pill misc-pill--warning">低库存 {{ miscMetrics.lowStock }}</span>
        </div>
      </div>

      <div class="misc-list-toolbar mb-4">
        <label class="misc-select-box">
          <span class="misc-select-box__label">关键词</span>
          <div class="misc-search">
            <svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4 text-slate-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="m21 21-4.35-4.35m1.1-4.65a5.75 5.75 0 1 1-11.5 0 5.75 5.75 0 0 1 11.5 0Z" />
            </svg>
            <input
              v-model.trim="tableFilters.keyword"
              type="text"
              placeholder="搜索名称或单位"
              class="misc-search__input"
            >
          </div>
        </label>

        <label class="misc-select-box">
          <span class="misc-select-box__label">状态</span>
          <select v-model="tableFilters.status" class="misc-select">
            <option value="all">全部</option>
            <option value="enabled">仅启用</option>
            <option value="disabled">仅停用</option>
          </select>
        </label>

        <label class="misc-select-box">
          <span class="misc-select-box__label">库存</span>
          <select v-model="tableFilters.stock" class="misc-select">
            <option value="all">全部</option>
            <option value="low">仅低库存</option>
            <option value="normal">正常库存</option>
          </select>
        </label>

        <button
          type="button"
          :disabled="!hasActiveTableFilters"
          class="misc-btn misc-btn--ghost"
          @click="resetTableFilters"
        >
          清空筛选
        </button>
      </div>

      <div v-if="loading" class="misc-empty-state">
        <div class="misc-loading-dot"></div>
        <p>正在同步杂项规则...</p>
      </div>
      <div v-else-if="sortedItems.length === 0" class="misc-empty-state">
        <p class="text-slate-600">暂无杂项规则</p>
        <p class="text-xs text-slate-500">先在上方新增一个计费项，例如钥匙串、包装袋、纪念贴纸。</p>
      </div>
      <div v-else-if="filteredItems.length === 0" class="misc-empty-state">
        <p class="text-slate-600">没有匹配当前筛选条件的规则</p>
        <p class="text-xs text-slate-500">尝试清空筛选，或调整关键字/状态条件。</p>
      </div>
      <div v-else class="misc-rule-grid">
        <article
          v-for="item in filteredItems"
          :key="item.id"
          :class="['misc-rule-card', isLowStock(item) ? 'misc-rule-card--low' : '']"
        >
          <header class="misc-rule-card__head">
            <div class="space-y-1">
              <template v-if="editingId === item.id">
                <input v-model="editForm.name" type="text" class="misc-inline-input">
              </template>
              <template v-else>
                <h3 class="misc-rule-card__title">{{ item.name }}</h3>
              </template>
              <p class="misc-rule-card__id">ID: {{ item.id }}</p>
            </div>
            <span :class="['misc-status-chip', item.enabled ? 'misc-status-chip--on' : 'misc-status-chip--off']">
              {{ item.enabled ? '启用中' : '已停用' }}
            </span>
          </header>

          <div class="misc-rule-card__details">
            <div class="misc-rule-card__detail">
              <p class="misc-rule-card__label">单价</p>
              <template v-if="editingId === item.id">
                <input v-model="editForm.unit_price" type="number" min="0" step="0.01" class="misc-inline-input">
              </template>
              <template v-else>
                <p class="misc-rule-card__value">{{ formatYuan(item.unit_price) }}</p>
              </template>
            </div>

            <div class="misc-rule-card__detail">
              <p class="misc-rule-card__label">单位</p>
              <template v-if="editingId === item.id">
                <input v-model="editForm.unit_label" type="text" class="misc-inline-input">
              </template>
              <template v-else>
                <p class="misc-rule-card__value">{{ item.unit_label || '个' }}</p>
              </template>
            </div>
          </div>

          <section class="misc-rule-stock">
            <div class="misc-rule-stock__top">
              <p class="misc-rule-card__label">当前库存</p>
              <p :class="['misc-rule-stock__value', isLowStock(item) ? 'misc-stock-value--low' : '']">
                {{ formatStock(item.current_stock) }} {{ item.unit_label || '个' }}
              </p>
            </div>
            <div class="misc-stock-progress">
              <span
                :class="['misc-stock-progress__bar', getStockProgressClass(item)]"
                :style="{ width: `${getStockProgress(item)}%` }"
              ></span>
            </div>
            <div class="misc-rule-stock__actions">
              <button @click="adjustStock(item, 'inbound')" :disabled="saving" class="misc-mini-btn misc-mini-btn--inbound">入库</button>
              <button @click="adjustStock(item, 'outbound')" :disabled="saving" class="misc-mini-btn misc-mini-btn--outbound">出库</button>
            </div>
          </section>

          <section class="misc-rule-alert">
            <template v-if="editingId === item.id">
              <div class="misc-rule-alert__form">
                <label class="misc-rule-card__label">低库存预警线</label>
                <input v-model="editForm.safe_stock" type="number" min="0" step="0.001" class="misc-inline-input">
                <label class="misc-toggle text-xs">
                  <input v-model="editForm.low_stock_alert" type="checkbox" class="h-3.5 w-3.5 rounded border-slate-300 text-amber-600">
                  <span>启用低库存预警</span>
                </label>
              </div>
            </template>
            <template v-else>
              <div class="misc-rule-alert__meta">
                <div class="misc-rule-alert__line">
                  <p class="misc-rule-card__label">预警线</p>
                  <p class="misc-rule-card__value">{{ formatStock(item.safe_stock) }} {{ item.unit_label || '个' }}</p>
                </div>
                <span :class="['misc-alert-flag', item.low_stock_alert ? 'misc-alert-flag--on' : 'misc-alert-flag--off']">
                  {{ item.low_stock_alert ? '预警开启' : '预警关闭' }}
                </span>
              </div>
            </template>
          </section>

          <p v-if="editError && editingId === item.id" class="misc-rule-card__error">{{ editError }}</p>

          <footer class="misc-rule-card__footer">
            <template v-if="editingId === item.id">
              <button @click="saveEdit(item)" :disabled="saving" class="misc-mini-btn misc-mini-btn--save">保存修改</button>
              <button @click="cancelEdit" :disabled="saving" class="misc-mini-btn">取消编辑</button>
            </template>
            <template v-else>
              <button @click="startEdit(item)" :disabled="saving" class="misc-mini-btn">编辑</button>
              <button @click="toggleEnabled(item)" :disabled="saving" class="misc-mini-btn misc-mini-btn--switch">
                {{ item.enabled ? '停用规则' : '启用规则' }}
              </button>
              <button @click="removeRule(item)" :disabled="saving" class="misc-mini-btn misc-mini-btn--danger">删除</button>
            </template>
          </footer>
        </article>
      </div>
    </section>
  </div>
</template>

<style scoped>
:root {
  --misc-ink: #2b1e18;
  --misc-muted: #6b5a4e;
  --misc-border: #e7d9cb;
  --misc-soft: #f7efe6;
  --misc-soft-2: #fff8f2;
  --misc-accent: #b7723e;
  --misc-accent-2: #8c4f2b;
  --misc-danger: #c74d4d;
}

.misc-overview-grid {
  display: grid;
  gap: 0.75rem;
  grid-template-columns: repeat(1, minmax(0, 1fr));
}

@media (min-width: 768px) {
  .misc-overview-grid {
    grid-template-columns: repeat(4, minmax(0, 1fr));
  }
}

.misc-kpi-card {
  position: relative;
  overflow: hidden;
  border: 1px solid var(--misc-border);
  border-radius: 1rem;
  background: linear-gradient(140deg, #fffaf5, #f8ede2 65%, #f3e3d2);
  padding: 0.9rem 1rem;
  box-shadow: 0 8px 24px rgba(111, 78, 55, 0.08);
}

.misc-kpi-card::after {
  content: '';
  position: absolute;
  right: -18px;
  top: -18px;
  width: 72px;
  height: 72px;
  border-radius: 999px;
  background: radial-gradient(circle, rgba(255, 255, 255, 0.6), rgba(255, 255, 255, 0));
}

.misc-kpi-card__label {
  font-size: 0.74rem;
  letter-spacing: 0.04em;
  color: var(--misc-muted);
  margin-bottom: 0.25rem;
}

.misc-kpi-card__value {
  font-size: 1.45rem;
  line-height: 1.2;
  font-weight: 700;
  color: var(--misc-ink);
}

.misc-kpi-card--alive {
  background: linear-gradient(140deg, #f2fbf6, #def5e8 60%, #cdeedc);
}

.misc-kpi-card--stock {
  background: linear-gradient(140deg, #f5fbff, #e5f3ff 60%, #d7ebff);
}

.misc-kpi-card--warning {
  background: linear-gradient(140deg, #fffaf0, #ffefcc 60%, #ffe3a8);
}

.misc-panel {
  border: 1px solid var(--misc-border);
  background:
    linear-gradient(180deg, rgba(255, 255, 255, 0.95), rgba(255, 248, 241, 0.95));
  box-shadow: 0 16px 34px rgba(99, 63, 39, 0.08);
}

.misc-panel--warning {
  border-color: #f0cf8f;
  background:
    radial-gradient(circle at 95% 18%, rgba(250, 204, 21, 0.18), transparent 38%),
    linear-gradient(180deg, rgba(255, 251, 235, 0.97), rgba(255, 247, 237, 0.95));
}

.misc-panel--composer {
  position: relative;
  overflow: hidden;
}

.misc-panel--composer::before {
  content: '';
  position: absolute;
  inset: 0;
  pointer-events: none;
  background:
    radial-gradient(circle at 92% 18%, rgba(183, 114, 62, 0.18), transparent 42%),
    radial-gradient(circle at 8% 86%, rgba(140, 79, 43, 0.14), transparent 38%);
}

.misc-panel__head {
  position: relative;
  z-index: 1;
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 0.75rem;
  flex-wrap: wrap;
}

.misc-sync-pill {
  border: 1px solid rgba(183, 114, 62, 0.35);
  color: var(--misc-accent-2);
  background: rgba(255, 244, 234, 0.88);
  border-radius: 999px;
  padding: 0.26rem 0.62rem;
  font-size: 0.74rem;
  font-weight: 600;
}

.misc-form-grid {
  position: relative;
  z-index: 1;
  display: grid;
  grid-template-columns: repeat(1, minmax(0, 1fr));
  gap: 0.85rem;
}

@media (min-width: 980px) {
  .misc-form-grid {
    grid-template-columns:
      minmax(0, 1.25fr)
      minmax(0, 0.9fr)
      minmax(0, 0.8fr)
      minmax(0, 0.9fr)
      minmax(0, 0.9fr)
      minmax(0, 1.2fr);
    align-items: end;
  }
}

.misc-list-toolbar {
  display: grid;
  grid-template-columns: minmax(0, 1fr);
  gap: 0.65rem;
}

@media (min-width: 980px) {
  .misc-list-toolbar {
    grid-template-columns:
      minmax(0, 1.4fr)
      minmax(0, 0.7fr)
      minmax(0, 0.7fr)
      auto;
    align-items: end;
  }
}

.misc-list-toolbar .misc-btn {
  min-height: 40px;
}

.misc-search {
  display: inline-flex;
  align-items: center;
  gap: 0.42rem;
  border: 1px solid #dcc8b9;
  border-radius: 0.82rem;
  background: rgba(255, 255, 255, 0.9);
  padding: 0 0.62rem;
  min-height: 40px;
}

.misc-search__input {
  border: 0;
  background: transparent;
  width: 100%;
  font-size: 0.85rem;
  color: #2f2119;
}

.misc-search__input:focus {
  outline: none;
}

.misc-search:focus-within {
  border-color: #b7723e;
  box-shadow: 0 0 0 3px rgba(183, 114, 62, 0.16);
}

.misc-select-box {
  display: grid;
  gap: 0.26rem;
}

.misc-select-box__label {
  font-size: 0.72rem;
  color: #6c5443;
  font-weight: 600;
}

.misc-select {
  width: 100%;
  border: 1px solid #dbc8b8;
  border-radius: 0.72rem;
  background: rgba(255, 255, 255, 0.9);
  color: #36261c;
  font-size: 0.82rem;
  padding: 0.48rem 0.62rem;
}

.misc-select:focus {
  outline: none;
  border-color: #b7723e;
  box-shadow: 0 0 0 3px rgba(183, 114, 62, 0.16);
}

.misc-field {
  display: flex;
  flex-direction: column;
}

.misc-field__label {
  font-size: 0.79rem;
  color: #4e3a2f;
  font-weight: 600;
  margin-bottom: 0.34rem;
}

.misc-field__control {
  width: 100%;
  border: 1px solid #dac7b8;
  border-radius: 0.78rem;
  background: rgba(255, 255, 255, 0.92);
  color: #2f2119;
  font-size: 0.9rem;
  padding: 0.56rem 0.72rem;
  transition: border-color 0.2s ease, box-shadow 0.2s ease;
}

.misc-field__control:focus {
  outline: none;
  border-color: #b7723e;
  box-shadow: 0 0 0 3px rgba(183, 114, 62, 0.18);
}

.misc-field__control--error {
  border-color: #e47b7b;
}

.misc-field__error {
  margin-top: 0.28rem;
  color: #d44c4c;
  font-size: 0.74rem;
}

.misc-submit-box {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.65rem;
  border: 1px dashed #dbc8b7;
  border-radius: 0.92rem;
  background: rgba(255, 251, 246, 0.92);
  padding: 0.64rem 0.72rem;
  min-height: 46px;
}

.misc-toggle {
  display: inline-flex;
  align-items: center;
  gap: 0.38rem;
  font-size: 0.82rem;
  color: #4a392f;
}

.misc-btn {
  border-radius: 0.78rem;
  font-size: 0.84rem;
  font-weight: 600;
  padding: 0.5rem 0.85rem;
  transition: transform 0.2s ease, box-shadow 0.2s ease, opacity 0.2s ease;
}

.misc-btn:disabled {
  opacity: 0.58;
  cursor: not-allowed;
}

.misc-btn--primary {
  border: 1px solid transparent;
  color: #fff;
  background: linear-gradient(135deg, #c78049, #9b5930);
  box-shadow: 0 8px 20px rgba(155, 89, 48, 0.27);
}

.misc-btn--primary:not(:disabled):hover {
  transform: translateY(-1px);
}

.misc-btn--ghost {
  border: 1px solid #dcc8b8;
  background: rgba(255, 250, 246, 0.92);
  color: #624635;
}

.misc-btn--ghost:not(:disabled):hover {
  background: #fff2e5;
  border-color: #cfaf93;
}

.misc-pill {
  border-radius: 999px;
  border: 1px solid #e0cebf;
  background: #fff6ed;
  color: #5f4a3c;
  padding: 0.2rem 0.58rem;
}

.misc-pill--success {
  border-color: #b6ddbf;
  background: #eaf9ee;
  color: #2f7a45;
}

.misc-pill--muted {
  border-color: #d8d8d8;
  background: #f6f6f6;
  color: #6a6a6a;
}

.misc-pill--warning {
  border-color: #f2c97b;
  background: #fff7df;
  color: #8a5a18;
}

.misc-empty-state {
  border: 1px dashed #dfcdbd;
  border-radius: 1rem;
  padding: 1.7rem 1rem;
  text-align: center;
  display: grid;
  place-items: center;
  gap: 0.45rem;
  color: #6a584b;
  background: #fffaf5;
}

.misc-warning-chip {
  border: 1px solid #edc57a;
  border-radius: 999px;
  background: #fff8e6;
  color: #7f4f18;
  padding: 0.24rem 0.66rem;
  font-size: 0.75rem;
  font-weight: 600;
  transition: background-color 0.2s ease, border-color 0.2s ease;
}

.misc-warning-chip:hover {
  background: #fff3cf;
  border-color: #dfaa4c;
}

.misc-loading-dot {
  width: 28px;
  height: 28px;
  border-radius: 999px;
  border: 3px solid rgba(183, 114, 62, 0.2);
  border-top-color: rgba(183, 114, 62, 0.9);
  animation: misc-spin 0.95s linear infinite;
}

.misc-rule-grid {
  display: grid;
  grid-template-columns: repeat(1, minmax(0, 1fr));
  gap: 0.8rem;
}

@media (min-width: 880px) {
  .misc-rule-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

.misc-rule-card {
  border: 1px solid #e3d2c2;
  border-radius: 1rem;
  background:
    linear-gradient(180deg, rgba(255, 255, 255, 0.96), rgba(255, 248, 242, 0.93));
  box-shadow: 0 10px 24px rgba(123, 81, 52, 0.09);
  padding: 0.85rem;
  display: grid;
  gap: 0.72rem;
  transition: transform 0.2s ease, box-shadow 0.2s ease, border-color 0.2s ease;
}

.misc-rule-card:hover {
  transform: translateY(-1px);
  box-shadow: 0 14px 30px rgba(123, 81, 52, 0.14);
}

.misc-rule-card--low {
  border-color: #edbd93;
  background:
    radial-gradient(circle at 88% 16%, rgba(245, 158, 11, 0.18), transparent 44%),
    linear-gradient(180deg, rgba(255, 251, 235, 0.96), rgba(255, 245, 230, 0.93));
}

.misc-rule-card__head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 0.6rem;
}

.misc-rule-card__title {
  font-size: 1rem;
  line-height: 1.25;
  color: #2d1f17;
  font-weight: 700;
}

.misc-rule-card__id {
  font-size: 0.68rem;
  color: #907261;
}

.misc-rule-card__details {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 0.6rem;
}

.misc-rule-card__detail {
  border: 1px solid #ead8c9;
  border-radius: 0.76rem;
  padding: 0.52rem 0.58rem;
  background: rgba(255, 255, 255, 0.84);
}

.misc-rule-card__label {
  font-size: 0.72rem;
  color: #755f51;
  font-weight: 600;
}

.misc-rule-card__value {
  margin-top: 0.1rem;
  font-size: 0.84rem;
  color: #2f2119;
  font-weight: 700;
}

.misc-rule-stock {
  border: 1px solid #e9d8c8;
  border-radius: 0.82rem;
  background: rgba(255, 255, 255, 0.84);
  padding: 0.56rem 0.62rem;
  display: grid;
  gap: 0.42rem;
}

.misc-rule-stock__top {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 0.5rem;
}

.misc-rule-stock__value {
  font-size: 0.9rem;
  color: #2d2018;
  font-weight: 700;
}

.misc-stock-progress {
  position: relative;
  height: 7px;
  border-radius: 999px;
  background: #efe6de;
  overflow: hidden;
}

.misc-stock-progress__bar {
  display: block;
  height: 100%;
  border-radius: inherit;
  transition: width 0.25s ease;
}

.misc-stock-progress__bar--ok {
  background: linear-gradient(90deg, #34d399, #059669);
}

.misc-stock-progress__bar--low {
  background: linear-gradient(90deg, #fb923c, #ea580c);
}

.misc-rule-stock__actions {
  display: flex;
  flex-wrap: wrap;
  gap: 0.42rem;
}

.misc-rule-alert {
  border: 1px solid #ead8c9;
  border-radius: 0.82rem;
  background: rgba(255, 255, 255, 0.84);
  padding: 0.56rem 0.62rem;
}

.misc-rule-alert__form {
  display: grid;
  gap: 0.35rem;
}

.misc-rule-alert__meta {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.5rem;
}

.misc-rule-alert__line {
  display: grid;
  gap: 0.08rem;
}

.misc-rule-card__footer {
  display: flex;
  flex-wrap: wrap;
  gap: 0.45rem;
}

.misc-rule-card__error {
  font-size: 0.75rem;
  color: #d04f4f;
}

.misc-stock-value--low {
  color: #c2410c;
}

.misc-alert-flag {
  display: inline-flex;
  width: fit-content;
  border-radius: 999px;
  padding: 0.12rem 0.48rem;
  font-size: 0.68rem;
  font-weight: 600;
}

.misc-alert-flag--on {
  background: #fff7df;
  color: #8a5a18;
  border: 1px solid #f2cf90;
}

.misc-alert-flag--off {
  background: #f4f4f5;
  color: #71717a;
  border: 1px solid #e4e4e7;
}

.misc-status-chip {
  display: inline-flex;
  align-items: center;
  border-radius: 999px;
  padding: 0.2rem 0.55rem;
  font-size: 0.72rem;
  font-weight: 600;
}

.misc-status-chip--on {
  background: #e9f8ee;
  color: #277642;
}

.misc-status-chip--off {
  background: #f1f1f1;
  color: #767676;
}

.misc-inline-input {
  width: 100%;
  border: 1px solid #d5c2b2;
  border-radius: 0.62rem;
  background: #fff;
  padding: 0.36rem 0.5rem;
  font-size: 0.82rem;
}

.misc-inline-input:focus {
  outline: none;
  border-color: #b7723e;
  box-shadow: 0 0 0 3px rgba(183, 114, 62, 0.16);
}

.misc-mini-btn {
  border: 1px solid #ddcab9;
  border-radius: 0.54rem;
  background: #fff8f2;
  color: #634d3e;
  font-size: 0.72rem;
  font-weight: 600;
  padding: 0.22rem 0.52rem;
  transition: background-color 0.2s ease, border-color 0.2s ease, transform 0.2s ease;
}

.misc-mini-btn:disabled {
  opacity: 0.44;
  cursor: not-allowed;
}

.misc-mini-btn:not(:disabled):hover {
  background: #fff1e4;
  border-color: #d3b59e;
  transform: translateY(-1px);
}

.misc-mini-btn--save {
  border-color: #abd7ba;
  background: #e9f8ef;
  color: #2d7c49;
}

.misc-mini-btn--switch {
  border-color: #c8d3f5;
  background: #eef2ff;
  color: #3b4f9f;
}

.misc-mini-btn--inbound {
  border-color: #b8e3c6;
  background: #ebf9f0;
  color: #237c45;
}

.misc-mini-btn--outbound {
  border-color: #f2c2ac;
  background: #fff2ec;
  color: #b45309;
}

.misc-mini-btn--danger {
  border-color: #e6b4b4;
  background: #fff0f0;
  color: var(--misc-danger);
}

@keyframes misc-spin {
  to {
    transform: rotate(360deg);
  }
}

@media (prefers-reduced-motion: reduce) {
  .misc-kpi-card,
  .misc-btn,
  .misc-mini-btn {
    transition: none !important;
  }

  .misc-loading-dot {
    animation: none;
  }
}
</style>
