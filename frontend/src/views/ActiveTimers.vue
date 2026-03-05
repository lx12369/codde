<script setup>
import { ref, reactive, computed, watch, onMounted, onUnmounted, nextTick } from 'vue'
import api from '@/api'
import { useAuthStore } from '@/stores'
import { useBackdropClose } from '@/utils/modalBackdrop'
import TimerConsumeDialog from '@/components/timers/TimerConsumeDialog.vue'
import {
  createTimerConsumeForm,
  timerTypeOptions as sharedTimerTypeOptions,
  timerPackagePlanOptionsByType as sharedTimerPackagePlanOptionsByType,
  getDefaultTimerPackagePlan,
  validateTimerConsumeForm as validateSharedTimerConsumeForm,
  buildTimerConsumeRequestPayload,
  TABLE_AREA_OPTIONS,
  TABLE_SEAT_OPTIONS,
  buildTableNo,
  isDoublePackagePlan
} from '@/utils/timerConsume'
import {
  normalizeBillingRules,
  calculateConsumptionAmount,
  buildConsumptionDescription,
  calculateMeituanDeduction,
  applyDeduction,
  getPackagePlanBaseFee
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
const restoreRoomAfterAddModal = ref('')
const warningQueue = ref([])
const activeWarning = ref(null)
const pendingDoubleSeatStart = ref(null)
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
  weekdayType: 'singleUnlimited',
  weekendType: 'singleUnlimited',
  overtimeMinutes: 0,
  largeImages: 0,
  extraSmallImages: 0,
  extraLargeImages: 0,
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
  secondTableArea: TABLE_AREA_OPTIONS[0],
  secondTableSeat: TABLE_SEAT_OPTIONS[0],
  secondTableNo: '',
  packagePlan: '',
  notes: '',
  largeImages: 0,
  extraSmallImages: 0,
  extraLargeImages: 0
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

const weekdayTypeOptions = [
  { value: 'singleUnlimited', label: '单人不限时不限板' },
  { value: 'doubleUnlimited', label: '双人不限时不限板' },
  { value: 'singleLimited', label: '单人不限时限板' }
]

const weekendTypeOptions = [
  { value: 'singleUnlimited', label: '单人不限时不限板' },
  { value: 'doubleUnlimited', label: '双人不限时不限板' },
  { value: 'singleLimited', label: '单人不限时限板' }
]

const addPackagePlanOptionsByType = sharedTimerPackagePlanOptionsByType

const allPackagePlanOptions = computed(() => Object.values(addPackagePlanOptionsByType).flat())
const filterPackagePlanOptions = computed(() => {
  if (!filterForm.timerType) {
    return allPackagePlanOptions.value
  }
  return addPackagePlanOptionsByType[filterForm.timerType] || []
})

function getDefaultAddPackagePlan(timerType = 'limited') {
  return getDefaultTimerPackagePlan(timerType)
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

const settleOvertimeFee = computed(() => {
  if (!settleForm.applyOvertimeFee) return 0
  return round2(settleOvertimeMinutes.value * settleOvertimeRatePerMinute.value)
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
  if (timerType === 'weekday') {
    if (packagePlan === 'weekdayDoubleUnlimited') return 'doubleUnlimited'
    if (packagePlan === 'weekdaySingleLimited') return 'singleLimited'
    return 'singleUnlimited'
  }

  if (timerType === 'weekend') {
    if (packagePlan === 'weekendDoubleUnlimited') return 'doubleUnlimited'
    if (packagePlan === 'weekendSingleLimited') return 'singleLimited'
    return 'singleUnlimited'
  }

  return ''
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
    settleForm.weekdayType = 'singleUnlimited'
    settleForm.overtimeMinutes = 0
    return
  }

  if (recommended.billingType === 'weekend') {
    settleForm.billingType = 'weekend'
    settleForm.weekendType = 'singleUnlimited'
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
  const map = {
    limited1h: '限时1小时',
    limited2h: '限时2小时',
    weekdaySingleUnlimited: '工作日单人不限时不限板',
    weekdayDoubleUnlimited: '工作日双人不限时不限板',
    weekdaySingleLimited: '工作日单人不限时限板',
    weekendSingleUnlimited: '周末单人不限时不限板',
    weekendDoubleUnlimited: '周末双人不限时不限板',
    weekendSingleLimited: '周末单人不限时限板'
  }
  return map[plan] || '-'
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

function parseTableNoParts(tableNo) {
  const parsed = parseExactTableNo(tableNo)
  if (!parsed) {
    return {
      tableArea: TABLE_AREA_OPTIONS[0],
      tableSeat: TABLE_SEAT_OPTIONS[0]
    }
  }
  const tableArea = parsed.tableArea
  const tableSeat = parsed.tableSeat
  return {
    tableArea: TABLE_AREA_OPTIONS.includes(tableArea) ? tableArea : TABLE_AREA_OPTIONS[0],
    tableSeat: TABLE_SEAT_OPTIONS.includes(tableSeat) ? tableSeat : TABLE_SEAT_OPTIONS[0]
  }
}

function getTimerOccupiedTableNos(timer) {
  const seats = []
  const firstSeat = normalizeTableNo(timer?.tableNo)
  if (isValidTableNo(firstSeat)) {
    seats.push(firstSeat)
  }

  if (isDoublePackagePlan(timer?.packagePlan)) {
    const secondSeat = normalizeTableNo(timer?.secondTableNo)
    if (isValidTableNo(secondSeat) && secondSeat !== firstSeat) {
      seats.push(secondSeat)
    }
  }

  return seats
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

function parseTimerNotes(rawNotes) {
  if (!rawNotes) {
      return {
        note: '',
        packagePlan: '',
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
      }
    }
  }

  try {
    const parsed = JSON.parse(rawNotes)
    if (parsed && typeof parsed === 'object') {
      return {
        note: parsed.note || '',
        packagePlan: parsed.packagePlan || '',
        secondTableNo: normalizeTableNo(parsed.secondTableNo),
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
        }
      }
    }
  } catch {
    // fallback to plain text.
  }

  return {
    note: String(rawNotes),
    packagePlan: '',
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
    }
  }
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
    secondTableNo: parsedNotes.secondTableNo || '',
    meituanCustomer: Boolean(parsedNotes.meituanCustomer),
    meituanPackageBaseFee: Number(parsedNotes.meituanPackageBaseFee) || 0,
    timing,
    materials: parsedNotes.materials
  }
}

function toNonNegativeInteger(value) {
  const n = Number(value)
  if (!Number.isFinite(n) || n < 0) return null
  return Math.floor(n)
}

function buildTimerNotesPayload(timer, materials) {
  return JSON.stringify({
    note: timer?.notes || '',
    packagePlan: timer?.packagePlan || '',
    secondTableNo: timer?.secondTableNo || '',
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
    }
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
  } catch (error) {
    console.error('获取计费规则失败:', error)
    billingRules.value = normalizeBillingRules()
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
  Object.assign(addForm, createTimerConsumeForm())
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
  Object.assign(addForm, createTimerConsumeForm(), nextForm)
}

function resetFilters() {
  filterForm.keyword = ''
  filterForm.timerType = ''
  filterForm.packagePlan = ''
}

function resetEditForm(timer = null) {
  const tableParts = parseTableNoParts(timer?.tableNo)
  const secondTableParts = parseTableNoParts(timer?.secondTableNo)
  editForm.tableArea = tableParts.tableArea
  editForm.tableSeat = tableParts.tableSeat
  editForm.tableNo = buildTableNo(tableParts.tableArea, tableParts.tableSeat)
  editForm.secondTableArea = secondTableParts.tableArea
  editForm.secondTableSeat = secondTableParts.tableSeat
  editForm.secondTableNo = buildTableNo(secondTableParts.tableArea, secondTableParts.tableSeat)
  editForm.packagePlan = timer?.packagePlan || getDefaultAddPackagePlan(timer?.timerType || 'limited')
  editForm.notes = timer?.notes || ''
  editForm.largeImages = Number(timer?.materials?.largeImages) || 0
  editForm.extraSmallImages = Number(timer?.materials?.extraSmallImages) || 0
  editForm.extraLargeImages = Number(timer?.materials?.extraLargeImages) || 0
  editErrors.value = {}
}

function isMeituanCustomerByName(name) {
  const text = String(name || '').trim()
  return text === '美团客户'
}

function resetSettleForm(timer = null) {
  settleForm.billingType = timer?.timerType || 'limited'
  settleForm.duration = '1'
  settleForm.weekdayType = 'singleUnlimited'
  settleForm.weekendType = 'singleUnlimited'
  settleForm.overtimeMinutes = 0
  settleForm.largeImages = Number(timer?.materials?.largeImages) || 0
  settleForm.extraSmallImages = Number(timer?.materials?.extraSmallImages) || 0
  settleForm.extraLargeImages = Number(timer?.materials?.extraLargeImages) || 0
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
  showLivingRoomModal.value = true
}

function closeLivingRoomModal() {
  showLivingRoomModal.value = false
}

function openSmallRoomModal() {
  showSmallRoomModal.value = true
}

function closeSmallRoomModal() {
  showSmallRoomModal.value = false
}

function openGardenModal() {
  showGardenModal.value = true
}

function closeGardenModal() {
  showGardenModal.value = false
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
  addForm.secondTableArea = area
  addForm.secondTableSeat = ''
  addForm.secondTableNo = ''
}

function clearPendingDoubleSeatStart() {
  pendingDoubleSeatStart.value = null
}

function resolveDoublePackagePreset() {
  const dayType = getEffectiveBillingDayType(new Date())
  if (dayType === 'weekend') {
    return { timerType: 'weekend', packagePlan: 'weekendDoubleUnlimited' }
  }
  return { timerType: 'weekday', packagePlan: 'weekdayDoubleUnlimited' }
}

function handleSeatRightClick(tableArea, seatNo, occupied = false) {
  if (occupied) {
    showFeedback('error', `该座位已有人：${tableArea}${seatNo}`)
    return
  }
  pendingDoubleSeatStart.value = {
    tableArea: String(tableArea || '').trim().toUpperCase(),
    seatNo: String(seatNo || '').trim()
  }
  showFeedback('info', `已选第一座位 ${tableArea}${seatNo}，请左键点击第二座位创建双人套餐`)
}

async function handleSeatLeftClick(tableArea, seatNo, occupied = false) {
  const area = String(tableArea || '').trim().toUpperCase()
  const seat = String(seatNo || '').trim()

  if (!pendingDoubleSeatStart.value) {
    await openAddModalForSeat(area, seat, occupied)
    return
  }

  if (occupied) {
    showFeedback('error', `第二座位已有人：${area}${seat}`)
    return
  }

  const first = pendingDoubleSeatStart.value
  if (first.tableArea === area && first.seatNo === seat) {
    showFeedback('error', '第二座位不能与第一座位相同')
    return
  }

  await openAddModal()
  const firstArea = first.tableArea
  const firstSeat = first.seatNo
  const secondArea = area
  const secondSeat = seat
  const preset = resolveDoublePackagePreset()

  addForm.tableArea = firstArea
  addForm.tableSeat = firstSeat
  addForm.tableNo = buildTableNo(firstArea, firstSeat)
  addForm.secondTableArea = secondArea
  addForm.secondTableSeat = secondSeat
  addForm.secondTableNo = buildTableNo(secondArea, secondSeat)
  addForm.timerType = preset.timerType
  addForm.packagePlan = preset.packagePlan
  clearPendingDoubleSeatStart()
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
  }
  addErrors.value = {}
  addCurrentBalance.value = null
  addBalanceLoading.value = false
  clearPendingDoubleSeatStart()
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
  const { isValid, errors } = validateSharedTimerConsumeForm(addForm, addTimerCustomerOptions.value)
  const tableNo = normalizeTableNo(buildTableNo(addForm.tableArea, addForm.tableSeat) || addForm.tableNo)
  const secondTableNo = normalizeTableNo(buildTableNo(addForm.secondTableArea, addForm.secondTableSeat) || addForm.secondTableNo)
  addForm.tableNo = tableNo
  addForm.secondTableNo = secondTableNo

  if (tableNo && !isValidTableNo(tableNo)) {
    errors.tableNo = '桌号必须在 A-H/J-N/P-Z 桌、1-20号范围内'
  } else if (tableNo && isTableNoOccupied(tableNo)) {
    errors.tableNo = `桌号已占用：${tableNo}`
  }

  if (isDoublePackagePlan(addForm.packagePlan)) {
    if (!secondTableNo) {
      errors.secondTableNo = '双人套餐请选择第二个座位'
    } else if (!isValidTableNo(secondTableNo)) {
      errors.secondTableNo = '第二座位格式不正确'
    } else if (secondTableNo === tableNo) {
      errors.secondTableNo = '第二座位不能与第一座位相同'
    } else if (isTableNoOccupied(secondTableNo)) {
      errors.secondTableNo = `第二座位已占用：${secondTableNo}`
    }
  }

  addErrors.value = errors
  return isValid && Object.keys(errors).length === 0
}

function validateEditForm() {
  const errors = {}
  const tableNo = normalizeTableNo(buildTableNo(editForm.tableArea, editForm.tableSeat) || editForm.tableNo)
  const secondTableNo = normalizeTableNo(buildTableNo(editForm.secondTableArea, editForm.secondTableSeat) || editForm.secondTableNo)
  editForm.tableNo = tableNo
  editForm.secondTableNo = secondTableNo

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

  if (isDoublePackagePlan(editForm.packagePlan)) {
    if (!secondTableNo) {
      errors.secondTableNo = '双人套餐请选择第二个座位'
    } else if (!isValidTableNo(secondTableNo)) {
      errors.secondTableNo = '第二座位格式不正确'
    } else if (secondTableNo === tableNo) {
      errors.secondTableNo = '第二座位不能与第一座位相同'
    } else if (isTableNoOccupied(secondTableNo, editingTimer.value?.id)) {
      errors.secondTableNo = `第二座位已占用：${secondTableNo}`
    }
  }

  const largeImages = toNonNegativeInteger(editForm.largeImages)
  const extraSmallImages = toNonNegativeInteger(editForm.extraSmallImages)
  const extraLargeImages = toNonNegativeInteger(editForm.extraLargeImages)

  if (largeImages === null) errors.largeImages = '大图数量必须大于或等于 0'
  if (extraSmallImages === null) errors.extraSmallImages = '超量小图必须大于或等于 0'
  if (extraLargeImages === null) errors.extraLargeImages = '超量大图必须大于或等于 0'

  editErrors.value = errors

  if (Object.keys(errors).length > 0) return null

  return {
    tableNo,
    secondTableNo: isDoublePackagePlan(editForm.packagePlan) ? secondTableNo : '',
    packagePlan: editForm.packagePlan,
    notes: String(editForm.notes || '').trim(),
    largeImages,
    extraSmallImages,
    extraLargeImages
  }
}

function resolveTimerTypeByPackagePlan(packagePlan, fallback = 'limited') {
  const plan = String(packagePlan || '')
  if (plan.startsWith('weekday')) return 'weekday'
  if (plan.startsWith('weekend')) return 'weekend'
  if (plan.startsWith('limited')) return 'limited'
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

  settleErrors.value = errors
  return Object.keys(errors).length === 0
}

async function startTimer() {
  if (!validateAddForm()) return

  submitting.value = true
  try {
    await api.post('/active-timers', buildTimerConsumeRequestPayload(addForm))
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
        secondTableNo: materials.secondTableNo
      },
      materials
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
          `加班费用￥${formatAmount(settleOvertimeFee.value)}（${settleOvertimeMinutes.value}分钟，￥${formatAmount(settleOvertimeRatePerMinute.value)}/分钟）`
        )
      } else {
        settleNotesParts.push(
          `已取消加班费用（${settleOvertimeMinutes.value}分钟，原￥${formatAmount(settleOvertimeMinutes.value * settleOvertimeRatePerMinute.value)}）`
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

    await api.post(`/active-timers/${selectedTimer.value.id}/settle`, {
      amount: settleFinalAmount.value,
      description,
      notes: settleNotes
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
      timer.materials
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
  [
    () => showSettleModal.value,
    () => selectedTimer.value?.id,
    () => settleElapsedMinutes.value,
    () => billingRules.value
  ],
  ([visible]) => {
    if (!visible || !selectedTimer.value) return
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
      <div class="mb-3 flex justify-end">
        <button
          @click="testSpeakerBroadcast"
          class="inline-flex items-center px-4 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 transition-colors"
        >
          测试播报
        </button>
      </div>
      <div class="grid grid-cols-1 md:grid-cols-3 gap-3">
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
      </div>
      <div class="mt-3 flex justify-end">
        <button
          @click="resetFilters"
          :disabled="!hasActiveFilters"
          class="px-3 py-1.5 border border-gray-300 text-sm text-gray-700 rounded-lg hover:bg-gray-50 disabled:opacity-40 disabled:cursor-not-allowed"
        >
          重置筛选
        </button>
      </div>
    </div>

    <section class="management-surface p-4 sm:p-5">
      <div class="grid grid-cols-1 md:grid-cols-3 gap-3">
        <button
          type="button"
          @click="openLivingRoomModal"
          class="w-full rounded-2xl border border-slate-200 bg-gradient-to-br from-slate-50 via-blue-50 to-cyan-50 p-4 text-left hover:border-blue-300 hover:shadow-md transition"
        >
          <div class="flex items-center justify-between">
            <div>
              <p class="text-base font-bold text-slate-900">客厅座位分布</p>
              <p class="text-xs text-slate-600 mt-1">点击查看客厅座位图（右键选第一座位，左键选第二座位）</p>
            </div>
            <div class="text-right">
              <p class="text-xs text-slate-500">总座位 {{ livingRoomSeatSummary.total }}</p>
              <p class="text-sm font-semibold text-emerald-700">剩余 {{ livingRoomSeatSummary.available }}</p>
              <p class="text-sm font-semibold text-rose-700">占用 {{ livingRoomSeatSummary.occupied }}</p>
            </div>
          </div>
        </button>
        <button
          type="button"
          @click="openSmallRoomModal"
          class="w-full rounded-2xl border border-slate-200 bg-gradient-to-br from-violet-50 via-fuchsia-50 to-pink-50 p-4 text-left hover:border-fuchsia-300 hover:shadow-md transition"
        >
          <div class="flex items-center justify-between">
            <div>
              <p class="text-base font-bold text-slate-900">小房间座位分布</p>
              <p class="text-xs text-slate-600 mt-1">点击查看小房间座位图（右键选第一座位，左键选第二座位）</p>
            </div>
            <div class="text-right">
              <p class="text-xs text-slate-500">总座位 {{ smallRoomSeatSummary.total }}</p>
              <p class="text-sm font-semibold text-emerald-700">剩余 {{ smallRoomSeatSummary.available }}</p>
              <p class="text-sm font-semibold text-rose-700">占用 {{ smallRoomSeatSummary.occupied }}</p>
            </div>
          </div>
        </button>
        <button
          type="button"
          @click="openGardenModal"
          class="w-full rounded-2xl border border-slate-200 bg-gradient-to-br from-emerald-50 via-lime-50 to-teal-50 p-4 text-left hover:border-emerald-300 hover:shadow-md transition"
        >
          <div class="flex items-center justify-between">
            <div>
              <p class="text-base font-bold text-slate-900">花园座位分布</p>
              <p class="text-xs text-slate-600 mt-1">点击查看花园座位图（右键选第一座位，左键选第二座位）</p>
            </div>
            <div class="text-right">
              <p class="text-xs text-slate-500">总座位 {{ gardenSeatSummary.total }}</p>
              <p class="text-sm font-semibold text-emerald-700">剩余 {{ gardenSeatSummary.available }}</p>
              <p class="text-sm font-semibold text-rose-700">占用 {{ gardenSeatSummary.occupied }}</p>
            </div>
          </div>
        </button>
      </div>
    </section>

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
            <p class="mb-3 text-xs text-slate-600">
              右键选第一座位，左键选第二座位可快速创建双人套餐；直接左键可创建单座位计时。
            </p>
            <p v-if="pendingDoubleSeatStart" class="mb-3 text-xs text-blue-800 font-semibold">
              已选第一座位：{{ pendingDoubleSeatStart.tableArea }}{{ pendingDoubleSeatStart.seatNo }}（等待左键选择第二座位）
            </p>
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
                      @contextmenu.prevent="handleSeatRightClick(table.area, seat.seatNo, seat.occupied)"
                      :class="[
                        'relative h-10 rounded-lg border flex items-center justify-center text-[12px] font-bold transition-colors',
                        pendingDoubleSeatStart && pendingDoubleSeatStart.tableArea === table.area && pendingDoubleSeatStart.seatNo === seat.seatNo
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
            <p class="mb-3 text-xs text-slate-600">
              右键选第一座位，左键选第二座位可快速创建双人套餐；直接左键可创建单座位计时。
            </p>
            <p v-if="pendingDoubleSeatStart" class="mb-3 text-xs text-blue-800 font-semibold">
              已选第一座位：{{ pendingDoubleSeatStart.tableArea }}{{ pendingDoubleSeatStart.seatNo }}（等待左键选择第二座位）
            </p>
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
                      @contextmenu.prevent="handleSeatRightClick(table.area, seat.seatNo, seat.occupied)"
                      :class="[
                        'relative h-10 rounded-lg border flex items-center justify-center text-[12px] font-bold transition-colors',
                        pendingDoubleSeatStart && pendingDoubleSeatStart.tableArea === table.area && pendingDoubleSeatStart.seatNo === seat.seatNo
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
            <p class="mb-3 text-xs text-slate-600">
              右键选第一座位，左键选第二座位可快速创建双人套餐；直接左键可创建单座位计时。
            </p>
            <p v-if="pendingDoubleSeatStart" class="mb-3 text-xs text-blue-800 font-semibold">
              已选第一座位：{{ pendingDoubleSeatStart.tableArea }}{{ pendingDoubleSeatStart.seatNo }}（等待左键选择第二座位）
            </p>
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
                    table.shape === 'square' ? 'max-w-[180px]' : table.shape === 'tall' ? 'max-w-[140px]' : 'max-w-[240px]'
                  ]"
                >
                  <div
                    class="grid gap-2"
                    :style="{ gridTemplateColumns: `repeat(${table.seatColumns || 3}, minmax(0, 1fr))` }"
                  >
                    <button
                      v-for="seat in table.seats"
                      :key="`garden-${table.area}-${seat.seatNo}`"
                      type="button"
                      @click="handleSeatLeftClick(table.area, seat.seatNo, seat.occupied)"
                      @contextmenu.prevent="handleSeatRightClick(table.area, seat.seatNo, seat.occupied)"
                      :class="[
                        'relative h-10 rounded-lg border flex items-center justify-center text-[12px] font-bold transition-colors',
                        pendingDoubleSeatStart && pendingDoubleSeatStart.tableArea === table.area && pendingDoubleSeatStart.seatNo === seat.seatNo
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
              <label class="block text-sm font-medium text-gray-700 mb-1">桌号</label>
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

            <div v-if="isDoublePackagePlan(editForm.packagePlan)">
              <label class="block text-sm font-medium text-gray-700 mb-1">第二座位（双人套餐）</label>
              <div class="grid grid-cols-2 gap-3">
                <select
                  v-model="editForm.secondTableArea"
                  :class="[
                    'w-full px-3 py-2 border rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent',
                    editErrors.secondTableNo ? 'border-red-500' : 'border-gray-300'
                  ]"
                >
                  <option v-for="area in tableAreaOptions" :key="`edit-second-area-${area}`" :value="area">
                    {{ area }}桌
                  </option>
                </select>
                <select
                  v-model="editForm.secondTableSeat"
                  :class="[
                    'w-full px-3 py-2 border rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent',
                    editErrors.secondTableNo ? 'border-red-500' : 'border-gray-300'
                  ]"
                >
                  <option v-for="seat in tableSeatOptions" :key="`edit-second-seat-${seat}`" :value="seat">
                    {{ seat }}号
                  </option>
                </select>
              </div>
              <p v-if="editErrors.secondTableNo" class="text-red-500 text-xs mt-1">{{ editErrors.secondTableNo }}</p>
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

