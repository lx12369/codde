<script setup>
import { ref, reactive, computed, onMounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import api from '@/api'
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

const loading = ref(false)
const cancellingTransactionId = ref('')
const transactions = ref([])
const customers = ref([])
const activities = ref([])
const total = ref(0)
const currentPage = ref(1)
const pageSize = ref(10)

const filterForm = reactive({
  type: '',
  startDate: '',
  endDate: '',
  customerKeyword: ''
})

const showRechargeDialog = ref(false)
const showConsumeDialog = ref(false)
const showDetailDialog = ref(false)
const selectedTransaction = ref(null)

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
  additionalFee: 0,
  notes: '',
  meituanCustomer: false
})

const timerConsumeForm = reactive({
  customerId: '',
  timerType: 'limited',
  packagePlan: 'limited1h',
  largeImages: 0,
  extraSmallImages: 0,
  extraLargeImages: 0,
  notes: ''
})

const rechargeErrors = ref({})
const manualConsumeErrors = ref({})
const autoConsumeErrors = ref({})
const timerConsumeErrors = ref({})

const consumeCurrentBalance = ref(null)
const consumeBalanceLoading = ref(false)
const billingRules = ref(normalizeBillingRules())

const transactionTypes = [
  { value: '', label: '全部' },
  { value: 'recharge', label: '充值' },
  { value: 'consumption', label: '消费' }
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

const timerTypeOptions = [
  { value: 'limited', label: '限时套餐' },
  { value: 'weekday', label: '工作日套餐' },
  { value: 'weekend', label: '周末套餐' }
]

const timerPackagePlanOptionsByType = {
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

const timerPackagePlanOptions = computed(() => timerPackagePlanOptionsByType[timerConsumeForm.timerType] || [])

function getDefaultTimerPackagePlan(timerType = 'limited') {
  const options = timerPackagePlanOptionsByType[timerType] || timerPackagePlanOptionsByType.limited
  return options[0]?.value || 'limited1h'
}

const totalPages = computed(() => Math.ceil(total.value / pageSize.value) || 1)

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
      additionalFee: autoConsumeForm.additionalFee
    },
    billingRules.value
  )
)

const manualInputAmount = computed(() => {
  const value = Number.parseFloat(manualConsumeForm.amount)
  return Number.isFinite(value) ? Math.max(0, value) : 0
})

const manualMeituanDeduction = computed(() => (
  manualConsumeForm.meituanCustomer
    ? calculateMeituanDeduction(manualInputAmount.value)
    : 0
))

const manualFinalAmount = computed(() =>
  applyDeduction(manualInputAmount.value, manualMeituanDeduction.value)
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
  bonusAmount: transaction.bonusAmount ?? transaction.bonus_amount ?? 0,
  paymentMethod: transaction.paymentMethod ?? transaction.payment_method ?? '',
  activityId: transaction.activityId ?? transaction.activity_id ?? null,
  createdAt: transaction.createdAt ?? transaction.created_at ?? transaction.transaction_time ?? null,
  status: transaction.status ?? 'completed'
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
  } catch (error) {
    console.error('Failed to fetch billing rules:', error)
    billingRules.value = normalizeBillingRules()
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
  autoConsumeForm.additionalFee = 0
  autoConsumeForm.notes = ''
  autoConsumeForm.meituanCustomer = false

  timerConsumeForm.customerId = customerId
  timerConsumeForm.timerType = 'limited'
  timerConsumeForm.packagePlan = getDefaultTimerPackagePlan('limited')
  timerConsumeForm.largeImages = 0
  timerConsumeForm.extraSmallImages = 0
  timerConsumeForm.extraLargeImages = 0
  timerConsumeForm.notes = ''

  manualConsumeErrors.value = {}
  autoConsumeErrors.value = {}
  timerConsumeErrors.value = {}
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

function handleExport() {
  console.log('Export transactions')
}

async function handlePageChange(page) {
  if (page < 1 || page > totalPages.value) return
  currentPage.value = page
  await fetchTransactions()
}

async function openRechargeDialog(customerId = '') {
  rechargeForm.customerId = await refreshCustomersAndResolveCustomerId(customerId)
  rechargeForm.amount = ''
  rechargeForm.bonusAmount = ''
  rechargeForm.paymentMethod = 'cash'
  rechargeForm.activityId = ''
  rechargeErrors.value = {}
  showRechargeDialog.value = true
}

async function openConsumeDialog(customerId = '') {
  const validCustomerId = await refreshCustomersAndResolveCustomerId(customerId)
  resetConsumeForms(validCustomerId)
  showConsumeDialog.value = true
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
  if (!manualConsumeForm.amount || parseFloat(manualConsumeForm.amount) <= 0) {
    errors.amount = '请输入有效金额'
  }
  if (!manualConsumeForm.description?.trim()) {
    errors.description = '请输入消费描述'
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
  }

  timerConsumeErrors.value = errors
  return Object.keys(errors).length === 0
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
    await Promise.all([fetchTransactions(), fetchCustomers()])
  } catch (error) {
    console.error('Failed to create recharge:', error)
    alert(error?.response?.data?.message || error?.message || '创建充值记录失败')
  } finally {
    loading.value = false
  }
}

async function submitManualConsume() {
  if (!validateManualConsumeForm()) return

  const amount = manualFinalAmount.value

  const currentBalance = await fetchCustomerBalance(manualConsumeForm.customerId)
  if (currentBalance !== null && amount > currentBalance) {
    manualConsumeErrors.value = {
      ...manualConsumeErrors.value,
      amount: '余额不足'
    }
    alert('客户余额不足')
    return
  }

  const description = manualConsumeForm.meituanCustomer
    ? `${manualConsumeForm.description} - 美团客户(抽成¥${formatAmount(manualMeituanDeduction.value)})`
    : manualConsumeForm.description

  await api.post('/transactions/consumption', {
    customer_id: manualConsumeForm.customerId,
    amount,
    description
  })
}

async function submitAutoConsume() {
  if (!validateAutoConsumeForm()) return

  const amount = autoFinalAmount.value
  const currentBalance = await fetchCustomerBalance(autoConsumeForm.customerId)
  if (currentBalance !== null && amount > currentBalance) {
    autoConsumeErrors.value = {
      ...autoConsumeErrors.value,
      total: '余额不足，无法结算'
    }
    alert('客户余额不足')
    return
  }

  const description = buildConsumptionDescription(
    {
      mode: 'auto',
      billingType: autoConsumeForm.billingType
    },
    autoConsumePreview.value,
    autoConsumeForm.meituanCustomer
      ? `${autoConsumeForm.notes || ''}${autoConsumeForm.notes ? '；' : ''}美团客户(基础费用抽成¥${formatAmount(autoMeituanDeduction.value)})`
      : autoConsumeForm.notes
  )

  await api.post('/transactions/consumption', {
    customer_id: autoConsumeForm.customerId,
    amount,
    description
  })
}

async function submitTimerConsume() {
  if (!validateTimerConsumeForm()) return

  const notesPayload = JSON.stringify({
    note: timerConsumeForm.notes || '',
    packagePlan: timerConsumeForm.packagePlan || getDefaultTimerPackagePlan(timerConsumeForm.timerType),
    materials: {
      largeImages: Number(timerConsumeForm.largeImages) || 0,
      extraSmallImages: Number(timerConsumeForm.extraSmallImages) || 0,
      extraLargeImages: Number(timerConsumeForm.extraLargeImages) || 0
    }
  })

  await api.post('/active-timers', {
    customer_id: timerConsumeForm.customerId,
    timer_type: timerConsumeForm.timerType,
    notes: notesPayload
  })

  alert('计时消费已开始，请到“正在计时”页面完成结算')
}

async function submitConsumeByMode() {
  loading.value = true
  try {
    if (consumeMode.value === 'manual') {
      await submitManualConsume()
    } else if (consumeMode.value === 'auto') {
      await submitAutoConsume()
    } else {
      await submitTimerConsume()
    }

    showConsumeDialog.value = false
    await Promise.all([fetchTransactions(), fetchCustomers()])
  } catch (error) {
    console.error('Failed to handle consume action:', error)
    alert(error?.response?.data?.message || error?.message || '消费操作失败')
  } finally {
    loading.value = false
    await syncConsumeBalance(activeConsumeCustomerId.value)
  }
}

function viewTransactionDetail(transaction) {
  selectedTransaction.value = normalizeTransaction(transaction)
  showDetailDialog.value = true
}

function isCancellingTransaction(transactionId = '') {
  return cancellingTransactionId.value === transactionId
}

async function cancelTransaction(transaction) {
  const normalized = normalizeTransaction(transaction)
  if (!normalized?.id) return

  const confirmed = window.confirm(
    `确认取消该笔${getTransactionTypeLabel(normalized.type)}记录？\n` +
    `交易ID：#${normalized.id}\n` +
    `金额：¥${formatAmount(normalized.amount)}\n` +
    '取消后会自动回滚客户余额。'
  )
  if (!confirmed) return

  cancellingTransactionId.value = normalized.id
  try {
    await api.post(`/transactions/${normalized.id}/cancel`)
    if (selectedTransaction.value?.id === normalized.id) {
      showDetailDialog.value = false
      selectedTransaction.value = null
    }
    await Promise.all([fetchTransactions(), fetchCustomers()])
  } catch (error) {
    console.error('Failed to cancel transaction:', error)
    alert(error?.response?.data?.message || error?.message || '取消交易失败')
  } finally {
    cancellingTransactionId.value = ''
  }
}

function getTransactionTypeLabel(type) {
  const typeMap = {
    recharge: '充值',
    consumption: '消费'
  }
  return typeMap[type] || type || '-'
}

function getTransactionTypeClass(type) {
  const classMap = {
    recharge: 'bg-green-100 text-green-800',
    consumption: 'bg-orange-100 text-orange-800'
  }
  return classMap[type] || 'bg-gray-100 text-gray-800'
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
  if (!dateTime) return '-'
  return new Date(dateTime).toLocaleString('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit'
  })
}

function getCustomerName(transaction) {
  const customerId = transaction.customerId || transaction.customer_id
  return (
    transaction.customer?.name ||
    transaction.customerName ||
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

function clearRouteActionQuery() {
  const query = { ...route.query }
  delete query.action
  delete query.customerId
  router.replace({ query })
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
  () => timerConsumeForm.timerType,
  (nextType) => {
    timerConsumeForm.packagePlan = getDefaultTimerPackagePlan(nextType)
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
  await Promise.all([fetchCustomers(), fetchActivities(), fetchBillingRules()])
  await fetchTransactions()
})
</script>

<template>
  <div class="space-y-6">
    <div class="flex items-center justify-between">
      <div>
        <h1 class="text-2xl font-bold text-gray-800">交易记录</h1>
        <p class="text-gray-500 mt-1">查看所有交易记录</p>
      </div>
      <div class="flex space-x-3">
        <button
          @click="openRechargeDialog"
          class="px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 transition-colors flex items-center space-x-2"
        >
          <svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 6v6m0 0v6m0-6h6m-6 0H6" />
          </svg>
          <span>充值</span>
        </button>
        <button
          @click="openConsumeDialog"
          class="px-4 py-2 bg-orange-600 text-white rounded-lg hover:bg-orange-700 transition-colors flex items-center space-x-2"
        >
          <svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M20 12H4" />
          </svg>
          <span>消费</span>
        </button>
      </div>
    </div>

    <div class="bg-white rounded-xl shadow-sm p-6">
      <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-5 gap-4">
        <div>
          <label class="block text-sm font-medium text-gray-700 mb-1">交易类型</label>
          <select
            v-model="filterForm.type"
            class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
          >
            <option v-for="type in transactionTypes" :key="type.value" :value="type.value">
              {{ type.label }}
            </option>
          </select>
        </div>

        <div>
          <label class="block text-sm font-medium text-gray-700 mb-1">开始日期</label>
          <input
            v-model="filterForm.startDate"
            type="date"
            class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
          />
        </div>

        <div>
          <label class="block text-sm font-medium text-gray-700 mb-1">结束日期</label>
          <input
            v-model="filterForm.endDate"
            type="date"
            class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
          />
        </div>

        <div>
          <label class="block text-sm font-medium text-gray-700 mb-1">客户搜索</label>
          <input
            v-model="filterForm.customerKeyword"
            type="text"
            placeholder="姓名或电话"
            class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
          />
        </div>

        <div class="flex items-end space-x-2">
          <button
            @click="handleFilter"
            class="flex-1 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors"
          >
            筛选
          </button>
          <button
            @click="handleReset"
            class="px-4 py-2 border border-gray-300 text-gray-700 rounded-lg hover:bg-gray-50 transition-colors"
          >
            重置
          </button>
          <button
            @click="handleExport"
            class="px-4 py-2 border border-gray-300 text-gray-700 rounded-lg hover:bg-gray-50 transition-colors"
            title="导出"
          >
            <svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
            </svg>
          </button>
        </div>
      </div>
    </div>

    <div class="bg-white rounded-xl shadow-sm overflow-hidden">
      <div class="overflow-x-auto">
        <table class="min-w-full divide-y divide-gray-200">
          <thead class="bg-gray-50">
            <tr>
              <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">交易ID</th>
              <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">客户</th>
              <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">金额</th>
              <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">赠送</th>
              <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">支付方式/描述</th>
              <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">时间</th>
              <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">状态</th>
              <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">操作员</th>
              <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">操作</th>
            </tr>
          </thead>
          <tbody class="bg-white divide-y divide-gray-200">
            <tr v-if="loading">
              <td colspan="9" class="px-6 py-12 text-center">
                <div class="flex items-center justify-center">
                  <svg class="animate-spin h-8 w-8 text-blue-600" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                    <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
                    <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                  </svg>
                </div>
              </td>
            </tr>
            <tr v-else-if="transactions.length === 0">
              <td colspan="9" class="px-6 py-12 text-center text-gray-500">
                暂无交易记录
              </td>
            </tr>
            <tr v-else v-for="transaction in transactions" :key="transaction.id" class="hover:bg-gray-50">
              <td class="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-900">
                #{{ transaction.id }}
              </td>
              <td class="px-6 py-4 whitespace-nowrap">
                <div class="text-sm font-medium text-gray-900">{{ getCustomerName(transaction) }}</div>
                <div class="text-sm text-gray-500">{{ getCustomerPhone(transaction) }}</div>
              </td>
              <td class="px-6 py-4 whitespace-nowrap">
                <span
                  :class="[
                    'text-sm font-medium',
                    transaction.type === 'recharge' ? 'text-green-600' : 'text-orange-600'
                  ]"
                >
                  {{ transaction.type === 'recharge' ? '+' : '-' }}¥{{ formatAmount(transaction.amount) }}
                </span>
              </td>
              <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                <span v-if="transaction.bonusAmount > 0" class="text-green-600">
                  +¥{{ formatAmount(transaction.bonusAmount) }}
                </span>
                <span v-else>-</span>
              </td>
              <td class="px-6 py-4">
                <div v-if="transaction.type === 'recharge'" class="text-sm text-gray-900">
                  {{ paymentMethods.find(p => p.value === transaction.paymentMethod)?.label || transaction.paymentMethod }}
                </div>
                <div v-else class="text-sm text-gray-500 max-w-xs truncate">
                  {{ transaction.description || '-' }}
                </div>
              </td>
              <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                {{ formatDateTime(transaction.createdAt) }}
              </td>
              <td class="px-6 py-4 whitespace-nowrap">
                <span
                  :class="[
                    'px-2 py-1 text-xs font-medium rounded-full',
                    getStatusClass(transaction.status)
                  ]"
                >
                  {{ getStatusLabel(transaction.status) }}
                </span>
              </td>
              <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                {{ transaction.operator?.name || transaction.operatorName || '-' }}
              </td>
              <td class="px-6 py-4 whitespace-nowrap text-sm">
                <div class="flex items-center gap-3">
                  <button
                    @click="viewTransactionDetail(transaction)"
                    class="text-blue-600 hover:text-blue-800 transition-colors"
                  >
                    查看详情
                  </button>
                  <button
                    @click="cancelTransaction(transaction)"
                    :disabled="isCancellingTransaction(transaction.id)"
                    class="text-red-600 hover:text-red-800 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                  >
                    {{ isCancellingTransaction(transaction.id) ? '取消中...' : '取消' }}
                  </button>
                </div>
              </td>
            </tr>
          </tbody>
        </table>
      </div>

      <div v-if="total > 0" class="bg-white px-6 py-4 border-t border-gray-200 flex items-center justify-between">
        <div class="text-sm text-gray-500">
          显示 {{ (currentPage - 1) * pageSize + 1 }} 到 {{ Math.min(currentPage * pageSize, total) }} 条，共 {{ total }} 条记录
        </div>
        <div class="flex items-center space-x-2">
          <button
            @click="handlePageChange(currentPage - 1)"
            :disabled="currentPage === 1"
            :class="[
              'px-3 py-1 rounded-lg transition-colors',
              currentPage === 1
                ? 'bg-gray-100 text-gray-400 cursor-not-allowed'
                : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
            ]"
          >
            上一页
          </button>
          <template v-for="page in totalPages" :key="page">
            <button
              v-if="page === 1 || page === totalPages || Math.abs(page - currentPage) <= 2"
              @click="handlePageChange(page)"
              :class="[
                'px-3 py-1 rounded-lg transition-colors',
                currentPage === page
                  ? 'bg-blue-600 text-white'
                  : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
              ]"
            >
              {{ page }}
            </button>
            <span v-else-if="Math.abs(page - currentPage) === 3" class="px-2 text-gray-400">...</span>
          </template>
          <button
            @click="handlePageChange(currentPage + 1)"
            :disabled="currentPage === totalPages"
            :class="[
              'px-3 py-1 rounded-lg transition-colors',
              currentPage === totalPages
                ? 'bg-gray-100 text-gray-400 cursor-not-allowed'
                : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
            ]"
          >
            Next
          </button>
        </div>
      </div>
    </div>

    <div
      v-if="showRechargeDialog"
      class="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50"
      @click.self="showRechargeDialog = false"
    >
      <div class="bg-white rounded-xl shadow-xl w-full max-w-md mx-4">
        <div class="px-6 py-4 border-b border-gray-200 flex items-center justify-between">
          <h3 class="text-lg font-semibold text-gray-800">新增充值</h3>
          <button
            @click="showRechargeDialog = false"
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
              <span class="absolute left-3 top-1/2 -translate-y-1/2 text-gray-500">¥</span>
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
              <span class="absolute left-3 top-1/2 -translate-y-1/2 text-gray-500">¥</span>
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
                {{ activity.name }}（每满¥{{ formatAmount(activity.minRechargeAmount) }}送¥{{ formatAmount(activity.bonusAmount) }}）
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

    <div
      v-if="showConsumeDialog"
      class="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50"
      @click.self="showConsumeDialog = false"
    >
      <div class="bg-white rounded-xl shadow-xl w-full max-w-3xl mx-4 max-h-[90vh] overflow-y-auto">
        <div class="px-6 py-4 border-b border-gray-200 flex items-center justify-between">
          <h3 class="text-lg font-semibold text-gray-800">新增消费</h3>
          <button
            @click="showConsumeDialog = false"
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
              当前客户余额: <strong>¥{{ formatAmount(consumeCurrentBalance) }}</strong>
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
                <span class="absolute left-3 top-1/2 -translate-y-1/2 text-gray-500">¥</span>
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

            <label class="inline-flex items-center gap-2 text-sm text-gray-700">
              <input
                v-model="manualConsumeForm.meituanCustomer"
                type="checkbox"
                class="h-4 w-4 rounded border-gray-300 text-blue-600 focus:ring-blue-500"
              >
              美团客户（消费金额抽成7%）
            </label>

            <div v-if="manualConsumeForm.meituanCustomer" class="bg-amber-50 border border-amber-200 rounded-lg p-3 text-sm text-amber-800 space-y-1">
              <p>原始金额：¥{{ formatAmount(manualInputAmount) }}</p>
              <p>美团抽成：-¥{{ formatAmount(manualMeituanDeduction) }}</p>
              <p class="font-semibold">结算金额：¥{{ formatAmount(manualFinalAmount) }}</p>
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
              <p>基础费用: ¥{{ formatAmount(autoConsumePreview.baseFee) }}</p>
              <p>超时费用: ¥{{ formatAmount(autoConsumePreview.overtimeFee) }}</p>
              <p>耗材费用: ¥{{ formatAmount(autoConsumePreview.materialFee) }}</p>
              <p>附加费用: ¥{{ formatAmount(autoConsumePreview.additionalFee) }}</p>
              <p v-if="autoConsumeForm.meituanCustomer">美团抽成: -¥{{ formatAmount(autoMeituanDeduction) }}</p>
              <p class="font-semibold text-base">
                结算金额: ¥{{ formatAmount(autoConsumeForm.meituanCustomer ? autoFinalAmount : autoConsumePreview.total) }}
              </p>
            </div>
            <p v-if="autoConsumeErrors.total" class="text-red-500 text-xs mt-1">
              {{ autoConsumeErrors.total }}
            </p>
          </div>

          <div v-else class="space-y-4">
            <div>
              <label class="block text-sm font-medium text-gray-700 mb-1">选择客户</label>
              <select
                v-model="timerConsumeForm.customerId"
                :class="[
                  'w-full px-3 py-2 border rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent',
                  timerConsumeErrors.customerId ? 'border-red-500' : 'border-gray-300'
                ]"
              >
                <option disabled value="">请选择客户</option>
                <option v-for="customer in validCustomers" :key="customer.id" :value="customer.id">
                  {{ customer.name }} ({{ customer.phone }})
                </option>
              </select>
              <p v-if="timerConsumeErrors.customerId" class="text-red-500 text-xs mt-1">
                {{ timerConsumeErrors.customerId }}
              </p>
            </div>

            <div>
              <label class="block text-sm font-medium text-gray-700 mb-1">计时类型</label>
              <select
                v-model="timerConsumeForm.timerType"
                :class="[
                  'w-full px-3 py-2 border rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent',
                  timerConsumeErrors.timerType ? 'border-red-500' : 'border-gray-300'
                ]"
              >
                <option v-for="item in timerTypeOptions" :key="item.value" :value="item.value">
                  {{ item.label }}
                </option>
              </select>
              <p v-if="timerConsumeErrors.timerType" class="text-red-500 text-xs mt-1">
                {{ timerConsumeErrors.timerType }}
              </p>
            </div>

            <div>
              <label class="block text-sm font-medium text-gray-700 mb-1">套餐方案</label>
              <select
                v-model="timerConsumeForm.packagePlan"
                :class="[
                  'w-full px-3 py-2 border rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent',
                  timerConsumeErrors.packagePlan ? 'border-red-500' : 'border-gray-300'
                ]"
              >
                <option v-for="item in timerPackagePlanOptions" :key="item.value" :value="item.value">
                  {{ item.label }}
                </option>
              </select>
              <p v-if="timerConsumeErrors.packagePlan" class="text-red-500 text-xs mt-1">
                {{ timerConsumeErrors.packagePlan }}
              </p>
            </div>

            <div class="grid grid-cols-1 md:grid-cols-3 gap-4">
              <div>
                <label class="block text-sm font-medium text-gray-700 mb-1">大图数量</label>
                <input
                  v-model.number="timerConsumeForm.largeImages"
                  type="number"
                  min="0"
                  class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                />
              </div>
              <div>
                <label class="block text-sm font-medium text-gray-700 mb-1">超量小图</label>
                <input
                  v-model.number="timerConsumeForm.extraSmallImages"
                  type="number"
                  min="0"
                  class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                />
              </div>
              <div>
                <label class="block text-sm font-medium text-gray-700 mb-1">超量大图</label>
                <input
                  v-model.number="timerConsumeForm.extraLargeImages"
                  type="number"
                  min="0"
                  class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                />
              </div>
            </div>

            <div>
              <label class="block text-sm font-medium text-gray-700 mb-1">备注</label>
              <textarea
                v-model="timerConsumeForm.notes"
                rows="2"
                class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent resize-none"
                placeholder="开始计时前的备注"
              ></textarea>
            </div>

            <div class="bg-amber-50 border border-amber-200 rounded-lg p-4 text-sm text-amber-800">
              计时开始后，请前往“正在计时”页面完成结算。
            </div>
          </div>
        </div>

        <div class="px-6 py-4 border-t border-gray-200 flex justify-end space-x-3">
          <button
            @click="showConsumeDialog = false"
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
<div
      v-if="showDetailDialog && selectedTransaction"
      class="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50"
      @click.self="showDetailDialog = false"
    >
      <div class="bg-white rounded-xl shadow-xl w-full max-w-lg mx-4">
        <div class="px-6 py-4 border-b border-gray-200 flex items-center justify-between">
          <h3 class="text-lg font-semibold text-gray-800">交易详情</h3>
          <button
            @click="showDetailDialog = false"
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
              <label class="text-sm text-gray-500">客户电话</label>
              <p class="text-gray-900">{{ getCustomerPhone(selectedTransaction) }}</p>
            </div>
            <div>
              <label class="text-sm text-gray-500">金额</label>
              <p
                :class="[
                  'font-medium',
                  selectedTransaction.type === 'recharge' ? 'text-green-600' : 'text-orange-600'
                ]"
              >
                {{ selectedTransaction.type === 'recharge' ? '+' : '-' }}¥{{ formatAmount(selectedTransaction.amount) }}
              </p>
            </div>
            <div>
              <label class="text-sm text-gray-500">赠送金额</label>
              <p class="text-green-600">
                {{ selectedTransaction.bonusAmount > 0 ? '+¥' + formatAmount(selectedTransaction.bonusAmount) : '-' }}
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
                {{ selectedTransaction.operator?.name || selectedTransaction.operatorName || '-' }}
              </p>
            </div>
          </div>
          <div v-if="selectedTransaction.type === 'consumption' && selectedTransaction.description">
            <label class="text-sm text-gray-500">描述</label>
            <p class="text-gray-900 mt-1">{{ selectedTransaction.description }}</p>
          </div>
          <div v-if="selectedTransaction.activity">
            <label class="text-sm text-gray-500">关联活动</label>
            <p class="text-gray-900">{{ selectedTransaction.activity?.name || '-' }}</p>
          </div>
        </div>
        <div class="px-6 py-4 border-t border-gray-200 flex justify-end">
          <button
            @click="showDetailDialog = false"
            class="px-4 py-2 bg-gray-100 text-gray-700 rounded-lg hover:bg-gray-200 transition-colors"
          >
            关闭
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
</style>




