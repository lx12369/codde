<script setup>
import { ref, reactive, computed, onMounted, onUnmounted, watch } from 'vue'
import api from '@/api'
import { formatServerDateTime } from '@/utils/dateTime'
import { useBackdropClose } from '@/utils/modalBackdrop'
import {
  normalizeBillingRules,
  calculateConsumptionAmount,
  buildConsumptionDescription,
  getBillingTypeLabel,
  calculateMeituanDeduction,
  applyDeduction
} from '@/utils/consumptionCalculator'
import {
  timerTypeOptions as sharedTimerTypeOptions,
  getTimerPackagePlanOptions,
  getDefaultTimerPackagePlan,
  buildTimerConsumeNotesPayload
} from '@/utils/timerConsume'

const customersLoading = ref(false)
const detailLoading = ref(false)
const loading = ref(false)
const batchDeleteLoading = ref(false)

const customers = ref([])
const total = ref(0)
const currentPage = ref(1)
const pageSize = ref(15)
const searchKeyword = ref('')
const selectedCustomerIds = ref(new Set())

const selectedCustomerId = ref('')
const selectedCustomerDetail = ref(null)

const activities = ref([])
const billingRules = ref(normalizeBillingRules())
const { onBackdropMouseDown, onBackdropMouseUp } = useBackdropClose()

const showRechargeDialog = ref(false)
const showConsumeDialog = ref(false)
const showDetailDialog = ref(false)
const showAddCustomerDialog = ref(false)
const showDeleteConfirmDialog = ref(false)
const feedback = reactive({
  tone: 'info',
  message: ''
})
let feedbackTimer = null

const addCustomerForm = reactive({
  name: '',
  phone: '',
  wechat: '',
  birthday: ''
})

const addCustomerErrors = ref({})

const showEditCustomerDialog = ref(false)
const editCustomerLoading = ref(false)
const deleteCustomerLoading = ref(false)
const deleteConfirmState = reactive({
  mode: 'single',
  customerId: '',
  customerName: '',
  batchIds: [],
  batchNames: []
})
const editCustomerForm = reactive({
  id: '',
  name: '',
  phone: '',
  wechat: '',
  birthday: '',
  balance: 0
})
const editCustomerErrors = ref({})

const rechargeForm = reactive({
  customerId: '',
  amount: '',
  bonusAmount: '',
  paymentMethod: 'cash',
  activityId: ''
})

const consumeMode = ref('manual')

const manualConsumeForm = reactive({
  customerId: '',
  amount: '',
  description: '',
  miscSelections: {},
  meituanCustomer: false
})

const autoConsumeForm = reactive({
  customerId: '',
  billingType: 'limited',
  duration: '1',
  weekdayType: getDefaultTimerPackagePlan('weekday'),
  weekendType: getDefaultTimerPackagePlan('weekend'),
  overtimeMinutes: 0,
  largeImages: 0,
  extraSmallImages: 0,
  extraLargeImages: 0,
  miscSelections: {},
  additionalFee: 0,
  notes: '',
  meituanCustomer: false
})

const timerConsumeForm = reactive({
  customerId: '',
  timerType: 'limited',
  packagePlan: getDefaultTimerPackagePlan('limited'),
  largeImages: 0,
  extraSmallImages: 0,
  extraLargeImages: 0,
  miscSelections: {},
  notes: ''
})

const rechargeErrors = ref({})
const manualConsumeErrors = ref({})
const autoConsumeErrors = ref({})
const timerConsumeErrors = ref({})

const consumeCurrentBalance = ref(null)
const consumeBalanceLoading = ref(false)

const paymentMethods = [
  { value: 'cash', label: '现金' },
  { value: 'wechat', label: '微信' },
  { value: 'alipay', label: '支付宝' },
  { value: 'card', label: '银行卡' }
]

const consumeModes = [
  { value: 'manual', label: '手动输入' },
  { value: 'auto', label: '自动结算' },
  { value: 'timer', label: '计时消费' }
]

const timerTypeOptions = sharedTimerTypeOptions
const timerPackagePlanOptions = computed(() => getTimerPackagePlanOptions(timerConsumeForm.timerType, billingRules.value))
const weekdayTypeOptions = computed(() => getTimerPackagePlanOptions('weekday', billingRules.value))
const weekendTypeOptions = computed(() => getTimerPackagePlanOptions('weekend', billingRules.value))
const pageSizeOptions = [5, 10, 15, 20, 25, 30, 35, 40, 45, 50]

const totalPages = computed(() => Math.max(1, Math.ceil(total.value / pageSize.value)))
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
const emptySlots = computed(() => Math.max(0, pageSize.value - customers.value.length))
const selectedCustomerCount = computed(() => selectedCustomerIds.value.size)
const hasSelectedCustomers = computed(() => selectedCustomerCount.value > 0)
const batchDeleteButtonText = computed(() => {
  if (batchDeleteLoading.value) return '删除中...'
  return `批量删除${selectedCustomerCount.value > 0 ? `（${selectedCustomerCount.value}）` : ''}`
})
const allVisibleSelected = computed(() => (
  customers.value.length > 0
  && customers.value.every((customer) => selectedCustomerIds.value.has(customer.id))
))
const deleteConfirmTitle = computed(() => (
  deleteConfirmState.mode === 'batch' ? '确认批量删除客户' : '确认删除客户'
))
const deleteConfirmMessage = computed(() => {
  if (deleteConfirmState.mode === 'batch') {
    return `即将删除已选 ${deleteConfirmState.batchIds.length} 位客户，此操作不可恢复。`
  }
  return `即将删除客户“${deleteConfirmState.customerName || '-'}”，此操作不可恢复。`
})
const deleteConfirmPreviewNames = computed(() => {
  const source = deleteConfirmState.mode === 'batch'
    ? deleteConfirmState.batchNames
    : [deleteConfirmState.customerName]
  return source.filter(Boolean).slice(0, 4)
})
const deleteConfirmRemainingCount = computed(() => {
  const totalCount = deleteConfirmState.mode === 'batch'
    ? deleteConfirmState.batchNames.filter(Boolean).length
    : (deleteConfirmState.customerName ? 1 : 0)
  return Math.max(0, totalCount - deleteConfirmPreviewNames.value.length)
})

const validCustomers = computed(() =>
  customers.value.filter((customer) => String(customer?.id ?? '').trim().length > 0)
)

const activeConsumeCustomerId = computed(() => {
  if (consumeMode.value === 'manual') return manualConsumeForm.customerId
  if (consumeMode.value === 'auto') return autoConsumeForm.customerId
  return timerConsumeForm.customerId
})

const customerTransactions = computed(() => {
  const transactions = selectedCustomerDetail.value?.transactions
  if (!Array.isArray(transactions)) return []
  return transactions.map(normalizeTransaction)
})

const enabledMiscItems = computed(() => {
  const source = Array.isArray(billingRules.value?.misc?.items) ? billingRules.value.misc.items : []
  return source
    .filter((item) => item && item.enabled)
    .map((item) => ({
      ...item,
      current_stock: Math.max(0, Number(item.current_stock) || 0),
      safe_stock: Math.max(0, Number(item.safe_stock) || 0),
      unit_label: String(item.unit_label || '个')
    }))
    .sort((left, right) => {
      const leftOrder = Number(left.sort_order || 0)
      const rightOrder = Number(right.sort_order || 0)
      if (leftOrder !== rightOrder) return leftOrder - rightOrder
      return String(left.name || '').localeCompare(String(right.name || ''), 'zh-CN')
    })
})

const autoConsumePreview = computed(() =>
  calculateConsumptionAmount(
    {
      billingType: autoConsumeForm.billingType,
      duration: autoConsumeForm.duration,
      weekdayType: autoConsumeForm.weekdayType,
      weekendType: autoConsumeForm.weekendType,
      overtimeMinutes: autoConsumeForm.overtimeMinutes,
      largeImages: autoConsumeForm.largeImages,
      extraSmallImages: autoConsumeForm.extraSmallImages,
      extraLargeImages: autoConsumeForm.extraLargeImages,
      miscSelections: autoConsumeForm.miscSelections,
      additionalFee: autoConsumeForm.additionalFee
    },
    billingRules.value
  )
)

const manualInputAmount = computed(() => {
  const value = Number.parseFloat(manualConsumeForm.amount)
  return Number.isFinite(value) ? Math.max(0, value) : 0
})

const manualMiscSummary = computed(() => buildMiscChargeSummary(manualConsumeForm.miscSelections))
const timerMiscSummary = computed(() => buildMiscChargeSummary(timerConsumeForm.miscSelections))
const manualRawTotal = computed(() => manualInputAmount.value + manualMiscSummary.value.fee)

const manualMeituanDeduction = computed(() => (
  manualConsumeForm.meituanCustomer
    ? calculateMeituanDeduction(manualRawTotal.value)
    : 0
))

const manualFinalAmount = computed(() =>
  applyDeduction(manualRawTotal.value, manualMeituanDeduction.value)
)

const autoMeituanDeduction = computed(() => (
  autoConsumeForm.meituanCustomer
    ? calculateMeituanDeduction(autoConsumePreview.value.baseFee)
    : 0
))

const autoFinalAmount = computed(() =>
  applyDeduction(autoConsumePreview.value.total, autoMeituanDeduction.value)
)

const consumeSubmitLabel = computed(() => {
  if (consumeMode.value === 'manual') return '确认消费'
  if (consumeMode.value === 'auto') return '确认结算'
  return '开始计时'
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
  }, 3800)
}

function getFeedbackClass(tone) {
  if (tone === 'success') return 'management-feedback--success'
  if (tone === 'error') return 'management-feedback--error'
  return 'management-feedback--info'
}

function createMiscSelectionMap(seed = {}) {
  const source = seed && typeof seed === 'object' ? seed : {}
  const result = {}
  enabledMiscItems.value.forEach((item) => {
    const current = Number(source[item.id])
    const available = getMiscAvailableQuantity(item)
    const normalized = Number.isFinite(current) && current >= 0 ? Math.floor(current) : 0
    result[item.id] = Math.min(available, normalized)
  })
  return result
}

function getMiscAvailableQuantity(item) {
  return Math.max(0, Math.floor(Number(item?.current_stock) || 0))
}

function formatMiscStock(item) {
  return `${getMiscAvailableQuantity(item)}${item?.unit_label || '个'}`
}

function clampMiscSelection(selectionMap, item) {
  if (!selectionMap || !item?.id) return
  const available = getMiscAvailableQuantity(item)
  const current = Number(selectionMap[item.id])
  const normalized = Number.isFinite(current) && current >= 0 ? Math.floor(current) : 0
  selectionMap[item.id] = Math.min(available, normalized)
}

function handleMiscSelectionInput(selectionMap, item, rawValue) {
  if (!selectionMap || !item?.id) return
  selectionMap[item.id] = rawValue
  clampMiscSelection(selectionMap, item)
}

function buildMiscChargeSummary(selectionMap = {}) {
  const safeMap = selectionMap && typeof selectionMap === 'object' ? selectionMap : {}
  const details = []
  let fee = 0

  enabledMiscItems.value.forEach((item) => {
    const count = Math.min(getMiscAvailableQuantity(item), Number(safeMap[item.id]))
    if (!Number.isFinite(count) || count <= 0 || !Number.isInteger(count)) return

    fee += count * (Number(item.unit_price) || 0)
    details.push(`${item.name}x${count}`)
  })

  return {
    fee: Math.round((fee + Number.EPSILON) * 100) / 100,
    details
  }
}

function syncAutoMiscSelections(seed = null) {
  const source = seed !== null ? seed : autoConsumeForm.miscSelections
  autoConsumeForm.miscSelections = createMiscSelectionMap(source)
}

function syncManualMiscSelections(seed = null) {
  const source = seed !== null ? seed : manualConsumeForm.miscSelections
  manualConsumeForm.miscSelections = createMiscSelectionMap(source)
}

function syncTimerMiscSelections(seed = null) {
  const source = seed !== null ? seed : timerConsumeForm.miscSelections
  timerConsumeForm.miscSelections = createMiscSelectionMap(source)
}

function collectMiscSelectionErrors(selectionMap = {}) {
  const errors = []
  enabledMiscItems.value.forEach((item) => {
    const raw = selectionMap[item.id]
    if (raw === '' || raw === null || raw === undefined) return
    const count = Number(raw)
    if (!Number.isFinite(count) || count < 0 || !Number.isInteger(count)) {
      errors.push(`${item.name}数量必须为非负整数`)
      return
    }
    if (count > getMiscAvailableQuantity(item)) {
      errors.push(`${item.name}库存不足（可用 ${formatMiscStock(item)}）`)
    }
  })
  return errors
}

function collectAutoMiscErrors(selectionMap = {}) {
  return collectMiscSelectionErrors(selectionMap)
}

function collectManualMiscErrors(selectionMap = {}) {
  return collectMiscSelectionErrors(selectionMap)
}

function collectTimerMiscErrors(selectionMap = {}) {
  return collectMiscSelectionErrors(selectionMap)
}

function normalizeCustomer(customer = {}) {
  return {
    ...customer,
    wechat: customer.wechat ?? '',
    birthday: customer.birthday ?? null,
    createdAt: customer.createdAt ?? customer.created_at ?? null,
    updatedAt: customer.updatedAt ?? customer.updated_at ?? null,
    balance: Number(customer.balance ?? customer.current_balance ?? 0)
  }
}

function normalizeActivity(activity = {}) {
  return {
    ...activity,
    startDate: activity.startDate ?? activity.start_date ?? null,
    endDate: activity.endDate ?? activity.end_date ?? null,
    minRechargeAmount: activity.minRechargeAmount ?? activity.min_amount ?? 0,
    bonusAmount: activity.bonusAmount ?? activity.bonus_amount ?? activity.bonus_rate ?? 0
  }
}

function normalizeTransaction(transaction = {}) {
  return {
    ...transaction,
    type: transaction.type === 'consume' ? 'consumption' : transaction.type,
    amount: Number(transaction.amount ?? 0),
    balanceDelta: Number(transaction.balanceDelta ?? transaction.balance_delta ?? 0),
    bonusAmount: Number(transaction.bonusAmount ?? transaction.bonus_amount ?? 0),
    paymentMethod: transaction.paymentMethod ?? transaction.payment_method ?? '',
    createdAt: transaction.createdAt ?? transaction.created_at ?? transaction.transaction_time ?? null
  }
}

function formatAmount(amount) {
  const value = Number(amount)
  return Number.isFinite(value) ? value.toFixed(2) : '0.00'
}

function formatDateTime(dateTime) {
  return formatServerDateTime(dateTime, {
    hour12: false
  })
}

function formatDate(dateValue) {
  if (!dateValue) return '-'
  return String(dateValue).split('T')[0]
}

function formatBirthdayInputLabel(value) {
  const raw = String(value || '').trim()
  if (!raw) return '年-月-日'
  const parts = raw.split('-')
  if (parts.length !== 3) return raw

  const [year, month, day] = parts
  const yearNum = Number.parseInt(year, 10)
  const monthNum = Number.parseInt(month, 10)
  const dayNum = Number.parseInt(day, 10)

  if (!Number.isFinite(yearNum) || !Number.isFinite(monthNum) || !Number.isFinite(dayNum)) {
    return raw
  }

  return `${yearNum}-${String(monthNum).padStart(2, '0')}-${String(dayNum).padStart(2, '0')}`
}

function getTransactionTypeLabel(type) {
  if (type === 'recharge') return '充值'
  if (type === 'consumption') return '消费'
  if (type === 'expense') return '支出'
  if (type === 'bead_purchase') return '买豆支出'
  return '-'
}

function getTransactionTypeClass(type) {
  if (type === 'recharge') return 'bg-green-100 text-green-700'
  if (type === 'consumption') return 'bg-orange-100 text-orange-700'
  if (type === 'expense') return 'bg-rose-100 text-rose-700'
  if (type === 'bead_purchase') return 'bg-amber-100 text-amber-700'
  return 'bg-gray-100 text-gray-700'
}

function getBalanceDeltaClass(balanceDelta) {
  if (balanceDelta > 0) return 'text-green-600'
  if (balanceDelta < 0) return 'text-orange-600'
  return 'text-gray-500'
}

function formatSignedAmount(amount) {
  const normalized = Number(amount) || 0
  if (normalized > 0) return `+￥${formatAmount(normalized)}`
  if (normalized < 0) return `-￥${formatAmount(Math.abs(normalized))}`
  return '￥0.00'
}

function resetAddCustomerForm() {
  addCustomerForm.name = ''
  addCustomerForm.phone = ''
  addCustomerForm.wechat = ''
  addCustomerForm.birthday = ''
  addCustomerErrors.value = {}
}

function openAddCustomerDialog() {
  resetAddCustomerForm()
  showAddCustomerDialog.value = true
}

function validateAddCustomerForm() {
  const errors = {}
  if (!String(addCustomerForm.name || '').trim()) {
    errors.name = '请输入客户姓名'
  }
  addCustomerErrors.value = errors
  return Object.keys(errors).length === 0
}

async function submitAddCustomer() {
  if (!validateAddCustomerForm()) return

  loading.value = true
  try {
    const response = await api.post('/customers', {
      name: String(addCustomerForm.name || '').trim(),
      phone: String(addCustomerForm.phone || '').trim() || null,
      wechat: String(addCustomerForm.wechat || '').trim() || null,
      birthday: addCustomerForm.birthday || null
    })

    const payload = response?.data || response || {}
    const createdCustomerId = payload.id || ''

    showAddCustomerDialog.value = false
    if (searchKeyword.value.trim()) {
      searchKeyword.value = ''
    }
    currentPage.value = 1
    await fetchCustomers()
    if (createdCustomerId) {
      await openCustomerDetail(createdCustomerId)
    }
    showFeedback('success', '客户已新增。')
  } catch (error) {
    console.error('Failed to create customer:', error)
    showFeedback('error', error?.response?.data?.message || error?.message || '新增客户失败')
  } finally {
    loading.value = false
  }
}

function openEditCustomerDialog() {
  if (!selectedCustomerDetail.value) return
  editCustomerForm.id = selectedCustomerDetail.value.id || ''
  editCustomerForm.name = selectedCustomerDetail.value.name || ''
  editCustomerForm.phone = selectedCustomerDetail.value.phone || ''
  editCustomerForm.wechat = selectedCustomerDetail.value.wechat || ''
  editCustomerForm.birthday = selectedCustomerDetail.value.birthday ? String(selectedCustomerDetail.value.birthday).split('T')[0] : ''
  editCustomerForm.balance = Number(selectedCustomerDetail.value.balance || 0)
  editCustomerErrors.value = {}
  showEditCustomerDialog.value = true
}

function resetDeleteConfirmState() {
  deleteConfirmState.mode = 'single'
  deleteConfirmState.customerId = ''
  deleteConfirmState.customerName = ''
  deleteConfirmState.batchIds = []
  deleteConfirmState.batchNames = []
}

function closeDeleteConfirmDialog() {
  if (deleteCustomerLoading.value || batchDeleteLoading.value) return
  showDeleteConfirmDialog.value = false
  resetDeleteConfirmState()
}

function openDeleteCustomerConfirm(customer) {
  if (!customer?.id) return
  deleteConfirmState.mode = 'single'
  deleteConfirmState.customerId = customer.id
  deleteConfirmState.customerName = customer.name || customer.id
  deleteConfirmState.batchIds = []
  deleteConfirmState.batchNames = []
  showDeleteConfirmDialog.value = true
}

function openBatchDeleteConfirm() {
  if (!hasSelectedCustomers.value) return
  const targetIds = Array.from(selectedCustomerIds.value)
  const customerMap = new Map(customers.value.map((customer) => [customer.id, customer]))
  deleteConfirmState.mode = 'batch'
  deleteConfirmState.customerId = ''
  deleteConfirmState.customerName = ''
  deleteConfirmState.batchIds = targetIds
  deleteConfirmState.batchNames = targetIds.map((id) => customerMap.get(id)?.name || id)
  showDeleteConfirmDialog.value = true
}

function validateEditCustomerForm() {
  const errors = {}
  if (!String(editCustomerForm.name || '').trim()) {
    errors.name = '请输入客户姓名'
  }
  editCustomerErrors.value = errors
  return Object.keys(errors).length === 0
}

async function submitEditCustomer() {
  if (!selectedCustomerDetail.value) return
  if (!validateEditCustomerForm()) return

  editCustomerLoading.value = true
  try {
    await api.put(`/customers/${selectedCustomerDetail.value.id}`, {
      name: String(editCustomerForm.name || '').trim(),
      phone: String(editCustomerForm.phone || '').trim() || null,
      wechat: String(editCustomerForm.wechat || '').trim() || null,
      birthday: editCustomerForm.birthday || null
    })

    showEditCustomerDialog.value = false
    await fetchCustomers()
    await fetchCustomerDetail(selectedCustomerDetail.value.id)
    showFeedback('success', '客户信息已更新。')
  } catch (error) {
    console.error('Failed to update customer:', error)
    showFeedback('error', error?.response?.data?.message || error?.message || '更新客户失败')
  } finally {
    editCustomerLoading.value = false
  }
}

async function performDeleteCustomer(targetId) {
  if (!targetId) return
  deleteCustomerLoading.value = true
  try {
    await api.delete(`/customers/${targetId}`)
    const nextSelectedIds = new Set(selectedCustomerIds.value)
    nextSelectedIds.delete(targetId)
    selectedCustomerIds.value = nextSelectedIds
    showEditCustomerDialog.value = false
    showDetailDialog.value = false
    selectedCustomerDetail.value = null
    selectedCustomerId.value = ''
    await fetchCustomers()
    showFeedback('success', '客户已删除。')
  } catch (error) {
    console.error('Failed to delete customer:', error)
    showFeedback('error', error?.response?.data?.message || error?.message || '删除客户失败')
  } finally {
    deleteCustomerLoading.value = false
  }
}

async function deleteCustomerFromDetail() {
  if (!selectedCustomerDetail.value) return
  openDeleteCustomerConfirm(selectedCustomerDetail.value)
}

function clearSelectedCustomers() {
  selectedCustomerIds.value = new Set()
}

function isCustomerSelected(customerId = '') {
  return selectedCustomerIds.value.has(customerId)
}

function toggleCustomerSelection(customerId = '', checked = false) {
  if (!customerId) return
  const nextSelectedIds = new Set(selectedCustomerIds.value)
  if (checked) {
    nextSelectedIds.add(customerId)
  } else {
    nextSelectedIds.delete(customerId)
  }
  selectedCustomerIds.value = nextSelectedIds
}

function toggleSelectAllVisibleCustomers(checked = false) {
  const nextSelectedIds = new Set(selectedCustomerIds.value)
  const visibleCustomerIds = customers.value.map((customer) => customer.id).filter(Boolean)
  if (checked) {
    visibleCustomerIds.forEach((id) => nextSelectedIds.add(id))
  } else {
    visibleCustomerIds.forEach((id) => nextSelectedIds.delete(id))
  }
  selectedCustomerIds.value = nextSelectedIds
}

async function batchDeleteCustomers() {
  if (!hasSelectedCustomers.value) return
  openBatchDeleteConfirm()
}

async function performBatchDeleteCustomers(targetIds) {
  if (!Array.isArray(targetIds) || targetIds.length === 0) return
  batchDeleteLoading.value = true
  try {
    const results = await Promise.allSettled(
      targetIds.map((customerId) => api.delete(`/customers/${customerId}`))
    )

    const failedIds = []
    results.forEach((result, index) => {
      if (result.status === 'rejected') {
        failedIds.push(targetIds[index])
      }
    })

    const successCount = targetIds.length - failedIds.length
    if (failedIds.length === 0) {
      showFeedback('success', `批量删除成功，共删除 ${successCount} 位客户。`)
    } else {
      showFeedback('error', `已删除 ${successCount} 位客户，删除失败 ${failedIds.length} 位：${failedIds.join('、')}`)
    }

    if (
      selectedCustomerDetail.value
      && targetIds.includes(selectedCustomerDetail.value.id)
      && !failedIds.includes(selectedCustomerDetail.value.id)
    ) {
      showEditCustomerDialog.value = false
      showDetailDialog.value = false
      selectedCustomerDetail.value = null
      selectedCustomerId.value = ''
    }

    clearSelectedCustomers()
    await fetchCustomers()
    if (customers.value.length === 0 && currentPage.value > 1) {
      currentPage.value -= 1
      await fetchCustomers()
    }
  } catch (error) {
    console.error('Failed to batch delete customers:', error)
    showFeedback('error', error?.response?.data?.message || error?.message || '批量删除失败')
  } finally {
    batchDeleteLoading.value = false
  }
}

async function confirmDeleteAction() {
  if (deleteConfirmState.mode === 'batch') {
    await performBatchDeleteCustomers([...deleteConfirmState.batchIds])
  } else {
    await performDeleteCustomer(deleteConfirmState.customerId)
  }

  if (!deleteCustomerLoading.value && !batchDeleteLoading.value) {
    closeDeleteConfirmDialog()
  }
}

async function fetchCustomers() {
  customersLoading.value = true
  try {
    const response = await api.get('/customers', {
      params: {
        page: currentPage.value,
        page_size: pageSize.value,
        search: searchKeyword.value.trim() || undefined
      }
    })

    const payload = response?.data || response || {}
    const items = Array.isArray(payload.items) ? payload.items : []
    const pagination = payload.pagination || {}

    customers.value = items.map(normalizeCustomer)
    total.value = Number(pagination.total ?? items.length)
    clearSelectedCustomers()

    const exists = customers.value.some((customer) => customer.id === selectedCustomerId.value)
    if (!exists) {
      selectedCustomerId.value = customers.value[0]?.id || ''
    }
  } catch (error) {
    console.error('Failed to fetch customers:', error)
    customers.value = []
    total.value = 0
    selectedCustomerId.value = ''
    clearSelectedCustomers()
  } finally {
    customersLoading.value = false
  }
}

async function fetchCustomerDetail(customerId) {
  if (!customerId) {
    selectedCustomerDetail.value = null
    return
  }

  detailLoading.value = true
  try {
    const response = await api.get(`/customers/${customerId}`)
    const payload = response?.data || response || {}
    selectedCustomerDetail.value = {
      ...normalizeCustomer(payload),
      transactions: Array.isArray(payload.transactions) ? payload.transactions : []
    }
  } catch (error) {
    console.error('Failed to fetch customer detail:', error)
    selectedCustomerDetail.value = null
  } finally {
    detailLoading.value = false
  }
}

async function fetchActivities() {
  try {
    const response = await api.get('/activities', { params: { status: 'active' } })
    const payload = response?.data || response || []
    activities.value = Array.isArray(payload) ? payload.map(normalizeActivity) : []
  } catch (error) {
    console.error('Failed to fetch activities:', error)
    activities.value = []
  }
}

async function fetchBillingRules() {
  try {
    const response = await api.get('/billing-rules')
    const payload = response?.data || response || {}
    billingRules.value = normalizeBillingRules(payload)
    syncManualMiscSelections()
    syncAutoMiscSelections()
    syncTimerMiscSelections()
  } catch (error) {
    console.error('Failed to fetch billing rules:', error)
    billingRules.value = normalizeBillingRules()
    syncManualMiscSelections()
    syncAutoMiscSelections()
    syncTimerMiscSelections()
  }
}

async function fetchCustomerBalance(customerId = '') {
  if (!customerId) return null
  try {
    const response = await api.get(`/customers/${customerId}/balance`)
    const payload = response?.data || response || {}
    const balance = Number(payload.balance)
    return Number.isFinite(balance) ? balance : 0
  } catch (error) {
    console.error('Failed to fetch customer balance:', error)
    return null
  }
}

async function syncConsumeBalance(customerId = '') {
  consumeCurrentBalance.value = null
  if (!customerId) return
  consumeBalanceLoading.value = true
  try {
    consumeCurrentBalance.value = await fetchCustomerBalance(customerId)
  } finally {
    consumeBalanceLoading.value = false
  }
}

async function handleSearch() {
  currentPage.value = 1
  await fetchCustomers()
}

async function handleResetSearch() {
  searchKeyword.value = ''
  currentPage.value = 1
  await fetchCustomers()
}

async function handlePageChange(page) {
  if (page < 1 || page > totalPages.value) return
  currentPage.value = page
  await fetchCustomers()
}

async function handlePageSizeChange() {
  currentPage.value = 1
  await fetchCustomers()
}

async function openCustomerDetail(customerId) {
  if (!customerId) return
  selectedCustomerId.value = customerId
  showDetailDialog.value = true
  await fetchCustomerDetail(customerId)
}

function calculateActivityBonus(activity, amount) {
  const parsedAmount = parseFloat(amount)
  if (!activity || Number.isNaN(parsedAmount) || parsedAmount <= 0) return 0

  const minRechargeAmount = parseFloat(activity.minRechargeAmount)
  const fixedBonus = parseFloat(activity.bonusAmount)
  if (Number.isNaN(minRechargeAmount) || minRechargeAmount <= 0) return 0
  if (Number.isNaN(fixedBonus) || fixedBonus < 0) return 0
  if (parsedAmount < minRechargeAmount) return 0

  const multiples = Math.floor(parsedAmount / minRechargeAmount)
  if (multiples <= 0) return 0
  return Number((multiples * fixedBonus).toFixed(2))
}

function applyRechargeActivityPreset(activityId) {
  if (!activityId) {
    if (!rechargeForm.bonusAmount) rechargeForm.bonusAmount = '0'
    return
  }

  const activity = activities.value.find((item) => item.id === activityId)
  if (!activity) return

  const minRecharge = parseFloat(activity.minRechargeAmount)
  const currentAmount = parseFloat(rechargeForm.amount)
  if (!Number.isNaN(minRecharge) && minRecharge > 0 && (Number.isNaN(currentAmount) || currentAmount <= 0)) {
    rechargeForm.amount = String(minRecharge)
  }

  rechargeForm.bonusAmount = String(calculateActivityBonus(activity, rechargeForm.amount))
}

function resetConsumeForms(customerId = '') {
  consumeMode.value = 'manual'

  manualConsumeForm.customerId = customerId
  manualConsumeForm.amount = ''
  manualConsumeForm.description = ''
  syncManualMiscSelections({})
  manualConsumeForm.meituanCustomer = false

  autoConsumeForm.customerId = customerId
  autoConsumeForm.billingType = 'limited'
  autoConsumeForm.duration = '1'
  autoConsumeForm.weekdayType = getDefaultTimerPackagePlan('weekday', billingRules.value)
  autoConsumeForm.weekendType = getDefaultTimerPackagePlan('weekend', billingRules.value)
  autoConsumeForm.overtimeMinutes = 0
  autoConsumeForm.largeImages = 0
  autoConsumeForm.extraSmallImages = 0
  autoConsumeForm.extraLargeImages = 0
  syncAutoMiscSelections({})
  autoConsumeForm.additionalFee = 0
  autoConsumeForm.notes = ''
  autoConsumeForm.meituanCustomer = false

  timerConsumeForm.customerId = customerId
  timerConsumeForm.timerType = 'limited'
  timerConsumeForm.packagePlan = getDefaultTimerPackagePlan('limited', billingRules.value)
  timerConsumeForm.largeImages = 0
  timerConsumeForm.extraSmallImages = 0
  timerConsumeForm.extraLargeImages = 0
  syncTimerMiscSelections({})
  timerConsumeForm.notes = ''

  manualConsumeErrors.value = {}
  autoConsumeErrors.value = {}
  timerConsumeErrors.value = {}
}

async function openRechargeDialog(customerId = '') {
  showDetailDialog.value = false
  rechargeForm.customerId = customerId || selectedCustomerId.value || ''
  rechargeForm.amount = ''
  rechargeForm.bonusAmount = ''
  rechargeForm.paymentMethod = 'cash'
  rechargeForm.activityId = ''
  rechargeErrors.value = {}
  showRechargeDialog.value = true
}

async function openConsumeDialog(customerId = '') {
  showDetailDialog.value = false
  const targetCustomerId = customerId || selectedCustomerId.value || ''
  resetConsumeForms(targetCustomerId)
  showConsumeDialog.value = true
  await Promise.all([fetchBillingRules(), syncConsumeBalance(targetCustomerId)])
}

function validateRechargeForm() {
  const errors = {}
  if (!rechargeForm.customerId) {
    errors.customerId = '请选择客户'
  } else if (!validCustomers.value.some((customer) => customer.id === rechargeForm.customerId)) {
    errors.customerId = '请选择有效客户'
  }
  if (!rechargeForm.amount || parseFloat(rechargeForm.amount) <= 0) {
    errors.amount = '请输入有效金额'
  }
  rechargeErrors.value = errors
  return Object.keys(errors).length === 0
}

function validateManualConsumeForm() {
  const errors = {}
  if (!manualConsumeForm.customerId) {
    errors.customerId = '请选择客户'
  } else if (!validCustomers.value.some((customer) => customer.id === manualConsumeForm.customerId)) {
    errors.customerId = '请选择有效客户'
  }
  if (manualRawTotal.value <= 0) {
    errors.amount = '请输入有效金额或杂项数量'
  }
  if (!manualConsumeForm.description?.trim()) {
    errors.description = '请输入消费描述'
  }

  const miscErrors = collectManualMiscErrors(manualConsumeForm.miscSelections)
  if (miscErrors.length > 0) {
    errors.misc = miscErrors[0]
  }

  manualConsumeErrors.value = errors
  return Object.keys(errors).length === 0
}

function validateAutoConsumeForm() {
  const errors = {}
  if (!autoConsumeForm.customerId) {
    errors.customerId = '请选择客户'
  } else if (!validCustomers.value.some((customer) => customer.id === autoConsumeForm.customerId)) {
    errors.customerId = '请选择有效客户'
  }
  if (autoFinalAmount.value <= 0) {
    errors.total = '自动结算金额必须大于0'
  }

  const miscErrors = collectAutoMiscErrors(autoConsumeForm.miscSelections)
  if (miscErrors.length > 0) {
    errors.misc = miscErrors[0]
  }

  autoConsumeErrors.value = errors
  return Object.keys(errors).length === 0
}

function validateTimerConsumeForm() {
  const errors = {}
  if (!timerConsumeForm.customerId) {
    errors.customerId = '请选择客户'
  } else if (!validCustomers.value.some((customer) => customer.id === timerConsumeForm.customerId)) {
    errors.customerId = '请选择有效客户'
  }
  if (!timerConsumeForm.timerType) {
    errors.timerType = '请选择计时类型'
  }
  if (!timerConsumeForm.packagePlan) {
    errors.packagePlan = '请选择套餐方案'
  } else {
    const options = getTimerPackagePlanOptions(timerConsumeForm.timerType || 'limited', billingRules.value)
    const exists = options.some((item) => String(item?.value || '').trim() === String(timerConsumeForm.packagePlan || '').trim())
    if (!exists) {
      errors.packagePlan = '套餐方案已失效，请重新选择'
    }
  }

  const miscErrors = collectTimerMiscErrors(timerConsumeForm.miscSelections)
  if (miscErrors.length > 0) {
    errors.misc = miscErrors[0]
  }

  timerConsumeErrors.value = errors
  return Object.keys(errors).length === 0
}

async function refreshAfterTransaction(targetCustomerId) {
  await fetchCustomers()
  if (targetCustomerId) selectedCustomerId.value = targetCustomerId
  if (showDetailDialog.value && selectedCustomerId.value) {
    await fetchCustomerDetail(selectedCustomerId.value)
  }
}

async function submitRecharge() {
  if (!validateRechargeForm()) return

  const parsedBonus = parseFloat(rechargeForm.bonusAmount)

  loading.value = true
  try {
    await api.post('/transactions/recharge', {
      customer_id: rechargeForm.customerId,
      amount: parseFloat(rechargeForm.amount),
      bonus_amount: Number.isNaN(parsedBonus) ? null : parsedBonus,
      payment_method: rechargeForm.paymentMethod,
      activity_id: rechargeForm.activityId || null
    })
    showRechargeDialog.value = false
    await refreshAfterTransaction(rechargeForm.customerId)
    showFeedback('success', '充值记录已创建。')
  } catch (error) {
    console.error('Failed to create recharge:', error)
    showFeedback('error', error?.response?.data?.message || error?.message || '创建充值记录失败')
  } finally {
    loading.value = false
  }
}

async function submitManualConsume() {
  if (!validateManualConsumeForm()) return
  const amount = manualFinalAmount.value
  const miscSelections = createMiscSelectionMap(manualConsumeForm.miscSelections)
  const currentBalance = await fetchCustomerBalance(manualConsumeForm.customerId)
  if (currentBalance !== null && amount > currentBalance) {
    manualConsumeErrors.value = { ...manualConsumeErrors.value, amount: '余额不足' }
    showFeedback('error', '客户余额不足。')
    return
  }

  const noteParts = [String(manualConsumeForm.description || '').trim()]
  if (manualMiscSummary.value.details.length > 0) {
    noteParts.push(`杂项${manualMiscSummary.value.details.join('、')}`)
  }
  if (manualConsumeForm.meituanCustomer) {
    noteParts.push(`美团客户(抽成￥${formatAmount(manualMeituanDeduction.value)})`)
  }
  const description = noteParts.filter(Boolean).join('；')

  await api.post('/transactions/consumption', {
    customer_id: manualConsumeForm.customerId,
    amount,
    description,
    misc_selections: miscSelections
  })
}

async function submitAutoConsume() {
  if (!validateAutoConsumeForm()) return
  const amount = autoFinalAmount.value
  const miscSelections = createMiscSelectionMap(autoConsumeForm.miscSelections)
  const currentBalance = await fetchCustomerBalance(autoConsumeForm.customerId)
  if (currentBalance !== null && amount > currentBalance) {
    autoConsumeErrors.value = { ...autoConsumeErrors.value, total: '余额不足，无法结算' }
    showFeedback('error', '客户余额不足。')
    return
  }

  const description = buildConsumptionDescription(
    {
      mode: 'auto',
      billingType: autoConsumeForm.billingType
    },
    autoConsumePreview.value,
    autoConsumeForm.meituanCustomer
      ? `${autoConsumeForm.notes || ''}${autoConsumeForm.notes ? '；' : ''}美团客户(基础费用抽成￥${formatAmount(autoMeituanDeduction.value)})`
      : autoConsumeForm.notes
  )

  await api.post('/transactions/consumption', {
    customer_id: autoConsumeForm.customerId,
    amount,
    description,
    misc_selections: miscSelections
  })
}

async function submitTimerConsume() {
  if (!validateTimerConsumeForm()) return

  const normalizedMiscSelections = createMiscSelectionMap(timerConsumeForm.miscSelections)
  const notesPayload = buildTimerConsumeNotesPayload(
    {
      ...timerConsumeForm,
      miscSelections: normalizedMiscSelections
    },
    billingRules.value
  )

  await api.post('/active-timers', {
    customer_id: timerConsumeForm.customerId,
    timer_type: timerConsumeForm.timerType,
    notes: notesPayload
  })

  showFeedback('info', '计时消费已开始，请到“正在计时”页面完成结算。')
}

async function submitConsumeByMode() {
  loading.value = true
  try {
    if (consumeMode.value === 'manual') {
      await submitManualConsume()
      await refreshAfterTransaction(manualConsumeForm.customerId)
      showFeedback('success', '消费已完成。')
    } else if (consumeMode.value === 'auto') {
      await submitAutoConsume()
      await refreshAfterTransaction(autoConsumeForm.customerId)
      showFeedback('success', '自动结算已完成。')
    } else {
      await submitTimerConsume()
      await fetchCustomerDetail(selectedCustomerId.value)
    }
    showConsumeDialog.value = false
  } catch (error) {
    console.error('Failed to handle consume action:', error)
    showFeedback('error', error?.response?.data?.message || error?.message || '消费操作失败')
  } finally {
    loading.value = false
    await syncConsumeBalance(activeConsumeCustomerId.value)
  }
}

watch(
  () => rechargeForm.activityId,
  (activityId) => {
    if (!showRechargeDialog.value) return
    applyRechargeActivityPreset(activityId)
  }
)

watch(
  () => rechargeForm.amount,
  () => {
    if (!showRechargeDialog.value || !rechargeForm.activityId) return
    const activity = activities.value.find((item) => item.id === rechargeForm.activityId)
    if (!activity) return
    rechargeForm.bonusAmount = String(calculateActivityBonus(activity, rechargeForm.amount))
  }
)

watch(
  () => activeConsumeCustomerId.value,
  async (customerId) => {
    if (!showConsumeDialog.value) return
    await syncConsumeBalance(customerId)
  }
)

watch(
  () => timerConsumeForm.timerType,
  (nextType) => {
    const options = getTimerPackagePlanOptions(nextType, billingRules.value)
    const currentPlan = timerConsumeForm.packagePlan
    if (!options.some((item) => item.value === currentPlan)) {
      timerConsumeForm.packagePlan = getDefaultTimerPackagePlan(nextType, billingRules.value)
    }
  }
)

watch(
  () => billingRules.value,
  () => {
    const weekdayOptions = weekdayTypeOptions.value
    const weekendOptions = weekendTypeOptions.value
    if (!weekdayOptions.some((item) => item.value === autoConsumeForm.weekdayType)) {
      autoConsumeForm.weekdayType = getDefaultTimerPackagePlan('weekday', billingRules.value)
    }
    if (!weekendOptions.some((item) => item.value === autoConsumeForm.weekendType)) {
      autoConsumeForm.weekendType = getDefaultTimerPackagePlan('weekend', billingRules.value)
    }

    const timerOptions = timerPackagePlanOptions.value
    if (!timerOptions.some((item) => item.value === timerConsumeForm.packagePlan)) {
      timerConsumeForm.packagePlan = getDefaultTimerPackagePlan(timerConsumeForm.timerType, billingRules.value)
    }
  },
  { deep: true }
)

onMounted(async () => {
  await Promise.all([fetchCustomers(), fetchActivities(), fetchBillingRules()])
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
          <p class="page-hero__eyebrow">Customer Desk</p>
          <h1 class="page-hero__title">客户管理</h1>
        </div>
        <div class="flex flex-wrap items-center gap-2">
          <button
            @click="openBatchDeleteConfirm"
            :disabled="batchDeleteLoading || !hasSelectedCustomers"
            class="page-hero__action page-hero__action--danger"
          >
            {{ batchDeleteButtonText }}
          </button>
          <button
            @click="openAddCustomerDialog"
            class="page-hero__action"
          >
            新增客户
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

    <div class="management-surface p-4 sm:p-6">
      <div class="flex flex-col sm:flex-row gap-3">
        <input
          v-model="searchKeyword"
          type="text"
          placeholder="搜索客户姓名、手机号、微信号或编号"
          class="flex-1 px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
        >
        <button
          @click="handleSearch"
          class="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors"
        >
          查询
        </button>
        <button
          @click="handleResetSearch"
          class="px-4 py-2 border border-gray-300 text-gray-700 rounded-lg hover:bg-gray-50 transition-colors"
        >
          重置
        </button>
      </div>
    </div>

    <div class="management-surface overflow-hidden">
      <div class="px-5 py-4 border-b border-gray-100 flex items-center justify-between">
        <h2 class="text-lg font-semibold text-gray-800">客户列表</h2>
        <div class="flex items-center gap-4">
          <label class="inline-flex items-center gap-2 text-sm text-gray-600">
            <input
              type="checkbox"
              :checked="allVisibleSelected"
              :disabled="customersLoading || customers.length === 0"
              @change="toggleSelectAllVisibleCustomers($event.target.checked)"
              class="h-4 w-4 rounded border-gray-300 text-blue-600 focus:ring-blue-500"
            >
            本页全选
          </label>
          <span class="text-sm text-gray-500">点击客户卡片查看详情</span>
        </div>
      </div>

      <div v-if="customersLoading" class="p-10 text-center text-gray-500">加载中...</div>
      <div v-else-if="customers.length === 0" class="p-10 text-center text-gray-500">暂无客户数据</div>
      <div v-else class="p-4 grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
        <div
          v-for="customer in customers"
          :key="customer.id"
          class="rounded-xl border border-gray-200 bg-gradient-to-br from-white to-gray-50 p-4 hover:shadow-md transition cursor-pointer"
          @click="openCustomerDetail(customer.id)"
        >
          <div class="flex items-start justify-between">
            <div>
              <p class="text-base font-semibold text-gray-900">{{ customer.name }}</p>
              <p class="text-xs text-gray-500 mt-0.5">{{ customer.id }}</p>
            </div>
            <div class="flex items-center gap-2">
              <input
                type="checkbox"
                :checked="isCustomerSelected(customer.id)"
                @click.stop
                @change.stop="toggleCustomerSelection(customer.id, $event.target.checked)"
                class="h-4 w-4 rounded border-gray-300 text-blue-600 focus:ring-blue-500"
              >
              <span class="px-2 py-1 rounded-full text-xs bg-blue-100 text-blue-700">￥{{ formatAmount(customer.balance) }}</span>
            </div>
          </div>

          <div class="mt-3 space-y-1">
            <p class="text-sm text-gray-600">微信号：{{ customer.wechat || '-' }}</p>
            <p class="text-sm text-gray-600">手机号：{{ customer.phone || '-' }}</p>
          </div>
        </div>
        <div
          v-for="slot in emptySlots"
          :key="`empty-slot-${slot}`"
          class="invisible min-h-[96px] p-4 pointer-events-none select-none"
          aria-hidden="true"
        ></div>
      </div>

      <div v-if="total > 0" class="px-5 py-4 border-t border-gray-100 bg-gradient-to-r from-gray-50 to-white">
        <div class="flex flex-col gap-3 xl:flex-row xl:items-center xl:justify-between">
          <p class="text-sm text-gray-600">
            显示 {{ (currentPage - 1) * pageSize + 1 }} 到 {{ Math.min(currentPage * pageSize, total) }} 条，共 {{ total }} 条记录
          </p>
          <div class="flex flex-col gap-3 sm:flex-row sm:items-center">
            <label class="flex items-center gap-2 text-sm text-gray-600">
              <span>每页</span>
              <select
                v-model.number="pageSize"
                @change="handlePageSizeChange"
                class="h-9 min-w-[92px] px-3 border border-gray-200 rounded-lg bg-white text-sm text-gray-700 focus:outline-none focus:ring-2 focus:ring-blue-500"
              >
                <option v-for="size in pageSizeOptions" :key="size" :value="size">{{ size }}条</option>
              </select>
            </label>
            <div class="flex items-center gap-1">
              <button
                @click="handlePageChange(currentPage - 1)"
                :disabled="currentPage === 1"
                class="h-9 px-3 rounded-lg border border-gray-200 bg-white text-sm font-medium text-gray-700 transition hover:bg-gray-100 disabled:cursor-not-allowed disabled:opacity-45"
              >
                上一页
              </button>
              <template v-for="(page, index) in visiblePages" :key="`customer-page-${page}-${index}`">
                <span v-if="page === '...'" class="w-9 text-center text-sm text-gray-400 select-none">...</span>
                <button
                  v-else
                  @click="handlePageChange(page)"
                  :class="[
                    'h-9 min-w-[2.25rem] px-2 rounded-lg border text-sm font-medium transition',
                    currentPage === page
                      ? 'border-blue-600 bg-blue-600 text-white shadow-sm shadow-blue-100'
                      : 'border-gray-200 bg-white text-gray-700 hover:bg-gray-100'
                  ]"
                >
                  {{ page }}
                </button>
              </template>
              <button
                @click="handlePageChange(currentPage + 1)"
                :disabled="currentPage === totalPages"
                class="h-9 px-3 rounded-lg border border-gray-200 bg-white text-sm font-medium text-gray-700 transition hover:bg-gray-100 disabled:cursor-not-allowed disabled:opacity-45"
              >
                下一页
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>

    <Teleport to="body">
      <div
        v-if="showDeleteConfirmDialog"
        class="fixed inset-0 bg-black bg-opacity-55 flex items-center justify-center z-[70] p-4"
        @mousedown="onBackdropMouseDown('customers-delete-confirm', $event)"
        @mouseup="onBackdropMouseUp('customers-delete-confirm', $event) && closeDeleteConfirmDialog()"
      >
        <div class="w-full max-w-sm rounded-2xl border border-gray-200 bg-white shadow-xl">
          <div class="px-6 py-5">
            <h3 class="text-lg font-semibold text-gray-900">{{ deleteConfirmTitle }}</h3>
            <p class="mt-2 text-sm text-gray-600">{{ deleteConfirmMessage }}</p>
            <div class="mt-4 rounded-lg bg-gray-50 px-3 py-3 text-sm text-gray-700">
              <p class="font-medium text-gray-900">删除对象</p>
              <p class="mt-1 leading-6">
                {{ deleteConfirmPreviewNames.join('、') || '-' }}
                <span v-if="deleteConfirmRemainingCount > 0" class="text-gray-500"> 等另外 {{ deleteConfirmRemainingCount }} 位</span>
              </p>
            </div>
            <p class="mt-3 text-xs text-rose-600">删除后不可恢复。</p>
          </div>

          <div class="flex items-center justify-end gap-3 border-t border-gray-100 px-6 py-4">
            <button
              @click="closeDeleteConfirmDialog"
              :disabled="deleteCustomerLoading || batchDeleteLoading"
              class="rounded-lg border border-gray-300 px-4 py-2 text-sm text-gray-700 hover:bg-gray-50 disabled:cursor-not-allowed disabled:opacity-50"
            >
              取消
            </button>
            <button
              @click="confirmDeleteAction"
              :disabled="deleteCustomerLoading || batchDeleteLoading"
              class="rounded-lg bg-red-600 px-4 py-2 text-sm text-white hover:bg-red-700 disabled:cursor-not-allowed disabled:bg-red-300"
            >
              {{ deleteCustomerLoading || batchDeleteLoading ? '删除中...' : '确认删除' }}
            </button>
          </div>
        </div>
      </div>
    </Teleport>

    <Teleport to="body">
      <div
        v-if="showAddCustomerDialog"
        class="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50"
        @mousedown="onBackdropMouseDown('customers-add', $event)"
        @mouseup="onBackdropMouseUp('customers-add', $event) && (showAddCustomerDialog = false)"
      >
        <div class="bg-white rounded-xl shadow-xl w-full max-w-md mx-4">
          <div class="px-6 py-4 border-b border-gray-200 flex items-center justify-between">
            <h3 class="text-lg font-semibold text-gray-800">新增客户</h3>
            <button @click="showAddCustomerDialog = false" class="text-gray-400 hover:text-gray-600 transition-colors">
              <svg xmlns="http://www.w3.org/2000/svg" class="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>
          <div class="p-6 space-y-4">
            <div>
              <label class="block text-sm font-medium text-gray-700 mb-1">客户姓名</label>
              <input
                v-model="addCustomerForm.name"
                type="text"
                placeholder="请输入客户姓名"
                :class="[
                  'w-full px-3 py-2 border rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500',
                  addCustomerErrors.name ? 'border-red-500' : 'border-gray-300'
                ]"
              >
              <p v-if="addCustomerErrors.name" class="text-red-500 text-xs mt-1">{{ addCustomerErrors.name }}</p>
            </div>
            <div>
              <label class="block text-sm font-medium text-gray-700 mb-1">手机号</label>
              <input
                v-model="addCustomerForm.phone"
                type="text"
                placeholder="请输入手机号（可选）"
                class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
              >
            </div>
            <div>
              <label class="block text-sm font-medium text-gray-700 mb-1">微信号</label>
              <input
                v-model="addCustomerForm.wechat"
                type="text"
                placeholder="请输入微信号（可选）"
                class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
              >
            </div>
            <div>
              <label class="block text-sm font-medium text-gray-700 mb-1">生日</label>
              <div class="customer-date-wrap">
                <input
                  v-model="addCustomerForm.birthday"
                  type="date"
                  class="customer-date-input w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                >
                <span
                  aria-hidden="true"
                  :class="[
                    'customer-date-overlay',
                    addCustomerForm.birthday ? 'customer-date-overlay--value' : 'customer-date-overlay--placeholder'
                  ]"
                >
                  {{ formatBirthdayInputLabel(addCustomerForm.birthday) }}
                </span>
              </div>
            </div>
          </div>
          <div class="px-6 py-4 border-t border-gray-200 flex justify-end gap-3">
            <button
              @click="showAddCustomerDialog = false"
              class="px-4 py-2 border border-gray-300 text-gray-700 rounded-lg hover:bg-gray-50 transition-colors"
            >
              取消
            </button>
            <button
              @click="submitAddCustomer"
              :disabled="loading"
              class="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            >
              确认新增
            </button>
          </div>
        </div>
      </div>
    </Teleport>

    <Teleport to="body">
      <div
        v-if="showDetailDialog"
        class="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50"
        @mousedown="onBackdropMouseDown('customers-detail', $event)"
        @mouseup="onBackdropMouseUp('customers-detail', $event) && (showDetailDialog = false)"
      >
        <div class="bg-white rounded-2xl shadow-xl w-full max-w-5xl mx-4 max-h-[90vh] overflow-y-auto">
          <div class="px-6 py-4 border-b border-gray-200 flex items-center justify-between">
            <div>
              <h3 class="text-lg font-semibold text-gray-800">客户详情</h3>
              <p class="text-sm text-gray-500 mt-1">查看余额和交易记录</p>
            </div>
            <button @click="showDetailDialog = false" class="text-gray-400 hover:text-gray-600 transition-colors">
              <svg xmlns="http://www.w3.org/2000/svg" class="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>

          <div class="p-6">
            <div v-if="detailLoading" class="py-16 text-center text-gray-500">加载详情中...</div>
            <div v-else-if="!selectedCustomerDetail" class="py-16 text-center text-gray-500">暂无客户详情</div>
            <template v-else>
              <div class="grid grid-cols-1 md:grid-cols-5 gap-4 mb-6">
                <div class="bg-gray-50 rounded-lg p-4">
                  <p class="text-xs text-gray-500">客户编号</p>
                  <p class="text-sm font-semibold text-gray-900 mt-1">{{ selectedCustomerDetail.id }}</p>
                </div>
                <div class="bg-gray-50 rounded-lg p-4">
                  <p class="text-xs text-gray-500">客户姓名</p>
                  <p class="text-sm font-semibold text-gray-900 mt-1">{{ selectedCustomerDetail.name }}</p>
                </div>
                <div class="bg-gray-50 rounded-lg p-4">
                  <p class="text-xs text-gray-500">手机号</p>
                  <p class="text-sm font-semibold text-gray-900 mt-1">{{ selectedCustomerDetail.phone || '-' }}</p>
                </div>
                <div class="bg-gray-50 rounded-lg p-4">
                  <p class="text-xs text-gray-500">微信号</p>
                  <p class="text-sm font-semibold text-gray-900 mt-1">{{ selectedCustomerDetail.wechat || '-' }}</p>
                </div>
                <div class="bg-gray-50 rounded-lg p-4">
                  <p class="text-xs text-gray-500">生日</p>
                  <p class="text-sm font-semibold text-gray-900 mt-1">{{ formatDate(selectedCustomerDetail.birthday) }}</p>
                </div>
                <div class="bg-blue-50 rounded-lg p-4">
                  <p class="text-xs text-blue-600">当前余额</p>
                  <p class="text-xl font-bold text-blue-700 mt-1">￥{{ formatAmount(selectedCustomerDetail.balance) }}</p>
                </div>
              </div>

              <div class="flex items-center gap-2 mb-5">
                <button
                  @click="openEditCustomerDialog"
                  class="px-3 py-1.5 bg-blue-600 text-white text-sm rounded-lg hover:bg-blue-700"
                >
                  编辑基础信息
                </button>
                <button
                  @click="openRechargeDialog(selectedCustomerDetail.id)"
                  class="px-3 py-1.5 bg-green-600 text-white text-sm rounded-lg hover:bg-green-700"
                >
                  充值
                </button>
                <button
                  @click="openConsumeDialog(selectedCustomerDetail.id)"
                  class="px-3 py-1.5 bg-orange-600 text-white text-sm rounded-lg hover:bg-orange-700"
                >
                  消费
                </button>
                <button
                  @click="deleteCustomerFromDetail"
                  :disabled="deleteCustomerLoading"
                  class="px-3 py-1.5 bg-red-600 text-white text-sm rounded-lg hover:bg-red-700 disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  删除客户
                </button>
              </div>

              <h4 class="text-sm font-semibold text-gray-700 mb-3">交易记录</h4>
              <div class="border border-gray-200 rounded-lg overflow-x-auto">
                <table class="min-w-full divide-y divide-gray-200">
                  <thead class="bg-gray-50">
                    <tr>
                      <th class="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">类型</th>
                      <th class="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">交易金额/余额</th>
                      <th class="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">说明</th>
                      <th class="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">时间</th>
                    </tr>
                  </thead>
                  <tbody class="bg-white divide-y divide-gray-200">
                    <tr v-if="customerTransactions.length === 0">
                      <td colspan="4" class="px-4 py-8 text-center text-gray-500">暂无交易记录</td>
                    </tr>
                    <tr v-for="transaction in customerTransactions" :key="transaction.id">
                      <td class="px-4 py-2">
                        <span class="inline-flex items-center px-2 py-1 rounded-full text-xs font-medium" :class="getTransactionTypeClass(transaction.type)">
                          {{ getTransactionTypeLabel(transaction.type) }}
                        </span>
                      </td>
                      <td class="px-4 py-2 text-sm">
                        <div :class="transaction.type === 'recharge' ? 'text-green-600' : 'text-slate-700'">
                          交易金额 ￥{{ formatAmount(transaction.amount) }}
                        </div>
                        <div :class="getBalanceDeltaClass(transaction.balanceDelta)" class="text-xs">
                          余额变动 {{ formatSignedAmount(transaction.balanceDelta) }}
                        </div>
                        <div v-if="transaction.type === 'recharge' && transaction.bonusAmount > 0" class="text-xs text-green-600">
                          赠送 +￥{{ formatAmount(transaction.bonusAmount) }}
                        </div>
                      </td>
                      <td class="px-4 py-2 text-sm text-gray-700">
                        <span v-if="transaction.type === 'recharge'">
                          {{ paymentMethods.find((m) => m.value === transaction.paymentMethod)?.label || transaction.paymentMethod || '-' }}
                        </span>
                        <span v-else>{{ transaction.description || '-' }}</span>
                      </td>
                      <td class="px-4 py-2 text-sm text-gray-500">{{ formatDateTime(transaction.createdAt) }}</td>
                    </tr>
                  </tbody>
                </table>
              </div>
            </template>
          </div>
        </div>
      </div>
    </Teleport>

    <Teleport to="body">
      <div
        v-if="showEditCustomerDialog"
        class="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-[60]"
        @mousedown="onBackdropMouseDown('customers-edit', $event)"
        @mouseup="onBackdropMouseUp('customers-edit', $event) && (showEditCustomerDialog = false)"
      >
        <div class="bg-white rounded-xl shadow-xl w-full max-w-md mx-4">
          <div class="px-6 py-4 border-b border-gray-200 flex items-center justify-between">
            <h3 class="text-lg font-semibold text-gray-800">编辑基础信息</h3>
            <button @click="showEditCustomerDialog = false" class="text-gray-400 hover:text-gray-600 transition-colors">
              <svg xmlns="http://www.w3.org/2000/svg" class="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>

          <div class="p-6 space-y-4">
            <div>
              <label class="block text-sm font-medium text-gray-700 mb-1">客户编号</label>
              <input
                :value="editCustomerForm.id"
                type="text"
                disabled
                class="w-full px-3 py-2 border border-gray-300 rounded-lg bg-gray-100 text-gray-500"
              >
            </div>

            <div>
              <label class="block text-sm font-medium text-gray-700 mb-1">当前余额</label>
              <input
                :value="`￥${formatAmount(editCustomerForm.balance)}`"
                type="text"
                disabled
                class="w-full px-3 py-2 border border-gray-300 rounded-lg bg-gray-100 text-gray-500"
              >
            </div>

            <div>
              <label class="block text-sm font-medium text-gray-700 mb-1">客户姓名</label>
              <input
                v-model="editCustomerForm.name"
                type="text"
                placeholder="请输入客户姓名"
                :class="[
                  'w-full px-3 py-2 border rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent',
                  editCustomerErrors.name ? 'border-red-500' : 'border-gray-300'
                ]"
              >
              <p v-if="editCustomerErrors.name" class="text-red-500 text-xs mt-1">
                {{ editCustomerErrors.name }}
              </p>
            </div>

            <div>
              <label class="block text-sm font-medium text-gray-700 mb-1">手机号</label>
              <input
                v-model="editCustomerForm.phone"
                type="text"
                placeholder="请输入手机号（可选）"
                class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
              >
            </div>

            <div>
              <label class="block text-sm font-medium text-gray-700 mb-1">微信号</label>
              <input
                v-model="editCustomerForm.wechat"
                type="text"
                placeholder="请输入微信号（可选）"
                class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
              >
            </div>

            <div>
              <label class="block text-sm font-medium text-gray-700 mb-1">生日</label>
              <input
                v-model="editCustomerForm.birthday"
                type="date"
                class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
              >
            </div>
          </div>

          <div class="px-6 py-4 border-t border-gray-200 flex justify-end gap-3">
            <button
              @click="showEditCustomerDialog = false"
              class="px-4 py-2 border border-gray-300 text-gray-700 rounded-lg hover:bg-gray-50 transition-colors"
            >
              取消
            </button>
            <button
              @click="submitEditCustomer"
              :disabled="editCustomerLoading"
              class="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            >
              保存
            </button>
          </div>
        </div>
      </div>
    </Teleport>

    <Teleport to="body">
      <div
        v-if="showRechargeDialog"
        class="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50"
        @mousedown="onBackdropMouseDown('customers-recharge', $event)"
        @mouseup="onBackdropMouseUp('customers-recharge', $event) && (showRechargeDialog = false)"
      >
        <div class="bg-white rounded-xl shadow-xl w-full max-w-md mx-4">
          <div class="px-6 py-4 border-b border-gray-200 flex items-center justify-between">
            <h3 class="text-lg font-semibold text-gray-800">新增充值</h3>
            <button @click="showRechargeDialog = false" class="text-gray-400 hover:text-gray-600 transition-colors">
              <svg xmlns="http://www.w3.org/2000/svg" class="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>
          <div class="p-6 space-y-4">
            <div>
              <label class="block text-sm font-medium text-gray-700 mb-1">选择客户</label>
              <select
                v-model="rechargeForm.customerId"
                :class="[
                  'w-full px-3 py-2 border rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent',
                  rechargeErrors.customerId ? 'border-red-500' : 'border-gray-300'
                ]"
              >
                <option disabled value="">请选择客户</option>
                <option v-for="customer in validCustomers" :key="customer.id" :value="customer.id">
                  {{ customer.name }} ({{ customer.phone }})
                </option>
              </select>
              <p v-if="rechargeErrors.customerId" class="text-red-500 text-xs mt-1">
                {{ rechargeErrors.customerId }}
              </p>
            </div>

            <div>
              <label class="block text-sm font-medium text-gray-700 mb-1">充值金额</label>
              <div class="relative">
                <span class="absolute left-3 top-1/2 -translate-y-1/2 text-gray-500">￥</span>
                <input
                  v-model="rechargeForm.amount"
                  type="number"
                  step="0.01"
                  min="0"
                  placeholder="0.00"
                  :class="[
                    'w-full pl-8 pr-3 py-2 border rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent',
                    rechargeErrors.amount ? 'border-red-500' : 'border-gray-300'
                  ]"
                >
              </div>
              <p v-if="rechargeErrors.amount" class="text-red-500 text-xs mt-1">
                {{ rechargeErrors.amount }}
              </p>
            </div>

            <div>
              <label class="block text-sm font-medium text-gray-700 mb-1">赠送金额</label>
              <div class="relative">
                <span class="absolute left-3 top-1/2 -translate-y-1/2 text-gray-500">￥</span>
                <input
                  v-model="rechargeForm.bonusAmount"
                  type="number"
                  step="0.01"
                  min="0"
                  :disabled="Boolean(rechargeForm.activityId)"
                  placeholder="0.00"
                  class="w-full pl-8 pr-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent disabled:bg-gray-100 disabled:text-gray-500"
                >
              </div>
              <p v-if="rechargeForm.activityId" class="text-xs text-gray-500 mt-1">已按活动规则自动计算赠送金额。</p>
            </div>

            <div>
              <label class="block text-sm font-medium text-gray-700 mb-1">支付方式</label>
              <select
                v-model="rechargeForm.paymentMethod"
                class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              >
                <option v-for="method in paymentMethods" :key="method.value" :value="method.value">
                  {{ method.label }}
                </option>
              </select>
            </div>

            <div>
              <label class="block text-sm font-medium text-gray-700 mb-1">选择活动（可选）</label>
              <select
                v-model="rechargeForm.activityId"
                class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              >
                <option value="">无</option>
                <option v-for="activity in activities" :key="activity.id" :value="activity.id">
                  {{ activity.name }}（每满￥{{ formatAmount(activity.minRechargeAmount) }}送￥{{ formatAmount(activity.bonusAmount) }}）
                </option>
              </select>
            </div>
          </div>
          <div class="px-6 py-4 border-t border-gray-200 flex justify-end space-x-3">
            <button
              @click="showRechargeDialog = false"
              class="px-4 py-2 border border-gray-300 text-gray-700 rounded-lg hover:bg-gray-50 transition-colors"
            >
              取消
            </button>
            <button
              @click="submitRecharge"
              :disabled="loading"
              class="px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            >
              确认充值
            </button>
          </div>
        </div>
      </div>
    </Teleport>

    <Teleport to="body">
      <div
        v-if="showConsumeDialog"
        class="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50"
        @mousedown="onBackdropMouseDown('customers-consume', $event)"
        @mouseup="onBackdropMouseUp('customers-consume', $event) && (showConsumeDialog = false)"
      >
        <div class="bg-white rounded-xl shadow-xl w-full max-w-3xl mx-4 max-h-[90vh] overflow-y-auto">
          <div class="px-6 py-4 border-b border-gray-200 flex items-center justify-between">
            <h3 class="text-lg font-semibold text-gray-800">新增消费</h3>
            <button @click="showConsumeDialog = false" class="text-gray-400 hover:text-gray-600 transition-colors">
              <svg xmlns="http://www.w3.org/2000/svg" class="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>

          <div class="p-6 space-y-4">
            <div class="grid grid-cols-1 sm:grid-cols-3 gap-2">
              <button
                v-for="mode in consumeModes"
                :key="mode.value"
                @click="consumeMode = mode.value"
                :class="[
                  'px-4 py-2 rounded-lg border text-sm font-medium transition-colors',
                  consumeMode === mode.value
                    ? 'border-blue-500 bg-blue-50 text-blue-700'
                    : 'border-gray-300 bg-white text-gray-700 hover:bg-gray-50'
                ]"
              >
                {{ mode.label }}
              </button>
            </div>

            <div class="bg-blue-50 border border-blue-200 rounded-lg px-4 py-3 text-sm">
              <span v-if="consumeBalanceLoading" class="text-blue-700">正在获取客户余额...</span>
              <span v-else-if="consumeCurrentBalance !== null" class="text-blue-700">
                当前客户余额: <strong>￥{{ formatAmount(consumeCurrentBalance) }}</strong>
              </span>
              <span v-else class="text-blue-700">请选择客户以查看余额</span>
            </div>

            <div v-if="consumeMode === 'manual'" class="space-y-4">
              <div>
                <label class="block text-sm font-medium text-gray-700 mb-1">选择客户</label>
                <select
                  v-model="manualConsumeForm.customerId"
                  :class="[
                    'w-full px-3 py-2 border rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent',
                    manualConsumeErrors.customerId ? 'border-red-500' : 'border-gray-300'
                  ]"
                >
                  <option disabled value="">请选择客户</option>
                  <option v-for="customer in validCustomers" :key="customer.id" :value="customer.id">
                    {{ customer.name }} ({{ customer.phone }})
                  </option>
                </select>
                <p v-if="manualConsumeErrors.customerId" class="text-red-500 text-xs mt-1">
                  {{ manualConsumeErrors.customerId }}
                </p>
              </div>
              <div>
                <label class="block text-sm font-medium text-gray-700 mb-1">消费金额</label>
                <div class="relative">
                  <span class="absolute left-3 top-1/2 -translate-y-1/2 text-gray-500">￥</span>
                  <input
                    v-model="manualConsumeForm.amount"
                    type="number"
                    step="0.01"
                    min="0"
                    placeholder="0.00"
                    :class="[
                      'w-full pl-8 pr-3 py-2 border rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent',
                      manualConsumeErrors.amount ? 'border-red-500' : 'border-gray-300'
                    ]"
                  >
                </div>
                <p v-if="manualConsumeErrors.amount" class="text-red-500 text-xs mt-1">
                  {{ manualConsumeErrors.amount }}
                </p>
              </div>

              <div>
                <label class="block text-sm font-medium text-gray-700 mb-1">描述</label>
                <textarea
                  v-model="manualConsumeForm.description"
                  rows="3"
                  placeholder="请输入消费描述"
                  :class="[
                    'w-full px-3 py-2 border rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent resize-none',
                    manualConsumeErrors.description ? 'border-red-500' : 'border-gray-300'
                  ]"
                ></textarea>
                <p v-if="manualConsumeErrors.description" class="text-red-500 text-xs mt-1">
                  {{ manualConsumeErrors.description }}
                </p>
              </div>

              <div v-if="enabledMiscItems.length > 0" class="space-y-3">
                <div class="flex items-center justify-between">
                  <h4 class="text-sm font-medium text-gray-700">杂项计费（仅整数）</h4>
                  <button
                    type="button"
                    class="text-xs text-blue-600 hover:text-blue-700"
                    @click="syncManualMiscSelections({})"
                  >
                    一键清零
                  </button>
                </div>
                <div class="grid grid-cols-1 md:grid-cols-3 gap-3">
                  <div v-for="item in enabledMiscItems" :key="`manual-misc-${item.id}`">
                    <label class="block text-sm font-medium text-gray-700 mb-1">
                      {{ item.name }}（￥{{ formatAmount(item.unit_price) }}/{{ item.unit_label || '个' }}）
                    </label>
                    <p class="text-xs text-slate-500 mb-1">可用库存：{{ formatMiscStock(item) }}</p>
                    <input
                      v-model.number="manualConsumeForm.miscSelections[item.id]"
                      type="number"
                      min="0"
                      :max="getMiscAvailableQuantity(item)"
                      step="1"
                      class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                      @input="handleMiscSelectionInput(manualConsumeForm.miscSelections, item, $event.target.value)"
                      @change="clampMiscSelection(manualConsumeForm.miscSelections, item)"
                    >
                  </div>
                </div>
                <p v-if="manualConsumeErrors.misc" class="text-red-500 text-xs mt-1">{{ manualConsumeErrors.misc }}</p>
              </div>

              <label class="inline-flex items-center gap-2 text-sm text-gray-700">
                <input
                  v-model="manualConsumeForm.meituanCustomer"
                  type="checkbox"
                  class="h-4 w-4 rounded border-gray-300 text-blue-600 focus:ring-blue-500"
                >
                美团客户（消费金额抽成7%）
              </label>

              <div v-if="manualConsumeForm.meituanCustomer || manualMiscSummary.fee > 0" class="bg-amber-50 border border-amber-200 rounded-lg p-3 text-sm text-amber-800 space-y-1">
                <p>手动金额：￥{{ formatAmount(manualInputAmount) }}</p>
                <p>杂项费用：￥{{ formatAmount(manualMiscSummary.fee) }}</p>
                <p>原始金额：￥{{ formatAmount(manualRawTotal) }}</p>
                <p v-if="manualConsumeForm.meituanCustomer">美团抽成：-￥{{ formatAmount(manualMeituanDeduction) }}</p>
                <p class="font-semibold">结算金额：￥{{ formatAmount(manualFinalAmount) }}</p>
              </div>
            </div>

            <div v-else-if="consumeMode === 'auto'" class="space-y-4">
              <div>
                <label class="block text-sm font-medium text-gray-700 mb-1">选择客户</label>
                <select
                  v-model="autoConsumeForm.customerId"
                  :class="[
                    'w-full px-3 py-2 border rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent',
                    autoConsumeErrors.customerId ? 'border-red-500' : 'border-gray-300'
                  ]"
                >
                  <option disabled value="">请选择客户</option>
                  <option v-for="customer in validCustomers" :key="customer.id" :value="customer.id">
                    {{ customer.name }} ({{ customer.phone }})
                  </option>
                </select>
                <p v-if="autoConsumeErrors.customerId" class="text-red-500 text-xs mt-1">{{ autoConsumeErrors.customerId }}</p>
              </div>

              <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                  <label class="block text-sm font-medium text-gray-700 mb-1">计费类型</label>
                  <select v-model="autoConsumeForm.billingType" class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500">
                    <option value="limited">限时计费</option>
                    <option value="weekday">工作日计费</option>
                    <option value="weekend">周末计费</option>
                  </select>
                </div>

                <div v-if="autoConsumeForm.billingType === 'limited'">
                  <label class="block text-sm font-medium text-gray-700 mb-1">时长</label>
                  <select v-model="autoConsumeForm.duration" class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500">
                    <option value="1">1小时</option>
                    <option value="2">2小时</option>
                  </select>
                </div>

                <div v-if="autoConsumeForm.billingType === 'weekday'">
                  <label class="block text-sm font-medium text-gray-700 mb-1">工作日方案</label>
                  <select v-model="autoConsumeForm.weekdayType" class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500">
                    <option v-for="item in weekdayTypeOptions" :key="item.value" :value="item.value">
                      {{ item.label }}
                    </option>
                  </select>
                </div>

                <div v-if="autoConsumeForm.billingType === 'weekend'">
                  <label class="block text-sm font-medium text-gray-700 mb-1">周末方案</label>
                  <select v-model="autoConsumeForm.weekendType" class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500">
                    <option v-for="item in weekendTypeOptions" :key="item.value" :value="item.value">
                      {{ item.label }}
                    </option>
                  </select>
                </div>

                <div v-if="autoConsumeForm.billingType === 'limited'">
                  <label class="block text-sm font-medium text-gray-700 mb-1">超时分钟</label>
                  <input v-model.number="autoConsumeForm.overtimeMinutes" type="number" min="0" class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500">
                </div>
              </div>

              <div class="grid grid-cols-1 md:grid-cols-4 gap-4">
                <div>
                  <label class="block text-sm font-medium text-gray-700 mb-1">大图数量</label>
                  <input v-model.number="autoConsumeForm.largeImages" type="number" min="0" class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500">
                </div>
                <div>
                  <label class="block text-sm font-medium text-gray-700 mb-1">超量小图</label>
                  <input v-model.number="autoConsumeForm.extraSmallImages" type="number" min="0" class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500">
                </div>
                <div>
                  <label class="block text-sm font-medium text-gray-700 mb-1">超量大图</label>
                  <input v-model.number="autoConsumeForm.extraLargeImages" type="number" min="0" class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500">
                </div>
                <div>
                  <label class="block text-sm font-medium text-gray-700 mb-1">附加费用</label>
                  <input v-model.number="autoConsumeForm.additionalFee" type="number" min="0" step="0.01" class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500">
                </div>
              </div>

              <div v-if="enabledMiscItems.length > 0" class="space-y-3">
                <div class="flex items-center justify-between">
                  <h4 class="text-sm font-medium text-gray-700">杂项计费（仅整数）</h4>
                  <button
                    type="button"
                    class="text-xs text-blue-600 hover:text-blue-700"
                    @click="syncAutoMiscSelections({})"
                  >
                    一键清零
                  </button>
                </div>
                <div class="grid grid-cols-1 md:grid-cols-3 gap-3">
                  <div v-for="item in enabledMiscItems" :key="item.id">
                    <label class="block text-sm font-medium text-gray-700 mb-1">
                      {{ item.name }}（￥{{ formatAmount(item.unit_price) }}/{{ item.unit_label || '个' }}）
                    </label>
                    <p class="text-xs text-slate-500 mb-1">可用库存：{{ formatMiscStock(item) }}</p>
                    <input
                      v-model.number="autoConsumeForm.miscSelections[item.id]"
                      type="number"
                      min="0"
                      :max="getMiscAvailableQuantity(item)"
                      step="1"
                      class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                      @input="handleMiscSelectionInput(autoConsumeForm.miscSelections, item, $event.target.value)"
                      @change="clampMiscSelection(autoConsumeForm.miscSelections, item)"
                    >
                  </div>
                </div>
              </div>

              <div>
                <label class="block text-sm font-medium text-gray-700 mb-1">备注</label>
                <textarea v-model="autoConsumeForm.notes" rows="2" class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 resize-none" placeholder="可选"></textarea>
              </div>

              <label class="inline-flex items-center gap-2 text-sm text-gray-700">
                <input
                  v-model="autoConsumeForm.meituanCustomer"
                  type="checkbox"
                  class="h-4 w-4 rounded border-gray-300 text-blue-600 focus:ring-blue-500"
                >
                美团客户（基础费用抽成7%）
              </label>

              <div class="bg-green-50 border border-green-200 rounded-lg p-4 text-sm text-green-800 space-y-1">
                <p>计费类型: {{ getBillingTypeLabel(autoConsumeForm.billingType) }}</p>
                <p>基础费用: ￥{{ formatAmount(autoConsumePreview.baseFee) }}</p>
                <p>超时费用: ￥{{ formatAmount(autoConsumePreview.overtimeFee) }}</p>
                <p>耗材费用: ￥{{ formatAmount(autoConsumePreview.materialFee) }}</p>
                <p>杂项费用: ￥{{ formatAmount(autoConsumePreview.miscFee) }}</p>
                <p>附加费用: ￥{{ formatAmount(autoConsumePreview.additionalFee) }}</p>
                <p v-if="autoConsumeForm.meituanCustomer">美团抽成: -￥{{ formatAmount(autoMeituanDeduction) }}</p>
                <p class="font-semibold text-base">
                  结算金额: ￥{{ formatAmount(autoConsumeForm.meituanCustomer ? autoFinalAmount : autoConsumePreview.total) }}
                </p>
              </div>
              <p v-if="autoConsumeErrors.total" class="text-red-500 text-xs mt-1">{{ autoConsumeErrors.total }}</p>
              <p v-if="autoConsumeErrors.misc" class="text-red-500 text-xs mt-1">{{ autoConsumeErrors.misc }}</p>
            </div>

            <div v-else class="space-y-4">
              <div>
                <label class="block text-sm font-medium text-gray-700 mb-1">选择客户</label>
                <select v-model="timerConsumeForm.customerId" :class="['w-full px-3 py-2 border rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500', timerConsumeErrors.customerId ? 'border-red-500' : 'border-gray-300']">
                  <option disabled value="">请选择客户</option>
                  <option v-for="customer in validCustomers" :key="customer.id" :value="customer.id">{{ customer.name }} ({{ customer.phone }})</option>
                </select>
                <p v-if="timerConsumeErrors.customerId" class="text-red-500 text-xs mt-1">{{ timerConsumeErrors.customerId }}</p>
              </div>

              <div>
                <label class="block text-sm font-medium text-gray-700 mb-1">计时类型</label>
                <select v-model="timerConsumeForm.timerType" :class="['w-full px-3 py-2 border rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500', timerConsumeErrors.timerType ? 'border-red-500' : 'border-gray-300']">
                  <option v-for="item in timerTypeOptions" :key="item.value" :value="item.value">
                    {{ item.label }}
                  </option>
                </select>
                <p v-if="timerConsumeErrors.timerType" class="text-red-500 text-xs mt-1">{{ timerConsumeErrors.timerType }}</p>
              </div>

              <div>
                <label class="block text-sm font-medium text-gray-700 mb-1">套餐方案</label>
                <select
                  v-model="timerConsumeForm.packagePlan"
                  :class="[
                    'w-full px-3 py-2 border rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500',
                    timerConsumeErrors.packagePlan ? 'border-red-500' : 'border-gray-300'
                  ]"
                >
                  <option v-for="item in timerPackagePlanOptions" :key="item.value" :value="item.value">
                    {{ item.label }}
                  </option>
                </select>
                <p v-if="timerConsumeErrors.packagePlan" class="text-red-500 text-xs mt-1">{{ timerConsumeErrors.packagePlan }}</p>
              </div>

              <div class="grid grid-cols-1 md:grid-cols-3 gap-4">
                <div>
                  <label class="block text-sm font-medium text-gray-700 mb-1">大图数量</label>
                  <input v-model.number="timerConsumeForm.largeImages" type="number" min="0" class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500">
                </div>
                <div>
                  <label class="block text-sm font-medium text-gray-700 mb-1">超量小图</label>
                  <input v-model.number="timerConsumeForm.extraSmallImages" type="number" min="0" class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500">
                </div>
                <div>
                  <label class="block text-sm font-medium text-gray-700 mb-1">超量大图</label>
                  <input v-model.number="timerConsumeForm.extraLargeImages" type="number" min="0" class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500">
                </div>
              </div>

              <div v-if="enabledMiscItems.length > 0" class="space-y-3">
                <div class="flex items-center justify-between">
                  <h4 class="text-sm font-medium text-gray-700">杂项计费（仅整数）</h4>
                  <button
                    type="button"
                    class="text-xs text-blue-600 hover:text-blue-700"
                    @click="syncTimerMiscSelections({})"
                  >
                    一键清零
                  </button>
                </div>
                <div class="grid grid-cols-1 md:grid-cols-3 gap-3">
                  <div v-for="item in enabledMiscItems" :key="`timer-misc-${item.id}`">
                    <label class="block text-sm font-medium text-gray-700 mb-1">
                      {{ item.name }}（￥{{ formatAmount(item.unit_price) }}/{{ item.unit_label || '个' }}）
                    </label>
                    <p class="text-xs text-slate-500 mb-1">可用库存：{{ formatMiscStock(item) }}</p>
                    <input
                      v-model.number="timerConsumeForm.miscSelections[item.id]"
                      type="number"
                      min="0"
                      :max="getMiscAvailableQuantity(item)"
                      step="1"
                      class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                      @input="handleMiscSelectionInput(timerConsumeForm.miscSelections, item, $event.target.value)"
                      @change="clampMiscSelection(timerConsumeForm.miscSelections, item)"
                    >
                  </div>
                </div>
                <div class="bg-blue-50 border border-blue-200 rounded-lg p-3 text-sm text-blue-800">
                  预计杂项费用：￥{{ formatAmount(timerMiscSummary.fee) }}
                </div>
                <p v-if="timerConsumeErrors.misc" class="text-red-500 text-xs mt-1">{{ timerConsumeErrors.misc }}</p>
              </div>

              <div>
                <label class="block text-sm font-medium text-gray-700 mb-1">备注</label>
                <textarea v-model="timerConsumeForm.notes" rows="2" class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 resize-none" placeholder="开始计时前的备注"></textarea>
              </div>

              <div class="bg-amber-50 border border-amber-200 rounded-lg p-4 text-sm text-amber-800">
                计时开始后，请前往“正在计时”页面完成结算。
              </div>
            </div>
          </div>

          <div class="px-6 py-4 border-t border-gray-200 flex justify-end space-x-3">
            <button @click="showConsumeDialog = false" class="px-4 py-2 border border-gray-300 text-gray-700 rounded-lg hover:bg-gray-50 transition-colors">取消</button>
            <button
              @click="submitConsumeByMode"
              :disabled="loading"
              class="px-4 py-2 bg-orange-600 text-white rounded-lg hover:bg-orange-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {{ consumeSubmitLabel }}
            </button>
          </div>
        </div>
      </div>
    </Teleport>
  </div>
</template>

<style scoped>
.customer-date-wrap {
  position: relative;
}

.customer-date-overlay {
  position: absolute;
  left: 0.75rem;
  top: 50%;
  transform: translateY(-50%);
  pointer-events: none;
  font-size: 0.875rem;
  line-height: 1.25rem;
  font-variant-numeric: tabular-nums;
  letter-spacing: 0.01em;
}

.customer-date-overlay--placeholder {
  color: #94a3b8;
}

.customer-date-overlay--value {
  color: #0f172a;
  font-weight: 500;
}

.customer-date-input {
  color: transparent;
  -webkit-text-fill-color: transparent;
  font-size: 0.875rem;
  line-height: 1.25rem;
  font-variant-numeric: tabular-nums;
}

.customer-date-input::-webkit-datetime-edit {
  color: transparent;
  letter-spacing: 0.01em;
}

.customer-date-input::-webkit-datetime-edit-text {
  color: transparent;
  padding: 0;
}

.customer-date-input::-webkit-calendar-picker-indicator {
  opacity: 0.82;
}
</style>


