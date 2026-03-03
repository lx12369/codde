const DEFAULT_BILLING_RULES = {
  limited: {
    price1h: 18.9,
    price2h: 35.8,
    overtimeFreeMinutes: 10,
    overtime10to30Fee: 10,
    overtime30Fee: 18.9
  },
  weekday: {
    singleUnlimited: 53.9,
    doubleUnlimited: 103.9,
    singleLimited: 35.9
  },
  weekend: {
    singleUnlimited: 63.9,
    doubleUnlimited: 123.9,
    singleLimited: 42.8
  },
  materials: {
    largeImageFee: 5,
    extraSmallImageFee: 3,
    extraLargeImageFee: 5
  }
}

const MEITUAN_RATE = 0.07

function toNumber(value, fallback = 0) {
  const n = Number(value)
  return Number.isFinite(n) ? n : fallback
}

function toInteger(value, fallback = 0) {
  return Math.floor(toNumber(value, fallback))
}

function round2(value) {
  return Math.round((value + Number.EPSILON) * 100) / 100
}

export function calculateMeituanDeduction(baseAmount, rate = MEITUAN_RATE) {
  const safeBase = Math.max(0, toNumber(baseAmount, 0))
  const safeRate = Math.max(0, toNumber(rate, MEITUAN_RATE))
  return round2(safeBase * safeRate)
}

export function applyDeduction(totalAmount, deductionAmount) {
  const safeTotal = Math.max(0, toNumber(totalAmount, 0))
  const safeDeduction = Math.max(0, toNumber(deductionAmount, 0))
  return round2(Math.max(0, safeTotal - safeDeduction))
}

export function getPackagePlanBaseFee(packagePlan = '', rawRules = {}) {
  const rules = normalizeBillingRules(rawRules)
  const map = {
    limited1h: rules.limited.price1h,
    limited2h: rules.limited.price2h,
    weekdaySingleUnlimited: rules.weekday.singleUnlimited,
    weekdayDoubleUnlimited: rules.weekday.doubleUnlimited,
    weekdaySingleLimited: rules.weekday.singleLimited,
    weekendSingleUnlimited: rules.weekend.singleUnlimited,
    weekendDoubleUnlimited: rules.weekend.doubleUnlimited,
    weekendSingleLimited: rules.weekend.singleLimited
  }

  return round2(Math.max(0, toNumber(map[packagePlan], 0)))
}

export function normalizeBillingRules(raw = {}) {
  return {
    limited: {
      ...DEFAULT_BILLING_RULES.limited,
      ...(raw.limited || {})
    },
    weekday: {
      ...DEFAULT_BILLING_RULES.weekday,
      ...(raw.weekday || {})
    },
    weekend: {
      ...DEFAULT_BILLING_RULES.weekend,
      ...(raw.weekend || {})
    },
    materials: {
      ...DEFAULT_BILLING_RULES.materials,
      ...(raw.materials || {})
    }
  }
}

export function getBillingTypeLabel(type) {
  const map = {
    limited: '限时',
    weekday: '工作日',
    weekend: '周末'
  }
  return map[type] || '未知'
}

function calculateTieredOvertime(overtimeMinutes, limitedRules) {
  const minutes = Math.max(0, toInteger(overtimeMinutes, 0))
  const freeMinutes = Math.max(0, toInteger(limitedRules.overtimeFreeMinutes, 10))
  const fee10to30 = Math.max(0, toNumber(limitedRules.overtime10to30Fee, 10))
  const hourFee = Math.max(0, toNumber(limitedRules.overtime30Fee, toNumber(limitedRules.price1h, 18.9)))

  if (minutes <= 0) {
    return {
      fee: 0,
      detail: '',
      billedHours: 0
    }
  }

  if (minutes <= freeMinutes) {
    return {
      fee: 0,
      detail: `超时${minutes}分钟(免费)`,
      billedHours: 0
    }
  }

  if (minutes <= 30) {
    return {
      fee: fee10to30,
      detail: `超时${minutes}分钟(+¥${fee10to30.toFixed(2)})`,
      billedHours: 0
    }
  }

  const billedHours = Math.ceil((minutes - 30) / 60)
  const fee = billedHours * hourFee

  return {
    fee,
    detail: `超时${minutes}分钟(超30分钟按${billedHours}小时计费)`,
    billedHours
  }
}

function calculateLimitedByTotalMinutes(totalMinutes, limitedRules) {
  const minutes = Math.max(0, toInteger(totalMinutes, 0))
  const price1h = Math.max(0, toNumber(limitedRules.price1h, 18.9))
  const price2h = Math.max(0, toNumber(limitedRules.price2h, 35.8))
  const fee10to30 = Math.max(0, toNumber(limitedRules.overtime10to30Fee, 10))
  const details = []

  let baseFee = 0
  let overtimeFee = 0
  let overtimeMinutes = 0

  if (minutes <= 60) {
    baseFee = price1h
    details.push('限时1小时')
    return { baseFee, overtimeFee, overtimeMinutes, details }
  }

  if (minutes <= 70) {
    baseFee = price1h
    overtimeMinutes = minutes - 60
    details.push('限时1小时')
    details.push(`超时${overtimeMinutes}分钟(免费)`)
    return { baseFee, overtimeFee, overtimeMinutes, details }
  }

  if (minutes < 90) {
    baseFee = price1h
    overtimeMinutes = minutes - 60
    overtimeFee = fee10to30
    details.push('限时1小时')
    details.push(`超时${overtimeMinutes}分钟(+¥${fee10to30.toFixed(2)})`)
    return { baseFee, overtimeFee, overtimeMinutes, details }
  }

  if (minutes <= 120) {
    baseFee = price2h
    details.push('限时2小时')
    return { baseFee, overtimeFee, overtimeMinutes, details }
  }

  baseFee = price2h
  overtimeMinutes = minutes - 120
  details.push('限时2小时')

  const overtimeResult = calculateTieredOvertime(overtimeMinutes, limitedRules)
  overtimeFee = overtimeResult.fee
  if (overtimeResult.detail) {
    details.push(overtimeResult.detail)
  }

  return { baseFee, overtimeFee, overtimeMinutes, details }
}

function resolveTimerDayType(requestedBillingType, timerDayType, settlementTimestamp) {
  if (requestedBillingType === 'weekday' || requestedBillingType === 'weekend') {
    return requestedBillingType
  }

  if (timerDayType === 'weekday' || timerDayType === 'weekend') {
    return timerDayType
  }

  const date = settlementTimestamp ? new Date(settlementTimestamp) : new Date()
  const day = date.getDay()
  return day === 0 || day === 6 ? 'weekend' : 'weekday'
}

function calculateTimerBestPrice(elapsedMinutes, requestedBillingType, rules, timerDayType, settlementTimestamp, packagePlan = '') {
  const normalizedElapsedMinutes = Math.max(0, toInteger(elapsedMinutes, 0))
  const effectiveElapsedMinutes = packagePlan === 'limited2h'
    ? Math.max(normalizedElapsedMinutes, 120)
    : normalizedElapsedMinutes

  const limitedResult = calculateLimitedByTotalMinutes(effectiveElapsedMinutes, rules.limited)
  const limitedTotal = limitedResult.baseFee + limitedResult.overtimeFee
  const hasOvertime = effectiveElapsedMinutes > 60

  const dayType = resolveTimerDayType(requestedBillingType, timerDayType, settlementTimestamp)
  const dayLabel = dayType === 'weekend' ? '周末' : '工作日'
  const unlimitedFee = dayType === 'weekend'
    ? Math.max(0, toNumber(rules.weekend.singleUnlimited, 63.9))
    : Math.max(0, toNumber(rules.weekday.singleUnlimited, 53.9))

  if (hasOvertime && unlimitedFee < limitedTotal) {
    return {
      billingType: dayType,
      baseFee: unlimitedFee,
      overtimeFee: 0,
      overtimeMinutes: 0,
      details: [`${dayLabel}单人不限时不限板(超时后自动最优)`]
    }
  }

  return {
    billingType: 'limited',
    baseFee: limitedResult.baseFee,
    overtimeFee: limitedResult.overtimeFee,
    overtimeMinutes: limitedResult.overtimeMinutes,
    details: limitedResult.details
  }
}

export function calculateConsumptionAmount(options = {}, rawRules = {}) {
  const rules = normalizeBillingRules(rawRules)

  const pricingMode = options.pricingMode || 'standard'
  const billingType = options.billingType || 'limited'
  const duration = String(options.duration || '1')
  const weekdayType = options.weekdayType || 'singleUnlimited'
  const weekendType = options.weekendType || 'singleUnlimited'

  const elapsedMinutes = Math.max(0, toInteger(options.elapsedMinutes, 0))
  const inputOvertimeMinutes = Math.max(0, toInteger(options.overtimeMinutes, 0))
  const largeImages = Math.max(0, toInteger(options.largeImages, 0))
  const extraSmallImages = Math.max(0, toInteger(options.extraSmallImages, 0))
  const extraLargeImages = Math.max(0, toInteger(options.extraLargeImages, 0))
  const additionalFee = Math.max(0, toNumber(options.additionalFee, 0))

  const details = []
  let appliedBillingType = billingType
  let baseFee = 0
  let overtimeFee = 0
  let effectiveOvertimeMinutes = inputOvertimeMinutes

  if (pricingMode === 'timer') {
    if (billingType === 'limited') {
      const timerResult = calculateTimerBestPrice(
        elapsedMinutes,
        billingType,
        rules,
        options.timerDayType,
        options.settlementTimestamp,
        options.packagePlan
      )

      appliedBillingType = timerResult.billingType
      baseFee = timerResult.baseFee
      overtimeFee = timerResult.overtimeFee
      effectiveOvertimeMinutes = timerResult.overtimeMinutes
      details.push(...timerResult.details)
    } else if (billingType === 'weekday') {
      appliedBillingType = 'weekday'
      effectiveOvertimeMinutes = 0

      if (weekdayType === 'doubleUnlimited') {
        baseFee = toNumber(rules.weekday.doubleUnlimited)
        details.push('工作日双人不限时不限板')
      } else if (weekdayType === 'singleLimited') {
        baseFee = toNumber(rules.weekday.singleLimited)
        details.push('工作日单人不限时限板')
      } else {
        baseFee = toNumber(rules.weekday.singleUnlimited)
        details.push('工作日单人不限时不限板')
      }
    } else {
      appliedBillingType = 'weekend'
      effectiveOvertimeMinutes = 0

      if (weekendType === 'doubleUnlimited') {
        baseFee = toNumber(rules.weekend.doubleUnlimited)
        details.push('周末双人不限时不限板')
      } else if (weekendType === 'singleLimited') {
        baseFee = toNumber(rules.weekend.singleLimited)
        details.push('周末单人不限时限板')
      } else {
        baseFee = toNumber(rules.weekend.singleUnlimited)
        details.push('周末单人不限时不限板')
      }
    }
  } else if (billingType === 'limited') {
    const packageMinutes = duration === '2' ? 120 : 60
    const totalMinutes = packageMinutes + inputOvertimeMinutes
    const limitedResult = calculateLimitedByTotalMinutes(totalMinutes, rules.limited)

    baseFee = limitedResult.baseFee
    overtimeFee = limitedResult.overtimeFee
    effectiveOvertimeMinutes = limitedResult.overtimeMinutes
    details.push(...limitedResult.details)
  } else if (billingType === 'weekday') {
    if (weekdayType === 'doubleUnlimited') {
      baseFee = toNumber(rules.weekday.doubleUnlimited)
      details.push('工作日双人不限时不限板')
    } else if (weekdayType === 'singleLimited') {
      baseFee = toNumber(rules.weekday.singleLimited)
      details.push('工作日单人不限时限板')
    } else {
      baseFee = toNumber(rules.weekday.singleUnlimited)
      details.push('工作日单人不限时不限板')
    }
  } else {
    if (weekendType === 'doubleUnlimited') {
      baseFee = toNumber(rules.weekend.doubleUnlimited)
      details.push('周末双人不限时不限板')
    } else if (weekendType === 'singleLimited') {
      baseFee = toNumber(rules.weekend.singleLimited)
      details.push('周末单人不限时限板')
    } else {
      baseFee = toNumber(rules.weekend.singleUnlimited)
      details.push('周末单人不限时不限板')
    }
  }

  const materialFee =
    largeImages * toNumber(rules.materials.largeImageFee) +
    extraSmallImages * toNumber(rules.materials.extraSmallImageFee) +
    extraLargeImages * toNumber(rules.materials.extraLargeImageFee)

  if (largeImages > 0) details.push(`大图${largeImages}张`)
  if (extraSmallImages > 0) details.push(`超量小图${extraSmallImages}张`)
  if (extraLargeImages > 0) details.push(`超量大图${extraLargeImages}张`)

  if (additionalFee > 0) {
    details.push(`附加费用¥${additionalFee.toFixed(2)}`)
  }

  const total = round2(baseFee + overtimeFee + materialFee + additionalFee)

  return {
    billingType: appliedBillingType,
    requestedBillingType: billingType,
    pricingMode,
    baseFee: round2(baseFee),
    overtimeFee: round2(overtimeFee),
    materialFee: round2(materialFee),
    additionalFee: round2(additionalFee),
    total,
    details,
    inputs: {
      duration,
      weekdayType,
      weekendType,
      overtimeMinutes: effectiveOvertimeMinutes,
      elapsedMinutes,
      largeImages,
      extraSmallImages,
      extraLargeImages,
      packagePlan: options.packagePlan || ''
    }
  }
}

export function buildConsumptionDescription(meta = {}, calcResult = {}, notes = '') {
  const mode = meta.mode || 'auto'
  const billingTypeLabel = getBillingTypeLabel(meta.billingType || calcResult.billingType)
  const parts = []

  if (mode === 'timer') {
    const elapsedMinutes = Math.max(0, Math.floor(toNumber(meta.elapsedMinutes, 0)))
    const hours = Math.floor(elapsedMinutes / 60)
    const minutes = elapsedMinutes % 60
    parts.push(`计时消费(${billingTypeLabel})`)
    parts.push(`${hours}小时${minutes}分钟`)
  } else {
    parts.push(`自动结算(${billingTypeLabel})`)
  }

  const detailParts = calcResult.details || []
  if (detailParts.length > 0) {
    parts.push(detailParts.join('，'))
  }

  const trimmedNotes = String(notes || '').trim()
  if (trimmedNotes) {
    parts.push(`备注: ${trimmedNotes}`)
  }

  return parts.join(' - ')
}

export { DEFAULT_BILLING_RULES }

