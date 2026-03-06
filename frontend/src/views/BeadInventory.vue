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
const restockSuggestions = ref([])
const ledgerItems = ref([])
const selectedMaterialId = ref('')
const selectedMaterialIds = ref(new Set())
const selectedLedgerIds = ref(new Set())

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
  search: ''
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

const restockSummary = reactive({
  total_items: 0,
  critical_items: 0,
  high_items: 0,
  suggested_restock_grams: 0,
  estimated_restock_cost: 0
})
const loadingRestockSuggestions = ref(false)

const selectedMaterial = computed(() => {
  return materials.value.find(item => item.id === selectedMaterialId.value) || null
})

const totalCurrentGrams = computed(() => {
  return materials.value.reduce((sum, item) => sum + Number(item.current_grams || 0), 0)
})

const lowStockCount = computed(() => {
  return alerts.value.length
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
const selectedOperationHint = computed(() => {
  if (selectedMaterialIds.value.size > 0) {
    return `批量已选 ${selectedMaterialIds.value.size} 项`
  }
  return selectedMaterialHint.value
})

const isAllSelected = computed(() => {
  if (materials.value.length === 0) return false
  return materials.value.every(item => selectedMaterialIds.value.has(item.id))
})

const isIndeterminate = computed(() => {
  const selectedCount = materials.value.filter(item => selectedMaterialIds.value.has(item.id)).length
  return selectedCount > 0 && selectedCount < materials.value.length
})

const selectedCount = computed(() => selectedMaterialIds.value.size)
const isAllLedgerSelected = computed(() => {
  if (ledgerItems.value.length === 0) return false
  return ledgerItems.value.every(item => selectedLedgerIds.value.has(item.id))
})

const isLedgerIndeterminate = computed(() => {
  if (ledgerItems.value.length === 0) return false
  const selectedCountOnPage = ledgerItems.value.filter(item => selectedLedgerIds.value.has(item.id)).length
  return selectedCountOnPage > 0 && selectedCountOnPage < ledgerItems.value.length
})

const selectedLedgerCount = computed(() => selectedLedgerIds.value.size)

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

function formatDays(value) {
  const num = Number(value)
  if (!Number.isFinite(num) || num < 0) return '—'
  return `${num.toFixed(1)} 天`
}

function getLedgerActionTypeLabel(value) {
  const raw = String(value || '').trim()
  return ledgerActionTypeLabelMap[raw] || raw || '-'
}

function getLedgerActionTypeClass(value) {
  const raw = String(value || '').trim()
  if (raw === 'inbound') return 'ledger-action-badge--inbound'
  if (raw === 'outbound') return 'ledger-action-badge--outbound'
  if (raw === 'loss') return 'ledger-action-badge--loss'
  if (raw === 'stocktake_adjust') return 'ledger-action-badge--adjust'
  return 'ledger-action-badge--default'
}

function getRestockUrgencyLabel(value) {
  const raw = String(value || '').trim().toLowerCase()
  if (raw === 'critical') return '紧急'
  if (raw === 'high') return '较高'
  return '常规'
}

function getRestockUrgencyClass(value) {
  const raw = String(value || '').trim().toLowerCase()
  if (raw === 'critical') return 'restock-urgency restock-urgency--critical'
  if (raw === 'high') return 'restock-urgency restock-urgency--high'
  return 'restock-urgency restock-urgency--medium'
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
      name: filters.search.trim()
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

function resetRestockSummary() {
  restockSummary.total_items = 0
  restockSummary.critical_items = 0
  restockSummary.high_items = 0
  restockSummary.suggested_restock_grams = 0
  restockSummary.estimated_restock_cost = 0
}

async function fetchRestockSuggestions() {
  loadingRestockSuggestions.value = true
  try {
    const response = await beadInventoryApi.getRestockSuggestions({ limit: 20 })
    const payload = response?.data || {}
    const items = Array.isArray(payload.items) ? payload.items : []
    const summary = payload.summary || {}

    restockSuggestions.value = items
    restockSummary.total_items = Number(summary.total_items || items.length || 0)
    restockSummary.critical_items = Number(summary.critical_items || 0)
    restockSummary.high_items = Number(summary.high_items || 0)
    restockSummary.suggested_restock_grams = Number(summary.suggested_restock_grams || 0)
    restockSummary.estimated_restock_cost = Number(summary.estimated_restock_cost || 0)
  } catch (error) {
    console.error('Failed to fetch restock suggestions:', error)
    restockSuggestions.value = []
    resetRestockSummary()
  } finally {
    loadingRestockSuggestions.value = false
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
  await fetchRestockSuggestions()
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

function toggleSelectAll() {
  if (isAllSelected.value) {
    selectedMaterialIds.value.clear()
  } else {
    materials.value.forEach(item => {
      selectedMaterialIds.value.add(item.id)
    })
  }
  selectedMaterialIds.value = new Set(selectedMaterialIds.value)
}

function toggleSelectItem(item) {
  if (selectedMaterialIds.value.has(item.id)) {
    selectedMaterialIds.value.delete(item.id)
  } else {
    selectedMaterialIds.value.add(item.id)
  }
  selectedMaterialIds.value = new Set(selectedMaterialIds.value)
}

function clearSelection() {
  selectedMaterialIds.value = new Set()
}

function toggleSelectAllLedger() {
  if (isAllLedgerSelected.value) {
    ledgerItems.value.forEach(item => {
      if (!item?.id) return
      selectedLedgerIds.value.delete(item.id)
    })
  } else {
    ledgerItems.value.forEach(item => {
      if (!item?.id) return
      selectedLedgerIds.value.add(item.id)
    })
  }
  selectedLedgerIds.value = new Set(selectedLedgerIds.value)
}

function toggleSelectLedgerItem(item) {
  if (!item?.id) return
  if (selectedLedgerIds.value.has(item.id)) {
    selectedLedgerIds.value.delete(item.id)
  } else {
    selectedLedgerIds.value.add(item.id)
  }
  selectedLedgerIds.value = new Set(selectedLedgerIds.value)
}

function clearLedgerSelection() {
  selectedLedgerIds.value = new Set()
}

async function batchSetCommonColor(commonColor) {
  if (selectedMaterialIds.value.size === 0) {
    requestError.value = '请先选择要操作的豆料'
    return
  }
  const ids = Array.from(selectedMaterialIds.value)
  const action = commonColor ? '设为常用色' : '取消常用色'
  const ok = window.confirm(`确认将选中的 ${ids.length} 个豆料${action}吗？`)
  if (!ok) return

  requestError.value = ''
  let successCount = 0
  let failCount = 0
  for (const id of ids) {
    try {
      await beadInventoryApi.updateMaterial(id, { common_color: commonColor })
      successCount++
    } catch {
      failCount++
    }
  }
  clearSelection()
  await refreshAll()
  if (failCount === 0) {
    showFeedback('success', `已${action} ${successCount} 个豆料`)
  } else {
    showFeedback('error', `${action}完成：成功 ${successCount} 个，失败 ${failCount} 个`)
  }
}

async function batchDeleteMaterials() {
  if (selectedMaterialIds.value.size === 0) {
    requestError.value = '请先选择要删除的豆料'
    return
  }
  const ids = Array.from(selectedMaterialIds.value)
  const ok = window.confirm(`确认删除选中的 ${ids.length} 个豆料吗？此操作不可恢复！`)
  if (!ok) return

  requestError.value = ''
  let successCount = 0
  let failCount = 0
  for (const id of ids) {
    try {
      await beadInventoryApi.deleteMaterial(id)
      successCount++
    } catch {
      failCount++
    }
  }
  clearSelection()
  await refreshAll()
  if (failCount === 0) {
    showFeedback('success', `已删除 ${successCount} 个豆料`)
  } else {
    showFeedback('error', `删除完成：成功 ${successCount} 个，失败 ${failCount} 个`)
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

async function handleRestockSuggestionClick(item) {
  if (!item?.id) return
  selectedMaterialId.value = item.id
  ledgerFilters.material_id = item.id
  await fetchLedger(1)
}

async function submitInbound() {
  const quantity = Number(inboundForm.quantity)
  if (!Number.isFinite(quantity) || quantity <= 0) {
    requestError.value = '请输入大于 0 的入库数量'
    return
  }

  const targetIds = selectedMaterialIds.value.size > 0
    ? Array.from(selectedMaterialIds.value)
    : (selectedMaterial.value?.id ? [selectedMaterial.value.id] : [])

  if (targetIds.length === 0) {
    requestError.value = '请先选择豆料（可勾选批量）'
    return
  }

  submittingInbound.value = true
  requestError.value = ''
  try {
    let successCount = 0
    let failCount = 0
    let lastErrorMessage = ''

    for (const materialId of targetIds) {
      try {
        await beadInventoryApi.createInbound({
          material_id: materialId,
          quantity,
          quantity_unit: inboundForm.quantity_unit,
          source: inboundForm.source,
          note: inboundForm.note
        })
        successCount += 1
      } catch (error) {
        failCount += 1
        lastErrorMessage = getErrorMessage(error, '补货入库失败')
      }
    }

    inboundForm.quantity = ''
    inboundForm.source = ''
    inboundForm.note = ''
    clearSelection()
    await refreshAll()

    if (failCount === 0) {
      showFeedback('success', targetIds.length > 1 ? `批量补货成功，共 ${successCount} 个豆料。` : '补货入库成功。')
    } else if (successCount > 0) {
      showFeedback('error', `批量补货完成：成功 ${successCount} 个，失败 ${failCount} 个。`)
    } else {
      requestError.value = lastErrorMessage || '补货入库失败'
      showFeedback('error', requestError.value)
    }
  } catch (error) {
    requestError.value = getErrorMessage(error, '补货入库失败')
    showFeedback('error', requestError.value)
  } finally {
    submittingInbound.value = false
  }
}

async function submitOutbound() {
  const quantity = Number(outboundForm.quantity)
  if (!Number.isFinite(quantity) || quantity <= 0) {
    requestError.value = '请输入大于 0 的出库数量'
    return
  }

  const targetIds = selectedMaterialIds.value.size > 0
    ? Array.from(selectedMaterialIds.value)
    : (selectedMaterial.value?.id ? [selectedMaterial.value.id] : [])

  if (targetIds.length === 0) {
    requestError.value = '请先选择豆料（可勾选批量）'
    return
  }

  submittingOutbound.value = true
  requestError.value = ''
  try {
    let successCount = 0
    let failCount = 0
    let lastErrorMessage = ''

    for (const materialId of targetIds) {
      try {
        await beadInventoryApi.createOutbound({
          material_id: materialId,
          quantity,
          quantity_unit: outboundForm.quantity_unit,
          outbound_type: 'loss',
          usage_type: outboundForm.source || '损耗出库',
          note: outboundForm.note
        })
        successCount += 1
      } catch (error) {
        failCount += 1
        lastErrorMessage = getErrorMessage(error, '出库失败')
      }
    }

    outboundForm.quantity = ''
    outboundForm.source = ''
    outboundForm.note = ''
    clearSelection()
    await refreshAll()

    if (failCount === 0) {
      showFeedback('success', targetIds.length > 1 ? `批量出库成功，共 ${successCount} 个豆料。` : '损耗出库成功。')
    } else if (successCount > 0) {
      showFeedback('error', `批量出库完成：成功 ${successCount} 个，失败 ${failCount} 个。`)
    } else {
      requestError.value = lastErrorMessage || '出库失败'
      showFeedback('error', requestError.value)
    }
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

    <section class="inventory-surface inventory-surface--kpi p-4 sm:p-5">
      <div class="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <article class="summary-card summary-card--neutral">
          <div class="summary-card__head">
            <p class="summary-card__label">豆料总数</p>
            <span class="summary-card__icon" aria-hidden="true">
              <svg viewBox="0 0 24 24" fill="none">
                <path d="M4 7.75h16m-16 4.25h16m-16 4.25h10" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" />
              </svg>
            </span>
          </div>
          <p class="summary-card__value">{{ pagination.total }}</p>
          <div class="summary-card__foot">
            <p class="summary-card__meta">当前列表统计</p>
            <span class="summary-card__chip">台账</span>
          </div>
          <div class="summary-card__track" aria-hidden="true">
            <span class="summary-card__bar"></span>
          </div>
        </article>
        <article class="summary-card summary-card--warning">
          <div class="summary-card__head">
            <p class="summary-card__label">低库存预警</p>
            <span class="summary-card__icon" aria-hidden="true">
              <svg viewBox="0 0 24 24" fill="none">
                <path d="M12 4.5L20 19H4l8-14.5Z" stroke="currentColor" stroke-width="1.7" stroke-linejoin="round" />
                <path d="M12 9v5.25m0 2.75h.01" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" />
              </svg>
            </span>
          </div>
          <p class="summary-card__value">{{ lowStockCount }}</p>
          <div class="summary-card__foot">
            <p class="summary-card__meta">需优先补货</p>
            <span class="summary-card__chip">告警</span>
          </div>
          <div class="summary-card__track" aria-hidden="true">
            <span class="summary-card__bar"></span>
          </div>
        </article>
        <article class="summary-card summary-card--success">
          <div class="summary-card__head">
            <p class="summary-card__label">当前总库存</p>
            <span class="summary-card__icon" aria-hidden="true">
              <svg viewBox="0 0 24 24" fill="none">
                <path d="M4 7.5 12 4l8 3.5v9L12 20l-8-3.5v-9Z" stroke="currentColor" stroke-width="1.7" stroke-linejoin="round" />
                <path d="M12 4v16m8-12.5L12 11 4 7.5" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" />
              </svg>
            </span>
          </div>
          <p class="summary-card__value">{{ formatGrams(totalCurrentGrams) }}</p>
          <div class="summary-card__foot">
            <p class="summary-card__meta">单位：克</p>
            <span class="summary-card__chip">库存</span>
          </div>
          <div class="summary-card__track" aria-hidden="true">
            <span class="summary-card__bar"></span>
          </div>
        </article>
        <article class="summary-card summary-card--value">
          <div class="summary-card__head">
            <p class="summary-card__label">库存总价值</p>
            <span class="summary-card__icon" aria-hidden="true">
              <svg viewBox="0 0 24 24" fill="none">
                <path d="M6.25 7.25h11.5a2 2 0 0 1 2 2v5.5a2 2 0 0 1-2 2H6.25a2 2 0 0 1-2-2v-5.5a2 2 0 0 1 2-2Z" stroke="currentColor" stroke-width="1.7" />
                <path d="M9 12h6m-6 2.75h3.5" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" />
              </svg>
            </span>
          </div>
          <p class="summary-card__value">{{ formatMoney(totalInventoryValue) }}</p>
          <div class="summary-card__foot">
            <p class="summary-card__meta">按市场价估算</p>
            <span class="summary-card__chip">估值</span>
          </div>
          <div class="summary-card__track" aria-hidden="true">
            <span class="summary-card__bar"></span>
          </div>
        </article>
      </div>
    </section>

    <section v-if="alerts.length" class="inventory-surface inventory-surface--alert p-4">
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

    <section class="inventory-surface inventory-surface--materials p-5 sm:p-6">
      <div class="materials-toolbar mb-3 flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
        <h2 class="materials-title text-lg font-semibold text-slate-900">豆料台账</h2>
        <div class="materials-filters flex flex-wrap items-center gap-2">
          <input
            v-model="filters.search"
            type="text"
            @keyup.enter="fetchMaterials(1)"
            placeholder="按名称搜索"
            class="inventory-input materials-filter-input"
          >
          <button @click="fetchMaterials(1)" class="inventory-btn inventory-btn--ghost materials-filter-btn">筛选</button>
        </div>
      </div>

      <div v-if="selectedCount > 0" class="batch-actions-bar mb-3 flex flex-wrap items-center justify-between gap-3 rounded-xl border border-blue-200 bg-blue-50 px-4 py-2">
        <div class="flex items-center gap-2 text-sm text-blue-800">
          <span class="font-medium">已选择 {{ selectedCount }} 项</span>
          <button @click="clearSelection" class="text-blue-600 hover:text-blue-800 underline">取消选择</button>
        </div>
        <div class="flex flex-wrap gap-2">
          <button @click="batchSetCommonColor(true)" class="inventory-btn inventory-btn--mini inventory-btn--primary">设为常用色</button>
          <button @click="batchSetCommonColor(false)" class="inventory-btn inventory-btn--mini inventory-btn--ghost">取消常用色</button>
          <button @click="batchDeleteMaterials" class="inventory-btn inventory-btn--mini inventory-btn--danger">批量删除</button>
        </div>
      </div>

      <div class="materials-table-wrap overflow-x-auto">
        <table class="materials-table min-w-full text-sm">
          <thead>
            <tr class="materials-table-head border-b border-slate-200 text-left text-slate-500">
              <th class="px-3 py-2 w-10">
                <input
                  type="checkbox"
                  :checked="isAllSelected"
                  :indeterminate="isIndeterminate"
                  @change="toggleSelectAll"
                  class="materials-checkbox w-4 h-4 rounded border-slate-300 text-blue-600 focus:ring-blue-500"
                >
              </th>
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
              <td colspan="10" class="px-3 py-6 text-center text-slate-500">加载中...</td>
            </tr>
            <tr v-else-if="materials.length === 0">
              <td colspan="10" class="px-3 py-6 text-center text-slate-500">暂无豆料</td>
            </tr>
            <tr
              v-for="item in materials"
              :key="item.id"
              @click="handleMaterialRowClick(item)"
              :class="[
                'materials-row border-b border-slate-100 cursor-pointer transition-colors',
                selectedMaterialId === item.id ? 'materials-row--active' : '',
                selectedMaterialIds.has(item.id) ? 'materials-row--selected' : ''
              ]"
            >
              <td class="px-3 py-2" @click.stop>
                <input
                  type="checkbox"
                  :checked="selectedMaterialIds.has(item.id)"
                  @change="toggleSelectItem(item)"
                  class="materials-checkbox w-4 h-4 rounded border-slate-300 text-blue-600 focus:ring-blue-500"
                >
              </td>
              <td class="px-3 py-2">{{ item.id }}</td>
              <td class="px-3 py-2 font-medium text-slate-900">{{ item.name }}</td>
              <td class="px-3 py-2">
                <button
                  @click.stop="toggleCommonColor(item)"
                  :class="[
                    'materials-common-toggle rounded-full px-2 py-0.5 text-xs',
                    item.common_color ? 'materials-common-toggle--on' : 'materials-common-toggle--off'
                  ]"
                >
                  {{ item.common_color ? '常用' : '设常用' }}
                </button>
              </td>
              <td class="px-3 py-2">
                <div class="flex items-center gap-2">
                  <span
                    class="materials-color-chip h-7 w-10 rounded border border-slate-300 shadow-inner"
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
                <span :class="['materials-status', item.status === 'active' ? 'materials-status--active' : 'materials-status--inactive']">
                  {{ item.status === 'active' ? '启用' : '停用' }}
                </span>
              </td>
              <td class="px-3 py-2">
                <div class="flex flex-wrap gap-1">
                  <button @click.stop="openEditMaterial(item)" class="inventory-btn inventory-btn--mini materials-row-action">编辑</button>
                  <button @click.stop="removeMaterial(item)" class="inventory-btn inventory-btn--mini-danger materials-row-action">删除</button>
                </div>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
      <div v-if="pagination.total > 0" class="materials-pagination mt-4 border-t border-slate-100 bg-gradient-to-r from-slate-50 to-white px-1 py-4">
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
                class="materials-page-size h-9 min-w-[92px] rounded-lg border border-slate-200 bg-white px-3 text-sm text-slate-700 focus:outline-none focus:ring-2 focus:ring-blue-500"
              >
                <option v-for="size in pageSizeOptions" :key="size" :value="size">{{ size }}条</option>
              </select>
            </label>
            <div class="flex items-center gap-1">
              <button
                @click="handleMaterialPageChange(pagination.page - 1)"
                :disabled="pagination.page === 1 || loading"
                class="materials-page-btn h-9 rounded-lg border border-slate-200 bg-white px-3 text-sm font-medium text-slate-700 transition hover:bg-slate-100 disabled:cursor-not-allowed disabled:opacity-45"
              >
                上一页
              </button>
              <template v-for="(page, index) in materialVisiblePages" :key="`material-page-${page}-${index}`">
                <span v-if="page === '...'" class="materials-page-ellipsis w-9 select-none text-center text-sm text-slate-400">...</span>
                <button
                  v-else
                  @click="handleMaterialPageChange(page)"
                  :class="[
                    'materials-page-number h-9 min-w-[2.25rem] rounded-lg border px-2 text-sm font-medium transition',
                    pagination.page === page
                      ? 'materials-page-number--active'
                      : 'materials-page-number--idle'
                  ]"
                >
                  {{ page }}
                </button>
              </template>
              <button
                @click="handleMaterialPageChange(pagination.page + 1)"
                :disabled="pagination.page === materialTotalPages || loading"
                class="materials-page-btn h-9 rounded-lg border border-slate-200 bg-white px-3 text-sm font-medium text-slate-700 transition hover:bg-slate-100 disabled:cursor-not-allowed disabled:opacity-45"
              >
                下一页
              </button>
            </div>
          </div>
        </div>
      </div>
    </section>

    <section class="inventory-operations-grid grid grid-cols-1 gap-4 xl:grid-cols-3">
      <article class="inventory-operation-card inventory-operation-card--inbound">
        <h3 class="text-base font-semibold text-slate-900">补货入库</h3>
        <p class="mt-1 text-xs text-slate-500">当前豆料：{{ selectedOperationHint }}</p>
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

      <article class="inventory-operation-card inventory-operation-card--outbound">
        <h3 class="text-base font-semibold text-slate-900">损耗出库</h3>
        <p class="mt-1 text-xs text-slate-500">当前豆料：{{ selectedOperationHint }}</p>
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

      <article class="inventory-operation-card inventory-operation-card--stocktake">
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

    <section class="inventory-surface inventory-surface--ledger p-5 sm:p-6">
      <div class="ledger-toolbar mb-3 flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
        <h2 class="ledger-title text-lg font-semibold text-slate-900">库存流水</h2>
        <div class="ledger-filters flex flex-wrap gap-2">
          <select v-model="ledgerFilters.material_id" class="inventory-input ledger-filter-input">
            <option value="">全部豆料</option>
            <option v-for="item in materials" :key="item.id" :value="item.id">{{ item.name }}（{{ item.id }}）</option>
          </select>
          <select v-model="ledgerFilters.action_type" class="inventory-input ledger-filter-input">
            <option value="">全部类型</option>
            <option value="inbound">入库</option>
            <option value="outbound">出库</option>
            <option value="loss">损耗</option>
            <option value="stocktake_adjust">盘点调整</option>
          </select>
          <button @click="fetchLedger(1)" class="inventory-btn inventory-btn--ghost ledger-filter-btn">查询</button>
        </div>
      </div>
      <div v-if="selectedLedgerCount > 0" class="ledger-batch-actions mb-3 flex flex-wrap items-center justify-between gap-3 rounded-xl border border-amber-200 bg-amber-50 px-4 py-2">
        <div class="flex items-center gap-2 text-sm text-amber-900">
          <span class="font-medium">已选择 {{ selectedLedgerCount }} 条流水</span>
          <button @click="clearLedgerSelection" class="text-amber-700 hover:text-amber-900 underline">
            取消选择
          </button>
        </div>
        <p class="text-xs text-amber-700">支持跨页勾选，当前页可一键全选/取消</p>
      </div>
      <div class="ledger-table-wrap overflow-x-auto">
        <table class="ledger-table min-w-full text-sm">
          <thead>
            <tr class="ledger-table-head border-b border-slate-200 text-left text-slate-500">
              <th class="px-3 py-2 w-10">
                <input
                  type="checkbox"
                  :checked="isAllLedgerSelected"
                  :indeterminate="isLedgerIndeterminate"
                  @change="toggleSelectAllLedger"
                  class="materials-checkbox h-4 w-4 rounded border-slate-300 text-blue-600 focus:ring-blue-500"
                >
              </th>
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
              <td colspan="8" class="px-3 py-6 text-center text-slate-500">加载中...</td>
            </tr>
            <tr v-else-if="ledgerItems.length === 0">
              <td colspan="8" class="px-3 py-6 text-center text-slate-500">暂无流水</td>
            </tr>
            <tr
              v-for="item in ledgerItems"
              :key="item.id"
              :class="[
                'ledger-row border-b border-slate-100',
                selectedLedgerIds.has(item.id) ? 'ledger-row--selected' : ''
              ]"
            >
              <td class="px-3 py-2" @click.stop>
                <input
                  type="checkbox"
                  :checked="selectedLedgerIds.has(item.id)"
                  @change="toggleSelectLedgerItem(item)"
                  class="materials-checkbox h-4 w-4 rounded border-slate-300 text-blue-600 focus:ring-blue-500"
                >
              </td>
              <td class="px-3 py-2">{{ formatDateTime(item.created_at) }}</td>
              <td class="px-3 py-2">{{ item.material_id }}</td>
              <td class="px-3 py-2">
                <span :class="['ledger-action-badge', getLedgerActionTypeClass(item.action_type)]">
                  {{ getLedgerActionTypeLabel(item.action_type) }}
                </span>
              </td>
              <td class="px-3 py-2">
                <span :class="['ledger-delta', Number(item.delta_grams) >= 0 ? 'ledger-delta--in' : 'ledger-delta--out']">
                  {{ Number(item.delta_grams) >= 0 ? '+' : '' }}{{ formatGrams(item.delta_grams) }}
                </span>
              </td>
              <td class="px-3 py-2">{{ formatGrams(item.balance_after_grams) }}</td>
              <td class="px-3 py-2">{{ item.reference_no || '-' }}</td>
              <td class="px-3 py-2">{{ item.operator || '-' }}</td>
            </tr>
          </tbody>
        </table>
      </div>
      <div v-if="ledgerPagination.total > 0" class="ledger-pagination mt-4 border-t border-slate-100 bg-gradient-to-r from-slate-50 to-white px-1 py-4">
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
                class="ledger-page-size h-9 min-w-[92px] rounded-lg border border-slate-200 bg-white px-3 text-sm text-slate-700 focus:outline-none focus:ring-2 focus:ring-blue-500"
              >
                <option v-for="size in pageSizeOptions" :key="size" :value="size">{{ size }}条</option>
              </select>
            </label>
            <div class="flex items-center gap-1">
              <button
                @click="handleLedgerPageChange(ledgerPagination.page - 1)"
                :disabled="ledgerPagination.page === 1 || loadingLedger"
                class="ledger-page-btn h-9 rounded-lg border border-slate-200 bg-white px-3 text-sm font-medium text-slate-700 transition hover:bg-slate-100 disabled:cursor-not-allowed disabled:opacity-45"
              >
                上一页
              </button>
              <template v-for="(page, index) in ledgerVisiblePages" :key="`ledger-page-${page}-${index}`">
                <span v-if="page === '...'" class="ledger-page-ellipsis w-9 select-none text-center text-sm text-slate-400">...</span>
                <button
                  v-else
                  @click="handleLedgerPageChange(page)"
                  :class="[
                    'ledger-page-number h-9 min-w-[2.25rem] rounded-lg border px-2 text-sm font-medium transition',
                    ledgerPagination.page === page
                      ? 'ledger-page-number--active'
                      : 'ledger-page-number--idle'
                  ]"
                >
                  {{ page }}
                </button>
              </template>
              <button
                @click="handleLedgerPageChange(ledgerPagination.page + 1)"
                :disabled="ledgerPagination.page === ledgerTotalPages || loadingLedger"
                class="ledger-page-btn h-9 rounded-lg border border-slate-200 bg-white px-3 text-sm font-medium text-slate-700 transition hover:bg-slate-100 disabled:cursor-not-allowed disabled:opacity-45"
              >
                下一页
              </button>
            </div>
          </div>
        </div>
      </div>
    </section>

    <section class="inventory-surface inventory-surface--restock p-4 sm:p-5">
      <div class="restock-header flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
        <div>
          <h2 class="text-base font-semibold text-amber-950">低库存补货建议</h2>
          <p class="mt-1 text-xs text-amber-900/80">
            按安全库存 + 近 7 天消耗估算生成，建议优先处理紧急项。
          </p>
        </div>
        <div class="restock-summary flex flex-wrap gap-2 text-xs">
          <span class="restock-summary__pill">建议 {{ restockSummary.total_items }} 项</span>
          <span class="restock-summary__pill">紧急 {{ restockSummary.critical_items }} 项</span>
          <span class="restock-summary__pill">建议补货 {{ formatGrams(restockSummary.suggested_restock_grams) }}</span>
          <span class="restock-summary__pill">估算成本 {{ formatMoney(restockSummary.estimated_restock_cost) }}</span>
        </div>
      </div>

      <div v-if="loadingRestockSuggestions" class="mt-3 text-sm text-amber-900/80">
        正在生成补货建议...
      </div>
      <div v-else-if="restockSuggestions.length === 0" class="mt-3 text-sm text-amber-900/80">
        当前没有需要补货的低库存项。
      </div>
      <div v-else class="restock-table-wrap mt-3 overflow-x-auto">
        <table class="restock-table min-w-[980px] text-sm">
          <thead>
            <tr class="border-b border-amber-200 text-left text-amber-900/75">
              <th class="px-3 py-2">豆料</th>
              <th class="px-3 py-2">当前 / 安全</th>
              <th class="px-3 py-2">缺口</th>
              <th class="px-3 py-2">建议补货</th>
              <th class="px-3 py-2">推荐包装</th>
              <th class="px-3 py-2">可用天数</th>
              <th class="px-3 py-2">预计成本</th>
              <th class="px-3 py-2">优先级</th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="item in restockSuggestions"
              :key="item.id"
              @click="handleRestockSuggestionClick(item)"
              class="restock-row border-b border-amber-100/80 cursor-pointer"
            >
              <td class="px-3 py-2">
                <p class="font-semibold text-slate-900">{{ item.name }}</p>
                <p class="text-xs text-slate-500">{{ item.id }}</p>
              </td>
              <td class="px-3 py-2 text-slate-700">
                {{ formatGrams(item.current_grams) }} / {{ formatGrams(item.safe_stock) }}
              </td>
              <td class="px-3 py-2 font-semibold text-rose-700">{{ formatGrams(item.shortage_grams) }}</td>
              <td class="px-3 py-2 font-semibold text-emerald-700">{{ formatGrams(item.suggested_restock_grams) }}</td>
              <td class="px-3 py-2 text-slate-700">
                <div class="restock-package flex flex-col gap-0.5 leading-5">
                  <span v-if="item.recommended_bags !== null">{{ item.recommended_bags }} 袋</span>
                  <span v-if="item.recommended_bottles !== null">{{ item.recommended_bottles }} 瓶</span>
                  <span v-if="item.recommended_bags === null && item.recommended_bottles === null">按克采购</span>
                </div>
              </td>
              <td class="px-3 py-2 text-slate-700">
                {{ formatDays(item.estimated_days_left) }} → {{ formatDays(item.expected_days_after_restock) }}
              </td>
              <td class="px-3 py-2 text-slate-700">{{ formatMoney(item.estimated_restock_cost) }}</td>
              <td class="px-3 py-2">
                <span :class="getRestockUrgencyClass(item.urgency)">
                  {{ getRestockUrgencyLabel(item.urgency) }}
                </span>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>

    <Teleport to="body">
      <div v-if="showMaterialModal" class="inventory-modal-overlay fixed inset-0 z-50 flex items-center justify-center bg-slate-900/55 px-4">
        <div class="inventory-modal inventory-modal--wide w-full max-w-xl rounded-2xl bg-white shadow-2xl">
          <div class="inventory-modal__header flex items-center justify-between border-b border-slate-200 px-6 py-4">
            <h3 class="inventory-modal__title text-lg font-semibold text-slate-900">{{ isEditingMaterial ? '编辑豆料' : '新增豆料' }}</h3>
            <button @click="showMaterialModal = false" class="inventory-modal__close text-slate-400 hover:text-slate-600">✕</button>
          </div>
          <div class="inventory-modal__body grid grid-cols-1 gap-3 px-6 py-4 sm:grid-cols-2">
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
            <label class="inventory-modal__checkbox col-span-1 inline-flex items-center gap-2 rounded-lg border border-slate-300 px-3 py-2 text-sm text-slate-700 sm:col-span-2">
              <input v-model="materialForm.common_color" type="checkbox">
              <span>设为常用色（列表优先）</span>
            </label>
          </div>
          <div class="inventory-modal__footer flex justify-end gap-2 border-t border-slate-200 px-6 py-4">
            <button @click="showMaterialModal = false" class="inventory-btn inventory-btn--ghost">
              取消
            </button>
            <button @click="submitMaterial" :disabled="savingMaterial" class="inventory-btn inventory-btn--primary">
              {{ savingMaterial ? '保存中...' : '保存' }}
            </button>
          </div>
        </div>
      </div>

      <div v-if="showConversionModal" class="inventory-modal-overlay fixed inset-0 z-50 flex items-center justify-center bg-slate-900/55 px-4">
        <div class="inventory-modal inventory-modal--compact w-full max-w-md rounded-2xl bg-white shadow-2xl">
          <div class="inventory-modal__header flex items-center justify-between border-b border-slate-200 px-6 py-4">
            <h3 class="inventory-modal__title text-lg font-semibold text-slate-900">单位换算标准</h3>
            <button @click="showConversionModal = false" class="inventory-modal__close text-slate-400 hover:text-slate-600">✕</button>
          </div>
          <div class="inventory-modal__body space-y-3 px-6 py-4">
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
          <div class="inventory-modal__footer flex justify-end gap-2 border-t border-slate-200 px-6 py-4">
            <button @click="showConversionModal = false" class="inventory-btn inventory-btn--ghost">
              取消
            </button>
            <button @click="submitConversionStandard" :disabled="savingConversion" class="inventory-btn inventory-btn--violet">
              {{ savingConversion ? '保存中...' : '保存标准' }}
            </button>
          </div>
        </div>
      </div>

      <div v-if="showMarketPriceModal" class="inventory-modal-overlay fixed inset-0 z-50 flex items-center justify-center bg-slate-900/55 px-4">
        <div class="inventory-modal inventory-modal--compact w-full max-w-md rounded-2xl bg-white shadow-2xl">
          <div class="inventory-modal__header flex items-center justify-between border-b border-slate-200 px-6 py-4">
            <h3 class="inventory-modal__title text-lg font-semibold text-slate-900">批量设置市场价</h3>
            <button @click="showMarketPriceModal = false" class="inventory-modal__close text-slate-400 hover:text-slate-600">✕</button>
          </div>
          <div class="inventory-modal__body space-y-3 px-6 py-4">
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
          <div class="inventory-modal__footer flex justify-end gap-2 border-t border-slate-200 px-6 py-4">
            <button @click="showMarketPriceModal = false" class="inventory-btn inventory-btn--ghost">
              取消
            </button>
            <button @click="submitMarketPrice" :disabled="savingMarketPrice" class="inventory-btn inventory-btn--cyan">
              {{ savingMarketPrice ? '保存中...' : '应用到全部' }}
            </button>
          </div>
        </div>
      </div>

      <div v-if="showSafeStockModal" class="inventory-modal-overlay fixed inset-0 z-50 flex items-center justify-center bg-slate-900/55 px-4">
        <div class="inventory-modal inventory-modal--compact w-full max-w-md rounded-2xl bg-white shadow-2xl">
          <div class="inventory-modal__header flex items-center justify-between border-b border-slate-200 px-6 py-4">
            <h3 class="inventory-modal__title text-lg font-semibold text-slate-900">一键更新安全库存</h3>
            <button @click="showSafeStockModal = false" class="inventory-modal__close text-slate-400 hover:text-slate-600">✕</button>
          </div>
          <div class="inventory-modal__body space-y-3 px-6 py-4">
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
          <div class="inventory-modal__footer flex justify-end gap-2 border-t border-slate-200 px-6 py-4">
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

.inventory-surface--kpi {
  position: relative;
  overflow: hidden;
  border-color: #e6d2ba;
  background:
    radial-gradient(circle at 12% 18%, rgba(202, 138, 4, 0.14), transparent 44%),
    radial-gradient(circle at 88% 82%, rgba(185, 28, 28, 0.12), transparent 38%),
    linear-gradient(155deg, #fff8ef 0%, #fff9f1 34%, #ffffff 100%);
  box-shadow: 0 16px 34px -26px rgba(124, 45, 18, 0.5);
}

.inventory-surface--kpi::before {
  content: '';
  position: absolute;
  inset: 0;
  pointer-events: none;
  opacity: 0.45;
  background:
    linear-gradient(90deg, rgba(255, 255, 255, 0) 0%, rgba(255, 255, 255, 0.66) 50%, rgba(255, 255, 255, 0) 100%);
  transform: translateX(-110%);
  animation: kpi-sheen 7s linear infinite;
}

.summary-card {
  --kpi-accent: #b45309;
  --kpi-accent-soft: rgba(180, 83, 9, 0.18);
  --kpi-chip-bg: #fff4e5;
  --kpi-chip-text: #9a3412;
  --kpi-track-bg: rgba(180, 83, 9, 0.1);
  border-radius: 1rem;
  border: 1px solid #e9d8c5;
  padding: 0.95rem 1rem;
  position: relative;
  overflow: hidden;
  background: linear-gradient(160deg, rgba(255, 255, 255, 0.95) 0%, rgba(255, 250, 245, 0.92) 100%);
  box-shadow: 0 14px 26px -24px rgba(69, 10, 10, 0.72);
  transition: transform 220ms ease, box-shadow 220ms ease, border-color 220ms ease;
}

.summary-card:hover {
  transform: translateY(-3px);
  box-shadow: 0 20px 34px -24px rgba(69, 10, 10, 0.52);
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
  background: var(--kpi-accent-soft);
}

.summary-card::before {
  content: '';
  position: absolute;
  left: 0.8rem;
  right: 0.8rem;
  top: 0.6rem;
  height: 1px;
  background: linear-gradient(90deg, rgba(255, 255, 255, 0.9), rgba(255, 255, 255, 0));
}

.summary-card--neutral {
  --kpi-accent: #8b5e34;
  --kpi-accent-soft: rgba(139, 94, 52, 0.2);
  --kpi-chip-bg: #f8efe5;
  --kpi-chip-text: #7c4a20;
  --kpi-track-bg: rgba(139, 94, 52, 0.14);
  border-color: #e2d3c5;
  background: linear-gradient(145deg, #fff9f2, #ffffff 68%);
}

.summary-card--warning {
  --kpi-accent: #d97706;
  --kpi-accent-soft: rgba(245, 158, 11, 0.24);
  --kpi-chip-bg: #ffedd5;
  --kpi-chip-text: #9a3412;
  --kpi-track-bg: rgba(217, 119, 6, 0.16);
  border-color: #f0b77f;
  background: linear-gradient(145deg, #fff5e9, #ffffff 70%);
}

.summary-card--success {
  --kpi-accent: #059669;
  --kpi-accent-soft: rgba(16, 185, 129, 0.2);
  --kpi-chip-bg: #d1fae5;
  --kpi-chip-text: #065f46;
  --kpi-track-bg: rgba(5, 150, 105, 0.16);
  border-color: #b3d7c2;
  background: linear-gradient(145deg, #f3fbf7, #ffffff 70%);
}

.summary-card--value {
  --kpi-accent: #b45309;
  --kpi-accent-soft: rgba(202, 138, 4, 0.22);
  --kpi-chip-bg: #fef3c7;
  --kpi-chip-text: #92400e;
  --kpi-track-bg: rgba(180, 83, 9, 0.16);
  border-color: #d8bf99;
  background: linear-gradient(145deg, #fff4df, #ffffff 70%);
}

.summary-card__label {
  font-size: 0.76rem;
  color: #7c2d12;
  letter-spacing: 0.03em;
}

.summary-card__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.55rem;
}

.summary-card__icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 1.85rem;
  height: 1.85rem;
  border-radius: 0.65rem;
  border: 1px solid rgba(255, 255, 255, 0.6);
  color: var(--kpi-accent);
  background: rgba(255, 255, 255, 0.68);
  box-shadow: 0 8px 14px -12px rgba(69, 10, 10, 0.82);
}

.summary-card__icon svg {
  width: 1.1rem;
  height: 1.1rem;
}

.summary-card__value {
  margin-top: 0.42rem;
  font-size: clamp(1.36rem, 1.2rem + 0.4vw, 1.78rem);
  font-weight: 700;
  color: #450a0a;
  line-height: 1.15;
}

.summary-card__meta {
  font-size: 0.72rem;
  color: #a16207;
}

.summary-card__foot {
  margin-top: 0.32rem;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.6rem;
}

.summary-card__chip {
  display: inline-flex;
  align-items: center;
  border-radius: 9999px;
  padding: 0.12rem 0.5rem;
  font-size: 0.66rem;
  font-weight: 700;
  letter-spacing: 0.04em;
  color: var(--kpi-chip-text);
  background: var(--kpi-chip-bg);
  border: 1px solid color-mix(in oklab, var(--kpi-chip-bg), #8b5a2b 24%);
}

.summary-card__track {
  margin-top: 0.48rem;
  height: 0.33rem;
  border-radius: 9999px;
  background: var(--kpi-track-bg);
  overflow: hidden;
}

.summary-card__bar {
  position: relative;
  display: block;
  height: 100%;
  border-radius: inherit;
  background: linear-gradient(90deg, color-mix(in oklab, var(--kpi-accent), #fff 8%), color-mix(in oklab, var(--kpi-accent), #fff 24%));
}

.summary-card__bar::after {
  content: '';
  position: absolute;
  inset: 0;
  background: linear-gradient(90deg, rgba(255, 255, 255, 0) 0%, rgba(255, 255, 255, 0.65) 50%, rgba(255, 255, 255, 0) 100%);
  transform: translateX(-120%);
  animation: kpi-bar-sheen 3.8s linear infinite;
}

.summary-card--neutral .summary-card__bar {
  width: 56%;
}

.summary-card--warning .summary-card__bar {
  width: 34%;
}

.summary-card--warning .summary-card__icon {
  animation: kpi-warning-pulse 2.2s ease-in-out infinite;
}

.summary-card--success .summary-card__bar {
  width: 74%;
}

.summary-card--value .summary-card__bar {
  width: 63%;
}

.inventory-surface--alert {
  border-color: #f3c995;
  background:
    radial-gradient(circle at right top, rgba(217, 119, 6, 0.16), transparent 38%),
    linear-gradient(150deg, rgba(255, 251, 235, 0.95) 0%, rgba(255, 245, 230, 0.92) 100%);
  box-shadow: 0 12px 26px -22px rgba(180, 83, 9, 0.46);
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
  border: 1px solid #f2c27b;
  background: linear-gradient(130deg, #fff9f0, #ffffff);
  border-radius: 9999px;
  padding: 0.34rem 0.78rem;
  font-size: 0.74rem;
  color: #7c2d12;
  line-height: 1.3;
  box-shadow: 0 7px 18px -16px rgba(120, 53, 15, 0.75);
  transition: transform 180ms ease, background-color 180ms ease, border-color 180ms ease, box-shadow 180ms ease;
}

.alert-row:hover {
  transform: translateY(-1px);
  background: #fffbeb;
  border-color: #d97706;
  box-shadow: 0 10px 18px -14px rgba(120, 53, 15, 0.72);
}

.inventory-surface--restock {
  border-color: #efcf9d;
  background:
    radial-gradient(circle at 90% 8%, rgba(249, 115, 22, 0.14), transparent 36%),
    linear-gradient(155deg, #fff9f1 0%, #fffefc 100%);
  box-shadow: 0 14px 28px -22px rgba(154, 52, 18, 0.38);
}

.restock-summary__pill {
  display: inline-flex;
  align-items: center;
  border-radius: 9999px;
  border: 1px solid #f2c27b;
  background: linear-gradient(130deg, #fff8eb, #ffffff);
  color: #9a3412;
  padding: 0.22rem 0.6rem;
  font-weight: 600;
}

.restock-table-wrap {
  border: 1px solid #f0d9b8;
  border-radius: 0.9rem;
  background: rgba(255, 255, 255, 0.84);
}

.restock-table {
  border-collapse: separate;
  border-spacing: 0;
}

.restock-row {
  transition: background-color 180ms ease;
}

.restock-row:hover {
  background: #fff7ed;
}

.restock-urgency {
  display: inline-flex;
  align-items: center;
  border-radius: 9999px;
  border: 1px solid transparent;
  padding: 0.14rem 0.56rem;
  font-size: 0.72rem;
  font-weight: 700;
}

.restock-urgency--critical {
  color: #9f1239;
  border-color: #fecdd3;
  background: #fff1f2;
}

.restock-urgency--high {
  color: #9a3412;
  border-color: #fdba74;
  background: #fff7ed;
}

.restock-urgency--medium {
  color: #075985;
  border-color: #bae6fd;
  background: #f0f9ff;
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

.inventory-btn--danger {
  color: #ffffff;
  background: #dc2626;
  border-color: #dc2626;
}

.inventory-btn--danger:hover:enabled {
  background: #b91c1c;
}

.inventory-surface--materials {
  position: relative;
  overflow: hidden;
  border-color: #e8d7c5;
  background:
    radial-gradient(circle at 100% 0%, rgba(202, 138, 4, 0.1), transparent 36%),
    linear-gradient(180deg, #fffdf9 0%, #fff8ef 100%);
  box-shadow: 0 16px 30px -25px rgba(92, 45, 12, 0.38);
}

.inventory-surface--materials::before {
  content: '';
  position: absolute;
  inset: 0;
  pointer-events: none;
  background: linear-gradient(180deg, rgba(255, 255, 255, 0.62), rgba(255, 255, 255, 0));
}

.materials-toolbar {
  position: relative;
  z-index: 1;
}

.materials-title {
  color: #5b2b10;
  letter-spacing: 0.03em;
}

.materials-filters {
  position: relative;
  z-index: 1;
}

.materials-filter-input {
  border-color: #dfcdb9;
  background: rgba(255, 255, 255, 0.92);
}

.materials-filter-input:focus {
  border-color: #ca8a04;
  box-shadow: 0 0 0 2px rgba(202, 138, 4, 0.14);
}

.materials-filter-btn {
  border-color: #d7c1a9;
  color: #7c2d12;
  background: linear-gradient(180deg, #ffffff, #fff8ef);
}

.materials-filter-btn:hover:enabled {
  background: #fffbf5;
  border-color: #c9ad8f;
}

.materials-table-wrap {
  position: relative;
  z-index: 1;
  border-radius: 0.9rem;
  border: 1px solid #eadbc9;
  background: rgba(255, 255, 255, 0.86);
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.8);
}

.materials-table {
  border-collapse: separate;
  border-spacing: 0;
}

.materials-table-head th {
  position: sticky;
  top: 0;
  z-index: 1;
  color: #8b5a2b;
  font-weight: 600;
  letter-spacing: 0.02em;
  background: linear-gradient(180deg, #fff8ee 0%, #fff2e2 100%);
  border-bottom-color: #eadbc9;
}

.materials-row td {
  border-bottom: 1px solid #f4e8db;
}

.materials-row {
  transition: background-color 180ms ease, box-shadow 180ms ease;
}

.materials-row:hover {
  background: #fff7eb;
}

.materials-row--active {
  background: linear-gradient(90deg, rgba(251, 191, 36, 0.12), rgba(255, 247, 235, 0.95));
  box-shadow: inset 3px 0 0 #d97706;
}

.materials-row--selected {
  background: linear-gradient(90deg, rgba(59, 130, 246, 0.08), rgba(239, 246, 255, 0.95));
}

.materials-checkbox {
  cursor: pointer;
  accent-color: #2563eb;
}

.batch-actions-bar {
  animation: slide-down 200ms ease-out;
}

@keyframes slide-down {
  from {
    opacity: 0;
    transform: translateY(-8px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

.materials-common-toggle {
  transition: all 160ms ease;
}

.materials-common-toggle--on {
  border: 1px solid #f2be78;
  color: #9a3412;
  background: linear-gradient(180deg, #fff4e5, #ffe9cc);
}

.materials-common-toggle--off {
  border: 1px solid #d9c8b7;
  color: #6b7280;
  background: #fff;
}

.materials-common-toggle--off:hover {
  background: #fff8ef;
  border-color: #d5b89b;
}

.materials-color-chip {
  border-color: #d6c3ae;
  box-shadow: inset 0 0 0 1px rgba(255, 255, 255, 0.62), 0 5px 10px -8px rgba(120, 53, 15, 0.56);
}

.materials-status {
  display: inline-flex;
  align-items: center;
  border-radius: 9999px;
  padding: 0.1rem 0.55rem;
  font-size: 0.72rem;
  font-weight: 600;
  border: 1px solid transparent;
}

.materials-status--active {
  color: #065f46;
  border-color: #99f6e4;
  background: #ecfdf5;
}

.materials-status--inactive {
  color: #6b7280;
  border-color: #d1d5db;
  background: #f9fafb;
}

.materials-row-action {
  box-shadow: 0 6px 12px -10px rgba(92, 45, 12, 0.65);
}

.materials-pagination {
  position: relative;
  z-index: 1;
  border-top-color: #eadbc9;
  background: linear-gradient(180deg, #fffaf2, #fff);
}

.materials-page-size {
  border-color: #dfcdb9;
  color: #7c2d12;
}

.materials-page-size:focus {
  border-color: #ca8a04;
  box-shadow: 0 0 0 2px rgba(202, 138, 4, 0.16);
}

.materials-page-btn {
  border-color: #dfcdb9;
  color: #7c2d12;
  background: #fff;
}

.materials-page-btn:hover:enabled {
  border-color: #cda886;
  background: #fff8ef;
}

.materials-page-ellipsis {
  color: #b38a61;
}

.materials-page-number {
  border-color: #dfcdb9;
}

.materials-page-number--idle {
  color: #7c2d12;
  background: #fff;
}

.materials-page-number--idle:hover {
  border-color: #cda886;
  background: #fff8ef;
}

.materials-page-number--active {
  border-color: #b45309;
  color: #fff;
  background: linear-gradient(180deg, #c2410c, #9a3412);
  box-shadow: 0 8px 16px -10px rgba(124, 45, 18, 0.7);
}

.inventory-operations-grid {
  align-items: stretch;
}

.inventory-operation-card {
  position: relative;
  overflow: hidden;
  border-radius: 1.05rem;
  border: 1px solid #e6d2ba;
  background:
    radial-gradient(circle at 90% 0%, rgba(255, 255, 255, 0.6), transparent 46%),
    linear-gradient(165deg, rgba(255, 255, 255, 0.96) 0%, rgba(255, 248, 239, 0.96) 100%);
  padding: 1rem;
  box-shadow: 0 16px 30px -26px rgba(69, 10, 10, 0.76);
  transition: transform 220ms ease, box-shadow 220ms ease, border-color 220ms ease;
}

.inventory-operation-card::before {
  content: '';
  position: absolute;
  left: 1rem;
  right: 1rem;
  top: 0;
  height: 3px;
  border-radius: 9999px;
}

.inventory-operation-card:hover {
  transform: translateY(-3px);
  box-shadow: 0 24px 34px -26px rgba(69, 10, 10, 0.62);
}

.inventory-operation-card--inbound {
  border-color: #98c7a7;
}

.inventory-operation-card--inbound::before {
  background: linear-gradient(90deg, #047857, #10b981);
}

.inventory-operation-card--outbound {
  border-color: #f3b689;
}

.inventory-operation-card--outbound::before {
  background: linear-gradient(90deg, #b45309, #f97316);
}

.inventory-operation-card--stocktake {
  border-color: #d9c59f;
}

.inventory-operation-card--stocktake::before {
  background: linear-gradient(90deg, #92400e, #ca8a04);
}

.inventory-operation-card .inventory-input {
  border-color: #e2d3bf;
  background: rgba(255, 255, 255, 0.9);
}

.inventory-operation-card .inventory-input:focus {
  border-color: #ca8a04;
  box-shadow: 0 0 0 2px rgba(202, 138, 4, 0.18);
}

.inventory-operation-card .inventory-btn {
  box-shadow: 0 11px 18px -14px rgba(69, 10, 10, 0.7);
}

.inventory-operation-card .inventory-btn:hover:enabled {
  transform: translateY(-1px);
}

.inventory-surface--ledger {
  position: relative;
  overflow: hidden;
  border-color: #e7d8c8;
  background:
    radial-gradient(circle at 95% 2%, rgba(202, 138, 4, 0.12), transparent 38%),
    linear-gradient(180deg, #fffdf9 0%, #fff9f1 100%);
  box-shadow: 0 16px 30px -25px rgba(120, 53, 15, 0.42);
}

.inventory-surface--ledger::before {
  content: '';
  position: absolute;
  inset: 0;
  pointer-events: none;
  background: linear-gradient(180deg, rgba(255, 255, 255, 0.56), rgba(255, 255, 255, 0));
}

.ledger-toolbar,
.ledger-table-wrap,
.ledger-pagination {
  position: relative;
  z-index: 1;
}

.ledger-title {
  color: #5b2b10;
  letter-spacing: 0.03em;
}

.ledger-filters {
  align-items: center;
}

.ledger-filter-input {
  border-color: #dfcdb9;
  background: rgba(255, 255, 255, 0.92);
}

.ledger-filter-input:focus {
  border-color: #c2410c;
  box-shadow: 0 0 0 2px rgba(194, 65, 12, 0.14);
}

.ledger-filter-btn {
  border-color: #dcc8b3;
  color: #7c2d12;
  background: linear-gradient(180deg, #ffffff, #fff8ef);
}

.ledger-filter-btn:hover:enabled {
  border-color: #cfa683;
  background: #fff7eb;
}

.ledger-batch-actions {
  border-color: #f7d8b0;
  background: linear-gradient(135deg, rgba(255, 247, 237, 0.92), rgba(255, 251, 235, 0.94));
}

.ledger-table-wrap {
  border: 1px solid #eadbc9;
  border-radius: 0.9rem;
  background: rgba(255, 255, 255, 0.86);
}

.ledger-table {
  border-collapse: separate;
  border-spacing: 0;
}

.ledger-table-head th {
  position: sticky;
  top: 0;
  z-index: 1;
  font-weight: 600;
  letter-spacing: 0.02em;
  color: #8b5a2b;
  background: linear-gradient(180deg, #fff8ee 0%, #fff2e2 100%);
  border-bottom-color: #eadbc9;
}

.ledger-row {
  transition: background-color 180ms ease;
}

.ledger-row:hover {
  background: #fff5e9;
}

.ledger-row--selected {
  background: #fff6e6;
}

.ledger-row--selected:hover {
  background: #ffefd6;
}

.ledger-action-badge {
  display: inline-flex;
  align-items: center;
  border-radius: 9999px;
  border: 1px solid transparent;
  padding: 0.1rem 0.56rem;
  font-size: 0.72rem;
  font-weight: 600;
}

.ledger-action-badge--inbound {
  color: #065f46;
  border-color: #99f6e4;
  background: #ecfdf5;
}

.ledger-action-badge--outbound {
  color: #9a3412;
  border-color: #fdba74;
  background: #fff7ed;
}

.ledger-action-badge--loss {
  color: #be123c;
  border-color: #fecdd3;
  background: #fff1f2;
}

.ledger-action-badge--adjust {
  color: #6d28d9;
  border-color: #ddd6fe;
  background: #f5f3ff;
}

.ledger-action-badge--default {
  color: #475569;
  border-color: #cbd5e1;
  background: #f8fafc;
}

.ledger-delta {
  font-weight: 700;
}

.ledger-delta--in {
  color: #047857;
}

.ledger-delta--out {
  color: #be123c;
}

.ledger-pagination {
  border-top-color: #eadbc9;
  background: linear-gradient(180deg, #fffaf2, #fff);
}

.ledger-page-size {
  border-color: #dfcdb9;
  color: #7c2d12;
}

.ledger-page-size:focus {
  border-color: #c2410c;
  box-shadow: 0 0 0 2px rgba(194, 65, 12, 0.15);
}

.ledger-page-btn {
  border-color: #dfcdb9;
  color: #7c2d12;
  background: #fff;
}

.ledger-page-btn:hover:enabled {
  border-color: #cfa683;
  background: #fff7eb;
}

.ledger-page-ellipsis {
  color: #b38a61;
}

.ledger-page-number {
  border-color: #dfcdb9;
}

.ledger-page-number--idle {
  color: #7c2d12;
  background: #fff;
}

.ledger-page-number--idle:hover {
  border-color: #cfa683;
  background: #fff7eb;
}

.ledger-page-number--active {
  border-color: #c2410c;
  color: #fff;
  background: linear-gradient(180deg, #ea580c, #9a3412);
  box-shadow: 0 8px 16px -10px rgba(124, 45, 18, 0.68);
}

.inventory-modal-overlay {
  backdrop-filter: blur(5px);
  background:
    radial-gradient(circle at 15% 8%, rgba(217, 119, 6, 0.25), transparent 42%),
    rgba(15, 23, 42, 0.58);
  animation: modal-fade-in 190ms ease;
}

.inventory-modal {
  position: relative;
  overflow: hidden;
  border: 1px solid #ead7c1;
  background: linear-gradient(180deg, #fffdfa 0%, #fff7ed 100%);
  box-shadow: 0 28px 46px -32px rgba(15, 23, 42, 0.74);
  animation: modal-pop-in 240ms cubic-bezier(0.2, 0.82, 0.2, 1);
}

.inventory-modal::before {
  content: '';
  position: absolute;
  inset: 0;
  pointer-events: none;
  background: linear-gradient(180deg, rgba(255, 255, 255, 0.72), rgba(255, 255, 255, 0));
}

.inventory-modal__header,
.inventory-modal__body,
.inventory-modal__footer {
  position: relative;
  z-index: 1;
}

.inventory-modal__header {
  border-bottom-color: #eadbc9;
  background: linear-gradient(180deg, rgba(255, 248, 238, 0.96), rgba(255, 243, 225, 0.84));
}

.inventory-modal__title {
  color: #5b2b10;
  letter-spacing: 0.03em;
}

.inventory-modal__close {
  width: 2rem;
  height: 2rem;
  border-radius: 9999px;
  border: 1px solid #e4d2bf;
  color: #8b5a2b;
  background: rgba(255, 255, 255, 0.88);
  transition: all 180ms ease;
}

.inventory-modal__close:hover {
  color: #7c2d12;
  background: #fff8ef;
  border-color: #d5b89b;
}

.inventory-modal__body {
  background: linear-gradient(180deg, rgba(255, 255, 255, 0.38), rgba(255, 255, 255, 0));
}

.inventory-modal__footer {
  border-top-color: #eadbc9;
  background: linear-gradient(180deg, rgba(255, 250, 242, 0.8), #fff);
}

.inventory-modal__footer .inventory-btn {
  min-width: 88px;
}

.inventory-modal__checkbox {
  border-color: #decbb6;
  background: rgba(255, 255, 255, 0.82);
}

.inventory-modal :where(.inventory-input) {
  border-color: #dfcdb9;
  background: rgba(255, 255, 255, 0.92);
}

.inventory-modal :where(.inventory-input:focus) {
  border-color: #c2410c;
  box-shadow: 0 0 0 2px rgba(194, 65, 12, 0.15);
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

@keyframes kpi-sheen {
  0% {
    transform: translateX(-110%);
  }
  100% {
    transform: translateX(130%);
  }
}

@keyframes kpi-bar-sheen {
  0% {
    transform: translateX(-120%);
  }
  100% {
    transform: translateX(130%);
  }
}

@keyframes kpi-warning-pulse {
  0%,
  100% {
    box-shadow: 0 8px 14px -12px rgba(69, 10, 10, 0.82);
  }
  50% {
    box-shadow: 0 10px 16px -10px rgba(217, 119, 6, 0.7);
  }
}

@keyframes modal-fade-in {
  from {
    opacity: 0;
  }
  to {
    opacity: 1;
  }
}

@keyframes modal-pop-in {
  from {
    opacity: 0;
    transform: translateY(14px) scale(0.98);
  }
  to {
    opacity: 1;
    transform: translateY(0) scale(1);
  }
}

@media (prefers-reduced-motion: reduce) {
  .inventory-surface--kpi::before {
    animation: none;
  }

  .inventory-modal-overlay,
  .inventory-modal,
  .summary-card__icon,
  .summary-card__bar::after {
    animation: none;
  }

  .summary-card,
  .alert-row,
  .restock-row,
  .inventory-operation-card {
    transition: none;
  }
}
</style>

