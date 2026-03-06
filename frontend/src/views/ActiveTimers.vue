<script setup>
import { ref, reactive, computed, watch, onMounted, onUnmounted, nextTick } from 'vue'
import api from '@/api'
import { useAuthStore } from '@/stores'
import { useBackdropClose } from '@/utils/modalBackdrop'
import TimerConsumeDialog from '@/components/timers/TimerConsumeDialog.vue'
import {
  createTimerConsumeForm,
  timerTypeOptions as sharedTimerTypeOptions,
  buildTimerPackagePlanOptionsByType,
  getDefaultTimerPackagePlan,
  validateTimerConsumeForm as validateSharedTimerConsumeForm,
  buildTimerConsumeRequestPayload,
  TABLE_AREA_OPTIONS,
  TABLE_SEAT_OPTIONS,
  buildTableNo,
  getRequiredExtraSeatCount,
  getTimerConsumeSeatPayload
} from '@/utils/timerConsume'
import {
  normalizeBillingRules,
  calculateConsumptionAmount,
  buildConsumptionDescription,
  calculateMeituanDeduction,
  applyDeduction,
  getPackagePlanBaseFee,
  getPackagePlanLabel as getPackagePlanLabelByRules,
  getPackagePlanPeopleCount,
  resolvePackagePlanInfo
} from '@/utils/consumptionCalculator'
import { getEffectiveBillingDayType } from '@/utils/dayType'

const timers = ref([])
const customers = ref([])
const billingRules = ref(normalizeBillingRules())
const authStore = useAuthStore()
const { onBackdropMouseDown, onBackdropMouseUp } = useBackdropClose()

const loading = ref(false)
const submitting = ref(false)
const addCurrentBalance = ref(null)
const addBalanceLoading = ref(false)

const showAddModal = ref(false)
const showEditModal = ref(false)
const showSettleModal = ref(false)
const showLivingRoomModal = ref(false)
const showSmallRoomModal = ref(false)
const showGardenModal = ref(false)
const showUpstairsModal = ref(false)
const showSeatOverviewModal = ref(false)
const restoreRoomAfterAddModal = ref('')
const warningQueue = ref([])
const activeWarning = ref(null)
const seatSelectionMode = ref('single')
const pendingMultiSeatSelection = ref(null)
const selectedTimer = ref(null)
const editingTimer = ref(null)
const addTimerDialogRef = ref(null)
const feedback = reactive({
  tone: 'info',
  message: ''
})
let feedbackTimer = null
const warnedTimerIds = ref(loadWarnedTimerIds())
const pendingWarningTimerIds = new Set()

const filterForm = reactive({
  keyword: '',
  timerType: '',
  packagePlan: ''
})

const nowTimestamp = ref(Date.now())
let ticker = null
const OVERTIME_START_HOUR = 19
const OVERTIME_START_MINUTE = 30
const DEFAULT_OVERTIME_RATE_PER_MINUTE = 0.5
const DAY_MS = 24 * 60 * 60 * 1000
const TABLE_NO_PATTERN = /^([A-HJ-NP-Za-hj-np-z])桌([1-9]|1[0-9]|20)号$/
const WARNING_STORAGE_KEY = 'active_timer_warning_v1'
const PACKAGE_TRIGGER_MINUTES = {
  limited1h: 50,
  limited2h: 110
}
const PACKAGE_TOTAL_MINUTES = {
  limited1h: 60,
  limited2h: 120
}

const addForm = reactive(createTimerConsumeForm())

const settleForm = reactive({
  billingType: 'limited',
  duration: '1',
  weekdayType: '',
  weekendType: '',
  overtimeMinutes: 0,
  largeImages: 0,
  extraSmallImages: 0,
  extraLargeImages: 0,
  miscSelections: {},
  additionalFee: 0,
  notes: '',
  meituanCustomer: false,
  applyOvertimeFee: true,
  useManualElapsed: false,
  manualElapsedMinutes: 0
})

const editForm = reactive({
  tableArea: TABLE_AREA_OPTIONS[0],
  tableSeat: TABLE_SEAT_OPTIONS[0],
  tableNo: '',
  extraTableSelections: [],
  extraTableNos: [],
  secondTableArea: TABLE_AREA_OPTIONS[0],
  secondTableSeat: '',
  secondTableNo: '',
  packagePlan: '',
  notes: '',
  largeImages: 0,
  extraSmallImages: 0,
  extraLargeImages: 0,
  miscSelections: {}
})

const addErrors = ref({})
const editErrors = ref({})
const settleErrors = ref({})
const isAdmin = computed(() => String(authStore.user?.role || '').toLowerCase() === 'admin')

const customerMap = computed(() => {
  const map = new Map()
  customers.value.forEach((customer) => map.set(customer.id, customer))
  return map
})

const addTimerCustomerOptions = computed(() => {
  const prioritized = []
  const remaining = []

  customers.value.forEach((customer) => {
    const name = String(customer?.name || '').trim()
    if (name.startsWith('微信') || name.startsWith('美')) {
      prioritized.push(customer)
      return
    }
    remaining.push(customer)
  })

  return [...prioritized, ...remaining]
})

const timerTypeOptions = sharedTimerTypeOptions
const tableAreaOptions = TABLE_AREA_OPTIONS
const tableSeatOptions = TABLE_SEAT_OPTIONS
const LIVING_ROOM_LAYOUT_TABLES = [
  { area: 'F', seatCount: 4, seatColumns: 2, shape: 'square' },
  { area: 'C', seatCount: 6, seatColumns: 3, shape: 'wide' },
  { area: 'E', seatCount: 4, seatColumns: 2, shape: 'square' },
  { area: 'B', seatCount: 6, seatColumns: 3, shape: 'wide' },
  { area: 'D', seatCount: 4, seatColumns: 2, shape: 'square' },
  { area: 'A', seatCount: 6, seatColumns: 3, shape: 'wide' }
]
const SMALL_ROOM_LAYOUT_TABLES = [
  { area: 'G', seatCount: 4, seatColumns: 2, shape: 'wide' },
  { area: 'H', seatCount: 4, seatColumns: 1, shape: 'tall' },
  { area: 'J', seatCount: 2, seatColumns: 2, shape: 'wide' }
]
const GARDEN_LAYOUT_TABLES = [
  { area: 'K', seatCount: 6, seatColumns: 3, shape: 'square' },
  { area: 'L', seatCount: 4, seatColumns: 2, shape: 'square' }
]
const UPSTAIRS_LAYOUT_TABLES = [
  { area: 'M', seatCount: 3, seatColumns: 3, shape: 'wide' }
]

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

const addPackagePlanOptionsByType = computed(() => buildTimerPackagePlanOptionsByType(billingRules.value))
const filterPackagePlanOptionsByType = computed(() => buildTimerPackagePlanOptionsByType(billingRules.value, { includeDisabled: true }))
const weekdayTypeOptions = computed(() => addPackagePlanOptionsByType.value.weekday || [])
const weekendTypeOptions = computed(() => addPackagePlanOptionsByType.value.weekend || [])

const allPackagePlanOptions = computed(() => Object.values(filterPackagePlanOptionsByType.value).flat())
const filterPackagePlanOptions = computed(() => {
  if (!filterForm.timerType) {
    return allPackagePlanOptions.value
  }
  return filterPackagePlanOptionsByType.value[filterForm.timerType] || []
})

function getDefaultAddPackagePlan(timerType = 'limited') {
  return getDefaultTimerPackagePlan(timerType, billingRules.value)
}

const hasActiveFilters = computed(() => (
  Boolean(String(filterForm.keyword || '').trim())
  || Boolean(filterForm.timerType)
  || Boolean(filterForm.packagePlan)
))

const filteredTimers = computed(() => {
  const keyword = String(filterForm.keyword || '').trim().toLowerCase()

  return timers.value.filter((timer) => {
    if (filterForm.timerType && timer.timerType !== filterForm.timerType) {
      return false
    }

    if (filterForm.packagePlan && timer.packagePlan !== filterForm.packagePlan) {
      return false
    }

    if (!keyword) return true

    const searchableText = [
      timer.customerName,
      timer.customerId,
      timer.tableNo,
      timer.notes,
      timer.packagePlan,
      getPackagePlanLabel(timer.packagePlan),
      getTimerTypeLabel(timer.timerType)
    ]
      .map((item) => String(item || '').toLowerCase())
      .join(' ')

    return searchableText.includes(keyword)
  })
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

const settleElapsedMinutes = computed(() => {
  if (settleForm.useManualElapsed) {
    const minutes = Number(settleForm.manualElapsedMinutes)
    if (!Number.isFinite(minutes) || minutes < 0) return 0
    return Math.floor(minutes)
  }

  return getElapsedMinutes(selectedTimer.value)
})

function round2(value) {
  return Math.round((Number(value) + Number.EPSILON) * 100) / 100
}

function isAfterOvertimeStart(timestamp = nowTimestamp.value) {
  const current = new Date(timestamp)
  if (Number.isNaN(current.getTime())) return false
  const hour = current.getHours()
  const minute = current.getMinutes()
  return hour > OVERTIME_START_HOUR || (hour === OVERTIME_START_HOUR && minute >= OVERTIME_START_MINUTE)
}

function calculateOvertimeMinutesByRange(startMs, endMs) {
  if (!Number.isFinite(startMs) || !Number.isFinite(endMs) || endMs <= startMs) {
    return 0
  }

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

const settleOvertimeMinutes = computed(() => {
  if (!selectedTimer.value) return 0

  if (settleForm.useManualElapsed) {
    return isAfterOvertimeStart() ? settleElapsedMinutes.value : 0
  }

  const startMs = toServerDateTimestamp(selectedTimer.value.startTime)
  return calculateOvertimeMinutesByRange(startMs, nowTimestamp.value)
})

const settleRawAdditionalFee = computed(() => Math.max(0, Number(settleForm.additionalFee) || 0))
const settleOvertimeRatePerMinute = computed(() => {
  const configuredRate = Number(billingRules.value?.overtime?.ratePerMinute)
  if (!Number.isFinite(configuredRate) || configuredRate < 0) {
    return DEFAULT_OVERTIME_RATE_PER_MINUTE
  }
  return configuredRate
})

const settleOvertimePeopleCount = computed(() => {
  if (!selectedTimer.value) return 1
  const packagePeopleCount = getPackagePlanPeopleCount(selectedTimer.value.packagePlan || '', billingRules.value)
  const occupiedSeatCount = getTimerOccupiedTableNos(selectedTimer.value).length
  const resolvedPeopleCount = Math.max(
    1,
    Math.floor(Number(packagePeopleCount) || 0),
    Math.floor(Number(occupiedSeatCount) || 0)
  )
  return resolvedPeopleCount >= 2 ? resolvedPeopleCount : 1
})

const settleOvertimeTotalRatePerMinute = computed(() =>
  round2(settleOvertimeRatePerMinute.value * settleOvertimePeopleCount.value)
)

const settleOvertimeFeeByRule = computed(() =>
  round2(settleOvertimeMinutes.value * settleOvertimeTotalRatePerMinute.value)
)

const settleOvertimeFee = computed(() => {
  if (!settleForm.applyOvertimeFee) return 0
  return settleOvertimeFeeByRule.value
})

const settleTotalAdditionalFee = computed(() => round2(settleRawAdditionalFee.value + settleOvertimeFee.value))

const settlePreview = computed(() =>
  calculateConsumptionAmount(
    {
      pricingMode: settleForm.billingType === 'limited' ? 'standard' : 'timer',
      billingType: settleForm.billingType,
      duration: settleForm.duration,
      weekdayType: settleForm.weekdayType,
      weekendType: settleForm.weekendType,
      overtimeMinutes: settleForm.overtimeMinutes,
      elapsedMinutes: settleElapsedMinutes.value,
      settlementTimestamp: nowTimestamp.value,
      timerDayType: selectedTimer.value?.timerType,
      packagePlan: selectedTimer.value?.packagePlan || '',
      largeImages: settleForm.largeImages,
      extraSmallImages: settleForm.extraSmallImages,
      extraLargeImages: settleForm.extraLargeImages,
      miscSelections: settleForm.miscSelections,
      additionalFee: settleTotalAdditionalFee.value
    },
    billingRules.value
  )
)

const settleStartPackageBaseFee = computed(() => {
  if (!selectedTimer.value) return 0

  const baseFeeFromNotes = Number(selectedTimer.value.meituanPackageBaseFee)
  if (Number.isFinite(baseFeeFromNotes) && baseFeeFromNotes > 0) {
    return baseFeeFromNotes
  }

  return getPackagePlanBaseFee(selectedTimer.value.packagePlan || '', billingRules.value)
})

const settleMeituanDeduction = computed(() => (
  settleForm.meituanCustomer
    ? calculateMeituanDeduction(
      settleStartPackageBaseFee.value,
      undefined,
      {
        packagePlan: selectedTimer.value?.packagePlan
      }
    )
    : 0
))

const settleFinalAmount = computed(() =>
  applyDeduction(settlePreview.value.total, settleMeituanDeduction.value)
)

const settlePackageUpgradeFee = computed(() => {
  const startBase = Number(settleStartPackageBaseFee.value) || 0
  const currentBase = Number(settlePreview.value.baseFee) || 0
  const diff = currentBase - startBase
  return diff > 0 ? diff : 0
})

const settleExtraOvertimeFee = computed(() =>
  (Number(settlePreview.value.overtimeFee) || 0) + settlePackageUpgradeFee.value
)

const settleExtraConsumption = computed(() =>
  settleExtraOvertimeFee.value +
  (Number(settlePreview.value.materialFee) || 0) +
  (Number(settlePreview.value.miscFee) || 0) +
  (Number(settlePreview.value.additionalFee) || 0)
)

function getRecommendedLimitedDuration(elapsedMinutes) {
  const minutes = Math.max(0, Math.floor(Number(elapsedMinutes) || 0))
  return minutes < 90 ? '1' : '2'
}

function getRecommendedOvertimeMinutes(elapsedMinutes) {
  const minutes = Math.max(0, Math.floor(Number(elapsedMinutes) || 0))

  if (minutes <= 60) return 0
  if (minutes < 90) return minutes - 60
  if (minutes <= 120) return 0
  return minutes - 120
}

function resolvePlanTypeFromPackagePlan(timerType, packagePlan) {
  if (timerType !== 'weekday' && timerType !== 'weekend') return ''
  const info = resolvePackagePlanInfo(packagePlan, billingRules.value)
  if (info?.timerType === timerType) {
    return info.code
  }
  return getDefaultAddPackagePlan(timerType)
}
function applyRecommendedSettlementPlan() {
  if (!selectedTimer.value) return

  const timerType = selectedTimer.value?.timerType
  const packagePlan = selectedTimer.value?.packagePlan || ''

  if (timerType === 'weekday' || timerType === 'weekend') {
    settleForm.billingType = timerType
    settleForm.overtimeMinutes = 0

    if (timerType === 'weekday') {
      settleForm.weekdayType = resolvePlanTypeFromPackagePlan('weekday', packagePlan)
    } else {
      settleForm.weekendType = resolvePlanTypeFromPackagePlan('weekend', packagePlan)
    }

    return
  }

  const elapsedMinutes = Math.max(0, Math.floor(Number(settleElapsedMinutes.value) || 0))
  const recommended = calculateConsumptionAmount(
    {
      pricingMode: 'timer',
      billingType: 'limited',
      elapsedMinutes,
      settlementTimestamp: nowTimestamp.value,
      timerDayType: selectedTimer.value?.timerType,
      packagePlan: selectedTimer.value?.packagePlan || ''
    },
    billingRules.value
  )

  if (recommended.billingType === 'weekday') {
    settleForm.billingType = 'weekday'
    settleForm.weekdayType = getDefaultAddPackagePlan('weekday')
    settleForm.overtimeMinutes = 0
    return
  }

  if (recommended.billingType === 'weekend') {
    settleForm.billingType = 'weekend'
    settleForm.weekendType = getDefaultAddPackagePlan('weekend')
    settleForm.overtimeMinutes = 0
    return
  }

  settleForm.billingType = 'limited'
  if (packagePlan === 'limited2h') {
    settleForm.duration = '2'
    settleForm.overtimeMinutes = Math.max(0, elapsedMinutes - 120)
    return
  }

  settleForm.duration = getRecommendedLimitedDuration(elapsedMinutes)
  settleForm.overtimeMinutes = getRecommendedOvertimeMinutes(elapsedMinutes)
}
function unwrapData(payload, fallback) {
  if (payload && typeof payload === 'object' && 'data' in payload) {
    return payload.data ?? fallback
  }
  return payload ?? fallback
}

function getTimerTypeLabel(type) {
  const map = {
    limited: '限时套餐',
    weekday: '工作日套餐',
    weekend: '周末套餐'
  }
  return map[type] || type || '-'
}

function getPackagePlanLabel(plan) {
  return getPackagePlanLabelByRules(plan, billingRules.value)
}

function normalizeTableNo(value) {
  const raw = String(value || '').trim()
  const matched = raw.match(TABLE_NO_PATTERN)
  if (!matched) return raw
  return `${matched[1].toUpperCase()}桌${matched[2]}号`
}

function isValidTableNo(value) {
  return TABLE_NO_PATTERN.test(normalizeTableNo(value))
}

function toDeskSpeechCode(tableNo) {
  const matched = normalizeTableNo(tableNo).match(TABLE_NO_PATTERN)
  if (!matched) return ''
  return `${matched[1].toLowerCase()}${matched[2]}`
}

function parseExactTableNo(tableNo) {
  const matched = normalizeTableNo(tableNo).match(TABLE_NO_PATTERN)
  if (!matched) return null
  return {
    tableArea: matched[1].toUpperCase(),
    tableSeat: matched[2]
  }
}

function parseTableNoParts(
  tableNo,
  fallbackArea = TABLE_AREA_OPTIONS[0],
  fallbackSeat = TABLE_SEAT_OPTIONS[0]
) {
  const normalizedFallbackArea = TABLE_AREA_OPTIONS.includes(String(fallbackArea || '').trim().toUpperCase())
    ? String(fallbackArea || '').trim().toUpperCase()
    : TABLE_AREA_OPTIONS[0]
  const rawFallbackSeat = String(fallbackSeat || '').trim()
  const normalizedFallbackSeat = TABLE_SEAT_OPTIONS.includes(rawFallbackSeat) ? rawFallbackSeat : ''
  const parsed = parseExactTableNo(tableNo)
  if (!parsed) {
    return {
      tableArea: normalizedFallbackArea,
      tableSeat: normalizedFallbackSeat
    }
  }
  const tableArea = parsed.tableArea
  const tableSeat = parsed.tableSeat
  return {
    tableArea: TABLE_AREA_OPTIONS.includes(tableArea) ? tableArea : normalizedFallbackArea,
    tableSeat: TABLE_SEAT_OPTIONS.includes(tableSeat) ? tableSeat : normalizedFallbackSeat
  }
}

function getTimerOccupiedTableNos(timer) {
  const seats = []
  const firstSeat = normalizeTableNo(timer?.tableNo)
  if (isValidTableNo(firstSeat)) {
    seats.push(firstSeat)
  }
  const seen = new Set(seats)
  getTimerExtraTableNos(timer).forEach((seatNo) => {
    if (seen.has(seatNo)) return
    seen.add(seatNo)
    seats.push(seatNo)
  })
  return seats
}

function getTimerExtraTableNos(timer, options = {}) {
  const includeLegacy = options.includeLegacy !== false
  const limitByPackage = options.limitByPackage === true
  const normalized = []
  const seen = new Set()
  const pushSeat = (rawSeatNo) => {
    const seatNo = normalizeTableNo(rawSeatNo)
    if (!isValidTableNo(seatNo)) return
    if (seen.has(seatNo)) return
    seen.add(seatNo)
    normalized.push(seatNo)
  }

  if (Array.isArray(timer?.extraTableNos)) {
    timer.extraTableNos.forEach((item) => pushSeat(item))
  }
  if (includeLegacy) {
    pushSeat(timer?.secondTableNo)
  }

  if (!limitByPackage) return normalized

  const requiredCount = getRequiredExtraSeatCount(timer?.packagePlan, billingRules.value)
  if (requiredCount <= 0) return []
  return normalized.slice(0, requiredCount)
}

function buildTimerExtraSeatSelections(timer, requiredCount = null) {
  const baseTable = parseTableNoParts(timer?.tableNo)
  const fallbackArea = baseTable.tableArea || TABLE_AREA_OPTIONS[0]
  const resolvedRequiredCount = requiredCount === null
    ? getRequiredExtraSeatCount(timer?.packagePlan, billingRules.value)
    : Math.max(0, Math.floor(Number(requiredCount) || 0))
  if (resolvedRequiredCount <= 0) return []

  const sourceSeats = getTimerExtraTableNos(timer, { limitByPackage: false })
  return Array.from({ length: resolvedRequiredCount }, (_, index) => {
    const parsed = parseTableNoParts(sourceSeats[index], fallbackArea, '')
    const tableNo = buildTableNo(parsed.tableArea, parsed.tableSeat)
    return {
      tableArea: parsed.tableArea || fallbackArea,
      tableSeat: parsed.tableSeat || '',
      tableNo
    }
  })
}

function formatTimerTableNoDisplay(timer) {
  const seats = getTimerOccupiedTableNos(timer)
  if (seats.length > 0) return seats.join(' / ')

  const fallback = normalizeTableNo(timer?.tableNo)
  if (fallback) return fallback
  return ''
}

function formatTimerSpeechDeskLabel(timer) {
  const deskCodes = getTimerOccupiedTableNos(timer)
    .map((seatNo) => toDeskSpeechCode(seatNo))
    .filter(Boolean)
  if (deskCodes.length > 0) return deskCodes.join('、')
  return timer?.customerName || `客户${timer?.customerId || ''}`
}

function buildSeatLayoutTables(layoutTables = []) {
  const activeTimers = timers.value.filter((timer) => timer.status === 'active' || timer.status === 'paused')
  const seatOwnerMap = new Map()

  activeTimers.forEach((timer) => {
    getTimerOccupiedTableNos(timer).forEach((seatNo) => {
      if (!seatOwnerMap.has(seatNo)) {
        seatOwnerMap.set(seatNo, timer)
      }
    })
  })

  return layoutTables.map((table) => {
    const seats = Array.from({ length: table.seatCount }, (_, index) => {
      const seatNo = String(index + 1)
      const tableNo = `${table.area}桌${seatNo}号`
      const matchedTimer = seatOwnerMap.get(tableNo)
      return {
        seatNo,
        occupied: Boolean(matchedTimer),
        customerName: matchedTimer?.customerName || '',
        timerId: matchedTimer?.id || ''
      }
    })
    return {
      ...table,
      occupiedCount: seats.filter((seat) => seat.occupied).length,
      seats
    }
  })
}

const seatLayoutTables = computed(() => buildSeatLayoutTables(LIVING_ROOM_LAYOUT_TABLES))
const smallRoomSeatLayoutTables = computed(() => buildSeatLayoutTables(SMALL_ROOM_LAYOUT_TABLES))
const gardenSeatLayoutTables = computed(() => buildSeatLayoutTables(GARDEN_LAYOUT_TABLES))
const upstairsSeatLayoutTables = computed(() => buildSeatLayoutTables(UPSTAIRS_LAYOUT_TABLES))

const livingRoomSeatSummary = computed(() => {
  const totals = seatLayoutTables.value.reduce((acc, table) => {
    acc.total += Number(table.seatCount) || 0
    acc.occupied += Number(table.occupiedCount) || 0
    return acc
  }, { total: 0, occupied: 0 })

  return {
    total: totals.total,
    occupied: totals.occupied,
    available: Math.max(0, totals.total - totals.occupied)
  }
})

const smallRoomSeatSummary = computed(() => {
  const totals = smallRoomSeatLayoutTables.value.reduce((acc, table) => {
    acc.total += Number(table.seatCount) || 0
    acc.occupied += Number(table.occupiedCount) || 0
    return acc
  }, { total: 0, occupied: 0 })

  return {
    total: totals.total,
    occupied: totals.occupied,
    available: Math.max(0, totals.total - totals.occupied)
  }
})

const gardenSeatSummary = computed(() => {
  const totals = gardenSeatLayoutTables.value.reduce((acc, table) => {
    acc.total += Number(table.seatCount) || 0
    acc.occupied += Number(table.occupiedCount) || 0
    return acc
  }, { total: 0, occupied: 0 })

  return {
    total: totals.total,
    occupied: totals.occupied,
    available: Math.max(0, totals.total - totals.occupied)
  }
})

const upstairsSeatSummary = computed(() => {
  const totals = upstairsSeatLayoutTables.value.reduce((acc, table) => {
    acc.total += Number(table.seatCount) || 0
    acc.occupied += Number(table.occupiedCount) || 0
    return acc
  }, { total: 0, occupied: 0 })

  return {
    total: totals.total,
    occupied: totals.occupied,
    available: Math.max(0, totals.total - totals.occupied)
  }
})

const overallSeatSummary = computed(() => {
  const summaries = [
    livingRoomSeatSummary.value,
    smallRoomSeatSummary.value,
    gardenSeatSummary.value,
    upstairsSeatSummary.value
  ]

  return summaries.reduce((acc, summary) => {
    acc.total += Number(summary?.total) || 0
    acc.occupied += Number(summary?.occupied) || 0
    acc.available += Number(summary?.available) || 0
    return acc
  }, { total: 0, occupied: 0, available: 0 })
})

const seatOverviewSections = computed(() => ([
  {
    key: 'living',
    title: '客厅',
    subtitle: '大厅区域',
    summary: livingRoomSeatSummary.value,
    tables: seatLayoutTables.value,
    panelClass: 'border-slate-200 bg-gradient-to-br from-slate-50 via-blue-50 to-cyan-50',
    badgeClass: 'bg-blue-100 text-blue-700'
  },
  {
    key: 'small',
    title: '小房间',
    subtitle: '私密小间',
    summary: smallRoomSeatSummary.value,
    tables: smallRoomSeatLayoutTables.value,
    panelClass: 'border-fuchsia-200 bg-gradient-to-br from-violet-50 via-fuchsia-50 to-pink-50',
    badgeClass: 'bg-fuchsia-100 text-fuchsia-700'
  },
  {
    key: 'garden',
    title: '花园',
    subtitle: '露台区域',
    summary: gardenSeatSummary.value,
    tables: gardenSeatLayoutTables.value,
    panelClass: 'border-emerald-200 bg-gradient-to-br from-emerald-50 via-lime-50 to-teal-50',
    badgeClass: 'bg-emerald-100 text-emerald-700'
  },
  {
    key: 'upstairs',
    title: '楼上',
    subtitle: '楼上区域',
    summary: upstairsSeatSummary.value,
    tables: upstairsSeatLayoutTables.value,
    panelClass: 'border-amber-200 bg-gradient-to-br from-amber-50 via-yellow-50 to-orange-50',
    badgeClass: 'bg-amber-100 text-amber-700'
  }
]))

function getUpstairsSeatGridPositionClass(seatNo) {
  const normalizedSeat = String(seatNo || '').trim()
  if (normalizedSeat === '1') return 'col-start-1 row-start-2'
  if (normalizedSeat === '2') return 'col-start-3 row-start-2'
  if (normalizedSeat === '3') return 'col-start-2 row-start-3'
  return 'col-start-2 row-start-2'
}

function isGardenKTable(tableArea) {
  return String(tableArea || '').trim().toUpperCase() === 'K'
}

function getGardenSeatGridPositionClass(tableArea, seatNo) {
  if (!isGardenKTable(tableArea)) return ''
  const normalizedSeat = String(seatNo || '').trim()
  if (normalizedSeat === '1') return 'col-start-2 row-start-1'
  if (normalizedSeat === '2') return 'col-start-3 row-start-1'
  if (normalizedSeat === '3') return 'col-start-1 row-start-2'
  if (normalizedSeat === '4') return 'col-start-1 row-start-3'
  if (normalizedSeat === '5') return 'col-start-4 row-start-2'
  if (normalizedSeat === '6') return 'col-start-4 row-start-3'
  return 'col-start-2 row-start-2'
}

function isTableNoOccupied(tableNo, excludeTimerId = '') {
  const normalized = normalizeTableNo(tableNo)
  if (!normalized) return false
  return timers.value.some((timer) => (
    timer.status !== 'completed'
    && timer.id !== excludeTimerId
    && getTimerOccupiedTableNos(timer).includes(normalized)
  ))
}

function loadWarnedTimerIds() {
  if (typeof window === 'undefined') return new Set()
  try {
    const raw = window.localStorage.getItem(WARNING_STORAGE_KEY)
    const parsed = raw ? JSON.parse(raw) : []
    if (!Array.isArray(parsed)) return new Set()
    return new Set(parsed.map((item) => String(item || '').trim()).filter(Boolean))
  } catch {
    return new Set()
  }
}

function persistWarnedTimerIds() {
  if (typeof window === 'undefined') return
  try {
    window.localStorage.setItem(WARNING_STORAGE_KEY, JSON.stringify(Array.from(warnedTimerIds.value)))
  } catch (error) {
    console.error('保存计时提醒状态失败:', error)
  }
}

function resolvePreferredFemaleVoice() {
  if (typeof window === 'undefined' || !window.speechSynthesis) return null

  const voices = window.speechSynthesis.getVoices()
  if (!Array.isArray(voices) || voices.length === 0) return null

  const zhVoices = voices.filter((voice) => String(voice?.lang || '').toLowerCase().startsWith('zh'))
  if (zhVoices.length === 0) return voices[0] || null

  const rankedVoiceKeywordGroups = [
    ['xiaoxiao', 'natural'],
    ['xiaoxiao', 'neural'],
    ['xiaoxiao'],
    ['xiaoyi', 'natural'],
    ['xiaoyi', 'neural'],
    ['xiaoyi'],
    ['female'],
    ['woman'],
    ['女']
  ]

  for (const keywords of rankedVoiceKeywordGroups) {
    const matched = zhVoices.find((voice) => {
      const lowerName = String(voice?.name || '').toLowerCase()
      return keywords.every((keyword) => lowerName.includes(keyword))
    })
    if (matched) return matched
  }

  const matchedGenderHint = zhVoices.find((voice) => String(voice?.name || '').includes('女'))
  if (matchedGenderHint) return matchedGenderHint

  return zhVoices[0] || voices[0] || null
}

function buildSpeechUtterance(text) {
  if (typeof window === 'undefined' || typeof window.SpeechSynthesisUtterance !== 'function') return null
  const utterance = new window.SpeechSynthesisUtterance(text)
  utterance.lang = 'zh-CN'
  utterance.rate = 0.94
  utterance.pitch = 1.12
  utterance.volume = 1
  const voice = resolvePreferredFemaleVoice()
  if (voice) {
    utterance.voice = voice
    utterance.lang = voice.lang || 'zh-CN'
  }
  return utterance
}

function playLeadTone() {
  if (typeof window === 'undefined') return
  try {
    const AudioContextCtor = window.AudioContext || window.webkitAudioContext
    if (!AudioContextCtor) return

    const ctx = new AudioContextCtor()
    const playBeep = (startAt, frequency = 880) => {
      const oscillator = ctx.createOscillator()
      const gainNode = ctx.createGain()
      oscillator.type = 'sine'
      oscillator.frequency.value = frequency
      gainNode.gain.setValueAtTime(0.0001, startAt)
      gainNode.gain.exponentialRampToValueAtTime(0.2, startAt + 0.02)
      gainNode.gain.exponentialRampToValueAtTime(0.0001, startAt + 0.22)
      oscillator.connect(gainNode)
      gainNode.connect(ctx.destination)
      oscillator.start(startAt)
      oscillator.stop(startAt + 0.22)
    }
    playBeep(ctx.currentTime, 880)
    playBeep(ctx.currentTime + 0.32, 1046.5)
    window.setTimeout(() => {
      ctx.close().catch(() => {})
    }, 700)
  } catch (error) {
    console.error('提示音播放失败:', error)
  }
}

function speakWarningText(text) {
  if (typeof window === 'undefined') return
  const synth = window.speechSynthesis
  if (!synth || typeof window.SpeechSynthesisUtterance !== 'function') return
  try {
    synth.cancel()
    const utterance = buildSpeechUtterance(text)
    if (!utterance) return
    playLeadTone()
    window.setTimeout(() => {
      synth.speak(utterance)
    }, 620)
  } catch (error) {
    console.error('语音播报失败:', error)
  }
}

function testSpeakerBroadcast() {
  if (typeof window === 'undefined') {
    showFeedback('error', '当前环境不支持语音播报。')
    return
  }

  const synth = window.speechSynthesis
  if (!synth || typeof window.SpeechSynthesisUtterance !== 'function') {
    showFeedback('error', '浏览器不支持语音播报，请更换浏览器后重试。')
    return
  }

  try {
    synth.cancel()
    const utterance = buildSpeechUtterance('语音测试，a1、a2剩余十分钟。请检查扬声器是否有声音。')
    if (!utterance) {
      showFeedback('error', '当前浏览器语音能力不可用。')
      return
    }
    utterance.onerror = () => {
      showFeedback('error', '测试播报失败，请检查浏览器语音权限与系统输出设备。')
    }
    playLeadTone()
    window.setTimeout(() => {
      synth.speak(utterance)
    }, 620)
    showFeedback('info', '已触发测试播报，请检查扬声器输出。')
  } catch (error) {
    console.error('测试播报失败:', error)
    showFeedback('error', '测试播报失败，请检查浏览器语音能力。')
  }
}

function showNextWarning() {
  if (activeWarning.value || warningQueue.value.length === 0) return
  const nextWarning = warningQueue.value.shift()
  if (!nextWarning) return
  activeWarning.value = nextWarning
  speakWarningText(nextWarning.speechText)
}

function queueTimerWarning(timer) {
  if (!timer?.id) return
  const timerId = String(timer.id)
  if (warnedTimerIds.value.has(timerId) || pendingWarningTimerIds.has(timerId)) return

  const triggerMinute = PACKAGE_TRIGGER_MINUTES[timer.packagePlan]
  const totalMinutes = PACKAGE_TOTAL_MINUTES[timer.packagePlan]
  if (!Number.isFinite(triggerMinute) || !Number.isFinite(totalMinutes)) return

  const elapsedMinutes = getElapsedMinutes(timer)
  const remainingMinutes = Math.max(0, totalMinutes - elapsedMinutes)
  const deskLabel = formatTimerSpeechDeskLabel(timer)
  const tableNoDisplay = formatTimerTableNoDisplay(timer)
  const warning = {
    timerId,
    tableNo: tableNoDisplay,
    customerName: timer.customerName || '',
    packagePlan: timer.packagePlan,
    remainingMinutes,
    speechText: `${deskLabel}剩余${remainingMinutes}分钟`,
    triggeredAt: nowTimestamp.value
  }

  pendingWarningTimerIds.add(timerId)
  warningQueue.value.push(warning)
  showNextWarning()
}

function dismissActiveWarning() {
  if (!activeWarning.value) return
  const timerId = String(activeWarning.value.timerId || '')
  if (timerId) {
    warnedTimerIds.value.add(timerId)
    pendingWarningTimerIds.delete(timerId)
    persistWarnedTimerIds()
  }
  activeWarning.value = null
  showNextWarning()
}

function evaluateWarnings() {
  if (typeof window !== 'undefined' && window.__STUDIO_GLOBAL_TIMER_WARNING_CENTER__) return
  timers.value.forEach((timer) => {
    if (timer.status !== 'active') return
    const triggerMinute = PACKAGE_TRIGGER_MINUTES[timer.packagePlan]
    if (!Number.isFinite(triggerMinute)) return
    if (getElapsedMinutes(timer) < triggerMinute) return
    queueTimerWarning(timer)
  })
}

function toServerDateTimestamp(dateTime) {
  if (!dateTime) return Number.NaN

  if (typeof dateTime !== 'string') {
    return new Date(dateTime).getTime()
  }

  const hasTimezone = /([zZ]|[+\-]\d{2}:\d{2})$/.test(dateTime)
  const normalized = hasTimezone ? dateTime : `${dateTime}Z`
  return new Date(normalized).getTime()
}

function normalizeStoredMiscSelections(rawMiscSelections) {
  if (!rawMiscSelections || typeof rawMiscSelections !== 'object') return {}

  const normalized = {}
  Object.entries(rawMiscSelections).forEach(([rawId, rawValue]) => {
    const id = String(rawId || '').trim()
    if (!id) return

    const amount = Number(rawValue)
    if (!Number.isFinite(amount) || amount < 0) return

    normalized[id] = Math.floor(amount)
  })
  return normalized
}

function parseTimerNotes(rawNotes) {
  const createDefaultNotes = (note = '') => ({
    note,
    packagePlan: '',
    extraTableNos: [],
    secondTableNo: '',
    meituanCustomer: false,
    meituanPackageBaseFee: 0,
    timing: {
      elapsedSeconds: 0,
      resumedAt: ''
    },
    materials: {
      largeImages: 0,
      extraSmallImages: 0,
      extraLargeImages: 0
    },
    miscSelections: {}
  })
  const normalizeExtraSeatList = (rawExtraTableNos, legacySecondTableNo = '') => {
    const source = Array.isArray(rawExtraTableNos) ? rawExtraTableNos : []
    const list = []
    const seen = new Set()
    const pushSeat = (rawSeatNo) => {
      const tableNo = normalizeTableNo(rawSeatNo)
      if (!isValidTableNo(tableNo)) return
      if (seen.has(tableNo)) return
      seen.add(tableNo)
      list.push(tableNo)
    }
    source.forEach((item) => pushSeat(item))
    if (list.length === 0 && legacySecondTableNo) {
      pushSeat(legacySecondTableNo)
    }
    return list
  }

  if (!rawNotes) {
    return createDefaultNotes('')
  }

  try {
    const parsed = JSON.parse(rawNotes)
    if (parsed && typeof parsed === 'object') {
      const extraTableNos = normalizeExtraSeatList(parsed.extraTableNos, parsed.secondTableNo)
      return {
        note: parsed.note || '',
        packagePlan: parsed.packagePlan || '',
        extraTableNos,
        secondTableNo: extraTableNos[0] || '',
        meituanCustomer: Boolean(parsed.meituanCustomer),
        meituanPackageBaseFee: Number(parsed.meituanPackageBaseFee) || 0,
        timing: {
          elapsedSeconds: Math.max(0, Math.floor(Number(parsed.timing?.elapsedSeconds) || 0)),
          resumedAt: String(parsed.timing?.resumedAt || '')
        },
        materials: {
          largeImages: Number(parsed.materials?.largeImages) || 0,
          extraSmallImages: Number(parsed.materials?.extraSmallImages) || 0,
          extraLargeImages: Number(parsed.materials?.extraLargeImages) || 0
        },
        miscSelections: normalizeStoredMiscSelections(parsed.miscSelections)
      }
    }
  } catch {
    // fallback to plain text.
  }

  return createDefaultNotes(String(rawNotes))
}

function normalizeTimer(timer = {}) {
  const parsedNotes = parseTimerNotes(timer.notes)
  const customerId = timer.customerId ?? timer.customer_id ?? ''
  const status = timer.status || 'active'
  const timing = {
    elapsedSeconds: Math.max(0, Math.floor(Number(parsedNotes.timing?.elapsedSeconds) || 0)),
    resumedAt: String(parsedNotes.timing?.resumedAt || '')
  }

  if (status === 'paused' && timing.elapsedSeconds <= 0) {
    const startTime = timer.startTime ?? timer.start_time ?? null
    const startMs = toServerDateTimestamp(startTime)
    if (Number.isFinite(startMs)) {
      timing.elapsedSeconds = Math.floor(Math.max(0, nowTimestamp.value - startMs) / 1000)
      timing.resumedAt = ''
    }
  }

  return {
    id: timer.id,
    customerId,
    customerName: timer.customer?.name || customerMap.value.get(customerId)?.name || '',
    tableNo: normalizeTableNo(timer.tableNo ?? timer.table_no),
    status,
    timerType: timer.timerType ?? timer.timer_type ?? 'limited',
    startTime: timer.startTime ?? timer.start_time ?? null,
    notes: parsedNotes.note,
    packagePlan: parsedNotes.packagePlan || '',
    extraTableNos: Array.isArray(parsedNotes.extraTableNos) ? parsedNotes.extraTableNos : [],
    secondTableNo: parsedNotes.secondTableNo || '',
    meituanCustomer: Boolean(parsedNotes.meituanCustomer),
    meituanPackageBaseFee: Number(parsedNotes.meituanPackageBaseFee) || 0,
    timing,
    materials: parsedNotes.materials,
    miscSelections: normalizeStoredMiscSelections(parsedNotes.miscSelections)
  }
}

function toNonNegativeInteger(value) {
  const n = Number(value)
  if (!Number.isFinite(n) || n < 0) return null
  return Math.floor(n)
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

function syncSettleMiscSelections(seed = null) {
  const source = seed !== null ? seed : settleForm.miscSelections
  settleForm.miscSelections = createMiscSelectionMap(source)
}

function syncAddMiscSelections(seed = null) {
  const source = seed !== null ? seed : addForm.miscSelections
  addForm.miscSelections = createMiscSelectionMap(source)
}

function syncEditMiscSelections(seed = null) {
  const source = seed !== null ? seed : editForm.miscSelections
  editForm.miscSelections = createMiscSelectionMap(source)
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

function buildTimerNotesPayload(timer, materials, miscSelections = null) {
  const extraTableNos = getTimerExtraTableNos(timer, { limitByPackage: false })
  const sourceMiscSelections = miscSelections === null ? timer?.miscSelections : miscSelections
  return JSON.stringify({
    note: timer?.notes || '',
    packagePlan: timer?.packagePlan || '',
    extraTableNos,
    secondTableNo: extraTableNos[0] || '',
    meituanCustomer: Boolean(timer?.meituanCustomer),
    meituanPackageBaseFee: Number(timer?.meituanPackageBaseFee) || 0,
    timing: {
      elapsedSeconds: Math.max(0, Math.floor(Number(timer?.timing?.elapsedSeconds) || 0)),
      resumedAt: String(timer?.timing?.resumedAt || '')
    },
    materials: {
      largeImages: Number(materials?.largeImages) || 0,
      extraSmallImages: Number(materials?.extraSmallImages) || 0,
      extraLargeImages: Number(materials?.extraLargeImages) || 0
    },
    miscSelections: normalizeStoredMiscSelections(sourceMiscSelections)
  })
}

function formatAmount(value) {
  const amount = Number(value) || 0
  return amount.toFixed(2)
}

function formatDateTime(dateTime) {
  if (!dateTime) return '-'
  const timestamp = toServerDateTimestamp(dateTime)
  if (!Number.isFinite(timestamp)) return '-'

  return new Date(timestamp).toLocaleString('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit'
  })
}

function formatDuration(totalSeconds) {
  const safeSeconds = Math.max(0, Number(totalSeconds) || 0)
  const hours = Math.floor(safeSeconds / 3600)
  const minutes = Math.floor((safeSeconds % 3600) / 60)
  const seconds = safeSeconds % 60

  return `${String(hours).padStart(2, '0')}:${String(minutes).padStart(2, '0')}:${String(seconds).padStart(2, '0')}`
}

function getElapsedSeconds(timer, timestamp = nowTimestamp.value) {
  const safeTimestamp = Number.isFinite(timestamp) ? timestamp : Date.now()
  const startMs = toServerDateTimestamp(timer?.startTime)
  const fallbackSeconds = Number.isFinite(startMs)
    ? Math.floor(Math.max(0, safeTimestamp - startMs) / 1000)
    : 0

  const baseElapsedSeconds = Math.max(0, Math.floor(Number(timer?.timing?.elapsedSeconds) || 0))
  const resumedAtMs = toServerDateTimestamp(timer?.timing?.resumedAt)

  if (timer?.status === 'paused') {
    return baseElapsedSeconds > 0 ? baseElapsedSeconds : fallbackSeconds
  }

  if (baseElapsedSeconds > 0 && Number.isFinite(resumedAtMs)) {
    const activeDeltaSeconds = Math.floor(Math.max(0, safeTimestamp - resumedAtMs) / 1000)
    return baseElapsedSeconds + activeDeltaSeconds
  }

  return fallbackSeconds
}

function getElapsedMinutes(timer, timestamp = nowTimestamp.value) {
  return Math.floor(getElapsedSeconds(timer, timestamp) / 60)
}

function getStatusClass(status) {
  const map = {
    active: 'bg-green-100 text-green-800',
    paused: 'bg-yellow-100 text-yellow-800'
  }

  return map[status] || 'bg-gray-100 text-gray-800'
}

function getStatusLabel(status) {
  const map = {
    active: '进行中',
    paused: '已暂停'
  }

  return map[status] || status
}

async function fetchCustomers() {
  try {
    const response = await api.get('/customers', { params: { page: 1, page_size: 1000 } })
    const payload = unwrapData(response, {})
    const items = Array.isArray(payload.items) ? payload.items : []
    customers.value = items
  } catch (error) {
    console.error('获取客户失败:', error)
    customers.value = []
  }
}

async function fetchBillingRules() {
  try {
    const response = await api.get('/billing-rules')
    const payload = unwrapData(response, {})
    billingRules.value = normalizeBillingRules(payload)
    syncSettleMiscSelections()
    syncAddMiscSelections()
    syncEditMiscSelections()
  } catch (error) {
    console.error('获取计费规则失败:', error)
    billingRules.value = normalizeBillingRules()
    syncSettleMiscSelections()
    syncAddMiscSelections()
    syncEditMiscSelections()
  }
}

async function fetchTimers() {
  loading.value = true
  try {
    const response = await api.get('/active-timers')
    const payload = unwrapData(response, [])
    const list = Array.isArray(payload) ? payload : []
    timers.value = list.map(normalizeTimer)
  } catch (error) {
    console.error('获取计时记录失败:', error)
    timers.value = []
    showFeedback('error', '计时记录加载失败，请稍后重试。')
  } finally {
    loading.value = false
  }
}

function resetAddForm() {
  Object.assign(addForm, createTimerConsumeForm('', billingRules.value))
  syncAddMiscSelections({})
  addErrors.value = {}
}

async function fetchCustomerBalance(customerId = '') {
  if (!customerId) return null

  try {
    const response = await api.get(`/customers/${customerId}/balance`)
    const payload = unwrapData(response, {})
    const balance = Number(payload?.balance)
    return Number.isFinite(balance) ? balance : 0
  } catch (error) {
    console.error('获取客户余额失败:', error)
    return null
  }
}

async function syncAddBalance(customerId = '') {
  addCurrentBalance.value = null
  if (!customerId) return

  addBalanceLoading.value = true
  try {
    addCurrentBalance.value = await fetchCustomerBalance(customerId)
  } finally {
    addBalanceLoading.value = false
  }
}

function applyAddForm(nextForm = {}) {
  Object.assign(addForm, createTimerConsumeForm('', billingRules.value), nextForm)
}

function resetFilters() {
  filterForm.keyword = ''
  filterForm.timerType = ''
  filterForm.packagePlan = ''
}

function resetEditForm(timer = null) {
  const packagePlan = timer?.packagePlan || getDefaultAddPackagePlan(timer?.timerType || 'limited')
  const requiredExtraSeatCount = getRequiredExtraSeatCount(packagePlan, billingRules.value)
  const tableParts = parseTableNoParts(timer?.tableNo)
  const extraTableSelections = buildTimerExtraSeatSelections(timer, requiredExtraSeatCount)
  const extraTableNos = extraTableSelections
    .map((item) => normalizeTableNo(item?.tableNo || buildTableNo(item?.tableArea, item?.tableSeat)))
    .filter((item) => Boolean(item))
  const firstExtraSeat = extraTableSelections[0] || {
    tableArea: tableParts.tableArea,
    tableSeat: '',
    tableNo: ''
  }

  editForm.tableArea = tableParts.tableArea
  editForm.tableSeat = tableParts.tableSeat
  editForm.tableNo = buildTableNo(tableParts.tableArea, tableParts.tableSeat)
  editForm.extraTableSelections = extraTableSelections
  editForm.extraTableNos = extraTableNos
  editForm.secondTableArea = firstExtraSeat.tableArea || tableParts.tableArea
  editForm.secondTableSeat = firstExtraSeat.tableSeat || ''
  editForm.secondTableNo = firstExtraSeat.tableNo || ''
  editForm.packagePlan = packagePlan
  editForm.notes = timer?.notes || ''
  editForm.largeImages = Number(timer?.materials?.largeImages) || 0
  editForm.extraSmallImages = Number(timer?.materials?.extraSmallImages) || 0
  editForm.extraLargeImages = Number(timer?.materials?.extraLargeImages) || 0
  syncEditMiscSelections(timer?.miscSelections || {})
  editErrors.value = {}
}

function syncEditSeatPayload() {
  const seatPayload = getTimerConsumeSeatPayload(editForm, billingRules.value)
  const firstExtraSeat = seatPayload.extraTableSelections[0] || {
    tableArea: seatPayload.tableArea,
    tableSeat: '',
    tableNo: ''
  }
  editForm.tableArea = seatPayload.tableArea
  editForm.tableSeat = seatPayload.tableSeat
  editForm.tableNo = seatPayload.tableNo
  editForm.extraTableSelections = seatPayload.extraTableSelections
  editForm.extraTableNos = seatPayload.extraTableNos
  editForm.secondTableArea = firstExtraSeat.tableArea
  editForm.secondTableSeat = firstExtraSeat.tableSeat
  editForm.secondTableNo = firstExtraSeat.tableNo
}

function updateEditExtraSeatArea(index, value) {
  const list = Array.isArray(editForm.extraTableSelections)
    ? editForm.extraTableSelections.map((item) => ({ ...item }))
    : []
  if (!list[index]) return
  const area = String(value || '').trim().toUpperCase()
  list[index] = {
    ...list[index],
    tableArea: area,
    tableNo: buildTableNo(area, list[index].tableSeat)
  }
  editForm.extraTableSelections = list
  syncEditSeatPayload()
}

function updateEditExtraSeatSeat(index, value) {
  const list = Array.isArray(editForm.extraTableSelections)
    ? editForm.extraTableSelections.map((item) => ({ ...item }))
    : []
  if (!list[index]) return
  const seat = String(value || '').trim()
  list[index] = {
    ...list[index],
    tableSeat: seat,
    tableNo: buildTableNo(list[index].tableArea, seat)
  }
  editForm.extraTableSelections = list
  syncEditSeatPayload()
}

function getEditExtraSeatError(index) {
  return editErrors.value?.[`extraTableNos.${index}`]
    || (index === 0 ? editErrors.value?.secondTableNo : '')
    || ''
}

function isMeituanCustomerByName(name) {
  const text = String(name || '').trim()
  return text === '美团客户'
}

function resetSettleForm(timer = null) {
  settleForm.billingType = timer?.timerType || 'limited'
  settleForm.duration = '1'
  settleForm.weekdayType = getDefaultAddPackagePlan('weekday')
  settleForm.weekendType = getDefaultAddPackagePlan('weekend')
  settleForm.overtimeMinutes = 0
  settleForm.largeImages = Number(timer?.materials?.largeImages) || 0
  settleForm.extraSmallImages = Number(timer?.materials?.extraSmallImages) || 0
  settleForm.extraLargeImages = Number(timer?.materials?.extraLargeImages) || 0
  syncSettleMiscSelections(timer?.miscSelections || {})
  settleForm.additionalFee = 0
  settleForm.notes = timer?.notes || ''
  settleForm.meituanCustomer = Boolean(
    timer?.meituanCustomer || isMeituanCustomerByName(timer?.customerName)
  )
  settleForm.applyOvertimeFee = true
  settleForm.useManualElapsed = false
  settleForm.manualElapsedMinutes = getElapsedMinutes(timer)

  settleErrors.value = {}
}

async function openAddModal() {
  if (showLivingRoomModal.value) {
    restoreRoomAfterAddModal.value = 'living'
    closeLivingRoomModal()
  } else if (showSmallRoomModal.value) {
    restoreRoomAfterAddModal.value = 'small'
    closeSmallRoomModal()
  } else if (showGardenModal.value) {
    restoreRoomAfterAddModal.value = 'garden'
    closeGardenModal()
  } else if (showUpstairsModal.value) {
    restoreRoomAfterAddModal.value = 'upstairs'
    closeUpstairsModal()
  } else if (showSeatOverviewModal.value) {
    restoreRoomAfterAddModal.value = 'overview'
    closeSeatOverviewModal()
  } else {
    restoreRoomAfterAddModal.value = ''
  }
  resetAddForm()
  addCurrentBalance.value = null
  addBalanceLoading.value = false
  showAddModal.value = true
  await nextTick()
  addTimerDialogRef.value?.focusFirstField?.()
}

function openLivingRoomModal() {
  deactivateMultiSeatSelectionMode()
  showLivingRoomModal.value = true
}

function closeLivingRoomModal() {
  deactivateMultiSeatSelectionMode()
  showLivingRoomModal.value = false
}

function openSmallRoomModal() {
  deactivateMultiSeatSelectionMode()
  showSmallRoomModal.value = true
}

function closeSmallRoomModal() {
  deactivateMultiSeatSelectionMode()
  showSmallRoomModal.value = false
}

function openGardenModal() {
  deactivateMultiSeatSelectionMode()
  showGardenModal.value = true
}

function closeGardenModal() {
  deactivateMultiSeatSelectionMode()
  showGardenModal.value = false
}

function openUpstairsModal() {
  deactivateMultiSeatSelectionMode()
  showUpstairsModal.value = true
}

function closeUpstairsModal() {
  deactivateMultiSeatSelectionMode()
  showUpstairsModal.value = false
}

function openSeatOverviewModal() {
  deactivateMultiSeatSelectionMode()
  showSeatOverviewModal.value = true
}

function closeSeatOverviewModal() {
  deactivateMultiSeatSelectionMode()
  showSeatOverviewModal.value = false
}

async function openAddModalForSeat(tableArea, seatNo, occupied = false) {
  if (occupied) {
    showFeedback('error', `该座位已有人：${tableArea}${seatNo}`)
    return
  }
  await openAddModal()
  const area = String(tableArea || '').trim().toUpperCase()
  const seat = String(seatNo || '').trim()
  addForm.tableArea = area
  addForm.tableSeat = seat
  addForm.tableNo = buildTableNo(area, seat)
  addForm.extraTableSelections = []
  addForm.extraTableNos = []
  addForm.secondTableArea = area
  addForm.secondTableSeat = ''
  addForm.secondTableNo = ''
}

function clearPendingMultiSeatSelection() {
  pendingMultiSeatSelection.value = null
}

function activateMultiSeatSelectionMode() {
  if (seatSelectionMode.value === 'multi') return
  seatSelectionMode.value = 'multi'
  clearPendingMultiSeatSelection()
  showFeedback('info', '已进入多人选座模式，左键依次点选座位，选好后点确认')
}

function deactivateMultiSeatSelectionMode(showMessage = false) {
  seatSelectionMode.value = 'single'
  clearPendingMultiSeatSelection()
  if (showMessage) {
    showFeedback('info', '已切回单座位模式')
  }
}

function getPendingSeatDisplayText() {
  const seats = Array.isArray(pendingMultiSeatSelection.value?.seats)
    ? pendingMultiSeatSelection.value.seats
    : []
  if (seats.length === 0) return ''
  return seats.map((item) => `${item.tableArea}${item.seatNo}`).join(' / ')
}

function isPendingSeatSelected(tableArea, seatNo) {
  const area = String(tableArea || '').trim().toUpperCase()
  const seat = String(seatNo || '').trim()
  return Array.isArray(pendingMultiSeatSelection.value?.seats)
    && pendingMultiSeatSelection.value.seats.some((item) => item.tableArea === area && item.seatNo === seat)
}

const pendingMultiSeatCount = computed(() => (
  Array.isArray(pendingMultiSeatSelection.value?.seats)
    ? pendingMultiSeatSelection.value.seats.length
    : 0
))

const pendingMultiSeatPreset = computed(() => {
  if (pendingMultiSeatCount.value < 2) return null
  return resolveMultiPersonPackagePresetByPeopleCount(pendingMultiSeatCount.value)
})

function resolveMultiPersonPackagePresetByPeopleCount(peopleCount) {
  const normalizedPeopleCount = Math.max(2, Math.floor(Number(peopleCount) || 0))
  const dayType = getEffectiveBillingDayType(new Date())
  const primaryType = dayType === 'weekend' ? 'weekend' : 'weekday'
  const searchOrder = primaryType === 'weekend'
    ? ['weekend', 'weekday']
    : ['weekday', 'weekend']

  for (const timerType of searchOrder) {
    const dayOptions = addPackagePlanOptionsByType.value[timerType] || []
    const multiPerson = dayOptions.find((item) => (
      getPackagePlanPeopleCount(item.value, billingRules.value) === normalizedPeopleCount
    ))
    if (multiPerson?.value) {
      return {
        timerType,
        packagePlan: multiPerson.value,
        peopleCount: normalizedPeopleCount
      }
    }
  }

  return null
}

async function handleSeatLeftClick(tableArea, seatNo, occupied = false) {
  const area = String(tableArea || '').trim().toUpperCase()
  const seat = String(seatNo || '').trim()

  if (seatSelectionMode.value !== 'multi') {
    await openAddModalForSeat(area, seat, occupied)
    return
  }

  if (occupied) {
    showFeedback('error', `该座位已有人：${area}${seat}`)
    return
  }

  const currentSeats = Array.isArray(pendingMultiSeatSelection.value?.seats)
    ? [...pendingMultiSeatSelection.value.seats]
    : []
  const existingIndex = currentSeats.findIndex((item) => item.tableArea === area && item.seatNo === seat)

  if (existingIndex >= 0) {
    currentSeats.splice(existingIndex, 1)
    pendingMultiSeatSelection.value = currentSeats.length > 0
      ? { seats: currentSeats }
      : null
    if (currentSeats.length > 0) {
      showFeedback('info', `已移除 ${area}${seat}，当前已选${currentSeats.length}个座位`)
    } else {
      showFeedback('info', '已清空多人选座，请重新点选')
    }
    return
  }

  currentSeats.push({
    tableArea: area,
    seatNo: seat
  })
  pendingMultiSeatSelection.value = { seats: currentSeats }

  const selectedCount = currentSeats.length
  const preset = selectedCount >= 2
    ? resolveMultiPersonPackagePresetByPeopleCount(selectedCount)
    : null

  if (selectedCount === 1) {
    showFeedback('info', `已选第一座位 ${area}${seat}，继续左键追加座位`)
    return
  }

  if (preset) {
    showFeedback('info', `已选${selectedCount}个座位，可直接确认进入${preset.peopleCount}人套餐`)
    return
  }

  showFeedback('error', `已选${selectedCount}个座位，但当前未配置对应多人套餐`)
}

async function confirmPendingMultiSeatSelection() {
  const currentSeats = Array.isArray(pendingMultiSeatSelection.value?.seats)
    ? [...pendingMultiSeatSelection.value.seats]
    : []

  if (currentSeats.length < 2) {
    showFeedback('error', '多人套餐至少需要选择2个座位')
    return
  }

  const preset = pendingMultiSeatPreset.value || resolveMultiPersonPackagePresetByPeopleCount(currentSeats.length)
  if (!preset) {
    pendingMultiSeatSelection.value = {
      seats: currentSeats
    }
    showFeedback('error', `当前未配置${currentSeats.length}人套餐，请在计费规则中新增并启用`)
    return
  }

  await openAddModal()
  const firstSeat = currentSeats[0]
  const extraSeats = currentSeats.slice(1).map((item) => ({
    tableArea: item.tableArea,
    tableSeat: item.seatNo,
    tableNo: buildTableNo(item.tableArea, item.seatNo)
  }))
  const firstExtraSeat = extraSeats[0] || {
    tableArea: firstSeat.tableArea,
    tableSeat: '',
    tableNo: ''
  }

  addForm.tableArea = firstSeat.tableArea
  addForm.tableSeat = firstSeat.seatNo
  addForm.tableNo = buildTableNo(firstSeat.tableArea, firstSeat.seatNo)
  addForm.extraTableSelections = extraSeats
  addForm.extraTableNos = extraSeats.map((item) => item.tableNo).filter(Boolean)
  addForm.secondTableArea = firstExtraSeat.tableArea
  addForm.secondTableSeat = firstExtraSeat.tableSeat
  addForm.secondTableNo = firstExtraSeat.tableNo
  addForm.timerType = preset.timerType
  addForm.packagePlan = preset.packagePlan
  deactivateMultiSeatSelectionMode()
  showFeedback('success', `已预填${preset.peopleCount}人套餐座位，请选择客户后开始计时`)
}

function closeAddModal(force = false) {
  if (!force && submitting.value) return
  showAddModal.value = false
  if (restoreRoomAfterAddModal.value === 'living') {
    showLivingRoomModal.value = true
  } else if (restoreRoomAfterAddModal.value === 'small') {
    showSmallRoomModal.value = true
  } else if (restoreRoomAfterAddModal.value === 'garden') {
    showGardenModal.value = true
  } else if (restoreRoomAfterAddModal.value === 'upstairs') {
    showUpstairsModal.value = true
  } else if (restoreRoomAfterAddModal.value === 'overview') {
    showSeatOverviewModal.value = true
  }
  addErrors.value = {}
  addCurrentBalance.value = null
  addBalanceLoading.value = false
  deactivateMultiSeatSelectionMode()
  restoreRoomAfterAddModal.value = ''
}

function openEditModal(timer) {
  editingTimer.value = timer
  resetEditForm(timer)
  showEditModal.value = true
}

function closeEditModal() {
  showEditModal.value = false
  editingTimer.value = null
  editErrors.value = {}
}

function openSettleModal(timer) {
  selectedTimer.value = timer
  resetSettleForm(timer)
  showSettleModal.value = true
  applyRecommendedSettlementPlan()
}

function closeSettleModal() {
  showSettleModal.value = false
  selectedTimer.value = null
  settleErrors.value = {}
}

function validateAddForm() {
  const seatPayload = getTimerConsumeSeatPayload(addForm, billingRules.value)
  const firstExtraSeat = seatPayload.extraTableSelections[0] || {
    tableArea: seatPayload.tableArea,
    tableSeat: '',
    tableNo: ''
  }
  addForm.tableArea = seatPayload.tableArea
  addForm.tableSeat = seatPayload.tableSeat
  addForm.extraTableSelections = seatPayload.extraTableSelections
  addForm.extraTableNos = seatPayload.extraTableNos
  addForm.secondTableArea = firstExtraSeat.tableArea
  addForm.secondTableSeat = firstExtraSeat.tableSeat
  addForm.secondTableNo = firstExtraSeat.tableNo

  const { isValid, errors } = validateSharedTimerConsumeForm(addForm, addTimerCustomerOptions.value, billingRules.value)
  const tableNo = normalizeTableNo(seatPayload.tableNo)
  addForm.tableNo = tableNo

  if (tableNo && !isValidTableNo(tableNo)) {
    errors.tableNo = '桌号必须在 A-H/J-N/P-Z 桌、1-20号范围内'
  } else if (tableNo && isTableNoOccupied(tableNo)) {
    errors.tableNo = `桌号已占用：${tableNo}`
  }

  const normalizedExtraTableNos = []
  seatPayload.extraTableSelections.forEach((selection, index) => {
    const tableNoAtIndex = normalizeTableNo(selection?.tableNo || buildTableNo(selection?.tableArea, selection?.tableSeat))
    if (!tableNoAtIndex || !isValidTableNo(tableNoAtIndex) || tableNoAtIndex === tableNo) return
    if (isTableNoOccupied(tableNoAtIndex)) {
      errors[`extraTableNos.${index}`] = `第${index + 2}座位已占用：${tableNoAtIndex}`
      return
    }
    normalizedExtraTableNos.push(tableNoAtIndex)
  })

  addForm.extraTableNos = normalizedExtraTableNos
  addForm.secondTableNo = normalizedExtraTableNos[0] || ''
  if (errors['extraTableNos.0']) {
    errors.secondTableNo = errors['extraTableNos.0']
  }
  if (!errors.extraTableNos) {
    const firstExtraError = Object.keys(errors)
      .filter((key) => key.startsWith('extraTableNos.'))
      .sort()[0]
    if (firstExtraError) {
      errors.extraTableNos = errors[firstExtraError]
    }
  }

  const miscErrors = collectMiscSelectionErrors(addForm.miscSelections)
  if (miscErrors.length > 0) {
    errors.misc = miscErrors[0]
  }

  addErrors.value = errors
  return isValid && Object.keys(errors).length === 0
}

function validateEditForm() {
  const errors = {}
  const seatPayload = getTimerConsumeSeatPayload(editForm, billingRules.value)
  const tableNo = normalizeTableNo(seatPayload.tableNo)
  const firstExtraSeat = seatPayload.extraTableSelections[0] || {
    tableArea: seatPayload.tableArea,
    tableSeat: '',
    tableNo: ''
  }
  editForm.tableArea = seatPayload.tableArea
  editForm.tableSeat = seatPayload.tableSeat
  editForm.tableNo = tableNo
  editForm.extraTableSelections = seatPayload.extraTableSelections
  editForm.extraTableNos = seatPayload.extraTableNos
  editForm.secondTableArea = firstExtraSeat.tableArea
  editForm.secondTableSeat = firstExtraSeat.tableSeat
  editForm.secondTableNo = firstExtraSeat.tableNo

  if (!editForm.packagePlan) {
    errors.packagePlan = '请选择初始套餐'
  }
  if (!tableNo) {
    errors.tableNo = '请选择桌号'
  } else if (!isValidTableNo(tableNo)) {
    errors.tableNo = '桌号必须在 A-H/J-N/P-Z 桌、1-20号范围内'
  } else if (isTableNoOccupied(tableNo, editingTimer.value?.id)) {
    errors.tableNo = `桌号已占用：${tableNo}`
  }

  const seenSeats = new Set(tableNo ? [tableNo] : [])
  const normalizedExtraTableNos = []
  seatPayload.extraTableSelections.forEach((selection, index) => {
    const seatLabel = `第${index + 2}座位`
    const tableNoAtIndex = normalizeTableNo(selection?.tableNo || buildTableNo(selection?.tableArea, selection?.tableSeat))
    const key = `extraTableNos.${index}`

    if (!tableNoAtIndex) {
      errors[key] = `${seatLabel}不能为空`
      return
    }
    if (!isValidTableNo(tableNoAtIndex)) {
      errors[key] = `${seatLabel}格式不正确`
      return
    }
    if (seenSeats.has(tableNoAtIndex)) {
      errors[key] = `${seatLabel}不能与已选座位重复`
      return
    }
    if (isTableNoOccupied(tableNoAtIndex, editingTimer.value?.id)) {
      errors[key] = `${seatLabel}已占用：${tableNoAtIndex}`
      return
    }

    seenSeats.add(tableNoAtIndex)
    normalizedExtraTableNos.push(tableNoAtIndex)
  })

  editForm.extraTableNos = normalizedExtraTableNos
  editForm.secondTableNo = normalizedExtraTableNos[0] || ''
  if (errors['extraTableNos.0']) {
    errors.secondTableNo = errors['extraTableNos.0']
  }
  if (!errors.extraTableNos) {
    const firstExtraError = Object.keys(errors)
      .filter((key) => key.startsWith('extraTableNos.'))
      .sort()[0]
    if (firstExtraError) {
      errors.extraTableNos = errors[firstExtraError]
    }
  }

  const largeImages = toNonNegativeInteger(editForm.largeImages)
  const extraSmallImages = toNonNegativeInteger(editForm.extraSmallImages)
  const extraLargeImages = toNonNegativeInteger(editForm.extraLargeImages)

  if (largeImages === null) errors.largeImages = '大图数量必须大于或等于 0'
  if (extraSmallImages === null) errors.extraSmallImages = '超量小图必须大于或等于 0'
  if (extraLargeImages === null) errors.extraLargeImages = '超量大图必须大于或等于 0'

  const miscErrors = collectMiscSelectionErrors(editForm.miscSelections)
  if (miscErrors.length > 0) {
    errors.misc = miscErrors[0]
  }

  editErrors.value = errors

  if (Object.keys(errors).length > 0) return null

  return {
    tableNo,
    extraTableSelections: seatPayload.extraTableSelections,
    extraTableNos: normalizedExtraTableNos,
    secondTableNo: normalizedExtraTableNos[0] || '',
    packagePlan: editForm.packagePlan,
    notes: String(editForm.notes || '').trim(),
    largeImages,
    extraSmallImages,
    extraLargeImages,
    miscSelections: createMiscSelectionMap(editForm.miscSelections)
  }
}

function resolveTimerTypeByPackagePlan(packagePlan, fallback = 'limited') {
  const info = resolvePackagePlanInfo(packagePlan, billingRules.value)
  if (info?.timerType) return info.timerType
  return fallback
}

function validateSettleForm() {
  const errors = {}

  if (!selectedTimer.value) {
    errors.general = '未选择计时记录'
  }

  if (settleForm.useManualElapsed) {
    const minutes = Number(settleForm.manualElapsedMinutes)
    if (!Number.isFinite(minutes) || minutes < 0) {
      errors.manualElapsed = '手动计时分钟必须大于或等于 0'
    }
  }

  if (settlePreview.value.total <= 0) {
    errors.total = '结算金额必须大于 0'
  }

  if (settleFinalAmount.value <= 0) {
    errors.total = '结算金额必须大于 0'
  }

  const miscErrors = collectMiscSelectionErrors(settleForm.miscSelections)
  if (miscErrors.length > 0) {
    errors.misc = miscErrors[0]
  }

  settleErrors.value = errors
  return Object.keys(errors).length === 0
}

async function startTimer() {
  if (!validateAddForm()) return

  submitting.value = true
  try {
    await api.post('/active-timers', buildTimerConsumeRequestPayload(addForm, billingRules.value))
    closeAddModal(true)
    await fetchTimers()
    showFeedback('success', '计时已开始。')
  } catch (error) {
    console.error('开始计时失败:', error)
    showFeedback('error', error?.response?.data?.message || error?.message || '开始计时失败')
  } finally {
    submitting.value = false
  }
}

async function saveTimerMaterials() {
  if (!editingTimer.value) return

  const materials = validateEditForm()
  if (!materials) return

  submitting.value = true
  try {
    const timerType = resolveTimerTypeByPackagePlan(materials.packagePlan, editingTimer.value.timerType)
    const notesPayload = buildTimerNotesPayload(
      {
        ...editingTimer.value,
        notes: materials.notes,
        packagePlan: materials.packagePlan,
        extraTableNos: materials.extraTableNos,
        secondTableNo: materials.secondTableNo
      },
      materials,
      materials.miscSelections
    )

    await api.put(`/active-timers/${editingTimer.value.id}`, {
      table_no: materials.tableNo,
      timer_type: timerType,
      notes: notesPayload
    })

    closeEditModal()
    await fetchTimers()
    showFeedback('success', '计时信息已更新。')
  } catch (error) {
    console.error('更新素材参数失败:', error)
    showFeedback('error', error?.response?.data?.message || error?.message || '更新素材参数失败')
  } finally {
    submitting.value = false
  }
}

async function submitSettlement() {
  if (!validateSettleForm()) return

  submitting.value = true
  try {
    const settleNotesParts = []
    const rawNotes = String(settleForm.notes || '').trim()

    if (rawNotes) {
      settleNotesParts.push(rawNotes)
    }

    if (settleOvertimeMinutes.value > 0) {
      if (settleForm.applyOvertimeFee) {
        settleNotesParts.push(
          `加班费用￥${formatAmount(settleOvertimeFee.value)}（${settleOvertimeMinutes.value}分钟，${settleOvertimePeopleCount.value}人，￥${formatAmount(settleOvertimeRatePerMinute.value)}/人/分钟）`
        )
      } else {
        settleNotesParts.push(
          `已取消加班费用（${settleOvertimeMinutes.value}分钟，${settleOvertimePeopleCount.value}人，原￥${formatAmount(settleOvertimeFeeByRule.value)}）`
        )
      }
    }

    if (settleForm.meituanCustomer) {
      settleNotesParts.push(`美团客户(按开始套餐抽成￥${formatAmount(settleMeituanDeduction.value)})`)
    }

    const settleNotes = settleNotesParts.join('；')

    const description = buildConsumptionDescription(
      {
        mode: 'timer',
        billingType: settlePreview.value.billingType,
        elapsedMinutes: settleElapsedMinutes.value
      },
      settlePreview.value,
      settleNotes
    )
    const miscSelections = createMiscSelectionMap(settleForm.miscSelections)

    await api.post(`/active-timers/${selectedTimer.value.id}/settle`, {
      amount: settleFinalAmount.value,
      description,
      notes: settleNotes,
      misc_selections: miscSelections
    })

    closeSettleModal()
    await fetchTimers()
    showFeedback('success', '计时已完成结算。')
  } catch (error) {
    console.error('结算失败:', error)
    showFeedback('error', error?.response?.data?.message || error?.message || '结算失败')
  } finally {
    submitting.value = false
  }
}

async function cancelTimer(timer) {
  const confirmed = window.confirm('确定结束该计时且不结算吗？')
  if (!confirmed) return

  submitting.value = true
  try {
    await api.delete(`/active-timers/${timer.id}`)
    await fetchTimers()
    showFeedback('success', '计时已结束。')
  } catch (error) {
    console.error('结束计时失败:', error)
    showFeedback('error', error?.response?.data?.message || error?.message || '结束计时失败')
  } finally {
    submitting.value = false
  }
}

async function toggleTimerPause(timer) {
  if (!timer?.id) return

  const isPaused = timer.status === 'paused'
  const nextStatus = isPaused ? 'active' : 'paused'
  const currentElapsedSeconds = getElapsedSeconds(timer)
  const nextTiming = isPaused
    ? {
      elapsedSeconds: currentElapsedSeconds,
      resumedAt: new Date(nowTimestamp.value).toISOString()
    }
    : {
      elapsedSeconds: currentElapsedSeconds,
      resumedAt: ''
    }

  submitting.value = true
  try {
    const notesPayload = buildTimerNotesPayload(
      {
        ...timer,
        timing: nextTiming
      },
      timer.materials,
      timer.miscSelections
    )

    await api.put(`/active-timers/${timer.id}`, {
      status: nextStatus,
      notes: notesPayload
    })
    await fetchTimers()
    showFeedback('success', nextStatus === 'paused' ? '计时已暂停。' : '计时已继续。')
  } catch (error) {
    console.error('更新计时状态失败:', error)
    showFeedback('error', error?.response?.data?.message || error?.message || '更新计时状态失败')
  } finally {
    submitting.value = false
  }
}

function startTicker() {
  ticker = setInterval(() => {
    nowTimestamp.value = Date.now()
  }, 1000)
}

function stopTicker() {
  if (ticker) {
    clearInterval(ticker)
    ticker = null
  }
}

watch(
  () => addForm.customerId,
  async (customerId) => {
    if (!showAddModal.value) return
    await syncAddBalance(customerId)
  }
)

watch(
  () => filterForm.timerType,
  () => {
    const nextOptions = filterPackagePlanOptions.value
    const isCurrentPlanValid = nextOptions.some((item) => item.value === filterForm.packagePlan)
    if (!isCurrentPlanValid) {
      filterForm.packagePlan = ''
    }
  }
)

watch(
  [() => showEditModal.value, () => editForm.packagePlan, () => editForm.tableArea],
  ([visible]) => {
    if (!visible) return
    syncEditSeatPayload()
  }
)

watch(
  [
    () => showSettleModal.value,
    () => selectedTimer.value?.id,
    () => settleElapsedMinutes.value,
    () => billingRules.value
  ],
  ([visible]) => {
    if (!visible || !selectedTimer.value) return
    syncSettleMiscSelections()
    applyRecommendedSettlementPlan()
  },
  { deep: true }
)

watch(
  [() => nowTimestamp.value, () => timers.value],
  () => {
    evaluateWarnings()
  },
  { deep: true }
)

function handleGlobalKeydown(event) {
  if (event.key !== 'Escape') return
  if (submitting.value) return

  const roomModalVisible = showLivingRoomModal.value || showSmallRoomModal.value || showGardenModal.value || showUpstairsModal.value || showSeatOverviewModal.value
  if (roomModalVisible && pendingMultiSeatSelection.value) {
    event.preventDefault()
    clearPendingMultiSeatSelection()
    showFeedback('info', '已取消多人选座')
    return
  }

  if (showLivingRoomModal.value) {
    event.preventDefault()
    closeLivingRoomModal()
    return
  }

  if (showSmallRoomModal.value) {
    event.preventDefault()
    closeSmallRoomModal()
    return
  }

  if (showGardenModal.value) {
    event.preventDefault()
    closeGardenModal()
    return
  }

  if (showUpstairsModal.value) {
    event.preventDefault()
    closeUpstairsModal()
    return
  }

  if (showSeatOverviewModal.value) {
    event.preventDefault()
    closeSeatOverviewModal()
    return
  }

  if (showSettleModal.value) {
    event.preventDefault()
    closeSettleModal()
    return
  }

  if (showEditModal.value) {
    event.preventDefault()
    closeEditModal()
    return
  }

  if (showAddModal.value) {
    event.preventDefault()
    closeAddModal()
  }
}

onMounted(async () => {
  window.addEventListener('keydown', handleGlobalKeydown)
  await Promise.all([fetchCustomers(), fetchBillingRules()])
  await fetchTimers()
  startTicker()
})

onUnmounted(() => {
  window.removeEventListener('keydown', handleGlobalKeydown)
  stopTicker()
  clearFeedbackTimer()
  if (typeof window !== 'undefined' && window.speechSynthesis) {
    window.speechSynthesis.cancel()
  }
})
</script>

<template>
  <div class="space-y-6">
    <section class="page-hero rounded-3xl p-6 sm:p-8">
      <div class="relative z-10 flex flex-col gap-6 lg:flex-row lg:items-start lg:justify-between">
        <div class="max-w-2xl space-y-2">
          <p class="page-hero__eyebrow">Live Timing Desk</p>
          <h1 class="page-hero__title">正在计时</h1>
        </div>
        <div class="flex items-center gap-2">
          <button
            @click="testSpeakerBroadcast"
            class="inline-flex items-center gap-2 rounded-xl border border-white/55 bg-white/15 px-4 py-2 text-sm font-semibold text-white hover:bg-white/25"
          >
            测试播报
          </button>
          <button
            @click="openAddModal"
            class="page-hero__action"
          >
            <svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4v16m8-8H4" />
            </svg>
            <span>新增消费</span>
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

    <Teleport to="body">
      <div
        v-if="activeWarning"
        class="fixed inset-0 bg-black bg-opacity-40 z-[70] flex items-center justify-center p-4"
      >
        <div class="bg-white rounded-xl shadow-2xl w-full max-w-md border border-orange-200">
          <div class="px-5 py-4 border-b border-orange-100 bg-orange-50">
            <h3 class="text-lg font-semibold text-orange-800">计时剩余提醒</h3>
          </div>
          <div class="px-5 py-4 space-y-2 text-sm text-gray-700">
            <p><span class="text-gray-500">桌号：</span> {{ activeWarning.tableNo || '-' }}</p>
            <p><span class="text-gray-500">客户：</span> {{ activeWarning.customerName || '-' }}</p>
            <p><span class="text-gray-500">套餐：</span> {{ getPackagePlanLabel(activeWarning.packagePlan) }}</p>
            <p class="text-base font-semibold text-orange-700">剩余 {{ activeWarning.remainingMinutes }} 分钟</p>
            <p class="text-xs text-gray-400">触发时间：{{ formatDateTime(activeWarning.triggeredAt) }}</p>
          </div>
          <div class="px-5 py-4 border-t border-gray-100 flex justify-end">
            <button
              @click="dismissActiveWarning"
              class="px-4 py-2 bg-orange-600 text-white rounded-lg hover:bg-orange-700"
            >
              我知道了
            </button>
          </div>
        </div>
      </div>
    </Teleport>

    <div class="management-surface p-4">
      <div class="grid grid-cols-1 md:grid-cols-[minmax(220px,2fr)_minmax(160px,1fr)_minmax(200px,1.2fr)_auto] gap-3 items-end">
        <div>
          <label class="block text-sm font-medium text-gray-700 mb-1">关键词</label>
          <input
            v-model.trim="filterForm.keyword"
            type="text"
            placeholder="客户/备注/套餐"
            class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
          >
        </div>
        <div>
          <label class="block text-sm font-medium text-gray-700 mb-1">计时类型</label>
          <select
            v-model="filterForm.timerType"
            class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
          >
            <option value="">全部类型</option>
            <option v-for="item in timerTypeOptions" :key="item.value" :value="item.value">
              {{ item.label }}
            </option>
          </select>
        </div>
        <div>
          <label class="block text-sm font-medium text-gray-700 mb-1">套餐方案</label>
          <select
            v-model="filterForm.packagePlan"
            class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
          >
            <option value="">全部套餐</option>
            <option v-for="item in filterPackagePlanOptions" :key="item.value" :value="item.value">
              {{ item.label }}
            </option>
          </select>
        </div>
        <div class="md:justify-self-end">
          <button
            @click="resetFilters"
            :disabled="!hasActiveFilters"
            class="w-full md:w-auto px-3 py-2 border border-gray-300 text-sm text-gray-700 rounded-lg hover:bg-gray-50 disabled:opacity-40 disabled:cursor-not-allowed"
          >
            重置筛选
          </button>
        </div>
      </div>
    </div>

    <section class="management-surface p-4 sm:p-5">
      <div class="flex gap-3 overflow-x-auto snap-x snap-mandatory pb-2 md:grid md:grid-cols-2 xl:grid-cols-5 md:overflow-visible md:snap-none md:pb-0">
        <button
          type="button"
          @click="openSeatOverviewModal"
          class="w-full min-w-[280px] shrink-0 snap-start rounded-2xl border border-slate-300 bg-[radial-gradient(circle_at_top_left,_rgba(59,130,246,0.18),_transparent_45%),linear-gradient(135deg,#0f172a,#1e293b_50%,#0f766e)] p-4 text-left text-white hover:shadow-lg transition md:min-w-0 h-full flex flex-col"
        >
          <div class="flex items-start justify-between gap-3">
            <div>
              <p class="text-base font-bold">全场座位总览</p>
              <p class="mt-1 text-xs text-slate-200">跨房间看空位，适合多人套餐一次选齐</p>
            </div>
            <span class="rounded-full bg-white/15 px-2 py-0.5 text-[11px] font-semibold text-cyan-100">Overview</span>
          </div>
          <div class="mt-4 grid grid-cols-3 gap-2 text-center mt-auto">
            <div class="rounded-xl bg-white/10 px-2 py-2 backdrop-blur-sm">
              <p class="text-[11px] text-slate-200">总座位</p>
              <p class="mt-1 text-lg font-bold">{{ overallSeatSummary.total }}</p>
            </div>
            <div class="rounded-xl bg-emerald-400/15 px-2 py-2 backdrop-blur-sm">
              <p class="text-[11px] text-emerald-100">剩余</p>
              <p class="mt-1 text-lg font-bold text-emerald-50">{{ overallSeatSummary.available }}</p>
            </div>
            <div class="rounded-xl bg-rose-400/15 px-2 py-2 backdrop-blur-sm">
              <p class="text-[11px] text-rose-100">占用</p>
              <p class="mt-1 text-lg font-bold text-rose-50">{{ overallSeatSummary.occupied }}</p>
            </div>
          </div>
        </button>
        <button
          type="button"
          @click="openLivingRoomModal"
          class="w-full min-w-[280px] shrink-0 snap-start rounded-2xl border border-slate-300 bg-[radial-gradient(circle_at_top_left,_rgba(96,165,250,0.18),_transparent_45%),linear-gradient(135deg,#0f172a,#1d4ed8_50%,#0f766e)] p-4 text-left text-white hover:shadow-lg transition md:min-w-0 h-full flex flex-col"
        >
          <div class="flex items-start justify-between gap-3">
            <div>
              <p class="text-base font-bold">客厅座位分布</p>
              <p class="mt-1 text-xs text-slate-200">点击查看客厅座位图（单座位左键开台，多人模式左键点选后确认）</p>
            </div>
            <span class="rounded-full bg-white/15 px-2 py-0.5 text-[11px] font-semibold text-cyan-100">Living</span>
          </div>
          <div class="mt-4 grid grid-cols-3 gap-2 text-center mt-auto">
            <div class="rounded-xl bg-white/10 px-2 py-2 backdrop-blur-sm">
              <p class="text-[11px] text-slate-200">总座位</p>
              <p class="mt-1 text-lg font-bold">{{ livingRoomSeatSummary.total }}</p>
            </div>
            <div class="rounded-xl bg-emerald-400/15 px-2 py-2 backdrop-blur-sm">
              <p class="text-[11px] text-emerald-100">剩余</p>
              <p class="mt-1 text-lg font-bold text-emerald-50">{{ livingRoomSeatSummary.available }}</p>
            </div>
            <div class="rounded-xl bg-rose-400/15 px-2 py-2 backdrop-blur-sm">
              <p class="text-[11px] text-rose-100">占用</p>
              <p class="mt-1 text-lg font-bold text-rose-50">{{ livingRoomSeatSummary.occupied }}</p>
            </div>
          </div>
        </button>
        <button
          type="button"
          @click="openSmallRoomModal"
          class="w-full min-w-[280px] shrink-0 snap-start rounded-2xl border border-slate-300 bg-[radial-gradient(circle_at_top_left,_rgba(217,70,239,0.2),_transparent_45%),linear-gradient(135deg,#111827,#7c3aed_48%,#db2777)] p-4 text-left text-white hover:shadow-lg transition md:min-w-0 h-full flex flex-col"
        >
          <div class="flex items-start justify-between gap-3">
            <div>
              <p class="text-base font-bold">小房间座位分布</p>
              <p class="mt-1 text-xs text-slate-200">点击查看小房间座位图（单座位左键开台，多人模式左键点选后确认）</p>
            </div>
            <span class="rounded-full bg-white/15 px-2 py-0.5 text-[11px] font-semibold text-fuchsia-100">Private</span>
          </div>
          <div class="mt-4 grid grid-cols-3 gap-2 text-center mt-auto">
            <div class="rounded-xl bg-white/10 px-2 py-2 backdrop-blur-sm">
              <p class="text-[11px] text-slate-200">总座位</p>
              <p class="mt-1 text-lg font-bold">{{ smallRoomSeatSummary.total }}</p>
            </div>
            <div class="rounded-xl bg-emerald-400/15 px-2 py-2 backdrop-blur-sm">
              <p class="text-[11px] text-emerald-100">剩余</p>
              <p class="mt-1 text-lg font-bold text-emerald-50">{{ smallRoomSeatSummary.available }}</p>
            </div>
            <div class="rounded-xl bg-rose-400/15 px-2 py-2 backdrop-blur-sm">
              <p class="text-[11px] text-rose-100">占用</p>
              <p class="mt-1 text-lg font-bold text-rose-50">{{ smallRoomSeatSummary.occupied }}</p>
            </div>
          </div>
        </button>
        <button
          type="button"
          @click="openGardenModal"
          class="w-full min-w-[280px] shrink-0 snap-start rounded-2xl border border-slate-300 bg-[radial-gradient(circle_at_top_left,_rgba(74,222,128,0.18),_transparent_45%),linear-gradient(135deg,#0f172a,#166534_48%,#0f766e)] p-4 text-left text-white hover:shadow-lg transition md:min-w-0 h-full flex flex-col"
        >
          <div class="flex items-start justify-between gap-3">
            <div>
              <p class="text-base font-bold">花园座位分布</p>
              <p class="mt-1 text-xs text-slate-200">点击查看花园座位图（单座位左键开台，多人模式左键点选后确认）</p>
            </div>
            <span class="rounded-full bg-white/15 px-2 py-0.5 text-[11px] font-semibold text-emerald-100">Garden</span>
          </div>
          <div class="mt-4 grid grid-cols-3 gap-2 text-center mt-auto">
            <div class="rounded-xl bg-white/10 px-2 py-2 backdrop-blur-sm">
              <p class="text-[11px] text-slate-200">总座位</p>
              <p class="mt-1 text-lg font-bold">{{ gardenSeatSummary.total }}</p>
            </div>
            <div class="rounded-xl bg-emerald-400/15 px-2 py-2 backdrop-blur-sm">
              <p class="text-[11px] text-emerald-100">剩余</p>
              <p class="mt-1 text-lg font-bold text-emerald-50">{{ gardenSeatSummary.available }}</p>
            </div>
            <div class="rounded-xl bg-rose-400/15 px-2 py-2 backdrop-blur-sm">
              <p class="text-[11px] text-rose-100">占用</p>
              <p class="mt-1 text-lg font-bold text-rose-50">{{ gardenSeatSummary.occupied }}</p>
            </div>
          </div>
        </button>
        <button
          type="button"
          @click="openUpstairsModal"
          class="w-full min-w-[280px] shrink-0 snap-start rounded-2xl border border-slate-300 bg-[radial-gradient(circle_at_top_left,_rgba(251,191,36,0.18),_transparent_45%),linear-gradient(135deg,#111827,#92400e_48%,#b45309)] p-4 text-left text-white hover:shadow-lg transition md:min-w-0 h-full flex flex-col"
        >
          <div class="flex items-start justify-between gap-3">
            <div>
              <p class="text-base font-bold">楼上座位分布</p>
              <p class="mt-1 text-xs text-slate-200">点击查看楼上座位图（单座位左键开台，多人模式左键点选后确认）</p>
            </div>
            <span class="rounded-full bg-white/15 px-2 py-0.5 text-[11px] font-semibold text-amber-100">Upstairs</span>
          </div>
          <div class="mt-4 grid grid-cols-3 gap-2 text-center mt-auto">
            <div class="rounded-xl bg-white/10 px-2 py-2 backdrop-blur-sm">
              <p class="text-[11px] text-slate-200">总座位</p>
              <p class="mt-1 text-lg font-bold">{{ upstairsSeatSummary.total }}</p>
            </div>
            <div class="rounded-xl bg-emerald-400/15 px-2 py-2 backdrop-blur-sm">
              <p class="text-[11px] text-emerald-100">剩余</p>
              <p class="mt-1 text-lg font-bold text-emerald-50">{{ upstairsSeatSummary.available }}</p>
            </div>
            <div class="rounded-xl bg-rose-400/15 px-2 py-2 backdrop-blur-sm">
              <p class="text-[11px] text-rose-100">占用</p>
              <p class="mt-1 text-lg font-bold text-rose-50">{{ upstairsSeatSummary.occupied }}</p>
            </div>
          </div>
        </button>
      </div>
    </section>

    <Teleport to="body">
      <div
        v-if="showSeatOverviewModal"
        class="fixed inset-0 bg-black bg-opacity-55 flex items-center justify-center z-40 p-4"
        @mousedown="onBackdropMouseDown('timers-seat-overview', $event)"
        @mouseup="onBackdropMouseUp('timers-seat-overview', $event) && closeSeatOverviewModal()"
      >
        <div class="w-full max-w-7xl max-h-[92vh] overflow-y-auto rounded-[28px] border border-slate-200 bg-white shadow-2xl">
          <div class="sticky top-0 z-10 border-b border-slate-200 bg-[radial-gradient(circle_at_top_left,_rgba(56,189,248,0.18),_transparent_30%),linear-gradient(135deg,#f8fafc,#eef6ff_45%,#f0fdfa)] px-6 py-5 backdrop-blur">
            <div class="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
              <div>
                <p class="text-xs font-semibold uppercase tracking-[0.28em] text-slate-500">Seat Overview</p>
                <h3 class="mt-1 text-2xl font-black tracking-tight text-slate-900">全场座位总览</h3>
                <p class="mt-2 text-sm text-slate-600">在一个界面里查看四个房间并跨房间选座，适合多人套餐快速拼桌。</p>
              </div>
              <div class="flex items-start gap-3">
                <div class="grid grid-cols-3 gap-2">
                  <div class="rounded-2xl border border-slate-200 bg-white/80 px-3 py-2 text-center shadow-sm">
                    <p class="text-[11px] text-slate-500">总座位</p>
                    <p class="mt-1 text-lg font-bold text-slate-900">{{ overallSeatSummary.total }}</p>
                  </div>
                  <div class="rounded-2xl border border-emerald-200 bg-emerald-50 px-3 py-2 text-center shadow-sm">
                    <p class="text-[11px] text-emerald-600">剩余</p>
                    <p class="mt-1 text-lg font-bold text-emerald-700">{{ overallSeatSummary.available }}</p>
                  </div>
                  <div class="rounded-2xl border border-rose-200 bg-rose-50 px-3 py-2 text-center shadow-sm">
                    <p class="text-[11px] text-rose-600">占用</p>
                    <p class="mt-1 text-lg font-bold text-rose-700">{{ overallSeatSummary.occupied }}</p>
                  </div>
                </div>
                <button
                  @click="closeSeatOverviewModal"
                  class="rounded-xl border border-slate-200 bg-white p-2 text-slate-400 hover:text-slate-700"
                >
                  <svg xmlns="http://www.w3.org/2000/svg" class="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
                  </svg>
                </button>
              </div>
            </div>
          </div>

          <div class="p-5">
            <div class="mb-4 rounded-3xl border border-slate-200 bg-[linear-gradient(135deg,rgba(15,23,42,0.98),rgba(30,41,59,0.95)_45%,rgba(8,145,178,0.9))] px-4 py-4 text-white shadow-lg">
              <div class="flex flex-col gap-3 xl:flex-row xl:items-center xl:justify-between">
                <div>
                  <p class="text-sm font-semibold text-cyan-100">总览操作台</p>
                  <p class="mt-1 text-xs text-slate-200">单座位直接左键开台；多人模式下左键点选或取消，选好后统一确认。</p>
                </div>
                <div class="flex flex-wrap items-center gap-2">
                  <button
                    type="button"
                    @click="deactivateMultiSeatSelectionMode()"
                    :class="[
                      'rounded-xl px-3 py-2 text-xs font-semibold transition-colors',
                      seatSelectionMode === 'single'
                        ? 'bg-white text-slate-900'
                        : 'border border-white/25 text-white hover:bg-white/10'
                    ]"
                  >
                    单座位开台
                  </button>
                  <button
                    type="button"
                    @click="activateMultiSeatSelectionMode"
                    :class="[
                      'rounded-xl px-3 py-2 text-xs font-semibold transition-colors',
                      seatSelectionMode === 'multi'
                        ? 'bg-cyan-300 text-slate-950'
                        : 'border border-cyan-200/40 text-cyan-50 hover:bg-cyan-300/10'
                    ]"
                  >
                    多人选座
                  </button>
                </div>
              </div>

              <div v-if="seatSelectionMode === 'multi'" class="mt-4 rounded-2xl border border-white/15 bg-white/10 px-4 py-3">
                <p v-if="pendingMultiSeatCount > 0" class="text-sm font-semibold text-white">已选座位：{{ getPendingSeatDisplayText() }}</p>
                <p v-else class="text-sm text-slate-100">请直接在下方四个房间里点选座位，再次点击已选座位可取消。</p>
                <p v-if="pendingMultiSeatCount >= 2 && pendingMultiSeatPreset" class="mt-1 text-xs text-cyan-100">
                  将匹配 {{ pendingMultiSeatPreset.peopleCount }}人套餐，确认后自动预填到新增消费。
                </p>
                <p v-else-if="pendingMultiSeatCount >= 2" class="mt-1 text-xs text-amber-100">
                  当前已选 {{ pendingMultiSeatCount }} 个座位，但未配置对应套餐。
                </p>
                <div class="mt-3 flex flex-wrap items-center gap-2">
                  <button
                    type="button"
                    @click="confirmPendingMultiSeatSelection"
                    :disabled="pendingMultiSeatCount < 2 || !pendingMultiSeatPreset"
                    class="rounded-xl bg-white px-3 py-2 text-xs font-semibold text-slate-900 hover:bg-slate-100 disabled:cursor-not-allowed disabled:bg-white/40 disabled:text-slate-500"
                  >
                    确认多人选座
                  </button>
                  <button
                    type="button"
                    @click="clearPendingMultiSeatSelection"
                    class="rounded-xl border border-white/20 px-3 py-2 text-xs font-semibold text-white hover:bg-white/10"
                  >
                    清空已选
                  </button>
                  <button
                    type="button"
                    @click="deactivateMultiSeatSelectionMode(true)"
                    class="rounded-xl border border-white/20 px-3 py-2 text-xs font-semibold text-white hover:bg-white/10"
                  >
                    退出多人模式
                  </button>
                </div>
              </div>
            </div>

            <div class="grid grid-cols-1 2xl:grid-cols-2 gap-4">
              <section
                v-for="section in seatOverviewSections"
                :key="`overview-${section.key}`"
                :class="['rounded-3xl border p-4 shadow-sm', section.panelClass]"
              >
                <div class="mb-4 flex items-start justify-between gap-3">
                  <div>
                    <div class="flex items-center gap-2">
                      <h4 class="text-lg font-black tracking-tight text-slate-900">{{ section.title }}</h4>
                      <span :class="['rounded-full px-2 py-0.5 text-[11px] font-semibold', section.badgeClass]">{{ section.subtitle }}</span>
                    </div>
                    <p class="mt-1 text-xs text-slate-600">剩余 {{ section.summary.available }} / 占用 {{ section.summary.occupied }} / 总计 {{ section.summary.total }}</p>
                  </div>
                </div>

                <div class="grid grid-cols-1 gap-4">
                  <article
                    v-for="table in section.tables"
                    :key="`overview-${section.key}-${table.area}`"
                    :class="[
                      'rounded-2xl border p-3 shadow-sm transition-all backdrop-blur-sm',
                      table.occupiedCount > 0 ? 'border-red-300 bg-white/95' : 'border-emerald-200 bg-white/95'
                    ]"
                  >
                    <div class="flex items-center justify-between mb-2">
                      <p class="text-sm font-bold text-gray-900">{{ table.area }}桌</p>
                      <p :class="['text-xs font-semibold px-2 py-0.5 rounded-full', table.occupiedCount > 0 ? 'bg-red-100 text-red-700' : 'bg-emerald-100 text-emerald-700']">
                        {{ table.occupiedCount > 0 ? `已坐 ${table.occupiedCount}/${table.seatCount}` : '当前全空' }}
                      </p>
                    </div>
                    <div
                      :class="[
                        'mx-auto rounded-2xl border-2 border-slate-300 bg-gradient-to-b from-slate-100 to-slate-200 px-3 py-3 shadow-inner',
                        section.key === 'garden' && table.area === 'K'
                          ? 'max-w-[220px]'
                          : table.shape === 'square'
                            ? 'max-w-[180px]'
                            : table.shape === 'tall'
                              ? 'max-w-[140px]'
                              : section.key === 'upstairs'
                                ? 'max-w-[210px]'
                                : 'max-w-[240px]'
                      ]"
                    >
                      <div
                        :class="[
                          section.key === 'garden' && isGardenKTable(table.area)
                            ? 'grid grid-cols-4 grid-rows-3 gap-1.5 h-[126px] items-center justify-items-center'
                            : section.key === 'upstairs'
                              ? 'grid grid-cols-3 grid-rows-3 gap-1.5 h-[126px] items-center justify-items-center'
                              : 'grid gap-2'
                        ]"
                        :style="(section.key === 'garden' && isGardenKTable(table.area)) || section.key === 'upstairs'
                          ? undefined
                          : { gridTemplateColumns: `repeat(${table.seatColumns || 3}, minmax(0, 1fr))` }"
                      >
                        <button
                          v-for="seat in table.seats"
                          :key="`overview-${section.key}-${table.area}-${seat.seatNo}`"
                          type="button"
                          @click="handleSeatLeftClick(table.area, seat.seatNo, seat.occupied)"
                          :class="[
                            'relative rounded-lg border flex items-center justify-center font-bold transition-colors',
                            section.key === 'upstairs'
                              ? 'h-12 w-12 text-sm'
                              : section.key === 'garden' && isGardenKTable(table.area)
                                ? 'h-10 w-10 text-[12px]'
                                : 'h-10 text-[12px]',
                            section.key === 'garden' ? getGardenSeatGridPositionClass(table.area, seat.seatNo) : '',
                            section.key === 'upstairs' ? getUpstairsSeatGridPositionClass(seat.seatNo) : '',
                            isPendingSeatSelected(table.area, seat.seatNo)
                              ? 'ring-2 ring-blue-600 ring-offset-2 ring-offset-slate-200'
                              : '',
                            seat.occupied
                              ? 'bg-red-600 border-red-700 text-white'
                              : 'bg-white border-slate-300 text-slate-800 hover:bg-slate-50 cursor-pointer'
                          ]"
                          :title="seat.occupied ? `${seat.customerName || '已占用'}（${table.area}${seat.seatNo}）` : `${table.area}${seat.seatNo} 空位`"
                        >
                          {{ seat.seatNo }}
                          <span
                            :class="[
                              section.key === 'upstairs' ? 'absolute top-1 right-1 h-2.5 w-2.5 rounded-full' : 'absolute top-1.5 right-1.5 h-2.5 w-2.5 rounded-full',
                              seat.occupied ? 'bg-rose-200' : 'bg-emerald-500'
                            ]"
                          ></span>
                        </button>
                      </div>
                    </div>
                    <div class="mt-2 text-xs text-gray-600">
                      <span v-if="table.occupiedCount > 0">深红座位为占用，浅红座位可开台</span>
                      <span v-else>全部可开台</span>
                    </div>
                  </article>
                </div>
              </section>
            </div>
          </div>
        </div>
      </div>
    </Teleport>

    <Teleport to="body">
      <div
        v-if="showLivingRoomModal"
        class="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-40 p-4"
        @mousedown="onBackdropMouseDown('timers-living-room', $event)"
        @mouseup="onBackdropMouseUp('timers-living-room', $event) && closeLivingRoomModal()"
      >
        <div class="bg-white rounded-xl shadow-xl w-full max-w-5xl max-h-[90vh] overflow-y-auto">
          <div class="px-6 py-4 border-b border-gray-200 flex items-center justify-between">
            <h3 class="text-lg font-semibold text-gray-800">客厅座位分布</h3>
            <button
              @click="closeLivingRoomModal"
              class="text-gray-400 hover:text-gray-600 transition-colors"
            >
              <svg xmlns="http://www.w3.org/2000/svg" class="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>
          <div class="p-4 sm:p-5 bg-gradient-to-br from-slate-50 via-blue-50 to-cyan-50 border border-slate-200 m-4 rounded-xl">
            <div class="flex items-center justify-between mb-3">
              <div class="text-xs text-slate-600">座位：红=有人，白=空位</div>
              <div class="text-xs text-slate-500">剩余 {{ livingRoomSeatSummary.available }} / 占用 {{ livingRoomSeatSummary.occupied }}</div>
            </div>
            <div class="mb-3 flex flex-wrap items-center gap-2">
              <button
                type="button"
                @click="deactivateMultiSeatSelectionMode()"
                :class="[
                  'rounded-lg px-3 py-1.5 text-xs font-semibold transition-colors',
                  seatSelectionMode === 'single'
                    ? 'bg-slate-900 text-white'
                    : 'border border-slate-300 text-slate-700 hover:bg-slate-50'
                ]"
              >
                单座位开台
              </button>
              <button
                type="button"
                @click="activateMultiSeatSelectionMode"
                :class="[
                  'rounded-lg px-3 py-1.5 text-xs font-semibold transition-colors',
                  seatSelectionMode === 'multi'
                    ? 'bg-blue-600 text-white'
                    : 'border border-blue-300 text-blue-700 hover:bg-blue-50'
                ]"
              >
                多人选座
              </button>
              <p class="text-xs text-slate-600 sm:ml-2">单座位直接左键开台；多人模式下左键点选或取消，选好后确认。</p>
            </div>
            <div v-if="seatSelectionMode === 'multi'" class="mb-3 rounded-lg border border-blue-200 bg-blue-50 px-3 py-2 text-xs text-blue-800">
              <p v-if="pendingMultiSeatCount > 0">已选座位：{{ getPendingSeatDisplayText() }}</p>
              <p v-else>请左键依次点选多人座位，再次点击已选座位可取消。</p>
              <p v-if="pendingMultiSeatCount >= 2 && pendingMultiSeatPreset" class="mt-1">
                将匹配 {{ pendingMultiSeatPreset.peopleCount }}人套餐，确认后自动预填。
              </p>
              <p v-else-if="pendingMultiSeatCount >= 2" class="mt-1 text-amber-700">
                当前已选 {{ pendingMultiSeatCount }} 个座位，但未配置对应套餐。
              </p>
              <div class="mt-2 flex flex-wrap items-center gap-2">
                <button
                  type="button"
                  @click="confirmPendingMultiSeatSelection"
                  :disabled="pendingMultiSeatCount < 2 || !pendingMultiSeatPreset"
                  class="rounded-lg bg-blue-600 px-3 py-1.5 text-xs font-semibold text-white hover:bg-blue-700 disabled:cursor-not-allowed disabled:bg-blue-300"
                >
                  确认多人选座
                </button>
                <button
                  type="button"
                  class="rounded-lg border border-blue-200 px-3 py-1.5 text-xs font-semibold text-blue-700 hover:bg-blue-100"
                  @click="clearPendingMultiSeatSelection"
                >
                  清空已选
                </button>
                <button
                  type="button"
                  class="rounded-lg border border-slate-200 px-3 py-1.5 text-xs font-semibold text-slate-700 hover:bg-slate-100"
                  @click="deactivateMultiSeatSelectionMode(true)"
                >
                  退出多人模式
                </button>
              </div>
            </div>
            <div class="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <article
                v-for="table in seatLayoutTables"
                :key="table.area"
                :class="[
                  'rounded-2xl border p-3 shadow-sm transition-all backdrop-blur-sm',
                  table.occupiedCount > 0 ? 'border-red-300 bg-white' : 'border-emerald-200 bg-white/95'
                ]"
              >
                <div class="flex items-center justify-between mb-2">
                  <p class="text-sm font-bold text-gray-900">{{ table.area }}桌</p>
                  <p :class="['text-xs font-semibold px-2 py-0.5 rounded-full', table.occupiedCount > 0 ? 'bg-red-100 text-red-700' : 'bg-emerald-100 text-emerald-700']">
                    {{ table.occupiedCount > 0 ? `已坐 ${table.occupiedCount}/${table.seatCount}` : '当前全空' }}
                  </p>
                </div>
                <div
                  :class="[
                    'mx-auto rounded-2xl border-2 border-slate-300 bg-gradient-to-b from-slate-100 to-slate-200 px-3 py-3 shadow-inner',
                    table.shape === 'square' ? 'max-w-[180px]' : table.shape === 'tall' ? 'max-w-[140px]' : 'max-w-[240px]'
                  ]"
                >
                  <div
                    class="grid gap-2"
                    :style="{ gridTemplateColumns: `repeat(${table.seatColumns || 3}, minmax(0, 1fr))` }"
                  >
                    <button
                      v-for="seat in table.seats"
                      :key="`${table.area}-${seat.seatNo}`"
                      type="button"
                      @click="handleSeatLeftClick(table.area, seat.seatNo, seat.occupied)"
                      :class="[
                        'relative h-10 rounded-lg border flex items-center justify-center text-[12px] font-bold transition-colors',
                        isPendingSeatSelected(table.area, seat.seatNo)
                          ? 'ring-2 ring-blue-600 ring-offset-2 ring-offset-slate-200'
                          : '',
                        seat.occupied
                          ? 'bg-red-600 border-red-700 text-white'
                          : 'bg-white border-slate-300 text-slate-800 hover:bg-slate-50 cursor-pointer'
                      ]"
                      :title="seat.occupied ? `${seat.customerName || '已占用'}（${table.area}${seat.seatNo}）` : `${table.area}${seat.seatNo} 空位`"
                    >
                      {{ seat.seatNo }}
                      <span
                        :class="[
                          'absolute top-1.5 right-1.5 h-2.5 w-2.5 rounded-full',
                          seat.occupied ? 'bg-rose-200' : 'bg-emerald-500'
                        ]"
                      ></span>
                    </button>
                  </div>
                </div>
                <div class="mt-2 text-xs text-gray-600">
                  <span v-if="table.occupiedCount > 0">深红座位为占用，浅红座位可开台</span>
                  <span v-else>全部可开台</span>
                </div>
              </article>
            </div>
          </div>
        </div>
      </div>
    </Teleport>

    <Teleport to="body">
      <div
        v-if="showSmallRoomModal"
        class="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-40 p-4"
        @mousedown="onBackdropMouseDown('timers-small-room', $event)"
        @mouseup="onBackdropMouseUp('timers-small-room', $event) && closeSmallRoomModal()"
      >
        <div class="bg-white rounded-xl shadow-xl w-full max-w-5xl max-h-[90vh] overflow-y-auto">
          <div class="px-6 py-4 border-b border-gray-200 flex items-center justify-between">
            <h3 class="text-lg font-semibold text-gray-800">小房间座位分布</h3>
            <button
              @click="closeSmallRoomModal"
              class="text-gray-400 hover:text-gray-600 transition-colors"
            >
              <svg xmlns="http://www.w3.org/2000/svg" class="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>
          <div class="p-4 sm:p-5 bg-gradient-to-br from-violet-50 via-fuchsia-50 to-pink-50 border border-fuchsia-200 m-4 rounded-xl">
            <div class="flex items-center justify-between mb-3">
              <div class="text-xs text-slate-600">座位：红=有人，白=空位</div>
              <div class="text-xs text-slate-500">剩余 {{ smallRoomSeatSummary.available }} / 占用 {{ smallRoomSeatSummary.occupied }}</div>
            </div>
            <div class="mb-3 flex flex-wrap items-center gap-2">
              <button
                type="button"
                @click="deactivateMultiSeatSelectionMode()"
                :class="[
                  'rounded-lg px-3 py-1.5 text-xs font-semibold transition-colors',
                  seatSelectionMode === 'single'
                    ? 'bg-slate-900 text-white'
                    : 'border border-slate-300 text-slate-700 hover:bg-slate-50'
                ]"
              >
                单座位开台
              </button>
              <button
                type="button"
                @click="activateMultiSeatSelectionMode"
                :class="[
                  'rounded-lg px-3 py-1.5 text-xs font-semibold transition-colors',
                  seatSelectionMode === 'multi'
                    ? 'bg-blue-600 text-white'
                    : 'border border-blue-300 text-blue-700 hover:bg-blue-50'
                ]"
              >
                多人选座
              </button>
              <p class="text-xs text-slate-600 sm:ml-2">单座位直接左键开台；多人模式下左键点选或取消，选好后确认。</p>
            </div>
            <div v-if="seatSelectionMode === 'multi'" class="mb-3 rounded-lg border border-blue-200 bg-blue-50 px-3 py-2 text-xs text-blue-800">
              <p v-if="pendingMultiSeatCount > 0">已选座位：{{ getPendingSeatDisplayText() }}</p>
              <p v-else>请左键依次点选多人座位，再次点击已选座位可取消。</p>
              <p v-if="pendingMultiSeatCount >= 2 && pendingMultiSeatPreset" class="mt-1">
                将匹配 {{ pendingMultiSeatPreset.peopleCount }}人套餐，确认后自动预填。
              </p>
              <p v-else-if="pendingMultiSeatCount >= 2" class="mt-1 text-amber-700">
                当前已选 {{ pendingMultiSeatCount }} 个座位，但未配置对应套餐。
              </p>
              <div class="mt-2 flex flex-wrap items-center gap-2">
                <button
                  type="button"
                  @click="confirmPendingMultiSeatSelection"
                  :disabled="pendingMultiSeatCount < 2 || !pendingMultiSeatPreset"
                  class="rounded-lg bg-blue-600 px-3 py-1.5 text-xs font-semibold text-white hover:bg-blue-700 disabled:cursor-not-allowed disabled:bg-blue-300"
                >
                  确认多人选座
                </button>
                <button
                  type="button"
                  class="rounded-lg border border-blue-200 px-3 py-1.5 text-xs font-semibold text-blue-700 hover:bg-blue-100"
                  @click="clearPendingMultiSeatSelection"
                >
                  清空已选
                </button>
                <button
                  type="button"
                  class="rounded-lg border border-slate-200 px-3 py-1.5 text-xs font-semibold text-slate-700 hover:bg-slate-100"
                  @click="deactivateMultiSeatSelectionMode(true)"
                >
                  退出多人模式
                </button>
              </div>
            </div>
            <div class="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <article
                v-for="table in smallRoomSeatLayoutTables"
                :key="`small-${table.area}`"
                :class="[
                  'rounded-2xl border p-3 shadow-sm transition-all backdrop-blur-sm',
                  table.occupiedCount > 0 ? 'border-red-300 bg-white' : 'border-emerald-200 bg-white/95'
                ]"
              >
                <div class="flex items-center justify-between mb-2">
                  <p class="text-sm font-bold text-gray-900">{{ table.area }}桌</p>
                  <p :class="['text-xs font-semibold px-2 py-0.5 rounded-full', table.occupiedCount > 0 ? 'bg-red-100 text-red-700' : 'bg-emerald-100 text-emerald-700']">
                    {{ table.occupiedCount > 0 ? `已坐 ${table.occupiedCount}/${table.seatCount}` : '当前全空' }}
                  </p>
                </div>
                <div
                  :class="[
                    'mx-auto rounded-2xl border-2 border-slate-300 bg-gradient-to-b from-slate-100 to-slate-200 px-3 py-3 shadow-inner',
                    table.shape === 'square' ? 'max-w-[180px]' : table.shape === 'tall' ? 'max-w-[140px]' : 'max-w-[240px]'
                  ]"
                >
                  <div
                    class="grid gap-2"
                    :style="{ gridTemplateColumns: `repeat(${table.seatColumns || 3}, minmax(0, 1fr))` }"
                  >
                    <button
                      v-for="seat in table.seats"
                      :key="`small-${table.area}-${seat.seatNo}`"
                      type="button"
                      @click="handleSeatLeftClick(table.area, seat.seatNo, seat.occupied)"
                      :class="[
                        'relative h-10 rounded-lg border flex items-center justify-center text-[12px] font-bold transition-colors',
                        isPendingSeatSelected(table.area, seat.seatNo)
                          ? 'ring-2 ring-blue-600 ring-offset-2 ring-offset-slate-200'
                          : '',
                        seat.occupied
                          ? 'bg-red-600 border-red-700 text-white'
                          : 'bg-white border-slate-300 text-slate-800 hover:bg-slate-50 cursor-pointer'
                      ]"
                      :title="seat.occupied ? `${seat.customerName || '已占用'}（${table.area}${seat.seatNo}）` : `${table.area}${seat.seatNo} 空位`"
                    >
                      {{ seat.seatNo }}
                      <span
                        :class="[
                          'absolute top-1.5 right-1.5 h-2.5 w-2.5 rounded-full',
                          seat.occupied ? 'bg-rose-200' : 'bg-emerald-500'
                        ]"
                      ></span>
                    </button>
                  </div>
                </div>
                <div class="mt-2 text-xs text-gray-600">
                  <span v-if="table.occupiedCount > 0">深红座位为占用，浅红座位可开台</span>
                  <span v-else>全部可开台</span>
                </div>
              </article>
            </div>
          </div>
        </div>
      </div>
    </Teleport>

    <Teleport to="body">
      <div
        v-if="showGardenModal"
        class="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-40 p-4"
        @mousedown="onBackdropMouseDown('timers-garden', $event)"
        @mouseup="onBackdropMouseUp('timers-garden', $event) && closeGardenModal()"
      >
        <div class="bg-white rounded-xl shadow-xl w-full max-w-5xl max-h-[90vh] overflow-y-auto">
          <div class="px-6 py-4 border-b border-gray-200 flex items-center justify-between">
            <h3 class="text-lg font-semibold text-gray-800">花园座位分布</h3>
            <button
              @click="closeGardenModal"
              class="text-gray-400 hover:text-gray-600 transition-colors"
            >
              <svg xmlns="http://www.w3.org/2000/svg" class="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>
          <div class="p-4 sm:p-5 bg-gradient-to-br from-emerald-50 via-lime-50 to-teal-50 border border-emerald-200 m-4 rounded-xl">
            <div class="flex items-center justify-between mb-3">
              <div class="text-xs text-slate-600">座位：红=有人，白=空位</div>
              <div class="text-xs text-slate-500">剩余 {{ gardenSeatSummary.available }} / 占用 {{ gardenSeatSummary.occupied }}</div>
            </div>
            <div class="mb-3 flex flex-wrap items-center gap-2">
              <button
                type="button"
                @click="deactivateMultiSeatSelectionMode()"
                :class="[
                  'rounded-lg px-3 py-1.5 text-xs font-semibold transition-colors',
                  seatSelectionMode === 'single'
                    ? 'bg-slate-900 text-white'
                    : 'border border-slate-300 text-slate-700 hover:bg-slate-50'
                ]"
              >
                单座位开台
              </button>
              <button
                type="button"
                @click="activateMultiSeatSelectionMode"
                :class="[
                  'rounded-lg px-3 py-1.5 text-xs font-semibold transition-colors',
                  seatSelectionMode === 'multi'
                    ? 'bg-blue-600 text-white'
                    : 'border border-blue-300 text-blue-700 hover:bg-blue-50'
                ]"
              >
                多人选座
              </button>
              <p class="text-xs text-slate-600 sm:ml-2">单座位直接左键开台；多人模式下左键点选或取消，选好后确认。</p>
            </div>
            <div v-if="seatSelectionMode === 'multi'" class="mb-3 rounded-lg border border-blue-200 bg-blue-50 px-3 py-2 text-xs text-blue-800">
              <p v-if="pendingMultiSeatCount > 0">已选座位：{{ getPendingSeatDisplayText() }}</p>
              <p v-else>请左键依次点选多人座位，再次点击已选座位可取消。</p>
              <p v-if="pendingMultiSeatCount >= 2 && pendingMultiSeatPreset" class="mt-1">
                将匹配 {{ pendingMultiSeatPreset.peopleCount }}人套餐，确认后自动预填。
              </p>
              <p v-else-if="pendingMultiSeatCount >= 2" class="mt-1 text-amber-700">
                当前已选 {{ pendingMultiSeatCount }} 个座位，但未配置对应套餐。
              </p>
              <div class="mt-2 flex flex-wrap items-center gap-2">
                <button
                  type="button"
                  @click="confirmPendingMultiSeatSelection"
                  :disabled="pendingMultiSeatCount < 2 || !pendingMultiSeatPreset"
                  class="rounded-lg bg-blue-600 px-3 py-1.5 text-xs font-semibold text-white hover:bg-blue-700 disabled:cursor-not-allowed disabled:bg-blue-300"
                >
                  确认多人选座
                </button>
                <button
                  type="button"
                  class="rounded-lg border border-blue-200 px-3 py-1.5 text-xs font-semibold text-blue-700 hover:bg-blue-100"
                  @click="clearPendingMultiSeatSelection"
                >
                  清空已选
                </button>
                <button
                  type="button"
                  class="rounded-lg border border-slate-200 px-3 py-1.5 text-xs font-semibold text-slate-700 hover:bg-slate-100"
                  @click="deactivateMultiSeatSelectionMode(true)"
                >
                  退出多人模式
                </button>
              </div>
            </div>
            <div class="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <article
                v-for="table in gardenSeatLayoutTables"
                :key="`garden-${table.area}`"
                :class="[
                  'rounded-2xl border p-3 shadow-sm transition-all backdrop-blur-sm',
                  table.occupiedCount > 0 ? 'border-red-300 bg-white' : 'border-emerald-200 bg-white/95'
                ]"
              >
                <div class="flex items-center justify-between mb-2">
                  <p class="text-sm font-bold text-gray-900">{{ table.area }}桌</p>
                  <p :class="['text-xs font-semibold px-2 py-0.5 rounded-full', table.occupiedCount > 0 ? 'bg-red-100 text-red-700' : 'bg-emerald-100 text-emerald-700']">
                    {{ table.occupiedCount > 0 ? `已坐 ${table.occupiedCount}/${table.seatCount}` : '当前全空' }}
                  </p>
                </div>
                <div
                  :class="[
                    'mx-auto rounded-2xl border-2 border-slate-300 bg-gradient-to-b from-slate-100 to-slate-200 px-3 py-3 shadow-inner',
                    table.area === 'K'
                      ? 'max-w-[220px]'
                      : table.shape === 'square'
                        ? 'max-w-[180px]'
                        : table.shape === 'tall'
                          ? 'max-w-[140px]'
                          : 'max-w-[240px]'
                  ]"
                >
                  <div
                    :class="[
                      isGardenKTable(table.area)
                        ? 'grid grid-cols-4 grid-rows-3 gap-1.5 h-[126px] items-center justify-items-center'
                        : 'grid gap-2'
                    ]"
                    :style="isGardenKTable(table.area) ? undefined : { gridTemplateColumns: `repeat(${table.seatColumns || 3}, minmax(0, 1fr))` }"
                  >
                    <button
                      v-for="seat in table.seats"
                      :key="`garden-${table.area}-${seat.seatNo}`"
                      type="button"
                      @click="handleSeatLeftClick(table.area, seat.seatNo, seat.occupied)"
                      :class="[
                        'relative rounded-lg border flex items-center justify-center text-[12px] font-bold transition-colors',
                        isGardenKTable(table.area) ? 'h-10 w-10' : 'h-10',
                        getGardenSeatGridPositionClass(table.area, seat.seatNo),
                        isPendingSeatSelected(table.area, seat.seatNo)
                          ? 'ring-2 ring-blue-600 ring-offset-2 ring-offset-slate-200'
                          : '',
                        seat.occupied
                          ? 'bg-red-600 border-red-700 text-white'
                          : 'bg-white border-slate-300 text-slate-800 hover:bg-slate-50 cursor-pointer'
                      ]"
                      :title="seat.occupied ? `${seat.customerName || '已占用'}（${table.area}${seat.seatNo}）` : `${table.area}${seat.seatNo} 空位`"
                    >
                      {{ seat.seatNo }}
                      <span
                        :class="[
                          'absolute top-1.5 right-1.5 h-2.5 w-2.5 rounded-full',
                          seat.occupied ? 'bg-rose-200' : 'bg-emerald-500'
                        ]"
                      ></span>
                    </button>
                  </div>
                </div>
                <div class="mt-2 text-xs text-gray-600">
                  <span v-if="table.occupiedCount > 0">深红座位为占用，浅红座位可开台</span>
                  <span v-else>全部可开台</span>
                </div>
              </article>
            </div>
          </div>
        </div>
      </div>
    </Teleport>

    <Teleport to="body">
      <div
        v-if="showUpstairsModal"
        class="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-40 p-4"
        @mousedown="onBackdropMouseDown('timers-upstairs', $event)"
        @mouseup="onBackdropMouseUp('timers-upstairs', $event) && closeUpstairsModal()"
      >
        <div class="bg-white rounded-xl shadow-xl w-full max-w-5xl max-h-[90vh] overflow-y-auto">
          <div class="px-6 py-4 border-b border-gray-200 flex items-center justify-between">
            <h3 class="text-lg font-semibold text-gray-800">楼上座位分布</h3>
            <button
              @click="closeUpstairsModal"
              class="text-gray-400 hover:text-gray-600 transition-colors"
            >
              <svg xmlns="http://www.w3.org/2000/svg" class="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>
          <div class="p-4 sm:p-5 bg-gradient-to-br from-slate-50 via-blue-50 to-cyan-50 border border-slate-200 m-4 rounded-xl">
            <div class="flex items-center justify-between mb-3">
              <div class="text-xs text-slate-600">座位：红=有人，白=空位</div>
              <div class="text-xs text-slate-500">剩余 {{ upstairsSeatSummary.available }} / 占用 {{ upstairsSeatSummary.occupied }}</div>
            </div>
            <div class="mb-3 flex flex-wrap items-center gap-2">
              <button
                type="button"
                @click="deactivateMultiSeatSelectionMode()"
                :class="[
                  'rounded-lg px-3 py-1.5 text-xs font-semibold transition-colors',
                  seatSelectionMode === 'single'
                    ? 'bg-slate-900 text-white'
                    : 'border border-slate-300 text-slate-700 hover:bg-slate-50'
                ]"
              >
                单座位开台
              </button>
              <button
                type="button"
                @click="activateMultiSeatSelectionMode"
                :class="[
                  'rounded-lg px-3 py-1.5 text-xs font-semibold transition-colors',
                  seatSelectionMode === 'multi'
                    ? 'bg-blue-600 text-white'
                    : 'border border-blue-300 text-blue-700 hover:bg-blue-50'
                ]"
              >
                多人选座
              </button>
              <p class="text-xs text-slate-600 sm:ml-2">单座位直接左键开台；多人模式下左键点选或取消，选好后确认。</p>
            </div>
            <div v-if="seatSelectionMode === 'multi'" class="mb-3 rounded-lg border border-blue-200 bg-blue-50 px-3 py-2 text-xs text-blue-800">
              <p v-if="pendingMultiSeatCount > 0">已选座位：{{ getPendingSeatDisplayText() }}</p>
              <p v-else>请左键依次点选多人座位，再次点击已选座位可取消。</p>
              <p v-if="pendingMultiSeatCount >= 2 && pendingMultiSeatPreset" class="mt-1">
                将匹配 {{ pendingMultiSeatPreset.peopleCount }}人套餐，确认后自动预填。
              </p>
              <p v-else-if="pendingMultiSeatCount >= 2" class="mt-1 text-amber-700">
                当前已选 {{ pendingMultiSeatCount }} 个座位，但未配置对应套餐。
              </p>
              <div class="mt-2 flex flex-wrap items-center gap-2">
                <button
                  type="button"
                  @click="confirmPendingMultiSeatSelection"
                  :disabled="pendingMultiSeatCount < 2 || !pendingMultiSeatPreset"
                  class="rounded-lg bg-blue-600 px-3 py-1.5 text-xs font-semibold text-white hover:bg-blue-700 disabled:cursor-not-allowed disabled:bg-blue-300"
                >
                  确认多人选座
                </button>
                <button
                  type="button"
                  class="rounded-lg border border-blue-200 px-3 py-1.5 text-xs font-semibold text-blue-700 hover:bg-blue-100"
                  @click="clearPendingMultiSeatSelection"
                >
                  清空已选
                </button>
                <button
                  type="button"
                  class="rounded-lg border border-slate-200 px-3 py-1.5 text-xs font-semibold text-slate-700 hover:bg-slate-100"
                  @click="deactivateMultiSeatSelectionMode(true)"
                >
                  退出多人模式
                </button>
              </div>
            </div>
            <div class="grid grid-cols-1 gap-4">
              <article
                v-for="table in upstairsSeatLayoutTables"
                :key="`upstairs-${table.area}`"
                :class="[
                  'rounded-2xl border p-3 shadow-sm transition-all backdrop-blur-sm',
                  table.occupiedCount > 0 ? 'border-red-300 bg-white' : 'border-emerald-200 bg-white/95'
                ]"
              >
                <div class="flex items-center justify-between mb-2">
                  <p class="text-sm font-bold text-gray-900">{{ table.area }}桌</p>
                  <p :class="['text-xs font-semibold px-2 py-0.5 rounded-full', table.occupiedCount > 0 ? 'bg-red-100 text-red-700' : 'bg-emerald-100 text-emerald-700']">
                    {{ table.occupiedCount > 0 ? `已坐 ${table.occupiedCount}/${table.seatCount}` : '当前全空' }}
                  </p>
                </div>
                <div
                  :class="[
                    'mx-auto rounded-2xl border-2 border-slate-300 bg-gradient-to-b from-slate-100 to-slate-200 px-3 py-3 shadow-inner',
                    table.shape === 'square' ? 'max-w-[180px]' : table.shape === 'tall' ? 'max-w-[140px]' : 'max-w-[210px]'
                  ]"
                >
                  <div
                    class="grid grid-cols-3 grid-rows-3 gap-1.5 h-[126px] items-center justify-items-center"
                  >
                    <button
                      v-for="seat in table.seats"
                      :key="`upstairs-${table.area}-${seat.seatNo}`"
                      type="button"
                      @click="handleSeatLeftClick(table.area, seat.seatNo, seat.occupied)"
                      :class="[
                        'relative h-12 w-12 rounded-lg border flex items-center justify-center text-sm font-bold transition-colors',
                        getUpstairsSeatGridPositionClass(seat.seatNo),
                        isPendingSeatSelected(table.area, seat.seatNo)
                          ? 'ring-2 ring-blue-600 ring-offset-2 ring-offset-slate-200'
                          : '',
                        seat.occupied
                          ? 'bg-red-600 border-red-700 text-white'
                          : 'bg-white border-slate-300 text-slate-800 hover:bg-slate-50 cursor-pointer'
                      ]"
                      :title="seat.occupied ? `${seat.customerName || '已占用'}（${table.area}${seat.seatNo}）` : `${table.area}${seat.seatNo} 空位`"
                    >
                      {{ seat.seatNo }}
                      <span
                        :class="[
                          'absolute top-1 right-1 h-2.5 w-2.5 rounded-full',
                          seat.occupied ? 'bg-rose-200' : 'bg-emerald-500'
                        ]"
                      ></span>
                    </button>
                  </div>
                </div>
                <div class="mt-2 text-xs text-gray-600">
                  <span v-if="table.occupiedCount > 0">深红座位为占用，浅红座位可开台</span>
                  <span v-else>全部可开台</span>
                </div>
              </article>
            </div>
          </div>
        </div>
      </div>
    </Teleport>

    <div v-if="loading && timers.length === 0" class="management-surface p-12 text-center text-gray-500">
      正在加载计时记录...
    </div>

    <div v-else-if="timers.length === 0" class="management-surface p-12 text-center">
      <p class="text-gray-500 mb-4">暂无进行中的计时记录。</p>
      <button
        @click="openAddModal"
        class="inline-flex items-center px-4 py-2 bg-[#1e40af] text-white rounded-lg hover:bg-[#1e3a8a] transition-colors"
      >
        开始计时
      </button>
    </div>

    <div v-else-if="filteredTimers.length === 0" class="management-surface p-12 text-center">
      <p class="text-gray-500 mb-4">暂无符合筛选条件的计时记录。</p>
      <button
        @click="resetFilters"
        class="inline-flex items-center px-4 py-2 border border-gray-300 text-gray-700 rounded-lg hover:bg-gray-50 transition-colors"
      >
        清空筛选
      </button>
    </div>

    <div v-else class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
      <div
        v-for="timer in filteredTimers"
        :key="timer.id"
        class="bg-white rounded-lg shadow-sm border border-gray-100 overflow-hidden h-full flex flex-col"
      >
        <div class="px-4 py-3 border-b border-gray-100 flex items-center justify-between">
          <div>
            <p class="font-medium text-gray-900">{{ timer.customerName || `客户 #${timer.customerId}` }}</p>
            <p class="text-xs text-gray-500">{{ timer.customerId }} · {{ formatTimerTableNoDisplay(timer) || '未设置桌号' }}</p>
          </div>
          <div class="flex items-center gap-2">
            <button
              @click="openEditModal(timer)"
              class="px-2.5 py-1 text-xs border border-blue-300 text-blue-700 rounded-md hover:bg-blue-50"
            >
              编辑
            </button>
            <span :class="['px-2 py-1 text-xs rounded-full', getStatusClass(timer.status)]">
              {{ getStatusLabel(timer.status) }}
            </span>
          </div>
        </div>

        <div class="px-4 py-3 space-y-2 text-sm flex-1">
          <p class="text-3xl font-bold text-blue-700 font-mono text-center py-2">
            {{ formatDuration(getElapsedSeconds(timer)) }}
          </p>
          <p><span class="text-gray-500">类型：</span> {{ getTimerTypeLabel(timer.timerType) }}</p>
          <p><span class="text-gray-500">桌号：</span> {{ formatTimerTableNoDisplay(timer) || '-' }}</p>
          <p><span class="text-gray-500">开始时间：</span> {{ formatDateTime(timer.startTime) }}</p>
          <p v-if="timer.packagePlan"><span class="text-gray-500">套餐方案：</span> {{ getPackagePlanLabel(timer.packagePlan) }}</p>
          <p><span class="text-gray-500">大图数量：</span> {{ timer.materials.largeImages || 0 }}</p>
          <p><span class="text-gray-500">超量小图：</span> {{ timer.materials.extraSmallImages || 0 }}</p>
          <p><span class="text-gray-500">超量大图：</span> {{ timer.materials.extraLargeImages || 0 }}</p>
          <p v-if="timer.notes"><span class="text-gray-500">备注：</span> {{ timer.notes }}</p>
        </div>

        <div class="px-4 py-3 bg-gray-50 border-t border-gray-100 flex justify-end gap-2 mt-auto">
          <button
            @click="toggleTimerPause(timer)"
            :disabled="submitting"
            :class="[
              'px-3 py-1.5 rounded-md text-sm disabled:opacity-50',
              timer.status === 'paused'
                ? 'bg-emerald-600 text-white hover:bg-emerald-700'
                : 'bg-amber-500 text-white hover:bg-amber-600'
            ]"
          >
            {{ timer.status === 'paused' ? '继续' : '暂停' }}
          </button>
          <button
            @click="openSettleModal(timer)"
            class="px-3 py-1.5 bg-orange-600 text-white rounded-md hover:bg-orange-700 text-sm"
          >
            结算
          </button>
          <button
            @click="cancelTimer(timer)"
            class="px-3 py-1.5 border border-red-300 text-red-600 rounded-md hover:bg-red-50 text-sm"
          >
            取消
          </button>
        </div>
      </div>
    </div>

    <Teleport to="body">
      <div
        v-if="showAddModal"
        class="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50"
        @mousedown="onBackdropMouseDown('timers-add', $event)"
        @mouseup="onBackdropMouseUp('timers-add', $event) && closeAddModal()"
      >
        <div class="bg-white rounded-xl shadow-xl w-full max-w-3xl mx-4 max-h-[90vh] overflow-y-auto">
          <div class="px-6 py-4 border-b border-gray-200 flex items-center justify-between">
            <h3 class="text-lg font-semibold text-gray-800">新增消费</h3>
            <button
              @click="closeAddModal()"
              class="text-gray-400 hover:text-gray-600 transition-colors"
            >
              <svg xmlns="http://www.w3.org/2000/svg" class="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>

          <div class="p-6 space-y-4">
            <div class="bg-blue-50 border border-blue-200 rounded-lg px-4 py-3 text-sm">
              <span v-if="addBalanceLoading" class="text-blue-700">正在获取客户余额...</span>
              <span v-else-if="addCurrentBalance !== null" class="text-blue-700">
                当前客户余额: <strong>￥{{ formatAmount(addCurrentBalance) }}</strong>
              </span>
              <span v-else class="text-blue-700">请选择客户以查看余额</span>
            </div>

            <TimerConsumeDialog
              ref="addTimerDialogRef"
              :model-value="addForm"
              :errors="addErrors"
              :customer-options="addTimerCustomerOptions"
              :enabled-misc-items="enabledMiscItems"
              :billing-rules="billingRules"
              @update:model-value="applyAddForm"
            />
          </div>

          <div class="px-6 py-4 border-t border-gray-200 flex justify-end gap-3">
            <button @click="closeAddModal()" class="px-4 py-2 border border-gray-300 rounded-lg text-gray-700 hover:bg-gray-50">取消</button>
            <button @click="startTimer" :disabled="submitting" class="px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 disabled:opacity-50">
              开始计时
            </button>
          </div>
        </div>
      </div>
    </Teleport>

    <Teleport to="body">
      <div
        v-if="showEditModal && editingTimer"
        class="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50"
        @mousedown="onBackdropMouseDown('timers-edit', $event)"
        @mouseup="onBackdropMouseUp('timers-edit', $event) && closeEditModal()"
      >
        <div class="bg-white rounded-xl shadow-xl w-full max-w-lg mx-4">
          <div class="px-6 py-4 border-b border-gray-200">
            <h3 class="text-lg font-semibold text-gray-800">编辑计时信息</h3>
            <p class="text-xs text-gray-500 mt-1">{{ editingTimer.customerName || editingTimer.customerId }}</p>
          </div>

          <div class="p-6 space-y-4">
            <div>
              <label class="block text-sm font-medium text-gray-700 mb-1">第1座位</label>
              <div class="grid grid-cols-2 gap-3">
                <select
                  v-model="editForm.tableArea"
                  :class="[
                    'w-full px-3 py-2 border rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent',
                    editErrors.tableNo ? 'border-red-500' : 'border-gray-300'
                  ]"
                >
                  <option v-for="area in tableAreaOptions" :key="area" :value="area">
                    {{ area }}桌
                  </option>
                </select>
                <select
                  v-model="editForm.tableSeat"
                  :class="[
                    'w-full px-3 py-2 border rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent',
                    editErrors.tableNo ? 'border-red-500' : 'border-gray-300'
                  ]"
                >
                  <option v-for="seat in tableSeatOptions" :key="seat" :value="seat">
                    {{ seat }}号
                  </option>
                </select>
              </div>
              <p v-if="editErrors.tableNo" class="text-red-500 text-xs mt-1">{{ editErrors.tableNo }}</p>
            </div>

            <div
              v-if="getRequiredExtraSeatCount(editForm.packagePlan, billingRules.value) > 0"
              class="space-y-3"
            >
              <p class="text-xs text-slate-600">
                当前套餐需选择 {{ getRequiredExtraSeatCount(editForm.packagePlan, billingRules.value) }} 个附加座位。
              </p>
              <div v-for="(seat, index) in editForm.extraTableSelections" :key="`edit-extra-seat-${index}`">
                <label class="block text-sm font-medium text-gray-700 mb-1">
                  第{{ index + 2 }}座位
                </label>
                <div class="grid grid-cols-2 gap-3">
                  <select
                    :value="seat.tableArea || editForm.tableArea"
                    :class="[
                      'w-full px-3 py-2 border rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent',
                      getEditExtraSeatError(index) ? 'border-red-500' : 'border-gray-300'
                    ]"
                    @change="updateEditExtraSeatArea(index, $event.target.value)"
                  >
                    <option v-for="area in tableAreaOptions" :key="`edit-extra-area-${index}-${area}`" :value="area">
                      {{ area }}桌
                    </option>
                  </select>
                  <select
                    :value="seat.tableSeat"
                    :class="[
                      'w-full px-3 py-2 border rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent',
                      getEditExtraSeatError(index) ? 'border-red-500' : 'border-gray-300'
                    ]"
                    @change="updateEditExtraSeatSeat(index, $event.target.value)"
                  >
                    <option value="">请选择号位</option>
                    <option v-for="seatNo in tableSeatOptions" :key="`edit-extra-seat-${index}-${seatNo}`" :value="seatNo">
                      {{ seatNo }}号
                    </option>
                  </select>
                </div>
                <p v-if="getEditExtraSeatError(index)" class="text-red-500 text-xs mt-1">
                  {{ getEditExtraSeatError(index) }}
                </p>
              </div>
              <p v-if="editErrors.extraTableNos" class="text-red-500 text-xs mt-1">{{ editErrors.extraTableNos }}</p>
            </div>

            <div>
              <label class="block text-sm font-medium text-gray-700 mb-1">初始套餐</label>
              <select
                v-model="editForm.packagePlan"
                :class="[
                  'w-full px-3 py-2 border rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent',
                  editErrors.packagePlan ? 'border-red-500' : 'border-gray-300'
                ]"
              >
                <option v-for="item in allPackagePlanOptions" :key="item.value" :value="item.value">
                  {{ item.label }}
                </option>
              </select>
              <p v-if="editErrors.packagePlan" class="text-red-500 text-xs mt-1">{{ editErrors.packagePlan }}</p>
              <p class="text-xs text-gray-500 mt-1">修改后将自动同步计时类型。</p>
            </div>

            <div>
              <label class="block text-sm font-medium text-gray-700 mb-1">备注</label>
              <textarea
                v-model="editForm.notes"
                rows="2"
                class="w-full px-3 py-2 border border-gray-300 rounded-lg resize-none focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                placeholder="可编辑备注"
              ></textarea>
            </div>

            <div class="grid grid-cols-1 md:grid-cols-3 gap-3">
              <div>
                <label class="block text-sm font-medium text-gray-700 mb-1">大图数量</label>
                <input
                  v-model.number="editForm.largeImages"
                  type="number"
                  min="0"
                  class="w-full px-3 py-2 border border-gray-300 rounded-lg"
                >
                <p v-if="editErrors.largeImages" class="text-red-500 text-xs mt-1">{{ editErrors.largeImages }}</p>
              </div>
              <div>
                <label class="block text-sm font-medium text-gray-700 mb-1">超量小图</label>
                <input
                  v-model.number="editForm.extraSmallImages"
                  type="number"
                  min="0"
                  class="w-full px-3 py-2 border border-gray-300 rounded-lg"
                >
                <p v-if="editErrors.extraSmallImages" class="text-red-500 text-xs mt-1">{{ editErrors.extraSmallImages }}</p>
              </div>
              <div>
                <label class="block text-sm font-medium text-gray-700 mb-1">超量大图</label>
                <input
                  v-model.number="editForm.extraLargeImages"
                  type="number"
                  min="0"
                  class="w-full px-3 py-2 border border-gray-300 rounded-lg"
                >
                <p v-if="editErrors.extraLargeImages" class="text-red-500 text-xs mt-1">{{ editErrors.extraLargeImages }}</p>
              </div>
            </div>

            <div v-if="enabledMiscItems.length > 0" class="space-y-3">
              <div class="flex items-center justify-between">
                <h4 class="text-sm font-medium text-gray-700">杂项计费（仅整数）</h4>
                <button
                  type="button"
                  class="text-xs text-blue-600 hover:text-blue-700"
                  @click="syncEditMiscSelections({})"
                >
                  一键清零
                </button>
              </div>
              <div class="grid grid-cols-1 md:grid-cols-3 gap-3">
                <div v-for="item in enabledMiscItems" :key="`edit-misc-${item.id}`">
                  <label class="block text-sm font-medium text-gray-700 mb-1">
                    {{ item.name }}（¥{{ formatAmount(item.unit_price) }}/{{ item.unit_label || '个' }}）
                  </label>
                  <p class="text-xs text-slate-500 mb-1">可用库存：{{ formatMiscStock(item) }}</p>
                  <input
                    v-model.number="editForm.miscSelections[item.id]"
                    type="number"
                    min="0"
                    :max="getMiscAvailableQuantity(item)"
                    step="1"
                    class="w-full px-3 py-2 border border-gray-300 rounded-lg"
                    @change="clampMiscSelection(editForm.miscSelections, item)"
                  />
                </div>
              </div>
              <p v-if="editErrors.misc" class="text-red-500 text-xs mt-1">{{ editErrors.misc }}</p>
            </div>
          </div>

          <div class="px-6 py-4 border-t border-gray-200 flex justify-end gap-3">
            <button @click="closeEditModal" class="px-4 py-2 border border-gray-300 rounded-lg text-gray-700 hover:bg-gray-50">取消</button>
            <button @click="saveTimerMaterials" :disabled="submitting" class="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50">
              保存
            </button>
          </div>
        </div>
      </div>
    </Teleport>

    <Teleport to="body">
      <div
        v-if="showSettleModal && selectedTimer"
        class="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50"
        @mousedown="onBackdropMouseDown('timers-settle', $event)"
        @mouseup="onBackdropMouseUp('timers-settle', $event) && closeSettleModal()"
      >
        <div class="bg-white rounded-xl shadow-xl w-full max-w-2xl mx-4 max-h-[90vh] overflow-y-auto">
          <div class="px-6 py-4 border-b border-gray-200">
            <h3 class="text-lg font-semibold text-gray-800">计时结算</h3>
          </div>

          <div class="p-6 space-y-4">
            <div class="bg-blue-50 border border-blue-200 rounded-lg p-4 text-sm text-blue-800 space-y-1">
              <p>客户：{{ selectedTimer.customerName || `客户 #${selectedTimer.customerId}` }}</p>
              <p>实际计时：{{ formatDuration(getElapsedSeconds(selectedTimer)) }}</p>
              <p>计费时长：{{ settleElapsedMinutes }} 分钟</p>
            </div>

            <div class="bg-amber-50 border border-amber-200 rounded-lg p-4 space-y-3">
              <label class="inline-flex items-center gap-2 text-sm font-medium text-amber-900">
                <input v-model="settleForm.useManualElapsed" type="checkbox" class="rounded border-amber-400 text-amber-600 focus:ring-amber-500" />
                手动输入计时时长（测试）
              </label>
              <div v-if="settleForm.useManualElapsed">
                <input
                  v-model.number="settleForm.manualElapsedMinutes"
                  type="number"
                  min="0"
                  class="w-full px-3 py-2 border border-amber-300 rounded-lg"
                  placeholder="例如：95"
                />
                <p class="text-xs text-amber-800 mt-1">用于测试结算预览，提交结算时会按此分钟数计算。</p>
                <p v-if="settleErrors.manualElapsed" class="text-red-500 text-xs mt-1">{{ settleErrors.manualElapsed }}</p>
              </div>
            </div>

            <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <label class="block text-sm font-medium text-gray-700 mb-1">计费类型</label>
                <select v-model="settleForm.billingType" class="w-full px-3 py-2 border border-gray-300 rounded-lg">
                  <option value="limited">限时套餐</option>
                  <option value="weekday">工作日套餐</option>
                  <option value="weekend">周末套餐</option>
                </select>
              </div>

              <div v-if="settleForm.billingType === 'limited'">
                <label class="block text-sm font-medium text-gray-700 mb-1">套餐时长</label>
                <select v-model="settleForm.duration" class="w-full px-3 py-2 border border-gray-300 rounded-lg">
                  <option value="1">1小时</option>
                  <option value="2">2小时</option>
                </select>
              </div>

              <div v-if="settleForm.billingType === 'weekday'">
                <label class="block text-sm font-medium text-gray-700 mb-1">工作日方案</label>
                <select v-model="settleForm.weekdayType" class="w-full px-3 py-2 border border-gray-300 rounded-lg">
                  <option v-for="item in weekdayTypeOptions" :key="item.value" :value="item.value">
                    {{ item.label }}
                  </option>
                </select>
              </div>

              <div v-if="settleForm.billingType === 'weekend'">
                <label class="block text-sm font-medium text-gray-700 mb-1">周末方案</label>
                <select v-model="settleForm.weekendType" class="w-full px-3 py-2 border border-gray-300 rounded-lg">
                  <option v-for="item in weekendTypeOptions" :key="item.value" :value="item.value">
                    {{ item.label }}
                  </option>
                </select>
              </div>

              <div v-if="settleForm.billingType === 'limited'">
                <label class="block text-sm font-medium text-gray-700 mb-1">超时分钟（手动调整）</label>
                <input v-model.number="settleForm.overtimeMinutes" type="number" min="0" class="w-full px-3 py-2 border border-gray-300 rounded-lg" />
              </div>
            </div>

            <div class="grid grid-cols-1 md:grid-cols-4 gap-3">
              <div>
                <label class="block text-sm font-medium text-gray-700 mb-1">大图数量</label>
                <input v-model.number="settleForm.largeImages" type="number" min="0" class="w-full px-3 py-2 border border-gray-300 rounded-lg" />
              </div>
              <div>
                <label class="block text-sm font-medium text-gray-700 mb-1">超量小图</label>
                <input v-model.number="settleForm.extraSmallImages" type="number" min="0" class="w-full px-3 py-2 border border-gray-300 rounded-lg" />
              </div>
              <div>
                <label class="block text-sm font-medium text-gray-700 mb-1">超量大图</label>
                <input v-model.number="settleForm.extraLargeImages" type="number" min="0" class="w-full px-3 py-2 border border-gray-300 rounded-lg" />
              </div>
              <div>
                <label class="block text-sm font-medium text-gray-700 mb-1">附加费用</label>
                <input v-model.number="settleForm.additionalFee" type="number" step="0.01" min="0" class="w-full px-3 py-2 border border-gray-300 rounded-lg" />
              </div>
            </div>

            <div v-if="enabledMiscItems.length > 0" class="space-y-3">
              <div class="flex items-center justify-between">
                <h4 class="text-sm font-medium text-gray-700">杂项计费（仅整数）</h4>
                <button
                  type="button"
                  class="text-xs text-blue-600 hover:text-blue-700"
                  @click="syncSettleMiscSelections({})"
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
                    v-model.number="settleForm.miscSelections[item.id]"
                    type="number"
                    min="0"
                    :max="getMiscAvailableQuantity(item)"
                    step="1"
                    class="w-full px-3 py-2 border border-gray-300 rounded-lg"
                    @change="clampMiscSelection(settleForm.miscSelections, item)"
                  />
                </div>
              </div>
            </div>

            <div class="flex flex-col gap-2">
              <label class="inline-flex items-center gap-2 text-sm text-gray-700">
                <input
                  v-model="settleForm.meituanCustomer"
                  type="checkbox"
                  class="h-4 w-4 rounded border-gray-300 text-blue-600 focus:ring-blue-500"
                >
                美团客户
              </label>

              <label class="inline-flex items-center gap-2 text-sm text-gray-700">
                <input
                  v-model="settleForm.applyOvertimeFee"
                  type="checkbox"
                  :disabled="settleOvertimeMinutes > 0 && !isAdmin"
                  class="h-4 w-4 rounded border-gray-300 text-blue-600 focus:ring-blue-500 disabled:opacity-60"
                >
                计入加班费用
              </label>
              <p v-if="settleOvertimeMinutes > 0 && !isAdmin" class="text-xs text-gray-500">
                当前账号非管理员，仅可查看加班费用，不能取消。
              </p>
            </div>

            <div>
              <label class="block text-sm font-medium text-gray-700 mb-1">备注</label>
              <textarea v-model="settleForm.notes" rows="2" class="w-full px-3 py-2 border border-gray-300 rounded-lg resize-none"></textarea>
            </div>

            <div class="bg-green-50 border border-green-200 rounded-lg p-4 text-sm text-green-800 space-y-1">
              <p>应用计费：{{ getTimerTypeLabel(settlePreview.billingType) }}</p>
              <p>基础费用：￥{{ formatAmount(settlePreview.baseFee) }}</p>
              <p>超时费用：￥{{ formatAmount(settlePreview.overtimeFee) }}</p>
              <p>素材费用：￥{{ formatAmount(settlePreview.materialFee) }}</p>
              <p>杂项费用：￥{{ formatAmount(settlePreview.miscFee) }}</p>
              <p>附加费用：￥{{ formatAmount(settleRawAdditionalFee) }}</p>
              <p>加班费用：￥{{ formatAmount(settleOvertimeFee) }}</p>
              <p class="font-semibold text-base">额外消费：￥{{ formatAmount(settleExtraConsumption) }}</p>
              <p v-if="settleForm.meituanCustomer">美团抽成（按开始套餐）：-￥{{ formatAmount(settleMeituanDeduction) }}</p>
              <p class="font-semibold text-base">
                结算金额：￥{{ formatAmount(settleForm.meituanCustomer ? settleFinalAmount : settlePreview.total) }}
              </p>
              <p v-if="settlePreview.details?.length || settlePackageUpgradeFee > 0" class="text-xs text-green-700">
                <span v-if="settlePreview.details?.length">{{ settlePreview.details.join(' | ') }}</span>
                <span v-if="settlePackageUpgradeFee > 0">
                  <span v-if="settlePreview.details?.length"> | </span>
                  已含自动变更套餐差额：￥{{ formatAmount(settlePackageUpgradeFee) }}
                </span>
              </p>
            </div>

            <p v-if="settleErrors.total" class="text-red-500 text-xs">{{ settleErrors.total }}</p>
            <p v-if="settleErrors.misc" class="text-red-500 text-xs">{{ settleErrors.misc }}</p>
            <p v-if="settleErrors.general" class="text-red-500 text-xs">{{ settleErrors.general }}</p>
          </div>

          <div class="px-6 py-4 border-t border-gray-200 flex justify-end gap-3">
            <button @click="closeSettleModal" class="px-4 py-2 border border-gray-300 rounded-lg text-gray-700 hover:bg-gray-50">取消</button>
            <button @click="submitSettlement" :disabled="submitting" class="px-4 py-2 bg-orange-600 text-white rounded-lg hover:bg-orange-700 disabled:opacity-50">
              确认结算
            </button>
          </div>
        </div>
      </div>
    </Teleport>
  </div>
</template>

