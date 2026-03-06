<script setup>
import { ref, reactive, computed, onMounted, onUnmounted, watch, nextTick } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import api from '@/api'
import { formatServerDateTime, toServerDate } from '@/utils/dateTime'
import { useBackdropClose } from '@/utils/modalBackdrop'
import TimerConsumeDialog from '@/components/timers/TimerConsumeDialog.vue'
import {
  createTimerConsumeForm,
  validateTimerConsumeForm as validateSharedTimerConsumeForm,
  buildTimerConsumeRequestPayload
} from '@/utils/timerConsume'
import {
  normalizeBillingRules,
  calculateConsumptionAmount,
  buildConsumptionDescription,
  getBillingTypeLabel,
  calculateMeituanDeduction,
  applyDeduction
} from '@/utils/consumptionCalculator'

const route = useRoute()
const router = useRouter()
const { onBackdropMouseDown, onBackdropMouseUp } = useBackdropClose()
const DEFAULT_OVERTIME_RATE_PER_MINUTE = 0.5
const OVERTIME_START_HOUR = 19
const OVERTIME_START_MINUTE = 30
const DAY_MS = 24 * 60 * 60 * 1000

const loading = ref(false)
const cancellingTransactionId = ref('')
const editingTransactionId = ref('')
const transactions = ref([])
const customers = ref([])
const activities = ref([])
const total = ref(0)
const currentPage = ref(1)
const pageSize = ref(15)

const filterForm = reactive({
  type: '',
  startDate: '',
  endDate: '',
  customerKeyword: ''
})

const showRechargeDialog = ref(false)
const showConsumeDialog = ref(false)
const showTimerEditDialog = ref(false)
const showDetailDialog = ref(false)
const showCancelConfirmDialog = ref(false)
const selectedTransaction = ref(null)
const timerEditTargetTransaction = ref(null)
const timerEditStartTimestamp = ref(null)
const cancelTargetTransaction = ref(null)
const cancelConfirmButtonRef = ref(null)
const timerEditAmountInputRef = ref(null)
const rechargeCustomerSelectRef = ref(null)
const manualConsumeCustomerSelectRef = ref(null)
const detailCloseButtonRef = ref(null)
const dialogTriggerStack = ref([])

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
  weekdayType: 'singleUnlimited',
  weekendType: 'singleUnlimited',
  overtimeMinutes: 0,
  largeImages: 0,
  extraSmallImages: 0,
  extraLargeImages: 0,
  miscSelections: {},
  additionalFee: 0,
  notes: '',
  meituanCustomer: false
})

const timerConsumeForm = reactive(createTimerConsumeForm())
const timerEditForm = reactive({
  elapsedMinutes: 60,
  billingType: 'limited',
  duration: '1',
  weekdayType: 'singleUnlimited',
  weekendType: 'singleUnlimited',
  overtimeMinutes: 0,
  largeImages: 0,
  extraSmallImages: 0,
  extraLargeImages: 0,
  miscSelections: {},
  additionalFee: 0,
  applyOvertimeFee: false,
  overtimeFeeMinutes: 0,
  notes: '',
  meituanCustomer: false
})

const rechargeErrors = ref({})
const manualConsumeErrors = ref({})
const autoConsumeErrors = ref({})
const timerConsumeErrors = ref({})
const timerEditErrors = ref({})
const feedback = reactive({
  tone: 'info',
  message: ''
})

const consumeCurrentBalance = ref(null)
const consumeBalanceLoading = ref(false)
const billingRules = ref(normalizeBillingRules())
let feedbackTimer = null

function getTimerEditConfiguredOvertimeRate() {
  const configuredRate = Number(billingRules.value?.overtime?.ratePerMinute)
  if (!Number.isFinite(configuredRate) || configuredRate < 0) {
    return DEFAULT_OVERTIME_RATE_PER_MINUTE
  }
  return configuredRate
}

const transactionTypes = [
  { value: '', label: '全部' },
  { value: 'recharge', label: '充值' },
  { value: 'consumption', label: '消费' },
  { value: 'bead_purchase', label: '买豆支出' }
]

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

const pageSizeOptions = [5, 10, 15, 20, 25, 30, 35, 40, 45, 50]
const totalPages = computed(() => Math.ceil(total.value / pageSize.value) || 1)
const feedbackClass = computed(() => {
  if (feedback.tone === 'success') return 'border-emerald-200 bg-emerald-50 text-emerald-800'
  if (feedback.tone === 'error') return 'border-rose-200 bg-rose-50 text-rose-800'
  return 'border-sky-200 bg-sky-50 text-sky-800'
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

const customerMap = computed(() => {
  const map = new Map()
  customers.value.forEach((customer) => map.set(customer.id, customer))
  return map
})

const activeConsumeCustomerId = computed(() => {
  if (consumeMode.value === 'manual') return manualConsumeForm.customerId
  if (consumeMode.value === 'auto') return autoConsumeForm.customerId
  return timerConsumeForm.customerId
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

const timerEditOvertimeRatePerMinute = computed(() => getTimerEditConfiguredOvertimeRate())

const timerEditAutoOvertimeMinutes = computed(() => {
  const startMs = Number(timerEditStartTimestamp.value)
  const elapsedMinutes = Math.max(0, Math.floor(Number(timerEditForm.elapsedMinutes) || 0))
  if (elapsedMinutes <= 0) return 0

  if (!Number.isFinite(startMs)) {
    return Math.max(0, Math.floor(Number(timerEditForm.overtimeFeeMinutes) || 0))
  }

  const endMs = startMs + (elapsedMinutes * 60 * 1000)
  return calculateOvertimeMinutesByRange(startMs, endMs)
})

const timerEditOvertimeFee = computed(() => {
  if (!timerEditForm.applyOvertimeFee) return 0
  const minutes = timerEditAutoOvertimeMinutes.value
  const rate = timerEditOvertimeRatePerMinute.value
  return Math.round(((minutes * rate) + Number.EPSILON) * 100) / 100
})

const timerEditTotalAdditionalFee = computed(() => {
  const manualAdditionalFee = Math.max(0, Number(timerEditForm.additionalFee) || 0)
  return Math.round(((manualAdditionalFee + timerEditOvertimeFee.value) + Number.EPSILON) * 100) / 100
})

const timerEditPreview = computed(() =>
  calculateConsumptionAmount(
    {
      billingType: timerEditForm.billingType,
      duration: timerEditForm.duration,
      weekdayType: timerEditForm.weekdayType,
      weekendType: timerEditForm.weekendType,
      overtimeMinutes: timerEditForm.overtimeMinutes,
      largeImages: timerEditForm.largeImages,
      extraSmallImages: timerEditForm.extraSmallImages,
      extraLargeImages: timerEditForm.extraLargeImages,
      miscSelections: timerEditForm.miscSelections,
      additionalFee: timerEditTotalAdditionalFee.value
    },
    billingRules.value
  )
)

const timerEditMeituanDeduction = computed(() => (
  timerEditForm.meituanCustomer
    ? calculateMeituanDeduction(timerEditPreview.value.baseFee)
    : 0
))

const timerEditFinalAmount = computed(() =>
  applyDeduction(timerEditPreview.value.total, timerEditMeituanDeduction.value)
)

const timerEditEndTimestamp = computed(() => {
  const startMs = Number(timerEditStartTimestamp.value)
  if (!Number.isFinite(startMs)) return null
  const elapsedMinutes = Math.max(0, Math.floor(Number(timerEditForm.elapsedMinutes) || 0))
  return startMs + (elapsedMinutes * 60 * 1000)
})

const timerEditStartTimeLabel = computed(() => formatTimestampLabel(timerEditStartTimestamp.value))
const timerEditEndTimeLabel = computed(() => formatTimestampLabel(timerEditEndTimestamp.value))

const consumeSubmitLabel = computed(() => {
  if (consumeMode.value === 'manual') return '确认消费'
  if (consumeMode.value === 'auto') return '确认结算'
  return '开始计时'
})

const normalizeCustomer = (customer = {}) => ({
  ...customer,
  createdAt: customer.createdAt ?? customer.created_at ?? null,
  updatedAt: customer.updatedAt ?? customer.updated_at ?? null,
  balance: customer.balance ?? customer.current_balance ?? 0
})

const normalizeActivity = (activity = {}) => ({
  ...activity,
  startDate: activity.startDate ?? activity.start_date ?? null,
  endDate: activity.endDate ?? activity.end_date ?? null,
  rechargeAmount: activity.rechargeAmount ?? activity.recharge_amount ?? activity.recharge ?? activity.minRechargeAmount ?? activity.min_amount ?? null,
  bonusAmount: activity.bonusAmount ?? activity.bonus_amount ?? activity.bonus_rate ?? null,
  minRechargeAmount: activity.minRechargeAmount ?? activity.min_amount ?? null
})

const normalizeTransaction = (transaction = {}) => ({
  ...transaction,
  type: transaction.type === 'consume' ? 'consumption' : transaction.type,
  customerId: transaction.customerId ?? transaction.customer_id ?? '',
  customerName: transaction.customerName ?? transaction.customer_name ?? '',
  customerPhone: transaction.customerPhone ?? transaction.customer_phone ?? '',
  customerWechat: transaction.customerWechat ?? transaction.customer_wechat ?? '',
  bonusAmount: transaction.bonusAmount ?? transaction.bonus_amount ?? 0,
  paymentMethod: transaction.paymentMethod ?? transaction.payment_method ?? '',
  activityId: transaction.activityId ?? transaction.activity_id ?? null,
  createdAt: transaction.createdAt ?? transaction.created_at ?? transaction.transaction_time ?? null,
  operatorName: transaction.operatorName ?? transaction.operator_name ?? '',
  status: transaction.status ?? 'completed',
  miscSelections: transaction.miscSelections ?? transaction.misc_selections ?? {}
})

const filteredCustomers = computed(() => {
  if (!filterForm.customerKeyword) return customers.value
  const keyword = filterForm.customerKeyword.toLowerCase()
  return customers.value.filter((customer) =>
    customer.name?.toLowerCase().includes(keyword) ||
    customer.phone?.includes(keyword) ||
    customer.id?.toLowerCase().includes(keyword)
  )
})

const validCustomers = computed(() =>
  customers.value.filter((customer) => {
    const id = String(customer?.id ?? '').trim()
    return id.length > 0
  })
)

function formatAmount(amount) {
  return parseFloat(amount || 0).toFixed(2)
}

function isTimerConsumptionTransaction(transaction = {}) {
  if (transaction?.type !== 'consumption') return false
  const description = String(transaction?.description || '').trim()
  return description.startsWith('计时消费')
}

function canEditTimerConsumptionTransaction(transaction = {}) {
  const normalized = normalizeTransaction(transaction)
  return Boolean(normalized?.id) && isTimerConsumptionTransaction(normalized)
}

const MISC_MARKER_PATTERN = /\s*\[\[MISC_B64:[A-Za-z0-9_-]+\]\]\s*$/
const TIMER_OVERTIME_NOTE_PATTERN = /加班费用[¥￥]\s*(\d+(?:\.\d+)?)\s*[（(]\s*(\d+)\s*分钟\s*[，,]\s*[¥￥]\s*(\d+(?:\.\d+)?)\s*\/\s*分钟\s*[）)]/
const TIMER_OVERTIME_CANCEL_NOTE_PATTERN = /已取消加班费用[（(]\s*(\d+)\s*分钟\s*[，,]\s*原[¥￥]\s*(\d+(?:\.\d+)?)\s*[）)]/

function stripMiscMarkerFromDescription(description = '') {
  return String(description || '').replace(MISC_MARKER_PATTERN, '').trim()
}

function splitTimerDescriptionSections(description = '') {
  return stripMiscMarkerFromDescription(description)
    .split(/\s+-\s+/)
    .map((segment) => String(segment || '').trim())
    .filter(Boolean)
}

function parseElapsedMinutesFromDescription(description = '') {
  const text = stripMiscMarkerFromDescription(description)
  const matched = text.match(/(\d+)\s*小时\s*(\d+)\s*分钟/)
  if (!matched) return 60
  const hours = Number.parseInt(matched[1], 10)
  const minutes = Number.parseInt(matched[2], 10)
  if (!Number.isFinite(hours) || !Number.isFinite(minutes) || hours < 0 || minutes < 0) return 60
  return (hours * 60) + minutes
}

function inferTimerBillingTypeFromDescription(description = '') {
  const text = stripMiscMarkerFromDescription(description)
  if (/计时消费[（(]工作日[）)]/.test(text)) return 'weekday'
  if (/计时消费[（(]周末[）)]/.test(text)) return 'weekend'
  return 'limited'
}

function escapeRegex(rawText = '') {
  return String(rawText || '').replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
}

function parseTimerDetailSectionFromDescription(description = '') {
  const sections = splitTimerDescriptionSections(description)
  if (sections.length <= 1) return ''
  return sections
    .slice(1)
    .filter((segment) => !/^\d+\s*小时\s*\d+\s*分钟$/.test(segment))
    .filter((segment) => !segment.startsWith('备注:'))
    .join('，')
}

function inferTimerDurationFromDescription(detailSection = '', elapsedMinutes = 60) {
  const detail = String(detailSection || '')
  if (detail.includes('限时2小时')) return '2'
  if (detail.includes('限时1小时')) return '1'
  return Math.max(0, Math.floor(Number(elapsedMinutes) || 0)) < 90 ? '1' : '2'
}

function inferTimerOvertimeMinutesFromDescription(detailSection = '', elapsedMinutes = 60, duration = '1') {
  const detail = String(detailSection || '')
  const matched = detail.match(/超时\s*(\d+)\s*分钟/)
  if (matched) {
    const minutes = Number.parseInt(matched[1], 10)
    if (Number.isFinite(minutes) && minutes >= 0) return minutes
  }

  const totalMinutes = Math.max(0, Math.floor(Number(elapsedMinutes) || 0))
  if (duration === '2') return Math.max(0, totalMinutes - 120)
  if (totalMinutes <= 60) return 0
  if (totalMinutes < 90) return totalMinutes - 60
  if (totalMinutes <= 120) return 0
  return totalMinutes - 120
}

function inferTimerWeekdayTypeFromDetail(detailSection = '') {
  const detail = String(detailSection || '')
  if (detail.includes('工作日双人不限时不限板')) return 'doubleUnlimited'
  if (detail.includes('工作日单人不限时限板')) return 'singleLimited'
  return 'singleUnlimited'
}

function inferTimerWeekendTypeFromDetail(detailSection = '') {
  const detail = String(detailSection || '')
  if (detail.includes('周末双人不限时不限板')) return 'doubleUnlimited'
  if (detail.includes('周末单人不限时限板')) return 'singleLimited'
  return 'singleUnlimited'
}

function parseCountFromDetail(detailSection = '', label = '') {
  const escapedLabel = escapeRegex(label)
  const matched = String(detailSection || '').match(new RegExp(`${escapedLabel}\\s*(\\d+)\\s*张`))
  if (!matched) return 0
  const count = Number.parseInt(matched[1], 10)
  return Number.isFinite(count) && count >= 0 ? count : 0
}

function parseAdditionalFeeFromDetail(detailSection = '') {
  const matched = String(detailSection || '').match(/附加费用[¥￥]\s*(\d+(?:\.\d+)?)/)
  if (!matched) return 0
  const fee = Number.parseFloat(matched[1])
  return Number.isFinite(fee) && fee >= 0 ? fee : 0
}

function inferTimerNotesStateFromDescription(description = '') {
  const sections = splitTimerDescriptionSections(description)
  const noteSection = sections.find((segment) => segment.startsWith('备注:')) || ''
  const rawNotes = noteSection.replace(/^备注:\s*/, '').trim()
  const overtimeAppliedMatch = rawNotes.match(TIMER_OVERTIME_NOTE_PATTERN)
  const overtimeCanceledMatch = rawNotes.match(TIMER_OVERTIME_CANCEL_NOTE_PATTERN)

  let applyOvertimeFee = false
  let overtimeFee = 0
  let overtimeFeeMinutes = 0
  let overtimeRatePerMinute = 0
  if (overtimeAppliedMatch) {
    applyOvertimeFee = true
    overtimeFee = Math.max(0, Number.parseFloat(overtimeAppliedMatch[1]) || 0)
    overtimeFeeMinutes = Math.max(0, Number.parseInt(overtimeAppliedMatch[2], 10) || 0)
    overtimeRatePerMinute = Math.max(0, Number.parseFloat(overtimeAppliedMatch[3]) || 0)
  } else if (overtimeCanceledMatch) {
    applyOvertimeFee = false
    overtimeFee = Math.max(0, Number.parseFloat(overtimeCanceledMatch[2]) || 0)
    overtimeFeeMinutes = Math.max(0, Number.parseInt(overtimeCanceledMatch[1], 10) || 0)
  }

  const meituanPattern = /(^|[；;，,\s])美团客户[（(][^）)]*[）)]/g
  const meituanCustomer = rawNotes.includes('美团客户') || sections.join('；').includes('美团客户')
  const notes = rawNotes
    .replace(TIMER_OVERTIME_NOTE_PATTERN, '')
    .replace(TIMER_OVERTIME_CANCEL_NOTE_PATTERN, '')
    .replace(meituanPattern, '$1')
    .replace(/[；;，,\s]+$/g, '')
    .replace(/^[；;，,\s]+/g, '')
    .trim()

  return {
    notes,
    meituanCustomer,
    applyOvertimeFee,
    overtimeFee,
    overtimeFeeMinutes,
    overtimeRatePerMinute
  }
}

function calculateOvertimeMinutesByRange(startMs, endMs) {
  if (!Number.isFinite(startMs) || !Number.isFinite(endMs) || endMs <= startMs) return 0

  let cursor = startMs
  let overtimeMs = 0

  while (cursor < endMs) {
    const dayStart = new Date(cursor)
    dayStart.setHours(0, 0, 0, 0)

    const dayStartMs = dayStart.getTime()
    const nextDayStartMs = dayStartMs + DAY_MS
    const segmentEnd = Math.min(endMs, nextDayStartMs)

    const overtimeStart = new Date(dayStartMs)
    overtimeStart.setHours(OVERTIME_START_HOUR, OVERTIME_START_MINUTE, 0, 0)
    const overtimeStartMs = overtimeStart.getTime()

    const overlapStart = Math.max(cursor, overtimeStartMs)
    if (segmentEnd > overlapStart) {
      overtimeMs += segmentEnd - overlapStart
    }

    cursor = segmentEnd
  }

  return Math.floor(overtimeMs / 60000)
}

function resolveTimerEditStartTimestamp(transaction = null, elapsedMinutes = 0) {
  const settledDate = toServerDate(transaction?.createdAt ?? transaction?.created_at ?? transaction?.transaction_time)
  if (!settledDate) return null
  const elapsedMs = Math.max(0, Math.floor(Number(elapsedMinutes) || 0)) * 60 * 1000
  return settledDate.getTime() - elapsedMs
}

function formatTimestampLabel(timestampMs) {
  const value = Number(timestampMs)
  if (!Number.isFinite(value)) return '-'
  return new Date(value).toLocaleString('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: false
  })
}

function formatFilterDateLabel(value) {
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

  return `${yearNum}年${monthNum}月${dayNum}日`
}

function applyTimerConsumeForm(nextForm = {}) {
  Object.assign(timerConsumeForm, createTimerConsumeForm(), nextForm)
}


function clearFeedbackTimer() {
  if (!feedbackTimer) return
  window.clearTimeout(feedbackTimer)
  feedbackTimer = null
}

function showFeedback(tone, message, { persist = false } = {}) {
  feedback.tone = tone
  feedback.message = message
  clearFeedbackTimer()
  if (!persist) {
    feedbackTimer = window.setTimeout(() => {
      feedback.message = ''
      feedbackTimer = null
    }, 4500)
  }
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

function syncTimerEditMiscSelections(seed = null) {
  const source = seed !== null ? seed : timerEditForm.miscSelections
  timerEditForm.miscSelections = createMiscSelectionMap(source)
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

function collectTimerEditMiscErrors(selectionMap = {}) {
  return collectMiscSelectionErrors(selectionMap)
}

function rememberDialogTrigger() {
  const activeElement = document.activeElement
  if (
    activeElement instanceof HTMLElement &&
    activeElement !== document.body &&
    activeElement !== document.documentElement
  ) {
    const stack = dialogTriggerStack.value
    const lastElement = stack[stack.length - 1]
    if (lastElement !== activeElement) {
      stack.push(activeElement)
    }
  }
}

function restoreDialogTrigger() {
  const stack = dialogTriggerStack.value
  while (stack.length > 0) {
    const element = stack.pop()
    if (element && document.contains(element)) {
      element.focus()
      return
    }
  }
}

async function fetchTransactions() {
  loading.value = true
  try {
    const params = {
      page: currentPage.value,
      page_size: pageSize.value,
      type: filterForm.type || undefined,
      date_start: filterForm.startDate || undefined,
      date_end: filterForm.endDate || undefined
    }

    const keyword = filterForm.customerKeyword.trim()
    if (keyword) {
      const matchedCustomer = customers.value.find(
        (customer) => customer.id === keyword || customer.name === keyword || customer.phone === keyword
      )
      if (matchedCustomer) {
        params.customer_id = matchedCustomer.id
      }
    }

    const response = await api.get('/transactions', { params })
    const payload = response?.data || response || {}
    const items = Array.isArray(payload.items) ? payload.items : []
    const pagination = payload.pagination || {}

    transactions.value = items.map(normalizeTransaction)
    total.value = pagination.total ?? items.length
  } catch (error) {
    console.error('Failed to fetch transactions:', error)
    transactions.value = []
    total.value = 0
    showFeedback('error', '获取交易记录失败，请稍后重试。')
  } finally {
    loading.value = false
  }
}

async function fetchCustomers() {
  try {
    const response = await api.get('/customers', { params: { page: 1, page_size: 1000 } })
    const payload = response?.data || response || {}
    const items = Array.isArray(payload.items) ? payload.items : []
    customers.value = items.map(normalizeCustomer)
  } catch (error) {
    console.error('Failed to fetch customers:', error)
    customers.value = []
  }
}

async function refreshCustomersAndResolveCustomerId(customerId = '') {
  await fetchCustomers()
  if (!customerId) return ''
  return validCustomers.value.some((customer) => customer.id === customerId) ? customerId : ''
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
    syncTimerEditMiscSelections()
  } catch (error) {
    console.error('Failed to fetch billing rules:', error)
    billingRules.value = normalizeBillingRules()
    syncManualMiscSelections()
    syncAutoMiscSelections()
    syncTimerMiscSelections()
    syncTimerEditMiscSelections()
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

  return 0
}

function applyRechargeActivityPreset(activityId) {
  if (!activityId) {
    if (!rechargeForm.bonusAmount) rechargeForm.bonusAmount = '0'
    return
  }

  const activity = activities.value.find((item) => item.id === activityId)
  if (!activity) return

  const minRecharge = parseFloat(activity.minRechargeAmount ?? activity.rechargeAmount)
  const currentAmount = parseFloat(rechargeForm.amount)
  if (!Number.isNaN(minRecharge) && minRecharge > 0 && (Number.isNaN(currentAmount) || currentAmount <= 0)) {
    rechargeForm.amount = String(minRecharge)
  }

  const calculatedBonus = calculateActivityBonus(activity, rechargeForm.amount)
  rechargeForm.bonusAmount = String(calculatedBonus)
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
  autoConsumeForm.weekdayType = 'singleUnlimited'
  autoConsumeForm.weekendType = 'singleUnlimited'
  autoConsumeForm.overtimeMinutes = 0
  autoConsumeForm.largeImages = 0
  autoConsumeForm.extraSmallImages = 0
  autoConsumeForm.extraLargeImages = 0
  syncAutoMiscSelections({})
  autoConsumeForm.additionalFee = 0
  autoConsumeForm.notes = ''
  autoConsumeForm.meituanCustomer = false

  Object.assign(timerConsumeForm, createTimerConsumeForm(customerId))
  syncTimerMiscSelections({})

  manualConsumeErrors.value = {}
  autoConsumeErrors.value = {}
  timerConsumeErrors.value = {}
}

function resetTimerEditForm(transaction = null) {
  const description = stripMiscMarkerFromDescription(transaction?.description)
  const inferredBillingType = inferTimerBillingTypeFromDescription(description)
  const inferredElapsedMinutes = parseElapsedMinutesFromDescription(description)
  const detailSection = parseTimerDetailSectionFromDescription(description)
  const inferredDuration = inferTimerDurationFromDescription(detailSection, inferredElapsedMinutes)
  const inferredOvertimeMinutes = inferTimerOvertimeMinutesFromDescription(
    detailSection,
    inferredElapsedMinutes,
    inferredDuration
  )
  const inferredWeekdayType = inferTimerWeekdayTypeFromDetail(detailSection)
  const inferredWeekendType = inferTimerWeekendTypeFromDetail(detailSection)
  const inferredNotesState = inferTimerNotesStateFromDescription(description)
  const inferredAdditionalFee = parseAdditionalFeeFromDetail(detailSection)
  const inferredOvertimeFee = inferredNotesState.applyOvertimeFee
    ? Math.max(0, Number(inferredNotesState.overtimeFee) || 0)
    : 0

  timerEditForm.elapsedMinutes = Math.max(0, Math.floor(Number(inferredElapsedMinutes) || 0))
  timerEditForm.billingType = inferredBillingType
  timerEditForm.duration = inferredDuration
  timerEditForm.weekdayType = inferredWeekdayType
  timerEditForm.weekendType = inferredWeekendType
  timerEditForm.overtimeMinutes = inferredBillingType === 'limited' ? inferredOvertimeMinutes : 0
  timerEditForm.largeImages = parseCountFromDetail(detailSection, '大图')
  timerEditForm.extraSmallImages = parseCountFromDetail(detailSection, '超量小图')
  timerEditForm.extraLargeImages = parseCountFromDetail(detailSection, '超量大图')
  timerEditForm.additionalFee = Math.max(0, Math.round(((inferredAdditionalFee - inferredOvertimeFee) + Number.EPSILON) * 100) / 100)
  timerEditForm.applyOvertimeFee = inferredNotesState.applyOvertimeFee
  timerEditForm.overtimeFeeMinutes = inferredNotesState.overtimeFeeMinutes
  timerEditForm.notes = inferredNotesState.notes
  timerEditForm.meituanCustomer = inferredNotesState.meituanCustomer
  timerEditStartTimestamp.value = resolveTimerEditStartTimestamp(transaction, timerEditForm.elapsedMinutes)
  syncTimerEditMiscSelections(transaction?.miscSelections || {})
  timerEditErrors.value = {}
}

function syncTimerEditLimitedOvertimeFromElapsed() {
  if (timerEditForm.billingType !== 'limited') {
    timerEditForm.overtimeMinutes = 0
    return
  }

  const totalMinutes = Math.max(0, Math.floor(Number(timerEditForm.elapsedMinutes) || 0))
  if (timerEditForm.duration === '2') {
    timerEditForm.overtimeMinutes = Math.max(0, totalMinutes - 120)
    return
  }

  if (totalMinutes <= 60) {
    timerEditForm.overtimeMinutes = 0
  } else if (totalMinutes < 90) {
    timerEditForm.overtimeMinutes = totalMinutes - 60
  } else if (totalMinutes <= 120) {
    timerEditForm.overtimeMinutes = 0
  } else {
    timerEditForm.overtimeMinutes = totalMinutes - 120
  }
}

async function handleFilter() {
  currentPage.value = 1
  await fetchTransactions()
}

async function handleReset() {
  filterForm.type = ''
  filterForm.startDate = ''
  filterForm.endDate = ''
  filterForm.customerKeyword = ''
  currentPage.value = 1
  await fetchTransactions()
}

async function handlePageChange(page) {
  if (page < 1 || page > totalPages.value) return
  currentPage.value = page
  await fetchTransactions()
}

async function handlePageSizeChange() {
  currentPage.value = 1
  await fetchTransactions()
}

function closeRechargeDialog(force = false) {
  if (!force && loading.value) return
  showRechargeDialog.value = false
  restoreDialogTrigger()
}

function closeConsumeDialog(force = false) {
  if (!force && loading.value) return
  showConsumeDialog.value = false
  restoreDialogTrigger()
}

function closeDetailDialog(force = false) {
  if (!force && loading.value) return
  showDetailDialog.value = false
  selectedTransaction.value = null
  restoreDialogTrigger()
}

function closeTimerEditDialog(force = false) {
  if (!force && timerEditTargetTransaction.value && isEditingTransaction(timerEditTargetTransaction.value.id)) return
  showTimerEditDialog.value = false
  timerEditTargetTransaction.value = null
  resetTimerEditForm()
  restoreDialogTrigger()
}

async function openRechargeDialog(customerId = '') {
  rememberDialogTrigger()
  rechargeForm.customerId = await refreshCustomersAndResolveCustomerId(customerId)
  rechargeForm.amount = ''
  rechargeForm.bonusAmount = ''
  rechargeForm.paymentMethod = 'cash'
  rechargeForm.activityId = ''
  rechargeErrors.value = {}
  showRechargeDialog.value = true
  await nextTick()
  rechargeCustomerSelectRef.value?.focus()
}

async function openConsumeDialog(customerId = '') {
  rememberDialogTrigger()
  const validCustomerId = await refreshCustomersAndResolveCustomerId(customerId)
  resetConsumeForms(validCustomerId)
  showConsumeDialog.value = true
  await nextTick()
  manualConsumeCustomerSelectRef.value?.focus()
  await Promise.all([fetchBillingRules(), syncConsumeBalance(validCustomerId)])
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

function validateTimerConsumeFormState() {
  const { isValid, errors } = validateSharedTimerConsumeForm(timerConsumeForm, validCustomers.value)
  const miscErrors = collectTimerMiscErrors(timerConsumeForm.miscSelections)
  if (miscErrors.length > 0) {
    errors.misc = miscErrors[0]
  }
  timerConsumeErrors.value = errors
  return isValid && miscErrors.length === 0
}

function validateTimerEditForm() {
  const errors = {}
  const elapsedMinutes = Number(timerEditForm.elapsedMinutes)
  if (!Number.isFinite(elapsedMinutes) || elapsedMinutes < 0) {
    errors.elapsedMinutes = '计费时长需为大于等于0的整数分钟'
  }

  const finalAmount = timerEditForm.meituanCustomer ? timerEditFinalAmount.value : timerEditPreview.value.total
  if (!Number.isFinite(finalAmount) || finalAmount <= 0) {
    errors.total = '重算后的交易金额必须大于0'
  }

  const miscErrors = collectTimerEditMiscErrors(timerEditForm.miscSelections)
  if (miscErrors.length > 0) {
    errors.misc = miscErrors[0]
  }

  timerEditErrors.value = errors
  if (Object.keys(errors).length > 0) return null

  const baseNotes = String(timerEditForm.notes || '').trim()
  const notesParts = []
  if (baseNotes) {
    notesParts.push(baseNotes)
  }

  const normalizedOvertimeFeeMinutes = timerEditAutoOvertimeMinutes.value
  const normalizedOvertimeRate = timerEditOvertimeRatePerMinute.value
  if (timerEditForm.applyOvertimeFee && normalizedOvertimeFeeMinutes > 0 && normalizedOvertimeRate > 0) {
    notesParts.push(
      `加班费用￥${formatAmount(timerEditOvertimeFee.value)}（${normalizedOvertimeFeeMinutes}分钟，￥${formatAmount(normalizedOvertimeRate)}/分钟）`
    )
  }

  if (timerEditForm.meituanCustomer) {
    notesParts.push(`美团客户(基础费用抽成￥${formatAmount(timerEditMeituanDeduction.value)})`)
  }

  const notes = notesParts.join('；')

  const description = buildConsumptionDescription(
    {
      mode: 'timer',
      billingType: timerEditForm.billingType,
      elapsedMinutes: Math.max(0, Math.floor(elapsedMinutes))
    },
    timerEditPreview.value,
    notes
  )

  return {
    amount: Math.round((finalAmount + Number.EPSILON) * 100) / 100,
    description,
    miscSelections: createMiscSelectionMap(timerEditForm.miscSelections)
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
    closeRechargeDialog(true)
    await Promise.all([fetchTransactions(), fetchCustomers()])
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
    manualConsumeErrors.value = {
      ...manualConsumeErrors.value,
      amount: '余额不足'
    }
    showFeedback('error', '客户余额不足')
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
    autoConsumeErrors.value = {
      ...autoConsumeErrors.value,
      total: '余额不足，无法结算'
    }
    showFeedback('error', '客户余额不足')
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
  if (!validateTimerConsumeFormState()) return

  await api.post('/active-timers', buildTimerConsumeRequestPayload(timerConsumeForm))
}

async function submitConsumeByMode() {
  const currentMode = consumeMode.value
  loading.value = true
  try {
    if (currentMode === 'manual') {
      await submitManualConsume()
      showFeedback('success', '消费记录已创建。')
    } else if (currentMode === 'auto') {
      await submitAutoConsume()
      showFeedback('success', '自动结算已完成。')
    } else {
      await submitTimerConsume()
      showFeedback('success', '计时消费已开始，请到“正在计时”页面完成结算。')
    }

    closeConsumeDialog(true)
    await Promise.all([fetchTransactions(), fetchCustomers()])
  } catch (error) {
    console.error('Failed to handle consume action:', error)
    showFeedback('error', error?.response?.data?.message || error?.message || '消费操作失败')
  } finally {
    loading.value = false
    await syncConsumeBalance(activeConsumeCustomerId.value)
  }
}

async function viewTransactionDetail(transaction) {
  rememberDialogTrigger()
  selectedTransaction.value = normalizeTransaction(transaction)
  showDetailDialog.value = true
  await nextTick()
  detailCloseButtonRef.value?.focus()
}

function isEditingTransaction(transactionId = '') {
  return editingTransactionId.value === transactionId
}

async function openTimerEditDialog(transaction) {
  const normalized = normalizeTransaction(transaction)
  if (!normalized?.id || !canEditTimerConsumptionTransaction(normalized)) return

  rememberDialogTrigger()
  timerEditTargetTransaction.value = normalized
  resetTimerEditForm(normalized)
  showTimerEditDialog.value = true
  await nextTick()
  timerEditAmountInputRef.value?.focus()
}

function isCancellingTransaction(transactionId = '') {
  return cancellingTransactionId.value === transactionId
}

async function cancelTransaction(transaction) {
  const normalized = normalizeTransaction(transaction)
  if (!normalized?.id) return

  rememberDialogTrigger()
  cancelTargetTransaction.value = normalized
  showCancelConfirmDialog.value = true
  await nextTick()
  cancelConfirmButtonRef.value?.focus()
}

function closeCancelConfirmDialog(force = false) {
  if (!force && cancelTargetTransaction.value && isCancellingTransaction(cancelTargetTransaction.value.id)) return
  showCancelConfirmDialog.value = false
  cancelTargetTransaction.value = null
  restoreDialogTrigger()
}

async function confirmCancelTransaction() {
  const normalized = normalizeTransaction(cancelTargetTransaction.value)
  if (!normalized?.id) return

  cancellingTransactionId.value = normalized.id
  try {
    await api.post(`/transactions/${normalized.id}/cancel`)
    closeCancelConfirmDialog(true)
    if (selectedTransaction.value?.id === normalized.id) {
      closeDetailDialog(true)
    }
    await Promise.all([fetchTransactions(), fetchCustomers()])
    showFeedback('success', `已取消交易 #${normalized.id}`)
  } catch (error) {
    console.error('Failed to cancel transaction:', error)
    showFeedback('error', error?.response?.data?.message || error?.message || '取消交易失败')
  } finally {
    cancellingTransactionId.value = ''
  }
}

async function confirmTimerEditTransaction() {
  const normalized = normalizeTransaction(timerEditTargetTransaction.value)
  if (!normalized?.id) return
  if (!canEditTimerConsumptionTransaction(normalized)) return

  const payload = validateTimerEditForm()
  if (!payload) return

  editingTransactionId.value = normalized.id
  try {
    const response = await api.put(`/transactions/${normalized.id}`, {
      amount: payload.amount,
      description: payload.description,
      misc_selections: payload.miscSelections,
      regenerate: true
    })

    const result = response?.data || response || {}
    const nextTransaction = normalizeTransaction(result.transaction || {})
    const replacedId = String(result.replaced_transaction_id || '').trim()

    if (selectedTransaction.value?.id === normalized.id) {
      selectedTransaction.value = nextTransaction?.id ? nextTransaction : null
    }

    closeTimerEditDialog(true)
    await Promise.all([fetchTransactions(), fetchCustomers()])
    if (nextTransaction?.id) {
      showFeedback(
        'success',
        replacedId
          ? `已重新结算并生成交易 #${nextTransaction.id}（原 #${replacedId}）`
          : `已重新结算计时消费 #${nextTransaction.id}`
      )
    } else {
      showFeedback('success', '计时消费重新结算成功')
    }
  } catch (error) {
    console.error('Failed to update timer consumption transaction:', error)
    showFeedback('error', error?.response?.data?.message || error?.message || '重新结算计时消费失败')
  } finally {
    editingTransactionId.value = ''
  }
}

function getTransactionTypeLabel(type) {
  const typeMap = {
    recharge: '充值',
    consumption: '消费',
    bead_purchase: '买豆支出'
  }
  return typeMap[type] || type || '-'
}

function getTransactionTypeClass(type) {
  const classMap = {
    recharge: 'bg-green-100 text-green-800',
    consumption: 'bg-orange-100 text-orange-800',
    bead_purchase: 'bg-rose-100 text-rose-800'
  }
  return classMap[type] || 'bg-gray-100 text-gray-800'
}

function isIncomeTransaction(type) {
  return type === 'recharge'
}

function getTransactionAmountClass(type) {
  return isIncomeTransaction(type) ? 'text-emerald-600' : 'text-amber-600'
}

function getTransactionAmountPrefix(type) {
  return isIncomeTransaction(type) ? '+' : '-'
}

function canCancelTransaction(type) {
  return type === 'recharge' || type === 'consumption' || type === 'bead_purchase'
}

function getStatusLabel(status) {
  const statusMap = {
    completed: '已完成',
    pending: '待处理',
    cancelled: '已取消'
  }
  return statusMap[status] || '已完成'
}

function getStatusClass(status) {
  const classMap = {
    completed: 'bg-green-100 text-green-800',
    pending: 'bg-yellow-100 text-yellow-800',
    cancelled: 'bg-red-100 text-red-800'
  }
  return classMap[status] || 'bg-green-100 text-green-800'
}

function formatDateTime(dateTime) {
  return formatServerDateTime(dateTime, {
    hour12: false
  })
}

function getCustomerName(transaction) {
  const customerId = transaction.customerId || transaction.customer_id
  return (
    transaction.customer?.name ||
    transaction.customerName ||
    transaction.customer_name ||
    customerMap.value.get(customerId)?.name ||
    '-'
  )
}

function getCustomerPhone(transaction) {
  const customerId = transaction.customerId || transaction.customer_id
  return (
    transaction.customer?.phone ||
    transaction.customerPhone ||
    customerMap.value.get(customerId)?.phone ||
    '-'
  )
}

function getCustomerWechat(transaction) {
  const customerId = transaction.customerId || transaction.customer_id
  return (
    transaction.customer?.wechat ||
    transaction.customerWechat ||
    transaction.customer_wechat ||
    customerMap.value.get(customerId)?.wechat ||
    '-'
  )
}

function getOperatorName(transaction) {
  const directOperator = transaction?.operator
  if (typeof directOperator === 'string') {
    const name = directOperator.trim()
    if (name) return name
  } else if (directOperator && typeof directOperator === 'object') {
    const nestedName = directOperator.name ?? directOperator.username ?? directOperator.id
    const parsedName = String(nestedName || '').trim()
    if (parsedName) return parsedName
  }

  const fallbackName = String(
    transaction?.operatorName ?? transaction?.operator_name ?? ''
  ).trim()
  return fallbackName || '-'
}

function clearRouteActionQuery() {
  const query = { ...route.query }
  delete query.action
  delete query.customerId
  router.replace({ query })
}

function handleGlobalKeydown(event) {
  if (event.key !== 'Escape') return

  if (showTimerEditDialog.value) {
    event.preventDefault()
    closeTimerEditDialog()
    return
  }

  if (showCancelConfirmDialog.value) {
    event.preventDefault()
    closeCancelConfirmDialog()
    return
  }

  if (showDetailDialog.value) {
    event.preventDefault()
    closeDetailDialog()
    return
  }

  if (showConsumeDialog.value) {
    event.preventDefault()
    closeConsumeDialog()
    return
  }

  if (showRechargeDialog.value) {
    event.preventDefault()
    closeRechargeDialog()
  }
}

async function handleRouteAction() {
  const action = String(route.query.action || '').toLowerCase()
  const customerId = route.query.customerId ? String(route.query.customerId) : ''
  if (!action) return

  if (action === 'recharge') {
    await openRechargeDialog(customerId)
  } else if (action === 'consume' || action === 'consumption') {
    await openConsumeDialog(customerId)
  }

  clearRouteActionQuery()
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

    const calculatedBonus = calculateActivityBonus(activity, rechargeForm.amount)
    rechargeForm.bonusAmount = String(calculatedBonus)
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
  () => [timerEditForm.elapsedMinutes, timerEditForm.billingType, timerEditForm.duration],
  () => {
    if (!showTimerEditDialog.value) return
    syncTimerEditLimitedOvertimeFromElapsed()
  }
)

watch(
  () => route.query,
  async () => {
    await handleRouteAction()
  },
  { immediate: true }
)

onMounted(async () => {
  window.addEventListener('keydown', handleGlobalKeydown)
  await Promise.all([fetchCustomers(), fetchActivities(), fetchBillingRules()])
  await fetchTransactions()
})

onUnmounted(() => {
  window.removeEventListener('keydown', handleGlobalKeydown)
  clearFeedbackTimer()
})
</script>

<template>
  <div class="transactions-page space-y-6">
    <section class="page-hero rounded-3xl px-5 py-6 sm:px-7 sm:py-7">
      <div class="relative z-10 flex flex-col gap-5 lg:flex-row lg:items-start lg:justify-between">
        <div class="space-y-2 max-w-2xl">
          <p class="page-hero__eyebrow">Transaction Workspace</p>
          <h1 class="page-hero__title">交易记录</h1>
        </div>
        <div class="flex flex-wrap items-center gap-2 sm:gap-3">
          <button
            @click="openRechargeDialog"
            class="page-hero__action"
          >
            <svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 6v6m0 0v6m0-6h6m-6 0H6" />
            </svg>
            <span>充值</span>
          </button>
          <button
            @click="openConsumeDialog"
            class="page-hero__action"
          >
            <svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M20 12H4" />
            </svg>
            <span>消费</span>
          </button>
        </div>
      </div>
    </section>

    <Transition name="feedback-fade">
      <div
        v-if="feedback.message"
        role="status"
        aria-live="polite"
        :class="['rounded-2xl border px-4 py-3 text-sm shadow-sm', feedbackClass]"
      >
        {{ feedback.message }}
      </div>
    </Transition>

    <section class="rounded-2xl border border-slate-200/70 bg-white p-4 sm:p-6 shadow-sm">
      <div class="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-[minmax(120px,0.75fr)_minmax(160px,1fr)_minmax(160px,1fr)_minmax(200px,1.2fr)_auto_auto] xl:items-end">
        <div>
          <label class="block text-sm font-semibold text-slate-700 mb-1.5">交易类型</label>
          <select
            v-model="filterForm.type"
            class="w-full h-10 px-3 border border-slate-300 rounded-xl focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
          >
            <option v-for="type in transactionTypes" :key="type.value" :value="type.value">
              {{ type.label }}
            </option>
          </select>
        </div>

        <div>
          <label class="block text-sm font-semibold text-slate-700 mb-1.5">开始日期</label>
          <div class="filter-date-wrap">
            <input
              v-model="filterForm.startDate"
              type="date"
              class="filter-date-input w-full h-10 px-3 border border-slate-300 rounded-xl focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
            />
            <span
              aria-hidden="true"
              :class="[
                'filter-date-overlay',
                filterForm.startDate ? 'filter-date-overlay--value' : 'filter-date-overlay--placeholder'
              ]"
            >
              {{ formatFilterDateLabel(filterForm.startDate) }}
            </span>
          </div>
        </div>

        <div>
          <label class="block text-sm font-semibold text-slate-700 mb-1.5">结束日期</label>
          <div class="filter-date-wrap">
            <input
              v-model="filterForm.endDate"
              type="date"
              class="filter-date-input w-full h-10 px-3 border border-slate-300 rounded-xl focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
            />
            <span
              aria-hidden="true"
              :class="[
                'filter-date-overlay',
                filterForm.endDate ? 'filter-date-overlay--value' : 'filter-date-overlay--placeholder'
              ]"
            >
              {{ formatFilterDateLabel(filterForm.endDate) }}
            </span>
          </div>
        </div>

        <div>
          <label class="block text-sm font-semibold text-slate-700 mb-1.5">客户搜索</label>
          <input
            v-model="filterForm.customerKeyword"
            type="text"
            placeholder="姓名 / 电话 / 编号"
            class="w-full h-10 px-3 border border-slate-300 rounded-xl focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
          />
        </div>

        <button
          @click="handleFilter"
          class="h-10 px-4 bg-blue-600 text-white rounded-xl hover:bg-blue-700 transition-colors xl:justify-self-end"
        >
          筛选
        </button>
        <button
          @click="handleReset"
          class="h-10 px-4 border border-slate-300 text-slate-700 rounded-xl hover:bg-slate-50 transition-colors xl:justify-self-start"
        >
          重置
        </button>
      </div>
    </section>

    <section class="rounded-2xl border border-slate-200/70 bg-white shadow-sm overflow-hidden">
      <div class="hidden md:block overflow-x-auto">
        <table class="min-w-full divide-y divide-slate-200">
          <thead class="bg-slate-50">
            <tr>
              <th class="px-5 py-3 text-left text-xs font-semibold text-slate-500 uppercase tracking-wider">交易ID</th>
              <th class="px-5 py-3 text-left text-xs font-semibold text-slate-500 uppercase tracking-wider">客户</th>
              <th class="px-5 py-3 text-left text-xs font-semibold text-slate-500 uppercase tracking-wider">金额</th>
              <th class="px-5 py-3 text-left text-xs font-semibold text-slate-500 uppercase tracking-wider">赠送</th>
              <th class="px-5 py-3 text-left text-xs font-semibold text-slate-500 uppercase tracking-wider">支付方式/描述</th>
              <th class="px-5 py-3 text-left text-xs font-semibold text-slate-500 uppercase tracking-wider">时间</th>
              <th class="px-5 py-3 text-left text-xs font-semibold text-slate-500 uppercase tracking-wider">状态</th>
              <th class="px-5 py-3 text-left text-xs font-semibold text-slate-500 uppercase tracking-wider">操作员</th>
              <th class="px-5 py-3 text-left text-xs font-semibold text-slate-500 uppercase tracking-wider">操作</th>
            </tr>
          </thead>
          <tbody class="divide-y divide-slate-100">
            <tr v-if="loading">
              <td colspan="9" class="px-6 py-14 text-center">
                <div class="flex items-center justify-center gap-2 text-blue-700">
                  <svg class="animate-spin h-6 w-6" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                    <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
                    <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                  </svg>
                  <span class="text-sm font-medium">正在加载交易数据...</span>
                </div>
              </td>
            </tr>
            <tr v-else-if="transactions.length === 0">
              <td colspan="9" class="px-6 py-14 text-center text-slate-500">
                暂无交易记录
              </td>
            </tr>
            <tr v-else v-for="transaction in transactions" :key="transaction.id" class="hover:bg-slate-50/75 transition-colors">
              <td class="px-5 py-4 whitespace-nowrap text-sm font-semibold text-slate-900">
                #{{ transaction.id }}
              </td>
              <td class="px-5 py-4 whitespace-nowrap">
                <div class="text-sm font-semibold text-slate-900">{{ getCustomerName(transaction) }}</div>
                <div class="text-sm text-slate-500">{{ getCustomerWechat(transaction) }}</div>
              </td>
              <td class="px-5 py-4 whitespace-nowrap">
                <span
                  :class="[
                    'text-sm font-semibold',
                    getTransactionAmountClass(transaction.type)
                  ]"
                >
                  {{ getTransactionAmountPrefix(transaction.type) }}￥{{ formatAmount(transaction.amount) }}
                </span>
              </td>
              <td class="px-5 py-4 whitespace-nowrap text-sm text-slate-500">
                <span v-if="transaction.bonusAmount > 0" class="text-emerald-600 font-medium">
                  +￥{{ formatAmount(transaction.bonusAmount) }}
                </span>
                <span v-else>-</span>
              </td>
              <td class="px-5 py-4">
                <div v-if="transaction.type === 'recharge'" class="text-sm text-slate-900">
                  {{ paymentMethods.find(p => p.value === transaction.paymentMethod)?.label || transaction.paymentMethod }}
                </div>
                <div v-else class="text-sm text-slate-500 max-w-xs truncate" :title="transaction.description || '-'">
                  {{ transaction.description || '-' }}
                </div>
              </td>
              <td class="px-5 py-4 whitespace-nowrap text-sm text-slate-500">
                {{ formatDateTime(transaction.createdAt) }}
              </td>
              <td class="px-5 py-4 whitespace-nowrap">
                <span
                  :class="[
                    'px-2.5 py-1 text-xs font-semibold rounded-full',
                    getStatusClass(transaction.status)
                  ]"
                >
                  {{ getStatusLabel(transaction.status) }}
                </span>
              </td>
              <td class="px-5 py-4 whitespace-nowrap text-sm text-slate-500">
                {{ getOperatorName(transaction) }}
              </td>
              <td class="px-5 py-4 whitespace-nowrap text-sm">
                <div class="flex items-center gap-3">
                  <button
                    @click="viewTransactionDetail(transaction)"
                    class="text-blue-600 hover:text-blue-800 transition-colors"
                  >
                    查看详情
                  </button>
                  <button
                    v-if="canEditTimerConsumptionTransaction(transaction)"
                    @click="openTimerEditDialog(transaction)"
                    :disabled="isEditingTransaction(transaction.id)"
                    class="text-amber-600 hover:text-amber-800 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                  >
                    {{ isEditingTransaction(transaction.id) ? '结算中...' : '重新结算' }}
                  </button>
                  <button
                    v-if="canCancelTransaction(transaction.type)"
                    @click="cancelTransaction(transaction)"
                    :disabled="isCancellingTransaction(transaction.id)"
                    class="text-rose-600 hover:text-rose-800 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                  >
                    {{ isCancellingTransaction(transaction.id) ? '取消中...' : '取消交易' }}
                  </button>
                </div>
              </td>
            </tr>
          </tbody>
        </table>
      </div>

      <div class="md:hidden px-3 py-3 sm:p-4 bg-slate-50/70">
        <div v-if="loading" class="rounded-xl border border-slate-200 bg-white p-6 text-center text-slate-500">
          <div class="flex items-center justify-center gap-2 text-blue-700">
            <svg class="animate-spin h-5 w-5" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
              <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
              <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
            </svg>
            <span>正在加载交易数据...</span>
          </div>
        </div>
        <div v-else-if="transactions.length === 0" class="rounded-xl border border-slate-200 bg-white p-6 text-center text-slate-500">
          暂无交易记录
        </div>
        <div v-else class="space-y-2.5">
          <article
            v-for="transaction in transactions"
            :key="`mobile-${transaction.id}`"
            class="rounded-xl border border-slate-200 bg-white p-3 sm:p-4 shadow-sm"
          >
            <div class="flex items-start justify-between gap-3">
              <div>
                <p class="text-xs text-slate-500">交易ID</p>
                <p class="text-sm font-semibold text-slate-900">#{{ transaction.id }}</p>
              </div>
              <span :class="['px-2.5 py-1 text-xs font-semibold rounded-full', getTransactionTypeClass(transaction.type)]">
                {{ getTransactionTypeLabel(transaction.type) }}
              </span>
            </div>
            <div class="mt-2.5 space-y-1 text-sm">
              <p class="text-slate-900 font-medium">{{ getCustomerName(transaction) }}</p>
              <p class="text-slate-500">{{ getCustomerWechat(transaction) }}</p>
              <p class="text-slate-500">{{ formatDateTime(transaction.createdAt) }}</p>
            </div>
            <div class="mt-2.5 flex items-end justify-between gap-3">
              <div>
                <p
                  :class="[
                    'text-base font-semibold',
                    getTransactionAmountClass(transaction.type)
                  ]"
                >
                  {{ getTransactionAmountPrefix(transaction.type) }}￥{{ formatAmount(transaction.amount) }}
                </p>
                <p class="text-xs text-slate-500">
                  赠送：{{ transaction.bonusAmount > 0 ? `+￥${formatAmount(transaction.bonusAmount)}` : '-' }}
                </p>
              </div>
              <span :class="['px-2 py-1 text-xs font-semibold rounded-full', getStatusClass(transaction.status)]">
                {{ getStatusLabel(transaction.status) }}
              </span>
            </div>
            <p class="mt-2.5 text-xs text-slate-500 truncate" :title="transaction.description || '-'">
              {{ transaction.type === 'recharge'
                ? `支付方式：${paymentMethods.find(p => p.value === transaction.paymentMethod)?.label || transaction.paymentMethod || '-'}`
                : `描述：${transaction.description || '-'}`
              }}
            </p>
            <div class="mt-2.5 flex flex-wrap items-center gap-2">
              <button
                @click="viewTransactionDetail(transaction)"
                class="flex-1 min-w-[90px] px-3 py-2 text-sm rounded-lg border border-blue-200 text-blue-700 bg-blue-50 hover:bg-blue-100 transition-colors"
              >
                查看详情
              </button>
              <button
                v-if="canEditTimerConsumptionTransaction(transaction)"
                @click="openTimerEditDialog(transaction)"
                :disabled="isEditingTransaction(transaction.id)"
                class="flex-1 min-w-[90px] px-3 py-2 text-sm rounded-lg border border-amber-200 text-amber-700 bg-amber-50 hover:bg-amber-100 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {{ isEditingTransaction(transaction.id) ? '结算中...' : '重新结算' }}
              </button>
              <button
                v-if="canCancelTransaction(transaction.type)"
                @click="cancelTransaction(transaction)"
                :disabled="isCancellingTransaction(transaction.id)"
                class="flex-1 min-w-[90px] px-3 py-2 text-sm rounded-lg border border-rose-200 text-rose-700 bg-rose-50 hover:bg-rose-100 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {{ isCancellingTransaction(transaction.id) ? '取消中...' : '取消交易' }}
              </button>
            </div>
          </article>
        </div>
      </div>

      <div v-if="total > 0" class="px-5 py-4 border-t border-slate-100 bg-gradient-to-r from-slate-50 to-white">
        <div class="flex flex-col gap-3 xl:flex-row xl:items-center xl:justify-between">
          <p class="text-sm text-slate-600">
            显示 {{ (currentPage - 1) * pageSize + 1 }} 到 {{ Math.min(currentPage * pageSize, total) }} 条，共 {{ total }} 条记录
          </p>
          <div class="flex flex-col gap-3 sm:flex-row sm:items-center">
            <label class="flex items-center gap-2 text-sm text-slate-600">
              <span>每页</span>
              <select
                v-model.number="pageSize"
                @change="handlePageSizeChange"
                class="h-9 min-w-[92px] px-3 border border-slate-200 rounded-lg bg-white text-sm text-slate-700 focus:outline-none focus:ring-2 focus:ring-blue-500"
              >
                <option v-for="size in pageSizeOptions" :key="size" :value="size">{{ size }}条</option>
              </select>
            </label>
            <div class="flex items-center gap-1">
              <button
                @click="handlePageChange(currentPage - 1)"
                :disabled="currentPage === 1"
                class="h-9 px-3 rounded-lg border border-slate-200 bg-white text-sm font-medium text-slate-700 transition hover:bg-slate-100 disabled:cursor-not-allowed disabled:opacity-45"
              >
                上一页
              </button>
              <template v-for="(page, index) in visiblePages" :key="`transaction-page-${page}-${index}`">
                <span v-if="page === '...'" class="w-9 text-center text-sm text-slate-400 select-none">...</span>
                <button
                  v-else
                  @click="handlePageChange(page)"
                  :class="[
                    'h-9 min-w-[2.25rem] px-2 rounded-lg border text-sm font-medium transition',
                    currentPage === page
                      ? 'border-blue-600 bg-blue-600 text-white shadow-sm shadow-blue-100'
                      : 'border-slate-200 bg-white text-slate-700 hover:bg-slate-100'
                  ]"
                >
                  {{ page }}
                </button>
              </template>
              <button
                @click="handlePageChange(currentPage + 1)"
                :disabled="currentPage === totalPages"
                class="h-9 px-3 rounded-lg border border-slate-200 bg-white text-sm font-medium text-slate-700 transition hover:bg-slate-100 disabled:cursor-not-allowed disabled:opacity-45"
              >
                下一页
              </button>
            </div>
          </div>
        </div>
      </div>
    </section>

    <Teleport to="body">
      <div
        v-if="showRechargeDialog"
        class="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50"
        @mousedown="onBackdropMouseDown('transactions-recharge', $event)"
        @mouseup="onBackdropMouseUp('transactions-recharge', $event) && closeRechargeDialog()"
      >
        <div class="bg-white rounded-xl shadow-xl w-full max-w-md mx-4">
          <div class="px-6 py-4 border-b border-gray-200 flex items-center justify-between">
            <h3 class="text-lg font-semibold text-gray-800">新增充值</h3>
            <button
              @click="closeRechargeDialog()"
              class="text-gray-400 hover:text-gray-600 transition-colors"
            >
              <svg xmlns="http://www.w3.org/2000/svg" class="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>
          <div class="p-6 space-y-4">
            <div>
              <label class="block text-sm font-medium text-gray-700 mb-1">选择客户</label>
              <select
                ref="rechargeCustomerSelectRef"
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
                />
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
                />
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
              @click="closeRechargeDialog()"
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
        @mousedown="onBackdropMouseDown('transactions-consume', $event)"
        @mouseup="onBackdropMouseUp('transactions-consume', $event) && closeConsumeDialog()"
      >
        <div class="bg-white rounded-xl shadow-xl w-full max-w-3xl mx-4 max-h-[90vh] overflow-y-auto">
          <div class="px-6 py-4 border-b border-gray-200 flex items-center justify-between">
            <h3 class="text-lg font-semibold text-gray-800">新增消费</h3>
            <button
              @click="closeConsumeDialog()"
              class="text-gray-400 hover:text-gray-600 transition-colors"
            >
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
                  ref="manualConsumeCustomerSelectRef"
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
                  />
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
                      {{ item.name }}（¥{{ formatAmount(item.unit_price) }}/{{ item.unit_label || '个' }}）
                    </label>
                    <p class="text-xs text-slate-500 mb-1">可用库存：{{ formatMiscStock(item) }}</p>
                    <input
                      v-model.number="manualConsumeForm.miscSelections[item.id]"
                      type="number"
                      min="0"
                      :max="getMiscAvailableQuantity(item)"
                      step="1"
                      class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                      @input="handleMiscSelectionInput(manualConsumeForm.miscSelections, item, $event.target.value)"
                      @change="clampMiscSelection(manualConsumeForm.miscSelections, item)"
                    />
                  </div>
                </div>
                <p v-if="manualConsumeErrors.misc" class="text-red-500 text-xs mt-1">
                  {{ manualConsumeErrors.misc }}
                </p>
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
                <p v-if="autoConsumeErrors.customerId" class="text-red-500 text-xs mt-1">
                  {{ autoConsumeErrors.customerId }}
                </p>
              </div>

              <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                  <label class="block text-sm font-medium text-gray-700 mb-1">计费类型</label>
                  <select
                    v-model="autoConsumeForm.billingType"
                    class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                  >
                    <option value="limited">限时计费</option>
                    <option value="weekday">工作日计费</option>
                    <option value="weekend">周末计费</option>
                  </select>
                </div>

                <div v-if="autoConsumeForm.billingType === 'limited'">
                  <label class="block text-sm font-medium text-gray-700 mb-1">时长</label>
                  <select
                    v-model="autoConsumeForm.duration"
                    class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                  >
                    <option value="1">1小时</option>
                    <option value="2">2小时</option>
                  </select>
                </div>

                <div v-if="autoConsumeForm.billingType === 'weekday'">
                  <label class="block text-sm font-medium text-gray-700 mb-1">工作日方案</label>
                  <select
                    v-model="autoConsumeForm.weekdayType"
                    class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                  >
                    <option value="singleUnlimited">单人不限时不限板</option>
                    <option value="doubleUnlimited">双人不限时不限板</option>
                    <option value="singleLimited">单人不限时限板</option>
                  </select>
                </div>

                <div v-if="autoConsumeForm.billingType === 'weekend'">
                  <label class="block text-sm font-medium text-gray-700 mb-1">周末方案</label>
                  <select
                    v-model="autoConsumeForm.weekendType"
                    class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                  >
                    <option value="singleUnlimited">单人不限时不限板</option>
                    <option value="doubleUnlimited">双人不限时不限板</option>
                    <option value="singleLimited">单人不限时限板</option>
                  </select>
                </div>

                <div v-if="autoConsumeForm.billingType === 'limited'">
                  <label class="block text-sm font-medium text-gray-700 mb-1">超时分钟</label>
                  <input
                    v-model.number="autoConsumeForm.overtimeMinutes"
                    type="number"
                    min="0"
                    class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                  />
                </div>
              </div>

              <div class="grid grid-cols-1 md:grid-cols-4 gap-4">
                <div>
                  <label class="block text-sm font-medium text-gray-700 mb-1">大图数量</label>
                  <input
                    v-model.number="autoConsumeForm.largeImages"
                    type="number"
                    min="0"
                    class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                  />
                </div>
                <div>
                  <label class="block text-sm font-medium text-gray-700 mb-1">超量小图</label>
                  <input
                    v-model.number="autoConsumeForm.extraSmallImages"
                    type="number"
                    min="0"
                    class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                  />
                </div>
                <div>
                  <label class="block text-sm font-medium text-gray-700 mb-1">超量大图</label>
                  <input
                    v-model.number="autoConsumeForm.extraLargeImages"
                    type="number"
                    min="0"
                    class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                  />
                </div>
                <div>
                  <label class="block text-sm font-medium text-gray-700 mb-1">附加费用</label>
                  <input
                    v-model.number="autoConsumeForm.additionalFee"
                    type="number"
                    min="0"
                    step="0.01"
                    class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                  />
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
                      {{ item.name }}（¥{{ formatAmount(item.unit_price) }}/{{ item.unit_label || '个' }}）
                    </label>
                    <p class="text-xs text-slate-500 mb-1">可用库存：{{ formatMiscStock(item) }}</p>
                    <input
                      v-model.number="autoConsumeForm.miscSelections[item.id]"
                      type="number"
                      min="0"
                      :max="getMiscAvailableQuantity(item)"
                      step="1"
                      class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                      @input="handleMiscSelectionInput(autoConsumeForm.miscSelections, item, $event.target.value)"
                      @change="clampMiscSelection(autoConsumeForm.miscSelections, item)"
                    />
                  </div>
                </div>
              </div>

              <div>
                <label class="block text-sm font-medium text-gray-700 mb-1">备注</label>
                <textarea
                  v-model="autoConsumeForm.notes"
                  rows="2"
                  class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent resize-none"
                  placeholder="可选"
                ></textarea>
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
              <p v-if="autoConsumeErrors.total" class="text-red-500 text-xs mt-1">
                {{ autoConsumeErrors.total }}
              </p>
              <p v-if="autoConsumeErrors.misc" class="text-red-500 text-xs mt-1">
                {{ autoConsumeErrors.misc }}
              </p>
            </div>

            <div v-else-if="consumeMode === 'timer'">
              <TimerConsumeDialog
                :model-value="timerConsumeForm"
                :errors="timerConsumeErrors"
                :customer-options="validCustomers"
                :enabled-misc-items="enabledMiscItems"
                @update:model-value="applyTimerConsumeForm"
              />
              <div v-if="enabledMiscItems.length > 0" class="mt-3 bg-blue-50 border border-blue-200 rounded-lg p-3 text-sm text-blue-800">
                预计杂项费用：￥{{ formatAmount(timerMiscSummary.fee) }}
              </div>
            </div>
          </div>
          <div class="px-6 py-4 border-t border-gray-200 flex justify-end space-x-3">
            <button
              @click="closeConsumeDialog()"
              class="px-4 py-2 border border-gray-300 text-gray-700 rounded-lg hover:bg-gray-50 transition-colors"
            >
              取消
            </button>
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
    <Teleport to="body">
      <div
        v-if="showTimerEditDialog && timerEditTargetTransaction"
        class="fixed inset-0 z-50 bg-black/55 flex items-center justify-center p-4"
        @mousedown="onBackdropMouseDown('transactions-timer-edit', $event)"
        @mouseup="onBackdropMouseUp('transactions-timer-edit', $event) && closeTimerEditDialog()"
      >
        <div class="w-full max-w-2xl bg-white rounded-2xl shadow-2xl border border-slate-100 max-h-[90vh] overflow-y-auto">
          <div class="px-6 py-5 border-b border-slate-100">
            <h3 class="text-lg font-semibold text-slate-900">重新结算计时消费（生成新交易）</h3>
            <p class="mt-2 text-sm text-slate-600">交易ID：#{{ timerEditTargetTransaction.id }}</p>
            <p class="mt-1 text-xs text-slate-500">当前金额：￥{{ formatAmount(timerEditTargetTransaction.amount) }}</p>
          </div>
          <div class="px-6 py-5 space-y-4">
            <div class="bg-sky-50 border border-sky-200 rounded-lg p-3 text-sm text-sky-800 space-y-1">
              <p>客户：{{ getCustomerName(timerEditTargetTransaction) }}</p>
              <p class="truncate" :title="timerEditTargetTransaction.description || '-'">
                原描述：{{ timerEditTargetTransaction.description || '-' }}
              </p>
            </div>

            <div>
              <label class="block text-sm font-medium text-slate-700 mb-1">计费时长（分钟）</label>
              <input
                ref="timerEditAmountInputRef"
                v-model.number="timerEditForm.elapsedMinutes"
                type="number"
                min="0"
                step="1"
                class="w-full px-3 py-2 border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              />
              <p v-if="timerEditErrors.elapsedMinutes" class="text-red-500 text-xs mt-1">
                {{ timerEditErrors.elapsedMinutes }}
              </p>
            </div>

            <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <label class="block text-sm font-medium text-gray-700 mb-1">计费类型</label>
                <select
                  v-model="timerEditForm.billingType"
                  class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                >
                  <option value="limited">限时计费</option>
                  <option value="weekday">工作日计费</option>
                  <option value="weekend">周末计费</option>
                </select>
              </div>

              <div v-if="timerEditForm.billingType === 'limited'">
                <label class="block text-sm font-medium text-gray-700 mb-1">时长</label>
                <select
                  v-model="timerEditForm.duration"
                  class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                >
                  <option value="1">1小时</option>
                  <option value="2">2小时</option>
                </select>
              </div>

              <div v-if="timerEditForm.billingType === 'weekday'">
                <label class="block text-sm font-medium text-gray-700 mb-1">工作日方案</label>
                <select
                  v-model="timerEditForm.weekdayType"
                  class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                >
                  <option value="singleUnlimited">单人不限时不限板</option>
                  <option value="doubleUnlimited">双人不限时不限板</option>
                  <option value="singleLimited">单人不限时限板</option>
                </select>
              </div>

              <div v-if="timerEditForm.billingType === 'weekend'">
                <label class="block text-sm font-medium text-gray-700 mb-1">周末方案</label>
                <select
                  v-model="timerEditForm.weekendType"
                  class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                >
                  <option value="singleUnlimited">单人不限时不限板</option>
                  <option value="doubleUnlimited">双人不限时不限板</option>
                  <option value="singleLimited">单人不限时限板</option>
                </select>
              </div>

              <div v-if="timerEditForm.billingType === 'limited'">
                <label class="block text-sm font-medium text-gray-700 mb-1">超时分钟</label>
                <input
                  v-model.number="timerEditForm.overtimeMinutes"
                  type="number"
                  min="0"
                  class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                />
              </div>
            </div>

            <div class="grid grid-cols-1 md:grid-cols-4 gap-3">
              <div>
                <label class="block text-sm font-medium text-gray-700 mb-1">大图数量</label>
                <input
                  v-model.number="timerEditForm.largeImages"
                  type="number"
                  min="0"
                  class="w-full px-3 py-2 border border-gray-300 rounded-lg"
                />
              </div>
              <div>
                <label class="block text-sm font-medium text-gray-700 mb-1">超量小图</label>
                <input
                  v-model.number="timerEditForm.extraSmallImages"
                  type="number"
                  min="0"
                  class="w-full px-3 py-2 border border-gray-300 rounded-lg"
                />
              </div>
              <div>
                <label class="block text-sm font-medium text-gray-700 mb-1">超量大图</label>
                <input
                  v-model.number="timerEditForm.extraLargeImages"
                  type="number"
                  min="0"
                  class="w-full px-3 py-2 border border-gray-300 rounded-lg"
                />
              </div>
              <div>
                <label class="block text-sm font-medium text-gray-700 mb-1">手动附加费用</label>
                <input
                  v-model.number="timerEditForm.additionalFee"
                  type="number"
                  min="0"
                  step="0.01"
                  class="w-full px-3 py-2 border border-gray-300 rounded-lg"
                />
              </div>
            </div>

            <div class="rounded-lg border border-slate-200 bg-slate-50 px-3 py-3 space-y-3">
              <label class="inline-flex items-center gap-2 text-sm text-gray-700">
                <input
                  v-model="timerEditForm.applyOvertimeFee"
                  type="checkbox"
                  class="h-4 w-4 rounded border-gray-300 text-blue-600 focus:ring-blue-500"
                >
                启用加班费（计入附加费用）
              </label>

              <div v-if="timerEditForm.applyOvertimeFee" class="space-y-1 text-xs text-slate-600">
                <p v-if="timerEditStartTimestamp !== null">计时开始：{{ timerEditStartTimeLabel }}</p>
                <p v-if="timerEditStartTimestamp !== null">预计结束：{{ timerEditEndTimeLabel }}</p>
                <p v-if="timerEditStartTimestamp !== null">加班分钟（自动）：{{ timerEditAutoOvertimeMinutes }}</p>
                <p v-else>未获取到计时开始时间，沿用历史加班分钟：{{ timerEditAutoOvertimeMinutes }}</p>
                <p>加班单价：￥{{ formatAmount(timerEditOvertimeRatePerMinute) }}/分钟</p>
              </div>

              <p class="text-xs text-slate-600">
                预计加班费：￥{{ formatAmount(timerEditOvertimeFee) }}
              </p>
            </div>

            <div v-if="enabledMiscItems.length > 0" class="space-y-3">
              <div class="flex items-center justify-between">
                <h4 class="text-sm font-medium text-gray-700">杂项计费（仅整数）</h4>
                <button
                  type="button"
                  class="text-xs text-blue-600 hover:text-blue-700"
                  @click="syncTimerEditMiscSelections({})"
                >
                  一键清零
                </button>
              </div>
              <div class="grid grid-cols-1 md:grid-cols-3 gap-3">
                <div v-for="item in enabledMiscItems" :key="`timer-edit-misc-${item.id}`">
                  <label class="block text-sm font-medium text-gray-700 mb-1">
                    {{ item.name }}（¥{{ formatAmount(item.unit_price) }}/{{ item.unit_label || '个' }}）
                  </label>
                  <p class="text-xs text-slate-500 mb-1">可用库存：{{ formatMiscStock(item) }}</p>
                  <input
                    v-model.number="timerEditForm.miscSelections[item.id]"
                    type="number"
                    min="0"
                    :max="getMiscAvailableQuantity(item)"
                    step="1"
                    class="w-full px-3 py-2 border border-gray-300 rounded-lg"
                    @input="handleMiscSelectionInput(timerEditForm.miscSelections, item, $event.target.value)"
                    @change="clampMiscSelection(timerEditForm.miscSelections, item)"
                  />
                </div>
              </div>
              <p v-if="timerEditErrors.misc" class="text-red-500 text-xs mt-1">
                {{ timerEditErrors.misc }}
              </p>
            </div>

            <label class="inline-flex items-center gap-2 text-sm text-gray-700">
              <input
                v-model="timerEditForm.meituanCustomer"
                type="checkbox"
                class="h-4 w-4 rounded border-gray-300 text-blue-600 focus:ring-blue-500"
              >
              美团客户（基础费用抽成7%）
            </label>

            <div>
              <label class="block text-sm font-medium text-gray-700 mb-1">备注</label>
              <textarea
                v-model="timerEditForm.notes"
                rows="2"
                class="w-full px-3 py-2 border border-gray-300 rounded-lg resize-none focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                placeholder="可选"
              ></textarea>
            </div>

            <div class="bg-green-50 border border-green-200 rounded-lg p-4 text-sm text-green-800 space-y-1">
              <p>计费类型：{{ getBillingTypeLabel(timerEditForm.billingType) }}</p>
              <p>基础费用：￥{{ formatAmount(timerEditPreview.baseFee) }}</p>
              <p>超时费用：￥{{ formatAmount(timerEditPreview.overtimeFee) }}</p>
              <p>耗材费用：￥{{ formatAmount(timerEditPreview.materialFee) }}</p>
              <p>杂项费用：￥{{ formatAmount(timerEditPreview.miscFee) }}</p>
              <p>手动附加：￥{{ formatAmount(timerEditForm.additionalFee) }}</p>
              <p v-if="timerEditForm.applyOvertimeFee">加班费用：￥{{ formatAmount(timerEditOvertimeFee) }}</p>
              <p>附加费用合计：￥{{ formatAmount(timerEditPreview.additionalFee) }}</p>
              <p v-if="timerEditForm.meituanCustomer">美团抽成：-￥{{ formatAmount(timerEditMeituanDeduction) }}</p>
              <p class="font-semibold text-base">
                重算金额：￥{{ formatAmount(timerEditForm.meituanCustomer ? timerEditFinalAmount : timerEditPreview.total) }}
              </p>
            </div>
            <p v-if="timerEditErrors.total" class="text-red-500 text-xs mt-1">
              {{ timerEditErrors.total }}
            </p>
          </div>
          <div class="px-6 py-4 border-t border-slate-100 flex justify-end gap-3">
            <button
              type="button"
              @click="closeTimerEditDialog"
              :disabled="isEditingTransaction(timerEditTargetTransaction.id)"
              class="px-4 py-2 rounded-lg border border-slate-300 text-slate-700 hover:bg-slate-50 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            >
              取消
            </button>
            <button
              type="button"
              @click="confirmTimerEditTransaction"
              :disabled="isEditingTransaction(timerEditTargetTransaction.id)"
              class="px-4 py-2 rounded-lg bg-amber-600 text-white hover:bg-amber-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {{ isEditingTransaction(timerEditTargetTransaction.id) ? '结算中...' : '确认重新结算' }}
            </button>
          </div>
        </div>
      </div>
    </Teleport>
    <Teleport to="body">
      <div
        v-if="showDetailDialog && selectedTransaction"
        class="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50"
        @mousedown="onBackdropMouseDown('transactions-detail', $event)"
        @mouseup="onBackdropMouseUp('transactions-detail', $event) && closeDetailDialog()"
      >
        <div class="bg-white rounded-xl shadow-xl w-full max-w-lg mx-4">
          <div class="px-6 py-4 border-b border-gray-200 flex items-center justify-between">
            <h3 class="text-lg font-semibold text-gray-800">交易详情</h3>
            <button
              ref="detailCloseButtonRef"
              @click="closeDetailDialog()"
              class="text-gray-400 hover:text-gray-600 transition-colors"
            >
              <svg xmlns="http://www.w3.org/2000/svg" class="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>
          <div class="p-6 space-y-4">
            <div class="grid grid-cols-2 gap-4">
              <div>
                <label class="text-sm text-gray-500">交易ID</label>
                <p class="text-gray-900 font-medium">#{{ selectedTransaction.id }}</p>
              </div>
              <div>
                <label class="text-sm text-gray-500">交易类型</label>
                <p>
                  <span
                    :class="[
                      'px-2 py-1 text-xs font-medium rounded-full',
                      getTransactionTypeClass(selectedTransaction.type)
                    ]"
                  >
                    {{ getTransactionTypeLabel(selectedTransaction.type) }}
                  </span>
                </p>
              </div>
              <div>
                <label class="text-sm text-gray-500">客户姓名</label>
                <p class="text-gray-900">{{ getCustomerName(selectedTransaction) }}</p>
              </div>
              <div>
                <label class="text-sm text-gray-500">客户微信号</label>
                <p class="text-gray-900">{{ getCustomerWechat(selectedTransaction) }}</p>
              </div>
              <div>
                <label class="text-sm text-gray-500">金额</label>
                <p
                  :class="[
                    'font-medium',
                    getTransactionAmountClass(selectedTransaction.type)
                  ]"
                >
                  {{ getTransactionAmountPrefix(selectedTransaction.type) }}￥{{ formatAmount(selectedTransaction.amount) }}
                </p>
              </div>
              <div>
                <label class="text-sm text-gray-500">赠送金额</label>
                <p class="text-green-600">
                  {{ selectedTransaction.bonusAmount > 0 ? '+￥' + formatAmount(selectedTransaction.bonusAmount) : '-' }}
                </p>
              </div>
              <div v-if="selectedTransaction.type === 'recharge'">
                <label class="text-sm text-gray-500">支付方式</label>
                <p class="text-gray-900">
                  {{ paymentMethods.find(p => p.value === selectedTransaction.paymentMethod)?.label || selectedTransaction.paymentMethod }}
                </p>
              </div>
              <div>
                <label class="text-sm text-gray-500">状态</label>
                <p>
                  <span
                    :class="[
                      'px-2 py-1 text-xs font-medium rounded-full',
                      getStatusClass(selectedTransaction.status)
                    ]"
                  >
                    {{ getStatusLabel(selectedTransaction.status) }}
                  </span>
                </p>
              </div>
              <div>
                <label class="text-sm text-gray-500">交易时间</label>
                <p class="text-gray-900">{{ formatDateTime(selectedTransaction.createdAt) }}</p>
              </div>
              <div>
                <label class="text-sm text-gray-500">操作员</label>
                <p class="text-gray-900">
                  {{ getOperatorName(selectedTransaction) }}
                </p>
              </div>
            </div>
            <div v-if="selectedTransaction.type !== 'recharge' && selectedTransaction.description">
              <label class="text-sm text-gray-500">描述</label>
              <p class="text-gray-900 mt-1">{{ selectedTransaction.description }}</p>
            </div>
            <div v-if="selectedTransaction.activity">
              <label class="text-sm text-gray-500">关联活动</label>
              <p class="text-gray-900">{{ selectedTransaction.activity?.name || '-' }}</p>
            </div>
          </div>
          <div class="px-6 py-4 border-t border-gray-200 flex items-center justify-between gap-3">
            <button
              v-if="canEditTimerConsumptionTransaction(selectedTransaction)"
              @click="openTimerEditDialog(selectedTransaction)"
              :disabled="isEditingTransaction(selectedTransaction.id)"
              class="px-4 py-2 bg-amber-50 text-amber-700 border border-amber-200 rounded-lg hover:bg-amber-100 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {{ isEditingTransaction(selectedTransaction.id) ? '结算中...' : '重新结算计时消费' }}
            </button>
            <span v-else class="flex-1"></span>
            <button
              @click="closeDetailDialog()"
              class="px-4 py-2 bg-gray-100 text-gray-700 rounded-lg hover:bg-gray-200 transition-colors"
            >
              关闭
            </button>
          </div>
        </div>
      </div>
    </Teleport>
    <Teleport to="body">
      <div
        v-if="showCancelConfirmDialog && cancelTargetTransaction"
        class="fixed inset-0 z-50 bg-black/55 flex items-center justify-center p-4"
        @mousedown="onBackdropMouseDown('transactions-cancel', $event)"
        @mouseup="onBackdropMouseUp('transactions-cancel', $event) && closeCancelConfirmDialog()"
      >
        <div class="w-full max-w-md bg-white rounded-2xl shadow-2xl border border-slate-100">
          <div class="px-6 py-5 border-b border-slate-100">
            <h3 class="text-lg font-semibold text-slate-900">确认取消交易？</h3>
              <p class="mt-2 text-sm text-slate-600 leading-relaxed">
                取消后将自动回滚对应数据（会员余额或豆仓库存），操作无法恢复。请确认交易信息无误后再继续。
              </p>
          </div>
          <div class="px-6 py-4 space-y-2 text-sm bg-slate-50 border-b border-slate-100">
            <p class="text-slate-700">交易ID：<strong>#{{ cancelTargetTransaction.id }}</strong></p>
            <p class="text-slate-700">交易类型：{{ getTransactionTypeLabel(cancelTargetTransaction.type) }}</p>
            <p class="text-slate-700">交易金额：￥{{ formatAmount(cancelTargetTransaction.amount) }}</p>
            <p class="text-slate-700">客户：{{ getCustomerName(cancelTargetTransaction) }}</p>
          </div>
          <div class="px-6 py-4 flex justify-end gap-3">
            <button
              type="button"
              @click="closeCancelConfirmDialog"
              :disabled="isCancellingTransaction(cancelTargetTransaction.id)"
              class="px-4 py-2 rounded-lg border border-slate-300 text-slate-700 hover:bg-slate-50 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            >
              返回
            </button>
            <button
              ref="cancelConfirmButtonRef"
              type="button"
              @click="confirmCancelTransaction"
              :disabled="isCancellingTransaction(cancelTargetTransaction.id)"
              class="px-4 py-2 rounded-lg bg-rose-600 text-white hover:bg-rose-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {{ isCancellingTransaction(cancelTargetTransaction.id) ? '取消中...' : '确认取消交易' }}
            </button>
          </div>
        </div>
      </div>
    </Teleport>
  </div>
</template>

<style scoped>
.feedback-fade-enter-active,
.feedback-fade-leave-active {
  transition: all 180ms ease;
}

.feedback-fade-enter-from,
.feedback-fade-leave-to {
  opacity: 0;
  transform: translateY(-6px);
}

.filter-date-wrap {
  position: relative;
}

.filter-date-overlay {
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

.filter-date-overlay--placeholder {
  color: #94a3b8;
}

.filter-date-overlay--value {
  color: #0f172a;
  font-weight: 600;
}

.filter-date-input {
  color: transparent;
  -webkit-text-fill-color: transparent;
  font-size: 0.875rem;
  line-height: 1.25rem;
  font-variant-numeric: tabular-nums;
}

.filter-date-input::-webkit-datetime-edit {
  color: transparent;
  letter-spacing: 0.01em;
}

.filter-date-input::-webkit-datetime-edit-text {
  color: transparent;
  padding: 0;
}

.filter-date-input::-webkit-calendar-picker-indicator {
  opacity: 0.82;
}
</style>








