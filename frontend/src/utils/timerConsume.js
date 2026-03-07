import {
  getDaySingleLimitedOption,
  getDayUnlimitedPackageOptions,
  getPackagePlanPeopleCount
} from '@/utils/consumptionCalculator'
export {
  TABLE_AREA_OPTIONS,
  TABLE_SEAT_OPTIONS,
  TABLE_NO_PATTERN,
  buildTableNo,
  normalizeTableNo,
  isValidTableNo,
  parseTableNoParts
} from '@/utils/seatLayout'
import {
  TABLE_AREA_OPTIONS,
  TABLE_SEAT_OPTIONS,
  buildTableNo,
  getSeatOptionByTableNo,
  getSeatOptionList,
  isConfiguredTableNo,
  isValidTableNo,
  normalizeTableNo,
  parseTableNoParts
} from '@/utils/seatLayout'

function normalizeTableArea(value = '', fallback = TABLE_AREA_OPTIONS[0]) {
  const normalized = String(value || '').trim().toUpperCase()
  if (TABLE_AREA_OPTIONS.includes(normalized)) return normalized
  if (fallback === '') return ''
  return TABLE_AREA_OPTIONS.includes(fallback) ? fallback : TABLE_AREA_OPTIONS[0]
}

function normalizeTableSeat(value = '', fallback = '') {
  const normalized = String(value || '').trim()
  if (TABLE_SEAT_OPTIONS.includes(normalized)) return normalized
  if (TABLE_SEAT_OPTIONS.includes(String(fallback || '').trim())) {
    return String(fallback || '').trim()
  }
  return ''
}

function buildLegacyExtraSeatSelection(form = {}, fallbackArea = TABLE_AREA_OPTIONS[0]) {
  const secondArea = normalizeTableArea(form.secondTableArea, fallbackArea)
  const secondSeat = normalizeTableSeat(form.secondTableSeat)
  if (secondSeat) {
    return {
      tableArea: secondArea,
      tableSeat: secondSeat,
      tableNo: buildTableNo(secondArea, secondSeat)
    }
  }

  const parsed = parseTableNoParts(form.secondTableNo, secondArea, '')
  if (!parsed.tableSeat) return null
  return {
    tableArea: parsed.tableArea,
    tableSeat: parsed.tableSeat,
    tableNo: buildTableNo(parsed.tableArea, parsed.tableSeat)
  }
}

function resolveSeatOption(rawSelection, seatLayoutConfig = null) {
  if (typeof rawSelection === 'string') {
    return getSeatOptionByTableNo(rawSelection, seatLayoutConfig)
  }

  const source = rawSelection && typeof rawSelection === 'object' ? rawSelection : {}
  const directTableNo = normalizeTableNo(source.tableNo)
  return getSeatOptionByTableNo(
    directTableNo || buildTableNo(source.tableArea ?? source.area, source.tableSeat ?? source.seat),
    seatLayoutConfig
  )
}

function normalizeExtraSeatSelection(rawSelection, fallbackArea = TABLE_AREA_OPTIONS[0], seatLayoutConfig = null) {
  const configuredSeatOption = resolveSeatOption(rawSelection, seatLayoutConfig)
  if (configuredSeatOption) {
    return {
      tableArea: configuredSeatOption.tableArea,
      tableSeat: configuredSeatOption.tableSeat,
      tableNo: configuredSeatOption.tableNo
    }
  }

  if (typeof rawSelection === 'string') {
    const parsed = parseTableNoParts(rawSelection, fallbackArea, '')
    return {
      tableArea: parsed.tableArea,
      tableSeat: parsed.tableSeat,
      tableNo: buildTableNo(parsed.tableArea, parsed.tableSeat)
    }
  }

  const source = rawSelection && typeof rawSelection === 'object' ? rawSelection : {}
  const baseArea = normalizeTableArea(source.tableArea ?? source.area, fallbackArea)
  const directSeat = normalizeTableSeat(source.tableSeat ?? source.seat)
  const directTableNo = normalizeTableNo(source.tableNo)
  if (directSeat) {
    return {
      tableArea: baseArea,
      tableSeat: directSeat,
      tableNo: buildTableNo(baseArea, directSeat)
    }
  }

  const parsed = parseTableNoParts(directTableNo, baseArea, '')
  return {
    tableArea: parsed.tableArea,
    tableSeat: parsed.tableSeat,
    tableNo: buildTableNo(parsed.tableArea, parsed.tableSeat)
  }
}

export function isMultiPersonPackagePlan(packagePlan = '', rawRules = {}) {
  return getPackagePlanPeopleCount(packagePlan, rawRules) > 1
}

export function isDoublePackagePlan(packagePlan = '', rawRules = {}) {
  return isMultiPersonPackagePlan(packagePlan, rawRules)
}

export function getRequiredExtraSeatCount(packagePlan = '', rawRules = {}) {
  const peopleCount = Math.max(1, getPackagePlanPeopleCount(packagePlan, rawRules))
  return Math.max(0, peopleCount - 1)
}

export const timerTypeOptions = [
  { value: 'limited', label: '限时套餐' },
  { value: 'weekday', label: '工作日套餐' },
  { value: 'weekend', label: '周末套餐' }
]

function getLimitedPackagePlanOptions() {
  return [
    { value: 'limited1h', label: '限时1小时' },
    { value: 'limited2h', label: '限时2小时' }
  ]
}

export function buildTimerPackagePlanOptionsByType(rawRules = {}, options = {}) {
  const includeDisabled = Boolean(options.includeDisabled)

  const weekdayUnlimitedOptions = getDayUnlimitedPackageOptions('weekday', rawRules, { includeDisabled })
    .map((item) => ({ value: item.value, label: item.label }))
  const weekendUnlimitedOptions = getDayUnlimitedPackageOptions('weekend', rawRules, { includeDisabled })
    .map((item) => ({ value: item.value, label: item.label }))

  const weekdaySingleLimitedOption = getDaySingleLimitedOption('weekday', rawRules)
  const weekendSingleLimitedOption = getDaySingleLimitedOption('weekend', rawRules)

  return {
    limited: getLimitedPackagePlanOptions(),
    weekday: [
      ...weekdayUnlimitedOptions,
      { value: weekdaySingleLimitedOption.value, label: weekdaySingleLimitedOption.label }
    ],
    weekend: [
      ...weekendUnlimitedOptions,
      { value: weekendSingleLimitedOption.value, label: weekendSingleLimitedOption.label }
    ]
  }
}

export const timerPackagePlanOptionsByType = buildTimerPackagePlanOptionsByType()

export function getTimerPackagePlanOptions(timerType = 'limited', rawRules = {}, options = {}) {
  const map = buildTimerPackagePlanOptionsByType(rawRules, options)
  return map[timerType] || map.limited
}

export function getDefaultTimerPackagePlan(timerType = 'limited', rawRules = {}, options = {}) {
  const optionsByType = getTimerPackagePlanOptions(timerType, rawRules, options)
  const normalizedOptions = Array.isArray(optionsByType) ? optionsByType : []
  return normalizedOptions[0]?.value || 'limited1h'
}

export function createTimerConsumeForm(customerId = '', rawRules = {}, seatLayoutConfig = null) {
  const defaultSeatOption = getSeatOptionList(seatLayoutConfig)[0] || {
    tableArea: TABLE_AREA_OPTIONS[0],
    tableSeat: TABLE_SEAT_OPTIONS[0],
    tableNo: `${TABLE_AREA_OPTIONS[0]}桌${TABLE_SEAT_OPTIONS[0]}号`
  }

  return {
    customerId,
    tableArea: defaultSeatOption.tableArea,
    tableSeat: defaultSeatOption.tableSeat,
    tableNo: defaultSeatOption.tableNo,
    extraTableSelections: [],
    extraTableNos: [],
    secondTableArea: defaultSeatOption.tableArea,
    secondTableSeat: '',
    secondTableNo: '',
    timerType: 'limited',
    packagePlan: getDefaultTimerPackagePlan('limited', rawRules),
    largeImages: 0,
    extraSmallImages: 0,
    extraLargeImages: 0,
    miscSelections: {},
    notes: ''
  }
}

function normalizeMiscSelections(selectionMap = {}) {
  if (!selectionMap || typeof selectionMap !== 'object') return {}

  const normalized = {}
  Object.entries(selectionMap).forEach(([rawKey, rawValue]) => {
    const key = String(rawKey || '').trim()
    if (!key) return

    const amount = Number(rawValue)
    if (!Number.isFinite(amount) || amount < 0) return

    normalized[key] = Math.floor(amount)
  })
  return normalized
}

export function normalizeExtraTableSelections(
  rawSelections = [],
  requiredCount = 0,
  fallbackArea = TABLE_AREA_OPTIONS[0],
  seatLayoutConfig = null
) {
  const count = Math.max(0, Math.floor(Number(requiredCount) || 0))
  if (count === 0) return []

  const list = Array.isArray(rawSelections) ? rawSelections : []
  const normalizedFallbackArea = normalizeTableArea(fallbackArea, TABLE_AREA_OPTIONS[0])
  return Array.from({ length: count }, (_, index) => {
    const normalized = normalizeExtraSeatSelection(list[index], normalizedFallbackArea, seatLayoutConfig)
    return {
      tableArea: normalized.tableArea,
      tableSeat: normalized.tableSeat,
      tableNo: buildTableNo(normalized.tableArea, normalized.tableSeat)
    }
  })
}

function collectDistinctExtraTableNos(extraTableSelections = [], primaryTableNo = '', seatLayoutConfig = null) {
  const unique = []
  const seen = new Set()
  const normalizedPrimary = normalizeTableNo(primaryTableNo)
  if (normalizedPrimary) {
    seen.add(normalizedPrimary)
  }

  extraTableSelections.forEach((selection) => {
    const tableNo = normalizeTableNo(selection?.tableNo || buildTableNo(selection?.tableArea, selection?.tableSeat))
    if (!isValidTableNo(tableNo)) return
    if (seatLayoutConfig && !isConfiguredTableNo(tableNo, seatLayoutConfig)) return
    if (seen.has(tableNo)) return
    seen.add(tableNo)
    unique.push(tableNo)
  })

  return unique
}

export function getTimerConsumeSeatPayload(form = {}, rawRules = {}, seatLayoutConfig = null) {
  const defaultSeatOption = getSeatOptionList(seatLayoutConfig)[0] || {
    tableArea: TABLE_AREA_OPTIONS[0],
    tableSeat: TABLE_SEAT_OPTIONS[0],
    tableNo: buildTableNo(TABLE_AREA_OPTIONS[0], TABLE_SEAT_OPTIONS[0])
  }
  const configuredPrimarySeat = resolveSeatOption(
    {
      tableArea: form.tableArea,
      tableSeat: form.tableSeat,
      tableNo: form.tableNo
    },
    seatLayoutConfig
  )
  const tableArea = configuredPrimarySeat?.tableArea || normalizeTableArea(form.tableArea, defaultSeatOption.tableArea)
  const tableSeat = configuredPrimarySeat?.tableSeat || normalizeTableSeat(form.tableSeat, defaultSeatOption.tableSeat)
  const tableNo = normalizeTableNo(
    configuredPrimarySeat?.tableNo
      || buildTableNo(tableArea, tableSeat)
      || form.tableNo
      || defaultSeatOption.tableNo
  )
  const requiredExtraSeatCount = getRequiredExtraSeatCount(form.packagePlan, rawRules)

  let sourceSelections = []
  if (Array.isArray(form.extraTableSelections) && form.extraTableSelections.length > 0) {
    sourceSelections = form.extraTableSelections
  } else if (Array.isArray(form.extraTableNos) && form.extraTableNos.length > 0) {
    sourceSelections = form.extraTableNos
  } else {
    const legacySelection = buildLegacyExtraSeatSelection(form, tableArea)
    if (legacySelection) {
      sourceSelections = [legacySelection]
    }
  }

  const extraTableSelections = normalizeExtraTableSelections(sourceSelections, requiredExtraSeatCount, tableArea, seatLayoutConfig)
  const extraTableNos = collectDistinctExtraTableNos(extraTableSelections, tableNo, seatLayoutConfig)

  return {
    tableArea,
    tableSeat,
    tableNo,
    requiredExtraSeatCount,
    extraTableSelections,
    extraTableNos,
    secondTableNo: extraTableNos[0] || ''
  }
}

export function validateTimerConsumeForm(form = {}, customers = [], rawRules = {}, seatLayoutConfig = null) {
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
  } else {
    const options = getTimerPackagePlanOptions(form.timerType || 'limited', rawRules)
    const exists = options.some((item) => String(item?.value || '').trim() === String(form.packagePlan || '').trim())
    if (!exists) {
      errors.packagePlan = '套餐方案已失效，请重新选择'
    }
  }

  const seatPayload = getTimerConsumeSeatPayload(form, rawRules, seatLayoutConfig)
  const tableNo = seatPayload.tableNo
  if (!tableNo) {
    errors.tableNo = '请选择桌号'
  } else if (!isValidTableNo(tableNo)) {
    errors.tableNo = '桌号必须在 A-H/J-N/P-Z 桌、1-100号范围内'
  } else if (seatLayoutConfig && !isConfiguredTableNo(tableNo, seatLayoutConfig)) {
    errors.tableNo = '请选择有效座位'
  }

  if (seatPayload.requiredExtraSeatCount > 0) {
    const seen = new Set(tableNo ? [tableNo] : [])
    const detailErrors = []
    seatPayload.extraTableSelections.forEach((selection, index) => {
      const seatLabel = `第${index + 2}座位`
      const tableNoAtIndex = normalizeTableNo(selection?.tableNo || buildTableNo(selection?.tableArea, selection?.tableSeat))
      const key = `extraTableNos.${index}`

      if (!tableNoAtIndex) {
        errors[key] = `${seatLabel}不能为空`
        detailErrors.push(errors[key])
        return
      }
      if (!isValidTableNo(tableNoAtIndex)) {
        errors[key] = `${seatLabel}格式不正确`
        detailErrors.push(errors[key])
        return
      }
      if (seatLayoutConfig && !isConfiguredTableNo(tableNoAtIndex, seatLayoutConfig)) {
        errors[key] = `${seatLabel}不在已配置座位中`
        detailErrors.push(errors[key])
        return
      }
      if (seen.has(tableNoAtIndex)) {
        errors[key] = `${seatLabel}不能与已选座位重复`
        detailErrors.push(errors[key])
        return
      }
      seen.add(tableNoAtIndex)
    })

    if (detailErrors.length > 0) {
      errors.extraTableNos = detailErrors[0]
      if (!errors.secondTableNo && errors['extraTableNos.0']) {
        errors.secondTableNo = errors['extraTableNos.0']
      }
    }
  }

  return {
    isValid: Object.keys(errors).length === 0,
    errors
  }
}

export function buildTimerConsumeNotesPayload(form = {}, rawRules = {}, seatLayoutConfig = null) {
  const seatPayload = getTimerConsumeSeatPayload(form, rawRules, seatLayoutConfig)
  return JSON.stringify({
    note: form.notes || '',
    packagePlan: form.packagePlan || getDefaultTimerPackagePlan(form.timerType, rawRules),
    extraTableNos: seatPayload.extraTableNos,
    secondTableNo: seatPayload.secondTableNo,
    materials: {
      largeImages: Number(form.largeImages) || 0,
      extraSmallImages: Number(form.extraSmallImages) || 0,
      extraLargeImages: Number(form.extraLargeImages) || 0
    },
    miscSelections: normalizeMiscSelections(form.miscSelections)
  })
}

export function buildTimerConsumeRequestPayload(form = {}, rawRules = {}, seatLayoutConfig = null) {
  const seatPayload = getTimerConsumeSeatPayload(form, rawRules, seatLayoutConfig)
  return {
    customer_id: form.customerId || '',
    table_no: seatPayload.tableNo,
    timer_type: form.timerType || 'limited',
    notes: buildTimerConsumeNotesPayload(form, rawRules, seatLayoutConfig)
  }
}
