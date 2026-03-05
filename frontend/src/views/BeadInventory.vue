<script setup>
import { ref, reactive, computed, onMounted, onUnmounted } from 'vue'
import { beadInventoryApi } from '@/api'

const loading = ref(false)
const importingMard = ref(false)
const savingMaterial = ref(false)
const submittingInbound = ref(false)
const submittingOutbound = ref(false)
const submittingStocktake = ref(false)
const loadingLedger = ref(false)
const requestError = ref('')
const feedback = reactive({
  tone: 'info',
  message: ''
})
let feedbackTimer = null

const materials = ref([])
const alerts = ref([])
const ledgerItems = ref([])
const selectedMaterialId = ref('')

const pagination = reactive({
  page: 1,
  page_size: 10,
  total: 0,
  total_pages: 0
})

const ledgerPagination = reactive({
  page: 1,
  page_size: 10,
  total: 0,
  total_pages: 0
})

const filters = reactive({
  search: '',
  status: 'active'
})

const ledgerFilters = reactive({
  material_id: '',
  action_type: '',
  date_start: '',
  date_end: ''
})

const showMaterialModal = ref(false)
const showConversionModal = ref(false)
const showMarketPriceModal = ref(false)
const showSafeStockModal = ref(false)
const editingMaterialId = ref('')
const savingConversion = ref(false)
const savingMarketPrice = ref(false)
const savingSafeStock = ref(false)
const materialForm = reactive({
  name: '',
  color_code: '',
  spec: '',
  brand: '',
  grams_per_bag: '',
  grams_per_bottle: '',
  market_price_per_500g: 50,
  safe_stock: '',
  common_color: false,
  status: 'active'
})

const inboundForm = reactive({
  quantity: '',
  quantity_unit: 'gram',
  source: '',
  note: ''
})

const outboundForm = reactive({
  quantity: '',
  quantity_unit: 'gram',
  source: '',
  note: ''
})

const stocktakeForm = reactive({
  counted_quantity: '',
  counted_unit: 'gram',
  note: ''
})

const conversionForm = reactive({
  grams_per_bag: '',
  grams_per_bottle: ''
})

const marketPriceForm = reactive({
  amount: 50,
  grams: 500
})

const safeStockBatchForm = reactive({
  common_safe_stock: '',
  normal_safe_stock: ''
})

const selectedMaterial = computed(() => {
  return materials.value.find(item => item.id === selectedMaterialId.value) || null
})

const totalCurrentGrams = computed(() => {
  return materials.value.reduce((sum, item) => sum + Number(item.current_grams || 0), 0)
})

const lowStockCount = computed(() => {
  return materials.value.filter(item => item.is_low_stock).length
})

const totalInventoryValue = computed(() => {
  return materials.value.reduce((sum, item) => {
    const grams = Number(item.current_grams || 0)
    const pricePer500g = Number(item.market_price_per_500g || 0)
    return sum + (grams * pricePer500g) / 500
  }, 0)
})

const isEditingMaterial = computed(() => Boolean(editingMaterialId.value))
const selectedMaterialHint = computed(() => {
  if (!selectedMaterial.value) return '未选择'
  return `${selectedMaterial.value.name}（${selectedMaterial.value.id}）`
})

const pageSizeOptions = [5, 10, 15, 20, 25, 30, 35, 40, 45, 50]

const materialTotalPages = computed(() => {
  const fallback = Math.ceil((pagination.total || 0) / (pagination.page_size || 1)) || 1
  return Math.max(1, Number(pagination.total_pages) || fallback)
})

const ledgerTotalPages = computed(() => {
  const fallback = Math.ceil((ledgerPagination.total || 0) / (ledgerPagination.page_size || 1)) || 1
  return Math.max(1, Number(ledgerPagination.total_pages) || fallback)
})

function buildVisiblePages(currentPage, totalPages) {
  const pages = []
  for (let page = 1; page <= totalPages; page += 1) {
    const shouldShow = page === 1 || page === totalPages || Math.abs(page - currentPage) <= 1
    if (shouldShow) {
      pages.push(page)
    } else if (pages[pages.length - 1] !== '...') {
      pages.push('...')
    }
  }
  return pages
}

const materialVisiblePages = computed(() => buildVisiblePages(pagination.page, materialTotalPages.value))
const ledgerVisiblePages = computed(() => buildVisiblePages(ledgerPagination.page, ledgerTotalPages.value))
const ledgerActionTypeLabelMap = Object.freeze({
  inbound: '入库',
  outbound: '出库',
  loss: '损耗',
  stocktake_adjust: '盘点调整'
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
  }, 3600)
}

function getFeedbackClass(tone) {
  if (tone === 'success') return 'management-feedback--success'
  if (tone === 'error') return 'management-feedback--error'
  return 'management-feedback--info'
}

function unwrapListResponse(payload) {
  const data = payload?.data || {}
  return {
    items: Array.isArray(data.items) ? data.items : [],
    pagination: data.pagination || {
      page: 1,
      page_size: 10,
      total: 0,
      total_pages: 0
    }
  }
}

function getErrorMessage(error, fallback) {
  return error?.response?.data?.message || error?.message || fallback
}

function formatGrams(value) {
  const num = Number(value || 0)
  return `${num.toLocaleString('zh-CN', { maximumFractionDigits: 3 })} g`
}

function formatPricePer500g(value) {
  const num = Number(value || 0)
  return `¥${num.toFixed(2)} / 500g`
}

function formatMoney(value) {
  const num = Number(value || 0)
  return `¥${num.toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`
}

function formatDateTime(value) {
  if (!value) return '-'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return '-'
  return date.toLocaleString('zh-CN')
}

function getLedgerActionTypeLabel(value) {
  const raw = String(value || '').trim()
  return ledgerActionTypeLabelMap[raw] || raw || '-'
}

function normalizeHexColor(value) {
  const raw = String(value || '').trim()
  if (/^#[0-9a-fA-F]{6}$/.test(raw)) return raw.toLowerCase()
  return ''
}

function getMardCode(name) {
  const raw = String(name || '').trim()
  const match = raw.match(/^Mard\s+([A-Za-z0-9]+)$/i)
  if (match) return match[1].toUpperCase()
  if (/^[A-Za-z0-9]+$/.test(raw)) return raw.toUpperCase()
  return '-'
}

function resetMaterialForm() {
  editingMaterialId.value = ''
  materialForm.name = ''
  materialForm.color_code = ''
  materialForm.spec = ''
  materialForm.brand = ''
  materialForm.grams_per_bag = ''
  materialForm.grams_per_bottle = ''
  materialForm.market_price_per_500g = 50
  materialForm.safe_stock = ''
  materialForm.common_color = false
  materialForm.status = 'active'
}

function openCreateMaterial() {
  resetMaterialForm()
  showMaterialModal.value = true
}

function openEditMaterial(item) {
  editingMaterialId.value = item.id
  materialForm.name = item.name || ''
  materialForm.color_code = item.color_code || ''
  materialForm.spec = item.spec || ''
  materialForm.brand = item.brand || ''
  materialForm.grams_per_bag = item.grams_per_bag ?? ''
  materialForm.grams_per_bottle = item.grams_per_bottle ?? ''
  materialForm.market_price_per_500g = item.market_price_per_500g ?? 50
  materialForm.safe_stock = item.safe_stock ?? ''
  materialForm.common_color = Boolean(item.common_color)
  materialForm.status = item.status || 'active'
  showMaterialModal.value = true
}

function openConversionModal() {
  requestError.value = ''
  conversionForm.grams_per_bag = ''
  conversionForm.grams_per_bottle = ''
  showConversionModal.value = true
}

function openSafeStockModal() {
  requestError.value = ''
  safeStockBatchForm.common_safe_stock = ''
  safeStockBatchForm.normal_safe_stock = ''
  showSafeStockModal.value = true
}

async function fetchMaterials(page = 1) {
  loading.value = true
  requestError.value = ''
  try {
    const response = await beadInventoryApi.getMaterials({
      page,
      page_size: pagination.page_size,
      search: filters.search.trim(),
      status: filters.status
    })
    const { items, pagination: pageData } = unwrapListResponse(response)
    materials.value = items
    pagination.page = pageData.page || 1
    pagination.page_size = pageData.page_size || 10
    pagination.total = pageData.total || 0
    pagination.total_pages = pageData.total_pages || 0

    if (!selectedMaterialId.value || !items.find(item => item.id === selectedMaterialId.value)) {
      selectedMaterialId.value = items[0]?.id || ''
    }
  } catch (error) {
    materials.value = []
    requestError.value = getErrorMessage(error, '加载豆料失败，请稍后重试')
  } finally {
    loading.value = false
  }
}

async function handleMaterialPageChange(page) {
  if (loading.value) return
  if (page < 1 || page > materialTotalPages.value) return
  await fetchMaterials(page)
}

async function handleMaterialPageSizeChange() {
  if (loading.value) return
  await fetchMaterials(1)
}

async function fetchAlerts() {
  try {
    const response = await beadInventoryApi.getAlerts()
    alerts.value = Array.isArray(response?.data?.items) ? response.data.items : []
  } catch (error) {
    console.error('Failed to fetch alerts:', error)
    alerts.value = []
  }
}

async function fetchLedger(page = 1) {
  loadingLedger.value = true
  try {
    const response = await beadInventoryApi.getLedger({
      page,
      page_size: ledgerPagination.page_size,
      material_id: ledgerFilters.material_id,
      action_type: ledgerFilters.action_type,
      date_start: ledgerFilters.date_start || undefined,
      date_end: ledgerFilters.date_end || undefined
    })
    const { items, pagination: pageData } = unwrapListResponse(response)
    ledgerItems.value = items
    ledgerPagination.page = pageData.page || 1
    ledgerPagination.page_size = pageData.page_size || 10
    ledgerPagination.total = pageData.total || 0
    ledgerPagination.total_pages = pageData.total_pages || 0
  } catch (error) {
    console.error('Failed to fetch ledger:', error)
    ledgerItems.value = []
  } finally {
    loadingLedger.value = false
  }
}

async function handleLedgerPageChange(page) {
  if (loadingLedger.value) return
  if (page < 1 || page > ledgerTotalPages.value) return
  await fetchLedger(page)
}

async function handleLedgerPageSizeChange() {
  if (loadingLedger.value) return
  await fetchLedger(1)
}

async function refreshAll() {
  await fetchMaterials(pagination.page || 1)
  await fetchAlerts()
  if (!ledgerFilters.material_id && selectedMaterialId.value) {
    ledgerFilters.material_id = selectedMaterialId.value
  }
  await fetchLedger(ledgerPagination.page || 1)
}

async function submitMaterial() {
  if (!materialForm.name.trim()) {
    requestError.value = '豆料名称不能为空'
    return
  }

  const payload = {
    name: materialForm.name.trim(),
    color_code: materialForm.color_code.trim(),
    spec: materialForm.spec.trim(),
    brand: materialForm.brand.trim(),
    grams_per_bag: materialForm.grams_per_bag === '' ? null : Number(materialForm.grams_per_bag),
    grams_per_bottle: materialForm.grams_per_bottle === '' ? null : Number(materialForm.grams_per_bottle),
    market_price_per_500g: materialForm.market_price_per_500g === '' ? 50 : Number(materialForm.market_price_per_500g),
    safe_stock: materialForm.safe_stock === '' ? 0 : Number(materialForm.safe_stock),
    common_color: Boolean(materialForm.common_color),
    status: materialForm.status
  }

  savingMaterial.value = true
  requestError.value = ''
  try {
    const editingMode = isEditingMaterial.value
    if (isEditingMaterial.value) {
      await beadInventoryApi.updateMaterial(editingMaterialId.value, payload)
    } else {
      await beadInventoryApi.createMaterial(payload)
    }
    showMaterialModal.value = false
    resetMaterialForm()
    await refreshAll()
    showFeedback('success', editingMode ? '豆料信息已更新。' : '豆料已创建。')
  } catch (error) {
    requestError.value = getErrorMessage(error, '保存豆料失败')
    showFeedback('error', requestError.value)
  } finally {
    savingMaterial.value = false
  }
}

async function importMardPalette() {
  const ok = window.confirm('将导入 Mard 221 色号到豆仓，是否继续？')
  if (!ok) return
  importingMard.value = true
  requestError.value = ''
  try {
    const result = await beadInventoryApi.importMardPalette()
    const stats = result?.data || {}
    await refreshAll()
    showFeedback('success', `导入完成：新建 ${stats.created || 0}，更新 ${stats.updated || 0}，跳过 ${stats.skipped || 0}`)
  } catch (error) {
    requestError.value = getErrorMessage(error, '导入 Mard 色卡失败')
    showFeedback('error', requestError.value)
  } finally {
    importingMard.value = false
  }
}

async function toggleCommonColor(item) {
  requestError.value = ''
  try {
    await beadInventoryApi.updateMaterial(item.id, {
      common_color: !item.common_color
    })
    await refreshAll()
    showFeedback('success', item.common_color ? '已取消常用色。' : '已设为常用色。')
  } catch (error) {
    requestError.value = getErrorMessage(error, '更新常用色失败')
    showFeedback('error', requestError.value)
  }
}

async function removeMaterial(item) {
  const ok = window.confirm(`确认删除豆料 ${item.name}（${item.id}）吗？`)
  if (!ok) return
  requestError.value = ''
  try {
    await beadInventoryApi.deleteMaterial(item.id)
    await refreshAll()
    showFeedback('success', '豆料已删除。')
  } catch (error) {
    requestError.value = getErrorMessage(error, '删除豆料失败')
    showFeedback('error', requestError.value)
  }
}

async function handleMaterialRowClick(item) {
  if (!item?.id) return
  selectedMaterialId.value = item.id
  ledgerFilters.material_id = item.id
  await fetchLedger(1)
}

async function handleAlertClick(alert) {
  if (!alert?.id) return
  selectedMaterialId.value = alert.id
  ledgerFilters.material_id = alert.id
  await fetchLedger(1)
}

async function submitInbound() {
  if (!selectedMaterial.value) {
    requestError.value = '请先选择豆料'
    return
  }
  submittingInbound.value = true
  requestError.value = ''
  try {
    await beadInventoryApi.createInbound({
      material_id: selectedMaterial.value.id,
      quantity: Number(inboundForm.quantity),
      quantity_unit: inboundForm.quantity_unit,
      source: inboundForm.source,
      note: inboundForm.note
    })
    inboundForm.quantity = ''
    inboundForm.source = ''
    inboundForm.note = ''
    await refreshAll()
    showFeedback('success', '补货入库成功。')
  } catch (error) {
    requestError.value = getErrorMessage(error, '补货入库失败')
    showFeedback('error', requestError.value)
  } finally {
    submittingInbound.value = false
  }
}

async function submitOutbound() {
  if (!selectedMaterial.value) {
    requestError.value = '请先选择豆料'
    return
  }
  submittingOutbound.value = true
  requestError.value = ''
  try {
    await beadInventoryApi.createOutbound({
      material_id: selectedMaterial.value.id,
      quantity: Number(outboundForm.quantity),
      quantity_unit: outboundForm.quantity_unit,
      outbound_type: 'loss',
      usage_type: outboundForm.source || '损耗出库',
      note: outboundForm.note
    })
    outboundForm.quantity = ''
    outboundForm.source = ''
    outboundForm.note = ''
    await refreshAll()
    showFeedback('success', '损耗出库成功。')
  } catch (error) {
    requestError.value = getErrorMessage(error, '出库失败')
    showFeedback('error', requestError.value)
  } finally {
    submittingOutbound.value = false
  }
}

async function submitStocktake() {
  if (!selectedMaterial.value) {
    requestError.value = '请先选择豆料'
    return
  }
  submittingStocktake.value = true
  requestError.value = ''
  try {
    await beadInventoryApi.createStocktake({
      material_id: selectedMaterial.value.id,
      counted_quantity: Number(stocktakeForm.counted_quantity),
      counted_unit: stocktakeForm.counted_unit,
      note: stocktakeForm.note
    })
    stocktakeForm.counted_quantity = ''
    stocktakeForm.note = ''
    await refreshAll()
    showFeedback('success', '库存盘点已完成。')
  } catch (error) {
    requestError.value = getErrorMessage(error, '盘点失败')
    showFeedback('error', requestError.value)
  } finally {
    submittingStocktake.value = false
  }
}

async function submitConversionStandard() {
  savingConversion.value = true
  requestError.value = ''
  try {
    const result = await beadInventoryApi.batchUpdateConversionStandard({
      grams_per_bag: conversionForm.grams_per_bag === '' ? null : Number(conversionForm.grams_per_bag),
      grams_per_bottle: conversionForm.grams_per_bottle === '' ? null : Number(conversionForm.grams_per_bottle)
    })
    const changed = result?.data?.changed ?? 0
    showConversionModal.value = false
    await refreshAll()
    showFeedback('success', `单位换算标准已应用，更新 ${changed} 条。`)
  } catch (error) {
    requestError.value = getErrorMessage(error, '保存单位换算标准失败')
    showFeedback('error', requestError.value)
  } finally {
    savingConversion.value = false
  }
}

async function setAllMarketPriceToDefault() {
  showMarketPriceModal.value = true
}

async function submitSafeStockBatch() {
  const common = Number(safeStockBatchForm.common_safe_stock)
  const normal = Number(safeStockBatchForm.normal_safe_stock)
  if (Number.isNaN(common) || common < 0) {
    requestError.value = '常用色安全库存必须是大于等于 0 的数字'
    return
  }
  if (Number.isNaN(normal) || normal < 0) {
    requestError.value = '非常用色安全库存必须是大于等于 0 的数字'
    return
  }

  savingSafeStock.value = true
  requestError.value = ''
  try {
    const result = await beadInventoryApi.batchUpdateSafeStockByCommonColor({
      common_safe_stock: Number(common.toFixed(3)),
      normal_safe_stock: Number(normal.toFixed(3))
    })
    const data = result?.data || {}
    showSafeStockModal.value = false
    await refreshAll()
    showFeedback(
      'success',
      `安全库存已更新：常用色 ${data.changed_common ?? 0}/${data.target_common ?? 0} 条，非常用色 ${data.changed_normal ?? 0}/${data.target_normal ?? 0} 条。`
    )
  } catch (error) {
    requestError.value = getErrorMessage(error, '批量更新安全库存失败')
    showFeedback('error', requestError.value)
  } finally {
    savingSafeStock.value = false
  }
}

async function submitMarketPrice() {
  const amount = Number(marketPriceForm.amount)
  const grams = Number(marketPriceForm.grams)
  if (Number.isNaN(amount) || amount < 0) {
    requestError.value = '价格必须是大于等于 0 的数字'
    return
  }
  if (Number.isNaN(grams) || grams <= 0) {
    requestError.value = '克数必须是大于 0 的数字'
    return
  }

  const marketPricePer500g = (amount / grams) * 500
  savingMarketPrice.value = true
  requestError.value = ''
  try {
    const result = await beadInventoryApi.batchUpdateMarketPrice({
      market_price_per_500g: Number(marketPricePer500g.toFixed(6))
    })
    const changed = result?.data?.changed ?? 0
    showMarketPriceModal.value = false
    await refreshAll()
    showFeedback('success', `市场价已批量更新（¥${amount.toFixed(2)} / ${grams}g），更新 ${changed} 条。`)
  } catch (error) {
    requestError.value = getErrorMessage(error, '设置全部市场价失败')
    showFeedback('error', requestError.value)
  } finally {
    savingMarketPrice.value = false
  }
}

onMounted(async () => {
  await refreshAll()
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
          <p class="page-hero__eyebrow">Inventory Control Deck</p>
          <h1 class="page-hero__title">豆仓管理</h1>
        </div>
        <div class="flex flex-wrap items-center gap-2">
          <button
            @click="openConversionModal"
            class="page-hero__action"
          >
            单位换算标准
          </button>
          <button
            @click="importMardPalette"
            :disabled="importingMard"
            class="page-hero__action"
          >
            {{ importingMard ? '导入中...' : '导入 Mard 221 色' }}
          </button>
          <button
            @click="setAllMarketPriceToDefault"
            :disabled="savingMarketPrice"
            class="page-hero__action"
          >
            {{ savingMarketPrice ? '设置中...' : '批量设置市场价' }}
          </button>
          <button
            @click="openSafeStockModal"
            :disabled="savingSafeStock"
            class="page-hero__action"
          >
            {{ savingSafeStock ? '更新中...' : '一键更新安全库存' }}
          </button>
          <button @click="openCreateMaterial" class="page-hero__action">
            新增豆料
          </button>
          <button @click="refreshAll" class="page-hero__action">
            刷新
          </button>
        </div>
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

    <section class="inventory-surface p-4 sm:p-5">
      <div class="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <article class="summary-card summary-card--neutral">
          <p class="summary-card__label">豆料总数</p>
          <p class="summary-card__value">{{ pagination.total }}</p>
          <p class="summary-card__meta">当前列表统计</p>
        </article>
        <article class="summary-card summary-card--warning">
          <p class="summary-card__label">低库存预警</p>
          <p class="summary-card__value">{{ lowStockCount }}</p>
          <p class="summary-card__meta">需优先补货</p>
        </article>
        <article class="summary-card summary-card--success">
          <p class="summary-card__label">当前总库存</p>
          <p class="summary-card__value">{{ formatGrams(totalCurrentGrams) }}</p>
          <p class="summary-card__meta">单位：克</p>
        </article>
        <article class="summary-card summary-card--value">
          <p class="summary-card__label">库存总价值</p>
          <p class="summary-card__value">{{ formatMoney(totalInventoryValue) }}</p>
          <p class="summary-card__meta">按市场价估算</p>
        </article>
      </div>
    </section>

    <section v-if="alerts.length" class="inventory-surface border-amber-200 bg-amber-50/80 p-4">
      <h2 class="text-sm font-semibold text-amber-900">低库存预警（{{ alerts.length }}）</h2>
      <div class="mt-2 alert-scroll">
        <button
          v-for="alert in alerts"
          :key="alert.id"
          type="button"
          @click="handleAlertClick(alert)"
          class="alert-row"
        >
          {{ alert.name }}：{{ formatGrams(alert.current_grams) }} / 安全库存 {{ formatGrams(alert.safe_stock) }}
        </button>
      </div>
    </section>

    <section class="inventory-surface p-5 sm:p-6">
      <div class="mb-3 flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
        <h2 class="text-lg font-semibold text-slate-900">豆料台账</h2>
        <div class="flex flex-wrap gap-2">
          <input
            v-model="filters.search"
            type="text"
            placeholder="搜索 ID/名称/颜色/规格"
            class="inventory-input"
          >
          <select v-model="filters.status" class="inventory-input">
            <option value="all">全部状态</option>
            <option value="active">启用</option>
            <option value="inactive">停用</option>
          </select>
          <button @click="fetchMaterials(1)" class="inventory-btn inventory-btn--ghost">筛选</button>
        </div>
      </div>

      <div class="overflow-x-auto">
        <table class="min-w-full text-sm">
          <thead>
            <tr class="border-b border-slate-200 text-left text-slate-500">
              <th class="px-3 py-2">ID</th>
              <th class="px-3 py-2">名称</th>
              <th class="px-3 py-2">常用</th>
              <th class="px-3 py-2">色卡</th>
              <th class="px-3 py-2">市场价</th>
              <th class="px-3 py-2">当前库存</th>
              <th class="px-3 py-2">安全库存</th>
              <th class="px-3 py-2">状态</th>
              <th class="px-3 py-2">操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-if="loading">
              <td colspan="9" class="px-3 py-6 text-center text-slate-500">加载中...</td>
            </tr>
            <tr v-else-if="materials.length === 0">
              <td colspan="9" class="px-3 py-6 text-center text-slate-500">暂无豆料</td>
            </tr>
            <tr
              v-for="item in materials"
              :key="item.id"
              @click="handleMaterialRowClick(item)"
              :class="[
                'border-b border-slate-100 cursor-pointer transition-colors',
                selectedMaterialId === item.id ? 'bg-sky-50' : 'hover:bg-slate-50'
              ]"
            >
              <td class="px-3 py-2">{{ item.id }}</td>
              <td class="px-3 py-2 font-medium text-slate-900">{{ item.name }}</td>
              <td class="px-3 py-2">
                <button
                  @click.stop="toggleCommonColor(item)"
                  :class="[
                    'rounded-full px-2 py-0.5 text-xs',
                    item.common_color
                      ? 'border border-amber-300 bg-amber-100 text-amber-800'
                      : 'border border-slate-300 bg-white text-slate-600 hover:bg-slate-50'
                  ]"
                >
                  {{ item.common_color ? '常用' : '设常用' }}
                </button>
              </td>
              <td class="px-3 py-2">
                <div class="flex items-center gap-2">
                  <span
                    class="h-7 w-10 rounded border border-slate-300 shadow-inner"
                    :style="{ background: normalizeHexColor(item.color_code) || '#f3f4f6' }"
                  ></span>
                  <div class="leading-tight">
                    <p class="text-xs font-semibold text-slate-700">{{ getMardCode(item.name) }}</p>
                    <p class="font-mono text-[11px] text-slate-500">{{ normalizeHexColor(item.color_code) || '-' }}</p>
                  </div>
                </div>
              </td>
              <td class="px-3 py-2 text-slate-700">{{ formatPricePer500g(item.market_price_per_500g) }}</td>
              <td class="px-3 py-2" :class="item.is_low_stock ? 'text-amber-700 font-semibold' : 'text-slate-700'">
                {{ formatGrams(item.current_grams) }}
              </td>
              <td class="px-3 py-2 text-slate-700">{{ formatGrams(item.safe_stock) }}</td>
              <td class="px-3 py-2">
                <span :class="item.status === 'active' ? 'text-emerald-700' : 'text-slate-500'">{{ item.status === 'active' ? '启用' : '停用' }}</span>
              </td>
              <td class="px-3 py-2">
                <div class="flex flex-wrap gap-1">
                  <button @click.stop="openEditMaterial(item)" class="inventory-btn inventory-btn--mini">编辑</button>
                  <button @click.stop="removeMaterial(item)" class="inventory-btn inventory-btn--mini-danger">删除</button>
                </div>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
      <div v-if="pagination.total > 0" class="mt-4 border-t border-slate-100 bg-gradient-to-r from-slate-50 to-white px-1 py-4">
        <div class="flex flex-col gap-3 xl:flex-row xl:items-center xl:justify-between">
          <p class="text-sm text-slate-600">
            显示 {{ (pagination.page - 1) * pagination.page_size + 1 }} 到 {{ Math.min(pagination.page * pagination.page_size, pagination.total) }} 条，共 {{ pagination.total }} 条记录
          </p>
          <div class="flex flex-col gap-3 sm:flex-row sm:items-center">
            <label class="flex items-center gap-2 text-sm text-slate-600">
              <span>每页</span>
              <select
                v-model.number="pagination.page_size"
                @change="handleMaterialPageSizeChange"
                class="h-9 min-w-[92px] rounded-lg border border-slate-200 bg-white px-3 text-sm text-slate-700 focus:outline-none focus:ring-2 focus:ring-blue-500"
              >
                <option v-for="size in pageSizeOptions" :key="size" :value="size">{{ size }}条</option>
              </select>
            </label>
            <div class="flex items-center gap-1">
              <button
                @click="handleMaterialPageChange(pagination.page - 1)"
                :disabled="pagination.page === 1 || loading"
                class="h-9 rounded-lg border border-slate-200 bg-white px-3 text-sm font-medium text-slate-700 transition hover:bg-slate-100 disabled:cursor-not-allowed disabled:opacity-45"
              >
                上一页
              </button>
              <template v-for="(page, index) in materialVisiblePages" :key="`material-page-${page}-${index}`">
                <span v-if="page === '...'" class="w-9 select-none text-center text-sm text-slate-400">...</span>
                <button
                  v-else
                  @click="handleMaterialPageChange(page)"
                  :class="[
                    'h-9 min-w-[2.25rem] rounded-lg border px-2 text-sm font-medium transition',
                    pagination.page === page
                      ? 'border-blue-600 bg-blue-600 text-white shadow-sm shadow-blue-100'
                      : 'border-slate-200 bg-white text-slate-700 hover:bg-slate-100'
                  ]"
                >
                  {{ page }}
                </button>
              </template>
              <button
                @click="handleMaterialPageChange(pagination.page + 1)"
                :disabled="pagination.page === materialTotalPages || loading"
                class="h-9 rounded-lg border border-slate-200 bg-white px-3 text-sm font-medium text-slate-700 transition hover:bg-slate-100 disabled:cursor-not-allowed disabled:opacity-45"
              >
                下一页
              </button>
            </div>
          </div>
        </div>
      </div>
    </section>

    <section class="grid grid-cols-1 gap-4 xl:grid-cols-3">
      <article class="inventory-operation-card border-emerald-200">
        <h3 class="text-base font-semibold text-slate-900">补货入库</h3>
        <p class="mt-1 text-xs text-slate-500">当前豆料：{{ selectedMaterialHint }}</p>
        <div class="mt-3 space-y-2">
          <input v-model="inboundForm.quantity" type="number" min="0" step="0.001" placeholder="数量" class="inventory-input w-full">
          <select v-model="inboundForm.quantity_unit" class="inventory-input w-full">
            <option value="gram">克</option>
            <option value="bag">袋</option>
            <option value="bottle">瓶</option>
          </select>
          <input v-model="inboundForm.source" type="text" placeholder="来源（可选）" class="inventory-input w-full">
          <textarea v-model="inboundForm.note" rows="2" placeholder="备注（可选）" class="inventory-input w-full"></textarea>
          <button @click="submitInbound" :disabled="submittingInbound" class="inventory-btn inventory-btn--success w-full">
            {{ submittingInbound ? '提交中...' : '确认补货' }}
          </button>
        </div>
      </article>

      <article class="inventory-operation-card border-orange-200">
        <h3 class="text-base font-semibold text-slate-900">损耗出库</h3>
        <p class="mt-1 text-xs text-slate-500">当前豆料：{{ selectedMaterialHint }}</p>
        <div class="mt-3 space-y-2">
          <input v-model="outboundForm.quantity" type="number" min="0" step="0.001" placeholder="数量" class="inventory-input w-full">
          <select v-model="outboundForm.quantity_unit" class="inventory-input w-full">
            <option value="gram">克</option>
            <option value="bag">袋</option>
            <option value="bottle">瓶</option>
          </select>
          <input v-model="outboundForm.source" type="text" placeholder="来源（可选）" class="inventory-input w-full">
          <textarea v-model="outboundForm.note" rows="2" placeholder="备注（可选）" class="inventory-input w-full"></textarea>
          <button @click="submitOutbound" :disabled="submittingOutbound" class="inventory-btn inventory-btn--warning w-full">
            {{ submittingOutbound ? '提交中...' : '确认损耗' }}
          </button>
        </div>
      </article>

      <article class="inventory-operation-card border-violet-200">
        <h3 class="text-base font-semibold text-slate-900">库存盘点（单人确认）</h3>
        <p class="mt-1 text-xs text-slate-500">当前豆料：{{ selectedMaterialHint }}</p>
        <div class="mt-3 space-y-2">
          <input v-model="stocktakeForm.counted_quantity" type="number" min="0" step="0.001" placeholder="实盘数量" class="inventory-input w-full">
          <select v-model="stocktakeForm.counted_unit" class="inventory-input w-full">
            <option value="gram">克</option>
            <option value="bag">袋</option>
            <option value="bottle">瓶</option>
          </select>
          <textarea v-model="stocktakeForm.note" rows="2" placeholder="盘点备注（可选）" class="inventory-input w-full"></textarea>
          <button @click="submitStocktake" :disabled="submittingStocktake" class="inventory-btn inventory-btn--violet w-full">
            {{ submittingStocktake ? '提交中...' : '确认盘点' }}
          </button>
        </div>
      </article>
    </section>

    <section class="inventory-surface p-5 sm:p-6">
      <div class="mb-3 flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
        <h2 class="text-lg font-semibold text-slate-900">库存流水</h2>
        <div class="flex flex-wrap gap-2">
          <select v-model="ledgerFilters.material_id" class="inventory-input">
            <option value="">全部豆料</option>
            <option v-for="item in materials" :key="item.id" :value="item.id">{{ item.name }}（{{ item.id }}）</option>
          </select>
          <select v-model="ledgerFilters.action_type" class="inventory-input">
            <option value="">全部类型</option>
            <option value="inbound">入库</option>
            <option value="outbound">出库</option>
            <option value="loss">损耗</option>
            <option value="stocktake_adjust">盘点调整</option>
          </select>
          <button @click="fetchLedger(1)" class="inventory-btn inventory-btn--ghost">查询</button>
        </div>
      </div>
      <div class="overflow-x-auto">
        <table class="min-w-full text-sm">
          <thead>
            <tr class="border-b border-slate-200 text-left text-slate-500">
              <th class="px-3 py-2">时间</th>
              <th class="px-3 py-2">豆料</th>
              <th class="px-3 py-2">类型</th>
              <th class="px-3 py-2">变化</th>
              <th class="px-3 py-2">结余</th>
              <th class="px-3 py-2">单号</th>
              <th class="px-3 py-2">操作人</th>
            </tr>
          </thead>
          <tbody>
            <tr v-if="loadingLedger">
              <td colspan="7" class="px-3 py-6 text-center text-slate-500">加载中...</td>
            </tr>
            <tr v-else-if="ledgerItems.length === 0">
              <td colspan="7" class="px-3 py-6 text-center text-slate-500">暂无流水</td>
            </tr>
            <tr v-for="item in ledgerItems" :key="item.id" class="border-b border-slate-100">
              <td class="px-3 py-2">{{ formatDateTime(item.created_at) }}</td>
              <td class="px-3 py-2">{{ item.material_id }}</td>
              <td class="px-3 py-2">{{ getLedgerActionTypeLabel(item.action_type) }}</td>
              <td class="px-3 py-2" :class="Number(item.delta_grams) >= 0 ? 'text-emerald-700' : 'text-rose-700'">
                {{ Number(item.delta_grams) >= 0 ? '+' : '' }}{{ formatGrams(item.delta_grams) }}
              </td>
              <td class="px-3 py-2">{{ formatGrams(item.balance_after_grams) }}</td>
              <td class="px-3 py-2">{{ item.reference_no || '-' }}</td>
              <td class="px-3 py-2">{{ item.operator || '-' }}</td>
            </tr>
          </tbody>
        </table>
      </div>
      <div v-if="ledgerPagination.total > 0" class="mt-4 border-t border-slate-100 bg-gradient-to-r from-slate-50 to-white px-1 py-4">
        <div class="flex flex-col gap-3 xl:flex-row xl:items-center xl:justify-between">
          <p class="text-sm text-slate-600">
            显示 {{ (ledgerPagination.page - 1) * ledgerPagination.page_size + 1 }} 到 {{ Math.min(ledgerPagination.page * ledgerPagination.page_size, ledgerPagination.total) }} 条，共 {{ ledgerPagination.total }} 条记录
          </p>
          <div class="flex flex-col gap-3 sm:flex-row sm:items-center">
            <label class="flex items-center gap-2 text-sm text-slate-600">
              <span>每页</span>
              <select
                v-model.number="ledgerPagination.page_size"
                @change="handleLedgerPageSizeChange"
                class="h-9 min-w-[92px] rounded-lg border border-slate-200 bg-white px-3 text-sm text-slate-700 focus:outline-none focus:ring-2 focus:ring-blue-500"
              >
                <option v-for="size in pageSizeOptions" :key="size" :value="size">{{ size }}条</option>
              </select>
            </label>
            <div class="flex items-center gap-1">
              <button
                @click="handleLedgerPageChange(ledgerPagination.page - 1)"
                :disabled="ledgerPagination.page === 1 || loadingLedger"
                class="h-9 rounded-lg border border-slate-200 bg-white px-3 text-sm font-medium text-slate-700 transition hover:bg-slate-100 disabled:cursor-not-allowed disabled:opacity-45"
              >
                上一页
              </button>
              <template v-for="(page, index) in ledgerVisiblePages" :key="`ledger-page-${page}-${index}`">
                <span v-if="page === '...'" class="w-9 select-none text-center text-sm text-slate-400">...</span>
                <button
                  v-else
                  @click="handleLedgerPageChange(page)"
                  :class="[
                    'h-9 min-w-[2.25rem] rounded-lg border px-2 text-sm font-medium transition',
                    ledgerPagination.page === page
                      ? 'border-blue-600 bg-blue-600 text-white shadow-sm shadow-blue-100'
                      : 'border-slate-200 bg-white text-slate-700 hover:bg-slate-100'
                  ]"
                >
                  {{ page }}
                </button>
              </template>
              <button
                @click="handleLedgerPageChange(ledgerPagination.page + 1)"
                :disabled="ledgerPagination.page === ledgerTotalPages || loadingLedger"
                class="h-9 rounded-lg border border-slate-200 bg-white px-3 text-sm font-medium text-slate-700 transition hover:bg-slate-100 disabled:cursor-not-allowed disabled:opacity-45"
              >
                下一页
              </button>
            </div>
          </div>
        </div>
      </div>
    </section>

    <Teleport to="body">
      <div v-if="showMaterialModal" class="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/55 px-4">
        <div class="w-full max-w-xl rounded-2xl bg-white shadow-2xl">
          <div class="flex items-center justify-between border-b border-slate-200 px-6 py-4">
            <h3 class="text-lg font-semibold text-slate-900">{{ isEditingMaterial ? '编辑豆料' : '新增豆料' }}</h3>
            <button @click="showMaterialModal = false" class="text-slate-400 hover:text-slate-600">✕</button>
          </div>
          <div class="grid grid-cols-1 gap-3 px-6 py-4 sm:grid-cols-2">
            <label class="space-y-1 text-sm text-slate-700">
              <span class="block font-medium">豆料名称 *</span>
              <input v-model="materialForm.name" type="text" placeholder="例如：M15" class="inventory-input w-full">
            </label>
            <label class="space-y-1 text-sm text-slate-700">
              <span class="block font-medium">颜色编码</span>
              <input v-model="materialForm.color_code" type="text" placeholder="例如：#747d7a" class="inventory-input w-full">
            </label>
            <label class="space-y-1 text-sm text-slate-700">
              <span class="block font-medium">规格</span>
              <input v-model="materialForm.spec" type="text" placeholder="例如：2.6mm" class="inventory-input w-full">
            </label>
            <label class="space-y-1 text-sm text-slate-700">
              <span class="block font-medium">品牌</span>
              <input v-model="materialForm.brand" type="text" placeholder="例如：Mard" class="inventory-input w-full">
            </label>
            <label class="space-y-1 text-sm text-slate-700">
              <span class="block font-medium">每袋克重（g）</span>
              <input v-model="materialForm.grams_per_bag" type="number" min="0" step="0.001" placeholder="可留空" class="inventory-input w-full">
            </label>
            <label class="space-y-1 text-sm text-slate-700">
              <span class="block font-medium">每瓶克重（g）</span>
              <input v-model="materialForm.grams_per_bottle" type="number" min="0" step="0.001" placeholder="可留空" class="inventory-input w-full">
            </label>
            <label class="space-y-1 text-sm text-slate-700">
              <span class="block font-medium">市场价（元 / 500g）</span>
              <input v-model="materialForm.market_price_per_500g" type="number" min="0" step="0.01" placeholder="例如：50" class="inventory-input w-full">
            </label>
            <label class="space-y-1 text-sm text-slate-700">
              <span class="block font-medium">安全库存（g）</span>
              <input v-model="materialForm.safe_stock" type="number" min="0" step="0.001" placeholder="例如：200" class="inventory-input w-full">
            </label>
            <label class="space-y-1 text-sm text-slate-700 sm:col-span-2">
              <span class="block font-medium">状态</span>
              <select v-model="materialForm.status" class="inventory-input w-full">
                <option value="active">启用</option>
                <option value="inactive">停用</option>
              </select>
            </label>
            <label class="col-span-1 inline-flex items-center gap-2 rounded-lg border border-slate-300 px-3 py-2 text-sm text-slate-700 sm:col-span-2">
              <input v-model="materialForm.common_color" type="checkbox">
              <span>设为常用色（列表优先）</span>
            </label>
          </div>
          <div class="flex justify-end gap-2 border-t border-slate-200 px-6 py-4">
            <button @click="showMaterialModal = false" class="inventory-btn inventory-btn--ghost">
              取消
            </button>
            <button @click="submitMaterial" :disabled="savingMaterial" class="inventory-btn inventory-btn--primary">
              {{ savingMaterial ? '保存中...' : '保存' }}
            </button>
          </div>
        </div>
      </div>

      <div v-if="showConversionModal" class="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/55 px-4">
        <div class="w-full max-w-md rounded-2xl bg-white shadow-2xl">
          <div class="flex items-center justify-between border-b border-slate-200 px-6 py-4">
            <h3 class="text-lg font-semibold text-slate-900">单位换算标准</h3>
            <button @click="showConversionModal = false" class="text-slate-400 hover:text-slate-600">✕</button>
          </div>
          <div class="space-y-3 px-6 py-4">
            <p class="text-sm text-slate-600">
              该设置将应用到<span class="font-medium text-slate-900">全部豆料</span>。
            </p>
            <input
              v-model="conversionForm.grams_per_bag"
              type="number"
              min="0"
              step="0.001"
              placeholder="每袋克重（可空）"
              class="inventory-input w-full"
            >
            <input
              v-model="conversionForm.grams_per_bottle"
              type="number"
              min="0"
              step="0.001"
              placeholder="每瓶克重（可空）"
              class="inventory-input w-full"
            >
            <p class="text-xs text-slate-500">保存后会统一覆盖全部豆料的换算标准；补货/损耗选择“袋”或“瓶”将按该标准换算成克。</p>
          </div>
          <div class="flex justify-end gap-2 border-t border-slate-200 px-6 py-4">
            <button @click="showConversionModal = false" class="inventory-btn inventory-btn--ghost">
              取消
            </button>
            <button @click="submitConversionStandard" :disabled="savingConversion" class="inventory-btn inventory-btn--violet">
              {{ savingConversion ? '保存中...' : '保存标准' }}
            </button>
          </div>
        </div>
      </div>

      <div v-if="showMarketPriceModal" class="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/55 px-4">
        <div class="w-full max-w-md rounded-2xl bg-white shadow-2xl">
          <div class="flex items-center justify-between border-b border-slate-200 px-6 py-4">
            <h3 class="text-lg font-semibold text-slate-900">批量设置市场价</h3>
            <button @click="showMarketPriceModal = false" class="text-slate-400 hover:text-slate-600">✕</button>
          </div>
          <div class="space-y-3 px-6 py-4">
            <p class="text-sm text-slate-600">
              输入任意“金额 + 克数”，系统会自动换算并应用到<span class="font-medium text-slate-900">全部豆料</span>。
            </p>
            <label class="space-y-1 text-sm text-slate-700">
              <span class="block font-medium">价格（元）</span>
              <input
                v-model="marketPriceForm.amount"
                type="number"
                min="0"
                step="0.01"
                placeholder="例如：50"
                class="inventory-input w-full"
              >
            </label>
            <label class="space-y-1 text-sm text-slate-700">
              <span class="block font-medium">对应克数（g）</span>
              <input
                v-model="marketPriceForm.grams"
                type="number"
                min="0.001"
                step="0.001"
                placeholder="例如：500"
                class="inventory-input w-full"
              >
            </label>
            <p class="text-xs text-slate-500">
              参考换算：当前等于 ¥{{ ((Number(marketPriceForm.amount || 0) / Number(marketPriceForm.grams || 1)) * 500).toFixed(2) }} / 500g
            </p>
          </div>
          <div class="flex justify-end gap-2 border-t border-slate-200 px-6 py-4">
            <button @click="showMarketPriceModal = false" class="inventory-btn inventory-btn--ghost">
              取消
            </button>
            <button @click="submitMarketPrice" :disabled="savingMarketPrice" class="inventory-btn inventory-btn--cyan">
              {{ savingMarketPrice ? '保存中...' : '应用到全部' }}
            </button>
          </div>
        </div>
      </div>

      <div v-if="showSafeStockModal" class="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/55 px-4">
        <div class="w-full max-w-md rounded-2xl bg-white shadow-2xl">
          <div class="flex items-center justify-between border-b border-slate-200 px-6 py-4">
            <h3 class="text-lg font-semibold text-slate-900">一键更新安全库存</h3>
            <button @click="showSafeStockModal = false" class="text-slate-400 hover:text-slate-600">✕</button>
          </div>
          <div class="space-y-3 px-6 py-4">
            <p class="text-sm text-slate-600">按“常用色/非常用色”分类批量覆盖全部豆料的安全库存。</p>
            <label class="space-y-1 text-sm text-slate-700">
              <span class="block font-medium">常用色安全库存（g）</span>
              <input
                v-model="safeStockBatchForm.common_safe_stock"
                type="number"
                min="0"
                step="0.001"
                placeholder="例如：300"
                class="inventory-input w-full"
              >
            </label>
            <label class="space-y-1 text-sm text-slate-700">
              <span class="block font-medium">非常用色安全库存（g）</span>
              <input
                v-model="safeStockBatchForm.normal_safe_stock"
                type="number"
                min="0"
                step="0.001"
                placeholder="例如：100"
                class="inventory-input w-full"
              >
            </label>
            <p class="text-xs text-slate-500">保存后将按当前“常用色”标签分组覆盖安全库存。</p>
          </div>
          <div class="flex justify-end gap-2 border-t border-slate-200 px-6 py-4">
            <button @click="showSafeStockModal = false" class="inventory-btn inventory-btn--ghost">
              取消
            </button>
            <button @click="submitSafeStockBatch" :disabled="savingSafeStock" class="inventory-btn inventory-btn--primary">
              {{ savingSafeStock ? '更新中...' : '立即更新' }}
            </button>
          </div>
        </div>
      </div>
    </Teleport>
  </div>
</template>

<style scoped>
.inventory-surface {
  border-radius: 1.5rem;
  border: 1px solid #dbe3ef;
  background: linear-gradient(180deg, #ffffff 0%, #f8fbff 100%);
  box-shadow: 0 12px 30px -24px rgba(15, 23, 42, 0.44);
}

.summary-card {
  border-radius: 0.95rem;
  border: 1px solid #dbe3ef;
  padding: 0.95rem 1rem;
  position: relative;
  overflow: hidden;
}

.summary-card::after {
  content: '';
  position: absolute;
  right: -22px;
  top: -22px;
  width: 72px;
  height: 72px;
  border-radius: 9999px;
  opacity: 0.38;
}

.summary-card--neutral {
  background: linear-gradient(145deg, #f8fafc, #ffffff 70%);
}

.summary-card--neutral::after {
  background: #cbd5e1;
}

.summary-card--warning {
  border-color: #fcd34d;
  background: linear-gradient(145deg, #fffbeb, #ffffff 70%);
}

.summary-card--warning::after {
  background: #fcd34d;
}

.summary-card--success {
  border-color: #86efac;
  background: linear-gradient(145deg, #f0fdf4, #ffffff 70%);
}

.summary-card--success::after {
  background: #86efac;
}

.summary-card--value {
  border-color: #a5b4fc;
  background: linear-gradient(145deg, #eef2ff, #ffffff 70%);
}

.summary-card--value::after {
  background: #a5b4fc;
}

.summary-card__label {
  font-size: 0.76rem;
  color: #64748b;
}

.summary-card__value {
  margin-top: 0.28rem;
  font-size: 1.5rem;
  font-weight: 700;
  color: #0f172a;
}

.summary-card__meta {
  margin-top: 0.2rem;
  font-size: 0.72rem;
  color: #94a3b8;
}

.alert-scroll {
  max-height: calc((1.9rem * 3) + (0.45rem * 2));
  overflow-y: auto;
  padding-right: 0.35rem;
  display: flex;
  flex-wrap: wrap;
  gap: 0.45rem;
  align-content: flex-start;
}

.alert-row {
  display: inline-flex;
  max-width: 100%;
  align-items: center;
  text-align: left;
  border: 1px solid #fcd34d;
  background: #ffffff;
  border-radius: 9999px;
  padding: 0.28rem 0.72rem;
  font-size: 0.74rem;
  color: #92400e;
  line-height: 1.3;
  transition: background-color 160ms ease, border-color 160ms ease;
}

.alert-row:hover {
  background: #fffbeb;
  border-color: #f59e0b;
}

.inventory-input {
  border-radius: 0.65rem;
  border: 1px solid #cbd5e1;
  padding: 0.5rem 0.75rem;
  font-size: 0.875rem;
}

.inventory-input:focus {
  outline: none;
  border-color: #3b82f6;
  box-shadow: 0 0 0 2px rgba(59, 130, 246, 0.16);
}

.inventory-btn {
  border-radius: 0.65rem;
  padding: 0.5rem 0.85rem;
  font-size: 0.875rem;
  font-weight: 600;
  transition: all 180ms ease;
}

.inventory-btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.inventory-btn--ghost {
  border: 1px solid #cbd5e1;
  color: #334155;
  background: #ffffff;
}

.inventory-btn--ghost:hover:enabled {
  background: #f8fafc;
}

.inventory-btn--primary {
  color: #ffffff;
  background: #2563eb;
}

.inventory-btn--primary:hover:enabled {
  background: #1d4ed8;
}

.inventory-btn--success {
  color: #ffffff;
  background: #059669;
}

.inventory-btn--success:hover:enabled {
  background: #047857;
}

.inventory-btn--warning {
  color: #ffffff;
  background: #ea580c;
}

.inventory-btn--warning:hover:enabled {
  background: #c2410c;
}

.inventory-btn--violet {
  color: #ffffff;
  background: #7c3aed;
}

.inventory-btn--violet:hover:enabled {
  background: #6d28d9;
}

.inventory-btn--cyan {
  color: #ffffff;
  background: #0891b2;
}

.inventory-btn--cyan:hover:enabled {
  background: #0e7490;
}

.inventory-btn--mini {
  border: 1px solid #93c5fd;
  padding: 0.2rem 0.5rem;
  font-size: 0.76rem;
  color: #1d4ed8;
  background: #eff6ff;
}

.inventory-btn--mini-danger {
  border: 1px solid #fda4af;
  padding: 0.2rem 0.5rem;
  font-size: 0.76rem;
  color: #be123c;
  background: #fff1f2;
}

.inventory-operation-card {
  border-radius: 1rem;
  border-width: 1px;
  background: #ffffff;
  padding: 1rem;
  box-shadow: 0 12px 24px -22px rgba(15, 23, 42, 0.9);
}

.notice-enter-active,
.notice-leave-active {
  transition: all 180ms ease;
}

.notice-enter-from,
.notice-leave-to {
  opacity: 0;
  transform: translateY(-8px);
}
</style>
