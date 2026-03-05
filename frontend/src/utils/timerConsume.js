export const TABLE_AREA_OPTIONS = 'ABCDEFGHJKLMNPQRSTUVWXYZ'.split('')
export const TABLE_SEAT_OPTIONS = Array.from({ length: 20 }, (_, index) => String(index + 1))
const TABLE_NO_PATTERN = /^([A-HJ-NP-Za-hj-np-z])桌([1-9]|1[0-9]|20)号$/

export function buildTableNo(area = '', seat = '') {
  const normalizedArea = String(area || '').trim().toUpperCase()
  const normalizedSeat = String(seat || '').trim()
  if (!TABLE_AREA_OPTIONS.includes(normalizedArea)) return ''
  if (!TABLE_SEAT_OPTIONS.includes(normalizedSeat)) return ''
  return `${normalizedArea}桌${normalizedSeat}号`
}

export function isDoublePackagePlan(packagePlan = '') {
  const plan = String(packagePlan || '').trim()
  return plan === 'weekdayDoubleUnlimited' || plan === 'weekendDoubleUnlimited'
}

export const timerTypeOptions = [
  { value: 'limited', label: '限时套餐' },
  { value: 'weekday', label: '工作日套餐' },
  { value: 'weekend', label: '周末套餐' }
]

export const timerPackagePlanOptionsByType = {
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

export function getTimerPackagePlanOptions(timerType = 'limited') {
  return timerPackagePlanOptionsByType[timerType] || timerPackagePlanOptionsByType.limited
}

export function getDefaultTimerPackagePlan(timerType = 'limited') {
  const options = getTimerPackagePlanOptions(timerType)
  return options[0]?.value || 'limited1h'
}

export function createTimerConsumeForm(customerId = '') {
  return {
    customerId,
    tableArea: TABLE_AREA_OPTIONS[0],
    tableSeat: TABLE_SEAT_OPTIONS[0],
    tableNo: `${TABLE_AREA_OPTIONS[0]}桌${TABLE_SEAT_OPTIONS[0]}号`,
    secondTableArea: TABLE_AREA_OPTIONS[0],
    secondTableSeat: '',
    secondTableNo: '',
    timerType: 'limited',
    packagePlan: getDefaultTimerPackagePlan('limited'),
    largeImages: 0,
    extraSmallImages: 0,
    extraLargeImages: 0,
    notes: ''
  }
}

export function validateTimerConsumeForm(form = {}, customers = []) {
  const errors = {}
  const customerId = String(form.customerId || '').trim()
  const customerExists = customers.some((customer) => String(customer?.id || '').trim() === customerId)

  if (!customerId) {
    errors.customerId = '请选择客户'
  } else if (!customerExists) {
    errors.customerId = '请选择有效客户'
  }

  if (!String(form.timerType || '').trim()) {
    errors.timerType = '请选择计时类型'
  }

  if (!String(form.packagePlan || '').trim()) {
    errors.packagePlan = '请选择套餐方案'
  }

  const tableNo = buildTableNo(form.tableArea, form.tableSeat) || String(form.tableNo || '').trim()
  if (!tableNo) {
    errors.tableNo = '请选择桌号'
  } else if (!TABLE_NO_PATTERN.test(tableNo)) {
    errors.tableNo = '桌号必须在 A-H/J-N/P-Z 桌、1-20号范围内'
  }

  if (isDoublePackagePlan(form.packagePlan)) {
    const secondTableNo = buildTableNo(form.secondTableArea, form.secondTableSeat) || String(form.secondTableNo || '').trim()
    if (!secondTableNo) {
      errors.secondTableNo = '双人套餐请选择第二个座位'
    } else if (!TABLE_NO_PATTERN.test(secondTableNo)) {
      errors.secondTableNo = '第二座位格式不正确'
    } else if (secondTableNo === tableNo) {
      errors.secondTableNo = '第二座位不能与第一座位相同'
    }
  }

  return {
    isValid: Object.keys(errors).length === 0,
    errors
  }
}

export function buildTimerConsumeNotesPayload(form = {}) {
  return JSON.stringify({
    note: form.notes || '',
    packagePlan: form.packagePlan || getDefaultTimerPackagePlan(form.timerType),
    secondTableNo: buildTableNo(form.secondTableArea, form.secondTableSeat) || String(form.secondTableNo || '').trim(),
    materials: {
      largeImages: Number(form.largeImages) || 0,
      extraSmallImages: Number(form.extraSmallImages) || 0,
      extraLargeImages: Number(form.extraLargeImages) || 0
    }
  })
}

export function buildTimerConsumeRequestPayload(form = {}) {
  const tableNo = buildTableNo(form.tableArea, form.tableSeat) || String(form.tableNo || '').trim()
  return {
    customer_id: form.customerId || '',
    table_no: tableNo,
    timer_type: form.timerType || 'limited',
    notes: buildTimerConsumeNotesPayload(form)
  }
}
