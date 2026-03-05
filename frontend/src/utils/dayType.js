const STORAGE_KEY = 'billing_day_type_override'
const VALID_DAY_TYPES = ['weekday', 'weekend']

function normalizeDayType(value) {
  const text = String(value || '').trim().toLowerCase()
  return VALID_DAY_TYPES.includes(text) ? text : ''
}

function canUseLocalStorage() {
  return typeof window !== 'undefined' && typeof window.localStorage !== 'undefined'
}

export function getManualBillingDayType() {
  if (!canUseLocalStorage()) return ''

  try {
    return normalizeDayType(window.localStorage.getItem(STORAGE_KEY))
  } catch (error) {
    return ''
  }
}

export function setManualBillingDayType(dayType) {
  const normalized = normalizeDayType(dayType)
  if (!canUseLocalStorage()) return normalized

  try {
    if (normalized) {
      window.localStorage.setItem(STORAGE_KEY, normalized)
    } else {
      window.localStorage.removeItem(STORAGE_KEY)
    }
  } catch (error) {
    // Ignore storage write failures and keep app usable.
  }

  return normalized
}

export function getCalendarDayType(dateInput = new Date()) {
  const date = dateInput instanceof Date ? dateInput : new Date(dateInput)

  if (Number.isNaN(date.getTime())) {
    return 'weekday'
  }

  const day = date.getDay()
  return day === 0 || day === 6 ? 'weekend' : 'weekday'
}

export function getEffectiveBillingDayType(dateInput = new Date()) {
  const manualDayType = getManualBillingDayType()
  if (manualDayType) return manualDayType
  return getCalendarDayType(dateInput)
}

export function toggleBillingDayType(currentType) {
  const normalized = normalizeDayType(currentType)
  return normalized === 'weekend' ? 'weekday' : 'weekend'
}
