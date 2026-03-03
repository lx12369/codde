<script setup>
import { ref, reactive, computed, watch, onMounted, onUnmounted } from 'vue'
import api from '@/api'
import {
  normalizeBillingRules,
  calculateConsumptionAmount,
  buildConsumptionDescription,
  calculateMeituanDeduction,
  applyDeduction,
  getPackagePlanBaseFee
} from '@/utils/consumptionCalculator'

const timers = ref([])
const customers = ref([])
const billingRules = ref(normalizeBillingRules())

const loading = ref(false)
const submitting = ref(false)

const showAddModal = ref(false)
const showEditModal = ref(false)
const showSettleModal = ref(false)
const selectedTimer = ref(null)
const editingTimer = ref(null)

const nowTimestamp = ref(Date.now())
let ticker = null

const addForm = reactive({
  customerId: '',
  timerType: 'limited',
  packagePlan: 'limited1h',
  largeImages: 0,
  extraSmallImages: 0,
  extraLargeImages: 0,
  notes: ''
})

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
  useManualElapsed: false,
  manualElapsedMinutes: 0
})

const editForm = reactive({
  largeImages: 0,
  extraSmallImages: 0,
  extraLargeImages: 0
})

const addErrors = ref({})
const editErrors = ref({})
const settleErrors = ref({})

const customerMap = computed(() => {
  const map = new Map()
  customers.value.forEach((customer) => map.set(customer.id, customer))
  return map
})

const timerTypeOptions = [
  { value: 'limited', label: '限时套餐' },
  { value: 'weekday', label: '工作日套餐' },
  { value: 'weekend', label: '周末套餐' }
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

const addPackagePlanOptionsByType = {
  limited: [
    { value: 'limited1h', label: '限时1小时' },
    { value: 'limited2h', label: '限时2小时' }
  ],
  weekday: [
    { value: 'weekdaySingleUnlimited', label: '工作日单人不限时不限板' },
    { value: 'weekdayDoubleUnlimited', label: '工作日双人不限时不限板' },
    { value: 'weekdaySingleLimited', label: '工作日单人不限时限板' }
  ],
  weekend: [
    { value: 'weekendSingleUnlimited', label: '周末单人不限时不限板' },
    { value: 'weekendDoubleUnlimited', label: '周末双人不限时不限板' },
    { value: 'weekendSingleLimited', label: '周末单人不限时限板' }
  ]
}

const addPackagePlanOptions = computed(() => addPackagePlanOptionsByType[addForm.timerType] || [])

function getDefaultAddPackagePlan(timerType = 'limited') {
  const options = addPackagePlanOptionsByType[timerType] || addPackagePlanOptionsByType.limited
  return options[0]?.value || 'limited1h'
}

const settleElapsedMinutes = computed(() => {
  if (settleForm.useManualElapsed) {
    const minutes = Number(settleForm.manualElapsedMinutes)
    if (!Number.isFinite(minutes) || minutes < 0) return 0
    return Math.floor(minutes)
  }

  return getElapsedMinutes(selectedTimer.value)
})

const settlePreview = computed(() =>
  calculateConsumptionAmount(
    {
      pricingMode: 'timer',
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
      additionalFee: settleForm.additionalFee
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
    ? calculateMeituanDeduction(settleStartPackageBaseFee.value)
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

  if (packagePlan === 'limited2h') {
    const elapsedMinutesFor2h = Math.max(0, Math.floor(Number(settleElapsedMinutes.value) || 0))
    settleForm.billingType = 'limited'
    settleForm.duration = '2'
    settleForm.overtimeMinutes = Math.max(0, elapsedMinutesFor2h - 120)
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
      meituanCustomer: false,
      meituanPackageBaseFee: 0,
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
        meituanCustomer: Boolean(parsed.meituanCustomer),
        meituanPackageBaseFee: Number(parsed.meituanPackageBaseFee) || 0,
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
    meituanCustomer: false,
    meituanPackageBaseFee: 0,
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

  return {
    id: timer.id,
    customerId,
    customerName: timer.customer?.name || customerMap.value.get(customerId)?.name || '',
    status: timer.status || 'active',
    timerType: timer.timerType ?? timer.timer_type ?? 'limited',
    startTime: timer.startTime ?? timer.start_time ?? null,
    notes: parsedNotes.note,
    packagePlan: parsedNotes.packagePlan || '',
    meituanCustomer: Boolean(parsedNotes.meituanCustomer),
    meituanPackageBaseFee: Number(parsedNotes.meituanPackageBaseFee) || 0,
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
    meituanCustomer: Boolean(timer?.meituanCustomer),
    meituanPackageBaseFee: Number(timer?.meituanPackageBaseFee) || 0,
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
  if (!timer?.startTime) return 0
  const startMs = toServerDateTimestamp(timer.startTime)
  if (!Number.isFinite(startMs)) return 0
  return Math.floor(Math.max(0, timestamp - startMs) / 1000)
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
  } finally {
    loading.value = false
  }
}

function resetAddForm() {
  addForm.customerId = ''
  addForm.timerType = 'limited'
  addForm.packagePlan = getDefaultAddPackagePlan('limited')
  addForm.largeImages = 0
  addForm.extraSmallImages = 0
  addForm.extraLargeImages = 0
  addForm.notes = ''
  addErrors.value = {}
}

function resetEditForm(timer = null) {
  editForm.largeImages = Number(timer?.materials?.largeImages) || 0
  editForm.extraSmallImages = Number(timer?.materials?.extraSmallImages) || 0
  editForm.extraLargeImages = Number(timer?.materials?.extraLargeImages) || 0
  editErrors.value = {}
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
  settleForm.meituanCustomer = false
  settleForm.useManualElapsed = false
  settleForm.manualElapsedMinutes = getElapsedMinutes(timer)

  settleErrors.value = {}
}

function openAddModal() {
  resetAddForm()
  showAddModal.value = true
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
  const errors = {}

  if (!addForm.customerId) {
    errors.customerId = '请选择客户'
  }

  if (!addForm.timerType) {
    errors.timerType = '请选择计时类型'
  }

  if (!addForm.packagePlan) {
    errors.packagePlan = '请选择套餐方案'
  }

  addErrors.value = errors
  return Object.keys(errors).length === 0
}

function validateEditForm() {
  const errors = {}

  const largeImages = toNonNegativeInteger(editForm.largeImages)
  const extraSmallImages = toNonNegativeInteger(editForm.extraSmallImages)
  const extraLargeImages = toNonNegativeInteger(editForm.extraLargeImages)

  if (largeImages === null) errors.largeImages = '大图数量必须大于或等于 0'
  if (extraSmallImages === null) errors.extraSmallImages = '超量小图必须大于或等于 0'
  if (extraLargeImages === null) errors.extraLargeImages = '超量大图必须大于或等于 0'

  editErrors.value = errors

  if (Object.keys(errors).length > 0) return null

  return {
    largeImages,
    extraSmallImages,
    extraLargeImages
  }
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
    const notesPayload = JSON.stringify({
      note: addForm.notes || '',
      packagePlan: addForm.packagePlan || getDefaultAddPackagePlan(addForm.timerType),
      materials: {
        largeImages: Number(addForm.largeImages) || 0,
        extraSmallImages: Number(addForm.extraSmallImages) || 0,
        extraLargeImages: Number(addForm.extraLargeImages) || 0
      }
    })

    await api.post('/active-timers', {
      customer_id: addForm.customerId,
      timer_type: addForm.timerType,
      notes: notesPayload
    })

    showAddModal.value = false
    await fetchTimers()
  } catch (error) {
    console.error('开始计时失败:', error)
    alert(error?.response?.data?.message || error?.message || '开始计时失败')
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
    const notesPayload = buildTimerNotesPayload(editingTimer.value, materials)

    await api.put(`/active-timers/${editingTimer.value.id}`, {
      notes: notesPayload
    })

    closeEditModal()
    await fetchTimers()
  } catch (error) {
    console.error('更新素材参数失败:', error)
    alert(error?.response?.data?.message || error?.message || '更新素材参数失败')
  } finally {
    submitting.value = false
  }
}

async function submitSettlement() {
  if (!validateSettleForm()) return

  submitting.value = true
  try {
    const settleNotes = settleForm.meituanCustomer
      ? `${settleForm.notes || ''}${settleForm.notes ? '；' : ''}美团客户(按开始套餐抽成¥${formatAmount(settleMeituanDeduction.value)})`
      : settleForm.notes

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
      notes: settleForm.notes
    })

    closeSettleModal()
    await fetchTimers()
  } catch (error) {
    console.error('结算失败:', error)
    alert(error?.response?.data?.message || error?.message || '结算失败')
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
  } catch (error) {
    console.error('结束计时失败:', error)
    alert(error?.response?.data?.message || error?.message || '结束计时失败')
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
  () => addForm.timerType,
  (nextType) => {
    addForm.packagePlan = getDefaultAddPackagePlan(nextType)
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
onMounted(async () => {
  await Promise.all([fetchCustomers(), fetchBillingRules()])
  await fetchTimers()
  startTicker()
})

onUnmounted(() => {
  stopTicker()
})
</script>

<template>
  <div class="space-y-6">
    <div class="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
      <div>
        <h1 class="text-2xl font-bold text-gray-800">计时消费</h1>
        <p class="text-gray-500 mt-1">管理进行中的计时消费记录</p>
      </div>
      <button
        @click="openAddModal"
        class="inline-flex items-center px-4 py-2 bg-[#1e40af] text-white rounded-lg hover:bg-[#1e3a8a] transition-colors"
      >
        <svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5 mr-2" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4v16m8-8H4" />
        </svg>
        新增消费
      </button>
    </div>

    <div v-if="loading && timers.length === 0" class="bg-white rounded-lg shadow-sm p-12 text-center text-gray-500">
      正在加载计时记录...
    </div>

    <div v-else-if="timers.length === 0" class="bg-white rounded-lg shadow-sm p-12 text-center">
      <p class="text-gray-500 mb-4">暂无进行中的计时记录。</p>
      <button
        @click="openAddModal"
        class="inline-flex items-center px-4 py-2 bg-[#1e40af] text-white rounded-lg hover:bg-[#1e3a8a] transition-colors"
      >
        开始计时
      </button>
    </div>

    <div v-else class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
      <div
        v-for="timer in timers"
        :key="timer.id"
        class="bg-white rounded-lg shadow-sm border border-gray-100 overflow-hidden h-full flex flex-col"
      >
        <div class="px-4 py-3 border-b border-gray-100 flex items-center justify-between">
          <div>
            <p class="font-medium text-gray-900">{{ timer.customerName || `客户 #${timer.customerId}` }}</p>
            <p class="text-xs text-gray-500">{{ timer.customerId }}</p>
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
          <p><span class="text-gray-500">开始时间：</span> {{ formatDateTime(timer.startTime) }}</p>
          <p v-if="timer.packagePlan"><span class="text-gray-500">套餐方案：</span> {{ getPackagePlanLabel(timer.packagePlan) }}</p>
          <p><span class="text-gray-500">大图数量：</span> {{ timer.materials.largeImages || 0 }}</p>
          <p><span class="text-gray-500">超量小图：</span> {{ timer.materials.extraSmallImages || 0 }}</p>
          <p><span class="text-gray-500">超量大图：</span> {{ timer.materials.extraLargeImages || 0 }}</p>
          <p v-if="timer.notes"><span class="text-gray-500">备注：</span> {{ timer.notes }}</p>
        </div>

        <div class="px-4 py-3 bg-gray-50 border-t border-gray-100 flex justify-end gap-2 mt-auto">
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

    <div
      v-if="showAddModal"
      class="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50"
      @click.self="showAddModal = false"
    >
      <div class="bg-white rounded-xl shadow-xl w-full max-w-lg mx-4">
        <div class="px-6 py-4 border-b border-gray-200">
          <h3 class="text-lg font-semibold text-gray-800">开始计时</h3>
        </div>

        <div class="p-6 space-y-4">
          <div>
            <label class="block text-sm font-medium text-gray-700 mb-1">客户</label>
            <select
              v-model="addForm.customerId"
              :class="[
                'w-full px-3 py-2 border rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent',
                addErrors.customerId ? 'border-red-500' : 'border-gray-300'
              ]"
            >
              <option disabled value="">请选择客户</option>
              <option v-for="customer in customers" :key="customer.id" :value="customer.id">
                {{ customer.name }} ({{ customer.phone }})
              </option>
            </select>
            <p v-if="addErrors.customerId" class="text-red-500 text-xs mt-1">{{ addErrors.customerId }}</p>
          </div>

          <div>
            <label class="block text-sm font-medium text-gray-700 mb-1">计时类型</label>
            <select
              v-model="addForm.timerType"
              :class="[
                'w-full px-3 py-2 border rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent',
                addErrors.timerType ? 'border-red-500' : 'border-gray-300'
              ]"
            >
              <option v-for="item in timerTypeOptions" :key="item.value" :value="item.value">
                {{ item.label }}
              </option>
            </select>
            <p v-if="addErrors.timerType" class="text-red-500 text-xs mt-1">{{ addErrors.timerType }}</p>
          </div>

          <div>
            <label class="block text-sm font-medium text-gray-700 mb-1">套餐方案</label>
            <select
              v-model="addForm.packagePlan"
              :class="[
                'w-full px-3 py-2 border rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent',
                addErrors.packagePlan ? 'border-red-500' : 'border-gray-300'
              ]"
            >
              <option v-for="item in addPackagePlanOptions" :key="item.value" :value="item.value">
                {{ item.label }}
              </option>
            </select>
            <p v-if="addErrors.packagePlan" class="text-red-500 text-xs mt-1">{{ addErrors.packagePlan }}</p>
          </div>

          <div class="grid grid-cols-1 md:grid-cols-3 gap-3">
            <div>
              <label class="block text-sm font-medium text-gray-700 mb-1">大图数量</label>
              <input v-model.number="addForm.largeImages" type="number" min="0" class="w-full px-3 py-2 border border-gray-300 rounded-lg" />
            </div>
            <div>
              <label class="block text-sm font-medium text-gray-700 mb-1">超量小图</label>
              <input v-model.number="addForm.extraSmallImages" type="number" min="0" class="w-full px-3 py-2 border border-gray-300 rounded-lg" />
            </div>
            <div>
              <label class="block text-sm font-medium text-gray-700 mb-1">超量大图</label>
              <input v-model.number="addForm.extraLargeImages" type="number" min="0" class="w-full px-3 py-2 border border-gray-300 rounded-lg" />
            </div>
          </div>

          <div>
            <label class="block text-sm font-medium text-gray-700 mb-1">备注</label>
            <textarea v-model="addForm.notes" rows="2" class="w-full px-3 py-2 border border-gray-300 rounded-lg resize-none"></textarea>
          </div>
        </div>

        <div class="px-6 py-4 border-t border-gray-200 flex justify-end gap-3">
          <button @click="showAddModal = false" class="px-4 py-2 border border-gray-300 rounded-lg text-gray-700 hover:bg-gray-50">取消</button>
          <button @click="startTimer" :disabled="submitting" class="px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 disabled:opacity-50">
            开始计时
          </button>
        </div>
      </div>
    </div>

    <div
      v-if="showEditModal && editingTimer"
      class="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50"
      @click.self="closeEditModal"
    >
      <div class="bg-white rounded-xl shadow-xl w-full max-w-lg mx-4">
        <div class="px-6 py-4 border-b border-gray-200">
          <h3 class="text-lg font-semibold text-gray-800">编辑素材参数</h3>
          <p class="text-xs text-gray-500 mt-1">{{ editingTimer.customerName || editingTimer.customerId }}</p>
        </div>

        <div class="p-6 space-y-4">
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

    <div
      v-if="showSettleModal && selectedTimer"
      class="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50"
      @click.self="closeSettleModal"
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

          <div>
            <label class="block text-sm font-medium text-gray-700 mb-1">备注</label>
            <textarea v-model="settleForm.notes" rows="2" class="w-full px-3 py-2 border border-gray-300 rounded-lg resize-none"></textarea>
          </div>

          <label class="inline-flex items-center gap-2 text-sm text-gray-700">
            <input
              v-model="settleForm.meituanCustomer"
              type="checkbox"
              class="h-4 w-4 rounded border-gray-300 text-blue-600 focus:ring-blue-500"
            >
            美团客户（按开始套餐抽成7%）
          </label>

          <div class="bg-green-50 border border-green-200 rounded-lg p-4 text-sm text-green-800 space-y-1">
            <p>应用计费：{{ getTimerTypeLabel(settlePreview.billingType) }}</p>
            <p>基础费用：¥{{ formatAmount(settlePreview.baseFee) }}</p>
            <p>超时费用：¥{{ formatAmount(settlePreview.overtimeFee) }}</p>
            <p>素材费用：¥{{ formatAmount(settlePreview.materialFee) }}</p>
            <p>附加费用：¥{{ formatAmount(settlePreview.additionalFee) }}</p>
            <p class="font-medium">额外消费：¥{{ formatAmount(settleExtraConsumption) }}</p>
            <p v-if="settlePackageUpgradeFee > 0" class="text-xs text-green-700">
              已含自动变更套餐差额：¥{{ formatAmount(settlePackageUpgradeFee) }}
            </p>
            <p v-if="settleForm.meituanCustomer">美团抽成（按开始套餐）：-¥{{ formatAmount(settleMeituanDeduction) }}</p>
            <p class="font-semibold text-base">
              结算金额：¥{{ formatAmount(settleForm.meituanCustomer ? settleFinalAmount : settlePreview.total) }}
            </p>
            <p v-if="settlePreview.details?.length" class="text-xs text-green-700">{{ settlePreview.details.join(' | ') }}</p>
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
  </div>
</template>

<style scoped>
</style>













