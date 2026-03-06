import { getEffectiveBillingDayType } from '@/utils/dayType'

const DEFAULT_UNLIMITED_PACKAGES = {
  weekday: [
    {
      id: 'weekday_unlimited_1p',
      code: 'weekdaySingleUnlimited',
      label: '工作日单人不限时不限板',
      people_count: 1,
      price: 53.9,
      enabled: true,
      sort_order: 1
    },
    {
      id: 'weekday_unlimited_2p',
      code: 'weekdayDoubleUnlimited',
      label: '工作日双人不限时不限板',
      people_count: 2,
      price: 103.9,
      enabled: true,
      sort_order: 2
    }
  ],
  weekend: [
    {
      id: 'weekend_unlimited_1p',
      code: 'weekendSingleUnlimited',
      label: '周末单人不限时不限板',
      people_count: 1,
      price: 63.9,
      enabled: true,
      sort_order: 1
    },
    {
      id: 'weekend_unlimited_2p',
      code: 'weekendDoubleUnlimited',
      label: '周末双人不限时不限板',
      people_count: 2,
      price: 123.9,
      enabled: true,
      sort_order: 2
    }
  ]
}

const LEGACY_DAY_TYPE_TO_PLAN_CODE = {
  weekday: {
    singleUnlimited: 'weekdaySingleUnlimited',
    doubleUnlimited: 'weekdayDoubleUnlimited',
    singleLimited: 'weekdaySingleLimited'
  },
  weekend: {
    singleUnlimited: 'weekendSingleUnlimited',
    doubleUnlimited: 'weekendDoubleUnlimited',
    singleLimited: 'weekendSingleLimited'
  }
}

const LEGACY_PLAN_CODE_META = {
  weekdaySingleUnlimited: { timerType: 'weekday', peopleCount: 1, label: '工作日单人不限时不限板', limited: false },
  weekdayDoubleUnlimited: { timerType: 'weekday', peopleCount: 2, label: '工作日双人不限时不限板', limited: false },
  weekdaySingleLimited: { timerType: 'weekday', peopleCount: 1, label: '工作日单人不限时限板', limited: true },
  weekendSingleUnlimited: { timerType: 'weekend', peopleCount: 1, label: '周末单人不限时不限板', limited: false },
  weekendDoubleUnlimited: { timerType: 'weekend', peopleCount: 2, label: '周末双人不限时不限板', limited: false },
  weekendSingleLimited: { timerType: 'weekend', peopleCount: 1, label: '周末单人不限时限板', limited: true }
}

const DEFAULT_BILLING_RULES = {
  limited: {
    price1h: 18.9,
    price2h: 35.8,
    overtimeFreeMinutes: 10,
    overtime10to30Fee: 10,
    overtime30Fee: 18.9
  },
  weekday: {
    unlimited_packages: DEFAULT_UNLIMITED_PACKAGES.weekday,
    singleLimited: 35.9
  },
  weekend: {
    unlimited_packages: DEFAULT_UNLIMITED_PACKAGES.weekend,
    singleLimited: 42.8
  },
  materials: {
    largeImageFee: 5,
    extraSmallImageFee: 3,
    extraLargeImageFee: 5
  },
  overtime: {
    ratePerMinute: 0.5
  },
  misc: {
    items: []
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

function cloneDefaultUnlimitedPackages(dayType = 'weekday') {
  const source = Array.isArray(DEFAULT_UNLIMITED_PACKAGES[dayType])
    ? DEFAULT_UNLIMITED_PACKAGES[dayType]
    : []
  return source.map((item) => ({ ...item }))
}

function normalizePackageCode(code, fallbackCode = '') {
  const normalized = String(code || '').trim()
  if (/^[A-Za-z0-9_-]{2,64}$/.test(normalized)) return normalized
  return String(fallbackCode || '').trim()
}

function inferPeopleCountFromCode(code = '') {
  const normalized = String(code || '').trim()
  const legacy = LEGACY_PLAN_CODE_META[normalized]
  if (legacy?.peopleCount) return Math.max(1, toInteger(legacy.peopleCount, 1))

  const matched = normalized.match(/(\d+)/)
  if (!matched) return null
  const count = toInteger(matched[1], 0)
  if (count < 1) return null
  return count
}

function getDayLabel(dayType = 'weekday') {
  return dayType === 'weekend' ? '周末' : '工作日'
}

function buildUnlimitedLabel(dayType = 'weekday', peopleCount = 1) {
  return `${getDayLabel(dayType)}${Math.max(1, toInteger(peopleCount, 1))}人不限时不限板`
}

function resolveDefaultUnlimitedCode(dayType = 'weekday', peopleCount = 1, index = 1) {
  const legacyMap = LEGACY_DAY_TYPE_TO_PLAN_CODE[dayType] || LEGACY_DAY_TYPE_TO_PLAN_CODE.weekday
  const safePeople = Math.max(1, toInteger(peopleCount, 1))
  if (safePeople === 1) return legacyMap.singleUnlimited
  if (safePeople === 2) return legacyMap.doubleUnlimited
  return `${dayType}Unlimited${safePeople}P${Math.max(1, toInteger(index, 1))}`
}

function normalizeUnlimitedPackages(dayType = 'weekday', rawDayRule = {}) {
  const sourceList = Array.isArray(rawDayRule?.unlimited_packages)
    ? rawDayRule.unlimited_packages
    : cloneDefaultUnlimitedPackages(dayType)

  const mergedList = sourceList.map((item, index) => {
    const rawCode = normalizePackageCode(item?.code)
    const peopleCount = Math.max(
      1,
      toInteger(
        item?.people_count ?? item?.peopleCount ?? inferPeopleCountFromCode(rawCode) ?? (index + 1),
        1
      )
    )
    const fallbackCode = resolveDefaultUnlimitedCode(dayType, peopleCount, index + 1)
    const code = normalizePackageCode(rawCode, fallbackCode) || fallbackCode

    return {
      id: String(item?.id || `${dayType}_pkg_${index + 1}`).trim() || `${dayType}_pkg_${index + 1}`,
      code,
      label: String(item?.label || '').trim() || buildUnlimitedLabel(dayType, peopleCount),
      people_count: peopleCount,
      price: round2(Math.max(0, toNumber(item?.price, 0))),
      enabled: item?.enabled !== false,
      sort_order: toInteger(item?.sort_order ?? item?.sortOrder ?? (index + 1), index + 1)
    }
  })

  const seenCodes = new Set()
  const normalized = mergedList
    .filter((item) => {
      if (!item.code) return false
      if (seenCodes.has(item.code)) return false
      seenCodes.add(item.code)
      return true
    })
    .sort((left, right) => {
      if (left.sort_order !== right.sort_order) return left.sort_order - right.sort_order
      if (left.people_count !== right.people_count) return left.people_count - right.people_count
      return String(left.code).localeCompare(String(right.code), 'en-US')
    })
    .map((item, index) => ({
      ...item,
      sort_order: index + 1
    }))

  if (normalized.length === 0) {
    return cloneDefaultUnlimitedPackages(dayType).map((item, index) => ({
      ...item,
      sort_order: index + 1
    }))
  }

  if (!normalized.some((item) => item.enabled)) {
    normalized[0].enabled = true
  }

  return normalized
}

function normalizeDayRule(dayType = 'weekday', rawDayRule = {}) {
  const source = rawDayRule && typeof rawDayRule === 'object' ? rawDayRule : {}
  const unlimitedPackages = normalizeUnlimitedPackages(dayType, source)

  let singleLimited = toNumber(source.singleLimited, Number.NaN)
  if (!Number.isFinite(singleLimited)) {
    singleLimited = toNumber(
      source.singleLimitedBoard,
      toNumber(DEFAULT_BILLING_RULES[dayType]?.singleLimited, 0)
    )
  }
  singleLimited = round2(Math.max(0, singleLimited))

  const singleUnlimitedPackage = unlimitedPackages.find((item) => item.people_count === 1)
    || unlimitedPackages[0]
  const doubleUnlimitedPackage = unlimitedPackages.find((item) => item.people_count === 2)
    || singleUnlimitedPackage

  return {
    ...source,
    singleLimited,
    singleUnlimited: round2(Math.max(0, toNumber(source.singleUnlimited, singleUnlimitedPackage?.price ?? 0))),
    doubleUnlimited: round2(Math.max(0, toNumber(source.doubleUnlimited, doubleUnlimitedPackage?.price ?? 0))),
    unlimited_packages: unlimitedPackages
  }
}

function isLimited2hPackage(options = {}) {
  const packagePlan = String(options.packagePlan || '').trim()
  if (packagePlan === 'limited2h') return true

  const billingType = String(options.billingType || '').trim()
  const duration = String(options.duration || '').trim()
  return billingType === 'limited' && duration === '2'
}

export function calculateMeituanDeduction(baseAmount, rate = MEITUAN_RATE, options = {}) {
  const safeBase = Math.max(0, toNumber(baseAmount, 0))
  if (isLimited2hPackage(options)) {
    return round2(Math.min(safeBase, 2.5))
  }

  const safeRate = Math.max(0, toNumber(rate, MEITUAN_RATE))
  return round2(safeBase * safeRate)
}

export function applyDeduction(totalAmount, deductionAmount) {
  const safeTotal = Math.max(0, toNumber(totalAmount, 0))
  const safeDeduction = Math.max(0, toNumber(deductionAmount, 0))
  return round2(Math.max(0, safeTotal - safeDeduction))
}

function normalizeDayType(dayType = 'weekday') {
  return dayType === 'weekend' ? 'weekend' : 'weekday'
}

function getDefaultDayUnlimitedPackage(dayRule = {}) {
  const packages = Array.isArray(dayRule?.unlimited_packages) ? dayRule.unlimited_packages : []
  return packages.find((item) => item?.enabled) || packages[0] || null
}

function findDayUnlimitedPackage(dayRule = {}, selector) {
  const packages = Array.isArray(dayRule?.unlimited_packages) ? dayRule.unlimited_packages : []
  return packages.find((item) => selector(item)) || null
}

function buildSingleLimitedPlanMeta(dayType = 'weekday', dayRule = {}) {
  const normalizedDayType = normalizeDayType(dayType)
  const legacyMap = LEGACY_DAY_TYPE_TO_PLAN_CODE[normalizedDayType] || LEGACY_DAY_TYPE_TO_PLAN_CODE.weekday
  const dayLabel = getDayLabel(normalizedDayType)

  return {
    code: legacyMap.singleLimited,
    label: `${dayLabel}单人不限时限板`,
    price: round2(Math.max(0, toNumber(dayRule?.singleLimited, 0))),
    peopleCount: 1,
    timerType: normalizedDayType,
    limited: true,
    enabled: true
  }
}

function buildUnlimitedPlanMeta(dayType = 'weekday', packageItem = {}) {
  const normalizedDayType = normalizeDayType(dayType)
  return {
    code: String(packageItem?.code || '').trim(),
    label: String(packageItem?.label || '').trim() || buildUnlimitedLabel(normalizedDayType, packageItem?.people_count),
    price: round2(Math.max(0, toNumber(packageItem?.price, 0))),
    peopleCount: Math.max(1, toInteger(packageItem?.people_count, 1)),
    timerType: normalizedDayType,
    limited: false,
    enabled: packageItem?.enabled !== false
  }
}

export function resolveDayPlanSelection(dayType = 'weekday', planSelection = '', rawRules = {}, options = {}) {
  const normalizedDayType = normalizeDayType(dayType)
  const rules = normalizeBillingRules(rawRules)
  const dayRule = rules[normalizedDayType] || {}
  const legacyMap = LEGACY_DAY_TYPE_TO_PLAN_CODE[normalizedDayType] || LEGACY_DAY_TYPE_TO_PLAN_CODE.weekday
  const normalizedSelection = String(planSelection || '').trim()
  const includeDisabled = options.includeDisabled !== false

  const pickUnlimitedMeta = (item) => {
    if (!item) return null
    if (!includeDisabled && item.enabled === false) return null
    return buildUnlimitedPlanMeta(normalizedDayType, item)
  }

  if (normalizedSelection === 'singleLimited' || normalizedSelection === legacyMap.singleLimited) {
    return buildSingleLimitedPlanMeta(normalizedDayType, dayRule)
  }

  if (normalizedSelection) {
    const byCode = findDayUnlimitedPackage(dayRule, (item) => String(item?.code || '').trim() === normalizedSelection)
    const matchedByCode = pickUnlimitedMeta(byCode)
    if (matchedByCode) return matchedByCode
  }

  if (normalizedSelection === 'singleUnlimited') {
    const byLegacyCode = findDayUnlimitedPackage(dayRule, (item) => String(item?.code || '').trim() === legacyMap.singleUnlimited)
    const byPeople = findDayUnlimitedPackage(dayRule, (item) => Math.max(1, toInteger(item?.people_count, 1)) === 1)
    return pickUnlimitedMeta(byLegacyCode || byPeople || getDefaultDayUnlimitedPackage(dayRule))
  }

  if (normalizedSelection === 'doubleUnlimited') {
    const byLegacyCode = findDayUnlimitedPackage(dayRule, (item) => String(item?.code || '').trim() === legacyMap.doubleUnlimited)
    const byPeople = findDayUnlimitedPackage(dayRule, (item) => Math.max(1, toInteger(item?.people_count, 1)) === 2)
    return pickUnlimitedMeta(byLegacyCode || byPeople || getDefaultDayUnlimitedPackage(dayRule))
  }

  if (normalizedSelection && normalizedSelection === legacyMap.singleUnlimited) {
    const matched = findDayUnlimitedPackage(dayRule, (item) => String(item?.code || '').trim() === normalizedSelection)
    return pickUnlimitedMeta(matched || getDefaultDayUnlimitedPackage(dayRule))
  }

  if (normalizedSelection && normalizedSelection === legacyMap.doubleUnlimited) {
    const matched = findDayUnlimitedPackage(dayRule, (item) => String(item?.code || '').trim() === normalizedSelection)
    return pickUnlimitedMeta(matched || getDefaultDayUnlimitedPackage(dayRule))
  }

  const fallbackUnlimited = pickUnlimitedMeta(getDefaultDayUnlimitedPackage(dayRule))
  if (fallbackUnlimited) return fallbackUnlimited
  return buildSingleLimitedPlanMeta(normalizedDayType, dayRule)
}

export function getDayUnlimitedPackageOptions(dayType = 'weekday', rawRules = {}, options = {}) {
  const normalizedDayType = normalizeDayType(dayType)
  const rules = normalizeBillingRules(rawRules)
  const dayRule = rules[normalizedDayType] || {}
  const includeDisabled = Boolean(options.includeDisabled)

  return (Array.isArray(dayRule.unlimited_packages) ? dayRule.unlimited_packages : [])
    .filter((item) => includeDisabled || item?.enabled !== false)
    .map((item) => ({
      value: String(item?.code || ''),
      label: String(item?.label || '').trim() || buildUnlimitedLabel(normalizedDayType, item?.people_count),
      peopleCount: Math.max(1, toInteger(item?.people_count, 1)),
      price: round2(Math.max(0, toNumber(item?.price, 0))),
      enabled: item?.enabled !== false
    }))
}

export function getDaySingleLimitedOption(dayType = 'weekday', rawRules = {}) {
  const normalizedDayType = normalizeDayType(dayType)
  const rules = normalizeBillingRules(rawRules)
  const singleLimited = buildSingleLimitedPlanMeta(normalizedDayType, rules[normalizedDayType] || {})
  return {
    value: singleLimited.code,
    label: singleLimited.label,
    peopleCount: singleLimited.peopleCount,
    price: singleLimited.price,
    enabled: true
  }
}

export function resolvePackagePlanInfo(packagePlan = '', rawRules = {}) {
  const normalizedPlan = String(packagePlan || '').trim()
  const rules = normalizeBillingRules(rawRules)

  if (normalizedPlan === 'limited1h') {
    return {
      code: 'limited1h',
      label: '限时1小时',
      price: round2(Math.max(0, toNumber(rules.limited.price1h, 0))),
      timerType: 'limited',
      peopleCount: 1,
      limited: false,
      enabled: true
    }
  }

  if (normalizedPlan === 'limited2h') {
    return {
      code: 'limited2h',
      label: '限时2小时',
      price: round2(Math.max(0, toNumber(rules.limited.price2h, 0))),
      timerType: 'limited',
      peopleCount: 1,
      limited: false,
      enabled: true
    }
  }

  for (const dayType of ['weekday', 'weekend']) {
    const dayRule = rules[dayType] || {}
    const matchedUnlimited = findDayUnlimitedPackage(dayRule, (item) => String(item?.code || '').trim() === normalizedPlan)
    if (matchedUnlimited) {
      return buildUnlimitedPlanMeta(dayType, matchedUnlimited)
    }

    const legacyMap = LEGACY_DAY_TYPE_TO_PLAN_CODE[dayType]
    if (normalizedPlan === legacyMap.singleLimited) {
      return buildSingleLimitedPlanMeta(dayType, dayRule)
    }
  }

  const legacyMeta = LEGACY_PLAN_CODE_META[normalizedPlan]
  if (legacyMeta?.timerType) {
    return resolveDayPlanSelection(legacyMeta.timerType, normalizedPlan, rules, { includeDisabled: true })
  }

  return null
}

export function getPackagePlanLabel(packagePlan = '', rawRules = {}) {
  const info = resolvePackagePlanInfo(packagePlan, rawRules)
  if (info?.label) return info.label
  return '-'
}

export function getPackagePlanPeopleCount(packagePlan = '', rawRules = {}) {
  const info = resolvePackagePlanInfo(packagePlan, rawRules)
  if (info) {
    return Math.max(1, toInteger(info.peopleCount, 1))
  }

  const normalized = String(packagePlan || '').trim()
  if (/double/i.test(normalized)) return 2
  const inferred = inferPeopleCountFromCode(normalized)
  if (inferred) return inferred
  return 1
}

export function getPackagePlanBaseFee(packagePlan = '', rawRules = {}) {
  const info = resolvePackagePlanInfo(packagePlan, rawRules)
  if (!info) return 0
  return round2(Math.max(0, toNumber(info.price, 0)))
}

function normalizeMiscRules(rawMisc = {}) {
  const sourceItems = Array.isArray(rawMisc)
    ? rawMisc
    : Array.isArray(rawMisc?.items)
      ? rawMisc.items
      : []

  const seenNames = new Set()

  const items = sourceItems
    .filter((item) => item && typeof item === 'object')
    .map((item, index) => {
      const name = String(item.name || '').trim()
      const currentStock = Number(item.current_stock)
      const safeStock = Number(item.safe_stock)
      return {
        id: String(item.id || `misc_${index + 1}`).trim() || `misc_${index + 1}`,
        name,
        unit_price: Math.max(0, toNumber(item.unit_price, 0)),
        unit_label: String(item.unit_label || '个').trim() || '个',
        enabled: Boolean(item.enabled),
        current_stock: Number.isFinite(currentStock) && currentStock >= 0 ? currentStock : 0,
        safe_stock: Number.isFinite(safeStock) && safeStock >= 0 ? safeStock : 0,
        low_stock_alert: item.low_stock_alert !== false,
        sort_order: toInteger(item.sort_order, index + 1)
      }
    })
    .filter((item) => {
      if (!item.name) return false
      const key = item.name.toLowerCase()
      if (seenNames.has(key)) return false
      seenNames.add(key)
      return true
    })
    .sort((left, right) => {
      if (left.sort_order !== right.sort_order) return left.sort_order - right.sort_order
      return left.name.localeCompare(right.name, 'zh-CN')
    })
    .map((item, index) => ({
      ...item,
      sort_order: index + 1
    }))

  return { items }
}

export function normalizeBillingRules(raw = {}) {
  const weekday = normalizeDayRule('weekday', raw.weekday || {})
  const weekend = normalizeDayRule('weekend', raw.weekend || {})

  return {
    limited: {
      ...DEFAULT_BILLING_RULES.limited,
      ...(raw.limited || {})
    },
    weekday,
    weekend,
    materials: {
      ...DEFAULT_BILLING_RULES.materials,
      ...(raw.materials || {})
    },
    overtime: {
      ...DEFAULT_BILLING_RULES.overtime,
      ...(raw.overtime || {})
    },
    misc: normalizeMiscRules(raw.misc || DEFAULT_BILLING_RULES.misc)
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

  return getEffectiveBillingDayType(settlementTimestamp || Date.now())
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
  const daySelection = resolveDayPlanSelection(dayType, 'singleUnlimited', rules, { includeDisabled: true })
  const unlimitedFee = round2(Math.max(0, toNumber(daySelection?.price, 0)))
  const dayLabel = String(daySelection?.label || `${getDayLabel(dayType)}单人不限时不限板`)

  if (hasOvertime && unlimitedFee < limitedTotal) {
    return {
      billingType: dayType,
      baseFee: unlimitedFee,
      overtimeFee: 0,
      overtimeMinutes: 0,
      details: [`${dayLabel}(超时后自动最优)`]
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
  const miscSelections = options.miscSelections && typeof options.miscSelections === 'object'
    ? options.miscSelections
    : {}

  const details = []
  let appliedBillingType = billingType
  let baseFee = 0
  let overtimeFee = 0
  let effectiveOvertimeMinutes = inputOvertimeMinutes

  const applyDayPlan = (dayType, selectionValue) => {
    const plan = resolveDayPlanSelection(dayType, selectionValue, rules, { includeDisabled: true })
    appliedBillingType = normalizeDayType(dayType)
    effectiveOvertimeMinutes = 0
    baseFee = Math.max(0, toNumber(plan?.price, 0))
    if (plan?.label) {
      details.push(plan.label)
    }
  }

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
      applyDayPlan('weekday', weekdayType)
    } else {
      applyDayPlan('weekend', weekendType)
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
    applyDayPlan('weekday', weekdayType)
  } else {
    applyDayPlan('weekend', weekendType)
  }

  const materialFee =
    largeImages * toNumber(rules.materials.largeImageFee) +
    extraSmallImages * toNumber(rules.materials.extraSmallImageFee) +
    extraLargeImages * toNumber(rules.materials.extraLargeImageFee)
  let miscFee = 0
  const miscDetails = []

  const enabledMiscItems = Array.isArray(rules.misc?.items)
    ? rules.misc.items.filter((item) => Boolean(item?.enabled))
    : []

  enabledMiscItems.forEach((item) => {
    const quantity = Math.max(0, toInteger(miscSelections[item.id], 0))
    if (quantity <= 0) return

    const lineFee = quantity * toNumber(item.unit_price, 0)
    miscFee += lineFee
    miscDetails.push(`${item.name}x${quantity}`)
  })

  if (largeImages > 0) details.push(`大图${largeImages}张`)
  if (extraSmallImages > 0) details.push(`超量小图${extraSmallImages}张`)
  if (extraLargeImages > 0) details.push(`超量大图${extraLargeImages}张`)
  if (miscDetails.length > 0) details.push(`杂项${miscDetails.join('、')}`)

  if (additionalFee > 0) {
    details.push(`附加费用¥${additionalFee.toFixed(2)}`)
  }

  const total = round2(baseFee + overtimeFee + materialFee + miscFee + additionalFee)

  return {
    billingType: appliedBillingType,
    requestedBillingType: billingType,
    pricingMode,
    baseFee: round2(baseFee),
    overtimeFee: round2(overtimeFee),
    materialFee: round2(materialFee),
    miscFee: round2(miscFee),
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
      miscSelections,
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


